# -*- coding: utf-8 -*-
"""Méta-relevé des champs et des relations entre gestions (livraison #448,
phase 4 : « analyser les champs, trouver les relations inter-gestions et
en faire un méta-relevé / graphe pour proposer une évolution fusion »).
Logique PURE.

Entrées, par application : la spec d'interface (#444 : écrans, tables et
colonnes réelles), le scan du code (relations candidates des jointures
PHP), le journal SQL collecté pendant les parcours (jointures réellement
exécutées) ; et la spec unique (#445 : équivalences de champs entre
applications).

`build_metagraph(...)` → graphe :
- nœuds = ENTITÉS (une table d'une application), avec leurs ATTRIBUTS
  (colonnes, type, clé primaire, écrans qui les montrent) ;
- arêtes `fk` = relation intra-application (jointure vue dans le code,
  dans le journal SQL, ou devinée par le nom `<table>_id` / `id_<table>`) ;
- arêtes `equiv` = même notion dans deux applications (écrans de même
  fonction de la spec unique, ou tables de même nom canonique), avec les
  colonnes appariées ;
- arêtes `xref` = colonne d'une application qui nomme une table d'une
  AUTRE application (`client_id` dans un CRM sans table clients) :
  relation inter-gestion probable.

`fusion_proposal(graph)` → proposition d'évolution : entités cibles (une
par groupe d'entités équivalentes, nommée par le terme canonique), union
des attributs avec la correspondance par application, conflits de types,
attributs orphelins (une seule application), relations conservées entre
entités cibles, entités propres à une application gardées telles quelles.
Chaque élément porte sa source : rien n'est fusionné sans raison visible.
"""
import re

from merge import _term, _canon
from php_sql_scanner import extract_join_candidates_from_sql

_ID_PATTERNS = (re.compile(r"^(.+?)_id$"), re.compile(r"^id_(.+)$"), re.compile(r"^(.+?)id$"))


def _node_id(app, table):
    return "%s:%s" % (app, table)


def _guess_ref_table(column, tables_by_term):
    """Table désignée par un nom de colonne `ville_id` / `id_ville` /
    `villeid` parmi `tables_by_term` {terme canonique: table} ; None sinon."""
    c = (column or "").lower()
    for p in _ID_PATTERNS:
        m = p.match(c)
        if m and len(m.group(1)) >= 3:
            t = _term(m.group(1))
            if t in tables_by_term:
                return tables_by_term[t]
    return None


def _columns_of(spec, columns_by_table, table):
    """[{name, type, pk}] d'une table : colonnes typées si fournies, sinon
    noms de la spec, sinon colonnes vues dans les écrans."""
    typed = (columns_by_table or {}).get(table)
    if typed:
        return [{"name": c.get("name"), "type": c.get("type"), "pk": bool(c.get("primary_key"))} for c in typed if c.get("name")]
    names = (spec.get("tables") or {}).get(table) or []
    pk = next((s.get("pk") for s in spec.get("screens") or [] if s.get("table") == table and s.get("pk")), None)
    if names:
        return [{"name": n, "type": None, "pk": n == pk} for n in names]
    seen = []
    for s in spec.get("screens") or []:
        if s.get("table") != table:
            continue
        for c in (s.get("columns") or []) + (s.get("fields") or []):
            if c.get("column") and c["column"] not in seen:
                seen.append(c["column"])
        if s.get("pk") and s["pk"] not in seen:
            seen.insert(0, s["pk"])
    return [{"name": n, "type": None, "pk": n == pk} for n in seen]


