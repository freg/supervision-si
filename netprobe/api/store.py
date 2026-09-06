"""
netprobe -- livraison #295, demandé explicitement : "un service type
smokeping permanent sur potentiellement tous les IP relevés -> bdd,
nmap à la demande -> bdd, tcpdump sans stockage utilisable par
d'autres modules, un collecteur d'IP -> bdd, une analyse multi
scripts (un ordonnanceur de scripts d'analyse des données des
services précédent), un système de contrôle permettant d'activer,
désactiver, temporiser (fréquence d'échantillonnage), programmer".

Module SÉPARÉ de network-agent (décision prise avec la personne,
"à toi de décider en fonction de l'impact de charge sur le reste") :
network-agent fait de la capture PASSIVE continue dans son propre
conteneur (`network_mode: host`) -- y ajouter du sondage ACTIF
(smokeping continu, tcpdump partagé) créerait une concurrence
CPU/mémoire risquant de dégrader sa précision de capture existante.
Isolé dans son propre conteneur, limitable/éteignable indépendamment.

Portée de CETTE livraison (#295) : la FONDATION dont les autres
volets dépendent -- le collecteur d'IP (targets, point 4 de la
demande) et le système de contrôle (probe_config, point 6). Les
volets actifs eux-mêmes (smokeping, nmap, tcpdump partagé, analyseur
multi-scripts) restent À CONSTRUIRE -- chantier trop vaste pour une
seule livraison, jamais bâclé.
"""
import json
import sqlite3
import time

# Types de sonde reconnus -- liste FERMÉE ici (contrairement à
# rights-api où les types de ressource restent ouverts) : chaque
# type correspond à un futur module CONCRET de ce projet, pas une
# catégorie arbitraire que n'importe qui pourrait inventer.
PROBE_TYPES = ("smokeping", "nmap", "tcpdump", "ip-collector", "analyzer", "iperf3")

SCHEMA = """
CREATE TABLE IF NOT EXISTS targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ip_address TEXT NOT NULL UNIQUE,
    label TEXT,
    source TEXT NOT NULL,
    added_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_targets_active ON targets(active);

CREATE TABLE IF NOT EXISTS probe_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    probe_type TEXT NOT NULL,
    -- Bug réel trouvé et corrigé en test (#295) : SQLite ne
    -- considère JAMAIS deux NULL comme égaux dans une contrainte
    -- UNIQUE (comportement SQL standard) -- une colonne target_id
    -- NULLABLE aurait laissé chaque config GLOBALE répétée créer
    -- une nouvelle ligne au lieu de mettre à jour l'existante.
    -- Sentinelle 0 pour "global" à la place de NULL (les vraies
    -- cibles commencent à 1, AUTOINCREMENT) -- traduit en/depuis
    -- None côté Python, jamais exposé tel quel à l'appelant.
    target_id INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    -- NULL = pas d'échantillonnage périodique (ex. nmap à la
    -- demande, jamais programmé automatiquement par défaut).
    frequency_seconds INTEGER,
    -- Fenêtre horaire optionnelle (0-23) -- NULL des deux =
    -- aucune restriction, tourne en continu si enabled et
    -- frequency_seconds sont définis.
    schedule_start_hour INTEGER,
    schedule_end_hour INTEGER,
    updated_at TEXT NOT NULL,
    UNIQUE(probe_type, target_id)
);

-- Smokeping (volet 1 de la demande #295, livraison #297) -- un
-- échantillon = un passage de sonde vers UNE cible. Jamais recalculé
-- à la volée : chaque passage crée une ligne, permet de voir une
-- TENDANCE dans le temps (même raisonnement déjà établi dans
-- vigilance/README.md pour son propre journal de signaux).
CREATE TABLE IF NOT EXISTS smokeping_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id),
    sampled_at TEXT NOT NULL,
    success INTEGER NOT NULL,
    latency_ms REAL,
    packet_loss_percent INTEGER,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_smokeping_target_time ON smokeping_samples(target_id, sampled_at);

-- nmap à la demande (volet 2 de la demande #295, livraison #302) --
-- un scan = un passage, PERMANENT (même raisonnement que
-- smokeping_samples) -- open_ports stocké en JSON (TEXT), jamais une
-- table normalisée séparée : le nombre de ports ouverts par scan est
-- petit et variable, une jointure supplémentaire n'apporterait rien
-- ici, contrairement à smokeping où chaque échantillon est un point
-- de donnée simple et régulier.
CREATE TABLE IF NOT EXISTS nmap_scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id),
    scanned_at TEXT NOT NULL,
    success INTEGER NOT NULL,
    open_ports_json TEXT NOT NULL,
    scan_duration_seconds REAL,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_nmap_target_time ON nmap_scans(target_id, scanned_at);

-- Débit réel à la demande (backlog item 47 reformulé 2026-09-05,
-- livraison #385) -- MÊME motif que nmap_scans ci-dessus (un test =
-- un passage, PERMANENT, à la demande jamais programmé
-- automatiquement -- voir iperf3_probe.py pour le raisonnement de
-- charge complet : un test iperf3 utilise de la vraie bande
-- passante pendant plusieurs secondes, contrairement à un ping
-- unique, jamais mis sur le même tick périodique que smokeping).
CREATE TABLE IF NOT EXISTS iperf3_tests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_id INTEGER NOT NULL REFERENCES targets(id),
    tested_at TEXT NOT NULL,
    success INTEGER NOT NULL,
    sent_mbps REAL,
    received_mbps REAL,
    retransmits INTEGER,
    error TEXT
);
CREATE INDEX IF NOT EXISTS idx_iperf3_target_time ON iperf3_tests(target_id, tested_at);

-- Analyseur multi-scripts (volet 4 de la demande #295, livraison
-- #307) -- résultat = un CONSTAT d'un analyseur pour une cible (ou
-- global si target_id NULL, ex. une observation transversale).
-- PERMANENT, même raisonnement que les autres tables de ce module --
-- un historique de constats, jamais recalculé à la volée.
CREATE TABLE IF NOT EXISTS analysis_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analyzer_name TEXT NOT NULL,
    target_id INTEGER REFERENCES targets(id),
    detected_at TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_analysis_time ON analysis_results(detected_at);
CREATE INDEX IF NOT EXISTS idx_analysis_target ON analysis_results(target_id);
"""

