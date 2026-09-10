FROM python:3.12-slim

WORKDIR /app

# #459 : le gestionnaire de sauvegardes du hub lance scripts/full_backup.py
# (git bundle, openssl enc, docker pour les volumes) dans ce conteneur.
RUN apt-get update && apt-get install -y --no-install-recommends git openssl ca-certificates curl \
    && ARCH="$(uname -m)" && DOCKER_VERSION=27.3.1 \
    && curl -fsSL "https://download.docker.com/linux/static/stable/${ARCH}/docker-${DOCKER_VERSION}.tgz" | tar xz --strip-components=1 -C /usr/local/bin docker/docker \
    && rm -rf /var/lib/apt/lists/*

COPY backup-restore/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backup-restore/api/app.py .
COPY backup-restore/api/store.py .
COPY backup-restore/api/hub_backups.py .
COPY backup-restore/api/connectors/ ./connectors/
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV BACKUP_RESTORE_DB_PATH=/data/backup-restore.db
RUN mkdir -p /data

EXPOSE 5000

# UN seul worker depuis #459 : le gestionnaire de sauvegardes du hub tient
# son état (sauvegarde en cours, planification) en mémoire du processus.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app"]
