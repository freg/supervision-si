#!/usr/bin/env python3
"""Plugin si-agent « poste-windows » (#896) : configuration à réinstaller et diagnostic d'un poste Windows, LECTURE SEULE.

1. Réinstallation : partages servis, lecteurs et raccourcis réseau par utilisateur, imprimantes, Office (Click-to-Run,
   identités Microsoft 365, profils Outlook, fichiers PST / OST à sauvegarder), Thunderbird (comptes, serveurs, agendas
   -- Google, CalDAV, locaux), licences Windows / Office (clé PARTIELLE seulement), antivirus, logiciels (machine et
   par utilisateur). Aucun mot de passe n'est lu.
2. Diagnostic : erreurs et avertissements des journaux Système / Application regroupés (30 jours), chronologie des
   évènements critiques (arrêts brutaux, écrans bleus, erreurs matérielles WHEA, erreurs disque / NTFS, pilote
   graphique, mémoire épuisée, diagnostic mémoire), plantages d'applications, vidages mémoire, disques (fiabilité :
   température, usure, erreurs), volumes, indice de stabilité, températures.
Relevé par collecte.ps1 (PowerShell 5.1, compte SYSTEM) ; analyse et constats ici (testés hors Windows).
Les lecteurs réseau, identités Office et logiciels « par utilisateur » ne sont lus que pour les profils chargés
(utilisateur connecté) : limite du compte SYSTEM, signalée dans le résultat.

Arguments : [--jours 30]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time

ICI = os.path.dirname(os.path.abspath(__file__))
SOURCES = {
    ("Microsoft-Windows-Kernel-Power", 41): ("arret_brutal", "arrêt ou redémarrage brutal (alimentation, plantage, bouton)"),
    ("EventLog", 6008): ("arret_brutal", "arrêt inattendu du système"),
    ("Microsoft-Windows-WER-SystemErrorReporting", 1001): ("ecran_bleu", "écran bleu (BugCheck)"),
    ("BugCheck", 1001): ("ecran_bleu", "écran bleu (BugCheck)"),
    ("disk", 7): ("disque", "secteur défectueux"), ("disk", 11): ("disque", "erreur de contrôleur disque"),
    ("disk", 51): ("disque", "erreur de pagination disque"), ("disk", 153): ("disque", "nouvelle tentative d'entrée-sortie disque"),
    ("storahci", 129): ("disque", "réinitialisation du contrôleur SATA"), ("stornvme", 129): ("disque", "réinitialisation du contrôleur NVMe"),
    ("stornvme", 11): ("disque", "erreur de contrôleur NVMe"),
    ("Ntfs", 55): ("fichiers", "structure du système de fichiers endommagée"), ("Ntfs", 98): ("fichiers", "volume à vérifier (chkdsk)"),
    ("Ntfs", 140): ("fichiers", "échec d'écriture NTFS"), ("volmgr", 161): ("ecran_bleu", "vidage mémoire impossible"),
    ("volmgr", 162): ("ecran_bleu", "vidage mémoire écrit"),
    ("Display", 4101): ("graphique", "le pilote graphique a cessé de répondre et a été relancé"),
    ("Microsoft-Windows-Resource-Exhaustion-Detector", 2004): ("memoire", "mémoire virtuelle épuisée"),
    ("Microsoft-Windows-MemoryDiagnostics-Results", 1101): ("diag_memoire", "diagnostic mémoire Windows : résultat"),
    ("Microsoft-Windows-MemoryDiagnostics-Results", 1201): ("diag_memoire", "diagnostic mémoire Windows : résultat"),
    ("Microsoft-Windows-MemoryDiagnostics-Results", 1102): ("diag_memoire_erreur", "diagnostic mémoire Windows : ERREURS MATÉRIELLES"),
    ("Microsoft-Windows-MemoryDiagnostics-Results", 1202): ("diag_memoire_erreur", "diagnostic mémoire Windows : ERREURS MATÉRIELLES"),
}
PREF = re.compile(r'^user_pref\("([^"]+)",\s*(.*)\);\s*$')
ETAT_LICENCE = {0: "sans licence", 1: "activée", 2: "période de grâce (OOB)", 3: "période de grâce (OOT)", 4: "non authentique", 5: "notification", 6: "grâce étendue"}


def _val(v):
    v = v.strip()
    if v.startswith('"') and v.endswith('"'):
        return v[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    if v in ("true", "false"):
        return v == "true"
    try:
        return int(v)
    except ValueError:
        return v


def thunderbird(profils):
    """Lignes prefs.js -> comptes (serveur, type, utilisateur), identités (adresse), serveurs d'envoi, agendas."""
    out = []
    for p in profils or []:
        prefs = {}
        for l in p.get("prefs") or []:
            m = PREF.match(l.strip())
            if m:
                prefs[m.group(1)] = _val(m.group(2))
        serveurs, idents, smtp, agendas = {}, {}, {}, {}
        for k, v in prefs.items():
            parts = k.split(".")
            if k.startswith("mail.server.") and len(parts) >= 4:
                serveurs.setdefault(parts[2], {})[".".join(parts[3:])] = v
            elif k.startswith("mail.identity.") and len(parts) >= 4:
                idents.setdefault(parts[2], {})[".".join(parts[3:])] = v
            elif k.startswith("mail.smtpserver.") and len(parts) >= 4:
                smtp.setdefault(parts[2], {})[".".join(parts[3:])] = v
            elif k.startswith("calendar.registry.") and len(parts) >= 4:
                agendas.setdefault(parts[2], {})[".".join(parts[3:])] = v
        comptes = [{"type": s.get("type"), "serveur": s.get("hostname"), "port": s.get("port"), "utilisateur": s.get("userName"), "nom": s.get("name"),
                    "securite": {0: "aucune", 2: "STARTTLS", 3: "SSL/TLS"}.get(s.get("socketType"), s.get("socketType"))}
                   for s in serveurs.values() if s.get("type") not in (None, "none") and s.get("hostname") not in (None, "Local Folders")]
        envoi = [{"serveur": s.get("hostname"), "port": s.get("port"), "utilisateur": s.get("username"), "description": s.get("description")} for s in smtp.values() if s.get("hostname")]
        ag = []
        for a in agendas.values():
            uri = str(a.get("uri") or "")
            if not uri and not a.get("name"):
                continue
            nature = "Google" if "google" in uri else "CalDAV" if a.get("type") == "caldav" else "local" if a.get("type") == "storage" or uri.startswith("moz-storage") else a.get("type")
            ag.append({"nom": a.get("name"), "type": a.get("type"), "nature": nature, "uri": uri[:200] if uri and not uri.startswith("moz-storage") else "",
                       "desactive": bool(a.get("disabled"))})
        out.append({"utilisateur": p.get("utilisateur"), "profil": p.get("profil"), "comptes": comptes, "envoi": envoi,
                    "identites": sorted({i.get("useremail") for i in idents.values() if i.get("useremail")}), "agendas": ag})
    return out


