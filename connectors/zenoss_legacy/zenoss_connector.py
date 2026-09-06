"""
Connecteur Zenoss 2.5.x (legacy) — extraction des équipements "vivants".

Contexte : Zenoss 2.x stocke ses événements dans une base MySQL séparée
(`events`), tables `status` (événements actifs) et `history` (événements
clos). Le catalogue complet des équipements (classes, hiérarchie) vit
dans la ZODB, PAS dans MySQL — mais on n'en a pas besoin pour ce v0 :
un équipement "vivant" (info < N jours) se déduit directement des
événements (device + lastTime).

Principe de fonctionnement — IMPORTANT, à lire avant de pousser quoi
que ce soit en production :
1. INTROSPECTION D'ABORD : le script interroge INFORMATION_SCHEMA pour
   découvrir les colonnes réellement présentes sur `status`/`history`,
   plutôt que de supposer un schéma figé. Les noms de champs Zenoss sont
   bien documentés à travers les versions (device, component, eventClass,
   severity, summary, firstTime, lastTime, count, prodState, DeviceClass,
   Location, DeviceGroups, Systems, ipAddress...) mais aucune source
   trouvée ne confirme la liste exacte pour la 2.5.2 précisément — d'où
   cette approche défensive.
2. MODE DRY-RUN PAR DÉFAUT : le script n'écrit rien vers l'API de
   supervision tant que --push n'est pas explicitement passé. Lance-le
   d'abord SANS --push, partage-moi la sortie d'introspection, et on
   ajuste le mapping de champs ensemble avant tout envoi réel.

Usage :
    python3 zenoss_connector.py --introspect-only
    python3 zenoss_connector.py --cutoff-days 365
    python3 zenoss_connector.py --cutoff-days 365 --push --api-url http://localhost:5003 --api-source zenoss_inventory
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

try:
    import pymysql
    import pymysql.cursors
except ImportError:
    print("Dépendance manquante : pip install pymysql --break-system-packages", file=sys.stderr)
    sys.exit(1)


# ============================================================
# Configuration — variables d'environnement (avec fallback CLI)
# ============================================================

def get_config():
    return {
        "host": os.environ.get("ZENOSS_MYSQL_HOST", "localhost"),
        "port": int(os.environ.get("ZENOSS_MYSQL_PORT", "3306")),
        "user": os.environ.get("ZENOSS_MYSQL_USER", "zenoss"),
        "password": os.environ.get("ZENOSS_MYSQL_PASSWORD", ""),
        "database": os.environ.get("ZENOSS_MYSQL_DB", "events"),
    }


def connect(config):
    """
    Connexion en lecture seule si possible côté MySQL (à configurer sur
    le compte utilisé, pas dans ce script). `old_passwords` sur des
    installs très anciennes peut casser l'authentification avec des
    drivers récents — si la connexion échoue avec une erreur
    d'authentification, c'est la première piste à vérifier côté serveur.
    """
    return pymysql.connect(
        host=config["host"],
        port=config["port"],
        user=config["user"],
        password=config["password"],
        database=config["database"],
        cursorclass=pymysql.cursors.DictCursor,
        connect_timeout=10,
    )


# ============================================================
# Introspection — découvre les colonnes réelles, ne suppose rien
# ============================================================

# Champs qu'on SAIT vouloir utiliser s'ils existent, par ordre
# d'importance décroissante — vocabulaire Zenoss standard à travers les
# versions (voir docstring module pour les sources).
CANDIDATE_COLUMNS = [
    "device", "component", "eventClass", "eventClassKey", "eventKey",
    "severity", "summary", "message", "firstTime", "lastTime", "count",
    "prodState", "eventState", "DeviceClass", "Location", "DeviceGroups",
    "Systems", "ipAddress", "DevicePriority", "agent", "monitor",
    "facility", "priority", "evid", "dedupid",
]

REQUIRED_MINIMUM = {"device", "lastTime"}


def introspect_table(cursor, database, table):
    cursor.execute(
        "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s",
        (database, table),
    )
    return {row["COLUMN_NAME"] for row in cursor.fetchall()}


def introspect_schema(conn, config):
    cursor = conn.cursor()

    tables_result = introspect_table(cursor, config["database"], "status")
    if not tables_result:
        cursor.execute("SHOW TABLES")
        all_tables = [list(row.values())[0] for row in cursor.fetchall()]
        raise RuntimeError(
            f"Table 'status' introuvable dans la base '{config['database']}'. "
            f"Tables présentes : {all_tables}"
        )

    status_columns = tables_result
    history_columns = introspect_table(cursor, config["database"], "history")

    usable_status = [c for c in CANDIDATE_COLUMNS if c in status_columns]
    usable_history = [c for c in CANDIDATE_COLUMNS if c in history_columns]
    # On ne garde pour la requête UNION que les colonnes présentes dans
    # LES DEUX tables, pour un SELECT homogène.
    common_columns = [c for c in usable_status if c in history_columns]

    missing_required = REQUIRED_MINIMUM - set(common_columns)
    if missing_required:
        raise RuntimeError(
            f"Colonnes indispensables absentes de status/history : {missing_required}. "
            f"Colonnes trouvées sur 'status' : {sorted(status_columns)}. "
            f"Colonnes trouvées sur 'history' : {sorted(history_columns)}."
        )

    return {
        "status_columns_all": sorted(status_columns),
        "history_columns_all": sorted(history_columns),
        "common_usable_columns": common_columns,
        "device_class_available": "DeviceClass" in common_columns,
    }


# ============================================================
# Extraction — équipements "vivants" + dernière info par équipement
# ============================================================

def fetch_recent_events(conn, common_columns, cutoff_days):
    cutoff = datetime.now(timezone.utc) - timedelta(days=cutoff_days)
    cutoff_str = cutoff.strftime("%Y-%m-%d %H:%M:%S")

    col_list = ", ".join(common_columns)
    query = f"""
        SELECT {col_list} FROM status WHERE lastTime >= %s
        UNION ALL
        SELECT {col_list} FROM history WHERE lastTime >= %s
    """

    cursor = conn.cursor()
    cursor.execute(query, (cutoff_str, cutoff_str))
    return cursor.fetchall()


def build_device_latest_map(events):
    """Pour chaque device, ne garde que l'événement avec le lastTime le plus récent."""
    latest_by_device = {}
    for event in events:
        device = event.get("device")
        if not device:
            continue
        current = latest_by_device.get(device)
        if current is None or event["lastTime"] > current["lastTime"]:
            latest_by_device[device] = event
    return latest_by_device


