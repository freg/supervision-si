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


# -- radar Wi-Fi mobile (#954) -------------------------------------------------------------------------------------
# Un navigateur ne peut pas balayer le Wi-Fi : les relevés viennent d'un petit script sur le téléphone (Termux + Termux:API,
# `termux-wifi-scaninfo`) ou d'une sonde portée (Pi + Alfa). Chaque balayage = liste des bornes visibles (BSSID, SSID, RSSI,
# fréquence) horodatée ; la position sur le plan est marquée à part (toucher le plan) et rapprochée par le temps en post-traitement.
def canal_depuis_frequence(mhz):
    try:
        f = int(mhz)
    except (TypeError, ValueError):
        return None
    if 2412 <= f <= 2484:
        return 14 if f == 2484 else (f - 2407) // 5
    if 5170 <= f <= 5895:
        return (f - 5000) // 5
    if 5955 <= f <= 7115:
        return (f - 5950) // 5
    return None


def bande_depuis_frequence(mhz):
    try:
        f = int(mhz)
    except (TypeError, ValueError):
        return None
    return "band24" if f < 3000 else "band5" if f < 5900 else "band6" if f < 7200 else None


def distance_estimee(rssi, frequence_mhz=None, n=2.7, p0=None):
    """Distance (m) par le modèle log-distance : d = 10^((P0 - RSSI) / (10 n)), P0 = puissance reçue à 1 m (défaut -40 dBm en
    2,4 GHz, -45 en 5 GHz, -48 en 6 GHz), n = 2,7 (intérieur cloisonné). Indicatif : le post-traitement affinera (étalonnage
    par borne, pertes de murs)."""
    try:
        r = float(rssi)
    except (TypeError, ValueError):
        return None
    if p0 is None:
        b = bande_depuis_frequence(frequence_mhz)
        p0 = {"band24": -40.0, "band5": -45.0, "band6": -48.0}.get(b, -42.0)
    d = 10 ** ((p0 - r) / (10.0 * n))
    return round(min(d, 500.0), 1)


def valider_balayage(d, now=None):
    """Corps d'un balayage {source, at?, x?, y?, scan: [{bssid, ssid, rssi, frequency_mhz|frequence, channel?}]} ->
    (balayage normalisé, erreur). Accepte tel quel la sortie de `termux-wifi-scaninfo`."""
    if not isinstance(d, dict):
        return None, "objet attendu"
    source = (str(d.get("source") or "")).strip()[:80]
    if not source:
        return None, "source requise (nom ou MAC de l'appareil qui balaie)"
    scan = d.get("scan")
    if not isinstance(scan, list) or not scan:
        return None, "scan attendu (liste des bornes visibles)"
    at = d.get("at")
    try:
        at = float(at) if at not in (None, "") else float(now or time.time())
    except (TypeError, ValueError):
        at = float(now or time.time())
    x, y = d.get("x"), d.get("y")
    try:
        pos = (min(1.0, max(0.0, float(x))), min(1.0, max(0.0, float(y)))) if x is not None and y is not None else (None, None)
    except (TypeError, ValueError):
        return None, "position invalide"
    bornes = []
    for b in scan[:200]:
        if not isinstance(b, dict):
            continue
        bssid = norm_mac(b.get("bssid"))
        if not bssid:
            continue
        try:
            rssi = int(float(b.get("rssi")))
        except (TypeError, ValueError):
            continue
        freq = b.get("frequency_mhz") or b.get("frequence") or b.get("frequency")
        try:
            freq = int(freq) if freq not in (None, "") else None
        except (TypeError, ValueError):
            freq = None
        bornes.append({"bssid": bssid, "ssid": (str(b.get("ssid") or ""))[:64], "rssi": rssi, "frequence": freq,
                       "canal": b.get("channel") or canal_depuis_frequence(freq), "bande": bande_depuis_frequence(freq),
                       "distance_m": distance_estimee(rssi, freq), "connecte": bool(b.get("connecte"))})
    if not bornes:
        return None, "aucune borne exploitable (bssid + rssi requis)"
    bornes.sort(key=lambda b: -b["rssi"])
    return {"source": source, "at": at, "x": pos[0], "y": pos[1], "bornes": bornes}, None


