#!/bin/bash
# Script de instalação e configuração da Intranet para Ubuntu 24.04 (Sem Docker)
# Este script deve ser executado no servidor Ubuntu.

echo "Iniciando configuração da Intranet no Ubuntu 24.04..."

# 1. Instalar dependências do sistema
echo "Instalando dependências..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip mariadb-server nginx

# 2. Configurar o MariaDB
echo "Configurando o MariaDB..."
sudo systemctl start mariadb
sudo systemctl enable mariadb

# Cria o banco de dados e o usuário (se não existirem)
# ATENÇÃO: Em produção, altere a senha 'intranet_pass'
sudo mysql -e "CREATE DATABASE IF NOT EXISTS intranet_db;"
sudo mysql -e "CREATE USER IF NOT EXISTS 'intranet_user'@'localhost' IDENTIFIED BY 'intranet_pass';"
sudo mysql -e "GRANT ALL PRIVILEGES ON intranet_db.* TO 'intranet_user'@'localhost';"
sudo mysql -e "FLUSH PRIVILEGES;"

# 3. Configurar o ambiente Python
echo "Configurando o ambiente Python..."
# O script presume que você o executa do diretório 'intranet'
cd web
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

# 4. Configurar o Firewall (UFW)
echo "Configurando o Firewall (UFW)..."
sudo ufw allow 'Nginx Full' # Permite tráfego HTTP e HTTPS
sudo ufw allow 8000/tcp # Porta da aplicação para troubleshooting
sudo ufw enable # Habilita o firewall (pode pedir confirmação)
sudo ufw status

# 5. Configurar o Nginx
echo "Configurando o Nginx..."

# Cria o diretório para os certificados SSL e copia os certificados
echo "Copiando certificados SSL..."
sudo mkdir -p /etc/nginx/ssl
# O script espera que os certificados estejam em ../certs relativo ao script
sudo cp certs/cert.pem /etc/nginx/ssl/cert.pem
sudo cp certs/key.pem /etc/nginx/ssl/key.pem

# Copia a configuração do Nginx
echo "Aplicando configuração do Nginx..."
# O caminho para a conf do nginx deve ser relativo ao local de execução do script
sudo cp nginx/default.conf /etc/nginx/sites-available/intranet
# Cria o link simbólico para ativar o site
sudo ln -sf /etc/nginx/sites-available/intranet /etc/nginx/sites-enabled/
# Remove o site padrão do Nginx para evitar conflitos
if [ -f /etc/nginx/sites-enabled/default ]; then
    sudo rm /etc/nginx/sites-enabled/default
fi
# Testa a configuração do Nginx e reinicia o serviço
echo "Reiniciando o Nginx..."
sudo nginx -t && sudo systemctl restart nginx

# 6. Criar serviço Systemd para a aplicação FastAPI
echo "Criando serviço systemd para a Intranet..."

# Obtém o diretório absoluto de onde o script está sendo executado
# Importante: Execute este script a partir do diretório 'intranet'
INTRANET_DIR=$(pwd)
WEB_DIR="$INTRANET_DIR/web"

cat <<EOF | sudo tee /etc/systemd/system/intranet.service
[Unit]
Description=Intranet FastAPI Application
After=network.target mariadb.service

[Service]
User=$USER
Group=$(id -gn $USER)
WorkingDirectory=$WEB_DIR
Environment="PATH=$WEB_DIR/venv/bin"
# O arquivo .env deve estar em web/
EnvironmentFile=$WEB_DIR/.env
ExecStart=$WEB_DIR/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable intranet.service
sudo systemctl start intranet.service

echo "------------------------------------------------------------------"
echo "Configuração concluída!"
echo "A intranet deve estar rodando na porta 80 (HTTP) e 443 (HTTPS) via Nginx."
echo ""
echo "LEMBRE-SE:"
echo "1. Crie o arquivo .env na pasta 'intranet/web/' baseado no 'intranet/web/.env.example'."
echo "2. Atualize o .env com as credenciais corretas do banco de dados."
echo "3. Certifique-se que os certificados SSL ('cert.pem', 'key.pem') estão no diretório 'intranet/certs/'."
echo "------------------------------------------------------------------"
