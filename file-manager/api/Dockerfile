FROM python:3.11-slim

WORKDIR /app

# Contexte de build = RACINE du projet (docker-compose.yml : context: .),
# comme pour tous les services : les chemins sont donc préfixés par
# file-manager/api/. Livré en #397 avec des chemins relatifs au dossier
# (COPY requirements.txt .) -- premier build réel en #409 : "/store.py:
# not found". Modèle : backup-restore/api/Dockerfile (même livraison, qui
# build). Piège déjà documenté : un service jamais construit ici ne révèle
# ce genre d'erreur qu'au premier `docker compose build` réel.
COPY file-manager/api/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt

COPY file-manager/api/app.py .
COPY file-manager/api/store.py .

# Fichiers partagés, copiés À PLAT dans /app : app.py fait
# `from log_buffer import ...` et `from version_endpoint import ...`
# (la version #397 copiait log_buffer.py dans /app/shared/, jamais
# importable ainsi -- le journal partagé aurait été silencieusement absent).
COPY shared/log_buffer.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .

RUN mkdir -p /data /protected-space

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
