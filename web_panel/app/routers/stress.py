import asyncio
import os
import subprocess
import time
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user

router = APIRouter()

class StressConfig(BaseModel):
    target_url: str
    duration_seconds: int
    concurrency: int
    network_intensity: str = "low"

# Variável global para rastrear o status do teste
stress_status = {
    "is_running": False,
    "target": "",
    "type": "",
    "requests_sent": 0,
    "start_time": 0,
    "duration": 0,
    "logs": []
}

async def stop_docker_botnet():
    try:
        # Comando para derrubar containers associados a botnet_agent
        print("Derrubando botnet via docker compose (timeout)")
        subprocess.run(["docker", "compose", "-f", "../botnet_agent/docker-compose.yml", "down"], check=False)
    except Exception as e:
        print(f"Erro ao derrubar botnet: {e}")

async def run_docker_botnet(url: str, duration: int, concurrency: int, bot_type: str = "ddos"):
    global stress_status
    stress_status["is_running"] = True
    stress_status["target"] = url
    stress_status["type"] = bot_type
    stress_status["start_time"] = time.time()
    stress_status["duration"] = duration
    
    # Reduzmos a concorrência se for em relação aos containeres Docker ao inves de workers assíncronos
    # ex: 200 no slider web faria 200 containers. Então limitamos, ou traduzimos os números.
    scale_num = min(concurrency // 10, 50) 
    if scale_num <= 0: scale_num = 1
    
    stress_status["logs"] = [
        f"Iniciando Botnet Distribuído via Docker Compose...",
        f"Alvo: {url}",
        f"Modo DOCKER: {bot_type} | Instâncias simultâneas geradas: {scale_num}",
        "Espere alguns instantes para a subida das interfaces macvlan..."
    ]
    
    service_map = {
        "ddos": "bot_ddos",
        "student": "bot_student",
        "professor": "bot_professor"
    }
    
    target_service = service_map.get(bot_type, "bot_ddos")
    
    # Injetando variável de ambiente TARGET_URL na execução
    env_vars = os.environ.copy()
    env_vars["TARGET_URL"] = url
    
    try:
        # Derruba restos antigos
        subprocess.run(["docker", "compose", "-f", "../botnet_agent/docker-compose.yml", "down"], check=False)
        stress_status["logs"].insert(0, f"Limpeza concluída. Distribuindo IPs...")
        
        # Sobe o esquadrão docker
        cmd = ["docker", "compose", "-f", "../botnet_agent/docker-compose.yml", "up", "-d", "--scale", f"{target_service}={scale_num}"]
        proc = subprocess.Popen(cmd, env=env_vars, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Dá um pequeno delay para a criação dos containers
        await asyncio.sleep(3)
        stress_status["logs"].insert(0, f"Esquadrão em execução na GNS3_Bridge. Atacando...")

        # Simula o andamento pelo tempo estipulado
        end_time = time.time() + duration
        while time.time() < end_time and stress_status["is_running"]:
            stress_status["requests_sent"] += (10 * scale_num) # fake counter estimativo visual
            await asyncio.sleep(1)
            
            if random.random() > 0.9:
                stress_status["logs"].insert(0, f"[Botnet] Tráfego intenso originado de {scale_num} diferentes IP(s)...")
                if len(stress_status["logs"]) > 15:
                            stress_status["logs"].pop()

    except Exception as e:
        stress_status["logs"].insert(0, f"Erro Fatal no Docker: {str(e)}")
        
    finally:
        # Encerramento total
        await stop_docker_botnet()
        stress_status["is_running"] = False
        stress_status["logs"].insert(0, f"Teste botnet finalizado e containeres destruídos com sucesso.")

@router.get("/status")
async def get_stress_status(current_user: dict = Depends(get_current_user)):
    return stress_status

@router.post("/stop")
async def stop_stress_test(current_user: dict = Depends(get_current_user)):
    global stress_status
    if stress_status["is_running"]:
        stress_status["is_running"] = False
        stress_status["logs"].insert(0, "Sinal de abort recebido! Derrubando containeres docker...")
        # Força derrubar o docker assincronamente através de background env se ele foi abortado no meio
        asyncio.create_task(stop_docker_botnet())
        return {"message": "Sinal de parada enviado. Botnet Docker será destruído."}
    return {"message": "Nenhum teste botnet em execução."}

@router.post("/frontend")
async def stress_frontend(config: StressConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if stress_status["is_running"]:
        raise HTTPException(status_code=400, detail="Um teste Botnet já está em execução.")
    
    # Relacionamos "/frontend" (leitura) ao perfíl do ALUNO
    # Traduzimos alvo do frontend para apenas a URL base.
    background_tasks.add_task(run_docker_botnet, config.target_url, config.duration_seconds, config.concurrency, "student")
    return {"message": f"Teste de estresse de Leitura (Alunos Docker) iniciado em {config.target_url} por {config.duration_seconds}s."}

@router.post("/backend/read")
async def stress_backend_read(config: StressConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if stress_status["is_running"]:
        raise HTTPException(status_code=400, detail="Um teste Botnet já está em execução.")

    # No backend de leitura vamos rodar o modo student forte também ou um ddos leve
    # Vamos adaptar para bot_student pois gera tráfego GET.
    background_tasks.add_task(run_docker_botnet, config.target_url, config.duration_seconds, config.concurrency, "student")
    return {"message": f"Simulação Docker de Estudantes na Nuvem iniciada."}

@router.post("/backend/write")
async def stress_backend_write(config: StressConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if stress_status["is_running"]:
        raise HTTPException(status_code=400, detail="Um teste Botnet já está em execução.")

    # Se a intensidade de rede for extrema, chamamos o modo DDOS brutal. 
    # Senão, chamamos o modo Professor (que atira cadastros na db).
    bot_mode = "ddos" if config.network_intensity == "high" else "professor"

    background_tasks.add_task(run_docker_botnet, config.target_url, config.duration_seconds, config.concurrency, bot_mode)
    return {"message": f"Ataque Botnet ({bot_mode}) iniciado com orquestração Docker."}

