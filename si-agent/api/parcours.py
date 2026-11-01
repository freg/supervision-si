# -*- coding: utf-8 -*-
"""Parcours appris (livraisons #799-#800) : un parcours = des étapes au format QA enregistrées dans le navigateur d'un
hôte (gestes de Freg), paramétrées ({{identifiant}}, {{mot_de_passe}}, {{objet}}…), rattachées à un navigateur, à une
adresse de base et éventuellement à un accès du coffre (tuile « Accès d'équipements ») qui fournit identifiant et mot
de passe AU MOMENT DU JEU -- jamais stockés dans le parcours, masqués dans les commandes une fois exécutées.

Jeu : étapes concrètes envoyées à l'agent de l'hôte (commande « navigateur », action « etapes »), arrêt avant la
première étape qui écrit sauf confirmation explicite. Interprétation d'une demande en langage courant (#800) :
l'assistant du hub choisit le parcours et les valeurs ; le plan est montré avant tout jeu.
Pur : valider, appliquer, catalogue, plan_depuis_interpretation."""
import json
import re
import time

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS parcours (id INTEGER PRIMARY KEY AUTOINCREMENT, nom TEXT NOT NULL UNIQUE, description TEXT, "
    "navigateur TEXT, base_url TEXT, etapes TEXT NOT NULL, parametres TEXT, acces TEXT, cree_le REAL, cree_par TEXT, maj_le REAL, "
    "jeux INTEGER DEFAULT 0, reussites INTEGER DEFAULT 0, dernier_jeu REAL, derniere_commande TEXT)",
)
ACTIONS = ("goto", "click", "fill", "select", "check", "press", "wait", "expect_visible", "expect_text", "expect_url",
           "expect_value", "expect_absent", "screenshot")
PARAM = re.compile(r"\{\{([a-z0-9_]{1,40})\}\}")
NOM_PARAM = re.compile(r"^[a-z0-9_]{1,40}$")
COFFRE = {"identifiant": "username", "mot_de_passe": "password"}


def ensure(conn):
    for s in SCHEMA:
        conn.execute(s)


def valider(p):
    """-> (parcours nettoyé, erreur|None)."""
    if not isinstance(p, dict):
        return None, "objet attendu"
    nom = str(p.get("nom") or "").strip()
    if not nom or len(nom) > 80:
        return None, "nom requis (80 caractères au plus)"
    base = str(p.get("base_url") or "").strip().rstrip("/")
    if base and not re.match(r"^https?://[^/\s]+$", base):
        return None, "adresse de base : http(s)://hôte[:port] attendu"
    et = p.get("etapes")
    if not isinstance(et, list) or not et or len(et) > 200:
        return None, "étapes : liste de 1 à 200"
    propres = []
    for i, s in enumerate(et, 1):
        if not isinstance(s, dict) or s.get("action") not in ACTIONS:
            return None, "étape %d : action inconnue" % i
        st = {k: s[k] for k in ("action", "selector", "value", "note") if s.get(k) not in (None, "")}
        if s.get("ecrit"):
            st["ecrit"] = True
        if s.get("secret"):
            st["secret"] = True
        propres.append(st)
    utilises = set()
    for s in propres:
        utilises.update(PARAM.findall(str(s.get("value") or "")))
    params = []
    for x in p.get("parametres") or []:
        if not isinstance(x, dict) or not NOM_PARAM.match(str(x.get("nom") or "")):
            return None, "paramètre invalide : %s" % (x.get("nom") if isinstance(x, dict) else x)
        secret = bool(x.get("secret")) or x["nom"] == "mot_de_passe"
        params.append({"nom": x["nom"], "note": str(x.get("note") or "")[:120], "secret": secret,
                       "defaut": "" if secret else str(x.get("defaut") or "")[:500]})
    connus = {x["nom"] for x in params}
    for n in sorted(utilises - connus):           # paramètre utilisé mais non décrit : ajouté, sans valeur par défaut
        params.append({"nom": n, "note": "", "secret": n == "mot_de_passe", "defaut": ""})
    acces = str(p.get("acces") or "").strip()[:120]
    nav = str(p.get("navigateur") or "").strip()
    if nav and not re.match(r"^[a-z0-9][a-z0-9-]{0,30}$", nav):
        return None, "navigateur : nom invalide"
    return {"nom": nom, "description": str(p.get("description") or "").strip()[:1000], "navigateur": nav, "base_url": base,
            "etapes": propres, "parametres": params, "acces": acces}, None


def appliquer(parcours, valeurs=None, coffre=None):
    """Étapes concrètes : {{x}} remplacé par valeurs > coffre (identifiant / mot_de_passe) > défaut.
    -> (étapes, manquants[]). Les étapes recevant une valeur secrète sont marquées `secret` (masquées après exécution)."""
    v = {}
    for p in parcours.get("parametres") or []:
        if p.get("defaut"):
            v[p["nom"]] = p["defaut"]
    for k, champ in COFFRE.items():
        if coffre and coffre.get(champ):
            v[k] = coffre[champ]
    v.update({k: str(x) for k, x in (valeurs or {}).items() if NOM_PARAM.match(str(k)) and x not in (None, "")})
    secrets = {p["nom"] for p in parcours.get("parametres") or [] if p.get("secret")} | {"mot_de_passe"}
    out, manquants = [], []
    for s in parcours.get("etapes") or []:
        s = dict(s)
        val = str(s.get("value") or "")
        noms = PARAM.findall(val)
        for n in noms:
            if n not in v:
                if n not in manquants:
                    manquants.append(n)
                continue
            val = val.replace("{{%s}}" % n, v[n])
        if noms:
            s["value"] = val
            if any(n in secrets for n in noms):
                s["secret"] = True
        out.append(s)
    return out, manquants


