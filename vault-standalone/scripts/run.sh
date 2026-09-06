#!/usr/bin/env bash
# Démarrage de l'instance ISOLÉE du coffre-fort.
#
#   ./vault-standalone/scripts/run.sh up -d --build
#
# Réutilise TELS QUELS les scripts PKI du projet principal
# (pki/scripts/generate-ca.sh, generate-server-cert.sh) -- ils lisent
# déjà PKI_DIR/HOST_IP par variable d'environnement EXPORTÉE en
# priorité sur .env (voir leur propre get_env()), il suffit donc de
# les surcharger ici pour obtenir une CA et un certificat séparés de
# ceux du stack principal, sans dupliquer un seul octet de ces
# scripts.
set -euo pipefail

HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # vault-standalone/
PROJECT_ROOT="$(cd "$HERE_DIR/.." && pwd)"

fail() {
  echo "" >&2
  echo "❌ ARRÊT — l'instance isolée n'a PAS été (re)lancée. Voir l'erreur ci-dessus." >&2
  echo "" >&2
  exit 1
}

# Sous-commandes spéciales, jamais transmises à docker compose.
if [ "${1:-}" = "down" ]; then
  cd "$HERE_DIR"
  docker compose down
  exit 0
fi

# HOST_IP dédiée à l'instance isolée -- décidé avec la personne, une
# IP/entrée DNS distincte du hub. Repli sur une détection automatique
# SEULEMENT si VAULT_STANDALONE_HOST_IP n'est explicitement définie
# nulle part (variable exportée, ou .env du projet) : sur la même
# machine que le hub, une détection automatique retomberait sur LA
# MÊME IP que HOST_IP, qui n'est probablement pas ce qui est voulu ici
# (le but même de cette instance est une entrée séparée).
VAULT_STANDALONE_HOST_IP="${VAULT_STANDALONE_HOST_IP:-}"
if [ -z "$VAULT_STANDALONE_HOST_IP" ]; then
  VAULT_STANDALONE_HOST_IP="$(grep -E '^VAULT_STANDALONE_HOST_IP=' "$PROJECT_ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2-)"
fi
if [ -z "$VAULT_STANDALONE_HOST_IP" ]; then
  echo "⚠️  VAULT_STANDALONE_HOST_IP non définie -- utilisation de '127.0.0.1'." >&2
  echo "   Pour une vraie IP/entrée DNS séparée du hub (le but de cette instance)," >&2
  echo "   la renseigner dans .env ou l'exporter avant d'appeler ce script :" >&2
  echo "     VAULT_STANDALONE_HOST_IP=<ip_ou_dns> $0 $*" >&2
  echo "" >&2
  # "localhost" (utilisé ici jusqu'à la livraison #357) CASSE le
  # démarrage -- ${VAULT_STANDALONE_HOST_IP} sert AUSSI d'adresse de
  # LIAISON de port Docker (docker-compose.yml, service
  # keycloak-standalone : "${VAULT_STANDALONE_HOST_IP:-127.0.0.1}:...")
  # -- Docker exige une VRAIE adresse IP pour cet usage précis (ou
  # 0.0.0.0), jamais un nom d'hôte : "invalid IP address: localhost"
  # en conditions réelles (signalé par la personne). "127.0.0.1" reste
  # un composant d'URL parfaitement valide pour les autres usages de
  # cette même variable (KC_HOSTNAME, VITE_*_URL) -- corrige les deux
  # usages avec la même valeur, jamais besoin de les distinguer.
  VAULT_STANDALONE_HOST_IP="127.0.0.1"
fi
export VAULT_STANDALONE_HOST_IP
echo "VAULT_STANDALONE_HOST_IP : $VAULT_STANDALONE_HOST_IP"

# Realm Keycloak isolé -- voir vault-standalone/keycloak/render.py
# (réutilise keycloak/render.py du stack principal par import, même
# .env, mêmes garde-fous).
python3 "$HERE_DIR/keycloak/render.py" || fail

# CA + certificat de CETTE instance -- PKI_DIR et HOST_IP surchargés
# pour cette seule invocation (export local à ce script, jamais
# propagé au stack principal) : les scripts pki/ restent
# TÉLS QUELS, jamais copiés ni modifiés.
if [ -x "$PROJECT_ROOT/pki/scripts/generate-ca.sh" ]; then
  PKI_DIR="$HERE_DIR/pki" HOST_IP="$VAULT_STANDALONE_HOST_IP" \
    "$PROJECT_ROOT/pki/scripts/generate-ca.sh" || fail
  PKI_DIR="$HERE_DIR/pki" HOST_IP="$VAULT_STANDALONE_HOST_IP" \
    "$PROJECT_ROOT/pki/scripts/generate-server-cert.sh" || fail
else
  echo "⚠️  pki/scripts/ introuvable — TLS non préparé." >&2
fi

# Config nginx isolée -- voir
# vault-standalone/tls-proxy/render_nginx_conf.py.
python3 "$HERE_DIR/tls-proxy/render_nginx_conf.py" || fail

cd "$HERE_DIR"
docker compose "$@"