def radar_csv(lignes):
    cols = ["scan_id", "source", "at", "x", "y", "bssid", "ssid", "rssi", "frequence", "canal", "bande", "distance_m"]
    out = [";".join(cols)]
    for l in lignes:
        out.append(";".join(str(l.get(c) if l.get(c) is not None else "").replace(";", ",") for c in cols))
    return "\n".join(out) + "\n"


# ----------------------------------------------------------------- sonde filaire (#959) : Raspberry Pi branché prise par prise
MODES_SONDE = ("prise", "brassage")


def numero_port(v):
    """Identifiant de port LLDP ou Nebula -> entier : « 12 », « ge12 », « port 12 », « 1/12 », « Port12 » -> 12."""
    if v in (None, ""):
        return None
    if isinstance(v, int):
        return v
    m = re.findall(r"\d+", str(v))
    return int(m[-1]) if m else None


def valider_sonde(d):
    """Relevé envoyé par la sonde (tools/sonde-prise.sh). Renvoie (releve, erreur)."""
    if not isinstance(d, dict):
        return None, "objet attendu"
    source = str(d.get("source") or "").strip()[:60]
    if not source:
        return None, "source requise (nom de la sonde)"
    mode = d.get("mode") if d.get("mode") in MODES_SONDE else "prise"
    lldp = d.get("lldp") if isinstance(d.get("lldp"), dict) else {}
    out = {"source": source, "mode": mode, "mac": norm_mac(d.get("mac")) if d.get("mac") else None, "ip": (str(d.get("ip") or "").strip()[:45] or None),
           "commutateur": (str(lldp.get("commutateur") or lldp.get("chassis") or "").strip()[:80] or None),
           "port": numero_port(lldp.get("port")), "port_id": (str(lldp.get("port") or "").strip()[:40] or None),
           "port_descr": (str(lldp.get("port_descr") or "").strip()[:120] or None), "vlan": numero_port(lldp.get("vlan")),
           "ip_gestion": (str(lldp.get("ip_gestion") or "").strip()[:45] or None), "lldp": bool(lldp.get("commutateur") or lldp.get("chassis")),
           "note": (str(d.get("note") or "").strip()[:200] or None)}
    try:
        out["id"] = int(d["id"]) if d.get("id") not in (None, "") else None
    except (TypeError, ValueError):
        return None, "id invalide"
    return out, None


def rapprocher_sonde(r, inv, prises=None):
    """Complète le relevé avec ce que Nebula voit de la MAC de la sonde (sw-clients) et la prise déjà déclarée sur ce port.
    confirme : True = LLDP et Nebula d'accord ; False = en désaccord ; None = Nebula n'a pas (encore) vu la sonde."""
    c = next((x for x in (inv or {}).get("clients") or [] if x.get("mac") == r.get("mac")), None) if r.get("mac") else None
    r = dict(r, nebula_commutateur=None, nebula_port=None, confirme=None)
    if c and c.get("type") == "filaire" and (c.get("commutateur") or c.get("port") is not None):
        r["nebula_commutateur"], r["nebula_port"] = c.get("commutateur") or c.get("commutateur_id"), numero_port(c.get("port"))
        if r["lldp"]:
            meme_sw = (r["commutateur"] or "").lower() == (r["nebula_commutateur"] or "").lower() or not r["commutateur"] or not r["nebula_commutateur"]
            r["confirme"] = bool(meme_sw and r["port"] == r["nebula_port"])
        else:                                        # pas de LLDP : Nebula fait foi
            r["commutateur"], r["port"], r["confirme"] = r["nebula_commutateur"], r["nebula_port"], True
    sw, po = (r.get("commutateur") or "").lower(), r.get("port")
    r["prise_connue"] = next((p for p in prises or [] if po is not None and p.get("port") == po and (p.get("commutateur") or "").lower() == sw), None)
    return r


