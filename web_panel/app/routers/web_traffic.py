import os
import asyncio
import tempfile
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from app.auth import get_current_user

router = APIRouter()

class TrafficConfig(BaseModel):
    target_ip: str = "10.10.2.253"
    target_user: str = "ubuntu"
    target_pass: str = "senha"

class URLsConfig(BaseModel):
    urls: str

# Caminho absoluto para o arquivo urls.txt que fica fora da pasta do painel web
URLS_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../web_traffic_simulator/urls.txt"))
SIMULATOR_FILE_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../web_traffic_simulator/simulator.py"))

async def run_docker_cmd_async(args_list):
    """Executa comando docker de forma assíncrona para não travar o painel."""
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
        except Exception as e:
            return False, str(e)
    return False, "Comando docker não encontrado."

async def is_container_running(container_name="web_traffic_bot"):
    success, out = await run_docker_cmd_async(["inspect", "-f", "{{.State.Running}}", container_name])
    return success and out.strip() == "true"

async def is_bot_running(container_name="web_traffic_bot"):
    # Verifica se o simulator.py está rodando dentro do container
    success, out = await run_docker_cmd_async(["exec", container_name, "sh", "-c", "ps -ef | grep '[s]imulator.py'"])
    return success and bool(out.strip())

@router.post("/start")
async def start_traffic(config: TrafficConfig, current_user: dict = Depends(get_current_user)):
    if not await is_container_running():
        raise HTTPException(status_code=500, detail="Erro: O contêiner web_traffic_bot não está rodando. Vá até a aba Gerenciamento Docker e inicie os Simuladores Unificados.")
        
    if await is_bot_running():
        raise HTTPException(status_code=400, detail="O bot de tráfego já está em execução na máquina destino.")
    
    # Atualiza o script e a lista de URLs no container antes de rodar
    if os.path.exists(SIMULATOR_FILE_PATH):
        await run_docker_cmd_async(["cp", SIMULATOR_FILE_PATH, "web_traffic_bot:/app/simulator.py"])
    if os.path.exists(URLS_FILE_PATH):
        await run_docker_cmd_async(["cp", URLS_FILE_PATH, "web_traffic_bot:/app/urls.txt"])

    # Prepara o comando para executar o script de SSH em background dentro do container
    cmd = [
        "exec", "-d",
        "-e", f"TARGET_IP={config.target_ip}",
        "-e", f"TARGET_USER={config.target_user}",
        "-e", f"TARGET_PASS={config.target_pass}",
        "web_traffic_bot",
        "sh", "-c", "python -u /app/simulator.py > /tmp/traffic.log 2>&1"
    ]
    
    success, msg = await run_docker_cmd_async(cmd)
    if not success:
        raise HTTPException(status_code=500, detail=f"Erro ao iniciar o script de tráfego: {msg}")
        
    return {"status": "success", "message": f"Bot iniciado! Enviando comandos SSH para {config.target_ip}."}

@router.post("/stop")
async def stop_traffic(current_user: dict = Depends(get_current_user)):
    if not await is_container_running():
        raise HTTPException(status_code=500, detail="Contêiner Docker não está rodando.")
        
    # Mata o processo do Python que está segurando a conexão SSH
    success, msg = await run_docker_cmd_async(["exec", "web_traffic_bot", "sh", "-c", "pkill -9 -f simulator.py"])
    if success:
        return {"status": "success", "message": "Bot parado. Conexão SSH encerrada."}
    else:
        return {"status": "success", "message": "Nenhum bot ativo para parar."}

@router.get("/status")
async def get_traffic_status(current_user: dict = Depends(get_current_user)):
    docker_running = await is_container_running()
    is_running = await is_bot_running()
    logs = []
    
    if is_running or docker_running:
        success, out = await run_docker_cmd_async(["exec", "web_traffic_bot", "tail", "-n", "150", "/tmp/traffic.log"])
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
            
        if await is_container_running():
            with tempfile.NamedTemporaryFile(delete=False, mode='w', encoding='utf-8') as tmp:
                tmp.write(config.urls)
                tmp_path = tmp.name
            await run_docker_cmd_async(["cp", tmp_path, "web_traffic_bot:/app/urls.txt"])
            os.remove(tmp_path)
            
        return {"status": "success", "message": "Lista de URLs salva e injetada no simulador com sucesso!"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao salvar URLs: {str(e)}")
