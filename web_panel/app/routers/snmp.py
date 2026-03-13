import os
import subprocess
from fastapi import APIRouter
from dotenv import load_dotenv

# Carrega as variáveis do .env
load_dotenv()

router = APIRouter()

# Tenta detectar o executável do docker compose automaticamente se não estiver no env
DOCKER_COMPOSE_EXEC = os.getenv("DOCKER_COMPOSE_EXECUTABLE")
if not DOCKER_COMPOSE_EXEC:
    DOCKER_COMPOSE_EXEC = "docker compose"

# Helper function to update snmprec files
def update_snmprec_file(file_path: str, updates: dict):
    if not os.path.exists(file_path):
        return False
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
        
    for i, line in enumerate(lines):
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        
        parts = line.split('|')
        if len(parts) == 3:
            oid = parts[0]
            if oid in updates:
                lines[i] = f"{oid}|{parts[1]}|{updates[oid]}\n"
                
    with open(file_path, 'w') as f:
        f.writelines(lines)
        
    return True

# Helper to read a specific OID value
def get_snmprec_value(file_path: str, target_oid: str):
    if not os.path.exists(file_path):
        return None
    
    with open(file_path, 'r') as f:
        lines = f.readlines()
        
    for line in lines:
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        parts = line.split('|')
        if len(parts) == 3 and parts[0] == target_oid:
            return parts[2]
            
    return None

TEMP_SNMPREC = os.path.join(os.path.dirname(__file__), "../../../snmp_simulator/data/sensor_temp.snmprec")
UPS_SNMPREC = os.path.join(os.path.dirname(__file__), "../../../snmp_simulator/data/nobreak.snmprec")
ROUTER_SNMPREC = os.path.join(os.path.dirname(__file__), "../../../snmp_simulator/data/router_core.snmprec")
SIMULATOR_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../snmp_simulator"))

def run_compose_command(args_list):
    docker_env = os.getenv("DOCKER_COMPOSE_EXECUTABLE")
    env_cmd = docker_env.split() if docker_env else []

    commands_to_try = [
        ["docker", "compose"],
        ["docker-compose"],
        ["/usr/local/bin/docker-compose"],
        ["/usr/libexec/docker/cli-plugins/docker-compose"]
    ]
    if env_cmd:
        commands_to_try.insert(0, env_cmd)

    env_vars = os.environ.copy()
    env_vars["DOCKER_API_VERSION"] = "1.41"

    last_err = None
    for base in commands_to_try:
        try:
            cmd = base + args_list
            result = subprocess.run(cmd, cwd=SIMULATOR_DIR, capture_output=True, text=True, check=True, env=env_vars)
            return True, result.stdout
        except FileNotFoundError as e:
            last_err = e
            continue
        except subprocess.CalledProcessError as e:
            return False, e.stderr

    raise FileNotFoundError(f"Docker compose não encontrado. Último erro: {last_err}")

@router.post("/simulator/start")
async def start_simulator():
    try:
        success, msg = run_compose_command(["up", "-d"])
        if success:
            return {"status": "success", "message": "Simulador SNMP iniciado com sucesso!"}
        return {"status": "error", "message": f"Erro ao iniciar simulador: {msg}"}
    except Exception as e:
        return {"status": "error", "message": f"Erro interno ao iniciar simulador: {str(e)}"}

@router.post("/simulator/stop")
async def stop_simulator():
    try:
        success, msg = run_compose_command(["down"])
        if success:
            return {"status": "success", "message": "Simulador SNMP parado com sucesso!"}
        return {"status": "error", "message": f"Erro ao parar simulador: {msg}"}
    except Exception as e:
        return {"status": "error", "message": f"Erro interno ao parar simulador: {str(e)}"}

@router.get("/simulator/status")
async def simulator_status():
    try:
        success, stdout = run_compose_command(["ps"])
        if success:
            is_running = "Up" in stdout or "running" in stdout.lower()
            return {"is_running": is_running, "status": "Up" if is_running else "Parado"}
        return {"is_running": False, "status": "Erro/Parado"}
    except Exception as e:
        return {"is_running": False, "status": "Erro/Parado"}

