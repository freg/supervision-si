FROM python:3.12-slim

WORKDIR /app

COPY tasks/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY tasks/api/app.py .
COPY tasks/api/store.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV TASKS_DB_PATH=/data/tasks.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
