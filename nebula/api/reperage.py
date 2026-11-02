# -*- coding: utf-8 -*-
"""Repérage physique sur site (livraison #949) -- logique PURE, testée (nebula/tests/test_reperage.py).

But : accompagner l'intervention sur place avec le téléphone, dans l'ordre d'importance demandé :
 1. prise terminale → équipement branché (nom, IP, MAC) → port de commutateur (Nebula : sw-clients.connectedPort) ;
 2. brassage : prises ↔ panneau / port, corrigées sur place (table `reperage_prises`) ;
 3. position de l'équipement dans la pièce sur le plan du site (fractions 0..1), photo (long cordon, Wi-Fi) ;
 4. couverture Wi-Fi relative : relevés géolocalisés sur le plan du signal du mobile tel que VU PAR LA BORNE
    (Nebula ap-clients : wifiStation.signal, bande, canal) -- Nebula rafraîchit ces valeurs avec un retard de l'ordre
    de la minute ; un RSSI lu sur le téléphone (appli d'analyse Wi-Fi) peut être saisi en complément.

Ce module ne parle pas à Nebula : il normalise ce que les routes lui donnent (clients de commutateurs, clients de bornes,
clients du site, inventaire des appareils) et construit la vue « inventaire » et la recherche."""
import re
import time

MAC_RE = re.compile(r"^([0-9a-f]{2}:){5}[0-9a-f]{2}$")


def norm_mac(m):
    """« AA-BB-CC-DD-EE-FF », « aabb.ccdd.eeff », « aabbccddeeff » → « aa:bb:cc:dd:ee:ff » (None si impossible)."""
    if not m:
        return None
    h = re.sub(r"[^0-9a-fA-F]", "", str(m)).lower()
    if len(h) != 12:
        return None
    return ":".join(h[i:i + 2] for i in range(0, 12, 2))


def _nom_appareil(dev_id, devices):
    for d in devices or []:
        if d.get("devId") == dev_id or d.get("id") == dev_id or d.get("mac") == dev_id:
            return d.get("name") or dev_id
    return dev_id