# Sentinelle interne pour "configuration globale" (target_id=None
# côté API Python) -- jamais une vraie valeur de clé primaire de
# targets (AUTOINCREMENT commence à 1).
_GLOBAL_TARGET_SENTINEL = 0


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


# ============================================================
# Collecteur d'IP (point 4 de la demande)
# ============================================================

def add_target(db_path, ip_address, label=None, source="manual"):
    """Ajoute une cible -- idempotent sur ip_address (UNIQUE) : un
    ajout répété de la MÊME IP ne crée jamais de doublon, met à jour
    le libellé si fourni. Renvoie (id, created) -- created=False si
    la cible existait déjà (utile à l'appelant pour distinguer un
    ajout d'une simple confirmation)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM targets WHERE ip_address = ?", [ip_address])
        existing = cur.fetchone()
        if existing:
            if label is not None:
                cur.execute("UPDATE targets SET label = ? WHERE id = ?", [label, existing["id"]])
                conn.commit()
            return existing["id"], False
        cur.execute(
            "INSERT INTO targets (ip_address, label, source, added_at, active) VALUES (?, ?, ?, ?, 1)",
            [ip_address, label, source, now_iso()],
        )
        conn.commit()
        return cur.lastrowid, True
    finally:
        conn.close()


def list_targets(db_path, active_only=False):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if active_only:
            cur.execute("SELECT * FROM targets WHERE active = 1 ORDER BY ip_address")
        else:
            cur.execute("SELECT * FROM targets ORDER BY ip_address")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def set_target_active(db_path, target_id, active):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE targets SET active = ? WHERE id = ?", [1 if active else 0, target_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_target(db_path, target_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM probe_config WHERE target_id = ?", [target_id])
        cur.execute("DELETE FROM targets WHERE id = ?", [target_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def import_targets_from_network_agent(db_path, devices):
    """Importe une liste de dicts {"ip_address", "hostname"?} --
    format déjà utilisé par network-agent (voir NetworkAgentView.jsx,
    architecture/api/app.py pour des exemples de consommation de ce
    même format). Best-effort : une IP absente/vide dans un item est
    ignorée, jamais une erreur qui ferait échouer tout l'import pour
    UNE seule entrée malformée. Renvoie {"imported": n, "skipped": n}."""
    imported = 0
    skipped = 0
    for device in devices:
        ip = (device.get("ip_address") or "").strip()
        if not ip:
            skipped += 1
            continue
        label = (device.get("hostname") or "").strip() or None
        _, created = add_target(db_path, ip, label=label, source="network-agent-import")
        if created:
            imported += 1
    return {"imported": imported, "skipped": skipped}


# ============================================================
# Système de contrôle (point 6 de la demande)
# ============================================================

def get_effective_config(db_path, probe_type, target_id=None):
    """Renvoie la config EFFECTIVE pour (probe_type, target_id) --
    un override PRÉCIS pour cette cible prime sur la config GLOBALE
    du type (target_id NULL), qui prime elle-même sur un défaut
    codé en dur (désactivé, jamais actif par défaut -- un nouveau
    type de sonde ne doit jamais démarrer tout seul sans configuration
    explicite). Ordre de recherche : précis d'abord, global ensuite,
    défaut en dernier recours."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if target_id is not None:
            cur.execute(
                "SELECT * FROM probe_config WHERE probe_type = ? AND target_id = ?",
                [probe_type, target_id],
            )
            row = cur.fetchone()
            if row:
                result = dict(row)
                result["target_id"] = target_id
                return result
        cur.execute(
            "SELECT * FROM probe_config WHERE probe_type = ? AND target_id = ?",
            [probe_type, _GLOBAL_TARGET_SENTINEL],
        )
        row = cur.fetchone()
        if row:
            result = dict(row)
            result["target_id"] = None
            return result
        return {
            "probe_type": probe_type, "target_id": target_id, "enabled": 0,
            "frequency_seconds": None, "schedule_start_hour": None, "schedule_end_hour": None,
        }
    finally:
        conn.close()


