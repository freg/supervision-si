# network-equipment-api (livraison #506) — facette « équipements réseau »
# de l'exploration : identification (constructeur, modèle, génération),
# import Zenoss, profils de supervision SNMP. Même patron que les autres
# services Python (contexte de build = racine du dépôt, pour shared/).
FROM python:3.12-slim

WORKDIR /app

COPY network-equipment/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY network-equipment/api/app.py network-equipment/api/store.py network-equipment/api/identify.py \
     network-equipment/api/oui.py network-equipment/api/profiles.py network-equipment/api/snmp_tables.py \
     network-equipment/api/zenoss_import.py .
COPY shared/version_endpoint.py .
# A1 (#620) : périmètre de site par groupe -- garde commune + vérification du jeton
COPY shared/site_scope.py .
COPY si-proxy/admin/auth.py .

COPY shared/VERSION.json .

# Base SQLite + fichier OUI IEEE optionnel : volume /data (docker-compose.yml)
RUN mkdir -p /data

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "180", "app:app"]
