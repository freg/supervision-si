# -*- coding: utf-8 -*-
"""Apprentissage des IA du hub (livraison #828, BACKLOG 132 T5) -- Parc IA > Apprentissage.

Raisonnable et cadré : pas d'entraînement complet, une adaptation légère (LoRA / QLoRA) d'un petit modèle (≤ 8 B) pour
le DÉCIDEUR des priorités, apprise sur NOS décisions humaines :
  - jeu de données : articles de veille décidés par une personne -- rejetés (règle de rejet) ou « non applicable » ->
    non urgent, gravité faible ; « à traiter / en cours / traité » posé par une personne -> urgent si l'article touche
    un de nos actifs ou une faille exploitée (KEV), gravité d'après la priorité vuln-api (P1 critique … P4 faible) ;
    les décisions automatiques et les articles non décidés sont exclus ;
  - même entrée que la production (états des priorités, consigne du décideur et skill actif) ; sortie au format attendu ;
  - découpage stable entraînement / test (10 % d'après l'identifiant de l'article) ;
  - entraînements : registre (modèle de base, hôte, état, modèle produit) et ÉVALUATION sur la part « test » avec le
    modèle produit (accord urgent / gravité), à comparer au modèle de production avant toute mise en service.
L'entraînement lui-même se lance sur un hôte GPU NVIDIA avec le kit si-agent/tools/apprentissage/ (pas de lien :
opération manuelle) ; les données ne quittent jamais nos machines.
Pur et testé : etiquette, candidat, exemple, part, mesurer."""
import hashlib
import json
import threading
import time
import urllib.request

from flask import Blueprint, Response, jsonify, request

import modeles_stockage as stockage
import priorites as P

bp = Blueprint("apprentissage", __name__)
GRAVITE_PAR_PRIORITE = {"P1": "critique", "P2": "haute", "P3": "moyenne", "P4": "faible"}
SCHEMA = """
CREATE TABLE IF NOT EXISTS entrainements (id INTEGER PRIMARY KEY, nom TEXT, modele_base TEXT, hote TEXT, statut TEXT, modele_produit TEXT,
  jeu TEXT, evaluation TEXT, notes TEXT, cree REAL, maj REAL, par TEXT);
"""
STATUTS = ("prevu", "en_cours", "termine", "abandonne")


def etiquette(a):
    """Décision humaine d'un article -> {"urgent": bool, "gravite": label} ; None si non décidé par une personne."""
    imp = a.get("impacts") or {}
    if a.get("rejet") or a.get("statut") == "non_applicable":
        if a.get("statut") == "non_applicable" and (a.get("statut_par") or "veille") == "veille":
            return None
        return {"urgent": False, "gravite": "faible"}
    if a.get("statut") in ("a_traiter", "en_cours", "traite") and (a.get("statut_par") or "veille") != "veille":
        urgent = bool(imp.get("actifs")) or bool(a.get("kev"))
        return {"urgent": urgent, "gravite": GRAVITE_PAR_PRIORITE.get(imp.get("priorite"), "moyenne" if urgent else "faible")}
    return None


def candidat(a):
    imp = a.get("impacts") or {}
    return {"id": "veille:%s" % a.get("id"), "source": "veille cyber", "titre": a.get("titre"), "genre": a.get("niveau") or "veille",
            "severite": "critique" if a.get("niveau") in ("alerte", "exploitee") or imp.get("priorite") == "P1" else "attention",
            "depuis": P._iso(a.get("publie")), "dernier": P._iso(a.get("publie")), "nb": 1, "actifs": imp.get("actifs") or [], "kev": a.get("kev")}


def part(aid, test_pct=10):
    return "test" if int(hashlib.sha256(str(aid).encode()).hexdigest(), 16) % 100 < test_pct else "train"


def exemple(a, questions, lab):
    import decideur
    etat = P.etats([candidat(a)])[0]
    rep = [{"urgent": 0.9 if lab["urgent"] else 0.1, "gravite": lab["gravite"]}]
    return {"id": a.get("id"), "part": part(a.get("id")), "etat": etat, "attendu": lab,
            "messages": [{"role": "user", "content": decideur.prompt_llm([etat], questions)},
                         {"role": "assistant", "content": json.dumps(rep, ensure_ascii=False)}]}


def construire(articles, questions):
    ex = []
    for a in articles or []:
        lab = etiquette(a)
        if lab:
            ex.append(exemple(a, questions, lab))
    stats = {"exemples": len(ex), "train": sum(1 for e in ex if e["part"] == "train"), "test": sum(1 for e in ex if e["part"] == "test"),
             "urgents": sum(1 for e in ex if e["attendu"]["urgent"]), "gravites": {}}
    for e in ex:
        stats["gravites"][e["attendu"]["gravite"]] = stats["gravites"].get(e["attendu"]["gravite"], 0) + 1
    return ex, stats


def mesurer(exemples, reponses):
    """Accord du modèle avec les décisions humaines sur la part test."""
    n = ok_u = ok_g = valides = 0
    for e, r in zip(exemples, reponses):
        n += 1
        if not r:
            continue
        valides += 1
        ok_u += (r["urgent"]["noul"] >= 0.5) == e["attendu"]["urgent"]
        ok_g += (r.get("gravite") or {}).get("label") == e["attendu"]["gravite"]
    return {"n": n, "valides": valides, "accord_urgent": round(ok_u / float(valides), 3) if valides else None,
            "accord_gravite": round(ok_g / float(valides), 3) if valides else None}


