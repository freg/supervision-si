#!/usr/bin/env python3
"""Sonde gpu (#782) : cartes graphiques de l'hôte, en lecture seule (stdlib).
- inventaire : `lspci -Dnn` (classes 0300 / 0302 / 0380), pilote lié lu dans /sys/bus/pci/devices/<slot>/driver ;
  les puces vidéo de gestion des serveurs (ASPEED, Matrox) sont ignorées ;
- NVIDIA : `nvidia-smi --query-gpu=... --format=csv,noheader,nounits` + processus (--query-compute-apps) ;
- autres (Intel xe / i915, AMD) : capteurs hwmon du noyau (température, puissance) quand ils existent.
Sortie JSON : {at, gpus[], alerts[], error}.
Usage : gpu_probe.py [--sysfs /sys] [--ignore 10de:13ba,...]  (cartes laissées sans pilote volontairement)"""
import glob
import json
import os
import re
import subprocess
import sys
import time

NV_FIELDS = ["index", "name", "uuid", "pci.bus_id", "driver_version", "memory.total", "memory.used", "utilization.gpu",
             "temperature.gpu", "power.draw", "power.limit", "fan.speed", "pstate"]
VENDORS = {"10de": "NVIDIA", "8086": "Intel", "1002": "AMD"}
IGNORED_VENDORS = ("1a03", "102b", "1af4", "1234", "15ad", "1b36")   # ASPEED, Matrox (gestion serveur) ; virtio, QEMU, VMware, QXL
TEMP_WARN, TEMP_CRIT, VRAM_WARN = 80, 87, 95


def _num(v):
    try:
        return float(str(v).strip())
    except (TypeError, ValueError):
        return None                          # « [N/A] », « [Not Supported] », vide


def norm_slot(s):
    """« 00000000:65:00.0 » (nvidia-smi) ou « 0000:65:00.0 » (lspci) -> « 65:00.0 »."""
    s = str(s or "").strip().lower()
    return ":".join(s.split(":")[-2:]) if s.count(":") >= 1 else s


def parse_lspci(text):
    """`lspci -Dnn` -> [{slot, vendor_id, device_id, vendor, name}] pour les cartes d'affichage / calcul."""
    out = []
    for line in (text or "").splitlines():
        m = re.match(r"^(\S+)\s+[^\[]*\[(030[02]|0380)\]:\s*(.*?)\s*\[([0-9a-f]{4}):([0-9a-f]{4})\]", line.strip(), re.I)
        if not m:
            continue
        vid, did = m.group(4).lower(), m.group(5).lower()
        if vid in IGNORED_VENDORS:
            continue
        out.append({"slot": norm_slot(m.group(1)), "pci": m.group(1), "vendor_id": vid, "device_id": did,
                    "vendor": VENDORS.get(vid, vid), "name": m.group(3).strip()})
    return out


def parse_nvidia(text):
    """Sortie csv sans en-tête ni unités de nvidia-smi -> [{...}] (Mio -> octets, W, °C, %)."""
    gpus = []
    for line in (text or "").splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) != len(NV_FIELDS):
            continue
        d = dict(zip(NV_FIELDS, cols))
        tot, used = _num(d["memory.total"]), _num(d["memory.used"])
        gpus.append({"slot": norm_slot(d["pci.bus_id"]), "uuid": d["uuid"], "vendor": "NVIDIA", "name": d["name"], "driver": "nvidia",
                     "driver_version": d["driver_version"], "vram_total": int(tot * 1048576) if tot is not None else None,
                     "vram_used": int(used * 1048576) if used is not None else None,
                     "vram_pct": round(100.0 * used / tot, 1) if tot and used is not None else None,
                     "util_pct": _num(d["utilization.gpu"]), "temp_c": _num(d["temperature.gpu"]), "power_w": _num(d["power.draw"]),
                     "power_limit_w": _num(d["power.limit"]), "fan_pct": _num(d["fan.speed"]), "pstate": d["pstate"], "processes": [],
                     "source": "nvidia-smi"})
    return gpus


def parse_nvidia_apps(text):
    """--query-compute-apps=gpu_uuid,pid,process_name,used_memory -> {uuid: [{pid, name, vram}]}."""
    by = {}
    for line in (text or "").splitlines():
        cols = [c.strip() for c in line.split(",")]
        if len(cols) != 4:
            continue
        mem = _num(cols[3])
        by.setdefault(cols[0], []).append({"pid": int(_num(cols[1]) or 0), "name": os.path.basename(cols[2])[:60],
                                           "vram": int(mem * 1048576) if mem is not None else None})
    return by


