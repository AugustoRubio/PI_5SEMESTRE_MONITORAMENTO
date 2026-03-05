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

# Tenta detectar o executável do docker compose automaticamente se não estiver no env
DOCKER_COMPOSE_EXEC = os.getenv("DOCKER_COMPOSE_EXECUTABLE")

if not DOCKER_COMPOSE_EXEC:
    # No Windows/Linux modernos, 'docker compose' é o padrão (v2)
    # Mas em alguns ambientes linux antigos ou instalações específicas, 'docker-compose' (v1) é o comando
    # O erro "/bin/sh: 1: docker compose: not found" sugere que o shell não reconhece o comando composto
    DOCKER_COMPOSE_EXEC = "docker compose"



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



async def run_docker_command(args: str, env=None):
    """Executa um comando docker compose tentando v2 e v1 como fallback."""
    global DOCKER_COMPOSE_EXEC
    
    # Lista de comandos para tentar se o principal falhar
    commands_to_try = [DOCKER_COMPOSE_EXEC, "docker-compose", "/usr/local/bin/docker-compose"]
    
    last_error = ""
    for cmd in commands_to_try:
        try:
            full_cmd = f'{cmd} -f "{DOCKER_COMPOSE_PATH}" {args}'
            # No Windows, shell=True usa cmd.exe. No Linux usa /bin/sh
            proc = await asyncio.create_subprocess_shell(
                full_cmd,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            # Se o erro for "not found", tentamos o próximo
            err_msg = stderr.decode('utf-8', errors='ignore')
            if proc.returncode != 0 and ("not found" in err_msg or "not recognized" in err_msg):
                last_error = err_msg
                continue
                
            # Se chegamos aqui, o comando ao menos foi encontrado
            if cmd != DOCKER_COMPOSE_EXEC:
                print(f"[*] Ajustando DOCKER_COMPOSE_EXEC para: {cmd}")
                DOCKER_COMPOSE_EXEC = cmd # Cache do comando que funcionou
                
            return proc.returncode, stdout.decode('utf-8', errors='ignore'), err_msg
        except Exception as e:
            last_error = str(e)
            continue
            
    return 1, "", f"Erro: Nenhum executável docker compose encontrado. Último erro: {last_error}"

async def stop_docker_botnet():
    """Tenta derrubar a botnet e retorna a saída do processo."""
    output_logs = []
    try:
        print("Derrubando botnet...")
        returncode, stdout, stderr = await run_docker_command("down")
        
        if stdout: output_logs.append(stdout)
        if stderr: output_logs.append(stderr)
        
        if returncode == 0:
            print("Botnet derrubada com sucesso.")
        else:
            print(f"Erro ao derrubar botnet, código: {returncode}")

    except Exception as e:
        output_logs.append(f"Exceção ao derrubar: {e}")
    
    return "\n".join(output_logs)



async def _monitor_and_shutdown_task(preset_name: str, duration: int):
    """Tarefa de fundo para monitorar o tempo de execução e derrubar o docker no final."""
    global stress_status
    
    config = presets.get(preset_name, presets["estudantes_leve"])
    end_time = time.time() + duration
    last_log_check = 0
        
    try:
        while time.time() < end_time and stress_status["is_running"]:
            await asyncio.sleep(3)
            # Simula a contagem de requests baseada na escala
            stress_status["requests_sent"] += int(config.get('scale', 1) * random.uniform(8, 20))
            
            # A cada ~10 segundos, verifica o status real dos containers e logs
            current_time = time.time()
            if current_time - last_log_check > 10:
                last_log_check = current_time
                try:
                    # Verifica status e logs usando o novo sistema robusto
                    rc_ps, stdout_ps, _ = await run_docker_command("ps --format json")
                    rc_logs, stdout_logs, _ = await run_docker_command(f"logs --tail=2 {config['service']}")
                    
                    if stdout_logs:
                        real_logs = stdout_logs.strip().split('\n')
                        for line in real_logs:
                            if line:
                                stress_status["logs"].insert(0, f"[DOCKER] {line}")
                    
                    stress_status["logs"].insert(0, f"[STATUS] Botnet '{config['name']}' ativa com {config['scale']} instâncias.")
                except Exception as e:
                    stress_status["logs"].insert(0, f"[AVISO] Erro ao buscar status real: {str(e)[:50]}")

            if len(stress_status["logs"]) > 20:
                stress_status["logs"] = stress_status["logs"][:20]

    finally:
        if stress_status["is_running"]:
            stress_status["logs"].insert(0, "Tempo de execução do preset finalizado. Derrubando containers...")
        else:
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

    # Inicia os containers com o comando robusto
    args_up = f"up --build -d --scale {preset_config['service']}={preset_config['scale']}"
    returncode, stdout_up, stderr_up = await run_docker_command(args_up, env=env_vars)
    
    startup_log = f"{stdout_up}\n{stderr_up}"

    if returncode != 0:
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
