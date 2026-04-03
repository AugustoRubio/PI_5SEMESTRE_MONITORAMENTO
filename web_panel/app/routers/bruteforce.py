import os
import asyncio
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user
import httpx
import time
import re
import random

router = APIRouter()

SNMP_REC_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../snmp_simulator/data/security_monitor.snmprec"))

async def run_docker_cmd_async(args_list):
    """Executa comando docker de forma assíncrona."""
    for base_cmd in ["docker", "/usr/bin/docker", "/usr/local/bin/docker"]:
        try:
            proc = await asyncio.create_subprocess_exec(
                base_cmd, *args_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode == 0, stdout.decode().strip() if proc.returncode == 0 else stderr.decode().strip()
        except FileNotFoundError:
            continue
    return False, "Comando docker não encontrado."

async def write_snmp_file_async(lines):
    def _sync_write():
        with open(SNMP_REC_PATH, "w") as f:
            f.write("\n".join(lines) + "\n")
    await asyncio.to_thread(_sync_write)

async def update_snmp_file(metrics, is_attacking=False, fake_ips=None, target_url="Nenhum"):
    ips = []
    if is_attacking:
        if fake_ips:
            ips = fake_ips
        else:
            recent = metrics.get('recent_failed_attempts', [])
            ips = list(set([str(att.get('ip', '')) for att in recent if att.get('ip')]))
    
    ip_str = ", ".join(ips[:10]) if ips else "Nenhum"
    top_users = metrics.get('top_users', [])
    top_users_str = ", ".join(top_users) if (is_attacking and top_users) else "Nenhum"
    target_str = target_url if is_attacking else "Nenhum"

    lines = [
        "1.3.6.1.2.1.1.5.0|4|Monitoramento de Seguranca Intranet",
        f"1.3.6.1.4.1.99999.1.1.0|66|{metrics.get('total_failures') or 0}",
        f"1.3.6.1.4.1.99999.1.2.0|66|{metrics.get('failures_last_hour') or 0}",
        f"1.3.6.1.4.1.99999.1.3.0|66|{metrics.get('active_ips') or 0}",
        f"1.3.6.1.4.1.99999.1.4.0|66|{1 if is_attacking else 0}",
        f"1.3.6.1.4.1.99999.1.5.0|4|{ip_str}",
        f"1.3.6.1.4.1.99999.1.6.0|4|{target_str}",
        f"1.3.6.1.4.1.99999.1.7.0|4|{top_users_str}"
    ]
    await write_snmp_file_async(lines)

async def get_attack_target_from_log():
    success, log_out = await run_docker_cmd_async(["exec", "bruteforce_pi", "sh", "-c", "grep 'Alvo/Página Atacada:' /tmp/attack.log | tail -n 1"])
    if success and log_out.strip():
        return log_out.split("Atacada: ")[-1].strip()
    return "Nenhum"

async def get_fake_ips_from_log():
    success, log_out = await run_docker_cmd_async(["exec", "bruteforce_pi", "tail", "-n", "100", "/tmp/attack.log"])
    if success:
        found_ips = re.findall(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b', log_out)
        return list(set([ip for ip in found_ips if not ip.startswith("10.") and not ip.startswith("192.") and ip != "127.0.0.1"]))
    return []

class BFConfig(BaseModel):
    target_url: str = "https://10.10.100.4/login"
    login_type: str = "student"
    duration: int = 60

async def is_container_running(container_name="bruteforce_pi"):
    success, out = await run_docker_cmd_async(["inspect", "-f", "{{.State.Running}}", container_name])
    return success and out.strip() == "true"

async def is_attack_running(container_name="bruteforce_pi"):
    success, out = await run_docker_cmd_async(["exec", container_name, "sh", "-c", "ps | grep '[a]ttack.py'"])
    return success and bool(out.strip())

async def sync_snmp_task(duration, target_url):
    parts = target_url.split('/')
    base_url = f"{parts[0]}//{parts[2]}"
    end_time = time.time() + duration
    
    async with httpx.AsyncClient(verify=False) as client:
        while time.time() < end_time:
            if not await is_attack_running():
                break
            try:
                m_resp = await client.get(f"{base_url}/security/metrics", timeout=3.0)
                if m_resp.status_code == 200:
                    fake_ips = await get_fake_ips_from_log()
                    await update_snmp_file(m_resp.json(), is_attacking=True, fake_ips=fake_ips, target_url=target_url)
            except:
                pass
            await asyncio.sleep(2)
            
        try:
            await run_docker_cmd_async(["exec", "bruteforce_pi", "pkill", "-f", "attack.py"])
            m_resp = await client.get(f"{base_url}/security/metrics", timeout=3.0)
            if m_resp.status_code == 200:
                await update_snmp_file(m_resp.json(), is_attacking=False, fake_ips=None, target_url="Nenhum")
        except:
            pass

@router.post("/start")
async def start_bf(config: BFConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if not await is_container_running():
        raise HTTPException(status_code=500, detail="Erro: Contêiner não está rodando.")
        
    if await is_attack_running():
        raise HTTPException(status_code=400, detail="Ataque já em execução.")
    
    if config.login_type.lower() == "dinamico":
        opcoes = [
            ("https://10.10.100.4/login?type=student", "student"),
            ("https://10.10.100.4/login?type=admin", "admin"),
            ("https://10.10.100.4/login?type=professor", "professor")
        ]
        alvo_escolhido = random.choice(opcoes)
        config.target_url, config.login_type = alvo_escolhido[0], alvo_escolhido[1]

    log_header = (
        f"echo '[*] --- INICIANDO SIMULAÇÃO DE BRUTE FORCE ---' > /tmp/attack.log && "
        f"echo '[*] Alvo/Página Atacada: {config.target_url}' >> /tmp/attack.log && "
    )

    cmd = [
        "exec", "-d",
        "-e", f"TARGET_URL={config.target_url}",
        "-e", f"LOGIN_TYPE={config.login_type}",
        "-e", "CONCURRENCY=15",
        "bruteforce_pi",
        "sh", "-c", f"{log_header} python attack.py >> /tmp/attack.log 2>&1"
    ]
    
    success, msg = await run_docker_cmd_async(cmd)
    if not success:
        raise HTTPException(status_code=500, detail=f"Erro ao iniciar ataque: {msg}")
        
    background_tasks.add_task(sync_snmp_task, config.duration, config.target_url)
    return {"status": "success", "message": "Ataque iniciado com sucesso."}

@router.post("/stop")
async def stop_bf(current_user: dict = Depends(get_current_user)):
    if not await is_container_running():
        raise HTTPException(status_code=500, detail="Contêiner não está rodando.")
    success, msg = await run_docker_cmd_async(["exec", "bruteforce_pi", "sh", "-c", "pkill -9 -f attack.py"])
    return {"status": "success", "message": "Ataque interrompido."}

@router.get("/status")
async def get_bf_status(current_user: dict = Depends(get_current_user)):
    is_running = await is_attack_running()
    logs = []
    if is_running or await is_container_running():
        success, out = await run_docker_cmd_async(["exec", "bruteforce_pi", "tail", "-n", "15", "/tmp/attack.log"])
        if success:
            logs = [line.strip() for line in out.split('\n') if line.strip()]
            logs.reverse()
    return {"is_running": is_running, "logs": logs}
