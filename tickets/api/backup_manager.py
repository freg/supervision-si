"""
Sauvegarde/restauration versionnée de la base tickets — demandé
explicitement en prévention des fonctionnalités plus risquées du
gestionnaire de base de données (éditeur générique de lignes, console
SQL directe) : avant d'exposer ces capacités, un vrai filet de
sécurité.

Dump SQL NATIF (pas le format JSON déjà utilisé par /export) --
demandé explicitement : plus robuste (ne dépend d'aucune logique
d'export/import maison), directement restaurable avec les outils
standards (`sqlite3 fichier.db < dump.sql`, `psql ... < dump.sql`).

Deux déclencheurs, demandés explicitement :
- périodique (voir start_periodic_backup_thread) ;
- avant chaque action risquée (appelé explicitement par les routes
  concernées une fois construites — éditeur générique, exécution SQL
  non-SELECT).

Toutes les fonctions ACCEPTENT LEURS DÉPENDANCES EN PARAMÈTRE
(chemin de la base, config PG, exécuteur de sous-processus) plutôt
que de lire les variables de module directement -- reste testable
sans avoir besoin d'un vrai SQLite/PostgreSQL ni d'un vrai
sous-processus.
"""

import glob
import logging
import os
import shutil
import sqlite3
import subprocess
import time

# Traces DEBUG (livraison #225, audit rétroactif). RÈGLE ABSOLUE :
# `env` (qui contient PGPASSWORD) n'est JAMAIS tracé -- seuls les
# éléments sûrs de `cmd` (host, port, base, chemin de fichier).
_log = logging.getLogger("backup_manager")


def _timestamp():
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


def backup_filename(trigger, timestamp=None):
    """Nom de fichier normalisé -- `trigger` tracé dans le nom pour
    comprendre l'historique sans avoir à ouvrir chaque fichier
    (périodique / avant-édition / avant-sql / manuel). Pure, testable
    sans horloge réelle via `timestamp` injecté."""
    ts = timestamp or _timestamp()
    safe_trigger = "".join(c if c.isalnum() or c == "-" else "-" for c in trigger)
    return f"tickets-{ts}-{safe_trigger}.sql"


def list_backup_files(backup_dir):
    """Liste les fichiers de sauvegarde, du plus récent au plus
    ancien -- tri par NOM (l'horodatage est en tête, donc un tri
    lexicographique est déjà un tri chronologique, jamais besoin de
    parser le nom pour trier correctement)."""
    if not os.path.isdir(backup_dir):
        return []
    return sorted(
        (f for f in os.listdir(backup_dir) if f.startswith("tickets-") and f.endswith(".sql")),
        reverse=True,
    )


def files_to_prune(all_files, retention_count):
    """Pure -- quels fichiers seraient supprimés pour ne conserver
    que les `retention_count` plus récents. `all_files` DOIT déjà être
    trié du plus récent au plus ancien (voir list_backup_files) --
    jamais retrié ici, pour ne dépendre que d'UNE SEULE définition de
    ce qu'est "le plus récent"."""
    if retention_count <= 0:
        return list(all_files)
    return list(all_files[retention_count:])


def is_safe_backup_filename(filename):
    """Un nom de fichier de sauvegarde est-il sûr à utiliser dans un
    chemin de fichier ? Rejette tout ce qui pourrait sortir du
    dossier de sauvegarde (traversée de chemin) -- vérifié AVANT tout
    accès disque, jamais après."""
    if not filename or not isinstance(filename, str):
        return False
    if "/" in filename or "\\" in filename or ".." in filename:
        return False
    return filename.startswith("tickets-") and filename.endswith(".sql")


def dump_sqlite(db_path, output_path, sqlite_connector=sqlite3.connect):
    """Dump natif via conn.iterdump() (bibliothèque standard) --
    jamais le format JSON maison. `sqlite_connector` injecté pour
    rester testable sans dépendre du VRAI module sqlite3.connect en
    test (bien qu'ici, sqlite3 réel reste utilisable directement en
    test, contrairement à psycopg2 qui exige un vrai serveur)."""
    conn = sqlite_connector(db_path)
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            for line in conn.iterdump():
                f.write(f"{line}\n")
    finally:
        conn.close()


def restore_sqlite(db_path, dump_path, sqlite_connector=sqlite3.connect, file_ops=None):
    """Restauration DESTRUCTIVE -- iterdump() produit des CREATE TABLE
    qui échoueraient si les tables existent déjà (restauration DANS
    une base déjà peuplée) : le fichier de base est donc entièrement
    supprimé puis recréé from scratch à partir du dump. Copie de
    sécurité de l'état ACTUEL conservée (db_path + '.before-restore')
    et restaurée automatiquement si la restauration échoue en cours
    de route -- jamais un échec partiel qui laisserait la base dans un
    état pire qu'avant. `file_ops` injecté (os.path.exists/remove,
    shutil.copy2) pour rester testable sans vrai système de fichiers
    si besoin -- None = utilise réellement os/shutil."""
    if file_ops is None:
        file_ops = {"exists": os.path.exists, "remove": os.remove, "copy2": shutil.copy2}

    safety_copy = db_path + ".before-restore"
    had_existing = file_ops["exists"](db_path)
    if had_existing:
        file_ops["copy2"](db_path, safety_copy)

    try:
        if had_existing:
            file_ops["remove"](db_path)
        conn = sqlite_connector(db_path)
        try:
            with open(dump_path, encoding="utf-8") as f:
                conn.executescript(f.read())
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # Échec en cours de route -- restaure l'état d'AVANT depuis la
        # copie de sécurité, jamais laisser la base dans un état pire
        # qu'avant la tentative.
        if had_existing and file_ops["exists"](safety_copy):
            file_ops["copy2"](safety_copy, db_path)
        raise


