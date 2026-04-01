FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y procps openssh-client && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulator.py .
COPY urls.txt .

# Inicia o simulador automaticamente com o container.
# Ele irá tentar conectar via SSH no alvo configurado no docker-compose.yml
CMD ["python", "-u", "simulator.py"]