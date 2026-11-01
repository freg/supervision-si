# -*- coding: utf-8 -*-
"""Veille de santé du réseau du campus (livraison #847) -- logique PURE, testée (tests/test_veille.py).

Deux sources croisées :
1. Nebula (sondeur à la minute #546) : passerelle / pare-feu, commutateurs, bornes Wi-Fi (« spots ») ;
   clients connectés (présence des postes suivis) ;
2. les agents internes du site (poste du campus, Proxmox…) : battement, sonde « chemin de service »
   (path-probe : bail DHCP, passerelle, DNS, Internet par interface ou par SSID), sonde « annonces réseau »
   (broadcast-probe : serveurs DHCP vus, appareils qui s'annoncent).

Par VLAN suivi : DHCP, passerelle, DNS, Internet tels que vus par une sonde présente dans ce VLAN ; usage
par créneaux (ex. VLAN à usage mixte : organisme extérieur certaines demi-journées) -> l'alerte d'un créneau
« externe » part sur une action de notification distincte. Postes suivis : présents / absents, attendus
toujours, aux heures ouvrées ou jamais (information).

Rien n'est écrit sur le réseau : lecture des relevés existants seulement."""
import ipaddress
import re
import time
from datetime import datetime

SEV_ORDER = {"haute": 0, "moyenne": 1, "basse": 2, "info": 3}
STATUTS = ("ok", "ko", "doute", "inconnu")
ATTENDUS = ("toujours", "heures", "info")
JOURS = {"lun": 1, "mar": 2, "mer": 3, "jeu": 4, "ven": 5, "sam": 6, "dim": 7}

DEFAUT = {
    "enabled": True,
    "site_id": "",                  # vide = premier site Nebula
    "agent_site": "",               # champ « site » des agents internes (vide = agents listés ci-dessous seulement)
    "agents": [],                   # identifiants d'agents internes (poste du campus, Proxmox…)
    "agent_silence_min": 10,        # au-delà, l'agent est muet : la veille devient aveugle de ce côté
    "fraicheur_min": 10,            # relevé de sonde plus vieux : « non observé »
    "periode_s": 120,
    "heures": "1-5 08:00-18:00",    # heures ouvrées (postes « attendus aux heures »)
    "vlans": [],                    # [{id, nom, connexion, sous_reseau, dhcp_attendus, creneaux}]
    "postes": [],                   # [{nom, mac, ip, vlan, attendu}]
    "alerte": {"enabled": True, "delay_minutes": 5, "repeat_hours": 4, "notify_recovery": True, "min_severity": "moyenne"},
}


def _int(v, lo, hi, d):
    try:
        v = int(v)
    except (TypeError, ValueError):
        return d
    return min(hi, max(lo, v))


def norm_mac(s):
    h = re.sub(r"[^0-9a-f]", "", str(s or "").lower())
    return ":".join(h[i:i + 2] for i in range(0, 12, 2)) if len(h) == 12 else ""


def parse_creneaux(texte):
    """« 1-5 08:00-12:30 externe ; lun,mer 13:30-18:00 interne » -> [{jours, debut, fin, usage}] ou ValueError."""
    out = []
    for part in [p.strip() for p in re.split(r"[;\n]", str(texte or "")) if p.strip()]:
        m = re.match(r"^([0-9a-z,\- ]+?)\s+(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})(?:\s+(\w+))?$", part.lower())
        if not m:
            raise ValueError("créneau illisible : « %s » (ex. 1-5 08:00-12:30 externe)" % part)
        jours = set()
        for tok in [t.strip() for t in m.group(1).split(",") if t.strip()]:
            a, _, b = tok.partition("-")
            a, b = JOURS.get(a[:3], a), JOURS.get(b[:3], b) if b else None
            try:
                a = int(a); b = int(b) if b else a
            except ValueError:
                raise ValueError("jours illisibles : « %s »" % tok)
            if not (1 <= a <= 7 and 1 <= b <= 7):
                raise ValueError("jours de 1 (lundi) à 7 (dimanche)")
            jours.update(range(a, b + 1) if a <= b else list(range(a, 8)) + list(range(1, b + 1)))
        debut, fin = m.group(2).zfill(5), m.group(3).zfill(5)
        if not (debut < fin <= "24:00"):
            raise ValueError("heures : début avant fin (« %s »)" % part)
        out.append({"jours": sorted(jours), "debut": debut, "fin": fin, "usage": m.group(4) or "interne"})
    return out


