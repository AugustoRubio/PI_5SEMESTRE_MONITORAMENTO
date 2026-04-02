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
            # Strip em cada linha e filtra se não estiver vazia nem começar com #
            urls = []
            for line in f:
                clean_line = line.strip()
                if clean_line and not clean_line.startswith('#'):
                    urls.append(clean_line)
            return urls
    except FileNotFoundError:
        print(f"Erro: Arquivo {URLS_FILE} não encontrado.")
        return []

def simulate_traffic():
    urls = load_urls()
    print(f"[*] Simulador carregou {len(urls)} URLs da lista.")
    
    if not urls:
        print("Nenhuma URL para acessar. Aguardando urls.txt...")
        while not urls:
            time.sleep(10)
            urls = load_urls()

    print(f"[*] Iniciando Bot de Tráfego Web...")
    print(f"[*] Alvo: {TARGET_USER}@{TARGET_IP}")
    
    while True:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        
        try:
            print(f"[*] Tentando conectar em {TARGET_IP}...")
            ssh.connect(TARGET_IP, username=TARGET_USER, password=TARGET_PASS, timeout=15)
            print("[+] Conexão SSH estabelecida com sucesso!")
            
            # Verificação automática de requisitos (curl)
            print("[*] Verificando dependências (curl) na máquina destino...")
            check_cmd = f"which curl || (echo '{TARGET_PASS}' | sudo -S apt-get update -qq && echo '{TARGET_PASS}' | sudo -S apt-get install -y curl -qq)"
            stdin, stdout, stderr = ssh.exec_command(check_cmd)
            exit_status = stdout.channel.recv_exit_status()
            
            if exit_status == 0:
                print("[+] Requisitos prontos.")
            else:
                print(f"[-] Aviso: Pode ter havido um problema ao verificar/instalar o curl.")
            
            print("[*] Iniciando navegação...\n")
            
            last_url_count = len(urls)
            while True:
                urls = load_urls()
                if len(urls) != last_url_count:
                    print(f"[*] Lista de URLs atualizada: {len(urls)} URLs detectadas.")
                    last_url_count = len(urls)

                if not urls:
                    print("[!] Lista de URLs vazia. Aguardando...")
                    time.sleep(10)
                    continue

                url = random.choice(urls)
                user_agent = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
                
                # Usamos aspas simples fortes para a URL no comando shell para evitar expansão de caracteres como &, ?, ;
                # Mas antes escapamos qualquer aspas simples que já exista na URL
                escaped_url = url.replace("'", "'\\''")
                cmd = f"curl -s -L -m 15 -A '{user_agent}' -o /dev/null -w '%{{http_code}}' '{escaped_url}'"
                
                print(f"Acessando: {url}")
                stdin, stdout, stderr = ssh.exec_command(cmd)
                
                # Esperamos o comando terminar e pegamos o código HTTP
                http_code = stdout.read().decode().strip()
                err_output = stderr.read().decode().strip()
                
                if http_code:
                    print(f"Resposta HTTP: {http_code} | Aguardando próximo acesso...")
                elif err_output:
                    print(f"[-] Erro ao acessar: {err_output[:50]}...")
                else:
                    print(f"[-] Erro: Sem resposta do curl.")
                
                time.sleep(random.randint(5, 15))
                
        except KeyboardInterrupt:
            print("\n[!] Simulação interrompida pelo usuário.")
            break
        except Exception as e:
            print(f"[!] Erro na conexão ou execução: {e}")
            print("[*] Reiniciando em 30 segundos...")
            time.sleep(30)
        finally:
            ssh.close()
            print("[-] Conexão SSH encerrada.")

if __name__ == "__main__":
    simulate_traffic()