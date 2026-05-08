# Diagrama de Funcionalidades e Rotas

Este documento descreve o fluxo lógico e as rotas dos componentes principais do projeto: `web_panel`, `intranet` e `billing_api`.

## Visão Geral do Sistema

O projeto é composto por três blocos principais que interagem entre si para simular um ambiente acadêmico monitorado por sistemas de segurança (pfSense, Suricata, Zabbix).

```mermaid
flowchart TB
    %% ==========================================
    %% Definição de Estilos (Cores e Formatos)
    %% ==========================================
    classDef attacker fill:#ffebee,stroke:#c62828,stroke-width:2px,color:#b71c1c;
    classDef target fill:#e3f2fd,stroke:#1565c0,stroke-width:2px,color:#0d47a1;
    classDef microservice fill:#e8f5e9,stroke:#2e7d32,stroke-width:2px,color:#1b5e20;
    classDef vuln fill:#fff3e0,stroke:#e65100,stroke-width:2px,color:#e65100,stroke-dasharray: 5 5;
    classDef legendStyle fill:#f5f5f5,stroke:#9e9e9e,stroke-width:1px;

    %% ==========================================
    %% Legenda (Subgrafo visual)
    %% ==========================================
    subgraph Legenda
        L1[Ambiente Atacante / C2]:::attacker
        L2[Aplicação Alvo / Intranet]:::target
        L3[Microserviços Internos]:::microservice
        L4((Vulnerabilidade / Gatilho)):::vuln
    end
    
    %% Ocultar conexões da legenda
    L1 ~~~ L2 ~~~ L3 ~~~ L4
    style Legenda fill:#fafafa,stroke:#bdbdbd,stroke-width:1px,stroke-dasharray: 5 5

    %% ==========================================
    %% Blocos Principais
    %% ==========================================
    
    subgraph Web_Panel ["1. Web Panel (Atacante & Simulador)"]
        direction LR
        WP_Index["/ (Dashboard)"]
        
        WP_Index --> WP_Attacks["/attacks"]
        WP_Index --> WP_Sim["/simulation"]
        WP_Index --> WP_Misc["/stress & /devices"]
        
        WP_Attacks -.-> ATK_Payloads((Payloads Maliciosos)):::vuln
        WP_Sim -.-> SIM_Traffic([Tráfego Simulado])
    end

    subgraph Intranet_Web ["2. Intranet (Aplicação Alvo)"]
        direction TB
        INT_Setup["/setup"] --> INT_Login["/login (Ponto de Entrada)"]
        
        INT_Login --> |"Autenticação\n(Brute Force Target)"| RoleRouter{Perfil}
        
        RoleRouter -- "Admin" --> INT_Admin["/admin_dashboard"]
        RoleRouter -- "Professor" --> INT_Prof["/prof_dashboard"]
        RoleRouter -- "Aluno" --> INT_Stud["/student_dashboard"]

        %% Detalhes Internos
        INT_Prof --> INT_Class["/class/{id} (Notas e Chamadas)"]
        
        %% Funcionalidade sensível
        INT_Admin -.-> |"/impersonate"| Vuln_Impersonate((Bypass de Sessão)):::vuln
        Vuln_Impersonate -.-> INT_Prof
        Vuln_Impersonate -.-> INT_Stud
    end

    subgraph SOA_Billing ["3. Billing API (Microserviço)"]
        direction TB
        BILL_Invoices["/invoices/{student_id}"] -.-> Vuln_BOLA((Vulnerabilidade BOLA\nVazamento DLP)):::vuln
        BILL_Pay["/pay"] -.-> Vuln_Fraud((Parameter Tampering)):::vuln
    end

    %% ==========================================
    %% Conexões Inter-Sistemas (Desenhadas para evitar cruzamentos)
    %% ==========================================
    
    %% Conectando o Atacante ao Alvo
    ATK_Payloads ==> |"Ataques Web"| INT_Login
    SIM_Traffic ==> |"Navegação"| INT_Login
    
    %% Conectando o Alvo ao Microserviço
    INT_Stud ==> |"Consulta Faturas"| BILL_Invoices

    %% Aplicando as classes principais aos subgrafos (mermaid trick: apply to nodes)
    class Web_Panel,WP_Index,WP_Attacks,WP_Sim,WP_Misc attacker;
    class Intranet_Web,INT_Setup,INT_Login,RoleRouter,INT_Admin,INT_Prof,INT_Stud,INT_Class target;
    class SOA_Billing,BILL_Invoices,BILL_Pay microservice;
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