def questions_courantes():
    c = P.skills_actifs().get("priorites-decideur")
    try:
        return P.questions_effectives(json.loads(c)) if c else P.QUESTIONS
    except ValueError:
        return P.QUESTIONS


def articles_decides(jours=365):
    import os
    url = os.environ.get("VULN_API_URL", "http://vuln-api:5000").rstrip("/") + "/veille/articles?jours=%d&rejetes=avec&limite=2000" % int(jours)
    with urllib.request.urlopen(url, timeout=60) as r:  # noqa: S310 (URL interne)
        return json.load(r).get("articles") or []


source_articles = articles_decides   # remplaçable (tests)


def cnx():
    c = stockage.cnx()
    c.executescript(SCHEMA)
    return c


def _lire(r):
    d = dict(r)
    for k in ("jeu", "evaluation"):
        d[k] = json.loads(d[k]) if d.get(k) else None
    return d


@bp.get("/apprentissage/jeu")
def jeu():
    try:
        jours = int(request.args.get("jours") or 365)
        ex, stats = construire(source_articles(jours), questions_courantes())
    except Exception as e:  # noqa: BLE001 -- vuln-api absente
        return jsonify({"error": "veille injoignable : %s" % str(e)[:200]}), 502
    p = request.args.get("part")
    if p in ("train", "test"):
        ex = [e for e in ex if e["part"] == p]
    if request.args.get("format") == "jsonl":
        corps = "\n".join(json.dumps({"messages": e["messages"]}, ensure_ascii=False) for e in ex) + "\n"
        return Response(corps, mimetype="application/x-ndjson",
                        headers={"Content-Disposition": "attachment; filename=decideur-%s-%s.jsonl" % (p or "tout", time.strftime("%Y%m%d"))})
    return jsonify({"stats": stats, "apercu": [{k: e[k] for k in ("id", "part", "etat", "attendu")} for e in ex[:30]]})


@bp.get("/apprentissage/entrainements")
def entrainements():
    return jsonify({"entrainements": [_lire(r) for r in cnx().execute("SELECT * FROM entrainements ORDER BY id DESC")], "statuts": STATUTS})


@bp.route("/apprentissage/entrainements", methods=["POST"])
@bp.route("/apprentissage/entrainements/<int:eid>", methods=["PUT"])
def entrainement_ecrire(eid=None):
    b = request.get_json(silent=True) or {}
    nom, base = str(b.get("nom") or "").strip()[:120], str(b.get("modele_base") or "").strip()[:200]
    statut = b.get("statut") or "prevu"
    if not nom or not base:
        return jsonify({"error": "nom et modèle de base requis"}), 400
    if statut not in STATUTS:
        return jsonify({"error": "statut : " + ", ".join(STATUTS)}), 400
    c, t, par = cnx(), time.time(), str(b.get("par") or request.headers.get("X-Forwarded-User") or "hub")[:64]
    vals = (nom, base, str(b.get("hote") or "")[:64], statut, str(b.get("modele_produit") or "")[:200], json.dumps(b.get("jeu")) if b.get("jeu") else None,
            str(b.get("notes") or "")[:2000])
    if eid is None:
        cur = c.execute("INSERT INTO entrainements (nom, modele_base, hote, statut, modele_produit, jeu, notes, cree, maj, par) VALUES (?,?,?,?,?,?,?,?,?,?)", vals + (t, t, par))
        eid = cur.lastrowid
    elif not c.execute("UPDATE entrainements SET nom=?, modele_base=?, hote=?, statut=?, modele_produit=?, jeu=COALESCE(?, jeu), notes=?, maj=?, par=? WHERE id=?",
                       vals + (t, par, eid)).rowcount:
        return jsonify({"error": "entraînement inconnu"}), 404
    c.commit()
    return jsonify(_lire(c.execute("SELECT * FROM entrainements WHERE id=?", (eid,)).fetchone())), 200


evaluer_lot = None   # (etats, questions, modele) -> réponses ; fourni par app.py (décideur), remplaçable (tests)


@bp.post("/apprentissage/entrainements/<int:eid>/evaluer")
def evaluer(eid):
    """Évalue le modèle produit (ou un modèle donné) sur la part test, en tâche de fond ; résultat dans l'entraînement."""
    b = request.get_json(silent=True) or {}
    c = cnx()
    r = c.execute("SELECT * FROM entrainements WHERE id=?", (eid,)).fetchone()
    if not r:
        return jsonify({"error": "entraînement inconnu"}), 404
    modele = str(b.get("modele") or r["modele_produit"] or "")
    if not modele:
        return jsonify({"error": "modèle produit inconnu : le renseigner (nom Ollama)"}), 400
    try:
        ex, _ = construire(source_articles(365), questions_courantes())
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": "veille injoignable : %s" % str(e)[:200]}), 502
    test = [e for e in ex if e["part"] == "test"][:200]
    if not test:
        return jsonify({"error": "aucun exemple de test : il faut des articles décidés (statuts, rejets)"}), 409

    def travail():
        t0 = time.time()
        try:
            reps = evaluer_lot([e["etat"] for e in test], questions_courantes(), modele)
            res = dict(mesurer(test, reps), modele=modele, at=time.time(), duree_s=round(time.time() - t0, 1))
        except Exception as e:  # noqa: BLE001
            res = {"modele": modele, "at": time.time(), "erreur": str(e)[:300]}
        cc = cnx()
        cc.execute("UPDATE entrainements SET evaluation=?, maj=? WHERE id=?", (json.dumps(res), time.time(), eid))
        cc.commit()
    threading.Thread(target=travail, daemon=True).start()
    return jsonify({"lance": True, "exemples": len(test), "modele": modele}), 202
