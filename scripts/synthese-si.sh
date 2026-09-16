#!/usr/bin/env bash
# Infos synthèse SI (livraison #523) : régénère synthese/generated/synthese.json
# depuis les exports déposés dans synthese/data/ (hors dépôt). À planifier :
#   crontab -e  ->  15 6 * * *  /chemin/supervision-si/scripts/synthese-si.sh >> /var/log/synthese-si.log 2>&1
# Le hub (prefs-api /synthese) lit le fichier tel quel : aucun service à redémarrer.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DATA="${1:-$ROOT/synthese/data}"
[ -d "$DATA" ] || { echo "dossier absent : $DATA -- y déposer l'export xlsx (feuilles : zones DNS, IP OVH, services OVH, sous-réseaux et équipements IPAM) ou des .csv/.txt, voir synthese/README.md" >&2; exit 2; }
python3 -c "import openpyxl" 2>/dev/null || echo "note : openpyxl absent (pip install openpyxl) -- seuls les .csv/.txt seront lus" >&2
exec python3 "$ROOT/synthese/generate.py" --data "$DATA"
