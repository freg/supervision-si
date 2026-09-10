"""Collecteurs de l'hôte (livraison #420, backlog 63) -- « l'agent host
surveille le host : CPU, disque, mémoire, logs, risques internes ».

Tout passe par `/proc`, `/sys`, `/etc` et quelques binaires système
(`systemctl`, `journalctl`, `ss`), jamais une bibliothèque tierce :
l'agent doit tourner tel quel sur un Debian/Ubuntu minimal, un Pi, une
VM ancienne, avec le seul Python 3 du système. `files` (lecture de
fichier) et `cmd` (exécution) sont INJECTABLES : les tests rejouent des
contenus réels capturés, sans hôte.

Chaque collecteur renvoie un dict sérialisable ; un collecteur qui n'a pas
ce qu'il lui faut (fichier absent, binaire absent) renvoie ce qu'il peut
et jamais une exception -- l'agent doit produire une mesure même sur un
hôte exotique, quitte à ce qu'elle soit partielle et le dise
(`partial: [...]`).
"""
import collections
import errno
import json
import os
import re
import select
import shutil
import signal
import subprocess
import time

DEFAULT_TIMEOUT = 15


class CmdResult(object):
    __slots__ = ("returncode", "stdout", "stderr")

    def __init__(self, returncode, stdout, stderr=""):
        self.returncode, self.stdout, self.stderr = returncode, stdout, stderr


def run_cmd(argv, timeout=DEFAULT_TIMEOUT, env=None, confined=None):
    """Exécution réelle ; jamais d'exception (binaire absent → -127, délai
    → -124), même contrat que netprobe_agent.tasks.run_cmd. `env` :
    variables AJOUTÉES à l'environnement courant (collecte) ; `confined`
    (plugins, #422) = {"env": environnement COMPLET de remplacement,
    "preexec_fn": confinement dans l'enfant, "cwd": dossier} -- la sonde
    tourne dans sa propre session et le délai tue tout son groupe de
    processus, jamais seulement le premier."""
    try:
        full_env = None
        if confined and confined.get("env") is not None:
            full_env = {k: str(v) for k, v in confined["env"].items()}
        elif env:
            full_env = dict(os.environ)
            full_env.update({k: str(v) for k, v in env.items()})
        if not confined:
            p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, env=full_env)
            return CmdResult(p.returncode, p.stdout, p.stderr)
        proc = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=full_env,
                                cwd=confined.get("cwd"), preexec_fn=confined.get("preexec_fn"))
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            _kill_group(proc)
            return CmdResult(-124, "", "délai dépassé (%ss) : %s" % (timeout, " ".join(argv)))
        return CmdResult(proc.returncode, out, err)
    except FileNotFoundError:
        return CmdResult(-127, "", "binaire introuvable : %s" % argv[0])
    except subprocess.TimeoutExpired:
        return CmdResult(-124, "", "délai dépassé (%ss) : %s" % (timeout, " ".join(argv)))
    except (OSError, subprocess.SubprocessError) as exc:
        return CmdResult(-1, "", str(exc))


def _kill_group(proc):
    import signal
    try:
        if not hasattr(os, "killpg"):  # Windows (#440) : pas de groupe de processus POSIX
            raise OSError("killpg indisponible")
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except (OSError, ProcessLookupError):
        try:
            proc.kill()
        except OSError:
            pass
    try:
        proc.communicate(timeout=5)
    except Exception:  # noqa: BLE001
        pass


# En conteneur (#430, deploy-docker.sh) : le système de fichiers de l'hôte
# est monté en lecture seule sous SI_AGENT_HOST_ROOT (ex. /host). Les
# fichiers de configuration et journaux (/etc, /var, /boot) sont lus là ;
# /proc et /sys viennent du noyau, partagés (--pid host, --network host).
HOST_ROOT = os.environ.get("SI_AGENT_HOST_ROOT", "").rstrip("/")
_HOST_PREFIXED = ("/etc/", "/var/", "/boot/", "/home/", "/root/")


