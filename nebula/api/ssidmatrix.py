# -*- coding: utf-8 -*-
"""Matrice SSID x VLAN d'un site Nebula : prévue / observée / prouvée
(livraison #686) -- logique PURE, testée (nebula/tests/test_ssidmatrix.py).

- **prévue** : la carte des VLAN (#548) -- SSID → VLAN, sous-réseau de la
  passerelle (ou déduit), zone invité, anomalies de transport du VLAN
  (absent des ports ou d'une liaison) ;
- **observée** : clients sans fil rattachés à un SSID (API, ou dernier export
  CSV du portail), et le sous-réseau de leur adresse : un client dans le
  sous-réseau prévu prouve DHCP + étiquetage sans rien injecter ;
- **prouvée** : résultat du test actif `nebula/tools/ssid-vlan-check.sh`
  (`SSIDCHECK_CSV=…`) importé dans le hub -- utile seulement là où
  l'observation manque ou contredit le plan.

Chaque SSID reçoit un verdict et des écarts en phrases (règle en cause)."""
import ipaddress
import re

SSID_KEYS = ("ssid", "ssidName", "ssid_name", "essid", "ssidname")
IP_KEYS = ("ipv4Address", "ipv4", "ipv4_address", "ip", "ipAddress")


def _first(d, keys):
    for k in keys:
        v = d.get(k)
        if v not in (None, "", "-"):
            return str(v).strip()
    return None


def _net(subnet):
    if not subnet:
        return None
    try:
        return ipaddress.ip_network(str(subnet), strict=False)
    except ValueError:
        return None


def _ip(v):
    try:
        return ipaddress.ip_address(str(v).split("/")[0].strip())
    except ValueError:
        return None


def _prefix24(ip):
    return str(ipaddress.ip_network("%s/24" % ip, strict=False))


def parse_check_csv(text):
    """Sortie `SSIDCHECK_CSV` de ssid-vlan-check.sh :
    `#ssid-vlan-check;<date>` puis `ssid;vlan;adresse;association;cible=OK|KO,...`.
    -> {"at", "rows": {ssid: {vlan, address, association, error, targets}}}."""
    out = {"at": None, "rows": {}}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#ssid-vlan-check"):
            parts = line.split(";", 1)
            out["at"] = parts[1].strip() if len(parts) > 1 else None
            continue
        if line.startswith("#"):
            continue
        parts = line.split(";")
        if len(parts) < 4 or not parts[0]:
            continue
        ssid, vlan, addr, assoc = parts[0], parts[1], parts[2], parts[3]
        targets = {}
        for t in (parts[4] if len(parts) > 4 else "").split(","):
            k, _, v = t.partition("=")
            if k.strip():
                targets[k.strip()] = v.strip().upper() == "OK"
        ok = assoc.upper().startswith("OK")
        out["rows"][ssid] = {"vlan": int(vlan) if vlan.strip().isdigit() else None,
                             "address": addr.strip() if addr.strip() not in ("", "-", "pas de bail") else None,
                             "association": ok, "error": None if ok else (assoc.partition(":")[2].strip() or assoc),
                             "targets": targets}
    return out


def observed_by_ssid(clients):
    """clients (API ou CSV) -> {ssid: {"clients": n, "subnets": {/24: n}, "ips": [ip...]}}."""
    out = {}
    for c in clients or []:
        if not isinstance(c, dict):
            continue
        ssid = _first(c, SSID_KEYS)
        if not ssid:
            continue
        o = out.setdefault(ssid, {"clients": 0, "subnets": {}, "ips": []})
        o["clients"] += 1
        ip = _ip(_first(c, IP_KEYS) or "")
        if ip is not None and ip.version == 4 and not ip.is_link_local:
            o["ips"].append(str(ip))
            p = _prefix24(ip)
            o["subnets"][p] = o["subnets"].get(p, 0) + 1
    return out


