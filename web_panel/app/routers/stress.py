import asyncio
import os
import time
import random
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from app.auth import get_current_user
from dotenv import load_dotenv

# Carrega variáveis de ambiente de um arquivo .env
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

# Caminho absoluto montado a partir de app/routers -> web_panel -> raiz.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DOCKER_COMPOSE_PATH = os.path.join(BASE_DIR, "botnet_agent", "docker-compose.yml")

# Use o caminho do executável do docker-compose se definido, caso contrário, use o comando padrão

DOCKER_COMPOSE_EXEC = os.getenv("DOCKER_COMPOSE_EXECUTABLE", "docker compose")



# Centraliza a definição de presets

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



async def stop_docker_botnet():

    """Tenta derrubar a botnet e retorna a saída do processo."""

    output_logs = []

    try:

        print("Derrubando botnet via docker compose...")

        cmd_down = f'"{DOCKER_COMPOSE_EXEC}" -f "{DOCKER_COMPOSE_PATH}" down'

        proc = await asyncio.create_subprocess_shell(

            cmd_down,

            stdout=asyncio.subprocess.PIPE,

            stderr=asyncio.subprocess.PIPE

        )

        stdout, stderr = await proc.communicate()

        

        if stdout:

            output_logs.append(stdout.decode('utf-8', errors='ignore'))

        if stderr:

            output_logs.append(stderr.decode('utf-8', errors='ignore'))

        

        if proc.returncode == 0:

            print("Botnet derrubada com sucesso.")

        else:

            print(f"Erro ao derrubar botnet, código de saída: {proc.returncode}")



    except Exception as e:

        error_msg = f"Exceção ao derrubar botnet: {e}"

        print(error_msg)

        output_logs.append(error_msg)

    

    return "\n".join(output_logs)



async def _monitor_and_shutdown_task(preset_name: str, duration: int):

    """Tarefa de fundo para monitorar o tempo de execução e derrubar o docker no final."""

    global stress_status

    

    config = presets.get(preset_name, presets["estudantes_leve"])

    end_time = time.time() + duration

        

    try:

        while time.time() < end_time and stress_status["is_running"]:

            await asyncio.sleep(2)

            # Simula a contagem de requests

            stress_status["requests_sent"] += int(config.get('scale', 1) * random.uniform(5, 15))

            

            if random.random() > 0.7:

                log_msg = f"[{config['name']}] Status: ~{stress_status['requests_sent']} reqs reportadas pela Botnet."

                stress_status["logs"].insert(0, log_msg)

                if len(stress_status["logs"]) > 15:

                    stress_status["logs"].pop()

    finally:

        if stress_status["is_running"]:

            stress_status["logs"].insert(0, "Tempo de execução do preset finalizado. Derrubando containers...")

        else:

            # Esta mensagem será usada se o stop for chamado manualmente

            stress_status["logs"].insert(0, "Sinal de aborto recebido. Derrubando containers...")



        shutdown_log = await stop_docker_botnet()

        stress_status["logs"].insert(0, shutdown_log)

        stress_status["is_running"] = False

        stress_status["logs"].insert(0, "Simulação de estresse finalizada no Docker!")

        print(f"==== [STRESS DOCKER] TAREFA DE FUNDO CONCLUÍDA/PARADA ====")



@router.get("/status")

async def get_stress_status(current_user: dict = Depends(get_current_user)):

    return stress_status



@router.post("/stop")

async def stop_stress_test(current_user: dict = Depends(get_current_user)):

    global stress_status

    if stress_status["is_running"]:

        stress_status["is_running"] = False

        print("==== [STRESS DOCKER] SINAL DE ABORTO RECEBIDO ====")

        shutdown_log = await stop_docker_botnet()

        return {"message": "Sinal de parada enviado. O Docker está sendo destruído.", "log": shutdown_log}

    

    return {"message": "Nenhum teste de estresse em execução.", "log": "Nenhuma operação de parada foi executada."}



@router.post("/run")

async def stress_frontend(config: StressConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):

    global stress_status

    if stress_status["is_running"]:

        raise HTTPException(status_code=400, detail="Um teste de Carga Docker já está em execução no painel.")



    preset_name = config.preset

    if preset_name not in presets:

        preset_name = "estudantes_leve"

    

    preset_config = presets[preset_name]

    

    stress_status.update({

        "is_running": True,

        "target": config.target_url,

        "type": preset_name,

        "start_time": time.time(),

        "duration": preset_config["duration"],

        "requests_sent": 0,

        "logs": [f"Iniciando DOCKER botnet: {preset_config['name']}..."]

    })



    # Derruba qualquer instância anterior para garantir um início limpo

    initial_shutdown_log = await stop_docker_botnet()

    

    env_vars = os.environ.copy()

    env_vars["TARGET_URL"] = config.target_url



    cmd_up = f'"{DOCKER_COMPOSE_EXEC}" -f "{DOCKER_COMPOSE_PATH}" up --build -d --scale {preset_config["service"]}={preset_config["scale"]}'

    

    proc_up = await asyncio.create_subprocess_shell(

        cmd_up,

        env=env_vars,

        stdout=asyncio.subprocess.PIPE,

        stderr=asyncio.subprocess.PIPE

    )

    stdout_up, stderr_up = await proc_up.communicate()

    

    startup_log = ""

    if stdout_up:

        startup_log += stdout_up.decode('utf-8', errors='ignore') + "\n"

    if stderr_up:

        startup_log += stderr_up.decode('utf-8', errors='ignore')



    if proc_up.returncode != 0:

        stress_status["is_running"] = False

        error_message = "Falha ao iniciar os containers do Docker."

        stress_status["logs"].insert(0, error_message)

        raise HTTPException(status_code=500, detail={"message": error_message, "log": startup_log})



    # Se a inicialização for bem-sucedida, agende a tarefa de monitoramento e desligamento

    background_tasks.add_task(_monitor_and_shutdown_task, preset_name, preset_config["duration"])

    

    return {

        "message": f"Carga '{preset_name}' iniciada com sucesso!",

        "log": f"Log de Limpeza Inicial:\n{initial_shutdown_log}\n\nLog de Inicialização:\n{startup_log}"

    }
