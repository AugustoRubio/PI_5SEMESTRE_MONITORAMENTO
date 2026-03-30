import os
import subprocess
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth import get_current_user

router = APIRouter()

class TrafficConfig(BaseModel):
    target_ip: str = "192.168.1.100"
    target_user: str = "ubuntu"
    target_pass: str = "senha"

def run_docker_cmd(args_list):
    for base in [["docker"], ["/usr/bin/docker"], ["/usr/local/bin/docker"]]:
        try:
            cmd = base + args_list
            result = subprocess.run(cmd, capture_output=True, text=True)
            return result.returncode == 0, result.stdout if result.returncode == 0 else result.stderr
        except FileNotFoundError:
            continue
    return False, "Comando docker não encontrado no PATH."

def is_container_running(container_name="web_traffic_bot"):
    success, out = run_docker_cmd(["inspect", "-f", "{{.State.Running}}", container_name])
    return success and out.strip() == "true"

def is_bot_running(container_name="web_traffic_bot"):
    # Verifica se o simulator.py está rodando dentro do container
    success, out = run_docker_cmd(["exec", container_name, "sh", "-c", "ps -ef | grep '[s]imulator.py'"])
    return success and bool(out.strip())

@router.post("/start")
async def start_traffic(config: TrafficConfig, current_user: dict = Depends(get_current_user)):
    if not is_container_running():
        raise HTTPException(status_code=500, detail="Erro: O contêiner web_traffic_bot não está rodando. Suba ele primeiro com docker-compose.")
        
    if is_bot_running():
        raise HTTPException(status_code=400, detail="O bot de tráfego já está em execução na máquina destino.")
    
    # Prepara o comando para executar o script de SSH em background dentro do container
    cmd = [
        "exec", "-d",
        "-e", f"TARGET_IP={config.target_ip}",
        "-e", f"TARGET_USER={config.target_user}",
        "-e", f"TARGET_PASS={config.target_pass}",
        "web_traffic_bot",
        "sh", "-c", "python -u /app/simulator.py > /tmp/traffic.log 2>&1"
    ]
    
    success, msg = run_docker_cmd(cmd)
    if not success:
        raise HTTPException(status_code=500, detail=f"Erro ao iniciar o script de tráfego: {msg}")
        
    return {"status": "success", "message": f"Bot iniciado! Enviando comandos SSH para {config.target_ip}."}

@router.post("/stop")
async def stop_traffic(current_user: dict = Depends(get_current_user)):
    if not is_container_running():
        raise HTTPException(status_code=500, detail="Contêiner Docker não está rodando.")
        
    # Mata o processo do Python que está segurando a conexão SSH
    success, msg = run_docker_cmd(["exec", "web_traffic_bot", "sh", "-c", "pkill -9 -f simulator.py"])
    if success:
        return {"status": "success", "message": "Bot parado. Conexão SSH encerrada."}
    else:
        return {"status": "success", "message": "Nenhum bot ativo para parar."}

@router.get("/status")
async def get_traffic_status(current_user: dict = Depends(get_current_user)):
    is_running = is_bot_running()
    logs = []
    
    if is_running or is_container_running():
        success, out = run_docker_cmd(["exec", "web_traffic_bot", "tail", "-n", "15", "/tmp/traffic.log"])
        if success:
            logs = [line.strip() for line in out.split('\n') if line.strip()]
            logs.reverse() # Mostra os logs mais recentes no topo
            
    return {"is_running": is_running, "logs": logs}
