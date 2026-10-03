# datasync-api (livraison #652) -- SGBD central de synchronisation (SQLite + FTS5), API source centrale.
FROM python:3.12-slim
WORKDIR /app
COPY datasync/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY datasync/api/app.py datasync/api/matching.py ./
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
RUN mkdir -p /data
EXPOSE 5000
# un seul worker : SQLite en WAL, écritures des connecteurs sérialisées dans le processus (threads).
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--timeout", "300", "app:app"]