def build_metagraph(specs, scans=None, queries_by_app=None, unified=None, columns_by_app=None):
    """`specs` {app: spec} ; `scans` {app: scan} ; `queries_by_app` {app:
    [{sql}]} ; `unified` : merge.unified_spec ; `columns_by_app` {app:
    {table: [{name, type, primary_key}]}}."""
    scans, queries_by_app, columns_by_app = scans or {}, queries_by_app or {}, columns_by_app or {}
    apps = sorted(specs)
    nodes, edges = {}, {}

    def add_edge(a, b, kind, source, **extra):
        key = (a, b, kind)
        e = edges.get(key)
        if e is None:
            e = edges[key] = {"from": a, "to": b, "kind": kind, "sources": [], "columns": [], "score": extra.get("score")}
        if source not in e["sources"]:
            e["sources"].append(source)
        for pair in extra.get("columns") or []:
            if pair not in e["columns"]:
                e["columns"].append(pair)
        if extra.get("score") is not None:
            e["score"] = max(e["score"] or 0, extra["score"])
        return e

    # 1. entités et attributs
    for app in apps:
        spec = specs[app] or {}
        tables = set((spec.get("tables") or {}).keys()) | {s.get("table") for s in spec.get("screens") or [] if s.get("table")}
        for c in (scans.get(app) or {}).get("join_candidates") or []:
            tables |= {c.get("from_table"), c.get("to_table")}
        for t in sorted(x for x in tables if x):
            cols = _columns_of(spec, columns_by_app.get(app), t)
            screens = [{"id": s["id"], "title": s.get("title"), "kind": s.get("kind")} for s in spec.get("screens") or [] if s.get("table") == t]
            shown = {}
            for s in spec.get("screens") or []:
                if s.get("table") != t:
                    continue
                for c in (s.get("columns") or []) + (s.get("fields") or []):
                    if c.get("column"):
                        shown.setdefault(c["column"], []).append(s["id"])
            for c in cols:
                c["term"] = _term(c["name"])
                c["screens"] = shown.get(c["name"], [])
            nodes[_node_id(app, t)] = {"id": _node_id(app, t), "app": app, "table": t, "term": _term(t), "columns": cols, "screens": screens,
                                       "in_code": bool((scans.get(app) or {}).get("file_tables")) and any(t in v for v in ((scans.get(app) or {}).get("file_tables") or {}).values())}

    # 2. relations intra-application : code, journal SQL, noms de colonnes
    for app in apps:
        for c in (scans.get(app) or {}).get("join_candidates") or []:
            a, b = _node_id(app, c.get("to_table")), _node_id(app, c.get("from_table"))
            if a in nodes and b in nodes and a != b:
                add_edge(a, b, "fk", "code", columns=[[c.get("to_column"), c.get("from_column")]])
        seen_sql = set()
        for q in queries_by_app.get(app) or []:
            sql = q.get("sql") if isinstance(q, dict) else q
            if not sql or sql in seen_sql:
                continue
            seen_sql.add(sql)
            for c in extract_join_candidates_from_sql(sql):
                a, b = _node_id(app, c.get("to_table")), _node_id(app, c.get("from_table"))
                if a in nodes and b in nodes and a != b:
                    add_edge(a, b, "fk", "journal SQL", columns=[[c.get("to_column"), c.get("from_column")]])
        by_term = {n["term"]: n["table"] for n in nodes.values() if n["app"] == app}
        for n in [n for n in nodes.values() if n["app"] == app]:
            for c in n["columns"]:
                if c["pk"]:
                    continue
                ref = _guess_ref_table(c["name"], by_term)
                if ref and ref != n["table"]:
                    target = nodes[_node_id(app, ref)]
                    pk = next((x["name"] for x in target["columns"] if x["pk"]), "id")
                    add_edge(n["id"], target["id"], "fk", "nom de colonne", columns=[[c["name"], pk]])

    # 3. équivalences inter-applications : spec unique (écrans de même fonction), puis noms canoniques
    for s in (unified or {}).get("screens") or []:
        targets = s.get("targets") or {}
        if len(targets) < 2:
            continue
        pairs = {}
        for f in (s.get("fields") or []) + (s.get("columns") or []):
            src = f.get("sources") or {}
            for a in src:
                for b in src:
                    if a < b and src[a].get("column") and src[b].get("column"):
                        pairs.setdefault((a, b), []).append([src[a]["column"], src[b]["column"]])
        tapps = sorted(targets)
        for i, a in enumerate(tapps):
            for b in tapps[i + 1:]:
                na, nb = _node_id(a, targets[a].get("table")), _node_id(b, targets[b].get("table"))
                if na in nodes and nb in nodes:
                    add_edge(na, nb, "equiv", "écran « %s »" % s.get("title"), columns=[p for p in pairs.get((a, b), []) if p not in []], score=s.get("score"))
    for i, a in enumerate(apps):
        for b in apps[i + 1:]:
            for na in [n for n in nodes.values() if n["app"] == a]:
                for nb in [n for n in nodes.values() if n["app"] == b]:
                    if na["term"] and na["term"] == nb["term"]:
                        e = add_edge(na["id"], nb["id"], "equiv", "même nom de table", score=0.5)
                        # colonnes de même terme
                        tb = {c["term"]: c["name"] for c in nb["columns"] if c["term"]}
                        for c in na["columns"]:
                            if c["term"] in tb and [c["name"], tb[c["term"]]] not in e["columns"]:
                                e["columns"].append([c["name"], tb[c["term"]]])
    # colonnes de même terme et clés primaires sur les équivalences (complète les paires)
    for e in edges.values():
        if e["kind"] != "equiv":
            continue
        na, nb = nodes[e["from"]], nodes[e["to"]]
        tb = {c["term"]: c["name"] for c in nb["columns"] if c["term"]}
        for c in na["columns"]:
            if c["term"] in tb and not any(p[0] == c["name"] for p in e["columns"]):
                e["columns"].append([c["name"], tb[c["term"]]])
        pa, pb = next((c["name"] for c in na["columns"] if c["pk"]), None), next((c["name"] for c in nb["columns"] if c["pk"]), None)
        if pa and pb and not any(p[0] == pa or p[1] == pb for p in e["columns"]):
            e["columns"].append([pa, pb])

    # 4. références inter-gestions : colonne qui nomme une table absente ici mais présente ailleurs
    for app in apps:
        own_terms = {n["term"] for n in nodes.values() if n["app"] == app}
        others = {}
        for n in nodes.values():
            if n["app"] != app:
                others.setdefault(n["term"], []).append(n)
        for n in [n for n in nodes.values() if n["app"] == app]:
            for c in n["columns"]:
                if c["pk"]:
                    continue
                ref = _guess_ref_table(c["name"], {t: t for t in others if t not in own_terms})
                if ref:
                    for target in others[ref]:
                        add_edge(n["id"], target["id"], "xref", "colonne %s sans table %s dans %s" % (c["name"], ref, app), columns=[[c["name"], next((x["name"] for x in target["columns"] if x["pk"]), "id")]], score=0.4)

    edge_list = sorted(edges.values(), key=lambda e: ({"fk": 0, "equiv": 1, "xref": 2}[e["kind"]], e["from"], e["to"]))
    for e in edge_list:
        e["score"] = round(e["score"], 3) if e["score"] is not None else None
    node_list = sorted(nodes.values(), key=lambda n: (n["app"], n["table"]))
    return {"version": 1, "apps": apps, "nodes": node_list, "edges": edge_list,
            "counts": {"nodes": len(node_list), "columns": sum(len(n["columns"]) for n in node_list),
                       "fk": sum(1 for e in edge_list if e["kind"] == "fk"), "equiv": sum(1 for e in edge_list if e["kind"] == "equiv"),
                       "xref": sum(1 for e in edge_list if e["kind"] == "xref"),
                       "by_app": {a: sum(1 for n in node_list if n["app"] == a) for a in apps}}}


