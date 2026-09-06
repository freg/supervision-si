#!/usr/bin/env bash
# Génère (ou renouvelle) le certificat SERVEUR utilisé par le proxy TLS
# pour TOUS les ports exposés — UN SEUL certificat suffit, un
# certificat valide un HÔTE (via ses Subject Alternative Names), pas
# un port : pas besoin d'un certificat par service.
#
# SAN dérivés de HOST_IP (.env) — critique : les navigateurs modernes
# ignorent le Common Name pour la validation de nom d'hôte, seuls les
# SAN comptent. Une IP doit être déclarée en "IP Address" SAN, pas en
# "DNS" SAN (openssl fait la distinction automatiquement selon la
# syntaxe -addext utilisée ci-dessous).
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE/../.."

# Lecture minimale de .env (même esprit que keycloak/render.py, sans
# dépendance à docker compose lui-même pour rester utilisable seul).
# Priorité IDENTIQUE au reste du projet : variable d'environnement
# déjà exportée en premier (ex. HOST_IP exporté par scripts/run.sh
# après détection via `hostname -I`, jamais écrit dans .env lui-même),
# puis .env, puis défaut. Un script qui ne lirait QUE .env manquerait
# précisément ce cas — bug réel rencontré en testant ce script depuis
# run.sh, corrigé ici. Définie tout en haut, AVANT tout usage (bug
# réel évité avant livraison : PKI_DIR utilisait cette fonction plus
# bas dans le fichier alors qu'elle n'était définie que plus tard —
# ça aurait planté "command not found" à l'exécution).
get_env() {
  local key="$1" default="$2"
  local value="${!key:-}"
  if [[ -z "$value" ]]; then
    value=$(grep -E "^${key}=" "$ROOT/.env" 2>/dev/null | tail -1 | cut -d= -f2- || true)
    value="${value%\"}"; value="${value#\"}"
    value="${value%\'}"; value="${value#\'}"
  fi
  echo "${value:-$default}"
}

PKI_DIR="$(get_env PKI_DIR "")"

# PKI_DIR (.env, optionnel) : voir generate-ca.sh pour l'explication
# complète (même garde-fou anti-"~", même raison d'être).
if [[ -n "$PKI_DIR" ]]; then
  case "$PKI_DIR" in
    "~"*)
      echo "ERREUR : PKI_DIR='$PKI_DIR' commence par '~' — non supporté : ni bash ni docker-compose ne l'étendent automatiquement. Utiliser un chemin absolu explicite, ex. /home/<utilisateur>/... plutôt que ~/..." >&2
      exit 1
      ;;
  esac
  CA_DIR="$PKI_DIR/ca"
  SERVER_DIR="$PKI_DIR/server"
else
  CA_DIR="$HERE/../ca"
  SERVER_DIR="$HERE/../server"
fi

DAYS="$(get_env SERVER_CERT_VALIDITY_DAYS 825)"  # ~27 mois -- plus long que la limite imposée par les navigateurs publics (398j, propre aux CA publiques) puisqu'on gère notre propre confiance, mais pas 10 ans non plus (bonne pratique : renouveler périodiquement)

if [[ ! -f "$CA_DIR/ca.crt" || ! -f "$CA_DIR/ca.key" ]]; then
  echo "ERREUR : CA absente ($CA_DIR) — lancer generate-ca.sh d'abord." >&2
  exit 1
fi

HOST_IP="$(get_env HOST_IP "")"
EXTRA_SAN="$(get_env TLS_EXTRA_SAN "")"  # ex. "DNS:supervision.interne.local,DNS:super"

mkdir -p "$SERVER_DIR"
chmod 700 "$SERVER_DIR"

# Construction de la liste SAN : toujours localhost/127.0.0.1 (utile
# en test via tunnel SSH, voir hub/README.md), + HOST_IP si renseignée
# (obligatoire en usage réel : c'est l'adresse que les postes clients
# tapent réellement), + toute entrée additionnelle fournie.
#
# HOST_IP n'est pas toujours une IP littérale malgré son nom — bug réel
# rencontré en conditions réelles : HOST_IP=localhost (recommandé ici
# même pour tester via tunnel SSH) fait planter openssl si traité comme
# "IP:localhost" ("bad ip address"), "localhost" étant un NOM, pas une
# adresse. Distinction faite ci-dessous plutôt que de supposer.
is_ipv4() {
  [[ "$1" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]]
}

