"""#903 : stockage des messages du « blog » du hub (SQLite). Un message a un auteur, une portée (tous / l'auteur seul),
un contenu, une date de création, et une échéance : permanent, ou expiration automatique (effacé à la lecture).
Logique SQL pure, testable : le chemin de base et l'horloge sont injectables.
"""
import os
import sqlite3
import time
import uuid

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
  id TEXT PRIMARY KEY,
  auteur TEXT NOT NULL,
  auteur_nom TEXT,
  portee TEXT NOT NULL DEFAULT 'tous',          -- 'tous' | 'moi'
  titre TEXT,
  corps TEXT NOT NULL,
  format TEXT NOT NULL DEFAULT 'texte',         -- 'texte' | 'commande'
  cree REAL NOT NULL,
  expire REAL                                   -- NULL = permanent
);
CREATE INDEX IF NOT EXISTS idx_messages_cree ON messages(cree);
"""


def connect(path):
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    return conn


def _row(r):
    return {"id": r["id"], "auteur": r["auteur"], "auteur_nom": r["auteur_nom"] or r["auteur"], "portee": r["portee"],
            "titre": r["titre"] or "", "corps": r["corps"], "format": r["format"], "cree": r["cree"], "expire": r["expire"]}


def purger(conn, now=None):
    now = now or time.time()
    n = conn.execute("DELETE FROM messages WHERE expire IS NOT NULL AND expire <= ?", (now,)).rowcount
    conn.commit()
    return n


def creer(conn, auteur, auteur_nom, corps, titre="", portee="tous", fmt="texte", duree_s=None, now=None):
    now = now or time.time()
    if not (corps or "").strip():
        raise ValueError("message vide")
    if portee not in ("tous", "moi"):
        portee = "tous"
    if fmt not in ("texte", "commande"):
        fmt = "texte"
    mid = uuid.uuid4().hex
    expire = None if not duree_s else now + float(duree_s)
    conn.execute("INSERT INTO messages (id, auteur, auteur_nom, portee, titre, corps, format, cree, expire) VALUES (?,?,?,?,?,?,?,?,?)",
                 (mid, auteur, auteur_nom, portee, (titre or "").strip()[:200], corps.strip()[:20000], fmt, now, expire))
    conn.commit()
    return lire_un(conn, mid)


def lire_un(conn, mid):
    r = conn.execute("SELECT * FROM messages WHERE id = ?", (mid,)).fetchone()
    return _row(r) if r else None


def lister(conn, username, now=None):
    """Messages visibles par `username` : les « tous », et les « moi » dont il est l'auteur. Purge d'abord les expirés."""
    purger(conn, now)
    rows = conn.execute("SELECT * FROM messages WHERE portee = 'tous' OR (portee = 'moi' AND auteur = ?) ORDER BY cree DESC", (username,)).fetchall()
    return [_row(r) for r in rows]


def supprimer(conn, mid, username, est_admin=False):
    """L'auteur supprime son message ; un administrateur peut supprimer n'importe lequel. -> (ok, motif)."""
    r = conn.execute("SELECT auteur, portee FROM messages WHERE id = ?", (mid,)).fetchone()
    if r is None:
        return False, "introuvable"
    if not est_admin and r["auteur"] != username:
        return False, "seul l'auteur (ou un administrateur) peut supprimer ce message"
    conn.execute("DELETE FROM messages WHERE id = ?", (mid,))
    conn.commit()
    return True, None
