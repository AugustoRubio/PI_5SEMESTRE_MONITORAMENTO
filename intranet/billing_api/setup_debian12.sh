#!/bin/bash
# Script de instalacao automatica do Docker e dependencias no Debian 12 (Bookworm)
# para o servico Billing API

echo "=========================================================="
echo " Instalacao do Docker e Dependencias - Debian 12 (Bookworm)"
echo "=========================================================="

# Verifica se o script esta rodando como root
if [ "$EUID" -ne 0 ]; then
  echo "Por favor, execute como root (sudo ./setup_debian12.sh)"
  exit
fi

# 1. Atualizar repositorios
echo "[+] Atualizando repositorios..."
apt update && apt upgrade -y

# 2. Instalar dependencias basicas
echo "[+] Instalando dependencias..."
apt install -y ca-certificates curl gnupg python3-pip python3-venv

# 3. Adicionar a chave GPG oficial do Docker
echo "[+] Configurando repositorio oficial do Docker..."
install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
chmod a+r /etc/apt/keyrings/docker.gpg

# 4. Configurar o repositorio
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  tee /etc/apt/sources.list.d/docker.list > /dev/null

# 5. Instalar Docker Engine, CLI e Compose Plugin
echo "[+] Instalando Docker Engine..."
apt update
apt install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 6. Habilitar o Docker para rodar no boot
systemctl enable --now docker

# 7. Adicionar o usuario ao grupo docker (se o script for executado com sudo e $SUDO_USER estiver disponivel)
if [ -n "$SUDO_USER" ]; then
    echo "[+] Adicionando usuario $SUDO_USER ao grupo docker..."
    usermod -aG docker $SUDO_USER
fi

# 8. Subir a infraestrutura do Billing API via Docker Compose
echo "[+] Subindo a infraestrutura do Billing API com Docker Compose..."
docker compose up --build -d --scale billing_api=3

# 9. Configurar o script de Autoscaling para rodar como servico systemd
echo "[+] Configurando o serviço de monitoramento do Autoscale..."
if [ -f "setup_autoscale_service.sh" ]; then
    bash setup_autoscale_service.sh
else
    echo "[-] setup_autoscale_service.sh nao encontrado no diretorio atual."
fi

echo "=========================================================="
echo " Instalacao concluida com sucesso!"
if [ -n "$SUDO_USER" ]; then
    echo " Lembre-se de logar novamente para aplicar as permissoes"
    echo " do grupo docker ao usuario $SUDO_USER."
fi
echo " O Load Balancer (Nginx) deve estar ouvindo na porta 9000."
echo "=========================================================="
