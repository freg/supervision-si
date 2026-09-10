#!/usr/bin/env bash
# Restauration sur un AUTRE host (livraison #458) : dépose tout dans un
# dossier cible sans rien démarrer, puis regenerate-host.sh.
#   ./restore-full.sh <archive.tar.gz[.enc]> --into /home/alice/supervision-si [--passphrase-file F] [--no-docker] [--force] [--absolute] [--project-name NOM]
# Ce script peut être lancé depuis N'IMPORTE OÙ (copié seul avec l'archive) :
# il n'a besoin que de python3, git, openssl et (facultatif) docker.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$HERE/full_backup.py"
if [ ! -f "$PY" ]; then
  # script copié seul : extraire full_backup.py du bundle git de l'archive n'est pas possible avant
  # déchiffrement -- on exige le dépôt (ou le script) à côté.
  echo "full_backup.py introuvable à côté de ce script -- copier scripts/full_backup.py avec restore-full.sh" >&2; exit 2
fi
exec python3 "$PY" restore "$@"
