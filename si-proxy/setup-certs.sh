#!/bin/bash
# Émet le certificat serveur du relais si-proxy (#452), signé par la CA
# interne du projet (pki/ca), et — si demandé — les certificats CLIENTS
# (freg, host) pour le TLS mutuel. À lancer sur la VM du hub, à la racine du
# dépôt déployé.
#
#   ./si-proxy/setup-certs.sh <nom_ou_ip_du_hub> [--clients]
#
# Résultat dans si-proxy/certs/ : ca.crt/ca.key (CA propre au bastion, #582),
# relay.crt/relay.key (montés dans le conteneur relais), et avec
# --clients : freg.crt/freg.key (Mac) et host.crt/host.key (shim).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"; REPO="$(cd "$HERE/.." && pwd)"
HUB="${1:?usage: setup-certs.sh <nom_ou_ip_du_hub> [--clients] [--san <nom_ou_ip>]... [--new-ca]}"
shift
# #469 : plusieurs noms/IP dans le certificat (LAN + nom public / DynDNS + IP
# publique) pour joindre le même relais depuis le LAN et depuis l'extérieur.
CLIENTS=""; EXTRA_SAN=""
while [ $# -gt 0 ]; do case "$1" in
  --clients) CLIENTS="--clients"; shift;;
  --new-ca) NEW_CA=1; shift;;
  --san) EXTRA_SAN="$EXTRA_SAN,$(printf '%s' "$2" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' && echo "IP:$2" || echo "DNS:$2")"; shift 2;;
  *) echo "argument inconnu : $1" >&2; exit 2;; esac; done
# PKI_DIR peut avoir été déplacée par .env (ex. hors du dépôt) : si la variable
# n'est pas exportée dans le shell, on la lit dans .env (#468).
# (PKI_DIR n'est plus utilisée : le bastion a sa propre CA depuis #582)
# #582 : CA PROPRE au bastion (si-proxy/certs/ca.crt + ca.key), avec les
# extensions qu'OpenSSL ≥ 3 exige (basicConstraints CA, keyUsage
# keyCertSign) -- la CA générale du projet en manquait (#495) et le shim
# d'un poste récent refusait le relais (« CA cert does not include key usage
# extension »). Indépendante de la CA des agents : la faire tourner ne
# touche que le relais, les shims et les clients Mac. Réutilisée si déjà là ;
# --new-ca pour la remplacer.
OUT="$HERE/certs"; mkdir -p "$OUT"
CRT="$OUT/ca.crt"; KEY="$OUT/ca.key"
if [ -n "${NEW_CA:-}" ] || [ ! -f "$KEY" ] || ! openssl x509 -in "$CRT" -noout -text 2>/dev/null | grep -q "Certificate Sign"; then
  [ -f "$KEY" ] && echo "CA du bastion sans extensions (ou --new-ca) : remplacée -- recopier ca.crt sur les shims et les clients" >&2
  printf "[req]\ndistinguished_name=dn\nx509_extensions=ca\nprompt=no\n[dn]\nCN=si-proxy CA\n[ca]\nbasicConstraints=critical,CA:TRUE,pathlen:0\nkeyUsage=critical,keyCertSign,cRLSign\nsubjectKeyIdentifier=hash\n" > "$OUT/ca.cnf"
  openssl req -x509 -newkey rsa:3072 -nodes -keyout "$KEY" -out "$CRT" -days 3650 -config "$OUT/ca.cnf" 2>/dev/null
  rm -f "$OUT/ca.cnf" "$OUT/ca.srl"; chmod 600 "$KEY"
  echo "CA du bastion créée : $CRT (empreinte $(openssl x509 -in "$CRT" -noout -fingerprint -sha256 | cut -d= -f2))"
fi
gen() { # gen <nom> <CN> <SAN?> <usage : server|client>
  local name="$1" cn="$2" san="${3:-}" usage="${4:-server}"
  openssl req -newkey rsa:2048 -nodes -keyout "$OUT/$name.key" -out "$OUT/$name.csr" -subj "/CN=$cn" 2>/dev/null
  { printf "basicConstraints=CA:FALSE\nkeyUsage=critical,digitalSignature,keyEncipherment\n"
    if [ "$usage" = "client" ]; then printf "extendedKeyUsage=clientAuth\n"; else printf "extendedKeyUsage=serverAuth\n"; fi
    [ -n "$san" ] && printf "subjectAltName=%s\n" "$san"; } > "$OUT/$name.ext"
  openssl x509 -req -in "$OUT/$name.csr" -CA "$CRT" -CAkey "$KEY" -CAcreateserial -out "$OUT/$name.crt" -days 825 -extfile "$OUT/$name.ext" 2>/dev/null
  rm -f "$OUT/$name.csr" "$OUT/$name.ext"
  chmod 600 "$OUT/$name.key"
}
# SAN : IP si $HUB est une IP, sinon DNS
# + DNS:si-proxy (#454) : nom Docker du relais, pour que si-proxy-admin-api
# vérifie le certificat de l'interface de contrôle (https://si-proxy:6452).
if printf '%s' "$HUB" | grep -Eq '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$'; then SAN="IP:$HUB,DNS:si-proxy"; else SAN="DNS:$HUB,DNS:si-proxy"; fi
SAN="$SAN$EXTRA_SAN"
gen relay "$HUB" "$SAN"
echo "cert serveur du relais émis pour $HUB (si-proxy/certs/relay.crt) -- SAN : $SAN"
if [ "$CLIENTS" = "--clients" ]; then
  gen freg freg "" client
  gen host si-proxy-host "" client
  echo "certs clients émis : freg.crt (Mac) et host.crt (shim) -- pour le TLS mutuel (SI_PROXY_MTLS=1)"
fi
echo "jetons suggérés (à mettre dans .env / host.env) :"
echo "  SI_PROXY_HOST_TOKEN=$(openssl rand -hex 24)"
echo "  SI_PROXY_CLIENT_TOKEN=$(openssl rand -hex 24)"
echo "  SI_PROXY_ADMIN_TOKEN=$(openssl rand -hex 24)   # interface de contrôle (#453)"
mkdir -p "$(dirname "$0")/data"
