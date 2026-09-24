# mikrotik (livraison #485) — supervision/commande des routeurs
# MikroTik. Même patron que les autres services Python du projet
# (contexte de build = racine du dépôt, pour shared/version_endpoint).
FROM python:3.12-slim

WORKDIR /app

COPY mikrotik/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY mikrotik/app.py mikrotik/routeros_client.py mikrotik/ssh_client.py mikrotik/natrules.py .
COPY mikrotik/static/ ./static/
# Registre des routeurs — écrasé au RUNTIME par le bind mount
# (./mikrotik/routers.json, voir docker-compose.yml) : la copie ne
# sert que de valeur de repli si le montage est oublié.
COPY mikrotik/routers.json ./routers.json
COPY shared/version_endpoint.py .
COPY shared/notify_client.py .
COPY shared/registry_edit.py .
COPY shared/VERSION.json .

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
