FROM python:3.9-slim

WORKDIR /app

RUN apt-get update && apt-get install -y procps openssh-client && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY simulator.py .
COPY urls.txt .

# Mantém o container ocioso em background aguardando comandos do web_panel via docker exec
CMD ["tail", "-f", "/dev/null"]