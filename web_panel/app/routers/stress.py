import asyncio
import os
import time
import random
import datetime
import re
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
    db_pass: str = "intranet_pass"
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
        now = datetime.datetime.now().strftime("%H:%M:%S")
        # Só adiciona o timestamp se a string não começar com o formato exato [HH:MM:SS]
        if not re.match(r"^\[\d{2}:\d{2}:\d{2}\]", msg):
            msg = f"[{now}] {msg}"
        stress_status["logs"].append(msg)
        if len(stress_status["logs"]) > 150:
            stress_status["logs"].pop(0)

async def run_docker_command(args: str, env=None, timeout=60):
    """Executa um comando docker compose com timeout e fallback."""
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
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except:
                    pass
                return 1, "", f"Erro: Comando '{args}' excedeu o timeout de {timeout}s"
            
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

async def run_docker_cli(args_list, timeout=45):
    """Executa comandos base do docker (não compose) de forma segura tentando múltiplos paths."""
    for base_cmd in ["docker", "/usr/bin/docker", "/usr/local/bin/docker"]:
        try:
            proc = await asyncio.create_subprocess_exec(
                base_cmd, *args_list,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
                return proc.returncode, stdout.decode(errors='ignore').strip(), stderr.decode(errors='ignore').strip()
            except asyncio.TimeoutError:
                try:
                    proc.kill()
                except:
                    pass
                return 1, "", f"Erro: Docker {args_list[0]} excedeu timeout de {timeout}s"
        except FileNotFoundError:
            continue
        except Exception as e:
            return 1, "", str(e)
    return 1, "", "Comando docker não encontrado no PATH."

async def stop_docker_botnet():
    """Tenta derrubar a botnet de forma resiliente."""
    try:
        add_stress_log("[-] Finalizando containers e limpando rede...")
        # Timeout curto para o down, se falhar ou demorar, seguimos para o restart forçado
        returncode, stdout, stderr = await run_docker_command("down", timeout=30)
        if returncode == 0:
            add_stress_log("[+] Ambiente Botnet (Compose) limpo.")
        else:
            add_stress_log(f"[-] Aviso ao limpar ambiente Compose (Pode estar offline).")
            
        # Garante que o ataque SOA seja encerrado de imediato
        add_stress_log("[*] Resetando container de ataque SOA (soa_stress_pi)...")
        await run_docker_cli(["restart", "soa_stress_pi"], timeout=20)
        add_stress_log("[+] Container SOA resetado.")
    except Exception as e:
        add_stress_log(f"[-] Exceção ao derrubar: {e}")

async def _orchestrate_stress_task(config: StressConfig, preset_config: dict, preset_name: str):
    """
    Orquestra o ciclo completo em background para evitar Timeout no servidor Web.
    """
    global stress_status
    
    try:
        # 1. Limpar ambiente anterior
        await stop_docker_botnet()
        await asyncio.sleep(2) # Aguarda a rede do container soa_stress_pi se restabelecer após o restart

        # --- Lógica Exclusiva para o SOA Flood (Apache Bench Centralizado) ---
        if preset_name == "soa_flood":
            base_url = config.target_url.rstrip('/')
            
            # Força o uso de HTTP. O ab tem problemas nativos com certificados self-signed HTTPS em certas distros Alpine.
            if base_url.startswith("https://"):
                base_url = base_url.replace("https://", "http://", 1)
                
            # Garante que o container esteja ligado (caso o usuário não tenha ligado o Docker Manager)
            rc, out, err = await run_docker_cli(["start", "soa_stress_pi"])
            if rc != 0:
                add_stress_log(f"[-] Erro ao ligar bot soa_stress_pi: {err}")
                stress_status["is_running"] = False
                return

            # Garante a instalacao das dependencias (aguarda o lock do gerenciador caso o container tenha recem iniciado)
            add_stress_log("[*] Validando dependências no bot de ataque...")
            await run_docker_cli(["exec", "soa_stress_pi", "sh", "-c", "timeout 30s sh -c \"while ps | grep '[a]pk' | grep -v grep; do sleep 1; done\" && apk add --no-cache curl jq tzdata apache2-utils"], timeout=45)
            
            # Script bash com Pré-Sincronismo e formatação cronológica exata + DIAGNÓSTICOS
            script = f"""
export TZ="BRT3"
TIME_STR=$(date +'%H:%M:%S')
echo "[$TIME_STR] [*] Iniciando Bot de Estresse SOA..." > /tmp/stress.log
echo "[$TIME_STR] [*] Alvo: {base_url}" >> /tmp/stress.log
echo "[$TIME_STR] [*] Realizando pre-sincronismo com a API SOA..." >> /tmp/stress.log

HTTP_CODE=$(curl -4 -k -L -s -o /dev/null -w "%{{http_code}}" -m 15 {base_url}/status)
if [ "$HTTP_CODE" != "200" ]; then
    TIME_STR=$(date +'%H:%M:%S')
    echo "[$TIME_STR] [-] Falha no Pre-Sincronismo: Nginx Inacessivel ($HTTP_CODE)" >> /tmp/stress.log
    echo "[$TIME_STR] [!] DIAGNOSTICO DE REDE NO CAMINHO ALTERNATIVO:" >> /tmp/stress.log
    echo "--- PING TEST ---" >> /tmp/stress.log
    TARGET_HOST=$(echo {base_url} | cut -d/ -f3 | cut -d: -f1)
    ping -c 4 -W 2 $TARGET_HOST >> /tmp/stress.log 2>&1
    echo "--- CURL DETALHADO (Verbose) ---" >> /tmp/stress.log
    curl -4 -k -v -m 5 {base_url}/status >> /tmp/stress.log 2>&1
    echo "--- IP ROUTE ---" >> /tmp/stress.log
    ip route >> /tmp/stress.log
    echo "--- TESTE DE PORTA TCP ---" >> /tmp/stress.log
    TARGET_PORT=$(echo {base_url} | cut -d/ -f3 | cut -d: -f2)
    [ -z "$TARGET_PORT" ] && TARGET_PORT=80
    nc -zv -w 5 $TARGET_HOST $TARGET_PORT >> /tmp/stress.log 2>&1
    echo "[!] DIAGNOSTICO CONCLUIDO. VERIFIQUE ACLs OU MTU DO ROTEADOR." >> /tmp/stress.log
    echo "ABORTANDO_FALHA_CRITICA" >> /tmp/stress.log
    exit 1
fi

TIME_STR=$(date +'%H:%M:%S')
echo "[$TIME_STR] [+] Sincronismo concluido: API Online. Alvos validados." >> /tmp/stress.log

TARGET_ID=$(( ( RANDOM % 500 ) + 1 ))
TARGET_URL="{base_url}/invoices/$TARGET_ID"

TIME_STR=$(date +'%H:%M:%S')
echo "[$TIME_STR] [*] Preparando Apache Bench (DDoS Layer 7) em background..." >> /tmp/stress.log
echo "[$TIME_STR] [*] Alvo Selecionado (BOLA): $TARGET_URL" >> /tmp/stress.log

ab -r -n 500000 -c 500 $TARGET_URL > /tmp/ab.log 2>&1 &

TIME_STR=$(date +'%H:%M:%S')
echo "[$TIME_STR] [+] Carga disparada! 500 conexoes simultaneas ativas." >> /tmp/stress.log

while true; do
    if ! pgrep ab > /dev/null; then
        echo "[$(date +'%H:%M:%S')] [-] Processo 'ab' morreu. Reiniciando..." >> /tmp/stress.log
        ab -r -n 500000 -c 500 $TARGET_URL > /tmp/ab.log 2>&1 &
    fi
    CHECK_ID=$(( ( RANDOM % 500 ) + 1 ))
    CHECK_URL="{base_url}/invoices/$CHECK_ID"
    HTTP_CODE=$(curl -4 -k -L -s -m 5 -o /dev/null -w "%{{http_code}}" $CHECK_URL)
    TIME_STR=$(date +'%H:%M:%S')
    echo "[$TIME_STR] [>] Acessando: $CHECK_URL" >> /tmp/stress.log
    if [ "$HTTP_CODE" = "000" ]; then
        echo "[$TIME_STR] [+] Resposta HTTP: ERR | Nginx Sobrecarregado (Trafego dropado!)" >> /tmp/stress.log
    else
        echo "[$TIME_STR] [>] Resposta HTTP: $HTTP_CODE | Mantendo estresse no backend..." >> /tmp/stress.log
    fi
    sleep 3
done
        """
        
            rc, out, err = await run_docker_cli(["exec", "-d", "soa_stress_pi", "sh", "-c", script])
            
            if rc != 0:
                add_stress_log(f"[-] Falha ao executar script de estresse: {err}")
                stress_status["is_running"] = False
                return
            
            duration = preset_config["duration"]
            end_time = time.time() + duration
            last_line_read = 0
            
            while time.time() < end_time and stress_status["is_running"]:
                for _ in range(3):
                    if not stress_status["is_running"]: break
                    await asyncio.sleep(1)
                    
                if not stress_status["is_running"]: break
                
                # Como o AB está em background no docker, simulamos o contador visual para a UI
                stress_status["requests_sent"] += random.randint(1500, 3000)
                
                # Busca os logs reais gerados pelo script em bash de forma incremental para manter o historico
                # Usamos tail para não sobrecarregar o container lendo o arquivo inteiro toda vez
                rc_logs, stdout_logs, _ = await run_docker_cli(["exec", "soa_stress_pi", "tail", "-n", "20", "/tmp/stress.log"], timeout=10)
                if rc_logs == 0 and stdout_logs:
                    lines = [line.strip() for line in stdout_logs.strip().split('\n') if line.strip()]
                    # Adiciona apenas linhas que ainda não foram processadas (baseado no conteúdo)
                    for line in lines:
                        if line not in stress_status["logs"]:
                            add_stress_log(line)
                    
                    if any("ABORTANDO_FALHA_CRITICA" in line for line in lines):
                        stress_status["is_running"] = False
                        add_stress_log("[-] Orquestração interrompida devido a bloqueios de rede.")
                        break
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
        returncode, stdout_up, stderr_up = await run_docker_command(args_up, env=env_vars, timeout=90)
        
        if returncode == 0:
            add_stress_log(f"[+] Botnet ativa! {preset_config['scale']} agentes em combate.")
            
            # 3. Iniciar monitoramento
            duration = preset_config["duration"]
            end_time = time.time() + duration
            last_log_check = 0
                
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
                        rc_logs, stdout_logs, _ = await run_docker_command(f"logs --tail=3 {preset_config['service']}", timeout=10)
                        if stdout_logs:
                            for line in stdout_logs.strip().split('\n'):
                                clean_line = line.strip()
                                # Limpa sujeira do Docker se existir
                                if '|' in clean_line:
                                    clean_line = clean_line.split('|')[-1].strip()
                                if clean_line: add_stress_log(f"[>] {clean_line}")
                        add_stress_log(f"[*] Status do Cluster: {preset_config['scale']} bots atacando.")
                    except: pass
        else:
            stress_status["is_running"] = False
            add_stress_log(f"[-] Falha crítica ao subir Docker: {stderr_up}")
    except Exception as e:
        add_stress_log(f"[-] Erro inesperado na orquestração: {e}")
        stress_status["is_running"] = False
    finally:
        add_stress_log("[*] Iniciando limpeza de segurança...")
        stress_status["is_running"] = False
        await stop_docker_botnet()
        add_stress_log("[*] Teste encerrado e ambiente limpo.")


@router.get("/status")
async def get_stress_status(current_user: dict = Depends(get_current_user)):
    return {**stress_status, "server_time": time.time()}

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
