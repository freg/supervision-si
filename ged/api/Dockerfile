FROM python:3.12-slim

WORKDIR /app

COPY ged/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ged/api/app.py .
COPY ged/api/documents_store.py .
COPY ged/api/mayan_client.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV GED_DB_PATH=/data/ged.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
