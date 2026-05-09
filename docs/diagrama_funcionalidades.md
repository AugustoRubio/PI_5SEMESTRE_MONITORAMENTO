# Diagrama de Funcionalidades e Rotas

Este documento detalha a arquitetura lógica, os fluxos de dados, os pontos de vulnerabilidade e a capacidade de carga da Botnet que compõem o ecossistema de monitoramento.

## Mapa de Fluxo, Interações e Capacidade de Carga

```mermaid
flowchart TD
    %% ==========================================
    %% Definições de Estilo (Alta Fidelidade - Safe Colors)
    %% ==========================================
    classDef attackerNode fill:mistyrose,stroke:darkred,stroke-width:3px,color:black,font-weight:bold;
    classDef targetNode fill:aliceblue,stroke:darkblue,stroke-width:3px,color:black,font-weight:bold;
    classDef microserviceNode fill:honeydew,stroke:darkgreen,stroke-width:3px,color:black,font-weight:bold;
    classDef securityNode fill:lavender,stroke:indigo,stroke-width:3px,color:black,font-weight:bold;
    classDef monitorNode fill:ivory,stroke:goldenrod,stroke-width:3px,color:black,font-weight:bold;
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

        %% Conexões ancoradas em nós específicos para evitar sobreposição de textos
        WP_Admin --> |"Define Alvos"| BOT_DDOS
        WP_Admin --> |"Config MIBs"| SNMP_APC
        WP_Stats -.-> |"Lê Métricas Docker"| BOT_STUD
        WP_Attacks --> |"Payload"| BOT_DDOS
    end

    %% ==========================================
    %% Subgrafo: Appliance de Segurança (Gateway)
    %% ==========================================
    subgraph Security_Appliance ["🛡️ 2. GATEWAY DE SEGURANÇA (IPS/IDS)"]
        direction TB
        PFSENSE["🔥 pfSense + Suricata\n(Deep Packet Inspection & Firewall)"]:::securityNode
    end

    %% ==========================================
    %% Subgrafo: Intranet Alvo (Aplicação Monitorada)
    %% ==========================================
    subgraph Intranet_App ["🎯 3. INTRANET (Alvo Principal)"]
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
    subgraph Billing_Microservice ["💰 4. BILLING API (Microserviço SOA)"]
        direction TB
        BILL_Invoices["📄 Listar Faturas\n(/invoices/{id})"]
        BILL_Pay["💳 Processar Pagamento\n(/pay)"]
        
        BILL_Invoices --- VULN_BOLA((Vulnerabilidade BOLA)):::vulnerability
        BILL_Pay --- VULN_Tamper((Parameter Tampering)):::vulnerability
    end

    %% ==========================================
    %% Subgrafo: Camada de Monitoramento (Zabbix)
    %% ==========================================
    subgraph Monitoring ["📊 5. MONITORAMENTO CENTRAL"]
        direction TB
        ZABBIX["🖥️ Zabbix Server\n(LLD, Traps, Triggers & Dashboards)"]:::monitorNode
    end

    %% ==========================================
    %% Conexões de Alta Visibilidade (Fluxo Completo)
    %% ==========================================
    
    %% Tráfego do Atacante Passa pelo Firewall/IPS
    BOT_DDOS ===> |"Flood L7 Lixo"| PFSENSE
    BOT_STUD ===> |"Auth Stress (Bcrypt)"| PFSENSE
    WP_Attacks ===> |"Injeção L7 (POST)"| PFSENSE
    
    %% Firewall encaminha para a Aplicação
    PFSENSE ===> |"Tráfego Filtrado"| INT_Login
    BOT_PROF ===> |"Carga Banco/Local"| INT_Login
    BOT_SOA ===> |"BOLA HTTP Flood"| BILL_Invoices
    
    %% Alvo -> Microserviço
    STUD_Billing ===> |"Consumo de API"| BILL_Invoices
    
    %% ==========================================
    %% O que o Zabbix monitora? (Pontos Chave)
    %% ==========================================
    PFSENSE -.-> |"1. Alertas DPI\n(eve.json: SQLi, XSS, Path Traversal)"| ZABBIX
    INT_Sec -.-> |"2. LLD Metrics API\n(Detecção de Bruteforce/Falhas)"| ZABBIX
    SNMP_Simulator -.-> |"3. SNMP Polling\n(Status Bateria, Temperatura)"| ZABBIX

    %% ==========================================
    %% Estilização de Subgrafos
    %% ==========================================
    style Web_Panel fill:white,stroke:darkred,stroke-width:2px,color:black
    style Security_Appliance fill:ghostwhite,stroke:indigo,stroke-width:2px,color:black
    style Intranet_App fill:white,stroke:darkblue,stroke-width:2px,color:black
    style Billing_Microservice fill:white,stroke:darkgreen,stroke-width:2px,color:black
    style Dashboards fill:aliceblue,stroke:dodgerblue,stroke-dasharray: 5 5,color:black
    style Monitoring fill:ivory,stroke:goldenrod,stroke-width:2px,color:black

    %% Aplicação de Classes
    class WP_Stats,WP_Attacks,WP_Admin attackerNode;
    class INT_Setup,INT_Login,INT_Admin,INT_Prof,INT_Stud,INT_Sec,PROF_Actions,STUD_Billing,INT_Router targetNode;
    class BILL_Invoices,BILL_Pay microserviceNode;
```

