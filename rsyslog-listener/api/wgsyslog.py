"""#895 : sessions WireGuard reconstituées à partir du syslog d'un routeur MikroTik (sujet « wireguard », niveaux info et
debug), en remplacement de la sonde wireguard (API RouterOS non ouverte par l'administrateur).

Lignes RouterOS observées (deux formes : avec en-tête bsd-syslog, l'interface est alors l'application ; sans en-tête,
le message commence par « wireguard,info <interface>: ») :
  [<nom du pair>] <clé publique>: Receiving handshake initiation from peer (ip:port)
  … Sending handshake response to peer (ip:port)                -> poignée de main réussie (pair initiateur)
  … Receiving handshake response from peer (ip:port)            -> poignée de main réussie (routeur initiateur)
  … Sending handshake initiation to peer (ip:port)              -> le routeur relance
  … Handshake for peer did not complete after 5 seconds, retrying (try N)    -> échec
  … Retrying handshake with peer because we stopped hearing back after 15 seconds -> perte de contact
  … Receiving keepalive packet from peer (ip:port)              -> activité
  … Zeroing out all keys for peer, since we haven't received a new one in 540 seconds -> fin de session
Une session s'ouvre à la première poignée de main réussie, se prolonge à chaque réussite / maintien, et se ferme à
l'effacement des clés ou après `inactif_s` sans réussite (fin = dernière activité). Doublons (même évènement reçu sous
les deux formes à moins de 2 s) écartés.
"""
import re

LIGNE = re.compile(r"\[(?P<nom>[^\]]*)\] (?P<cle>[A-Za-z0-9+/]{42,44}=): (?P<ev>.*)$")
IFACE = re.compile(r"^(?:[a-z0-9_-]+(?:,[a-z0-9_-]+)*) (?P<iface>[^\s:]+): ")
ADR = re.compile(r"\(((?:\d{1,3}\.){3}\d{1,3}|\[[0-9a-fA-F:]+\]):(\d+)\)")
ESSAI = re.compile(r"\(try (\d+)\)")


def evenement(m):
    """Message conservé (journal.py) -> évènement WireGuard ou None."""
    txt = m.get("msg") or ""
    l = LIGNE.search(txt)
    if not l:
        return None
    iface = m.get("app") or ""
    if not iface or iface.startswith("wireguard,") or "," in iface:
        x = IFACE.match(txt)
        iface = x.group("iface") if x else (iface or "wireguard")
    ev = l.group("ev")
    a = ADR.search(ev)
    if "Sending handshake response" in ev or "Receiving handshake response" in ev:
        type_ = "reussite"
    elif "Receiving keepalive" in ev or "Receiving handshake initiation" in ev:
        type_ = "activite"
    elif "did not complete" in ev:
        type_ = "echec"
    elif "stopped hearing back" in ev:
        type_ = "perte"
    elif "Zeroing out all keys" in ev:
        type_ = "fin"
    elif "Sending handshake initiation" in ev or "Sending keepalive" in ev:
        type_ = "relance"
    else:
        type_ = "autre"
    e = ESSAI.search(ev)
    return {"t": m["t"], "routeur": m.get("hote") or m.get("ip") or "", "ip_routeur": m.get("ip") or "", "interface": iface,
            "nom": l.group("nom"), "cle": l.group("cle"), "type": type_, "origine": "%s:%s" % (a.group(1), a.group(2)) if a else None,
            "essai": int(e.group(1)) if e else None, "texte": ev[:300]}


def sessions(messages, maintenant, inactif_s=300):
    """messages (plus récents d'abord, comme journal.chercher) -> {pairs: [état par pair], sessions: [...]}."""
    evs, vus = [], {}
    for m in sorted(messages, key=lambda x: x.get("t") or 0):
        e = evenement(m)
        if e is None:
            continue
        cle_dbl = (e["ip_routeur"], e["cle"], e["texte"])
        if cle_dbl in vus and e["t"] - vus[cle_dbl] < 2:
            continue
        vus[cle_dbl] = e["t"]
        evs.append(e)
    pairs, ouvertes, closes = {}, {}, []

    def fermer(k, fin):
        s = ouvertes.pop(k)
        s.update(fin=fin, duree_s=int(fin - s["debut"]), en_cours=False)
        closes.append(s)
    for e in evs:
        k = (e["ip_routeur"], e["interface"], e["cle"])
        p = pairs.setdefault(k, {"routeur": e["routeur"], "interface": e["interface"], "nom": e["nom"], "cle": e["cle"], "derniere_reussite": None,
                                 "derniere_activite": None, "origine": None, "origines": [], "echecs": 0, "pertes": 0, "relances": 0})
        p["nom"] = e["nom"] or p["nom"]
        if e["origine"]:
            p["origine"] = e["origine"]
            ip = e["origine"].rsplit(":", 1)[0]
            if ip not in p["origines"]:
                p["origines"].append(ip)
        s = ouvertes.get(k)
        if s is not None and e["t"] - s["_derniere"] > inactif_s:
            fermer(k, s["_derniere"])
            s = None
        if e["type"] in ("reussite", "activite"):
            p["derniere_activite"] = e["t"]
            if e["type"] == "reussite":
                p["derniere_reussite"] = e["t"]
            if s is None and e["type"] == "reussite":
                s = ouvertes[k] = {"routeur": e["routeur"], "interface": e["interface"], "nom": e["nom"], "cle": e["cle"], "debut": e["t"],
                                   "origine": e["origine"], "origines": [], "echecs": 0, "pertes": 0, "_derniere": e["t"]}
            if s is not None:
                s["_derniere"] = e["t"]
        elif e["type"] == "echec":
            p["echecs"] += 1
            if s is not None:
                s["echecs"] += 1
        elif e["type"] == "perte":
            p["pertes"] += 1
            if s is not None:
                s["pertes"] += 1
        elif e["type"] == "relance":
            p["relances"] += 1
        elif e["type"] == "fin" and s is not None:
            fermer(k, s["_derniere"])
            s = None
        if s is not None and e["origine"]:
            ip = e["origine"].rsplit(":", 1)[0]
            if ip not in s["origines"]:
                s["origines"].append(ip)
            s["origine"] = e["origine"]
    for k, s in list(ouvertes.items()):
        if maintenant - s["_derniere"] > inactif_s:
            fermer(k, s["_derniere"])
        else:
            s.update(fin=None, duree_s=int(maintenant - s["debut"]), en_cours=True)
            closes.append(ouvertes.pop(k))
    for s in closes:
        s.pop("_derniere", None)
    for p in pairs.values():
        p["connecte"] = bool(p["derniere_activite"] and maintenant - p["derniere_activite"] <= 180)
    return {"pairs": sorted(pairs.values(), key=lambda p: (not p["connecte"], p["nom"])),
            "sessions": sorted(closes, key=lambda s: -s["debut"])}
