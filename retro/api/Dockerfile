FROM python:3.12-slim

WORKDIR /app

COPY retro/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY retro/api/app.py .
COPY retro/api/php_sql_scanner.py .
COPY retro/api/html_view_scanner.py .
COPY retro/api/route_scanner.py .
COPY retro/api/journeys.py .
COPY retro/api/journeys_store.py .
COPY retro/api/ui_spec.py .
COPY retro/api/merge.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

EXPOSE 5000

# --timeout allongé (livraison #243) -- une grosse archive ZIP (code
# d'une application entière, potentiellement des centaines de
# fichiers) peut prendre plus que les 30s par défaut de gunicorn à
# analyser -- jamais un worker tué en pleine analyse.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "120", "app:app"]
