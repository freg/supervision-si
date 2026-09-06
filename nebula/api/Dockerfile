FROM python:3.12-slim

WORKDIR /app

COPY nebula/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY nebula/api/app.py .
COPY nebula/api/nebula_client.py .
COPY nebula/api/csv_import.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV NEBULA_DB_PATH=/data/nebula.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:app"]