def set_probe_config(db_path, probe_type, enabled, frequency_seconds=None,
                      schedule_start_hour=None, schedule_end_hour=None, target_id=None):
    """Crée ou met à jour la config -- UPSERT sur (probe_type,
    target_id), jamais une ligne dupliquée pour la même combinaison.
    `target_id=None` (API publique) traduit en sentinelle interne
    avant écriture -- voir SCHEMA, bug réel corrigé (#295)."""
    if probe_type not in PROBE_TYPES:
        raise ValueError(f"probe_type invalide : {probe_type!r} (attendu : {PROBE_TYPES})")
    stored_target_id = _GLOBAL_TARGET_SENTINEL if target_id is None else target_id
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO probe_config (probe_type, target_id, enabled, frequency_seconds, schedule_start_hour, schedule_end_hour, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(probe_type, target_id) DO UPDATE SET
                   enabled = excluded.enabled,
                   frequency_seconds = excluded.frequency_seconds,
                   schedule_start_hour = excluded.schedule_start_hour,
                   schedule_end_hour = excluded.schedule_end_hour,
                   updated_at = excluded.updated_at""",
            [probe_type, stored_target_id, 1 if enabled else 0, frequency_seconds, schedule_start_hour, schedule_end_hour, now_iso()],
        )
        conn.commit()
        return True
    finally:
        conn.close()


def set_probe_config_enabled(db_path, config_id, enabled):
    """Bascule RAPIDE activé/désactivé par id de ligne -- jamais
    besoin de resoumettre tout le formulaire pour ce seul champ.
    Renvoie False si la ligne n'existe pas (jamais une exception --
    l'appelant décide du code HTTP)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE probe_config SET enabled = ?, updated_at = ? WHERE id = ?",
            [1 if enabled else 0, now_iso(), config_id],
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_probe_config(db_path, config_id):
    """Supprime une configuration de sonde -- jamais de suppression
    en cascade d'autre chose (une config est indépendante des
    échantillons déjà enregistrés, qui restent -- historique
    préservé même après suppression de la config qui les a
    produits)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM probe_config WHERE id = ?", [config_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def is_within_schedule(config, reference_hour):
    """Vrai si `reference_hour` (0-23) tombe dans la fenêtre horaire
    configurée -- aucune restriction si les deux bornes sont NULL.
    Gère le passage minuit (ex. 22h -> 6h) : fenêtre INVERSÉE si
    start > end."""
    start = config.get("schedule_start_hour")
    end = config.get("schedule_end_hour")
    if start is None or end is None:
        return True
    if start <= end:
        return start <= reference_hour <= end
    return reference_hour >= start or reference_hour <= end


def list_probe_configs(db_path, probe_type=None):
    """`target_id` traduit de la sentinelle interne (0) vers `None`
    dans chaque résultat -- l'appelant ne doit jamais voir la
    sentinelle, seulement la convention publique (None = global)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if probe_type:
            cur.execute("SELECT * FROM probe_config WHERE probe_type = ? ORDER BY target_id", [probe_type])
        else:
            cur.execute("SELECT * FROM probe_config ORDER BY probe_type, target_id")
        results = [dict(r) for r in cur.fetchall()]
        for r in results:
            if r["target_id"] == _GLOBAL_TARGET_SENTINEL:
                r["target_id"] = None
        return results
    finally:
        conn.close()


# ============================================================
# Smokeping (volet 1 de la demande, livraison #297)
# ============================================================

def record_sample(db_path, target_id, success, latency_ms=None, packet_loss_percent=None, error=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO smokeping_samples (target_id, sampled_at, success, latency_ms, packet_loss_percent, error)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [target_id, now_iso(), 1 if success else 0, latency_ms, packet_loss_percent, error],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_samples(db_path, target_id, limit=100):
    """Les plus RÉCENTS d'abord (ORDER BY id DESC) -- une consultation
    typique veut voir l'état actuel en premier, jamais le tout début
    de l'historique."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM smokeping_samples WHERE target_id = ? ORDER BY id DESC LIMIT ?",
            [target_id, limit],
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def latest_sample_per_target(db_path):
    """Un seul échantillon PAR CIBLE -- le plus récent -- pour une
    vue d'ensemble (tableau de bord) sans charger tout l'historique
    de chaque cible. Sous-requête corrélée plutôt qu'un GROUP BY
    simple : SQLite ne garantit pas quelle ligne un GROUP BY renvoie
    pour les colonnes hors agrégat, jamais présumé sans le
    garantir explicitement."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT s.* FROM smokeping_samples s
               WHERE s.id = (
                   SELECT id FROM smokeping_samples s2
                   WHERE s2.target_id = s.target_id
                   ORDER BY s2.id DESC LIMIT 1
               )
               ORDER BY s.target_id"""
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def prune_old_samples(db_path, keep_count_per_target=2000):
    """Purge -- garde les `keep_count_per_target` plus récents PAR
    CIBLE, supprime le reste. Jamais appelé automatiquement à chaque
    écriture (coûteux) -- prévu pour un appel périodique séparé
    (voir scheduler.py)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT target_id FROM smokeping_samples")
        target_ids = [r["target_id"] for r in cur.fetchall()]
        total_deleted = 0
        for tid in target_ids:
            cur.execute(
                """DELETE FROM smokeping_samples WHERE target_id = ? AND id NOT IN (
                       SELECT id FROM smokeping_samples WHERE target_id = ? ORDER BY id DESC LIMIT ?
                   )""",
                [tid, tid, keep_count_per_target],
            )
            total_deleted += cur.rowcount
        conn.commit()
        return total_deleted
    finally:
        conn.close()


# ============================================================
# nmap à la demande (volet 2 de la demande, livraison #302)
# ============================================================

def record_nmap_scan(db_path, target_id, success, open_ports=None, scan_duration_seconds=None, error=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO nmap_scans (target_id, scanned_at, success, open_ports_json, scan_duration_seconds, error)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [target_id, now_iso(), 1 if success else 0, json.dumps(open_ports or []), scan_duration_seconds, error],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_nmap_scans(db_path, target_id, limit=50):
    """Les plus RÉCENTS d'abord -- `open_ports_json` décodé avant
    renvoi, jamais laissé en chaîne brute à la charge de l'appelant."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM nmap_scans WHERE target_id = ? ORDER BY id DESC LIMIT ?",
            [target_id, limit],
        )
        results = []
        for r in cur.fetchall():
            row = dict(r)
            try:
                row["open_ports"] = json.loads(row.pop("open_ports_json"))
            except (json.JSONDecodeError, TypeError):
                row["open_ports"] = []
            results.append(row)
        return results
    finally:
        conn.close()


# ============================================================
# Débit réel à la demande (backlog item 47 reformulé, livraison #385)
# ============================================================

def record_iperf3_test(db_path, target_id, success, sent_mbps=None, received_mbps=None, retransmits=None, error=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO iperf3_tests (target_id, tested_at, success, sent_mbps, received_mbps, retransmits, error)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [target_id, now_iso(), 1 if success else 0, sent_mbps, received_mbps, retransmits, error],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_iperf3_tests(db_path, target_id, limit=50):
    """Les plus RÉCENTS d'abord -- même motif que list_nmap_scans."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM iperf3_tests WHERE target_id = ? ORDER BY id DESC LIMIT ?",
            [target_id, limit],
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


# ============================================================
# Analyseur multi-scripts (volet 4, livraison #307)
# ============================================================

def record_analysis_result(db_path, analyzer_name, severity, message, target_id=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO analysis_results (analyzer_name, target_id, detected_at, severity, message) VALUES (?, ?, ?, ?, ?)",
            [analyzer_name, target_id, now_iso(), severity, message],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_analysis_results(db_path, target_id=None, analyzer_name=None, limit=100):
    """Les plus RÉCENTS d'abord. `target_id`/`analyzer_name`
    optionnels -- sans filtre, renvoie tous les constats (utile pour
    une vue d'ensemble)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        query = "SELECT * FROM analysis_results WHERE 1=1"
        params = []
        if target_id is not None:
            query += " AND target_id = ?"
            params.append(target_id)
        if analyzer_name is not None:
            query += " AND analyzer_name = ?"
            params.append(analyzer_name)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        cur.execute(query, params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
