import os
import subprocess
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user
import httpx
import asyncio
import time
import re
import random

router = APIRouter()

SNMP_REC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../snmp_simulator/data/security_monitor.snmprec"))

def update_snmp_file(metrics, is_attacking=False, fake_ips=None, target_url="Nenhum"):
    ips = []
    # Somente coleta e exibe os IPs se o ataque estiver rodando
    if is_attacking:
        if fake_ips:
            ips = fake_ips
        else:
            # Extrai os IPs únicos das tentativas recentes
            recent = metrics.get('recent_failed_attempts', [])
            ips = list(set([str(att.get('ip', '')) for att in recent if att.get('ip')]))
    
    # Formata separando por quebras de linha (\n) para o Zabbix colocar um embaixo do outro
    ip_str = "\n".join(ips[:10]) if ips else "Nenhum"

    # Converte para hexadecimal, pois o arquivo .snmprec quebra se houver \n no texto puro
    ip_hex = ip_str.encode('utf-8').hex()
    
    target_str = target_url if is_attacking else "Nenhum"

    try:
        lines = [
            "1.3.6.1.2.1.1.5.0|4|Monitoramento de Seguranca Intranet",
            f"1.3.6.1.4.1.99999.1.1.0|66|{metrics.get('total_failures', 0)}",
            f"1.3.6.1.4.1.99999.1.2.0|66|{metrics.get('failures_last_hour', 0)}",
            f"1.3.6.1.4.1.99999.1.3.0|66|{metrics.get('active_ips', 0)}",
            f"1.3.6.1.4.1.99999.1.4.0|66|{1 if is_attacking else 0}",
            # Utilizando tipo 4x (Hex) para permitir o envio da quebra de linha ao Zabbix
            f"1.3.6.1.4.1.99999.1.5.0|4x|{ip_hex}",
            # Novo OID: Enviando o alvo atual (URL)
            f"1.3.6.1.4.1.99999.1.6.0|4|{target_str}"
        ]
        with open(SNMP_REC_PATH, "w") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        print(f"Erro ao atualizar SNMP: {e}")

def get_fake_ips_from_log():
    success, log_out = run_docker_cmd(["exec", "bruteforce_pi", "tail", "-n", "100", "/tmp/attack.log"])
    if success:
        found_ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', log_out)
        # Filtra os IPs para pegar somente os de "internet", ignorando IPs locais
        return list(set([ip for ip in found_ips if not ip.startswith("10.") and not ip.startswith("192.") and ip != "127.0.0.1"]))
    return []

class BFConfig(BaseModel):
    target_url: str = "https://10.10.100.4/login"
    login_type: str = "student"
    duration: int = 60 # seconds

def run_docker_cmd(args_list):
    for base in [["docker"], ["/usr/bin/docker"], ["/usr/local/bin/docker"]]:
        try:
            cmd = base + args_list
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0, result.stdout if result.returncode == 0 else result.stderr
        except FileNotFoundError:
            continue
    return False, "Comando docker não encontrado no PATH."

def is_container_running(container_name="bruteforce_pi"):
    success, out = run_docker_cmd(["inspect", "-f", "{{.State.Running}}", container_name])
    return success and out.strip() == "true"

def is_attack_running(container_name="bruteforce_pi"):
    # grep '[a]ttack.py' impede que o próprio processo do grep seja capturado
    success, out = run_docker_cmd(["exec", container_name, "sh", "-c", "ps | grep '[a]ttack.py'"])
    return success and bool(out.strip())

async def sync_snmp_task(duration, target_url):
    base_url = target_url.split("/login")[0]
    end_time = time.time() + duration
    
    async with httpx.AsyncClient(verify=False) as client:
        while time.time() < end_time:
            if not is_attack_running():
                break
                
            try:
                m_resp = await client.get(f"{base_url}/security/metrics", timeout=3.0)
                if m_resp.status_code == 200:
                    fake_ips = get_fake_ips_from_log()
                    update_snmp_file(m_resp.json(), is_attacking=True, fake_ips=fake_ips, target_url=target_url)
            except:
                pass
            await asyncio.sleep(2)
            
        # Final sync and stop attack if it was timeout
        try:
            run_docker_cmd(["exec", "bruteforce_pi", "pkill", "-f", "attack.py"])
            m_resp = await client.get(f"{base_url}/security/metrics", timeout=3.0)
            if m_resp.status_code == 200:
                update_snmp_file(m_resp.json(), is_attacking=False, fake_ips=None, target_url="Nenhum")
        except:
            pass

