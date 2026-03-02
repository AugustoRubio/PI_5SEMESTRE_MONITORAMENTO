import asyncio
import os
import time
import httpx
import random
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user

router = APIRouter()

class StressConfig(BaseModel):
    target_url: str
    preset: str

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

async def worker(target_url: str, stop_event: asyncio.Event, payload_size: int, is_post: bool):
    global stress_status
    
    # Gere um payload grande com caracteres dummy se necessário
    payload_data = b"A" * payload_size if is_post and payload_size > 0 else None
    
    async with httpx.AsyncClient(verify=False, timeout=3.0) as client:
        while not stop_event.is_set():
            try:
                if is_post:
                    await client.post(target_url, content=payload_data)
                else:
                    await client.get(target_url)
                stress_status["requests_sent"] += 1
            except Exception:
                # Ignoramos erros para evitar sobrecarga de logs durante flood e continuar atacando
                pass
            
            # Pequeno intervalo para não travar o event loop do próprio painel monitor
            await asyncio.sleep(0.01)

async def _run_stress_preset(target_url: str, preset_name: str):
    print(f"==== [STRESS] INICIANDO PRESET: {preset_name} ALVO: {target_url} ====")
    global stress_status
    stress_status["is_running"] = True
    stress_status["target"] = target_url
    stress_status["type"] = preset_name
    stress_status["start_time"] = time.time()
    stress_status["requests_sent"] = 0
    
    # Tabela de Presets Pre-Configurados para testes progressivos e seguros
    presets = {
        "estudantes_leve": {
            "name": "Onda de Estudantes (Leve)",
            "concurrency": 20, "duration": 30, "payload": 0, "is_post": False
        },
        "surto_notas": {
            "name": "Surto de Notas DB (Medio)",
            "concurrency": 50, "duration": 45, "payload": 1024 * 50, "is_post": True # 50 KB
        },
        "acesso_constante": {
            "name": "Acesso Constante (Intermediário)",
            "concurrency": 100, "duration": 60, "payload": 1024 * 10, "is_post": True # 10 KB
        },
        "pico_matriculas": {
            "name": "Pico de Matriculas (Pesado)",
            "concurrency": 200, "duration": 60, "payload": 1024 * 500, "is_post": True # 500 KB
        },
        "ddos_extremo": {
            "name": "Ataque Volumetrico DDoS (Extremo)",
            "concurrency": 400, "duration": 120, "payload": 1024 * 1024 * 5, "is_post": True # 5 MB
        }
    }
    
    if preset_name not in presets:
        preset_name = "estudantes_leve"
        
    config = presets[preset_name]
    
    stress_status["duration"] = config["duration"]
    stress_status["logs"] = [
        f"Iniciando cenario: {config['name']}...",
        f"Alvo: {target_url} | Requisições Paralelas: {config['concurrency']} | Duração base: {config['duration']}s",
        "Disparando carga assíncrona com httpx nativo..."
    ]
    
    stop_event = asyncio.Event()
    
    # Inicia os workers definidos
    tasks = []
    for _ in range(config["concurrency"]):
        tasks.append(asyncio.create_task(worker(target_url, stop_event, config["payload"], config["is_post"])))
        
    end_time = time.time() + config["duration"]
    while time.time() < end_time and stress_status["is_running"]:
        await asyncio.sleep(1)
        # Log aleatório de andamento
        if random.random() > 0.7:
            stress_status["logs"].insert(0, f"[{config['name']}] Status: {stress_status['requests_sent']} reqs disparadas.")
            if len(stress_status["logs"]) > 15:
                stress_status["logs"].pop()

    # Tempo estourou ou usuário interrompeu o teste manualmente, cancelando o envio
    stop_event.set()
    stress_status["logs"].insert(0, f"Aguardando cancelamento dos workers...")
    
    # Tolerância máxima de 2 seg pro gathering
    try:
        await asyncio.wait_for(asyncio.gather(*tasks, return_exceptions=True), timeout=2.0)
    except asyncio.TimeoutError:
        pass
    
    stress_status["is_running"] = False
    stress_status["logs"].insert(0, f"Simulacao de estresse '{config['name']}' concluida!")
    print(f"==== [STRESS] CONCLUIDO/PARADO ====")

@router.get("/status")
async def get_stress_status(current_user: dict = Depends(get_current_user)):
    return stress_status

@router.post("/stop")
async def stop_stress_test(current_user: dict = Depends(get_current_user)):
    global stress_status
    if stress_status["is_running"]:
        stress_status["is_running"] = False
        print("==== [STRESS] SINAL DE ABORTO RECEBIDO ====")
        stress_status["logs"].insert(0, "Sinal manual de aborto recebido! Cortando repasses HTTP...")
        return {"message": "Sinal de parada enviado."}
    return {"message": "Nenhum teste de estresse em execução."}

@router.post("/run")
async def stress_frontend(config: StressConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if stress_status["is_running"]:
        raise HTTPException(status_code=400, detail="Um teste de Carga já está em execução no painel.")
    
    background_tasks.add_task(_run_stress_preset, config.target_url, config.preset)
    return {"message": f"Carga pre-configurada '{config.preset}' iniciada contra {config.target_url}."}