def stringify_row(row):
    """Convertit les types non-JSON-sérialisables (datetime, Decimal) en str/nombre simple."""
    result = {}
    for key, value in row.items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif value is None:
            result[key] = None
        else:
            try:
                json.dumps(value)
                result[key] = value
            except TypeError:
                result[key] = str(value)
    return result


def build_tree(latest_by_device, device_class_available):
    """
    Construit l'arborescence pour la colonne de gauche de l'inventaire.
    Si DeviceClass est disponible, découpe son chemin ("/Server/Linux")
    en niveaux imbriqués. Sinon, repli sur un unique groupe
    "Unclassified" (l'absence de hiérarchie native MySQL est documentée
    en tête de ce module — nécessiterait une extraction ZODB pour aller
    plus loin).
    """
    root = {"name": "/", "children": {}, "devices": []}

    for device_name, event in latest_by_device.items():
        leaf = {"name": device_name, "latest_event": stringify_row(event)}

        if device_class_available and event.get("DeviceClass"):
            parts = [p for p in event["DeviceClass"].split("/") if p]
        else:
            parts = ["Unclassified"]

        node = root
        for part in parts:
            node = node["children"].setdefault(part, {"name": part, "children": {}, "devices": []})
        node["devices"].append(leaf)

    def finalize(node):
        node["children"] = [finalize(c) for c in node["children"].values()]
        if not node["children"]:
            del node["children"]
        if not node["devices"]:
            del node["devices"]
        return node

    return finalize(root)


