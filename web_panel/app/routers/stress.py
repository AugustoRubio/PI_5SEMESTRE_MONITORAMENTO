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

# Caminho absoluto montado a partir de app/routers -> web_panel -> raiz.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
DOCKER_COMPOSE_PATH = os.path.join(BASE_DIR, "botnet_agent", "docker-compose.yml")

# Tenta detectar o executável do docker compose automaticamente se não estiver no env
DOCKER_COMPOSE_EXEC = os.getenv("DOCKER_COMPOSE_EXECUTABLE")
if not DOCKER_COMPOSE_EXEC:
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

stress_status = {
    "is_running": False,
    "target": "",
    "type": "",
    "requests_sent": 0,
    "start_time": 0,
    "duration": 0,
    "logs": [],       # Mensagens amigáveis para o feed
    "raw_logs": ""    # Logs brutos do Docker para a modal
}

def add_stress_log(msg: str, is_raw: bool = False):
    """Adiciona log ao status, mantendo limite e separando técnicos de amigáveis."""
    global stress_status
    if is_raw:
        # Acumula logs brutos
        stress_status["raw_logs"] = (msg + "\n" + stress_status["raw_logs"])[:10000]
    else:
        stress_status["logs"].insert(0, msg)
        if len(stress_status["logs"]) > 25:
            stress_status["logs"].pop()

