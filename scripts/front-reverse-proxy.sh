#!/bin/bash
# Frontal public du hub supervision-si (livraison #471) : Apache en HTTPS
# (certificat Let's Encrypt via certbot, renouvellement automatique) qui
# fait proxy inverse vers la VM du hub. À lancer en root sur la VM qui
# reçoit le 443 public (Debian / Ubuntu). Idempotent : relançable, la
# configuration du site est régénérée à chaque passage.
#
#   PUBLIC_HOST=hub.mondomaine.fr LE_EMAIL=moi@mondomaine.fr sudo -E ./front-reverse-proxy.sh
#
# Variables :
#   PUBLIC_HOST    nom public de CE frontal (DNS -> adresse publique ; 80 et 443 publiés vers lui) [obligatoire]
#   LE_EMAIL       courriel Let's Encrypt (expiration, incidents)                                  [obligatoire]
#   HUB_UPSTREAM   passerelle du hub vue depuis ce frontal                     (défaut https://super:443)
#   HUB_CA         ca.crt de la PKI du projet pour VÉRIFIER le certificat du hub (recommandé) ;
#                  absent = SSLProxyCheckPeerName off (chiffré mais non vérifié -- LAN seulement)
#   HTTP_PORT      port en clair pour le défi ACME et la redirection           (défaut 80)
#   STAGING=1      certificat de test Let's Encrypt (sans quota) pour valider la chaîne d'abord
#   INTERNAL_ORIGIN  origine INTERNE du hub telle que construite (https://<HOST_IP>:<GATEWAY_PORT>,
#                  ex. https://192.0.2.10:6443) : le frontal RÉÉCRIT alors cette origine en
#                  https://PUBLIC_HOST dans les réponses (HTML, JS, CSS, JSON, en-têtes Location)
#                  -> le hub reste construit pour le LAN, aucun rebuild, les deux accès coexistent (#473).
#                  Côté hub il ne reste qu'à déclarer l'origine publique à Keycloak :
#                  KEYCLOAK_EXTRA_ORIGINS=https://PUBLIC_HOST dans .env, python3 keycloak/render.py, ré-import.
#
# Sans INTERNAL_ORIGIN -- prérequis CÔTÉ HUB (VM super) : les URL du hub sont construites au BUILD
# avec HOST_IP:GATEWAY_PORT (36 usages dans docker-compose.yml). Pour être
# utilisable derrière ce frontal, le hub doit être construit pour le nom
# public. Dans .env de super :
#     HOST_IP=hub.mondomaine.fr      GATEWAY_PORT=443
# puis  ./pki/scripts/generate-server-cert.sh      (SAN = le nouveau nom)
#       python3 keycloak/render.py                 (URL de redirection des clients OIDC ;
#                                                   run.sh propose la ré-importation du realm)
#       ./scripts/run.sh up -d --build
# et, sur le LAN, faire résoudre hub.mondomaine.fr vers ce frontal (DNS
# interne ou /etc/hosts) si la box ne fait pas de « hairpin NAT ».
set -euo pipefail
: "${PUBLIC_HOST:?PUBLIC_HOST requis (nom public de ce frontal)}"
: "${LE_EMAIL:?LE_EMAIL requis (courriel pour Let’s Encrypt)}"
HUB_UPSTREAM="${HUB_UPSTREAM:-https://super:443}"
HUB_CA="${HUB_CA:-}"
HTTP_PORT="${HTTP_PORT:-80}"
INTERNAL_ORIGIN="${INTERNAL_ORIGIN:-}"; INTERNAL_ORIGIN="${INTERNAL_ORIGIN%/}"
INTERNAL_HOSTPORT="${INTERNAL_ORIGIN#https://}"; INTERNAL_HOSTPORT="${INTERNAL_HOSTPORT#http://}"
SITE="hub-${PUBLIC_HOST}"
CONF="/etc/apache2/sites-available/${SITE}.conf"
CERT_DIR="/etc/letsencrypt/live/${PUBLIC_HOST}"
UPSTREAM_HOSTPORT="${HUB_UPSTREAM#https://}"; UPSTREAM_HOSTPORT="${UPSTREAM_HOSTPORT#http://}"; UPSTREAM_HOSTPORT="${UPSTREAM_HOSTPORT%/}"
[ "$(id -u)" = "0" ] || { echo "à lancer en root (sudo -E pour conserver les variables)" >&2; exit 1; }

# --- blocs de configuration -------------------------------------------------
http_block() {
cat <<EOF
# Frontal public du hub supervision-si -- généré par front-reverse-proxy.sh (#471). Ne pas éditer : relancer le script.
<VirtualHost *:${HTTP_PORT}>
    ServerName ${PUBLIC_HOST}
    DocumentRoot /var/www/acme
    <Directory /var/www/acme>
        Require all granted
    </Directory>
    # défi ACME servi en clair, tout le reste redirigé en HTTPS
    RewriteEngine On
    RewriteCond %{REQUEST_URI} !^/\.well-known/acme-challenge/
    RewriteRule ^ https://${PUBLIC_HOST}%{REQUEST_URI} [R=301,L]
    ErrorLog \${APACHE_LOG_DIR}/${SITE}-error.log
    CustomLog \${APACHE_LOG_DIR}/${SITE}-access.log combined
</VirtualHost>
EOF
}

