# -*- coding: utf-8 -*-
"""Parcours applicatifs (livraison #441, backlog 30 volet 2 -- « schéma
FONCTIONNEL de l'interface ») : logique PURE, sans base ni réseau.

La personne parcourt l'application web réelle avec l'extension Firefox
(`retro/browser-extension`), qui envoie des ÉVÉNEMENTS bruts (navigation,
DOM d'un écran, clic, saisie, envoi de formulaire, requête HTTP vue par le
navigateur, repère posé à la main) à l'agent relais puis à retro-api.
Ici :

- `build_steps(events)` : les événements deviennent des ÉTAPES (une par
  écran affiché ou par repère), chacune avec ses actions, ses requêtes
  et ses formulaires ;
- `normalize_path` / `match_route` : l'URL réelle (`/client/42/edit`)
  est rapprochée d'une route Fat-Free extraite du code (`/client/@id/edit`,
  `route_scanner`) → contrôleur, méthode, fichier source ;
- `functional_map(steps, scan)` : chaque écran ↔ route ↔ fichiers ↔ TABLES
  (jointures et `Mapper` trouvés par `php_sql_scanner` dans ces fichiers)
  et champs de formulaire ↔ champs de gabarit (`html_view_scanner`) : le
  schéma fonctionnel, vu du parcours réel ;
- `tables_in_sql` / `attribute_queries` : les requêtes SQL réellement
  exécutées (journal général MySQL lu via dba-api, « analyse bdd »)
  rattachées à l'étape pendant laquelle elles ont eu lieu → tables
  réellement touchées par écran, à confronter à celles déduites du code.

Rien n'est deviné en silence : chaque rapprochement porte sa méthode
(`matched_by`) et les écrans sans route ou sans table restent listés.
"""
import re
from datetime import datetime, timezone
from urllib.parse import urlsplit, parse_qsl

STEP_EVENTS = ("navigation", "mark")
_NUM = re.compile(r"^\d+$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
_HEX = re.compile(r"^[0-9a-f]{16,}$", re.I)
_SQL_TABLES = re.compile(r"\b(?:FROM|JOIN|INTO|UPDATE|DELETE\s+FROM|TABLE)\s+`?([A-Za-z_][\w$]*)`?(?:\s*\.\s*`?([A-Za-z_][\w$]*)`?)?", re.I)
_SQL_KIND = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE|REPLACE|CREATE|ALTER|DROP|TRUNCATE|SHOW|SET|BEGIN|COMMIT|ROLLBACK|START|CALL)\b", re.I)
_SQL_NOISE = re.compile(r"\b(?:general_log|information_schema|performance_schema|mysql)\b", re.I)


def parse_ts(s):
    """ISO 8601 (avec Z, ±hh:mm, ou fractions) ou epoch → float epoch."""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s) / (1000.0 if s > 1e11 else 1.0)
    s = str(s).strip()
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        if " " in s and "T" not in s:
            s = s.replace(" ", "T", 1)
        d = datetime.fromisoformat(s)
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.timestamp()
    except ValueError:
        try:
            return float(s)
        except ValueError:
            return None


def normalize_path(url, base_url=None):
    """Chemin d'une URL sans hôte ni valeurs variables : segments
    numériques, UUID et longs hexadécimaux → `{n}` ; la query garde ses
    clés seulement (`?id={n}&tab=x` → `?id&tab`). Base retirée si l'appli
    vit sous un préfixe (`https://h/appli/` → `/appli` enlevé)."""
    if not url:
        return "/"
    u = urlsplit(url if "://" in url else "http://x" + (url if url.startswith("/") else "/" + url))
    path = u.path or "/"
    if base_url:
        bp = urlsplit(base_url if "://" in base_url else "http://x" + base_url).path.rstrip("/")
        if bp and path.startswith(bp + "/"):
            path = path[len(bp):]
        elif bp and path == bp:
            path = "/"
    segs = []
    for seg in path.split("/"):
        if seg and (_NUM.match(seg) or _UUID.match(seg) or _HEX.match(seg)):
            segs.append("{n}")
        else:
            segs.append(seg)
    out = "/".join(segs) or "/"
    keys = sorted({k for k, _v in parse_qsl(u.query, keep_blank_values=True)})
    if keys:
        out += "?" + "&".join(keys)
    return out


