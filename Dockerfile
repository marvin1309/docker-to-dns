FROM python:3.12-slim

# Arbeitsverzeichnis erstellen und setzen
WORKDIR /app

# Python-Abhängigkeiten kopieren und installieren
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Applikationscode kopieren
COPY app/ /app/

# Datenverzeichnis für SQLite erstellen
RUN mkdir -p /app/data

# Standard-Environment setzen
ENV DNS_PROVIDER=powerdns \
    PDNS_API_URL=http://localhost:8081/api/v1 \
    PDNS_ZONE=example.com \
    CHECK_INTERVAL=60 \
    DB_PATH=/app/data/dns_records.db

# Startbefehl festlegen
CMD ["python", "main.py"]
