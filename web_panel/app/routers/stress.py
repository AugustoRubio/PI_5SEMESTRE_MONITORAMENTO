from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user
import httpx
import asyncio
import time

router = APIRouter()

class StressConfig(BaseModel):
    target_url: str
    duration_seconds: int
    concurrency: int

# Variável global para rastrear o status do teste
stress_status = {
    "is_running": False,
    "target": "",
    "type": "",
    "requests_sent": 0,
    "start_time": 0,
    "duration": 0
}

async def perform_stress_test(url: str, duration: int, concurrency: int, method: str = "GET"):
    global stress_status
    stress_status["is_running"] = True
    stress_status["target"] = url
    stress_status["type"] = method
    stress_status["requests_sent"] = 0
    stress_status["start_time"] = time.time()
    stress_status["duration"] = duration

    timeout = httpx.Timeout(10.0)
    # Usamos limites altos para permitir concorrência real
    limits = httpx.Limits(max_connections=concurrency, max_keepalive_connections=concurrency)
    
    async with httpx.AsyncClient(timeout=timeout, limits=limits, verify=False) as client:
        end_time = asyncio.get_event_loop().time() + duration
        
        async def worker():
            req_count = 0
            while asyncio.get_event_loop().time() < end_time and stress_status["is_running"]:
                try:
                    if method == "GET":
                        await client.get(url)
                    else:
                        await client.post(url)
                    req_count += 1
                    stress_status["requests_sent"] += 1
                except Exception:
                    # Ignora erros de timeout/conexão durante o estresse
                    pass
            return req_count

        tasks = [worker() for _ in range(concurrency)]
        await asyncio.gather(*tasks)
        
    stress_status["is_running"] = False
    print(f"Teste de estresse finalizado. Total de requisições: {stress_status['requests_sent']}")

@router.get("/status")
async def get_stress_status(current_user: dict = Depends(get_current_user)):
    return stress_status

@router.post("/stop")
async def stop_stress_test(current_user: dict = Depends(get_current_user)):
    global stress_status
    if stress_status["is_running"]:
        stress_status["is_running"] = False
        return {"message": "Sinal de parada enviado. O teste será encerrado em instantes."}
    return {"message": "Nenhum teste em execução."}

@router.post("/frontend")
async def stress_frontend(config: StressConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if stress_status["is_running"]:
        raise HTTPException(status_code=400, detail="Um teste já está em execução.")
    
    background_tasks.add_task(perform_stress_test, config.target_url, config.duration_seconds, config.concurrency, "GET")
    return {"message": f"Teste de estresse Frontend iniciado em {config.target_url} por {config.duration_seconds}s."}

@router.post("/backend/read")
async def stress_backend_read(config: StressConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if stress_status["is_running"]:
        raise HTTPException(status_code=400, detail="Um teste já está em execução.")
        
    url = f"{config.target_url.rstrip('/')}/api/stress/read"
    background_tasks.add_task(perform_stress_test, url, config.duration_seconds, config.concurrency, "GET")
    return {"message": f"Teste de estresse de Leitura (DB) iniciado em {url} por {config.duration_seconds}s."}

@router.post("/backend/write")
async def stress_backend_write(config: StressConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if stress_status["is_running"]:
        raise HTTPException(status_code=400, detail="Um teste já está em execução.")
        
    url = f"{config.target_url.rstrip('/')}/api/stress/write"
    background_tasks.add_task(perform_stress_test, url, config.duration_seconds, config.concurrency, "POST")
    return {"message": f"Teste de estresse de Escrita (DB) iniciado em {url} por {config.duration_seconds}s."}