# -*- coding: utf-8 -*-
"""Identification d'un équipement réseau -- logique PURE, testée
(tests/test_identify.py), sans réseau : on lui donne ce que les sources
ont vu (MAC, sysDescr/sysObjectID SNMP, ENTITY-MIB, classe Zenoss,
indices de l'exploration) et elle rend constructeur, modèle, système,
genre (routeur / switch / …), GÉNÉRATION (récent / ancien) et la
confiance, avec les preuves.

Demandé (#506) : « identifier côté LAN la marque et le modèle d'un
routeur sachant que les routeurs récents sont les MikroTik et que les
autres, s'il en reste, datent de l'origine de la boucle locale fibre,
c'est-à-dire d'environ 25 ans ». D'où le champ `generation` : un IOS
12.x, un Catalyst 2900XL, un ProCurve 2524, un BayStack 450 ou un
SuperStack II sont datés « ancien (années 2000) » avec la raison ; un
RouterOS est « récent ».

Tout ce qui suit est écrit d'après les formats CONNUS des sysDescr des
constructeurs (documentation et exemples publics), jamais vérifié ici
contre un équipement réel : chaque motif est une expression régulière
volontairement tolérante, et un texte non reconnu reste `model=None`,
jamais une valeur inventée.
"""
import re

# --- IANA Private Enterprise Numbers (sysObjectID = 1.3.6.1.4.1.<pen>.…)
ENTERPRISES = {
    9: ("Cisco", "reseau"), 11: ("HP / HPE", "reseau"), 43: ("3Com", "reseau"),
    45: ("SynOptics / Nortel", "reseau"), 171: ("D-Link", "reseau"), 232: ("Compaq", "hote"),
    311: ("Microsoft", "hote"), 318: ("APC", "onduleur"), 562: ("Nortel", "reseau"),
    674: ("Dell", "hote"), 890: ("Zyxel", "reseau"), 1588: ("Brocade", "reseau"),
    1872: ("Alteon / Nortel", "reseau"), 1916: ("Extreme Networks", "reseau"),
    1991: ("Foundry / Brocade", "reseau"), 2011: ("Huawei", "reseau"), 2021: ("UCD-SNMP (Linux)", "hote"),
    2620: ("Check Point", "reseau"), 2636: ("Juniper", "reseau"), 3224: ("NetScreen / Juniper", "reseau"),
    3375: ("F5", "reseau"), 3955: ("Linksys", "reseau"), 4413: ("Broadcom (switch OEM)", "reseau"),
    4526: ("Netgear", "reseau"), 5624: ("Enterasys", "reseau"), 6027: ("Force10 / Dell", "reseau"),
    6486: ("Alcatel-Lucent Enterprise", "reseau"), 6574: ("Synology", "stockage"), 6889: ("Avaya", "reseau"),
    8072: ("net-snmp (Linux/BSD)", "hote"), 8741: ("SonicWall", "reseau"), 12356: ("Fortinet", "reseau"),
    14823: ("Aruba", "reseau"), 14988: ("MikroTik", "reseau"), 24681: ("QNAP", "stockage"),
    25461: ("Palo Alto", "reseau"), 25506: ("H3C / HP Comware", "reseau"), 30065: ("Arista", "reseau"),
    41112: ("Ubiquiti", "reseau"), 44641: ("Teltonika", "reseau"), 2352: ("Redback / Ericsson", "reseau"),
    5771: ("Cisco (Meraki)", "reseau"), 29671: ("Meraki", "reseau"), 10002: ("Frogfoot (OpenWrt)", "reseau"),
}

KINDS = ("routeur", "switch", "pare-feu", "point d'accès", "hôte", "hyperviseur", "imprimante", "onduleur", "stockage", "inconnu")


def enterprise_of(sys_object_id):
    """« 1.3.6.1.4.1.14988.1 » -> (14988, 'MikroTik', 'reseau') ; None
    si l'OID n'est pas sous enterprises ou inconnu de la table."""
    m = re.match(r"^\.?1\.3\.6\.1\.4\.1\.(\d+)(?:\.|$)", str(sys_object_id or ""))
    if not m:
        return None
    pen = int(m.group(1))
    hit = ENTERPRISES.get(pen)
    return (pen, hit[0], hit[1]) if hit else (pen, None, None)


