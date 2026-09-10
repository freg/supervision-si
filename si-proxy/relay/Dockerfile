# Relais du bastion si-proxy (#452) : aiguilleur TLS pur stdlib, aucune
# dépendance. Réservé à freg (jetons + TLS ; mTLS optionnel).
FROM python:3.12-slim
WORKDIR /app
COPY si-proxy/siproxy /app/siproxy
COPY si-proxy/relay/entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh
ENTRYPOINT ["/app/entrypoint.sh"]
