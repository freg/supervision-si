# -*- coding: utf-8 -*-
"""Relais vers le collecteur du site (livraison #807) -- commande du central `collecteur`, exécutée par l'agent du
mini-PC qui porte le collecteur (si-collecteur, 127.0.0.1 seulement) :
  {action: "sondes"}                                    sondes enrôlées au collecteur (nom, IP, dernier contact)
  {action: "commande", sonde, type, params, attendre_s}  dépose une commande pour une sonde et attend son résultat
                                                        (relève toutes les 5 s ; 90 s au plus)
Le hub n'atteint ainsi les sondes du site que par l'agent du mini-PC : rien ne transite vers le LAN du client."""
import json
import os
import re
import ssl
import time
import urllib.error
import urllib.request

ENV = "/etc/si-collecteur/env"
TYPES = ("wifi_config", "collect_now", "run_plugin", "enable_plugin", "disable_plugin")


def port_collecteur(env=ENV):
    try:
        m = re.search(r"^SI_PORT=(\d+)", open(env, encoding="utf-8").read(), re.M)
        return int(m.group(1)) if m else 6444
    except OSError:
        return 6444


def http_local(methode, chemin, corps=None, port=None):
    """Requête au collecteur local (certificat auto-signé du collecteur : vérification inutile sur 127.0.0.1)."""
    ctx = ssl.create_default_context()
    ctx.check_hostname, ctx.verify_mode = False, ssl.CERT_NONE
    url = "https://127.0.0.1:%d%s" % (port or port_collecteur(), chemin)
    data = json.dumps(corps).encode() if corps is not None else None
    req = urllib.request.Request(url, data=data, method=methode, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15, context=ctx) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}
    except (OSError, ValueError) as e:
        return 0, {"error": "collecteur injoignable (si-collecteur installé et démarré ?) : %s" % e}


def run(params, http=http_local, pause=time.sleep, horloge=time.time):
    p = params or {}
    a = p.get("action") or "sondes"
    st, etat = http("GET", "/ui/state")
    if st != 200:
        return {"ok": False, "error": etat.get("error") or "collecteur : HTTP %s" % st}
    agents = {x.get("agent_id"): x for x in etat.get("agents") or []}
    if a == "sondes":
        return {"ok": True, "result": {"sondes": [{"agent_id": k, "sonde": v.get("hostname"), "ip": v.get("ip"), "vu": v.get("last_seen"),
                                                   "version": v.get("config_version")} for k, v in sorted(agents.items())]}}
    if a != "commande":
        return {"ok": False, "error": "action inconnue : %s (sondes, commande)" % a}
    sonde, typ = p.get("sonde"), p.get("type")
    if sonde not in agents:
        noms = {v.get("hostname"): k for k, v in agents.items()}
        sonde = noms.get(sonde, sonde)
    if sonde not in agents:
        return {"ok": False, "error": "sonde inconnue du collecteur : %s" % p.get("sonde")}
    if typ not in TYPES:
        return {"ok": False, "error": "type non relayé : %s (%s)" % (typ, ", ".join(TYPES))}
    st, c = http("POST", "/ui/command", {"agent_id": sonde, "type": typ, "params": p.get("params") or {}})
    if st != 201:
        return {"ok": False, "error": c.get("error") or "collecteur : dépôt refusé (HTTP %s)" % st}
    fin = horloge() + min(int(p.get("attendre_s") or 90), 90)
    while horloge() < fin:
        pause(5)
        st, etat = http("GET", "/ui/state")
        for x in etat.get("commands") or []:
            if x.get("id") == c.get("id") and x.get("status") != "pending":
                r = x.get("result") or {}
                return {"ok": x.get("status") == "done", "error": r.get("error"), "result": {"sonde": agents[sonde].get("hostname"), "commande": c.get("id"),
                                                                                              "resultat": r.get("result", r)}}
    return {"ok": False, "error": "la sonde n'a pas relevé la commande %s en %d s (hors ligne ?) ; elle l'exécutera à son retour" % (c.get("id"), min(int(p.get("attendre_s") or 90), 90)),
            "result": {"commande": c.get("id")}}
