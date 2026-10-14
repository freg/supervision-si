# -*- coding: utf-8 -*-
"""#750 : rapatriement d'un CT / d'une VM d'un nœud Proxmox distant (hors cluster, ex. OVH) vers le nœud de l'agent, piloté
depuis le hub. Tout passe par ssh vers les nœuds déclarés dans pve-remote.json (nom -> hôte, clé) : le hub ne connaît que
le NOM du nœud distant, jamais son adresse ni sa clé.

  export    : vzdump --stdout sur le distant (débit borné), flux écrit dans le dossier de dump local, puis restauration
              (pct restore / qmrestore --unique) sous un nouvel identifiant ; l'archive est gardée ou supprimée ;
  verify    : liste triée (chemin, taille, date) de l'original et de la copie, comparée ; exclusions vzdump attendues ;
  destroy   : destruction de l'original sur le distant, après réduction de ses images brutes par tranches (pas de gel
              d'IO), seulement s'il est arrêté, que la copie locale existe, et dans la plage horaire demandée.
Fonctions pures (construction des commandes, comparaison) ; l'exécution détachée est dans agent.py."""
import json
import re
import shlex

REMOTE_FILE = "/etc/si-agent/pve-remote.json"
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$")
STORAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,62}$")
DIR_RE = re.compile(r"^/[A-Za-z0-9._/+-]{1,200}$")
WINDOW_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)-([01]\d|2[0-3]):([0-5]\d)$")
KINDS = ("lxc", "qemu")
MODES = ("stop", "snapshot", "suspend")
# vzdump exclut par défaut ces chemins d'un conteneur : leur absence dans la copie n'est pas une différence
VZDUMP_EXCLUDED = (re.compile(r"^\./tmp/."), re.compile(r"^\./var/tmp/."), re.compile(r"^\./var/run/.+\.pid$"), re.compile(r"^\./run/.+\.pid$"))
PRUNE = ("./proc/", "./sys/", "./dev/")


def load_remotes(text):
    """Contenu de pve-remote.json -> {nom: {host, user, key}}."""
    try:
        rows = json.loads(text or "[]")
    except ValueError:
        return {}
    out = {}
    for h in rows if isinstance(rows, list) else []:
        if isinstance(h, dict) and h.get("host"):
            out[str(h.get("name") or h["host"])] = {"host": str(h["host"]), "user": str(h.get("user") or "root"), "key": h.get("key")}
    return out


def ssh_argv(h):
    a = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=30", "-o", "StrictHostKeyChecking=accept-new"]
    if h.get("key"):
        a += ["-i", str(h["key"]), "-o", "IdentitiesOnly=yes"]
    return a + ["%s@%s" % (h.get("user") or "root", h["host"])]


def tool(kind):
    return "pct" if kind == "lxc" else "qm"


def check(p, need):
    """Paramètres communs -> (dict normalisé, erreur)."""
    q = {}
    remote = str(p.get("remote") or "")
    if not NAME_RE.match(remote):
        return None, "remote : nom du nœud distant (pve-remote.json)"
    q["remote"] = remote
    q["kind"] = str(p.get("kind") or "lxc")
    if q["kind"] not in KINDS:
        return None, "kind : lxc ou qemu"
    for k in ("vmid", "newid", "copy"):
        if k in need or p.get(k) not in (None, ""):
            try:
                q[k] = int(p.get(k))
            except (TypeError, ValueError):
                return None, "%s entier requis" % k
            if q[k] < 100:
                return None, "%s ≥ 100" % k
    if "storage" in need:
        q["storage"] = str(p.get("storage") or "")
        if not STORAGE_RE.match(q["storage"]):
            return None, "storage : stockage Proxmox local"
    q["dumpdir"] = str(p.get("dumpdir") or "/var/lib/vz/dump")
    if not DIR_RE.match(q["dumpdir"]) or ".." in q["dumpdir"]:
        return None, "dumpdir : chemin absolu"
    q["mode"] = str(p.get("mode") or "stop")
    if q["mode"] not in MODES:
        return None, "mode : stop, snapshot ou suspend"
    try:
        q["bwlimit_mbps"] = max(0.0, float(p.get("bwlimit_mbps") or 0))
        q["slice_gb"] = max(1, int(p.get("slice_gb") or 10))
        q["pause_s"] = max(0, min(600, int(p.get("pause_s") or 20)))
    except (TypeError, ValueError):
        return None, "bwlimit_mbps, slice_gb, pause_s numériques"
    q["window"] = str(p.get("window") or "")
    if q["window"] and not WINDOW_RE.match(q["window"]):
        return None, "window : HH:MM-HH:MM (ex. 20:00-07:00)"
    q["keep_archive"] = bool(p.get("keep_archive"))
    q["confirm"] = str(p.get("confirm") or "")
    return q, None


def archive_name(kind, vmid, stamp):
    return "vzdump-%s-%d-%s.%s.zst" % (kind, vmid, stamp, "tar" if kind == "lxc" else "vma")


