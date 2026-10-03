# -*- coding: utf-8 -*-
"""Contrôle des VM / conteneurs d'un hôte Proxmox par l'agent (livraison #572)
-- commande `vm_action` du central : {vmid, action, kind?, snapname?}.

Actions : start, shutdown (ACPI, délai), stop (coupure), reboot, reset,
suspend, resume, snapshot (crée `snapname`), rollback (`snapname`),
delsnapshot (`snapname`). Ligne de commande construite (`build_argv`) et
résultat interprété (`interpret`) par des fonctions pures testées ; l'agent
doit tourner en root sur l'hôte (comme la sonde proxmox). Chaque action est
journalisée par un événement côté central (`command-vm`)."""
import re

ACTIONS = {"start": [], "shutdown": ["--timeout", "120"], "stop": [], "reboot": [], "reset": [], "suspend": [], "resume": [],
           "snapshot": None, "rollback": None, "delsnapshot": None,
           # #653 : opérations d'exploitation / PRA -- migrate (vers un nœud), backup (vzdump), move_disk (stockage), clone,
           # replicate / unreplicate (pvesr, réplication ZFS planifiée vers un nœud) ; argv construits par build_ops_argv
           "migrate": None, "backup": None, "move_disk": None, "clone": None, "replicate": None, "unreplicate": None}
OPS = ("migrate", "backup", "move_disk", "clone", "replicate", "unreplicate")
NODE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$")
STORAGE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,62}$")
DISK_RE = re.compile(r"^(scsi|virtio|sata|ide|efidisk|tpmstate|rootfs|mp)\d{0,2}$")
SCHEDULE_RE = re.compile(r"^[A-Za-z0-9*/:,. -]{1,40}$")
LONG_TIMEOUT = 3600          # migration, sauvegarde, déplacement de disque, clonage : opérations longues


def build_ops_argv(action, vmid, kind, params):
    """#653 : argv des opérations longues ; chaque paramètre est validé par un motif fermé (jamais interpolé tel quel)."""
    tool = KINDS[kind]
    if action == "migrate":
        target = str(params.get("target") or "")
        if not NODE_RE.match(target): return None, "target (nœud cible) requis"
        argv = [tool, "migrate", str(vmid), target]
        if kind == "qemu" and params.get("online", True): argv.append("--online")
        if kind == "lxc" and params.get("online", True): argv.append("--restart")
        if params.get("with_local_disks"): argv.append("--with-local-disks")
        return argv, None
    if action == "backup":
        storage = str(params.get("storage") or "")
        if not STORAGE_RE.match(storage): return None, "storage (stockage de sauvegarde) requis"
        mode = str(params.get("mode") or "snapshot")
        if mode not in ("snapshot", "suspend", "stop"): return None, "mode : snapshot, suspend ou stop"
        argv = ["vzdump", str(vmid), "--storage", storage, "--mode", mode, "--compress", "zstd"]
        if params.get("notes"): argv += ["--notes-template", re.sub(r"[^\w .:-]", "", str(params["notes"]))[:80]]
        return argv, None
    if action == "move_disk":
        disk, storage = str(params.get("disk") or ""), str(params.get("storage") or "")
        if not DISK_RE.match(disk): return None, "disk (scsi0, virtio0, rootfs, mp0…) requis"
        if not STORAGE_RE.match(storage): return None, "storage (stockage cible) requis"
        if kind == "lxc": return ["pct", "move-volume", str(vmid), disk, storage, "--delete", "1"], None
        return ["qm", "disk", "move", str(vmid), disk, storage, "--delete", "1"], None
    if action == "clone":
        try: newid = int(params.get("newid"))
        except (TypeError, ValueError): return None, "newid entier requis"
        if newid <= 0 or newid == vmid: return None, "newid invalide"
        argv = [tool, "clone", str(vmid), str(newid)]
        if params.get("name") and SNAP_RE.match(str(params["name"])): argv += ["--name" if kind == "qemu" else "--hostname", str(params["name"])]
        if params.get("full", True): argv.append("--full")
        if params.get("storage") and STORAGE_RE.match(str(params["storage"])): argv += ["--storage", str(params["storage"])]
        if params.get("target") and NODE_RE.match(str(params["target"])): argv += ["--target", str(params["target"])]
        return argv, None
    if action == "replicate":
        target = str(params.get("target") or "")
        if not NODE_RE.match(target): return None, "target (nœud de réplication) requis"
        try: jobnum = int(params.get("job", 0))
        except (TypeError, ValueError): return None, "job entier"
        schedule = str(params.get("schedule") or "*/15")
        if not SCHEDULE_RE.match(schedule): return None, "schedule invalide (format calendrier Proxmox, ex. */15, 2:00)"
        argv = ["pvesr", "create-local-job", "%d-%d" % (vmid, jobnum), target, "--schedule", schedule]
        if params.get("comment"): argv += ["--comment", re.sub(r"[^\w .:-]", "", str(params["comment"]))[:80]]
        return argv, None
    if action == "unreplicate":
        try: jobnum = int(params.get("job", 0))
        except (TypeError, ValueError): return None, "job entier"
        return ["pvesr", "delete", "%d-%d" % (vmid, jobnum), "--force", "1"], None
    return None, "opération inconnue"
