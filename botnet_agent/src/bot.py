import time
import random
import os
import requests
import urllib3
import pymysql
import datetime
import urllib.parse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Configurações do Banco de Dados Alvo (necessário para pegar usuários reais)
DB_HOST = os.getenv('DB_HOST', '10.10.100.4')
DB_PORT = int(os.getenv('DB_PORT', '3306'))
DB_USER = os.getenv('DB_USER', 'intranet_user')
DB_PASS = os.getenv('DB_PASS', 'bcd127')
DB_NAME = os.getenv('DB_NAME', 'intranet_db')

def get_random_user(role):
    """Busca um usuário aleatório do tipo especificado no banco da Intranet."""
    try:
        conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME)
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            if role == 'student':
                cursor.execute("SELECT registration as username, 'senha123' as password FROM students WHERE password IS NOT NULL ORDER BY RAND() LIMIT 1")
            else:
                cursor.execute("SELECT username, 'senha123' as password, id FROM professors WHERE password IS NOT NULL ORDER BY RAND() LIMIT 1")
            return cursor.fetchone()
    except:
        return None
    finally:
        if 'conn' in locals(): conn.close()

def bot_routine():
    target_url = os.getenv('TARGET_URL', 'https://10.10.100.4').rstrip('/')
    bot_type = os.getenv('BOT_TYPE', 'student') 

    print(f"[*] Bot Iniciado. Tipo: {bot_type} | Alvo: {target_url}")

    while True:
        session = requests.Session()
        session.verify = False
        session.headers.update({'User-Agent': f'Bot-Agent-{random.randint(100,999)}'})

        try:
            if bot_type == 'ddos':
                payload = {'data': "X" * 10240} # 10KB
                session.post(target_url, data=payload, timeout=5)
                continue

            # --- FLUXO DE LOGIN REAL ---
            user = get_random_user(bot_type)
            if not user:
                print(f"[!] Sem usuários {bot_type} no DB. Tentando novamente...")
                time.sleep(5); continue

            login_data = {
                "username": user['username'],
                "password": user['password'],
                "login_type": bot_type
            }
            
            print(f"[>] Login: {user['username']} ({bot_type}) em {target_url}...")
            res = session.post(f"{target_url}/login", data=login_data, timeout=10, allow_redirects=True)
            
            if "dashboard" in res.url.lower():
                print(f"[+] Login bem-sucedido: {user['username']}")
                
                if bot_type == 'student':
                    # Aluno: Visualiza Dashboard (Leitura)
                    print(f"📡 Aluno {user['username']} visualizando notas...")
                    session.get(f"{target_url}/student_dashboard", timeout=5)
                    time.sleep(random.uniform(5, 15)) # Tempo de "leitura"
                    
                elif bot_type == 'professor':
                    # Professor: Lança Notas e Faltas (Escrita)
                    conn = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS, database=DB_NAME)
                    with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                        cursor.execute(f"SELECT id FROM classes WHERE professor_id = {user['id']} LIMIT 1")
                        cls = cursor.fetchone()
                        if cls:
                            class_id = cls['id']
                            # 1. Lança uma Nota
                            cursor.execute(f"SELECT student_id FROM student_class WHERE class_id = {class_id} ORDER BY RAND() LIMIT 1")
                            st = cursor.fetchone()
                            if st:
                                grade_data = {"student_id": st['student_id'], "value": str(random.randint(5,10)), "description": "Prova Bimestral"}
                                session.post(f"{target_url}/prof_dashboard/class/{class_id}/grade", data=grade_data, timeout=5)
                                print(f"📝 Professor {user['username']} lançou nota para aluno {st['student_id']}.")

                            # 2. Marca Faltas (Hoje)
                            today = datetime.datetime.now().strftime("%Y-%m-%d")
                            cursor.execute(f"SELECT student_id FROM student_class WHERE class_id = {class_id} ORDER BY RAND() LIMIT 3")
                            absent_ids = [str(r['student_id']) for r in cursor.fetchall()]
                            
                            # O FastAPI espera múltiplos campos 'absent_students' para listas
                            att_data = [('date', today)]
                            for s_id in absent_ids: att_data.append(('absent_students', s_id))
                            
                            session.post(f"{target_url}/prof_dashboard/class/{class_id}/attendance", data=att_data, timeout=5)
                            print(f"📋 Professor {user['username']} marcou {len(absent_ids)} faltas na turma {class_id}.")
                    conn.close()
                    time.sleep(random.uniform(3, 8))

                session.get(f"{target_url}/logout", timeout=5)
                print(f"[-] Logout: {user['username']}")
            else:
                print(f"[!] Falha no login para {user['username']}. Verifique credenciais.")
            
            time.sleep(random.uniform(2, 5))

        except Exception as e:
            print(f"[!] Erro: {str(e)[:60]}")
            time.sleep(5)

if __name__ == '__main__':
    bot_routine()
