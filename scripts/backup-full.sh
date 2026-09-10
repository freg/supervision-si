#!/usr/bin/env bash
# Sauvegarde TOTALE du hub (livraison #458) -- dépôt, .env, PKI, données,
# volumes Docker, dumps SQL, côté host -- archive chiffrée AES-256.
#   ./scripts/backup-full.sh [--out DIR] [--passphrase-file F] [--no-encrypt] [--no-docker] [--no-sql]
#   ./scripts/backup-full.sh inventory      # ce qui serait sauvegardé, sans rien écrire
# Sans --passphrase-file ni SI_BACKUP_PASSPHRASE, la phrase est demandée.
# À lancer en sudo si le shim si-proxy (/etc/si-proxy) doit être inclus.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ "${1:-}" = "inventory" ]; then exec python3 "$HERE/full_backup.py" inventory; fi
exec python3 "$HERE/full_backup.py" backup "$@"
