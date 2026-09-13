# imap-connectors (livraison #489) — gestionnaire de connecteurs IMAP
# vers les API du hub. Même patron que les autres services Python du
# projet (contexte de build = racine du dépôt, pour shared/).
FROM python:3.12-slim

WORKDIR /app

COPY imap-connectors/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY imap-connectors/app.py imap-connectors/store.py \
     imap-connectors/imap_fetch.py imap-connectors/interpreters.py \
     imap-connectors/router.py ./
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

EXPOSE 5000

# UN SEUL worker : le poller est un thread du processus — deux workers
# double-sonderaient les boîtes et se voleraient les marquages « lu ».
# Les requêtes HTTP restent concurrentes via les threads.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "app:app"]
