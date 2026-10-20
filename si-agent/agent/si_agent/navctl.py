# -*- coding: utf-8 -*-
"""Navigateur de l'hôte (livraison #798) -- commande du central `navigateur` {action, …} relayée à l'automate local
(navigateur/automate.py, 127.0.0.1:<port>, jeton /etc/si-agent/navigateur/jeton) :
  etat                                  navigateur joignable, URL et titre de l'onglet courant
  aller {url}                           ouvre l'adresse dans le navigateur visible
  capture {qualite?}                    capture JPEG (base64)
  etapes {etapes[], base_url?, arret_avant_ecriture?}   parcours au format QA, capture à l'échec et à la fin
  enregistrer {etape: debut|etat|fin}  apprentissage (#799) : les gestes faits dans l'écran deviennent des étapes
Le navigateur est celui que l'écran web du hub montre : on voit l'automate travailler et on peut reprendre la main."""
import json
import os
import re

DOSSIER = "/etc/si-agent/navigateur"
ACTIONS = ("etat", "aller", "capture", "etapes", "enregistrer")
MAX_RESULTAT = 3 * 1024 * 1024     # au-delà, les captures intermédiaires sont retirées (le central stocke le résultat)


def lire_config(dossier=DOSSIER):
    try:
        jeton = open(os.path.join(dossier, "jeton")).read().strip()
    except OSError:
        return None
    try:
        port = int(open(os.path.join(dossier, "port")).read().strip() or 8094)
    except (OSError, ValueError):
        port = 8094
    return {"jeton": jeton, "port": port}


def alleger(res, limite=MAX_RESULTAT):
    """Retire les captures intermédiaires si le résultat est trop gros (la capture finale est gardée tant que possible)."""
    if len(json.dumps(res)) <= limite:
        return res
    for r in res.get("resultats") or []:
        if r.pop("capture", None):
            r["capture_retiree"] = True
    if len(json.dumps(res)) > limite:
        res.pop("capture", None)
        res["capture_retiree"] = True
    return res


def run(params, http, dossier=DOSSIER):
    """params de la commande -> {ok, error?, result}. http(methode, chemin, corps, cfg) -> (code, dict) injecté."""
    a = (params or {}).get("action")
    if a not in ACTIONS:
        return {"ok": False, "error": "action inconnue (%s)" % ", ".join(ACTIONS)}
    cfg = lire_config(dossier)
    if not cfg:
        return {"ok": False, "error": "navigateur non installé sur cet hôte (navigateur/installer.sh du dépôt)"}
    if a == "etat":
        code, r = http("GET", "/etat", None, cfg)
    elif a == "capture":
        code, r = http("GET", "/capture?qualite=%d" % max(20, min(90, int(params.get("qualite") or 60))), None, cfg)
    elif a == "aller":
        url = str(params.get("url") or "")
        if not re.match(r"^https?://", url):
            return {"ok": False, "error": "adresse http(s) attendue"}
        code, r = http("POST", "/aller", {"url": url}, cfg)
    elif a == "enregistrer":
        if params.get("etape") not in ("debut", "etat", "fin"):
            return {"ok": False, "error": "enregistrer : etape debut, etat ou fin"}
        code, r = http("POST", "/enregistrer", {"etape": params["etape"]}, cfg)
    else:
        corps = {k: params.get(k) for k in ("etapes", "base_url", "arret_avant_ecriture") if params.get(k) is not None}
        code, r = http("POST", "/etapes", corps, cfg)
    if code != 200:
        return {"ok": False, "error": (r or {}).get("error") or "automate : HTTP %s" % code}
    r = alleger(dict(r))
    return {"ok": bool(r.get("ok", True)), "error": None if r.get("ok", True) else "parcours en échec", "result": r}


def http_local(methode, chemin, corps, cfg, delai=900):
    import urllib.error
    import urllib.request
    req = urllib.request.Request("http://127.0.0.1:%d%s" % (cfg["port"], chemin), method=methode,
                                 data=json.dumps(corps).encode() if corps is not None else None,
                                 headers={"Authorization": "Bearer " + cfg["jeton"], "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=delai) as x:
            return x.status, json.loads(x.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {"error": str(e)}
    except (urllib.error.URLError, OSError, ValueError) as e:
        return 502, {"error": "automate injoignable (conteneur navigateur arrêté ?) : %s" % e}
