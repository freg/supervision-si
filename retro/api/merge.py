# -*- coding: utf-8 -*-
"""Comparaison d'applications enregistrées et outil de gestion unique
(livraison #445, phase 3 : « comparer les applications enregistrées et
produire un outil unique de gestion »). Logique PURE sur les
spécifications d'interface (#444) de plusieurs applications :

- `compare_apps(specs)` : rapproche les écrans d'applications différentes
  qui remplissent la même FONCTION -- même genre (liste / formulaire),
  champs ou colonnes de même nom (après normalisation), titres et tables
  voisins → groupes d'équivalence avec score, champs communs et champs
  propres ; écrans sans équivalent listés à part ;
- `unified_spec(specs, comparison)` : une seule spécification -- un écran
  par fonction, champs = union des champs des applications, chaque champ
  portant, application par application, la table et la colonne réelles
  (`sources`) : l'outil unique sait où lire et écrire pour chaque
  application, et signale ce qui n'existe que dans l'une d'elles.

Les scores sont explicites (`score`, `why`) ; rien n'est fusionné sous un
seuil bas : c'est une proposition à valider.
"""
from ui_spec import norm, slug

MATCH_THRESHOLD = 0.4

# Équivalents fréquents entre applications françaises / anglaises et
# entre singulier / pluriel : « clients » et « customers » désignent la même
# fonction. Petit dictionnaire volontaire, pas de traduction automatique.
_SYNONYMS = {
    "customer": "client", "product": "produit", "invoice": "facture", "order": "commande",
    "user": "utilisateur", "supplier": "fournisseur", "provider": "fournisseur", "contact": "contact",
    "name": "nom", "lastname": "nom", "firstname": "prenom", "phone": "tel", "telephone": "tel",
    "mail": "email", "city": "ville", "town": "ville", "zip": "cp", "zipcode": "cp", "postcode": "cp",
    "address": "adresse", "country": "pays", "price": "prix", "amount": "montant", "quantity": "quantite",
    "date": "date", "status": "statut", "state": "statut", "comment": "commentaire", "note": "commentaire",
    "company": "societe", "firm": "societe", "title": "titre", "label": "libelle", "description": "description",
    "reference": "ref", "code": "code", "number": "numero", "num": "numero",
}


def _canon(tok):
    """Forme canonique d'un jeton : singulier, synonyme connu."""
    t = tok
    if len(t) > 3 and t.endswith("s"):
        t = t[:-1]
    return _SYNONYMS.get(t, _SYNONYMS.get(tok, t))


def _term(name):
    """Terme comparable d'un champ / colonne / table : normalisation de
    ui_spec, jetons canoniques, « _id » final ignoré (ville_id ≡ ville)."""
    toks = [_canon(t) for t in norm(name).split()]
    if len(toks) > 1 and toks[-1] == "id":
        toks = toks[:-1]
    return " ".join(toks)


def _screen_terms(screen):
    """Jetons comparables d'un écran : champs (formulaire) ou colonnes (liste)."""
    if screen.get("kind") in ("form", "detail"):
        return {_term(f.get("name")) for f in screen.get("fields") or [] if _term(f.get("name"))}
    return {_term(c.get("label")) for c in screen.get("columns") or [] if _term(c.get("label"))}


def _title_terms(screen):
    words = norm(screen.get("title") or "").split() + norm((screen.get("screen") or "").replace("{n}", "")).split()
    return {_canon(w) for w in words}


def _jaccard(a, b):
    return len(a & b) / len(a | b) if (a or b) else 0.0


def _overlap(a, b):
    """Coefficient de recouvrement : part du plus petit ensemble retrouvée
    dans l'autre (une fiche courte incluse dans une fiche longue = même
    fonction, même si l'autre a beaucoup de champs en plus)."""
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def screen_similarity(a, b):
    """(score 0-1, raisons) entre deux écrans d'applications différentes :
    0.6 × champs/colonnes communs, 0.25 × titres/chemins, 0.15 × tables."""
    if a.get("kind") != b.get("kind") and not ({a.get("kind"), b.get("kind")} <= {"form", "detail"}):
        return 0.0, ["genres différents"]
    ta, tb = _screen_terms(a), _screen_terms(b)
    common = ta & tb
    terms = _overlap(ta, tb) if len(common) >= 2 else _jaccard(ta, tb)
    titles = _jaccard(_title_terms(a), _title_terms(b))
    xa, xb = _term(a.get("table")), _term(b.get("table"))
    tables = 1.0 if xa and xb and xa == xb else (0.5 if xa and xb and (xa in xb or xb in xa) else 0.0)
    score = 0.6 * terms + 0.25 * titles + 0.15 * tables
    why = []
    if common:
        why.append("champs communs : %s" % ", ".join(sorted(common)[:8]))
    if titles:
        why.append("titres/chemins voisins")
    if tables:
        why.append("tables %s" % ("identiques" if tables == 1.0 else "voisines"))
    return round(score, 3), why or ["rien en commun"]