def fusion_prise_sonde(existante, releve, saisie):
    """Prise à enregistrer après validation d'un relevé de sonde : mode prise -> commutateur/port ; mode brassage -> panneau.
    `saisie` : {prise, local, panneau, note} tapé sur le téléphone."""
    p = dict(existante or {})
    p["prise"] = (saisie.get("prise") or p.get("prise") or "").strip()
    for k in ("local", "note"):
        if saisie.get(k):
            p[k] = saisie[k]
    if releve.get("mode") == "brassage":
        if saisie.get("panneau"):
            p["panneau"] = saisie["panneau"]
    if releve.get("commutateur") and releve.get("port") is not None:
        p["commutateur"], p["port"] = releve["commutateur"], releve["port"]
    return p


# ----------------------------------------------------------------- registre des équipements du site (#960)
# Saisie au bureau des notes de terrain : nom, rôle, IP, MAC, position sur le plan, local, prise, étiquettes (tags) libres.
IP_RX = re.compile(r"^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$")


def norm_ip(v):
    s = str(v or "").strip()
    m = IP_RX.match(s)
    if not m or any(int(g) > 255 for g in m.groups()):
        return None
    return ".".join(str(int(g)) for g in m.groups())


def norm_tags(v):
    """« rôle:serveur, vlan 20 ,  Critique » ou liste -> ['rôle:serveur', 'vlan 20', 'critique'] (minuscules, sans doublon, 20 max).
    Forme libre ; « clé:valeur » permet plus tard des catégories (rôle principal, criticité, propriétaire…)."""
    items = v if isinstance(v, list) else re.split(r"[,;\n]", str(v or ""))
    out = []
    for t in items:
        t = re.sub(r"\s+", " ", str(t or "")).strip().lower()[:40]
        t = re.sub(r"\s*:\s*", ":", t)
        if t and t not in out:
            out.append(t)
    return out[:20]


def valider_equipement(d):
    """Renvoie (equipement, erreur). Il faut au moins un nom, une IP ou une MAC."""
    if not isinstance(d, dict):
        return None, "objet attendu"
    out = {}
    for k, lim in (("nom", 80), ("role", 80), ("local", 80), ("prise", 60), ("note", 1000), ("source", 40)):
        v = d.get(k)
        out[k] = (str(v).strip()[:lim] if v not in (None, "") else None)
    out["ip"] = norm_ip(d.get("ip")) if d.get("ip") not in (None, "") else None
    if d.get("ip") not in (None, "") and not out["ip"]:
        return None, "IP invalide : %s (attendu a.b.c.d)" % d.get("ip")
    out["mac"] = norm_mac(d.get("mac")) if d.get("mac") not in (None, "") else None
    if d.get("mac") not in (None, "") and not out["mac"]:
        return None, "MAC invalide : %s (12 chiffres hexadécimaux)" % d.get("mac")
    if not (out["nom"] or out["ip"] or out["mac"]):
        return None, "il faut au moins un nom, une IP ou une MAC"
    x, y = d.get("x"), d.get("y")
    if x in (None, "") or y in (None, ""):
        out["x"] = out["y"] = None
    else:
        try:
            out["x"], out["y"] = min(1.0, max(0.0, float(x))), min(1.0, max(0.0, float(y)))
        except (TypeError, ValueError):
            return None, "position invalide"
    out["tags"] = norm_tags(d.get("tags"))
    eid = str(d.get("id") or "").strip()
    out["id"] = re.sub(r"[^A-Za-z0-9_-]", "", eid)[:40] or None
    return out, None