KINDS = {"qemu": "qm", "lxc": "pct"}
SNAP_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,39}$")


def build_argv(params):
    """-> (argv, erreur). vmid entier > 0, action connue, snapname sûr."""
    try:
        vmid = int(params.get("vmid"))
    except (TypeError, ValueError):
        return None, "vmid entier requis"
    if vmid <= 0:
        return None, "vmid invalide"
    action = str(params.get("action") or "").strip().lower()
    if action not in ACTIONS:
        return None, "action inconnue (%s)" % ", ".join(sorted(ACTIONS))
    kind = str(params.get("kind") or "qemu").lower()
    tool = KINDS.get(kind)
    if not tool:
        return None, "kind : qemu ou lxc"
    if kind == "lxc" and action in ("reset",):
        return None, "action %s impossible sur un conteneur" % action
    if action in OPS:
        return build_ops_argv(action, vmid, kind, params)
    if action in ("snapshot", "rollback", "delsnapshot"):
        snap = str(params.get("snapname") or "").strip()
        if not SNAP_RE.match(snap):
            return None, "snapname : lettres/chiffres/_/-, commence par une lettre, 40 max"
        argv = [tool, action, str(vmid), snap]
        if action == "snapshot" and params.get("description"):
            argv += ["--description", str(params["description"])[:200]]
        if action == "snapshot" and kind == "qemu" and params.get("vmstate"):
            argv += ["--vmstate", "1"]
        return argv, None
    return [tool, action, str(vmid)] + list(ACTIONS[action]), None


def interpret(r):
    """Résultat de run_cmd -> {ok, stdout, stderr, returncode}."""
    rc = getattr(r, "returncode", -1)
    out = (getattr(r, "stdout", "") or "").strip()[-2000:]
    err = (getattr(r, "stderr", "") or "").strip()[-2000:]
    if rc == -127:
        return {"ok": False, "error": "qm/pct/vzdump/pvesr absent : cet hôte n'est pas un Proxmox", "returncode": rc}
    if rc == -124:
        return {"ok": False, "error": "délai dépassé (l'action peut se poursuivre côté Proxmox)", "returncode": rc, "stdout": out, "stderr": err}
    return {"ok": rc == 0, "error": None if rc == 0 else (err or out or "code %s" % rc), "returncode": rc, "stdout": out, "stderr": err}


def run(cmd, params, timeout=180):
    argv, err = build_argv(params or {})
    if err:
        return {"ok": False, "error": err}
    if str((params or {}).get("action") or "").lower() in OPS:
        timeout = LONG_TIMEOUT
    res = interpret(cmd(argv, timeout=timeout))
    res["argv"] = argv
    return {"ok": res["ok"], "error": res["error"], "result": res}