https_block() {
cat <<EOF

<VirtualHost *:443>
    ServerName ${PUBLIC_HOST}
    SSLEngine on
    SSLCertificateFile ${CERT_DIR}/fullchain.pem
    SSLCertificateKeyFile ${CERT_DIR}/privkey.pem
    SSLProtocol -all +TLSv1.2 +TLSv1.3
    Header always set Strict-Transport-Security "max-age=31536000"

    # vers la passerelle nginx du hub (HTTPS, certificat de la PKI interne)
    SSLProxyEngine on
    ${CA_LINES}
    ProxyPreserveHost On
    ProxyRequests Off
    ProxyTimeout 900
    RequestHeader set X-Forwarded-Proto "https"
    RequestHeader set X-Forwarded-Port "443"
    # WebSocket (consoles, HMR) : bascule sur wstunnel quand le client demande Upgrade
    RewriteEngine On
    RewriteCond %{HTTP:Upgrade} =websocket [NC]
    RewriteRule ^/(.*)$ wss://${UPSTREAM_HOSTPORT}/\$1 [P,L]
    ProxyPass        / ${HUB_UPSTREAM%/}/ retry=0 keepalive=On
    ProxyPassReverse / ${HUB_UPSTREAM%/}/
    # gros envois (sauvegardes, GED) : pas de plafond côté frontal
    LimitRequestBody 0
${SUBST_LINES}

    ErrorLog \${APACHE_LOG_DIR}/${SITE}-error.log
    CustomLog \${APACHE_LOG_DIR}/${SITE}-access.log combined
</VirtualHost>
EOF
}

echo "== 1/5 paquets"
export DEBIAN_FRONTEND=noninteractive
apt-get install -y -q apache2 certbot >/dev/null
a2enmod -q ssl proxy proxy_http proxy_wstunnel headers rewrite >/dev/null

echo "== 2/5 CA du hub"
if [ -n "$HUB_CA" ] && [ -f "$HUB_CA" ]; then
  install -m 644 "$HUB_CA" /etc/ssl/certs/supervision-si-ca.crt
  CA_LINES="SSLProxyCACertificateFile /etc/ssl/certs/supervision-si-ca.crt"
  echo "   certificat du hub vérifié avec $HUB_CA"
else
  CA_LINES="SSLProxyCheckPeerName off
    SSLProxyCheckPeerCN off"
  echo "   AVERTISSEMENT : pas de HUB_CA -> le certificat du hub n'est pas vérifié (chiffré seulement)"
fi

SUBST_LINES=""
if [ -n "$INTERNAL_ORIGIN" ]; then
  a2enmod -q substitute deflate filter >/dev/null
  SUBST_LINES="
    # #473 : réécriture de l'origine interne (${INTERNAL_ORIGIN}) en https://${PUBLIC_HOST}
    # dans les corps (HTML, JS, CSS, JSON) et les en-têtes Location / cookies -- le hub reste
    # construit pour le LAN. Réponses décompressées (INFLATE) avant substitution.
    ProxyPassReverse / ${INTERNAL_ORIGIN}/
    ProxyPassReverseCookieDomain ${INTERNAL_HOSTPORT%%:*} ${PUBLIC_HOST}
    RequestHeader unset Accept-Encoding
    AddOutputFilterByType INFLATE;SUBSTITUTE;DEFLATE text/html text/css text/javascript application/javascript application/x-javascript application/json text/plain
    SubstituteMaxLineLength 32m
    Substitute \"s|${INTERNAL_ORIGIN}|https://${PUBLIC_HOST}|ni\"
    Substitute \"s|wss://${INTERNAL_HOSTPORT}|wss://${PUBLIC_HOST}|ni\"
    Substitute \"s|//${INTERNAL_HOSTPORT}/|//${PUBLIC_HOST}/|n\""
  echo "   réécriture activée : ${INTERNAL_ORIGIN} -> https://${PUBLIC_HOST}"
fi

echo "== 3/5 site HTTP (défi ACME + redirection)"
mkdir -p /var/www/acme
http_block > "$CONF"
a2ensite -q "$SITE" >/dev/null
apache2ctl configtest >/dev/null && systemctl reload apache2

echo "== 4/5 certificat Let's Encrypt"
STAGE=""; [ "${STAGING:-0}" = "1" ] && STAGE="--staging"
certbot certonly --webroot -w /var/www/acme -d "$PUBLIC_HOST" -m "$LE_EMAIL" --agree-tos --non-interactive --keep-until-expiring $STAGE
[ -f "$CERT_DIR/fullchain.pem" ] || { echo "certificat absent : $CERT_DIR" >&2; exit 1; }
# renouvellement : certbot.timer (paquet, 2 essais/jour) + rechargement d'Apache après un renouvellement
mkdir -p /etc/letsencrypt/renewal-hooks/deploy
printf '#!/bin/sh\nsystemctl reload apache2\n' > /etc/letsencrypt/renewal-hooks/deploy/reload-apache.sh
chmod +x /etc/letsencrypt/renewal-hooks/deploy/reload-apache.sh
systemctl enable --now certbot.timer >/dev/null 2>&1 || true

echo "== 5/5 site HTTPS -> ${HUB_UPSTREAM}"
{ http_block; https_block; } > "$CONF"
apache2ctl configtest && systemctl reload apache2
echo
echo "frontal prêt : https://${PUBLIC_HOST}/  ->  ${HUB_UPSTREAM}"
echo "renouvellement : systemctl list-timers certbot.timer ; essai à blanc : certbot renew --dry-run"
echo "journal : tail -f /var/log/apache2/${SITE}-error.log"
