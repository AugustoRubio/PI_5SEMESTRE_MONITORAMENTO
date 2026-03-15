import os
import subprocess
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user
import httpx
import asyncio
import time

router = APIRouter()

DOCKER_COMPOSE_EXEC = os.getenv("DOCKER_COMPOSE_EXECUTABLE", "docker compose")

BF_SIMULATOR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../bruteforce_simulator"))
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

def run_compose_command(args_list, env_vars=None):
    docker_env = os.getenv("DOCKER_COMPOSE_EXECUTABLE")
    env_cmd = docker_env.split() if docker_env else []

    commands_to_try = [
        ["docker", "compose"],
        ["docker-compose"],
        ["/usr/local/bin/docker-compose"],
        ["/usr/libexec/docker/cli-plugins/docker-compose"]
    ]
    if env_cmd:
        commands_to_try.insert(0, env_cmd)

    environ = os.environ.copy()
    environ["DOCKER_API_VERSION"] = "1.41"
    if env_vars:
        environ.update(env_vars)

    last_err = None
    for base in commands_to_try:
        try:
            cmd = base + args_list
            result = subprocess.run(cmd, cwd=BF_SIMULATOR_DIR, capture_output=True, text=True, check=True, env=environ)
            return True, result.stdout
        except FileNotFoundError as e:
            last_err = e
            continue
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    raise FileNotFoundError(f"Docker compose não encontrado. Último erro: {last_err}")

class BFConfig(BaseModel):
    target_url: str = "https://10.10.100.4/login"
    login_type: str = "student"
    duration: int = 60 # seconds

async def sync_snmp_task(duration, target_url):
    base_url = target_url.split("/login")[0]
    end_time = time.time() + duration
    
    async with httpx.AsyncClient(verify=False) as client:
        while time.time() < end_time:
            # Check if container is still running
            try:
                success, stdout = run_compose_command(["ps"])
                is_running = success and ("Up" in stdout or "running" in stdout.lower())
                if not is_running:
                    break
            except Exception:
                break
                
            try:
                m_resp = await client.get(f"{base_url}/security/metrics", timeout=3.0)
                if m_resp.status_code == 200:
                    update_snmp_file(m_resp.json(), is_attacking=True)
            except:
                pass
            await asyncio.sleep(2)
            
        # Final sync and stop docker if it was timeout
        try:
            run_compose_command(["down"])
            m_resp = await client.get(f"{base_url}/security/metrics", timeout=3.0)
            if m_resp.status_code == 200:
                update_snmp_file(m_resp.json(), is_attacking=False)
        except:
            pass

@router.post("/start")
async def start_bf(config: BFConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    try:
        success, stdout = run_compose_command(["ps"])
        if success and ("Up" in stdout or "running" in stdout.lower()):
            raise HTTPException(status_code=400, detail="Simulação já em execução.")
    except Exception:
        pass
    
    env_vars = {
        "TARGET_URL": config.target_url,
        "LOGIN_TYPE": config.login_type,
        "CONCURRENCY": "15" # Simula o stress pedindo para 15 threads baterem na intranet simultaneamente
    }
    
    try:
        success, msg = run_compose_command(["up", "-d", "--build"], env_vars=env_vars)
        if not success:
            raise HTTPException(status_code=500, detail=f"Erro ao iniciar simulador Docker: {msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
        
    background_tasks.add_task(sync_snmp_task, config.duration, config.target_url)
    return {"status": "success", "message": f"Ataque de brute force ({config.login_type}) iniciado via Docker."}

@router.post("/stop")
async def stop_bf(current_user: dict = Depends(get_current_user)):
    try:
        success, msg = run_compose_command(["down"])
        if success:
            return {"status": "success", "message": "Sinal de parada enviado ao simulador."}
        else:
            raise HTTPException(status_code=500, detail=f"Erro ao parar o simulador: {msg}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_bf_status(current_user: dict = Depends(get_current_user)):
    is_running = False
    logs = []
    
    try:
        success, stdout = run_compose_command(["ps"])
        is_running = success and ("Up" in stdout or "running" in stdout.lower())
        
        if is_running:
            success_logs, logs_out = run_compose_command(["logs", "--tail=15"])
            if success_logs:
                # Pegar as últimas 15 linhas não-vazias de traz para frente
                lines = [line.strip() for line in logs_out.split('\n') if line.strip()]
                logs = lines[-15:]
                logs.reverse() # Mostrar o mais recente primeiro na interface
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