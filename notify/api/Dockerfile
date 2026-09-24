# notify-api (#590) : notifications par courriel et gestionnaire d'envoi détaché.
# Chemins RELATIFS À LA RACINE du projet (context: .) -- piège #409.
FROM python:3.12-slim
WORKDIR /app
COPY notify/api/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt
COPY notify/api/app.py notify/api/core.py .
COPY si-proxy/admin/auth.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
EXPOSE 5000
# UN seul worker : le fil d'envoi et le verrou vivent dans le processus.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "app:app"]
