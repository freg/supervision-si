# -*- coding: utf-8 -*-
"""Sonde « postes Windows » (livraison #567) -- bibliothèque standard seulement.

Pour chaque hôte des cibles : NetBIOS node status (UDP 137), négociation SMB2
(TCP 445), demande de connexion RDP X.224 (TCP 3389), présence des ports
AnyDesk 7070, VNC 5900, WinRM 5985/5986, SSH 22. Aucune authentification.
Sortie JSON : {"at", "targets", "hosts": [...], "findings": [...], "stats"}.
Les analyseurs (nbstat, smb2, rdp) sont des fonctions pures testées
(si-agent/agent/test_windows_probe.py)."""
import concurrent.futures
import ipaddress
import json
import os
import random
import socket
import struct
import subprocess
import sys
import time

PORTS = {"smb": 445, "rdp": 3389, "anydesk": 7070, "vnc": 5900, "winrm": 5985, "winrm_tls": 5986, "ssh": 22, "http": 80, "https": 443}
CONNECT_TIMEOUT = 0.6
MAX_HOSTS = 1024


# ------------------------------------------------------------------ NetBIOS
def nbstat_query(txid=None):
    """Requête NBSTAT (« * » encodé en premier niveau) -- bytes."""
    txid = random.randint(1, 65535) if txid is None else txid
    name = b"CKAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"  # « * » + 15 espaces, encodés
    return struct.pack(">HHHHHH", txid, 0x0000, 1, 0, 0, 0) + b"\x20" + name + b"\x00" + struct.pack(">HH", 0x0021, 0x0001)


def parse_nbstat(data):
    """Réponse NBSTAT -> {"name", "workgroup", "mac", "names": [...]} ou None."""
    if not data or len(data) < 57:
        return None
    try:
        ancount = struct.unpack(">H", data[6:8])[0]
        if ancount < 1:
            return None
        p = 12
        while p < len(data) and data[p] != 0:  # nom (question répétée dans la réponse)
            p += data[p] + 1
        p += 1 + 2 + 2 + 4  # 0, type, class, ttl
        rdlen = struct.unpack(">H", data[p:p + 2])[0]; p += 2
        n = data[p]; p += 1
        names = []
        for _ in range(n):
            raw = data[p:p + 15]; suffix = data[p + 15]; flags = struct.unpack(">H", data[p + 16:p + 18])[0]; p += 18
            names.append({"name": raw.decode("latin-1").rstrip(), "suffix": suffix, "group": bool(flags & 0x8000)})
        mac = ":".join("%02x" % b for b in data[p:p + 6]) if len(data) >= p + 6 else None
        host = next((x["name"] for x in names if x["suffix"] == 0x00 and not x["group"]), None) or next((x["name"] for x in names if x["suffix"] == 0x20), None)
        group = next((x["name"] for x in names if x["suffix"] == 0x00 and x["group"]), None)
        return {"name": host, "workgroup": group, "mac": mac if mac and mac != "00:00:00:00:00:00" else None, "names": names}
    except (struct.error, IndexError):
        return None


def nbstat(ip, timeout=1.0):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.settimeout(timeout)
    try:
        s.sendto(nbstat_query(), (ip, 137))
        data, _ = s.recvfrom(1024)
        return parse_nbstat(data)
    except (socket.timeout, OSError):
        return None
    finally:
        s.close()


# ------------------------------------------------------------------ SMB
SMB_DIALECTS = {0x0202: "2.0.2", 0x0210: "2.1", 0x0300: "3.0", 0x0302: "3.0.2", 0x0311: "3.1.1"}


def smb2_negotiate_request():
    dialects = [0x0202, 0x0210, 0x0300, 0x0302, 0x0311]
    hdr = b"\xfeSMB" + struct.pack("<HHIHHIIQIIQ16s", 64, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, b"\x00" * 16)
    body = struct.pack("<HHHHI", 36, len(dialects), 1, 0, 0) + b"\x00" * 16 + struct.pack("<Q", 0) + b"".join(struct.pack("<H", d) for d in dialects)
    msg = hdr + body
    return struct.pack(">I", len(msg)) + msg


def smb1_negotiate_request():
    """Négociation SMB1 (NT LM 0.12 seul) : si le serveur répond en SMB1, il l'accepte encore."""
    hdr = b"\xffSMB" + b"\x72" + b"\x00" * 4 + b"\x18" + b"\x53\xc8" + b"\x00" * 2 + b"\x00" * 8 + b"\x00" * 2 + struct.pack("<HHH", 0xfffe, 0, 0)
    dialect = b"\x02NT LM 0.12\x00"
    body = b"\x00" + struct.pack("<H", len(dialect)) + dialect
    msg = hdr + body
    return struct.pack(">I", len(msg)) + msg


