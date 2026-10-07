FROM python:3.12-slim

WORKDIR /app

# #703 : police DejaVu (PDF : accents, flèches) et fuseaux horaires (heure du récapitulatif)
RUN apt-get update && apt-get install -y --no-install-recommends fonts-dejavu-core tzdata && rm -rf /var/lib/apt/lists/*
ENV TZ=Europe/Paris

COPY nebula/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# #702 : tous les modules du dossier (une liste à la main avait oublié ssidmatrix.py
# depuis #686 -> nebula-api ne démarrait plus après reconstruction)
COPY nebula/api/*.py ./
COPY nebula/plans/ ./plans/
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .
COPY shared/notify_client.py .

ENV NEBULA_DB_PATH=/data/nebula.db
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "60", "app:app"]
