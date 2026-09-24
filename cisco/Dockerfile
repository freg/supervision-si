# cisco-api (livraison #508) — supervision, sauvegarde/restauration de
# configuration et gestes d'urgence sur switchs/routeurs Cisco (IOS,
# NX-OS) par SSH. Même patron que mikrotik. UN seul worker : sessions
# SSH séquentielles, sauvegarde automatique sans doublon.
FROM python:3.12-slim
WORKDIR /app
COPY cisco/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY cisco/app.py cisco/parsers.py cisco/ssh_client.py .
COPY cisco/static/ ./static/
# Registre écrasé au runtime par le bind mount (docker-compose.yml)
COPY cisco/switches.json ./switches.json
COPY shared/version_endpoint.py .
COPY shared/notify_client.py .
COPY shared/registry_edit.py .
COPY shared/VERSION.json .
RUN mkdir -p /data
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "4", "--timeout", "300", "app:app"]
