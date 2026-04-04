import subprocess
import time
import json

MAX_REPLICAS = 10
MIN_REPLICAS = 3
CPU_THRESHOLD = 80.0 # Se a média de CPU passar de 80%, aumenta as máquinas

current_replicas = MIN_REPLICAS

def get_cpu_usage():
    try:
        # 1. Descobre os IDs apenas dos containers que pertencem ao billing_api
        ps_result = subprocess.run(
            ["docker", "ps", "-q", "-f", "name=billing_api"],
            capture_output=True, text=True
        )
        container_ids = ps_result.stdout.strip().split('\n')
        if not container_ids or not container_ids[0]: return 0
        
        # 2. Pega o uso de CPU exclusivo desses containers
        stats_cmd = ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}"] + container_ids
        stats_result = subprocess.run(stats_cmd, capture_output=True, text=True)
        lines = [line.strip().replace('%', '') for line in stats_result.stdout.split('\n') if line.strip()]
        if not lines: return 0
        
        # Calcula a média de uso de CPU
        total_cpu = sum(float(cpu) for cpu in lines)
        return total_cpu / len(lines)
    except Exception as e:
        print(f"Erro ao ler docker stats: {e}")
        return 0

def scale_service(replicas):
    print(f"Escalonando billing_api para {replicas} réplicas...")
    subprocess.run(["docker", "compose", "up", "--scale", f"billing_api={replicas}", "-d"])

print("Iniciando Monitoramento de Autoscale do SOA...")
while True:
    cpu_avg = get_cpu_usage()
    print(f"Média de CPU Atual: {cpu_avg:.2f}% | Réplicas: {current_replicas}")

    if cpu_avg > CPU_THRESHOLD and current_replicas < MAX_REPLICAS:
        current_replicas += 2
        print(f"ALERTA: Alta carga detectada! Subindo novas instâncias...")
        scale_service(current_replicas)
    
    elif cpu_avg < (CPU_THRESHOLD / 2) and current_replicas > MIN_REPLICAS:
        # Se a carga caiu bastante, diminui as instâncias aos poucos para economizar recursos
        current_replicas -= 1
        print(f"Carga normalizada. Reduzindo instâncias...")
        scale_service(current_replicas)

    time.sleep(10)
