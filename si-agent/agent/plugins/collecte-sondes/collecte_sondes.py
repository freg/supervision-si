#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collecte des sondes radio d'un site (livraison #806), sur l'agent du mini-PC qui porte le collecteur du site
(central local `si-collecteur`) : lit l'état du collecteur (dernières mesures de chaque sonde enrôlée) et le remonte au
hub par l'agent du mini-PC, seul chemin sortant du site. Rien ne transite vers le LAN du client.

Par sonde : nom, IP, dernier contact, et la dernière mesure de wifi-monitor (canaux, bornes), rf-spectrum (spectre,
occupation par canal) et wifi-probe (lien, RSSI, chemin -- résumé). Constats : ceux des sondes, préfixés par leur
nom, plus « sonde muette » (aucun contact depuis 5 min). Alimente la tuile « Data RF ».

Usage : collecte_sondes.py [--etat /opt/si-collecteur/si-agent/local-central/data/state.json] [--muette 300]
Réglages de l'hôte : /etc/si-agent/collecte-sondes/args (une « --option valeur » par ligne)."""
import calendar
import json
import os
import sys
import time

ETAT = "/opt/si-collecteur/si-agent/local-central/data/state.json"
DOSSIER = "/etc/si-agent/collecte-sondes"
TACHES = {"plugin:wifi-monitor": "wifi_monitor", "plugin:rf-spectrum": "rf_spectrum", "plugin:wifi-probe": "wifi_probe",
          "plugin:path-probe": "path_probe"}   # #811 : chemin (bail, DNS, HTTP) -- colonne LAN de l'état du réseau de sondes


def args_locaux(argv, chemin):
    try:
        with open(chemin, encoding="utf-8") as fh:
            for ligne in fh:
                ligne = ligne.strip()
                if ligne and not ligne.startswith("#"):
                    argv = argv + ligne.split(None, 1)
    except OSError:
        pass
    return argv


def secondes(iso):
    try:
        return calendar.timegm(time.strptime((iso or "")[:19], "%Y-%m-%dT%H:%M:%S"))
    except ValueError:
        return None


def resume_probe(d):
    """wifi-probe : garde, de chaque bloc (lien, canal, chemin, débits, iperf), les valeurs simples ; le voisinage complet
    et le relevé brut de la station restent sur la sonde."""
    if not isinstance(d, dict):
        return None
    out = {k: d.get(k) for k in ("iface", "error", "summary") if d.get(k) is not None}
    for k in ("link", "channel", "ping", "rates", "iperf"):
        if isinstance(d.get(k), dict):
            out[k] = {kk: vv for kk, vv in d[k].items() if not isinstance(vv, (list, dict))}
    return out


def resume_chemin(d):
    """#811 : path-probe -- état global et, par chemin (interface / connexion), son état ; le détail reste sur la sonde."""
    if not isinstance(d, dict):
        return None
    out = {k: d.get(k) for k in ("error", "summary", "rotated_to") if d.get(k) is not None}
    out["paths"] = [{k: p.get(k) for k in ("iface", "connection", "up_error", "summary") if p.get(k) is not None}
                    for p in d.get("paths") or [] if isinstance(p, dict)][:6]
    return out


def sondes(etat, maintenant, muette=300):
    """État du collecteur -> (sondes, constats)."""
    out, constats = [], []
    mesures = etat.get("measurements") or {}
    for aid, a in sorted((etat.get("agents") or {}).items()):
        m = mesures.get(aid) or {}
        s = {"sonde": a.get("hostname") or aid, "agent_id": aid, "ip": a.get("ip"), "vu": a.get("last_seen"), "site": a.get("site")}
        vu = secondes(a.get("last_seen"))
        s["age_s"] = int(maintenant - vu) if vu else None
        for tache, cle in TACHES.items():
            x = m.get(tache)
            if not x:
                continue
            d = x.get("data") if isinstance(x.get("data"), dict) else {}
            if x.get("error") and not d.get("error"):   # #811 : sonde en échec côté agent (délai dépassé…) -- l'erreur remonte
                d = dict(d, error=str(x["error"])[:300])
            s[cle] = resume_probe(d) if cle == "wifi_probe" else resume_chemin(d) if cle == "path_probe" else d
            s[cle + "_at"] = x.get("at")
            for c in d.get("alerts") or []:
                if isinstance(c, dict) and c.get("code"):
                    constats.append(dict(c, code="%s:%s" % (s["sonde"], c["code"])[:64], message="%s : %s" % (s["sonde"], c.get("message", ""))))
        if s["age_s"] is None or s["age_s"] > muette:
            constats.append({"code": "sonde-muette:%s" % s["sonde"], "severity": "warning",
                             "message": "%s : aucun contact avec le collecteur depuis %s" % (s["sonde"], "toujours" if s["age_s"] is None else "%d min" % (s["age_s"] // 60))})
        out.append(s)
    return out, constats


def main(argv):
    argv = args_locaux(argv, os.path.join(DOSSIER, "args"))
    o = {"etat": ETAT, "muette": 300}
    i = 0
    while i < len(argv):
        k = argv[i].lstrip("-")
        if k in o and i + 1 < len(argv):
            o[k] = int(argv[i + 1]) if k == "muette" else argv[i + 1]
            i += 2
            continue
        i += 1
    try:
        with open(o["etat"], encoding="utf-8") as fh:
            etat = json.load(fh)
    except (OSError, ValueError) as e:
        print(json.dumps({"sondes": [], "alerts": [{"code": "collecteur-illisible", "severity": "warning",
                                                     "message": "état du collecteur illisible (%s) : si-collecteur installé ? %s" % (o["etat"], e)}]}, ensure_ascii=False))
        return 0
    s, c = sondes(etat, time.time(), o["muette"])
    print(json.dumps({"collecteur": o["etat"], "sondes": s, "alerts": c}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
