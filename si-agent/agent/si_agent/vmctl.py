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
           "snapshot": None, "rollback": None, "delsnapshot": None}
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
        return {"ok": False, "error": "qm/pct absent : cet hôte n'est pas un Proxmox", "returncode": rc}
    if rc == -124:
        return {"ok": False, "error": "délai dépassé (l'action peut se poursuivre côté Proxmox)", "returncode": rc, "stdout": out, "stderr": err}
    return {"ok": rc == 0, "error": None if rc == 0 else (err or out or "code %s" % rc), "returncode": rc, "stdout": out, "stderr": err}


def run(cmd, params, timeout=180):
    argv, err = build_argv(params or {})
    if err:
        return {"ok": False, "error": err}
    res = interpret(cmd(argv, timeout=timeout))
    res["argv"] = argv
    return {"ok": res["ok"], "error": res["error"], "result": res}
