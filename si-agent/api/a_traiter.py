# -*- coding: utf-8 -*-
"""Erreurs à traiter des agents hôtes (livraison #977) -- logique pure.

Le bandeau du hub n'affiche plus des compteurs (« 72 critiques ») mais la liste des PROBLÈMES : événements critiques
regroupés par (agent, genre, tâche de sonde), sauf ceux qu'un événement de rétablissement a suivis (sonde revenue,
agent de nouveau en ligne, déblocage), plus les agents hors ligne et bloqués. Chaque élément a une clé stable : le hub
s'en sert pour « ignorer pour la journée » et pour le lien vers l'objet (fiche de l'agent, bon onglet).
"""
import json

RETABLISSEMENT = {"probe-alert": "probe-recovered", "backup-alert": "backup-recovered", "agent-offline": "agent-online",
                  "plugin-blocked": "plugin-unblocked", "agent-blocked": "agent-unblocked", "fleet-blocked": "fleet-unblocked",
                  "blocked": "unblocked"}
GENRES_RETABLISSEMENT = set(RETABLISSEMENT.values())
_ORIGINE = {v: k for k, v in RETABLISSEMENT.items()}


def _details(e):
    d = e.get("details")
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except ValueError:
            d = {}
    return d if isinstance(d, dict) else {}


def regrouper(events, hors_ligne=(), bloques=(), severites=("critical",), limite=60):
    """events : dicts {at, agent_id, kind, severity, message, details} (ordre quelconque) -> [élément à traiter]."""
    groupes = {}
    for e in sorted(events or [], key=lambda x: (x.get("at") or "", x.get("id") or 0)):
        d = _details(e)
        tache = str(d.get("task") or d.get("plugin") or "")
        agent, kind = e.get("agent_id") or "", e.get("kind") or ""
        if kind in GENRES_RETABLISSEMENT:
            origine = _ORIGINE[kind]
            for cle in [k for k, g in groupes.items() if g["agent_id"] == agent and g["kind"] == origine and (not tache or g["tache"] == tache)]:
                del groupes[cle]            # rétabli après la dernière alerte : plus à traiter
            continue
        if e.get("severity") not in severites:
            continue
        cle = "%s|%s|%s" % (agent, kind, tache)
        g = groupes.setdefault(cle, {"cle": cle, "agent_id": agent or None, "kind": kind, "tache": tache or None, "severity": e.get("severity"),
                                     "n": 0, "premiere": e.get("at"), "derniere": e.get("at"), "message": ""})
        g["n"] += 1
        g["derniere"] = e.get("at")
        g["message"] = str(e.get("message") or "")[:300]
    items = list(groupes.values())
    deja = {g["agent_id"] for g in items if g["kind"] == "agent-offline"}
    for a in hors_ligne or ():
        if a not in deja:
            items.append({"cle": "%s|agent-offline|" % a, "agent_id": a, "kind": "agent-offline", "tache": None, "severity": "critical",
                          "n": 1, "premiere": None, "derniere": None, "message": "agent hors ligne"})
    for a in bloques or ():
        items.append({"cle": "%s|agent-blocked|" % a, "agent_id": a, "kind": "agent-blocked", "tache": None, "severity": "critical",
                      "n": 1, "premiere": None, "derniere": None, "message": "agent bloqué"})
    items.sort(key=lambda g: (g["derniere"] or "9999"), reverse=True)
    return items[:limite]
