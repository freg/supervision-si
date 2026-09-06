#!/usr/bin/env bash
# Charge un CSV généré par generate_csv.sh dans une base SQLite.
# Usage : ./load_sqlite.sh <csv> <config.json> <db_file>

set -euo pipefail

CSV_FILE="${1:?Usage: $0 <csv> <config.json> <db_file>}"
CONFIG_FILE="${2:?Usage: $0 <csv> <config.json> <db_file>}"
DB_FILE="${3:-timeseries.db}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

for cmd in jq sqlite3; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Dépendance manquante : $cmd" >&2; exit 1; }
done

TYPE=$(jq -r '.type' "$CONFIG_FILE")
KIND=$(jq -r '.kind' "$CONFIG_FILE")

sqlite3 "$DB_FILE" < "$SCRIPT_DIR/schema.sql"

echo "Import dans ${DB_FILE} (SQLite)..." >&2

sqlite3 "$DB_FILE" <<SQL
DROP TABLE IF EXISTS _staging_import;
CREATE TABLE _staging_import (ts INTEGER, valeur REAL, nom TEXT, type TEXT, data TEXT);
.mode csv
.import ${CSV_FILE} _staging_import
INSERT INTO events (ts, valeur, nom, type, data) SELECT ts, valeur, nom, type, data FROM _staging_import;
DROP TABLE _staging_import;
SQL

CONFIG_JSON_ESCAPED=$(jq -c '.' "$CONFIG_FILE" | sed "s/'/''/g")
sqlite3 "$DB_FILE" "INSERT OR REPLACE INTO type_meta (type, kind, config_json) VALUES ('${TYPE}', '${KIND}', '${CONFIG_JSON_ESCAPED}');"

COUNT=$(sqlite3 "$DB_FILE" "SELECT COUNT(*) FROM events WHERE type = '${TYPE}';")
echo "Terminé — ${COUNT} lignes en base (SQLite) pour le type '${TYPE}'." >&2

# Détection automatique des nouveaux lieux "Localisation" — n'échoue pas
# le chargement si le scan a un souci (best-effort).
python3 "$SCRIPT_DIR/scan_geolocations.py" --backend sqlite --db-file "$DB_FILE" --type "$TYPE" || \
  echo "Avertissement : le scan de géolocalisation a échoué (chargement des données non affecté)." >&2
