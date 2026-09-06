FROM python:3.12-slim

# openssh-client -- fournit les binaires `ssh` et `ssh-keygen`
# RÉELLEMENT utilisés par ce service (tunnel_process.py/key_scanner.py),
# absents de l'image de base. sshfs (livraison #180, montage SSHFS
# réel) fournit le binaire `sshfs` lui-même ET `fusermount` en
# dépendance (paquet fuse3). sshpass (livraison #210, authentification
# par mot de passe -- backlog item 12) fournit le mécanisme non
# interactif de saisie du mot de passe (`sshpass -e`, lit la variable
# d'environnement `SSHPASS`) utilisé par tunnel_process.py/
# mount_process.py en mode `auth_method="password"`. Aucun de ces
# paquets n'est installable dans l'environnement de développement
# (réseau restreint, voir ssh-tunnels/README.md), mais l'installation
# normale ici, dans l'image FINALE, n'a pas cette contrainte.
RUN apt-get update && apt-get install -y --no-install-recommends openssh-client sshfs sshpass \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ssh-tunnels/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ssh-tunnels/api/app.py .
COPY ssh-tunnels/api/tunnels_store.py .
COPY ssh-tunnels/api/key_scanner.py .
COPY ssh-tunnels/api/tunnel_process.py .
COPY ssh-tunnels/api/mount_process.py .
COPY ssh-tunnels/api/credential_crypto.py .
COPY shared/secret_crypto.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV SSH_TUNNELS_DB_PATH=/data/ssh-tunnels.db
ENV SSH_KEYS_DIR=/keys
ENV SSH_MOUNTS_BASE_DIR=/mounts
RUN mkdir -p /data /mounts

EXPOSE 5000

# UN SEUL worker -- voir app.py/README.md pour le raisonnement
# complet (gestion de VRAIS processus OS, PID en base, récolteur de
# zombies -- ne se prête pas au même partage multi-worker que les
# tampons de logs des autres services de ce projet).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "60", "app:app"]
