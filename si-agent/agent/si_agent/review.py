# -*- coding: utf-8 -*-
"""Revue de l'hôte (livraison #428, backlog 66) : MATÉRIEL (constructeur et
modèle DMI ou Raspberry, CPU, mémoire installée, disques physiques, cartes
réseau, virtualisation) -- collecté avec l'inventaire (toutes les heures,
ça ne bouge pas) -- et ACTIVITÉ (processus les plus gourmands, sessions
ouvertes, dernières connexions, nombre de processus et de services actifs,
mises à jour en attente) -- collectée avec la mesure `host`.

Les niveaux de ressources (CPU, mémoire, disques) sont déjà dans `host`.
Parseurs purs (lsblk -J, ps, who, last) testés sans machine.
"""
import json
import re

from . import host


def _read(files, path):
    v = files(path)
    return (v or "").replace("\x00", "").strip() or None


# ---- matériel -----------------------------------------------------------------

def parse_lsblk(data):
    """`lsblk -J -d -o NAME,TYPE,SIZE,MODEL,SERIAL,ROTA,TRAN,VENDOR` -> disques
    physiques (loop, rom, zram exclus)."""
    out = []
    for d in (data or {}).get("blockdevices") or []:
        if d.get("type") not in ("disk",) or str(d.get("name", "")).startswith(("loop", "zram", "ram")):
            continue
        out.append({"name": d.get("name"), "size": d.get("size"), "model": (d.get("model") or "").strip() or None,
                    "serial": (d.get("serial") or "").strip() or None, "vendor": (d.get("vendor") or "").strip() or None,
                    "rotational": d.get("rota") in (True, "1", 1), "transport": d.get("tran")})
    return out


def parse_lscpu(text):
    """`lscpu` -> {model, sockets, cores, threads, arch, mhz_max, virtualization}"""
    kv = {}
    for line in (text or "").splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            kv[k.strip().lower()] = v.strip()
    def num(k):
        try:
            return int(kv.get(k, "").split()[0])
        except (ValueError, IndexError):
            return None
    return {"model": kv.get("model name"), "arch": kv.get("architecture"), "sockets": num("socket(s)"),
            "cores_per_socket": num("core(s) per socket"), "threads_per_core": num("thread(s) per core"),
            "cpus": num("cpu(s)"), "mhz_max": kv.get("cpu max mhz"), "hypervisor": kv.get("hypervisor vendor"),
            "virtualization": kv.get("virtualization type") or kv.get("virtualization")}


def collect_hardware(cmd=host.run_cmd, files=host.read_file):
    dmi = "/sys/class/dmi/id/"
    vendor = _read(files, dmi + "sys_vendor")
    product = _read(files, dmi + "product_name")
    version = _read(files, dmi + "product_version")
    serial = _read(files, dmi + "product_serial")
    bios = _read(files, dmi + "bios_version")
    board = _read(files, dmi + "board_name")
    pi = _read(files, "/proc/device-tree/model")
    if pi:
        vendor, product = "Raspberry Pi Foundation", pi
        serial = serial or _read(files, "/proc/device-tree/serial-number")
    r = cmd(["lscpu"])
    cpu = parse_lscpu(r.stdout) if r.returncode == 0 else {}
    lsblk = cmd(["lsblk", "-J", "-d", "-o", "NAME,TYPE,SIZE,MODEL,SERIAL,ROTA,TRAN,VENDOR"])
    disks = []
    if lsblk.returncode == 0:
        try:
            disks = parse_lsblk(json.loads(lsblk.stdout))
        except ValueError:
            disks = []
    mem_total = None
    for line in (files("/proc/meminfo") or "").splitlines():
        if line.startswith("MemTotal:"):
            try:
                mem_total = int(line.split()[1]) * 1024
            except (ValueError, IndexError):
                pass
    virt = cmd(["systemd-detect-virt"])
    virtualization = (virt.stdout or "").strip() if virt.returncode == 0 else ("none" if virt.returncode == 1 else None)
    nics = []
    link = cmd(["ip", "-j", "link"])
    if link.returncode == 0:
        try:
            for it in json.loads(link.stdout):
                if it.get("link_type") == "ether":
                    speed = _read(files, "/sys/class/net/%s/speed" % it["ifname"])
                    nics.append({"name": it["ifname"], "mac": it.get("address"), "state": (it.get("operstate") or "").lower(),
                                 "speed_mbps": int(speed) if speed and speed.lstrip("-").isdigit() and int(speed) > 0 else None})
        except (ValueError, KeyError):
            pass
    return {
        "vendor": vendor, "product": product, "product_version": version, "serial": serial, "bios": bios, "board": board,
        "cpu": cpu, "memory_total_bytes": mem_total, "disks": disks, "nics": nics, "virtualization": virtualization,
        "partial": [k for k, v in (("dmi", vendor or product), ("lscpu", cpu), ("lsblk", disks), ("ip-link", nics)) if not v],
    }


