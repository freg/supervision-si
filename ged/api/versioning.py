# -*- coding: utf-8 -*-
"""Archivage versionné du dépôt de documents (livraison #460).

Demandé : « un mécanisme d'archivage versionné pour le dépôt de document,
et un visualiseur de graphe d'évolution des versions », en pensant aux
gestions documentaires des années 90 sur Novell. Ce qui est repris de
SoftSolutions / GroupWise Document Management (WordPerfect, puis Novell,
1993-1998) : le PROFIL de document, les versions numérotées avec une
« version officielle » (Document Life Cycle status), le check-out /
check-in (« Document In-Use » : celui qui a sorti le document est le seul
à le modifier, les autres le consultent), l'édition de plusieurs versions
en parallèle (donc des BRANCHES), la sécurité au niveau version,
l'archivage planifié vers un emplacement d'archive. Et d'ARCserve : une
archive = copie immuable + catalogue.

Mayan EDMS garde les fichiers (ged-api #158) mais ne connaît qu'une suite
linéaire de fichiers par document. Cette couche LOCALE (SQLite du
ged-api) ajoute, par version Mayan : le PARENT (d'où elle dérive -- par
défaut la précédente ; une autre = branche), la branche, le statut
(draft | official | superseded | archived), l'auteur, le commentaire ;
par document : le check-out ; et l'ARCHIVE : copie immuable du fichier
(sha256 vérifié) dans GED_ARCHIVE_DIR + catalogue, indépendante de Mayan.

Logique PURE (graphe, voies, statuts) dans build_graph / assign_lanes,
testée dans test_versioning.py sans Mayan.
"""
import hashlib
import json
import os
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS version_meta (
    document_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    mayan_file_id INTEGER,
    parent_version INTEGER,
    branch TEXT NOT NULL DEFAULT 'principale',
    status TEXT NOT NULL DEFAULT 'draft',
    author TEXT,
    comment TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (document_id, version_number)
);
CREATE TABLE IF NOT EXISTS checkouts (
    document_id INTEGER PRIMARY KEY,
    user TEXT NOT NULL,
    version_number INTEGER,
    checked_out_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS archive_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL,
    version_number INTEGER NOT NULL,
    document_name TEXT,
    filename TEXT,
    path TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    size INTEGER NOT NULL,
    archived_by TEXT,
    archived_at TEXT NOT NULL,
    UNIQUE(document_id, version_number)
);
"""
STATUSES = ("draft", "official", "superseded", "archived")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _conn(db_path):
    c = sqlite3.connect(db_path)
    c.row_factory = sqlite3.Row
    return c


def ensure_schema(db_path):
    c = _conn(db_path)
    try:
        c.executescript(SCHEMA)
        c.commit()
    finally:
        c.close()


# ---------------------------------------------------------------- pur --
def build_graph(versions, metas, checkout=None, archives=None):
    """Fusionne la liste des versions Mayan [{version_number, mayan_file_id,
    raw}] avec les métadonnées locales -> {nodes, edges, official, checkout}.
    Une version sans méta a pour parent la précédente (suite linéaire) et le
    statut draft ; la dernière version officielle marque `official`."""
    by_v = {m["version_number"]: m for m in (metas or [])}
    arch = {a["version_number"]: a for a in (archives or [])}
    nodes, edges = [], []
    for v in sorted(versions, key=lambda x: x["version_number"]):
        n = v["version_number"]
        m = by_v.get(n, {})
        parent = m.get("parent_version")
        if parent is None and n > 1:
            parent = n - 1
        node = {"version": n, "mayan_file_id": v.get("mayan_file_id"), "parent": parent,
                "branch": m.get("branch") or "principale", "status": m.get("status") or "draft",
                "author": m.get("author"), "comment": m.get("comment"), "created_at": m.get("created_at") or (v.get("raw") or {}).get("timestamp"),
                "filename": (v.get("raw") or {}).get("filename"), "archived": n in arch,
                "archive": {"sha256": arch[n]["sha256"], "archived_at": arch[n]["archived_at"], "size": arch[n]["size"]} if n in arch else None}
        nodes.append(node)
        if parent is not None and any(x["version_number"] == parent for x in versions):
            edges.append({"from": parent, "to": n})
    official = max((x["version"] for x in nodes if x["status"] == "official"), default=None)
    return {"nodes": nodes, "edges": edges, "official": official, "checkout": checkout,
            "branches": sorted({x["branch"] for x in nodes})}


def assign_lanes(nodes):
    """Voies façon `git log --graph` : la branche principale en voie 0, chaque
    branche naissante prend la première voie libre à partir de son point de
    fourche ; rendu déterministe. -> {version: lane}"""
    lanes, order = {}, {}
    branch_lane = {}
    used = []
    for i, n in enumerate(sorted(nodes, key=lambda x: x["version"])):
        b = n["branch"]
        if b not in branch_lane:
            if not branch_lane:
                lane = 0
            else:
                lane = 0
                while lane in used:
                    lane += 1
            branch_lane[b] = lane
            used.append(lane)
        lanes[n["version"]] = branch_lane[b]
        order[n["version"]] = i
    return lanes


def lifecycle_transition(nodes, version, new_status):
    """Règles de cycle de vie (SoftSolutions : une seule version officielle) :
    passer `version` à `new_status` -> {version: statut} à écrire. Une nouvelle
    officielle rétrograde l'ancienne en superseded ; archived est terminal."""
    if new_status not in STATUSES:
        raise ValueError("statut inconnu : %s" % new_status)
    cur = {n["version"]: n["status"] for n in nodes}
    if version not in cur:
        raise ValueError("version inconnue : %s" % version)
    if cur[version] == "archived" and new_status != "archived":
        raise ValueError("une version archivée ne change plus de statut")
    changes = {version: new_status}
    if new_status == "official":
        for v, s in cur.items():
            if s == "official" and v != version:
                changes[v] = "superseded"
    return changes


