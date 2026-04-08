#!/bin/bash
# Script para configurar o Autoscaling Monitor como um serviço em background no Ubuntu

echo "[*] Criando servico systemd para o Autoscale Monitor..."

SERVICE_FILE="/etc/systemd/system/billing_autoscale.service"
WORK_DIR=$(pwd)

sudo tee $SERVICE_FILE > /dev/null <<EOF
[Unit]
Description=Billing API Autoscale Monitor
After=network.target docker.service
Requires=docker.service

[Service]
Type=simple
User=root
WorkingDirectory=$WORK_DIR
ExecStart=/usr/bin/python3 $WORK_DIR/autoscale_monitor.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable billing_autoscale.service
sudo systemctl start billing_autoscale.service

echo "[+] Servico criado e iniciado em background com sucesso!"
echo "[i] Para ver os logs do autoscaling, use: sudo journalctl -fu billing_autoscale"