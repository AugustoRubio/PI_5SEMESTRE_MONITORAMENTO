import subprocess
import time
import re
import datetime

# --- CONFIGURACOES DO AUTOSCALING ---
TARGET_SERVICE = "billing_api"
MIN_REPLICAS = 3
MAX_REPLICAS = 15
SCALE_UP_CPU = 75.0   # Escala se a media de CPU passar de 75%
SCALE_DOWN_CPU = 20.0 # Reduz se a media de CPU cair abaixo de 20%
CHECK_INTERVAL = 5    # Checa a cada 5 segundos
COOLDOWN_PERIOD = 20  # Espera 20 segundos apos escalar para checar de novo

current_replicas = MIN_REPLICAS

def log(msg):
    now = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{now}] {msg}")

def get_containers_cpu():
    """Obtem a porcentagem de CPU dos containers da API"""
    try:
        # Roda o docker stats apenas uma vez (--no-stream)
        result = subprocess.run(
            ["docker", "stats", "--no-stream", "--format", "{{.Name}}|{{.CPUPerc}}"],
            capture_output=True, text=True, check=True
        )
        
        total_cpu = 0.0
        count = 0
        
        for line in result.stdout.strip().split('\n'):
            if not line: continue
            name, cpu_str = line.split('|')
            
            # Filtra apenas os containers do backend (ignorando o Nginx/Load Balancer)
            if TARGET_SERVICE in name and "lb" not in name:
                # Remove o simbolo de '%' e converte para float
                cpu_val = float(cpu_str.replace('%', '').strip())
                total_cpu += cpu_val
                count += 1
                
        if count == 0:
            return 0.0
            
        return total_cpu / count
    except Exception as e:
        log(f"Erro ao ler Docker Stats: {e}")
        return 0.0

def scale_service(replicas):
    """Executa o comando nativo e seguro do Docker Compose para escalar"""
    global current_replicas
    log(f"[*] Solicitando alteracao para {replicas} replicas...")
    try:
        subprocess.run(
            ["docker", "compose", "up", "-d", "--scale", f"{TARGET_SERVICE}={replicas}"],
            capture_output=True, text=True, check=True
        )
        current_replicas = replicas
        log(f"[+] Escalonamento concluido. Total de replicas ativas: {current_replicas}")
        
        # Forca o Nginx a refazer a resolucao DNS e enxergar as novas maquinas
        log("[*] Recarregando Load Balancer (Nginx) para distribuir carga...")
        subprocess.run(
            ["docker", "compose", "exec", "billing_lb", "nginx", "-s", "reload"],
            capture_output=True, text=True, check=False
        )

        log(f"[*] Entrando em Cooldown de {COOLDOWN_PERIOD}s para a rede estabilizar...")
        time.sleep(COOLDOWN_PERIOD)
    except subprocess.CalledProcessError as e:
        log(f"[-] Erro critico ao tentar escalar: {e.stderr}")

def main():
    log(f"Iniciando Monitor de Autoscaling para o servico '{TARGET_SERVICE}'")
    log(f"Limites: Min {MIN_REPLICAS} | Max {MAX_REPLICAS}")
    
    # Forca o estado inicial limpo
    scale_service(MIN_REPLICAS)
    
    while True:
        avg_cpu = get_containers_cpu()
        
        # log(f"Media de CPU atual: {avg_cpu:.2f}% (Replicas: {current_replicas})")
        
        if avg_cpu > SCALE_UP_CPU and current_replicas < MAX_REPLICAS:
            log(f"[!] ALERTA DE CARGA: CPU Media em {avg_cpu:.2f}%. Acionando Scale UP!")
            new_replicas = min(current_replicas + 3, MAX_REPLICAS) # Sobe de 3 em 3
            scale_service(new_replicas)
            
        elif avg_cpu < SCALE_DOWN_CPU and current_replicas > MIN_REPLICAS:
            log(f"[*] Carga normalizada: CPU Media em {avg_cpu:.2f}%. Acionando Scale DOWN.")
            new_replicas = max(current_replicas - 2, MIN_REPLICAS) # Desce de 2 em 2
            scale_service(new_replicas)
            
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    main()