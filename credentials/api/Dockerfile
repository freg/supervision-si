# credentials-api (livraison #498) — coffre des accès d'équipements du
# hub (identifiants utilisés par les SERVICES : RouterOS, SSH, HTTP,
# SNMP). Même patron que les autres services Python (contexte de build =
# racine du dépôt, pour shared/secret_crypto.py et version_endpoint.py).
FROM python:3.12-slim

WORKDIR /app

COPY credentials/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY credentials/api/app.py credentials/api/store.py credentials/api/credential_crypto.py .
COPY credentials/api/static/ ./static/
COPY shared/secret_crypto.py shared/version_endpoint.py .
COPY shared/VERSION.json .

# Base SQLite + sel de chiffrement : volume /data (voir docker-compose.yml)
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
