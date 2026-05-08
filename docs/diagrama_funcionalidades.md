# Diagrama de Funcionalidades e Rotas

Este documento detalha a arquitetura lógica, os fluxos de dados e os pontos de vulnerabilidade dos sistemas que compõem o ecossistema de monitoramento.

## Mapa de Fluxo e Interações

```mermaid
flowchart TD
    %% ==========================================
    %% Definições de Estilo de Alto Contraste
    %% ==========================================
    classDef attackerNode fill:#ffcdd2,stroke:#b71c1c,stroke-width:3px,color:#000000,font-weight:bold;
    classDef targetNode fill:#bbdefb,stroke:#0d47a1,stroke-width:3px,color:#000000,font-weight:bold;
    classDef microserviceNode fill:#c8e6c9,stroke:#1b5e20,stroke-width:3px,color:#000000,font-weight:bold;
    classDef vulnerability fill:#fff9c4,stroke:#f57f17,stroke-width:3px,color:#000000,stroke-dasharray: 5 5;

    %% Estilo global para as setas (links) e seus textos
    linkStyle default stroke:#333333,stroke-width:3px,color:#000000;

    %% ==========================================
    %% Subgrafo: Painel do Atacante (C2)
    %% ==========================================
    subgraph Web_Panel ["🚨 1. WEB PANEL (Comando & Controle)"]
        direction TB
        WP_Stats["📊 Dashboard\n(Estatísticas Docker)"]
        WP_Attacks["⚔️ Central de Ataques\n(SQLi, XSS, Path Traversal)"]
        WP_Stress["🔥 Estresse L7\n(Botnet DDoS Sim)"]
        WP_Sim["👥 Simulador de Uso\n(User Behavior Sim)"]
        WP_SNMP["🔌 SNMP Manager\n(Controle de MIBs)"]
        WP_Admin["⚙️ Configurações\n(Ambiente & Usuários)"]

        %% Detalhes das Ações de Ataque
        WP_Attacks --- ATK_SQLI((Injeção SQL)):::vulnerability
        WP_Attacks --- ATK_XSS((XSS / Scripts)):::vulnerability
        WP_Sim --- SIM_Botnet([Controle de Alunos/Profs Fake])
    end

    %% ==========================================
    %% Subgrafo: Intranet Alvo (Aplicação Monitorada)
    %% ==========================================
    subgraph Intranet_App ["🎯 2. INTRANET (Alvo Principal)"]
        direction TB
        INT_Setup["🛠️ Setup\n(Configuração de DB)"]
        INT_Login["🔐 Portal de Login\n(Entry Point)"]
        
        %% Roteamento por Perfil
        INT_Login ==> |"Sessão Ativa"| INT_Router{Seletor de Perfil}
        
        subgraph Dashboards ["Painéis Internos"]
            INT_Admin["👑 Dashboard Admin\n(Gestão de Pessoas/Classes)"]
            INT_Prof["👨‍🏫 Dashboard Professor\n(Notas & Chamada)"]
            INT_Stud["🎓 Dashboard Aluno\n(Consulta de Status)"]
        end

        %% Ações Específicas Detalhadas
        INT_Admin --- ADM_Impersonate((Vulnerabilidade:\nIDOR / Impersonate)):::vulnerability
        INT_Prof --- PROF_Actions["Lançar Notas\nRegistrar Presença"]
        INT_Stud --- STUD_Billing["Acessar Área Financeira"]
        
        %% Métrica para Zabbix
        INT_Sec["🛡️ Security Metrics API\n(Fail Logs para Zabbix)"]
    end

    %% ==========================================
    %% Subgrafo: Microserviço de Faturamento
    %% ==========================================
    subgraph Billing_Microservice ["💰 3. BILLING API (Microserviço SOA)"]
        direction TB
        BILL_Invoices["📄 Listar Faturas\n(/invoices/{id})"]
        BILL_Pay["💳 Processar Pagamento\n(/pay)"]
        BILL_Status["💓 Healthcheck\n(/status)"]

        %% Vulnerabilidades do Microserviço
        BILL_Invoices --- VULN_BOLA((Vulnerabilidade BOLA\nVazamento de Cartão)):::vulnerability
        BILL_Pay --- VULN_Tamper((Parameter Tampering\nFraude de Valor)):::vulnerability
    end

    %% ==========================================
    %% Conexões de Alta Visibilidade (Inter-Sistemas)
    %% ==========================================
    
    %% Fluxo de Ataque (Web Panel -> Intranet)
    ATK_SQLI ===> |"Envio de Payloads Maliciosos"| INT_Login
    ATK_XSS ===> |"Injeção de Scripts"| INT_Login
    SIM_Botnet ===> |"Tráfego de Navegação Simulado"| INT_Login
    
    %% Fluxo de Dados (Intranet -> Billing)
    STUD_Billing ===> |"Request JSON (BOLA Flaw)"| BILL_Invoices
    
    %% Fluxo de Monitoramento (Intranet -> Zabbix/Security)
    INT_Login -.-> |"Log de Falhas"| INT_Sec

    %% ==========================================
    %% Legenda de Cores
    %% ==========================================
    subgraph Legenda
        direction LR
        L1[Ambiente Atacante]:::attackerNode
        L2[Aplicação Alvo]:::targetNode
        L3[Microserviço SOA]:::microserviceNode
        L4((Ponto de Vulnerabilidade)):::vulnerability
    end

    %% Estilização de Subgrafos garantindo contraste (Fundo Branco + Texto Preto)
    style Web_Panel fill:#ffffff,stroke:#b71c1c,stroke-width:2px,color:#000000
    style Intranet_App fill:#ffffff,stroke:#0d47a1,stroke-width:2px,color:#000000
    style Billing_Microservice fill:#ffffff,stroke:#1b5e20,stroke-width:2px,color:#000000
    style Dashboards fill:#f1f8ff,stroke:#90caf9,stroke-dasharray: 5 5,color:#000000
    style Legenda fill:#ffffff,stroke:#9e9e9e,stroke-width:2px,color:#000000

    %% Aplicação de Classes aos nós
    class WP_Stats,WP_Attacks,WP_Stress,WP_Sim,WP_SNMP,WP_Admin attackerNode;
    class INT_Setup,INT_Login,INT_Admin,INT_Prof,INT_Stud,INT_Sec,PROF_Actions,STUD_Billing,INT_Router targetNode;
    class BILL_Invoices,BILL_Pay,BILL_Status microserviceNode;
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
| `/admin` | `admin_page` | Gestão de usuários do próprio Painel de Controle. |

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
