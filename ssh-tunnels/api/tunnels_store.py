"""
Persistance des clés/connexions/tunnels/montages SSH (livraison
#159, backlog BACKLOG.md #2). Demandé explicitement : superviser les
tunnels SSH et partages SSHFS, gérer les clés (activer/désactiver/
informer), une interface de montage/démontage -- objectif : accès à
des ressources privées distantes (service redistribué en mode proxy
type rinetd/proxy-delegated, ou système de fichiers distant).

Trois points tranchés avec la personne avant de coder :
- Clés SSH : chemin PROTÉGÉ PARAMÉTRÉ (jamais gérées/générées par ce
  module -- un simple REGISTRE par-dessus des fichiers déjà présents
  sur un volume monté en LECTURE SEULE, voir key_scanner.py).
- SSHFS : "on verra plus tard mais c'est bien de préparer
  l'interface" -- table `ssh_mounts` et routes CRUD présentes dans
  CETTE livraison, mais les actions mount/démontage renvoient
  explicitement "pas encore implémenté", AUCUN montage FUSE réel
  (privilèges élevés requis -- SYS_ADMIN, /dev/fuse -- décision
  explicitement reportée).
- Mode proxy CONFIRMÉ ("rinetd"/"proxy delegated") : un tunnel ouvre
  son port LOCAL sur CE conteneur (réseau Docker partagé), les autres
  API s'y connectent directement par le nom du conteneur -- jamais un
  vrai relais applicatif à construire.

Même motif SQLite que les autres modules de ce projet
(DB_PATH/get_connection/ensure_schema/now_iso).
"""
import sqlite3
import time

