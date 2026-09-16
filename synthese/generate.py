#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Infos synthèse SI (livraison #523) -- génère synthese/generated/synthese.json
à partir des exports DNS / IP OVH / IPAM / services déposés dans synthese/data/
(HORS dépôt : ce sont des données réelles ; synthese/data.example/ porte un jeu
fictif pour les tests et la documentation).

Demandé : « présenter ça dans une page “infos synthèse SI” de la tuile
documentation, la rendre interactive pour accéder aux équipements, outils et
autres ; maintien automatique ; liens vers ipam, la gestion des IP OVH, les
zones DNS, Online ».

Entrées reconnues (fichiers .xlsx -- une feuille = une source -- ou .csv/.txt),
détectées par leur CONTENU, jamais par le nom de la feuille :
  - dump de zone BIND (`$ORIGIN <zone>.` puis enregistrements `nom ttl IN TYPE valeur`)
  - liste des blocs d'IP OVH (en-tête « Bloc d'IP / Correspondances DNS / Version / Type / Pays / Service »)
  - liste des services OVH (en-tête « Service / Type / Statut / Renouvellement / Date d'effet »)
  - export IPAM d'un sous-réseau (titre, CIDR, « vlan: … », en-tête « ip address / hostname / … »)
  - liste d'équipements IPAM (nom, IP, …, type, constructeur, modèle)

Sortie : zones, ovh_ips, ovh_services, ipam (subnets, devices), et un INDEX
par adresse IP qui recoupe DNS ↔ OVH ↔ IPAM (« à qui sert cette IP ? »).
Logique pure testée (tests/test_generate.py) ; `python3 synthese/generate.py
[--data DIR] [--out FICHIER]`."""
import csv
import glob
import ipaddress
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "data")
OUT_PATH = os.path.join(HERE, "generated", "synthese.json")
DNS_TYPES = {"A", "AAAA", "CNAME", "MX", "TXT", "NS", "SOA", "SRV", "PTR", "CAA", "DKIM", "SPF"}


def _s(v):
    return ("" if v is None else str(v)).strip()


def _norm(v):
    return re.sub(r"[^a-z0-9]+", "", _s(v).lower())


# ---------------------------------------------------------------- détection
def detect(rows):
    """Type de source d'une grille de lignes : zone | ovh_ips | ovh_services | ipam_subnet | ipam_devices | None."""
    for row in rows[:8]:
        cells = [_s(c) for c in row]
        if any(c.startswith("$ORIGIN") for c in cells):
            return "zone"
        norm = [_norm(c) for c in cells]
        if any(n.startswith("blocdip") or n.startswith("bloquedip") for n in norm) and "type" in norm:
            return "ovh_ips"
        if "service" in norm and "type" in norm and "statut" in norm and any(n.startswith("renouvellement") for n in norm):
            return "ovh_services"
        if "ipaddress" in norm and "hostname" in norm:
            return "ipam_subnet"
    for row in rows[:3]:
        cells = [_s(c) for c in row]
        if len(cells) >= 6 and _is_ip(cells[1]) and re.search(r"\d+ objects?", " ".join(cells).lower()):
            return "ipam_devices"
    return None


def _is_ip(v):
    try:
        ipaddress.ip_address(_s(v))
        return True
    except ValueError:
        return False


# ---------------------------------------------------------------- parseurs
def parse_zone(rows):
    zone, records, note = None, [], None
    for row in rows:
        cells = [_s(c) for c in row]
        if not any(cells):
            continue
        if cells[0].startswith(";;"):
            note = " ".join(c for c in cells if c)
            continue
        if cells[0] == "$ORIGIN":
            zone = (cells[1] if len(cells) > 1 else "").rstrip(".")
            continue
        if cells[0].startswith("$"):
            continue
        try:
            i = cells.index("IN")
        except ValueError:
            continue
        name = cells[0]
        ttl = cells[1] if i >= 1 and cells[1].isdigit() else None
        rest = [c for c in cells[i + 1:] if c]
        if not rest:
            continue
        rtype = rest[0].upper()
        if rtype not in DNS_TYPES:
            continue
        values = rest[1:]
        if rtype == "SOA":
            value, comment = " ".join(values), ""
        elif rtype == "MX":
            value, comment = " ".join(values[:2]), " ".join(values[2:])
        elif rtype in ("TXT", "SPF", "DKIM"):
            value, comment = " ".join(values), ""
        else:
            value, comment = (values[0] if values else ""), " ".join(values[1:])
        fqdn = zone if name in ("@", "") else ("%s.%s" % (name, zone) if zone and not name.endswith(".") else name.rstrip("."))
        records.append({"name": name, "fqdn": fqdn, "ttl": int(ttl) if ttl else None, "type": rtype, "value": value, "comment": comment or None})
    return {"zone": zone, "note": note, "records": records, "provider": zone_provider(records, note)}


def zone_provider(records, note=None):
    """Hébergeur DNS déduit du SOA / des NS : ovh | online | autre | None."""
    text = " ".join([r["value"] for r in records if r["type"] in ("SOA", "NS")] + [note or ""]).lower()
    if "online.net" in text or "scaleway" in text:
        return "online"
    if "ovh" in text:
        return "ovh"
    return "autre" if text.strip() else None


def _header_index(rows, needles):
    """(indice de la ligne d'en-tête, {clé normalisée: colonne}) pour la première ligne contenant les needles."""
    for i, row in enumerate(rows[:12]):
        norm = [_norm(c) for c in row]
        if all(any(n.startswith(k) for n in norm) for k in needles):
            return i, {n: j for j, n in enumerate(norm) if n}
    return None, {}


def _col(cols, *prefixes):
    for p in prefixes:
        for k, j in cols.items():
            if k.startswith(p):
                return j
    return None


def parse_ovh_ips(rows):
    hi, cols = _header_index(rows, ["bloc", "type"])
    if hi is None:
        hi, cols = _header_index(rows, ["bloque", "type"])
    out = []
    if hi is None:
        return out
    c_block, c_dns, c_ver, c_type, c_country, c_svc, c_desc = (_col(cols, "blocdip", "bloquedip", "bloc"), _col(cols, "correspondances"), _col(cols, "version"),
                                                              _col(cols, "type"), _col(cols, "pays"), _col(cols, "service"), _col(cols, "description"))
    for row in rows[hi + 1:]:
        cells = [_s(c) for c in row]
        if not any(cells) or c_block is None or c_block >= len(cells):
            continue
        block = cells[c_block]
        if not block:
            continue
        ip = block.split("/")[0]
        out.append({"block": block, "ip": ip if _is_ip(ip) else None, "dns_count": _int(cells, c_dns), "version": _get(cells, c_ver),
                    "type": _get(cells, c_type), "country": _get(cells, c_country), "service": _get(cells, c_svc), "description": _get(cells, c_desc)})
    return out


def parse_ovh_services(rows):
    hi, cols = _header_index(rows, ["service", "type", "statut"])
    out = []
    if hi is None:
        return out
    c = {k: _col(cols, p) for k, p in (("service", "service"), ("type", "type"), ("status", "statut"), ("renewal", "renouvellement"),
                                        ("pending", "actionsencours"), ("effective", "datedeffet"), ("ip", "ipextraite"), ("dns_count", "nbdns"))}
    for row in rows[hi + 1:]:
        cells = [_s(x) for x in row]
        if not any(cells) or not _get(cells, c["service"]):
            continue
        out.append({"service": _get(cells, c["service"]), "type": _get(cells, c["type"]), "status": _get(cells, c["status"]),
                    "renewal": _get(cells, c["renewal"]), "pending": _get(cells, c["pending"]), "effective": _get(cells, c["effective"]),
                    "effective_iso": _iso_date(_get(cells, c["effective"])), "ip": _get(cells, c["ip"]) or None, "dns_count": _int(cells, c["dns_count"])})
    return out


def parse_ipam_subnet(rows):
    hi, cols = _header_index(rows, ["ipaddress", "hostname"])
    title, cidr, vlan = None, None, None
    for row in rows[:hi if hi is not None else 0]:
        for c in row:
            v = _s(c)
            if not v:
                continue
            if re.match(r"^\d+\.\d+\.\d+\.\d+/\d+$", v):
                cidr = v
            elif v.lower().startswith("vlan"):
                vlan = v.split(":", 1)[-1].strip()
            elif title is None:
                title = v
    hosts = []
    if hi is not None:
        c = {k: _col(cols, p) for k, p in (("ip", "ipaddress"), ("state", "ipstate"), ("description", "description"), ("hostname", "hostname"),
                                            ("fw", "fwobject"), ("mac", "mac"), ("owner", "owner"), ("device", "device"), ("port", "port"),
                                            ("note", "note"), ("location", "location"), ("reverse", "reverse"))}
        for row in rows[hi + 1:]:
            cells = [_s(x) for x in row]
            ip = _get(cells, c["ip"])
            if not _is_ip(ip):
                continue
            hosts.append({k: (_get(cells, j) or None) for k, j in c.items() if k != "ip"} | {"ip": ip})
    return {"title": title, "cidr": cidr, "vlan": vlan, "hosts": hosts}


def parse_ipam_devices(rows):
    out = []
    for row in rows:
        cells = [_s(c) for c in row]
        if len(cells) < 2 or not cells[0] or not _is_ip(cells[1]):
            continue
        rest = [c for c in cells[2:] if c and not re.search(r"\d+ objects?", c.lower())]
        out.append({"name": cells[0], "ip": cells[1], "type": rest[0] if rest else None, "vendor": rest[1] if len(rest) > 1 else None,
                    "model": rest[2] if len(rest) > 2 else None, "extra": rest[3:] or None})
    return out


def _get(cells, j):
    return cells[j] if j is not None and j < len(cells) else ""


def _int(cells, j):
    v = _get(cells, j)
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _iso_date(v):
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})", _s(v))
    if m:
        return "%s-%s-%s" % (m.group(3), m.group(2), m.group(1))
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", _s(v))
    return m.group(0) if m else None


