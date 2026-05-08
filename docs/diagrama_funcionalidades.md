# Diagrama de Funcionalidades e Rotas

Este documento detalha a arquitetura lógica, os fluxos de dados e os pontos de vulnerabilidade dos sistemas que compõem o ecossistema de monitoramento.

## Mapa de Fluxo e Interações

```mermaid
flowchart TD
    %% Definições de Estilo
    classDef attackerNode fill:#ffcdd2,stroke:#b71c1c,stroke-width:2px;
    classDef targetNode fill:#bbdefb,stroke:#0d47a1,stroke-width:2px;
    classDef microserviceNode fill:#c8e6c9,stroke:#1b5e20,stroke-width:2px;
    classDef vulnerability fill:#fff9c4,stroke:#f57f17,stroke-width:2px,stroke-dasharray: 5 5;

    subgraph Web_Panel ["🚨 1. WEB PANEL (Comando & Controle)"]
        direction TB
        WP_Stats["📊 Dashboard (Stats Docker)"]
        WP_Attacks["⚔️ Central de Ataques (SQLi/XSS)"]
        WP_Stress["🔥 Estresse L7 (DDoS Sim)"]
        WP_Sim["👥 Simulador de Uso"]
        WP_SNMP["🔌 SNMP Manager"]
        
        WP_Attacks --- ATK_SQLI((Injeção SQL)):::vulnerability
        WP_Attacks --- ATK_XSS((XSS / Scripts)):::vulnerability
        WP_Sim --- SIM_Botnet([Controle de Alunos/Profs Fake])
    end

    subgraph Intranet_App ["🎯 2. INTRANET (Alvo Principal)"]
        direction TB
        INT_Setup["🛠️ Setup DB"]
        INT_Login["🔐 Portal de Login"]
        
        INT_Login ==> |"Sessão"| INT_Router{Perfil}
        
        subgraph Dashboards ["Painéis Internos"]
            INT_Admin["👑 Dashboard Admin"]
            INT_Prof["👨‍🏫 Dashboard Professor"]
            INT_Stud["🎓 Dashboard Aluno"]
        end

        INT_Admin --- ADM_Impersonate((Vulnerabilidade: IDOR)):::vulnerability
        INT_Prof --- PROF_Actions["Notas e Chamada"]
        INT_Stud --- STUD_Billing["Área Financeira"]
        INT_Sec["🛡️ Metrics API (Zabbix)"]
    end

    subgraph Billing_Microservice ["💰 3. BILLING API (Microserviço)"]
        direction TB
        BILL_Invoices["📄 /invoices/{id}"]
        BILL_Pay["💳 /pay"]
        
        BILL_Invoices --- VULN_BOLA((BOLA / DLP)):::vulnerability
        BILL_Pay --- VULN_Tamper((Parameter Tampering)):::vulnerability
    end

    %% Conexões
    ATK_SQLI ===> |"Ataques"| INT_Login
    ATK_XSS ===> |"Scripts"| INT_Login
    SIM_Botnet ===> |"Navegação"| INT_Login
    STUD_Billing ===> |"JSON Request"| BILL_Invoices
    INT_Login -.-> |"Log"| INT_Sec

    subgraph Legenda
        direction LR
        L1[Atacante]:::attackerNode
        L2[Alvo]:::targetNode
        L3[Microserviço]:::microserviceNode
        L4((Vuln)):::vulnerability
    end

    %% Classes
    class WP_Stats,WP_Attacks,WP_Stress,WP_Sim,WP_SNMP attackerNode;
    class INT_Setup,INT_Login,INT_Admin,INT_Prof,INT_Stud,INT_Sec,PROF_Actions,STUD_Billing,INT_Router targetNode;
    class BILL_Invoices,BILL_Pay microserviceNode;
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

### 2. Intranet (`/intranet/web`)
Aplicação acadêmica completa, servindo como o alvo principal do monitoramento.

| Rota | Função Técnica | Detalhes |
| :--- | :--- | :--- |
| `/setup` | `setup_post` | Configuração dinâmica da conexão com o MySQL e criação de tabelas. |
| `/login` | `login` | Autenticação central. Falhas aqui são enviadas ao Zabbix. |
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
| `/status` | `status` | Retorna o status da réplica e saúde do microserviço. |

---
*Este diagrama é atualizado automaticamente conforme novas rotas são integradas ao sistema.*