def inventaire(sw_clients, ap_clients, site_clients, devices, now=None):
    """Fusion par MAC. Renvoie {"clients": [...], "commutateurs": [{id, nom, ports: {num: [mac...]}}], "bornes": [...]}.
    Chaque client : {mac, ip, nom, fabricant, vlan, type (filaire|wifi|inconnu), commutateur, port, borne, ssid, signal,
    bande, canal, derniere_vue, description}."""
    now = now or int(time.time())
    par_mac = {}

    def rec(mac):
        return par_mac.setdefault(mac, {"mac": mac, "ip": None, "nom": None, "fabricant": None, "vlan": None, "type": "inconnu",
                                        "commutateur": None, "commutateur_id": None, "port": None, "borne": None, "borne_id": None,
                                        "ssid": None, "signal": None, "bande": None, "canal": None, "derniere_vue": None, "description": None})

    for c in site_clients or []:
        mac = norm_mac(c.get("macAddress") or c.get("mac"))
        if not mac:
            continue
        r = rec(mac)
        oh = c.get("osHostname") or {}
        r.update({"ip": c.get("ipv4Address") or c.get("ipv4") or r["ip"], "nom": (oh.get("hostname") if isinstance(oh, dict) else None) or r["nom"],
                  "fabricant": c.get("manufacturer") or r["fabricant"], "vlan": c.get("vlan") or r["vlan"], "derniere_vue": c.get("lastSeen") or r["derniere_vue"],
                  "description": c.get("description") or r["description"]})
    for c in sw_clients or []:
        mac = norm_mac(c.get("macAddress") or c.get("mac"))
        if not mac:
            continue
        r = rec(mac)
        dev = c.get("connectedTo") or c.get("connectedDeviceId") or c.get("switch")
        oh = c.get("osHostname") or {}
        r.update({"type": "filaire", "commutateur_id": dev, "commutateur": _nom_appareil(dev, devices) if dev else r["commutateur"],
                  "port": c.get("connectedPort") or c.get("port") or r["port"], "vlan": c.get("vlan") or r["vlan"],
                  "ip": c.get("ipv4Address") or r["ip"], "nom": r["nom"] or (oh.get("hostname") if isinstance(oh, dict) else None),
                  "description": r["description"] or c.get("description"),
                  "fabricant": r["fabricant"] or c.get("manufacturer"), "derniere_vue": c.get("lastSeen") or r["derniere_vue"]})
    for c in ap_clients or []:
        mac = norm_mac(c.get("macAddress") or c.get("mac"))
        if not mac:
            continue
        r = rec(mac)
        dev = c.get("connectedTo") or c.get("connectedDeviceId")
        ws = c.get("wifiStation") or {}
        oh = c.get("osHostname") or {}
        r.update({"type": "wifi", "borne_id": dev, "borne": _nom_appareil(dev, devices) if dev else r["borne"], "ssid": c.get("ssid") or r["ssid"],
                  "signal": ws.get("signal") if isinstance(ws, dict) else None, "bande": ws.get("band") if isinstance(ws, dict) else None,
                  "canal": ws.get("channel") if isinstance(ws, dict) else None, "ip": c.get("ipv4Address") or r["ip"],
                  "nom": r["nom"] or (oh.get("hostname") if isinstance(oh, dict) else None), "description": r["description"] or c.get("description"),
                  "derniere_vue": c.get("lastSeen") or r["derniere_vue"]})
    for r in par_mac.values():
        if not r["nom"]:
            r["nom"] = r["description"]
    clients = sorted(par_mac.values(), key=lambda x: ((x["nom"] or "~").lower(), x["mac"]))
    comm = {}
    for cl in clients:
        if cl["type"] == "filaire" and cl["commutateur_id"]:
            s = comm.setdefault(cl["commutateur_id"], {"id": cl["commutateur_id"], "nom": cl["commutateur"], "ports": {}})
            s["ports"].setdefault(str(cl["port"] or "?"), []).append(cl["mac"])
    bornes = {}
    for cl in clients:
        if cl["type"] == "wifi" and cl["borne_id"]:
            b = bornes.setdefault(cl["borne_id"], {"id": cl["borne_id"], "nom": cl["borne"], "clients": 0, "signaux": []})
            b["clients"] += 1
            if isinstance(cl["signal"], (int, float)):
                b["signaux"].append(cl["signal"])
    for b in bornes.values():
        b["signal_moyen"] = round(sum(b["signaux"]) / len(b["signaux"])) if b["signaux"] else None
        del b["signaux"]
    return {"at": now, "clients": clients, "commutateurs": sorted(comm.values(), key=lambda s: (s["nom"] or s["id"]).lower()),
            "bornes": sorted(bornes.values(), key=lambda s: (s["nom"] or s["id"]).lower())}


def rechercher(inv, prises, q):
    """Recherche souple : MAC (partielle), IP, nom d'hôte, fabricant, « sw:port » (ex. GS2220-1 p12, 12), libellé de prise,
    local. Renvoie [{genre: client|prise, score, objet}] triés."""
    q = (q or "").strip().lower()
    if len(q) < 2:
        return []
    qmac = re.sub(r"[^0-9a-f]", "", q) if re.fullmatch(r"[0-9a-f:\-\.]+", q) and len(re.sub(r"[^0-9a-f]", "", q)) >= 4 else None
    mport = re.search(r"(?:^|\s)(?:p|port)\s*(\d+)$", q)
    out = []
    for c in inv.get("clients") or []:
        score = 0
        if qmac and qmac in c["mac"].replace(":", ""):
            score = 100
        for champ, pts in (("ip", 90), ("nom", 80), ("description", 60), ("fabricant", 30), ("commutateur", 40), ("borne", 40), ("ssid", 20)):
            v = (c.get(champ) or "")
            if v and q in str(v).lower():
                score = max(score, pts)
        if mport and c.get("port") is not None and str(c["port"]) == mport.group(1):
            score = max(score, 70)
        if score:
            out.append({"genre": "client", "score": score, "objet": c})
    for p in prises or []:
        score = 0
        for champ, pts in (("prise", 95), ("local", 70), ("panneau", 50), ("note", 30), ("commutateur", 40), ("mac", 60)):
            v = p.get(champ) or ""
            if v and q in str(v).lower():
                score = max(score, pts)
        if mport and p.get("port") is not None and str(p["port"]) == mport.group(1):
            score = max(score, 70)
        if score:
            out.append({"genre": "prise", "score": score, "objet": p})
    out.sort(key=lambda r: -r["score"])
    return out[:60]


