# -*- coding: utf-8 -*-
"""Image complète d'un poste Windows À CHAUD, en vue d'une virtualisation
(livraison #621, item 101) -- commande du central `image_host`
{target, tool_url?, tool_sha256?, drives?, force?}.

Outil : Disk2vhd (Sysinternals) -- instantané VSS, la machine reste en
service ; sortie VHDX (`-v`) importable tel quel dans Proxmox (`qm
importdisk`). L'agent télécharge disk2vhd64.exe (URL par défaut
live.sysinternals.com, remplaçable par un miroir interne ; empreinte SHA-256
vérifiée quand elle est fournie), refuse de partir si BitLocker protège un
volume visé (image illisible), si la cible manque d'espace (espace utilisé
des volumes × 1,1), si une image est déjà en cours ; puis lance
`disk2vhd64.exe <lecteurs|*> <cible>.vhdx -c -v -accepteula` DÉTACHÉ (30 à
60 min sur Gigabit pour 200-300 Go) et suit le travail à chaque tour de
boucle : événements `image-started`, `image-progress` (taille de la cible
toutes les 5 min), `image-finished` (taille, durée) ou `image-failed`.

Pure ici : validation des paramètres, analyse de `manage-bde -status`,
`fsutil volume diskfree`, construction de la ligne de commande, décision
de suivi. Tout ce qui touche le système est dans l'agent.
"""
import os
import re
import time

DEFAULT_TOOL_URL = "https://live.sysinternals.com/disk2vhd64.exe"
TARGET_RE = re.compile(r"^(\\\\[^\\/:*?\"<>|]+\\[^\\/:*?\"<>|]+(\\[^\\/:*?\"<>|]+)*|[A-Za-z]:(\\[^\\/:*?\"<>|]+)+)\\?$")
DRIVE_RE = re.compile(r"^[A-Za-z]:$")


def validate(params):
    """-> (plan, erreur). plan = {target_dir, target_file, drives, tool_url, tool_sha256, force}."""
    p = params or {}
    target = str(p.get("target") or "").strip().rstrip("\\")
    if not target or not TARGET_RE.match(target + "\\"):
        return None, "target : dossier cible (partage \\\\serveur\\partage\\dossier ou D:\\dossier)"
    drives = p.get("drives") or "*"
    if isinstance(drives, str):
        drives = [d.strip().upper() for d in drives.replace(",", " ").split() if d.strip()]
    if drives != ["*"] and not all(DRIVE_RE.match(d) for d in drives):
        return None, "drives : liste de lettres (C: D:) ou *"
    url = str(p.get("tool_url") or DEFAULT_TOOL_URL).strip()
    if not url.lower().startswith(("https://", "http://")):
        return None, "tool_url : http(s) requis"
    sha = str(p.get("tool_sha256") or "").strip().lower().replace("sha256:", "")
    if sha and not re.match(r"^[0-9a-f]{64}$", sha):
        return None, "tool_sha256 : 64 caractères hexadécimaux"
    name = str(p.get("name") or "").strip() or None
    return {"target_dir": target, "name": name, "drives": drives, "tool_url": url, "tool_sha256": sha or None, "force": bool(p.get("force"))}, None


def target_file(plan, hostname, now=None):
    stamp = time.strftime("%Y%m%d-%H%M", time.localtime(now or time.time()))
    base = re.sub(r"[^A-Za-z0-9._-]", "-", plan.get("name") or hostname or "poste")[:40]
    return os.path.join(plan["target_dir"], "%s-%s.vhdx" % (base, stamp))


def parse_bitlocker(text):
    """Sortie de `manage-bde -status` -> {lettre: 'on'|'off'|'suspended'|'?'} (fr/en)."""
    out = {}
    cur = None
    for line in (text or "").splitlines():
        m = re.match(r"^\s*(?:Volume|Volume)\s+([A-Za-z]:)", line)
        if m:
            cur = m.group(1).upper(); out[cur] = "?"; continue
        if cur and re.search(r"Protection Status|tat de la protection|Statut de la protection", line, re.I):
            low = line.lower()
            if "suspend" in low or "suspendu" in low:
                out[cur] = "suspended"
            elif re.search(r"\b(on|activ)", low.split(":")[-1]):
                out[cur] = "on"
            elif re.search(r"\b(off|d[ée]sactiv)", low.split(":")[-1]):
                out[cur] = "off"
    return out


def bitlocker_blocks(status, drives):
    """Lettres protégées parmi celles visées ('*' = toutes les lettres connues)."""
    wanted = list(status) if drives == ["*"] else [d.upper() for d in drives]
    return [d for d in wanted if status.get(d) == "on"]


def parse_used_bytes(diskfree_text):
    """`fsutil volume diskfree X:` (fr/en) -> (total, libre) ou (None, None)."""
    total = free = None
    for line in (diskfree_text or "").splitlines():
        m = re.search(r":\s*([\d][\d\s\xa0]*)", line)
        if not m:
            continue
        v = int(re.sub(r"\D", "", m.group(1)))
        low = line.lower()
        if "quota" in low:
            continue
        if ("free" in low or "libre" in low) and free is None:
            free = v
        elif ("total bytes" in low or "total d'octets" in low) and "free" not in low and "libre" not in low:
            total = v
    return total, free


def enough_space(used_bytes, free_target_bytes, margin=1.1):
    if used_bytes is None or free_target_bytes is None:
        return True  # inconnu : on n'empêche pas, l'échec sera signalé par disk2vhd
    return free_target_bytes >= used_bytes * margin


def build_argv(tool_path, plan, out_file):
    argv = [tool_path] + (["*"] if plan["drives"] == ["*"] else plan["drives"]) + [out_file, "-c", "-v", "-accepteula"]
    return argv


def follow(job, exists, size_of, alive, now):
    """Décision de suivi d'un travail détaché : job = {started, target_file, pid, last_size, last_report}.
    -> (état, détails) : 'running' | 'finished' | 'failed' | 'progress'."""
    running = alive(job.get("pid"))
    present = exists(job["target_file"])
    size = size_of(job["target_file"]) if present else 0
    if not running:
        if present and size > 0:
            return "finished", {"bytes": size, "seconds": int(now - job["started"])}
        return "failed", {"reason": "processus terminé sans image (voir le journal disk2vhd)", "seconds": int(now - job["started"])}
    if now - job.get("last_report", job["started"]) >= 300:
        return "progress", {"bytes": size, "seconds": int(now - job["started"])}
    return "running", {"bytes": size}


PROXMOX_RUNBOOK = """Import Proxmox de l'image (sur le nœud, image copiée dans /mnt/partage) :
  qm create <vmid> --name <nom> --memory 8192 --cores 4 --bios ovmf --machine q35 --ostype win11 \\
     --efidisk0 <stockage>:1 --tpmstate0 <stockage>:1,version=v2.0 --net0 virtio,bridge=vmbr0,link_down=1
  qm importdisk <vmid> /mnt/partage/<image>.vhdx <stockage> --format qcow2
  qm set <vmid> --sata0 <stockage>:vm-<vmid>-disk-2 --boot order=sata0
Démarrer réseau COUPÉ (link_down=1) : même nom, même IP que l'original. Après le premier
démarrage : pilotes VirtIO (virtio-win-guest-tools), basculer le disque en virtio/scsi,
activation Windows à vérifier, logiciel de pilotage lié au matériel (USB/série/carte) à tester."""
