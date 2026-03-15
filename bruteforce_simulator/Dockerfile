FROM python:3.11-alpine
WORKDIR /app
RUN pip install --no-cache-dir httpx
COPY attack.py .
CMD ["python", "attack.py"]