def valider_prise(d):
    """Nettoie un enregistrement de prise envoyé par le téléphone. Renvoie (prise, erreur)."""
    if not isinstance(d, dict):
        return None, "objet attendu"
    prise = (str(d.get("prise") or "")).strip()[:60]
    if not prise:
        return None, "libellé de prise requis (ex. « B-12 »)"
    out = {"prise": prise}
    for k, lim in (("local", 80), ("commutateur", 80), ("panneau", 80), ("note", 500), ("mac", 17), ("equipement", 120)):
        v = d.get(k)
        out[k] = (str(v).strip()[:lim] if v not in (None, "") else None)
    out["mac"] = norm_mac(out["mac"]) if out["mac"] else None
    port = d.get("port")
    try:
        out["port"] = int(port) if port not in (None, "") else None
    except (TypeError, ValueError):
        return None, "port invalide"
    for k in ("long_cordon", "wifi", "defaut"):
        out[k] = bool(d.get(k))
    x, y = d.get("x"), d.get("y")
    if x is None or y is None:
        out["x"], out["y"] = None, None
    else:
        try:
            out["x"], out["y"] = min(1.0, max(0.0, float(x))), min(1.0, max(0.0, float(y)))
        except (TypeError, ValueError):
            return None, "position invalide"
    photos = d.get("photos")
    out["photos"] = [str(p)[:64] for p in photos][:12] if isinstance(photos, list) else []
    return out, None


def signal_couleur(signal):
    """dBm → classe : bon (≥ -60), moyen (≥ -70), faible (≥ -80), mauvais."""
    if signal is None:
        return "inconnu"
    try:
        s = float(signal)
    except (TypeError, ValueError):
        return "inconnu"
    return "bon" if s >= -60 else "moyen" if s >= -70 else "faible" if s >= -80 else "mauvais"


def releve_depuis_mobile(mobile, x, y, note=None, rssi_mobile=None, now=None):
    """Point de couverture : position sur le plan + ce que la borne voit du mobile (ou rien si absent)."""
    m = mobile or {}
    try:
        x, y = min(1.0, max(0.0, float(x))), min(1.0, max(0.0, float(y)))
    except (TypeError, ValueError):
        return None
    r = {"x": x, "y": y, "at": now or int(time.time()), "mac": m.get("mac"), "borne": m.get("borne"), "borne_id": m.get("borne_id"), "ssid": m.get("ssid"),
         "signal": m.get("signal"), "bande": m.get("bande"), "canal": m.get("canal"), "note": (note or "")[:200] or None}
    try:
        r["rssi_mobile"] = int(rssi_mobile) if rssi_mobile not in (None, "") else None
    except (TypeError, ValueError):
        r["rssi_mobile"] = None
    r["classe"] = signal_couleur(r["rssi_mobile"] if r["rssi_mobile"] is not None else r["signal"])
    return r


def prises_csv(prises):
    cols = ["prise", "local", "commutateur", "port", "panneau", "equipement", "mac", "long_cordon", "wifi", "defaut", "note", "x", "y", "photos", "maj"]
    lignes = [";".join(cols)]
    for p in prises:
        vals = []
        for c in cols:
            v = p.get(c)
            if isinstance(v, bool):
                v = "oui" if v else "non"
            elif isinstance(v, list):
                v = " ".join(map(str, v))
            vals.append(str(v if v is not None else "").replace(";", ",").replace("\n", " "))
        lignes.append(";".join(vals))
    return "\n".join(lignes) + "\n"


