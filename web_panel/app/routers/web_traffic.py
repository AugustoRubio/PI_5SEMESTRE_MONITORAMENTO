import os
import subprocess
import tempfile
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth import get_current_user

router = APIRouter()

class TrafficConfig(BaseModel):
    target_ip: str = "192.168.1.100"
    target_user: str = "ubuntu"
    target_pass: str = "senha"

class URLsConfig(BaseModel):
    urls: str

# Caminho absoluto para o arquivo urls.txt que fica fora da pasta do painel web
URLS_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../web_traffic_simulator/urls.txt"))

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
    docker_running = is_container_running()
    is_running = is_bot_running()
    logs = []
    
    if is_running or docker_running:
        success, out = run_docker_cmd(["exec", "web_traffic_bot", "tail", "-n", "20", "/tmp/traffic.log"])
        if success:
            logs = [line.strip() for line in out.split('\n') if line.strip()]
            
    return {
        "is_docker_running": docker_running,
        "is_running": is_running, 
        "logs": logs
    }

@router.get("/urls")
async def get_urls(current_user: dict = Depends(get_current_user)):
    try:
        with open(URLS_FILE_PATH, "r", encoding="utf-8") as f:
            return {"urls": f.read()}
    except FileNotFoundError:
        return {"urls": ""}

@router.post("/urls")
async def save_urls(config: URLsConfig, current_user: dict = Depends(get_current_user)):
    try:
        os.makedirs(os.path.dirname(URLS_FILE_PATH), exist_ok=True)
        with open(URLS_FILE_PATH, "w", encoding="utf-8") as f:
            f.write(config.urls)
            
        if is_container_running():
            with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8') as tmp:
                tmp.write(config.urls)
                tmp_path = tmp.name
            run_docker_cmd(["cp", tmp_path, "web_traffic_bot:/app/urls.txt"])
            os.remove(tmp_path)
            
        return {"status": "success", "message": "Lista de URLs salva e injetada no simulador com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar URLs: {str(e)}")