# --- sysDescr ---------------------------------------------------------
# Ordre : du plus spécifique au plus général. Chaque motif rend un dict
# partiel (vendor, model, os, version, kind, generation, reason).

def _cisco_ios(d):
    # « Cisco Internetwork Operating System Software IOS (tm) C2600 Software (C2600-I-M), Version 12.2(13) »
    # « Cisco IOS Software, C2960 Software (C2960-LANBASEK9-M), Version 12.2(55)SE12 »
    # « Cisco IOS Software [Everest], Catalyst L3 Switch Software (CAT9K_IOSXE), Version 16.6.4 »
    if not re.search(r"Cisco (Internetwork Operating System|IOS)", d):
        return None
    out = {"vendor": "Cisco", "os": "IOS"}
    if "IOSXE" in d.upper() or "IOS-XE" in d.upper():
        out["os"] = "IOS-XE"
    m = re.search(r"IOS \(tm\) (\S+) Software|IOS Software(?: \[[^\]]*\])?, (\S+) Software", d)
    fam = (m.group(1) or m.group(2)) if m else None
    if fam:
        out["family"] = fam
        out["model"] = fam
    m = re.search(r"Version ([\w.()]+)", d)
    if m:
        out["version"] = m.group(1)
    if fam:
        if _CISCO_SWITCH_FAMILIES.match(fam):
            out["kind"] = "switch"
        elif _CISCO_ROUTER_FAMILIES.match(fam):
            out["kind"] = "routeur"
    return out


# Familles d'images IOS : Catalyst (switch) d'abord -- C3750 est un switch
# alors que C37xx désigne les routeurs 3700 ; C2900XL un switch alors que
# C2900 est l'ISR G2. C1000 volontairement absent des deux (routeur 1000
# des années 1990 ET Catalyst 1000 de 2019).
_CISCO_SWITCH_FAMILIES = re.compile(r"^(C2900XL|C3500XL|C29[4-7]\d\w*|C2960\w*|C35[56]0\w*|C3750\w*|C3650\w*|C3850\w*|C45\d\d\w*|C49\d\d\w*|C65\d\d\w*|C9[2-6]\d\d\w*|CAT\w*|WS-C\w*|IE\w*|ME\w*)$", re.I)
_CISCO_ROUTER_FAMILIES = re.compile(r"^(C8\d\d\w*|C1[1-9]\d\d\w*|C25\d\d\w*|C26\d\d\w*|C28\d\d\w*|C29[0-3]\d|C2951|C2921|C2911|C2901|C36[0-4]\d\w*|C37[0-4]\d\w*|C38\d\d\w*|C39\d\d\w*|C72\d\d\w*|C75\d\d\w*|C4000|ISR\w*|ASR\w*|CSR\w*|RSP\w*)$", re.I)


def _cisco_nxos(d):
    # « Cisco NX-OS(tm) n3000, Software (n3000-uk9), Version 6.0(2)U6(10), RELEASE SOFTWARE … »
    # « Cisco Nexus Operating System (NX-OS) Software 9.3(5) » -- Nexus (2008+) : toujours récent.
    if "NX-OS" not in d and "Nexus Operating System" not in d:
        return None
    out = {"vendor": "Cisco", "os": "NX-OS", "kind": "switch", "generation": "recent", "reason": "NX-OS (Nexus, 2008+)"}
    m = re.search(r"NX-OS\(tm\) (\S+?),", d)
    if m:
        out["family"] = m.group(1)
        out["model"] = "Nexus " + m.group(1).lstrip("nN").split("-")[0] if m.group(1).lower().startswith("n") else m.group(1)
    v = re.search(r"Version ([\w.()]+)|Software ([\d][\w.()]*)", d)
    if v:
        out["version"] = v.group(1) or v.group(2)
    return out


def _cisco_catos(d):
    # « Cisco Systems, Inc. WS-C2948 Cisco Catalyst Operating System Software, Version McpSW: 6.3(3) »
    # « Cisco Systems WS-C5000 Software, Version McpSW: 4.5(2) NmpSW: 4.5(2) »
    m = re.search(r"Cisco Systems(?:, Inc\.)? (WS-C\S+)", d)
    if not m or "Catalyst Operating System" not in d and "McpSW" not in d:
        return None
    out = {"vendor": "Cisco", "os": "CatOS", "model": m.group(1), "family": m.group(1), "kind": "switch"}
    v = re.search(r"NmpSW: ([\w.()]+)", d) or re.search(r"Version ([\w.()]+)", d)
    if v:
        out["version"] = v.group(1)
    return out


