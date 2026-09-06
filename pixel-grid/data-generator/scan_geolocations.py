"""
Scan de géolocalisation en autonome (sans passer par l'API HTTP) —
détecte les chemins "Localisation" jamais vus dans les données d'un
type et les ajoute comme entrées en attente (coordonnées NULL).

Appelé automatiquement par load_sqlite.sh / load_postgres.sh après
chargement, mais peut aussi être relancé seul en cas de besoin.

Usage :
    python3 scan_geolocations.py --backend sqlite --db-file timeseries.db --type alerte_zenoss_email
    python3 scan_geolocations.py --backend postgres --type alerte_zenoss_email
    (backend postgres : utilise les variables d'environnement PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE)
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone


def scan(cursor, placeholder, type_name):
    cursor.execute(f"SELECT data FROM events WHERE type = {placeholder}", [type_name])
    rows = cursor.fetchall()

    found = set()
    for (data,) in rows:
        if not data:
            continue
        try:
            parsed = json.loads(data)
        except (TypeError, ValueError):
            continue
        loc = parsed.get("localisation") if isinstance(parsed, dict) else None
        if loc:
            found.add(loc)

    cursor.execute("SELECT localisation FROM geolocations")
    existing = {row[0] for row in cursor.fetchall()}
    new_locations = found - existing

    now = datetime.now(timezone.utc).isoformat()
    for loc in sorted(new_locations):
        cursor.execute(
            f"INSERT INTO geolocations (localisation, latitude, longitude, created_at, updated_at) "
            f"VALUES ({placeholder}, NULL, NULL, {placeholder}, {placeholder})",
            [loc, now, now],
        )

    return len(rows), sorted(new_locations)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--backend", choices=["sqlite", "postgres"], required=True)
    parser.add_argument("--db-file", default="timeseries.db", help="Fichier SQLite (backend sqlite uniquement)")
    parser.add_argument("--type", required=True, help="Type d'événement à scanner")
    args = parser.parse_args()

    if args.backend == "sqlite":
        import sqlite3
        conn = sqlite3.connect(args.db_file)
        placeholder = "?"
    else:
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get("PGHOST", "localhost"),
            port=os.environ.get("PGPORT", "6543"),
            user=os.environ.get("PGUSER", "pixelgrid"),
            password=os.environ.get("PGPASSWORD", "pixelgrid"),
            dbname=os.environ.get("PGDATABASE", "pixelgrid"),
        )
        placeholder = "%s"

    cursor = conn.cursor()
    scanned, new_locations = scan(cursor, placeholder, args.type)
    conn.commit()
    conn.close()

    print(f"{scanned} événement(s) scanné(s) pour le type '{args.type}'.", file=sys.stderr)
    if new_locations:
        print(f"{len(new_locations)} nouveau(x) lieu(x) ajouté(s) en attente de coordonnées :", file=sys.stderr)
        for loc in new_locations:
            print(f"  - {loc}", file=sys.stderr)
    else:
        print("Aucun nouveau lieu détecté.", file=sys.stderr)


if __name__ == "__main__":
    main()