def route_regex(route_path):
    """`/client/@id/edit` → regex ; `*` de Fat-Free → tout ; jetons → un
    segment."""
    parts = []
    for seg in route_path.split("/"):
        if seg == "*":
            parts.append(".*")
        elif seg.startswith("@"):
            parts.append(r"[^/]+")
        else:
            parts.append(re.escape(seg))
    return re.compile("^" + "/".join(parts) + "/?$")


def match_route(path, method, routes):
    """La route Fat-Free la plus précise (moins de jetons, plus de segments
    fixes) dont le motif accepte `path` et la méthode ; None sinon."""
    raw = path.split("?", 1)[0]
    best, best_key = None, None
    for r in routes or []:
        rp = r.get("path") or ""
        if not rp.startswith("/"):
            continue
        methods = [m.upper() for m in (r.get("methods") or [])]
        if method and methods and method.upper() not in methods and "*" not in methods:
            continue
        try:
            rx = route_regex(rp)
        except re.error:
            continue
        # le chemin réel a ses valeurs remplacées par {n} : on teste les deux formes
        if not (rx.match(raw) or rx.match(raw.replace("{n}", "1"))):
            continue
        key = (len(r.get("url_tokens") or []) + rp.count("*"), -len([s for s in rp.split("/") if s and not s.startswith("@")]))
        if best is None or key < best_key:
            best, best_key = r, key
    return best