def usage_a(creneaux, dt):
    """Usage du créneau en cours (« interne » hors créneau)."""
    hm, j = dt.strftime("%H:%M"), dt.isoweekday()
    for c in creneaux or []:
        if j in c["jours"] and c["debut"] <= hm < c["fin"]:
            return c["usage"]
    return "interne"


def normalize(cfg):
    """Réglages complets et propres ; -> (réglages, erreurs [texte])."""
    cfg = cfg or {}
    errs = []
    out = {k: (dict(v) if isinstance(v, dict) else v) for k, v in DEFAUT.items()}
    out["enabled"] = bool(cfg.get("enabled", True))
    out["site_id"] = str(cfg.get("site_id") or "")[:80]
    out["agent_site"] = str(cfg.get("agent_site") or "")[:80]
    out["agents"] = [str(a)[:80] for a in (cfg.get("agents") or []) if str(a).strip()][:10]
    out["agent_silence_min"] = _int(cfg.get("agent_silence_min"), 2, 240, 10)
    out["fraicheur_min"] = _int(cfg.get("fraicheur_min"), 2, 240, 10)
    out["periode_s"] = _int(cfg.get("periode_s"), 60, 3600, 120)
    out["heures"] = str(cfg.get("heures") or DEFAUT["heures"])
    try:
        parse_creneaux(out["heures"])
    except ValueError as e:
        errs.append("heures ouvrées : %s" % e); out["heures"] = DEFAUT["heures"]
    vlans = []
    for v in (cfg.get("vlans") or [])[:40]:
        vid = _int(v.get("id"), 1, 4094, None)
        if vid is None:
            errs.append("VLAN sans numéro ignoré"); continue
        sr = str(v.get("sous_reseau") or "").strip()
        if sr:
            try:
                sr = str(ipaddress.ip_network(sr, strict=False))
            except ValueError:
                errs.append("VLAN %d : sous-réseau illisible" % vid); sr = ""
        cr_txt = v.get("creneaux") if isinstance(v.get("creneaux"), str) else "; ".join(
            "%s %s-%s %s" % (",".join(map(str, c.get("jours") or [])), c.get("debut"), c.get("fin"), c.get("usage") or "interne") for c in (v.get("creneaux") or []))
        try:
            cr = parse_creneaux(cr_txt)
        except ValueError as e:
            errs.append("VLAN %d : %s" % (vid, e)); cr = []
        dhcp = [s.strip() for s in (v.get("dhcp_attendus") if isinstance(v.get("dhcp_attendus"), list) else str(v.get("dhcp_attendus") or "").split(",")) if s.strip()]
        vlans.append({"id": vid, "nom": str(v.get("nom") or "VLAN %d" % vid)[:60], "connexion": str(v.get("connexion") or "").strip()[:80],
                      "sous_reseau": sr, "dhcp_attendus": dhcp[:6], "creneaux": cr, "internet": bool(v.get("internet", True))})
    out["vlans"] = vlans
    postes = []
    for p in (cfg.get("postes") or [])[:300]:
        mac, ip = norm_mac(p.get("mac")), str(p.get("ip") or "").strip()
        if not (mac or ip):
            continue
        att = p.get("attendu") if p.get("attendu") in ATTENDUS else "info"
        postes.append({"nom": str(p.get("nom") or mac or ip)[:60], "mac": mac, "ip": ip, "vlan": _int(p.get("vlan"), 1, 4094, None), "attendu": att})
    out["postes"] = postes
    a = cfg.get("alerte") or {}
    out["alerte"] = {"enabled": bool(a.get("enabled", True)), "delay_minutes": _int(a.get("delay_minutes"), 0, 240, 5),
                     "repeat_hours": _int(a.get("repeat_hours"), 0, 168, 4), "notify_recovery": bool(a.get("notify_recovery", True)),
                     "min_severity": a.get("min_severity") if a.get("min_severity") in SEV_ORDER else "moyenne"}
    return out, errs


