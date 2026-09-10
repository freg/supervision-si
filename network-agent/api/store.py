"""
Stockage de l'agent d'exploration réseau (livraison #233, backlog
item 20). Modèle de données CLARIFIÉ avec la personne avant de
coder : "un seul agent... une seule tuile même si on distinguera les
sites et les réseaux dans l'organisation des données" -- d'où la
hiérarchie site -> segment réseau -> appareil ci-dessous, même si un
seul agent (donc généralement un seul site/segment actifs à la fois)
tourne réellement pour l'instant.

**Découverte PROGRESSIVE, jamais un scan ponctuel** (demandé
explicitement) : ce module ne fait qu'ACCUMULER -- `first_seen` n'est
jamais réécrit, `last_seen`/compteurs sont mis à jour à chaque
paquet vu concernant un appareil déjà connu.
"""
import ipaddress
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS na_sites (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS na_network_segments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id INTEGER NOT NULL REFERENCES na_sites(id),
    label TEXT NOT NULL,
    cidr TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(site_id, label)
);

-- Un appareil = une adresse MAC, DANS un segment réseau donné (la
-- même MAC physique pourrait apparaître dans deux segments captés
-- par deux agents différents un jour -- pas confondue). `ip_address`
-- = la DERNIÈRE IP vue pour cette MAC (peut changer -- DHCP -- sans
-- que ce soit un nouvel appareil).
CREATE TABLE IF NOT EXISTS na_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    network_segment_id INTEGER NOT NULL REFERENCES na_network_segments(id),
    mac_address TEXT NOT NULL,
    ip_address TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    packet_count INTEGER NOT NULL DEFAULT 0,
    bytes_total INTEGER NOT NULL DEFAULT 0,
    external_relay_count INTEGER NOT NULL DEFAULT 0,
    role_hint TEXT,
    UNIQUE(network_segment_id, mac_address)
);
CREATE INDEX IF NOT EXISTS idx_na_devices_segment ON na_devices(network_segment_id);

-- Services vus PAR appareil -- seulement en tant que DESTINATAIRE
-- (`port` reçu par cet appareil) : signal bien plus fiable qu'un
-- port source, généralement éphémère et sans valeur pour identifier
-- un service REELLEMENT offert par l'appareil (voir capture.py).
CREATE TABLE IF NOT EXISTS na_device_services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL REFERENCES na_devices(id),
    protocol TEXT NOT NULL,
    port INTEGER NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    packet_count INTEGER NOT NULL DEFAULT 0,
    UNIQUE(device_id, protocol, port)
);
CREATE INDEX IF NOT EXISTS idx_na_services_device ON na_device_services(device_id);

-- Échanges ENTRE appareils -- "qui parle à qui" (livraison #250,
-- demandé explicitement par la personne : "détection de la
-- communication => échange"). DIRECTIONNEL (device_a = source,
-- device_b = destination) plutôt qu'un lien non orienté normalisé --
-- garde l'information la plus riche (qui INITIE l'échange), une
-- conversation bidirectionnelle apparaît naturellement comme DEUX
-- lignes (A->B et B->A), révélant les motifs asymétriques (un client
-- qui envoie beaucoup à un serveur, la réponse nettement plus légère)
-- plutôt que de les fondre en une moyenne qui masquerait ce signal.
CREATE TABLE IF NOT EXISTS na_device_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    network_segment_id INTEGER NOT NULL REFERENCES na_network_segments(id),
    device_a_id INTEGER NOT NULL REFERENCES na_devices(id),
    device_b_id INTEGER NOT NULL REFERENCES na_devices(id),
    packet_count INTEGER NOT NULL DEFAULT 0,
    bytes_total INTEGER NOT NULL DEFAULT 0,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    UNIQUE(network_segment_id, device_a_id, device_b_id)
);
CREATE INDEX IF NOT EXISTS idx_na_links_segment ON na_device_links(network_segment_id);
CREATE INDEX IF NOT EXISTS idx_na_links_device_a ON na_device_links(device_a_id);

-- Services utilisés PAR PAIRE d'appareils (livraison #251, demandé
-- explicitement : "les services connectés par paire d'ip") --
-- TABLE SÉPARÉE de `na_device_links` plutôt qu'une extension de son
-- schéma (déjà livré en #250, pas encore confirmé en usage réel --
-- additif ici, aucun risque de migration sur une table qui pourrait
-- déjà être en service). Même granularité directionnelle que
-- `na_device_links` (device_a = source, device_b = destination).
CREATE TABLE IF NOT EXISTS na_device_link_services (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    network_segment_id INTEGER NOT NULL REFERENCES na_network_segments(id),
    device_a_id INTEGER NOT NULL REFERENCES na_devices(id),
    device_b_id INTEGER NOT NULL REFERENCES na_devices(id),
    protocol TEXT NOT NULL,
    port INTEGER NOT NULL,
    packet_count INTEGER NOT NULL DEFAULT 0,
    bytes_total INTEGER NOT NULL DEFAULT 0,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    UNIQUE(network_segment_id, device_a_id, device_b_id, protocol, port)
);
CREATE INDEX IF NOT EXISTS idx_na_link_services_pair ON na_device_link_services(device_a_id, device_b_id);

