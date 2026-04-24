#!/bin/bash
# Script para configurar os parametros customizados no Zabbix Agent da Intranet

wget https://repo.zabbix.com/zabbix/7.4/release/debian/pool/main/z/zabbix-release/zabbix-release_latest_7.4+debian13_all.deb
dpkg -i zabbix-release_latest_7.4+debian13_all.deb
apt update 

apt install zabbix-agent2
apt install zabbix-agent2-plugin-mongodb zabbix-agent2-plugin-mssql zabbix-agent2-plugin-postgresql 

echo "[*] Configurando UserParameters do Zabbix Agent para o Monitoramento SOA..."
CONF_FILE="/etc/zabbix/zabbix_agent2.d/billing_api.conf"

# Cria arquivo de atalho (UserParameter) para o zabbix extrair as réplicas e a CPU média dos Dockers
sudo tee $CONF_FILE > /dev/null <<'EOF'
UserParameter=soa.billing.replicas,docker ps --format "{{.Names}}" | grep "billing_api" | grep -v "lb" | wc -l
UserParameter=soa.billing.cpu.avg,docker stats --no-stream --format "{{.Name}}|{{.CPUPerc}}" | grep "billing_api" | grep -v "lb" | sed 's/%//g' | awk -F'|' '{sum+=$2; count++} END {if (count > 0) print sum/count; else print 0}'
EOF

# Habilita execucao da chave system.run (necessário para o Agent 2 ler o status do systemctl)
grep -q "^AllowKey=system.run\[\*\]" /etc/zabbix/zabbix_agent2.conf || echo "AllowKey=system.run[*]" | sudo tee -a /etc/zabbix/zabbix_agent2.conf > /dev/null

# Adiciona o usuario zabbix ao grupo docker para que ele possa executar os comandos sem usar SUDO
sudo usermod -aG docker zabbix

# Reinicia o Zabbix Agent 2
sudo systemctl restart zabbix-agent2

echo "[+] Concluido! O Zabbix Agent local agora e compativel com o Template SOA."
echo "[i] Importe o arquivo YAML no painel do Zabbix e associe-o a este host."