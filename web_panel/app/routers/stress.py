import asyncio
import os
import time
import random
import paramiko
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user
from dotenv import load_dotenv

load_dotenv()

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

# --- Configuração do Cliente SSH ---
REMOTE_HOST = os.getenv("REMOTE_HOST")
REMOTE_USER = os.getenv("REMOTE_USER")
REMOTE_PASSWORD = os.getenv("REMOTE_PASSWORD")

# ATENÇÃO: Altere este caminho para o caminho absoluto do docker-compose.yml NO SERVIDOR REMOTO
REMOTE_DOCKER_COMPOSE_PATH = "/app/botnet_agent/docker-compose.yml" 

def execute_remote_command(command):
    if not all([REMOTE_HOST, REMOTE_USER, REMOTE_PASSWORD]):
        msg = "Variáveis de ambiente para conexão remota (REMOTE_HOST, REMOTE_USER, REMOTE_PASSWORD) não configuradas."
        print(f"[SSH_ERROR] {msg}")
        stress_status["logs"].insert(0, f"Erro de Configuração: {msg}")
        return None, msg

    ssh_client = paramiko.SSHClient()
    ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        print(f"[SSH] Conectando a {REMOTE_USER}@{REMOTE_HOST}...")
        ssh_client.connect(hostname=REMOTE_HOST, username=REMOTE_USER, password=REMOTE_PASSWORD, timeout=10)
        
        print(f"[SSH] Executando comando: {command}")
        stdin, stdout, stderr = ssh_client.exec_command(command, get_pty=True)
        
        # Esperar o comando terminar. stdout.channel.recv_exit_status() bloqueia até a conclusão.
        exit_status = stdout.channel.recv_exit_status() 
        
        stdout_output = stdout.read().decode('utf-8')
        stderr_output = stderr.read().decode('utf-8')

        print(f"[SSH] Comando finalizado. Exit Status: {exit_status}")
        if exit_status != 0:
             print(f"[SSH_STDOUT] {stdout_output}")
             print(f"[SSH_STDERR] {stderr_output}")

        return exit_status, stdout_output + stderr_output

    except Exception as e:
        error_msg = f"Falha na conexão ou execução SSH: {e}"
        print(f"[SSH_ERROR] {error_msg}")
        stress_status["logs"].insert(0, f"Erro de Conexão: {error_msg}")
        return None, error_msg
    finally:
        if ssh_client:
            ssh_client.close()
            print("[SSH] Conexão fechada.")


def stop_docker_botnet():
    try:
        print("Derrubando botnet remotamente via docker compose...")
        cmd_down = f'docker compose -f "{REMOTE_DOCKER_COMPOSE_PATH}" down'
        execute_remote_command(cmd_down)
    except Exception as e:
        print(f"Erro ao derrubar botnet remoto: {e}")

def _run_stress_preset(target_url: str, preset_name: str):
    print(f"==== [STRESS] INICIANDO PRESET DOCKER REMOTO: {preset_name} ALVO: {target_url} ====")
    global stress_status
    stress_status["is_running"] = True
    stress_status["target"] = target_url
    stress_status["type"] = preset_name
    stress_status["start_time"] = time.time()
    stress_status["requests_sent"] = 0

    presets = {
        "estudantes_leve": {"name": "Onda de Estudantes (Leve)", "service": "bot_student", "scale": 15, "duration": 300},
        "surto_notas": {"name": "Surto de Notas DB (Médio)", "service": "bot_professor", "scale": 30, "duration": 300},
        "acesso_constante": {"name": "Acesso Constante (Intermediário)", "service": "bot_student", "scale": 50, "duration": 300},
        "pico_matriculas": {"name": "Pico de Matrículas (Pesado)", "service": "bot_professor", "scale": 80, "duration": 300},
        "ddos_extremo": {"name": "Ataque Volumétrico DDoS (Extremo)", "service": "bot_ddos", "scale": 120, "duration": 600}
    }
    
    config = presets.get(preset_name, presets["estudantes_leve"])

    stress_status["duration"] = config["duration"]
    stress_status["logs"] = [
        f"Iniciando DOCKER botnet REMOTO: {config['name']}...",
        f"Alvo: {target_url} | Containers (scale): {config['scale']} | Duração: {config['duration']}s",
        f"Conectando ao servidor remoto em {REMOTE_HOST}..."
    ]
    
    # Inicia a limpeza de containers antigos em segundo plano
    stop_docker_botnet()

    # O TARGET_URL precisa ser passado para o ambiente do docker-compose
    env_export = f'export TARGET_URL="{target_url}";'
    cmd_up = f'{env_export} docker compose -f "{REMOTE_DOCKER_COMPOSE_PATH}" up --build -d --scale {config["service"]}={config["scale"]}'
    
    exit_code, output = execute_remote_command(cmd_up)
    
    if exit_code == 0:
        stress_status["logs"].insert(0, f"Esquadrão DOCKER em execução remota! Atacando...")
    else:
        stress_status["logs"].insert(0, f"Erro ao subir docker remoto. Código: {exit_code}")
        stress_status["logs"].insert(0, f"Saída: {output}")
        stress_status["is_running"] = False
        print(f"Docker Remoto Erro: {output}")
        return # Finaliza a execução

    end_time = time.time() + config["duration"]
    
    try:
        while time.time() < end_time and stress_status["is_running"]:
            time.sleep(2) # Usar time.sleep em vez de asyncio.sleep
            stress_status["requests_sent"] += int(config["scale"] * random.uniform(5, 15))
            
            if random.random() > 0.7:
                log_msg = f"[{config['name']}] Status: ~{stress_status['requests_sent']} reqs reportadas enviadas pela Botnet."
                stress_status["logs"].insert(0, log_msg)
                if len(stress_status["logs"]) > 15:
                    stress_status["logs"].pop()
    finally:
        log_end_reason = "Tempo ou limite alcançado" if stress_status["is_running"] else "Aborto manual recebido"
        stress_status["logs"].insert(0, f"{log_end_reason}. Derrubando containers remotos...")
        
        stop_docker_botnet()
        stress_status["is_running"] = False
        stress_status["logs"].insert(0, "Simulação de estresse remoto finalizada!")
        print("==== [STRESS DOCKER REMOTO] CONCLUÍDO/PARADO ====")


@router.get("/status")
async def get_stress_status(current_user: dict = Depends(get_current_user)):
    return stress_status

@router.post("/stop")
async def stop_stress_test(current_user: dict = Depends(get_current_user)):
    global stress_status
    if stress_status["is_running"]:
        stress_status["is_running"] = False
        print("==== [STRESS DOCKER REMOTO] SINAL DE ABORTO RECEBIDO ====")
        stress_status["logs"].insert(0, "Sinal manual de aborto recebido! Solicitando encerramento remoto...")
        return {"message": "Sinal de parada enviado. A botnet remota está sendo destruída."}
    return {"message": "Nenhum teste de estresse em execução."}

@router.post("/run")
async def stress_frontend(config: StressConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    if not all([REMOTE_HOST, REMOTE_USER, REMOTE_PASSWORD]):
         raise HTTPException(status_code=400, detail="Servidor remoto não configurado. Verifique as variáveis de ambiente.")

    if stress_status["is_running"]:
        raise HTTPException(status_code=400, detail="Um teste de Carga Docker já está em execução no painel.")

    background_tasks.add_task(_run_stress_preset, config.target_url, config.preset)
    return {"message": f"Carga pre-configurada '{config.preset}' iniciada remotamente contra {config.target_url}."}