-- Relevés périodiques -- "rémanence", demandé explicitement : "voir
-- dans le temps... présence des ip/mac, volumes échangés/usages par
-- paire d'ip, services connectés par paire d'ip". Toutes les tables
-- ci-dessus (`na_devices`, `na_device_links`,
-- `na_device_link_services`) sont CUMULATIVES -- une seule ligne par
-- entité, jamais d'évolution dans le temps. Un relevé = une COPIE
-- PONCTUELLE des compteurs cumulatifs à un instant donné -- comparer
-- deux relevés (soustraction côté lecture, jamais stocké en delta
-- ici -- garde la flexibilité d'interroger n'importe quel intervalle,
-- pas seulement celui figé à la capture) révèle l'évolution entre
-- les deux. Retenue VOLONTAIREMENT bornée dans le temps -- voir
-- `purge_old_snapshots` -- jamais une croissance illimitée.
-- IP DISTANTES vues derrière un relais (livraison #427) : une IP hors du
-- CIDR du segment n'est JAMAIS l'adresse de la MAC qui la porte (c'est la
-- passerelle) -- elle est rangée ici, avec le relais (`via_device_id`) et
-- le sens (in = source distante, out = destination distante). C'est ce
-- qui nourrit la fiche « sous-réseau » : d'où vient un sous-réseau qui
-- n'est pas le LAN immédiat, quelles IP y ont été vues, par quel relais.
CREATE TABLE IF NOT EXISTS na_remote_ips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    network_segment_id INTEGER NOT NULL REFERENCES na_network_segments(id),
    via_device_id INTEGER NOT NULL REFERENCES na_devices(id),
    ip_address TEXT NOT NULL,
    direction TEXT NOT NULL,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    packet_count INTEGER NOT NULL DEFAULT 0,
    bytes_total INTEGER NOT NULL DEFAULT 0,
    UNIQUE(network_segment_id, via_device_id, ip_address, direction)
);
CREATE INDEX IF NOT EXISTS idx_na_remote_ips_segment ON na_remote_ips(network_segment_id);

CREATE TABLE IF NOT EXISTS na_history_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    network_segment_id INTEGER NOT NULL REFERENCES na_network_segments(id),
    snapshot_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_na_snapshots_segment_time ON na_history_snapshots(network_segment_id, snapshot_at);

