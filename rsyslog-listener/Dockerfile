FROM python:3.12-slim

WORKDIR /app

COPY rsyslog-listener/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rsyslog-listener/api/app.py .
COPY rsyslog-listener/api/listener.py .
COPY rsyslog-listener/api/syslog_parser.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

EXPOSE 5000
# Port UDP d'écoute syslog -- voir app.py (RSYSLOG_LISTEN_PORT),
# EXPOSÉ séparément du port HTTP 5000 (/health, /logs) -- deux
# protocoles distincts sur deux ports distincts, jamais mélangés.
EXPOSE 5514/udp

# UN SEUL worker -- voir app.py/README.md pour le raisonnement complet
# (le port UDP ne peut être BOUND que par un seul processus à la
# fois -- même motif que ssh-tunnels-api, #159).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "60", "app:app"]
