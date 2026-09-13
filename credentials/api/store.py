# -*- coding: utf-8 -*-
"""Base des accès d'équipements (livraison #498) -- SQLite, un fichier
dans /data. Tables :

  credentials  nom unique (clé de référence pour les consommateurs :
               registre mikrotik, futurs modules), genre (routeros, ssh,
               http, snmp, other), identifiant, mot de passe CHIFFRÉ
               (credential_crypto, jamais en clair sur disque), notes,
               dates. Le mot de passe n'est JAMAIS renvoyé par la liste --
               seulement `has_password`.
  reveals      journal des révélations : quel consommateur (en-tête
               X-Credentials-Consumer), quel accès, quand, succès --
               jamais la valeur.

Aucune valeur en clair dans les traces. La phrase de passe vient de
l'environnement (CREDENTIALS_PASSPHRASE) ; le sel est généré UNE fois et
conservé dans /data/salt.b64 (sauvegardé avec la base, jamais régénéré).
"""
import os
import sqlite3
import time

import credential_crypto

KINDS = ("routeros", "ssh", "http", "snmp", "other")
NAME_RE = r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$"


def connect(db_path):
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(db_path):
    conn = connect(db_path)
    try:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            kind TEXT NOT NULL DEFAULT 'other',
            username TEXT NOT NULL DEFAULT '',
            password TEXT NOT NULL DEFAULT '',
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS reveals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            at TEXT NOT NULL,
            name TEXT NOT NULL,
            consumer TEXT NOT NULL DEFAULT '',
            ok INTEGER NOT NULL DEFAULT 1,
            detail TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_reveals_at ON reveals(at);
        """)
        conn.commit()
    finally:
        conn.close()


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _public(row, usage=None):
    d = {k: row[k] for k in ("id", "name", "kind", "username", "notes", "created_at", "updated_at")}
    d["has_password"] = bool(row["password"])
    d["password_encrypted"] = credential_crypto.is_protected(row["password"] or "")
    if usage is not None:
        d["last_reveal_at"] = usage.get("at")
        d["last_consumer"] = usage.get("consumer")
    return d


def list_credentials(db_path):
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT * FROM credentials ORDER BY name").fetchall()
        usage = {}
        for r in conn.execute("SELECT name, MAX(at) AS at, consumer FROM reveals WHERE ok = 1 GROUP BY name").fetchall():
            usage[r["name"]] = {"at": r["at"], "consumer": r["consumer"]}
        return [_public(r, usage.get(r["name"], {})) for r in rows]
    finally:
        conn.close()


def get_credential(db_path, name):
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM credentials WHERE name = ?", [name]).fetchone()
        return _public(row) if row else None
    finally:
        conn.close()


def upsert(db_path, name, kind, username, password, notes, keep_password=False):
    """Crée ou met à jour. `keep_password=True` : mot de passe inchangé
    (formulaire de modification sans ressaisie). Retourne la fiche
    publique. Lève ValueError si le chiffrement est requis et absent."""
    if kind not in KINDS:
        raise ValueError("genre inconnu : %s (attendu : %s)" % (kind, ", ".join(KINDS)))
    conn = connect(db_path)
    try:
        now = _now()
        row = conn.execute("SELECT * FROM credentials WHERE name = ?", [name]).fetchone()
        if row:
            stored = row["password"] if keep_password else credential_crypto.protect(password or "")
            conn.execute("UPDATE credentials SET kind=?, username=?, password=?, notes=?, updated_at=? WHERE name=?",
                         [kind, username or "", stored, notes or "", now, name])
        else:
            stored = credential_crypto.protect(password or "")
            conn.execute("INSERT INTO credentials (name, kind, username, password, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                         [name, kind, username or "", stored, notes or "", now, now])
        conn.commit()
        return _public(conn.execute("SELECT * FROM credentials WHERE name = ?", [name]).fetchone())
    finally:
        conn.close()


def delete(db_path, name):
    conn = connect(db_path)
    try:
        cur = conn.execute("DELETE FROM credentials WHERE name = ?", [name])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def reveal(db_path, name, consumer):
    """(username, password_clair) ou lève KeyError (inconnu) / ValueError
    (déchiffrement impossible). Chaque appel est journalisé, sans la
    valeur."""
    conn = connect(db_path)
    try:
        row = conn.execute("SELECT * FROM credentials WHERE name = ?", [name]).fetchone()
        if not row:
            conn.execute("INSERT INTO reveals (at, name, consumer, ok, detail) VALUES (?,?,?,0,?)", [_now(), name, consumer, "inconnu"])
            conn.commit()
            raise KeyError(name)
        try:
            clear = credential_crypto.reveal(row["password"] or "")
        except ValueError as exc:
            conn.execute("INSERT INTO reveals (at, name, consumer, ok, detail) VALUES (?,?,?,0,?)", [_now(), name, consumer, "déchiffrement impossible"])
            conn.commit()
            raise ValueError(str(exc))
        conn.execute("INSERT INTO reveals (at, name, consumer, ok, detail) VALUES (?,?,?,1,'')", [_now(), name, consumer])
        conn.commit()
        return row["username"], clear
    finally:
        conn.close()


def audit(db_path, limit=200):
    conn = connect(db_path)
    try:
        rows = conn.execute("SELECT at, name, consumer, ok, detail FROM reveals ORDER BY id DESC LIMIT ?", [min(int(limit), 1000)]).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def reencrypt_all(db_path):
    """Rechiffre les mots de passe encore en clair (après activation de la
    phrase de passe). Retourne le nombre traité."""
    conn = connect(db_path)
    try:
        n = 0
        for row in conn.execute("SELECT name, password FROM credentials").fetchall():
            if row["password"] and not credential_crypto.is_protected(row["password"]):
                conn.execute("UPDATE credentials SET password=?, updated_at=? WHERE name=?",
                             [credential_crypto.protect(row["password"]), _now(), row["name"]])
                n += 1
        conn.commit()
        return n
    finally:
        conn.close()
