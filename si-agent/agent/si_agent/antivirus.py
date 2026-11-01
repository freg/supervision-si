# -*- coding: utf-8 -*-
"""Antivirus / protection des postes (livraison #520) -- Windows ET macOS,
même forme de sortie, évaluée par risks.evaluate_antivirus.

Demandé (demande SAV) : « un contrôle / alerte sur les antivirus des
Windows et des Mac ». Windows : le Centre de sécurité (WMI
root/SecurityCenter2, AntiVirusProduct) enregistre TOUT antivirus
installé (Defender, Bitdefender GravityZone, ESET…) avec son état
codé ; Defender lui-même reste lu par Get-MpComputerStatus (#440).
macOS : aucun registre commun -- les produits sont reconnus par leurs
fichiers et leurs démons (liste ci-dessous), complétés par les
protections système (XProtect : version et date, Gatekeeper, SIP).

Forme : {"products": [{name, enabled, up_to_date, source}], "primary": name,
         "status": ok | disabled | outdated | none | unknown, "platform": {...}}
Logique PURE (aucun sous-processus ici) : testée dans tests/test_antivirus.py."""
import re

# productState du Centre de sécurité Windows : 6 chiffres hexadécimaux,
# les deux du milieu = actif (10/11) ou non (00/01), les deux derniers =
# définitions à jour (00) ou périmées (10). Décodage d'usage courant, jamais
# documenté officiellement : un état inconnu reste None, pas deviné.
def decode_security_center_state(state):
    try:
        hexs = "%06X" % int(state)
    except (TypeError, ValueError):
        return None, None
    mid, last = hexs[2:4], hexs[4:6]
    enabled = True if mid in ("10", "11") else False if mid in ("00", "01") else None
    up_to_date = True if last == "00" else False if last == "10" else None
    return enabled, up_to_date


def map_windows(products, defender=None):
    """Liste AntiVirusProduct (displayName, productState) + bloc Defender -> section antivirus."""
    out = []
    seen = set()
    for p in products or []:
        name = (p.get("displayName") or p.get("name") or "").strip()
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        enabled, up_to_date = decode_security_center_state(p.get("productState"))
        out.append({"name": name, "enabled": enabled, "up_to_date": up_to_date, "source": "security-center"})
    if isinstance(defender, dict) and not any("defender" in x["name"].lower() for x in out):
        out.append({"name": "Microsoft Defender", "enabled": bool(defender.get("enabled")),
                    "up_to_date": None if defender.get("signatures_age_days") is None else defender["signatures_age_days"] <= 7,
                    "realtime": defender.get("realtime"), "definitions_age_days": defender.get("signatures_age_days"), "source": "defender"})
    return _finish(out, platform=None)


# macOS : produits reconnus par la présence de fichiers ET/OU d'un démon.
MAC_PRODUCTS = [
    ("Bitdefender", ["/Library/Bitdefender/AVP", "/Applications/Endpoint Security for Mac.app", "/Applications/Bitdefender"], ["BDLDaemon", "bdmd", "EndpointSecurityforMac", "BDCoreIssues"]),
    ("Microsoft Defender", ["/Applications/Microsoft Defender.app", "/Library/Application Support/Microsoft/Defender"], ["wdavdaemon"]),
    ("Sophos", ["/Library/Sophos Anti-Virus", "/Applications/Sophos/Sophos Endpoint.app", "/Applications/Sophos Endpoint.app"], ["SophosScanD", "SophosAntiVirus", "SophosServiceManager"]),
    ("ESET", ["/Applications/ESET Endpoint Security.app", "/Applications/ESET Cyber Security.app", "/Applications/ESET Endpoint Antivirus.app"], ["esets_daemon", "ecs_daemon"]),
    ("Kaspersky", ["/Applications/Kaspersky Internet Security.app", "/Library/Application Support/Kaspersky Lab"], ["kav", "klnagent"]),
    ("Avast", ["/Applications/Avast.app", "/Applications/Avast Security.app"], ["com.avast.daemon"]),
    ("Malwarebytes", ["/Applications/Malwarebytes.app", "/Library/Application Support/Malwarebytes"], ["RTProtectionDaemon"]),
    ("SentinelOne", ["/Applications/SentinelOne", "/Library/Sentinel"], ["sentineld"]),
    ("CrowdStrike Falcon", ["/Applications/Falcon.app", "/Library/CS"], ["falcond", "falcon-sensor"]),
    ("ClamAV", ["/usr/local/sbin/clamd", "/opt/homebrew/sbin/clamd", "/usr/local/bin/clamscan", "/opt/homebrew/bin/clamscan"], ["clamd"]),
]
XPROTECT_MAX_AGE_DAYS = 60


