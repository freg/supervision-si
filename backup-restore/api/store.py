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
