#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « nas-qnap » (#939) : relevé LECTURE SEULE d'un NAS QNAP (QTS) par SSH depuis un agent du LAN -- ce que le SNMP
ne donne pas : snapshots par volume, sauvegardes Time Machine (bundles, ancienneté), partages (dont ceux déclarés Time
Machine), état RAID (mdstat), remplissage des volumes, et une DÉCOUVERTE des outils de sauvegarde / snapshot présents
(HBS, RTRR, outils en ligne de commande) pour préparer la gestion à distance -- aucune commande de modification.

Réglages : /etc/si-agent/nas-qnap.json = [{"name": "nas-1", "host": "192.0.2.9", "user": "admin", "port": 22,
"key": "/etc/si-agent/keys/nas-1"}] (clé SSH sans mot de passe, déposée sur le NAS : Panneau de configuration ›
Sécurité ou ~/.ssh/authorized_keys). Ne touche pas au SNMP du NAS.

Sortie JSON : {"nas": [{name, host, ok, error, systeme, volumes, raid, partages, snapshots, timemachine, outils, alertes}],
"alerts": [...]}. Pur (testé) : SCRIPT, decouper, parse_df, parse_mdstat, parse_smb, parse_snapshots, parse_bundles, analyser.
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import time

# Script exécuté sur le NAS (sh de QTS = BusyBox) : chaque section est bornée par « === nom ». Tout en lecture.
SCRIPT = r'''
echo "=== version"; getcfg System Version 2>/dev/null; getcfg System "Build Number" 2>/dev/null; getcfg System "Model" 2>/dev/null; hostname 2>/dev/null; uptime 2>/dev/null
echo "=== df"; df -k 2>/dev/null
echo "=== mdstat"; cat /proc/mdstat 2>/dev/null
echo "=== smb"; cat /etc/config/smb.conf 2>/dev/null
echo "=== snapshots"
for v in /share/CACHEDEV*_DATA /share/CE_CACHEDEV*_DATA /share/ZFS*_DATA; do
  [ -d "$v" ] || continue
  echo "## $v"
  for d in "$v/.snapshot" "$v/.@snapshot" "$v/.@snapshots" "$v/.zfs/snapshot"; do
    [ -d "$d" ] && ls -1 "$d" 2>/dev/null | sed "s|^|$d/|"
  done
done
echo "=== timemachine"
for b in /share/*/*.sparsebundle /share/*/*.backupbundle /share/*/*/*.sparsebundle /share/*/*/*.backupbundle /share/CACHEDEV*_DATA/*/*.sparsebundle /share/CACHEDEV*_DATA/*/*.backupbundle /share/CACHEDEV*_DATA/*/*/*.sparsebundle /share/CACHEDEV*_DATA/*/*/*.backupbundle; do
  [ -d "$b" ] || continue
  m=$(stat -c %Y "$b/com.apple.TimeMachine.MachineID.plist" 2>/dev/null || stat -c %Y "$b" 2>/dev/null)
  s=$(du -sk "$b" 2>/dev/null | cut -f1)
  echo "$m $s $b"
done
echo "=== outils"
ls -1 /etc/config 2>/dev/null | grep -i -E "backup|hbs|snapshot|rtrr|qsync|rsync|timemachine|afp" | sort -u
ls -1 /share/CACHEDEV*_DATA/.qpkg 2>/dev/null | sort -u | sed "s|^|qpkg:|"
for p in /sbin /usr/sbin /usr/local/sbin /usr/bin /usr/local/bin /usr/local/HBS3 /share/CACHEDEV1_DATA/.qpkg/HybridBackup; do
  ls -1 "$p" 2>/dev/null | grep -i -E "snap|hbs|rtrr|backup|qcli" | sed "s|^|$p/|"
done
echo "=== fin"
'''

RE_SNAP_DATE = re.compile(r"(\d{4})[-.](\d{2})[-.](\d{2})[-_ T.]*(\d{2})[.:]?(\d{2})")


def decouper(texte):
    """Sortie brute -> {section: [lignes]}."""
    out, cur = {}, None
    for l in str(texte or "").splitlines():
        m = re.match(r"^=== (\w+)\s*$", l)
        if m:
            cur = m.group(1)
            out.setdefault(cur, [])
            continue
        if cur:
            out[cur].append(l.rstrip("\n"))
    return out


def parse_df(lignes):
    """df -k -> volumes de données (/share/*_DATA) : [{montage, nom, ko, utilise_ko, libre_ko, pct}]."""
    out = []
    for l in lignes or []:
        p = l.split()
        if len(p) < 6 or not p[1].isdigit():
            continue
        mnt = p[-1]
        if not re.search(r"/share/(CE_)?(CACHEDEV|ZFS|MD)\d*_DATA$", mnt):
            continue
        ko, used, avail = int(p[1]), int(p[2]), int(p[3])
        out.append({"montage": mnt, "nom": mnt.rsplit("/", 1)[-1], "ko": ko, "utilise_ko": used, "libre_ko": avail,
                    "pct": round(100.0 * used / ko, 1) if ko else None})
    return out