# -- site de test (bureau, sans Nebula) ---------------------------------------------------------------------------
SITE_TEST = "test-bureau"


def valider_appareil(d):
    """Appareil connu (téléphone de test, tablette…) : {mac, nom, genre}. Renvoie (appareil, erreur)."""
    if not isinstance(d, dict):
        return None, "objet attendu"
    mac = norm_mac(d.get("mac"))
    if not mac:
        return None, "MAC invalide (attendu aa:bb:cc:dd:ee:ff)"
    nom = (str(d.get("nom") or "")).strip()[:80]
    if not nom:
        return None, "nom requis (ex. « Téléphone Freg »)"
    genre = str(d.get("genre") or "telephone")
    if genre not in ("telephone", "tablette", "pc", "autre"):
        genre = "autre"
    return {"mac": mac, "nom": nom, "genre": genre}, None


def enrichir_connus(inv, appareils):
    """Nom des appareils connus appliqué aux clients sans nom (et champ `connu` dans tous les cas)."""
    par_mac = {a["mac"]: a for a in appareils or []}
    for c in inv.get("clients") or []:
        a = par_mac.get(c["mac"])
        if a:
            c["connu"] = a["nom"]
            if not c.get("nom"):
                c["nom"] = a["nom"]
    return inv


def inventaire_test(now=None, mac_mobile=None, appareils=None):
    """Inventaire simulé pour s'exercer au bureau : un commutateur SW-TEST (ports 1-6), une borne BORNE-TEST, et le
    téléphone (MAC donnée) vu avec un signal qui varie dans le temps (pour voir les couleurs changer)."""
    now = now or int(time.time())
    sw = [{"macAddress": "02:00:00:00:00:%02x" % i, "ipv4Address": "192.0.2.%d" % (10 + i), "connectedTo": "sw-test", "connectedPort": i, "vlan": 10 if i < 4 else 20,
           "osHostname": {"hostname": n}} for i, n in ((1, "pc-accueil"), (2, "imprimante"), (3, "ecran-salle"), (4, "camera-1"), (5, "nas"), (6, "borne-test-uplink"))]
    sc = [{"macAddress": "02:00:00:00:00:01", "manufacturer": "Dell"}, {"macAddress": "02:00:00:00:00:02", "manufacturer": "Brother"}, {"macAddress": "02:00:00:00:00:05", "manufacturer": "QNAP"}]
    ap = [{"macAddress": "02:00:00:00:00:21", "ipv4Address": "192.0.2.51", "connectedTo": "ap-test", "ssid": "GROUPE_I", "wifiStation": {"signal": -63, "band": "band5", "channel": 36}, "osHostname": {"hostname": "tablette"}}]
    mobiles = [norm_mac(mac_mobile)] if norm_mac(mac_mobile) else []
    for a in appareils or []:          # appareils connus (téléphones de test) : tous vus par la borne de test
        if a.get("genre") in ("telephone", "tablette") and a["mac"] not in mobiles:
            mobiles.append(a["mac"])
    for i, m in enumerate(mobiles):
        ap.append({"macAddress": m, "ipv4Address": "192.0.2.%d" % (77 + i), "connectedTo": "ap-test", "ssid": "GROUPE_I",
                   "wifiStation": {"signal": -48 - ((int(now / 15) + 7 * i) % 40), "band": "band5", "channel": 36}, "osHostname": {"hostname": "mobile-%d" % (i + 1)}})
    inv = inventaire(sw, ap, sc, [{"devId": "sw-test", "name": "SW-TEST"}, {"devId": "ap-test", "name": "BORNE-TEST"}], now=now)
    inv["test"] = True
    return inv
