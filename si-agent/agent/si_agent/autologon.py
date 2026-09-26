# -*- coding: utf-8 -*-
"""Réouverture de session UNE FOIS après un redémarrage commandé (livraison
#628) -- `power_action` {action: reboot, autologon: {user, password, domain?}}.

Mécanisme Windows natif : dans Winlogon, `AutoAdminLogon=1` + `AutoLogonCount=1`
(+ DefaultUserName / DefaultDomainName / DefaultPassword). Winlogon ouvre la
session au démarrage suivant, décrémente le compteur et, à zéro, EFFACE
lui-même AutoAdminLogon et DefaultPassword : rien de permanent. L'agent
repasse derrière au démarrage suivant (`cleanup`) au cas où Winlogon n'aurait
pas nettoyé (session jamais ouverte, coupure) : mot de passe retiré, autologon
désactivé. Boucle « redémarrer et revenir dans l'état initial » d'un poste
kiosque, sans autologon permanent.

Le mot de passe ne fait que passer : jamais journalisé, jamais dans un
événement, jamais dans l'acquittement ; le central le masque dès l'envoi
(voir store.py / local_central.py). Il est écrit dans le registre en clair
le temps d'UN démarrage, puis effacé -- c'est le fonctionnement de Winlogon,
identique à Sysprep / MDT. Comptes locaux ou de domaine avec mot de passe ;
un compte Microsoft avec PIN seul ne convient pas.

Pure ici : validation, valeurs à écrire, décision de nettoyage. Le registre
est touché par l'agent (winreg), jamais par une ligne de commande (le mot de
passe n'apparaît dans aucune liste de processus).
"""
import re

WINLOGON_KEY = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon"
MAX_COUNT = 5


def validate(params):
    """{user, password, domain?, count?} -> (plan, erreur)."""
    p = params or {}
    user = str(p.get("user") or "").strip()
    password = p.get("password")
    domain = str(p.get("domain") or ".").strip() or "."
    if not user or len(user) > 104 or re.search(r"[\x00-\x1f\"/\\\[\]:;|=,+*?<>]", user):
        return None, "autologon.user : nom de compte requis (sans caractères spéciaux)"
    if not isinstance(password, str) or not password or "\x00" in password or len(password) > 127:
        return None, "autologon.password : mot de passe requis (un compte sans mot de passe ne peut pas rouvrir sa session)"
    if re.search(r"[\x00-\x1f\"/\\\[\]:;|=,+*?<>]", domain):
        return None, "autologon.domain : nom de domaine invalide ('.' = ce poste)"
    try:
        count = max(1, min(MAX_COUNT, int(p.get("count", 1))))
    except (TypeError, ValueError):
        return None, "autologon.count : entier"
    return {"user": user, "password": password, "domain": domain, "count": count}, None


def values(plan):
    """Valeurs Winlogon à écrire : [(nom, type, valeur)] ; type 'sz' ou 'dword'."""
    return [("AutoAdminLogon", "sz", "1"), ("DefaultUserName", "sz", plan["user"]), ("DefaultDomainName", "sz", plan["domain"]),
            ("DefaultPassword", "sz", plan["password"]), ("AutoLogonCount", "dword", plan["count"]), ("ForceAutoLogon", "dword", 0)]


def apply(plan, set_value):
    """set_value(name, kind, value) -- lève en cas d'échec. Retourne un résumé SANS mot de passe."""
    for name, kind, value in values(plan):
        set_value(name, kind, value)
    return {"user": plan["user"], "domain": plan["domain"], "count": plan["count"]}


def cleanup(get_value, delete_value, set_value):
    """Après le redémarrage : si le compteur est consommé (absent ou 0) mais que des
    traces subsistent, les retirer. get_value(name) -> valeur ou None.
    -> {cleaned: bool, remaining: int|None}"""
    count = get_value("AutoLogonCount")
    try:
        remaining = int(count) if count is not None else 0
    except (TypeError, ValueError):
        remaining = 0
    if remaining > 0:
        return {"cleaned": False, "remaining": remaining}
    done = False
    if get_value("DefaultPassword") is not None:
        delete_value("DefaultPassword"); done = True
    if str(get_value("AutoAdminLogon") or "0") != "0":
        set_value("AutoAdminLogon", "sz", "0"); done = True
    if count is not None:
        delete_value("AutoLogonCount"); done = True
    return {"cleaned": done, "remaining": 0}


def redact(params):
    """Copie des paramètres d'une commande, mot de passe masqué (stockage / affichage)."""
    p = dict(params or {})
    if isinstance(p.get("autologon"), dict) and "password" in p["autologon"]:
        a = dict(p["autologon"]); a["password"] = "***"; p["autologon"] = a
    return p