def _mikrotik(d):
    # « RouterOS CCR1036-8G-2S+ », « RouterOS v6.49.10 (long-term) on CRS326-24G-2S+ », « RouterOS RB5009UG+S+ »
    m = re.match(r"^\s*RouterOS(?: v?([\d.]+\S*)(?: \([^)]*\))? on)? (\S+)", d)
    if not m:
        return None
    out = {"vendor": "MikroTik", "os": "RouterOS", "model": m.group(2), "generation": "recent",
           "reason": "RouterOS (MikroTik) -- génération récente"}
    if m.group(1):
        out["version"] = m.group(1)
    return out


def _hp_procurve(d):
    # « ProCurve J9028A Switch 1800-24G, revision PB.03.02, ROM PB.03.00 »
    # « HP J9019B ProCurve Switch 2510-24, revision Y.11.12, ROM Y.10.00 »
    # « HP J4813A ProCurve Switch 2524, revision F.05.70, ROM F.02.01 »
    # « Aruba JL256A 2930F-48G-PoE+-4SFP+ Switch, revision WC.16.10.0009 »
    m = re.search(r"(?:HP|ProCurve|Aruba|HPE)\s+(J[A-Z]?\d{3,4}[A-Z]?)\s+(?:ProCurve\s+)?(?:Switch\s+)?([\w./+-]+(?:\s+Switch)?)", d)
    if not m:
        return None
    out = {"vendor": "HP ProCurve / HPE", "os": "ProCurve", "part": m.group(1), "model": m.group(2).replace(" Switch", ""), "kind": "switch"}
    if d.lstrip().startswith("Aruba") or "Aruba" in d:
        out["vendor"] = "Aruba (HPE)"
        out["os"] = "ArubaOS-Switch"
    v = re.search(r"revision ([A-Z]{1,2}\.[\d.]+)", d)
    if v:
        out["version"] = v.group(1)
    return out


def _hp_comware(d):
    # « HP Comware Platform Software, Software Version 5.20 Release 2208P01, HP A5120-48G EI Switch »
    # « H3C Comware Platform Software, Software Version 5.20 … H3C S5120-28P-SI »
    if "Comware" not in d:
        return None
    out = {"vendor": "H3C / HP Comware" if d.startswith("H3C") else "HP / HPE (Comware)", "os": "Comware", "kind": "switch"}
    v = re.search(r"Software Version ([\w.]+)", d)
    if v:
        out["version"] = v.group(1)
    m = re.search(r"(?:HP|H3C|HPE)\s+([A-Z]?\d{4}[\w-]*)", d)
    if m:
        out["model"] = m.group(1)
    return out


def _threecom(d):
    # « 3Com SuperStack 3 Switch 4400, SW Version 6.10 », « 3Com SuperStack II Switch 3300 », « 3Com Baseline Switch 2226 Plus »
    if not d.lstrip().startswith("3Com"):
        return None
    out = {"vendor": "3Com", "kind": "switch"}
    m = re.search(r"3Com\s+((?:SuperStack (?:II|3|4)|Baseline|OfficeConnect)\s+Switch\s+[\w-]+(?: Plus)?)", d)
    if m:
        out["model"] = m.group(1)
        if "SuperStack II" in m.group(1) or "SuperStack 3" in m.group(1):
            out["generation"] = "ancien"
            out["reason"] = "3Com SuperStack II/3 -- gamme des années 1997-2005"
    v = re.search(r"(?:SW )?Version ([\w.]+)", d)
    if v:
        out["version"] = v.group(1)
    return out


