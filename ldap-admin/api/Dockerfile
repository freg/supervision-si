FROM python:3.12-slim

WORKDIR /app

COPY ldap-admin/api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ldap-utils -- fournit les VRAIS binaires ldapsearch/ldapmodify,
# demandé explicitement ("réinjectable depuis un shell") : ldap_client.py
# construit des commandes shell vers ces mêmes outils, jamais une
# bibliothèque Python intermédiaire (aucune disponible pour la tester
# dans l'environnement de développement -- voir README pour cette
# réserve).
RUN apt-get update && apt-get install -y --no-install-recommends ldap-utils \
    && rm -rf /var/lib/apt/lists/*

COPY ldap-admin/api/app.py ldap-admin/api/ldap_client.py ldap-admin/api/ldap_backup.py ldap-admin/api/ldif_tools.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
COPY shared/log_buffer.py .

RUN mkdir -p /data/backups

EXPOSE 5000

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "app:app"]
