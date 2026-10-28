#!/usr/bin/env python3
"""Plugin si-agent « partages-reseau » (#902) : inventaire des partages de fichiers servis sur le LAN, LECTURE SEULE.

Pour chaque machine SMB (port 445) des réseaux ciblés, liste les partages offerts et teste s'ils sont lisibles sans
authentification (session « invité »), sans jamais écrire ni lire de fichier. Repère les partages ouverts à tous, les
serveurs en SMBv1 et l'absence de signature. Le NAS déjà suivi par SNMP (#883) peut être exclu (--exclude). À coupler
avec la découverte d'hôtes : --targets explicites, ou les machines SMB déjà vues par la sonde windows-probe du même
agent (--from-windows-probe, lu par l'API). Désactivée par défaut.

Énumération par `smbclient -L` (paquet smba / samba-client) ; à défaut, seules les présences SMB sont rapportées
(port ouvert, dialecte), sans la liste des partages. Jamais d'authentification : uniquement la session invité (-N).

Arguments : --targets a.b.c.0/24,ip,…  [--exclude ip,…]  [--max-hosts 512]  [--timeout 4]
"""
import argparse
import ipaddress
import json
import os
import re
import shutil
import socket
import struct
import subprocess
import sys
import time

SMB_DIALECTS = {0x0202: "SMB 2.0.2", 0x0210: "SMB 2.1", 0x0300: "SMB 3.0", 0x0302: "SMB 3.0.2", 0x0311: "SMB 3.1.1"}
ADMIN = {"ADMIN$", "IPC$", "print$"}
LIGNE = re.compile(r"^\s*(\S+)\s+(Disk|Disque|IPC|Printer|Imprimante)\s*(.*)$", re.I)


def hotes(cibles, exclure=None, maxi=512):
    exclure = set(exclure or [])
    def flux():
        for c in cibles:
            try:
                if "/" in c:
                    for a in ipaddress.ip_network(c, strict=False).hosts():
                        yield str(a)
                else:
                    yield str(ipaddress.ip_address(c))
            except ValueError:
                continue
    vus, res = set(), []
    for ip in flux():
        if ip not in vus and ip not in exclure:
            vus.add(ip)
            res.append(ip)
            if len(res) >= maxi:
                break
    return res


def smb2_negotiate():
    h = struct.pack("<4sHHIHH16s", b"\xfeSMB", 64, 0, 0, 0, 0, b"\x00" * 16) + struct.pack("<IIQQQ", 0, 0, 0, 0, 0)
    d = [0x0202, 0x0210, 0x0300, 0x0302, 0x0311]
    body = struct.pack("<HHHH I 16s", 36, len(d), 0x01, 0, 0, b"\x00" * 16) + struct.pack("<IHHHH", 0, 0, 0, 0, 0) + b"".join(struct.pack("<H", x) for x in d)
    pdu = h + body
    return struct.pack(">I", len(pdu)) + pdu


def presence_smb(ip, timeout):
    """(ouvert, dialecte, signature exigée) par une négociation SMB2, sans authentification."""
    try:
        s = socket.create_connection((ip, 445), timeout=timeout)
    except OSError:
        return {"smb": False}
    try:
        s.sendall(smb2_negotiate())
        head = s.recv(4)
        if len(head) < 4:
            return {"smb": True}
        n = struct.unpack(">I", head)[0] & 0xFFFFFF
        buf = b""
        while len(buf) < n:
            c = s.recv(n - len(buf))
            if not c:
                break
            buf += c
        if len(buf) >= 72 and buf[:4] == b"\xfeSMB":
            mode, dial = struct.unpack("<HH", buf[64:68])
            return {"smb": True, "dialecte": SMB_DIALECTS.get(dial, "0x%04x" % dial), "signature_exigee": bool(mode & 0x02)}
        return {"smb": True}
    except OSError:
        return {"smb": True}
    finally:
        s.close()


def parse_smbclient(sortie):
    """Sortie de `smbclient -L //ip -N` -> [{nom, type, commentaire}] (hors partages administratifs)."""
    parts = []
    for l in (sortie or "").splitlines():
        if "Sharename" in l or "---------" in l or not l.strip():
            continue
        m = LIGNE.match(l)
        if not m:
            continue
        nom, typ, com = m.group(1), m.group(2).lower(), m.group(3).strip()
        typ = "disque" if typ.startswith(("disk", "disque")) else "imprimante" if typ.startswith(("print", "impr")) else "ipc"
        parts.append({"nom": nom, "type": typ, "commentaire": com, "administratif": nom.upper() in ADMIN or nom.endswith("$")})
    return parts