def _nortel(d):
    # « BayStack 450-24T HW:RevD  FW:V1.46 SW:v4.5.0.9 ISVN:2 », « Ethernet Routing Switch 5520-48T-PWR HW:02 FW:6.0.0.9 SW:v6.6.0.024 », « Passport-8610 »
    m = re.search(r"(BayStack\s+[\w-]+|Ethernet Routing Switch\s+[\w-]+|Passport-?\s?\d+|Accelar\s+\d+|Nortel\s+[\w-]+)", d)
    if not m:
        return None
    out = {"vendor": "Nortel / Bay Networks", "model": m.group(1), "kind": "switch"}
    if m.group(1).startswith(("BayStack", "Accelar")):
        out["generation"] = "ancien"
        out["reason"] = "BayStack / Accelar (Bay Networks, Nortel) -- gamme des années 1998-2005"
    v = re.search(r"SW:v?([\d.]+)", d)
    if v:
        out["version"] = v.group(1)
    return out


def _alcatel(d):
    # « Alcatel-Lucent OS6450-24 6.7.1.71.R04 », « Alcatel-Lucent Enterprise OS6860E-24 8.5.255.R02 », « Alcatel OmniStack 6224 »
    m = re.search(r"Alcatel(?:-Lucent)?(?: Enterprise)?\s+((?:OS|OmniSwitch|OmniStack)[\w-]*(?:\s+\d{4}[\w-]*)?)", d)
    if not m:
        return None
    out = {"vendor": "Alcatel-Lucent Enterprise", "model": m.group(1), "kind": "switch"}
    v = re.search(r"\s(\d+\.\d+\.\d+(?:\.\d+)?(?:\.R\d+)?)", d)
    if v:
        out["version"] = v.group(1)
    if "OmniStack" in m.group(1):
        out["generation"] = "ancien"
        out["reason"] = "OmniStack (Alcatel) -- gamme des années 2000-2005"
    return out


def _juniper(d):
    # « Juniper Networks, Inc. ex2200-24t-4g Ethernet Switch, kernel JUNOS 12.3R6.6 … »
    m = re.search(r"Juniper Networks, Inc\.\s+(\S+)\s+(?:internet router|Ethernet Switch|[\w ]+?),\s+kernel JUNOS ([\w.]+)", d)
    if not m:
        if "JUNOS" in d or "Juniper" in d:
            return {"vendor": "Juniper", "os": "Junos"}
        return None
    kind = "switch" if "Ethernet Switch" in d else "routeur"
    return {"vendor": "Juniper", "os": "Junos", "model": m.group(1), "version": m.group(2), "kind": kind}


def _netgear(d):
    # « GS724Tv4 », « GS748Tv5 », « M4300-52G ProSAFE … », « Netgear GSM7224 »
    m = re.search(r"\b(GS\d{3}(?!\d)[\w+-]*|GSM\d{4}\w*|M4[23]00[\w-]*|JGS\d{3}\w*|FS\d{3}(?!\d)\w*|XS\d{3}(?!\d)\w*|GSS\d{3}\w*|MS\d{3}(?!\d)\w*)\b", d)
    if not m or not (d.lstrip().startswith(("GS", "GSM", "M4", "XS", "FS", "JGS", "MS", "GSS")) or re.search(r"netgear|prosafe", d, re.I)):
        return None
    return {"vendor": "Netgear", "model": m.group(1), "kind": "switch"}


def _dlink(d):
    m = re.search(r"\b(D[EGX]S-\d{4}[\w/-]*)\b", d)
    if not m:
        return None
    return {"vendor": "D-Link", "model": m.group(1), "kind": "switch"}


def _zyxel(d):
    m = re.search(r"\b((?:GS|XGS|XS|ES|MES|XMG)\d{4}[\w-]*|USG[\w-]*\d+|ZyWALL[\w -]*\d+|NWA\d{4}[\w-]*|NSG\d+|VMG\d+)\b", d)
    if not m or not re.search(r"zyxel|zywall|nebula", d, re.I) and not d.lstrip().startswith(("GS", "XGS", "USG", "NWA", "XS", "MES")):
        return None
    kind = "pare-feu" if m.group(1).upper().startswith(("USG", "ZYWALL", "NSG")) else "point d'accès" if m.group(1).startswith("NWA") else "switch"
    return {"vendor": "Zyxel", "model": m.group(1), "kind": kind}