def parse_mdstat(lignes):
    """/proc/mdstat -> [{dev, niveau, disques, etat, degrade}]."""
    out, cur = [], None
    for l in lignes or []:
        m = re.match(r"^(md\d+)\s*:\s*(\w+)\s+(raid\d+|linear|multipath)?\s*(.*)$", l)
        if m:
            cur = {"dev": m.group(1), "actif": m.group(2) == "active", "niveau": (m.group(3) or "").replace("raid", "RAID ") or "simple",
                   "disques": re.findall(r"(sd\w+|nvme\w+|sata\w+)\d*\[", m.group(4)), "etat": None, "degrade": False}
            out.append(cur)
            continue
        if cur and re.search(r"\[[U_]+\]", l):
            u = re.search(r"\[([U_]+)\]", l).group(1)
            cur["etat"] = u
            cur["degrade"] = "_" in u
            cur = None
    return out


def parse_smb(lignes):
    """smb.conf -> partages [{nom, chemin, timemachine, lecture_seule, navigable}] (sections hors [global])."""
    out, cur = [], None
    for l in lignes or []:
        s = l.strip()
        m = re.match(r"^\[(.+)\]$", s)
        if m:
            cur = None if m.group(1).lower() in ("global",) else {"nom": m.group(1), "chemin": None, "timemachine": False, "lecture_seule": False, "navigable": True}
            if cur:
                out.append(cur)
            continue
        if not cur or "=" not in s:
            continue
        k, v = [x.strip() for x in s.split("=", 1)]
        k = k.lower()
        if k == "path":
            cur["chemin"] = v
        elif k in ("fruit:time machine", "fruit:timemachine"):
            cur["timemachine"] = v.lower() in ("yes", "true", "1")
        elif k == "read only":
            cur["lecture_seule"] = v.lower() in ("yes", "true", "1")
        elif k == "browseable" or k == "browsable":
            cur["navigable"] = v.lower() not in ("no", "false", "0")
    return out


def _date_snap(nom, now):
    m = RE_SNAP_DATE.search(nom)
    if not m:
        return None
    try:
        t = time.mktime((int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(4)), int(m.group(5)), 0, 0, 0, -1))
        return t if t <= now + 86400 else None
    except (ValueError, OverflowError):
        return None


def parse_snapshots(lignes, now):
    """Section snapshots -> par volume : {volume, dossiers, nombre, dernier, dernier_age_h, noms[-5:]}."""
    out, cur = [], None
    for l in lignes or []:
        if l.startswith("## "):
            cur = {"volume": l[3:].strip().rsplit("/", 1)[-1], "montage": l[3:].strip(), "nombre": 0, "dernier": None, "dernier_age_h": None, "noms": [], "dossier": None}
            out.append(cur)
            continue
        if not cur or not l.strip():
            continue
        dossier, nom = l.rsplit("/", 1) if "/" in l else (None, l)
        cur["dossier"] = cur["dossier"] or dossier
        cur["nombre"] += 1
        cur["noms"].append(nom)
        t = _date_snap(nom, now)
        if t and (cur["dernier"] is None or t > cur["dernier"]):
            cur["dernier"] = t
    for v in out:
        v["noms"] = v["noms"][-5:]
        if v["dernier"]:
            v["dernier_age_h"] = round((now - v["dernier"]) / 3600.0, 1)
    return out


def parse_bundles(lignes, now):
    """Section timemachine : « <mtime> <ko> <chemin> » -> [{chemin, machine, ko, modifie, age_h}]."""
    out = []
    for l in lignes or []:
        p = l.split(" ", 2)
        if len(p) < 3 or not p[0].isdigit():
            continue
        chemin = p[2].strip()
        out.append({"chemin": chemin, "machine": chemin.rsplit("/", 1)[-1].replace(".sparsebundle", "").replace(".backupbundle", ""),
                    "ko": int(p[1]) if p[1].isdigit() else None, "modifie": int(p[0]), "age_h": round((now - int(p[0])) / 3600.0, 1)})
    return out


