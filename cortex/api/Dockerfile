# cortex-api (#462) -- chemins relatifs à la racine du projet (context: .)
FROM python:3.12-slim
WORKDIR /app
COPY cortex/api/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt
COPY cortex/api/app.py cortex/api/store.py cortex/api/normalize.py cortex/api/correlate.py cortex/api/collectors.py cortex/api/principles.py cortex/api/oui.py cortex/api/changes.py ./
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
ENV CORTEX_DB_PATH=/data/cortex.db
RUN mkdir -p /data
EXPOSE 5000
# UN seul worker : la boucle de collecte et l'état « en cours » vivent dans le processus.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "120", "app:app"]
