FROM python:3.12-slim

WORKDIR /app

# Client mysql officiel -- nécessaire pour l'import de sauvegardes
# mysqldump (voir /connections/<id>/import-mysql-dump dans app.py) :
# s'appuie sur cet outil plutôt que de reparser le SQL nous-mêmes,
# bien plus robuste face aux subtilités d'un vrai fichier de dump
# (points-virgules dans des littéraux, DELIMITER pour les routines...).
RUN apt-get update && apt-get install -y --no-install-recommends default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

COPY dba/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY dba/api/app.py .
COPY dba/api/connectors/ connectors/
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV DBA_DB_PATH=/data/dba.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
