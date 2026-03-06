from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user
import asyncio
import httpx
import time
import random
import os

router = APIRouter()

SNMP_REC_PATH = os.path.join(os.path.dirname(__file__), "../../../snmp_simulator/data/security_monitor.snmprec")

bruteforce_status = {
    "is_running": False,
    "target_url": "",
    "attempts_made": 0,
    "blocked_detected": False,
    "start_time": 0,
    "logs": []
}

class BFConfig(BaseModel):
    target_url: str = "https://10.10.100.4/login"
    login_type: str = "student"
    usernames: list[str] = ["admin", "root", "professor", "aluno", "joao", "maria", "pedro"]
    duration: int = 60 # seconds

def update_snmp_file(metrics, is_attacking=False):
    try:
        # Format: OID|TYPE|VALUE (2 is Integer)
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

async def run_bruteforce(config: BFConfig):
    global bruteforce_status
    bruteforce_status["is_running"] = True
    bruteforce_status["attempts_made"] = 0
    bruteforce_status["blocked_detected"] = False
    bruteforce_status["start_time"] = time.time()
    bruteforce_status["target_url"] = config.target_url
    bruteforce_status["logs"] = [f"Iniciando brute force ({config.login_type}) contra {config.target_url}..."]

    end_time = time.time() + config.duration
    
    # disable SSL verification since internal network might use self-signed certs
    async with httpx.AsyncClient(verify=False) as client:
        while time.time() < end_time and bruteforce_status["is_running"]:
            user = random.choice(config.usernames)
            password = f"senha_{random.randint(100, 999)}"
            
            try:
                # Intranet expects Form data
                response = await client.post(
                    config.target_url,
                    data={"username": user, "password": password, "login_type": config.login_type},
                    follow_redirects=False
                )
                
                bruteforce_status["attempts_made"] += 1
                
                if response.status_code == 302:
                    location = response.headers.get("location", "")
                    if "error=blocked" in location:
                        bruteforce_status["blocked_detected"] = True
                        if "[!] IP BLOQUEADO" not in (bruteforce_status["logs"][0] if bruteforce_status["logs"] else ""):
                            bruteforce_status["logs"].insert(0, f"[!] IP BLOQUEADO pelo sistema após {bruteforce_status['attempts_made']} tentativas.")
                    elif "error=1" in location:
                        bruteforce_status["logs"].insert(0, f"Tentativa falha: {user}:{password}")
                
                if len(bruteforce_status["logs"]) > 10:
                    bruteforce_status["logs"].pop()
                
                # Update SNMP immediately during attack
                base_url = config.target_url.split("/login")[0]
                m_resp = await client.get(f"{base_url}/security/metrics")
                if m_resp.status_code == 200:
                    update_snmp_file(m_resp.json(), is_attacking=True)
                    
            except Exception as e:
                bruteforce_status["logs"].insert(0, f"Erro na conexão: {str(e)}")
            
            # Fast attempts
            await asyncio.sleep(0.2)

    bruteforce_status["is_running"] = False
    # Final sync
    try:
        base_url = config.target_url.split("/login")[0]
        async with httpx.AsyncClient(verify=False) as client:
            m_resp = await client.get(f"{base_url}/security/metrics")
            if m_resp.status_code == 200:
                update_snmp_file(m_resp.json(), is_attacking=False)
    except:
        pass
    bruteforce_status["logs"].insert(0, "Simulação de brute force finalizada.")

@router.post("/start")
async def start_bf(config: BFConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    global bruteforce_status
    if bruteforce_status["is_running"]:
        raise HTTPException(status_code=400, detail="Simulação já em execução.")
    
    background_tasks.add_task(run_bruteforce, config)
    return {"message": f"Ataque de brute force ({config.login_type}) iniciado."}

@router.post("/stop")
async def stop_bf(current_user: dict = Depends(get_current_user)):
    global bruteforce_status
    bruteforce_status["is_running"] = False
    return {"message": "Sinal de parada enviado."}

@router.get("/status")
async def get_bf_status(current_user: dict = Depends(get_current_user)):
    return bruteforce_status

@router.get("/metrics")
async def get_metrics(target_api: str):
    # Proxy to the intranet metrics
    try:
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.get(f"{target_api}/security/metrics")
            return response.json()
    except Exception as e:
        return {"error": str(e)}