def _ubiquiti(d):
    # « EdgeSwitch 24-Port 250W, 1.9.3, Linux 3.6.5 », « EdgeOS … », « UAP-AC-Pro … »
    m = re.search(r"(EdgeSwitch[\w -]*?|EdgeRouter[\w -]*?|EdgeOS|US-\d+[\w-]*|USW-[\w-]+|UAP-[\w-]+|UniFi[\w -]*)", d)
    if not m:
        return None
    model = m.group(1).strip(" ,")
    kind = "routeur" if model.startswith(("EdgeRouter", "EdgeOS")) else "point d'accès" if model.startswith("UAP") else "switch"
    return {"vendor": "Ubiquiti", "model": model, "kind": kind, "generation": "recent", "reason": "gamme Ubiquiti (années 2010+)"}


def _fortinet(d):
    m = re.search(r"\b(F(?:GT|WF|SW|AP)[_-]?[\w-]+)\b", d)
    if not m and "Fortinet" not in d and "FortiGate" not in d:
        return None
    out = {"vendor": "Fortinet", "kind": "pare-feu"}
    if m:
        out["model"] = m.group(1)
        if m.group(1).startswith(("FSW", "FS-")):
            out["kind"] = "switch"
    return out


def _apc(d):
    if not re.search(r"APC (Web/SNMP Management Card|Network Management Card|Smart-UPS)", d):
        return None
    out = {"vendor": "APC (Schneider)", "kind": "onduleur", "model": "Network Management Card"}
    v = re.search(r"AOS v?([\d.]+)|PF:v?([\d.]+)", d)
    if v:
        out["version"] = v.group(1) or v.group(2)
    return out


def _printer(d):
    if re.search(r"HP ETHERNET MULTI-ENVIRONMENT|JETDIRECT|Brother NC-|KONICA MINOLTA|Canon iR|RICOH|Lexmark|Xerox|KYOCERA|EPSON", d, re.I):
        v = re.search(r"(HP|Brother|KONICA MINOLTA|Canon|RICOH|Lexmark|Xerox|KYOCERA|EPSON)", d, re.I)
        return {"vendor": v.group(1).title() if v else None, "kind": "imprimante"}
    return None


def _windows(d):
    m = re.search(r"Software: Windows (?:Version )?([\d.]+)(?: \(Build (\d+))?", d)
    if not m:
        return None
    return {"os": "Windows", "version": m.group(1) + (" build " + m.group(2) if m.group(2) else ""), "kind": "hôte"}


def _linux(d):
    # « Linux hostname 5.10.0-8-amd64 #1 SMP Debian … x86_64 »
    m = re.match(r"^\s*(Linux|FreeBSD|OpenBSD|NetBSD|Darwin)\s+(\S+)\s+([\w.+-]+)", d)
    if not m:
        return None
    out = {"os": m.group(1), "version": m.group(3), "sys_hostname": m.group(2), "kind": "hôte"}
    if re.search(r"pve|proxmox", d, re.I):
        out["kind"] = "hyperviseur"
    return out


SYSDESCR_PARSERS = [_mikrotik, _cisco_nxos, _cisco_catos, _cisco_ios, _hp_procurve, _hp_comware, _threecom, _nortel,
                    _alcatel, _juniper, _ubiquiti, _fortinet, _apc, _zyxel, _netgear, _dlink, _printer,
                    _windows, _linux]


def parse_sys_descr(sys_descr):
    """-> dict partiel (vendor, model, os, version, kind, generation,
    reason, family) ; {} si rien de reconnu. Jamais d'exception."""
    d = " ".join(str(sys_descr or "").replace("\r", " ").replace("\n", " ").split())
    if not d:
        return {}
    for parser in SYSDESCR_PARSERS:
        try:
            out = parser(d)
        except Exception:  # noqa: BLE001 -- un motif ne doit jamais faire tomber l'identification
            out = None
        if out:
            out.setdefault("matched_by", parser.__name__.lstrip("_"))
            return out
    return {}


# --- Génération ---------------------------------------------------------
# Familles Cisco d'avant ~2005 (routeurs et Catalyst de la première
# génération des boucles locales fibre), IOS 12.x compris.
_CISCO_OLD_FAMILIES = re.compile(
    r"^(C(?:1[0-9]{2}|2500|2600|3600|3700|1600|1700|2800|3800|800|1000|4000|4500|7200|7500|AS5)\w*|"
    r"C2900XL|C3500XL|C2950|C2955|C2940|C3550|C3560(?!-)|C3750(?!-)|C2970|C2948|C4000|C5000|C6000|"
    r"WS-C(?:19|29|35|40|50|55|60)\d{2}\w*|RSP|GS7)", re.I)