def enumerer(ip, timeout, runner, smbclient):
    """Partages d'une machine via smbclient -L (session invité) ; ([...], accessible_invite, erreur)."""
    try:
        p = runner([smbclient, "-L", "//%s" % ip, "-N", "-g", "-t", str(int(timeout))], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout * 3 + 5, universal_newlines=True)
    except (OSError, subprocess.TimeoutExpired) as e:
        return [], False, str(e)[:120]
    texte = (p.stdout or "") + (p.stderr or "")
    if "-g" in texte or "Disk|" in texte or "\nDisk|" in texte:   # format -g : "Disk|nom|commentaire"
        parts = []
        for l in texte.splitlines():
            f = l.split("|")
            if len(f) >= 2 and f[0] in ("Disk", "IPC", "Printer"):
                nom = f[1]
                parts.append({"nom": nom, "type": {"Disk": "disque", "IPC": "ipc", "Printer": "imprimante"}[f[0]], "commentaire": (f[2] if len(f) > 2 else "").strip(),
                              "administratif": nom.upper() in ADMIN or nom.endswith("$")})
    else:
        parts = parse_smbclient(texte)
    invite = bool(parts) and "NT_STATUS_ACCESS_DENIED" not in texte and "NT_STATUS_LOGON_FAILURE" not in texte
    err = None
    if not parts:
        m = re.search(r"NT_STATUS_\w+", texte)
        err = m.group(0) if m else (texte.strip()[:120] or None)
    return parts, invite, err


def main(argv=None, runner=subprocess.run, which=shutil.which):
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default="")
    ap.add_argument("--exclude", default="")
    ap.add_argument("--max-hosts", type=int, default=512)
    ap.add_argument("--timeout", type=float, default=4)
    a = ap.parse_args(argv)
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "serveurs": [], "alerts": []}
    cibles = hotes([x for x in re.split(r"[\s,]+", a.targets) if x], [x for x in re.split(r"[\s,]+", a.exclude) if x], a.max_hosts)
    if not cibles:
        out["alerts"].append({"code": "partages-cibles", "severity": "info", "message": "aucune cible : --targets a.b.c.0/24,…"})
        return out
    smbclient = which("smbclient")
    if not smbclient:
        out["alerts"].append({"code": "partages-smbclient", "severity": "info", "message": "smbclient absent (apt install smbclient) : seules les présences SMB sont rapportées, sans la liste des partages"})
    for ip in cibles:
        pres = presence_smb(ip, a.timeout)
        if not pres.get("smb"):
            continue
        s = {"ip": ip, "dialecte": pres.get("dialecte"), "signature_exigee": pres.get("signature_exigee"), "partages": [], "accessible_invite": None, "erreur": None}
        if smbclient:
            s["partages"], s["accessible_invite"], s["erreur"] = enumerer(ip, a.timeout, runner, smbclient)
        out["serveurs"].append(s)
        util = [p for p in s["partages"] if not p["administratif"] and p["type"] == "disque"]
        if s["accessible_invite"] and util:
            out["alerts"].append({"code": "partages-invite@%s" % ip, "severity": "warning",
                                  "message": "%s : %d partage(s) lisible(s) sans authentification (%s)" % (ip, len(util), ", ".join(p["nom"] for p in util[:6]))})
        if pres.get("signature_exigee") is False and util:
            out["alerts"].append({"code": "partages-signature@%s" % ip, "severity": "info", "message": "%s : signature SMB non exigée" % ip})
    out["serveurs"].sort(key=lambda s: tuple(int(x) for x in s["ip"].split(".")) if s["ip"].count(".") == 3 else (0,))
    # SMBv1 : repéré par windows-probe ; ici on signale l'absence de SMB2 (négociation SMB2 sans réponse de dialecte)
    for s in out["serveurs"]:
        if s["partages"] and s.get("dialecte") is None:
            out["alerts"].append({"code": "partages-smbv1@%s" % s["ip"], "severity": "warning", "message": "%s : pas de SMB2 négocié (SMBv1 probable, obsolète)" % s["ip"]})
    return out


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1:]), ensure_ascii=False))
