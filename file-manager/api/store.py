#!/usr/bin/env python3
"""
file-manager -- store.py (livraison #396, backlog item 26).

SQLite local pour l'index de l'espace protégé (métadonnées uniquement :
chemins, tailles, dates -- jamais le contenu). Ce module ne stocke
aucun document ni montage -- il agrège ged-api et ssh-tunnels-api.
"""
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS protected_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relative_path TEXT UNIQUE NOT NULL,
    item_type TEXT NOT NULL,  -- 'file' | 'folder' | 'other'
    size INTEGER,
    mtime INTEGER,
    scanned_at INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_protected_path ON protected_index(relative_path);
CREATE INDEX IF NOT EXISTS idx_protected_parent ON protected_index(relative_path);
"""


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema(db_path):
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def upsert_index_entry(db_path, relative_path, item_type, size, mtime):
    conn = get_connection(db_path)
    try:
        conn.execute(
            """INSERT INTO protected_index (relative_path, item_type, size, mtime, scanned_at)
               VALUES (?, ?, ?, ?, strftime('%s','now'))
               ON CONFLICT(relative_path) DO UPDATE SET
                 item_type = excluded.item_type,
                 size = excluded.size,
                 mtime = excluded.mtime,
                 scanned_at = strftime('%s','now')""",
            (relative_path, item_type, size, mtime),
        )
        conn.commit()
    finally:
        conn.close()


def get_index_entry(db_path, relative_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM protected_index WHERE relative_path = ?", (relative_path,))
        row = cur.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_index_entries(db_path, parent_path=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        if parent_path:
            cur.execute(
                "SELECT * FROM protected_index WHERE relative_path LIKE ? ORDER BY relative_path",
                (parent_path + "/%",),
            )
        else:
            cur.execute("SELECT * FROM protected_index ORDER BY relative_path")
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def delete_index_entry(db_path, relative_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM protected_index WHERE relative_path = ?", (relative_path,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
