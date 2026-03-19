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
            f"1.3.6.1.4.1.99999.1.1.0|2|{metrics.get('total_failures', 0)}",
            f"1.3.6.1.4.1.99999.1.2.0|2|{metrics.get('failures_last_hour', 0)}",
            f"1.3.6.1.4.1.99999.1.3.0|2|{metrics.get('active_ips', 0)}",
            f"1.3.6.1.4.1.99999.1.4.0|2|{1 if is_attacking else 0}"
        ]
        with open(SNMP_REC_PATH, "w") as f:
            f.write("\n".join(lines) + "\n")
    except Exception as e:
        print(f"Erro ao atualizar SNMP: {e}")

class BFConfig(BaseModel):
    target_url: str = "https://10.10.100.4/login"
    login_type: str = "student"
    duration: int = 60 # seconds

def is_container_running(container_name="bruteforce_pi"):
    try:
        result = subprocess.run(["docker", "inspect", "-f", "{{.State.Running}}", container_name], capture_output=True, text=True)
        return result.stdout.strip() == "true"
    except Exception:
        return False

def is_attack_running(container_name="bruteforce_pi"):
    try:
        result = subprocess.run(["docker", "exec", container_name, "pgrep", "-f", "attack.py"], capture_output=True, text=True)
        return bool(result.stdout.strip())
    except Exception:
        return False

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
            subprocess.run(["docker", "exec", "bruteforce_pi", "pkill", "-f", "attack.py"], capture_output=True)
            m_resp = await client.get(f"{base_url}/security/metrics", timeout=3.0)
            if m_resp.status_code == 200:
                update_snmp_file(m_resp.json(), is_attacking=False)
        except:
            pass

@router.post("/start")
async def start_bf(config: BFConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if not is_container_running():
        raise HTTPException(status_code=500, detail="Erro: O simulador não está ligado. Por favor, inicie o Docker na aba de Gerenciamento Docker primeiro.")
        
    if is_attack_running():
        raise HTTPException(status_code=400, detail="A simulação de ataque já está em execução.")
    
    # Prepara o comando para executar o script no background dentro do contêiner já existente
    cmd = [
        "docker", "exec", "-d",
        "-e", f"TARGET_URL={config.target_url}",
        "-e", f"LOGIN_TYPE={config.login_type}",
        "-e", "CONCURRENCY=15",
        "bruteforce_pi",
        "sh", "-c", "python attack.py > /tmp/attack.log 2>&1"
    ]
    
    try:
        # Limpa logs antigos
        subprocess.run(["docker", "exec", "bruteforce_pi", "sh", "-c", "> /tmp/attack.log"], capture_output=True, check=False)
        # Executa o novo ataque
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Erro ao iniciar o script de ataque: {e.stderr}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro de conexão com o docker: {str(e)}")
        
    background_tasks.add_task(sync_snmp_task, config.duration, config.target_url)
    return {"status": "success", "message": f"Ataque de brute force ({config.login_type}) iniciado via Docker unificado."}

@router.post("/stop")
async def stop_bf(current_user: dict = Depends(get_current_user)):
    if not is_container_running():
        raise HTTPException(status_code=500, detail="Contêiner não está rodando.")
        
    try:
        # Mata o processo do Python que roda o ataque
        subprocess.run(["docker", "exec", "bruteforce_pi", "pkill", "-f", "attack.py"], capture_output=True, text=True)
        return {"status": "success", "message": "Ataque parado com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_bf_status(current_user: dict = Depends(get_current_user)):
    is_running = is_attack_running()
    logs = []
    
    if is_running or is_container_running():
        try:
            result = subprocess.run(["docker", "exec", "bruteforce_pi", "tail", "-n", "15", "/tmp/attack.log"], capture_output=True, text=True)
            if result.returncode == 0:
                lines = [line.strip() for line in result.stdout.split('\n') if line.strip()]
                logs = lines[-15:]
                logs.reverse()
        except Exception:
            pass
            
    return {"is_running": is_running, "logs": logs}

@router.get("/metrics")
async def get_metrics(target_api: str):
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(f"{target_api}/security/metrics", timeout=3.0)
            return response.json()
    except Exception as e:
        return {"error": str(e)}