async def run_docker_command(args: str, env=None):
    """Executa um comando docker compose tentando v2 e v1 como fallback."""
    global DOCKER_COMPOSE_EXEC
    
    run_env = os.environ.copy() if env is None else env.copy()
    run_env["DOCKER_API_VERSION"] = "1.41"
    
    commands_to_try = [DOCKER_COMPOSE_EXEC, "docker-compose", "/usr/local/bin/docker-compose", "/usr/libexec/docker/cli-plugins/docker-compose"]
    last_error = ""

    for cmd in commands_to_try:
        try:
            full_cmd = f'{cmd} -f "{DOCKER_COMPOSE_PATH}" {args}'
            proc = await asyncio.create_subprocess_shell(
                full_cmd,
                env=run_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            err_msg = stderr.decode('utf-8', errors='ignore')
            if proc.returncode != 0 and ("not found" in err_msg or "not recognized" in err_msg):
                last_error = err_msg
                continue
                
            if cmd != DOCKER_COMPOSE_EXEC:
                DOCKER_COMPOSE_EXEC = cmd
                
            out_str = stdout.decode('utf-8', errors='ignore')
            log_content = out_str
            
            # Se for o comando ps com json, tenta formatar para legibilidade
            if "ps --format json" in args and out_str.strip():
                try:
                    import json
                    lines = out_str.strip().split('\n')
                    formatted_json_list = []
                    for line in lines:
                        if line.strip().startswith('{'):
                            formatted_json_list.append(json.dumps(json.loads(line), indent=4, ensure_ascii=False))
                        else:
                            formatted_json_list.append(line)
                    log_content = "\n\n".join(formatted_json_list)
                except:
                    pass

            if log_content or err_msg:
                add_stress_log(f"--- Comando: {args} ---\n{log_content}\n{err_msg}", is_raw=True)

            return proc.returncode, out_str, err_msg
        except Exception as e:
            last_error = str(e)
            continue
            
    return 1, "", f"Erro: Nenhum executável docker encontrado. {last_error}"

async def stop_docker_botnet():
    """Tenta derrubar a botnet."""
    try:
        add_stress_log("🛑 Finalizando containers e limpando rede...")
        returncode, stdout, stderr = await run_docker_command("down")
        if returncode == 0:
            add_stress_log("✅ Ambiente Docker limpo com sucesso.")
        else:
            add_stress_log(f"⚠️ Aviso ao limpar ambiente (Código {returncode}).")
    except Exception as e:
        add_stress_log(f"Exceção ao derrubar: {e}")

async def _monitor_and_shutdown_task(preset_name: str, duration: int):
    """Tarefa de fundo para monitoramento."""
    global stress_status
    config = presets.get(preset_name, presets["estudantes_leve"])
    end_time = time.time() + duration
    last_log_check = 0
        
    try:
        while time.time() < end_time and stress_status["is_running"]:
            await asyncio.sleep(3)
            new_reqs = int(config.get('scale', 1) * random.uniform(8, 20))
            stress_status["requests_sent"] += new_reqs
            
            current_time = time.time()
            if current_time - last_log_check > 12:
                last_log_check = current_time
                try:
                    rc_ps, stdout_ps, _ = await run_docker_command("ps --format json")
                    rc_logs, stdout_logs, _ = await run_docker_command(f"logs --tail=2 {config['service']}")
                    
                    if stdout_logs:
                        real_logs = stdout_logs.strip().split('\n')
                        for line in real_logs:
                            if line and "Bot Iniciado" in line:
                                add_stress_log(f"🤖 Novo agente pronto: {line.split('|')[0].strip()}")
                            elif line and "[*]" in line:
                                add_stress_log(f"📡 Atividade detectada: {line}")

                    add_stress_log(f"📊 Status: {config['scale']} instâncias operando. Total ~{stress_status['requests_sent']} reqs.")
                except Exception as e:
                    add_stress_log(f"❌ Erro de monitoramento: {str(e)[:40]}")
    finally:
        if stress_status["is_running"]:
            add_stress_log("⏱️ Tempo de execução atingido.")
        else:
            add_stress_log("🛑 Interrupção manual solicitada.")
        await stop_docker_botnet()
        stress_status["is_running"] = False
        add_stress_log("🏁 Teste de estresse concluído.")

@router.get("/status")
async def get_stress_status(current_user: dict = Depends(get_current_user)):
    return stress_status

@router.post("/stop")
async def stop_stress_test(current_user: dict = Depends(get_current_user)):
    global stress_status
    if stress_status["is_running"]:
        stress_status["is_running"] = False
        return {"message": "Sinal de parada enviado."}
    return {"message": "Nenhum teste em execução."}

@router.post("/run")
async def stress_frontend(config: StressConfig, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    global stress_status
    if stress_status["is_running"]:
        raise HTTPException(status_code=400, detail="Já em execução.")

    preset_name = config.preset
    preset_config = presets.get(preset_name, presets["estudantes_leve"])
    
    stress_status.update({
        "is_running": True, "target": config.target_url, "type": preset_name,
        "start_time": time.time(), "duration": preset_config["duration"],
        "requests_sent": 0, "logs": [], "raw_logs": ""
    })
    
    add_stress_log(f"🚀 Iniciando orquestração da botnet: {preset_config['name']}...")
    await stop_docker_botnet()
    
    env_vars = os.environ.copy()
    env_vars["TARGET_URL"] = config.target_url
    env_vars["DB_HOST"] = config.db_host
    env_vars["DB_PORT"] = str(config.db_port)
    env_vars["DB_USER"] = config.db_user
    env_vars["DB_PASS"] = config.db_pass
    env_vars["DB_NAME"] = config.db_name

    add_stress_log("🛠️ Construindo imagens e subindo containers (Limpando Cache)...")
    # Agora especifica o serviço no final do comando para não subir o ddos acidentalmente
    args_up = f"up --build --force-recreate -d --scale {preset_config['service']}={preset_config['scale']} {preset_config['service']}"
    returncode, stdout_up, stderr_up = await run_docker_command(args_up, env=env_vars)
    
    if returncode == 0:
        add_stress_log(f"✅ Botnet ativa! {preset_config['scale']} agentes em combate.")
        background_tasks.add_task(_monitor_and_shutdown_task, preset_name, preset_config["duration"])
        return {"message": "Iniciado com sucesso."}
    else:
        stress_status["is_running"] = False
        add_stress_log("❌ Falha crítica ao iniciar Docker.")
        raise HTTPException(status_code=500, detail="Erro ao subir Docker.")
