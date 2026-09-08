FROM python:3.12-slim

WORKDIR /app

# Chemins RELATIFS À LA RACINE du projet (context: .) -- piège corrigé
# en #409 sur file-manager-api, jamais `COPY app.py .` ici.
COPY ups-monitor/api/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt

COPY ups-monitor/api/app.py .
COPY ups-monitor/api/store.py .
COPY ups-monitor/api/poller.py .
COPY ups-monitor/api/alerts.py .
COPY ups-monitor/api/notify.py .
COPY shared/secrets_alert.py .
COPY ups-monitor/api/ups_parser.py .
COPY ups-monitor/api/credential_crypto.py .
COPY shared/secret_crypto.py .
COPY shared/log_buffer.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

ENV UPS_MONITOR_DB_PATH=/data/ups-monitor.db
RUN mkdir -p /data

EXPOSE 5000

# UN seul worker, VOLONTAIREMENT : l'automate de relevé tourne dans le
# processus (thread de fond) et décide « est-il temps ? » sur la base --
# deux workers feraient parfois deux relevés au même instant. Le trafic
# de cette API (une tuile, quelques onduleurs) n'a pas besoin de plus.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "app:app"]
