FROM python:3.12-slim

WORKDIR /app

COPY glpi/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY glpi/api/app.py .
COPY glpi/api/glpi_client.py .
COPY glpi/api/excel_import.py .
COPY glpi/api/nebula_import.py .
COPY glpi/api/nebula_clients_import.py .
COPY glpi/api/snmp_import.py .
COPY glpi/api/network_agent_import.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

EXPOSE 5000

# 2 workers -- ce service ne gère aucun processus OS, aucune raison
# de se limiter à un seul worker (contrairement à ssh-tunnels).
# --timeout 300 -- un import de plusieurs centaines de lignes (le
# fichier fourni en a 220, plusieurs appels GLPI par ligne : recherche
# de doublon, dropdowns, création) peut dépasser largement les 60s
# habituels contre un GLPI réel -- éviter que le worker soit tué EN
# PLEIN IMPORT, ce qui laisserait un état partiel sans signal clair.
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "app:app"]
