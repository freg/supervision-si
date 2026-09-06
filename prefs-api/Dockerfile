FROM python:3.12-slim

WORKDIR /app

COPY prefs-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY prefs-api/app.py .
COPY prefs-api/keycloak_admin.py .
COPY prefs-api/log_sources_poller.py .
COPY prefs-api/file_source_poller.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV PREFS_DB_PATH=/data/prefs.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
