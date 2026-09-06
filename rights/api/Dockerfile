FROM python:3.12-slim

WORKDIR /app

COPY rights/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY rights/api/app.py .
COPY rights/api/store.py .
COPY rights/api/file_inventory.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

ENV RIGHTS_DB_PATH=/data/rights.db
ENV RIGHTS_PROJECT_ROOT=/project
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
