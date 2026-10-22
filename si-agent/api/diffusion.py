# -*- coding: utf-8 -*-
"""Diffusions en cascade (livraison #822) : déploiement automatique avec la notion de dépendance.

Une règle de diffusion = une cible (agents qui portent telle sonde, tel OS, telle liste) et des étapes ordonnées par
leurs dépendances (« apres »). Pour chaque agent ciblé, une étape ne démarre que lorsque toutes celles dont elle dépend
sont faites ; le central fait le geste (commande de mise à jour forcée, affectation ou retrait d'une sonde) puis
constate le résultat aux passages suivants. Exemple fourni : « forcer la mise à jour, puis activer pve-preflight sur
les agents qui portent guest-usage ou pve-remote ».

Types d'étape :
  mise_a_jour        agent à la version servie (ou ≥ version_min) ; geste : commande `update`, hors canal bêta / général
  activer_sonde      sonde affectée et active ; geste : affectation (enabled)
  desactiver_sonde   sonde absente ou inactive ; geste : désactivation
  attendre_releve    un relevé réussi de la sonde est arrivé (aucun geste : on attend)
États par agent et étape : fait, a_faire (geste à faire maintenant), en_cours, attente (dépendance non faite), echec.
Pur et testé : valider, ordre, cibles, etat_etape, planifier."""
import re

import updates

TYPES = {"mise_a_jour": "mettre à jour l'agent", "activer_sonde": "activer une sonde", "desactiver_sonde": "désactiver une sonde",
         "attendre_releve": "attendre un relevé de la sonde"}
_ID = re.compile(r"^[a-z0-9_-]{1,40}$")


def ordre(etapes):
    """Ordre topologique des étapes (dépendances d'abord) ; ValueError si dépendance inconnue ou cycle."""
    ids = [e["id"] for e in etapes]
    par = {e["id"]: e for e in etapes}
    for e in etapes:
        for d in e.get("apres") or []:
            if d not in par:
                raise ValueError("étape %s : dépendance inconnue %s" % (e["id"], d))
    vus, encours, out = set(), set(), []

    def visiter(i):
        if i in vus:
            return
        if i in encours:
            raise ValueError("cycle de dépendances autour de %s" % i)
        encours.add(i)
        for d in par[i].get("apres") or []:
            visiter(d)
        encours.discard(i)
        vus.add(i)
        out.append(par[i])
    for i in ids:
        visiter(i)
    return out


def valider(b, plugins_connus=()):
    """-> (règle normalisée, None) ou (None, erreur)."""
    b = b or {}
    nom = str(b.get("nom") or "").strip()[:120]
    if not nom:
        return None, "nom requis"
    c = b.get("cible") or {}
    cible = {k: sorted({str(x) for x in (c.get(k) or []) if str(x).strip()}) for k in ("plugins_any", "plugins_all", "os", "agents", "exclure")}
    if not any(cible[k] for k in ("plugins_any", "plugins_all", "os", "agents")):
        return None, "cible vide : au moins une sonde, un OS ou un agent"
    etapes = []
    for e in b.get("etapes") or []:
        e = dict(e or {})
        eid, t = str(e.get("id") or "").strip(), e.get("type")
        if not _ID.match(eid):
            return None, "identifiant d'étape invalide (a-z, 0-9, _ -) : %r" % eid
        if t not in TYPES:
            return None, "étape %s : type inconnu (%s)" % (eid, ", ".join(TYPES))
        x = {"id": eid, "type": t, "apres": [str(d) for d in e.get("apres") or []]}
        if t in ("activer_sonde", "desactiver_sonde", "attendre_releve"):
            x["sonde"] = str(e.get("sonde") or "")
            if not x["sonde"] or (plugins_connus and x["sonde"] not in plugins_connus):
                return None, "étape %s : sonde inconnue %r" % (eid, x["sonde"])
        if t == "mise_a_jour" and e.get("version_min"):
            x["version_min"] = str(e["version_min"])
        etapes.append(x)
    if not etapes:
        return None, "au moins une étape"
    if len({e["id"] for e in etapes}) != len(etapes):
        return None, "identifiants d'étape en double"
    try:
        etapes = ordre(etapes)
    except ValueError as exc:
        return None, str(exc)
    return {"nom": nom, "actif": bool(b.get("actif", True)), "auto": bool(b.get("auto", False)), "cible": cible, "etapes": etapes}, None


