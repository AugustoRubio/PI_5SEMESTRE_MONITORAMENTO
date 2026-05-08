# Diagrama de Funcionalidades e Rotas

Este documento detalha a arquitetura lógica, os fluxos de dados, os pontos de vulnerabilidade e a capacidade de carga da Botnet que compõem o ecossistema de monitoramento.

## Mapa de Fluxo, Interações e Capacidade de Carga

```mermaid
flowchart TD
    %% ==========================================
    %% Definições de Estilo (Alta Fidelidade)
    %% ==========================================
    classDef attackerNode fill:mistyrose,stroke:darkred,stroke-width:3px,color:black,font-weight:bold;
    classDef targetNode fill:aliceblue,stroke:darkblue,stroke-width:3px,color:black,font-weight:bold;
    classDef microserviceNode fill:honeydew,stroke:darkgreen,stroke-width:3px,color:black,font-weight:bold;
    classDef vulnerability fill:lightyellow,stroke:darkorange,stroke-width:3px,color:black,stroke-dasharray: 5 5;

    %% Estilo global para as setas
    linkStyle default stroke:dimgray,stroke-width:3px,color:black;

    %% ==========================================
    %% Subgrafo: Painel do Atacante (C2) e Botnet
    %% ==========================================
    subgraph Web_Panel ["🚨 1. WEB PANEL & BOTNET (C2)"]
        direction TB
        WP_Stats["📊 Dashboard\n(Monitoramento Docker Stats)"]
        WP_Attacks["⚔️ Central de Ataques\n(SQLi, XSS, Path Traversal)"]
        WP_Admin["⚙️ Configurações\n(Ambiente & Usuários)"]
        
        subgraph Botnet_Agent ["🤖 BOTNET AGENT (Simuladores de Carga)"]
            direction LR
            BOT_DDOS["🔥 DDoS Bot\n(50 Workers)"]:::attackerNode
            BOT_STUD["🎓 Aluno Bot\n(10 Workers)"]:::attackerNode
            BOT_PROF["👨‍🏫 Prof Bot\n(10 Workers)"]:::attackerNode
            BOT_SOA["💰 SOA Bot\n(30 Workers)"]:::attackerNode
        end

        subgraph SNMP_Simulator ["🔌 SNMP SIMULATOR (IoT/Hardware)"]
            direction LR
            SNMP_APC["🔋 Nobreak APC"]:::attackerNode
            SNMP_TEMP["🌡️ Sensores Temp"]:::attackerNode
        end

        %% Conexões de Controle Interno
        WP_Admin --> |"Define Alvos"| Botnet_Agent
        WP_Admin --> |"Config MIBs"| SNMP_Simulator
        WP_Stats -.-> |"Lê Métricas"| Botnet_Agent
        WP_Attacks --> |"Gera Payload"| BOT_DDOS
    end

    %% ==========================================
    %% Subgrafo: Intranet Alvo (Aplicação Monitorada)
    %% ==========================================
    subgraph Intranet_App ["🎯 2. INTRANET (Alvo Principal)"]
        direction TB
        INT_Setup["🛠️ Setup\n(Configuração de DB)"]
        INT_Login["🔐 Portal de Login\n(Entry Point)"]
        
        INT_Login ==> |"Sessão Ativa"| INT_Router{Seletor de Perfil}
        
        subgraph Dashboards ["Painéis Internos"]
            INT_Admin["👑 Dashboard Admin"]
            INT_Prof["👨‍🏫 Dashboard Professor"]
            INT_Stud["🎓 Dashboard Aluno"]
        end

        %% Ações e Vulnerabilidades
        INT_Admin --- ADM_Impersonate((IDOR / Impersonate)):::vulnerability
        INT_Prof --- PROF_Actions["Lançar Notas\nRegistrar Presença"]
        INT_Stud --- STUD_Billing["Acessar Área Financeira"]
        
        %% Métricas de Segurança
        INT_Sec["🛡️ Metrics API\n(Fail Logs JSON)"]
    end

    %% ==========================================
    %% Subgrafo: Microserviço de Faturamento
    %% ==========================================
    subgraph Billing_Microservice ["💰 3. BILLING API (Microserviço SOA)"]
        direction TB
        BILL_Invoices["📄 Listar Faturas\n(/invoices/{id})"]
        BILL_Pay["💳 Processar Pagamento\n(/pay)"]
        
        BILL_Invoices --- VULN_BOLA((Vulnerabilidade BOLA)):::vulnerability
        BILL_Pay --- VULN_Tamper((Parameter Tampering)):::vulnerability
    end

    %% ==========================================
    %% Subgrafo: Camada de Monitoramento (Externo)
    %% ==========================================
    subgraph Monitoring ["📊 MONITORAMENTO (Zabbix/Syslog)"]
        ZABBIX["🖥️ Zabbix Server\n(LLD & Trappers)"]
    end

    %% ==========================================
    %% Conexões de Alta Visibilidade (Fluxo Completo)
    %% ==========================================
    
    %% Atacante -> Alvo
    BOT_DDOS ===> |"DDoS / Exploit Flood"| INT_Login
    BOT_STUD ===> |"Navegação Humana"| INT_Login
    BOT_PROF ===> |"Carga de Banco"| INT_Login
    BOT_SOA ===> |"Stress Financeiro"| BILL_Invoices
    
    %% Alvo -> Microserviço
    STUD_Billing ===> |"Consumo Interno"| BILL_Invoices
    
    %% Fluxo de Monitoramento (Onde os dados são coletados)
    INT_Sec -.-> |"Pull de Métricas"| ZABBIX
    SNMP_Simulator -.-> |"SNMP Polling"| ZABBIX
    INT_Login -.-> |"Logs de Segurança"| ZABBIX

    %% Estilização de Subgrafos
    style Web_Panel fill:white,stroke:darkred,stroke-width:2px,color:black
    style Intranet_App fill:white,stroke:darkblue,stroke-width:2px,color:black
    style Billing_Microservice fill:white,stroke:darkgreen,stroke-width:2px,color:black
    style Dashboards fill:aliceblue,stroke:dodgerblue,stroke-dasharray: 5 5,color:black
    style Monitoring fill:ivory,stroke:goldenrod,stroke-width:2px,color:black

    %% Aplicação de Classes
    class WP_Stats,WP_Attacks,WP_Admin attackerNode;
    class INT_Setup,INT_Login,INT_Admin,INT_Prof,INT_Stud,INT_Sec,PROF_Actions,STUD_Billing,INT_Router targetNode;
    class BILL_Invoices,BILL_Pay microserviceNode;
    class ZABBIX microserviceNode;
```

