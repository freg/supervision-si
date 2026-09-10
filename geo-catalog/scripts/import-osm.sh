#!/bin/bash
# Import d'un extrait OpenStreetMap (Geofabrik, .osm.pbf) dans la base du
# catalogue de positions avec osm2pgsql (livraison #429).
#
#   ./geo-catalog/scripts/import-osm.sh <fichier.osm.pbf | URL Geofabrik> [--db URL]
#
# Exemples :
#   ./geo-catalog/scripts/import-osm.sh https://download.geofabrik.de/europe/france/poitou-charentes-latest.osm.pbf
#   ./geo-catalog/scripts/import-osm.sh ./france-latest.osm.pbf --db postgresql://geocat:geocat@hote-secondaire:5432/geocat
#
# VOLUME : une région française = 1 à 5 Go en base ; la France entière =
# plusieurs dizaines de Go et des heures d'import -- d'où la base DÉDIÉE
# (geo-catalog-postgres), déplaçable sur un hôte secondaire (README).
# Choisir l'extrait le plus petit qui couvre le parc (région, département).
#
# osm2pgsql tourne dans un conteneur jetable (image officielle) et écrit
# dans la base via le réseau du projet ; sans Docker, installer osm2pgsql
# (apt install osm2pgsql) et lancer la commande finale à la main.
# Tables produites : planet_osm_point / _line / _polygon (avec `name`),
# que geo-catalog-api interroge par pg_trgm (refs.osm_refs). Relancer =
# ré-import complet (osm2pgsql --create), pas de mise à jour incrémentale.
set -euo pipefail
SRC="${1:-}"
[ -n "$SRC" ] || { echo "usage : $0 <fichier.osm.pbf | URL> [--db postgresql://...]" >&2; exit 2; }
shift
DB_URL="${GEO_CATALOG_DB_URL:-}"
while [ $# -gt 0 ]; do case "$1" in --db) DB_URL="$2"; shift 2;; *) echo "argument inconnu : $1" >&2; exit 2;; esac; done
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" && set +a
DB_URL="${DB_URL:-postgresql://${GEO_CATALOG_DB_USER:-geocat}:${GEO_CATALOG_DB_PASSWORD:-geocat}@geo-catalog-postgres:5432/${GEO_CATALOG_DB_NAME:-geocat}}"
NET="${SUPERVISION_SI_NETWORK_NAME:-supervision-si-net}"
WORK="$(mktemp -d)"
case "$SRC" in
  http://*|https://*) echo "téléchargement de $SRC…"; curl -fL --progress-bar -o "$WORK/extract.osm.pbf" "$SRC"; FILE="$WORK/extract.osm.pbf";;
  *) FILE="$(cd "$(dirname "$SRC")" && pwd)/$(basename "$SRC")";;
esac
[ -f "$FILE" ] || { echo "fichier introuvable : $FILE" >&2; exit 1; }
echo "import de $(du -h "$FILE" | cut -f1) vers ${DB_URL%%@*}@… (cache 2 Go, style par défaut)"
docker run --rm --network "$NET" -v "$(dirname "$FILE"):/data:ro" iboates/osm2pgsql:latest \
  osm2pgsql --create --slim --drop --cache 2000 --number-processes 2 \
  --database "$DB_URL" "/data/$(basename "$FILE")"
rm -rf "$WORK"
echo "terminé : tables planet_osm_* dans la base -- GET /status de geo-catalog-api doit lister osm_tables"
