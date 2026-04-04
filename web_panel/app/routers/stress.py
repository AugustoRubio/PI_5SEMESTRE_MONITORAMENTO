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
    db_host: str = "10.10.100.4"
    db_port: int = 3306
    db_user: str = "intranet_user"
    db_pass: str = "bcd127"
    db_name: str = "intranet_db"

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
    },
    "soa_flood": {
        "name": "Estresse em Microsserviços (SOA/Billing API)",
        "service": "bot_soa", "scale": 15, "duration": 300
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
    
    # IMPORTANTE: Sempre manter as variáveis de sistema (PATH, etc) no ambiente de execução
    run_env = os.environ.copy()
    if env:
        run_env.update(env)
        
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

async def run_docker_cli(args_list):
    """Executa comandos base do docker (não compose) de forma segura tentando múltiplos paths."""
    for base_cmd in ["docker", "/usr/bin/docker", "/usr/local/bin/docker"]:
        try:
            proc = await asyncio.create_subprocess_exec(
                base_cmd, *args_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            return proc.returncode, stdout.decode(errors='ignore').strip(), stderr.decode(errors='ignore').strip()
        except FileNotFoundError:
            continue
        except Exception as e:
            return 1, "", str(e)
    return 1, "", "Comando docker não encontrado no PATH."

async def stop_docker_botnet():
    """Tenta derrubar a botnet."""
    try:
        add_stress_log("[-] Finalizando containers e limpando rede...")
        returncode, stdout, stderr = await run_docker_command("down")
        if returncode == 0:
            add_stress_log("[+] Ambiente Docker limpo com sucesso.")
        else:
            add_stress_log(f"[-] Aviso ao limpar ambiente (Código {returncode}).")
            
        # Garante que o ataque SOA seja encerrado de imediato e o container volte ao estado limpo
        await run_docker_cli(["restart", "soa_stress_pi"])
    except Exception as e:
        add_stress_log(f"[-] Exceção ao derrubar: {e}")

async def _orchestrate_stress_task(config: StressConfig, preset_config: dict, preset_name: str):
    """
    Orquestra o ciclo completo em background para evitar Timeout no servidor Web.
    """
    global stress_status
    
    # 1. Limpar ambiente anterior
    await stop_docker_botnet()

    # --- Lógica Exclusiva para o SOA Flood (Apache Bench Centralizado) ---
    if preset_name == "soa_flood":
        base_url = config.target_url.rstrip('/')
        
        # Força o uso de HTTP. O ab tem problemas nativos com certificados self-signed HTTPS em certas distros Alpine.
        if base_url.startswith("https://"):
            base_url = base_url.replace("https://", "http://", 1)
            
        target = base_url + "/invoices/1"
        
        # Garante que o container esteja ligado (caso o usuário não tenha ligado o Docker Manager)
        rc, out, err = await run_docker_cli(["start", "soa_stress_pi"])
        if rc != 0:
            stress_status["logs"] = [f"[-] Erro ao ligar bot soa_stress_pi: {err}"]
            stress_status["is_running"] = False
            return

        # Garante que o curl está instalado no container
        await run_docker_cli(["exec", "soa_stress_pi", "apk", "add", "--no-cache", "curl"])
        
        # Script bash para gerar carga e logs idênticos ao simulator.py
        script = f"""
echo '[*] Iniciando Bot de Estresse SOA...' > /tmp/stress.log
echo '[*] Alvo: {target}' >> /tmp/stress.log
echo '[*] Preparando Apache Bench (DDoS Layer 7) em background...' >> /tmp/stress.log
ab -r -n 500000 -c 100 {target} > /tmp/ab.log 2>&1 &
echo '[+] Carga disparada! 100 conexoes simultaneas ativas.' >> /tmp/stress.log
while true; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{{http_code}}" {target} || echo "ERR")
    echo "Acessando: {target}" >> /tmp/stress.log
    echo "Resposta HTTP: $HTTP_CODE | Mantendo estresse de backend..." >> /tmp/stress.log
    sleep 2
done
        """
        
        rc, out, err = await run_docker_cli(["exec", "-d", "soa_stress_pi", "sh", "-c", script])
        
        if rc != 0:
            stress_status["logs"] = [f"[-] Falha ao executar script de estresse: {err}"]
            stress_status["is_running"] = False
            return
        
        duration = preset_config["duration"]
        end_time = time.time() + duration
        
        try:
            while time.time() < end_time and stress_status["is_running"]:
                for _ in range(3):
                    if not stress_status["is_running"]: break
                    await asyncio.sleep(1)
                    
                if not stress_status["is_running"]: break
                
                # Como o AB está em background no docker, simulamos o contador visual para a UI
                stress_status["requests_sent"] += random.randint(1500, 3000)
                
                # Busca os logs reais gerados pelo script em bash
                rc_logs, stdout_logs, _ = await run_docker_cli(["exec", "soa_stress_pi", "tail", "-n", "15", "/tmp/stress.log"])
                if rc_logs == 0 and stdout_logs:
                    lines = [line.strip() for line in stdout_logs.strip().split('\n') if line.strip()]
                    lines.reverse() # Inverte para que o mais recente fique no topo cronologicamente igual add_stress_log
                    stress_status["logs"] = lines
        finally:
            await stop_docker_botnet()
            stress_status["logs"].append("[-] Simulação interrompida. Conexões encerradas.")
            stress_status["is_running"] = False
        return
    
    # 2. Preparar ambiente do Docker
    env_vars = {
        "TARGET_URL": str(config.target_url),
        "DB_HOST": str(config.db_host),
        "DB_PORT": str(config.db_port),
        "DB_USER": str(config.db_user),
        "DB_PASS": str(config.db_pass),
        "DB_NAME": str(config.db_name)
    }

    add_stress_log("[*] Subindo containers (Escalando botnet)...")
    
    # Comando rápido (sem --build) para resposta imediata
    args_up = f"up -d --scale {preset_config['service']}={preset_config['scale']}"
    returncode, stdout_up, stderr_up = await run_docker_command(args_up, env=env_vars)
    
    if returncode == 0:
        add_stress_log(f"[+] Botnet ativa! {preset_config['scale']} agentes em combate.")
        
        # 3. Iniciar monitoramento
        duration = preset_config["duration"]
        end_time = time.time() + duration
        last_log_check = 0
            
        try:
            while time.time() < end_time and stress_status["is_running"]:
                for _ in range(3):
                    if not stress_status["is_running"]: break
                    await asyncio.sleep(1)
                    
                if not stress_status["is_running"]: break
                
                # Estimativa de requisições baseada na escala
                new_reqs = int(preset_config.get('scale', 1) * random.uniform(20, 50))
                stress_status["requests_sent"] += new_reqs
                
                current_time = time.time()
                if current_time - last_log_check > 15:
                    last_log_check = current_time
                    try:
                        # Pega uma amostra de logs do bot ativo
                        rc_logs, stdout_logs, _ = await run_docker_command(f"logs --tail=3 {preset_config['service']}")
                        if stdout_logs:
                            for line in stdout_logs.strip().split('\n'):
                                clean_line = line.strip()
                                # Limpa sujeira do Docker se existir
                                if '|' in clean_line:
                                    clean_line = clean_line.split('|')[-1].strip()
                                if clean_line: add_stress_log(f"[>] {clean_line}")
                        add_stress_log(f"[*] Status do Cluster: {preset_config['scale']} bots atacando.")
                    except: pass
        finally:
            if stress_status["is_running"]:
                add_stress_log("[*] Tempo de execução atingido.")
            else:
                add_stress_log("[-] Interrupção manual solicitada.")
            await stop_docker_botnet()
            stress_status["is_running"] = False
            add_stress_log("[*] Teste de estresse concluído.")
    else:
        stress_status["is_running"] = False
        add_stress_log("[-] Falha crítica ao subir Docker.")

@router.get("/status")
async def get_stress_status(current_user: dict = Depends(get_current_user)):
    return stress_status

@router.post("/stop")
async def stop_stress_test(current_user: dict = Depends(get_current_user)):
    global stress_status
    stress_status["is_running"] = False
    return {"message": "Sinal de encerramento de emergência enviado."}

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
    
    add_stress_log(f"[*] Orquestrando botnet: {preset_config['name']}...")
    
    # DISPARO EM BACKGROUND: Retorna sucesso imediato para o frontend não dar Timeout.
    background_tasks.add_task(_orchestrate_stress_task, config, preset_config, preset_name)
    
    return {"status": "success", "message": "Comando de estresse recebido. Verifique o console abaixo para acompanhar a subida dos containers."}