@router.post("/start")
async def start_bf(config: BFConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if not is_container_running():
        raise HTTPException(status_code=500, detail="Erro: O simulador Datacenter/Bruteforce não está rodando. Por favor, inicie-o na aba de Gerenciamento Docker primeiro.")
        
    if is_attack_running():
        raise HTTPException(status_code=400, detail="A simulação de ataque já está em execução.")
    
    # Nova lógica do Modo Dinâmico
    if config.login_type.lower() == "dinamico":
        opcoes = [
            ("https://10.10.100.4/login", "student"),
            ("https://10.10.100.4/admin/login", "admin"),
            ("https://10.10.100.4/teacher/login", "teacher")
        ]
        alvo_escolhido = random.choice(opcoes)
        config.target_url = alvo_escolhido[0]
        config.login_type = alvo_escolhido[1]

    # Cabeçalho para enriquecer os logs no Painel
    log_header = (
        f"echo '[*] --- INICIANDO SIMULAÇÃO DE BRUTE FORCE ---' > /tmp/attack.log && "
        f"echo '[*] Alvo/Página Atacada: {config.target_url}' >> /tmp/attack.log && "
        f"echo '[*] Perfil de Usuário: {config.login_type}' >> /tmp/attack.log && "
        f"echo '[*] Status: Os IPs abaixo estão tentando acesso e sendo bloqueados nesta página:' >> /tmp/attack.log && "
    )

    # Prepara o comando para executar o script no background dentro do contêiner já existente
    cmd = [
        "exec", "-d",
        "-e", f"TARGET_URL={config.target_url}",
        "-e", f"LOGIN_TYPE={config.login_type}",
        "-e", "CONCURRENCY=15",
        "bruteforce_pi",
        "sh", "-c", f"{log_header} python attack.py >> /tmp/attack.log 2>&1"
    ]
    
    # Executa o novo ataque
    success, msg = run_docker_cmd(cmd)
    if not success:
        raise HTTPException(status_code=500, detail=f"Erro ao iniciar o script de ataque: {msg}")
        
    background_tasks.add_task(sync_snmp_task, config.duration, config.target_url)
    return {"status": "success", "message": f"Ataque de brute force ({config.login_type}) iniciado via Docker unificado."}

@router.post("/stop")
async def stop_bf(current_user: dict = Depends(get_current_user)):
    if not is_container_running():
        raise HTTPException(status_code=500, detail="Contêiner Docker não está rodando.")
        
    # Adicionado 'sh -c pkill -9' para garantir a morte instantânea do processo
    success, msg = run_docker_cmd(["exec", "bruteforce_pi", "sh", "-c", "pkill -9 -f attack.py"])
    if success:
        return {"status": "success", "message": "Ataque parado com sucesso e CPU liberada."}
    else:
        return {"status": "success", "message": "Nenhum ataque ativo para parar."}


@router.get("/status")
async def get_bf_status(current_user: dict = Depends(get_current_user)):
    is_running = is_attack_running()
    logs = []
    
    if is_running or is_container_running():
        success, out = run_docker_cmd(["exec", "bruteforce_pi", "tail", "-n", "15", "/tmp/attack.log"])
        if success:
            lines = [line.strip() for line in out.split('\n') if line.strip()]
            logs = lines[-15:]
            logs.reverse()
            
    return {"is_running": is_running, "logs": logs}

@router.get("/metrics")
async def get_metrics(target_api: str):
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(f"{target_api}/security/metrics", timeout=3.0)
            data = response.json()
            
            # Intercepta e substitui os IPs locais (192.168.1.1) pelos do log para exibição correta
            fake_ips = get_fake_ips_from_log()
            if fake_ips:
                recent = data.get('recent_failed_attempts', [])
                for i, attempt in enumerate(recent):
                    # Substitui circularmente com os IPs encontrados
                    attempt['ip'] = fake_ips[i % len(fake_ips)]
                    
            return data
    except Exception as e:
        return {"error": str(e)}