def export_argv(h, q):
    """ssh distant : vzdump --stdout (zstd), débit borné en Kio/s."""
    cmd = ["vzdump", str(q["vmid"]), "--stdout", "--compress", "zstd", "--mode", q["mode"]]
    if q.get("bwlimit_mbps"):
        cmd += ["--bwlimit", str(int(q["bwlimit_mbps"] * 1000 / 8))]
    return ssh_argv(h) + [" ".join(shlex.quote(c) for c in cmd)]


def restore_argv(q, archive):
    if q["kind"] == "lxc":
        return ["pct", "restore", str(q["newid"]), archive, "--storage", q["storage"], "--unique", "1"]
    return ["qmrestore", archive, str(q["newid"]), "--storage", q["storage"], "--unique", "1"]


def in_window(window, hhmm):
    """window 'HH:MM-HH:MM' (peut passer minuit), hhmm 'HH:MM' -> bool ; fenêtre vide = toujours."""
    if not window:
        return True
    a, b = window.split("-")
    return (a <= hhmm < b) if a <= b else (hhmm >= a or hhmm < b)


# Liste triée d'une arborescence : chemin \t taille (0 pour un dossier : les tailles de dossier dépendent du système de
# fichiers) \t date (secondes). Racine : rootfs monté par pct mount (arrêté) ou /proc/PID/root (en marche).
LIST_SH = (r"""R=%(root)s; cd "$R" || exit 4; LC_ALL=C find . \( -path ./proc -o -path ./sys -o -path ./dev \) -prune -o """
           r"""\( -type d -printf '%%p\t0\t%%T@\n' \) -o -printf '%%p\t%%s\t%%T@\n' | sed -E 's/\.[0-9]+$//' | LC_ALL=C sort""")


def list_script(kind, vmid):
    """Script shell : monte (si arrêté), liste, démonte. Code 3 = type non pris en charge."""
    if kind != "lxc":
        return "echo 'comparaison de fichiers : conteneurs seulement' >&2; exit 3"
    return ("ID=%d; if pct status $ID | grep -q running; then P=$(lxc-info -n $ID -p -H); ROOT=/proc/$P/root; M=0; "
            "else pct mount $ID >/dev/null || exit 5; ROOT=/var/lib/lxc/$ID/rootfs; M=1; fi; "
            "( %s ); RC=$?; [ $M = 1 ] && pct unmount $ID; exit $RC") % (vmid, LIST_SH % {"root": "$ROOT"})


def parse_list(text):
    out = {}
    for line in (text or "").splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            out[parts[0]] = (parts[1], parts[2])
    return out


def compare(orig, copy, limit=40):
    """orig, copy : {chemin: (taille, date)} -> résumé : absents de la copie (hors exclusions vzdump), en trop, différents."""
    def excluded(p):
        return any(r.match(p) for r in VZDUMP_EXCLUDED)
    missing = [p for p in orig if p not in copy and not excluded(p)]
    skipped = [p for p in orig if p not in copy and excluded(p)]
    extra = [p for p in copy if p not in orig]
    changed = [p for p in orig if p in copy and orig[p] != copy[p] and p != "."]
    size = lambda d: sum(int(v[0]) for v in d.values() if v[0].isdigit())  # noqa: E731
    return {"identical": not (missing or extra or changed), "orig_files": len(orig), "copy_files": len(copy),
            "orig_bytes": size(orig), "copy_bytes": size(copy), "missing": len(missing), "extra": len(extra), "changed": len(changed),
            "vzdump_excluded": len(skipped), "samples": {"missing": sorted(missing)[:limit], "extra": sorted(extra)[:limit],
                                                       "changed": [{"path": p, "orig": orig[p], "copy": copy[p]} for p in sorted(changed)[:limit]]}}


def destroy_script(q):
    """Sur le distant : refuse si en marche ; réduit chaque image brute (fichier) par tranches ; puis destroy --purge."""
    t = tool(q["kind"])
    return ("set -e; ID=%(id)d; S=$(%(t)s status $ID) || exit 6; echo \"$S\" | grep -q stopped || { echo \"$ID n'est pas arrêté : $S\" >&2; exit 7; }; "
            "for V in $(%(t)s config $ID | sed -nE '/media=cdrom/d; s/^(rootfs|mp[0-9]+|scsi[0-9]+|virtio[0-9]+|sata[0-9]+|ide[0-9]+|efidisk0|tpmstate0): ([^,]+).*/\\2/p'); do "
            "[ \"$V\" = none ] && continue; P=$(pvesm path \"$V\" 2>/dev/null) || continue; [ -f \"$P\" ] || continue; "
            "while [ $(stat -c %%s \"$P\") -gt %(sl)d ]; do truncate -s -%(g)dG \"$P\"; echo \"tranche $P $(stat -c %%s \"$P\")\"; sleep %(ps)d; done; done; "
            "%(t)s destroy $ID --purge 1; echo DESTROY-OK") % {"id": q["vmid"], "t": t, "sl": q["slice_gb"] * 2**30, "g": q["slice_gb"], "ps": q["pause_s"]}