# -- évaluation ---------------------------------------------------------------------------------------------------------
def _ts(v):
    """Horodatage ISO (« …Z ») ou nombre -> epoch, sinon None."""
    if v is None or v == "":
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def _v(fam, vid, nom, statut, sev, detail, source="", usage="interne", lien=None):
    return {"id": "%s:%s" % (fam, vid), "famille": fam, "nom": nom, "statut": statut, "severite": sev, "detail": detail,
            "source": source, "usage": usage, "lien": lien}


def _kind(t):
    t = str(t or "").upper()
    return "passerelle" if t in ("GW", "GWH", "FIREWALL", "GATEWAY", "USG") else "commutateur" if t in ("SW", "SWITCH") else "borne" if t == "AP" else "autre"


def _ago(sec):
    sec = int(max(0, sec))
    return "%d min" % (sec // 60) if sec < 5400 else "%d h" % (sec // 3600)


def _paths(agents, fraicheur_s, now):
    """Chemins path-probe récents de tous les agents : [(agent_id, chemin)]."""
    out = []
    for a in agents:
        m = (a.get("latest") or {}).get("plugin:path-probe") or {}
        t = _ts(m.get("at"))
        if not m.get("data") or t is None or now - t > fraicheur_s:
            continue
        for p in m["data"].get("paths") or []:
            out.append((a["agent_id"], p))
    return out


def _path_du_vlan(v, paths):
    for aid, p in paths:
        if v["connexion"] and v["connexion"] in (p.get("connection"), p.get("ssid"), p.get("iface")):
            return aid, p
        if v["sous_reseau"] and p.get("ip"):
            try:
                if ipaddress.ip_address(p["ip"]) in ipaddress.ip_network(v["sous_reseau"]):
                    return aid, p
            except ValueError:
                pass
    return None, None


def _chemin(p):
    """Un chemin -> {dhcp, passerelle, dns, internet : (statut, détail)} depuis ses mesures et ses constats
    (codes de path_probe.evaluate : conn-up-failed, no-ip, gw-*, dns-*, http(s)-*, captive-portal)."""
    al = {a.get("code"): a for a in p.get("alerts") or []}

    def pire(*codes):
        lst = [al[c] for c in codes if c in al]
        lst.sort(key=lambda a: a.get("severity") != "critical")
        return lst[0] if lst else None

    def st(a, ok_detail, rien=False):
        if a:
            return ("ko" if a.get("severity") == "critical" else "doute", a.get("message") or a.get("code"))
        return ("inconnu", "non mesuré") if rien else ("ok", ok_detail)

    r = {}
    a = pire("conn-up-failed", "no-ip")
    if a or not p.get("ip"):
        r["dhcp"] = ("ko", a["message"] if a else "aucune adresse reçue")
    elif p.get("static"):
        r["dhcp"] = ("ok", "adresse fixe %s" % p["ip"])
    else:
        r["dhcp"] = ("ok", "bail %s du serveur %s" % (p["ip"], (p.get("dhcp") or {}).get("server") or "?"))
    r["passerelle"] = st(pire("gw-unreachable", "gw-loss", "gw-slow"), "%s répond" % p.get("gateway"), rien=not p.get("gateway"))
    dns = p.get("dns") or []
    r["dns"] = st(pire("dns-none", "dns-all-down", "dns-public-down", "dns-server-down", "dns-single", "dns-slow"),
                  "%d serveur(s) DNS répondent" % sum(1 for d in dns if d.get("ok")), rien=not dns and "dns-none" not in al)
    h, hs = p.get("http") or {}, p.get("https") or {}
    r["internet"] = st(pire("captive-portal", "https-failed", "http-failed", "https-slow", "http-slow"),
                       "page de test en %s ms" % (hs.get("ms") or h.get("ms")), rien=not (h or hs))
    return r


def evaluer(cfg, entrees, maintenant=None, dt=None):
    """entrees : {nebula: {devices: [{dev_id, name, type, status, since}], ok: bool, erreur},
                  agents: [{agent_id, hostname, site, last_seen_at, latest: {tâche: mesure}}],
                  clients: [{mac, ip, status}] | None}
    -> {etat, resume, verifs, compte}"""
    now = maintenant or time.time()
    dt = dt or datetime.fromtimestamp(now)
    V = []
    agents = entrees.get("agents") or []
    lien_agent = lambda aid: "?view=si-agent&agent=%s&section=plugins" % aid

    # 1. agents internes
    if not agents:
        V.append(_v("agents", "aucun", "Agents internes du site", "inconnu", "haute",
                    "aucun agent interne choisi ou joignable : la veille ne voit que Nebula", lien="?view=nebula&tab=veille"))
    for a in agents:
        t = _ts(a.get("last_seen_at"))
        muet = t is None or now - t > cfg["agent_silence_min"] * 60
        V.append(_v("agents", a["agent_id"], "Agent %s" % (a.get("hostname") or a["agent_id"]), "ko" if muet else "ok", "haute",
                    ("muet depuis %s" % _ago(now - t) if t else "jamais vu") if muet else "vu il y a %s" % _ago(now - t), "agent", lien=lien_agent(a["agent_id"])))

    # 2. équipements Nebula
    neb = entrees.get("nebula") or {}
    if not neb.get("ok", True):
        V.append(_v("equipements", "nebula", "Relevé Nebula", "inconnu", "moyenne", neb.get("erreur") or "Nebula injoignable", "nebula", lien="?view=nebula&tab=health"))
    devs = neb.get("devices") or []
    groupes = {}
    for d in devs:
        groupes.setdefault(_kind(d.get("type")), []).append(d)
    for kind, nom, sev in (("passerelle", "Passerelle / pare-feu", "haute"), ("commutateur", "Commutateurs", "haute"), ("borne", "Bornes Wi-Fi", "moyenne")):
        lst = groupes.get(kind) or []
        if not lst:
            continue
        hors = [d for d in lst if d.get("status") == "offline"]
        alerte = [d for d in lst if d.get("status") == "alerting"]
        if kind == "borne":
            for d in hors:
                V.append(_v("equipements", "dev-" + str(d.get("dev_id")), "Borne %s" % (d.get("name") or d.get("dev_id")), "ko", "moyenne",
                            "hors ligne" + (" depuis %s" % _ago(now - d["since"]) if d.get("since") else ""), "nebula", lien="?view=nebula&tab=health"))
            V.append(_v("equipements", "bornes", nom, "ok" if not hors and not alerte else "doute" if not hors else "ko", "basse",
                        "%d/%d en ligne%s" % (len(lst) - len(hors), len(lst), ", %d en alerte" % len(alerte) if alerte else ""), "nebula", lien="?view=nebula&tab=health"))
        else:
            V.append(_v("equipements", kind, nom, "ko" if hors else "doute" if alerte else "ok", sev,
                        ", ".join("%s hors ligne" % (d.get("name") or d.get("dev_id")) for d in hors) or
                        (", ".join("%s en alerte" % (d.get("name") or d.get("dev_id")) for d in alerte)) or "%d en ligne" % len(lst), "nebula", lien="?view=nebula&tab=health"))

    # 3. VLAN suivis (vus par une sonde présente dans le VLAN)
    paths = _paths(agents, cfg["fraicheur_min"] * 60, now)
    dhcp_vus = {}
    for a in agents:
        m = (a.get("latest") or {}).get("plugin:broadcast-probe") or {}
        t = _ts(m.get("at"))
        if m.get("data") and t is not None and now - t <= cfg["fraicheur_min"] * 60 * 3:
            for srv in (m["data"].get("dhcp_servers") or {}):
                dhcp_vus.setdefault(srv, set()).add(a["agent_id"])
    internet_vus = []
    for v in cfg["vlans"]:
        usage = usage_a(v["creneaux"], dt)
        aid, p = _path_du_vlan(v, paths)
        tag = "%s (VLAN %d)" % (v["nom"], v["id"])
        if p is None:
            V.append(_v("vlans", "%d" % v["id"], tag, "inconnu", "basse",
                        "non observé : aucune sonde « chemin de service » récente dans ce VLAN (connexion %s, sous-réseau %s)" % (v["connexion"] or "—", v["sous_reseau"] or "—"),
                        "agent", usage, lien=lien_agent(agents[0]["agent_id"]) if agents else None))
            continue
        r = _chemin(p)
        etapes = [("dhcp", "DHCP"), ("passerelle", "passerelle"), ("dns", "DNS")] + ([("internet", "Internet")] if v["internet"] else [])
        sts = [r[k][0] for k, _l in etapes]
        pire = "ko" if "ko" in sts else "doute" if "doute" in sts else "ok" if "ok" in sts else "inconnu"
        if v["internet"]:
            internet_vus.append((tag, r["internet"]))
        detail = " · ".join("%s %s" % (lib, {"ok": "✓", "ko": "✗", "doute": "?", "inconnu": "—"}[r[k][0]]) for k, lib in etapes)
        defaut = next((r[k][1] for k, _l in etapes if r[k][0] == "ko"), None) or next((r[k][1] for k, _l in etapes if r[k][0] == "doute"), None)
        V.append(_v("vlans", "%d" % v["id"], tag, pire, "haute" if pire == "ko" else "moyenne", detail + (" — " + defaut if defaut else ""),
                    "agent:%s" % aid, usage, lien=lien_agent(aid)))
        if v["dhcp_attendus"] and p.get("dhcp", {}).get("server") and p["dhcp"]["server"] not in v["dhcp_attendus"]:
            V.append(_v("vlans", "%d-dhcp" % v["id"], "%s : serveur DHCP" % tag, "ko", "haute",
                        "bail reçu de %s, attendu %s" % (p["dhcp"]["server"], ", ".join(v["dhcp_attendus"])), "agent:%s" % aid, usage, lien=lien_agent(aid)))
    attendus = {s for v in cfg["vlans"] for s in v["dhcp_attendus"]}
    if attendus:
        etrangers = sorted(s for s in dhcp_vus if s not in attendus)
        if etrangers:
            V.append(_v("vlans", "dhcp-inattendu", "Serveur DHCP inattendu", "ko", "haute",
                        "annonces DHCP de %s (vu par %s)" % (", ".join(etrangers), ", ".join(sorted({x for s in etrangers for x in dhcp_vus[s]}))), "agent"))

    # 4. liaison Internet (tous VLAN confondus ; à défaut, tous les chemins sondés)
    if not internet_vus:
        internet_vus = [("%s" % (p.get("ssid") or p.get("connection") or p.get("iface")), _chemin(p)["internet"]) for _a, p in paths]
    if internet_vus:
        oks = [t for t, (st, _d) in internet_vus if st == "ok"]
        kos = [(t, d) for t, (st, d) in internet_vus if st == "ko"]
        mes = [(t, s) for t, (s, _d) in internet_vus if s != "inconnu"]
        if mes:
            st = "ok" if len(oks) == len(mes) else "ko" if not oks else "doute"
            V.append(_v("internet", "liaison", "Liaison Internet", st, "haute",
                        "joignable depuis %d/%d chemin(s)" % (len(oks), len(mes)) + (" — en échec : " + "; ".join("%s (%s)" % k for k in kos[:3]) if kos else ""), "agent"))
    else:
        V.append(_v("internet", "liaison", "Liaison Internet", "inconnu", "moyenne", "aucune sonde « chemin de service » récente", "agent",
                    lien=lien_agent(agents[0]["agent_id"]) if agents else None))

    # 5. postes suivis
    clients = entrees.get("clients")
    vus_mac, vus_ip = {}, {}
    for c in clients or []:
        if (c.get("status") or "connected") in ("connected", "online", "") or c.get("status") is None:
            if norm_mac(c.get("mac")):
                vus_mac[norm_mac(c.get("mac"))] = "Nebula"
            if c.get("ip"):
                vus_ip[c["ip"]] = "Nebula"
    for a in agents:
        m = (a.get("latest") or {}).get("plugin:broadcast-probe") or {}
        t = _ts(m.get("at"))
        if m.get("data") and t is not None and now - t <= cfg["fraicheur_min"] * 60 * 3:
            for an in m["data"].get("announcers") or []:
                if norm_mac(an.get("mac")):
                    vus_mac.setdefault(norm_mac(an["mac"]), "annonces (%s)" % a["agent_id"])
                for ip in an.get("ips") or []:
                    vus_ip.setdefault(ip, "annonces (%s)" % a["agent_id"])
    heures = parse_creneaux(cfg["heures"])
    ouvre = any(dt.isoweekday() in c["jours"] and c["debut"] <= dt.strftime("%H:%M") < c["fin"] for c in heures)
    vlan_usage = {v["id"]: usage_a(v["creneaux"], dt) for v in cfg["vlans"]}
    for p in cfg["postes"]:
        ou = vus_mac.get(p["mac"]) or vus_ip.get(p["ip"])
        attendu = p["attendu"] == "toujours" or (p["attendu"] == "heures" and ouvre)
        usage = vlan_usage.get(p["vlan"], "interne")
        if ou:
            st, d = "ok", "présent (vu par %s)" % ou
        elif clients is None and not vus_mac:
            st, d = "inconnu", "aucune source de présence (clients Nebula, annonces réseau)"
        else:
            st, d = ("ko" if attendu else "inconnu"), "absent" + ("" if attendu else " (non attendu à cette heure)" if p["attendu"] == "heures" else " (information)")
        V.append(_v("postes", p["mac"] or p["ip"], "Poste %s" % p["nom"], st, "moyenne" if attendu else "info", d, "nebula/agent", usage))

    # synthèse
    ko = [v for v in V if v["statut"] == "ko"]
    doute = [v for v in V if v["statut"] == "doute"]
    if any(v["severite"] == "haute" for v in ko):
        etat = "panne"
    elif ko or doute:
        etat = "degrade"
    elif all(v["statut"] == "inconnu" for v in V):
        etat = "inconnu"
    else:
        etat = "ok"
    pire = sorted(ko, key=lambda v: SEV_ORDER[v["severite"]])
    resume = {"ok": "Réseau du campus : tout va bien (%d vérification(s))" % sum(1 for v in V if v["statut"] == "ok"),
              "inconnu": "Réseau du campus : rien d'observable (agents et Nebula muets)",
              "degrade": "Réseau du campus dégradé : %s" % "; ".join("%s — %s" % (v["nom"], v["detail"]) for v in (pire or doute)[:3]),
              "panne": "PANNE réseau du campus : %s" % "; ".join("%s — %s" % (v["nom"], v["detail"]) for v in pire[:3])}[etat]
    compte = {s: sum(1 for v in V if v["statut"] == s) for s in STATUTS}
    return {"etat": etat, "resume": resume, "verifs": V, "compte": compte, "at": int(now), "usage_vlans": vlan_usage}


def lignes_alerte(res, site_id, site):
    """Vérifications en échec -> lignes pour alerting.track (une par vérification ; « kind » = usage du créneau)."""
    out = []
    for v in res["verifs"]:
        if v["statut"] != "ko":
            continue
        out.append({"site_id": site_id, "site": site, "id": "veille:" + v["id"], "severity": v["severite"], "element": v["nom"],
                    "message": v["detail"], "action": v.get("lien") or "", "kind": v.get("usage") or "interne"})
    return out


def suggestions(vmap, assets, agents, agent_site=""):
    """Pré-remplissage des réglages : VLAN de la carte Nebula (numéro, nom, SSID, sous-réseau), postes des fiches
    Matériels du campus (MAC ou IP, attendus « info » : à passer en « toujours » / « heures » au choix), agents du site."""
    vlans = []
    for v in (vmap or {}).get("vlans") or []:
        if not v.get("vid"):
            continue
        ssid = next((s.get("name") for s in v.get("ssids") or [] if s.get("enabled", True) and s.get("name")), "")
        vlans.append({"id": int(v["vid"]), "nom": v.get("gateway_interface") or ssid or "VLAN %s" % v["vid"], "connexion": ssid,
                      "sous_reseau": v.get("subnet") or "", "dhcp_attendus": [], "creneaux": [], "internet": not v.get("management")})
    postes, vus = [], set()
    for a in assets or []:
        mac, ip = norm_mac(a.get("mac")), str(a.get("ip") or "").strip()
        cle = mac or ip
        if not cle or cle in vus:
            continue
        vus.add(cle)
        postes.append({"nom": str(a.get("name") or cle)[:60], "mac": mac, "ip": ip, "vlan": None, "attendu": "info"})
    ag = [{"agent_id": a.get("agent_id"), "hostname": a.get("hostname"), "site": a.get("site")} for a in agents or []
          if a.get("agent_id") and (not agent_site or a.get("site") == agent_site)]
    return {"vlans": vlans, "postes": postes[:300], "agents": ag}
