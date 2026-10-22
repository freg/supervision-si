# -*- coding: utf-8 -*-
"""Navigateurs des hôtes (livraison #798) : registre des hôtes d'agent qui portent un navigateur visible (écran web
noVNC publié par le bastion et servi par tls-proxy sous /navigateur/<nom>/, automate Playwright local piloté par la
commande « navigateur » de l'agent). Pur : valider."""
import re

NOM = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")


def valider(liste, agents_connus=None):
    """[{nom, agent_id, libelle?, accueil?, usage?}] -> (liste nettoyée, erreur|None). `nom` = celui de NAVIGATEURS (tls-proxy).
    usage « emulation » (#839) : la publication est la porte des écrans d'émulation de l'hôte (websockify à jetons, 6899)."""
    if not isinstance(liste, list):
        return None, "liste attendue"
    out, vus = [], set()
    for i, n in enumerate(liste, 1):
        if not isinstance(n, dict):
            return None, "entrée %d : objet attendu" % i
        nom = str(n.get("nom") or "").strip()
        aid = str(n.get("agent_id") or "").strip()
        if not NOM.match(nom):
            return None, "entrée %d : nom invalide (minuscules, chiffres, tirets, comme dans NAVIGATEURS)" % i
        if nom in vus:
            return None, "nom %s en double" % nom
        if not aid:
            return None, "entrée %d : agent_id requis" % i
        if agents_connus is not None and aid not in agents_connus:
            return None, "agent inconnu : %s" % aid
        acc = str(n.get("accueil") or "").strip()
        if acc and not re.match(r"^https?://", acc):
            return None, "entrée %d : page d'accueil http(s) attendue" % i
        usage = str(n.get("usage") or "navigateur")
        if usage not in ("navigateur", "emulation"):
            return None, "entrée %d : usage navigateur ou emulation" % i
        vus.add(nom)
        out.append({"nom": nom, "agent_id": aid, "libelle": str(n.get("libelle") or nom).strip()[:80], "accueil": acc[:300], "usage": usage})
    return out, None
