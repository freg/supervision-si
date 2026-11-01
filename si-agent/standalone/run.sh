#!/usr/bin/env bash
# Agents hôtes en mode autonome (livraison #517).
#   si-agent/standalone/run.sh up|down|ps|logs|restart …   pile autonome (VM légère)
#   si-agent/standalone/run.sh edge up|down|ps|logs …      aiguillage TLS sur super
# Lit le .env de la RACINE du dépôt (clé par clé : non sourçable) ; génère
# generated/htpasswd depuis SI_STANDALONE_USER / SI_STANDALONE_PASSWORD
# (mot de passe jamais affiché ni journalisé).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd); ROOT=$(cd "$HERE/../.." && pwd)
load_env() {
  local k v
  while IFS= read -r line; do
    k=${line%%=*}; v=${line#*=}
    [[ $k =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    v=${v%\"}; v=${v#\"}; v=${v%\'}; v=${v#\'}
    export "$k=$v"
  done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${1:-$ROOT/.env}" 2>/dev/null || true)
}
[ -f "$ROOT/.env" ] || { echo ".env absent à la racine ($ROOT) -- copier celui de super" >&2; exit 1; }
load_env "$ROOT/.env"
[ -n "${HOST_IP:-}" ] || { echo "HOST_IP absent du .env : c'est l'adresse de super, telle que les agents la joignent" >&2; exit 1; }
# chemins relatifs du .env (./pki, ./si-agent/data) : relatifs à la RACINE, pas à ce dossier
for var in PKI_DIR SI_AGENT_DATA_DIR; do
  v=${!var:-}; case "$v" in ""|/*) ;; *) export "$var=$ROOT/${v#./}" ;; esac
done

if [ "${1:-}" = "edge" ]; then
  shift
  [ -n "${SI_STANDALONE_UPSTREAM:-}" ] || { echo "SI_STANDALONE_UPSTREAM (ip:port du front autonome, ex. 192.0.2.20:6480) manquant dans .env" >&2; exit 1; }
  if docker ps --format '{{.Names}}' | grep -q '^supervision-si-gateway-tls-proxy'; then
    echo "tls-proxy du hub en marche sur le port ${GATEWAY_PORT:-6443} : arrêter d'abord  ./gateway/scripts/run.sh down" >&2; exit 1
  fi
  exec docker compose -p si-agent-edge --project-directory "$HERE/edge" -f "$HERE/edge/docker-compose.yml" "$@"
fi

mkdir -p "$HERE/generated"
if [ "${1:-}" = "up" ] || [ ! -s "$HERE/generated/htpasswd" ]; then
  user=${SI_STANDALONE_USER:-admin}; pwd=${SI_STANDALONE_PASSWORD:-}
  if [ -z "$pwd" ]; then
    echo "SI_STANDALONE_PASSWORD vide dans .env : identifiant local requis (auth basique du front)" >&2; exit 1
  fi
  hash=$(printf '%s' "$pwd" | openssl passwd -apr1 -stdin)
  printf '%s:%s\n' "$user" "$hash" > "$HERE/generated/htpasswd"; chmod 600 "$HERE/generated/htpasswd"
  echo "identifiant local : $user (mot de passe : .env, SI_STANDALONE_PASSWORD)"
fi
exec docker compose -p si-agent-standalone --project-directory "$HERE" -f "$HERE/docker-compose.yml" "$@"
