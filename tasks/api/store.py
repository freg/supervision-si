"""
Gestion de tâches INDÉPENDANTE des tickets (livraison #271, backlog
-- demandé explicitement : "une gestion de tâche indépendante des
tickets avec une vue kanban"). Module SÉPARÉ de `tickets-api` --
donnée volontairement DISTINCTE (aucune table partagée, aucune clé
étrangère vers `tickets`) : une tâche personnelle/d'équipe n'est PAS
un ticket de support, même si les deux peuvent un jour être
affichés ensemble dans la tuile "ENT" côté hub.

Trois colonnes FIXES pour cette première tranche (`todo`/`doing`/
`done`) -- un jeu de colonnes personnalisable serait un
enrichissement raisonnable plus tard, mais pas demandé explicitement
ici, jamais présumé.

`position` gère l'ORDRE au sein d'une colonne (le Kanban demandé
explicitement implique un tri visuel, pas seulement un statut) --
entier, dense au sein d'une même colonne (0, 1, 2...), jamais un
"gap" volontaire (plus simple à raisonner, léger coût de
renumérotation sur un déplacement, largement acceptable au volume
d'une tuile de tâches personnelle).
"""
import sqlite3
import time

VALID_STATUSES = ("todo", "doing", "done")

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL DEFAULT 'todo',
    position INTEGER NOT NULL,
    due_date TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status, position);
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


def _next_position(cur, status):
    cur.execute("SELECT COALESCE(MAX(position), -1) + 1 FROM tasks WHERE status = ?", [status])
    return cur.fetchone()[0]


def create_task(db_path, title, description=None, status="todo", due_date=None):
    if status not in VALID_STATUSES:
        return None, f"statut invalide '{status}' (attendus : {list(VALID_STATUSES)})"
    title = (title or "").strip()
    if not title:
        return None, "'title' requis"

    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        position = _next_position(cur, status)
        now = now_iso()
        cur.execute(
            "INSERT INTO tasks (title, description, status, position, due_date, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            [title, description, status, position, due_date, now, now],
        )
        conn.commit()
        return cur.lastrowid, None
    finally:
        conn.close()


def list_tasks(db_path):
    """Renvoie TOUTES les tâches, triées par statut puis position --
    l'appelant (route API) les groupe par colonne s'il le souhaite,
    cette fonction reste une simple lecture, jamais une mise en
    forme métier."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks ORDER BY status, position")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def get_task(db_path, task_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE id = ?", [task_id])
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_task(db_path, task_id, **fields):
    """Mise à jour SIMPLE (titre/description/échéance) -- pour un
    déplacement Kanban (changement de statut ET/OU de position),
    utiliser `move_task` à la place (gère la renumérotation, ce que
    cette fonction ne fait PAS)."""
    allowed = {"title", "description", "due_date"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return False
    updates["updated_at"] = now_iso()
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(f"UPDATE tasks SET {set_clause} WHERE id = ?", [*updates.values(), task_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def move_task(db_path, task_id, new_status, new_position):
    """LE mouvement Kanban -- change la colonne (`status`) et/ou la
    position d'une tâche, en renumérotant proprement les DEUX
    colonnes concernées (source ET destination si elles diffèrent)
    pour qu'elles restent denses (0, 1, 2... sans trou ni doublon).
    `new_position` est bornée à la taille de la colonne destination
    (jamais une position hors limites qui laisserait un trou)."""
    if new_status not in VALID_STATUSES:
        return False, f"statut invalide '{new_status}' (attendus : {list(VALID_STATUSES)})"

    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT status, position FROM tasks WHERE id = ?", [task_id])
        row = cur.fetchone()
        if row is None:
            return False, "tâche introuvable"
        old_status, old_position = row["status"], row["position"]

        if old_status == new_status:
            _reorder_within_column(cur, new_status, task_id, old_position, new_position)
        else:
            # Retire la tâche de son ancienne colonne (comble le trou)
            cur.execute("UPDATE tasks SET position = position - 1 WHERE status = ? AND position > ?", [old_status, old_position])
            # Fait de la place dans la colonne destination
            cur.execute("SELECT COUNT(*) FROM tasks WHERE status = ?", [new_status])
            dest_count = cur.fetchone()[0]
            new_position = max(0, min(new_position, dest_count))
            cur.execute("UPDATE tasks SET position = position + 1 WHERE status = ? AND position >= ?", [new_status, new_position])
            cur.execute("UPDATE tasks SET status = ?, position = ?, updated_at = ? WHERE id = ?", [new_status, new_position, now_iso(), task_id])

        conn.commit()
        return True, None
    finally:
        conn.close()


def _reorder_within_column(cur, status, task_id, old_position, new_position):
    """Réordonne AU SEIN d'une même colonne -- décale les tâches
    entre l'ancienne et la nouvelle position (dans le bon sens selon
    que la tâche avance ou recule)."""
    cur.execute("SELECT COUNT(*) FROM tasks WHERE status = ?", [status])
    count = cur.fetchone()[0]
    new_position = max(0, min(new_position, count - 1))
    if new_position == old_position:
        return
    if new_position < old_position:
        cur.execute(
            "UPDATE tasks SET position = position + 1 WHERE status = ? AND position >= ? AND position < ?",
            [status, new_position, old_position],
        )
    else:
        cur.execute(
            "UPDATE tasks SET position = position - 1 WHERE status = ? AND position > ? AND position <= ?",
            [status, old_position, new_position],
        )
    cur.execute("UPDATE tasks SET position = ?, updated_at = ? WHERE id = ?", [new_position, now_iso(), task_id])


def delete_task(db_path, task_id):
    """Supprime ET comble le trou laissé dans sa colonne (renumérote
    les positions suivantes) -- jamais un trou permanent qui
    fausserait un futur calcul de position."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT status, position FROM tasks WHERE id = ?", [task_id])
        row = cur.fetchone()
        if row is None:
            return False
        cur.execute("DELETE FROM tasks WHERE id = ?", [task_id])
        cur.execute("UPDATE tasks SET position = position - 1 WHERE status = ? AND position > ?", [row["status"], row["position"]])
        conn.commit()
        return True
    finally:
        conn.close()
