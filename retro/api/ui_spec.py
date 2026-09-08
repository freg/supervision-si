# -*- coding: utf-8 -*-
"""Spécification d'interface générée (livraison #444, phase 2 : « de ce
parcours, générer une interface avec le design du hub offrant les mêmes
fonctionnalités »). Logique PURE : étapes des parcours + carte
fonctionnelle + colonnes réelles des tables (dba-api) → une SPEC que le
hub sait rendre (`GeneratedAppView.jsx`) : écrans (liste, fiche/formulaire,
action), table principale de chaque écran, colonnes affichées, champs de
saisie rattachés aux colonnes, liens de navigation, actions.

Chaque rattachement porte sa méthode et sa confiance (`*_source`,
`*_confidence`) ; la spec est enregistrée par application et MODIFIABLE
(table d'un écran, colonne d'un champ, libellés) : ce qui n'a pas été vu
dans un parcours n'est pas inventé, il est marqué « à compléter ».
"""
import re
import unicodedata

VERSION = 1
_STOP = {"le", "la", "les", "de", "du", "des", "un", "une", "et", "d", "l", "the", "of"}
_PREFIXES = ("txt", "f_", "fld_", "champ_", "input_", "frm_", "id_")


def slug(s):
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-zA-Z0-9]+", "-", s).strip("-").lower()
    return s or "ecran"


def norm(name):
    """Forme comparable d'un nom de champ / colonne / en-tête : sans
    accents, minuscules, sans préfixes de formulaire, sans crochets."""
    s = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode().lower()
    s = re.sub(r"\[.*$", "", s)
    for p in _PREFIXES:
        if s.startswith(p) and len(s) > len(p) + 1:
            s = s[len(p):]
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return " ".join(w for w in s.split() if w not in _STOP)


def _tokens(s):
    return set(norm(s).split())


def match_column(name, columns):
    """(colonne, confiance, méthode) : nom exact normalisé (1.0), sans
    séparateurs (0.9), l'un contient l'autre (0.7), jetons communs (0.5)."""
    n = norm(name)
    if not n or not columns:
        return None, 0.0, None
    cols = {c: norm(c) for c in columns}
    for c, cn in cols.items():
        if cn == n:
            return c, 1.0, "exact"
    for c, cn in cols.items():
        if cn.replace(" ", "") == n.replace(" ", ""):
            return c, 0.9, "sans-separateurs"
    best, score = None, 0.0
    for c, cn in cols.items():
        if len(n) >= 3 and (n in cn or cn in n) and min(len(n), len(cn)) >= 3:
            s = 0.7 * min(len(n), len(cn)) / max(len(n), len(cn)) + 0.3
            if s > score:
                best, score = c, min(s, 0.85)
    if best:
        return best, round(score, 2), "inclusion"
    tn = _tokens(name)
    for c, cn in cols.items():
        tc = set(cn.split())
        if tn and tc:
            j = len(tn & tc) / len(tn | tc)
            if j > score and j >= 0.5:
                best, score = c, j
    return (best, round(min(score, 0.6), 2), "jetons") if best else (None, 0.0, None)


def _title(screen, steps):
    for s in steps:
        h = ((s.get("dom") or {}).get("headings") or [None])[0]
        if h:
            return h
    for s in steps:
        if s.get("title"):
            return re.sub(r"\s*[-–|:]\s*.*$", "", s["title"]) or s["title"]
    seg = [x for x in (screen or "/").split("?")[0].split("/") if x and x != "{n}"]
    return (seg[-1].replace("-", " ").replace("_", " ").capitalize() if seg else "Accueil")


def _screen_kind(sc, steps, method):
    if method and method != "GET":
        return "action"
    has_table = any((s.get("dom") or {}).get("tables") for s in steps)
    post_forms = [f for s in steps for f in (s.get("forms") or []) if (f.get("method") or "get") == "post" and len(f.get("fields") or []) >= 2]
    if post_forms:
        return "form"
    if has_table:
        return "list"
    if "{n}" in (sc.get("screen") or ""):
        return "detail"
    return "other"


def _main_table(sc, kind, action_screen=None):
    """Table principale : écrites par l'action (formulaire), lues (liste),
    sinon celles du code ; confiance selon la source."""
    db = sc.get("db_tables") or {}
    if kind == "form" and action_screen:
        writes = {t: e.get("writes", 0) for t, e in (action_screen.get("db_tables") or {}).items() if e.get("writes")}
        if writes:
            t = max(writes, key=writes.get)
            return t, 0.9, "écritures SQL de l'action"
    if db:
        reads = {t: e.get("reads", 0) + 2 * e.get("writes", 0) for t, e in db.items()}
        t = max(reads, key=reads.get)
        return t, 0.8, "journal SQL de l'écran"
    code = sc.get("code_tables") or {}
    if code:
        # la table dont le nom ressemble le plus au chemin de l'écran, sinon la première
        seg = _tokens(sc.get("screen") or "")
        best = max(code, key=lambda t: (len(_tokens(t) & seg), -len(t)))
        return best, 0.5 if _tokens(best) & seg else 0.35, "code (route → fichier)"
    return None, 0.0, None


