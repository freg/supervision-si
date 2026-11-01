#!/bin/sh
# Rend la configuration de Radicale depuis l'environnement (LDAP_* du .env), puis lance le serveur.
# Sans LDAP_URL : authentification htpasswd (/config/users, bcrypt) -- fichier à créer à la main (htpasswd -B).
set -eu
CFG=/config/radicale.conf
if [ -n "${LDAP_URL:-}" ]; then
  AUTH="type = ldap
ldap_uri = ${LDAP_URL}
ldap_base = ${LDAP_USERS_DN:-}
ldap_reader_dn = ${LDAP_BIND_DN:-}
ldap_secret = ${LDAP_BIND_PASSWORD:-}
ldap_filter = ${RADICALE_LDAP_FILTER:-(&(objectClass=inetOrgPerson)(uid={0}))}
ldap_user_attribute = uid"
else
  AUTH="type = htpasswd
htpasswd_filename = /config/users
htpasswd_encryption = bcrypt"
fi
# compte de service de groupware-api (carnet / agenda dans le hub) : en htpasswd, ajouté ou mis à jour ici (bcrypt) ;
# en LDAP, il doit exister dans l'annuaire (GROUPWARE_DAV_SERVICE_USER / PASSWORD = un compte LDAP dédié).
if [ -z "${LDAP_URL:-}" ] && [ -n "${GROUPWARE_DAV_SERVICE_USER:-}" ] && [ -n "${GROUPWARE_DAV_SERVICE_PASSWORD:-}" ]; then
  touch /config/users
  python3 - "$GROUPWARE_DAV_SERVICE_USER" "$GROUPWARE_DAV_SERVICE_PASSWORD" <<'PY'
import sys, bcrypt
u, p = sys.argv[1], sys.argv[2]
lines = [l for l in open("/config/users", encoding="utf-8").read().splitlines() if l and not l.startswith(u + ":")]
lines.append(u + ":" + bcrypt.hashpw(p.encode(), bcrypt.gensalt()).decode())
open("/config/users", "w", encoding="utf-8").write("\n".join(lines) + "\n")
PY
fi
[ -f /config/rights ] || printf '[owner-write]\nuser: .+\ncollection: ^{user}(/.*)?$\npermissions: RW\n\n[root]\nuser: .+\ncollection: ^$\npermissions: R\n' > /config/rights
cat > "$CFG" <<CONF
[server]
hosts = 0.0.0.0:5232
max_content_length = 100000000

[auth]
${AUTH}
delay = 1

[rights]
type = from_file
file = /config/rights

[storage]
filesystem_folder = /data/collections

[web]
type = internal

[logging]
level = ${RADICALE_LOG_LEVEL:-info}
CONF
exec radicale --config "$CFG"
