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
    tool_args = p.get("tool_args")
    if isinstance(tool_args, str):
        tool_args = tool_args.split()
    if tool_args is not None and (not isinstance(tool_args, list) or not all(re.match(r"^-[A-Za-z]+$", str(a)) for a in tool_args)):
        return None, "tool_args : options Disk2vhd (-accepteula -h -c)"
    share, err = validate_share(p.get("share"), target)
    if err:
        return None, err
    return {"target_dir": target, "name": name, "drives": drives, "tool_url": url, "tool_sha256": sha or None, "force": bool(p.get("force")),
            "tool_args": tool_args, "transfer": bool(p.get("transfer")) and not share, "delete_after": bool(p.get("delete_after")), "share": share}, None


SHARE_RE = re.compile(r"^\\\\[^\\/:*?\"<>|]+\\[^\\/:*?\"<>|]+$")


def validate_share(share, target):
    """#635 : partage du serveur monté par l'agent (SYSTEM) le temps de l'image :
    {unc: \\\\serveur\\partage, user, password, domain?} ; la cible doit être sous ce partage."""
    if not share:
        return None, None
    if not isinstance(share, dict):
        return None, "share : {unc, user, password}"
    unc = str(share.get("unc") or "").strip().rstrip("\\")
    if not SHARE_RE.match(unc):
        return None, "share.unc : \\\\serveur\\partage"
    user = str(share.get("user") or "").strip()
    pwd = share.get("password")
    if not user or not isinstance(pwd, str) or not pwd:
        return None, "share.user / share.password requis"
    if not target.lower().startswith(unc.lower()):
        return None, "target doit être sous le partage %s" % unc
    domain = str(share.get("domain") or "").strip() or None
    return {"unc": unc, "user": ("%s\\%s" % (domain, user)) if domain else user, "password": pwd}, None


def redact(params):
    """Paramètres sans mot de passe de partage (stockage / affichage)."""
    p = dict(params or {})
    if isinstance(p.get("share"), dict) and "password" in p["share"]:
        p["share"] = dict(p["share"], password="***")
    return p


def target_file(plan, hostname, now=None, ext="vhdx"):
    stamp = time.strftime("%Y%m%d-%H%M", time.localtime(now or time.time()))
    base = re.sub(r"[^A-Za-z0-9._-]", "-", plan.get("name") or hostname or "poste")[:40]
    return os.path.join(plan["target_dir"], "%s-%s.%s" % (base, stamp, ext))


# ---- #658 (item 112) : image à chaud d'un serveur LINUX (dd du disque système, compressé zstd), même suivi que Disk2vhd
LINUX_TARGET_RE = re.compile(r"^/[A-Za-z0-9._/+-]{1,250}$")
DEVICE_RE = re.compile(r"^/dev/[A-Za-z0-9/_-]{1,60}$")


def validate_linux(params):
    """-> (plan, erreur). plan = {target_dir, device?, name, force, transfer, delete_after}. target_dir = dossier
    ABSOLU (point de montage NFS/CIFS ou disque séparé : jamais le disque imagé, vérifié par l'agent)."""
    p = params or {}
    target = str(p.get("target") or "").strip().rstrip("/")
    if not LINUX_TARGET_RE.match(target):
        return None, "target : dossier absolu sur un stockage séparé (ex. /mnt/images)"
    device = str(p.get("device") or "").strip() or None
    if device and not DEVICE_RE.match(device):
        return None, "device : /dev/sdX ou /dev/nvme0n1 (vide = disque de la racine)"
    name = str(p.get("name") or "").strip() or None
    return {"target_dir": target, "device": device, "name": name, "force": bool(p.get("force")), "transfer": bool(p.get("transfer")),
            "delete_after": bool(p.get("delete_after")), "share": None}, None


def parent_disk(source, pkname_of):
    """Disque physique derrière un volume (/dev/sda2, /dev/mapper/vg-root -> sda) : remonte `lsblk -no pkname` jusqu'au bout."""
    cur, seen = (source or "").strip(), 0
    while cur and seen < 8:
        up = (pkname_of(cur) or "").strip().splitlines()
        up = up[0].strip() if up else ""
        if not up: break
        cur, seen = "/dev/" + up, seen + 1
    return cur or None


