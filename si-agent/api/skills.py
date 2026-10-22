# -*- coding: utf-8 -*-
"""Skills des IA du hub (livraison #827, BACKLOG 132 T4) -- Parc IA > Skills.

Un skill = une consigne réutilisable (prompt système, consignes d'un décideur) rattachée à un usage, versionnée :
chaque enregistrement crée une version, l'historique est conservé, une version ancienne se restaure. Les skills
« priorites-* » sont branchés sur les Priorités de la page d'accueil (préparation, décideur, explication) : le code
impose le format de réponse et les clés du décideur, le skill ne change que la consigne. D'autres skills (créés à la
main) forment la bibliothèque des consignes pour l'assistant, la veille, le harnais. « Essayer » joue un skill sur un
texte avec le modèle de l'usage. Les bancs (#132 T3) les comparent.
Pur et testé : valider, base."""
import json
import re
import time

from flask import Blueprint, jsonify, request

import modeles_stockage as stockage

bp = Blueprint("skills", __name__)
USAGES = ("preparation", "decideur", "explication", "code", "embeddings", "vision", "transcription", "traduction", "assistant", "veille")
TYPES = {"consigne": "consigne (prompt système)", "decision": "consignes d'un décideur (JSON : instructions / critères par question)"}
_ID = re.compile(r"^[a-z0-9][a-z0-9-]{1,62}$")
SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (id TEXT PRIMARY KEY, nom TEXT, usage TEXT, type TEXT, texte TEXT, actif INTEGER DEFAULT 1, notes TEXT,
  version INTEGER, maj REAL, par TEXT, systeme INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS skills_hist (id INTEGER PRIMARY KEY, skill TEXT, version INTEGER, texte TEXT, actif INTEGER, notes TEXT, maj REAL, par TEXT);
"""


def defauts():
    """Skills branchés sur le code (texte = valeur du code tant qu'ils ne sont pas personnalisés)."""
    import priorites as P
    return [
        {"id": "priorites-preparation", "nom": "Priorités : préparation de la liste", "usage": "preparation", "type": "consigne", "texte": P.CONSIGNE_PREPARATION},
        {"id": "priorites-decideur", "nom": "Priorités : décideur urgent / gravité", "usage": "decideur", "type": "decision",
         "texte": json.dumps({k: {x: v[x] for x in ("instructions", "criteria") if x in v} for k, v in P.QUESTIONS.items()}, ensure_ascii=False, indent=1)},
        {"id": "priorites-explication", "nom": "Priorités : explication des urgences", "usage": "explication", "type": "consigne", "texte": P.CONSIGNE_EXPLICATION},
    ]


def valider(b, systeme=None):
    """-> (skill, None) ou (None, erreur). `systeme` : le skill par défaut (id, usage et type imposés)."""
    b = b or {}
    sid = str((systeme or {}).get("id") or b.get("id") or "").strip()
    if not _ID.match(sid):
        return None, "identifiant : minuscules, chiffres, tirets (2 à 63)"
    usage = (systeme or {}).get("usage") or str(b.get("usage") or "")
    typ = (systeme or {}).get("type") or str(b.get("type") or "consigne")
    if usage not in USAGES:
        return None, "usage : " + ", ".join(USAGES)
    if typ not in TYPES:
        return None, "type : " + ", ".join(TYPES)
    texte = str(b.get("texte") or "").strip()
    if not texte or len(texte) > 20000:
        return None, "texte requis (20 000 caractères au plus)"
    if typ == "decision":
        try:
            d = json.loads(texte)
        except ValueError as e:
            return None, "JSON invalide : %s" % e
        if not isinstance(d, dict) or not all(isinstance(v, dict) for v in d.values()):
            return None, "décideur : {question: {instructions, criteria}}"
        if systeme:
            import priorites as P
            inconnues = set(d) - set(P.QUESTIONS)
            if inconnues:
                return None, "questions inconnues : %s (clés imposées par le code : %s)" % (", ".join(sorted(inconnues)), ", ".join(P.QUESTIONS))
    return {"id": sid, "nom": str((systeme or {}).get("nom") or b.get("nom") or sid)[:120], "usage": usage, "type": typ, "texte": texte,
            "actif": bool(b.get("actif", True)), "notes": str(b.get("notes") or "")[:1000], "systeme": 1 if systeme else 0}, None


def cnx():
    c = stockage.cnx()
    c.executescript(SCHEMA)
    return c


def lignes(cur):
    return [dict(r) for r in cur]


def tous(c):
    enr = {r["id"]: r for r in lignes(c.execute("SELECT * FROM skills"))}
    out = []
    for d in defauts():
        r = enr.pop(d["id"], None)
        out.append(dict(d, systeme=1, actif=bool(r["actif"]) if r else True, personnalise=bool(r), version=(r or {}).get("version") or 0,
                        texte=(r or {}).get("texte") or d["texte"], notes=(r or {}).get("notes") or "", maj=(r or {}).get("maj"), par=(r or {}).get("par"),
                        defaut=d["texte"]))
    for r in sorted(enr.values(), key=lambda x: x["id"]):
        out.append(dict(r, actif=bool(r["actif"]), personnalise=True, systeme=bool(r["systeme"])))
    return out


def textes_actifs(ids, c=None):
    """Textes PERSONNALISÉS et actifs de ces skills (un skill non personnalisé laisse le code décider)."""
    c = c or cnx()
    q = ",".join("?" * len(ids))
    return {r["id"]: r["texte"] for r in lignes(c.execute("SELECT id, texte FROM skills WHERE actif=1 AND id IN (%s)" % q, list(ids)))}


def enregistrer(c, s, par):
    r = c.execute("SELECT * FROM skills WHERE id=?", (s["id"],)).fetchone()
    v = (dict(r)["version"] if r else 0) + 1
    t = time.time()
    c.execute("INSERT OR REPLACE INTO skills (id, nom, usage, type, texte, actif, notes, version, maj, par, systeme) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
              (s["id"], s["nom"], s["usage"], s["type"], s["texte"], 1 if s["actif"] else 0, s["notes"], v, t, par, s["systeme"]))
    c.execute("INSERT INTO skills_hist (skill, version, texte, actif, notes, maj, par) VALUES (?,?,?,?,?,?,?)", (s["id"], v, s["texte"], 1 if s["actif"] else 0, s["notes"], t, par))
    c.commit()
    return v


def _par():
    return str(request.headers.get("X-Forwarded-User") or (request.get_json(silent=True) or {}).get("par") or "hub")[:64]


@bp.get("/skills")
def liste():
    return jsonify({"skills": tous(cnx()), "usages": USAGES, "types": TYPES})


@bp.route("/skills", methods=["POST"])
@bp.route("/skills/<sid>", methods=["PUT"])
def ecrire(sid=None):
    b = request.get_json(silent=True) or {}
    sysd = {d["id"]: d for d in defauts()}
    systeme = sysd.get(sid or b.get("id"))
    s, err = valider(dict(b, id=sid or b.get("id")), systeme)
    if err:
        return jsonify({"error": err}), 400
    c = cnx()
    if sid is None and (systeme or c.execute("SELECT 1 FROM skills WHERE id=?", (s["id"],)).fetchone()):
        return jsonify({"error": "skill déjà présent : le modifier"}), 409
    if sid is not None and not systeme and not c.execute("SELECT 1 FROM skills WHERE id=?", (sid,)).fetchone():
        return jsonify({"error": "skill inconnu"}), 404
    v = enregistrer(c, s, _par())
    return jsonify(dict(s, version=v)), 201 if sid is None else 200


@bp.delete("/skills/<sid>")
def supprimer(sid):
    """Skill personnel : supprimé ; skill branché sur le code : retour au texte du code (l'historique reste)."""
    c = cnx()
    n = c.execute("DELETE FROM skills WHERE id=?", (sid,)).rowcount
    c.commit()
    return (jsonify({"ok": True}), 200) if n else (jsonify({"error": "skill inconnu ou non personnalisé"}), 404)


@bp.get("/skills/<sid>/historique")
def historique(sid):
    return jsonify({"versions": lignes(cnx().execute("SELECT version, texte, actif, notes, maj, par FROM skills_hist WHERE skill=? ORDER BY version DESC LIMIT 100", (sid,)))})


@bp.post("/skills/<sid>/restaurer")
def restaurer(sid):
    b = request.get_json(silent=True) or {}
    c = cnx()
    h = c.execute("SELECT texte, notes FROM skills_hist WHERE skill=? AND version=?", (sid, int(b.get("version") or 0))).fetchone()
    cur = c.execute("SELECT * FROM skills WHERE id=?", (sid,)).fetchone()
    if not h or not cur:
        return jsonify({"error": "version inconnue"}), 404
    s = dict(dict(cur), texte=h["texte"], notes="restauration de la version %s" % b.get("version"), actif=bool(cur["actif"]))
    return jsonify({"version": enregistrer(c, s, _par())}), 200


essayer_hook = None   # fourni par app.py : (skill, texte) -> {sortie, modele, duree_s}


@bp.post("/skills/<sid>/essai")
def essai(sid):
    b = request.get_json(silent=True) or {}
    sk = next((x for x in tous(cnx()) if x["id"] == sid), None)
    if not sk:
        return jsonify({"error": "skill inconnu"}), 404
    texte = str(b.get("texte") or "").strip()[:8000]
    if not texte:
        return jsonify({"error": "texte d'essai requis"}), 400
    if b.get("brouillon"):
        sk = dict(sk, texte=str(b["brouillon"]))
    if essayer_hook is None:
        return jsonify({"error": "essai indisponible"}), 503
    try:
        return jsonify(essayer_hook(sk, texte)), 200
    except ValueError as e:
        return jsonify({"error": str(e)[:300]}), 502
