FROM python:3.12-slim

WORKDIR /app

COPY docker-monitor/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker-monitor/api/app.py .
COPY shared/log_buffer.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

EXPOSE 5000

# ⚠️ --workers 1 (PAS 2 comme les autres services de ce projet) --
# DÉLIBÉRÉ, voir le docstring de app.py : la boucle d'analyse
# périodique tournerait en double avec 2 workers séparés (2 process
# Python distincts, chacun sa propre boucle) -- double écriture dans
# le fichier d'analyse externe, double charge sur l'API Docker.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--timeout", "60", "app:app"]
