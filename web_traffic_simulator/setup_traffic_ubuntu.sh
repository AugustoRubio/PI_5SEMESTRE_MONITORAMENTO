#!/bin/bash
# Script para preparar a máquina Ubuntu que servirá de "Usuário" para gerar tráfego

echo "Atualizando pacotes do sistema..."
sudo apt update

echo "Instalando dependências (curl, openssh-server)..."
sudo apt install -y curl openssh-server

echo "Garantindo que o serviço SSH está rodando para receber conexões do Docker..."
sudo systemctl enable ssh
sudo systemctl start ssh

echo "Configuração concluída! Esta máquina já pode receber os comandos do bot."