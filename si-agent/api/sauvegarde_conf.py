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


# #941 : inventaire compact des éléments de configuration par application -- où vivent les choses et ce qui s'exporte.
# Connaissance métier (chemins relatifs au dossier de config), sans aucune valeur : l'inventaire décrit, il ne lit pas.
# « export » = ce que l'utilisateur ou l'outil doit faire pour obtenir une forme réutilisable (mots de passe des
# navigateurs Chromium sont chiffrés DPAPI par compte Windows : la copie brute ne se réimporte pas ailleurs).
EXPORTS = {
    "Firefox": {"profil": r"%APPDATA%\Mozilla\Firefox\Profiles\<xxx>.default-release", "conf": ["prefs.js", "user.js", "handlers.json", "extensions.json"],
                "mots_de_passe": {"fichiers": ["logins.json", "key4.db"], "export": "about:logins › ⋯ › Exporter les identifiants (CSV en clair : à chiffrer / supprimer après import)", "portable": "copie logins.json + key4.db ensemble = réutilisable dans un autre profil"},
                "favoris": {"fichiers": ["places.sqlite", "bookmarkbackups/*.jsonlz4"], "export": "Bibliothèque › Importation et sauvegarde › Exporter les marque-pages au format HTML"},
                "historique": {"fichiers": ["places.sqlite", "formhistory.sqlite"], "export": "copie de places.sqlite (profil fermé)"},
                "sessions_onglets": {"fichiers": ["sessionstore-backups/recovery.jsonlz4"]}, "extensions": {"fichiers": ["extensions/", "extensions.json"]},
                "cache": {"dossier": r"%LOCALAPPDATA%\Mozilla\Firefox\Profiles\<xxx>\cache2", "sauvegarder": False}},
    "Thunderbird": {"profil": r"%APPDATA%\Thunderbird\Profiles\<xxx>.default-release", "conf": ["prefs.js", "profiles.ini (parent)", "handlers.json"],
                    "comptes": {"fichiers": ["prefs.js (mail.server.*, mail.identity.*)"], "export": "Outils › Exporter (profil complet .zip, Thunderbird ≥ 102)"},
                    "mots_de_passe": {"fichiers": ["logins.json", "key4.db"], "portable": "copie des deux fichiers ensemble"},
                    "courriers": {"fichiers": ["Mail/", "ImapMail/ (cache IMAP)"], "export": "comptes IMAP : rien à exporter ; POP / dossiers locaux : copier Mail/Local Folders"},
                    "carnet_adresses": {"fichiers": ["abook.sqlite", "history.sqlite"], "export": "Carnet d'adresses › Exporter (vCard / CSV)"},
                    "agendas": {"fichiers": ["calendar-data/local.sqlite"], "export": "Agenda › Exporter (ICS) ; CalDAV : rien, réabonner"},
                    "filtres": {"fichiers": ["<compte>/msgFilterRules.dat"]}, "cache": {"dossier": r"%LOCALAPPDATA%\Thunderbird", "sauvegarder": False}},
    "Chrome": {"profil": r"%LOCALAPPDATA%\Google\Chrome\User Data\Default", "conf": ["Preferences", "Secure Preferences"],
               "mots_de_passe": {"fichiers": ["Login Data"], "export": "chrome://password-manager/settings › Exporter (CSV)", "portable": "NON : chiffrés DPAPI (compte Windows) -- la copie brute ne sert qu'au même compte sur le même poste"},
               "favoris": {"fichiers": ["Bookmarks", "Bookmarks.bak"], "export": "chrome://bookmarks › ⋮ › Exporter (HTML)"},
               "historique": {"fichiers": ["History", "Top Sites"]}, "extensions": {"fichiers": ["Extensions/", "Preferences (extensions.settings)"], "export": "liste des identifiants d'extensions (réinstallation par le Web Store)"},
               "sessions_onglets": {"fichiers": ["Sessions/"]}, "cache": {"dossier": r"%LOCALAPPDATA%\Google\Chrome\User Data\Default\Cache", "sauvegarder": False},
               "synchro": "si le profil est connecté à un compte Google : favoris, mots de passe et extensions reviennent par la synchronisation"},
    "Edge": {"profil": r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default", "conf": ["Preferences", "Secure Preferences"],
             "mots_de_passe": {"fichiers": ["Login Data"], "export": "edge://wallet/passwords › Exporter (CSV)", "portable": "NON : chiffrés DPAPI (compte Windows)"},
             "favoris": {"fichiers": ["Bookmarks"], "export": "edge://favorites › ⋯ › Exporter (HTML)"}, "historique": {"fichiers": ["History"]},
             "extensions": {"fichiers": ["Extensions/"]}, "cache": {"dossier": r"%LOCALAPPDATA%\Microsoft\Edge\User Data\Default\Cache", "sauvegarder": False},
             "synchro": "compte Microsoft connecté : favoris, mots de passe, extensions reviennent par la synchronisation"},
    "Office": {"conf": [r"HKCU\Software\Microsoft\Office\16.0 (options, listes MRU)", r"%APPDATA%\Microsoft\Templates (Normal.dotm, modèles)", r"%APPDATA%\Microsoft\Signatures"],
               "outlook": {"fichiers": [r"%LOCALAPPDATA%\Microsoft\Outlook\*.ost (cache Exchange/365 : ne pas sauvegarder)", r"%USERPROFILE%\Documents\Fichiers Outlook\*.pst (À SAUVEGARDER)", r"%APPDATA%\Microsoft\Outlook\*.xml (barres, vues)", r"%APPDATA%\Microsoft\Outlook\*.srs"],
                           "export": "Fichier › Ouvrir et exporter › Importer/Exporter › Fichier de données Outlook (.pst)", "comptes": "profils dans HKCU\\Software\\Microsoft\\Office\\16.0\\Outlook\\Profiles (mots de passe : NON portables, à ressaisir)"},
               "licence": "activation liée au compte Microsoft 365 / à la clé : se reconnecter après réinstallation (clé partielle relevée par poste-windows)",
               "dictionnaires": {"fichiers": [r"%APPDATA%\Microsoft\UProof\CUSTOM.DIC"]}, "autocorrection": {"fichiers": [r"%APPDATA%\Microsoft\Office\*.acl"]}},
    "PuTTY": {"conf": [r"HKCU\Software\SimonTatham\PuTTY\Sessions (sessions : hôte, port, clé)", r"HKCU\Software\SimonTatham\PuTTY\SshHostKeys (empreintes connues)"],
              "export": "reg export HKCU\\Software\\SimonTatham putty.reg (fait par la sauvegarde de poste)", "cles": {"fichiers": ["*.ppk (où l'utilisateur les a mises -- souvent Documents ou .ssh)"], "portable": "les .ppk sont à copier à part ; mots de passe de session jamais stockés par PuTTY"}},
    "WinSCP": {"conf": [r"HKCU\Software\Martin Prikryl\WinSCP 2\Sessions", r"%APPDATA%\WinSCP.ini (si mode INI)"],
               "export": "Outils › Exporter/Sauvegarder la configuration (INI)", "mots_de_passe": {"portable": "mots de passe de sites chiffrés faiblement dans la conf : réutilisables, à traiter comme un secret"}},
    "OpenVPN": {"conf": [r"%USERPROFILE%\OpenVPN\config\*.ovpn", r"C:\Program Files\OpenVPN\config\*.ovpn (machine)"],
                "secrets": {"fichiers": ["*.key", "*.p12", "auth.txt (si identifiants enregistrés)"], "portable": "à copier avec le .ovpn ; les protéger"},
                "export": "copie du dossier config"},
}


