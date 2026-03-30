import paramiko
import time
import random
import os

# Configurações lidas do Docker (Variáveis de Ambiente)
TARGET_IP = os.getenv("TARGET_IP", "192.168.1.100")
TARGET_USER = os.getenv("TARGET_USER", "ubuntu")
TARGET_PASS = os.getenv("TARGET_PASS", "senha")
URLS_FILE = os.getenv("URLS_FILE", "urls.txt")

def load_urls():
    try:
        with open(URLS_FILE, 'r') as f:
            return [line.strip() for line in f if line.strip() and not line.startswith('#')]
    except FileNotFoundError:
        print(f"Erro: Arquivo {URLS_FILE} não encontrado.")
        return []

def simulate_traffic():
    urls = load_urls()
    if not urls:
        print("Nenhuma URL para acessar. Encerrando.")
        return

    print(f"[*] Iniciando Bot de Tráfego Web...")
    print(f"[*] Conectando via SSH em {TARGET_USER}@{TARGET_IP}...")
    
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        ssh.connect(TARGET_IP, username=TARGET_USER, password=TARGET_PASS, timeout=10)
        print("[+] Conexão SSH estabelecida com sucesso! Iniciando navegação...\n")
        
        while True:
            url = random.choice(urls)
            # Simula um navegador real. -s (silent), -L (follow redirects), -m 15 (timeout de 15s), -o /dev/null (descarta o arquivo baixado)
            user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            cmd = f'curl -s -L -m 15 -A "{user_agent}" -o /dev/null -w "%{{http_code}}" "{url}"'
            
            print(f"Acessando: {url}")
            stdin, stdout, stderr = ssh.exec_command(cmd)
            http_code = stdout.read().decode().strip()
            print(f"Resposta HTTP: {http_code} | Aguardando próximo acesso...")
            
            # Pausa de 5 a 15 segundos para simular a leitura humana da página e não causar DDoS
            time.sleep(random.randint(5, 15))
            
    except KeyboardInterrupt:
        print("\n[!] Simulação interrompida.")
    except Exception as e:
        print(f"[!] Erro na conexão ou execução: {e}")
    finally:
        ssh.close()
        print("[-] Conexão SSH encerrada.")

if __name__ == "__main__":
    simulate_traffic()