_CISCO_RECENT_FAMILIES = re.compile(r"^(C(?:9|8|1[0-9]{3})\w*|CAT9K|ISR|ASR|C3650|C3850|C2960(?:X|XR|L|CX|S)|C3560(?:X|CX|E)|C3750(?:X|E)|IE-|CSR|C1100|C1900|C4500X|N[3579]K)", re.I)


def generation_of(info, oui_category=None):
    """(« recent » | « ancien » | None, raison). Un modèle inconnu reste
    None -- on ne date jamais au hasard."""
    if info.get("generation"):
        return info["generation"], info.get("reason")
    vendor = (info.get("vendor") or "").lower()
    fam = info.get("family") or info.get("model") or ""
    version = info.get("version") or ""
    if vendor.startswith("cisco"):
        if info.get("os") == "CatOS":
            return "ancien", "CatOS (Catalyst 1ère génération, avant 2005)"
        if _CISCO_RECENT_FAMILIES.match(fam) or info.get("os") == "IOS-XE":
            return "recent", "famille Cisco des années 2010+ / IOS-XE"
        if _CISCO_OLD_FAMILIES.match(fam):
            return "ancien", "famille Cisco %s (Catalyst/routeurs des années 1998-2008)" % fam
        m = re.match(r"(\d+)\.(\d+)", version)
        if m:
            major, minor = int(m.group(1)), int(m.group(2))
            if major <= 11:
                return "ancien", "IOS %s (branche 11.x, années 1990)" % version
            if major == 12:
                if re.search(r"\)(SE|SG|EX|EY|EW|SX|SR|SB|XE|E)[A-Z]*\d*$", version):
                    return None, "IOS %s (branche Catalyst 12.2S*, 2005-2013 : génération indéterminée)" % version
                if minor <= 2:
                    return "ancien", "IOS %s (branche 12.0-12.2, années 1999-2005)" % version
                return "ancien", "IOS %s (branche 12.3/12.4, années 2005-2010)" % version
            if major >= 15:
                return "recent", "IOS %s (2010+)" % version
        return None, None
    if "procurve" in vendor or "aruba" in vendor:
        m = re.match(r"([A-Z]{1,2})\.", version)
        if m and len(m.group(1)) == 1:
            return "ancien", "révision ProCurve à une lettre (%s : firmwares d'avant 2010)" % version
        if re.match(r"^(1600M|2400M|2424M|4000M|8000M|2524|2512|2650|2626|2610|2510|2610|4100|4104|4108|5300|1800|2300|2500|2800)", fam):
            return "ancien", "gamme ProCurve %s (années 1998-2008)" % fam
        if m and len(m.group(1)) == 2:
            return "recent", "révision ProCurve/Aruba à deux lettres (%s : 2010+)" % version
        return None, None
    if "mikrotik" in vendor or "ubiquiti" in vendor:
        return "recent", "gamme %s (2010+)" % info.get("vendor")
    return None, None


# --- Genre (routeur / switch / …) ---------------------------------------
_KIND_FROM_ZENOSS = [
    ("/Network/Router/Firewall", "pare-feu"), ("/Network/Firewall", "pare-feu"),
    ("/Network/Router", "routeur"), ("/Network/Switch", "switch"), ("/Network/Wireless", "point d'accès"),
    ("/Network/Access", "point d'accès"), ("/Printer", "imprimante"), ("/Power/UPS", "onduleur"), ("/Power", "onduleur"),
    ("/Server/Virtual", "hyperviseur"), ("/Server", "hôte"), ("/Storage", "stockage"), ("/KVM", "hyperviseur"),
]


