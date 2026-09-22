# -*- coding: utf-8 -*-
"""Espace « Simple » pour les non-initiés (livraison #541) -- logique PURE,
testée (tests/test_simple.py) : l'état d'une demande en français courant,
et l'état des services avec propagation des dépendances (« le Wi-Fi du
bâtiment B est en panne, donc la messagerie ne marche pas depuis ce
bâtiment »). Voir docs/ergonomie-redesign.md.

Le référentiel de services est un JSON tenu par l'administration :
  {"services": [{"id": "reseau-b", "nom": "Réseau du bâtiment B",
                 "sert_a": "se connecter depuis le bâtiment B",
                 "depend_de": ["coeur-reseau"]}, …]}
et les états un JSON posé par l'exploitation (ou plus tard service-watch /
Cortex) : {"a": "2026-09-22T09:00:00Z",
           "etats": {"reseau-b": {"etat": "panne", "depuis": "…", "message": "…"}}}
Un service absent des états est considéré « ok »."""
import time

ETATS = ("ok", "degrade", "panne")
REF_PREFIX = "D-"


def public_ref(key):
    """Numéro de suivi montré au demandeur : « D-<12 hex> », tiré de la clé
    du pont (`<label>:s:<hex>`) -- court, dictable au téléphone, sans le
    nom interne du pont. None pour une clé d'import (pas de suivi public)."""
    if not key or ":s:" not in str(key):
        return None
    return REF_PREFIX + str(key).rsplit(":s:", 1)[1].strip().lower()


def ref_matches(ref, key):
    """Le numéro saisi correspond-il à cette clé ? Tolère la casse, les
    espaces et l'absence du préfixe."""
    r = (ref or "").strip().lower().replace(" ", "")
    if r.startswith(REF_PREFIX.lower()):
        r = r[len(REF_PREFIX):]
    return bool(r) and public_ref(key) == REF_PREFIX + r
MOTS = {"ok": "ça marche", "degrade": "dégradé", "panne": "en panne"}


def plain_status(ticket, now=None):
    """Une demande vue par son demandeur : état en trois mots, dernier
    mouvement, conseil. Ne renvoie JAMAIS le contenu ni le demandeur :
    seulement ce qu'il faut pour savoir « où ça en est »."""
    if not ticket:
        return None
    now = now if now is not None else time.time()
    closed = bool(ticket.get("ts_closed"))
    label = (ticket.get("statut_label") or "").strip()
    created = ticket.get("ts_created") or 0
    updated = ticket.get("ts_updated") or ticket.get("ts_closed") or created
    if closed:
        etat, mot = "resolue", "résolue"
        conseil = "Si le problème revient, déposez une nouvelle demande en indiquant ce numéro."
    elif ticket.get("user_id") or ticket.get("user_login") or (label and label.lower() not in ("nouveau", "nouvelle", "à valider", "a valider", "ouvert", "reçue", "recue")):
        etat, mot = "en_cours", "en cours"
        conseil = "Quelqu'un s'en occupe. Vous serez contacté si un complément est nécessaire."
    else:
        etat, mot = "recue", "reçue"
        conseil = "Votre demande est dans la file du service informatique."
    attente_h = round((now - created) / 3600.0, 1) if created else None
    if etat != "resolue" and attente_h is not None and attente_h > 48:
        conseil = "Sans nouvelles depuis plus de deux jours : contactez le service informatique en citant ce numéro."
    return {
        "etat": etat, "mot": mot, "statut": label or None,
        "depuis": created or None, "dernier_mouvement": updated or None,
        "attente_heures": attente_h, "conseil": conseil,
        "sujet": (ticket.get("subject") or "")[:120] or None,
    }


def _index(services):
    return {s["id"]: s for s in services or [] if isinstance(s, dict) and s.get("id")}


def impacted(services, down_ids):
    """Services indirectement touchés : tout ce qui dépend (à n'importe
    quelle profondeur) d'un service en panne ou dégradé. Retourne
    {id: [causes racines]} ; les cycles sont tolérés."""
    idx = _index(services)
    down = set(down_ids or [])
    out = {}
    changed = True
    while changed:
        changed = False
        for sid, s in idx.items():
            if sid in down or sid in out:
                continue
            causes = []
            for dep in s.get("depend_de") or []:
                if dep in down:
                    causes.append(dep)
                elif dep in out:
                    causes.extend(out[dep])
            if causes:
                out[sid] = sorted(set(causes))
                changed = True
    return out


def etat_des_services(services, etats, now=None):
    """La page « Est-ce que ça marche ? » : chaque service en français,
    son état (direct ou hérité d'une dépendance), et une phrase pour les
    pannes : « X est en panne, donc Y et Z ne marchent pas »."""
    idx = _index(services)
    etats = etats or {}
    directs = {sid: e for sid, e in etats.items() if sid in idx and isinstance(e, dict) and e.get("etat") in ("degrade", "panne")}
    herites = impacted(services, list(directs))
    lignes, phrases = [], []
    for sid, s in idx.items():
        if sid in directs:
            e = directs[sid]
            etat, cause, message = e["etat"], None, e.get("message") or ""
            depuis = e.get("depuis")
        elif sid in herites:
            racines = herites[sid]
            pire = "panne" if any(directs[r]["etat"] == "panne" for r in racines) else "degrade"
            etat, cause, message, depuis = pire, racines, "", min((directs[r].get("depuis") or "" for r in racines), default=None) or None
        else:
            etat, cause, message, depuis = "ok", None, "", None
        lignes.append({"id": sid, "nom": s.get("nom") or sid, "sert_a": s.get("sert_a") or "", "etat": etat, "mot": MOTS[etat],
                       "cause": [idx[c].get("nom") or c for c in cause] if cause else [], "message": message, "depuis": depuis})
    for sid, e in directs.items():
        touches = [idx[t].get("nom") or t for t, racines in herites.items() if sid in racines]
        nom = idx[sid].get("nom") or sid
        if touches:
            phrases.append("%s : %s, donc %s ne %s pas." % (nom, MOTS[e["etat"]], ", ".join(touches), "marche" if len(touches) == 1 else "marchent"))
        else:
            phrases.append("%s : %s." % (nom, MOTS[e["etat"]]))
    ordre = {"panne": 0, "degrade": 1, "ok": 2}
    lignes.sort(key=lambda l: (ordre[l["etat"]], l["nom"].lower()))
    n_ko = sum(1 for l in lignes if l["etat"] != "ok")
    resume = "Tout fonctionne." if n_ko == 0 else ("%d service%s touché%s." % (n_ko, "s" if n_ko > 1 else "", "s" if n_ko > 1 else ""))
    return {"a": (etats.get("_a") if isinstance(etats, dict) else None), "resume": resume, "phrases": phrases, "services": lignes}
