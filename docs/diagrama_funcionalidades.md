# Diagrama de Funcionalidades e Rotas

Este documento descreve o fluxo lógico e as rotas dos componentes principais do projeto: `web_panel`, `intranet` e `billing_api`.

## Visão Geral do Sistema

O projeto é composto por três blocos principais que interagem entre si para simular um ambiente acadêmico monitorado por sistemas de segurança (pfSense, Suricata, Zabbix).

```mermaid
graph TD
    subgraph Web_Panel ["Web Panel (C2 & Simulator)"]
        WP_Index["/ (Dashboard)"] --> WP_Stats["Estatísticas Docker"]
        WP_Index --> WP_Attacks["/attacks (Central de Ataques)"]
        WP_Index --> WP_Stress["/stress (Estresse L7)"]
        WP_Index --> WP_Sim["/simulation (Simular Alunos/Profs)"]
        WP_Index --> WP_SNMP["/devices (Simuladores SNMP)"]
        
        WP_Attacks --> ATK_SQLI["SQLi / XSS / Path Traversal"]
        WP_Sim --> SIM_LOGIN["Logins Randômicos [SIM]"]
        WP_Sim --> SIM_ACT["Ações: Notas e Chamadas"]
    end

    subgraph Intranet_Web ["Intranet (Target App)"]
        INT_Setup["/setup (Config DB)"] --> INT_Login["/login (Auth)"]
        INT_Login -- "Role: Admin" --> INT_Admin["/admin_dashboard"]
        INT_Login -- "Role: Prof" --> INT_Prof["/prof_dashboard"]
        INT_Login -- "Role: Aluno" --> INT_Stud["/student_dashboard"]

        INT_Admin -- "Impersonate" --> INT_Prof
        INT_Admin -- "Impersonate" --> INT_Stud
        
        INT_Prof --> INT_Class["/prof_dashboard/class/{id}"]
        INT_Class --> INT_Grade["Lançar Notas"]
        INT_Class --> INT_Attend["Realizar Chamada"]

        INT_Admin --> INT_Users["Gerenciar Alunos/Profs"]
    end

    subgraph SOA_Billing ["Billing API (Microservice)"]
        BILL_Invoices["/invoices/{student_id}"] -- "Gatilho DLP" --> BILL_Data["Vazamento de Cartão (BOLA)"]
        BILL_Pay["/pay"] -- "Parameter Tampering" --> BILL_Fraud["Fraude de Valor"]
    end

    %% Conexões de Interação
    WP_Attacks -.->|Injeção de Payloads| INT_Login
    WP_Sim -.->|Tráfego Simulado| INT_Login
    INT_Stud -.->|Consome| BILL_Invoices
    
    %% Estilização
    style Web_Panel fill:#f9f,stroke:#333,stroke-width:2px
    style Intranet_Web fill:#bbf,stroke:#333,stroke-width:2px
    style SOA_Billing fill:#bfb,stroke:#333,stroke-width:2px
```

## Detalhamento de Rotas

### 1. Web Panel (`/web_panel`)
Responsável por orquestrar os ataques e as simulações.

| Rota | Função | Descrição |
| :--- | :--- | :--- |
| `/` | `read_root` | Dashboard principal com status dos containers. |
| `/attacks` | `attacks_page` | Interface para disparar ataques (SQLi, XSS). |
| `/simulation` | `simulation_page` | Controle de simuladores de usuários legítimos. |
| `/devices` | `devices_page` | Gerenciamento de instâncias SNMP. |
| `/api/docker/stats` | `get_docker_stats` | API para métricas de performance dos containers. |

### 2. Intranet (`/intranet/web`)
Aplicação principal que sofre os ataques e gera logs de acesso.

| Rota | Função | Descrição |
| :--- | :--- | :--- |
| `/setup` | `setup_get/post` | Configuração inicial da conexão com MySQL. |
| `/login` | `login` | Ponto central de autenticação (Gatilho de Brute Force). |
| `/admin_dashboard`| `admin_dashboard` | Gestão total de alunos, professores e turmas. |
| `/security/metrics`| `security_metrics`| Endpoint de métricas de falha (usado pelo Zabbix). |
| `/admin/impersonate`| `impersonate_user`| Permite admin assumir outra conta (Vulnerabilidade lógica). |

### 3. Billing API (`/intranet/billing_api`)
Microserviço isolado para simular vulnerabilidades modernas (SOA).

| Rota | Função | Descrição |
| :--- | :--- | :--- |
| `/invoices/{id}` | `get_invoices` | Vulnerável a BOLA (Broken Object Level Authorization). |
| `/pay` | `pay_invoice` | Vulnerável a Parameter Tampering (Fraude no valor). |
| `/status` | `status` | Healthcheck do serviço. |
