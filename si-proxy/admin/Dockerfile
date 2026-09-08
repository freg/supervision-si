# si-proxy-admin-api (#454) : pont hub -> interface de contrôle du bastion.
# Chemins RELATIFS À LA RACINE du projet (context: .) -- piège #409.
FROM python:3.12-slim
WORKDIR /app
COPY si-proxy/admin/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt
COPY si-proxy/admin/app.py .
COPY si-proxy/admin/auth.py .
COPY si-proxy/admin/summary.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "app:app"]
