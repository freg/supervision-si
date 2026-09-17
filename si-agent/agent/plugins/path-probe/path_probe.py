#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « chemin de service » (livraison #527, famille « explorer »).

Rejoue, chaque minute et par interface, ce qu'un utilisateur subit quand il
dit « je n'ai plus Internet » -- dans l'ordre où ça casse :

1. bail : adresse IPv4, serveur DHCP, passerelle et DNS reçus (NetworkManager),
   âge et durée du bail ; adresse statique signalée ;
2. passerelle : ping court (latence, pertes) ;
3. DNS distribués : requête UDP/53 vers CHAQUE serveur reçu du DHCP (un
   serveur mort parmi d'autres est un constat, un seul serveur distribué en
   est un autre) ;
4. DNS publics : mêmes requêtes vers 8.8.8.8 / 1.1.1.1 (sortie UDP/53) ;
5. HTTP réel : GET d'une page de test connue (portail captif / interception
   détectés sur le contenu), puis HTTPS (certificat vérifié).

Les sockets sont liés à l'adresse de l'interface ; pour une interface sans
route par défaut (Wi-Fi d'observation), une table de routage dédiée est
posée le temps du passage puis retirée (`ip rule` / `ip route ... table`).

Rotation optionnelle (`--connections wifi-a,wifi-b`) : à chaque passage la
sonde active la connexion NetworkManager suivante, ce qui rejoue un vrai
échange DHCP sur chaque SSID à tour de rôle.

Stdlib seulement ; `ip`, `ping`, `nmcli` requis (`iw` pour le SSID).
Usage : path_probe.py [--ifaces auto|a,b] [--connections c1,c2] [--name NOM]
                      [--public-dns 8.8.8.8,1.1.1.1] [--http URL] [--https URL]
                      [--state FICHIER]
"""
import http.client
import json
import os
import random
import re
import socket
import ssl
import struct
import subprocess
import sys
import time
import urllib.parse

VERSION = "1"
STATE_DEFAULT = "/var/lib/si-agent/path-probe.state.json"
PUBLIC_DNS = ["8.8.8.8", "1.1.1.1"]
HTTP_URL = "http://detectportal.firefox.com/success.txt"
HTTP_EXPECT = "success"
HTTPS_URL = "https://www.google.com/generate_204"
THRESHOLDS = {"gw_loss_warn": 5.0, "gw_ms_warn": 50.0, "dns_ms_warn": 500.0, "http_ms_warn": 3000.0}
ROUTE_TABLE_BASE = 250


def run(cmd, timeout=30):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)


# --- analyseurs (purs, testés) -------------------------------------------

def parse_dhcp_options(text):
    """Sortie de `nmcli -f DHCP4 device show IFACE` -> {option: valeur}."""
    opts = {}
    for m in re.finditer(r"DHCP4\.OPTION\[\d+\]:\s*(\S+)\s*=\s*(.*)", text or ""):
        opts[m.group(1)] = m.group(2).strip()
    return opts


def parse_ip_addr(text):
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)/(\d+)", text or "")
    return (m.group(1), int(m.group(2))) if m else (None, None)


def parse_ping(text):
    out = {"sent": 0, "received": 0, "loss_pct": None, "avg_ms": None}
    m = re.search(r"(\d+) packets transmitted, (\d+) received.*?([\d.]+)% packet loss", text or "")
    if m:
        out.update(sent=int(m.group(1)), received=int(m.group(2)), loss_pct=float(m.group(3)))
    m = re.search(r"= ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms", text or "")
    if m:
        out["avg_ms"] = float(m.group(2))
    return out


def build_dns_query(name, tid, qtype=1):
    header = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    q = b"".join(bytes([len(p)]) + p.encode("idna") for p in name.strip(".").split(".")) + b"\x00"
    return header + q + struct.pack(">HH", qtype, 1)


def _skip_name(data, pos):
    while True:
        if pos >= len(data):
            raise ValueError("réponse tronquée")
        n = data[pos]
        if n == 0:
            return pos + 1
        if n & 0xC0 == 0xC0:
            return pos + 2
        pos += n + 1


def parse_dns_response(data, tid):
    """Réponse DNS brute -> {rcode, answers (A), count} ; ValueError si incohérente."""
    if len(data) < 12:
        raise ValueError("réponse trop courte")
    rtid, flags, qd, an = struct.unpack(">HHHH", data[:8])
    if rtid != tid:
        raise ValueError("identifiant de réponse inattendu")
    if not flags & 0x8000:
        raise ValueError("pas une réponse")
    pos = 12
    for _ in range(qd):
        pos = _skip_name(data, pos) + 4
    answers = []
    for _ in range(an):
        pos = _skip_name(data, pos)
        rtype, _rclass, _ttl, rdlen = struct.unpack(">HHIH", data[pos:pos + 10])
        pos += 10
        if rtype == 1 and rdlen == 4:
            answers.append(".".join(str(b) for b in data[pos:pos + 4]))
        pos += rdlen
    return {"rcode": flags & 0xF, "answers": answers, "count": an}


RCODES = {0: "NOERROR", 1: "FORMERR", 2: "SERVFAIL", 3: "NXDOMAIN", 5: "REFUSED"}


def evaluate(path, t=None):
    """Constats d'un chemin (jamais d'action)."""
    t = t or THRESHOLDS
    alerts = []

    def add(sev, code, msg):
        alerts.append({"severity": sev, "code": code, "message": msg})

    tag = path.get("ssid") or path.get("connection") or path.get("iface") or "?"
    if path.get("up_error"):
        add("critical", "conn-up-failed", "%s : activation échouée (%s) -- pas de bail ?" % (tag, path["up_error"]))
    if not path.get("ip"):
        add("critical", "no-ip", "%s : aucune adresse IPv4 (pas de bail DHCP ?)" % tag)
        return alerts
    gw = path.get("gw_ping") or {}
    if gw.get("sent"):
        if gw.get("received") == 0:
            add("critical", "gw-unreachable", "%s : passerelle %s injoignable" % (tag, path.get("gateway")))
        elif (gw.get("loss_pct") or 0) > t["gw_loss_warn"]:
            add("warning", "gw-loss", "%s : %.0f %% de pertes vers la passerelle" % (tag, gw["loss_pct"]))
        elif (gw.get("avg_ms") or 0) > t["gw_ms_warn"]:
            add("warning", "gw-slow", "%s : passerelle à %.0f ms" % (tag, gw["avg_ms"]))
    dns = path.get("dns") or []
    if path.get("dhcp") and not path.get("static"):
        if len(dns) == 0:
            add("critical", "dns-none", "%s : aucun serveur DNS distribué par le DHCP" % tag)
        elif len(dns) == 1:
            add("warning", "dns-single", "%s : un seul serveur DNS distribué (%s), aucun secours" % (tag, dns[0]["server"]))
    ok = [d for d in dns if d.get("ok")]
    down = [d for d in dns if not d.get("ok")]
    if dns and not ok:
        add("critical", "dns-all-down", "%s : aucun des DNS distribués ne répond (%s)" % (tag, ", ".join(d["server"] for d in dns)))
    elif down:
        add("warning", "dns-server-down", "%s : DNS distribué %s ne répond pas (%s) -- les postes qui l'ont en premier ou en dur sont sans résolution" % (tag, ", ".join(d["server"] for d in down), down[0].get("error") or "erreur"))
    slow = [d for d in ok if (d.get("ms") or 0) > t["dns_ms_warn"]]
    if slow:
        add("warning", "dns-slow", "%s : résolution lente (%s)" % (tag, ", ".join("%s %.0f ms" % (d["server"], d["ms"]) for d in slow)))
    pub = path.get("dns_public") or []
    if pub and not any(d.get("ok") for d in pub) and gw.get("received"):
        add("critical", "dns-public-down", "%s : aucun DNS public ne répond (sortie UDP/53 coupée ou filtrée)" % tag)
    for key, label in (("http", "HTTP"), ("https", "HTTPS")):
        h = path.get(key)
        if not h:
            continue
        if h.get("portal"):
            add("critical", "captive-portal", "%s : %s intercepté (portail captif ou filtrage) : %s" % (tag, label, h.get("detail") or ""))
        elif not h.get("ok"):
            add("critical", key + "-failed", "%s : %s en échec (%s)" % (tag, label, h.get("error") or ("statut %s" % h.get("status"))))
        elif (h.get("ms") or 0) > t["http_ms_warn"]:
            add("warning", key + "-slow", "%s : %s en %.1f s" % (tag, label, h["ms"] / 1000.0))
    return alerts


def summarize(alerts):
    counts = {"critical": 0, "warning": 0}
    for a in alerts or []:
        counts[a.get("severity", "warning")] = counts.get(a.get("severity", "warning"), 0) + 1
    return {"state": "critical" if counts["critical"] else ("warning" if counts["warning"] else "ok"), "counts": counts}


# --- mesures réseau -------------------------------------------------------

def dns_query(server, name, source_ip=None, timeout=2.0):
    tid = random.randint(0, 65535)
    res = {"server": server, "ok": False, "ms": None, "rcode": None, "answers": [], "error": None}
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.settimeout(timeout)
        if source_ip:
            s.bind((source_ip, 0))
        t0 = time.monotonic()
        s.sendto(build_dns_query(name, tid), (server, 53))
        data, _ = s.recvfrom(4096)
        res["ms"] = round((time.monotonic() - t0) * 1000.0, 1)
        r = parse_dns_response(data, tid)
        res.update(rcode=RCODES.get(r["rcode"], str(r["rcode"])), answers=r["answers"][:4])
        res["ok"] = r["rcode"] == 0 and bool(r["answers"])
        if not res["ok"]:
            res["error"] = res["rcode"] if r["rcode"] else "aucune réponse A"
    except socket.timeout:
        res["error"] = "délai dépassé"
    except (OSError, ValueError) as exc:
        res["error"] = str(exc)[:80]
    finally:
        s.close()
    return res


def http_check(url, source_ip, resolve, expect=None, timeout=5.0):
    """GET url (source liée), hôte résolu par `resolve(host)` -> IP ; vérifie
    le statut et, pour HTTP, le contenu attendu (portail captif)."""
    u = urllib.parse.urlsplit(url)
    res = {"url": url, "ok": False, "status": None, "ms": None, "ip": None, "error": None, "portal": False}
    host = u.hostname
    ip = resolve(host)
    if not ip:
        res["error"] = "hôte %s non résolu" % host
        return res
    res["ip"] = ip
    t0 = time.monotonic()
    try:
        if u.scheme == "https":
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(ip, u.port or 443, timeout=timeout, context=ctx,
                                               source_address=(source_ip, 0) if source_ip else None)
            # SNI et vérification sur le nom, pas sur l'IP
            conn.connect = _https_connect(conn, ctx, host, ip, u.port or 443, timeout, source_ip)
        else:
            conn = http.client.HTTPConnection(ip, u.port or 80, timeout=timeout,
                                              source_address=(source_ip, 0) if source_ip else None)
        conn.request("GET", u.path or "/", headers={"Host": host, "User-Agent": "si-agent path-probe", "Connection": "close"})
        r = conn.getresponse()
        body = r.read(2048)
        res["ms"] = round((time.monotonic() - t0) * 1000.0, 1)
        res["status"] = r.status
        if u.scheme == "https":
            res["ok"] = r.status < 400
        else:
            text = body.decode("utf-8", "replace")
            if r.status in (301, 302, 303, 307, 308) and host not in (r.getheader("Location") or ""):
                res["portal"], res["detail"] = True, "redirigé vers %s" % (r.getheader("Location") or "?")[:80]
            elif expect and expect not in text:
                res["portal"], res["detail"] = True, "contenu inattendu (statut %s)" % r.status
            else:
                res["ok"] = r.status == 200
        conn.close()
    except ssl.SSLCertVerificationError as exc:
        res["portal"], res["detail"], res["error"] = True, "certificat non valide : %s" % str(exc)[:80], "certificat"
        res["ms"] = round((time.monotonic() - t0) * 1000.0, 1)
    except (OSError, http.client.HTTPException, ssl.SSLError) as exc:
        res["error"] = str(exc)[:80] or exc.__class__.__name__
    return res


def _https_connect(conn, ctx, host, ip, port, timeout, source_ip):
    def connect():
        sock = socket.create_connection((ip, port), timeout, (source_ip, 0) if source_ip else None)
        conn.sock = ctx.wrap_socket(sock, server_hostname=host)
    return connect


# --- routage temporaire ---------------------------------------------------

class TempRoute:
    """Table de routage dédiée pour sortir par une interface sans route par
    défaut (Wi-Fi d'observation) : posée à l'entrée, retirée à la sortie."""

    def __init__(self, iface, ip, gateway, table):
        self.iface, self.ip, self.gateway, self.table, self.active = iface, ip, gateway, table, False

    def __enter__(self):
        code, out, _ = run(["ip", "-4", "route", "show", "default", "dev", self.iface], 10)
        if code == 0 and "default" in out:
            return self  # l'interface a déjà sa route par défaut
        if not (self.ip and self.gateway):
            return self
        run(["ip", "-4", "route", "replace", "default", "via", self.gateway, "dev", self.iface, "table", str(self.table)], 10)
        run(["ip", "-4", "rule", "del", "priority", str(self.table)], 10)
        code, _, _ = run(["ip", "-4", "rule", "add", "from", self.ip, "lookup", str(self.table), "priority", str(self.table)], 10)
        self.active = code == 0
        return self

    def __exit__(self, *exc):
        if self.active:
            run(["ip", "-4", "rule", "del", "priority", str(self.table)], 10)
            run(["ip", "-4", "route", "flush", "table", str(self.table)], 10)
        return False


# --- collecte -------------------------------------------------------------

def detect_ifaces():
    code, out, _ = run(["ip", "-4", "-o", "addr", "show", "up"], 10)
    names = []
    for line in (out or "").splitlines():
        m = re.match(r"\d+:\s+(\S+)\s+inet", line)
        if m and re.match(r"^(en|eth|wl|ww)", m.group(1)) and m.group(1) not in names:
            names.append(m.group(1))
    return names


def describe_iface(iface):
    p = {"iface": iface, "connection": None, "ssid": None, "ip": None, "prefix": None, "gateway": None,
         "static": False, "dhcp": None, "dns_servers": []}
    code, out, _ = run(["ip", "-4", "-o", "addr", "show", "dev", iface], 10)
    p["ip"], p["prefix"] = parse_ip_addr(out)
    code, out, _ = run(["nmcli", "-g", "GENERAL.CONNECTION", "device", "show", iface], 10)
    if code == 0 and out.strip() and out.strip() != "--":
        p["connection"] = out.strip().splitlines()[0]
    code, out, _ = run(["iw", "dev", iface, "link"], 10)
    m = re.search(r"^\s*SSID: (.+)$", out or "", re.M)
    if m:
        p["ssid"] = m.group(1).strip()
    code, out, _ = run(["nmcli", "-f", "DHCP4", "device", "show", iface], 10)
    opts = parse_dhcp_options(out) if code == 0 else {}
    if opts:
        lease = int(opts.get("dhcp_lease_time") or 0) or None
        expiry = int(opts.get("expiry") or 0) or None
        p["dhcp"] = {"server": opts.get("dhcp_server_identifier"), "lease_s": lease, "expiry": expiry,
                     "age_s": (int(time.time()) - (expiry - lease)) if lease and expiry else None}
        p["gateway"] = (opts.get("routers") or "").split()[0] if opts.get("routers") else None
        p["dns_servers"] = (opts.get("domain_name_servers") or "").split()
    else:
        p["static"] = bool(p["ip"])
    if not p["gateway"]:
        code, out, _ = run(["ip", "-4", "route", "show", "default", "dev", iface], 10)
        m = re.search(r"default via (\S+)", out or "")
        if m:
            p["gateway"] = m.group(1)
    if not p["dns_servers"]:
        code, out, _ = run(["nmcli", "-g", "IP4.DNS", "device", "show", iface], 10)
        p["dns_servers"] = [x for x in re.split(r"[\s|]+", out or "") if re.match(r"^\d+\.\d+\.\d+\.\d+$", x)]
    return p


def measure_path(p, name, public_dns, http_url, https_url, table):
    if not p.get("ip"):
        return p
    with TempRoute(p["iface"], p["ip"], p.get("gateway"), table):
        if p.get("gateway"):
            code, out, _ = run(["ping", "-I", p["iface"], "-n", "-q", "-c", "5", "-i", "0.2", "-W", "1", p["gateway"]], 15)
            p["gw_ping"] = parse_ping(out)
        p["dns"] = [dns_query(s, name, p["ip"]) for s in p.get("dns_servers") or []]
        p["dns_public"] = [dns_query(s, name, p["ip"]) for s in public_dns]
        cache = {}

        def resolve(host):
            if host in cache:
                return cache[host]
            if re.match(r"^\d+\.\d+\.\d+\.\d+$", host):
                return host
            for srv in [d["server"] for d in p["dns"] if d.get("ok")] + [d["server"] for d in p["dns_public"] if d.get("ok")]:
                r = dns_query(srv, host, p["ip"])
                if r.get("ok"):
                    cache[host] = r["answers"][0]
                    return cache[host]
            cache[host] = None
            return None

        if http_url:
            p["http"] = http_check(http_url, p["ip"], resolve, HTTP_EXPECT if http_url == HTTP_URL else None)
        if https_url:
            p["https"] = http_check(https_url, p["ip"], resolve)
    return p


def rotate_connection(connections, state):
    """Active la connexion suivante de la liste ; renvoie (nom, erreur)."""
    if not connections:
        return None, None
    last = state.get("last_connection")
    idx = (connections.index(last) + 1) % len(connections) if last in connections else 0
    name = connections[idx]
    code, out, err = run(["nmcli", "-w", "30", "connection", "up", name], 45)
    if code != 0:
        return name, (err or out).strip().splitlines()[-1][:120] if (err or out).strip() else "nmcli %d" % code
    for _ in range(20):  # attendre l'adresse
        code, out, _ = run(["nmcli", "-g", "IP4.ADDRESS", "connection", "show", "--active", name], 10)
        if code == 0 and re.search(r"\d+\.\d+\.\d+\.\d+/", out or ""):
            return name, None
        time.sleep(1)
    return name, "pas d'adresse IPv4 après activation"


def load_state(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return {}


def save_state(path, state):
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(state, fh)
        os.replace(tmp, path)
    except OSError:
        pass


def collect(ifaces=None, connections=None, name="www.google.com", public_dns=None, http_url=HTTP_URL,
            https_url=HTTPS_URL, state_path=STATE_DEFAULT):
    result = {"plugin": "path-probe", "version": VERSION, "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    state = load_state(state_path)
    conn_name, up_error = rotate_connection(connections or [], state)
    if conn_name:
        state["last_connection"] = conn_name
        save_state(state_path, state)
        result["rotated_to"] = conn_name
    names = ifaces if ifaces and ifaces != ["auto"] else detect_ifaces()
    paths = []
    for i, iface in enumerate(names):
        p = describe_iface(iface)
        if conn_name and p.get("connection") == conn_name and up_error:
            p["up_error"] = up_error
        p = measure_path(p, name, public_dns or PUBLIC_DNS, http_url, https_url, ROUTE_TABLE_BASE + i)
        p["alerts"] = evaluate(p)
        p["summary"] = summarize(p["alerts"])
        paths.append(p)
    if conn_name and up_error and not any(p.get("up_error") for p in paths):
        paths.append({"iface": None, "connection": conn_name, "up_error": up_error, "alerts": [], "summary": None})
        paths[-1]["alerts"] = evaluate(paths[-1]); paths[-1]["summary"] = summarize(paths[-1]["alerts"])
    if not paths:
        result["error"] = "aucune interface IPv4 (ip -4 addr)"
    alerts = [a for p in paths for a in p.get("alerts", [])]
    result.update({"name": name, "paths": paths, "alerts": alerts, "summary": summarize(alerts)})
    return result


def main(argv):
    ifaces, connections, name, public, http_url, https_url, state = ["auto"], [], "www.google.com", None, HTTP_URL, HTTPS_URL, STATE_DEFAULT
    i = 0
    while i < len(argv):
        a, v = argv[i], argv[i + 1] if i + 1 < len(argv) else None
        if a == "--ifaces" and v is not None:
            ifaces = [x for x in v.split(",") if x]; i += 2; continue
        if a == "--connections" and v is not None:
            connections = [x for x in v.split(",") if x]; i += 2; continue
        if a == "--name" and v is not None:
            name = v; i += 2; continue
        if a == "--public-dns" and v is not None:
            public = [x for x in v.split(",") if x]; i += 2; continue
        if a == "--http" and v is not None:
            http_url = None if v in ("", "none") else v; i += 2; continue
        if a == "--https" and v is not None:
            https_url = None if v in ("", "none") else v; i += 2; continue
        if a == "--state" and v is not None:
            state = v; i += 2; continue
        i += 1
    try:
        print(json.dumps(collect(ifaces, connections, name, public, http_url, https_url, state)))
    except Exception as exc:  # noqa: BLE001 -- une sonde ne doit jamais planter l'agent
        print(json.dumps({"error": "collecte échouée : %s" % exc}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
