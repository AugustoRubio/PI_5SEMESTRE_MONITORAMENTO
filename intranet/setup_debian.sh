#!/bin/bash
# Script de instalação e configuração da Intranet (Sem Docker)
# Este script deve ser executado no servidor Debian (VM GNS3)

set -e # Aborta se algum comando falhar

echo "Iniciando configuração da Intranet no Debian..."

# 1. Instalar dependências do sistema
sudo apt update
sudo apt install -y python3 python3-venv python3-pip mariadb-server nginx php-fpm php-mysql

# Identificar a versão do PHP instalada para configurar o socket corretamente
PHP_VERSION=$(php -r 'echo PHP_MAJOR_VERSION.".".PHP_MINOR_VERSION;')
PHP_SOCK="/var/run/php/php$PHP_VERSION-fpm.sock"
echo "Detectada versão do PHP: $PHP_VERSION. Socket: $PHP_SOCK"

# 2. Configurar o MariaDB
echo "Configurando o MariaDB..."
sudo systemctl start mariadb
sudo systemctl enable mariadb

# Permitir conexões remotas no MariaDB
sudo sed -i 's/bind-address            = 127.0.0.1/bind-address            = 0.0.0.0/' /etc/mysql/mariadb.conf.d/50-server.cnf
sudo systemctl restart mariadb

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
# O script presume que você o executa do diretório 'intranet'
cd web
python3 -m venv venv
source venv/bin/activate
pip install --upgrade -r requirements.txt

# Cria o arquivo .env se não existir
if [ ! -f .env ]; then
    echo "Criando arquivo .env a partir do .env.example..."
    cp .env.example .env
fi

# Executa migrações do banco
echo "Executando migrações do banco de dados..."
python migrate_db.py
cd ..

# 4. Configurar o Nginx e Certificados
echo "Configurando o Nginx e Certificados..."
sudo mkdir -p /etc/nginx/ssl
sudo cp certs/cert.pem /etc/nginx/ssl/cert.pem
sudo cp certs/key.pem /etc/nginx/ssl/key.pem

# Ajustar o socket do PHP na configuração do Nginx para a versão instalada
# Criamos uma cópia temporária para não alterar o arquivo original do repositório
cp nginx/default.conf nginx/default.conf.tmp
sed -i "s|fastcgi_pass unix:/var/run/php/php8.3-fpm.sock;|fastcgi_pass unix:$PHP_SOCK;|g" nginx/default.conf.tmp

sudo cp nginx/default.conf.tmp /etc/nginx/sites-available/intranet
rm nginx/default.conf.tmp

sudo ln -sf /etc/nginx/sites-available/intranet /etc/nginx/sites-enabled/
if [ -f /etc/nginx/sites-enabled/default ]; then
    sudo rm /etc/nginx/sites-enabled/default
fi
sudo nginx -t && sudo systemctl restart nginx

# 5. Criar serviço Systemd para a aplicação FastAPI
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
Group=$(id -gn $USER)
WorkingDirectory=$WEB_DIR
Environment="PATH=$WEB_DIR/venv/bin"
EnvironmentFile=-$WEB_DIR/.env
ExecStart=$WEB_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000 --timeout-keep-alive 75
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable intranet.service
sudo systemctl restart intranet.service

echo "Configuração concluída! A intranet deve estar rodando em HTTPS (porta 443) via Nginx."
echo "Nota: O PHP-FPM foi configurado para a versão $PHP_VERSION para suportar o phpMyAdmin."
