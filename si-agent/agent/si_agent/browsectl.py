# -*- coding: utf-8 -*-
"""Parcours de l'arborescence du poste (livraison #627) -- commande du central
`browse` {path?} : sans `path`, la liste des lecteurs (lettre, système de
fichiers, espace libre / total) ; avec `path` (lecteur, dossier ou partage
UNC \\\\serveur\\partage\\dossier), les sous-dossiers seulement, jamais les
fichiers. Sert au choix graphique de la cible d'une image (image_host) ou
d'un dossier quelconque depuis le hub / le central local.

Lecture seule, bornée (300 entrées), depuis le compte de l'agent (SYSTEM
sous Windows : les lecteurs réseau « mappés » d'une session utilisateur
n'y sont pas visibles -- taper le chemin UNC ; un partage accessible à
SYSTEM l'est aussi pour Disk2vhd, lancé par le même agent).
"""
import os
import re
import string

MAX_ENTRIES = 300
UNC_RE = re.compile(r"^\\\\[^\\/:*?\"<>|]+\\[^\\/:*?\"<>|]+")


def normalize(path):
    """Chemin nettoyé (séparateurs Windows, sans '..'), ou None si vide."""
    p = str(path or "").strip().strip('"')
    if not p:
        return None
    p = p.replace("/", "\\")
    if ".." in p.split("\\"):
        return None
    if re.match(r"^[A-Za-z]:$", p):
        p += "\\"
    return p


def parent_of(path):
    p = (path or "").rstrip("\\")
    if not p or re.match(r"^[A-Za-z]:$", p) or UNC_RE.match(p + "\\") and p.count("\\") <= 3:
        return None
    head = p.rsplit("\\", 1)[0]
    if re.match(r"^[A-Za-z]:$", head):
        head += "\\"
    return head or None


def list_drives(exists=os.path.exists, usage=None, fstype=None):
    """Lettres présentes -> [{path, free, total, fs}] (pure par injection)."""
    out = []
    for letter in string.ascii_uppercase:
        root = "%s:\\" % letter
        if not exists(root):
            continue
        d = {"path": root, "free": None, "total": None, "fs": None}
        if usage:
            try:
                u = usage(root)
                d["free"], d["total"] = int(u.free), int(u.total)
            except OSError:
                pass
        if fstype:
            try:
                d["fs"] = fstype(root)
            except OSError:
                pass
        out.append(d)
    return out


def list_dir(path, scandir=os.scandir, usage=None):
    """Sous-dossiers de `path` -> {path, parent, entries, free, total} ou erreur."""
    entries = []
    try:
        with scandir(path) as it:
            for e in it:
                try:
                    if e.is_dir(follow_symlinks=False):
                        entries.append({"name": e.name, "path": os.path.join(path, e.name)})
                except OSError:
                    continue
                if len(entries) >= MAX_ENTRIES:
                    break
    except FileNotFoundError:
        return {"ok": False, "error": "chemin introuvable : %s" % path}
    except PermissionError:
        return {"ok": False, "error": "accès refusé : %s (compte de l'agent)" % path}
    except OSError as exc:
        return {"ok": False, "error": "%s : %s" % (path, exc)}
    entries.sort(key=lambda x: x["name"].lower())
    free = total = None
    if usage:
        try:
            u = usage(path)
            free, total = int(u.free), int(u.total)
        except OSError:
            pass
    return {"ok": True, "path": path, "parent": parent_of(path), "entries": entries, "free": free, "total": total, "truncated": len(entries) >= MAX_ENTRIES}


def run(params, exists=os.path.exists, scandir=os.scandir, usage=None, fstype=None):
    path = normalize((params or {}).get("path"))
    if path is None:
        if (params or {}).get("path"):
            return {"ok": False, "error": "chemin invalide"}
        return {"ok": True, "path": None, "parent": None, "drives": list_drives(exists, usage, fstype), "entries": []}
    return list_dir(path, scandir, usage)