def build_pg_dump_command(pg_config, output_path):
    """Pure -- construit la commande pg_dump, testable sans lancer de
    VRAI sous-processus. Le mot de passe passe par l'environnement
    (PGPASSWORD), jamais en argument de ligne de commande (visible
    dans `ps`, comme ailleurs dans ce projet -- même précaution que
    pour les autres identifiants)."""
    return [
        "pg_dump",
        "-h", pg_config["host"],
        "-p", str(pg_config["port"]),
        "-U", pg_config["user"],
        "-d", pg_config["dbname"],
        "-f", output_path,
    ]


def build_psql_restore_command(pg_config, input_path):
    """Pure, même raisonnement que build_pg_dump_command ci-dessus."""
    return [
        "psql",
        "-h", pg_config["host"],
        "-p", str(pg_config["port"]),
        "-U", pg_config["user"],
        "-d", pg_config["dbname"],
        "-f", input_path,
    ]


def dump_postgres(pg_config, output_path, runner=subprocess.run):
    """`runner` injecté -- jamais un vrai sous-processus en test."""
    _log.debug("dump_postgres : démarré (%s:%s, base=%s, jamais le mot de passe ici -- transite via PGPASSWORD)",
               pg_config.get("host"), pg_config.get("port"), pg_config.get("dbname"))
    start = time.monotonic()
    env = os.environ.copy()
    env["PGPASSWORD"] = pg_config["password"]
    result = runner(build_pg_dump_command(pg_config, output_path), env=env, capture_output=True, timeout=120)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace") if isinstance(result.stderr, bytes) else result.stderr
        _log.debug("dump_postgres : ÉCHEC après %d ms (code retour %s)", elapsed_ms, result.returncode)
        raise RuntimeError(f"pg_dump échoué : {stderr}")
    _log.debug("dump_postgres : succès en %d ms", elapsed_ms)


def restore_postgres(pg_config, input_path, runner=subprocess.run):
    _log.debug("restore_postgres : démarré (%s:%s, base=%s, jamais le mot de passe ici -- transite via PGPASSWORD)",
               pg_config.get("host"), pg_config.get("port"), pg_config.get("dbname"))
    start = time.monotonic()
    env = os.environ.copy()
    env["PGPASSWORD"] = pg_config["password"]
    result = runner(build_psql_restore_command(pg_config, input_path), env=env, capture_output=True, timeout=120)
    elapsed_ms = int((time.monotonic() - start) * 1000)
    if result.returncode != 0:
        stderr = result.stderr.decode(errors="replace") if isinstance(result.stderr, bytes) else result.stderr
        _log.debug("restore_postgres : ÉCHEC après %d ms (code retour %s)", elapsed_ms, result.returncode)
        raise RuntimeError(f"restauration PostgreSQL échouée : {stderr}")
    _log.debug("restore_postgres : succès en %d ms", elapsed_ms)


def create_backup(backup_dir, trigger, db_backend, db_path=None, pg_config=None,
                   sqlite_connector=sqlite3.connect, runner=subprocess.run, retention_count=30):
    """Point d'entrée unique -- crée le dump (SQLite ou PostgreSQL
    selon db_backend), applique la rétention, renvoie le nom de
    fichier créé. Jamais appelée directement par une route sans
    passer par ici -- un seul endroit qui sait comment dumper les
    deux moteurs."""
    os.makedirs(backup_dir, exist_ok=True)
    filename = backup_filename(trigger)
    filepath = os.path.join(backup_dir, filename)

    if db_backend == "postgres":
        dump_postgres(pg_config, filepath, runner=runner)
    else:
        dump_sqlite(db_path, filepath, sqlite_connector=sqlite_connector)

    all_files = list_backup_files(backup_dir)
    for old_file in files_to_prune(all_files, retention_count):
        try:
            os.remove(os.path.join(backup_dir, old_file))
        except OSError:
            pass  # jamais bloquant -- une sauvegarde qui vient de réussir ne doit pas échouer sur le nettoyage

    return filename


def restore_backup(backup_dir, filename, db_backend, db_path=None, pg_config=None,
                    sqlite_connector=sqlite3.connect, runner=subprocess.run):
    """Point d'entrée unique de restauration -- vérifie la sécurité du
    nom de fichier AVANT tout accès disque (voir
    is_safe_backup_filename), jamais après."""
    if not is_safe_backup_filename(filename):
        raise ValueError("nom de fichier de sauvegarde invalide")
    filepath = os.path.join(backup_dir, filename)
    if not os.path.isfile(filepath):
        raise ValueError("sauvegarde introuvable")

    if db_backend == "postgres":
        restore_postgres(pg_config, filepath, runner=runner)
    else:
        restore_sqlite(db_path, filepath, sqlite_connector=sqlite_connector)
