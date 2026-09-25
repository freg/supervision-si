# -*- coding: utf-8 -*-
"""Utilisateurs de démonstration (livraison #608) -- demandé : « pour les
besoins de démo il faudrait des utilisateurs démo, préparer leur
configuration activable / désactivable sur le hub ; ils doivent pouvoir se
connecter par le processus normal ».

Des comptes Keycloak LOCAUX (hors LDAP : avec la fédération en lecture
seule, Keycloak crée le compte chez lui), rattachés aux groupes du hub, avec
un mot de passe généré à l'activation et affiché une seule fois. « Activer »
crée ou réactive les comptes ; « désactiver » les passe `enabled = false`
(connexion refusée, comptes conservés) ; « supprimer » les efface.
Profils : ACCOUNTS_DEMO_PROFILES (JSON) ou les trois par défaut."""
import json
import secrets
import string

DEFAULT_PROFILES = [
    {"username": "demo-admin", "first_name": "Démo", "last_name": "Administrateur", "groups": ["administrateurs"], "description": "tout le hub, tour de contrôle, comptes, coffres"},
    {"username": "demo-technicien", "first_name": "Démo", "last_name": "Technicien", "groups": ["techniciens"], "description": "supervision, réseau, agents, tickets"},
    {"username": "demo-lecture", "first_name": "Démo", "last_name": "Lecture", "groups": ["lecteurs"], "description": "consultation seule"},
]
DEMO_MAIL_DOMAIN = "demo.invalid"  # jamais un vrai domaine : aucun courriel ne part


def profiles(raw=None):
    """Profils depuis la variable d'environnement (JSON) ou par défaut ; validés."""
    out = []
    try:
        items = json.loads(raw) if raw else DEFAULT_PROFILES
    except ValueError:
        items = DEFAULT_PROFILES
    for p in items if isinstance(items, list) else DEFAULT_PROFILES:
        u = str(p.get("username") or "").strip().lower()
        if not u.startswith("demo-") or len(u) > 40:
            continue  # un compte de démo porte toujours le préfixe demo- (repérable, supprimable en bloc)
        out.append({"username": u, "first_name": str(p.get("first_name") or "Démo"), "last_name": str(p.get("last_name") or u[5:].capitalize()),
                    "groups": [str(g) for g in (p.get("groups") or []) if str(g).strip()], "description": str(p.get("description") or "")})
    return out or [dict(x) for x in DEFAULT_PROFILES]


def generate_password(n=14):
    """Lisible à l'oral pour une démo : lettres + chiffres, sans ambiguïtés (0/O, 1/l), un tiret au milieu."""
    alphabet = "".join(c for c in string.ascii_letters + string.digits if c not in "0O1lI")
    half = n // 2
    return "".join(secrets.choice(alphabet) for _ in range(half)) + "-" + "".join(secrets.choice(alphabet) for _ in range(n - half))


def state(profiles_list, users):
    """Croise les profils avec les comptes Keycloak existants -> [{...profil, exists, enabled, id, groups_current}]."""
    by = {u.get("username"): u for u in users or []}
    out = []
    for p in profiles_list:
        u = by.get(p["username"])
        out.append(dict(p, exists=bool(u), enabled=bool(u and u.get("enabled")), id=(u or {}).get("id"), groups_current=(u or {}).get("groups") or []))
    return out


def summary(states):
    n = len(states)
    on = sum(1 for s in states if s["exists"] and s["enabled"])
    return {"profiles": n, "active": on, "existing": sum(1 for s in states if s["exists"]), "mode": "on" if on == n and n else "partial" if on else "off"}