def catalogue(liste):
    """Parcours -> catalogue pour le modèle : id, nom, description, paramètres NON secrets (le modèle ne voit jamais les
    mots de passe ni les identifiants du coffre)."""
    out = []
    for p in liste:
        out.append({"id": p["id"], "nom": p["nom"], "description": p.get("description") or "", "base_url": p.get("base_url") or "",
                    "parametres": [{"nom": x["nom"], "note": x.get("note") or "", "exemple": x.get("defaut") or ""}
                                   for x in p.get("parametres") or [] if not x.get("secret") and not (p.get("acces") and x["nom"] in COFFRE)]})
    return out


def plan_depuis_interpretation(liste, interp):
    """Réponse du modèle {parcours_id, valeurs, confiance, explication} -> plan contrôlé :
    parcours existant, valeurs limitées aux paramètres non secrets du parcours, manquants calculés."""
    if not isinstance(interp, dict):
        return {"ok": False, "erreur": "réponse du modèle illisible"}
    try:
        pid = int(interp.get("parcours_id"))
    except (TypeError, ValueError):
        return {"ok": False, "erreur": "aucun parcours appris ne correspond à la demande", "explication": str(interp.get("explication") or "")[:500]}
    p = next((x for x in liste if x["id"] == pid), None)
    if not p:
        return {"ok": False, "erreur": "parcours %s inconnu (réponse du modèle)" % pid}
    permis = {x["nom"] for x in p.get("parametres") or [] if not x.get("secret") and not (p.get("acces") and x["nom"] in COFFRE)}
    valeurs = {k: str(v)[:500] for k, v in (interp.get("valeurs") or {}).items() if k in permis and v not in (None, "")}
    _et, manquants = appliquer(p, valeurs, {"username": "x", "password": "x"} if p.get("acces") else None)
    try:
        conf = max(0.0, min(1.0, float(interp.get("confiance"))))
    except (TypeError, ValueError):
        conf = None
    return {"ok": True, "parcours_id": pid, "parcours": p["nom"], "valeurs": valeurs, "manquants": manquants,
            "confiance": conf, "explication": str(interp.get("explication") or "")[:500],
            "ecrit": any(s.get("ecrit") for s in p.get("etapes") or [])}


# -- base -------------------------------------------------------------------------------------------
def _row(r):
    d = dict(r)
    d["etapes"] = json.loads(d["etapes"] or "[]")
    d["parametres"] = json.loads(d.get("parametres") or "[]")
    return d


def lister(conn):
    ensure(conn)
    return [_row(r) for r in conn.execute("SELECT * FROM parcours ORDER BY nom")]


def lire(conn, pid):
    ensure(conn)
    r = conn.execute("SELECT * FROM parcours WHERE id = ?", (pid,)).fetchone()
    return _row(r) if r else None


def enregistrer(conn, p, qui="", pid=None, now=None):
    """-> (parcours, erreur)."""
    ensure(conn)
    v, err = valider(p)
    if err:
        return None, err
    now = now or time.time()
    try:
        if pid:
            n = conn.execute("UPDATE parcours SET nom=?, description=?, navigateur=?, base_url=?, etapes=?, parametres=?, acces=?, maj_le=? WHERE id=?",
                             (v["nom"], v["description"], v["navigateur"], v["base_url"], json.dumps(v["etapes"]), json.dumps(v["parametres"]), v["acces"], now, pid)).rowcount
            if not n:
                return None, "parcours inconnu"
        else:
            pid = conn.execute("INSERT INTO parcours (nom, description, navigateur, base_url, etapes, parametres, acces, cree_le, cree_par, maj_le) "
                               "VALUES (?,?,?,?,?,?,?,?,?,?)", (v["nom"], v["description"], v["navigateur"], v["base_url"], json.dumps(v["etapes"]),
                                                                json.dumps(v["parametres"]), v["acces"], now, (qui or "")[:64], now)).lastrowid
    except Exception as e:  # noqa: BLE001 -- nom en double
        if "UNIQUE" in str(e):
            return None, "un parcours porte déjà ce nom"
        raise
    return lire(conn, pid), None


def supprimer(conn, pid):
    ensure(conn)
    return conn.execute("DELETE FROM parcours WHERE id = ?", (pid,)).rowcount > 0


def noter_jeu(conn, pid, commande_id, now=None):
    conn.execute("UPDATE parcours SET jeux = jeux + 1, dernier_jeu = ?, derniere_commande = ? WHERE id = ?", (now or time.time(), commande_id, pid))