SCHEMA = """
-- Registre des clés SSH -- `filename` RELATIF au dossier de clés
-- monté en lecture seule (SSH_KEYS_DIR), JAMAIS un chemin absolu ou
-- construit à la main côté appelant (anti-traversée de chemin, voir
-- key_scanner.py). Ce module ne stocke JAMAIS le contenu d'une clé,
-- seulement des métadonnées à son sujet.
CREATE TABLE IF NOT EXISTS ssh_keys (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL UNIQUE,
    label TEXT,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Connexion SSH réutilisable (hôte/port/utilisateur/clé) -- base
-- commune aux tunnels ET aux montages ci-dessous (une même
-- connexion peut servir aux deux usages).
CREATE TABLE IF NOT EXISTS ssh_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    ssh_host TEXT NOT NULL,
    ssh_port INTEGER NOT NULL DEFAULT 22,
    ssh_user TEXT NOT NULL,
    ssh_key_id INTEGER NOT NULL REFERENCES ssh_keys(id),
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Tunnel `ssh -L` (redirection de port locale) -- `local_port` UNIQUE
-- : jamais deux tunnels sur le même port local en même temps (ce
-- conteneur écoute sur ce port pour le mode proxy). `pid` : stocké en
-- BASE (pas seulement en mémoire du processus qui l'a lancé) --
-- CRITIQUE avec 2 workers Gunicorn qui ne partagent pas leur mémoire
-- (même problème que les logs avant #145, mais pas résoluble de la
-- même façon pour un VRAI processus OS -- voir ssh-tunnels/README.md
-- pour le choix assumé : 1 seul worker pour ce service précis).
CREATE TABLE IF NOT EXISTS ssh_tunnels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id INTEGER NOT NULL REFERENCES ssh_connections(id),
    label TEXT NOT NULL,
    remote_host TEXT NOT NULL,
    remote_port INTEGER NOT NULL,
    local_port INTEGER NOT NULL UNIQUE,
    pid INTEGER,
    status TEXT NOT NULL DEFAULT 'stopped',
    last_error TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Montage SSHFS -- action RÉELLE depuis #180 (interface préparée
-- seule depuis #159). `pid`/`last_error` : même motif que
-- ssh_tunnels ci-dessus (processus RÉEL, PID en base -- 2 workers
-- Gunicorn ne partagent pas leur mémoire).
CREATE TABLE IF NOT EXISTS ssh_mounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id INTEGER NOT NULL REFERENCES ssh_connections(id),
    label TEXT NOT NULL,
    remote_path TEXT NOT NULL,
    local_mount_path TEXT NOT NULL,
    pid INTEGER,
    status TEXT NOT NULL DEFAULT 'unmounted',
    last_error TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Historique d'USAGE des identifiants (livraison #210, backlog item
-- 12 -- "avec un historique d'usage (quand, via quelle API/connexion,
-- durée)"). Une ligne PAR TENTATIVE de démarrage (tunnel OU montage),
-- pas seulement les succès -- une tentative échouée fait AUSSI partie
-- de l'historique d'usage demandé. `ended_at` NULL tant que l'action
-- (tunnel/montage) est encore active -- rempli à l'arrêt, permet de
-- calculer une durée a posteriori sans dépendre d'un minuteur actif.
CREATE TABLE IF NOT EXISTS ssh_credential_usage_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    connection_id INTEGER NOT NULL REFERENCES ssh_connections(id),
    action_type TEXT NOT NULL,
    auth_method TEXT NOT NULL,
    success INTEGER NOT NULL,
    error_message TEXT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    created_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_ssh_credential_usage_connection ON ssh_credential_usage_history(connection_id);
"""


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        # Migration (livraison #180, montage SSHFS réel -- ces deux
        # colonnes n'existaient pas quand ssh_mounts a été créée en
        # #159, "interface préparée" seulement) -- même motif
        # idempotent que pixel-grid/api/app.py (PRAGMA table_info,
        # ADD COLUMN seulement si absente, jamais une erreur sur une
        # base déjà migrée).
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(ssh_mounts)")
        existing_columns = {row[1] for row in cur.fetchall()}
        if "pid" not in existing_columns:
            cur.execute("ALTER TABLE ssh_mounts ADD COLUMN pid INTEGER")
        if "last_error" not in existing_columns:
            cur.execute("ALTER TABLE ssh_mounts ADD COLUMN last_error TEXT")
        # Anciennes lignes à "not_implemented" (créées avant #180,
        # l'action réelle n'existait pas encore) -- reclassées
        # "unmounted", leur état RÉEL maintenant que l'action existe
        # (aucun montage actif tant que /mount n'a jamais été appelé
        # dessus).
        cur.execute("UPDATE ssh_mounts SET status = 'unmounted' WHERE status = 'not_implemented'")
        conn.commit()
    finally:
        conn.close()

    ensure_ssh_connections_password_auth_columns(db_path)