_ZENOSS_VENDORS = {"cisco": "Cisco", "hp": "HP ProCurve / HPE", "procurve": "HP ProCurve / HPE", "hpe": "HP ProCurve / HPE", "aruba": "Aruba (HPE)",
                   "nortel": "Nortel / Bay Networks", "baystack": "Nortel / Bay Networks", "bay": "Nortel / Bay Networks", "3com": "3Com",
                   "juniper": "Juniper", "mikrotik": "MikroTik", "alcatel": "Alcatel-Lucent Enterprise", "netgear": "Netgear", "zyxel": "Zyxel",
                   "fortinet": "Fortinet", "dell": "Dell", "dlink": "D-Link", "d-link": "D-Link", "ubiquiti": "Ubiquiti", "extreme": "Extreme Networks",
                   "huawei": "Huawei", "arista": "Arista", "brocade": "Brocade", "foundry": "Foundry / Brocade", "avaya": "Avaya", "linksys": "Linksys (Cisco)",
                   "checkpoint": "Check Point", "paloalto": "Palo Alto", "sonicwall": "SonicWall", "watchguard": "WatchGuard", "tplink": "TP-Link", "tp-link": "TP-Link"}


def zenoss_class_info(device_class):
    """« /Network/Router/Cisco » -> (kind, vendor hint). Le dernier
    segment d'une classe /Network/* est souvent le constructeur."""
    dc = str(device_class or "").strip()
    kind = None
    for prefix, k in _KIND_FROM_ZENOSS:
        if dc.startswith(prefix):
            kind = k
            break
    vendor = None
    if dc.startswith("/Network/"):
        # premier segment reconnu comme constructeur (« /Network/Switch/Cisco/Nexus »
        # -> Cisco) ; un segment inconnu (gamme, modèle, site) ne devient jamais
        # un constructeur inventé
        for seg in [p for p in dc.split("/") if p][2:]:
            hit = _ZENOSS_VENDORS.get(seg.lower())
            if hit:
                vendor = hit
                break
    return kind, vendor


def kind_from_services(ports):
    """Indice de genre d'après les services vus par l'exploration
    (ports en écoute) -- faible : un serveur Linux a aussi SSH/HTTP."""
    p = set(int(x) for x in (ports or []) if str(x).isdigit())
    if {8728, 8729} & p or 8291 in p:  # API RouterOS, Winbox
        return "routeur", "API RouterOS / Winbox en écoute"
    if 161 in p and (23 in p or 22 in p) and not ({3389, 445, 139, 5432, 3306, 25} & p):
        return None, "SNMP + telnet/SSH sans services de serveur (équipement de gestion probable)"
    if {3389, 445, 139} & p:
        return "hôte", "services Windows en écoute"
    if 631 in p or 9100 in p:
        return "imprimante", "port d'impression en écoute"
    return None, None


