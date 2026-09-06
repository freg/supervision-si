FROM python:3.12-slim

# gdal-bin fournit ogr2ogr -- utilisé en sous-processus plutôt que les
# bindings Python GDAL (notoirement fragiles à installer/maintenir).
# libpq-dev requis pour compiler psycopg2 si le binaire pre-compile
# psycopg2-binary ne convient pas a l'architecture cible.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gdal-bin \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY geo-import/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY geo-import/api/app.py .
COPY shared/log_buffer.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "app:app"]
