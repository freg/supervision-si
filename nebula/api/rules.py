"""Règles lisibles (livraison #556) -- lecture des fichiers `rules/*.md`
(voir rules/README.md pour le format) et application aux anomalies typées.
Logique pure, testée dans nebula/tests/test_rules.py.

Une règle : identifiant (titre « ## R-XXX-NN · Titre »), puis des lignes
« - Clé : valeur ». Clés : Quand (type d'anomalie), Gravité, Action (avec
{champs}), Applicable (oui/non), Pourquoi, Vérifier, Exemples. Relu à
chaque appel ; un fichier illisible est ignoré avec une erreur en clair."""
import glob
import os
import re

SEVERITY_ORDER = {"haute": 0, "moyenne": 1, "basse": 2, "info": 3}
_TITLE = re.compile(r"^##\s+(?P<id>[A-Za-z][\w-]*)\s*[·:\-–]\s*(?P<title>.+?)\s*$")
_FIELD = re.compile(r"^-\s*(?P<key>[A-Za-zÀ-ÿ]+)\s*:\s*(?P<val>.*)$")
_KEYS = {"quand": "when", "gravité": "severity", "gravite": "severity", "action": "action", "applicable": "applicable",
         "pourquoi": "why", "vérifier": "verify", "verifier": "verify", "exemples": "examples", "exemple": "examples"}


def parse_rules(text, source=""):
    rules, cur, last_key = [], None, None
    for raw in text.splitlines():
        line = raw.rstrip()
        m = _TITLE.match(line)
        if m:
            cur = {"id": m.group("id"), "title": m.group("title"), "source": source, "when": None, "severity": "info", "action": "", "applicable": False, "why": "", "verify": "", "examples": ""}
            rules.append(cur)
            last_key = None
            continue
        if cur is None:
            continue
        if line.startswith("## ") or line.startswith("# "):
            cur, last_key = None, None
            continue
        f = _FIELD.match(line)
        if f and f.group("key").lower() in _KEYS:
            key = _KEYS[f.group("key").lower()]
            val = f.group("val").strip()
            if key == "applicable":
                cur[key] = val.lower().startswith("oui")
            elif key == "severity":
                cur[key] = val.lower() if val.lower() in SEVERITY_ORDER else "info"
            else:
                cur[key] = val
            last_key = key
        elif last_key and line.strip() and not line.startswith("-") and last_key not in ("when", "severity", "applicable"):
            cur[last_key] = (cur[last_key] + " " + line.strip()).strip()  # suite de paragraphe
    return [r for r in rules if r["when"]]


def load_rules(directory):
    """Toutes les règles des fichiers *.md du dossier ; (règles, erreurs)."""
    rules, errors = [], []
    for path in sorted(glob.glob(os.path.join(directory or "", "*.md"))):
        if os.path.basename(path).lower() == "readme.md":
            continue
        try:
            with open(path, encoding="utf-8") as fh:
                rules.extend(parse_rules(fh.read(), os.path.basename(path)))
        except OSError as exc:
            errors.append("%s : %s" % (os.path.basename(path), exc))
    return rules, errors


class _Safe(dict):
    def __missing__(self, key):
        return "{" + key + "}"


def _fmt(template, details):
    d = {k: (", ".join(map(str, v)) if isinstance(v, (list, tuple)) else v) for k, v in (details or {}).items()}
    try:
        return template.format_map(_Safe(d))
    except (ValueError, IndexError):
        return template


def apply_rules(anomalies, rules):
    """Complète chaque anomalie typée avec rule_id, severity, action,
    applicable, why, verify. Type sans règle : action « à qualifier »."""
    by_when = {}
    for r in rules:
        by_when.setdefault(r["when"], r)
    out = []
    for a in anomalies or []:
        r = by_when.get(a.get("kind"))
        b = dict(a)
        if r:
            b.update({"rule_id": r["id"], "rule_title": r["title"], "severity": r["severity"], "action": _fmt(r["action"], a.get("details")),
                      "applicable": bool(r["applicable"]), "why": r["why"], "verify": r["verify"]})
        else:
            b.update({"rule_id": None, "rule_title": None, "severity": "info", "action": "À qualifier : aucune règle pour le type « %s » (ajouter une règle dans rules/)." % a.get("kind"),
                      "applicable": False, "why": "", "verify": ""})
        out.append(b)
    out.sort(key=lambda x: (SEVERITY_ORDER.get(x["severity"], 9), x.get("element") or "", x.get("message") or ""))
    return out
