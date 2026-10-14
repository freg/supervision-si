#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#762 : liste des mises à jour affichée en pied de page du hub -- générée depuis CHANGELOG.md (titres
« ## AAAA-MM-JJ — titre (livraison #N) »), les 40 dernières livraisons, dans hub/src/hubUpdates.json.
À relancer à chaque livraison (le test hub/tests/hubUpdates.test.mjs vérifie que la dernière y figure) :
    cd <racine du dépôt> && python3 scripts/gen-hub-updates.py"""
import json
import os
import re

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HEAD = re.compile(r"^## (\d{4}-\d{2}-\d{2}) — (.+?)\s*\(livraisons? #(\d+)(?:\s*[-à,]\s*#?(\d+))?[^)]*\)\s*$")


def parse(text, limit=40):
    out, seen = [], set()
    for line in text.splitlines():
        m = HEAD.match(line.strip())
        if not m:
            continue
        n = int(m.group(4) or m.group(3))
        if n in seen:
            continue
        seen.add(n)
        out.append({"n": n, "from": int(m.group(3)), "date": m.group(1), "title": m.group(2).strip()})
    out.sort(key=lambda x: -x["n"])
    return out[:limit]


if __name__ == "__main__":
    with open(os.path.join(ROOT, "CHANGELOG.md"), encoding="utf-8") as fh:
        items = parse(fh.read())
    path = os.path.join(ROOT, "hub", "src", "hubUpdates.json")
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(items, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    print("%d livraison(s) -> %s (dernière #%s)" % (len(items), os.path.relpath(path, ROOT), items[0]["n"] if items else "?"))