CREATE TABLE IF NOT EXISTS na_device_presence_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES na_history_snapshots(id),
    device_id INTEGER NOT NULL REFERENCES na_devices(id),
    ip_address TEXT,
    packet_count INTEGER NOT NULL,
    bytes_total INTEGER NOT NULL,
    last_seen TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_na_presence_snapshot ON na_device_presence_history(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_na_presence_device ON na_device_presence_history(device_id);

CREATE TABLE IF NOT EXISTS na_link_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_id INTEGER NOT NULL REFERENCES na_history_snapshots(id),
    device_a_id INTEGER NOT NULL,
    device_b_id INTEGER NOT NULL,
    protocol TEXT,
    port INTEGER,
    packet_count INTEGER NOT NULL,
    bytes_total INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_na_link_history_snapshot ON na_link_history(snapshot_id);
CREATE INDEX IF NOT EXISTS idx_na_link_history_pair ON na_link_history(device_a_id, device_b_id);
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
    _ensure_hostname_columns(db_path)
    _ensure_topology_columns(db_path)


def _ensure_hostname_columns(db_path):
    """Migration (livraison #250, "afficher la résolution dns") --
    `hostname`/`hostname_resolved_at` NULLABLES, simple `ALTER TABLE
    ADD COLUMN` (même motif que `imap-client/api/interpreters_store.py`
    #230 -- aucune contrainte NOT NULL à lever, pas besoin de
    reconstruire la table). Idempotente. NULL = jamais encore résolu
    -- traité PAR le thread de résolution en arrière-plan (voir
    app.py), jamais une valeur par défaut trompeuse."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(na_devices)")
        existing_columns = {row[1] for row in cur.fetchall()}
        if "hostname" not in existing_columns:
            cur.execute("ALTER TABLE na_devices ADD COLUMN hostname TEXT")
        if "hostname_resolved_at" not in existing_columns:
            cur.execute("ALTER TABLE na_devices ADD COLUMN hostname_resolved_at TEXT")
        conn.commit()
    finally:
        conn.close()


def _ensure_topology_columns(db_path):
    """Migration (livraison #392, backlog item 58 -- filtres
    "profondeur de voisinage" et "géographie" demandés explicitement
    pour l'interface de netmap-orchestrator) -- même motif NULLABLE/
    ADD COLUMN que _ensure_hostname_columns ci-dessus.

    `network_depth` : notation "pN.M" -- N = nombre de routeurs
    traversés depuis le point d'observation (p0 = même sous-réseau),
    M = nombre de commutateurs traversés à ce même niveau de routeur
    (p0.1 = 1 commutateur, p0 seul = direct sans commutateur
    identifié). PAS mesurée automatiquement par ce module (aucune
    détection de topologie réelle construite ici -- capture passive
    seulement) -- renseignée manuellement ou par un générateur de
    données de démonstration (voir scripts/seed_demo_data.py) pour
    l'instant. NULL = profondeur inconnue, jamais une valeur inventée
    par défaut.

    `building`/`room`/`zone`/`latitude`/`longitude` : géographie
    déclarative, même raisonnement -- ce module ne déduit AUCUNE
    position depuis le trafic réseau lui-même, ces champs restent
    NULL tant que personne (humain ou générateur de démonstration)
    ne les renseigne explicitement."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(na_devices)")
        existing_columns = {row[1] for row in cur.fetchall()}
        new_columns = [
            ("network_depth", "TEXT"),
            ("building", "TEXT"),
            ("room", "TEXT"),
            ("zone", "TEXT"),
            ("latitude", "REAL"),
            ("longitude", "REAL"),
        ]
        for col_name, col_type in new_columns:
            if col_name not in existing_columns:
                cur.execute(f"ALTER TABLE na_devices ADD COLUMN {col_name} {col_type}")
        conn.commit()
    finally:
        conn.close()


def get_or_create_site(conn, name):
    cur = conn.cursor()
    cur.execute("SELECT id FROM na_sites WHERE name = ?", [name])
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute("INSERT INTO na_sites (name, created_at) VALUES (?, ?)", [name, now_iso()])
    return cur.lastrowid


def get_or_create_segment(conn, site_id, label, cidr=None):
    cur = conn.cursor()
    cur.execute("SELECT id FROM na_network_segments WHERE site_id = ? AND label = ?", [site_id, label])
    row = cur.fetchone()
    if row:
        return row["id"]
    cur.execute(
        "INSERT INTO na_network_segments (site_id, label, cidr, created_at) VALUES (?, ?, ?, ?)",
        [site_id, label, cidr, now_iso()],
    )
    return cur.lastrowid


def upsert_device(conn, network_segment_id, mac_address, ip_address, bytes_delta, is_external_relay):
    """Point d'entrée UNIQUE de mise à jour d'un appareil -- appelé
    une fois par paquet où ce MAC apparaît (voir capture.py).
    `first_seen` JAMAIS réécrit sur un appareil déjà connu -- c'est
    précisément ce qui rend la découverte "progressive" (l'ancienneté
    réelle d'un appareil reste visible, jamais remise à zéro)."""
    now = now_iso()
    cur = conn.cursor()
    cur.execute(
        "SELECT id, packet_count, bytes_total, external_relay_count FROM na_devices WHERE network_segment_id = ? AND mac_address = ?",
        [network_segment_id, mac_address],
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            """INSERT INTO na_devices
               (network_segment_id, mac_address, ip_address, first_seen, last_seen, packet_count, bytes_total, external_relay_count)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
            [network_segment_id, mac_address, ip_address, now, now, bytes_delta, 1 if is_external_relay else 0],
        )
        return cur.lastrowid
    device_id = row["id"]
    cur.execute(
        """UPDATE na_devices SET ip_address = COALESCE(?, ip_address), last_seen = ?,
           packet_count = packet_count + 1, bytes_total = bytes_total + ?,
           external_relay_count = external_relay_count + ?
           WHERE id = ?""",
        [ip_address, now, bytes_delta, 1 if is_external_relay else 0, device_id],
    )
    return device_id


def upsert_remote_ip(conn, network_segment_id, via_device_id, ip_address, direction, bytes_delta):
    """IP hors segment vue derrière `via_device_id` (livraison #427) --
    même motif UPSERT que les autres compteurs cumulatifs."""
    now = now_iso()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM na_remote_ips WHERE network_segment_id = ? AND via_device_id = ? AND ip_address = ? AND direction = ?",
        [network_segment_id, via_device_id, ip_address, direction],
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            """INSERT INTO na_remote_ips (network_segment_id, via_device_id, ip_address, direction, first_seen, last_seen, packet_count, bytes_total)
               VALUES (?, ?, ?, ?, ?, ?, 1, ?)""",
            [network_segment_id, via_device_id, ip_address, direction, now, now, bytes_delta],
        )
        return
    cur.execute(
        "UPDATE na_remote_ips SET last_seen = ?, packet_count = packet_count + 1, bytes_total = bytes_total + ? WHERE id = ?",
        [now, bytes_delta, row["id"]],
    )


def upsert_device_service(conn, device_id, protocol, port):
    now = now_iso()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM na_device_services WHERE device_id = ? AND protocol = ? AND port = ?",
        [device_id, protocol, port],
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            """INSERT INTO na_device_services (device_id, protocol, port, first_seen, last_seen, packet_count)
               VALUES (?, ?, ?, ?, ?, 1)""",
            [device_id, protocol, port, now, now],
        )
        return
    cur.execute(
        "UPDATE na_device_services SET last_seen = ?, packet_count = packet_count + 1 WHERE id = ?",
        [now, row["id"]],
    )


def upsert_device_link(conn, network_segment_id, device_a_id, device_b_id, bytes_delta):
    """Enregistre/met à jour un échange DIRECTIONNEL device_a -> device_b
    (livraison #250) -- même motif UPSERT que `upsert_device_service`."""
    now = now_iso()
    cur = conn.cursor()
    cur.execute(
        "SELECT id FROM na_device_links WHERE network_segment_id = ? AND device_a_id = ? AND device_b_id = ?",
        [network_segment_id, device_a_id, device_b_id],
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            """INSERT INTO na_device_links
               (network_segment_id, device_a_id, device_b_id, packet_count, bytes_total, first_seen, last_seen)
               VALUES (?, ?, ?, 1, ?, ?, ?)""",
            [network_segment_id, device_a_id, device_b_id, bytes_delta, now, now],
        )
        return
    cur.execute(
        "UPDATE na_device_links SET last_seen = ?, packet_count = packet_count + 1, bytes_total = bytes_total + ? WHERE id = ?",
        [now, bytes_delta, row["id"]],
    )


def list_device_links(db_path, network_segment_id):
    """Renvoie les échanges d'un segment, triés par volume décroissant
    -- les conversations les plus significatives en premier."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM na_device_links WHERE network_segment_id = ? ORDER BY bytes_total DESC",
            [network_segment_id],
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def upsert_device_link_service(conn, network_segment_id, device_a_id, device_b_id, protocol, port, bytes_delta):
    """Service utilisé DANS un échange device_a -> device_b (livraison
    #251, "services connectés par paire d'ip") -- même motif UPSERT
    que les autres compteurs cumulatifs de ce module."""
    now = now_iso()
    cur = conn.cursor()
    cur.execute(
        """SELECT id FROM na_device_link_services
           WHERE network_segment_id = ? AND device_a_id = ? AND device_b_id = ? AND protocol = ? AND port = ?""",
        [network_segment_id, device_a_id, device_b_id, protocol, port],
    )
    row = cur.fetchone()
    if row is None:
        cur.execute(
            """INSERT INTO na_device_link_services
               (network_segment_id, device_a_id, device_b_id, protocol, port, packet_count, bytes_total, first_seen, last_seen)
               VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)""",
            [network_segment_id, device_a_id, device_b_id, protocol, port, bytes_delta, now, now],
        )
        return
    cur.execute(
        "UPDATE na_device_link_services SET last_seen = ?, packet_count = packet_count + 1, bytes_total = bytes_total + ? WHERE id = ?",
        [now, bytes_delta, row["id"]],
    )


def list_device_link_services(db_path, device_a_id, device_b_id):
    """Services utilisés dans les échanges ENTRE deux appareils
    précis (dans les deux sens -- A->B ET B->A, la personne veut voir
    "les services connectés PAR PAIRE", pas par direction)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT * FROM na_device_link_services
               WHERE (device_a_id = ? AND device_b_id = ?) OR (device_a_id = ? AND device_b_id = ?)
               ORDER BY bytes_total DESC""",
            [device_a_id, device_b_id, device_b_id, device_a_id],
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def take_snapshot(db_path, network_segment_id):
    """Relevé PONCTUEL de l'état cumulatif actuel (livraison #251,
    "rémanence" -- voir docstring du schéma pour le raisonnement
    complet : copie des compteurs CUMULATIFS, jamais un delta stocké
    ici). Appelé périodiquement par le thread de fond (voir app.py).
    Renvoie l'id du relevé créé."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        now = now_iso()
        cur.execute(
            "INSERT INTO na_history_snapshots (network_segment_id, snapshot_at) VALUES (?, ?)",
            [network_segment_id, now],
        )
        snapshot_id = cur.lastrowid

        cur.execute("SELECT id, ip_address, packet_count, bytes_total, last_seen FROM na_devices WHERE network_segment_id = ?", [network_segment_id])
        for row in cur.fetchall():
            cur.execute(
                """INSERT INTO na_device_presence_history
                   (snapshot_id, device_id, ip_address, packet_count, bytes_total, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                [snapshot_id, row["id"], row["ip_address"], row["packet_count"], row["bytes_total"], row["last_seen"]],
            )

        cur.execute(
            "SELECT device_a_id, device_b_id, protocol, port, packet_count, bytes_total FROM na_device_link_services WHERE network_segment_id = ?",
            [network_segment_id],
        )
        for row in cur.fetchall():
            cur.execute(
                """INSERT INTO na_link_history
                   (snapshot_id, device_a_id, device_b_id, protocol, port, packet_count, bytes_total)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                [snapshot_id, row["device_a_id"], row["device_b_id"], row["protocol"], row["port"], row["packet_count"], row["bytes_total"]],
            )
        conn.commit()
        return snapshot_id
    finally:
        conn.close()


def purge_old_snapshots(db_path, older_than_iso):
    """Retenue VOLONTAIREMENT bornée -- supprime les relevés (et leurs
    lignes de présence/historique de liens, via la contrainte de
    clé étrangère logique -- SQLite ne fait PAS de CASCADE par
    défaut, suppression explicite ici) plus anciens que
    `older_than_iso`. Renvoie le nombre de relevés supprimés."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM na_history_snapshots WHERE snapshot_at < ?", [older_than_iso])
        old_ids = [row["id"] for row in cur.fetchall()]
        if not old_ids:
            return 0
        placeholders = ",".join("?" * len(old_ids))
        cur.execute(f"DELETE FROM na_device_presence_history WHERE snapshot_id IN ({placeholders})", old_ids)
        cur.execute(f"DELETE FROM na_link_history WHERE snapshot_id IN ({placeholders})", old_ids)
        cur.execute(f"DELETE FROM na_history_snapshots WHERE id IN ({placeholders})", old_ids)
        conn.commit()
        return len(old_ids)
    finally:
        conn.close()


def list_presence_history(db_path, device_id):
    """Évolution de la présence d'UN appareil dans le temps -- une
    ligne par relevé où il était connu (pas nécessairement ACTIF
    depuis le relevé précédent -- voir `last_seen` dans chaque ligne
    pour distinguer présence continue d'un simple enregistrement
    résiduel)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT h.snapshot_at, p.ip_address, p.packet_count, p.bytes_total, p.last_seen
               FROM na_device_presence_history p
               JOIN na_history_snapshots h ON h.id = p.snapshot_id
               WHERE p.device_id = ?
               ORDER BY h.snapshot_at ASC""",
            [device_id],
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def list_devices_for_period(db_path, network_segment_id, start_iso, end_iso):
    """Livraison #394, backlog item 58 -- dernier des 4 filtres
    demandés ("période temporelle"), volontairement différé en #392
    (nature de requête différente des 3 autres, qui portent sur
    l'état ACTUEL cumulatif). Pour CHAQUE appareil du segment, calcule
    le volume ÉCHANGÉ PENDANT la période [start_iso, end_iso[ --
    PAR DIFFÉRENCE entre le relevé le plus proche (sans le dépasser)
    de `end_iso` et celui le plus proche (sans le dépasser) de
    `start_iso` -- même principe que `/traffic-rate` sur snmp-api
    (#384), un compteur cumulatif brut ne répond pas à "combien
    PENDANT cette période", seule une différence entre deux points le
    fait.

    Un appareil SANS relevé avant `start_iso` (apparu PENDANT la
    période) utilise 0 comme référence de départ -- son volume "dans
    la période" est alors son cumul total au dernier relevé de la
    période, pas une valeur manquante. Un appareil sans AUCUN relevé
    dans l'intervalle [start_iso, end_iso] est OMIS du résultat
    (aucune activité connue sur cette période précise, jamais une
    valeur inventée)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM na_devices WHERE network_segment_id = ?", [network_segment_id])
        devices = {row["id"]: dict(row) for row in cur.fetchall()}
        if not devices:
            return []

        # Un seul aller-retour BDD pour tous les appareils du segment
        # -- jamais une requête par appareil, qui grossirait linéairement.
        cur.execute(
            """SELECT p.device_id, h.snapshot_at, p.bytes_total, p.packet_count
               FROM na_device_presence_history p
               JOIN na_history_snapshots h ON h.id = p.snapshot_id
               WHERE h.network_segment_id = ? AND h.snapshot_at <= ?
               ORDER BY p.device_id, h.snapshot_at ASC""",
            [network_segment_id, end_iso],
        )
        by_device = {}
        for row in cur.fetchall():
            by_device.setdefault(row["device_id"], []).append(dict(row))

        results = []
        for device_id, readings in by_device.items():
            if device_id not in devices:
                continue
            # Dernier relevé <= end_iso (garanti par la requête SQL
            # ci-dessus, juste le dernier de la liste triée).
            end_reading = readings[-1]
            if end_reading["snapshot_at"] < start_iso:
                continue  # aucun relevé DANS la période -- omis, jamais une valeur inventée
            # Dernier relevé <= start_iso (référence de départ) --
            # 0 si aucun (appareil apparu PENDANT la période).
            baseline = 0
            baseline_packets = 0
            for r in readings:
                if r["snapshot_at"] <= start_iso:
                    baseline = r["bytes_total"]
                    baseline_packets = r["packet_count"]
                else:
                    break
            device = dict(devices[device_id])
            device["bytes_total_period"] = max(0, end_reading["bytes_total"] - baseline)
            device["packet_count_period"] = max(0, end_reading["packet_count"] - baseline_packets)
            results.append(device)
        return results
    finally:
        conn.close()


def list_device_links_for_period(db_path, network_segment_id, start_iso, end_iso):
    """Livraison #414 -- fenêtre temporelle sur les FLUX (« filtre sur
    fenêtre temporelle » du retour de tests), même principe que
    `list_devices_for_period` (#394) : pour chaque paire (A -> B) du
    segment, volume échangé PENDANT [start_iso, end_iso] = différence entre
    le dernier relevé <= end_iso et le dernier relevé <= start_iso (0 si la
    paire est apparue pendant la période), sommée sur les services
    (protocole/port) de la paire -- `na_link_history` est un relevé de
    `na_device_link_services`, pas de `na_device_links`. Une paire sans
    aucun relevé dans la période est omise, jamais une valeur inventée.

    Même forme de ligne que `list_device_links` (device_a_id, device_b_id,
    packet_count, bytes_total) avec `period: True`, pour que le hub
    applique les mêmes filtres et les mêmes vues sans cas particulier."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT l.device_a_id, l.device_b_id, l.protocol, l.port, h.snapshot_at, l.packet_count, l.bytes_total
               FROM na_link_history l
               JOIN na_history_snapshots h ON h.id = l.snapshot_id
               WHERE h.network_segment_id = ? AND h.snapshot_at <= ?
               ORDER BY l.device_a_id, l.device_b_id, l.protocol, l.port, h.snapshot_at ASC""",
            [network_segment_id, end_iso],
        )
        series = {}
        for row in cur.fetchall():
            key = (row["device_a_id"], row["device_b_id"], row["protocol"], row["port"])
            series.setdefault(key, []).append(dict(row))

        totals = {}
        for (a, b, _protocol, _port), readings in series.items():
            end_reading = readings[-1]
            if end_reading["snapshot_at"] < start_iso:
                continue  # aucun relevé dans la période pour ce service
            baseline_bytes = 0
            baseline_packets = 0
            for r in readings:
                if r["snapshot_at"] <= start_iso:
                    baseline_bytes = r["bytes_total"]
                    baseline_packets = r["packet_count"]
                else:
                    break
            entry = totals.setdefault((a, b), {"device_a_id": a, "device_b_id": b, "bytes_total": 0, "packet_count": 0, "period": True})
            entry["bytes_total"] += max(0, end_reading["bytes_total"] - baseline_bytes)
            entry["packet_count"] += max(0, end_reading["packet_count"] - baseline_packets)

        results = list(totals.values())
        for i, r in enumerate(results):
            # Identifiant stable pour les clés React : pas de ligne en base
            # derrière un flux « de période », l'id est synthétique.
            r["id"] = f"period-{r['device_a_id']}-{r['device_b_id']}"
        results.sort(key=lambda r: r["bytes_total"], reverse=True)
        return results
    finally:
        conn.close()


def list_link_history(db_path, device_a_id, device_b_id):
    """Évolution du volume échangé entre DEUX appareils précis, dans
    le temps -- une ligne CUMULATIVE par relevé (jamais un delta
    stocké, voir `take_snapshot`) ; calculer un delta entre deux
    points est la responsabilité de la lecture (hub), jamais figé
    ici à un pas de temps fixe."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT h.snapshot_at, l.protocol, l.port, l.packet_count, l.bytes_total
               FROM na_link_history l
               JOIN na_history_snapshots h ON h.id = l.snapshot_id
               WHERE (l.device_a_id = ? AND l.device_b_id = ?) OR (l.device_a_id = ? AND l.device_b_id = ?)
               ORDER BY h.snapshot_at ASC""",
            [device_a_id, device_b_id, device_b_id, device_a_id],
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def apply_role_hints(conn, network_segment_id, relay_threshold=5):
    """Passe de post-traitement -- un appareil dont
    `external_relay_count` dépasse `relay_threshold` reçoit le
    `role_hint` "passerelle probable (NAT/routeur)" : il a servi de
    relais MAC pour du trafic dont l'IP finale sort du segment assez
    souvent pour ne pas être une coïncidence (voir capture.py pour le
    raisonnement complet de cette détection). Seuil VOLONTAIREMENT
    bas -- mieux vaut un faux positif signalé que silencieux, une
    hypothèse à confirmer humainement, jamais une certitude
    affichée."""
    cur = conn.cursor()
    cur.execute(
        """UPDATE na_devices SET role_hint = 'passerelle probable (NAT/routeur)'
           WHERE network_segment_id = ? AND external_relay_count >= ? AND role_hint IS NULL""",
        [network_segment_id, relay_threshold],
    )


def list_devices(db_path, network_segment_id=None, depths=None, building=None, room=None, zone=None, min_bytes_total=None):
    """Livraison #392 -- filtres ajoutés pour l'interface de
    netmap-orchestrator (backlog item 58) : `depths` (liste de
    valeurs `network_depth` exactes, ex. ["p0", "p0.1"] -- OU logique
    entre elles), `building`/`room`/`zone` (correspondance EXACTE,
    jamais une recherche floue ici -- ces champs sont déclaratifs,
    pas du texte libre à deviner), `min_bytes_total` (volume minimum,
    filtre les appareils avec MOINS que ça). Tous optionnels, aucun
    changement de comportement si aucun n'est fourni (non-régression
    du seul filtre existant, `network_segment_id`)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        clauses, params = [], []
        if network_segment_id:
            clauses.append("network_segment_id = ?")
            params.append(network_segment_id)
        if depths:
            placeholders = ",".join("?" * len(depths))
            clauses.append(f"network_depth IN ({placeholders})")
            params.extend(depths)
        if building:
            clauses.append("building = ?")
            params.append(building)
        if room:
            clauses.append("room = ?")
            params.append(room)
        if zone:
            clauses.append("zone = ?")
            params.append(zone)
        if min_bytes_total is not None:
            clauses.append("bytes_total >= ?")
            params.append(min_bytes_total)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cur.execute(f"SELECT * FROM na_devices {where_sql} ORDER BY last_seen DESC", params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def list_filter_options(db_path, network_segment_id=None):
    """Valeurs DISTINCTES réellement présentes (profondeurs,
    bâtiments, salles, zones) -- pour peupler les filtres côté
    interface avec ce qui existe VRAIMENT plutôt qu'une liste
    devinée/codée en dur (livraison #392). NULL toujours exclu (une
    valeur non renseignée n'est jamais une "option" de filtre
    valide)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        where_sql = "WHERE network_segment_id = ?" if network_segment_id else ""
        params = [network_segment_id] if network_segment_id else []

        def distinct_values(column):
            cur.execute(
                f"SELECT DISTINCT {column} FROM na_devices {where_sql}"
                f"{' AND' if where_sql else 'WHERE'} {column} IS NOT NULL ORDER BY {column}",
                params,
            )
            return [row[0] for row in cur.fetchall()]

        return {
            "depths": distinct_values("network_depth"),
            "buildings": distinct_values("building"),
            "rooms": distinct_values("room"),
            "zones": distinct_values("zone"),
        }
    finally:
        conn.close()


def _segment_cidr(cur, network_segment_id):
    cur.execute("SELECT cidr FROM na_network_segments WHERE id = ?", [network_segment_id])
    row = cur.fetchone()
    return row["cidr"] if row and row["cidr"] else None


def _in_cidr(subnet, cidr):
    if not cidr:
        return None
    try:
        return ipaddress.ip_network(subnet, strict=False).subnet_of(ipaddress.ip_network(cidr, strict=False))
    except (ValueError, TypeError):
        return None


def list_observed_subnets(db_path, network_segment_id, prefix_length=24):
    """Découverte de sous-réseaux DEPUIS LE TRAFIC OBSERVÉ (livraison
    #256, demandé explicitement -- "notre module d'exploration doit
    répondre à cette question [combien de segments réseau distincts
    faut-il couvrir]" -- backlog item 21, préparation GLPI Inventory).
    Plutôt que d'exiger que la personne connaisse déjà tous ses
    sous-réseaux à l'avance, ce module les REGROUPE lui-même depuis
    les adresses IP déjà vues -- un supernet configuré large (ex. le
    /16 réel de la personne) laisse apparaître sa STRUCTURE INTERNE
    réelle (les /24 effectivement en usage) à mesure que la capture
    avance.

    Livraison #427 : DEUX origines, distinguées -- les IP des appareils
    du segment (MAC vue : `device_count`) et les IP DISTANTES vues
    derrière un relais (`na_remote_ips` : `remote_ip_count`, `via` =
    relais) ; `origin` = local | relais | mixte ; `in_segment` = le
    sous-réseau est dans le CIDR configuré (None si pas de CIDR). C'est
    la réponse à « je vois d'autres sous-réseaux que le LAN immédiat, mais
    aucune de leurs IP dans les appareils découverts » : elles ne sont pas
    des appareils, elles sont derrière la passerelle.

    Calcul PUREMENT en lecture, groupé côté Python via `ipaddress`.
    `prefix_length` (défaut 24) -- granularité du regroupement. Tri par
    nombre d'adresses décroissant. IP malformées IGNORÉES proprement."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cidr = _segment_cidr(cur, network_segment_id)
        cur.execute(
            "SELECT ip_address, first_seen, last_seen FROM na_devices WHERE network_segment_id = ? AND ip_address IS NOT NULL",
            [network_segment_id],
        )
        local_rows = cur.fetchall()
        cur.execute(
            """SELECT r.ip_address, r.first_seen, r.last_seen, r.packet_count, r.direction,
                      d.mac_address AS via_mac, d.ip_address AS via_ip, d.hostname AS via_hostname
               FROM na_remote_ips r JOIN na_devices d ON d.id = r.via_device_id
               WHERE r.network_segment_id = ?""",
            [network_segment_id],
        )
        remote_rows = cur.fetchall()
    finally:
        conn.close()

    grouped = {}

    def entry_for(ip):
        try:
            network = ipaddress.ip_network(f"{ip}/{prefix_length}", strict=False)
        except ValueError:
            return None  # IP malformée/inattendue -- ignorée, jamais une exception qui casse toute la liste
        key = str(network)
        if key not in grouped:
            grouped[key] = {"subnet": key, "device_count": 0, "remote_ip_count": 0, "packet_count": 0, "first_seen": None, "last_seen": None,
                            "via": [], "in_segment": _in_cidr(key, cidr), "_remote_ips": set()}
        return grouped[key]

    def touch(e, first, last):
        e["first_seen"] = first if e["first_seen"] is None else min(e["first_seen"], first)
        e["last_seen"] = last if e["last_seen"] is None else max(e["last_seen"], last)

    for row in local_rows:
        e = entry_for(row["ip_address"])
        if e is None:
            continue
        e["device_count"] += 1
        touch(e, row["first_seen"], row["last_seen"])
    for row in remote_rows:
        e = entry_for(row["ip_address"])
        if e is None:
            continue
        e["_remote_ips"].add(row["ip_address"])
        e["packet_count"] += row["packet_count"]
        touch(e, row["first_seen"], row["last_seen"])
        via = row["via_hostname"] or row["via_ip"] or row["via_mac"]
        if via not in e["via"]:
            e["via"].append(via)

    out = []
    for e in grouped.values():
        e["remote_ip_count"] = len(e.pop("_remote_ips"))
        e["origin"] = "mixte" if e["device_count"] and e["remote_ip_count"] else ("local" if e["device_count"] else "relais")
        out.append(e)
    return sorted(out, key=lambda e: -(e["device_count"] + e["remote_ip_count"]))


def subnet_detail(db_path, network_segment_id, subnet):
    """Fiche récapitulative d'UN sous-réseau (livraison #427) : d'où il
    vient (segment configuré, appareils locaux, relais), les IP vues (avec
    l'appareil ou le relais, le sens, les volumes), les services de ses
    appareils, les échanges qui le concernent, premières/dernières vues.
    `subnet` en notation CIDR ; IP malformées ignorées."""
    try:
        net = ipaddress.ip_network(subnet, strict=False)
    except ValueError:
        return None

    def inside(ip):
        try:
            return ipaddress.ip_address(ip) in net
        except (ValueError, TypeError):
            return False

    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cidr = _segment_cidr(cur, network_segment_id)
        cur.execute("SELECT s.label, s.cidr, si.name AS site FROM na_network_segments s JOIN na_sites si ON si.id = s.site_id WHERE s.id = ?", [network_segment_id])
        seg = cur.fetchone()
        cur.execute("SELECT * FROM na_devices WHERE network_segment_id = ? AND ip_address IS NOT NULL", [network_segment_id])
        devices = [dict(r) for r in cur.fetchall() if inside(r["ip_address"])]
        device_ids = [d["id"] for d in devices]
        services = []
        if device_ids:
            q = ",".join("?" * len(device_ids))
            cur.execute(f"SELECT device_id, protocol, port, packet_count, last_seen FROM na_device_services WHERE device_id IN ({q}) ORDER BY packet_count DESC", device_ids)
            services = [dict(r) for r in cur.fetchall()]
            cur.execute(
                f"""SELECT l.device_a_id, l.device_b_id, l.packet_count, l.bytes_total, l.last_seen,
                           a.ip_address AS a_ip, a.mac_address AS a_mac, a.hostname AS a_hostname,
                           b.ip_address AS b_ip, b.mac_address AS b_mac, b.hostname AS b_hostname
                    FROM na_device_links l JOIN na_devices a ON a.id = l.device_a_id JOIN na_devices b ON b.id = l.device_b_id
                    WHERE l.network_segment_id = ? AND (l.device_a_id IN ({q}) OR l.device_b_id IN ({q}))
                    ORDER BY l.bytes_total DESC LIMIT 200""",
                [network_segment_id, *device_ids, *device_ids],
            )
            links = [dict(r) for r in cur.fetchall()]
        else:
            links = []
        cur.execute(
            """SELECT r.ip_address, r.direction, r.first_seen, r.last_seen, r.packet_count, r.bytes_total,
                      d.id AS via_id, d.mac_address AS via_mac, d.ip_address AS via_ip, d.hostname AS via_hostname, d.role_hint AS via_role
               FROM na_remote_ips r JOIN na_devices d ON d.id = r.via_device_id
               WHERE r.network_segment_id = ? ORDER BY r.bytes_total DESC""",
            [network_segment_id],
        )
        remote = [dict(r) for r in cur.fetchall() if inside(r["ip_address"])]
    finally:
        conn.close()

    ips = {}
    for d in devices:
        ips[d["ip_address"]] = {"ip": d["ip_address"], "kind": "appareil", "mac": d["mac_address"], "hostname": d.get("hostname"),
                                "first_seen": d["first_seen"], "last_seen": d["last_seen"], "packet_count": d["packet_count"], "bytes_total": d["bytes_total"], "via": None, "directions": []}
    for r in remote:
        e = ips.setdefault(r["ip_address"], {"ip": r["ip_address"], "kind": "distante", "mac": None, "hostname": None, "first_seen": r["first_seen"], "last_seen": r["last_seen"],
                                             "packet_count": 0, "bytes_total": 0, "via": None, "directions": []})
        if e["kind"] == "distante":
            e["packet_count"] += r["packet_count"]; e["bytes_total"] += r["bytes_total"]
            e["first_seen"] = min(e["first_seen"], r["first_seen"]); e["last_seen"] = max(e["last_seen"], r["last_seen"])
            e["via"] = r["via_hostname"] or r["via_ip"] or r["via_mac"]
            if r["direction"] not in e["directions"]:
                e["directions"].append(r["direction"])
    relays = {}
    for r in remote:
        k = r["via_id"]
        relays.setdefault(k, {"device_id": k, "mac": r["via_mac"], "ip": r["via_ip"], "hostname": r["via_hostname"], "role_hint": r["via_role"], "ip_count": 0, "bytes_total": 0})
        relays[k]["ip_count"] += 1
        relays[k]["bytes_total"] += r["bytes_total"]
    all_first = [x["first_seen"] for x in ips.values()]
    all_last = [x["last_seen"] for x in ips.values()]
    in_segment = _in_cidr(str(net), cidr)
    if in_segment:
        explanation = "Sous-réseau inclus dans le CIDR configuré du segment : ses adresses sont des appareils vus directement (MAC connue)."
    elif in_segment is False:
        explanation = ("Sous-réseau HORS du CIDR configuré : ses adresses ont été vues comme sources ou destinations de paquets relayés par une "
                       "passerelle du segment -- ce ne sont pas des appareils du LAN immédiat, elles n'apparaissent donc pas dans la table des découvertes.")
    else:
        explanation = ("Aucun CIDR configuré sur ce segment (NETWORK_AGENT_SEGMENT_CIDR) : local et distant ne peuvent pas être distingués -- "
                       "les IP publiques sont traitées comme distantes, le reste est attribué à la MAC qui le porte.")
    if not devices and not remote:
        explanation += " Aucune adresse de ce sous-réseau n'est connue avec cette granularité."
    return {
        "subnet": str(net), "segment": dict(seg) if seg else None, "segment_cidr": cidr, "in_segment": in_segment, "explanation": explanation,
        "device_count": len(devices), "remote_ip_count": sum(1 for x in ips.values() if x["kind"] == "distante"),
        "first_seen": min(all_first) if all_first else None, "last_seen": max(all_last) if all_last else None,
        "ips": sorted(ips.values(), key=lambda x: ipaddress.ip_address(x["ip"])),
        "relays": sorted(relays.values(), key=lambda r: -r["bytes_total"]),
        "services": services, "links": links,
        "sources": [x for x, ok in (("appareils du segment (MAC vue, ARP ou trafic)", bool(devices)), ("trafic relayé (IP distantes derrière une passerelle)", bool(remote))) if ok],
    }


def list_devices_needing_dns_resolution(db_path, stale_before_iso, limit=50):
    """Appareils à (re)résoudre -- IP connue, ET (jamais résolu OU
    résolu avant `stale_before_iso`, permettant une RE-résolution
    périodique -- un bail DHCP change, l'ancien nom devient faux sans
    jamais être corrigé sinon). `limit` -- borne le travail d'un seul
    passage du thread de résolution (voir app.py), jamais tous les
    appareils d'un coup sur un grand réseau."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, ip_address FROM na_devices
               WHERE ip_address IS NOT NULL
                 AND (hostname_resolved_at IS NULL OR hostname_resolved_at < ?)
               ORDER BY hostname_resolved_at IS NOT NULL, hostname_resolved_at ASC
               LIMIT ?""",
            [stale_before_iso, limit],
        )
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def update_device_hostname(db_path, device_id, hostname):
    """`hostname` peut être `None` (résolution tentée mais SANS
    résultat -- toujours marqué `hostname_resolved_at` pour éviter de
    ré-essayer en boucle immédiatement, voir la fenêtre de
    fraîcheur ci-dessus)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE na_devices SET hostname = ?, hostname_resolved_at = ? WHERE id = ?",
            [hostname, now_iso(), device_id],
        )
        conn.commit()
    finally:
        conn.close()


def list_device_services(db_path, device_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM na_device_services WHERE device_id = ? ORDER BY packet_count DESC", [device_id])
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def list_services_by_segment(db_path, network_segment_id):
    """Tous les services de TOUS les appareils d'un segment, EN UNE
    SEULE requête (livraison #250) -- évite un appel par appareil
    côté hub pour afficher les points de service sur CHAQUE ligne de
    la liste simultanément (voir NetworkAgentView.jsx). Renvoie
    {device_id: [services triés par volume décroissant]}."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT s.* FROM na_device_services s
               JOIN na_devices d ON d.id = s.device_id
               WHERE d.network_segment_id = ?
               ORDER BY s.device_id, s.packet_count DESC""",
            [network_segment_id],
        )
        rows = [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()
    grouped = {}
    for row in rows:
        grouped.setdefault(row["device_id"], []).append(row)
    return grouped



def list_sites_with_segments(db_path):
    """Structure imbriquée site -> segments, prête pour l'affichage
    hiérarchique côté hub (voir docstring du module -- "on distinguera
    les sites et les réseaux dans l'organisation des données")."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM na_sites ORDER BY name")
        sites = [dict(r) for r in cur.fetchall()]
        for site in sites:
            cur.execute("SELECT * FROM na_network_segments WHERE site_id = ? ORDER BY label", [site["id"]])
            site["segments"] = [dict(r) for r in cur.fetchall()]
        return sites
    finally:
        conn.close()
