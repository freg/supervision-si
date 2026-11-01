# -*- coding: utf-8 -*-
"""#800 : relais si-htop vu du central -- lecture de son état (HTTP interne, jeton) pour la tuile « htop » et passage
de ses constats dans le journal d'événements (donc les notifications) : un constat apparu -> « htop-alert » (sa
gravité), disparu -> « htop-recovered » (info). Un constat qui persiste n'est pas répété. Pur sauf `lire`."""
import json
import urllib.error
import urllib.parse
import urllib.request


def lire(base, jeton, chemin, timeout=5):
    """GET base + chemin -> (code, objet)."""
    if not base:
        return 503, {"error": "relais htop non configuré (HTOP_RELAIS_URL)"}
    q = urllib.request.Request(base.rstrip("/") + chemin, headers={"X-Htop-Token": jeton or ""})
    try:
        with urllib.request.urlopen(q, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except ValueError:
            return e.code, {"error": "relais htop : HTTP %d" % e.code}
    except (OSError, ValueError) as e:
        return 502, {"error": "relais htop injoignable : %s" % e}


def chemin_hote(nom):
    return "/hote/" + urllib.parse.quote(str(nom or "")[:64], safe="")


def transitions(avant, constats):
    """avant : {code: [gravité, message]} ; constats : liste du relais -> (événements [(genre, gravité, message, détails)], après)."""
    apres, evs = {}, []
    for a in constats or []:
        if isinstance(a, dict) and a.get("code") and a.get("severity") in ("warning", "critical"):
            apres[str(a["code"])[:96]] = [a["severity"], str(a.get("message") or "")[:300]]
    for code, (sev, msg) in sorted(apres.items()):
        p = (avant or {}).get(code)
        if not p or p[0] != sev:
            evs.append(("htop-alert", sev, msg, {"code": code, "hote": code.split(":")[1] if ":" in code else "", "aggravation": bool(p)}))
    for code, (sev, msg) in sorted((avant or {}).items()):
        if code not in apres:
            evs.append(("htop-recovered", "info", "fin : %s" % msg, {"code": code, "hote": code.split(":")[1] if ":" in code else ""}))
    return evs, apres
