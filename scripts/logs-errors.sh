#!/usr/bin/env bash
# Agrégation centralisée des logs d'erreur -- tous les conteneurs de
# la stack, préfixés par leur nom de service ("docker compose logs"
# le fait déjà nativement, rien à construire pour ça), filtrés sur
# les motifs d'erreur usuels. Demandé après une confusion réelle :
# naviguer conteneur par conteneur dans Portainer sans jamais être
# sûr du bon à consulter.
#
# Usage :
#   ./scripts/logs-errors.sh            -- dernières erreurs (500 lignes/service)
#   ./scripts/logs-errors.sh --follow   -- suit en continu
#   ./scripts/logs-errors.sh dba-api    -- limité à un service précis
#   ./scripts/logs-errors.sh --follow vault-api vault-admin-api

set -euo pipefail
cd "$(dirname "$0")/.."

# Motif volontairement large -- mieux vaut un faux positif de temps en
# temps (une ligne contenant "failed" dans un contexte bénin) qu'un
# vrai problème raté. "-i" (insensible à la casse) plutôt que "(?i)"
# inline -- POSIX ERE (grep -E) ne le supporte pas, seul PCRE (-P) le
# ferait, pas systématiquement disponible.
PATTERN='error|exception|traceback|critical|refused|denied|fatal|panic|failed'

if [ "${1:-}" = "--follow" ]; then
  shift
  echo "Suivi en continu (Ctrl+C pour arrêter) -- filtré sur : erreurs, exceptions, refus, échecs..."
  docker compose logs -f --tail=50 "$@" | grep --line-buffered -iE "$PATTERN"
else
  docker compose logs --tail=500 "$@" | grep -iE "$PATTERN" || {
    echo "Aucune ligne correspondant à un motif d'erreur dans les 500 dernières lignes par service."
    exit 0
  }
fi
