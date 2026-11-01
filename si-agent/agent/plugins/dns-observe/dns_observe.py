#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « observabilité DNS » (livraison #639, item 105, famille explorer).

Complète `path-probe` : au lieu de vérifier qu'un DNS répond, elle observe
CE QU'IL RÉPOND et compare les résolutions d'une même liste de noms selon la
SOURCE (interface / connexion Wi-Fi / route) et selon le RÉSOLVEUR interrogé.
Cible le type d'incident « la ressource marche depuis un segment, pas depuis
un autre » : DNS différent par VLAN, réponse divergente, NXDOMAIN partiel,
résolveur inattendu.

Pour chaque interface IPv4 (option `--connections` : rotation Wi-Fi comme
path-probe), et pour chaque nom de `--names`, la sonde interroge chaque DNS
distribué par le DHCP + les DNS publics, et enregistre : résolveur, IP(s)
renvoyées (triées), rcode/erreur, latence. Puis l'analyse PURE (testable)
apprend les réponses, compare les répartitions par source et par destination,
et produit des constats. Un état local retient la dernière réponse par
(nom, résolveur) pour signaler un CHANGEMENT entre deux passages.

Constats (`alerts`, repris en événements par le central, #530) :
  dns-divergent   : un nom résout vers des IP différentes selon la source/résolveur
  dns-partial-nxdomain : un nom résout sur certaines sources, échoue (NXDOMAIN) sur d'autres
  dns-answer-changed   : la réponse d'un résolveur pour un nom a changé depuis le dernier passage
  dns-unexpected-resolver : une source utilise un résolveur hors de la liste attendue (--expected-dns)
  dns-all-down    : aucun résolveur ne répond pour un nom

Stdlib seulement ; `ip`, `nmcli` (comme path-probe) pour l'inventaire des sources.
Usage : dns_observe.py --names a.fr,b.fr [--ifaces auto|a,b] [--connections c1,c2]
        [--public-dns 8.8.8.8,1.1.1.1] [--expected-dns 192.0.2.1,192.0.2.2] [--state FICHIER]
"""
import json
import os
import re
import socket
import struct
import subprocess
import sys
import time

STATE_DEFAULT = "/var/lib/si-agent/dns-observe.state.json"
PUBLIC_DNS = ["8.8.8.8", "1.1.1.1"]
DNS_MS_WARN = 800.0


# ---------------------------------------------------------------------------
# codec DNS minimal (A + AAAA), stdlib
# ---------------------------------------------------------------------------
def build_query(name, tid, qtype=1):
    q = struct.pack(">HHHHHH", tid, 0x0100, 1, 0, 0, 0)
    for part in name.rstrip(".").split("."):
        q += struct.pack(">B", len(part)) + part.encode("idna" if any(ord(c) > 127 for c in part) else "ascii")
    return q + b"\x00" + struct.pack(">HH", qtype, 1)


def _skip_name(data, pos):
    while pos < len(data):
        n = data[pos]
        if n == 0:
            return pos + 1
        if n & 0xC0 == 0xC0:
            return pos + 2
        pos += n + 1
    return pos


def parse_answer(data, tid):
    """-> (rcode, [ip triées]) ; lève ValueError si l'identifiant ne correspond pas."""
    if len(data) < 12:
        raise ValueError("réponse tronquée")
    rid, flags, qd, an = struct.unpack(">HHHH", data[:8])
    if rid != tid:
        raise ValueError("identifiant DNS différent")
    rcode = flags & 0x0F
    pos = 12
    for _ in range(qd):
        pos = _skip_name(data, pos) + 4
    ips = []
    for _ in range(an):
        pos = _skip_name(data, pos)
        if pos + 10 > len(data):
            break
        rtype, _cls, _ttl, rdlen = struct.unpack(">HHIH", data[pos:pos + 10])
        pos += 10
        rdata = data[pos:pos + rdlen]
        if rtype == 1 and rdlen == 4:
            ips.append(socket.inet_ntoa(rdata))
        elif rtype == 28 and rdlen == 16:
            ips.append(socket.inet_ntop(socket.AF_INET6, rdata))
        pos += rdlen
    return rcode, sorted(ips)


RCODE = {0: "ok", 1: "format", 2: "servfail", 3: "nxdomain", 5: "refused"}


def query(server, name, source_ip=None, timeout=2.0, qtype=1):
    tid = int.from_bytes(os.urandom(2), "big")
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if source_ip:
            s.bind((source_ip, 0))
        s.settimeout(timeout)
        t0 = time.time()
        s.sendto(build_query(name, tid, qtype), (server, 53))
        data, _ = s.recvfrom(2048)
        ms = round((time.time() - t0) * 1000, 1)
        rcode, ips = parse_answer(data, tid)
        return {"server": server, "name": name, "ok": rcode == 0, "rcode": RCODE.get(rcode, str(rcode)), "ips": ips, "ms": ms}
    except (OSError, ValueError) as exc:
        return {"server": server, "name": name, "ok": False, "rcode": "error", "ips": [], "ms": None, "error": str(exc)}
    finally:
        s.close()


# ---------------------------------------------------------------------------
# analyse PURE (testable) : apprentissage, comparaison, constats
# ---------------------------------------------------------------------------
def learn(observations):
    """observations : [{source, resolver, name, ok, rcode, ips}]. -> base apprise :
    par nom -> {answers: {clé_ip: [sources]}, resolvers: {resolver: clé_ip}, fail: [sources]}."""
    kb = {}
    for o in observations:
        name = o["name"]
        e = kb.setdefault(name, {"answers": {}, "resolvers": {}, "fail": []})
        src = "%s→%s" % (o.get("source", "?"), o["resolver"])
        if o.get("ok") and o.get("ips"):
            key = ",".join(o["ips"])
            e["answers"].setdefault(key, []).append(src)
            e["resolvers"][src] = key
        else:
            e["fail"].append({"src": src, "rcode": o.get("rcode")})
    return kb


def distribution(observations):
    """Répartition par source (résolveurs utilisés, taux d'échec) et par destination (IP -> noms qui y pointent)."""
    by_source, by_dest = {}, {}
    for o in observations:
        s = by_source.setdefault(o.get("source", "?"), {"resolvers": set(), "queries": 0, "fail": 0})
        s["resolvers"].add(o["resolver"]); s["queries"] += 1
        if not o.get("ok"):
            s["fail"] += 1
        for ip in (o.get("ips") or []):
            by_dest.setdefault(ip, set()).add(o["name"])
    return ({k: {"resolvers": sorted(v["resolvers"]), "queries": v["queries"], "fail": v["fail"]} for k, v in by_source.items()},
            {ip: sorted(names) for ip, names in by_dest.items()})


def compare(observations, expected_dns=None, previous=None):
    """-> (alerts, learned, state) ; alerts = [{code, severity, message}]."""
    kb = learn(observations)
    alerts = []
    for name, e in sorted(kb.items()):
        answers, fails = e["answers"], e["fail"]
        if answers and len(answers) > 1:
            detail = " ; ".join("%s → %s" % (", ".join(srcs), key) for key, srcs in sorted(answers.items()))
            alerts.append({"code": "dns-divergent", "severity": "warning",
                           "message": "%s résout différemment selon la source : %s" % (name, detail)})
        if answers and fails:
            alerts.append({"code": "dns-partial-nxdomain", "severity": "warning",
                           "message": "%s résout sur certaines sources mais échoue sur d'autres (%s)" % (name, ", ".join("%s:%s" % (f["src"], f["rcode"]) for f in fails))})
        if not answers and fails:
            alerts.append({"code": "dns-all-down", "severity": "critical",
                           "message": "%s ne résout depuis aucune source (%s)" % (name, ", ".join(sorted({f["rcode"] for f in fails})))})
    if expected_dns:
        allowed = set(expected_dns)
        for o in observations:
            # un résolveur distribué (pas public) hors liste attendue
            if o["resolver"] not in allowed and o["resolver"] not in PUBLIC_DNS and o.get("kind") == "distributed":
                alerts.append({"code": "dns-unexpected-resolver", "severity": "warning",
                               "message": "%s utilise le résolveur %s, hors de la liste attendue" % (o.get("source", "?"), o["resolver"])})
                break
    # changement depuis le dernier passage (état : {name→resolver: clé_ip})
    state = {}
    for o in observations:
        if o.get("ok") and o.get("ips"):
            state["%s|%s" % (o["name"], o["resolver"])] = ",".join(o["ips"])
    if previous:
        changed = [(k, previous[k], state[k]) for k in state if k in previous and previous[k] != state[k]]
        for k, before, after in changed[:20]:
            nm, rv = k.split("|", 1)
            alerts.append({"code": "dns-answer-changed", "severity": "info",
                           "message": "%s via %s : réponse changée %s → %s" % (nm, rv, before, after)})
    # dédup par code+message
    seen, uniq = set(), []
    for a in alerts:
        key = (a["code"], a["message"])
        if key not in seen:
            seen.add(key); uniq.append(a)
    return uniq, kb, state


def gateway_findings(observations, gateways):
    """#642 : sur chaque segment, le résolveur légitime est la passerelle (firewall .1).
    gateways = {source(iface): ip_passerelle}. Signale un DNS distribué qui n'est pas la
    passerelle du segment (DHCP mal réglé / résolveur imposé)."""
    alerts = []
    by_src = {}
    for o in observations:
        if o.get("kind") == "distributed":
            by_src.setdefault(o.get("source", "?"), set()).add(o["resolver"])
    for src, resolvers in sorted(by_src.items()):
        gw = gateways.get(src)
        if gw and gw not in resolvers:
            alerts.append({"code": "dns-not-gateway", "severity": "warning",
                           "message": "%s : DNS distribué %s ≠ passerelle %s (le firewall du VLAN devrait être le résolveur)" % (src, ", ".join(sorted(resolvers)) or "aucun", gw)})
    return alerts


def summarize(observations, alerts):
    ok = sum(1 for o in observations if o.get("ok"))
    state = "critical" if any(a["severity"] == "critical" for a in alerts) else "warning" if any(a["severity"] == "warning" for a in alerts) else "ok"
    return {"state": state, "queries": len(observations), "resolved": ok, "alerts": len(alerts)}


# ---------------------------------------------------------------------------
# collecte (I/O) -- inventaire des sources façon path-probe
# ---------------------------------------------------------------------------
def _run(cmd, timeout=15):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, r.stdout, r.stderr
    except (OSError, subprocess.SubprocessError) as exc:
        return 127, "", str(exc)


def detect_ifaces():
    _rc, out, _e = _run(["ip", "-o", "-4", "addr", "show", "scope", "global"])
    seen, ifaces = set(), []
    for line in (out or "").splitlines():
        parts = line.split()
        if len(parts) >= 4 and parts[1] not in seen:
            seen.add(parts[1]); ifaces.append(parts[1])
    return ifaces


def iface_source(iface):
    """(ip source, [DNS distribués]) d'une interface, via nmcli puis resolv.conf."""
    _rc, out, _e = _run(["ip", "-o", "-4", "addr", "show", "dev", iface])
    m = re.search(r"inet (\d+\.\d+\.\d+\.\d+)", out or "")
    src = m.group(1) if m else None
    dns = []
    _rc, out, _e = _run(["nmcli", "-g", "IP4.DNS", "device", "show", iface])
    dns = [x for x in re.split(r"[\s|]+", out or "") if re.match(r"^\d+\.\d+\.\d+\.\d+$", x)]
    return src, dns


def iface_gateway(iface):
    """Passerelle par défaut d'une interface (ip route), ou None."""
    rc, out, _e = _run(["ip", "-o", "route", "show", "default", "dev", iface])
    m = re.search(r"default via (\d+\.\d+\.\d+\.\d+)", out or "")
    return m.group(1) if m else None


def collect(names, ifaces, public, expected, state_path, expect_gateway=False):
    if ifaces == ["auto"] or not ifaces:
        ifaces = detect_ifaces()
    observations = []
    for iface in ifaces:
        src_ip, dns = iface_source(iface)
        resolvers = [(d, "distributed") for d in dns] + [(p, "public") for p in (public or PUBLIC_DNS)]
        for name in names:
            for server, kind in resolvers:
                r = query(server, name, source_ip=src_ip)
                observations.append({"source": iface, "resolver": server, "kind": kind,
                                     "name": name, "ok": r["ok"], "rcode": r["rcode"], "ips": r["ips"], "ms": r["ms"]})
    previous = {}
    try:
        with open(state_path, encoding="utf-8") as fh:
            previous = json.load(fh).get("answers", {})
    except (OSError, ValueError):
        pass
    alerts, kb, new_state = compare(observations, expected_dns=expected, previous=previous)
    if expect_gateway:
        gateways = {iface: iface_gateway(iface) for iface in ifaces}
        alerts = alerts + gateway_findings(observations, gateways)
    try:
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as fh:
            json.dump({"answers": new_state, "at": time.time()}, fh)
    except OSError:
        pass
    by_source, by_dest = distribution(observations)
    return {"names": names, "ifaces": ifaces, "observations": observations, "learned": kb,
            "by_source": by_source, "by_destination": by_dest, "alerts": alerts, "summary": summarize(observations, alerts)}


def main(argv):
    names, ifaces, public, expected, state, expect_gw = [], ["auto"], None, None, STATE_DEFAULT, False
    i = 0
    while i < len(argv):
        a, v = argv[i], argv[i + 1] if i + 1 < len(argv) else None
        if a == "--names" and v is not None:
            names = [x.strip() for x in v.split(",") if x.strip()]; i += 2; continue
        if a == "--names-file" and v is not None:
            try:
                names += [l.strip() for l in open(v, encoding="utf-8") if l.strip() and not l.startswith("#")]
            except OSError:
                pass
            i += 2; continue
        if a == "--ifaces" and v is not None:
            ifaces = [x for x in v.split(",") if x]; i += 2; continue
        if a == "--public-dns" and v is not None:
            public = [x for x in v.split(",") if x]; i += 2; continue
        if a == "--expected-dns" and v is not None:
            expected = [x for x in v.split(",") if x]; i += 2; continue
        if a == "--state" and v is not None:
            state = v; i += 2; continue
        if a == "--expected-gateway":
            expect_gw = True; i += 1; continue
        i += 1
    if not names:
        names = ["www.gouv.fr", "detectportal.firefox.com"]
    try:
        print(json.dumps(collect(names, ifaces, public, expected, state, expect_gateway=expect_gw)))
    except Exception as exc:  # noqa: BLE001 -- une sonde ne plante jamais l'agent
        print(json.dumps({"error": "collecte échouée : %s" % exc, "alerts": []}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
