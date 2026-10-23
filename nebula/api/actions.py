# -*- coding: utf-8 -*-
"""Module d'action sur le réseau (livraison #852) -- logique PURE, testée (tests/test_actions.py).

Pour une anomalie de la carte des VLAN : un PLAN (par l'API ou manuel, étapes, retour arrière), l'IMPACT immédiat
(clients du périmètre vus récemment, volume récent = flux actifs approchés), puis les CONTRÔLES du chien de garde après
l'action. L'OpenAPI Nebula n'écrit que les réglages de ports des commutateurs (et quelques réglages Wi-Fi) : les
interfaces de la passerelle sont en lecture seule -> plan manuel guidé, vérifié ensuite par relecture."""
import re
import time

ACTIF_S = 600                      # client vu depuis moins de 10 min = actif
SEUIL_FORT_CLIENTS = 3
SEUIL_FORT_OCTETS = 100e6          # 100 Mo en 2 h


def _mac(s):
    h = re.sub(r"[^0-9a-f]", "", str(s or "").lower())
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)) if len(h) == 12 else str(s or "").lower()


def _ts(v):
    """last_seen en ms ou en s -> secondes."""
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    return v / 1000.0 if v > 1e11 else v


def _vlans(d):
    out = []
    for v in (d.get("vlans") or []) + ([d["vlan"]] if d.get("vlan") not in (None, "") else []):
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            pass
    return sorted(set(out))


def plan(a):
    """Anomalie (kind, details, action, element) -> {mode: api|manuel, perimetre, etapes, retour, pourquoi_manuel}."""
    d, k = a.get("details") or {}, a.get("kind")
    if k == "link_missing_vlan":
        p = {"dev": d.get("missing_dev"), "equipement": d.get("missing_on"), "port": d.get("missing_port"), "vlans": _vlans(d)}
        vl = ", ".join(map(str, p["vlans"]))
        return {"mode": "api", "perimetre": p, "retour": "automatique : le port est remis dans son état sauvegardé si un contrôle échoue",
                "etapes": ["relire et sauvegarder le réglage du port %s de %s" % (p["port"], p["equipement"]),
                           "ajouter le VLAN %s en étiqueté sur ce port (écriture par l'API Nebula)" % vl,
                           "surveiller (chien de garde) : commutateur en ligne, VLAN %s présent sur le port, clients du périmètre revenus" % vl,
                           "si un contrôle échoue : retour arrière automatique, journal et alerte"]}
    if k == "gateway_ip_not_host":
        p = {"vlans": _vlans(d), "interface": d.get("interface"), "avant": d.get("address"), "apres": d.get("suggest")}
        return {"mode": "manuel", "perimetre": p, "pourquoi_manuel": "l'API Nebula ne permet pas de modifier les interfaces de la passerelle (lecture seule)",
                "retour": "manuel : remettre %s sur l'interface %s dans Nebula" % (p["avant"], p["interface"]),
                "etapes": ["Nebula : Pare-feu > Configuration > Interfaces, interface %s : %s -> %s" % (p["interface"], p["avant"], p["apres"]),
                           "vérifier l'étendue DHCP de cette interface (même réseau, passerelle annoncée %s)" % str(p["apres"]).split("/")[0],
                           "revenir ici : « Fait, vérifier » relit la configuration et la carte des VLAN"]}
    return {"mode": "manuel", "perimetre": {"vlans": _vlans(d)}, "retour": "manuel", "pourquoi_manuel": "pas de correction par l'API pour ce type",
            "etapes": [a.get("action") or "action à définir", "revenir ici : « Fait, vérifier » relit la carte des VLAN"]}


