#!/bin/bash
# Script para subir o microsserviço de pagamentos (Billing API) via Docker Compose

echo "Iniciando configuração do Microsserviço de Pagamentos (Billing API)..."

cd billing_api || exit 1

# Instalação do Docker (se não estiver instalado)
if ! command -v docker &> /dev/null
then
    echo "Docker não encontrado. Instalando Docker..."
    sudo apt update
    sudo apt install -y docker.io docker-compose-v2
    sudo systemctl enable --now docker
    sudo usermod -aG docker $USER
fi

echo "Construindo as imagens e subindo os containers (3 Réplicas + 1 Load Balancer)..."
sudo docker compose up --build -d --scale billing_api=3

echo "------------------------------------------------------------------"
echo "Microsserviço de Pagamentos operante!"
echo "O Load Balancer (Nginx interno) está ouvindo na porta 9000 do host."
echo "Certifique-se de que o Nginx principal (intranet) esteja configurado com o proxy_pass para /api/billing/."
echo "------------------------------------------------------------------"
