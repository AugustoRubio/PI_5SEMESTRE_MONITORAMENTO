FROM python:3.11-alpine

WORKDIR /app

# Invalidação de cache explícita para garantir instalação do pymysql e aiohttp
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir requests pymysql aiohttp aiomysql

COPY src/bot.py /app/bot.py

# ENV TARGET_URL e ENV BOT_TYPE serão injetados pelo Docker na inicialização
CMD ["python", "bot.py"]