def ensure_ssh_connections_password_auth_columns(db_path):
    """Migration (livraison #210, backlog item 12 -- authentification
    SSH par mot de passe) -- `ssh_key_id` doit devenir NULLABLE (une
    connexion par mot de passe n'a pas de clé) et trois colonnes
    ajoutées (`auth_method`, `password_username`, `password_encrypted`).
    SQLite ne permet PAS de modifier une contrainte NOT NULL
    directement (`ALTER TABLE ... ALTER COLUMN` n'existe pas) --
    reconstruction de la table dans une TRANSACTION EXPLICITE (motif
    standard et sûr pour ce genre de migration -- ROLLBACK automatique
    si une étape échoue, jamais de table à moitié migrée). Idempotente
    -- si `auth_method` existe déjà, ne fait rien. Chaque connexion
    EXISTANTE reçoit explicitement `auth_method='key'` (son
    comportement réel actuel, jamais supposé différent)."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(ssh_connections)")
        existing_columns = {row[1] for row in cur.fetchall()}
        if "auth_method" in existing_columns:
            return
        cur.execute("BEGIN")
        cur.execute("""
            CREATE TABLE ssh_connections_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                label TEXT NOT NULL,
                ssh_host TEXT NOT NULL,
                ssh_port INTEGER NOT NULL DEFAULT 22,
                ssh_user TEXT NOT NULL,
                ssh_key_id INTEGER REFERENCES ssh_keys(id),
                auth_method TEXT NOT NULL DEFAULT 'key',
                password_username TEXT,
                password_encrypted TEXT,
                created_by TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            INSERT INTO ssh_connections_new
                (id, label, ssh_host, ssh_port, ssh_user, ssh_key_id, auth_method, created_by, created_at, updated_at)
            SELECT id, label, ssh_host, ssh_port, ssh_user, ssh_key_id, 'key', created_by, created_at, updated_at
            FROM ssh_connections
        """)
        cur.execute("DROP TABLE ssh_connections")
        cur.execute("ALTER TABLE ssh_connections_new RENAME TO ssh_connections")
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ------------------------------------------------------------------
# Clés SSH -- registre par-dessus des fichiers déjà présents (voir
# key_scanner.py pour la découverte elle-même) -- ce module gère
# uniquement les MÉTADONNÉES (label, enabled), jamais le contenu.
# ------------------------------------------------------------------
def upsert_key(db_path, filename, label=None, created_by=None):
    """Enregistre une clé DÉCOUVERTE sur le disque si elle n'est pas
    déjà connue (voir key_scanner.py, appelé à chaque listage) --
    JAMAIS créée depuis une saisie utilisateur libre. `enabled=1` par
    défaut à la découverte -- une clé nouvellement trouvée est
    utilisable tout de suite, pas besoin d'un geste explicite en plus
    du dépôt du fichier lui-même sur le volume."""
    now = now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM ssh_keys WHERE filename = ?", [filename])
        existing = cur.fetchone()
        if existing:
            return existing["id"]
        cur.execute(
            "INSERT INTO ssh_keys (filename, label, enabled, created_by, created_at, updated_at) VALUES (?, ?, 1, ?, ?, ?)",
            [filename, label or filename, created_by, now, now],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_keys(db_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ssh_keys ORDER BY label")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_key(db_path, key_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ssh_keys WHERE id = ?", [key_id])
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def set_key_enabled(db_path, key_id, enabled):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE ssh_keys SET enabled = ?, updated_at = ? WHERE id = ?", [1 if enabled else 0, now_iso(), key_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def remove_keys_not_in(db_path, present_filenames):
    """Retire du registre les clés dont le FICHIER a disparu du
    disque (appelé après un scan complet, voir key_scanner.py) --
    jamais l'inverse (un fichier présent mais pas encore en base est
    ajouté par upsert_key, jamais supprimé ici)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if not present_filenames:
            cur.execute("SELECT id FROM ssh_keys")
        else:
            placeholders = ",".join("?" * len(present_filenames))
            cur.execute(f"SELECT id FROM ssh_keys WHERE filename NOT IN ({placeholders})", present_filenames)
        stale_ids = [r["id"] for r in cur.fetchall()]
        for key_id in stale_ids:
            cur.execute("DELETE FROM ssh_keys WHERE id = ?", [key_id])
        conn.commit()
        return stale_ids
    finally:
        conn.close()


def connections_using_key(db_path, key_id):
    """Connexions RÉFÉRENÇANT encore cette clé (livraison #277,
    "permettre la suppression des clés ssh sans aucune sauvegarde
    surtout") -- vérifié AVANT toute suppression réelle : supprimer
    le fichier d'une clé encore utilisée par une connexion active
    casserait cette connexion silencieusement (sans que la personne
    le sache avant le prochain échec de tunnel/montage) -- jamais
    voulu, même en l'absence de sauvegarde demandée explicitement
    (la demande porte sur l'absence de COPIE conservée, pas sur
    l'absence de vérification de sécurité élémentaire)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, label FROM ssh_connections WHERE ssh_key_id = ?", [key_id])
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def delete_key_registry(db_path, key_id):
    """Retire UNIQUEMENT la ligne de registre -- la suppression du
    FICHIER lui-même (aucune sauvegarde, demandé explicitement) est
    la responsabilité de l'appelant (voir app.py -- l'ordre est
    délibéré : fichier supprimé D'ABORD, registre ENSUITE, pour
    qu'un échec de suppression du fichier laisse la clé encore
    visible plutôt qu'un registre incohérent avec un fichier
    orphelin)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM ssh_keys WHERE id = ?", [key_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ------------------------------------------------------------------
