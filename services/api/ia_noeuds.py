# -*- coding: utf-8 -*-
"""Nœuds IA (livraison #988) : Hermes, atelier de codage et apprentissage tournent sur prodia / preprodia (service
hermes-web du hub perso du nœud) et s'ouvrent dans le hub sous /ia/<nœud>/ au seul groupe Keycloak « ia ».

La passerelle (tls-proxy) demande à services-api, pour CHAQUE requête /ia/… (auth_request), si le jeton Keycloak de la
personne est valide et porte un groupe admis ; elle pose ensuite le jeton du nœud (X-Hermes-Jeton). Les iframes ne
peuvent pas envoyer d'en-tête Authorization : le hub recopie donc son jeton d'accès dans un cookie limité à /ia/
(si_ia_jeton), relu ici. Logique pure, testée dans test_ia_noeuds.py."""
import re

COOKIE = "si_ia_jeton"
NOM = re.compile(r"^[a-z0-9][a-z0-9-]{0,30}$")
GROUPES_DEFAUT = "ia,administrateurs,admin_hub"


def noeuds(raw):
    """IA_NOEUDS « prodia=http://hôte:8092,preprodia=… » -> ['prodia', 'preprodia'] (noms seuls, adresses jamais
    renvoyées au navigateur ; entrées invalides ignorées ici, refusées au rendu de la passerelle)."""
    out = []
    for item in (raw or "").split(","):
        nom = item.partition("=")[0].strip()
        if NOM.match(nom) and nom not in out:
            out.append(nom)
    return out


def groupes(raw):
    return [g.strip().strip("/") for g in (raw if raw is not None else GROUPES_DEFAUT).split(",") if g.strip()]


def jeton(entete_authorization, cookies):
    """Jeton d'accès : en-tête « Bearer … » (appels fetch) sinon cookie si_ia_jeton (iframes)."""
    v = (entete_authorization or "").strip()
    if v.lower().startswith("bearer ") and v[7:].strip():
        return v[7:].strip()
    c = (cookies or {}).get(COOKIE) or ""
    return c.strip() or None
