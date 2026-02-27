#!/bin/bash
# Script de instalação e configuração da Intranet (Sem Docker)
# Este script deve ser executado no servidor Debian (VM GNS3)

echo "Iniciando configuração da Intranet..."

# 1. Instalar dependências do sistema
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
cd /caminho/para/sua/pasta/intranet/web # <-- ALTERE ESTE CAMINHO NO SERVIDOR
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 4. Configurar o Nginx
echo "Configurando o Nginx..."
# Copia a configuração do Nginx (ajuste o caminho conforme necessário)
sudo cp ../nginx/default.conf /etc/nginx/sites-available/intranet
sudo ln -s /etc/nginx/sites-available/intranet /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default # Remove o site padrão do Nginx
sudo systemctl restart nginx

# 5. Criar serviço Systemd para a aplicação FastAPI (Opcional, mas recomendado)
echo "Criando serviço systemd para a Intranet..."
cat <<EOF | sudo tee /etc/systemd/system/intranet.service
[Unit]
Description=Intranet FastAPI Application
After=network.target mariadb.service

[Service]
User=$USER
WorkingDirectory=/caminho/para/sua/pasta/intranet/web # <-- ALTERE ESTE CAMINHO
Environment="PATH=/caminho/para/sua/pasta/intranet/web/venv/bin" # <-- ALTERE ESTE CAMINHO
EnvironmentFile=/caminho/para/sua/pasta/intranet/web/.env # <-- CRIE ESTE ARQUIVO BASEADO NO .env.example
ExecStart=/caminho/para/sua/pasta/intranet/web/venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable intranet.service
sudo systemctl start intranet.service

echo "Configuração concluída! A intranet deve estar rodando na porta 443 (HTTPS) via Nginx."
echo "Lembre-se de criar o arquivo .env na pasta web/ baseado no .env.example com as credenciais corretas."
