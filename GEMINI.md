# Projeto Monitoramento PI 5º Semestre

## Instruções de IA (Gemini CLI)

- **Comunicação:** O usuário prefere que eu me comunique em português.
- **Commits:** Eu DEVO realizar o commit e o push automático de todas as alterações feitas ao final de cada interação/prompt, sem a necessidade de perguntar ou pedir confirmação ao usuário, a menos que me seja instruído o contrário para um caso específico.
- **Estilo de Commit:** Utilizar o padrão de Conventional Commits (ex: `feat:`, `fix:`, `perf:`, `refactor:`).

## Contexto do Projeto

- **Objetivo Principal:** Simulação de ataques e monitoramento avançado com foco em SPI (Stateful Packet Inspection) e DPI (Deep Packet Inspection), integrando pfSense (com Suricata para DPI), Zabbix (Monitoramento via LLD), Mikrotik e GNS3 (Topologia de Rede).
- **Estratégia de Estresse/Carga:** O projeto utiliza concorrência assíncrona (`aiohttp`, `aiomysql`) e processamento em lotes (DB batching) para gerar volume de requisições suficiente para estressar arquiteturas multi-core (ex: VMs com 4 Cores e 4GB RAM).
- **Gatilhos DPI (Suricata):** Para forçar o Suricata a agir, os simuladores propositalmente inserem payloads maliciosos (SQLi, XSS, Path Traversal) dentro dos corpos de requisições HTTP (POST) ou acessam URLs vulneráveis reais (ex: `testphp.vulnweb.com`). 
- **Simulação de DB:** Para logins válidos, o simulador cria usuários fictícios no banco marcados com o prefixo `[SIM]` e a senha descriptografada `sim`.

## Estrutura Principal de Diretórios

- `/web_panel/`: Interface principal de controle (FastAPI backend + Jinja2 frontend). A lógica de comandos está em `app/routers/` e o visual em `app/templates/`.
- `/botnet_agent/`: Serviço Dockerizado que atua como uma botnet. Contém os scripts (`src/bot.py`) que simulam alunos navegando, professores lançando notas, e ataques DDoS volumétricos.
- `/bruteforce_simulator/`: Script focado em tentar quebrar credenciais via HTTP POST, injetando payloads no campo username para disparar alertas no pfSense.
- `/web_traffic_simulator/`: Agente de navegação focado em requisitar URLs externas com assinaturas maliciosas conhecidas pela indústria (Emerging Threats, Acunetix, EICAR).
- `/zabbix_templates/`: Templates do Zabbix exportados em YAML. Contém configurações LLD para ler dinamicamente os alertas `eve.json` vindos do pfSense.
- `/snmp_simulator/`: Simulador Docker que emula dispositivos de hardware (Nobreak APC, Sensores) para o Zabbix monitorar.
- `/intranet/`: Scripts Bash e configurações (Nginx) para montar as VMs Alvo rapidamente (Debian, Ubuntu, etc).
