# -*- coding: utf-8 -*-
"""#930 : sélection des configurations logicielles à sauvegarder depuis un poste (clés de registre + dossiers de
config). Catalogue par défaut, déduction des logiciels relevés par poste-windows, et liste éditée (réglage du hub
`postes-sauvegarde`). Le hub fusionne ces sources et envoie la liste FINALE à l'agent. Module pur, testé par
test_z_sauvegarde.py. Aucun secret ici (les identifiants du partage viennent du coffre au lancement).
"""
# Catalogue par défaut : applications dont la configuration vaut d'être sauvegardée. Chemins avec variables
# d'environnement Windows (développées sur le poste). Clés de registre + dossiers (%APPDATA%, %LOCALAPPDATA%).
CATALOGUE_DEFAUT = [
    {"app": "Thunderbird", "cles": [], "dossiers": [r"%APPDATA%\Thunderbird"]},
    {"app": "Firefox", "cles": [r"HKCU\Software\Mozilla"], "dossiers": [r"%APPDATA%\Mozilla\Firefox"]},
    {"app": "Chrome", "cles": [r"HKCU\Software\Google\Chrome"], "dossiers": [r"%LOCALAPPDATA%\Google\Chrome\User Data\Default"]},
    {"app": "Edge", "cles": [r"HKCU\Software\Microsoft\Edge"], "dossiers": [r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default"]},
    {"app": "Office", "cles": [r"HKCU\Software\Microsoft\Office"], "dossiers": [r"%APPDATA%\Microsoft\Templates", r"%APPDATA%\Microsoft\Signatures"]},
    {"app": "PuTTY", "cles": [r"HKCU\Software\SimonTatham"], "dossiers": []},
    {"app": "WinSCP", "cles": [r"HKCU\Software\Martin Prikryl\WinSCP 2"], "dossiers": []},
    {"app": "OpenVPN", "cles": [], "dossiers": [r"%USERPROFILE%\OpenVPN\config"]},
]


def _nettoyer(cible):
    if not isinstance(cible, dict):
        return None
    app = str(cible.get("app") or "").strip()
    if not app:
        return None
    cles = list(dict.fromkeys(str(c).strip() for c in (cible.get("cles") or []) if str(c).strip()))
    dossiers = list(dict.fromkeys(str(d).strip() for d in (cible.get("dossiers") or []) if str(d).strip()))
    return {"app": app, "cles": cles, "dossiers": dossiers}


def deduire_des_logiciels(logiciels):
    """Depuis les logiciels relevés (poste-windows), propose des cibles probables (clé HKCU/HKLM de l'éditeur,
    dossier %APPDATA%\\<éditeur>). Simple proposition à cocher côté hub."""
    out, vus = [], set()
    for l in logiciels or []:
        editeur = str((l or {}).get("editeur") or "").strip()
        nom = str((l or {}).get("nom") or "").strip()
        cle = editeur or nom
        if not cle or cle.lower() in vus:
            continue
        vus.add(cle.lower())
        out.append({"app": nom or editeur, "cles": [r"HKCU\Software\%s" % cle, r"HKLM\SOFTWARE\%s" % cle],
                    "dossiers": [r"%%APPDATA%%\%s" % cle], "propose": True})
    return out


def valider(liste):
    """Valide la liste éditée du réglage -> (liste_propre, erreur|None)."""
    if liste is None:
        return [], None
    if not isinstance(liste, list):
        return None, "liste de confs attendue"
    out = []
    for i, c in enumerate(liste):
        n = _nettoyer(c)
        if n is None:
            return None, "conf #%d : « app » requis" % (i + 1)
        if not n["cles"] and not n["dossiers"]:
            return None, "conf « %s » : au moins une clé de registre ou un dossier" % n["app"]
        out.append(n)
    return out, None


def cibles(liste_editee=None, logiciels=None, inclure_catalogue=True, inclure_deduit=False):
    """Fusionne catalogue + déduction + liste éditée (qui l'emporte, par application). -> [{app, cles, dossiers}]."""
    par_app, sources = {}, []
    if inclure_catalogue:
        sources += CATALOGUE_DEFAUT
    if inclure_deduit:
        sources += deduire_des_logiciels(logiciels)
    sources += (liste_editee or [])
    for c in sources:
        n = _nettoyer(c)
        if n:
            par_app[n["app"]] = n
    return [par_app[k] for k in sorted(par_app)]


def montages_du_releve(poste_windows_data):
    """Extrait du relevé poste-windows les montages à reconstruire : partages servis, lecteurs réseau, imprimantes."""
    d = poste_windows_data or {}
    return {"partages": d.get("partages") or [], "lecteurs": d.get("lecteurs") or [], "imprimantes": d.get("imprimantes") or []}