## Detalhamento das Rotas e Funcionalidades

### 1. Web Panel (`/web_panel`)
Interface de controle utilizada para orquestrar as simulações e ataques contra a infraestrutura.

| Rota | Função Técnica | Detalhes |
| :--- | :--- | :--- |
| `/` | `read_root` | Dashboard central com métricas de consumo de CPU/Memória dos simuladores. |
| `/attacks` | `attacks_page` | Disparo de injeções (SQLi, XSS, Path Traversal) via POST para a Intranet. |
| `/simulation` | `simulation_page` | Ativação da Botnet que emula comportamento de Alunos e Professores. |
| `/stress` | `stress_page` | Geração de carga volumétrica para testar as regras de Firewall/IPS. |
| `/devices` | `devices_page` | Controle de simuladores SNMP (Nobreaks, Sensores de Temperatura). |
| `/admin` | `admin_page` | Gestão de usuários do próprio Painel de Controle e Alvos de Rede. |

### 2. Intranet (`/intranet/web`)
Aplicação acadêmica completa, servindo como o alvo principal do monitoramento.

| Rota | Função Técnica | Detalhes |
| :--- | :--- | :--- |
| `/setup` | `setup_post` | Configuração dinâmica da conexão com o MySQL e criação de tabelas. |
| `/login` | `login` | Autenticação central. Falhas aqui são coletadas pelo Zabbix. |
| `/admin_dashboard`| `admin_dashboard` | Painel de gestão. Inclui a função `/admin/impersonate/{role}/{id}`. |
| `/prof_dashboard` | `prof_dashboard` | Visualização de turmas e chamada (`/attendance`) e notas (`/grade`). |
| `/student_dashboard`| `student_dashboard`| Consulta de faturas (consome a API de Billing). |
| `/security/metrics`| `security_metrics`| API que expõe tentativas de login malsucedidas em formato JSON. |

### 3. Billing API (`/intranet/billing_api`)
Microserviço que simula uma arquitetura SOA com vulnerabilidades de design.

| Rota | Função Técnica | Detalhes |
| :--- | :--- | :--- |
| `/invoices/{id}` | `get_invoices` | Retorna faturas. **Vulnerabilidade BOLA**: Permite ver faturas de outros IDs. |
| `/pay` | `pay_invoice` | Processa pagamentos. **Parameter Tampering**: Confia no valor enviado pelo cliente. |

### 4. Camada de Monitoramento (Zabbix)
O Zabbix atua como o receptor central de dados de todos os componentes:
- **LPO (Low-Level Discovery)**: Mapeia os containers via Metrics API.
- **SNMP Polling**: Coleta dados dos simuladores de hardware (Nobreaks/Sensores).
- **Security Trapping**: Monitora o arquivo `eve.json` (via Suricata) e a `Metrics API` da Intranet.

---
*Este diagrama é atualizado automaticamente conforme novas rotas ou capacidades de carga são integradas ao sistema.*
