FROM python:3.12-slim

WORKDIR /app

COPY api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY api/app.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

ENV DATA_DIR=/app/data
RUN mkdir -p /app/data

EXPOSE 5000

# gunicorn en prod-like dès le squelette, évite de changer de serveur plus tard
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
