FROM python:3.12-slim

WORKDIR /app

# tcpdump -- le seul paquet système nécessaire, c'est l'outil de
# capture lui-même (demandé explicitement : "à base de tcpdump").
# Nécessite CAP_NET_RAW/CAP_NET_ADMIN au lancement du conteneur (voir
# docker-compose.yml, cap_add) -- sans ces capacités, tcpdump échoue
# avec "You don't have permission to capture on that device", géré
# proprement par la boucle de réessai de app.py (jamais un crash).
RUN apt-get update && apt-get install -y --no-install-recommends tcpdump \
    && rm -rf /var/lib/apt/lists/*

COPY network-agent/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY network-agent/api/app.py .
COPY network-agent/api/capture.py .
COPY network-agent/api/pcap_parser.py .
COPY network-agent/api/store.py .
COPY network-agent/api/dns_resolver.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV NETWORK_AGENT_DB_PATH=/data/network-agent.db
RUN mkdir -p /data

# Port configurable (livraison #239) -- COLLISION RÉELLE trouvée au
# déploiement : ce conteneur tourne en `network_mode: host` (#238),
# donc son port est directement celui de l'HÔTE, pas un port Docker
# isolé -- 5000 était déjà occupé par un `docker-registry` tournant
# sur la même machine ("Connection in use: ('0.0.0.0', 5000)" dans
# les vrais logs gunicorn). Défaut changé pour 15000 (bien moins
# courant que 5000, un des ports par défaut les plus disputés qui
# soient) -- reste SURCHARGEABLE via NETWORK_AGENT_HOST_PORT si
# jamais CE port entre aussi en collision sur un déploiement donné.
ENV NETWORK_AGENT_HOST_PORT=15000
EXPOSE 15000

# Forme SHELL (pas exec) -- volontaire, SEUL moyen pour que
# $NETWORK_AGENT_HOST_PORT soit interpolé par le shell avant que
# gunicorn ne démarre (la forme exec `CMD ["gunicorn", ...]` ne fait
# AUCUNE expansion de variable d'environnement).
CMD gunicorn --bind 0.0.0.0:$NETWORK_AGENT_HOST_PORT --workers 1 --timeout 60 app:app
