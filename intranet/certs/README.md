# Instruções para Certificados SSL

Como o Nginx está configurado para usar HTTPS na porta 443, você precisa colocar os certificados SSL nesta pasta antes de subir os containers ou rodar o script de instalação.

Os arquivos devem ter exatamente os seguintes nomes:
- `cert.pem` (O certificado público)
- `key.pem` (A chave privada)

Se você estiver apenas testando localmente e quiser gerar um certificado autoassinado rápido, execute o seguinte comando no Linux (dentro desta pasta `certs`). 

> **Aviso GNS3**: Utilize RSA 2048 bits ou ECDSA. O uso de chaves de 4096 bits (como em tutoriais antigos) gera certificados muito grandes que excedem o tamanho de um único pacote de rede (MTU de 1500 bytes). No GNS3, isso frequentemente causa falha de fragmentação e o navegador trava na etapa "Performing a TLS handshake..." até dar Timeout.

**Comando recomendado (RSA 2048, rápido e compatível):**
```bash
openssl req -x509 -newkey rsa:2048 -keyout key.pem -out cert.pem -days 365 -nodes -subj "/CN=localhost"
```