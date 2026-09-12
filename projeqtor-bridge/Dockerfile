# projeqtor-bridge (livraison #484) — pont OPTLINE/ProjeQtOr/hub.
# Même patron que les autres services Python du projet (contexte de
# build = racine du dépôt, pour partager shared/version_endpoint.py).
FROM python:3.12-slim

WORKDIR /app

COPY projeqtor-bridge/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY projeqtor-bridge/app.py projeqtor-bridge/optline_format.py \
     projeqtor-bridge/mapping.py projeqtor-bridge/projeqtor_client.py \
     projeqtor-bridge/sync.py projeqtor-bridge/ldap_import.py .
COPY projeqtor-bridge/static/ ./static/
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

# État de la synchronisation (derniers ids poussés) — bind mount,
# voir docker-compose.yml.
RUN mkdir -p /data

EXPOSE 5000

# Un seul worker : la boucle de synchronisation tourne en thread DANS
# le processus — deux workers feraient deux boucles (doublons évités
# par la déduplication de tickets-api, mais trafic inutile).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "app:app"]