def merge(evidence):
    """Fusionne les preuves en une identification.

    `evidence` : {
        mac: str, oui: {vendor, category, source} | None,
        sys_descr: str, sys_object_id: str, sys_name: str,
        entity: {model, serial, mfg, sw, hw}, zenoss: {device_class, hw_manufacturer, hw_product,
        os_manufacturer, os_product, serial}, role_hint: str, ports: [int], hostname: str,
        manual: {vendor, model, kind} (l'utilisateur a le dernier mot) }
    -> {vendor, model, os, os_version, serial, kind, generation, generation_reason,
        confidence (0-1), sources: [..], evidence: {…}}"""
    ev = evidence or {}
    out = {"vendor": None, "model": None, "os": None, "os_version": None, "serial": None, "kind": "inconnu",
           "generation": None, "generation_reason": None, "confidence": 0.0, "sources": [], "notes": []}
    score = 0.0
    parsed = parse_sys_descr(ev.get("sys_descr")) if ev.get("sys_descr") else {}
    ent = ev.get("entity") or {}
    zen = ev.get("zenoss") or {}
    oui = ev.get("oui") or {}
    pen = enterprise_of(ev.get("sys_object_id"))

    # 1. sysDescr : la meilleure source quand elle parle
    if parsed:
        out["sources"].append("sysDescr")
        for k_src, k_dst in (("vendor", "vendor"), ("model", "model"), ("os", "os"), ("version", "os_version"), ("kind", "kind")):
            if parsed.get(k_src):
                out[k_dst] = parsed[k_src]
        score += 0.5 if parsed.get("model") else 0.3
    # 2. sysObjectID : constructeur sûr (numéro IANA), jamais le modèle
    if pen:
        out["sources"].append("sysObjectID")
        if pen[1] and not out["vendor"]:
            out["vendor"] = pen[1]
            score += 0.3
        elif pen[1]:
            score += 0.1
        if pen[1] is None:
            out["notes"].append("numéro d'entreprise IANA %d inconnu de la table" % pen[0])
    # 3. ENTITY-MIB : modèle et numéro de série exacts
    if ent.get("model") or ent.get("serial"):
        out["sources"].append("ENTITY-MIB")
        if ent.get("model"):
            out["model"] = ent["model"]
            score += 0.2
        if ent.get("serial"):
            out["serial"] = ent["serial"]
        if ent.get("mfg") and not out["vendor"]:
            out["vendor"] = ent["mfg"]
        if ent.get("sw") and not out["os_version"]:
            out["os_version"] = ent["sw"]
    # 4. Zenoss : classe (genre + constructeur), matériel, série
    if zen:
        out["sources"].append("zenoss")
        zkind, zvendor = zenoss_class_info(zen.get("device_class"))
        if zkind and out["kind"] == "inconnu":
            out["kind"] = zkind
        if not out["vendor"] and (zen.get("hw_manufacturer") or zvendor):
            out["vendor"] = zen.get("hw_manufacturer") or zvendor
            score += 0.2
        if not out["model"] and zen.get("hw_product"):
            out["model"] = zen["hw_product"]
            score += 0.15
        if not out["os"] and zen.get("os_product"):
            out["os"] = zen["os_product"]
        if not out["serial"] and zen.get("serial"):
            out["serial"] = zen["serial"]
    # 5. Exploration : rôle observé (passerelle = routeur), services
    role = (ev.get("role_hint") or "").lower()
    if role:
        out["sources"].append("exploration")
        if "gateway" in role or "passerelle" in role or "router" in role or "routeur" in role:
            if out["kind"] == "inconnu":
                out["kind"] = "routeur"
            score += 0.1
    skind, sreason = kind_from_services(ev.get("ports"))
    if skind and out["kind"] == "inconnu":
        out["kind"] = skind
        out["notes"].append(sreason)
    # 6. OUI : constructeur probable, catégorie -> genre par défaut
    if oui.get("vendor") or oui.get("category"):
        out["sources"].append("OUI")
        if not out["vendor"] and oui.get("vendor") and oui.get("category") not in ("virtualisation", "locale"):
            out["vendor"] = oui["vendor"]
            score += 0.15
        elif out["vendor"] and oui.get("vendor") and oui["vendor"].split()[0].lower() in out["vendor"].lower():
            score += 0.1  # deux sources concordantes
        cat = oui.get("category")
        if out["kind"] == "inconnu":
            if cat == "virtualisation":
                out["kind"] = "hôte"
                out["notes"].append("MAC d'hyperviseur/VM (%s) : jamais un équipement physique" % (oui.get("vendor") or "?"))
            elif cat == "onduleur":
                out["kind"] = "onduleur"
            elif cat == "stockage":
                out["kind"] = "stockage"
            elif cat == "hote":
                out["kind"] = "hôte"
        if cat == "locale":
            out["notes"].append("MAC localement administrée : l'OUI ne désigne aucun constructeur")
    # 7. Genre par défaut d'un constructeur réseau sans autre indice
    if out["kind"] == "inconnu" and out["vendor"]:
        vcat = oui.get("category") if oui.get("vendor") == out["vendor"] else (pen[2] if pen else None)
        if vcat == "reseau" or (parsed and parsed.get("vendor")):
            out["kind"] = "switch" if re.search(r"switch|catalyst|procurve|baystack|superstack", (out["model"] or "") + " " + (out["os"] or ""), re.I) else "équipement réseau"
    # 8. Génération
    gen, reason = generation_of({"vendor": out["vendor"], "model": out["model"], "family": parsed.get("family"),
                                 "version": out["os_version"], "os": out["os"], "generation": parsed.get("generation"),
                                 "reason": parsed.get("reason")})
    out["generation"], out["generation_reason"] = gen, reason
    # 9. Choix manuels : le dernier mot
    manual = ev.get("manual") or {}
    for k in ("vendor", "model", "kind", "generation"):
        if manual.get(k):
            out[k] = manual[k]
            if "manuel" not in out["sources"]:
                out["sources"].append("manuel")
    if manual.get("vendor") or manual.get("model"):
        score = max(score, 0.9)
    out["confidence"] = round(min(1.0, score), 2)
    return out