# ---- activité -------------------------------------------------------------------

def parse_ps(text, limit=10):
    """`ps -eo pid,user,pcpu,pmem,rss,etimes,comm --sort=-pcpu` (sans en-tête)
    -> [{pid, user, cpu_percent, mem_percent, rss_bytes, elapsed_seconds, command}]"""
    out = []
    for line in (text or "").splitlines():
        parts = line.split(None, 6)
        if len(parts) < 7 or not parts[0].isdigit():
            continue
        try:
            out.append({"pid": int(parts[0]), "user": parts[1], "cpu_percent": float(parts[2]), "mem_percent": float(parts[3]),
                        "rss_bytes": int(parts[4]) * 1024, "elapsed_seconds": int(parts[5]), "command": parts[6].strip()})
        except ValueError:
            continue
        if len(out) >= limit:
            break
    return out


def parse_who(text):
    out = []
    for line in (text or "").splitlines():
        parts = line.split()
        if len(parts) >= 2:
            m = re.search(r"\(([^)]+)\)", line)
            out.append({"user": parts[0], "tty": parts[1], "since": " ".join(parts[2:4]) if len(parts) >= 4 else None, "from": m.group(1) if m else None})
    return out


def parse_last(text, limit=10):
    out = []
    for line in (text or "").splitlines():
        if not line.strip() or line.startswith(("wtmp", "btmp")):
            continue
        parts = line.split()
        if len(parts) < 3:
            continue
        out.append({"user": parts[0], "tty": parts[1], "from": parts[2] if not parts[2][:3].isalpha() or parts[2].count(".") else None,
                    "line": line.strip()})
        if len(out) >= limit:
            break
    return out


def collect_activity(cmd=host.run_cmd, files=host.read_file):
    partial = []
    ps_cpu = cmd(["ps", "-eo", "pid,user,pcpu,pmem,rss,etimes,comm", "--sort=-pcpu", "--no-headers"])
    ps_mem = cmd(["ps", "-eo", "pid,user,pcpu,pmem,rss,etimes,comm", "--sort=-rss", "--no-headers"])
    if ps_cpu.returncode != 0:
        partial.append("ps")
    top_cpu = parse_ps(ps_cpu.stdout, 8) if ps_cpu.returncode == 0 else []
    top_mem = parse_ps(ps_mem.stdout, 8) if ps_mem.returncode == 0 else []
    total = len((ps_cpu.stdout or "").splitlines()) if ps_cpu.returncode == 0 else None
    who = cmd(["who"])
    sessions = parse_who(who.stdout) if who.returncode == 0 else []
    last = cmd(["last", "-n", "10", "-w", "-F"])
    logins = parse_last(last.stdout) if last.returncode == 0 else []
    if last.returncode < 0:
        partial.append("last")
    units = cmd(["systemctl", "list-units", "--type=service", "--state=running", "--no-legend", "--no-pager", "--plain"])
    running = [l.split()[0] for l in (units.stdout or "").splitlines() if l.strip()] if units.returncode == 0 else None
    updates = None
    upd = files("/var/lib/update-notifier/updates-available")
    if upd:
        m = re.search(r"(\d+)\s+(?:mise|update|paquet|package)", upd)
        updates = int(m.group(1)) if m else None
    return {"process_count": total, "top_cpu": top_cpu, "top_memory": top_mem, "sessions": sessions, "last_logins": logins,
            "running_services": running, "running_services_count": len(running) if running is not None else None,
            "updates_available": updates, "partial": partial}
