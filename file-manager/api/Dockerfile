FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY store.py .

# shared/ est monté depuis le contexte de build (racine du projet)
COPY shared/log_buffer.py /app/shared/log_buffer.py
COPY shared/version_endpoint.py /app/version_endpoint.py

RUN mkdir -p /data /protected-space

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
