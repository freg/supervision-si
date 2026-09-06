FROM python:3.12-slim

WORKDIR /app

COPY snmp/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY snmp/api/app.py .
COPY snmp/api/snmp_client.py .
COPY snmp/api/targets_store.py .
COPY snmp/api/credential_crypto.py .
COPY shared/secret_crypto.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV SNMP_DB_PATH=/data/snmp.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:app"]
