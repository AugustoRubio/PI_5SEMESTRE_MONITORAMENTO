#!/bin/bash
# Script de instalação e configuração da Intranet (Sem Docker)
# Este script deve ser executado no servidor AlmaLinux 9 (VM GNS3)

echo "Iniciando configuração da Intranet no AlmaLinux 9..."

# 1. Instalar dependências do sistema
sudo dnf update -y
sudo dnf install -y epel-release
sudo dnf install -y python3 python3-pip mariadb-server nginx policycoreutils-python-utils

# 2. Configurar o MariaDB
echo "Configurando o MariaDB..."
sudo systemctl start mariadb
sudo systemctl enable mariadb

# Permitir conexões remotas no MariaDB (AlmaLinux)
# No AlmaLinux, o arquivo de configuração costuma ser /etc/my.cnf.d/mariadb-server.cnf
if [ -f /etc/my.cnf.d/mariadb-server.cnf ]; then
    sudo sed -i '/\[mysqld\]/a bind-address=0.0.0.0' /etc/my.cnf.d/mariadb-server.cnf
    sudo systemctl restart mariadb
fi

# Aguarda o MariaDB iniciar completamente
sleep 3

# Cria o banco de dados e o usuário (se não existirem)
# ATENÇÃO: Em produção, altere a senha 'intranet_pass'
sudo mysql -e "CREATE DATABASE IF NOT EXISTS intranet_db;"
sudo mysql -e "CREATE USER IF NOT EXISTS 'intranet_user'@'localhost' IDENTIFIED BY 'intranet_pass';"
sudo mysql -e "CREATE USER IF NOT EXISTS 'intranet_user'@'%' IDENTIFIED BY 'intranet_pass';"
sudo mysql -e "GRANT ALL PRIVILEGES ON intranet_db.* TO 'intranet_user'@'localhost';"
sudo mysql -e "GRANT ALL PRIVILEGES ON intranet_db.* TO 'intranet_user'@'%';"
sudo mysql -e "FLUSH PRIVILEGES;"

# 3. Configurar o ambiente Python
echo "Configurando o ambiente Python..."
cd web
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cd ..

# 4. Configurar o Nginx e SELinux
echo "Configurando o Nginx e SELinux..."

# No AlmaLinux/RHEL, as configurações de sites ficam em /etc/nginx/conf.d/
sudo cp nginx/default.conf /etc/nginx/conf.d/intranet.conf

# O SELinux vem ativado por padrão no AlmaLinux. 
# Precisamos permitir que o Nginx faça proxy reverso (conexões de rede) para o Uvicorn na porta 8000.
sudo setsebool -P httpd_can_network_connect 1

sudo systemctl enable nginx
sudo systemctl restart nginx

# 5. Configurar o Firewall (Firewalld)
echo "Configurando o Firewall..."
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=3306/tcp
sudo firewall-cmd --reload

# 6. Criar serviço Systemd para a aplicação FastAPI
echo "Criando serviço systemd para a Intranet..."

# Obtém o diretório atual absoluto onde o script está sendo executado
INTRANET_DIR=$(pwd)
WEB_DIR="$INTRANET_DIR/web"

cat <<EOF | sudo tee /etc/systemd/system/intranet.service
[Unit]
Description=Intranet FastAPI Application
After=network.target mariadb.service

[Service]
User=$USER
WorkingDirectory=$WEB_DIR
Environment="PATH=$WEB_DIR/venv/bin"
EnvironmentFile=-$WEB_DIR/.env
ExecStart=$WEB_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 75

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable intranet.service
sudo systemctl start intranet.service

echo "Configuração concluída! A intranet deve estar rodando na porta 443 (HTTPS) via Nginx."
echo "Lembre-se de criar o arquivo .env na pasta web/ baseado no .env.example com as credenciais corretas."
