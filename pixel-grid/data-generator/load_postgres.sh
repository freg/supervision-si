#!/usr/bin/env bash
# Charge un CSV généré par generate_csv.sh dans PostgreSQL.
# Usage : ./load_postgres.sh <csv> <config.json>
#
# Connexion via les variables d'environnement standard psql :
#   PGHOST (défaut: localhost)  PGPORT (défaut: 6543 — pas 5432,
#   volontairement décalé pour ne pas entrer en conflit avec un
#   PostgreSQL déjà installé sur la machine hôte)
#   PGUSER (défaut: pixelgrid)  PGPASSWORD (défaut: pixelgrid)
#   PGDATABASE (défaut: pixelgrid)
#
# Le schéma (schema.postgres.sql) est appliqué automatiquement par
# l'image Docker au premier démarrage du conteneur pixel-grid-postgres
# (mécanisme /docker-entrypoint-initdb.d/) — ce script ne le réapplique
# pas, il suppose la table déjà créée.

set -euo pipefail

CSV_FILE="${1:?Usage: $0 <csv> <config.json>}"
CONFIG_FILE="${2:?Usage: $0 <csv> <config.json>}"

export PGHOST="${PGHOST:-localhost}"
export PGPORT="${PGPORT:-6543}"
export PGUSER="${PGUSER:-pixelgrid}"
export PGPASSWORD="${PGPASSWORD:-pixelgrid}"
export PGDATABASE="${PGDATABASE:-pixelgrid}"

for cmd in jq psql; do
  command -v "$cmd" >/dev/null 2>&1 || { echo "Dépendance manquante : $cmd" >&2; exit 1; }
done

TYPE=$(jq -r '.type' "$CONFIG_FILE")
KIND=$(jq -r '.kind' "$CONFIG_FILE")

echo "Import dans PostgreSQL (${PGHOST}:${PGPORT}/${PGDATABASE})..." >&2

# Table de passage, comme pour SQLite : évite tout souci d'alignement de
# colonnes avec la colonne id (BIGSERIAL) absente du CSV.
psql -v ON_ERROR_STOP=1 -c "
  DROP TABLE IF EXISTS _staging_import;
  CREATE TABLE _staging_import (ts BIGINT, valeur DOUBLE PRECISION, nom TEXT, type TEXT, data TEXT);
"

psql -v ON_ERROR_STOP=1 -c "\\copy _staging_import (ts, valeur, nom, type, data) FROM '${CSV_FILE}' WITH (FORMAT csv)"

psql -v ON_ERROR_STOP=1 -c "
  INSERT INTO events (ts, valeur, nom, type, data)
  SELECT ts, valeur, nom, type, data FROM _staging_import;
  DROP TABLE _staging_import;
"

CONFIG_JSON_ESCAPED=$(jq -c '.' "$CONFIG_FILE" | sed "s/'/''/g")
psql -v ON_ERROR_STOP=1 -c "
  INSERT INTO type_meta (type, kind, config_json) VALUES ('${TYPE}', '${KIND}', '${CONFIG_JSON_ESCAPED}')
  ON CONFLICT (type) DO UPDATE SET kind = EXCLUDED.kind, config_json = EXCLUDED.config_json;
"

COUNT=$(psql -t -A -c "SELECT COUNT(*) FROM events WHERE type = '${TYPE}';")
echo "Terminé — ${COUNT} lignes en base (PostgreSQL) pour le type '${TYPE}'." >&2

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "$SCRIPT_DIR/scan_geolocations.py" --backend postgres --type "$TYPE" || \
  echo "Avertissement : le scan de géolocalisation a échoué (chargement des données non affecté)." >&2
