# Plano de Implantação - Simulação de Redes e Segurança (PI 5º Semestre)

Este documento descreve a arquitetura e os passos para integrar o simulador SNMP e os ataques controlados na infraestrutura existente (GNS3 + pfSense + Mikrotik + Zabbix via VPN/GRE/OSPF).

## 1. Visão Geral da Arquitetura Atual

*   **Servidor Físico (Debian 12):** Hospeda o GNS3 Server. Possui adaptadores físicos e virtuais (NAT).
*   **GNS3 (Interno):**
    *   2x VMs pfSense (Firewall de Borda).
    *   Redes internas simuladas atrás dos pfSenses.
*   **Roteamento e VPN:**
    *   Mikrotik físico atuando como roteador principal.
    *   Túnel GRE + OSPF para roteamento dinâmico.
    *   VPN Wireguard conectando sites externos.
*   **Monitoramento (Externo):**
    *   Máquina externa rodando Zabbix Server (conectada via Wireguard/GRE).
*   **VPS (Off-site):**
    *   Conectada via Wireguard e GRE/OSPF, recebendo rotas dos pfSenses.

## 2. Onde posicionar os novos componentes?

Para que o cenário seja realista e o Zabbix consiga monitorar tudo corretamente através dos túneis e firewalls, a distribuição ideal é a seguinte:

### A. Simulador SNMP (snmpsim) -> Dentro do GNS3
*   **Onde:** Em uma nova VM Linux (ex: Alpine ou Debian leve) conectada a uma das redes internas atrás do pfSense no GNS3.
*   **Por quê:** O Zabbix (externo) terá que passar pelo Mikrotik, pelo túnel GRE, pelo pfSense (regras de firewall) para chegar no simulador SNMP. Isso testa perfeitamente o roteamento OSPF e as regras do pfSense.
*   **O que fará:** Simulará o Nobreak e o Sensor de Temperatura.

### B. Máquina Alvo (Vítima) + Suricata (IDS/IPS) -> Dentro do GNS3
*   **Onde:** Na mesma rede interna do simulador SNMP ou em uma DMZ separada atrás do pfSense.
*   **Por quê:** O Suricata precisa inspecionar o tráfego que entra na rede protegida pelo pfSense.
*   **O que fará:** Rodará um serviço web (Nginx) e o Suricata analisando os pacotes em busca de assinaturas de DDoS e Brute Force. O Zabbix Agent rodará aqui para enviar os alertas do Suricata para o Zabbix Server.

### C. Máquina Atacante Externa (Red Team WAN) -> Na VPS (Off-site)
*   **Onde:** Na sua VPS que já está conectada via Wireguard/GRE.
*   **Por quê:** Isso simula um ataque real vindo da Internet (WAN). O tráfego de ataque (DDoS/Brute Force) sairá da VPS, passará pelo túnel, baterá no Mikrotik, entrará no GNS3, passará pelo pfSense (que pode tentar bloquear) e chegará na VM Alvo. É o cenário perfeito para testar o consumo de link (SPI) e a detecção (DPI) na borda.

### D. Máquina Atacante Interna (Red Team LAN) -> Dentro do GNS3
*   **Onde:** Em uma VM Linux (ex: Kali ou Ubuntu) conectada à mesma rede interna (LAN/DMZ) da Máquina Alvo.
*   **Por quê:** Simula um cenário de "Lateral Movement" (Movimentação Lateral), onde um atacante já comprometeu uma máquina interna ou um funcionário mal-intencionado está agindo. O tráfego *não* passa pelo firewall de borda (pfSense), testando exclusivamente a eficácia do IDS (Suricata) interno e a segmentação da rede.
*   **O que fará:** Executará ataques de DDoS (UDP Flood), MAC Spoofing e Man-in-the-Middle (ARP Poisoning) contra a Máquina Alvo.

