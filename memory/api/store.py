"""
Rémanence du tampon de logs Memcached (livraison #259, backlog item
32 -- tuile "Mémoire"). Demandé explicitement : "api/service de
rémanence du memcached... un outil à faible impact et simplement
supervisé qui va récupérer les kv du memcached régulièrement et les
stocke en base... avec un mécanisme de repopulation du memcached et
avec un garbage collector ou un timeout de remise en ligne, avec une
interface d'accès et de calcul pour naviguer dans les historiques et
calculer dessus... à relier aux autres données".

**Portée VOLONTAIREMENT SCOPÉE au tampon de logs partagé
(`shared/log_buffer.py`, #145), PAS un "tout Memcached" générique** --
raison technique réelle, vérifiée avant de coder : Memcached N'OFFRE
PAS de "lister les clés existantes" (confirmé par le commentaire déjà
présent dans `shared/log_buffer.py` lui-même, à l'origine du registre
`pushed_log_sources` -- ce module réutilise EXACTEMENT le même
raisonnement). Sans une liste de clés CONNUE À L'AVANCE, "récupérer
les kv du memcached" n'est tout simplement pas réalisable de façon
générique.

Ce module énumère donc les clés du tampon de logs de DEUX façons
COMBINÉES, les deux seules sources véritablement énumérables :
1. Les `SERVICE_NAME` INTERNES connus (26 services de ce projet,
   chacun écrit sous `logbuf:{service_name}`) -- liste FIXE,
   recensée directement dans le code de chaque backend.
2. Le registre `pushed_log_sources` (déjà construit en #145 pour
   `/push-log`, sources EXTERNES dont le nom n'est connu qu'après
   qu'elles aient poussé au moins une fois) -- lu via
   `read_shared_log_source_registry`, jamais deviné.

**AUTRE usage de Memcached dans ce projet, DÉLIBÉRÉMENT HORS DE
PORTÉE** : le cache de requêtes court (ex. `zenoss-api`,
`ZENOSS_CACHE_TTL=60s` par défaut) -- RECALCULABLE à la demande
depuis la vraie source, jamais une donnée à préserver dans le temps,
fondamentalement différent en nature du tampon de logs (historique
diagnostique). Persister ce cache n'aurait aucun sens.
"""
import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS mem_log_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    service TEXT NOT NULL,
    entry_timestamp REAL NOT NULL,
    level TEXT NOT NULL,
    logger TEXT,
    message TEXT NOT NULL,
    collected_at TEXT NOT NULL,
    UNIQUE(service, entry_timestamp, message)
);
CREATE INDEX IF NOT EXISTS idx_mem_entries_service ON mem_log_entries(service);
CREATE INDEX IF NOT EXISTS idx_mem_entries_timestamp ON mem_log_entries(entry_timestamp);

