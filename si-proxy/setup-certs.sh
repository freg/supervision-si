#!/bin/bash
# Émet le certificat serveur du relais si-proxy (#452), signé par la CA
# interne du projet (pki/ca), et — si demandé — les certificats CLIENTS
# (freg, host) pour le TLS mutuel. À lancer sur la VM du hub, à la racine du
# dépôt déployé.
#
#   ./si-proxy/setup-certs.sh <nom_ou_ip_du_hub> [--clients]
#
# Résultat dans si-proxy/certs/ : relay.crt/relay.key (montés dans le
# conteneur relais), ca.crt (copie de la CA, pour les clients), et avec
# --clients : freg.crt/freg.key (Mac) et host.crt/host.key (shim).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/.." && pwd)"
HUB="${1:?usage: setup-certs.sh <nom_ou_ip_du_hub> [--clients]}"
CLIENTS="${2:-}"
CA_DIR="${PKI_DIR:-$REPO/pki}/ca"
CRT="$CA_DIR/ca.crt"; KEY="$CA_DIR/ca.key"
[ -f "$CRT" ] && [ -f "$KEY" ] || { echo "CA introuvable ($CRT / $KEY) -- initialiser la PKI d'abord" >&2; exit 1; }
OUT="$HERE/certs"; mkdir -p "$OUT"; cp "$CRT" "$OUT/ca.crt"
gen() { # gen <nom> <CN> <SAN?>
  local name="$1" cn="$2" san="${3:-}"
  openssl req -newkey rsa:2048 -nodes -keyout "$OUT/$name.key" -out "$OUT/$name.csr" -subj "/CN=$cn" 2>/dev/null
  if [ -n "$san" ]; then printf "subjectAltName=%s\n" "$san" > "$OUT/$name.ext"; EXT="-extfile $OUT/$name.ext"; else EXT=""; fi
  openssl x509 -req -in "$OUT/$name.csr" -CA "$CRT" -CAkey "$KEY" -CAcreateserial -out "$OUT/$name.crt" -days 825 $EXT 2>/dev/null
  rm -f "$OUT/$name.csr" "$OUT/$name.ext"
  chmod 600 "$OUT/$name.key"
}
# SAN : IP si $HUB est une IP, sinon DNS
# + DNS:si-proxy (#454) : nom Docker du relais, pour que si-proxy-admin-api
# vérifie le certificat de l'interface de contrôle (https://si-proxy:6452).
if printf '%s' "$HUB" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then SAN="IP:$HUB,DNS:si-proxy"; else SAN="DNS:$HUB,DNS:si-proxy"; fi
gen relay "$HUB" "$SAN"
echo "cert serveur du relais émis pour $HUB (si-proxy/certs/relay.crt)"
if [ "$CLIENTS" = "--clients" ]; then
  gen freg freg ""
  gen host si-proxy-host ""
  echo "certs clients émis : freg.crt (Mac) et host.crt (shim) -- pour le TLS mutuel (SI_PROXY_MTLS=1)"
fi
echo "jetons suggérés (à mettre dans .env / host.env) :"
echo "  SI_PROXY_HOST_TOKEN=$(openssl rand -hex 24)"
echo "  SI_PROXY_CLIENT_TOKEN=$(openssl rand -hex 24)"
echo "  SI_PROXY_ADMIN_TOKEN=$(openssl rand -hex 24)   # interface de contrôle (#453)"
mkdir -p "$(dirname "$0")/data"
