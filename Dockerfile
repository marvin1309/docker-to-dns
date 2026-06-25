FROM python:3.12-slim

# Build-time version (set by CI from version.py); surfaced at runtime in logs.
ARG VERSION=dev

# Arbeitsverzeichnis erstellen und setzen
WORKDIR /app

# Python-Abhängigkeiten kopieren und installieren
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Applikationscode kopieren
COPY app/ /app/

# Datenverzeichnis für SQLite erstellen
RUN mkdir -p /app/data

# Standard-Environment setzen.
# PDNS_HOST_IP / PDNS_ZONE / PDNS_API_KEY are intentionally NOT defaulted: a
# missing value must fail loudly at startup instead of silently registering
# wrong records (e.g. in an example.com zone).
ENV APP_VERSION=$VERSION \
    DNS_PROVIDER=powerdns \
    PDNS_API_URL=http://localhost:8081/api/v1 \
    PDNS_API_TIMEOUT=10 \
    CHECK_INTERVAL=60 \
    RECONCILE_INTERVAL=300 \
    DB_PATH=/app/data/dns_records.db \
    PYTHONUNBUFFERED=1
    
# Startbefehl festlegen
CMD ["python", "main.py"]
