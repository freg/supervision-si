"""
Persistance des interpréteurs (livraison #191, backlog BACKLOG.md #4,
volet 3/4 : "Gestionnaire d'interpréteur"). Généralise en outil
CONFIGURABLE ce que `pixel-grid/data-generator/parse_zenoss_emails.py`
fait aujourd'hui EN DUR pour un seul format d'alerte -- ce fichier-là
reste INCHANGÉ (parseur hors-ligne existant, voir imap-client/README.md
pour la distinction), jamais remplacé automatiquement -- juste une
RÉFÉRENCE pour concevoir la généralisation (motifs nommés `(?P<nom>...)`
appliqués au sujet/corps).

**Choix : un CHAMP = un MOTIF indépendant**, plutôt qu'un seul motif
géant à groupes nommés (comme `parse_zenoss_emails.py`) -- plus
simple à configurer sans expertise regex poussée pour quelqu'un qui
ajoute un NOUVEL interpréteur : chaque champ se règle et se teste
indépendamment des autres, une regex compliquée en moins à
maintenir d'un coup.

Un interpréteur = critères de correspondance (`match_subject`/
`match_from`, optionnels, pour choisir AUTOMATIQUEMENT quel
interpréteur s'applique à un message donné) + une liste de CHAMPS
(`fields`, JSON : `[{"name": ..., "source": "subject"|"body",
"pattern": "..."}, ...]`) -- chaque champ applique son motif à la
partie du message désignée par `source`, stocke le résultat sous
`name` dans le JSON produit.
"""
import json
import re
import sqlite3
import time


SCHEMA = """
CREATE TABLE IF NOT EXISTS imap_interpreters (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    match_subject TEXT,
    match_from TEXT,
    fields TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
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
    ensure_target_source_column(db_path)


def ensure_target_source_column(db_path):
    """Migration (livraison #230, backlog item 4 -- connecteur
    source) -- `target_source` NULLABLE, simple `ALTER TABLE ADD
    COLUMN` (contrairement à la migration `ssh_key_id` de #210, aucune
    contrainte NOT NULL à lever ici, pas besoin de reconstruire la
    table). Idempotente -- si la colonne existe déjà, ne fait rien.
    NULL = comportement INCHANGÉ (interpréteur qui ne pousse vers
    aucune source, comme avant cette livraison) -- fonctionnalité
    strictement OPT-IN, jamais activée pour un interpréteur
    existant sans action explicite."""
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(imap_interpreters)")
        existing_columns = {row[1] for row in cur.fetchall()}
        if "target_source" in existing_columns:
            return
        cur.execute("ALTER TABLE imap_interpreters ADD COLUMN target_source TEXT")
        conn.commit()
    finally:
        conn.close()


def validate_fields(fields):
    """Valide LA FORME de `fields` (liste de dicts name/source/pattern)
    ET que chaque `pattern` compile réellement -- jamais stocké un
    interpréteur avec un motif invalide, l'erreur se verrait bien plus
    tard sinon, au moment de l'appliquer à un vrai message plutôt qu'à
    la création. Renvoie (ok, error) -- jamais une exception."""
    if not isinstance(fields, list) or not fields:
        return False, "'fields' doit être une liste non vide"
    for i, field in enumerate(fields):
        if not isinstance(field, dict):
            return False, f"champ #{i} : doit être un objet"
        name = field.get("name")
        source = field.get("source")
        pattern = field.get("pattern")
        if not name or not isinstance(name, str):
            return False, f"champ #{i} : 'name' requis"
        if source not in ("subject", "body"):
            return False, f"champ #{i} ('{name}') : 'source' doit être 'subject' ou 'body'"
        if not pattern or not isinstance(pattern, str):
            return False, f"champ #{i} ('{name}') : 'pattern' requis"
        try:
            re.compile(pattern)
        except re.error as exc:
            return False, f"champ #{i} ('{name}') : motif invalide -- {exc}"
    return True, None


def row_to_interpreter(row):
    return {
        "id": row["id"],
        "name": row["name"],
        "match_subject": row["match_subject"],
        "match_from": row["match_from"],
        "fields": json.loads(row["fields"]),
        "enabled": bool(row["enabled"]),
        # target_source (livraison #230) -- connecteur source, voir
        # ensure_target_source_column. Colonne ajoutée par migration,
        # peut être absente sur une base pas encore migrée -- accès
        # défensif via .keys() plutôt qu'un accès direct qui lèverait
        # IndexError sur sqlite3.Row si la colonne manque.
        "target_source": row["target_source"] if "target_source" in row.keys() else None,
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def list_interpreters(db_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM imap_interpreters ORDER BY id")
        return [row_to_interpreter(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_interpreter(db_path, interpreter_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM imap_interpreters WHERE id = ?", [interpreter_id])
        row = cur.fetchone()
        return row_to_interpreter(row) if row else None
    finally:
        conn.close()


def create_interpreter(db_path, name, fields, match_subject=None, match_from=None, target_source=None):
    now = now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO imap_interpreters
               (name, match_subject, match_from, fields, enabled, target_source, created_at, updated_at)
               VALUES (?, ?, ?, ?, 1, ?, ?, ?)""",
            [name, match_subject, match_from, json.dumps(fields), target_source, now, now],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_interpreter(db_path, interpreter_id, patch):
    """Mise à jour PARTIELLE -- même motif que rules_store.update_rule
    (#190). `fields`, si fourni, est REVALIDÉ intégralement (jamais
    de fusion champ par champ -- une liste de champs se remplace en
    bloc, jamais partiellement, pour rester simple à raisonner)."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM imap_interpreters WHERE id = ?", [interpreter_id])
        row = cur.fetchone()
        if row is None:
            return None, None
        current = row_to_interpreter(row)
        merged = {**current, **patch}
        if "fields" in patch:
            ok, error = validate_fields(merged["fields"])
            if not ok:
                return None, error
        cur.execute(
            """UPDATE imap_interpreters SET name = ?, match_subject = ?, match_from = ?,
               fields = ?, enabled = ?, target_source = ?, updated_at = ? WHERE id = ?""",
            [merged["name"], merged["match_subject"], merged["match_from"],
             json.dumps(merged["fields"]), int(merged["enabled"]), merged.get("target_source"), now_iso(), interpreter_id],
        )
        conn.commit()
        cur.execute("SELECT * FROM imap_interpreters WHERE id = ?", [interpreter_id])
        return row_to_interpreter(cur.fetchone()), None
    finally:
        conn.close()


def delete_interpreter(db_path, interpreter_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM imap_interpreters WHERE id = ?", [interpreter_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
