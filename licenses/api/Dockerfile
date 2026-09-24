# licenses-api (#595) : gestionnaire de licences logicielles par site.
# Chemins RELATIFS À LA RACINE du projet (context: .) -- piège #409.
FROM python:3.12-slim
WORKDIR /app
COPY licenses/api/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt
COPY licenses/api/app.py licenses/api/rules.py licenses/api/vendors.py .
COPY si-proxy/admin/auth.py .
COPY shared/version_endpoint.py .
COPY shared/notify_client.py .
COPY shared/VERSION.json .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "app:app"]