def _norm_type(t):
    """Famille d'un type SQL : int / decimal / text / date / bool / autre."""
    s = (t or "").lower()
    if not s:
        return None
    if re.match(r"^(tiny|small|medium|big)?int|^integer|^serial", s):
        return "bool" if s.startswith("tinyint(1)") else "int"
    if re.match(r"^(decimal|numeric|float|double|real|money)", s):
        return "decimal"
    if re.match(r"^(var)?char|^text|^(tiny|medium|long)text|^enum|^set|^json|^uuid", s):
        return "text"
    if re.match(r"^date|^time|^year", s):
        return "date"
    if s.startswith("bool") or s.startswith("bit"):
        return "bool"
    return "autre"


def fusion_proposal(graph):
    """Groupes d'entités équivalentes (fermeture transitive des arêtes
    `equiv`) → entités cibles ; attributs = union par terme canonique avec
    la colonne de chaque application ; conflits de types, orphelins ;
    relations `fk` / `xref` reportées entre entités cibles."""
    nodes = {n["id"]: n for n in graph.get("nodes") or []}
    parent = {nid: nid for nid in nodes}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    equiv_cols = {}  # (node_a, node_b) -> [[col_a, col_b]]
    for e in graph.get("edges") or []:
        if e["kind"] == "equiv" and e["from"] in parent and e["to"] in parent:
            parent[find(e["from"])] = find(e["to"])
            equiv_cols[(e["from"], e["to"])] = e.get("columns") or []
    groups = {}
    for nid in nodes:
        groups.setdefault(find(nid), []).append(nid)
    entities = []
    target_of = {}
    for members in groups.values():
        members = sorted(members)
        ms = [nodes[m] for m in members]
        apps = sorted({m["app"] for m in ms})
        name = _majority_term(ms)
        # attributs : union par terme, colonnes appariées par les arêtes ou par terme canonique
        attrs = {}
        for m in ms:
            for c in m["columns"]:
                key = "id" if c.get("pk") else (c["term"] or c["name"])
                # une colonne déjà appariée explicitement à un attribut existant ?
                for (a, b), pairs in equiv_cols.items():
                    for pa, pb in pairs:
                        if (a == m["id"] and pa == c["name"]) or (b == m["id"] and pb == c["name"]):
                            other = pb if a == m["id"] else pa
                            other_node = b if a == m["id"] else a
                            for k, at in attrs.items():
                                if at["columns"].get(nodes[other_node]["app"], {}).get("column") == other:
                                    key = k
                at = attrs.setdefault(key, {"name": key.replace(" ", "_"), "columns": {}, "types": {}, "screens": 0})
                at["columns"][m["app"]] = {"table": m["table"], "column": c["name"], "type": c.get("type"), "pk": c.get("pk")}
                fam = _norm_type(c.get("type"))
                if fam:
                    at["types"][m["app"]] = fam
                at["screens"] += len(c.get("screens") or [])
        attr_list = []
        for at in attrs.values():
            fams = set(at["types"].values())
            at["shared"] = len(at["columns"]) == len(apps) and len(apps) > 1
            at["orphan"] = len(apps) > 1 and len(at["columns"]) == 1
            at["type_conflict"] = sorted(fams) if len(fams) > 1 else None
            at["pk"] = any(v.get("pk") for v in at["columns"].values())
            attr_list.append(at)
        attr_list.sort(key=lambda a: (not a["pk"], not a["shared"], a["name"]))
        ent = {"name": name, "members": [{"app": m["app"], "table": m["table"], "id": m["id"]} for m in ms], "apps": apps,
               "attributes": attr_list, "shared": len(apps) == len(graph.get("apps") or []) and len(apps) > 1,
               "counts": {"attributes": len(attr_list), "shared": sum(1 for a in attr_list if a["shared"]), "orphans": sum(1 for a in attr_list if a["orphan"]),
                          "conflicts": sum(1 for a in attr_list if a["type_conflict"])}}
        ent["todo"] = [t for t in ((("%d conflit(s) de type à arbitrer" % ent["counts"]["conflicts"]) if ent["counts"]["conflicts"] else None),
                                   (("%d attribut(s) propre(s) à une application" % ent["counts"]["orphans"]) if ent["counts"]["orphans"] else None),
                                   (None if len(apps) > 1 else "propre à %s : reprise telle quelle" % apps[0])) if t]
        entities.append(ent)
        for m in members:
            target_of[m] = ent
    entities.sort(key=lambda e: (-len(e["apps"]), -e["counts"]["attributes"], e["name"]))
    # relations entre entités cibles
    rels = {}
    for e in graph.get("edges") or []:
        if e["kind"] not in ("fk", "xref"):
            continue
        a, b = target_of.get(e["from"]), target_of.get(e["to"])
        if not a or not b or a is b:
            continue
        key = (a["name"], b["name"], e["kind"])
        r = rels.setdefault(key, {"from": a["name"], "to": b["name"], "kind": e["kind"], "sources": [], "via": []})
        for s in e["sources"]:
            if s not in r["sources"]:
                r["sources"].append(s)
        r["via"].append({"from": e["from"], "to": e["to"], "columns": e.get("columns")})
    relations = sorted(rels.values(), key=lambda r: (r["kind"], r["from"], r["to"]))
    return {"version": 1, "apps": graph.get("apps") or [], "entities": entities, "relations": relations,
            "counts": {"entities": len(entities), "merged": sum(1 for e in entities if len(e["apps"]) > 1), "kept": sum(1 for e in entities if len(e["apps"]) == 1),
                       "relations": len(relations), "conflicts": sum(e["counts"]["conflicts"] for e in entities), "orphans": sum(e["counts"]["orphans"] for e in entities)}}


def _majority_term(members):
    terms = [m["term"] for m in members if m["term"]]
    if not terms:
        return members[0]["table"]
    best = max(sorted(set(terms)), key=terms.count)
    return best.replace(" ", "_")
