# -*- coding: utf-8 -*-
"""#765 : restes d'un rapatriement sur le nœud LOCAL -- archives vzdump gardées après restauration, fichiers .part
d'un export interrompu, images brutes copiées depuis le nœud distant (montées en boucle pour comparaison). L'agent les
LISTE (action xfer « leftovers ») ; le hub évalue les conditions (copie présente, démarrée, sauvegardée sur PBS) et
l'opérateur valide la suppression (action xfer « purge » : démontage, détachement de la boucle, effacement), avec
motif, journal d'audit et nouvelle vérification ici (fichier listé, pas en cours d'usage, non référencé par une conf).
Module pur : les accès système sont injectés (tests : test_leftovers.py)."""
import json
import os
import re
import time

DEFAULT_DIRS = ["/var/lib/vz/dump", "/data/dump", "/var/lib/vz/import"]
AUDIT_LOG = "/var/log/si-agent/xfer-purge-audit.log"
ARCHIVE_RE = re.compile(r"^vzdump-(lxc|qemu|openvz)-(\d+)-(\d{4})_(\d\d)_(\d\d)-(\d\d)_(\d\d)_(\d\d)\.(tar|vma|tgz)(\.(gz|zst|lzo))?(\.part)?$")
IMAGE_RE = re.compile(r"\.(raw|img|qcow2)$", re.I)
VMID_RES = (re.compile(r"(?:vm|subvol|base)-(\d{3,9})-disk"), re.compile(r"(?:^|[/_-])(\d{3,9})(?:[/_.-]|$)"))
MIN_IMAGE = 1 << 30
CONF_GLOB_DIRS = ("/etc/pve/lxc", "/etc/pve/qemu-server")


def guess_vmid(path):
    for rx in VMID_RES:
        m = rx.findall(path)
        if m:
            return int(m[-1])
    return None


def classify(path, size, mtime):
    """Un fichier d'un dossier surveillé -> élément ou None."""
    name = os.path.basename(path)
    m = ARCHIVE_RE.match(name)
    if m:
        kind = "part" if m.group(12) else "archive"
        return {"path": path, "kind": kind, "size": size, "mtime": int(mtime), "vmid": int(m.group(2)),
                "guest_kind": "lxc" if m.group(1) in ("lxc", "openvz") else "qemu"}
    if IMAGE_RE.search(name) and size >= MIN_IMAGE:
        return {"path": path, "kind": "image", "size": size, "mtime": int(mtime), "vmid": guess_vmid(path), "guest_kind": None}
    return None


def parse_losetup(text):
    """losetup -J -l -> {dev: fichier}."""
    try:
        d = json.loads(text or "{}")
    except ValueError:
        return {}
    out = {}
    for x in d.get("loopdevices") or []:
        bf = (x.get("back-file") or "").replace(" (deleted)", "").strip()
        if x.get("name") and bf:
            out[x["name"]] = bf
    return out


def parse_mounts(text):
    """/proc/mounts -> {source: point de montage}."""
    out = {}
    for line in (text or "").splitlines():
        p = line.split()
        if len(p) >= 2:
            out[p[0]] = p[1].replace("\\040", " ")
    return out


def scan(dirs, walk, losetup_text, mounts_text, stat, confs=None, busy=()):
    """dirs : dossiers surveillés ; walk(dir) -> [(chemin, taille, mtime)] ; stat(chemin) -> (taille, mtime) ou None ;
    confs : {nom de conf: texte} des CT / VM ; busy : chemins en cours d'usage (export en cours) -> éléments."""
    items, seen = [], set()
    for d in dirs:
        for path, size, mtime in walk(d) or []:
            it = classify(path, size, mtime)
            if it and path not in seen:
                seen.add(path); items.append(it)
    mounts = parse_mounts(mounts_text)
    for dev, bf in parse_losetup(losetup_text).items():
        it = next((x for x in items if x["path"] == bf), None)
        if not it:
            st = stat(bf)
            it = {"path": bf, "kind": "image", "size": st[0] if st else None, "mtime": int(st[1]) if st else None,
                  "vmid": guess_vmid(bf), "guest_kind": None, "missing": st is None}
            items.append(it)
        it["loop"] = {"dev": dev, "mount": mounts.get(dev)}
    for it in items:
        base = os.path.basename(it["path"])
        ref = sorted(n for n, t in (confs or {}).items() if base in (t or ""))
        if ref:
            it["in_use"] = "référencé par la configuration %s" % ", ".join(ref)
        elif it["path"] in busy or it["path"] + ".part" in busy:
            it["in_use"] = "export en cours"
    return sorted(items, key=lambda x: -(x.get("size") or 0))


def check_purge(p, items):
    """Paramètres de purge -> (élément, erreur)."""
    path, confirm, reason = str(p.get("path") or ""), str(p.get("confirm") or ""), str(p.get("reason") or "").strip()
    it = next((x for x in items if x["path"] == path), None)
    if not it:
        return None, "%s ne fait pas partie des restes listés (dossiers %s ou images en boucle)" % (path or "chemin", ", ".join(DEFAULT_DIRS))
    if confirm != os.path.basename(path):
        return None, "confirm doit répéter le nom du fichier (%s)" % os.path.basename(path)
    if len(reason) < 8:
        return None, "motif requis (8 caractères au moins)"
    if it.get("in_use"):
        return None, "suppression refusée : %s" % it["in_use"]
    return it, None


def purge_steps(it):
    """Commandes à passer avant l'effacement (démontage, détachement de la boucle)."""
    lo = it.get("loop") or {}
    steps = []
    if lo.get("mount"):
        steps.append(["umount", lo["mount"]])
    if lo.get("dev"):
        steps.append(["losetup", "-d", lo["dev"]])
    return steps


def audit_line(it, p, ok, msg):
    return json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%S"), "actor": p.get("actor"), "reason": p.get("reason"), "force": bool(p.get("force")),
                       "path": it.get("path") if it else p.get("path"), "size": (it or {}).get("size"), "ok": ok, "message": msg}, ensure_ascii=False)