def map_macos(exists, processes, xprotect_version=None, xprotect_age_days=None, spctl=None, csrutil=None):
    """exists(path) -> bool ; processes : texte de `ps -axo comm` ; spctl/csrutil : sorties texte."""
    procs = set()
    for line in (processes or "").splitlines():
        name = line.strip().split("/")[-1]
        if name:
            procs.add(name)
    out = []
    for name, paths, daemons in MAC_PRODUCTS:
        installed = any(exists(p) for p in paths)
        running = any(d in procs for d in daemons)
        if not installed and not running:
            continue
        out.append({"name": name, "enabled": running, "up_to_date": None, "source": "files+daemons",
                    "installed": installed, "daemon_running": running})
    platform = {
        "xprotect_version": xprotect_version, "xprotect_age_days": xprotect_age_days,
        "gatekeeper": _parse_spctl(spctl), "sip": _parse_csrutil(csrutil),
    }
    return _finish(out, platform=platform)


def _parse_spctl(text):
    if not text:
        return None
    t = text.lower()
    return True if "assessments enabled" in t else False if "assessments disabled" in t else None


def _parse_csrutil(text):
    if not text:
        return None
    t = text.lower()
    return True if "status: enabled" in t else False if "status: disabled" in t else None


def _finish(products, platform=None):
    status = "none"
    primary = None
    if products:
        enabled = [p for p in products if p.get("enabled")]
        primary = (enabled or products)[0]["name"]
        if not enabled:
            status = "unknown" if all(p.get("enabled") is None for p in products) else "disabled"
        elif any(p.get("up_to_date") is False for p in enabled):
            status = "outdated"
        else:
            status = "ok"
    return {"products": products, "primary": primary, "status": status, "platform": platform}


def evaluate(av, thresholds=None):
    """Risques (forme de risks.evaluate) depuis la section antivirus."""
    t = thresholds or {}
    out = []
    if not isinstance(av, dict):
        return out
    products = av.get("products") or []
    status = av.get("status")
    if products and all(p.get("source") == "defender" for p in products):
        status = None  # Defender seul : ses risques détaillés (#440) sont déjà produits par risks.evaluate
    if status == "none":
        out.append({"id": "antivirus-none", "severity": "warning", "subject": "antivirus", "message": "aucun antivirus détecté sur ce poste"})
    elif status == "disabled":
        names = ", ".join(p["name"] for p in products) or "?"
        out.append({"id": "antivirus-off", "severity": "critical", "subject": "antivirus", "message": "antivirus désactivé : %s" % names})
    elif status == "outdated":
        names = ", ".join(p["name"] for p in products if p.get("up_to_date") is False)
        out.append({"id": "antivirus-outdated", "severity": "warning", "subject": "antivirus", "message": "définitions antivirus périmées : %s" % names})
    for p in products:
        if p.get("enabled") is None and p.get("source") == "security-center":
            out.append({"id": "antivirus-state-unknown", "severity": "info", "subject": p["name"], "message": "état de %s illisible dans le Centre de sécurité" % p["name"]})
    plat = av.get("platform") or {}
    if plat.get("gatekeeper") is False:
        out.append({"id": "gatekeeper-off", "severity": "warning", "subject": "gatekeeper", "message": "Gatekeeper désactivé (spctl --master-disable)"})
    if plat.get("sip") is False:
        out.append({"id": "sip-off", "severity": "warning", "subject": "sip", "message": "System Integrity Protection désactivée"})
    age = plat.get("xprotect_age_days")
    if age is not None and age > t.get("xprotect_max_age_days", XPROTECT_MAX_AGE_DAYS):
        out.append({"id": "xprotect-old", "severity": "info", "subject": "xprotect", "message": "XProtect non mis à jour depuis %d jours" % age})
    return out


def summary_line(av):
    """Une ligne lisible pour la tuile (repli si le front n'a pas la version)."""
    if not isinstance(av, dict):
        return None
    if not av.get("products"):
        return "aucun antivirus détecté"
    parts = []
    for p in av["products"]:
        st = "actif" if p.get("enabled") else "inactif" if p.get("enabled") is False else "état inconnu"
        if p.get("up_to_date") is False:
            st += ", définitions périmées"
        parts.append("%s (%s)" % (p["name"], st))
    return " · ".join(parts)