def enrichir_equipements(eqs, inv):
    """Ajoute à chaque équipement ce que Nebula en voit (par MAC, sinon par IP) et les doublons de saisie.
    nebula : {mac, ip, nom, fabricant, ou (ligne « où est branché »), derniere_vue} ; alertes : [texte]."""
    clients = (inv or {}).get("clients") or []
    par_mac = {c["mac"]: c for c in clients if c.get("mac")}
    par_ip = {c["ip"]: c for c in clients if c.get("ip")}
    vus_mac, vus_ip = {}, {}
    for e in eqs:
        if e.get("mac"):
            vus_mac.setdefault(e["mac"], []).append(e)
        if e.get("ip"):
            vus_ip.setdefault(e["ip"], []).append(e)
    out = []
    for e in eqs:
        e = dict(e)
        c = par_mac.get(e.get("mac")) or par_ip.get(e.get("ip"))
        alertes = []
        if c:
            ou = ("%s port %s" % (c.get("commutateur") or c.get("commutateur_id") or "?", c.get("port") if c.get("port") is not None else "?")) if c.get("type") == "filaire" \
                else ("borne %s · %s" % (c.get("borne") or c.get("borne_id") or "?", c.get("ssid") or "")) if c.get("type") == "wifi" else None
            e["nebula"] = {"mac": c.get("mac"), "ip": c.get("ip"), "nom": c.get("nom") or c.get("description"), "fabricant": c.get("fabricant"),
                           "ou": ou, "vlan": c.get("vlan"), "derniere_vue": c.get("derniere_vue"), "par": "mac" if par_mac.get(e.get("mac")) is c else "ip"}
            if e.get("ip") and c.get("ip") and e["ip"] != c["ip"]:
                alertes.append("Nebula voit cette MAC en %s (saisi %s)" % (c["ip"], e["ip"]))
            if e.get("mac") and c.get("mac") and e["mac"] != c["mac"]:
                alertes.append("Nebula voit cette IP avec la MAC %s (saisi %s)" % (c["mac"], e["mac"]))
        else:
            e["nebula"] = None
        if e.get("mac") and len(vus_mac.get(e["mac"], [])) > 1:
            alertes.append("MAC saisie aussi pour : %s" % ", ".join(x.get("nom") or x.get("ip") or x["id"] for x in vus_mac[e["mac"]] if x.get("id") != e.get("id")))
        if e.get("ip") and len(vus_ip.get(e["ip"], [])) > 1:
            alertes.append("IP saisie aussi pour : %s" % ", ".join(x.get("nom") or x.get("mac") or x["id"] for x in vus_ip[e["ip"]] if x.get("id") != e.get("id")))
        e["alertes"] = alertes
        out.append(e)
    return out


def equipements_csv(eqs):
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";")
    w.writerow(["nom", "role", "ip", "mac", "local", "prise", "x", "y", "tags", "note", "nebula_ou", "nebula_fabricant"])
    for e in eqs:
        n = e.get("nebula") or {}
        w.writerow([e.get("nom") or "", e.get("role") or "", e.get("ip") or "", e.get("mac") or "", e.get("local") or "", e.get("prise") or "",
                    "" if e.get("x") is None else ("%.4f" % e["x"]).replace(".", ","), "" if e.get("y") is None else ("%.4f" % e["y"]).replace(".", ","),
                    ", ".join(e.get("tags") or []), e.get("note") or "", n.get("ou") or "", n.get("fabricant") or ""])
    return "﻿" + buf.getvalue()


def lire_csv_equipements(texte):
    """Import d'un tableau (CSV ; ou , ou tabulation, avec en-tête nom/role/ip/mac/local/prise/tags/note) -> (lignes, erreurs)."""
    import csv
    import io
    texte = (texte or "").lstrip("﻿")
    if not texte.strip():
        return [], ["fichier vide"]
    sep = "\t" if "\t" in texte.splitlines()[0] else (";" if ";" in texte.splitlines()[0] else ",")
    rd = csv.DictReader(io.StringIO(texte), delimiter=sep)
    alias = {"rôle": "role", "adresse ip": "ip", "adresse mac": "mac", "nom": "nom", "name": "nom", "étiquettes": "tags", "tag": "tags", "commentaire": "note", "pièce": "local", "salle": "local"}
    lignes, erreurs = [], []
    for i, r in enumerate(rd, start=2):
        d = {alias.get((k or "").strip().lower(), (k or "").strip().lower()): v for k, v in r.items()}
        d.pop("x", None); d.pop("y", None)
        e, err = valider_equipement(d)
        if err:
            erreurs.append("ligne %d : %s" % (i, err))
        else:
            lignes.append(e)
    return lignes, erreurs