def parse_smb2_negotiate(data):
    """Réponse (sans les 4 octets NetBIOS) -> {"dialect", "signing_required", "guid"} ou None."""
    if not data or len(data) < 64 + 8 or data[:4] != b"\xfeSMB":
        return None
    try:
        body = data[64:]
        size, security_mode, dialect = struct.unpack("<HHH", body[:6])
        guid = body[8:24].hex()
        return {"dialect": SMB_DIALECTS.get(dialect, "0x%04x" % dialect), "signing_required": bool(security_mode & 0x02), "guid": guid}
    except struct.error:
        return None


def _smb_exchange(ip, payload, timeout):
    s = socket.create_connection((ip, 445), timeout=timeout)
    try:
        s.sendall(payload)
        head = s.recv(4)
        if len(head) < 4:
            return None
        n = struct.unpack(">I", head)[0] & 0xffffff
        buf = b""
        while len(buf) < n:
            chunk = s.recv(n - len(buf))
            if not chunk:
                break
            buf += chunk
        return buf
    finally:
        s.close()


def smb_probe(ip, timeout=2.0):
    out = {"open": False}
    try:
        r = _smb_exchange(ip, smb2_negotiate_request(), timeout)
    except OSError:
        return out
    out["open"] = True
    parsed = parse_smb2_negotiate(r)
    if parsed:
        out.update(parsed)
    try:
        r1 = _smb_exchange(ip, smb1_negotiate_request(), timeout)
        out["smb1"] = bool(r1 and r1[:4] == b"\xffSMB")
    except OSError:
        out["smb1"] = None
    return out


# ------------------------------------------------------------------ RDP
def rdp_request():
    """X.224 Connection Request + RDP_NEG_REQ (TLS | CredSSP | RDSTLS)."""
    neg = struct.pack("<BBHI", 1, 0, 8, 0x0B)
    x224 = struct.pack(">BBHHB", 6 + len(neg), 0xE0, 0, 0, 0) + neg
    return struct.pack(">BBH", 3, 0, 4 + len(x224)) + x224


def parse_rdp_response(data):
    """-> {"nla": bool, "tls": bool, "protocol": "..."} ou None."""
    if not data or len(data) < 11 or data[0] != 3:
        return None
    try:
        x = data[4:]
        if x[1] != 0xD0:  # Connection Confirm
            return None
        if len(x) < 15:
            return {"nla": False, "tls": False, "protocol": "standard RDP security"}
        typ, _flags, _ln, proto = struct.unpack("<BBHI", x[7:15])
        if typ == 3:  # RDP_NEG_FAILURE
            return {"nla": False, "tls": False, "protocol": "refus (code %d)" % proto}
        return {"nla": bool(proto & 0x02), "tls": bool(proto & 0x01), "protocol": {0: "standard", 1: "TLS", 2: "CredSSP (NLA)", 8: "RDSTLS"}.get(proto, "0x%x" % proto)}
    except (struct.error, IndexError):
        return None


def rdp_probe(ip, timeout=2.0):
    try:
        s = socket.create_connection((ip, 3389), timeout=timeout)
    except OSError:
        return {"open": False}
    try:
        s.sendall(rdp_request())
        data = s.recv(64)
    except OSError:
        data = b""
    finally:
        s.close()
    out = {"open": True}
    parsed = parse_rdp_response(data)
    if parsed:
        out.update(parsed)
    return out


# ------------------------------------------------------------------ ports
def port_open(ip, port, timeout=CONNECT_TIMEOUT):
    try:
        s = socket.create_connection((ip, port), timeout=timeout)
        s.close()
        return True
    except OSError:
        return False


def ping(ip, timeout=1):
    try:
        r = subprocess.run(["ping", "-c", "1", "-W", str(timeout), ip] if os.name != "nt" else ["ping", "-n", "1", "-w", str(timeout * 1000), ip],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=timeout + 2)
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


# ------------------------------------------------------------------ cibles
def own_networks():
    """Sous-réseaux IPv4 du poste (/24 au plus large), via `ip -4 -o addr` ; repli hostname."""
    nets = []
    try:
        out = subprocess.run(["ip", "-4", "-o", "addr"], capture_output=True, text=True, timeout=5).stdout
        for line in out.splitlines():
            parts = line.split()
            if len(parts) > 3 and "/" in parts[3] and parts[1] != "lo":
                n = ipaddress.ip_network(parts[3], strict=False)
                if n.prefixlen < 24:  # jamais plus large qu'un /24 : 254 hôtes par sonde
                    n = ipaddress.ip_network((parts[3].split("/")[0], 24), strict=False)
                nets.append(str(n))
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    if not nets:  # sans `ip` (Windows, VM minimale) : l'adresse de sortie vers le réseau
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("192.0.2.1", 9)); ip = s.getsockname()[0]; s.close()
            if not ip.startswith("127."):
                nets.append(str(ipaddress.ip_network((ip, 24), strict=False)))
        except (OSError, ValueError):
            pass
    return sorted(set(nets))