def analyser(name, host, sortie, now=None, vol_warn=85, vol_crit=95, snap_max_h=48, tm_max_h=24 * 7):
    """Sortie brute du SCRIPT -> fiche du NAS + constats."""
    now = now if now is not None else time.time()
    s = decouper(sortie)
    ver = [l.strip() for l in s.get("version", []) if l.strip()]
    systeme = {"version": ver[0] if ver else None, "build": ver[1] if len(ver) > 1 else None, "modele": ver[2] if len(ver) > 2 else None,
               "hostname": ver[3] if len(ver) > 3 else None, "uptime": ver[4] if len(ver) > 4 else None}
    volumes = parse_df(s.get("df"))
    raid = parse_mdstat(s.get("mdstat"))
    partages = parse_smb(s.get("smb"))
    snaps = parse_snapshots(s.get("snapshots"), now)
    tm = parse_bundles(s.get("timemachine"), now)
    outils = [l.strip() for l in s.get("outils", []) if l.strip()]
    al = []

    def alerte(code, sev, msg):
        al.append({"code": code, "severity": sev, "message": "%s : %s" % (name, msg)})
    for v in volumes:
        if v["pct"] is not None and v["pct"] >= vol_crit:
            alerte("nas-volume-plein@%s" % v["nom"], "critical", "volume %s à %s %%" % (v["nom"], v["pct"]))
        elif v["pct"] is not None and v["pct"] >= vol_warn:
            alerte("nas-volume-presque-plein@%s" % v["nom"], "warning", "volume %s à %s %%" % (v["nom"], v["pct"]))
    for r in raid:
        if r["degrade"] or not r["actif"]:
            alerte("nas-raid-degrade@%s" % r["dev"], "critical", "%s (%s) dégradé : %s" % (r["dev"], r["niveau"], r["etat"] or "inactif"))
    for v in snaps:
        if v["nombre"] == 0:
            continue
        if v["dernier_age_h"] is not None and v["dernier_age_h"] > snap_max_h:
            alerte("nas-snapshot-vieux@%s" % v["volume"], "warning", "dernier snapshot de %s il y a %d h (%d snapshots)" % (v["volume"], int(v["dernier_age_h"]), v["nombre"]))
    tm_parts = [p["nom"] for p in partages if p["timemachine"]]
    for b in tm:
        if b["age_h"] > tm_max_h:
            alerte("nas-timemachine-vieux@%s" % b["machine"], "warning", "Time Machine « %s » : dernière écriture il y a %d j" % (b["machine"], int(b["age_h"] // 24)))
    if tm_parts and not tm:
        alerte("nas-timemachine-vide", "info", "partage(s) Time Machine déclaré(s) (%s) sans sauvegarde trouvée" % ", ".join(tm_parts))
    sans_snap = [v["nom"] for v in volumes if not any(x["volume"] == v["nom"] and x["nombre"] for x in snaps)]
    return {"name": name, "host": host, "ok": True, "error": None, "at": now, "systeme": systeme, "volumes": volumes, "raid": raid,
            "partages": partages, "partages_timemachine": tm_parts, "snapshots": snaps, "volumes_sans_snapshot": sans_snap,
            "timemachine": tm, "outils": outils, "alertes": al}


# --- accès réel (non testé hors LAN) ---

def relever(cible, runner=subprocess.run, timeout=90):
    argv = ["ssh", "-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10",
            "-p", str(int(cible.get("port") or 22))]
    if cible.get("key"):
        argv += ["-i", str(cible["key"])]
    argv += ["%s@%s" % (cible.get("user") or "admin", cible["host"]), "sh", "-s"]
    try:
        r = runner(argv, input=SCRIPT, capture_output=True, text=True, timeout=timeout, check=False)
    except Exception as e:  # noqa: BLE001
        return None, "ssh : %s" % e
    if r.returncode != 0 and "=== fin" not in (r.stdout or ""):
        return None, (r.stderr or r.stdout or "code %s" % r.returncode).strip()[:300]
    return r.stdout, None


def main(argv=None, runner=subprocess.run, which=shutil.which):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="/etc/si-agent/nas-qnap.json")
    ap.add_argument("--vol-warn", type=float, default=85)
    ap.add_argument("--vol-crit", type=float, default=95)
    ap.add_argument("--snap-max-h", type=float, default=48)
    ap.add_argument("--tm-max-days", type=float, default=7)
    a = ap.parse_args(argv)
    out = {"nas": [], "alerts": []}
    try:
        with open(a.config, encoding="utf-8") as fh:
            cibles = [c for c in json.load(fh) if isinstance(c, dict) and c.get("host")]
    except (OSError, ValueError) as e:
        out["alerts"].append({"code": "nas-qnap-config", "severity": "warning", "message": "réglages illisibles (%s) : %s" % (a.config, e)})
        return out
    if not which("ssh"):
        out["alerts"].append({"code": "nas-qnap-ssh", "severity": "warning", "message": "client ssh absent sur l'hôte de l'agent"})
        return out
    for c in cibles:
        name = c.get("name") or c["host"]
        sortie, err = relever(c, runner=runner)
        if err:
            out["nas"].append({"name": name, "host": c["host"], "ok": False, "error": err, "at": time.time()})
            out["alerts"].append({"code": "nas-qnap-injoignable@%s" % name, "severity": "warning", "message": "%s : SSH impossible -- %s" % (name, err)})
            continue
        fiche = analyser(name, c["host"], sortie, vol_warn=a.vol_warn, vol_crit=a.vol_crit, snap_max_h=a.snap_max_h, tm_max_h=a.tm_max_days * 24)
        out["nas"].append(fiche)
        out["alerts"].extend(fiche["alertes"])
    return out


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1:]), ensure_ascii=False))
