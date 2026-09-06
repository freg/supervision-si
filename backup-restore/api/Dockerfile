FROM python:3.12-slim

WORKDIR /app

COPY backup-restore/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backup-restore/api/app.py .
COPY backup-restore/api/store.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV BACKUP_RESTORE_DB_PATH=/data/backup-restore.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:app"]
