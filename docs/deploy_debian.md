# Guia de Implantação do Painel Web no Debian 12

Este guia descreve como colocar o Painel Web (FastAPI) em produção no seu servidor físico Debian 12, utilizando seus próprios certificados SSL e configurando-o como um serviço do sistema (`systemd`) para que ele inicie automaticamente com o servidor.

## 1. Pré-requisitos no Debian 12

Acesse seu servidor Debian 12 via SSH e instale os pacotes necessários:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip git
```

## 2. Clonar o Repositório

Vá para o diretório onde deseja hospedar a aplicação (ex: `/opt`):

```bash
cd /opt
sudo git clone https://github.com/AugustoRubio/PI_5SEMESTRE_MONITORAMENTO.git
sudo chown -R $USER:$USER /opt/PI_5SEMESTRE_MONITORAMENTO
cd /opt/PI_5SEMESTRE_MONITORAMENTO/web_panel
```

## 3. Configurar o Ambiente Virtual e Dependências

Crie o ambiente virtual e instale as bibliotecas:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 4. Configurar os Certificados SSL e Variáveis de Ambiente

O painel agora suporta a definição de certificados SSL reais através de um arquivo `.env`.

1. Copie o arquivo de exemplo:
   ```bash
   cp .env.example .env
   ```

2. Edite o arquivo `.env` com o seu editor preferido (ex: `nano .env`):
   ```env
   HOST=0.0.0.0
   PORT=8443

   # AQUI VOCÊ DEFINE OS CAMINHOS PARA OS SEUS CERTIFICADOS REAIS
   # Exemplo se estiver usando Let's Encrypt:
   SSL_CERT_PATH=/etc/letsencrypt/live/seudominio.com/fullchain.pem
   SSL_KEY_PATH=/etc/letsencrypt/live/seudominio.com/privkey.pem

   # Mude isso para uma string longa e aleatória (ex: gerada com `openssl rand -hex 32`)
   SECRET_KEY=sua_chave_secreta_gerada_aqui
   ```

*Nota: Certifique-se de que o usuário que vai rodar o painel tenha permissão de leitura nos arquivos do certificado.*

## 5. Criar o Serviço Systemd (Para rodar em Background)

Para que o painel rode continuamente e reinicie caso o servidor seja reiniciado, criaremos um serviço no Linux.

1. Crie o arquivo do serviço:
   ```bash
   sudo nano /etc/systemd/system/webpanel.service
   ```

2. Cole o seguinte conteúdo (ajuste os caminhos se você clonou em outro lugar):
   ```ini
   [Unit]
   Description=Painel Web de Simulacao PI 5 Semestre
   After=network.target

   [Service]
   User=root
   Group=root
   WorkingDirectory=/opt/PI_5SEMESTRE_MONITORAMENTO/web_panel
   Environment="PATH=/opt/PI_5SEMESTRE_MONITORAMENTO/web_panel/venv/bin"
   ExecStart=/opt/PI_5SEMESTRE_MONITORAMENTO/web_panel/venv/bin/python run.py
   Restart=always

   [Install]
   WantedBy=multi-user.target
   ```
   *(Nota: Usamos `User=root` aqui para facilitar a leitura de certificados em `/etc/` e para futuras execuções de comandos SSH, mas em ambientes de altíssima segurança, recomenda-se criar um usuário específico).*

## 6. Iniciar e Habilitar o Serviço

Recarregue o systemd, inicie o serviço e habilite-o para iniciar no boot:

```bash
sudo systemctl daemon-reload
sudo systemctl start webpanel
sudo systemctl enable webpanel
```

## 7. Verificar o Status

Para verificar se o painel está rodando corretamente e se carregou seus certificados:

```bash
sudo systemctl status webpanel
```

Se tudo estiver verde (active/running), você já pode acessar o painel pelo navegador usando o IP ou Domínio do seu servidor Debian na porta 8443:
`https://seu-dominio-ou-ip:8443`
