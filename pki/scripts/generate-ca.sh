#!/usr/bin/env bash
# Génère l'autorité de certification interne (une fois) — jamais
# régénérée si elle existe déjà, car la redéployer signifierait
# réinstaller le certificat racine sur TOUS les postes clients qui
# l'auraient déjà accepté. Effacer pki/ca/ à la main si un vrai
# renouvellement est un jour nécessaire.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$HERE/../.."

# Lecture .env identique à generate-server-cert.sh -- BUG RÉEL ÉVITÉ
# ICI, avant livraison : ce script ne vérifiait que la variable
# d'environnement déjà exportée, jamais .env lui-même. scripts/run.sh
# n'exporte que HOST_IP globalement, rien d'autre -- PKI_DIR renseigné
# UNIQUEMENT dans .env (le cas d'usage normal, sans l'exporter à la
# main) aurait donc été silencieusement ignoré. Repéré en relisant
# avant de livrer, pas en conditions réelles cette fois.
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

# PKI_DIR (.env, optionnel) : sort tout pki/ (ca/ + server/) de
# l'arborescence du projet -- même logique que KEYCLOAK_IMPORT_DIR/
# KEYCLOAK_BACKUP_DIR/TICKETS_DATA_DIR. Bug réel confirmé sur
# tickets.db, même mécanisme ici : un déploiement qui supprime puis
# réextrait le projet à chaque livraison régénère une CA neuve à
# chaque fois -- même nom d'émetteur (toujours "Supervision SI
# Internal CA"), même numéro de série de départ (le fichier .srl ne
# survit pas non plus) -- collision garantie côté navigateur si une
# CA plus ancienne y traîne encore (SEC_ERROR_REUSED_ISSUER_AND_SERIAL,
# rencontré en conditions réelles). "~" REFUSÉ explicitement (ni bash
# ni docker-compose ne l'étendent) -- chemin absolu explicite requis.
if [[ -n "$PKI_DIR" ]]; then
  case "$PKI_DIR" in
    "~"*)
      echo "ERREUR : PKI_DIR='$PKI_DIR' commence par '~' — non supporté : ni bash ni docker-compose ne l'étendent automatiquement. Utiliser un chemin absolu explicite, ex. /home/<utilisateur>/... plutôt que ~/..." >&2
      exit 1
      ;;
  esac
  CA_DIR="$PKI_DIR/ca"
else
  CA_DIR="$HERE/../ca"
fi

DAYS="$(get_env CA_VALIDITY_DAYS 3650)"  # 10 ans par défaut -- un root CA se renouvelle rarement

if [[ -f "$CA_DIR/ca.crt" && -f "$CA_DIR/ca.key" ]]; then
  echo "CA déjà présente dans $CA_DIR — rien fait (supprimer ce dossier à la main pour en régénérer une)."
  exit 0
fi

mkdir -p "$CA_DIR"
chmod 700 "$CA_DIR"

openssl req -x509 -new -nodes \
  -newkey rsa:4096 \
  -sha256 \
  -days "$DAYS" \
  -keyout "$CA_DIR/ca.key" \
  -out "$CA_DIR/ca.crt" \
  -subj "/O=Supervision SI/CN=Supervision SI Internal CA"

chmod 600 "$CA_DIR/ca.key"
chmod 644 "$CA_DIR/ca.crt"

echo "CA générée :"
echo "  $CA_DIR/ca.crt  (à distribuer sur les postes clients — voir pki/README.md)"
echo "  $CA_DIR/ca.key  (SECRET — ne jamais distribuer, ne jamais versionner)"
openssl x509 -in "$CA_DIR/ca.crt" -noout -subject -dates
