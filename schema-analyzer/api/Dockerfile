FROM python:3.12-slim

WORKDIR /app

COPY schema-analyzer/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY schema-analyzer/api/app.py .
COPY schema-analyzer/api/schema_client.py .
COPY schema-analyzer/api/relation_detector.py .
COPY schema-analyzer/api/list_detector.py .
COPY schema-analyzer/api/relation_validator.py .
COPY schema-analyzer/api/relations_store.py .
COPY schema-analyzer/api/graph_export.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV SCHEMA_ANALYZER_DB_PATH=/data/schema-analyzer.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