-- Repère de collecte PAR SERVICE -- évite de retraiter tout le
-- tampon (jusqu'à 200 entrées par défaut) à chaque passage : seules
-- les entrées PLUS RÉCENTES que le dernier repère connu sont
-- effectivement insérées (la contrainte UNIQUE ci-dessus reste un
-- filet de sécurité, jamais le mécanisme principal de dédoublonnage
-- -- plus coûteux à chaque tentative qu'une comparaison directe).
CREATE TABLE IF NOT EXISTS mem_collection_state (
    service TEXT PRIMARY KEY,
    last_entry_timestamp REAL NOT NULL,
    last_collected_at TEXT NOT NULL
);
"""


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_last_collected_timestamp(db_path, service):
    """`None` si ce service n'a encore jamais été collecté --
    signale à l'appelant de tout considérer comme "nouveau" plutôt
    que de filtrer contre une valeur inventée."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT last_entry_timestamp FROM mem_collection_state WHERE service = ?", [service])
        row = cur.fetchone()
        return row["last_entry_timestamp"] if row else None
    finally:
        conn.close()


def persist_new_entries(db_path, service, entries):
    """Persiste les entrées PLUS RÉCENTES que le dernier repère connu
    pour `service` -- `entries` est la liste COMPLÈTE actuellement
    dans le tampon Memcached (voir `read_shared_log_buffer`), jamais
    seulement un delta calculé côté appelant (le tri/filtrage se fait
    ICI, une seule logique à maintenir). Renvoie le nombre d'entrées
    RÉELLEMENT insérées (jamais compté deux fois via la contrainte
    UNIQUE -- `INSERT OR IGNORE`, un filet de sécurité, pas le
    mécanisme principal, voir docstring du schéma)."""
    if not entries:
        return 0
    last_ts = get_last_collected_timestamp(db_path, service)
    new_entries = [e for e in entries if last_ts is None or e.get("timestamp", 0) > last_ts]
    if not new_entries:
        return 0

    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        inserted = 0
        max_ts = last_ts or 0
        for entry in new_entries:
            ts = entry.get("timestamp", 0)
            try:
                cur.execute(
                    """INSERT OR IGNORE INTO mem_log_entries
                       (service, entry_timestamp, level, logger, message, collected_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    [service, ts, entry.get("level", "?"), entry.get("logger"), entry.get("message", ""), now_iso()],
                )
                if cur.rowcount > 0:
                    inserted += 1
            except sqlite3.Error:
                continue  # une entrée malformée ne doit jamais interrompre les suivantes
            max_ts = max(max_ts, ts)
        cur.execute(
            """INSERT INTO mem_collection_state (service, last_entry_timestamp, last_collected_at)
               VALUES (?, ?, ?)
               ON CONFLICT(service) DO UPDATE SET last_entry_timestamp = ?, last_collected_at = ?""",
            [service, max_ts, now_iso(), max_ts, now_iso()],
        )
        conn.commit()
        return inserted
    finally:
        conn.close()


def purge_old_entries(db_path, older_than_iso):
    """Rétention -- "garbage collector", VOLONTAIREMENT bornée dans
    le temps, même motif que `network-agent`/#251
    (`purge_old_snapshots`). Compare sur `collected_at` (quand
    l'entrée a été PERSISTÉE ici), pas `entry_timestamp` (quand le
    service a émis le log) -- une entrée ancienne mais collectée
    récemment (ex. après une longue interruption de la collecte)
    reste conservée au moins le temps de rétention PLEIN à partir de
    sa collecte, jamais purgée immédiatement."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM mem_log_entries WHERE collected_at < ?", [older_than_iso])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def list_entries(db_path, service=None, level=None, since=None, until=None, limit=500):
    """Filtres sur `entry_timestamp` (horodatage RÉEL du log, Unix --
    voir schéma ci-dessus), jamais `collected_at` (quand CE service
    l'a archivé) -- fusion #353 (backlog item 8, deux systèmes
    d'archivage parallèles consolidés en un seul) : reprend
    exactement la sémantique since/until de l'ancien
    `prefs-api/log_archiver.py` (`query_persisted_logs`), désormais
    supprimé. Remplace l'ancien paramètre `since_iso` (filtrait sur
    `collected_at`, jamais utilisé par aucune interface avant cette
    fusion -- changement sûr, aucun appelant existant à préserver)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        clauses, params = [], []
        if service:
            clauses.append("service = ?")
            params.append(service)
        if level:
            clauses.append("level = ?")
            params.append(level)
        if since is not None:
            clauses.append("entry_timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("entry_timestamp <= ?")
            params.append(until)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur.execute(f"SELECT * FROM mem_log_entries {where} ORDER BY entry_timestamp DESC LIMIT ?", params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def list_known_services(db_path):
    """Services ayant AU MOINS une entrée persistée -- pour peupler
    un filtre côté hub, jamais une liste statique qui se périmerait."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT service FROM mem_log_entries ORDER BY service")
        return [r["service"] for r in cur.fetchall()]
    finally:
        conn.close()


def compute_stats_by_service(db_path, since=None, until=None):
    """LE "calcul" demandé explicitement ("une interface d'accès et
    de calcul... pour calculer dessus") -- comptage par service ET
    par niveau, sur la période demandée -- répond directement à "quel
    service génère le plus d'avertissements/erreurs". Calculé PUREMENT
    en lecture depuis les entrées déjà persistées, jamais une nouvelle
    table de compteurs à maintenir en parallèle (une seule source de
    vérité). Filtres sur `entry_timestamp` (même raisonnement que
    `list_entries` ci-dessus, fusion #353)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        clauses, params = [], []
        if since is not None:
            clauses.append("entry_timestamp >= ?")
            params.append(since)
        if until is not None:
            clauses.append("entry_timestamp <= ?")
            params.append(until)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cur.execute(f"SELECT service, level, COUNT(*) as n FROM mem_log_entries {where} GROUP BY service, level", params)
        rows = cur.fetchall()
    finally:
        conn.close()

    grouped = {}
    for row in rows:
        entry = grouped.setdefault(row["service"], {"service": row["service"], "total": 0, "by_level": {}})
        entry["by_level"][row["level"]] = row["n"]
        entry["total"] += row["n"]
    return sorted(grouped.values(), key=lambda e: -e["total"])