def sysfs_info(pci, root="/sys"):
    """Pilote lié et capteurs hwmon (température la plus haute en °C, puissance en W) d'une carte PCI."""
    dev = os.path.join(root, "bus", "pci", "devices", pci)
    info = {"driver": None, "temp_c": None, "power_w": None}
    try:
        info["driver"] = os.path.basename(os.readlink(os.path.join(dev, "driver")))
    except OSError:
        pass
    temps, power = [], None
    for hw in glob.glob(os.path.join(dev, "hwmon", "hwmon*")) + glob.glob(os.path.join(dev, "drm", "card*", "device", "hwmon", "hwmon*")):
        for f in glob.glob(os.path.join(hw, "temp*_input")):
            v = _read_num(f)
            if v is not None and 0 < v < 150000:
                temps.append(v / 1000.0)
        p = _read_num(os.path.join(hw, "power1_input")) or _read_num(os.path.join(hw, "power1_average"))
        if p:
            power = round(p / 1e6, 1)
    info["temp_c"] = max(temps) if temps else None
    info["power_w"] = power
    return info


def _read_num(path):
    try:
        with open(path) as fh:
            return float(fh.read().strip())
    except (OSError, ValueError):
        return None


def alerts_for(gpus, nvidia_error=None, ignore=()):
    """Constats ; `ignore` : identifiants « vendeur:modèle » de cartes volontairement laissées sans pilote."""
    out = []
    for g in gpus:
        tag = "%s@%s" % ((g.get("name") or "gpu")[:40], g.get("slot"))
        if not g.get("driver") and "%s:%s" % (g.get("vendor_id"), g.get("device_id")) not in ignore:
            out.append({"code": "gpu-no-driver@" + tag, "severity": "warning",
                        "message": "%s : aucun pilote chargé, carte inutilisable" % g.get("name")})
        t = g.get("temp_c")
        if t is not None and t >= TEMP_WARN:
            out.append({"code": "gpu-hot@" + tag, "severity": "critical" if t >= TEMP_CRIT else "warning",
                        "message": "%s à %d °C" % (g.get("name"), t)})
        if g.get("vram_pct") is not None and g["vram_pct"] >= VRAM_WARN:
            out.append({"code": "gpu-vram-full@" + tag, "severity": "warning",
                        "message": "%s : mémoire vidéo pleine à %s %%" % (g.get("name"), g["vram_pct"])})
    if nvidia_error:
        out.append({"code": "nvidia-smi", "severity": "warning", "message": "nvidia-smi en échec : %s" % nvidia_error[:150]})
    return out


def _run(args, timeout=15):
    r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    if r.returncode != 0:
        raise RuntimeError((r.stderr or r.stdout or "code %d" % r.returncode).strip().splitlines()[-1][:200])
    return r.stdout


def collect(run=_run, root="/sys", which=None, ignore=()):
    """Inventaire lspci complété par nvidia-smi (cartes NVIDIA avec pilote) et par sysfs (les autres)."""
    import shutil
    which = which or shutil.which
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "gpus": [], "alerts": [], "error": None}
    cards = []
    if which("lspci"):
        try:
            cards = parse_lspci(run(["lspci", "-Dnn"]))
        except Exception as exc:  # noqa: BLE001
            out["error"] = "lspci : %s" % str(exc)[:150]
    nv, nv_err = {}, None
    if which("nvidia-smi"):
        try:
            nv = {g["slot"]: g for g in parse_nvidia(run(["nvidia-smi", "--query-gpu=" + ",".join(NV_FIELDS), "--format=csv,noheader,nounits"]))}
            try:
                apps = parse_nvidia_apps(run(["nvidia-smi", "--query-compute-apps=gpu_uuid,pid,process_name,used_memory", "--format=csv,noheader,nounits"]))
                for g in nv.values():
                    g["processes"] = apps.get(g["uuid"], [])
            except Exception:  # noqa: BLE001 -- processus : complément facultatif
                pass
        except Exception as exc:  # noqa: BLE001
            nv_err = str(exc)
    for c in cards:
        if c["slot"] in nv:
            g = dict(nv.pop(c["slot"]), pci=c["pci"], vendor_id=c["vendor_id"], device_id=c["device_id"])
            g["name"] = g["name"] or c["name"]
        else:
            s = sysfs_info(c["pci"], root)
            g = dict(c, driver=s["driver"], temp_c=s["temp_c"], power_w=s["power_w"], vram_total=None, vram_used=None,
                     vram_pct=None, util_pct=None, processes=[], source="sysfs", passthrough=s["driver"] == "vfio-pci")
        out["gpus"].append(g)
    out["gpus"] += list(nv.values())                 # lspci absent : cartes vues par nvidia-smi seulement
    if nv_err and not any(g["vendor"] == "NVIDIA" for g in cards):
        nv_err = None                                # nvidia-smi installé sans carte NVIDIA : pas un constat
    out["alerts"] = alerts_for(out["gpus"], nv_err, ignore)
    return out


if __name__ == "__main__":
    def arg(name, default):
        return sys.argv[sys.argv.index(name) + 1] if name in sys.argv[:-1] else default
    ign = tuple(x.strip().lower() for x in arg("--ignore", "").split(",") if x.strip())
    print(json.dumps(collect(root=arg("--sysfs", "/sys"), ignore=ign), ensure_ascii=False))