# Connexions SSH
# ------------------------------------------------------------------
def create_connection(db_path, label, ssh_host, ssh_port, ssh_user, ssh_key_id, created_by=None,
                       auth_method="key", password_username=None, password_encrypted=None):
    """`auth_method="password"` (livraison #210) -- `ssh_key_id` doit
    alors être `None` (une connexion par mot de passe n'a pas de clé),
    `password_encrypted` déjà chiffré par l'APPELANT (voir app.py,
    `credential_crypto.encrypt_password`) -- cette fonction ne
    chiffre JAMAIS rien elle-même, ne reçoit qu'un jeton déjà prêt à
    stocker."""
    now = now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO ssh_connections
               (label, ssh_host, ssh_port, ssh_user, ssh_key_id, auth_method, password_username, password_encrypted, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [label, ssh_host, ssh_port, ssh_user, ssh_key_id, auth_method, password_username, password_encrypted, created_by, now, now],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def record_credential_usage(db_path, connection_id, action_type, auth_method, success, error_message=None, created_by=None):
    """Historique d'usage (livraison #210) -- UNE ligne par tentative
    de démarrage (tunnel OU montage), succès OU échec. Renvoie l'id
    de la ligne créée -- l'appelant peut ensuite appeler
    `close_credential_usage` pour renseigner `ended_at` quand l'action
    s'arrête, si elle a réussi (jamais pour une tentative déjà en
    échec, qui n'a rien à "fermer")."""
    now = now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO ssh_credential_usage_history
               (connection_id, action_type, auth_method, success, error_message, started_at, created_by)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [connection_id, action_type, auth_method, 1 if success else 0, error_message, now, created_by],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def close_credential_usage(db_path, usage_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("UPDATE ssh_credential_usage_history SET ended_at = ? WHERE id = ?", [now_iso(), usage_id])
        conn.commit()
    finally:
        conn.close()


def close_latest_open_usage(db_path, connection_id, action_type):
    """Ferme la PLUS RÉCENTE entrée d'usage encore ouverte
    (`ended_at IS NULL`) pour cette connexion/type d'action --
    heuristique simple (pas de référence directe stockée entre le
    démarrage et l'arrêt, pour éviter une colonne supplémentaire sur
    `ssh_tunnels`/`ssh_mounts`) -- suffisante tant que les tunnels/
    montages d'une même connexion ne sont pas démarrés/arrêtés en
    parallèle de façon chevauchée, jamais le cas dans l'usage normal
    de ce module (un seul tunnel actif par connexion à la fois en
    pratique). Silencieux si aucune entrée ouverte -- jamais bloquant
    pour l'appelant (arrêt d'un tunnel qui n'a pas d'historique
    d'usage, ex. créé avant #210)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id FROM ssh_credential_usage_history
               WHERE connection_id = ? AND action_type = ? AND ended_at IS NULL
               ORDER BY id DESC LIMIT 1""",
            [connection_id, action_type],
        )
        row = cur.fetchone()
        if row is None:
            return
        cur.execute("UPDATE ssh_credential_usage_history SET ended_at = ? WHERE id = ?", [now_iso(), row["id"]])
        conn.commit()
    finally:
        conn.close()


def list_credential_usage(db_path, connection_id=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if connection_id is not None:
            cur.execute("SELECT * FROM ssh_credential_usage_history WHERE connection_id = ? ORDER BY id DESC", [connection_id])
        else:
            cur.execute("SELECT * FROM ssh_credential_usage_history ORDER BY id DESC LIMIT 500")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def list_connections(db_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ssh_connections ORDER BY label")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_connection_row(db_path, connection_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ssh_connections WHERE id = ?", [connection_id])
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_connection(db_path, connection_id):
    """Refuse la suppression si des tunnels/montages en dépendent
    ENCORE (contrainte FOREIGN KEY, PRAGMA foreign_keys=ON activé à
    la connexion) -- renvoie False dans ce cas plutôt qu'une
    sqlite3.IntegrityError brute. Jamais de suppression en cascade
    silencieuse ici : un tunnel actif qui perdrait sa connexion sans
    prévenir serait un vrai piège opérationnel."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM ssh_connections WHERE id = ?", [connection_id])
        conn.commit()
        return cur.rowcount > 0
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


# ------------------------------------------------------------------
# Tunnels
# ------------------------------------------------------------------
def create_tunnel(db_path, connection_id, label, remote_host, remote_port, local_port, created_by=None):
    """Renvoie (id, error) -- error si local_port déjà pris (contrainte
    UNIQUE) ou connection_id inconnu (contrainte FOREIGN KEY)."""
    now = now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO ssh_tunnels
               (connection_id, label, remote_host, remote_port, local_port, status, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, 'stopped', ?, ?, ?)""",
            [connection_id, label, remote_host, remote_port, local_port, created_by, now, now],
        )
        conn.commit()
        return cur.lastrowid, None
    except sqlite3.IntegrityError as exc:
        return None, f"création refusée : {exc}"
    finally:
        conn.close()


def list_tunnels(db_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ssh_tunnels ORDER BY label")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_tunnel(db_path, tunnel_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ssh_tunnels WHERE id = ?", [tunnel_id])
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_tunnel_state(db_path, tunnel_id, status, pid=None, last_error=None):
    """Met à jour l'état d'EXÉCUTION d'un tunnel (status/pid/erreur)
    -- jamais ses paramètres de configuration (remote_host, etc.),
    volontairement séparé -- démarrer/arrêter un tunnel ne doit
    jamais pouvoir en modifier la définition par accident."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE ssh_tunnels SET status = ?, pid = ?, last_error = ?, updated_at = ? WHERE id = ?",
            [status, pid, last_error, now_iso(), tunnel_id],
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def delete_tunnel(db_path, tunnel_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM ssh_tunnels WHERE id = ?", [tunnel_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# ------------------------------------------------------------------
# Montages SSHFS -- CRUD de la DÉFINITION seulement, aucune action
# mount/démontage réelle dans cette livraison (voir docstring du
# module).
# ------------------------------------------------------------------
def create_mount(db_path, connection_id, label, remote_path, local_mount_path, created_by=None):
    now = now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO ssh_mounts
               (connection_id, label, remote_path, local_mount_path, status, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, 'unmounted', ?, ?, ?)""",
            [connection_id, label, remote_path, local_mount_path, created_by, now, now],
        )
        conn.commit()
        return cur.lastrowid, None
    except sqlite3.IntegrityError as exc:
        return None, f"création refusée : {exc}"
    finally:
        conn.close()


def get_mount(db_path, mount_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ssh_mounts WHERE id = ?", [mount_id])
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_mount_state(db_path, mount_id, status, pid=None, last_error=None):
    """Même motif que update_tunnel_state ci-dessus -- état
    D'EXÉCUTION seulement (status/pid/erreur), jamais la définition
    (remote_path, etc.)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE ssh_mounts SET status = ?, pid = ?, last_error = ?, updated_at = ? WHERE id = ?",
            [status, pid, last_error, now_iso(), mount_id],
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def list_mounts(db_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM ssh_mounts ORDER BY label")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def delete_mount(db_path, mount_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM ssh_mounts WHERE id = ?", [mount_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
