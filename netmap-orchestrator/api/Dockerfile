FROM python:3.12-slim

WORKDIR /app

COPY netmap-orchestrator/api/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt

COPY netmap-orchestrator/api/app.py .
COPY netmap-orchestrator/api/store.py .
COPY netmap-orchestrator/api/engine.py .
COPY netmap-orchestrator/api/network_agent_client.py .
COPY netmap-orchestrator/api/rules/ ./rules/
COPY shared/log_buffer.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

ENV NETMAP_ORCHESTRATOR_DB_PATH=/data/netmap-orchestrator.db
RUN mkdir -p /data

EXPOSE 5000

# ⚠️ --workers 1 (PAS 2) -- MÊME raisonnement que docker-monitor-api
# (#376) : la boucle de fond (passage périodique des règles) tournerait
# en double avec 2 workers séparés -- écritures concurrentes sur la
# même base SQLite, appels redondants à network-agent-api.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "60", "app:app"]