def build_matrix(vmap, clients=None, proof=None):
    """vmap : carte des VLAN (#548) ; clients : liste API/CSV ; proof : parse_check_csv().
    -> {"ssids": [...], "summary": {...}, "vlans_without_ssid": [...]}."""
    vmap = vmap or {}
    proof = proof or {"rows": {}}
    observed = observed_by_ssid(clients)
    anomalies = vmap.get("anomalies_detail") or []
    rows, seen = [], set()
    for v in vmap.get("vlans") or []:
        for s in v.get("ssids") or []:
            name = s.get("name")
            if not name or name in seen:
                continue
            seen.add(name)
            rows.append(_row(name, s, v, observed.get(name), proof["rows"].get(name), anomalies))
    # SSID observés ou testés mais absents du plan (VLAN inconnu, SSID non publié par l'API)
    for name in sorted(set(observed) | set(proof["rows"])):
        if name not in seen:
            seen.add(name)
            rows.append(_row(name, None, None, observed.get(name), proof["rows"].get(name), anomalies))
    summary = {}
    for r in rows:
        summary[r["verdict"]] = summary.get(r["verdict"], 0) + 1
    return {"ssids": rows, "summary": summary, "proof_at": proof.get("at"),
            "vlans_without_ssid": [v["vid"] for v in vmap.get("vlans") or [] if not v.get("ssids") and v.get("vid") != 1]}


def _row(name, ssid, vlan, obs, pr, anomalies):
    vid = vlan.get("vid") if vlan else None
    subnet = vlan.get("subnet") if vlan else None
    net = _net(subnet)
    r = {"ssid": name, "enabled": (ssid or {}).get("enabled", True), "guest": bool((ssid or {}).get("guest") or (vlan or {}).get("guest")),
         "planned": {"vlan": vid, "subnet": subnet, "subnet_inferred": bool((vlan or {}).get("subnet_inferred")),
                     "gateway_interface": (vlan or {}).get("gateway_interface")},
         "observed": None, "proven": None, "gaps": [], "notes": [], "verdict": None}
    if vid is None:
        r["gaps"].append("SSID absent du plan : aucun VLAN connu pour lui dans Nebula (SSID non publié par l'API ou réglage local).")
    for a in anomalies:
        d = a.get("details") or {}
        if vid is not None and (d.get("vlan") == vid or vid in (d.get("vlans") or [])):
            r["gaps"].append("Transport du VLAN %d : %s" % (vid, a.get("message")))
    if obs:
        in_plan = sum(1 for ip in obs["ips"] if net is not None and _ip(ip) in net)
        off = sorted(p for p in obs["subnets"] if net is None or not _net(p).overlaps(net))
        r["observed"] = {"clients": obs["clients"], "with_ip": len(obs["ips"]), "in_plan": in_plan, "subnets": obs["subnets"], "off_plan_subnets": off}
        if net is not None and off:
            r["gaps"].append("Clients observés hors du sous-réseau prévu %s : %s (DHCP d'un autre VLAN, étiquetage du SSID ou de la liaison de la borne)."
                             % (subnet, ", ".join("%s ×%d" % (p, obs["subnets"][p]) for p in off)))
        if net is None and obs["subnets"]:
            r["gaps"].append("Sous-réseau prévu inconnu : les clients sont en %s." % ", ".join(sorted(obs["subnets"])))
    if pr:
        addr = _ip(pr["address"] or "")
        r["proven"] = dict(pr, in_plan=bool(addr is not None and net is not None and addr in net))
        if not pr["association"]:
            r["gaps"].append("Test actif : association refusée (%s)." % (pr["error"] or "?"))
        elif pr["address"] is None:
            r["gaps"].append("Test actif : associé mais aucun bail DHCP (VLAN non porté jusqu'au serveur DHCP, ou étendue épuisée).")
        elif net is not None and addr is not None and addr not in net:
            r["gaps"].append("Test actif : adresse %s hors du sous-réseau prévu %s." % (pr["address"], subnet))
        ko = sorted(t for t, ok in (pr.get("targets") or {}).items() if not ok)
        if ko and r["guest"]:
            r["notes"].append("Test actif : %s injoignables depuis ce SSID invité (isolation attendue)." % ", ".join(ko))
        elif ko:
            r["gaps"].append("Test actif : cibles injoignables depuis ce SSID : %s (règle de pare-feu / isolation à confirmer si voulu)." % ", ".join(ko))
    observed_ok = bool(r["observed"] and r["observed"]["in_plan"] > 0 and not r["observed"]["off_plan_subnets"])
    proven_ok = bool(r["proven"] and r["proven"]["association"] and r["proven"]["in_plan"])
    if r["gaps"]:
        r["verdict"] = "écart"
    elif proven_ok:
        r["verdict"] = "prouvé"
    elif observed_ok:
        r["verdict"] = "observé"
    elif not r["enabled"]:
        r["verdict"] = "désactivé"
    else:
        r["verdict"] = "à prouver"
    return r

