import os
import subprocess
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user
import httpx
import asyncio
import time

router = APIRouter()

SNMP_REC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../snmp_simulator/data/security_monitor.snmprec"))

def update_snmp_file(metrics, is_attacking=False):
    try:
        lines = [
            f"1.3.6.1.4.1.99999.1.1.0|66|{metrics.get('total_failures', 0)}",
            f"1.3.6.1.4.1.99999.1.2.0|66|{metrics.get('failures_last_hour', 0)}",
            f"1.3.6.1.4.1.99999.1.3.0|66|{metrics.get('active_ips', 0)}",
            f"1.3.6.1.4.1.99999.1.4.0|66|{1 if is_attacking else 0}"
        ]
        with open(SNMP_REC_PATH, "w") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        print(f"Erro ao atualizar SNMP: {e}")

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
                    update_snmp_file(m_resp.json(), is_attacking=True)
            except:
                pass
            await asyncio.sleep(2)
            
        # Final sync and stop attack if it was timeout
        try:
            run_docker_cmd(["exec", "bruteforce_pi", "pkill", "-f", "attack.py"])
            m_resp = await client.get(f"{base_url}/security/metrics", timeout=3.0)
            if m_resp.status_code == 200:
                update_snmp_file(m_resp.json(), is_attacking=False)
        except:
            pass

@router.post("/start")
async def start_bf(config: BFConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if not is_container_running():
        raise HTTPException(status_code=500, detail="Erro: O simulador Datacenter/Bruteforce não está rodando. Por favor, inicie-o na aba de Gerenciamento Docker primeiro.")
        
    if is_attack_running():
        raise HTTPException(status_code=400, detail="A simulação de ataque já está em execução.")
    
    # Prepara o comando para executar o script no background dentro do contêiner já existente
    cmd = [
        "exec", "-d",
        "-e", f"TARGET_URL={config.target_url}",
        "-e", f"LOGIN_TYPE={config.login_type}",
        "-e", "CONCURRENCY=15",
        "bruteforce_pi",
        "sh", "-c", "python attack.py > /tmp/attack.log 2>&1"
    ]
    
    # Limpa logs antigos no contêiner
    run_docker_cmd(["exec", "bruteforce_pi", "sh", "-c", "> /tmp/attack.log"])
    
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
        
    success, msg = run_docker_cmd(["exec", "bruteforce_pi", "pkill", "-f", "attack.py"])
    if success:
        return {"status": "success", "message": "Ataque parado com sucesso."}
    else:
        # Se pkill não encontrou o processo, ele falha com código 1. 
        # Assumimos que o ataque já estava parado.
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
            return response.json()
    except Exception as e:
        return {"error": str(e)}
