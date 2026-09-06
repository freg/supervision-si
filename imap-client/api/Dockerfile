FROM python:3.12-slim

WORKDIR /app

COPY imap-client/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY imap-client/api/app.py .
COPY imap-client/api/imap_wrapper.py .
COPY imap-client/api/rules_store.py .
COPY imap-client/api/rule_engine.py .
COPY imap-client/api/interpreters_store.py .
COPY imap-client/api/interpreter_engine.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV IMAP_RULES_DB_PATH=/data/imap-rules.db
RUN mkdir -p /data

EXPOSE 5000

# `imaplib` = bibliothèque STANDARD Python -- aucune dépendance
# supplémentaire à installer pour ce service, contrairement à
# ssh-tunnels (openssh-client) ou dba-api (pymysql/psycopg2).
# 2 workers -- SQLite gère bien un accès concurrent LÉGER (simple
# CRUD + application de règles, pas de vrais processus OS à gérer,
# contrairement à ssh-tunnels qui EXIGE un seul worker).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "30", "app:app"]
