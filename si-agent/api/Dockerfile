FROM python:3.12-slim

WORKDIR /app

# Chemins RELATIFS À LA RACINE du projet (context: .) -- piège corrigé
# en #409 sur file-manager-api, jamais `COPY app.py .` ici.
COPY si-agent/api/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt

COPY si-agent/api/app.py .
COPY si-agent/api/store.py .
# COPIES du protocole et du moteur de plugins partagés avec l'agent
# (source canonique : si-agent/agent/si_agent/), jamais une
# réimplémentation. Oublier l'une des deux = ModuleNotFoundError.
COPY si-agent/agent/si_agent/protocol.py ./si_agent_protocol.py
COPY si-agent/agent/si_agent/plugins.py ./si_agent_plugins.py
COPY shared/log_buffer.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

ENV SI_AGENT_DB_PATH=/data/si-agent.db
RUN mkdir -p /data

EXPOSE 5000

# UN seul worker : le thread de purge tourne dans le processus ; le trafic
# (quelques agents toutes les 30-60 s + une tuile) n'a pas besoin de plus.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "app:app"]