def compare_apps(specs):
    """`specs` : {app: spec}. Groupes d'écrans équivalents entre
    applications (appariement glouton par score décroissant, un écran par
    application et par groupe) + écrans propres à une application."""
    apps = sorted(specs)
    screens = [(app, s) for app in apps for s in (specs[app] or {}).get("screens") or [] if s.get("kind") != "action" and not s.get("hidden")]
    pairs = []
    for i, (app_a, a) in enumerate(screens):
        for app_b, b in screens[i + 1:]:
            if app_a == app_b:
                continue
            score, why = screen_similarity(a, b)
            if score >= MATCH_THRESHOLD:
                pairs.append((score, app_a, a, app_b, b, why))
    pairs.sort(key=lambda p: -p[0])
    groups = []
    member_of = {}
    for score, app_a, a, app_b, b, why in pairs:
        ka, kb = (app_a, a["id"]), (app_b, b["id"])
        ga, gb = member_of.get(ka), member_of.get(kb)
        if ga is None and gb is None:
            g = {"screens": [{"app": app_a, **_brief(a)}, {"app": app_b, **_brief(b)}], "scores": [score], "why": list(why)}
            groups.append(g); member_of[ka] = member_of[kb] = g
        elif ga is not None and gb is None and app_b not in [s["app"] for s in ga["screens"]]:
            ga["screens"].append({"app": app_b, **_brief(b)}); ga["scores"].append(score); ga["why"].extend(w for w in why if w not in ga["why"]); member_of[kb] = ga
        elif gb is not None and ga is None and app_a not in [s["app"] for s in gb["screens"]]:
            gb["screens"].append({"app": app_a, **_brief(a)}); gb["scores"].append(score); gb["why"].extend(w for w in why if w not in gb["why"]); member_of[ka] = gb
    out = []
    for g in groups:
        terms = [_screen_terms(_find(specs, s)) for s in g["screens"]]
        common = set.intersection(*terms) if terms else set()
        g["function"] = _function_label(g["screens"])
        g["kind"] = _majority([s["kind"] for s in g["screens"]])
        g["score"] = round(sum(g["scores"]) / len(g["scores"]), 3)
        g["common_fields"] = sorted(common)
        g["specific_fields"] = {s["app"]: sorted(t - common) for s, t in zip(g["screens"], terms)}
        g["apps"] = [s["app"] for s in g["screens"]]
        del g["scores"]
        out.append(g)
    out.sort(key=lambda g: (-len(g["apps"]), -g["score"]))
    unique = [{"app": app, **_brief(s)} for app, s in screens if (app, s["id"]) not in member_of]
    return {"apps": apps, "groups": out, "unique": unique,
            "counts": {"groups": len(out), "shared_by_all": sum(1 for g in out if len(g["apps"]) == len(apps)), "unique": len(unique),
                       "screens": {app: sum(1 for a, _s in screens if a == app) for app in apps}}}


def _brief(s):
    return {"id": s["id"], "title": s.get("title"), "kind": s.get("kind"), "screen": s.get("screen"), "table": s.get("table")}


def _find(specs, brief):
    for s in (specs.get(brief["app"]) or {}).get("screens") or []:
        if s["id"] == brief["id"]:
            return s
    return {}


def _majority(values):
    """Valeur la plus fréquente ; à égalité, la première par ordre
    alphabétique (résultat stable d'un appel à l'autre)."""
    return max(sorted(set(values)), key=values.count) if values else None


def _function_label(screens):
    titles = [s.get("title") for s in screens if s.get("title")]
    return _majority(titles) or screens[0].get("screen") or "fonction"