# ---------------------------------------------------------------- lecture des fichiers
def read_sources(data_dir):
    """[(nom de source, lignes)] depuis les .xlsx (une entrée par feuille), .csv et .txt."""
    out = []
    for path in sorted(glob.glob(os.path.join(data_dir, "**", "*"), recursive=True)):
        if os.path.isdir(path):
            continue
        rel = os.path.relpath(path, data_dir)
        low = path.lower()
        if low.endswith(".xlsx"):
            try:
                import openpyxl
            except ImportError:
                print("openpyxl absent : %s ignoré (pip install openpyxl)" % rel, file=sys.stderr)
                continue
            wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
            for ws in wb.worksheets:
                rows = [list(r) for r in ws.iter_rows(values_only=True)]
                out.append(("%s:%s" % (rel, ws.title), rows))
        elif low.endswith(".csv"):
            with open(path, encoding="utf-8-sig", newline="") as fh:
                sample = fh.read(4096)
                fh.seek(0)
                try:
                    dialect = csv.Sniffer().sniff(sample, delimiters=";,\t")
                except csv.Error:
                    dialect = csv.excel
                out.append((rel, [row for row in csv.reader(fh, dialect)]))
        elif low.endswith((".txt", ".zone", ".db")):
            with open(path, encoding="utf-8", errors="replace") as fh:
                out.append((rel, [re.split(r"\s+", line.rstrip("\n")) for line in fh if line.strip()]))
    return out