def expand_targets(specs):
    ips = []
    for spec in specs:
        spec = spec.strip()
        if not spec:
            continue
        try:
            if "/" in spec:
                ips.extend(str(h) for h in ipaddress.ip_network(spec, strict=False).hosts())
            else:
                ips.append(str(ipaddress.ip_address(spec)))
        except ValueError:
            continue
    seen = set(); out = []
    for ip in ips:
        if ip not in seen:
            seen.add(ip); out.append(ip)
    return out[:MAX_HOSTS]


# ------------------------------------------------------------------ collecte
def probe_host(ip, full=True):
    """Un hôte : ports d'abord (rapides), puis NetBIOS/SMB/RDP si quelque chose répond."""
    ports = {k: port_open(ip, p) for k, p in PORTS.items()}
    alive = any(ports.values())
    nb = nbstat(ip)
    if not alive and not nb and not ping(ip):
        return None
    host = {"ip": ip, "ports": {k: p for k, p in PORTS.items() if ports[k]}, "netbios": nb and {k: nb[k] for k in ("name", "workgroup", "mac")},
            "name": (nb or {}).get("name"), "mac": (nb or {}).get("mac"), "workgroup": (nb or {}).get("workgroup")}
    if full and ports["smb"]:
        host["smb"] = smb_probe(ip)
    if full and ports["rdp"]:
        host["rdp"] = rdp_probe(ip)
    host["windows_like"] = bool(nb or ports["smb"] or ports["rdp"] or ports["winrm"])
    return host


def findings_for(host):
    f = []
    smb = host.get("smb") or {}
    rdp = host.get("rdp") or {}
    if smb.get("smb1"):
        f.append({"code": "smb1_enabled", "severity": "warning", "text": "accepte encore SMB1 (protocole obsolète, vecteur de rançongiciel)"})
    if smb.get("open") and smb.get("signing_required") is False:
        f.append({"code": "smb_signing_optional", "severity": "info", "text": "signature SMB non exigée"})
    if rdp.get("open") and rdp.get("nla") is False and "protocol" in rdp:
        f.append({"code": "rdp_without_nla", "severity": "warning", "text": "RDP ouvert sans NLA (%s)" % rdp.get("protocol")})
    if host.get("ports", {}).get("vnc"):
        f.append({"code": "vnc_open", "severity": "info", "text": "VNC en écoute"})
    if host.get("windows_like") and not host.get("name"):
        f.append({"code": "netbios_silent", "severity": "info", "text": "pas de réponse NetBIOS (pare-feu ou service désactivé) : nom inconnu"})
    return f


def collect(specs, workers=48):
    targets = own_networks() if specs == ["auto"] else specs
    ips = expand_targets(targets)
    started = time.time()
    hosts = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as ex:
        for h in ex.map(probe_host, ips):
            if h:
                hosts.append(h)
    hosts.sort(key=lambda h: tuple(int(x) for x in h["ip"].split(".")))
    findings = []
    for h in hosts:
        h["findings"] = findings_for(h)
        for f in h["findings"]:
            findings.append(dict(f, ip=h["ip"], name=h.get("name")))
    # `alerts` : même forme que les autres sondes (#530) -> événements du central au changement
    alerts = [{"code": "%s@%s" % (f["code"], f["ip"]), "severity": f["severity"], "message": "%s (%s) : %s" % (f.get("name") or f["ip"], f["ip"], f["text"])} for f in findings]
    return {"at": int(time.time()), "targets": targets, "scanned": len(ips), "duration_seconds": round(time.time() - started, 1),
            "hosts": hosts, "findings": findings, "alerts": alerts,
            "stats": {"alive": len(hosts), "windows_like": sum(1 for h in hosts if h["windows_like"]), "rdp": sum(1 for h in hosts if "rdp" in h["ports"]),
                      "anydesk": sum(1 for h in hosts if "anydesk" in h["ports"]), "smb": sum(1 for h in hosts if "smb" in h["ports"])}}


def main(argv):
    specs = ["auto"]
    i = 0
    while i < len(argv):
        if argv[i] == "--targets" and i + 1 < len(argv):
            specs = [x for x in argv[i + 1].split(",") if x]; i += 2; continue
        i += 1
    try:
        print(json.dumps(collect(specs)))
    except Exception as exc:  # noqa: BLE001 -- une sonde ne doit jamais planter l'agent
        print(json.dumps({"error": "collecte échouée : %s" % exc}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
