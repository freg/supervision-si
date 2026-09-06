"""
Stockage de l'orchestrateur d'analyse réseau (livraison #388,
backlog -- volet Nebula recentré : "le besoin d'analyse et de
supervision d'un environnement réseau... est prioritaire", demandé
explicitement après avoir constaté que `network-agent-api` couvre
déjà l'essentiel des deux listes demandées (appareils IP/MAC/DNS/
ports confirmés dans le temps, liens/flux/volumes) -- ce module NE
DUPLIQUE PAS ces données, il les LIT (via l'API HTTP de
network-agent-api, voir network_agent_client.py) et PROPOSE des
étapes d'analyse/supervision suivantes.

Même motif ACCUMULATIF que network-agent (voir son store.py) :
`first_detected_at` n'est JAMAIS réécrit, `last_detected_at` est mis
à jour à chaque passage où la condition est retrouvée VRAIE -- une
suggestion existe UNE SEULE FOIS par (règle, sujet), son statut
évolue dans le temps plutôt que d'être dupliquée à chaque passage de
l'orchestrateur.
"""
import json
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_name TEXT NOT NULL,
    subject_type TEXT NOT NULL,
    subject_key TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    suggested_action TEXT,
    action_params_json TEXT,
    first_detected_at TEXT NOT NULL,
    last_detected_at TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    resolved_at TEXT,
    UNIQUE(rule_name, subject_type, subject_key)
);
CREATE INDEX IF NOT EXISTS idx_suggestions_status ON suggestions(status);
CREATE INDEX IF NOT EXISTS idx_suggestions_rule ON suggestions(rule_name);
"""

STATUSES = ("open", "dismissed", "done")


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


def record_or_update_suggestion(db_path, rule_name, subject_type, subject_key, severity, message,
                                 suggested_action=None, action_params=None):
    """Une ligne UNIQUE par (rule_name, subject_type, subject_key) --
    jamais dupliquée. Si elle existe déjà et est 'dismissed'/'done',
    la condition qui la justifie a été retrouvée VRAIE à nouveau --
    RÉOUVERTE automatiquement (statut -> 'open') plutôt que de rester
    silencieusement invisible -- une personne qui avait rejeté un
    signal AUTREMENT résolu depuis devrait le revoir s'il recommence.
    """
    now = now_iso()
    action_params_json = json.dumps(action_params) if action_params is not None else None
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT id, status FROM suggestions WHERE rule_name = ? AND subject_type = ? AND subject_key = ?",
            [rule_name, subject_type, subject_key],
        )
        existing = cur.fetchone()
        if existing is None:
            cur.execute(
                """INSERT INTO suggestions
                   (rule_name, subject_type, subject_key, severity, message, suggested_action,
                    action_params_json, first_detected_at, last_detected_at, status)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')""",
                [rule_name, subject_type, subject_key, severity, message, suggested_action,
                 action_params_json, now, now],
            )
            conn.commit()
            return cur.lastrowid, "created"
        new_status = "open"  # réouverte si elle avait été close, voir docstring
        cur.execute("SELECT action_params_json FROM suggestions WHERE id = ?", [existing["id"]])
        existing_action_params_json = cur.fetchone()["action_params_json"]
        # Préserve les action_params EXISTANTS si cet appel n'en fournit
        # pas explicitement (action_params=None) -- une mise à jour qui
        # ne fait que rafraîchir le message ne doit JAMAIS effacer un
        # contexte d'action déjà enregistré par un appel précédent.
        final_action_params_json = action_params_json if action_params_json is not None else existing_action_params_json
        cur.execute(
            """UPDATE suggestions SET severity = ?, message = ?, suggested_action = ?,
               action_params_json = ?, last_detected_at = ?, status = ?,
               resolved_at = CASE WHEN ? = 'open' THEN NULL ELSE resolved_at END
               WHERE id = ?""",
            [severity, message, suggested_action, final_action_params_json, now, new_status, new_status, existing["id"]],
        )
        conn.commit()
        return existing["id"], "updated"
    finally:
        conn.close()


def list_suggestions(db_path, status=None, rule_name=None, limit=200):
    """Les plus RÉCEMMENT détectées d'abord."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        clauses, params = [], []
        if status:
            clauses.append("status = ?")
            params.append(status)
        if rule_name:
            clauses.append("rule_name = ?")
            params.append(rule_name)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur.execute(f"SELECT * FROM suggestions {where_sql} ORDER BY last_detected_at DESC LIMIT ?", params)
        results = []
        for r in cur.fetchall():
            row = dict(r)
            try:
                row["action_params"] = json.loads(row.pop("action_params_json") or "null")
            except (json.JSONDecodeError, TypeError):
                row["action_params"] = None
            results.append(row)
        return results
    finally:
        conn.close()


def set_suggestion_status(db_path, suggestion_id, status):
    """`status` doit être l'un de STATUSES -- validé par l'appelant
    (route Flask), jamais silencieusement accepté ici tel quel."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        resolved_at = now_iso() if status in ("dismissed", "done") else None
        cur.execute(
            "UPDATE suggestions SET status = ?, resolved_at = ? WHERE id = ?",
            [status, resolved_at, suggestion_id],
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_suggestion(db_path, suggestion_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM suggestions WHERE id = ?", [suggestion_id])
        row = cur.fetchone()
        if row is None:
            return None
        result = dict(row)
        try:
            result["action_params"] = json.loads(result.pop("action_params_json") or "null")
        except (json.JSONDecodeError, TypeError):
            result["action_params"] = None
        return result
    finally:
        conn.close()


def count_by_status(db_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT status, COUNT(*) as n FROM suggestions GROUP BY status")
        return {r["status"]: r["n"] for r in cur.fetchall()}
    finally:
        conn.close()