> **Dica para uso no Word:** O diagrama acima foi convertido para uma imagem pronta para ser copiada e colada.  
> ![Diagrama de Funcionalidades](diagrama_funcionalidades.png)

## Especificações Técnicas e Carga do Sistema

### 1. Botnet Agent (Capacidade de Simulação)
O projeto utiliza um motor assíncrono (`aiohttp`) para gerar carga volumétrica e estressar o monitoramento.

| Tipo de Bot | Qtd de Workers | Ações Principais | Impacto no Monitoramento |
| :--- | :---: | :--- | :--- |
| **DDoS Bot** | 50 | POST Flood com payload de 20KB de dados lixo. | Estresse de CPU e Tráfego no pfSense/Suricata. |
| **Aluno Bot** | 10 | Login (Bcrypt), navegação randômica, consulta de notas. | Estresse de CPU (Criptografia) nos containers. |
| **Prof Bot** | 10 | Login, lançamento de notas em massa, registro de presença. | Estresse de I/O de Banco de Dados (MySQL). |
| **SOA Bot** | 30 | Acesso direto a faturas (BOLA) e fraudes de valor (Tampering). | Gatilhos de DLP e Estresse na Billing API. |

### 2. Os 3 Pilares do Monitoramento (Zabbix)
A integração com o **Zabbix Server** ocorre lendo métricas de 3 camadas distintas da infraestrutura:

1. **Inspeção Profunda (DPI) via Suricata**:
   * O tráfego dos bots passa pelo **pfSense**.
   * O **Suricata** analisa os pacotes (Layer 7) procurando assinaturas maliciosas (SQLi, XSS, Path Traversal disparados pelo `WP_Attacks`).
   * Alertas são escritos no `eve.json` e lidos pelo Zabbix (Log Trapping).
2. **Monitoramento de Aplicação (Bruteforce)**:
   * A Intranet possui uma API em `/security/metrics` que expõe logs em tempo real de tentativas de login malsucedidas.
   * O Zabbix utiliza **LLD (Low-Level Discovery)** para alertar ataques de Bruteforce (vindos do *Aluno Bot*).
3. **Monitoramento IoT/Hardware (SNMP)**:
   * O **SNMP Simulator** emula dispositivos reais (Nobreaks APC, Sensores de Temperatura).
   * O Zabbix realiza *Polling* ativo utilizando as MIBs e Templates (`zabbix_templates/`) configurados no projeto, acionando triggers caso a bateria caia ou a temperatura suba.

### 3. Recursos de Infraestrutura (VEX)
O projeto está preparado para rodar em arquiteturas virtualizadas com as seguintes metas:

- **Gateway/Firewall**: pfSense (Mínimo 2 vCPUs, 2GB RAM para aguentar o Suricata inline).
- **Alvo (Intranet + API + DB)**: VM com 4 vCPUs e 4GB RAM (Recomendado devido ao Bcrypt stress).
- **Atacante (Web Panel + Bots)**: VM Dockerizada com 2 vCPUs e 2GB RAM.
- **Monitoramento**: VM Zabbix Server 6.0 LTS (2 vCPUs, 2GB RAM).

---
*Este diagrama é atualizado automaticamente conforme novas rotas ou capacidades de carga são integradas ao sistema.*
