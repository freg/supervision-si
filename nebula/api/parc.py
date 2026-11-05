# -*- coding: utf-8 -*-
"""Parc des terminaux d'un site (livraison #971) -- logique pure, sans base ni Nebula.

- synthese(eqs)            : comptes par catégorie et par lab des fiches du registre (#960), avec / sans MAC ;
- associer(eqs, vus)       : MAC proposée pour une fiche SANS MAC dont le nom est celui que le terminal annonce sur le réseau
                             (nom DHCP : « E11 AmpIm » <-> « E11-AmpIm ») -- seulement si un seul terminal porte ce nom ;
- inconnus(vus, eqs, ...)  : MAC vues sur le réseau et absentes du registre ;
- baux(sessions, eqs)      : changements d'adresse IP d'une même MAC (renouvellement de bail DHCP sur une autre adresse) et
                             adresses IP passées d'une MAC à une autre, d'après les sessions de l'historique des clients (#872,
                             relève horaire : une session change quand l'IP change).
`vus` : lignes de nebula_client_seen ; `sessions` : lignes de nebula_client_sessions (mac, start, end, ip), triées ou non.
"""
import re
import unicodedata

from reperage import macs_de


def norm_nom(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def synthese(eqs):
    cats, labs, tab = {}, {}, {}
    avec = 0
    for e in eqs:
        c = e.get("categorie") or e.get("role") or "(sans catégorie)"
        lb = e.get("lab") or e.get("local") or "(sans lieu)"
        cats[c] = cats.get(c, 0) + 1
        labs[lb] = labs.get(lb, 0) + 1
        tab.setdefault(c, {})[lb] = tab.get(c, {}).get(lb, 0) + 1
        avec += 1 if e.get("mac") else 0
    ordre = lambda d: sorted(d, key=lambda k: (-d[k], k.lower()))
    return {"total": len(eqs), "avec_mac": avec, "sans_mac": len(eqs) - avec, "categories": [{"nom": c, "n": cats[c]} for c in ordre(cats)],
            "labs": [{"nom": lb, "n": labs[lb]} for lb in ordre(labs)], "tableau": tab}


def associer(eqs, vus):
    """-> [{id, nom, mac, ip, nom_reseau, derniere_vue, par}] pour les fiches sans MAC dont le nom est porté par une seule MAC."""
    deja = {m for e in eqs for m in macs_de(e)}
    par_nom = {}
    for v in vus or []:
        n = norm_nom(v.get("name"))
        if len(n) >= 3 and v.get("mac") not in deja:
            par_nom.setdefault(n, []).append(v)
    noms_fiches = {}
    for e in eqs:
        if not e.get("mac") and e.get("nom"):
            noms_fiches.setdefault(norm_nom(e["nom"]), []).append(e)
    out = []
    for n, fiches in noms_fiches.items():
        cand = {v["mac"]: v for v in par_nom.get(n, [])}
        if len(fiches) != 1 or len(cand) != 1:
            continue                       # nom ambigu d'un côté ou de l'autre : rien d'automatique
        v = next(iter(cand.values()))
        e = fiches[0]
        out.append({"id": e["id"], "nom": e["nom"], "mac": v["mac"], "ip": v.get("ip"), "nom_reseau": v.get("name"),
                    "fabricant": v.get("manufacturer"), "derniere_vue": v.get("last_seen"), "par": "nom réseau"})
    return sorted(out, key=lambda p: p["nom"].lower())


def inconnus(vus, eqs, depuis=0):
    connues = {m for e in eqs for m in macs_de(e)}
    out = [{"mac": v["mac"], "ip": v.get("ip"), "nom_reseau": v.get("name"), "fabricant": v.get("manufacturer"),
            "derniere_vue": v.get("last_seen"), "premiere_vue": v.get("first_seen"),
            "ou": v.get("ssid") or (("%s port %s" % (v.get("device"), v.get("port"))) if v.get("device") else None), "vlan": v.get("vlan")}
           for v in vus or [] if v.get("mac") and v["mac"] not in connues and (v.get("last_seen") or 0) >= depuis]
    return sorted(out, key=lambda x: -(x["derniere_vue"] or 0))


def baux(sessions, eqs):
    """-> {changements: [{mac, nom, ancienne, nouvelle, at}], par_mac: [{mac, nom, n, ips}], ip_partagees: [{ip, macs: [{mac, nom, de, a}]}]}."""
    noms = {m: (e.get("nom") or e.get("ip")) for e in eqs for m in macs_de(e)}
    par_mac = {}
    for s in sorted(sessions or [], key=lambda s: (s["mac"], s["start"])):
        if s.get("ip"):
            par_mac.setdefault(s["mac"], []).append(s)
    changements, resume = [], []
    for mac, ss in par_mac.items():
        n, ips = 0, []
        for a, b in zip(ss, ss[1:]):
            if a["ip"] != b["ip"]:
                changements.append({"mac": mac, "nom": noms.get(mac), "ancienne": a["ip"], "nouvelle": b["ip"], "at": b["start"]})
                n += 1
        for s in ss:
            if s["ip"] not in ips:
                ips.append(s["ip"])
        if n:
            resume.append({"mac": mac, "nom": noms.get(mac), "n": n, "ips": ips})
    par_ip = {}
    for mac, ss in par_mac.items():
        for s in ss:
            x = par_ip.setdefault(s["ip"], {}).setdefault(mac, {"mac": mac, "nom": noms.get(mac), "de": s["start"], "a": s["end"]})
            x["de"], x["a"] = min(x["de"], s["start"]), max(x["a"], s["end"])
    partagees = [{"ip": ip, "macs": sorted(m.values(), key=lambda x: x["de"])} for ip, m in par_ip.items() if len(m) > 1]
    return {"changements": sorted(changements, key=lambda c: -c["at"]), "par_mac": sorted(resume, key=lambda r: (-r["n"], r["mac"])),
            "ip_partagees": sorted(partagees, key=lambda p: -max(x["a"] for x in p["macs"]))}


def pieces_des_bornes(eqs):
    """Bornes et commutateurs inscrits au registre -> {nom normalisé: pièce} (champ local, sinon lab)."""
    return {norm_nom(e["nom"]): (e.get("local") or e.get("lab")) for e in eqs if e.get("nom") and (e.get("local") or e.get("lab"))}


def deplacements(sessions, eqs, limite=500):
    """Localisation dans le temps d'un terminal inscrit : à chaque session (#872), le SSID, la borne (ou le port du commutateur) et
    la pièce de cette borne sur le plan (registre). -> {par_mac: {mac: [{de, a, ip, ssid, borne, port, vlan, piece}]},
    changements: [{mac, nom, at, de, vers}]} -- un changement = autre pièce, autre SSID ou autre borne."""
    noms = {m: (e.get("nom") or e.get("ip")) for e in eqs for m in macs_de(e)}
    pieces = pieces_des_bornes(eqs)
    par_mac, changements = {}, []
    for s in sorted(sessions or [], key=lambda s: (s["mac"], s["start"])):
        if s["mac"] not in noms:
            continue
        lieu = {"de": s["start"], "a": s["end"], "ip": s.get("ip"), "ssid": s.get("ssid"), "borne": s.get("device"), "port": s.get("port"),
                "vlan": s.get("vlan"), "piece": pieces.get(norm_nom(s.get("device")))}
        par_mac.setdefault(s["mac"], []).append(lieu)
    cle = lambda l: (l["piece"] or l["borne"], l["ssid"])
    for mac, ls in par_mac.items():
        for a, b in zip(ls, ls[1:]):
            if cle(a) != cle(b):
                txt = lambda l: " · ".join(x for x in (l["piece"], l["ssid"], None if l["piece"] else l["borne"]) if x) or "?"
                changements.append({"mac": mac, "nom": noms.get(mac), "at": b["de"], "de": txt(a), "vers": txt(b)})
    return {"par_mac": {m: ls[-limite:] for m, ls in par_mac.items()}, "changements": sorted(changements, key=lambda c: -c["at"])[:limite]}
