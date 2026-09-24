# services-api (#584) : feu tricolore et redémarrage des conteneurs du hub.
# Chemins RELATIFS À LA RACINE du projet (context: .) -- piège #409.
FROM python:3.12-slim
# #586 : le même conteneur sert de « runner » aux jobs de la tour de contrôle
# (./scripts/run.sh ... up -d --build) : CLI Docker + plugin compose
# (binaires statiques de l'image officielle), bash et git.
COPY --from=docker:27-cli /usr/local/bin/docker /usr/local/bin/docker
COPY --from=docker:27-cli /usr/local/libexec/docker/cli-plugins /usr/local/libexec/docker/cli-plugins
RUN apt-get update && apt-get install -y --no-install-recommends git iproute2 && rm -rf /var/lib/apt/lists/* \
    && git config --system --add safe.directory '*'
WORKDIR /app
COPY services/api/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 60 -r requirements.txt
COPY services/api/app.py .
COPY services/api/lights.py .
COPY services/api/tower.py .
# Vérificateur de jeton Keycloak partagé avec si-proxy-admin-api (#454).
COPY si-proxy/admin/auth.py .
COPY shared/version_endpoint.py .
COPY shared/VERSION.json .
EXPOSE 5000
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "1", "--threads", "8", "--timeout", "300", "app:app"]