# ---------------------------------------------------------------- assemblage
DEFAULT_LINKS = {
    "ipam_url": "", "ipam_search": "{ipam_url}index.php?page=tools&section=search&ip={query}",
    "ovh_ip": "https://www.ovh.com/manager/#/dedicated/ip?ip={ip}", "ovh_zone": "https://www.ovh.com/manager/#/web/domain/{zone}/zone",
    "ovh_services": "https://www.ovh.com/manager/#/hub/services", "ovh_domain": "https://www.ovh.com/manager/#/web/domain/{zone}/information",
    "online_console": "https://console.online.net/fr/server/list", "online_zone": "https://console.online.net/fr/domain/{zone}/dns",
}


def load_links(data_dir):
    """Liens : défauts (consoles OVH / Online) + synthese/data/links.json (URL IPAM réelle, hors dépôt)."""
    links = dict(DEFAULT_LINKS)
    p = os.path.join(data_dir, "links.json")
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as fh:
                links.update({k: v for k, v in json.load(fh).items() if isinstance(v, str)})
        except (OSError, ValueError) as exc:
            print("links.json illisible : %s" % exc, file=sys.stderr)
    if links.get("ipam_url") and not links["ipam_url"].endswith("/"):
        links["ipam_url"] += "/"
    return links


def build(sources, now=None, links=None):
    doc = {"generated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now or time.time())), "links": links or dict(DEFAULT_LINKS), "sources": [],
           "zones": [], "ovh_ips": [], "ovh_services": [], "ipam": {"subnets": [], "devices": []}, "index": {}, "unrecognized": []}
    for name, rows in sources:
        kind = detect(rows)
        entry = {"source": name, "kind": kind, "rows": len(rows)}
        if kind == "zone":
            z = parse_zone(rows)
            entry["zone"] = z["zone"]
            entry["count"] = len(z["records"])
            doc["zones"].append(z)
        elif kind == "ovh_ips":
            items = parse_ovh_ips(rows)
            entry["count"] = len(items)
            doc["ovh_ips"].extend(items)
        elif kind == "ovh_services":
            items = parse_ovh_services(rows)
            entry["count"] = len(items)
            doc["ovh_services"].extend(items)
        elif kind == "ipam_subnet":
            sn = parse_ipam_subnet(rows)
            entry["count"] = len(sn["hosts"])
            entry["subnet"] = sn["cidr"]
            doc["ipam"]["subnets"].append(sn)
        elif kind == "ipam_devices":
            items = parse_ipam_devices(rows)
            entry["count"] = len(items)
            doc["ipam"]["devices"].extend(items)
        else:
            doc["unrecognized"].append(name)
        doc["sources"].append(entry)
    doc["index"] = cross_index(doc)
    doc["summary"] = {"zones": len(doc["zones"]), "records": sum(len(z["records"]) for z in doc["zones"]),
                      "ovh_ips": len(doc["ovh_ips"]), "ovh_services": len(doc["ovh_services"]),
                      "ipam_subnets": len(doc["ipam"]["subnets"]), "ipam_hosts": sum(len(s["hosts"]) for s in doc["ipam"]["subnets"]),
                      "ipam_devices": len(doc["ipam"]["devices"]), "indexed_ips": len(doc["index"])}
    return doc


