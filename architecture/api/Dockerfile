FROM python:3.12-slim

WORKDIR /app

COPY architecture/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY architecture/api/app.py .
COPY architecture/api/store.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .
COPY shared/safe_json.py .

ENV ARCHITECTURE_DB_PATH=/data/architecture.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
