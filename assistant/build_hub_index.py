# -*- coding: utf-8 -*-
"""Index du hub pour les questions pratiques (#715), construit À LA CONSTRUCTION DE L'IMAGE depuis le dépôt :
  - catalogue des vues : hub/src/hubThemes.js (source unique de l'accueil et des menus) ;
  - routes d'API : décorateurs @app.route / @bp.route des fichiers Python des modules, avec la 1re ligne
    de la docstring de la fonction.
  python3 assistant/build_hub_index.py <racine du dépôt> <fichier de sortie .json>"""
import json
import os
import re
import sys

THEME = re.compile(r'\{\s*id:\s*"([^"]+)",\s*name:\s*"([^"]+)"(?:.*?description:\s*"([^"]*)")?')
ENTRY = re.compile(r'\{\s*(view|front):\s*"([^"]+)",\s*label:\s*"([^"]+)"')
ROUTE = re.compile(r'@(?:app|bp|blueprint|api)\.(?:route|get|post|put|delete)\(\s*(?:[A-Z_]+\s*\+\s*)?["\']([^"\']*)["\']([^)]*)\)')
DEF = re.compile(r'^\s*def\s+(\w+)\s*\(')
SKIP = {"node_modules", "tests", "test", "__pycache__", ".git", "dist", "build", "data", "samples", "docs"}


def parse_themes(text):
    out, theme = [], None
    for line in text.splitlines():
        m = THEME.search(line)
        if m:
            theme = {"theme": m.group(2), "theme_id": m.group(1), "description": m.group(3) or ""}
        for kind, ident, label in ENTRY.findall(line):
            if theme:
                out.append({kind: ident, "label": label, "theme": theme["theme"], "description": theme["description"]})
    return out


def parse_routes(text, module):
    lines = text.splitlines()
    out = []
    for i, line in enumerate(lines):
        m = ROUTE.search(line)
        if not m:
            continue
        meth = re.findall(r'"(GET|POST|PUT|PATCH|DELETE)"|\'(GET|POST|PUT|PATCH|DELETE)\'', m.group(2))
        methods = ",".join(a or b for a, b in meth) or ("POST" if ".post(" in line else "GET")
        fn, doc = "", ""
        for j in range(i + 1, min(i + 8, len(lines))):
            d = DEF.match(lines[j])
            if d:
                fn = d.group(1)
                rest = "\n".join(lines[j + 1:j + 6])
                ds = re.match(r'\s*(?:"""|\'\'\')(.*?)(?:"""|\'\'\'|\n)', rest, re.S)
                doc = ds.group(1).strip() if ds else ""
                break
        out.append({"module": module, "path": m.group(1) or "/", "methods": methods, "function": fn, "doc": doc[:200]})
    return out


def build(root):
    catalog = []
    themes = os.path.join(root, "hub", "src", "hubThemes.js")
    if os.path.isfile(themes):
        with open(themes, encoding="utf-8") as fh:
            catalog = parse_themes(fh.read())
    routes = []
    for top in sorted(os.listdir(root)):
        base = os.path.join(root, top)
        if not os.path.isdir(base) or top in SKIP or top.startswith("."):
            continue
        for dirpath, dirs, files in os.walk(base):
            dirs[:] = [d for d in dirs if d not in SKIP and not d.startswith(".")]
            if dirpath.count(os.sep) - base.count(os.sep) > 2:
                continue
            for f in files:
                if f.endswith(".py") and not f.startswith("test"):
                    try:
                        with open(os.path.join(dirpath, f), encoding="utf-8", errors="replace") as fh:
                            routes += parse_routes(fh.read(), top)
                    except OSError:
                        pass
    return {"catalog": catalog, "routes": routes}


if __name__ == "__main__":
    idx = build(sys.argv[1] if len(sys.argv) > 1 else ".")
    out = sys.argv[2] if len(sys.argv) > 2 else "hub-index.json"
    os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(idx, fh, ensure_ascii=False)
    print("hub-index : %d vues, %d routes" % (len(idx["catalog"]), len(idx["routes"])))
