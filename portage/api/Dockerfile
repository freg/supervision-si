# portage-api (livraison #650) -- fiche projet, imports code/dump, exécution de portage-kit.
# portage-kit n'est PAS dans ce dépôt : volume PORTAGE_KIT_DIR -> /opt/portage-kit, installé par l'entrypoint.
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1
RUN apt-get update && apt-get install -y --no-install-recommends mariadb-client git && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY portage/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
# dépendances du kit et des applications générées (le kit lui-même arrive par volume)
RUN pip install --no-cache-dir "sqlalchemy>=2.0" "pymysql>=1.1" "pytest>=8" "requests>=2.31" "pillow>=10"
COPY portage/api/app.py .
COPY portage/api/portspec.py .
COPY portage/api/entrypoint.sh /entrypoint.sh
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
RUN chmod +x /entrypoint.sh && mkdir -p /data
EXPOSE 5000
ENTRYPOINT ["/entrypoint.sh"]
# UN seul worker : l'exécution de la chaîne vit dans un thread du processus (état _runs), pas de doublon multi-workers.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "600", "app:app"]
