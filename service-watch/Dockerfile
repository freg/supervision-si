# service-watch-api (livraison #531) -- supervision des entrées de services
# vues d'Internet : inventaire DNS, qualification, scénarios HTTP avec
# compte de test du coffre, empreinte de contenu, canaris mail. Un seul
# worker (planificateur en thread), page servie sous /service-watch/.
FROM python:3.12-slim
WORKDIR /app
COPY service-watch/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY service-watch/app.py service-watch/checks.py service-watch/probe.py service-watch/store.py .
COPY service-watch/static/ ./static/
COPY service-watch/entries.json ./entries.json
COPY shared/version_endpoint.py shared/secrets_alert.py .
COPY shared/VERSION.json .
RUN mkdir -p /data
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--timeout", "600", "app:app"]
