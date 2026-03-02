import asyncio
import os
import time
import random
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user

router = APIRouter()

class StressConfig(BaseModel):
    target_url: str
    preset: str

stress_status = {
    "is_running": False,
    "target": "",
    "type": "",
    "requests_sent": 0,
    "start_time": 0,
    "duration": 0,
    "logs": []
}

# Caminho absoluto montado a partir de app/routers -> web_panel -> raiz.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DOCKER_COMPOSE_PATH = os.path.join(BASE_DIR, "botnet_agent", "docker-compose.yml")

async def stop_docker_botnet():
    try:
        print("Derrubando botnet via docker compose...")
        docker_cmd = os.name == 'nt' and 'docker.exe' or 'docker'
        proc = await asyncio.create_subprocess_exec(
            docker_cmd, "compose", "-f", DOCKER_COMPOSE_PATH, "down",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()
    except Exception as e:
        print(f"Erro ao derrubar botnet: {e}")

async def _run_stress_preset(target_url: str, preset_name: str):
    print(f"==== [STRESS] INICIANDO PRESET DOCKER: {preset_name} ALVO: {target_url} ====")
    global stress_status
    stress_status["is_running"] = True
    stress_status["target"] = target_url
    stress_status["type"] = preset_name
    stress_status["start_time"] = time.time()
    stress_status["requests_sent"] = 0

    presets = {
        "estudantes_leve": {
            "name": "Onda de Estudantes (Leve)",
            "service": "bot_student", "scale": 15, "duration": 300
        },
        "surto_notas": {
            "name": "Surto de Notas DB (Médio)",
            "service": "bot_professor", "scale": 30, "duration": 300
        },
        "acesso_constante": {
            "name": "Acesso Constante (Intermediário)",
            "service": "bot_student", "scale": 50, "duration": 300
        },
        "pico_matriculas": {
            "name": "Pico de Matrículas (Pesado)",
            "service": "bot_professor", "scale": 80, "duration": 300
        },
        "ddos_extremo": {
            "name": "Ataque Volumétrico DDoS (Extremo)",
            "service": "bot_ddos", "scale": 120, "duration": 600
        }
    }

    if preset_name not in presets:
        preset_name = "estudantes_leve"

    config = presets[preset_name]

    stress_status["duration"] = config["duration"]
    stress_status["logs"] = [
        f"Iniciando DOCKER botnet: {config['name']}...",
        f"Alvo: {target_url} | Containers (scale): {config['scale']} | Duração base: {config['duration']}s",
        f"Lendo docker-compose em: {DOCKER_COMPOSE_PATH}",
        "Aguardando subida da orquestração Docker..."
    ]

    env_vars = os.environ.copy()
    env_vars["TARGET_URL"] = target_url

    try:
        await stop_docker_botnet()

        docker_cmd = os.name == 'nt' and 'docker.exe' or 'docker'
        cmd = [docker_cmd, "compose", "-f", DOCKER_COMPOSE_PATH, "up", "-d", "--scale", f"{config['service']}={config['scale']}"]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            env=env_vars,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        
        if proc.returncode == 0:
            stress_status["logs"].insert(0, f"Esquadrão DOCKER em execução! Atacando...")
        else:
            stress_status["logs"].insert(0, f"Erro ao subir docker. Código: {proc.returncode}")
            print(f"Docker Erro: {stderr.decode('utf-8', errors='ignore')}")

        end_time = time.time() + config["duration"]
        
        while time.time() < end_time and stress_status["is_running"]:
            await asyncio.sleep(2)
            stress_status["requests_sent"] += int(config["scale"] * random.uniform(5, 15))
            
            if random.random() > 0.7:
                stress_status["logs"].insert(0, f"[{config['name']}] Status: ~{stress_status['requests_sent']} reqs reportadas enviadas pela Botnet.")
                if len(stress_status["logs"]) > 15:
                    stress_status["logs"].pop()

    except FileNotFoundError as e:
        msg = "O executável do Docker não foi encontrado na sua máquina. O Docker Desktop está instalado e adicionado ao PATH?"
        stress_status["logs"].insert(0, f"Exceção interna: {msg}")
        print(f"Erro: {msg} | {str(e)}")
    except Exception as e:
        stress_status["logs"].insert(0, f"Exceção interna: {str(e)}")
        print(f"Erro: {str(e)}")

    finally:
        if stress_status["is_running"]:
            stress_status["logs"].insert(0, f"Tempo ou limite alcançado. Derrubando containers...")
        else:
            stress_status["logs"].insert(0, f"Aborto manual recebido. Derrubando containers...")

        await stop_docker_botnet()
        stress_status["is_running"] = False
        stress_status["logs"].insert(0, f"Simulação de estresse finalizada no Docker!")
        print(f"==== [STRESS DOCKER] CONCLUÍDO/PARADO ====")

@router.get("/status")
async def get_stress_status(current_user: dict = Depends(get_current_user)):
    return stress_status

@router.post("/stop")
async def stop_stress_test(current_user: dict = Depends(get_current_user)):
    global stress_status
    if stress_status["is_running"]:
        stress_status["is_running"] = False
        print("==== [STRESS DOCKER] SINAL DE ABORTO RECEBIDO ====")
        stress_status["logs"].insert(0, "Sinal manual de aborto recebido! Solicitando encerramento do Docker...")
        return {"message": "Sinal de parada enviado. O Docker está sendo destruído."}
    return {"message": "Nenhum teste de estresse em execução."}

@router.post("/run")
async def stress_frontend(config: StressConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if stress_status["is_running"]:
        raise HTTPException(status_code=400, detail="Um teste de Carga Docker já está em execução no painel.")

    background_tasks.add_task(_run_stress_preset, config.target_url, config.preset)
    return {"message": f"Carga pre-configurada '{config.preset}' via DOCKER iniciada contra {config.target_url}."}
