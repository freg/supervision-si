# -*- coding: utf-8 -*-
"""#928 : liste des sites de service de l'entreprise à tester depuis un poste (GED, cloud, annuaire, tickets…) --
réglage du hub `services-poste`. La liste ne contient JAMAIS de secret : seulement le NOM d'un accès du coffre
(credentials-api). Au moment de lancer un test, le hub révèle l'accès et compose les cibles envoyées à l'agent ;
le secret ne vit qu'en mémoire côté hub puis dans la commande caviardée (store.redact_params). Module pur, testé
par test_z_services_poste.py.
"""
TYPES = ("aucun", "form", "basic", "token")


def valider(liste):
    """-> (liste_propre, erreur|None). N'accepte aucun champ secret dans la configuration."""
    if not isinstance(liste, list):
        return None, "services-poste : liste attendue"
    out, noms = [], set()
    for i, s in enumerate(liste):
        if not isinstance(s, dict):
            return None, "service #%d : objet attendu" % (i + 1)
        nom = str(s.get("nom") or "").strip()
        url = str(s.get("url") or "").strip()
        if not nom:
            return None, "service #%d : nom requis" % (i + 1)
        if nom in noms:
            return None, "nom en double : %s" % nom
        noms.add(nom)
        if not url.startswith(("http://", "https://")):
            return None, "service « %s » : url http(s) requise" % nom
        a = s.get("auth") if isinstance(s.get("auth"), dict) else {}
        typ = str(a.get("type") or "aucun")
        if typ not in TYPES:
            return None, "service « %s » : type d'authentification « %s » inconnu (%s)" % (nom, typ, ", ".join(TYPES))
        for interdit in ("secret", "password", "valeur", "user", "username"):
            if a.get(interdit):
                return None, "service « %s » : « %s » interdit dans la configuration (le secret vient du coffre)" % (nom, interdit)
        auth = {"type": typ}
        if typ != "aucun":
            acces = str(a.get("acces") or "").strip()
            if not acces:
                return None, "service « %s » : « acces » (nom au coffre) requis pour l'authentification" % nom
            auth["acces"] = acces
        if typ == "form":
            if not a.get("champ_user") or not a.get("champ_pass"):
                return None, "service « %s » : champ_user et champ_pass requis (noms des champs du formulaire)" % nom
            auth["champ_user"] = str(a["champ_user"])
            auth["champ_pass"] = str(a["champ_pass"])
            for k in ("url_login", "marqueur_connecte", "marqueur_echec"):
                if a.get(k):
                    auth[k] = str(a[k])
            if isinstance(a.get("champs"), dict):
                auth["champs"] = {str(k): str(v) for k, v in a["champs"].items()}
        if typ == "token":
            auth["entete"] = str(a.get("entete") or "Authorization")
            auth["prefixe"] = str(a.get("prefixe") if a.get("prefixe") is not None else "Bearer ")
        out.append({"nom": nom, "url": url, "auth": auth})
    return out, None


def cibles_pour_mesure(liste, reveler):
    """Compose les cibles envoyées à l'agent, secrets injectés depuis le coffre.
    `reveler(nom)` -> {"username", "password"} (lève RuntimeError si indisponible).
    -> (cibles, erreurs) ; une cible dont l'accès au coffre échoue est signalée dans `erreurs` et testée en brut seul."""
    cibles, erreurs = [], []
    for s in liste or []:
        a = dict(s.get("auth") or {"type": "aucun"})
        typ = a.get("type") or "aucun"
        cible = {"nom": s["nom"], "url": s["url"]}
        if typ == "aucun":
            cibles.append(cible)
            continue
        try:
            acces = reveler(a["acces"])
        except RuntimeError as e:
            erreurs.append({"nom": s["nom"], "acces": a.get("acces"), "erreur": str(e)})
            cibles.append(cible)                      # testé en accès brut seulement
            continue
        user = acces.get("username") or acces.get("user") or ""
        secret = acces.get("password") or acces.get("secret") or ""
        auth = {"type": typ}
        if typ == "basic":
            auth.update(user=user, secret=secret)
        elif typ == "token":
            auth["entete"] = a.get("entete") or "Authorization"
            auth["valeur"] = (a.get("prefixe") or "") + secret
        elif typ == "form":
            auth.update(champ_user=a["champ_user"], champ_pass=a["champ_pass"], user=user, secret=secret)
            for k in ("url_login", "marqueur_connecte", "marqueur_echec", "champs"):
                if a.get(k):
                    auth[k] = a[k]
        cibles.append(dict(cible, auth=auth))
    return cibles, erreurs
