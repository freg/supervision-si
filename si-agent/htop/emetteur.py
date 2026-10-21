#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""si-htop : émetteur (#800). Relevé « htop » de l'hôte toutes les 2 s envoyé en UDP signé (HMAC-SHA256) à un ou
plusieurs relais. Autonome : bibliothèque standard seule, compatible Python 3.4 (Debian 8 dans un CT) et 3.5 (Proxmox VE 5.4 / Debian 9).

Relevé : CPU global et par cœur, iowait, steal (VM : temps volé par l'hyperviseur), charge, mémoire, swap, tâches,
processus les plus gourmands (CPU puis mémoire), partitions (toutes les 30 s), pools ZFS et ARC (Proxmox, toutes
les 60 s) et, sur un Proxmox, consommation de chaque CT / VM lue dans les cgroups (v1 et v2) avec leur nom.

Usage : emetteur.py --relais hote:8399[,hote2:8399] --cle-fichier /etc/si-htop/cle [--nom N] [--periode 2]
        emetteur.py --afficher           (un relevé JSON sur la sortie standard, rien n'est envoyé)
        emetteur.py --transit 0.0.0.0:8399 --relais hote:8399   (#802, sur un Proxmox : relaie vers le relais les paquets
            des émetteurs de ses CT, qui sortent avec leur propre IP publique alors que l'entrée du routeur n'accepte
            que celles des nœuds ; sources admises : IP déclarées dans les CT du nœud, plus --transit-depuis)
Paquet : b"SH1E" + HMAC-SHA256(clé, magie + corps)[:16] + zlib(JSON)."""
import argparse
import glob
import hashlib
import hmac
import json
import os
import random
import re
import shutil
import socket
import subprocess
import sys
import time
import zlib

MAGIE = b"SH1E"
VERSION = 1
FS_REELS = ("ext2", "ext3", "ext4", "xfs", "btrfs", "zfs", "f2fs", "jfs", "reiserfs")


def emballer(magie, cle, obj):
    corps = zlib.compress(json.dumps(obj, separators=(",", ":"), ensure_ascii=False).encode("utf-8"), 6)
    return magie + hmac.new(cle, magie + corps, hashlib.sha256).digest()[:16] + corps


def lire(chemin, defaut=""):
    try:
        with open(chemin, "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    except (OSError, IOError):
        return defaut


# ---------------------------------------------------------------- analyse pure (testée)
def cpu_stat(texte):
    """/proc/stat -> {"cpu": [user, nice, system, idle, iowait, irq, softirq, steal], "cpu0": [...], ...}"""
    out = {}
    for ligne in texte.splitlines():
        if ligne.startswith("cpu"):
            f = ligne.split()
            v = [int(x) for x in f[1:9]]
            while len(v) < 8:
                v.append(0)
            out[f[0]] = v
    return out


def cpu_pourcents(cur, prev):
    """-> (occupé %, iowait %, steal %) entre deux lectures d'une même ligne cpu."""
    if not cur or not prev:
        return None, None, None
    d = [a - b for a, b in zip(cur, prev)]
    tot = sum(d)
    if tot <= 0:
        return None, None, None
    idle = d[3] + d[4]
    return round(100.0 * (tot - idle) / tot, 1), round(100.0 * d[4] / tot, 1), round(100.0 * d[7] / tot, 1)


def meminfo(texte):
    kv = dict((k, int(v) * 1024) for k, v in re.findall(r"^(\w+):\s+(\d+)", texte, re.M))
    tot = kv.get("MemTotal", 0)
    dispo = kv.get("MemAvailable", kv.get("MemFree", 0) + kv.get("Cached", 0))
    return {"total": tot, "used": max(0, tot - dispo), "swap_total": kv.get("SwapTotal", 0),
            "swap_used": max(0, kv.get("SwapTotal", 0) - kv.get("SwapFree", 0))}


def arc_taille(texte):
    m = re.search(r"^size\s+\d+\s+(\d+)", texte or "", re.M)
    return int(m.group(1)) if m else 0


def proc_stat(texte):
    """/proc/<pid>/stat -> (nom, ticks utilisateur + système, rss en pages) ; le nom peut contenir espaces et parenthèses."""
    i, j = texte.find("("), texte.rfind(")")
    if i < 0 or j < 0:
        return None
    f = texte[j + 2:].split()
    if len(f) < 22:
        return None
    return texte[i + 1:j], int(f[11]) + int(f[12]), int(f[21])


def invite_du_cgroup(texte):
    """/proc/<pid>/cgroup -> identifiant du CT / VM Proxmox (lxc/102, lxc.payload.102, qemu.slice/100.scope) ou None."""
    m = re.search(r"/lxc(?:\.payload)?[/.](\d+)|/qemu\.slice/(\d+)\.scope", texte or "")
    return (m.group(1) or m.group(2)) if m else None


def montages(texte):
    """/proc/mounts -> [(périphérique, point de montage)] des systèmes de fichiers réels ; volumes des CT / VM écartés."""
    vus, out = set(), []
    for ligne in texte.splitlines():
        f = ligne.split()
        if len(f) < 3 or f[2] not in FS_REELS or f[0] in vus:
            continue
        if f[1].startswith(("/boot/efi", "/snap", "/run", "/var/lib/docker", "/proc", "/sys")):
            continue
        if f[2] == "zfs" and re.search(r"(subvol|basevol|vm)-\d+-disk", f[0]):
            continue
        vus.add(f[0])
        out.append((f[0], f[1].replace("\\040", " ")))
    return out[:12]


def nom_invite(conf_texte, cle):
    m = re.search(r"^%s:\s*(\S+)" % cle, conf_texte or "", re.M)
    return m.group(1) if m else ""


def nature(racine="/"):
    if os.path.isdir(os.path.join(racine, "etc/pve")):
        return "pve"
    env = lire(os.path.join(racine, "proc/1/environ"))
    if "container=" in env or os.path.exists(os.path.join(racine, "run/systemd/container")):
        return "ct"
    if "hypervisor" in lire(os.path.join(racine, "proc/cpuinfo")) or "QEMU" in lire(os.path.join(racine, "sys/class/dmi/id/sys_vendor")):
        return "vm"
    return "hote"


# ---------------------------------------------------------------- relevé
class Releve(object):
    def __init__(self, nom=None, proc="/proc", top=8):
        self.nom = nom or socket.gethostname().split(".")[0]
        self.proc, self.top = proc, top
        self.nature = nature()
        self.hz = os.sysconf("SC_CLK_TCK") if hasattr(os, "sysconf") else 100
        self.page = os.sysconf("SC_PAGE_SIZE") if hasattr(os, "sysconf") else 4096
        self.prec_cpu, self.prec_proc, self.prec_inv, self.prec_t = {}, {}, {}, None
        self.noms, self.noms_t = {}, 0
        self.disques, self.disques_t, self.pools, self.pools_t = [], 0, [], 0
        self.boot = "%08x" % random.getrandbits(32)
        self.seq = 0

    def _noms_invites(self, maintenant):
        if self.nature != "pve" or maintenant - self.noms_t < 60:
            return self.noms
        noms = {}
        for c in glob.glob("/etc/pve/lxc/*.conf"):
            noms[os.path.basename(c)[:-5]] = (nom_invite(lire(c), "hostname"), "ct")
        for c in glob.glob("/etc/pve/qemu-server/*.conf"):
            noms[os.path.basename(c)[:-5]] = (nom_invite(lire(c), "name"), "vm")
        self.noms, self.noms_t = noms, maintenant
        return noms

    def _invites(self, dt, ncpu):
        """Proxmox : CPU (cœurs, % du nœud) et mémoire (utilisée, anonyme, limite) de chaque CT / VM lus dans les cgroups."""
        if self.nature != "pve":
            return []
        lus = {}
        for d in glob.glob("/sys/fs/cgroup/cpuacct/lxc/[0-9]*") + glob.glob("/sys/fs/cgroup/cpuacct/qemu.slice/[0-9]*.scope"):   # cgroup v1
            vid = re.sub(r"\.scope$", "", os.path.basename(d))
            m = d.replace("/cpuacct/", "/memory/", 1)
            st = dict(re.findall(r"^(\w+) (\d+)", lire(m + "/memory.stat"), re.M))
            lus[vid] = (lire(d + "/cpuacct.usage").strip(), lire(m + "/memory.usage_in_bytes").strip(), st.get("total_rss", "0"),
                        lire(m + "/memory.limit_in_bytes").strip())
        for d in glob.glob("/sys/fs/cgroup/lxc/[0-9]*") + glob.glob("/sys/fs/cgroup/qemu.slice/[0-9]*.scope"):   # cgroup v2
            vid = re.sub(r"\.scope$", "", os.path.basename(d))
            if vid in lus:
                continue
            cs = dict(re.findall(r"^(\w+) (\d+)", lire(d + "/cpu.stat"), re.M))
            st = dict(re.findall(r"^(\w+) (\d+)", lire(d + "/memory.stat"), re.M))
            lus[vid] = (str(int(cs.get("usage_usec", "0")) * 1000), lire(d + "/memory.current").strip(), st.get("anon", "0"),
                        lire(d + "/memory.max").strip())
        noms = self._noms_invites(time.time())
        out, prec = [], {}
        for vid, (ns, mem, anon, lim) in lus.items():
            if not ns.isdigit():
                continue
            prec[vid] = int(ns)
            p = self.prec_inv.get(vid)
            coeurs = (int(ns) - p) / 1e9 / dt if p is not None and dt > 0 and int(ns) >= p else None
            limite = int(lim) if lim.isdigit() and int(lim) < (1 << 60) else None
            nom, typ = noms.get(vid, ("", "vm" if "qemu" in vid else "ct"))
            out.append([int(vid), nom, typ, round(100.0 * coeurs / ncpu, 1) if coeurs is not None and ncpu else None,
                        round(coeurs, 2) if coeurs is not None else None, int(mem) if mem.isdigit() else None,
                        int(anon) if anon.isdigit() else None, limite])
        self.prec_inv = prec
        return sorted(out, key=lambda g: -(g[4] or 0))[:40]

    def _processus(self, dt):
        cur, lignes = {}, []
        for pid in os.listdir(self.proc):
            if not pid.isdigit():
                continue
            r = proc_stat(lire(os.path.join(self.proc, pid, "stat")))
            if not r:
                continue
            nom, ticks, rss = r
            cur[pid] = ticks
            p = self.prec_proc.get(pid)
            cpu = round(100.0 * (ticks - p) / self.hz / dt, 1) if p is not None and dt > 0 and ticks >= p else 0.0
            lignes.append([int(pid), nom[:24], cpu, rss * self.page])
        self.prec_proc = cur
        haut = [x for x in sorted(lignes, key=lambda x: -x[2]) if x[2] > 0][:self.top]     # actifs, puis les plus gros en mémoire
        pris = set(x[0] for x in haut)
        haut += [x for x in sorted(lignes, key=lambda x: -x[3]) if x[0] not in pris][:self.top + self.top // 2 - len(haut)]
        if self.nature == "pve":   # processus d'un CT / VM vus depuis l'hôte : leur invité
            for x in haut:
                x.append(invite_du_cgroup(lire(os.path.join(self.proc, str(x[0]), "cgroup"))))
        return haut, len(lignes)

    def _disques(self, maintenant):
        if maintenant - self.disques_t < 30 and self.disques_t:
            return self.disques
        out = []
        for dev, mp in montages(lire(os.path.join(self.proc, "mounts"))):
            try:
                s = os.statvfs(mp)
            except OSError:
                continue
            taille = s.f_blocks * s.f_frsize
            if taille > 0:
                out.append([mp, taille, (s.f_blocks - s.f_bfree) * s.f_frsize])
        self.disques, self.disques_t = out, maintenant
        return out

    def _pools(self, maintenant):
        if self.nature != "pve" or (maintenant - self.pools_t < 60 and self.pools_t) or not shutil.which("zpool"):
            return self.pools
        try:
            p = subprocess.Popen(["zpool", "list", "-Hp", "-o", "name,size,alloc,health"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            sortie = p.communicate(timeout=8)[0]
            out = []
            for ligne in sortie.decode("utf-8", "replace").splitlines():
                f = ligne.split("\t")
                if len(f) == 4 and f[1].isdigit():
                    out.append([f[0], int(f[1]), int(f[2]), f[3]])
            self.pools = out
        except (OSError, subprocess.SubprocessError):
            pass
        self.pools_t = maintenant
        return self.pools

    def mesurer(self):
        maintenant = time.time()
        dt = maintenant - self.prec_t if self.prec_t else 0
        cpu = cpu_stat(lire(os.path.join(self.proc, "stat")))
        ncpu = len([k for k in cpu if k != "cpu"]) or 1
        c, io, st = cpu_pourcents(cpu.get("cpu"), self.prec_cpu.get("cpu"))
        coeurs = [cpu_pourcents(cpu[k], self.prec_cpu.get(k))[0] for k in sorted((k for k in cpu if k != "cpu"), key=lambda k: int(k[3:]))]
        self.prec_cpu = cpu
        mem = meminfo(lire(os.path.join(self.proc, "meminfo")))
        la = lire(os.path.join(self.proc, "loadavg")).split()
        procs, nproc = self._processus(dt)
        self.seq += 1
        obj = {"v": VERSION, "h": self.nom, "k": self.nature, "t": round(maintenant, 1), "b": self.boot, "s": self.seq, "n": ncpu,
               "c": c, "cc": coeurs, "io": io, "st": st, "l": [float(x) for x in la[:3]] if len(la) >= 3 else None,
               "m": [mem["total"], mem["used"], arc_taille(lire(os.path.join(self.proc, "spl/kstat/zfs/arcstats")))],
               "sw": [mem["swap_total"], mem["swap_used"]], "up": int(float((lire(os.path.join(self.proc, "uptime")).split() or ["0"])[0])),
               "pr": procs, "np": nproc, "d": self._disques(maintenant)}
        if self.nature == "pve":
            obj["g"] = self._invites(dt, ncpu)
            obj["z"] = self._pools(maintenant)
        self.prec_t = maintenant
        return obj


def cibles(spec):
    out = []
    for x in (spec or "").split(","):
        x = x.strip()
        if x:
            h, _, p = x.rpartition(":")
            out.append((h.strip("[]") or x, int(p) if p.isdigit() else 8399))
    return out


def ip_des_invites(confs):
    """Textes des configurations de CT (/etc/pve/lxc/*.conf) -> IP v4 déclarées (net*: ...,ip=a.b.c.d/nn) : sources admises en transit."""
    out = set()
    for t in confs:
        out.update(re.findall(r"^net\d+:.*?\bip=(\d+\.\d+\.\d+\.\d+)", t or "", re.M))
    return out


def admis(ip, connues, depuis):
    """Source admise : IP d'un CT du nœud, ou dans --transit-depuis (IP ou réseau a.b.c.d/nn)."""
    if ip in connues:
        return True
    try:
        import ipaddress
        a = ipaddress.ip_address(ip)
        return any(a in ipaddress.ip_network(d, strict=False) for d in depuis)
    except ValueError:
        return False


def transit(ecoute, dest, depuis, duree=None):
    """Relaie tel quel vers le relais chaque paquet SH1E reçu d'une source admise (le relais vérifie la signature)."""
    h, _, p = ecoute.rpartition(":")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind((h or "0.0.0.0", int(p)))
    s.settimeout(1)
    sortie = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    connues, lu, adresses, resolu, debut, compte = set(), 0, [], 0, time.time(), {"relayes": 0, "refuses": 0}
    while duree is None or time.time() - debut < duree:
        t = time.time()
        if t - lu > 60:
            connues = ip_des_invites(lire(c) for c in glob.glob("/etc/pve/lxc/*.conf"))
            lu = t
        if t - resolu > 60:
            adresses = []
            for hh, pp in dest:
                try:
                    adresses.append(socket.getaddrinfo(hh, pp, socket.AF_INET, socket.SOCK_DGRAM)[0][4])
                except (OSError, socket.gaierror) as e:
                    sys.stderr.write("relais %s introuvable : %s\n" % (hh, e))
            resolu = t
        try:
            paquet, (ip, _) = s.recvfrom(65535)
        except socket.timeout:
            continue
        if paquet[:4] != MAGIE or not admis(ip, connues, depuis):
            compte["refuses"] += 1
            continue
        for ad in adresses:
            try:
                sortie.sendto(paquet, ad)
                compte["relayes"] += 1
            except OSError as e:
                sys.stderr.write("transit vers %s : %s\n" % (ad, e))
    s.close()
    return compte


def main(argv=None):
    ap = argparse.ArgumentParser(description="si-htop : émetteur UDP (#800)")
    ap.add_argument("--relais", default=os.environ.get("SI_HTOP_RELAIS", ""))
    ap.add_argument("--cle-fichier", default=os.environ.get("SI_HTOP_CLE_FICHIER", "/etc/si-htop/cle"))
    ap.add_argument("--nom", default=os.environ.get("SI_HTOP_NOM") or None)
    ap.add_argument("--periode", type=float, default=2.0)
    ap.add_argument("--afficher", action="store_true", help="un relevé JSON sur la sortie standard, rien n'est envoyé")
    ap.add_argument("--transit", default=os.environ.get("SI_HTOP_TRANSIT", ""), help="adresse:port d'écoute du relais local des CT (#802)")
    ap.add_argument("--transit-depuis", default=os.environ.get("SI_HTOP_TRANSIT_DEPUIS", ""), help="IP ou réseaux admis en plus des CT (virgules)")
    a = ap.parse_args(argv)
    if a.transit:
        dest = cibles(a.relais)
        if not dest:
            sys.stderr.write("aucun relais (--relais hote:port)\n")
            return 2
        transit(a.transit, dest, [d.strip() for d in a.transit_depuis.split(",") if d.strip()])
        return 0
    r = Releve(a.nom)
    if a.afficher:
        r.mesurer()
        time.sleep(1)
        print(json.dumps(r.mesurer(), ensure_ascii=False, indent=1))
        return 0
    cle = lire(a.cle_fichier).strip().encode("utf-8")
    if len(cle) < 16:
        sys.stderr.write("clé absente ou trop courte (16 caractères au moins) : %s\n" % a.cle_fichier)
        return 2
    dest = cibles(a.relais)
    if not dest:
        sys.stderr.write("aucun relais (--relais hote:port)\n")
        return 2
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    adresses, resolu = {}, 0
    r.mesurer()
    while True:
        debut = time.time()
        if debut - resolu > 60:
            for h, p in dest:
                try:
                    adresses[(h, p)] = socket.getaddrinfo(h, p, socket.AF_INET, socket.SOCK_DGRAM)[0][4]
                except (OSError, socket.gaierror) as e:
                    sys.stderr.write("relais %s introuvable : %s\n" % (h, e))
            resolu = debut
        time.sleep(max(0.2, a.periode - (time.time() - debut)))
        try:
            paquet = emballer(MAGIE, cle, r.mesurer())
        except Exception as e:  # noqa: BLE001 -- un relevé raté n'arrête pas l'émetteur
            sys.stderr.write("relevé : %s\n" % e)
            continue
        for ad in adresses.values():
            try:
                sock.sendto(paquet, ad)
            except OSError as e:
                sys.stderr.write("envoi vers %s : %s\n" % (ad, e))


if __name__ == "__main__":
    sys.exit(main())