@router.post("/temperature/increase")
async def increase_temperature():
    current_temp = float(get_snmprec_value(TEMP_SNMPREC, "1.3.6.1.4.1.2021.255.1.0") or 22)
    new_temp = current_temp + 5
    
    status = "1" # Normal
    if new_temp >= 30:
        status = "3" # Critical
    elif new_temp <= 15:
        status = "2" # Alert
        
    updates = {
        "1.3.6.1.4.1.2021.255.1.0": str(int(new_temp)),
        "1.3.6.1.4.1.2021.255.3.0": status
    }
    
    success = update_snmprec_file(TEMP_SNMPREC, updates)
    if success:
        return {"status": "success", "message": f"Temperatura aumentada para {new_temp}°C no simulador."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}

@router.post("/temperature/decrease")
async def decrease_temperature():
    current_temp = float(get_snmprec_value(TEMP_SNMPREC, "1.3.6.1.4.1.2021.255.1.0") or 22)
    new_temp = current_temp - 5
    
    status = "1" # Normal
    if new_temp >= 30:
        status = "3" # Critical
    elif new_temp <= 15:
        status = "2" # Alert
        
    updates = {
        "1.3.6.1.4.1.2021.255.1.0": str(int(new_temp)),
        "1.3.6.1.4.1.2021.255.3.0": status
    }
    
    success = update_snmprec_file(TEMP_SNMPREC, updates)
    if success:
        return {"status": "success", "message": f"Temperatura diminuída para {new_temp}°C no simulador."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}

@router.post("/ups/power-fail")
async def simulate_power_fail():
    # 1.3.6.1.2.1.33.1.2.1.0 = batteryStatus (3 = batteryLow / 4 = batteryDepleted)
    # 1.3.6.1.2.1.33.1.2.4.0 = battery capacity
    # 1.3.6.1.2.1.33.1.4.1.0 = secondsOnBattery (>0)
    
    updates = {
        "1.3.6.1.2.1.33.1.2.1.0": "3",  # batteryLow or discharging
        "1.3.6.1.2.1.33.1.2.4.0": "85", # Simulating immediate drop
        "1.3.6.1.2.1.33.1.4.1.0": "60"  # 60 seconds on battery
    }
    
    success = update_snmprec_file(UPS_SNMPREC, updates)
    if success:
        return {"status": "success", "message": "Queda de energia simulada. Nobreak em modo bateria."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}

@router.post("/ups/power-restore")
async def simulate_power_restore():
    updates = {
        "1.3.6.1.2.1.33.1.2.1.0": "2",  # batteryNormal
        "1.3.6.1.2.1.33.1.2.4.0": "100", # Fully charged
        "1.3.6.1.2.1.33.1.4.1.0": "0"    # Online
    }
    
    success = update_snmprec_file(UPS_SNMPREC, updates)
    if success:
        return {"status": "success", "message": "Energia restaurada. Nobreak em modo online."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}

@router.post("/router/cpu-spike")
async def simulate_router_cpu_spike():
    updates = {
        "1.3.6.1.2.1.25.3.3.1.2.1": "99"  # 99% CPU load
    }
    
    success = update_snmprec_file(ROUTER_SNMPREC, updates)
    if success:
        return {"status": "success", "message": "Pico de CPU simulado no Roteador."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}

@router.post("/router/cpu-normal")
async def simulate_router_cpu_normal():
    updates = {
        "1.3.6.1.2.1.25.3.3.1.2.1": "15"  # 15% CPU load
    }
    
    success = update_snmprec_file(ROUTER_SNMPREC, updates)
    if success:
        return {"status": "success", "message": "CPU do Roteador normalizada."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}

@router.post("/router/link-down")
async def simulate_router_link_down():
    updates = {
        "1.3.6.1.2.1.2.2.1.8.1": "2"  # 2 = down
    }
    
    success = update_snmprec_file(ROUTER_SNMPREC, updates)
    if success:
        return {"status": "success", "message": "Queda de link (Interface GigabitEthernet0/0) simulada."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}

@router.post("/router/link-up")
async def simulate_router_link_up():
    updates = {
        "1.3.6.1.2.1.2.2.1.8.1": "1"  # 1 = up
    }
    
    success = update_snmprec_file(ROUTER_SNMPREC, updates)
    if success:
        return {"status": "success", "message": "Link do Roteador restabelecido."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}