def cross_index(doc):
    """ip -> {dns: [fqdn…], ovh: {...}, ipam: [{subnet, hostname, description}], devices: [name]}."""
    idx = {}

    def slot(ip):
        return idx.setdefault(ip, {"dns": [], "ovh": None, "services": [], "ipam": [], "devices": []})

    for z in doc["zones"]:
        for r in z["records"]:
            if r["type"] in ("A", "AAAA") and _is_ip(r["value"]):
                s = slot(r["value"])
                if r["fqdn"] not in s["dns"]:
                    s["dns"].append(r["fqdn"])
    for o in doc["ovh_ips"]:
        if o.get("ip"):
            slot(o["ip"])["ovh"] = {"block": o["block"], "type": o["type"], "service": o["service"], "country": o["country"]}
    for sv in doc["ovh_services"]:
        if sv.get("ip") and _is_ip(sv["ip"]):
            slot(sv["ip"])["services"].append({"service": sv["service"], "type": sv["type"], "effective": sv.get("effective_iso") or sv.get("effective")})
    for sn in doc["ipam"]["subnets"]:
        for h in sn["hosts"]:
            slot(h["ip"])["ipam"].append({"subnet": sn["cidr"], "title": sn["title"], "hostname": h.get("hostname"), "description": h.get("description"), "device": h.get("device")})
    for d in doc["ipam"]["devices"]:
        slot(d["ip"])["devices"].append(d["name"])
    return dict(sorted(idx.items(), key=lambda kv: _ip_key(kv[0])))


def _ip_key(ip):
    try:
        a = ipaddress.ip_address(ip)
        return (a.version, int(a))
    except ValueError:
        return (9, 0)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    data = argv[argv.index("--data") + 1] if "--data" in argv else DATA_DIR
    out = argv[argv.index("--out") + 1] if "--out" in argv else OUT_PATH
    if not os.path.isdir(data):
        print("dossier de données absent : %s (déposer les exports DNS / OVH / IPAM, voir synthese/README.md)" % data, file=sys.stderr)
        return 2
    doc = build(read_sources(data), links=load_links(data))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    s = doc["summary"]
    print("%s : %d zone(s)/%d enregistrements, %d IP OVH, %d services OVH, %d sous-réseau(x) IPAM/%d hôtes, %d équipements, %d IP indexées%s" % (
        out, s["zones"], s["records"], s["ovh_ips"], s["ovh_services"], s["ipam_subnets"], s["ipam_hosts"], s["ipam_devices"], s["indexed_ips"],
        (" ; non reconnu : " + ", ".join(doc["unrecognized"])) if doc["unrecognized"] else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
