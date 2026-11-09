# -*- coding: utf-8 -*-
"""#999 : instances ownCloud (sonde owncloud des agents) -- synthèse pour le hub et pour le plan de migration :
statut de chaque compte (actif / récent / inactif / jamais connecté), doublons (même nom affiché), comptes locaux hors
annuaire, gains possibles (corbeilles, comptes inactifs), données vivantes après décisions, et les étapes de migration
d'une instance avec leur état (à décider, accepté, refusé, fait) enregistré dans le hub. Pur, testé dans test_z_owncloud.py."""
import re
import unicodedata

ETATS = ("a_decider", "accepte", "refuse", "a_faire", "fait")
ETAPES = (
    ("corbeilles", "décision", "Conservation des corbeilles", "fixer une durée de conservation (ex. 90 jours) : les fichiers supprimés plus anciens sont purgés"),
    ("comptes_inactifs", "décision", "Comptes inactifs depuis plus d'un an", "archiver leurs fichiers puis supprimer les comptes, après accord (données de l'entreprise)"),
    ("doublons", "décision", "Comptes en double", "garder un compte par personne : récupérer les fichiers de l'ancien puis le supprimer"),
    ("comptes_locaux", "décision", "Comptes locaux hors annuaire", "désactiver ceux qui ne servent pas ; garder « admin » avec un mot de passe fort"),
    ("sauvegarde", "étape", "Sauvegarde vérifiée", "sauvegarde complète (données + base) restaurée à l'essai avant tout geste"),
    ("systeme", "étape", "Système maintenu", "passer sur une version de Debian encore suivie (Debian 12 ou 13)"),
    ("cible", "étape", "Hébergement cible", "sur place, ou VM sur le cluster du LAN, avec la place pour les données vivantes et la croissance"),
    ("owncloud", "étape", "ownCloud à jour", "dernière version 10.x, applications vérifiées, après la sauvegarde"),
)


def _cle_nom(nom):
    n = unicodedata.normalize("NFKD", str(nom or "")).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", n).strip().lower()


def statut(c, maintenant, actif_jours=30, dormant_jours=365):
    d = c.get("derniere_connexion")
    if not d:
        return "jamais"
    age = (maintenant - d) / 86400.0
    return "actif" if age <= actif_jours else "recent" if age <= dormant_jours else "inactif"


def synthese(data, decisions=None, maintenant=0):
    """Mesure de la sonde owncloud + décisions enregistrées -> {comptes (avec statut, doublon), chiffres, etapes}."""
    data = data or {}
    tot = data.get("totaux") or {}
    aj, dj = int(tot.get("actif_jours") or 30), int(tot.get("dormant_jours") or 365)
    groupes = {}
    for c in data.get("comptes") or []:
        groupes.setdefault(_cle_nom(c.get("nom")), []).append(c.get("id"))
    comptes = []
    for c in data.get("comptes") or []:
        x = dict(c)
        x["statut"] = statut(c, maintenant, aj, dj)
        x["doublon"] = len(groupes.get(_cle_nom(c.get("nom")), [])) > 1 and c.get("origine") != "locale"
        comptes.append(x)
    inactifs = [c for c in comptes if c["statut"] in ("inactif", "jamais") and c.get("origine") != "locale"]
    locaux = [c for c in comptes if c.get("origine") == "locale" and c.get("id") != "admin"]
    doublons = sorted({c["nom"] for c in comptes if c["doublon"]})
    go_inactifs = round(sum((c.get("go_fichiers") or 0) for c in inactifs), 1)
    fichiers, corbeilles, versions = tot.get("fichiers") or 0, tot.get("corbeilles") or 0, tot.get("versions") or 0
    systeme = (data.get("instance") or {}).get("systeme") or {}
    chiffres = {
        "comptes": len(comptes), "actifs": sum(1 for c in comptes if c["statut"] == "actif"), "recents": sum(1 for c in comptes if c["statut"] == "recent"),
        "inactifs": len(inactifs), "go_inactifs": go_inactifs, "locaux": [c["id"] for c in locaux], "doublons": doublons,
        "go_fichiers": fichiers, "go_corbeilles": corbeilles, "go_versions": versions, "go_total": round(fichiers + corbeilles + versions, 1),
        "go_vivantes": round(max(0.0, fichiers - go_inactifs) + versions, 1),
        "actions_30j": sum(a.get("actions") or 0 for a in (data.get("activite") or [])[-30:]),
    }
    detail = {
        "corbeilles": "%s Go en corbeilles (%s)" % (corbeilles, (data.get("instance") or {}).get("conservation_corbeille") or "conservation par défaut : purge seulement quand la place manque"),
        "comptes_inactifs": "%d compte(s), %s Go de fichiers" % (len(inactifs), go_inactifs),
        "doublons": ", ".join(doublons) or "aucun",
        "comptes_locaux": ", ".join(chiffres["locaux"]) or "aucun",
        "sauvegarde": "à vérifier",
        "systeme": "%s%s" % (systeme.get("nom") or "?", (" -- sans mises à jour de sécurité depuis le %s" % systeme["fin"]) if systeme.get("depasse") else ""),
        "cible": "%s Go de données vivantes après décisions (%s Go aujourd'hui)" % (chiffres["go_vivantes"], chiffres["go_total"]),
        "owncloud": (data.get("instance") or {}).get("version") or "?",
    }
    dec = decisions or {}
    etapes = []
    for eid, genre, titre, aide in ETAPES:
        d = dec.get(eid) or {}
        defaut = "a_decider" if genre == "décision" else "a_faire"
        if eid == "doublons" and not doublons or eid == "comptes_locaux" and not locaux:
            defaut = "fait"
        if eid == "systeme" and systeme.get("fin") and not systeme.get("depasse"):
            defaut = "fait"
        etapes.append({"id": eid, "genre": genre, "titre": titre, "aide": aide, "detail": detail[eid],
                       "etat": d.get("etat") if d.get("etat") in ETATS else defaut, "note": d.get("note") or "", "par": d.get("par"), "le": d.get("le")})
    return {"comptes": comptes, "chiffres": chiffres, "etapes": etapes}


def valider_decision(b):
    b = b or {}
    if b.get("etape") not in {e[0] for e in ETAPES}:
        return "étape inconnue"
    if b.get("etat") not in ETATS:
        return "état : %s" % ", ".join(ETATS)
    if len(str(b.get("note") or "")) > 1000:
        return "note trop longue (1 000 caractères)"
    if not re.match(r"^[A-Za-z0-9._-]{1,64}$", str(b.get("agent_id") or "")):
        return "agent_id requis"
    return None