def build_ui_spec(steps, fmap, columns_by_table, app_label=None, existing=None):
    """`steps` : toutes les étapes de tous les parcours ; `fmap` :
    functional_map ; `columns_by_table` : {table: [{name, type, nullable,
    primary_key}]} (dba-api, best-effort). `existing` : spec précédente,
    pour conserver les choix faits à la main (table, colonnes, libellés,
    écrans masqués)."""
    columns_by_table = columns_by_table or {}
    prev = {s["id"]: s for s in (existing or {}).get("screens") or []} if existing else {}
    by_screen = {}
    for s in steps:
        by_screen.setdefault(_screen_key(s), []).append(s)
    screens = {sc["screen"]: sc for sc in (fmap or {}).get("screens") or []}
    action_by_path = {}
    out = []
    for key, sc in screens.items():
        st = by_screen.get(key, [])
        method = next((s.get("method") for s in st if s.get("method")), "GET")
        kind = _screen_kind(sc, st, method)
        if kind == "action":
            action_by_path[key] = sc
    for key, sc in screens.items():
        st = by_screen.get(key, [])
        if not key.startswith("/"):
            continue  # repères : pas des écrans
        method = next((s.get("method") for s in st if s.get("method")), "GET")
        kind = _screen_kind(sc, st, method)
        sid = slug(key)
        forms = [f for f in sc.get("forms") or [] if f.get("fields")]
        post_form = next((f for f in forms if f.get("method") == "post"), None)
        action_screen = action_by_path.get((post_form or {}).get("action")) if post_form else None
        table, conf, src = _main_table(sc, kind, action_screen)
        old = prev.get(sid) or {}
        if old.get("table_manual"):
            table, conf, src = old["table"], 1.0, "choisi à la main"
        cols = [c["name"] for c in columns_by_table.get(table) or []] if table else []
        pk = next((c["name"] for c in columns_by_table.get(table) or [] if c.get("primary_key")), None)
        # colonnes de liste : en-têtes des tableaux vus rapprochés des colonnes réelles
        headers = []
        for s in st:
            for t in (s.get("dom") or {}).get("tables") or []:
                for h in t.get("headers") or []:
                    if h not in headers:
                        headers.append(h)
        columns = []
        for h in headers[:20]:
            col, c2, how = match_column(h, cols)
            columns.append({"label": h, "column": col, "confidence": c2, "source": how or "en-tête sans colonne"})
        if not columns and cols:
            columns = [{"label": c, "column": c, "confidence": 0.3, "source": "colonnes de la table (aucun tableau vu)"} for c in cols[:8]]
        # champs : formulaire principal → colonnes
        fields = []
        seen = set()
        for f in (forms if kind in ("form", "detail") else forms[:1]):
            for name in f.get("fields") or []:
                if name in seen or norm(name) in ("csrf", "token", "submit"):
                    continue
                seen.add(name)
                meta = next((x for s in st for fm in ((s.get("dom") or {}).get("forms") or []) for x in (fm.get("fields") or []) if x.get("name") == name), {})
                col, c2, how = match_column(name, cols)
                fields.append({"name": name, "label": meta.get("label") or name, "type": meta.get("type") or "text", "required": bool(meta.get("required")),
                               "column": col, "confidence": c2, "source": how or "champ sans colonne"})
        links, actions = [], []
        for s in st:
            for a in s.get("actions") or []:
                if a.get("kind") == "click" and a.get("href"):
                    to = _norm_href(a["href"])
                    if to in screens and to != key and to not in [l["to"] for l in links]:
                        links.append({"to": slug(to), "screen": to, "label": (a.get("text") or "")[:40] or to, "via": "clic"})
        if post_form:
            actions.append({"label": "Enregistrer", "method": "POST", "path": post_form.get("action"), "to": slug(post_form["action"]) if post_form.get("action") in screens else None,
                            "writes": sorted((action_screen or {}).get("db_tables") or {}) if action_screen else []})
        spec = {"id": sid, "screen": key, "title": old.get("title") if old.get("title_manual") else _title(key, st), "kind": kind, "route": sc.get("route"), "handler": sc.get("handler"),
                "table": table, "table_confidence": conf, "table_source": src, "table_manual": bool(old.get("table_manual")), "pk": pk,
                "columns": old.get("columns") if old.get("columns_manual") else columns, "columns_manual": bool(old.get("columns_manual")),
                "fields": fields, "links": links, "actions": actions, "visits": sc.get("visits"), "hidden": bool(old.get("hidden")),
                "nav": kind in ("list", "form", "detail") and not old.get("hidden"),
                "todo": [t for t in (("table à choisir" if not table else None), ("colonnes non rattachées : %d" % sum(1 for c in columns if not c["column"]) if any(not c["column"] for c in columns) else None),
                                     ("champs non rattachés : %d" % sum(1 for f in fields if not f["column"]) if any(not f["column"] for f in fields) else None)) if t]}
        out.append(spec)
    # ordre : écrans de navigation d'abord (liste, formulaire, fiche), par nombre de visites
    order = {"list": 0, "form": 1, "detail": 2, "other": 3, "action": 4}
    out.sort(key=lambda s: (order.get(s["kind"], 9), -(s.get("visits") or 0)))
    return {"version": VERSION, "app": app_label, "screens": out,
            "tables": {t: [c["name"] for c in cs] for t, cs in columns_by_table.items()},
            "counts": {"screens": len(out), "with_table": sum(1 for s in out if s["table"]), "nav": sum(1 for s in out if s["nav"]), "todo": sum(len(s["todo"]) for s in out)}}


def _screen_key(step):
    if step.get("kind") == "mark" and not step.get("path"):
        return "repère : %s" % (step.get("label") or step["n"])
    return (step.get("path") or "/").split("?", 1)[0]


def _norm_href(href):
    """Normalisation légère d'un href relatif (valeurs numériques → {n})."""
    path = (href or "").split("?", 1)[0].split("#", 1)[0]
    if "://" in path:
        path = "/" + "/".join(path.split("/")[3:])
    return "/".join("{n}" if seg.isdigit() else seg for seg in path.split("/")) or "/"
