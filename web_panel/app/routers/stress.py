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
    "logs": [],       # Mensagens amigáveis para o feed
    "raw_logs": ""    # Logs brutos do Docker para a modal
}

def add_stress_log(msg: str, is_raw: bool = False):
    """Adiciona log ao status, mantendo limite e separando técnicos de amigáveis."""
    global stress_status
    if is_raw:
        # Acumula logs brutos (limita a 10000 caracteres para não estourar memória)
        stress_status["raw_logs"] = (msg + "\n" + stress_status["raw_logs"])[:10000]
    else:
        stress_status["logs"].insert(0, msg)
        if len(stress_status["logs"]) > 25:
            stress_status["logs"].pop()

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

            out_str = stdout.decode('utf-8', errors='ignore')
            if out_str or err_msg:
                add_stress_log(f"--- Comando: {args} ---\n{out_str}\n{err_msg}", is_raw=True)

            return proc.returncode, out_str, err_msg
        except Exception as e:
            last_error = str(e)
            continue

    return 1, "", f"Erro: Nenhum executável docker compose encontrado. Último erro: {last_error}"

async def stop_docker_botnet():
    """Tenta derrubar a botnet e retorna a saída do processo."""
    output_logs = []
    try:
        add_stress_log("🛑 Finalizando containers e limpando rede...")
        returncode, stdout, stderr = await run_docker_command("down")

        if stdout: output_logs.append(stdout)
        if stderr: output_logs.append(stderr)

        if returncode == 0:
            add_stress_log("✅ Ambiente Docker limpo com sucesso.")
        else:
            add_stress_log(f"⚠️ Aviso ao limpar ambiente (Código {returncode}).")

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
            new_reqs = int(config.get('scale', 1) * random.uniform(8, 20))
            stress_status["requests_sent"] += new_reqs

            # A cada ~10 segundos, verifica o status real dos containers e logs
            current_time = time.time()
            if current_time - last_log_check > 12:
                last_log_check = current_time
                try:
                    # Verifica status e logs usando o novo sistema robusto
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
        "logs": [],
        "raw_logs": ""
    })
    
    add_stress_log(f"🚀 Iniciando orquestração da botnet: {preset_config['name']}...")
    add_stress_log(f"🎯 Alvo definido: {config.target_url}")

    # Derruba qualquer instância anterior para garantir um início limpo
    await stop_docker_botnet()
    
    env_vars = os.environ.copy()
    env_vars["TARGET_URL"] = config.target_url

    # Inicia os containers com o comando robusto
    add_stress_log("🛠️ Construindo imagens e subindo containers (isso pode levar alguns segundos)...")
    args_up = f"up --build -d --scale {preset_config['service']}={preset_config['scale']}"
    returncode, stdout_up, stderr_up = await run_docker_command(args_up, env=env_vars)
    
    if returncode == 0:
        add_stress_log(f"✅ Botnet ativa! {preset_config['scale']} agentes em combate.")
    else:
        stress_status["is_running"] = False
        add_stress_log("❌ Falha crítica ao iniciar Docker.")
        raise HTTPException(status_code=500, detail={"message": "Erro ao subir Docker", "log": stderr_up})

    # Se a inicialização for bem-sucedida, agende a tarefa de monitoramento e desligamento
    background_tasks.add_task(_monitor_and_shutdown_task, preset_name, preset_config["duration"])
    
    return {"message": f"Preset {preset_name} em execução."}