def antivirus_etat(code):
    """productState du Centre de sécurité -> (actif, à jour). Octet du milieu : 0x10 actif ; octet bas : 0x00 à jour."""
    try:
        c = int(code)
    except (TypeError, ValueError):
        return None, None
    return bool((c >> 8) & 0x10), (c & 0xFF) == 0


def analyse(raw, maintenant=None):
    maintenant = maintenant or time.time()
    al = []

    def alerte(code, gravite, message):
        al.append({"code": code, "severity": gravite, "message": message})
    # --- réinstallation
    tb = thunderbird(raw.get("thunderbird"))
    licences = [dict(l, etat_lib=ETAT_LICENCE.get(l.get("etat"), l.get("etat"))) for l in raw.get("licences") or []]
    av = []
    for a in raw.get("antivirus") or []:
        actif, a_jour = antivirus_etat(a.get("etat"))
        av.append(dict(a, actif=actif, a_jour=a_jour))
        if actif is False:
            alerte("poste-antivirus-inactif@%s" % a.get("nom"), "warning", "antivirus %s désactivé" % a.get("nom"))
        elif a_jour is False:
            alerte("poste-antivirus-ancien@%s" % a.get("nom"), "warning", "antivirus %s pas à jour" % a.get("nom"))
    for l in licences:
        if "Windows" in str(l.get("nom")) and l.get("etat") != 1:
            alerte("poste-windows-licence", "warning", "licence Windows : %s" % l["etat_lib"])
    logiciels = sorted(raw.get("logiciels") or [], key=lambda x: str(x.get("nom")).lower())
    vus, uniques = set(), []
    for l in logiciels:
        k = (str(l.get("nom")).lower(), l.get("version"), l.get("portee"))
        if k not in vus:
            vus.add(k)
            uniques.append(l)
    # --- diagnostic
    categories = {}
    for e in raw.get("critiques") or []:
        cat, lib = SOURCES.get((e.get("source"), e.get("id")), ("materiel" if "WHEA" in str(e.get("source")) else "autre",
                                                                   "erreur matérielle signalée par le processeur / la mémoire / le bus (WHEA)" if "WHEA" in str(e.get("source")) else e.get("source")))
        e["categorie"], e["libelle"] = cat, lib
        categories.setdefault(cat, []).append(e)
    n = {k: len(v) for k, v in categories.items()}
    if n.get("ecran_bleu") or raw.get("vidages"):
        alerte("poste-ecran-bleu", "critical", "%d écran(s) bleu(s) sur %d jours (%d vidage(s) mémoire)" % (n.get("ecran_bleu", 0), raw.get("jours") or 30, len(raw.get("vidages") or [])))
    if n.get("materiel"):
        alerte("poste-materiel", "critical", "%d erreur(s) matérielle(s) WHEA (processeur, mémoire ou bus) : panne matérielle probable" % n["materiel"])
    if n.get("diag_memoire_erreur"):
        alerte("poste-memoire-defectueuse", "critical", "le diagnostic mémoire Windows a trouvé des erreurs : barrette(s) à remplacer")
    if n.get("disque"):
        alerte("poste-disque-erreurs", "critical", "%d erreur(s) de disque ou de contrôleur : disque, câble ou contrôleur suspects" % n["disque"])
    if n.get("fichiers"):
        alerte("poste-ntfs", "warning", "%d alerte(s) du système de fichiers : vérification du disque (chkdsk) à prévoir" % n["fichiers"])
    if n.get("arret_brutal", 0) >= 2:
        alerte("poste-arrets-brutaux", "warning", "%d arrêt(s) ou redémarrage(s) brutal(aux) sur la période (alimentation, plantage, bouton)" % n["arret_brutal"])
    if n.get("graphique", 0) >= 2:
        alerte("poste-pilote-graphique", "warning", "pilote graphique relancé %d fois (pilote ou carte graphique)" % n["graphique"])
    if n.get("memoire"):
        alerte("poste-memoire-epuisee", "warning", "mémoire virtuelle épuisée %d fois (application gourmande ou mémoire insuffisante)" % n["memoire"])
    pl = {}
    for p in raw.get("plantages") or []:
        k = (p.get("application") or "?").lower()
        x = pl.setdefault(k, {"application": p.get("application"), "plantages": 0, "blocages": 0, "modules": {}, "dernier": None})
        x["plantages" if p.get("type") == "plantage" else "blocages"] += 1
        if p.get("module"):
            x["modules"][p["module"]] = x["modules"].get(p["module"], 0) + 1
        x["dernier"] = max(x["dernier"] or "", p.get("t") or "")
    plantages = sorted(pl.values(), key=lambda x: -(x["plantages"] + x["blocages"]))
    for x in plantages:
        x["modules"] = sorted(x["modules"], key=lambda m: -x["modules"][m])[:3]
    for x in plantages[:3]:
        if x["plantages"] + x["blocages"] >= 3:
            alerte("poste-plantages@%s" % x["application"], "warning", "%s : %d plantage(s), %d blocage(s)%s" % (
                x["application"], x["plantages"], x["blocages"], " (module : %s)" % x["modules"][0] if x["modules"] else ""))
    for d in raw.get("disques") or []:
        nom = d.get("modele") or "disque"
        if str(d.get("sante") or "Healthy") not in ("Healthy", "0", ""):
            alerte("poste-disque-sante@%s" % nom, "critical", "%s : santé %s" % (nom, d.get("sante")))
        if (d.get("usure") or 0) >= 80:
            alerte("poste-disque-usure@%s" % nom, "warning", "%s usé à %s %%" % (nom, d["usure"]))
        if (d.get("erreurs_lecture_non_corrigees") or 0) > 0:
            alerte("poste-disque-illisible@%s" % nom, "critical", "%s : %s erreur(s) de lecture non corrigée(s)" % (nom, d["erreurs_lecture_non_corrigees"]))
        if (d.get("temperature") or 0) >= 60:
            alerte("poste-disque-chaud@%s" % nom, "warning", "%s à %s °C" % (nom, d["temperature"]))
    for v in raw.get("volumes") or []:
        if v.get("octets") and v.get("libre") is not None and v["libre"] / float(v["octets"]) < 0.10:
            alerte("poste-volume-plein@%s" % v.get("lettre"), "warning", "volume %s : %.0f %% libre" % (v.get("lettre"), 100.0 * v["libre"] / v["octets"]))
    st = [s.get("indice") for s in raw.get("stabilite") or [] if isinstance(s.get("indice"), (int, float))]
    if st and st[0] < 5:
        alerte("poste-stabilite", "warning", "indice de stabilité Windows à %.1f / 10" % st[0])
    for t in raw.get("temperatures") or []:
        if (t.get("celsius") or 0) >= 90:
            alerte("poste-temperature@%s" % t.get("zone"), "warning", "zone thermique %s à %s °C" % (t.get("zone"), t["celsius"]))
    non_charges = [p["utilisateur"] for p in raw.get("profils") or [] if not p.get("charge")]
    return {
        "poste": {k: raw.get(k) for k in ("nom", "systeme", "version", "demarrage", "fabricant", "modele", "memoire_octets", "domaine", "jours")},
        "reinstallation": {"partages": raw.get("partages") or [], "lecteurs": raw.get("lecteurs") or [], "raccourcis_reseau": raw.get("raccourcis_reseau") or [],
                           "imprimantes": raw.get("imprimantes") or [], "office": raw.get("office"), "identites_office": raw.get("identites_office") or [],
                           "outlook": raw.get("outlook") or [], "fichiers_outlook": raw.get("fichiers_outlook") or [], "thunderbird": tb,
                           "licences": licences, "antivirus": av, "logiciels": uniques, "profils": raw.get("profils") or [],
                           "profils_non_lus": non_charges},
        "diagnostic": {"categories": n, "critiques": sorted(raw.get("critiques") or [], key=lambda e: e.get("t") or "", reverse=True)[:300],
                       "evenements": sorted(raw.get("evenements") or [], key=lambda g: (g.get("niveau", 9), -g.get("nombre", 0)))[:200],
                       "plantages": plantages[:50], "vidages": raw.get("vidages") or [], "memory_dmp": raw.get("memory_dmp"),
                       "disques": raw.get("disques") or [], "volumes": raw.get("volumes") or [], "stabilite": raw.get("stabilite") or [],
                       "temperatures": raw.get("temperatures") or []},
        "alerts": al,
    }


