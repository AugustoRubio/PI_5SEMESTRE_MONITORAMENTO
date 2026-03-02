import time
import random
import os
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

def bot_routine():
    target_url = os.getenv('TARGET_URL', 'http://172.16.1.100')
    bot_type = os.getenv('BOT_TYPE', 'student') # student, professor, ou ddos

    print(f"[*] Bot Iniciado. Tipo: {bot_type} | Alvo: {target_url}")

    session = requests.Session()
    session.verify = False
    session.headers.update({
        'User-Agent': f'Botnet-Agent-{random.randint(1000, 9999)} Mozilla/5.0'
    })
    
    while True:
        try:
            if bot_type == 'student':
                # Simula um aluno navegando na plataforma (Leitura)
                print(f"[>] Aluno acessando a página inicial {target_url}...")
                session.get(target_url, timeout=5)
                time.sleep(random.uniform(1.0, 3.0))
                
            elif bot_type == 'professor':
                # Simula um professor logando e enviando notas (Escrita)
                print(f"[>] Professor logando no painel {target_url}...")
                session.get(f"{target_url}/login", timeout=5)
                time.sleep(1)
                
                # Payload simulando o cadastro de um aluno
                dummy_student = {
                    "username": f"aluno_teste_{random.randint(100, 999)}",
                    "password": "senha",
                    "nome_completo": "Aluno Teste Carga",
                    "email": "aluno@escola.local",
                    "role": "aluno"
                }
                
                # Tenta postar na API de usuários
                print(f"[+] Professor cadastrando notas em {target_url}/api/users/ ...")
                session.post(f"{target_url}/api/users/", json=dummy_student, timeout=5)
                time.sleep(random.uniform(2.0, 5.0))
                
            elif bot_type == 'ddos':
                # Flooding contínuo sem pausas
                payload = {'data': "".join(random.choices('abcdef0123456789', k=10240))} # 500KB
                session.post(f"{target_url}", json=payload, timeout=10)
                
        except Exception as e:
            print(f"[!] Erro de conexão com o alvo: {str(e)[:50]}...")
            time.sleep(2) # Pausa antes de tentar de novo, para não quebrar o container

if __name__ == '__main__':
    bot_routine()
