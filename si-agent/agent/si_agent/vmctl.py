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
           "migrate": None, "backup": None, "move_disk": None, "clone": None, "replicate": None, "unreplicate": None,
           # #658 (item 112) : migration d'un serveur vers la virtualisation -- create (VM vide / conteneur depuis un modèle),
           # import_disk (image P2V -> disque de la VM, qm importdisk), set (options en liste blanche), destroy (confirm = vmid)
           "create": None, "import_disk": None, "set": None, "destroy": None}
OPS = ("migrate", "backup", "move_disk", "clone", "replicate", "unreplicate", "create", "import_disk", "set", "destroy")
BRIDGE_RE = re.compile(r"^vmbr\d{1,3}$")
HOSTNAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,62}$")
TEMPLATE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,62}:vztmpl/[A-Za-z0-9._+-]{1,120}$")
PATH_RE = re.compile(r"^/[A-Za-z0-9._/+-]{1,250}$")
OPTVAL_RE = re.compile(r"^[A-Za-z0-9=:,._/+ -]{1,200}$")
SET_KEYS = {"qemu": ("scsi0", "sata0", "virtio0", "ide0", "boot", "net0", "memory", "cores", "onboot", "name", "agent", "bios", "machine", "ostype", "description", "scsihw", "balloon"),
            "lxc": ("hostname", "memory", "cores", "net0", "onboot", "description", "swap")}
DISK_BUS_RE = re.compile(r"^(scsi|sata|virtio|ide)\d$")
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
    if action == "create": return build_create_argv(vmid, kind, params)
    if action == "import_disk":
        if kind != "qemu": return None, "import_disk : VM qemu seulement"
        path, storage = str(params.get("path") or ""), str(params.get("storage") or "")
        if not PATH_RE.match(path): return None, "path (fichier image sur le nœud : .vhdx, .img, .raw, .qcow2) requis"
        if not STORAGE_RE.match(storage): return None, "storage (stockage cible) requis"
        argv = ["qm", "importdisk", str(vmid), path, storage]
        if params.get("format") in ("raw", "qcow2", "vmdk"): argv += ["--format", params["format"]]
        return argv, None
    if action == "set":
        opts = params.get("options") or {}
        if not isinstance(opts, dict) or not opts: return None, "options {clé: valeur} requises"
        argv = [tool, "set", str(vmid)]
        for k, v in opts.items():
            if k not in SET_KEYS[kind]: return None, "option %s refusée (liste blanche : %s)" % (k, ", ".join(SET_KEYS[kind]))
            if not OPTVAL_RE.match(str(v)): return None, "valeur de %s invalide" % k
            argv += ["--" + k, str(v)]
        return argv, None
    if action == "destroy":
        if str(params.get("confirm") or "") != str(vmid): return None, "destroy : confirm doit répéter le vmid (%d)" % vmid
        return ([tool, "destroy", str(vmid), "--purge", "1"] + (["--destroy-unreferenced-disks", "1"] if kind == "qemu" else [])), None
    return None, "opération inconnue"


def build_create_argv(vmid, kind, params):
    """#658 : VM vide (qemu, réseau coupé si link_down, OVMF + TPM pour Windows) ou conteneur depuis un modèle (lxc)."""
    name = str(params.get("name") or "")
    if not HOSTNAME_RE.match(name): return None, "name (nom de la VM / du conteneur) requis"
    bridge = str(params.get("bridge") or "vmbr0")
    if not BRIDGE_RE.match(bridge): return None, "bridge : vmbrN"
    try: memory, cores = int(params.get("memory") or 2048), int(params.get("cores") or 2)
    except (TypeError, ValueError): return None, "memory (Mo) et cores entiers"
    if not (128 <= memory <= 1048576 and 1 <= cores <= 256): return None, "memory / cores hors bornes"
    storage = str(params.get("storage") or "")
    if kind == "lxc":
        template = str(params.get("template") or "")
        if not TEMPLATE_RE.match(template): return None, "template (ex. local:vztmpl/debian-12-standard_12.7-1_amd64.tar.zst) requis"
        if not STORAGE_RE.match(storage): return None, "storage (rootfs) requis"
        try: rootfs = int(params.get("rootfs_gb") or 8)
        except (TypeError, ValueError): return None, "rootfs_gb entier"
        ip = str(params.get("ip") or "dhcp")
        if not re.match(r"^(dhcp|\d{1,3}(\.\d{1,3}){3}/\d{1,2})$", ip): return None, "ip : dhcp ou a.b.c.d/nn"
        net = "name=eth0,bridge=%s,ip=%s" % (bridge, ip)
        if ip != "dhcp" and params.get("gateway") and re.match(r"^\d{1,3}(\.\d{1,3}){3}$", str(params["gateway"])): net += ",gw=%s" % params["gateway"]
        if params.get("link_down"): net += ",link_down=1"
        return ["pct", "create", str(vmid), template, "--hostname", name, "--memory", str(memory), "--cores", str(cores), "--net0", net,
                "--rootfs", "%s:%d" % (storage, rootfs), "--unprivileged", "1", "--start", "0", "--onboot", "0"], None
    ostype = str(params.get("ostype") or "l26")
    if ostype not in ("l26", "l24", "win10", "win11", "w2k19", "w2k22", "other"): return None, "ostype : l26, win10, win11, w2k19, w2k22, other"
    net = "virtio,bridge=%s" % bridge + (",link_down=1" if params.get("link_down") else "")
    argv = ["qm", "create", str(vmid), "--name", name, "--memory", str(memory), "--cores", str(cores), "--sockets", "1", "--cpu", "host",
            "--net0", net, "--scsihw", "virtio-scsi-single", "--ostype", ostype, "--agent", "1", "--onboot", "0"]
    if ostype.startswith("w"):
        if not STORAGE_RE.match(storage): return None, "storage requis pour Windows (disque EFI et TPM)"
        argv += ["--bios", "ovmf", "--machine", "q35", "--efidisk0", "%s:1,efitype=4m,pre-enrolled-keys=1" % storage, "--tpmstate0", "%s:1,version=v2.0" % storage]
    return argv, None


def parse_unused(config_text):
    """`qm config <vmid>` -> volume du premier disque `unusedN` (celui que vient de créer importdisk), ou None."""
    for line in (config_text or "").splitlines():
        m = re.match(r"^unused\d+:\s*(\S+)", line.strip())
        if m: return m.group(1).split(",")[0]
    return None


def build_attach_argv(vmid, bus, volume, boot=True):
    """Disque importé rattaché à la VM (scsi0 / sata0 / virtio0 / ide0) et placé en premier dans l'ordre de démarrage."""
    if not DISK_BUS_RE.match(str(bus or "")): return None, "attach : scsi0, sata0, virtio0 ou ide0"
    if not OPTVAL_RE.match(str(volume or "")) or ":" not in str(volume): return None, "volume importé introuvable (unused0 absent de la configuration)"
    argv = ["qm", "set", str(vmid), "--" + bus, volume + (",discard=on" if bus.startswith(("scsi", "virtio")) else "")]
    if boot: argv += ["--boot", "order=" + bus]
    return argv, None
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
