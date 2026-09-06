FROM python:3.12-slim

WORKDIR /app

COPY classifier/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY classifier/api/app.py .
COPY classifier/api/store.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV CLASSIFIER_DB_PATH=/data/classifier.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
