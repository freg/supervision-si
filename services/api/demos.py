# -*- coding: utf-8 -*-
"""Tuile « Démonstrations » (livraison #984) -- logique pure : parcours disponibles (demo/parcours), visites générées
(demo/sorties/<parcours>-<date>/manifeste.json), fichiers servis (noms contrôlés : jamais de chemin libre), commande de
génération (./scripts/demo.sh, valeurs des variables restreintes et citées)."""
import json
import os
import re
import shlex
import shutil

RE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}$")
RE_DOSSIER = re.compile(r"^[a-z0-9][a-z0-9_-]{0,40}-\d{8}-\d{4}$")
RE_FICHIER = re.compile(r"^(diaporama\.html|journal\.txt|manifeste\.json|\d{2}\.png|[a-z0-9_-]{1,41}\.pptx)$")
RE_VAR = re.compile(r"^[a-z_]{1,30}$")
RE_VALEUR = re.compile(r"^[\w .:/'()+-]{0,80}$", re.UNICODE)
TYPES = {".html": "text/html; charset=utf-8", ".txt": "text/plain; charset=utf-8", ".json": "application/json",
         ".png": "image/png", ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation"}


def _json(chemin):
    try:
        with open(chemin, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def parcours(projet):
    d = os.path.join(projet, "demo", "parcours")
    out = []
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        p = _json(os.path.join(d, f)) if f.endswith(".json") else None
        if p and RE_ID.match(f[:-5]):
            out.append({"id": f[:-5], "titre": p.get("titre", f[:-5]), "sous_titre": p.get("sous_titre", ""), "public": p.get("public", ""),
                        "variables": p.get("variables") or {}, "etapes": len(p.get("etapes") or [])})
    return out


def visites(projet):
    d = os.path.join(projet, "demo", "sorties")
    out = []
    for nom in sorted(os.listdir(d), reverse=True) if os.path.isdir(d) else []:
        m = _json(os.path.join(d, nom, "manifeste.json")) if RE_DOSSIER.match(nom) else None
        if not m:
            continue
        fichiers = set(os.listdir(os.path.join(d, nom)))
        pptx = next((f for f in sorted(fichiers) if f.endswith(".pptx") and RE_FICHIER.match(f)), None)
        rem = ["%s : %s" % (e.get("titre"), r) for e in m.get("etapes") or [] for r in e.get("remarques") or []]
        out.append({"dossier": nom, "id": m.get("id"), "titre": m.get("titre"), "date": m.get("date"), "livraison": m.get("livraison"),
                    "public": m.get("public"), "etapes": len(m.get("etapes") or []), "remarques": rem, "pptx": pptx,
                    "diaporama": "diaporama.html" in fichiers, "apercu": (m.get("etapes") or [{}])[0].get("image")})
    return out


def fichier(projet, dossier, nom):
    """Chemin d'un fichier d'une visite, ou None (nom non conforme, absent)."""
    if not RE_DOSSIER.match(dossier or "") or not RE_FICHIER.match(nom or ""):
        return None
    p = os.path.join(projet, "demo", "sorties", dossier, nom)
    return p if os.path.isfile(p) else None


def supprimer(projet, dossier):
    """#992 : supprime une visite (dossier demo/sorties/<parcours>-<date>) ; nom contrôlé, jamais de chemin libre.
    Renvoie un message d'erreur, ou None si c'est fait."""
    if not RE_DOSSIER.match(dossier or ""):
        return "nom de visite non conforme"
    d = os.path.join(projet, "demo", "sorties", dossier)
    if os.path.islink(d) or not os.path.isfile(os.path.join(d, "manifeste.json")):
        return "visite inconnue"
    try:
        shutil.rmtree(d)
    except OSError as exc:
        return "suppression impossible : %s" % exc
    return None


def type_mime(nom):
    return TYPES.get(os.path.splitext(nom)[1], "application/octet-stream")


def commande(pid, variables, connus):
    """-> (commande shell, erreur). La commande se lance depuis la racine du dépôt."""
    if pid not in connus:
        return None, "parcours inconnu : %s" % pid
    args = ["./scripts/demo.sh", pid]
    for k, v in sorted((variables or {}).items()):
        if not RE_VAR.match(str(k)) or not RE_VALEUR.match(str(v)):
            return None, "variable refusée : %s (lettres, chiffres, espaces et . : / ' ( ) + - seulement)" % k
        args += ["--var", "%s=%s" % (k, v)]
    return " ".join(shlex.quote(a) for a in args), None
