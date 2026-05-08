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
    classDef metricsNode fill:white,stroke:dimgray,stroke-width:1px,color:black,font-size:10px;

    %% Estilo global para as setas
    linkStyle default stroke:dimgray,stroke-width:3px,color:black;

    %% ==========================================
    %% Subgrafo: Painel do Atacante (C2) e Botnet
    %% ==========================================
    subgraph Web_Panel ["🚨 1. WEB PANEL & BOTNET (C2)"]
        direction TB
        WP_Stats["📊 Dashboard\n(Monitoramento Docker Stats)"]
        WP_Attacks["⚔️ Central de Ataques\n(SQLi, XSS, Path Traversal)"]
        
        subgraph Botnet_Agent ["🤖 BOTNET AGENT (Capacidade de Carga)"]
            direction LR
            BOT_DDOS["🔥 DDoS Bot\n(50 Workers)\nPayload: 20KB/req"]:::attackerNode
            BOT_STUD["🎓 Aluno Bot\n(10 Workers)\nAuth + Bcrypt Stress"]:::attackerNode
            BOT_PROF["👨‍🏫 Prof Bot\n(10 Workers)\nDB Write/Read Batch"]:::attackerNode
            BOT_SOA["💰 SOA Bot\n(30 Workers)\nBOLA/Tamper Stress"]:::attackerNode
        end

        WP_Stats -.-> |"Métricas CPU/MEM"| Botnet_Agent
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
            INT_Admin["👑 Dashboard Admin\n(Gestão de Pessoas/Classes)"]
            INT_Prof["👨‍🏫 Dashboard Professor\n(Notas & Chamada)"]
            INT_Stud["🎓 Dashboard Aluno\n(Consulta de Status)"]
        end

        %% Ações Específicas Detalhadas
        INT_Admin --- ADM_Impersonate((IDOR / Impersonate)):::vulnerability
        INT_Prof --- PROF_Actions["Lançar Notas\nRegistrar Presença"]
        INT_Stud --- STUD_Billing["Acessar Área Financeira"]
        
        INT_Sec["🛡️ Metrics API\n(Fail Logs para Zabbix)"]
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
    %% Conexões de Alta Visibilidade (Inter-Sistemas)
    %% ==========================================
    
    BOT_DDOS ===> |"POST Flood 20KB"| INT_Login
    BOT_STUD ===> |"Auth + Navegação"| INT_Login
    BOT_PROF ===> |"Batch DB Writes"| INT_Login
    BOT_SOA ===> |"JSON Flood"| BILL_Invoices
    
    STUD_Billing ===> |"Request JSON"| BILL_Invoices
    INT_Login -.-> |"Zabbix Monitoring"| INT_Sec

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

    %% Estilização de Subgrafos
    style Web_Panel fill:white,stroke:darkred,stroke-width:2px,color:black
    style Intranet_App fill:white,stroke:darkblue,stroke-width:2px,color:black
    style Billing_Microservice fill:white,stroke:darkgreen,stroke-width:2px,color:black
    style Dashboards fill:aliceblue,stroke:dodgerblue,stroke-dasharray: 5 5,color:black
    style Legenda fill:white,stroke:gray,stroke-width:2px,color:black

    %% Aplicação de Classes aos nós
    class WP_Stats,WP_Attacks attackerNode;
    class INT_Setup,INT_Login,INT_Admin,INT_Prof,INT_Stud,INT_Sec,PROF_Actions,STUD_Billing,INT_Router targetNode;
    class BILL_Invoices,BILL_Pay microserviceNode;
```

## Especificações Técnicas e Carga do Sistema

### 1. Botnet Agent (Capacidade de Simulação)
O projeto utiliza um motor assíncrono (`aiohttp`) para gerar carga volumétrica e estressar o monitoramento.

| Tipo de Bot | Qtd de Workers | Ações Principais | Impacto no Monitoramento |
| :--- | :---: | :--- | :--- |
| **DDoS Bot** | 50 | POST Flood com payload de 20KB de dados lixo. | Estresse de CPU no Firewall e IPS (Suricata). |
| **Aluno Bot** | 10 | Login (Bcrypt), navegação randômica, consulta de notas. | Estresse de CPU (Criptografia) e Sessions. |
| **Prof Bot** | 10 | Login, lançamento de notas em massa, registro de presença. | Estresse de I/O de Banco de Dados (MySQL). |
| **SOA Bot** | 30 | Acesso direto a faturas (BOLA) e fraudes de valor (Tampering). | Gatilhos de DLP (Vazamento de Cartão de Crédito). |

### 2. Recursos e Monitoramento Docker
O **Web Panel** consome a API do Docker Engine para expor métricas em tempo real:

- **CPU Usage (%)**: Calculado via `cpu_delta` e `system_delta`, permitindo ver o impacto de cada bot no host.
- **Memory Usage (%)**: Monitoramento de *Memory Leaks* durante testes de estresse longos.
- **I/O Batching**: O simulador de professor utiliza `aiomysql` com `pool_size=100` e `max_overflow=200` para suportar milhares de requisições simultâneas.

### 3. Recursos de Infraestrutura (VEX)
O projeto está preparado para rodar em arquiteturas virtualizadas com as seguintes metas:

- **Alvo (Intranet)**: VM com 4 vCPUs e 4GB RAM (Mínimo recomendado para Bcrypt stress).
- **Atacante (Web Panel)**: VM com 2 vCPUs e 2GB RAM.
- **Banco de Dados**: MySQL 8.0 otimizado para conexões simultâneas.

---
*Este diagrama é atualizado automaticamente conforme novas rotas ou capacidades de carga são integradas ao sistema.*
