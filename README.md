# Projeto Monitoramento PI 5º Semestre

Este projeto é um simulador de ambiente de redes focado em segurança, desenvolvido como Projeto Integrador do 5º Semestre. O objetivo principal é proporcionar um ambiente completo de simulação de ataques e monitoramento avançado com foco em **SPI (Stateful Packet Inspection)** e **DPI (Deep Packet Inspection)**.

A arquitetura do projeto integra diversas tecnologias de rede e segurança, incluindo:
- **pfSense** (com Suricata para DPI)
- **Zabbix** (para monitoramento dinâmico via LLD)
- **Mikrotik** e **GNS3** (para topologia de rede)

---

## 🎛️ Painel de Controle (Web Panel)
**Diretório:** `/web_panel/`

A interface principal de controle desenvolvida em FastAPI (backend) e Jinja2 (frontend). Permite gerenciar de forma centralizada os simuladores de ataques, cargas de rede e monitorar o status dos testes em tempo real.

---

## 🧟 Simulação de Acesso Humano & Estresse (Botnet Agent)
**Diretório:** `/botnet_agent/`

Serviço dockerizado que orquestra uma **Botnet de Agentes** simulando tanto o tráfego de usuários comuns (alunos navegando, professores lançando notas) quanto ataques volumétricos. 

O painel web disponibiliza 5 presets rápidos (1-Click) para estressar a infraestrutura:

| Preset | Foco do Teste | Ação dos Agentes | Escala (Containers) | Duração Média |
| :--- | :--- | :--- | :--- | :--- |
| **Fluxo de Alunos** | Leitura / Tráfego Leve | Simula alunos consultando notas e dashboards (operações GET). Valida o comportamento do servidor sob navegação comum. | 15 | 5 min |
| **Rotina de Professores**| Escrita / Banco de Dados | Simula professores lançando notas e faltas. Gera carga mista com muitas operações POST, testando a integridade do banco. | 30 | 5 min |
| **Campus Ativo** | Concorrência Média | Cenário de uso real combinando navegação de alunos e ações de professores. Ideal para testar gráficos de estabilidade do Zabbix. | 50 | 5 min |
| **Período de Provas** | Stress de Backend | Evento de alta criticidade com volume massivo de requisições de escrita. Força filas de rede e testa bloqueios do IPS. | 80 | 5 min |
| **Ataque DDoS** | Inundação / Segurança | Ataque puro e agressivo. Agentes não seguem rotina humana e bombardeiam o alvo com o máximo de requisições possíveis para forçar travamentos. | 120 | 10 min |

---

## 🛠️ Outros Simuladores e Ferramentas

### 🔓 Bruteforce Simulator (`/bruteforce_simulator/`)
Script focado em tentar quebrar credenciais via HTTP POST. Além da tentativa de intrusão, injeta payloads deliberadamente no campo `username` para garantir o disparo de alertas DPI no pfSense.

### 🕷️ Web Traffic Simulator (`/web_traffic_simulator/`)
Agente de navegação que requisita URLs externas com assinaturas maliciosas conhecidas pela indústria (Emerging Threats, Acunetix, EICAR). O objetivo é forçar o Suricata a agir interceptando o tráfego de saída.

### 📡 Simulador SNMP (`/snmp_simulator/`)
Serviço Docker que emula dispositivos físicos (Nobreak APC, Sensores de Temperatura/Umidade). Gera dados OID realistas para que o Zabbix possa monitorar hardwares que não existem fisicamente na maquete.

### 💻 Infraestrutura Intranet (`/intranet/`)
Scripts Bash e configurações Nginx para montar rapidamente as VMs Alvo que sofrerão os ataques e simulações (Debian, Ubuntu, etc).

---

## 📊 Monitoramento (Zabbix Templates)
**Diretório:** `/zabbix_templates/`

Repositório contendo templates exportados em YAML, focados em LLD (Low-Level Discovery) para monitoramento dinâmico. Destaques:
- **pfSense/Suricata:** Lê dinamicamente os alertas do `eve.json` e cria gatilhos baseados em severidade.
- **SOA/Billing API:** Monitora tempo de resposta HTTP, uso de CPU e estado do autoscaler.
- **Hardwares Simulados:** Templates SNMP customizados para ler OIDs da APC e sensores ambientais.

---

## 👨‍💻 Integrantes

- Augusto Rubio
- Erik Freitas
- Hugo Santos
- Walber Cavalcante
