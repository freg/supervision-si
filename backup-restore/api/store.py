"""
Suivi des images de sauvegarde système (livraison #249, backlog item
27 -- "backup-restore", sous-volet marqué URGENT par la personne :
"Clonezilla (ou équivalent) pour produire une IMAGE SYSTÈME complète
-- objectif immédiat = future VIRTUALISATION de postes Windows
existants").

**Portée VOLONTAIREMENT LIMITÉE au SUIVI/COUVERTURE, pas à
l'automatisation réelle de Clonezilla** -- déclencher une vraie
capture d'image (PXE, boot Clonezilla, DRBL) nécessite une
infrastructure matérielle/réseau réelle (serveur PXE/TFTP, postes
Windows accessibles) qu'aucun test dans cet environnement ne peut
valider -- exactement le même raisonnement que pour l'agent réseau
(#233), livré d'abord en connaissance de cause puis confirmé/corrigé
sur de vrais retours de déploiement (#238-240).

Ce module répond d'abord à l'exigence explicite du backlog : "toute
machine [détectée sur le LAN] doit avoir une image prête à la
restauration" -- un registre des images connues, croisé avec les
appareils DÉJÀ découverts par `network-agent` (#233/#240), pour
répondre à la question "quelles machines n'ont PAS d'image récente ?"
-- la partie la plus immédiatement utile et vérifiable ici, avant
même de savoir précisément comment Clonezilla sera piloté.

Même motif SQLite que tous les autres modules de ce projet
(get_connection/ensure_schema/now_iso).
"""
import sqlite3
import time

SCHEMA = """
-- Un enregistrement = UNE image de sauvegarde connue, quelle que
-- soit l'origine (Clonezilla en priorité, mais `tool` reste un
-- champ libre pour ne jamais fermer la porte à BackupPC ou une
-- autre solution -- voir les autres volets, non traités ici).
-- `device_mac` optionnel -- une image peut être enregistrée AVANT
-- que la machine correspondante soit rapprochée d'un appareil
-- découvert par network-agent (ou si cette machine n'est pas/plus
-- sur le réseau surveillé) ; le rapprochement se fait alors par
-- `device_label` (nom lisible, saisi à la main).
CREATE TABLE IF NOT EXISTS backup_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_mac TEXT,
    device_label TEXT NOT NULL,
    tool TEXT NOT NULL,
    image_type TEXT,
    storage_path TEXT,
    taken_at TEXT NOT NULL,
    size_bytes INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_backup_images_mac ON backup_images(device_mac);
CREATE INDEX IF NOT EXISTS idx_backup_images_taken_at ON backup_images(taken_at);
"""


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


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def create_image(db_path, device_mac, device_label, tool, taken_at,
                  image_type=None, storage_path=None, size_bytes=None, notes=None):
    """`device_mac` normalisé en minuscules s'il est fourni -- une
    même adresse MAC peut arriver en casses différentes selon l'outil
    source (Clonezilla, network-agent...), jamais deux entrées qui ne
    se rapprochent pas à cause d'une différence de casse."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO backup_images
               (device_mac, device_label, tool, image_type, storage_path, taken_at, size_bytes, notes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                device_mac.lower().strip() if device_mac else None,
                device_label.strip(), tool.strip(), image_type, storage_path,
                taken_at, size_bytes, notes, now_iso(),
            ],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_images(db_path, device_mac=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if device_mac:
            cur.execute(
                "SELECT * FROM backup_images WHERE device_mac = ? ORDER BY taken_at DESC",
                [device_mac.lower().strip()],
            )
        else:
            cur.execute("SELECT * FROM backup_images ORDER BY taken_at DESC")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def delete_image(db_path, image_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM backup_images WHERE id = ?", [image_id])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def most_recent_by_mac(db_path):
    """Renvoie {mac_address: ligne_la_plus_recente} -- UNE seule
    ligne par MAC (la plus récente par `taken_at`), calculé en
    Python plutôt qu'en SQL (portable, cohérent avec le reste de ce
    projet -- voir `relation_validator.py` pour le même raisonnement
    appliqué ailleurs) : SQLite n'a pas de fenêtre `DISTINCT ON`
    native comme PostgreSQL, une requête corrélée serait plus fragile
    à lire que ce simple regroupement après lecture complète."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM backup_images WHERE device_mac IS NOT NULL ORDER BY taken_at DESC")
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    latest = {}
    for row in rows:
        mac = row["device_mac"]
        if mac not in latest:  # la première rencontrée est la plus récente, grâce au tri SQL ci-dessus
            latest[mac] = row
    return latest

# ===================================================================
# Extensions livraison #270 -- Connecteurs BackupPC, Clonezilla, Restic
# ===================================================================

# Table des configurations de connecteurs
SCHEMA_CONNECTORS = """
CREATE TABLE IF NOT EXISTS connector_configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connector_type TEXT NOT NULL,
    name TEXT NOT NULL,
    url TEXT,
    config_json TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_connector_configs_type ON connector_configs(connector_type);
"""

