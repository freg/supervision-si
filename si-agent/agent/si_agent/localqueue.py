"""File locale store-and-forward (SQLite) -- utilisée À L'IDENTIQUE par la
sonde (vers le collecteur) et par le collecteur (vers le central).

Pourquoi une file et pas un envoi direct : la coupure de liaison est
précisément le phénomène à observer. Une sonde qui perdrait ses mesures
quand le WiFi tombe ne dirait jamais QUAND ni COMBIEN de temps il est
tombé. Tout est écrit localement d'abord, marqué `sent` seulement après
accusé de réception, et purgé bien après.

Robustesse Pi Zero W (carte SD, coupures d'alimentation) : `journal_mode
= WAL` + `synchronous = NORMAL` -- bon compromis durabilité/usure de la
carte. Une base corrompue est détectée à l'ouverture et mise de côté
(renommée) plutôt que de bloquer la sonde pour toujours.
"""
import json
import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS outbox (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_id TEXT NOT NULL,
    task TEXT NOT NULL,
    at TEXT NOT NULL,
    ok INTEGER NOT NULL DEFAULT 1,
    data TEXT,
    error TEXT,
    created_at REAL NOT NULL,
    sent_at REAL,
    attempts INTEGER NOT NULL DEFAULT 0,
    UNIQUE(agent_id, task, at)
);
CREATE INDEX IF NOT EXISTS idx_outbox_pending ON outbox(sent_at, id);
"""


class LocalQueue:
    def __init__(self, db_path):
        self.db_path = db_path
        self._open()

    def _open(self):
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        try:
            self.conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.execute("PRAGMA synchronous = NORMAL")
            self.conn.executescript(SCHEMA)
            self.conn.execute("SELECT count(*) FROM outbox").fetchone()
        except sqlite3.DatabaseError:
            # Base illisible (carte SD abîmée) : on la met de côté et on repart
            # vide -- perdre l'historique local vaut mieux que ne plus mesurer.
            try:
                self.conn.close()
            except Exception:
                pass
            os.replace(self.db_path, self.db_path + ".corrupt.%d" % int(time.time()))
            self.conn = sqlite3.connect(self.db_path, timeout=10, check_same_thread=False)
            self.conn.execute("PRAGMA journal_mode = WAL")
            self.conn.executescript(SCHEMA)

    def close(self):
        self.conn.close()

    def put(self, measurement):
        """Insère une mesure ; renvoie True si nouvelle, False si déjà
        présente (même agent/tâche/instant -- idempotent)."""
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO outbox(agent_id, task, at, ok, data, error, created_at) VALUES (?,?,?,?,?,?,?)",
                    (measurement["agent_id"], measurement["task"], measurement["at"],
                     1 if measurement.get("ok", True) else 0,
                     json.dumps(measurement.get("data"), ensure_ascii=False) if measurement.get("data") is not None else None,
                     measurement.get("error"), time.time()),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def put_many(self, measurements):
        return sum(1 for m in measurements if self.put(m))

    def pending(self, limit=200):
        cur = self.conn.execute(
            "SELECT id, agent_id, task, at, ok, data, error FROM outbox WHERE sent_at IS NULL ORDER BY id LIMIT ?", (limit,))
        rows = []
        for r in cur.fetchall():
            rows.append({
                "_id": r[0], "agent_id": r[1], "task": r[2], "at": r[3], "ok": bool(r[4]),
                "data": json.loads(r[5]) if r[5] else None, "error": r[6],
            })
        return rows

    def pending_count(self):
        return self.conn.execute("SELECT count(*) FROM outbox WHERE sent_at IS NULL").fetchone()[0]

    def mark_sent(self, ids):
        if not ids:
            return
        with self.conn:
            self.conn.executemany("UPDATE outbox SET sent_at = ? WHERE id = ?", [(time.time(), i) for i in ids])

    def mark_attempt(self, ids):
        if not ids:
            return
        with self.conn:
            self.conn.executemany("UPDATE outbox SET attempts = attempts + 1 WHERE id = ?", [(i,) for i in ids])

    def latest(self, task=None, limit=50):
        """Dernières mesures locales (envoyées ou non) -- pour le statut
        local consultable sur place par le technicien."""
        if task:
            cur = self.conn.execute(
                "SELECT agent_id, task, at, ok, data, error, sent_at FROM outbox WHERE task = ? ORDER BY id DESC LIMIT ?", (task, limit))
        else:
            cur = self.conn.execute(
                "SELECT agent_id, task, at, ok, data, error, sent_at FROM outbox ORDER BY id DESC LIMIT ?", (limit,))
        return [{"agent_id": r[0], "task": r[1], "at": r[2], "ok": bool(r[3]),
                 "data": json.loads(r[4]) if r[4] else None, "error": r[5], "sent": r[6] is not None}
                for r in cur.fetchall()]

    def purge_sent(self, older_than_seconds=7 * 86400, keep_min=500):
        """Supprime les mesures ENVOYÉES plus vieilles que `older_than_seconds`,
        en gardant toujours les `keep_min` plus récentes (statut local).
        Les mesures non envoyées ne sont JAMAIS purgées ici."""
        cutoff = time.time() - older_than_seconds
        with self.conn:
            cur = self.conn.execute(
                "DELETE FROM outbox WHERE sent_at IS NOT NULL AND sent_at < ? AND id NOT IN ("
                "SELECT id FROM outbox ORDER BY id DESC LIMIT ?)", (cutoff, keep_min))
            return cur.rowcount

    def stats(self):
        total = self.conn.execute("SELECT count(*) FROM outbox").fetchone()[0]
        pending = self.pending_count()
        oldest = self.conn.execute("SELECT min(created_at) FROM outbox WHERE sent_at IS NULL").fetchone()[0]
        return {"total": total, "pending": pending,
                "oldest_pending_age_s": int(time.time() - oldest) if oldest else 0}
