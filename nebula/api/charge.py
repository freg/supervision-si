# -*- coding: utf-8 -*-
"""Charge du réseau (livraison #851) -- logique PURE, testée (tests/test_charge.py).

Ce que l'OpenAPI Nebula permet (doc officielle) : pas de compteur direct par borne, SSID ou VLAN ; on agrège
- les clients des bornes (v2 ap-clients : borne, SSID, octets montants / descendants par client sur la période)
  -> par borne et par SSID : clients distincts, volume, débit moyen sur la fenêtre ;
- les clients du site (v2 clients : VLAN) et des commutateurs (v2 sw-clients : VLAN, port) -> par VLAN : clients
  distincts ; volume Wi-Fi du VLAN par la correspondance SSID -> VLAN de la carte ;
- l'usage de la liaison montante des commutateurs (traffic-usage) -> par commutateur ;
- les relevés d'occupation du hub (nombre de clients par borne toutes les N minutes, #747) -> clients simultanés
  moyens et maximum sur la fenêtre (Nebula ne donne que les clients distincts de la période)."""
import re

PERIODES = {"2h": 7200, "1d": 86400, "7d": 7 * 86400, "30d": 30 * 86400}


def _mac(s):
    h = re.sub(r"[^0-9a-f]", "", str(s or "").lower())
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)) if len(h) == 12 else str(s or "").lower()


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _g(c, *cles):
    for k in cles:
        if c.get(k) not in (None, ""):
            return c[k]
    return None


def mbps(octets, secondes):
    return round(octets * 8 / secondes / 1e6, 3) if secondes else 0.0


def agreger(periode, devices, ap_clients=None, clients=None, sw_clients=None, sw_usage=None, gw_usage=None,
            ssid_vlan=None, occupation=None):
    """devices : [{devId, name, type}] ; *_clients : listes de l'API ; sw_usage / gw_usage : {devId: réponse} ;
    ssid_vlan : {ssid: vlan} ; occupation : {devId: {moyenne, max, releves}} -> tableaux par borne, SSID, VLAN,
    commutateur, passerelle."""
    sec = PERIODES.get(periode, 86400)
    noms = {d.get("devId"): d.get("name") or d.get("devId") for d in devices or []}
    types = {d.get("devId"): str(d.get("type") or "").upper() for d in devices or []}
    par_ap, par_ssid = {}, {}
    for c in ap_clients or []:
        mac = _mac(_g(c, "mac_address", "macAddress", "mac"))
        ap = _g(c, "connected_device_id", "connectedDeviceId", "devId") or "?"
        ssid = _g(c, "ssid", "ssid_name", "ssidName") or "?"
        up, down = _num(_g(c, "upload", "tx", "uplink")), _num(_g(c, "download", "rx", "downlink"))
        for table, cle in ((par_ap, ap), (par_ssid, ssid)):
            e = table.setdefault(cle, {"macs": set(), "up": 0.0, "down": 0.0})
            e["macs"].add(mac); e["up"] += up; e["down"] += down
    occ = occupation or {}
    bornes = []
    for dev in sorted(set(par_ap) | {d for d, t in types.items() if t == "AP"}, key=lambda d: str(noms.get(d) or d)):
        e = par_ap.get(dev) or {"macs": set(), "up": 0.0, "down": 0.0}
        o = occ.get(dev) or {}
        bornes.append({"dev_id": dev, "nom": noms.get(dev) or dev, "clients": len(e["macs"]), "simultanes_moy": o.get("moyenne"), "simultanes_max": o.get("max"),
                       "releves": o.get("releves", 0), "montant_o": e["up"], "descendant_o": e["down"], "debit_mbps": mbps(e["up"] + e["down"], sec)})
    ssids = [{"ssid": k, "vlan": (ssid_vlan or {}).get(k), "clients": len(e["macs"]), "montant_o": e["up"], "descendant_o": e["down"],
              "debit_mbps": mbps(e["up"] + e["down"], sec)} for k, e in sorted(par_ssid.items())]
    par_vlan = {}
    for src, lst in (("site", clients), ("commutateurs", sw_clients)):
        for c in lst or []:
            v = _g(c, "vlan", "vlanId")
            if v in (None, ""):
                continue
            e = par_vlan.setdefault(int(_num(v)), {"macs": set(), "filaires": set(), "up": 0.0, "down": 0.0, "ssids": set()})
            m = _mac(_g(c, "mac_address", "macAddress", "mac"))
            e["macs"].add(m)
            if src == "commutateurs":
                e["filaires"].add(m)
    for s in ssids:
        if s["vlan"] is not None:
            e = par_vlan.setdefault(int(s["vlan"]), {"macs": set(), "filaires": set(), "up": 0.0, "down": 0.0, "ssids": set()})
            e["up"] += s["montant_o"]; e["down"] += s["descendant_o"]; e["ssids"].add(s["ssid"])
            e["macs"].update(par_ssid[s["ssid"]]["macs"])
    vlans = [{"vlan": k, "clients": len(e["macs"]), "filaires": len(e["filaires"]), "ssids": sorted(e["ssids"]),
              "wifi_montant_o": e["up"], "wifi_descendant_o": e["down"], "wifi_debit_mbps": mbps(e["up"] + e["down"], sec)} for k, e in sorted(par_vlan.items())]
    comm = []
    for dev, r in sorted((sw_usage or {}).items(), key=lambda kv: str(noms.get(kv[0]) or kv[0])):
        r = r if isinstance(r, dict) else {}
        tx, rx = _num(_g(r, "uplinkTxUsage", "uplink_tx_usage")), _num(_g(r, "uplinkRxUage", "uplinkRxUsage", "uplink_rx_usage"))
        comm.append({"dev_id": dev, "nom": noms.get(dev) or dev, "montant_o": tx, "descendant_o": rx, "debit_mbps": mbps(tx + rx, sec), "erreur": r.get("erreur")})
    pass_ = []
    for dev, r in (gw_usage or {}).items():
        r = r if isinstance(r, dict) else {}
        pass_.append({"dev_id": dev, "nom": noms.get(dev) or dev, "brut": {k: v for k, v in r.items() if k != "erreur"} or None, "erreur": r.get("erreur")})
    tot = sum(b["montant_o"] + b["descendant_o"] for b in bornes)
    return {"periode": periode, "secondes": sec, "bornes": bornes, "ssids": ssids, "vlans": vlans, "commutateurs": comm, "passerelles": pass_,
            "total": {"clients_wifi": len({m for e in par_ap.values() for m in e["macs"]}), "wifi_octets": tot, "wifi_debit_mbps": mbps(tot, sec)}}


def occupation(lignes, debut):
    """Relevés d'occupation [(dev_id, at, clients)] -> {dev_id: {moyenne, max, releves}} depuis `debut`."""
    out = {}
    for dev, at, n in lignes or []:
        if at < debut:
            continue
        e = out.setdefault(dev, {"somme": 0, "max": 0, "releves": 0})
        e["somme"] += n or 0; e["max"] = max(e["max"], n or 0); e["releves"] += 1
    return {d: {"moyenne": round(e["somme"] / e["releves"], 1), "max": e["max"], "releves": e["releves"]} for d, e in out.items() if e["releves"]}