# --------------------------------------------------------------- store --
def list_meta(db_path, document_id):
    c = _conn(db_path)
    try:
        return [dict(r) for r in c.execute("SELECT * FROM version_meta WHERE document_id=? ORDER BY version_number", (document_id,))]
    finally:
        c.close()


def upsert_meta(db_path, document_id, version_number, **fields):
    allowed = {k: v for k, v in fields.items() if k in ("mayan_file_id", "parent_version", "branch", "status", "author", "comment")}
    c = _conn(db_path)
    try:
        row = c.execute("SELECT 1 FROM version_meta WHERE document_id=? AND version_number=?", (document_id, version_number)).fetchone()
        if row:
            if allowed:
                sets = ", ".join("%s=?" % k for k in allowed)
                c.execute("UPDATE version_meta SET %s WHERE document_id=? AND version_number=?" % sets, list(allowed.values()) + [document_id, version_number])
        else:
            cols = ["document_id", "version_number", "created_at"] + list(allowed)
            vals = [document_id, version_number, now_iso()] + list(allowed.values())
            c.execute("INSERT INTO version_meta (%s) VALUES (%s)" % (", ".join(cols), ", ".join("?" * len(cols))), vals)
        c.commit()
    finally:
        c.close()


def set_statuses(db_path, document_id, changes):
    for v, s in changes.items():
        upsert_meta(db_path, document_id, v, status=s)


def get_checkout(db_path, document_id):
    c = _conn(db_path)
    try:
        r = c.execute("SELECT * FROM checkouts WHERE document_id=?", (document_id,)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def checkout(db_path, document_id, user, version_number=None):
    """-> (ok, détenteur actuel si refus)"""
    cur = get_checkout(db_path, document_id)
    if cur and cur["user"] != user:
        return False, cur
    c = _conn(db_path)
    try:
        c.execute("INSERT OR REPLACE INTO checkouts (document_id, user, version_number, checked_out_at) VALUES (?,?,?,?)",
                  (document_id, user, version_number, now_iso()))
        c.commit()
    finally:
        c.close()
    return True, None


def checkin(db_path, document_id, user, force=False):
    cur = get_checkout(db_path, document_id)
    if not cur:
        return False, "document non sorti"
    if cur["user"] != user and not force:
        return False, "sorti par %s" % cur["user"]
    c = _conn(db_path)
    try:
        c.execute("DELETE FROM checkouts WHERE document_id=?", (document_id,))
        c.commit()
    finally:
        c.close()
    return True, None


def list_checkouts(db_path):
    c = _conn(db_path)
    try:
        return [dict(r) for r in c.execute("SELECT * FROM checkouts ORDER BY checked_out_at DESC")]
    finally:
        c.close()


def archive_version(db_path, archive_dir, document_id, version_number, content, filename, document_name=None, archived_by=None):
    """Copie IMMUABLE : <archive_dir>/<doc>/v<N>-<sha8>-<nom> + entrée de
    catalogue ; refuse une seconde archive de la même version (WORM)."""
    c = _conn(db_path)
    try:
        if c.execute("SELECT 1 FROM archive_entries WHERE document_id=? AND version_number=?", (document_id, version_number)).fetchone():
            return None, "version déjà archivée (archive immuable)"
    finally:
        c.close()
    sha = hashlib.sha256(content).hexdigest()
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in (filename or "fichier"))[:120]
    d = os.path.join(archive_dir, str(document_id))
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "v%d-%s-%s" % (version_number, sha[:8], safe))
    with open(path, "wb") as fh:
        fh.write(content)
    os.chmod(path, 0o440)
    c = _conn(db_path)
    try:
        c.execute("INSERT INTO archive_entries (document_id, version_number, document_name, filename, path, sha256, size, archived_by, archived_at) VALUES (?,?,?,?,?,?,?,?,?)",
                  (document_id, version_number, document_name, filename, path, sha, len(content), archived_by, now_iso()))
        c.commit()
    finally:
        c.close()
    with open(os.path.join(d, "catalogue.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"document_id": document_id, "version": version_number, "file": os.path.basename(path), "sha256": sha, "size": len(content),
                             "archived_at": now_iso(), "archived_by": archived_by, "document_name": document_name}, ensure_ascii=False) + "\n")
    return {"path": path, "sha256": sha, "size": len(content)}, None


def list_archives(db_path, document_id=None):
    c = _conn(db_path)
    try:
        if document_id is None:
            rows = c.execute("SELECT * FROM archive_entries ORDER BY archived_at DESC").fetchall()
        else:
            rows = c.execute("SELECT * FROM archive_entries WHERE document_id=? ORDER BY version_number", (document_id,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        c.close()


def get_archive(db_path, document_id, version_number):
    c = _conn(db_path)
    try:
        r = c.execute("SELECT * FROM archive_entries WHERE document_id=? AND version_number=?", (document_id, version_number)).fetchone()
        return dict(r) if r else None
    finally:
        c.close()


def verify_archive(entry):
    """Intégrité : le fichier est-il toujours celui du catalogue ?"""
    try:
        with open(entry["path"], "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest() == entry["sha256"]
    except OSError:
        return False