def build_linux_argv(device, out_file):
    """dd du disque entier, compressé à la volée (zstd multi-fil) ; device et out_file déjà validés par motif fermé."""
    return ["sh", "-c", "dd if=%s bs=4M status=none | zstd -T0 -3 -q -o %s" % (device, out_file)]


LINUX_RUNBOOK = """Import Proxmox de l'image Linux (.img.zst = disque entier) : zstd -d <image>.img.zst -o <vmid>.img ;
  qm create <vmid> --name <nom> --memory 4096 --cores 2 --ostype l26 --net0 virtio,bridge=vmbr0,link_down=1 --scsihw virtio-scsi-single
  qm importdisk <vmid> <vmid>.img <stockage> ; qm set <vmid> --scsi0 <stockage>:vm-<vmid>-disk-0 --boot order=scsi0
Image prise À CHAUD : cohérence comme après une coupure de courant (fsck au premier démarrage) ; geler les
écritures applicatives (services en lecture seule) pendant l'image. Depuis le hub : plan de migration (#658)."""


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
    """`fsutil volume diskfree X:` (fr/en) -> (total, libre) ou (None, None).
    Sortie réelle (#629, Windows 11 fr) : « Nombre total d'octets libres », « Nombre
    total d'octets », « … libres dans le quota », « … réservés », « Octets utilisés »…
    -> premier total sans libre/quota/réservé, premier libre sans quota."""
    total = free = None
    for line in (diskfree_text or "").splitlines():
        m = re.search(r":\s*([\d][\d\s\xa0]*)", line)
        if not m:
            continue
        v = int(re.sub(r"\D", "", m.group(1)))
        low = line.lower()
        if "quota" in low or "pool" in low or "reserv" in low or "réserv" in low or "commit" in low or "valid" in low or "disponible" in low or "available" in low:
            continue
        if ("free" in low or "libre" in low):
            if free is None:
                free = v
        elif ("total bytes" in low or "total d'octets" in low) and total is None:
            total = v
    return total, free


def parse_used_direct(diskfree_text):
    """Ligne « Used bytes » / « Octets utilisés » quand fsutil la donne (Windows 10+)."""
    for line in (diskfree_text or "").splitlines():
        low = line.lower()
        if ("used bytes" in low or "octets utilis" in low) and ":" in line:
            m = re.search(r":\s*([\d][\d\s\xa0]*)", line)
            if m:
                return int(re.sub(r"\D", "", m.group(1)))
    return None


def used_bytes(diskfree_text):
    """Espace occupé du volume : « Octets utilisés » si présent, sinon total - libre, sinon None."""
    direct = parse_used_direct(diskfree_text)
    if direct is not None:
        return direct
    total, free = parse_used_bytes(diskfree_text)
    if total is not None and free is not None and total >= free:
        return total - free
    return None


def enough_space(used_bytes, free_target_bytes, margin=1.1):
    if used_bytes is None or free_target_bytes is None:
        return True  # inconnu : on n'empêche pas, l'échec sera signalé par disk2vhd
    return free_target_bytes >= used_bytes * margin


STALL_SECONDS = 180


def build_argv(tool_path, plan, out_file):
    """Disk2vhd : options AVANT les volumes -- `-accepteula`, `-h` (VHDX), `-c` (cliché VSS).
    (#630 : l'ancienne forme `… -c -v -accepteula` en fin de ligne n'était pas comprise ;
    Disk2vhd affichait alors sa boîte d'usage, invisible sous SYSTEM, et attendait.)
    `tool_args` du paramétrage remplace les options par défaut si Sysinternals les change."""
    opts = plan.get("tool_args") or ["-accepteula", "-h", "-c"]
    return [tool_path] + list(opts) + (["*"] if plan["drives"] == ["*"] else plan["drives"]) + [out_file]


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
    if not present and now - job["started"] >= STALL_SECONDS:
        # #630 : vivant mais rien d'écrit après 3 min = Disk2vhd bloqué sur une boîte de dialogue (usage, EULA, erreur)
        return "stalled", {"reason": "aucun fichier créé après %d s : Disk2vhd attend sur une boîte de dialogue (options, licence ou erreur) -- processus arrêté" % STALL_SECONDS,
                           "seconds": int(now - job["started"])}
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
