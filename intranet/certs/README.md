# Instruções para Certificados SSL

Como o Nginx está configurado para usar HTTPS na porta 443, você precisa colocar os certificados SSL nesta pasta antes de subir os containers.

Os arquivos devem ter exatamente os seguintes nomes:
- `cert.pem` (O certificado público)
- `key.pem` (A chave privada)

Se você estiver apenas testando localmente e quiser gerar um certificado autoassinado rápido, pode rodar o seguinte comando no Linux (dentro desta pasta `certs`):

```bash
openssl req -x509 -newkey rsa:4096 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```