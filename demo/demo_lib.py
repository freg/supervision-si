# -*- coding: utf-8 -*-
"""Démonstration automatisée du hub (livraison #982) -- logique pure (testée sans navigateur).

Un PARCOURS (demo/parcours/<id>.json) décrit une visite thématique : une suite d'étapes, chacune = une vue du hub
(?view=…&paramètres), des clics facultatifs (onglets, lignes), une attente, une capture et sa légende. Les variables
({terminal}, {site}…) se remplacent depuis le parcours ou la ligne de commande (--var terminal="E11 AmpIm").
"""
import json
import os
import re
from urllib.parse import urlencode

CHAMPS_ETAPE = {"titre", "legende", "vue", "params", "cliquer", "saisir", "attendre", "pause_ms", "zone", "defiler"}


def substituer(valeur, variables):
    """Remplace {nom} dans les chaînes (récursif sur listes / dicts) ; une variable inconnue reste telle quelle."""
    if isinstance(valeur, str):
        return re.sub(r"\{([a-z_]+)\}", lambda m: str(variables.get(m.group(1), m.group(0))), valeur)
    if isinstance(valeur, list):
        return [substituer(v, variables) for v in valeur]
    if isinstance(valeur, dict):
        return {k: substituer(v, variables) for k, v in valeur.items()}
    return valeur


def valider(p):
    """-> liste d'erreurs (vide = parcours utilisable)."""
    err = []
    if not isinstance(p, dict):
        return ["parcours : objet JSON attendu"]
    for k in ("id", "titre", "etapes"):
        if not p.get(k):
            err.append("champ « %s » manquant" % k)
    for i, e in enumerate(p.get("etapes") or [], 1):
        if not isinstance(e, dict):
            err.append("étape %d : objet attendu" % i)
            continue
        if not e.get("vue"):
            err.append("étape %d : « vue » manquante" % i)
        if not e.get("titre"):
            err.append("étape %d : « titre » manquant" % i)
        inconnus = set(e) - CHAMPS_ETAPE
        if inconnus:
            err.append("étape %d : champ(s) inconnu(s) %s" % (i, ", ".join(sorted(inconnus))))
    return err


def charger(chemin, variables=None):
    """Parcours lu, variables appliquées (celles du parcours, écrasées par la ligne de commande). -> (parcours, erreurs)."""
    with open(chemin, encoding="utf-8") as fh:
        p = json.load(fh)
    v = dict(p.get("variables") or {})
    v.update(variables or {})
    p = substituer(p, v)
    p["variables"] = v
    return p, valider(p)


def url_etape(base, etape):
    """URL du hub pour une étape : base + ?view=…&params (paramètres vides ignorés)."""
    q = {"view": etape["vue"]}
    q.update({k: v for k, v in (etape.get("params") or {}).items() if v not in (None, "")})
    return base.rstrip("/") + "/?" + urlencode(q)


def lister(dossier):
    """Parcours disponibles -> [(id, titre)]."""
    out = []
    for f in sorted(os.listdir(dossier)):
        if f.endswith(".json"):
            try:
                with open(os.path.join(dossier, f), encoding="utf-8") as fh:
                    out.append((f[:-5], json.load(fh).get("titre", "")))
            except (OSError, ValueError):
                out.append((f[:-5], "(illisible)"))
    return out


def nom_dossier(parcours_id, horodatage):
    return "%s-%s" % (re.sub(r"[^A-Za-z0-9_-]", "-", parcours_id), horodatage)
