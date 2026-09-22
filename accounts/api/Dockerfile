FROM python:3.12-slim

WORKDIR /app

COPY accounts/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY accounts/api/app.py .
COPY accounts/api/kc.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