def cibles(regle, agents):
    """agents : [{agent_id, os, plugin_ids}] -> ceux que vise la règle."""
    c = regle.get("cible") or {}
    out = []
    for a in agents:
        aid, pl = a.get("agent_id"), set(a.get("plugin_ids") or [])
        if aid in (c.get("exclure") or []):
            continue
        if c.get("agents") and aid not in c["agents"]:
            continue
        if c.get("os") and (a.get("os") or "") not in c["os"]:
            continue
        if c.get("plugins_any") and not pl & set(c["plugins_any"]):
            continue
        if c.get("plugins_all") and not set(c["plugins_all"]) <= pl:
            continue
        out.append(a)
    return out


def etat_etape(e, agent, sondes, releves, pkg_version, derniere_maj, now=None):
    """État d'une étape pour un agent, dépendances mises à part. sondes : {id: {enabled}} ; releves : {tâche: {ok}}."""
    t = e["type"]
    if t == "mise_a_jour":
        cible = e.get("version_min") or pkg_version
        if not cible:
            return "echec", "aucun paquet d'agent servi par le central"
        v = agent.get("agent_version")
        if v and updates.version_tuple(v) >= updates.version_tuple(cible):
            return "fait", "agent en %s" % v
        st = updates.agent_status(agent, pkg_version, {"general_enabled": True, "beta_agents": []}, derniere_maj, now)
        if st in ("pending", "started"):
            return "en_cours", "mise à jour %s" % ("envoyée" if st == "pending" else "lancée sur l'hôte")
        if st in ("stalled", "failed"):
            return "echec", "mise à jour %s (nouvel essai au délai de relance)" % ("bloquée" if st == "stalled" else "en échec")
        if st == "unknown":
            return "attente", "version de l'agent inconnue (jamais vu ?)"
        return "a_faire", "mise à jour %s -> %s" % (v or "?", pkg_version)
    s = sondes.get(e.get("sonde")) or {}
    if t == "activer_sonde":
        return ("fait", "active") if s.get("enabled") else ("a_faire", "à activer")
    if t == "desactiver_sonde":
        return ("fait", "inactive") if not s.get("enabled") else ("a_faire", "à désactiver")
    if t == "attendre_releve":
        r = releves.get("plugin:%s" % e.get("sonde")) or {}
        if r and r.get("ok"):
            return "fait", "relevé reçu %s" % (r.get("at") or "")
        return ("echec", "dernier relevé en erreur : %s" % (r.get("error") or "")[:120]) if r else ("en_cours", "pas encore de relevé")
    return "echec", "type inconnu"


def planifier(regle, agents, contexte, pkg_version, now=None):
    """-> {agents: [{agent_id, etapes: [{id, type, etat, detail}], termine}], gestes: [(agent_id, étape)]}.
    contexte(agent_id) -> (sondes, releves, derniere_maj)."""
    lignes, gestes = [], []
    for a in cibles(regle, agents):
        sondes, releves, der = contexte(a["agent_id"])
        etats = {}
        lst = []
        for e in regle["etapes"]:
            bloque = [d for d in e.get("apres") or [] if etats.get(d) != "fait"]
            if bloque:
                st, det = "attente", "après %s" % ", ".join(bloque)
            else:
                st, det = etat_etape(e, a, sondes, releves, pkg_version, der, now)
                if st == "a_faire":
                    gestes.append((a["agent_id"], e))
            etats[e["id"]] = st
            lst.append({"id": e["id"], "type": e["type"], "sonde": e.get("sonde"), "etat": st, "detail": det})
        lignes.append({"agent_id": a["agent_id"], "version": a.get("agent_version"), "etapes": lst, "termine": all(x["etat"] == "fait" for x in lst)})
    return {"agents": lignes, "gestes": gestes}


EXEMPLE = {"nom": "Préparation des nœuds PVE : mise à jour puis pve-preflight", "actif": True, "auto": False,
           "cible": {"plugins_any": ["guest-usage", "pve-remote"]},
           "etapes": [{"id": "maj", "type": "mise_a_jour"},
                      {"id": "preflight", "type": "activer_sonde", "sonde": "pve-preflight", "apres": ["maj"]},
                      {"id": "releve", "type": "attendre_releve", "sonde": "pve-preflight", "apres": ["preflight"]}]}