### E. Painel Web de Controle (FastAPI) -> Servidor Físico (Debian 12)
*   **Onde:** Rodando nativamente (ou em Docker) no próprio servidor físico Debian 12 que hospeda o GNS3.
*   **Por quê:** Centraliza a administração. Como o servidor físico já possui as interfaces virtuais (TAP/TUN) conectadas ao GNS3, o Painel Web terá comunicação direta, rápida e estável via SSH com todas as VMs internas e com a VPS externa (via túnel).
*   **Como funciona:** O Painel Web se conectará via SSH (usando a biblioteca `paramiko`) nas máquinas atacantes (VPS e VM Interna) para disparar os scripts de ataque, e na VM do Simulador SNMP para alterar os valores dos sensores.

---

## 3. Passos de Implementação

### Passo 1: Configurar o Simulador SNMP no GNS3
1.  Adicione uma VM Linux (Debian/Ubuntu) no GNS3, atrás do pfSense.
2.  Instale o Docker e o Docker Compose nessa VM.
3.  Crie um `docker-compose.yml` para subir o `snmpsim`.
4.  Crie os arquivos `.snmprec` (arquivos de texto com as OIDs falsas de temperatura e bateria).
5.  Configure o pfSense para permitir tráfego UDP na porta 161 (SNMP) vindo do IP do Zabbix Server.
6.  No Zabbix, adicione o IP dessa VM como um Host e crie os itens/gráficos para ler as OIDs.

### Passo 2: Configurar a Máquina Alvo e o Suricata no GNS3
1.  Adicione outra VM Linux no GNS3 (ou use a mesma do SNMP, mas separado é melhor).
2.  Instale o Nginx (para ser o alvo do DDoS/Brute Force) e o Suricata.
3.  Configure o Suricata para escutar a interface de rede da VM.
4.  Instale o Zabbix Agent nessa VM.
5.  Configure o Zabbix Agent para ler o arquivo `/var/log/suricata/fast.log` (onde o Suricata grava os alertas de ataque) e enviar para o Zabbix Server.

### Passo 3: Preparar as Máquinas Atacantes (Externa e Interna)
1.  **Na VPS (Externa):**
    *   Acesse via SSH.
    *   Instale as ferramentas: `sudo apt install hping3 hydra`.
    *   Crie scripts bash (`start_ddos_ext.sh`, `stop_ddos_ext.sh`) apontando para o IP Público/NAT do pfSense.
2.  **Na VM Atacante (Interna no GNS3):**
    *   Adicione uma VM Linux na mesma LAN da Máquina Alvo.
    *   Instale as ferramentas: `sudo apt install hping3 ettercap-text-only dsniff`.
    *   Crie scripts bash (`start_mitm_int.sh`, `start_ddos_int.sh`) apontando para o IP local da Máquina Alvo.

### Passo 4: Integrar o Painel Web (FastAPI) no Servidor Físico
1.  Mova o código do Painel Web para o servidor Debian 12.
2.  Instale a biblioteca `paramiko` (`pip install paramiko`).
3.  Configure chaves SSH (sem senha) do usuário que roda o Painel Web para o usuário `root` (ou com sudo) da VPS e das VMs do GNS3.
4.  Atualize as rotas (`/api/snmp/...` e `/api/attacks/...`) para executar os comandos via SSH:
    *   **Ataque Externo:** SSH na VPS -> Executa `./start_ddos_ext.sh`.
    *   **Ataque Interno:** SSH na VM Interna -> Executa `./start_mitm_int.sh`.
    *   **Sensores:** SSH na VM do Simulador -> Usa `sed` para alterar o `.snmprec`.

### Passo 5: Testes de Roteamento, Firewall e IDS
1.  Garanta que a VPS consegue pingar o IP externo do pfSense (validando OSPF/GRE).
2.  Garanta que o Zabbix Server consegue fazer requisições SNMP (`snmpwalk`) para a VM do Simulador no GNS3.
3.  Inicie um ataque externo pelo Painel e verifique se o pfSense bloqueia/registra.
4.  Inicie um ataque interno pelo Painel e verifique se o Suricata (na Máquina Alvo) detecta e se o Zabbix gera o alerta.
