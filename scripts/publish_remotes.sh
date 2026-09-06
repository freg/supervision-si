#!/usr/bin/env bash
# Pousse le dépôt vers GitHub et/ou Framagit (un seul historique, deux
# remotes — évite deux dépôts qui divergent).
#
# 1. Créer un dépôt VIDE (sans README ni licence auto-générés) sur
#    chaque plateforme, puis :
#
#   GITHUB_REMOTE=git@github.com:<compte>/supervision-si.git \
#   FRAMAGIT_REMOTE=git@framagit.org:<compte>/supervision-si.git \
#   ./scripts/publish_remotes.sh
#
# (HTTPS marche aussi : https://github.com/<compte>/supervision-si.git)
# Relançable sans risque : les remotes existantes sont juste mises à jour.

set -euo pipefail
cd "$(dirname "$0")/.."

if [ -z "${GITHUB_REMOTE:-}" ] && [ -z "${FRAMAGIT_REMOTE:-}" ]; then
  echo "Définis GITHUB_REMOTE et/ou FRAMAGIT_REMOTE (voir l'en-tête de ce script)." >&2
  exit 1
fi

branch="$(git rev-parse --abbrev-ref HEAD)"

setup_and_push() {
  local name="$1" url="$2"
  if git remote get-url "$name" >/dev/null 2>&1; then
    git remote set-url "$name" "$url"
  else
    git remote add "$name" "$url"
  fi
  echo "→ push vers $name ($url)"
  git push -u "$name" "$branch"
}

[ -n "${GITHUB_REMOTE:-}" ] && setup_and_push github "$GITHUB_REMOTE"
[ -n "${FRAMAGIT_REMOTE:-}" ] && setup_and_push framagit "$FRAMAGIT_REMOTE"

echo "Terminé. Pour les pushes suivants : git push github $branch && git push framagit $branch"
