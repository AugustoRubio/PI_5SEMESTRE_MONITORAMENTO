#!/bin/bash
# Script para configurar os parametros customizados no Zabbix Agent da Intranet

echo "[*] Configurando UserParameters do Zabbix Agent para o Monitoramento SOA..."
CONF_FILE="/etc/zabbix/zabbix_agentd.d/billing_api.conf"

# Cria arquivo de atalho (UserParameter) para o zabbix extrair as réplicas e a CPU média dos Dockers
sudo tee $CONF_FILE > /dev/null <<'EOF'
UserParameter=soa.billing.replicas,docker ps --format "{{.Names}}" | grep "billing_api" | grep -v "lb" | wc -l
UserParameter=soa.billing.cpu.avg,docker stats --no-stream --format "{{.Name}}|{{.CPUPerc}}" | grep "billing_api" | grep -v "lb" | sed 's/%//g' | awk -F'|' '{sum+=$2; count++} END {if (count > 0) print sum/count; else print 0}'
EOF

# Habilita execucao remota de comandos simples e inofensivos (necessário para ver o status do systemctl do autoscaler)
sudo sed -i 's/^# EnableRemoteCommands=0/EnableRemoteCommands=1/' /etc/zabbix/zabbix_agentd.conf
sudo sed -i 's/^EnableRemoteCommands=0/EnableRemoteCommands=1/' /etc/zabbix/zabbix_agentd.conf

# Adiciona o usuario zabbix ao grupo docker para que ele possa executar os comandos sem usar SUDO
sudo usermod -aG docker zabbix

# Reinicia o agent
sudo systemctl restart zabbix-agent

echo "[+] Concluido! O Zabbix Agent local agora e compativel com o Template SOA."
echo "[i] Importe o arquivo YAML no painel do Zabbix e associe-o a este host."