def inventaire(cibles, resultat=None):
    """#941 : inventaire compact par application : clés, dossiers, exports connus, et ce que la dernière sauvegarde a trouvé
    (présence / taille par dossier et par clé) -- jamais une valeur. `cibles` = liste finale envoyée à l'agent ;
    `resultat` = data de la dernière mesure sauvegarde-poste (confs, dossiers, archive) ou None."""
    r = resultat or {}
    trouves_cles = {}
    for c in r.get("confs") or []:
        if isinstance(c, dict):
            trouves_cles.setdefault(str(c.get("app") or ""), []).append({"cle": c.get("cle"), "fichier": c.get("fichier"), "octets": c.get("octets")})
    trouves_dossiers = {}
    for d in r.get("dossiers") or []:
        if isinstance(d, dict):
            trouves_dossiers.setdefault(str(d.get("app") or ""), []).append({"source": d.get("source"), "octets": d.get("octets"), "absent": bool(d.get("absent"))})
    out = {}
    for c in cibles or []:
        app = c.get("app")
        e = {"cles": list(c.get("cles") or []), "dossiers": list(c.get("dossiers") or [])}
        if app in EXPORTS:
            e["elements"] = EXPORTS[app]
        if app in trouves_cles or app in trouves_dossiers:
            e["releve"] = {"cles": trouves_cles.get(app, []), "dossiers": trouves_dossiers.get(app, [])}
            e["releve"]["octets"] = sum(int(x.get("octets") or 0) for x in e["releve"]["dossiers"]) + sum(int(x.get("octets") or 0) for x in e["releve"]["cles"])
            e["releve"]["absents"] = [x["source"] for x in e["releve"]["dossiers"] if x.get("absent")]
        out[app] = e
    meta = {"archive": (r.get("archive") or {}).get("nom"), "octets": (r.get("archive") or {}).get("octets"), "at": r.get("at"),
            "applications": len(out), "avec_releve": sum(1 for e in out.values() if "releve" in e),
            "note": "inventaire des emplacements et exports, sans aucune valeur (mots de passe, clés) ; « portable : NON » = à ressaisir après réinstallation"}
    return {"meta": meta, "applications": out}