def _texte(b):
    """#920 : sortie de PowerShell -- UTF-8 (collecte.ps1 l'impose) ; mais le message d'erreur natif de powershell.exe
    (avant même le chargement du script) est en page OEM : « managé », « échoué » ne doivent plus devenir « ï¿½ »."""
    if not b:
        return ""
    try:
        return b.decode("utf-8").lstrip("\ufeff")
    except UnicodeDecodeError:
        for codec in ("oem", "cp850"):
            try:
                return b.decode(codec, "replace")
            except LookupError:
                continue
        return b.decode("latin-1")


def main(argv=None, runner=subprocess.run, plateforme=sys.platform):
    ap = argparse.ArgumentParser()
    ap.add_argument("--jours", type=int, default=30)
    a = ap.parse_args(argv)
    if plateforme != "win32":
        return {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "alerts": [{"code": "poste-windows-plateforme", "severity": "info", "message": "sonde réservée aux postes Windows"}]}
    ps = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    p = runner([ps if os.path.exists(ps) else "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                os.path.join(ICI, "collecte.ps1"), "-Jours", str(a.jours)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=540)
    sortie = _texte(p.stdout)
    debut = sortie.find("{")
    try:
        raw = json.loads(sortie[debut:]) if debut >= 0 else None
    except ValueError:
        raw = None
    if raw is None:
        err = _texte(p.stderr).strip()[:300] or sortie[:300]
        return {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "alerts": [{"code": "poste-windows-collecte", "severity": "warning", "message": "relevé PowerShell illisible : %s" % err}]}
    out = analyse(raw)
    out["at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return out


def executer(argv=None, runner=subprocess.run, plateforme=sys.platform):
    """#923 : la sonde ne plante plus -- un délai dépassé ou une erreur inattendue devient un constat lisible dans le
    Diagnostic (type, message, fichier et ligne), au lieu d'une trace Python tronquée dans le résultat de la commande."""
    at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    try:
        return main(argv, runner=runner, plateforme=plateforme)
    except subprocess.TimeoutExpired:
        return {"at": at, "alerts": [{"code": "poste-windows-delai", "severity": "warning",
                                      "message": "relevé PowerShell trop long (plus de 540 s) : relancer la sonde, ou réduire --jours"}]}
    except Exception as exc:  # noqa: BLE001
        import traceback
        tb = traceback.extract_tb(exc.__traceback__)
        lieu = ("%s, ligne %d" % (os.path.basename(tb[-1].filename), tb[-1].lineno)) if tb else "?"
        return {"at": at, "alerts": [{"code": "poste-windows-sonde", "severity": "warning",
                                      "message": "la sonde poste-windows a échoué : %s : %s (%s)" % (type(exc).__name__, str(exc)[:200], lieu)}]}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    print(json.dumps(executer(sys.argv[1:]), ensure_ascii=False))
