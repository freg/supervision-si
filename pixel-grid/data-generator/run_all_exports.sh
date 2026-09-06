#!/usr/bin/env bash
# Orchestration des trois exports du calendrier partagé (livraison
# #220, suite de #218-219 -- "reste à faire : automatisation de
# l'export périodique" noté explicitement dans ces livraisons).
# Lance les trois scripts Python (SSH, tickets, GED) puis charge
# chaque CSV résultant -- SQLite OU PostgreSQL selon
# PIXEL_GRID_BACKEND (même variable que celle déjà utilisée dans
# .env.example pour ce module, jamais une nouvelle convention).
#
# Pensé pour être ajouté à UNE tâche cron par la personne -- ce
# script lui-même NE SE PLANIFIE PAS tout seul (jamais introduit de
# dépendance à un ordonnanceur dans ce projet, qui n'en a nulle part
# ailleurs) :
#   */30 * * * * /chemin/vers/supervision-si/pixel-grid/data-generator/run_all_exports.sh >> /var/log/pixel-grid-export.log 2>&1
#
# Usage :
#   ./run_all_exports.sh
#   SSH_TUNNELS_DB=/autre/chemin/ssh-tunnels.db ./run_all_exports.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# Chemins des bases sources -- mêmes valeurs par défaut que
# SSH_TUNNELS_DATA_DIR/TICKETS_DATA_DIR/GED_DATA_DIR dans
# .env.example (./<module>/data), surchargeable individuellement si
# la personne a changé ces emplacements dans son propre .env.
SSH_TUNNELS_DB="${SSH_TUNNELS_DB:-$PROJECT_ROOT/ssh-tunnels/data/ssh-tunnels.db}"
TICKETS_DB="${TICKETS_DB:-$PROJECT_ROOT/tickets/data/tickets.db}"
GED_DB="${GED_DB:-$PROJECT_ROOT/ged/data/ged.db}"

PIXEL_GRID_BACKEND="${PIXEL_GRID_BACKEND:-postgres}"  # même défaut que .env.example
SQLITE_DB_FILE="${SQLITE_DB_FILE:-$SCRIPT_DIR/timeseries.db}"

WORK_DIR="$(mktemp -d)"
trap 'rm -rf "$WORK_DIR"' EXIT

echo "=== Export du calendrier partagé -- $(date -u +%FT%TZ) ==="
echo "Backend pixel-grid : $PIXEL_GRID_BACKEND"

run_one() {
  local label="$1" export_script="$2" source_db="$3" config="$4"
  echo ""
  echo "--- $label ---"
  if [ ! -f "$source_db" ]; then
    echo "⚠️  base introuvable ($source_db) -- source ignorée (pas une erreur bloquante, les deux autres continuent)" >&2
    return 0
  fi
  local csv_file="$WORK_DIR/$label.csv"
  # Vérification EXPLICITE du code de sortie -- `set -e` seul ne
  # suffit PAS ici : cette fonction est appelée via `run_one ... ||
  # true` plus bas (pour qu'un échec n'arrête jamais les DEUX autres
  # sources) -- piège bash RÉEL, trouvé en testant : dès qu'un appel
  # de fonction est suivi de `||`, bash désactive `errexit` pour
  # TOUTE la durée de cet appel, y compris À L'INTÉRIEUR du corps de
  # la fonction -- sans ce `if ! ...`, un export Python en échec
  # laissait quand même le chargeur être appelé juste après, sur un
  # CSV absent ou incomplet.
  if ! python3 "$SCRIPT_DIR/$export_script" "$source_db" "$csv_file"; then
    echo "⚠️  export de '$label' échoué -- chargement ignoré pour cette source, les deux autres continuent" >&2
    return 1
  fi
  if [ "$PIXEL_GRID_BACKEND" = "sqlite" ]; then
    "$SCRIPT_DIR/load_sqlite.sh" "$csv_file" "$SCRIPT_DIR/configs/$config" "$SQLITE_DB_FILE"
  else
    "$SCRIPT_DIR/load_postgres.sh" "$csv_file" "$SCRIPT_DIR/configs/$config"
  fi
}

# Chaque source est INDÉPENDANTE -- l'échec d'une (base absente,
# service jamais déployé...) ne doit jamais empêcher les deux autres
# de s'exécuter -- voir run_one, qui avale une base manquante sans
# arrêter le script (contrairement à `set -e` qui arrêterait tout au
# premier échec sans ce garde-fou explicite).
run_one "ssh" "export_ssh_tunnel_activity.py" "$SSH_TUNNELS_DB" "activite_tunnel_ssh.json" || true
run_one "tickets" "export_ticket_time_entries.py" "$TICKETS_DB" "activite_ticket_temps.json" || true
run_one "ged" "export_document_links.py" "$GED_DB" "activite_document_ged.json" || true

echo ""
echo "=== Terminé -- $(date -u +%FT%TZ) ==="
