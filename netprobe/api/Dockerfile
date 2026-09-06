FROM python:3.12-slim

WORKDIR /app

# iputils-ping -- binaire réel utilisé par ping_probe.py (#297), même
# motif que openssh-client pour ssh-tunnels-api : jamais réimplémenté
# soi-même un protocole déjà bien géré par un binaire mature.
# nmap -- même raisonnement, utilisé par nmap_probe.py (#302).
# tcpdump -- même raisonnement, utilisé par tcpdump_probe.py (#305).
# iperf3 -- même raisonnement, utilisé par iperf3_probe.py (#385,
# backlog item 47 reformulé -- "couche expérience client" sans RF).
# Boucle de reprise -- livraison #304, réseau instable confirmé en
# conditions réelles (échec systématique sur le build complet du
# stack, réussi seulement à la 3ème tentative même en isolation) --
# nmap tire des dépendances (scripts NSE, libpcap) assez lourdes pour
# être exposées à une coupure transitoire. 3 essais, 5s de pause
# entre chacun -- jamais une boucle infinie qui masquerait un vrai
# problème de configuration (dépôt injoignable, proxy mal réglé).
RUN for i in 1 2 3; do \
      apt-get update && apt-get install -y --no-install-recommends iputils-ping nmap tcpdump iperf3 && break; \
      echo "apt-get a échoué (tentative $i/3) -- nouvel essai dans 5s..." >&2; \
      sleep 5; \
    done && rm -rf /var/lib/apt/lists/*

COPY netprobe/api/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt

COPY netprobe/api/app.py .
COPY netprobe/api/store.py .
COPY netprobe/api/ping_probe.py .
COPY netprobe/api/scheduler.py .
COPY netprobe/api/nmap_probe.py .
COPY netprobe/api/tcpdump_probe.py .
COPY netprobe/api/iperf3_probe.py .
COPY netprobe/api/analyzer_engine.py .
COPY netprobe/api/analyzers/ ./analyzers/
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

ENV NETPROBE_DB_PATH=/data/netprobe.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
