import uvicorn
import os
from dotenv import load_dotenv

# Carrega as variáveis de ambiente do arquivo .env
load_dotenv()

if __name__ == "__main__":
    # Busca os caminhos dos certificados no .env, com fallback para a pasta certs local (apenas para dev)
    cert_path = os.getenv("SSL_CERT_PATH", "certs/cert.pem")
    key_path = os.getenv("SSL_KEY_PATH", "certs/key.pem")
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8443))
    
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print("="*60)
        print("ERRO FATAL: Certificados SSL não encontrados!")
        print("Verifique os caminhos definidos no seu arquivo .env:")
        print(f"SSL_CERT_PATH: {cert_path}")
        print(f"SSL_KEY_PATH: {key_path}")
        print("="*60)
        exit(1)

    print(f"Iniciando o servidor com suporte a SSL (HTTPS) em {host}:{port}...")
    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        ssl_keyfile=key_path,
        ssl_certfile=cert_path,
        reload=False  # Em produção (Debian), o reload deve ficar desativado
    )
