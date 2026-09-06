#!/usr/bin/env bash
# Orchestrateur : génère le CSV puis le charge dans le backend choisi.
#
# Usage :
#   ./generate.sh configs/etat_example.json sqlite timeseries.db
#   ./generate.sh configs/etat_example.json postgres
#
# Pour le detail des dépendances et variables d'environnement de chaque
# backend, voir generate_csv.sh, load_sqlite.sh et load_postgres.sh.

set -euo pipefail

CONFIG_FILE="${1:?Usage: $0 <config.json> <sqlite|postgres> [db_file (sqlite uniquement)]}"
BACKEND="${2:?Usage: $0 <config.json> <sqlite|postgres> [db_file (sqlite uniquement)]}"
DB_FILE="${3:-timeseries.db}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CSV_FILE=$(mktemp --suffix=.csv)
trap 'rm -f "$CSV_FILE"' EXIT

"$SCRIPT_DIR/generate_csv.sh" "$CONFIG_FILE" "$CSV_FILE"

case "$BACKEND" in
  sqlite)
    "$SCRIPT_DIR/load_sqlite.sh" "$CSV_FILE" "$CONFIG_FILE" "$DB_FILE"
    ;;
  postgres)
    "$SCRIPT_DIR/load_postgres.sh" "$CSV_FILE" "$CONFIG_FILE"
    ;;
  *)
    echo "Backend inconnu : '$BACKEND' (attendu: sqlite ou postgres)" >&2
    exit 1
    ;;
esac
