# Projeto Monitoramento PI 5º Semestre

## Sobre o Projeto

Este projeto é um simulador de ambiente de redes focado em segurança, desenvolvido como Projeto Integrador do 5º Semestre. O objetivo principal é proporcionar um ambiente completo de simulação de ataques e monitoramento avançado com foco em **SPI (Stateful Packet Inspection)** e **DPI (Deep Packet Inspection)**.

A arquitetura do projeto integra diversas tecnologias de rede e segurança, incluindo:
- **pfSense** (com Suricata para DPI)
- **Zabbix** (para monitoramento dinâmico via LLD)
- **Mikrotik** e **GNS3** (para topologia de rede)

### Como Funciona

O projeto não se resume a apenas uma rede isolada; ele possui um ecossistema ativo de geradores de tráfego, simulando tanto comportamento benigno quanto malicioso.

- **Estratégia de Estresse/Carga:** Utilizamos scripts assíncronos (`aiohttp`, `aiomysql`) e processamento em lotes para gerar um volume de requisições capaz de estressar arquiteturas multi-core (por exemplo, VMs com 4 Cores e 4GB RAM).
- **Gatilhos DPI (Suricata):** Os simuladores inserem propositalmente payloads maliciosos, como SQL Injection, XSS e Path Traversal, nos corpos de requisições HTTP (POST) ou acessam URLs conhecidas como vulneráveis para engatilhar as assinaturas do Suricata e disparar alertas que são coletados pelo Zabbix.

## Principais Componentes e Funcionalidades

- 🎛️ **Web Panel (`/web_panel/`):** Interface principal de controle desenvolvida em FastAPI (backend) e Jinja2 (frontend). Permite gerenciar os simuladores de ataques e o tráfego da rede.
- 🧟 **Botnet Agent (`/botnet_agent/`):** Serviço dockerizado que atua como uma botnet simulando tráfego de usuários comuns (alunos navegando, professores lançando notas) e gerando ataques volumétricos como DDoS.
- 🔓 **Bruteforce Simulator (`/bruteforce_simulator/`):** Script para testar a resiliência contra quebras de credenciais via HTTP POST, injetando payloads no campo username para disparar alertas no firewall.
- 🕷️ **Web Traffic Simulator (`/web_traffic_simulator/`):** Agente focado em buscar URLs externas com assinaturas conhecidas (Emerging Threats, Acunetix, EICAR) para validar a eficácia do IPS.
- 📡 **Monitoramento SNMP (`/snmp_simulator/`):** Simulador Docker que emula dispositivos de hardware, como Nobreaks APC e sensores, para validação das métricas pelo Zabbix.
- 📊 **Templates Zabbix (`/zabbix_templates/`):** Templates LLD para leitura dinâmica dos alertas gerados pelo pfSense/Suricata e dos sensores emulados.
- 🛠️ **VMs Alvo (`/intranet/`):** Scripts de automação Bash e configurações Nginx para o rápido provisionamento de ambientes de teste (Debian, Ubuntu, etc).

## Integrantes

- Augusto Rubio
- Erik Freitas
- Hugo Santos
- Walber Cavalcante
