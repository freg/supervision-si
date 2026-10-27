#!/usr/bin/env python3
"""Plugin si-agent « lan-audit » (#873) : inventaire actif des réseaux du site -- hôtes, services, versions, système.

Pour l'état des lieux (décideurs) et le suivi de migration : qui est sur le réseau, ce qui y tourne, en quelle version,
et ce qui n'est plus maintenu. Deux passes nmap (sortie XML, analysée ici) :
  1. découverte des hôtes vivants (ARP sur le segment local, ICMP et quelques ports ailleurs) ;
  2. sur les seuls hôtes vivants : ports usuels, identification des services (--version-light) et du système (-O).
Rien n'est modifié sur les cibles, aucune connexion authentifiée. Mais c'est du trafic ACTIF : désactivé par défaut,
lancé à la demande (« Exécuter… ») ou programmé hors heures ouvrées ; débit plafonné ; liste d'exclusion pour les
équipements fragiles (automates, vieilles imprimantes, téléphonie). Privilégié : -O et ARP exigent root.

Arguments : --targets 192.0.2.0/24,198.51.100.0/24 (obligatoire) [--exclude 192.0.2.10,192.0.2.20-30]
            [--top-ports 300] [--max-rate 200] [--host-timeout 300] [--no-os] [--no-versions]
Sortie : {"hosts": [{ip, mac, vendor, hostname, os: {name, accuracy, family, gen, vendor}, ports: [{port, proto, service,
         product, version, extrainfo, cpe}]}], "stats", "targets", "alerts"} ; constats : nmap absent, cibles absentes.
"""
import argparse
import json
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def parse_xml(text):
    """XML nmap (-oX -) -> [hôte] ; seuls les hôtes « up »."""
    hosts = []
    try:
        root = ET.fromstring(text or "<nmaprun/>")
    except ET.ParseError:
        return hosts
    for h in root.findall("host"):
        st = h.find("status")
        if st is not None and st.get("state") != "up":
            continue
        x = {"ip": None, "mac": None, "vendor": None, "hostname": None, "os": None, "ports": []}
        for a in h.findall("address"):
            if a.get("addrtype") == "ipv4":
                x["ip"] = a.get("addr")
            elif a.get("addrtype") == "mac":
                x["mac"], x["vendor"] = (a.get("addr") or "").lower(), a.get("vendor")
        hn = h.find("hostnames/hostname")
        if hn is not None:
            x["hostname"] = hn.get("name")
        best = None
        for m in h.findall("os/osmatch"):
            acc = int(m.get("accuracy") or 0)
            if best is None or acc > best["accuracy"]:
                c = m.find("osclass")
                best = {"name": m.get("name"), "accuracy": acc, "family": c.get("osfamily") if c is not None else None,
                        "gen": c.get("osgen") if c is not None else None, "vendor": c.get("vendor") if c is not None else None}
        x["os"] = best
        for p in h.findall("ports/port"):
            s = p.find("state")
            if s is None or s.get("state") != "open":
                continue
            sv = p.find("service")
            g = (lambda k: sv.get(k) if sv is not None else None)
            x["ports"].append({"port": int(p.get("portid")), "proto": p.get("protocol"), "service": g("name"), "product": g("product"),
                               "version": g("version"), "extrainfo": g("extrainfo"), "ostype": g("ostype"),
                               "cpe": [c.text for c in (sv.findall("cpe") if sv is not None else []) if c.text]})
        if x["ip"]:
            hosts.append(x)
    return hosts


def run(cmd, timeout, runner=subprocess.run):
    p = runner(cmd, capture_output=True, text=True, timeout=timeout)
    return p.stdout, (p.stderr or "").strip()[-400:]


def main(argv=None, runner=subprocess.run, which=shutil.which):
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", default="")
    ap.add_argument("--exclude", default="")
    ap.add_argument("--top-ports", type=int, default=300)
    ap.add_argument("--max-rate", type=int, default=200)
    ap.add_argument("--host-timeout", type=int, default=300)
    ap.add_argument("--no-os", action="store_true")
    ap.add_argument("--no-versions", action="store_true")
    a = ap.parse_args(argv)
    targets = [t.strip() for t in a.targets.replace(" ", ",").split(",") if t.strip()]
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "targets": targets, "exclude": a.exclude or None,
           "hosts": [], "stats": {}, "alerts": []}
    exe = which("nmap")
    if not exe:
        out["alerts"].append({"code": "lan-audit-nmap", "severity": "warning",
                              "message": "nmap absent sur l'hôte de l'agent (Debian : apt install nmap)"})
        return out
    if not targets:
        out["alerts"].append({"code": "lan-audit-cibles", "severity": "warning",
                              "message": "aucune cible : régler --targets (ex. 192.0.2.0/24,198.51.100.0/24) dans les arguments de la sonde"})
        return out
    excl = ["--exclude", a.exclude] if a.exclude else []
    t0 = time.time()
    # 1. découverte (ARP sur le segment local, ailleurs ICMP écho + SYN/ACK sur quelques ports usuels)
    xml1, err1 = run([exe, "-n", "-sn", "-PE", "-PS22,80,443,445,3389,8006", "-PA80", "--max-rate", str(a.max_rate), "-oX", "-"] + excl + targets,
                     timeout=900, runner=runner)
    vivants = [h for h in parse_xml(xml1)]
    out["stats"]["decouverte_s"] = round(time.time() - t0)
    if not vivants:
        out["stats"].update(vivants=0)
        out["alerts"].append({"code": "lan-audit-vide", "severity": "warning", "message": "aucun hôte découvert (%s)" % (err1 or "réseau injoignable ?")})
        return out
    # 2. services, versions et système sur les seuls hôtes vivants (résolution des noms activée pour l'inventaire)
    t1 = time.time()
    cmd = [exe, "-sS", "--top-ports", str(a.top_ports), "--max-rate", str(a.max_rate), "--host-timeout", "%ds" % a.host_timeout,
           "-T3", "--max-retries", "2", "-oX", "-"]
    if not a.no_versions:
        cmd += ["-sV", "--version-light"]
    if not a.no_os:
        cmd += ["-O", "--osscan-limit"]
    xml2, err2 = run(cmd + [h["ip"] for h in vivants], timeout=7200, runner=runner)
    detail = {h["ip"]: h for h in parse_xml(xml2)}
    for h in vivants:
        d = detail.get(h["ip"]) or {}
        out["hosts"].append({"ip": h["ip"], "mac": d.get("mac") or h["mac"], "vendor": d.get("vendor") or h["vendor"],
                             "hostname": d.get("hostname") or h["hostname"], "os": d.get("os"), "ports": d.get("ports") or []})
    out["hosts"].sort(key=lambda x: tuple(int(p) for p in x["ip"].split(".")))
    out["stats"].update(vivants=len(vivants), detailles=len(detail), services=sum(len(h["ports"]) for h in out["hosts"]),
                        services_s=round(time.time() - t1), erreur=err2 or None)
    return out


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1:]), ensure_ascii=False))
