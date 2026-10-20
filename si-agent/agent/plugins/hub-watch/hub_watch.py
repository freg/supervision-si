#!/usr/bin/env python3
"""Sonde hub-watch (#793) : garde du hub depuis un autre hôte, avec alerte qui ne dépend PAS du hub.
Le hub ne peut pas signaler sa propre panne : cette sonde tourne sur un autre agent (ex. un Proxmox du LAN), teste les URL
du hub et du central, et après --echecs passages en échec de suite :
  - courriel par le sendmail de l'hôte (un Proxmox a toujours postfix) ;
  - SMS direct par la passerelle (--sms-url-fichier : URL avec {numero} et {texte}, ex. service « Post/Get » du TRB140,
    qui ne passe pas par le relais hébergé sur l'hôte du hub) ;
puis rappel toutes les heures tant que ça dure, et message « rétabli » au retour.
« Répond » = réponse HTTP < 500 (une page de connexion ou un 401 prouvent que le service tourne).
Sortie JSON : {at, urls[], panne, alerts[], error}. État entre deux passages : /var/lib/si-agent/hub-watch.json."""
import json
import os
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DOSSIER = "/etc/si-agent/hub-watch"
ETAT = "/var/lib/si-agent/hub-watch.json"
RAPPEL_S = 3600


def args_locaux(argv, chemin):
    """Arguments de l'hôte (« --option valeur » par ligne, # = commentaire) ajoutés à ceux du catalogue."""
    try:
        for l in open(chemin, encoding="utf-8"):
            l = l.strip()
            if l and not l.startswith("#"):
                o, _, v = l.partition(" ")
                argv = argv + ([o, v.strip()] if v.strip() else [o])
    except OSError:
        pass
    return argv


def _ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE          # CA interne du hub : on teste la disponibilité, pas le certificat
    return c


def tester(url, timeout=15):
    """-> (ok, détail). ok = réponse HTTP < 500 dans le délai."""
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "si-agent hub-watch"}), timeout=timeout, context=_ctx()) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    except (urllib.error.URLError, socket.timeout, OSError) as e:
        return False, "injoignable : %s" % str(getattr(e, "reason", e))[:120]
    d = "HTTP %d en %.1f s" % (code, time.monotonic() - t0)
    return code < 500, d


def decider(etat, panne_urls, echecs_max, maintenant):
    """Machine d'état : -> (nouvel_etat, message à envoyer ou None). etat = {echecs, en_panne, depuis, derniere_alerte}."""
    e = dict({"echecs": 0, "en_panne": False, "depuis": None, "derniere_alerte": 0}, **(etat or {}))
    if not panne_urls:
        msg = None
        if e["en_panne"]:
            msg = ("RETABLI", "hub de nouveau joignable (panne depuis %s)" % time.strftime("%d/%m %H:%M", time.localtime(e["depuis"] or maintenant)))
        return {"echecs": 0, "en_panne": False, "depuis": None, "derniere_alerte": 0}, msg
    e["echecs"] += 1
    if e["echecs"] < echecs_max:
        return e, None
    if not e["en_panne"]:
        e.update(en_panne=True, depuis=maintenant, derniere_alerte=maintenant)
        return e, ("ALERTE", "hub injoignable : " + " ; ".join(panne_urls))
    if maintenant - (e["derniere_alerte"] or 0) >= RAPPEL_S:
        e["derniere_alerte"] = maintenant
        return e, ("RAPPEL", "hub toujours injoignable depuis %s : %s" % (time.strftime("%d/%m %H:%M", time.localtime(e["depuis"])), " ; ".join(panne_urls)))
    return e, None


def courriel(dest, exp, sujet, texte, run=subprocess.run):
    corps = "From: %s\nTo: %s\nSubject: %s\nMIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\n\n%s\n" % (exp, dest, sujet, texte)
    for sm in ("/usr/sbin/sendmail", "/usr/lib/sendmail"):
        if os.path.exists(sm):
            r = run([sm, "-t", "-f", exp], input=corps.encode("utf-8"), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            return r.returncode == 0, "sendmail code %d" % r.returncode
    return False, "pas de sendmail sur cet hôte"


def sms(modele, numero, texte, ouvrir=urllib.request.urlopen):
    url = modele.replace("{numero}", urllib.parse.quote(numero)).replace("{texte}", urllib.parse.quote(texte[:150]))
    try:
        with ouvrir(url, timeout=20, context=_ctx()) as r:
            return r.status == 200, "HTTP %d" % r.status
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)[:120]


def collect(argv, tester=tester, envoyer_courriel=courriel, envoyer_sms=sms, etat_chemin=ETAT, maintenant=None):
    def arg(n, d=None):
        return argv[argv.index(n) + 1] if n in argv[:-1] else d
    maintenant = maintenant or time.time()
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "urls": [], "panne": False, "alerts": [], "error": None, "envois": []}
    cibles = [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "--url"]
    if not cibles:
        out["error"] = "aucune --url (ex. --url hub=https://hôte-du-hub:6443/)"
        return out
    panne = []
    for c in cibles:
        nom, _, url = c.partition("=") if "=" in c else (c, "", c)
        ok, d = tester(url)
        out["urls"].append({"nom": nom, "url": url, "ok": ok, "detail": d})
        if not ok:
            panne.append("%s %s" % (nom, d))
    try:
        etat = json.load(open(etat_chemin, encoding="utf-8"))
    except (OSError, ValueError):
        etat = {}
    etat, msg = decider(etat, panne, int(arg("--echecs", "2")), maintenant)
    out["panne"] = etat["en_panne"]
    if msg:
        sujet = "[%s] hub de supervision (%s)" % (msg[0], socket.gethostname())
        if arg("--courriel"):
            out["envois"].append(("courriel",) + envoyer_courriel(arg("--courriel"), arg("--expediteur", "root@" + socket.gethostname()), sujet, msg[1]))
        if arg("--sms-url-fichier") and arg("--numero"):
            try:
                modele = open(arg("--sms-url-fichier"), encoding="utf-8").read().strip()
                out["envois"].append(("sms",) + envoyer_sms(modele, arg("--numero"), "%s %s" % (msg[0], msg[1])))
            except OSError as exc:
                out["envois"].append(("sms", False, "URL illisible : %s" % exc))
    try:
        os.makedirs(os.path.dirname(etat_chemin), exist_ok=True)
        json.dump(etat, open(etat_chemin, "w", encoding="utf-8"))
    except OSError as exc:
        out["error"] = "état non enregistré : %s" % exc
    if panne:
        out["alerts"].append({"code": "hub-watch-down", "severity": "critical" if etat["en_panne"] else "warning",
                              "message": "hub injoignable depuis cet hôte : " + " ; ".join(panne)[:250]})
    if any(not e[1] for e in out["envois"]):
        out["alerts"].append({"code": "hub-watch-alert-failed", "severity": "critical",
                              "message": "alerte hors hub NON envoyée : " + " ; ".join("%s %s" % (e[0], e[2]) for e in out["envois"] if not e[1])})
    return out


if __name__ == "__main__":
    print(json.dumps(collect(args_locaux(sys.argv[1:], DOSSIER + "/args")), ensure_ascii=False))
