FROM python:3.12-slim

WORKDIR /app

COPY tickets/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# postgresql-client -- fournit pg_dump/psql, nécessaires à
# backup_manager.py pour le dump natif en backend PostgreSQL (voir
# tickets/README.md, sauvegardes versionnées). Sans effet en backend
# SQLite (défaut) -- backup_manager utilise alors conn.iterdump(),
# natif à la bibliothèque standard.
RUN apt-get update && apt-get install -y --no-install-recommends postgresql-client \
    && rm -rf /var/lib/apt/lists/*

COPY tickets/api/app.py tickets/api/ics_parser.py tickets/api/filter_engine.py tickets/api/suggestion_engine.py tickets/api/nlp_helper.py tickets/api/google_oauth.py tickets/api/backup_manager.py tickets/api/db_explorer.py tickets/api/sql_console.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .
COPY shared/safe_json.py .

ENV TICKETS_DB_PATH=/data/tickets.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
