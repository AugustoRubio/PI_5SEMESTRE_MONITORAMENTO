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

@router.get("/simulator/logs")
async def simulator_logs():
    try:
        success, stdout = run_compose_command(["logs", "--tail=50"])
        if success:
            return {"status": "success", "logs": stdout}
        return {"status": "error", "message": f"Erro ao buscar logs: {stdout}"}
    except Exception as e:
        return {"status": "error", "message": f"Erro interno ao buscar logs: {str(e)}"}

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
    
    # Atualiza tanto o sensor dedicado quanto a probe do nobreak APC (para Zabbix)
    success = update_snmprec_file(TEMP_SNMPREC, updates)
    update_snmprec_file(UPS_SNMPREC, {"1.3.6.1.4.1.318.1.1.25.1.2.1.3.1.1": str(int(new_temp))})
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
    update_snmprec_file(UPS_SNMPREC, {"1.3.6.1.4.1.318.1.1.25.1.2.1.3.1.1": str(int(new_temp))})
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
        "1.3.6.1.2.1.33.1.4.1.0": "60", # 60 seconds on battery
        
        # OIDs Específicos da APC
        "1.3.6.1.4.1.318.1.1.1.2.1.1.0": "3",  # upsBasicBatteryStatus = onBattery
        "1.3.6.1.4.1.318.1.1.1.2.2.1.0": "85", # upsAdvBatteryCapacity = 85%
        "1.3.6.1.4.1.318.1.1.1.2.1.2.0": "6000", # upsBasicBatteryTimeOnBattery (60s em centésimos)
        "1.3.6.1.4.1.318.1.1.1.3.3.4.0": "4",  # upsAdvInputLineFailCause = blackout
        "1.3.6.1.4.1.318.1.1.1.3.3.1.0": "0"   # upsAdvInputVoltage = 0v
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
        "1.3.6.1.2.1.33.1.4.1.0": "0",   # Online
        
        # OIDs Específicos da APC
        "1.3.6.1.4.1.318.1.1.1.2.1.1.0": "2",  # upsBasicBatteryStatus = normal
        "1.3.6.1.4.1.318.1.1.1.2.2.1.0": "100", # upsAdvBatteryCapacity = 100%
        "1.3.6.1.4.1.318.1.1.1.2.1.2.0": "0", # upsBasicBatteryTimeOnBattery = 0s
        "1.3.6.1.4.1.318.1.1.1.3.3.4.0": "1",  # upsAdvInputLineFailCause = noTransfer
        "1.3.6.1.4.1.318.1.1.1.3.3.1.0": "120" # upsAdvInputVoltage = 120v
    }
    
    success = update_snmprec_file(UPS_SNMPREC, updates)
    if success:
        return {"status": "success", "message": "Energia restaurada. Nobreak em modo online."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}


@router.post("/humidity/increase")
async def increase_humidity():
    current_hum = float(get_snmprec_value(TEMP_SNMPREC, "1.3.6.1.4.1.2021.255.2.0") or 45)
    new_hum = min(current_hum + 10, 100)
    
    success = update_snmprec_file(TEMP_SNMPREC, {"1.3.6.1.4.1.2021.255.2.0": str(int(new_hum))})
    if success:
        return {"status": "success", "message": f"Umidade aumentada para {new_hum}% no simulador."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}

@router.post("/humidity/decrease")
async def decrease_humidity():
    current_hum = float(get_snmprec_value(TEMP_SNMPREC, "1.3.6.1.4.1.2021.255.2.0") or 45)
    new_hum = max(current_hum - 10, 0)
    
    success = update_snmprec_file(TEMP_SNMPREC, {"1.3.6.1.4.1.2021.255.2.0": str(int(new_hum))})
    if success:
        return {"status": "success", "message": f"Umidade diminuída para {new_hum}% no simulador."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}

@router.post("/ups/high-load")
async def simulate_ups_high_load():
    updates = {
        "1.3.6.1.4.1.318.1.1.1.4.3.3.0": "98", # upsAdvOutputLoad = 98%
        "1.3.6.1.4.1.318.1.1.1.4.3.4.0": "25"  # upsAdvOutputCurrent = 25A
    }
    success = update_snmprec_file(UPS_SNMPREC, updates)
    if success:
        return {"status": "success", "message": "Alta carga simulada (98%)."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}

@router.post("/ups/normal-load")
async def simulate_ups_normal_load():
    updates = {
        "1.3.6.1.4.1.318.1.1.1.4.3.3.0": "15", # upsAdvOutputLoad = 15%
        "1.3.6.1.4.1.318.1.1.1.4.3.4.0": "10"  # upsAdvOutputCurrent = 10A
    }
    success = update_snmprec_file(UPS_SNMPREC, updates)
    if success:
        return {"status": "success", "message": "Carga normalizada (15%)."}
    return {"status": "error", "message": "Falha ao atualizar o simulador."}