def impact(perimetre, clients=None, sw_clients=None, ap_clients=None, ssid_vlan=None, maintenant=None):
    """Clients et flux touchés par l'action : par VLAN du périmètre et par port du commutateur visé.
    -> {clients: [{mac, nom, ip, vlan, vu_il_y_a_s, actif, source}], actifs, recents, octets_2h, niveau, texte}"""
    now = maintenant or time.time()
    vl, dev, port = set(perimetre.get("vlans") or []), perimetre.get("dev"), perimetre.get("port")
    sv = {k: v for k, v in (ssid_vlan or {}).items()}
    vus, octets = {}, 0.0

    def ajout(c, source, vlan):
        m = _mac(c.get("mac_address") or c.get("macAddress") or c.get("mac"))
        if not m:
            return
        t = _ts(c.get("last_seen") or c.get("lastSeen"))
        e = vus.setdefault(m, {"mac": m, "nom": c.get("os_hostname") or c.get("description") or c.get("name") or "", "ip": c.get("ipv4") or c.get("ipv4Address") or c.get("ip"),
                               "vlan": vlan, "vu_il_y_a_s": None, "source": source})
        if t is not None:
            e["vu_il_y_a_s"] = int(now - t) if e["vu_il_y_a_s"] is None else min(e["vu_il_y_a_s"], int(now - t))
    for c in clients or []:
        v = c.get("vlan")
        if v not in (None, "") and int(float(v)) in vl:
            ajout(c, "site", int(float(v)))
    for c in sw_clients or []:
        v = c.get("vlan")
        sur_port = dev and str(c.get("connected_device_id") or c.get("devId") or "") == str(dev) and str(c.get("connected_port") or c.get("port") or "") == str(port)
        if sur_port or (v not in (None, "") and int(float(v)) in vl):
            ajout(c, "port %s" % port if sur_port else "commutateurs", int(float(v)) if v not in (None, "") else None)
    for c in ap_clients or []:
        v = sv.get(c.get("ssid"))
        if v is not None and int(v) in vl:
            ajout(c, "Wi-Fi %s" % c.get("ssid"), int(v))
            try:
                octets += float(c.get("upload") or 0) + float(c.get("download") or 0)
            except (TypeError, ValueError):
                pass
    lst = sorted(vus.values(), key=lambda e: (e["vu_il_y_a_s"] is None, e["vu_il_y_a_s"] or 0))
    for e in lst:
        e["actif"] = e["vu_il_y_a_s"] is not None and e["vu_il_y_a_s"] <= ACTIF_S
    actifs = sum(1 for e in lst if e["actif"])
    niveau = "aucun" if not lst else "fort" if actifs > SEUIL_FORT_CLIENTS or octets > SEUIL_FORT_OCTETS else "faible"
    texte = {"aucun": "aucun client vu sur le périmètre : action sans effet visible pour les utilisateurs",
             "faible": "%d client(s) actif(s), %d vu(s) sur 2 h, %.0f Mo échangés : coupure brève possible pour eux" % (actifs, len(lst), octets / 1e6),
             "fort": "%d client(s) actif(s), %d vu(s) sur 2 h, %.0f Mo échangés : à faire de préférence hors activité, confirmation renforcée" % (actifs, len(lst), octets / 1e6)}[niveau]
    return {"clients": lst[:200], "actifs": actifs, "recents": len(lst), "octets_2h": octets, "niveau": niveau, "texte": texte}


def controles(perimetre, etat):
    """Contrôles du chien de garde. etat : {dev_status, port: réglage relu, clients_avant, clients_apres, anomalie_presente}
    -> [{nom, ok, detail}]"""
    out = []
    if perimetre.get("dev"):
        st = etat.get("dev_status")
        out.append({"nom": "commutateur en ligne", "ok": st == "online", "detail": "état Nebula : %s" % (st or "inconnu")})
    if perimetre.get("dev") and perimetre.get("vlans"):
        p = etat.get("port") or {}
        porte = {str(v) for v in p.get("allowedVLAN") or []}
        manque = [v for v in perimetre["vlans"] if str(v) not in porte and not p.get("all")]
        out.append({"nom": "VLAN présents sur le port", "ok": bool(p) and not manque,
                    "detail": ("manquent : %s" % ", ".join(map(str, manque))) if manque else "port %s : %s" % (perimetre.get("port"), ", ".join(sorted(porte)) or "?")})
    av, ap = etat.get("clients_avant"), etat.get("clients_apres")
    if av:
        out.append({"nom": "clients du périmètre revenus", "ok": (ap or 0) >= max(1, int(av * 0.5)), "detail": "%s actif(s) après, %s avant" % (ap if ap is not None else "?", av)})
    if "anomalie_presente" in etat:
        out.append({"nom": "anomalie disparue de la carte", "ok": not etat["anomalie_presente"], "detail": "toujours signalée" if etat["anomalie_presente"] else "plus signalée"})
    return out


def bilan(ctrl):
    return all(c["ok"] for c in ctrl) if ctrl else None
