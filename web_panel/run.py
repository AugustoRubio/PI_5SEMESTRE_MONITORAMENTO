import uvicorn
import os

if __name__ == "__main__":
    # Verifica se os certificados SSL existem, se não, avisa o usuário
    cert_path = "certs/cert.pem"
    key_path = "certs/key.pem"
    
    if not os.path.exists(cert_path) or not os.path.exists(key_path):
        print("="*60)
        print("AVISO: Certificados SSL não encontrados!")
        print("Por favor, execute 'python generate_certs.py' primeiro.")
        print("="*60)
        exit(1)

    print("Iniciando o servidor com suporte a SSL (HTTPS)...")
    # Rodando o servidor na porta 8443 (HTTPS)
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8443,
        ssl_keyfile=key_path,
        ssl_certfile=cert_path,
        reload=True
    )
