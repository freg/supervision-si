FROM python:3.12-slim

WORKDIR /app

COPY zenoss/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY zenoss/api/app.py .
COPY shared/log_buffer.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