SAN_ENTRIES=("DNS:localhost" "IP:127.0.0.1")
if [[ -n "$HOST_IP" ]]; then
  if is_ipv4 "$HOST_IP"; then
    SAN_ENTRIES+=("IP:$HOST_IP")
  elif [[ "$HOST_IP" != "localhost" ]]; then
    # Un nom (pas "localhost", déjà dans la liste de base) -> DNS, pas IP.
    SAN_ENTRIES+=("DNS:$HOST_IP")
  fi
else
  echo "⚠️  HOST_IP absent de .env — le certificat ne couvrira que localhost/127.0.0.1." >&2
  echo "    Sans HOST_IP renseigné, un accès par IP LAN échouera la validation TLS." >&2
fi
if [[ -n "$EXTRA_SAN" ]]; then
  IFS=',' read -ra EXTRA_ARR <<< "$EXTRA_SAN"
  SAN_ENTRIES+=("${EXTRA_ARR[@]}")
fi
SAN_LIST=$(IFS=,; echo "${SAN_ENTRIES[*]}")

echo "SAN du certificat serveur : $SAN_LIST"

# Fichier temporaire classique plutôt qu'une substitution de processus
# <(...) -- bug réel rencontré en conditions réelles : <(...) est une
# syntaxe bash, absente de sh/dash (l'implémentation par défaut de
# /bin/sh sur Debian/Ubuntu) ; selon la façon exacte dont ce script
# finit par être invoqué dans une chaîne d'appel (sudo, etc.), il peut
# se retrouver interprété par sh et échouer avec une erreur de syntaxe
# obscure ("Syntax error: ( unexpected") plutôt que par bash comme son
# shebang le prévoit. Un fichier temporaire fonctionne à l'identique
# sous n'importe quel shell.
EXTFILE="$(mktemp)"
trap 'rm -f "$EXTFILE"' EXIT
printf "subjectAltName=%s\nbasicConstraints=CA:FALSE\nkeyUsage=digitalSignature,keyEncipherment\nextendedKeyUsage=serverAuth" "$SAN_LIST" > "$EXTFILE"

# Sortie d'openssl JAMAIS masquée (>/dev/null 2>&1 retiré, présent par
# erreur avant) : un openssl qui échoue doit échouer bruyamment, pas
# silencieusement avec juste un ❌ ARRÊT générique côté run.sh sans
# indice sur la cause réelle -- même bug de masquage que celui trouvé
# et corrigé ici.
openssl req -new -nodes \
  -newkey rsa:2048 \
  -keyout "$SERVER_DIR/server.key" \
  -out "$SERVER_DIR/server.csr" \
  -subj "/O=Supervision SI/CN=supervision-si-proxy"

openssl x509 -req \
  -in "$SERVER_DIR/server.csr" \
  -CA "$CA_DIR/ca.crt" -CAkey "$CA_DIR/ca.key" -CAcreateserial \
  -out "$SERVER_DIR/server.crt" \
  -days "$DAYS" -sha256 \
  -extfile "$EXTFILE"

rm -f "$SERVER_DIR/server.csr"
chmod 600 "$SERVER_DIR/server.key"
chmod 644 "$SERVER_DIR/server.crt"

echo "Certificat serveur généré :"
echo "  $SERVER_DIR/server.crt"
echo "  $SERVER_DIR/server.key  (SECRET — ne jamais versionner)"
# Affichage des dates SEULEMENT (jamais "-ext subjectAltName" ici,
# déjà affiché plus haut via $SAN_LIST, la source de vérité réelle
# puisque c'est exactement ce qui a été demandé à openssl, pas une
# relecture du certificat généré) -- bug réel macOS rencontré :
# "-ext" n'existe pas sur LibreSSL (openssl système par défaut sur
# macOS, contrairement à OpenSSL sur Linux), faisait échouer TOUT le
# script avec "unknown option -ext" malgré une génération de
# certificat déjà réussie juste avant. "|| true" en plus, par
# précaution -- cette ligne reste purement informative, jamais une
# raison d'arrêter le déploiement si UNE AUTRE variante d'openssl
# venait à ne pas supporter non plus cette syntaxe précise.
openssl x509 -in "$SERVER_DIR/server.crt" -noout -dates || true