def host_path(path):
    """Chemin réel d'un fichier de l'hôte (préfixé en conteneur)."""
    if HOST_ROOT and path.startswith(_HOST_PREFIXED):
        return HOST_ROOT + path
    return path


def read_file(path):
    try:
        with open(host_path(path), "r", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def host_exists(path):
    return os.path.exists(host_path(path))


def _kv_file(text):
    """`/etc/os-release`, `/proc/meminfo`… → dict (clé: valeur brute)."""
    out = {}
    for line in (text or "").splitlines():
        if "=" in line and ":" not in line.split("=", 1)[0]:
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"')
        elif ":" in line:
            k, v = line.split(":", 1)
            out[k.strip()] = v.strip()
    return out


def _kb(value):
    m = re.match(r"\s*(\d+)", value or "")
    return int(m.group(1)) * 1024 if m else None


# ---------------------------------------------------------------------
# Identité et système
# ---------------------------------------------------------------------

def collect_system(files=read_file, hostname=None, exists=os.path.exists):
    osr = _kv_file(files("/etc/os-release"))
    uptime = None
    m = re.match(r"([\d.]+)", files("/proc/uptime") or "")
    if m:
        uptime = float(m.group(1))
    kernel = (files("/proc/sys/kernel/osrelease") or "").strip() or None
    cpus = len([l for l in (files("/proc/cpuinfo") or "").splitlines() if l.startswith("processor")]) or None
    model = None
    for line in (files("/proc/cpuinfo") or "").splitlines():
        if line.lower().startswith(("model name", "hardware", "model")):
            model = line.split(":", 1)[1].strip()
            if line.lower().startswith("model name"):
                break
    # Raspberry Pi : /proc/device-tree/model est plus parlant que cpuinfo.
    dt_model = (files("/proc/device-tree/model") or "").replace("\x00", "").strip()
    if dt_model:
        model = dt_model
    return {
        "hostname": hostname or (files("/etc/hostname") or "").strip() or None,
        "os": osr.get("PRETTY_NAME") or osr.get("NAME"),
        "os_id": osr.get("ID"),
        "os_version": osr.get("VERSION_ID"),
        "kernel": kernel,
        "cpus": cpus,
        "cpu_model": model,
        "uptime_seconds": uptime,
        # Debian/Ubuntu : fichier (souvent vide) déposé par apt quand un
        # redémarrage est requis -- son EXISTENCE compte, pas son contenu.
        "reboot_required": bool(exists("/var/run/reboot-required")),
    }


# ---------------------------------------------------------------------
# CPU / charge / mémoire
# ---------------------------------------------------------------------

def parse_proc_stat(text):
    """Première ligne `cpu ...` → (busy, total) en jiffies, ou None."""
    for line in (text or "").splitlines():
        if line.startswith("cpu "):
            parts = [int(x) for x in line.split()[1:] if x.isdigit()]
            if len(parts) < 4:
                return None
            idle = parts[3] + (parts[4] if len(parts) > 4 else 0)   # idle + iowait
            total = sum(parts)
            return total - idle, total
    return None


def cpu_percent(before, after):
    """Usage CPU entre deux lectures de /proc/stat (0-100), None si
    impossible (même instant, lecture manquante)."""
    if not before or not after:
        return None
    d_busy = after[0] - before[0]
    d_total = after[1] - before[1]
    if d_total <= 0:
        return None
    return round(100.0 * d_busy / d_total, 1)


def collect_cpu(files=read_file, sleep=time.sleep, sample_seconds=0.5, previous=None):
    """`previous` = (busy, total) d'un passage précédent : évite de dormir
    dans la boucle de l'agent ; sans lui, deux lectures espacées de
    `sample_seconds`."""
    now_stat = parse_proc_stat(files("/proc/stat"))
    if previous is None and now_stat is not None and sample_seconds:
        sleep(sample_seconds)
        previous, now_stat = now_stat, parse_proc_stat(files("/proc/stat"))
    load = (files("/proc/loadavg") or "").split()
    try:
        load1, load5, load15 = float(load[0]), float(load[1]), float(load[2])
    except (IndexError, ValueError):
        load1 = load5 = load15 = None
    return {
        "percent": cpu_percent(previous, now_stat),
        "load1": load1, "load5": load5, "load15": load15,
        "_stat": now_stat,   # pour le passage suivant (retiré avant envoi)
    }


def collect_memory(files=read_file):
    mi = _kv_file(files("/proc/meminfo"))
    total = _kb(mi.get("MemTotal"))
    available = _kb(mi.get("MemAvailable"))
    if available is None and total is not None:
        free = _kb(mi.get("MemFree")) or 0
        available = free + (_kb(mi.get("Buffers")) or 0) + (_kb(mi.get("Cached")) or 0)
    swap_total = _kb(mi.get("SwapTotal"))
    swap_free = _kb(mi.get("SwapFree"))
    used_pct = round(100.0 * (total - available) / total, 1) if total and available is not None else None
    swap_used_pct = round(100.0 * (swap_total - swap_free) / swap_total, 1) if swap_total and swap_free is not None else None
    return {
        "total_bytes": total, "available_bytes": available, "used_percent": used_pct,
        "swap_total_bytes": swap_total, "swap_used_percent": swap_used_pct,
    }


# ---------------------------------------------------------------------
# Disques
# ---------------------------------------------------------------------

_SKIP_FS = {"proc", "sysfs", "devtmpfs", "devpts", "tmpfs", "cgroup", "cgroup2", "pstore", "bpf", "securityfs",
            "debugfs", "tracefs", "configfs", "mqueue", "hugetlbfs", "fusectl", "fuse.gvfsd-fuse", "autofs",
            "binfmt_misc", "rpc_pipefs", "nsfs", "overlay", "squashfs", "efivarfs", "ramfs"}


def parse_mounts(text):
    """`/proc/mounts` → [{device, mountpoint, fstype}] des systèmes de
    fichiers « réels » (disques, cartes SD, NFS…), sans les pseudo-fs."""
    out = []
    seen = set()
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        dev, mp, fs = parts[0], parts[1].replace("\\040", " "), parts[2]
        if fs in _SKIP_FS or mp.startswith(("/snap/", "/proc", "/sys", "/dev", "/run")) or mp in seen:
            continue
        seen.add(mp)
        out.append({"device": dev, "mountpoint": mp, "fstype": fs, "options": parts[3] if len(parts) > 3 else ""})
    return out


# Systèmes de fichiers distants / montés par un utilisateur (sshfs, NFS,
# CIFS, rclone, WebDAV…) : signalés `remote`, et jamais tus quand leur
# lecture échoue (#438 : « je ne vois pas mon sshfs »).
_REMOTE_FS_PREFIXES = ("fuse.", "nfs", "cifs", "smb", "davfs", "9p", "ceph", "glusterfs", "afs", "lustre", "ncpfs")


# Supports amovibles / images montées (clé USB, ISO GParted, CD) : listés,
# jamais des risques de remplissage (#442 : un ISO monté en lecture seule
# à 100 % remontait « disque plein » en critique).
_REMOVABLE_FS = ("iso9660", "udf", "squashfs", "fuseblk", "vfat", "exfat")
_REMOVABLE_MOUNT_PREFIXES = ("/media/", "/run/media/", "/mnt/usb", "/cdrom", "/run/live/")


def is_removable_mount(mountpoint, fstype):
    return (mountpoint or "").startswith(_REMOVABLE_MOUNT_PREFIXES) or (fstype in ("iso9660", "udf", "squashfs"))


def is_remote_fs(fstype):
    return bool(fstype) and fstype.startswith(_REMOTE_FS_PREFIXES) and fstype not in ("fuse.gvfsd-fuse", "fuse.portal")


_Usage = collections.namedtuple("_Usage", "total used free")
REMOTE_STATVFS_TIMEOUT = 5.0


def fuse_owner(options):
    """(uid, gid) de l'utilisateur qui a fait un montage FUSE : FUSE inscrit
    lui-même `user_id=` / `group_id=` dans les options (`/proc/mounts`)."""
    uid = gid = None
    for opt in (options or "").split(","):
        if opt.startswith("user_id="):
            try:
                uid = int(opt[8:])
            except ValueError:
                pass
        elif opt.startswith("group_id="):
            try:
                gid = int(opt[9:])
            except ValueError:
                pass
    return uid, gid


def statvfs_isolated(path, uid=None, gid=None, timeout=REMOTE_STATVFS_TIMEOUT):
    """`statvfs` dans un processus fils, avec délai (un sshfs/NFS dont le
    serveur ne répond plus ne bloque jamais la collecte) et, si `uid` est
    donné et que l'agent est root, en se présentant comme cet utilisateur :
    FUSE n'autorise que l'utilisateur qui a monté (sauf allow_other), mais
    ne regarde que l'uid de l'appelant -- aucune option de montage ni
    configuration du serveur à changer (#439). Même forme de résultat que
    shutil.disk_usage ; lève OSError (errno ETIMEDOUT si délai)."""
    r, w = os.pipe()
    pid = os.fork()
    if pid == 0:  # fils
        try:
            os.close(r)
            if uid is not None:
                try:
                    os.setgroups([])
                except OSError:
                    pass
                os.setgid(gid if gid is not None else uid)
                os.setuid(uid)
            st = os.statvfs(path)
            total = st.f_frsize * st.f_blocks
            os.write(w, json.dumps({"total": total, "used": total - st.f_frsize * st.f_bfree, "free": st.f_frsize * st.f_bavail}).encode())
        except OSError as exc:
            os.write(w, json.dumps({"errno": exc.errno, "strerror": exc.strerror}).encode())
        finally:
            os._exit(0)
    os.close(w)
    try:
        ready, _, _ = select.select([r], [], [], timeout)
        if not ready:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
            os.waitpid(pid, 0)
            raise OSError(errno.ETIMEDOUT, "délai dépassé (%ss) : serveur injoignable ?" % timeout)
        data = os.read(r, 4096)
    finally:
        os.close(r)
    os.waitpid(pid, 0)
    try:
        d = json.loads(data.decode("utf-8") or "{}")
    except ValueError:
        d = {}
    if "total" not in d:
        raise OSError(d.get("errno") or errno.EIO, d.get("strerror") or "erreur")
    return _Usage(d["total"], d["used"], d["free"])


def _usage_error(fstype, exc, owner_uid=None, retried_as_owner=False, is_root=True):
    err = getattr(exc, "errno", None)
    if fstype and fstype.startswith("fuse.") and err in (errno.EPERM, errno.EACCES):
        if retried_as_owner:
            return "accès refusé, même en se présentant comme l'utilisateur du montage (uid %s) : montage FUSE (%s) -- sshfs -o allow_root, ou user_allow_other dans /etc/fuse.conf" % (owner_uid, fstype)
        if owner_uid is not None and not is_root:
            return "accès refusé : montage FUSE (%s) réservé à l'utilisateur uid %s ; l'agent n'est pas root, il ne peut pas se présenter comme lui" % (fstype, owner_uid)
        return "accès refusé : montage FUSE (%s) sans allow_other/allow_root -- seul l'utilisateur qui l'a monté peut le lire (sshfs -o allow_root, user_allow_other dans /etc/fuse.conf)" % fstype
    if err == errno.ESTALE:
        return "montage périmé (stale) : serveur injoignable ?"
    if err == errno.ETIMEDOUT:
        return "sans réponse : %s" % (getattr(exc, "strerror", None) or "délai dépassé")
    return "lecture impossible : %s" % (getattr(exc, "strerror", None) or str(exc) or "erreur")


def collect_disks(files=read_file, usage=shutil.disk_usage, host_root=None, usage_remote=None, usage_as=None, euid=None):
    """En conteneur (`host_root`, ex. /host) : seuls les montages de
    l'hôte (sous /host) comptent, affichés sans le préfixe.

    #438 : un montage dont la taille ne peut pas être lue (FUSE sans
    allow_other, NFS périmé…) est LISTÉ avec `error` (tailles à null)
    plutôt qu'ignoré ; en conteneur, la table de montage de l'hôte
    (`/proc/1/mounts`, visible grâce à --pid host) est comparée à ce que
    le conteneur voit : un montage fait sur l'hôte après le démarrage du
    conteneur (sans propagation rslave) apparaît avec `visible: false`.

    #439 : un système distant (`remote`) est mesuré par `usage_remote`
    (statvfs isolé avec délai) ; un FUSE qui refuse l'accès est remesuré
    par `usage_as(mountpoint, uid, gid)` en se présentant comme
    l'utilisateur du montage (`user_id=` des options) si l'agent est root
    -- `measured_as` le dit. Rien à changer sur l'hôte."""
    root = HOST_ROOT if host_root is None else host_root
    usage_remote = usage_remote or (lambda p: statvfs_isolated(p))
    usage_as = usage_as or (lambda p, u, g: statvfs_isolated(p, u, g))
    is_root = (os.geteuid() if euid is None else euid) == 0
    disks = []
    shown_points = set()
    for m in parse_mounts(files("/proc/mounts")):
        mountpoint = m["mountpoint"]
        if root:
            if mountpoint != root and not mountpoint.startswith(root + "/"):
                continue
            shown = mountpoint[len(root):] or "/"
            if shown.startswith(("/proc", "/sys", "/dev", "/run", "/snap/")):
                continue
        else:
            shown = mountpoint
        opts = (m.get("options") or "").split(",")
        entry = {"mountpoint": shown, "device": m["device"], "fstype": m["fstype"], "remote": is_remote_fs(m["fstype"]),
                 "readonly": "ro" in opts, "removable": is_removable_mount(shown, m["fstype"]),
                 "total_bytes": None, "used_bytes": None, "free_bytes": None, "used_percent": None, "visible": True}
        shown_points.add(shown)
        owner_uid, owner_gid = fuse_owner(m.get("options")) if m["fstype"].startswith("fuse.") else (None, None)
        try:
            u = usage_remote(mountpoint) if entry["remote"] else usage(mountpoint)
        except OSError as exc:
            u = None
            if owner_uid is not None and is_root and getattr(exc, "errno", None) in (errno.EPERM, errno.EACCES):
                try:
                    u = usage_as(mountpoint, owner_uid, owner_gid)
                    entry["measured_as"] = "uid %d" % owner_uid
                except OSError as exc2:
                    entry["error"] = _usage_error(m["fstype"], exc2, owner_uid, retried_as_owner=True)
            else:
                entry["error"] = _usage_error(m["fstype"], exc, owner_uid, is_root=is_root)
            if u is None:
                disks.append(entry)
                continue
        total = u.total
        if not total and owner_uid is not None:
            # Constaté avec un vrai sshfs (#439) : pour un autre utilisateur que
            # celui du montage, FUSE ne renvoie pas EACCES à statvfs mais des
            # tailles NULLES -- d'où le montage « invisible » d'avant.
            if is_root and "measured_as" not in entry:
                try:
                    u = usage_as(mountpoint, owner_uid, owner_gid)
                    entry["measured_as"] = "uid %d" % owner_uid
                    total = u.total
                except OSError as exc2:
                    entry["error"] = _usage_error(m["fstype"], exc2, owner_uid, retried_as_owner=True)
                    disks.append(entry)
                    continue
            if not total:
                entry["error"] = _usage_error(m["fstype"], OSError(errno.EACCES, "tailles nulles"), owner_uid, retried_as_owner=is_root, is_root=is_root)
                disks.append(entry)
                continue
        if not total:
            continue
        entry.update({"total_bytes": total, "used_bytes": u.used, "free_bytes": u.free, "used_percent": round(100.0 * u.used / total, 1)})
        disks.append(entry)
    if root:
        # Table de montage de l'hôte (PID 1 de l'hôte, --pid host) : ce que
        # l'hôte a monté et que le conteneur ne voit pas (propagation).
        host_view = files("/proc/1/mounts") or ""
        for m in parse_mounts(host_view):
            mp = m["mountpoint"]
            if mp in shown_points or mp.startswith((root + "/", "/proc", "/sys", "/dev", "/run", "/snap/")) or mp == root:
                continue
            if m["fstype"] == "overlay" or (m["device"] == "overlay"):
                continue
            disks.append({"mountpoint": mp, "device": m["device"], "fstype": m["fstype"], "remote": is_remote_fs(m["fstype"]),
                          "total_bytes": None, "used_bytes": None, "free_bytes": None, "used_percent": None, "visible": False,
                          "error": "monté sur l'hôte mais invisible depuis le conteneur (monté après son démarrage ?) -- relancer deploy-docker.sh (/host en rslave) ou redémarrer le conteneur"})
            shown_points.add(mp)
    return disks


# ---------------------------------------------------------------------
# Services, ports, journaux, comptes
# ---------------------------------------------------------------------

def collect_failed_services(cmd=run_cmd):
    r = cmd(["systemctl", "--failed", "--no-legend", "--plain", "--no-pager"])
    if r.returncode < 0 or (r.returncode != 0 and not (r.stdout or "").strip()):
        # absent, ou présent sans bus systemd joignable (conteneur, #430)
        return {"available": False, "failed": []}
    failed = []
    for line in r.stdout.splitlines():
        parts = line.split()
        if parts and parts[0].endswith((".service", ".timer", ".socket", ".mount")):
            failed.append(parts[0])
        elif len(parts) > 1 and parts[1].endswith((".service", ".timer", ".socket", ".mount")):
            failed.append(parts[1])   # ligne avec puce « ● »
    return {"available": True, "failed": failed}


def parse_ss_listening(text):
    """`ss -Hlntup` → [{proto, local, port, process}], toutes adresses."""
    out = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        proto = parts[0]
        local = parts[4] if parts[1] in ("LISTEN", "UNCONN") else parts[3]
        if ":" not in local:
            continue
        addr, port = local.rsplit(":", 1)
        try:
            port = int(port)
        except ValueError:
            continue
        addr = addr.strip("[]")
        process = None
        m = re.search(r'users:\(\("([^"]+)"', line)
        if m:
            process = m.group(1)
        out.append({"proto": proto, "address": addr, "port": port, "process": process,
                    "exposed": addr in ("0.0.0.0", "*", "::", "")})
    return out


def collect_listening_ports(cmd=run_cmd):
    r = cmd(["ss", "-Hlntup"])
    if r.returncode < 0:
        return {"available": False, "ports": []}
    return {"available": True, "ports": parse_ss_listening(r.stdout)}


def collect_log_errors(cmd=run_cmd, files=read_file, lines=40):
    """Dernières erreurs du journal : journald si présent, sinon la queue
    de /var/log/syslog ou /var/log/messages filtrée sur err/crit/fail."""
    argv = ["journalctl", "-p", "err", "-n", str(lines), "--no-pager", "-o", "short-iso", "--since", "-24h"]
    if HOST_ROOT:
        argv += ["-D", HOST_ROOT + "/var/log/journal"]  # journal de l'hôte lu directement, sans systemd dans le conteneur
    r = cmd(argv)
    if r.returncode >= 0 and r.returncode != -127:
        entries = [l for l in r.stdout.splitlines() if l and not l.startswith("-- ")]
        return {"source": "journald", "lines": entries[-lines:]}
    for path in ("/var/log/syslog", "/var/log/messages"):
        text = files(path)
        if text:
            pat = re.compile(r"\b(error|err|crit|critical|fail(ed|ure)?|panic|oom)\b", re.IGNORECASE)
            entries = [l for l in text.splitlines()[-2000:] if pat.search(l)]
            return {"source": path, "lines": entries[-lines:]}
    return {"source": None, "lines": []}


def collect_accounts(files=read_file):
    """Comptes à privilèges : membres de sudo/wheel/adm, comptes à shell
    interactif, comptes root-équivalents (uid 0 autres que root)."""
    groups = {}
    for line in (files("/etc/group") or "").splitlines():
        parts = line.split(":")
        if len(parts) >= 4:
            groups[parts[0]] = [u for u in parts[3].split(",") if u]
    sudoers = sorted(set(groups.get("sudo", []) + groups.get("wheel", []) + groups.get("admin", [])))
    interactive, uid0 = [], []
    for line in (files("/etc/passwd") or "").splitlines():
        parts = line.split(":")
        if len(parts) < 7:
            continue
        name, uid, shell = parts[0], parts[2], parts[6]
        if uid == "0" and name != "root":
            uid0.append(name)
        if shell.endswith(("sh",)) and not shell.endswith(("nologin", "false")):
            interactive.append(name)
    return {"sudoers": sudoers, "interactive": interactive, "uid0_not_root": uid0}


# ---------------------------------------------------------------------
# Inventaire des capacités (binaires disponibles)
# ---------------------------------------------------------------------

KNOWN_TOOLS = ["nmap", "iperf3", "tcpdump", "iw", "iwconfig", "snmpwalk", "snmpget", "ss", "ip", "arp",
               "journalctl", "systemctl", "docker", "python3", "curl", "wget", "dig", "nslookup", "ping",
               "traceroute", "mtr", "lldpctl", "ethtool", "smartctl", "sensors", "vcgencmd", "apt", "dnf"]


def collect_tools(which=shutil.which, tools=KNOWN_TOOLS):
    found = {}
    for t in tools:
        p = which(t)
        if p:
            found[t] = p
    return {"available": sorted(found), "paths": found, "missing": [t for t in tools if t not in found]}


# ---------------------------------------------------------------------
# Passage complet
# ---------------------------------------------------------------------

def collect_all(files=read_file, cmd=run_cmd, usage=shutil.disk_usage, which=shutil.which,
                sleep=time.sleep, previous_cpu=None, hostname=None, include_tools=True, exists=host_exists):
    """Une mesure `host` complète. `previous_cpu` = `_stat` du passage
    précédent pour un pourcentage CPU sans pause."""
    partial = []
    system = collect_system(files, hostname=hostname, exists=exists)
    cpu = collect_cpu(files, sleep=sleep, previous=previous_cpu)
    memory = collect_memory(files)
    disks = collect_disks(files, usage=usage, usage_remote=None if usage is shutil.disk_usage else usage)
    services = collect_failed_services(cmd)
    ports = collect_listening_ports(cmd)
    logs = collect_log_errors(cmd, files)
    accounts = collect_accounts(files)
    if system.get("os") is None:
        partial.append("os-release")
    if cpu.get("load1") is None:
        partial.append("loadavg")
    if memory.get("total_bytes") is None:
        partial.append("meminfo")
    if not disks:
        partial.append("mounts")
    elif any(d.get("error") for d in disks):
        partial.append("mounts:%d" % sum(1 for d in disks if d.get("error")))
    if not services.get("available"):
        partial.append("systemctl")
    if not ports.get("available"):
        partial.append("ss")
    if logs.get("source") is None:
        partial.append("logs")
    data = {
        "system": system,
        "cpu": {k: v for k, v in cpu.items() if not k.startswith("_")},
        "memory": memory,
        "disks": disks,
        "services": services,
        "ports": ports,
        "logs": logs,
        "accounts": accounts,
        "partial": partial,
    }
    if include_tools:
        data["tools"] = collect_tools(which)
    return data, cpu.get("_stat")