# ============================================================
# Push vers l'API de supervision (/ingest)
# ============================================================

def push_to_api(api_url, api_source, payload):
    import requests  # import local : uniquement nécessaire en mode --push

    response = requests.post(
        f"{api_url}/ingest/{api_source}",
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    try:
        return response.json()
    except ValueError:
        # Livraison #287 -- "rendre les erreurs systématiquement plus
        # explicites", généralisé depuis #286. Cible interne
        # (/ingest, cette plateforme), donc risque plus faible qu'un
        # système tiers -- corrigé quand même pour la cohérence
        # demandée explicitement.
        snippet = (response.text or "").strip()[:300]
        raise RuntimeError(f"push vers {api_url}/ingest/{api_source} : réponse 2xx inattendue (pas du JSON valide) -- début de la réponse : {snippet!r}")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--introspect-only", action="store_true", help="Affiche le schéma découvert et s'arrête là, sans rien extraire.")
    parser.add_argument("--cutoff-days", type=int, default=365, help="Ancienneté max pour considérer un équipement 'vivant' (défaut: 365).")
    parser.add_argument("--push", action="store_true", help="Pousse réellement le résultat vers l'API. Sans ce flag : dry-run (affiche seulement).")
    parser.add_argument("--api-url", default="http://localhost:5003", help="URL de base de l'API de supervision.")
    parser.add_argument("--api-source", default="zenoss_inventory", help="Nom de la source pour /ingest/<source>.")
    parser.add_argument("--output-file", default=None, help="Écrit aussi le résultat dans ce fichier JSON local.")
    args = parser.parse_args()

    config = get_config()
    print(f"Connexion à mysql://{config['user']}@{config['host']}:{config['port']}/{config['database']} ...", file=sys.stderr)

    try:
        conn = connect(config)
    except Exception as exc:
        print(f"ÉCHEC de connexion : {exc}", file=sys.stderr)
        print(
            "Pistes si erreur d'authentification : vérifier 'old_passwords' côté "
            "serveur MySQL 5.0, ou tester avec le driver mysql-connector-python "
            "en alternative à pymysql.",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        schema_info = introspect_schema(conn, config)
        print("=== Schéma découvert ===", file=sys.stderr)
        print(json.dumps(schema_info, indent=2, ensure_ascii=False), file=sys.stderr)

        if args.introspect_only:
            return

        events = fetch_recent_events(conn, schema_info["common_usable_columns"], args.cutoff_days)
        print(f"{len(events)} événements trouvés sur les {args.cutoff_days} derniers jours.", file=sys.stderr)

        latest_by_device = build_device_latest_map(events)
        print(f"{len(latest_by_device)} équipement(s) 'vivant(s)' distinct(s).", file=sys.stderr)

        tree = build_tree(latest_by_device, schema_info["device_class_available"])

        payload = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "source_system": "Zenoss 2.5.2 (legacy)",
            "cutoff_days": args.cutoff_days,
            "device_count": len(latest_by_device),
            "schema_introspection": schema_info,
            "tree": tree,
        }

        if args.output_file:
            with open(args.output_file, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
            print(f"Écrit dans {args.output_file}", file=sys.stderr)

        if args.push:
            result = push_to_api(args.api_url, args.api_source, payload)
            print(f"Poussé vers l'API : {result}", file=sys.stderr)
        else:
            print("--- DRY RUN (pas de --push) : aperçu du payload ci-dessous ---")
            print(json.dumps(payload, ensure_ascii=False, indent=2)[:3000])
            print("... (tronqué pour l'aperçu console)")

    finally:
        conn.close()


if __name__ == "__main__":
    main()