def _short_time(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else None


def build_steps(events, base_url=None):
    """Événements bruts (triés par `seq`) → [{n, kind, at, until, url, path,
    title, label, method, dom, actions, requests, forms, inputs}].

    Une étape commence quand le navigateur ENVOIE la requête d'une page
    (`request` de type main_frame : c'est à ce moment que le serveur
    travaille, donc que ses requêtes SQL s'exécutent), ou à un `mark`
    (repère posé par la personne). L'événement `navigation` qui suit
    (page chargée) complète l'étape ouverte par cette requête (titre, URL
    finale) ; un `navigation` sans requête préalable (page ouverte avant
    l'enregistrement, historique) ouvre une étape à lui seul. Un POST
    suivi d'une redirection donne donc DEUX étapes : l'action (POST, ses
    écritures SQL) puis la page affichée."""
    steps = []
    cur = None

    def new_step(kind, at, url=None, title=None, label=None, method=None, awaiting=False):
        nonlocal cur
        cur = {"n": len(steps) + 1, "kind": kind, "at": at, "at_ts": parse_ts(at), "until": None, "until_ts": None,
               "url": url, "path": normalize_path(url, base_url) if url else None, "title": title, "label": label, "method": method,
               "note": None, "dom": None, "actions": [], "requests": [], "forms": [], "inputs": [], "replay": [], "_awaiting_nav": awaiting}
        steps.append(cur)

    for ev in sorted(events or [], key=lambda e: (e.get("seq") or 0)):
        kind = ev.get("kind")
        d = ev.get("data") or {}
        if kind == "mark":
            new_step("mark", ev.get("at"), label=d.get("label"))
            continue
        if kind == "navigation":
            if cur is not None and cur["_awaiting_nav"]:
                cur["_awaiting_nav"] = False
                cur["title"] = d.get("title") or cur["title"]
                if d.get("url"):
                    cur["url"] = d["url"]; cur["path"] = normalize_path(d["url"], base_url)
            else:
                new_step("navigation", ev.get("at"), url=d.get("url"), title=d.get("title"))
            continue
        if kind == "request" and d.get("type") == "main_frame":
            new_step("navigation", ev.get("at"), url=d.get("url"), method=(d.get("method") or "GET").upper(), awaiting=True)
        if kind not in ("dom", "click", "submit", "input", "change", "keydown", "request", "note", "replay-action", "replay-end"):
            continue
        if cur is None:
            if kind in ("replay-action", "replay-end"):
                continue
            new_step("navigation", ev.get("at"), url=d.get("url") or d.get("page_url"))
        if kind == "dom":
            cur["_awaiting_nav"] = False
            cur["dom"] = {"forms": d.get("forms") or [], "headings": d.get("headings") or [], "tables": d.get("tables") or [],
                          "links_count": d.get("links_count"), "title": d.get("title")}
            if d.get("title") and not cur["title"]:
                cur["title"] = d["title"]
            for f in d.get("forms") or []:
                cur["forms"].append({"action": f.get("action"), "method": (f.get("method") or "get").lower(),
                                     "fields": [x.get("name") for x in (f.get("fields") or []) if x.get("name")], "source": "dom"})
        elif kind in ("click", "submit", "input", "change", "keydown"):
            a = {"kind": kind, "at": ev.get("at"), "selector": d.get("selector"), "text": (d.get("text") or "")[:80] or None,
                 "tag": d.get("tag"), "href": d.get("href"), "field": d.get("field"), "form": d.get("form")}
            if kind == "submit":
                cur["forms"].append({"action": d.get("action"), "method": (d.get("method") or "get").lower(),
                                     "fields": list(d.get("fields") or []), "source": "submit"})
            if kind in ("input", "change") and d.get("field"):
                entry = {"field": d.get("field"), "type": d.get("type"), "length": d.get("length"), "value": d.get("value")}
                last = cur["inputs"][-1] if cur["inputs"] else None
                if last and last["field"] == entry["field"]:
                    cur["inputs"][-1] = entry   # frappe puis validation du même champ : une seule saisie, la dernière
                else:
                    cur["inputs"].append(entry)
            cur["actions"].append(a)
        elif kind == "request":
            url = d.get("url")
            cur["requests"].append({"at": ev.get("at"), "method": (d.get("method") or "GET").upper(), "url": url,
                                    "path": normalize_path(url, base_url) if url else None, "type": d.get("type"),
                                    "status": d.get("status"), "duration_ms": d.get("duration_ms"), "page": d.get("type") == "main_frame",
                                    "form_keys": list(d.get("form_keys") or [])})
        elif kind == "note":
            cur["note"] = d.get("text")
        elif kind == "replay-action":   # #443 : trace du rejeu (action ok / en échec) sur l'étape où elle a eu lieu
            cur.setdefault("replay", []).append({"action": d.get("action"), "ok": bool(d.get("ok")), "error": d.get("error"), "what": d.get("what"), "step_ref": d.get("step")})
    for i, s in enumerate(steps):
        s.pop("_awaiting_nav", None)
        nxt = steps[i + 1] if i + 1 < len(steps) else None
        s["until_ts"] = nxt["at_ts"] if nxt else None
        s["until"] = nxt["at"] if nxt else None
    return steps


def tables_in_sql(sql):
    """Tables citées par une requête (FROM/JOIN/INTO/UPDATE/DELETE FROM),
    sans les schémas système ; `kind` = premier mot-clé."""
    if not sql:
        return [], None
    m = _SQL_KIND.match(sql)
    kind = m.group(1).upper() if m else None
    tables = []
    for a, b in _SQL_TABLES.findall(sql):
        t = b or a
        if not t or _SQL_NOISE.search(t) or t.upper() in ("SELECT", "DUAL", "SET", "VALUES"):
            continue
        if t not in tables:
            tables.append(t)
    return tables, kind


def attribute_queries(steps, queries, tolerance=0.0, skew=0.0):
    """`queries` : [{at, sql, ...}] (journal général) → chaque étape reçoit
    `queries` (celles exécutées entre le début de l'étape -- l'envoi de sa
    requête de page -- et le début de la suivante) et `db_tables`
    {table: {reads, writes}}. `skew` : décalage d'horloge base − navigateur
    en secondes (à mesurer : `SELECT NOW()` contre l'heure du poste),
    `tolerance` : marge avant le début d'une étape (0 : une requête ne peut
    pas précéder la requête de page qui la provoque). Renvoie le
    nombre de requêtes rattachées ; celles d'avant la première étape sont
    ignorées, celles d'après la dernière lui reviennent."""
    n = 0
    for s in steps:
        s["queries"] = []
        s["db_tables"] = {}
    if not steps:
        return 0
    for q in queries or []:
        ts = parse_ts(q.get("at"))
        if ts is None:
            continue
        ts -= skew
        target = None
        for s in steps:
            if s["at_ts"] is not None and ts >= s["at_ts"] - tolerance:
                target = s
        if target is None:
            continue
        tables, kind = tables_in_sql(q.get("sql"))
        if kind in (None, "SET", "SHOW", "BEGIN", "COMMIT", "ROLLBACK", "START") and not tables:
            continue
        target["queries"].append({"at": q.get("at"), "kind": kind, "tables": tables, "sql": (q.get("sql") or "")[:400]})
        for t in tables:
            e = target["db_tables"].setdefault(t, {"reads": 0, "writes": 0})
            if kind in ("SELECT", "SHOW"):
                e["reads"] += 1
            else:
                e["writes"] += 1
        n += 1
    return n


def _file_tables(scan):
    """{fichier: {tables…}} depuis les jointures candidates et les tables
    `Mapper` par fichier (`file_tables` du scan si présent)."""
    out = {}
    for c in (scan or {}).get("join_candidates") or []:
        f = c.get("source_file")
        if f:
            out.setdefault(f, set()).update([c.get("from_table"), c.get("to_table")])
    for f, tables in ((scan or {}).get("file_tables") or {}).items():
        out.setdefault(f, set()).update(tables or [])
    return {f: {t for t in ts if t} for f, ts in out.items()}


def _class_file(scan, cls):
    return ((scan or {}).get("classes") or {}).get(cls)


def screen_key(step):
    """Clé d'écran : chemin normalisé (sans query) ou libellé du repère."""
    if step.get("kind") == "mark" and not step.get("path"):
        return "repère : %s" % (step.get("label") or step["n"])
    return (step.get("path") or "/").split("?", 1)[0]


def functional_map(steps, scan, base_url=None):
    """Le schéma fonctionnel vu du parcours : [{screen, titles, visits,
    route, handler, files, code_tables, db_tables, forms, form_fields,
    template_fields, requests}] + les tables agrégées."""
    routes = (scan or {}).get("routes") or []
    file_tables = _file_tables(scan)
    template_fields = (scan or {}).get("template_fields") or {}
    screens = {}
    for s in steps:
        key = screen_key(s)
        sc = screens.setdefault(key, {"screen": key, "titles": [], "visits": 0, "steps": [], "route": None, "handler": None, "files": [],
                                      "code_tables": {}, "db_tables": {}, "forms": [], "form_fields": [], "requests": {}, "matched_by": None,
                                      "actions": 0})
        sc["visits"] += 1
        sc["steps"].append(s["n"])
        sc["actions"] += len(s.get("actions") or [])
        if s.get("title") and s["title"] not in sc["titles"]:
            sc["titles"].append(s["title"])
        # requêtes de l'écran (page + XHR) → routes du code
        page_method = "GET"
        for r in s.get("requests") or []:
            rp = (r.get("path") or "/").split("?", 1)[0]
            k = "%s %s" % (r["method"], rp)
            e = sc["requests"].setdefault(k, {"method": r["method"], "path": rp, "count": 0, "types": [], "route": None, "files": []})
            e["count"] += 1
            if r.get("type") and r["type"] not in e["types"]:
                e["types"].append(r["type"])
            if r.get("page"):
                page_method = r["method"]
            rt = match_route(rp, r["method"], routes)
            if rt:
                e["route"] = rt.get("path")
                f = _class_file(scan, rt.get("controller_class")) or rt.get("source_file")
                if f and f not in e["files"]:
                    e["files"].append(f)
                for t in file_tables.get(f, ()):
                    sc["code_tables"].setdefault(t, set()).add("requête %s" % k)
        if sc["route"] is None and key.startswith("/"):
            rt = match_route(key, page_method, routes)
            if rt:
                sc["route"] = rt.get("path")
                sc["handler"] = "%s%s%s" % (rt.get("controller_class") or "", "->" if rt.get("controller_method") else "", rt.get("controller_method") or "") or rt.get("handler_type")
                sc["matched_by"] = "route"
                f = _class_file(scan, rt.get("controller_class")) or rt.get("source_file")
                if f and f not in sc["files"]:
                    sc["files"].append(f)
                for t in file_tables.get(f, ()):
                    sc["code_tables"].setdefault(t, set()).add("code %s" % f)
        for f in s.get("forms") or []:
            fa = normalize_path(f.get("action"), base_url) if f.get("action") else key
            sig = (fa, f.get("method"), tuple(f.get("fields") or []))
            if sig not in [(x["action"], x["method"], tuple(x["fields"])) for x in sc["forms"]]:
                sc["forms"].append({"action": fa, "method": f.get("method"), "fields": list(f.get("fields") or []), "source": f.get("source")})
            for name in f.get("fields") or []:
                if name not in sc["form_fields"]:
                    sc["form_fields"].append(name)
        for t, e in (s.get("db_tables") or {}).items():
            agg = sc["db_tables"].setdefault(t, {"reads": 0, "writes": 0})
            agg["reads"] += e.get("reads", 0)
            agg["writes"] += e.get("writes", 0)
    out = []
    for sc in screens.values():
        sc["code_tables"] = {t: sorted(v) for t, v in sc["code_tables"].items()}
        sc["requests"] = sorted(sc["requests"].values(), key=lambda e: -e["count"])
        # champs de formulaire ↔ champs de gabarit (html_view_scanner) : racine.champ
        matches = []
        for name in sc["form_fields"]:
            base = re.sub(r"\[.*$", "", name)
            for root, fields in template_fields.items():
                names = fields if isinstance(fields, (list, set, tuple)) else (fields.get("fields") if isinstance(fields, dict) else [])
                for tf in names or []:
                    tfn = tf.get("field") if isinstance(tf, dict) else tf
                    if tfn and tfn.lower() == base.lower():
                        matches.append({"field": name, "template": "%s.%s" % (root, tfn)})
        sc["template_fields"] = matches
        sc["tables"] = sorted(set(sc["code_tables"]) | set(sc["db_tables"]))
        out.append(sc)
    out.sort(key=lambda s: (s["steps"][0] if s["steps"] else 0))
    tables = {}
    for sc in out:
        for t in sc["tables"]:
            tables.setdefault(t, {"screens": [], "from_code": False, "from_db": False})
            tables[t]["screens"].append(sc["screen"])
            tables[t]["from_code"] |= t in sc["code_tables"]
            tables[t]["from_db"] |= t in sc["db_tables"]
    return {"screens": out, "tables": tables,
            "counts": {"screens": len(out), "with_route": sum(1 for s in out if s["route"]), "with_tables": sum(1 for s in out if s["tables"]), "tables": len(tables)}}


# ---- Rejeu et comparaison (#443) ------------------------------------------------------

def replay_script(steps):
    """Étapes → script de rejeu pour l'extension : [{action, step, …}].
    `navigate` seulement pour un écran atteint sans clic ni envoi à l'étape
    précédente (URL tapée, premier écran) : les autres écrans découlent des
    actions rejouées. `fill` reprend la valeur enregistrée si elle l'a été
    (option de l'extension), sinon `value: null` -- à saisir à la main, le
    rejeu s'arrête sur le champ."""
    script = []
    prev_ended_with_action = False
    prev_redirected = False
    for s in steps:
        if s.get("kind") == "mark":
            script.append({"action": "mark", "step": s["n"], "label": s.get("label")})
            continue
        page_req = next((r for r in s.get("requests") or [] if r.get("page")), None)
        method = (s.get("method") or (page_req or {}).get("method") or "GET").upper()
        if s.get("url") and method == "GET" and not prev_ended_with_action and not prev_redirected:
            script.append({"action": "navigate", "step": s["n"], "url": s["url"], "expect_path": s.get("path")})
        elif s.get("url"):
            script.append({"action": "expect", "step": s["n"], "expect_path": s.get("path"), "method": method})
        pending_inputs = {i["field"]: i for i in s.get("inputs") or []}
        last = None
        for a in s.get("actions") or []:
            k = a.get("kind")
            if k in ("input", "change"):
                i = pending_inputs.pop(a.get("field"), None)
                if i is not None:
                    script.append({"action": "fill", "step": s["n"], "field": i["field"], "selector": a.get("selector"), "value": i.get("value"), "length": i.get("length")})
                    last = "fill"
            elif k == "click":
                script.append({"action": "click", "step": s["n"], "selector": a.get("selector"), "text": a.get("text"), "href": a.get("href"), "tag": a.get("tag")})
                last = "click"
            elif k == "submit":
                # le clic sur le bouton d'envoi (juste avant) provoque déjà l'envoi : ne pas soumettre deux fois
                if script and script[-1]["action"] == "click" and (script[-1].get("tag") or "").upper() in ("BUTTON", "INPUT") and script[-1]["step"] == s["n"]:
                    last = "submit"
                    continue
                script.append({"action": "submit", "step": s["n"], "selector": a.get("selector"), "form": a.get("form")})
                last = "submit"
        for i in pending_inputs.values():   # saisies sans action associée (frappe seule)
            script.append({"action": "fill", "step": s["n"], "field": i["field"], "selector": None, "value": i.get("value"), "length": i.get("length")})
        prev_ended_with_action = last in ("click", "submit")
        status = (page_req or {}).get("status")
        prev_redirected = isinstance(status, int) and 300 <= status < 400   # l'écran suivant vient de la redirection
    return script


def _step_sig(s):
    page = next((r for r in s.get("requests") or [] if r.get("page")), None)
    return {"n": s["n"], "kind": s["kind"], "path": s.get("path"), "method": s.get("method"), "title": s.get("title"),
            "status": (page or {}).get("status"), "label": s.get("label"),
            "forms": sorted({tuple(f.get("fields") or []) for f in s.get("forms") or []}),
            "headings": list((s.get("dom") or {}).get("headings") or []), "tables": [t.get("headers") for t in (s.get("dom") or {}).get("tables") or []],
            "xhr": sorted({(r["method"], r.get("path")) for r in s.get("requests") or [] if not r.get("page")}),
            "db_tables": sorted((s.get("db_tables") or {}).keys())}


def compare_journeys(steps_a, steps_b):
    """Deux parcours (le second est en général le rejeu du premier) alignés
    étape par étape : mêmes écrans, statuts, formulaires, en-têtes,
    tableaux, requêtes secondaires, tables SQL ? → {pairs, summary}."""
    pairs = []
    n = max(len(steps_a), len(steps_b))
    same = 0
    for i in range(n):
        a = _step_sig(steps_a[i]) if i < len(steps_a) else None
        b = _step_sig(steps_b[i]) if i < len(steps_b) else None
        diffs = []
        if a is None or b is None:
            diffs.append("étape absente dans %s" % ("le premier" if a is None else "le second"))
        else:
            for key, label in (("path", "écran"), ("method", "méthode"), ("status", "statut HTTP"), ("title", "titre"), ("forms", "champs de formulaire"),
                               ("headings", "en-têtes"), ("tables", "colonnes des tableaux"), ("xhr", "requêtes secondaires"), ("db_tables", "tables SQL")):
                if a.get(key) != b.get(key) and not (key == "db_tables" and (not a.get(key) or not b.get(key))):
                    diffs.append("%s : %s ≠ %s" % (label, _fmt_sig(a.get(key)), _fmt_sig(b.get(key))))
        if not diffs:
            same += 1
        pairs.append({"n": i + 1, "a": a, "b": b, "same": not diffs, "diffs": diffs})
    return {"pairs": pairs, "summary": {"steps_a": len(steps_a), "steps_b": len(steps_b), "same": same, "different": n - same}}


def _fmt_sig(v):
    if v is None or v == [] or v == ():
        return "—"
    if isinstance(v, (list, tuple, set)):
        return ", ".join(_fmt_sig(x) if isinstance(x, (list, tuple)) else str(x) for x in v) or "—"
    return str(v)