SCHEMA_JOBS = """
CREATE TABLE IF NOT EXISTS backup_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connector_type TEXT NOT NULL,
    connector_id INTEGER,
    job_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    device TEXT,
    image_name TEXT,
    snapshot_id TEXT,
    target_path TEXT,
    progress_percent INTEGER DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    duration_seconds INTEGER,
    error_message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (connector_id) REFERENCES connector_configs(id)
);
CREATE INDEX IF NOT EXISTS idx_backup_jobs_status ON backup_jobs(status);
CREATE INDEX IF NOT EXISTS idx_backup_jobs_connector ON backup_jobs(connector_type);
"""

SCHEMA_SCHEDULES = """
CREATE TABLE IF NOT EXISTS backup_schedules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connector_type TEXT NOT NULL,
    connector_id INTEGER,
    name TEXT NOT NULL,
    cron_expression TEXT NOT NULL,
    config_json TEXT,
    enabled INTEGER DEFAULT 1,
    last_run_at TEXT,
    last_status TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (connector_id) REFERENCES connector_configs(id)
);
"""

SCHEMA_FILE_VERSIONS = """
CREATE TABLE IF NOT EXISTS file_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connector_type TEXT NOT NULL,
    host TEXT NOT NULL,
    file_path TEXT NOT NULL,
    version_number INTEGER NOT NULL,
    snapshot_id TEXT,
    size_bytes INTEGER,
    modified_at TEXT,
    hash TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_file_versions_host_path ON file_versions(host, file_path);
CREATE INDEX IF NOT EXISTS idx_file_versions_snapshot ON file_versions(snapshot_id);
"""

NEW_SCHEMAS = SCHEMA_CONNECTORS + SCHEMA_JOBS + SCHEMA_SCHEDULES + SCHEMA_FILE_VERSIONS


def ensure_connector_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(NEW_SCHEMAS)
        conn.commit()
    finally:
        conn.close()


def list_connector_configs(db_path, connector_type=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if connector_type:
            cur.execute("SELECT * FROM connector_configs WHERE connector_type = ? ORDER BY name", [connector_type])
        else:
            cur.execute("SELECT * FROM connector_configs ORDER BY connector_type, name")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def create_connector_config(db_path, connector_type, name, url=None, config_json=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO connector_configs (connector_type, name, url, config_json, enabled, created_at, updated_at) VALUES (?, ?, ?, ?, 1, ?, ?)",
            [connector_type, name, url, config_json, now_iso(), now_iso()])
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_connector_config(db_path, config_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM connector_configs WHERE id = ?", [config_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_jobs(db_path, connector_type=None, status=None, limit=50):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        query = "SELECT * FROM backup_jobs WHERE 1=1"
        params = []
        if connector_type:
            query += " AND connector_type = ?"
            params.append(connector_type)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def create_job(db_path, connector_type, job_type, connector_id=None, device=None, image_name=None, snapshot_id=None, target_path=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO backup_jobs (connector_type, connector_id, job_type, status, device, image_name, snapshot_id, target_path, created_at) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)",
            [connector_type, connector_id, job_type, device, image_name, snapshot_id, target_path, now_iso()])
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_job_status(db_path, job_id, status, progress_percent=None, error_message=None, finished_at=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        fields = ["status = ?"]
        params = [status]
        if progress_percent is not None:
            fields.append("progress_percent = ?")
            params.append(progress_percent)
        if error_message is not None:
            fields.append("error_message = ?")
            params.append(error_message)
        if finished_at is not None:
            fields.append("finished_at = ?")
            params.append(finished_at)
        elif status in ("completed", "failed", "cancelled"):
            fields.append("finished_at = ?")
            params.append(now_iso())
        if status == "running":
            fields.append("started_at = COALESCE(started_at, ?)")
            params.append(now_iso())
        params.append(job_id)
        cur.execute(f"UPDATE backup_jobs SET {', '.join(fields)} WHERE id = ?", params)
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_job(db_path, job_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM backup_jobs WHERE id = ?", [job_id])
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_schedules(db_path, connector_type=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if connector_type:
            cur.execute("SELECT * FROM backup_schedules WHERE connector_type = ? ORDER BY name", [connector_type])
        else:
            cur.execute("SELECT * FROM backup_schedules ORDER BY connector_type, name")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def create_schedule(db_path, connector_type, name, cron_expression, connector_id=None, config_json=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO backup_schedules (connector_type, connector_id, name, cron_expression, config_json, enabled, created_at) VALUES (?, ?, ?, ?, ?, 1, ?)",
            [connector_type, connector_id, name, cron_expression, config_json, now_iso()])
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_schedule(db_path, schedule_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM backup_schedules WHERE id = ?", [schedule_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_file_versions(db_path, host, file_path, limit=20):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM file_versions WHERE host = ? AND file_path = ? ORDER BY version_number DESC LIMIT ?",
            [host, file_path, limit])
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def add_file_version(db_path, connector_type, host, file_path, version_number, snapshot_id=None, size_bytes=None, modified_at=None, hash=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO file_versions (connector_type, host, file_path, version_number, snapshot_id, size_bytes, modified_at, hash, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [connector_type, host, file_path, version_number, snapshot_id, size_bytes, modified_at, hash, now_iso()])
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_hosts_with_versions(db_path, connector_type=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if connector_type:
            cur.execute("SELECT DISTINCT host FROM file_versions WHERE connector_type = ? ORDER BY host", [connector_type])
        else:
            cur.execute("SELECT DISTINCT host FROM file_versions ORDER BY host")
        return [r["host"] for r in cur.fetchall()]
    finally:
        conn.close()