def unified_spec(specs, comparison=None, label="outil unique"):
    """Une spécification unique : un écran par groupe d'équivalence
    (champs = union, avec `sources` {app: {table, column}}) + les écrans
    propres à une application (tagués). `targets` par écran : la connexion
    et la table de chaque application, pour lire / écrire au bon endroit."""
    comparison = comparison or compare_apps(specs)
    screens = []
    for g in comparison["groups"]:
        members = [(s["app"], _find(specs, s)) for s in g["screens"]]
        fields, columns, seen_f, seen_c = [], [], {}, {}
        for app, sc in members:
            for f in sc.get("fields") or []:
                k = _term(f.get("name"))
                if not k:
                    continue
                if k not in seen_f:
                    seen_f[k] = {"name": k.replace(" ", "_"), "label": f.get("label") or f.get("name"), "type": f.get("type") or "text", "required": bool(f.get("required")),
                                 "sources": {}, "apps": [], "names": {}}
                    fields.append(seen_f[k])
                seen_f[k]["sources"][app] = {"table": sc.get("table"), "column": f.get("column"), "confidence": f.get("confidence")}
                seen_f[k]["apps"].append(app)
                seen_f[k]["names"][app] = f.get("name")
                seen_f[k]["required"] = seen_f[k]["required"] or bool(f.get("required"))
            for c in sc.get("columns") or []:
                k = _term(c.get("label"))
                if not k:
                    continue
                if k not in seen_c:
                    seen_c[k] = {"label": c.get("label"), "sources": {}, "apps": []}
                    columns.append(seen_c[k])
                seen_c[k]["sources"][app] = {"table": sc.get("table"), "column": c.get("column")}
                seen_c[k]["apps"].append(app)
        for f in fields:
            f["shared"] = len(f["apps"]) == len(members)
        for c in columns:
            c["shared"] = len(c["apps"]) == len(members)
        targets = {app: {"table": sc.get("table"), "pk": sc.get("pk"), "screen_id": sc.get("id"), "dba_connection_id": (specs[app] or {}).get("dba_connection_id"),
                         "dba_database": (specs[app] or {}).get("dba_database")} for app, sc in members}
        screens.append({"id": slug("u-" + g["function"]), "title": g["function"], "kind": g["kind"], "apps": g["apps"], "score": g["score"], "why": g["why"],
                        "fields": fields, "columns": columns, "targets": targets, "shared": len(g["apps"]) == len(comparison["apps"]),
                        "todo": ([] if all(f["shared"] for f in fields) else ["champs propres à une application : %d" % sum(1 for f in fields if not f["shared"])])})
    for u in comparison["unique"]:
        sc = _find(specs, u)
        screens.append({"id": slug("u-%s-%s" % (u["app"], u["id"])), "title": "%s (%s)" % (u.get("title") or u["id"], u["app"]), "kind": u.get("kind"), "apps": [u["app"]], "score": None, "why": ["propre à %s" % u["app"]],
                        "fields": [{"name": (_term(f.get("name")) or norm(f.get("name")) or "champ").replace(" ", "_"), "label": f.get("label") or f.get("name"), "type": f.get("type") or "text", "required": bool(f.get("required")), "apps": [u["app"]], "shared": False, "names": {u["app"]: f.get("name")},
                                    "sources": {u["app"]: {"table": sc.get("table"), "column": f.get("column"), "confidence": f.get("confidence")}}} for f in sc.get("fields") or []],
                        "columns": [{"label": c.get("label"), "apps": [u["app"]], "shared": False, "sources": {u["app"]: {"table": sc.get("table"), "column": c.get("column")}}} for c in sc.get("columns") or []],
                        "targets": {u["app"]: {"table": sc.get("table"), "pk": sc.get("pk"), "screen_id": sc.get("id"), "dba_connection_id": (specs[u["app"]] or {}).get("dba_connection_id"),
                                               "dba_database": (specs[u["app"]] or {}).get("dba_database")}},
                        "shared": False, "todo": []})
    order = {"list": 0, "form": 1, "detail": 2, "other": 3}
    screens.sort(key=lambda s: (0 if s["shared"] else 1, order.get(s["kind"], 9), -(s["score"] or 0)))
    return {"version": 1, "label": label, "apps": comparison["apps"], "screens": screens,
            "counts": {"screens": len(screens), "shared": sum(1 for s in screens if s["shared"]), "partial": sum(1 for s in screens if not s["shared"] and len(s["apps"]) > 1),
                       "unique": sum(1 for s in screens if len(s["apps"]) == 1)}}


def per_app_view(unified, app):
    """La spec unique projetée sur UNE application (table / colonnes de
    cette application) -- ce que GeneratedAppView sait rendre."""
    out = []
    for s in unified.get("screens") or []:
        t = (s.get("targets") or {}).get(app)
        if not t:
            continue
        out.append({"id": s["id"], "screen": s["id"], "title": s["title"], "kind": s["kind"], "table": t.get("table"), "pk": t.get("pk"), "nav": s["kind"] in ("list", "form", "detail"),
                    "hidden": False, "apps": s["apps"], "shared": s["shared"], "todo": s.get("todo") or [],
                    "columns": [{"label": c["label"], "column": (c["sources"].get(app) or {}).get("column"), "confidence": 1.0, "source": "outil unique"} for c in s.get("columns") or []],
                    "fields": [{"name": f["name"], "label": f["label"], "type": f["type"], "required": f["required"], "column": (f["sources"].get(app) or {}).get("column"),
                                "confidence": (f["sources"].get(app) or {}).get("confidence"), "source": "outil unique", "shared": f["shared"]} for f in s.get("fields") or []],
                    "links": [], "actions": []})
    return {"version": 1, "app": app, "screens": out, "tables": {}, "dba_connection_id": next((s["targets"][app].get("dba_connection_id") for s in unified.get("screens") or [] if app in (s.get("targets") or {})), None),
            "dba_database": next((s["targets"][app].get("dba_database") for s in unified.get("screens") or [] if app in (s.get("targets") or {})), None),
            "counts": {"screens": len(out), "nav": sum(1 for s in out if s["nav"]), "with_table": sum(1 for s in out if s["table"]), "todo": sum(len(s["todo"]) for s in out)}}
