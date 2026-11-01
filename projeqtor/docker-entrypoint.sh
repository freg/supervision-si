#!/bin/bash
# Entrypoint de projeqtor-app (livraison #476) — voir projeqtor/README.md.
#
# Au PREMIER démarrage seulement, génère /data/config/parameters.php
# (fichier de paramètres ProjeQtOr, placé hors de la portée web via
# tool/parametersLocation.php — écrit au build, voir Dockerfile) à
# partir des variables d'environnement. JAMAIS régénéré ensuite : les
# retouches faites depuis l'écran de configuration de ProjeQtOr (qui
# réécrit ce fichier) ou à la main sont préservées.
set -euo pipefail

DATA_DIR="${PROJEQTOR_DATA_CONTAINER_DIR:-/data}"
PARAMS_FILE="$DATA_DIR/config/parameters.php"

DB_HOST="${PROJEQTOR_DB_HOST:-projeqtor-db}"
DB_PORT="${PROJEQTOR_DB_PORT:-3306}"
DB_NAME="${PROJEQTOR_DB_NAME:-projeqtor}"
DB_USER="${PROJEQTOR_DB_USER:-projeqtor}"
DB_PASSWORD="${PROJEQTOR_DB_PASSWORD:?PROJEQTOR_DB_PASSWORD manquante -- voir .env.example (scripts/generate-env.sh la genere)}"

LOCALE="${PROJEQTOR_DEFAULT_LOCALE:-fr}"
TIMEZONE="${PROJEQTOR_DEFAULT_TIMEZONE:-Europe/Paris}"

# Échappe une valeur pour une chaîne PHP entre apostrophes (\ puis ').
php_quote() {
  printf '%s' "$1" | sed -e 's/\\/\\\\/g' -e "s/'/\\\\'/g"
}

# LDAP_URL (ldap://hote:port ou ldaps://hote:port) -> hôte et port
# SÉPARÉS, format attendu par les paramètres ProjeQtOr
# (paramLdap_host / paramLdap_port, voir src/tool/config.php).
LDAP_HOST=""
LDAP_PORT=""
if [ -n "${LDAP_URL:-}" ]; then
  scheme="${LDAP_URL%%://*}"
  rest="${LDAP_URL#*://}"
  LDAP_HOST="${rest%%:*}"
  LDAP_HOST="${LDAP_HOST%%/*}"
  if [ "$scheme" = "ldaps" ]; then
    LDAP_PORT="636"
  else
    LDAP_PORT="389"
  fi
  case "$rest" in
    *:*)
      port_part="${rest#*:}"
      port_part="${port_part%%/*}"
      if [ -n "$port_part" ]; then
        LDAP_PORT="$port_part"
      fi
      ;;
  esac
fi

mkdir -p "$DATA_DIR/config" "$DATA_DIR/attachments" "$DATA_DIR/documents" \
         "$DATA_DIR/logs" "$DATA_DIR/tmp"

if [ ! -f "$PARAMS_FILE" ]; then
  echo "projeqtor-app : génération de $PARAMS_FILE (premier démarrage)"
  {
    echo '<?php'
    echo "// Généré par projeqtor/docker-entrypoint.sh au premier démarrage,"
    echo "// depuis les variables d'environnement (.env). ProjeQtOr RÉÉCRIT ce"
    echo "// fichier quand on utilise son écran de configuration ; l'entrypoint"
    echo "// ne le régénère jamais tant qu'il existe -- le supprimer pour"
    echo "// repartir des variables d'environnement."
    printf '$paramDbType=%s;\n' "'mysql'"
    printf '$paramDbHost=%s;\n' "'$(php_quote "$DB_HOST")'"
    printf '$paramDbPort=%s;\n' "'$(php_quote "$DB_PORT")'"
    printf '$paramDbName=%s;\n' "'$(php_quote "$DB_NAME")'"
    printf '$paramDbUser=%s;\n' "'$(php_quote "$DB_USER")'"
    printf '$paramDbPassword=%s;\n' "'$(php_quote "$DB_PASSWORD")'"
    printf '$paramDbPrefix=%s;\n' "''"
    printf '$paramDbDisplayName=%s;\n' "'ProjeQtOr (hub supervision-si)'"
    printf '$defaultLocale=%s;\n' "'$(php_quote "$LOCALE")'"
    printf '$paramDefaultTimezone=%s;\n' "'$(php_quote "$TIMEZONE")'"
    # Chemins HORS de la portée web (conseil de sécurité upstream,
    # src/readme.txt) -- volume monté, voir docker-compose.yml.
    printf '$logFile=%s;\n' "'/data/logs/projeqtor_\${date}.log'"
    printf '$paramAttachmentDirectory=%s;\n' "'/data/attachments/'"
    printf '$documentRoot=%s;\n' "'/data/documents/'"
    printf '$paramReportTempDirectory=%s;\n' "'/data/tmp/'"
    if [ -n "$LDAP_HOST" ]; then
      echo '// Authentification sur l annuaire du hub (livraison #476) --'
      echo '// mêmes comptes que Keycloak (uid). Voir projeqtor/README.md.'
      printf '$paramLdap_allow_login=%s;\n' "'true'"
      printf '$paramLdap_base_dn=%s;\n' "'$(php_quote "${LDAP_USERS_DN:-}")'"
      printf '$paramLdap_host=%s;\n' "'$(php_quote "$LDAP_HOST")'"
      printf '$paramLdap_port=%s;\n' "'$(php_quote "$LDAP_PORT")'"
      printf '$paramLdap_version=%s;\n' "'3'"
      printf '$paramLdap_search_user=%s;\n' "'$(php_quote "${LDAP_BIND_DN:-}")'"
      printf '$paramLdap_search_pass=%s;\n' "'$(php_quote "${LDAP_BIND_PASSWORD:-}")'"
      printf '$paramLdap_user_filter=%s;\n' "'uid=%USERNAME%'"
    else
      printf '$paramLdap_allow_login=%s;\n' "'false'"
    fi
  } > "$PARAMS_FILE"
fi

# Attente BORNÉE de la base (MariaDB met quelques secondes à s'initialiser
# au tout premier démarrage) : évite un premier accès web cassé. Au-delà
# du délai, on démarre quand même -- ProjeQtOr réessaie à chaque accès.
echo "projeqtor-app : attente de la base $DB_HOST:$DB_PORT ..."
tries=0
until mysqladmin ping -h "$DB_HOST" -P "$DB_PORT" --silent 2>/dev/null; do
  tries=$((tries + 1))
  if [ "$tries" -ge 30 ]; then
    echo "AVERTISSEMENT : base injoignable après ~60s -- démarrage quand même." >&2
    break
  fi
  sleep 2
done

# Le volume /data est un bind mount depuis l'hôte : le conteneur écrit
# en www-data (uid 33). Idempotent, sans effet si déjà au bon propriétaire.
chown -R www-data:www-data "$DATA_DIR"

exec "$@"
