# -*- coding: utf-8 -*-
"""Profils de supervision génériques par constructeur (#506) -- ce qu'il
faut relever en SNMP sur un équipement une fois identifié : CPU,
mémoire, température, ventilation/alimentation, voisins (LLDP, CDP),
table des adresses MAC (switch), interfaces (IF-MIB, déjà couvert par
snmp-api `/walk-interfaces`).

Demandé : « préparer des interfaces de supervision génériques Cisco,
HP… ». Chaque profil est une DONNÉE (OID, libellé, unité, décodage des
énumérations), pas du code : ajouter un constructeur = ajouter une
entrée. Les OID viennent des MIB publiques des constructeurs
(CISCO-PROCESS-MIB, CISCO-MEMORY-POOL-MIB, CISCO-ENVMON-MIB, CISCO-CDP-MIB,
HP hpSwitch/hpicfChassis, MIKROTIK-MIB, JUNIPER-MIB, HOST-RESOURCES-MIB,
UCD-SNMP-MIB, LLDP-MIB, BRIDGE-MIB, ENTITY-MIB).

⚠️ `verified: False` partout : aucun de ces OID n'a été relevé ici sur
un équipement réel (pas de pysnmp ni de matériel dans cet environnement).
Le premier relevé réel de chaque profil le confirmera -- la tuile
affiche « non vérifié » tant que `verified` n'est pas passé à True dans
ce fichier après constat.
"""
import re

# Énumérations (valeurs normatives des MIB)
CISCO_ENVMON_STATE = {1: "normal", 2: "warning", 3: "critical", 4: "shutdown", 5: "notPresent", 6: "notFunctioning"}
HP_SENSOR_STATUS = {1: "unknown", 2: "bad", 3: "warning", 4: "good", 5: "notPresent"}
JUNIPER_OPERATING_STATE = {1: "unknown", 2: "running", 3: "ready", 4: "reset", 5: "runningAtFullSpeed", 6: "down", 7: "standby"}

# Walks communs à tous les profils
COMMON_WALKS = {
    "entity": {"oid": "1.3.6.1.2.1.47.1.1.1.1", "label": "ENTITY-MIB (châssis : modèle, série, versions)", "mib": "ENTITY-MIB",
               "columns": {"2": "descr", "5": "class", "7": "name", "8": "hw", "9": "fw", "10": "sw", "11": "serial", "12": "mfg", "13": "model"}},
    "lldp": {"oid": "1.0.8802.1.1.2.1.4.1.1", "label": "Voisins LLDP", "mib": "LLDP-MIB",
             "columns": {"5": "chassis_id", "7": "port_id", "8": "port_descr", "9": "sys_name", "10": "sys_descr"}},
    "fdb": {"oid": "1.3.6.1.2.1.17.4.3.1.2", "label": "Table des adresses MAC (dot1dTpFdbPort)", "mib": "BRIDGE-MIB"},
    "fdb_q": {"oid": "1.3.6.1.2.1.17.7.1.2.2.1.2", "label": "Table des adresses MAC par VLAN (dot1qTpFdbPort)", "mib": "Q-BRIDGE-MIB"},
    "bridge_port_ifindex": {"oid": "1.3.6.1.2.1.17.1.4.1.2", "label": "Port de pont -> ifIndex (dot1dBasePortIfIndex)", "mib": "BRIDGE-MIB"},
}

PROFILES = [
    {
        "id": "cisco-ios", "label": "Cisco IOS / IOS-XE (routeurs, Catalyst)", "verified": False,
        "match": {"vendor": r"^cisco", "os": r"^IOS"},
        "gets": {
            "cpu_5min_legacy": {"oid": "1.3.6.1.4.1.9.2.1.58.0", "label": "CPU 5 min (%) -- OLD-CISCO-CPU-MIB (IOS 11/12)", "unit": "%"},
            "cpu_1min_legacy": {"oid": "1.3.6.1.4.1.9.2.1.57.0", "label": "CPU 1 min (%) -- OLD-CISCO-CPU-MIB", "unit": "%"},
        },
        "walks": {
            "cpu_5min": {"oid": "1.3.6.1.4.1.9.9.109.1.1.1.1.8", "label": "CPU 5 min par processeur (%) -- cpmCPUTotal5minRev", "unit": "%"},
            "mem_used": {"oid": "1.3.6.1.4.1.9.9.48.1.1.1.5", "label": "Mémoire utilisée par pool (octets) -- ciscoMemoryPoolUsed", "unit": "o"},
            "mem_free": {"oid": "1.3.6.1.4.1.9.9.48.1.1.1.6", "label": "Mémoire libre par pool (octets) -- ciscoMemoryPoolFree", "unit": "o"},
            "mem_name": {"oid": "1.3.6.1.4.1.9.9.48.1.1.1.2", "label": "Nom des pools mémoire"},
            "temp_value": {"oid": "1.3.6.1.4.1.9.9.13.1.3.1.3", "label": "Température (°C) -- ciscoEnvMonTemperatureStatusValue", "unit": "°C"},
            "temp_state": {"oid": "1.3.6.1.4.1.9.9.13.1.3.1.6", "label": "État température", "enum": CISCO_ENVMON_STATE},
            "fan_state": {"oid": "1.3.6.1.4.1.9.9.13.1.4.1.3", "label": "État ventilateurs -- ciscoEnvMonFanState", "enum": CISCO_ENVMON_STATE},
            "psu_state": {"oid": "1.3.6.1.4.1.9.9.13.1.5.1.3", "label": "État alimentations -- ciscoEnvMonSupplyState", "enum": CISCO_ENVMON_STATE},
            "cdp": {"oid": "1.3.6.1.4.1.9.9.23.1.2.1.1", "label": "Voisins CDP", "mib": "CISCO-CDP-MIB",
                    "columns": {"4": "address", "6": "device_id", "7": "device_port", "8": "platform"}},
        },
        "notes": ["Les IOS 11.x/12.x anciens n'ont souvent que OLD-CISCO-CPU-MIB (avgBusy5) et pas CISCO-PROCESS-MIB : les deux sont relevés.",
                  "CDP est le mécanisme de voisinage natif ; LLDP est désactivé par défaut sur les Catalyst anciens."],
    },
    {
        "id": "cisco-catos", "label": "Cisco CatOS (Catalyst 1ère génération)", "verified": False,
        "match": {"vendor": r"^cisco", "os": r"^CatOS"},
        "gets": {},
        "walks": {
            "cdp": {"oid": "1.3.6.1.4.1.9.9.23.1.2.1.1", "label": "Voisins CDP", "mib": "CISCO-CDP-MIB",
                    "columns": {"4": "address", "6": "device_id", "7": "device_port", "8": "platform"}},
            "temp_state": {"oid": "1.3.6.1.4.1.9.9.13.1.3.1.6", "label": "État température (si CISCO-ENVMON-MIB)", "enum": CISCO_ENVMON_STATE},
        },
        "notes": ["CatOS expose surtout IF-MIB, BRIDGE-MIB et CDP ; pas de CPU/mémoire standardisés -- surveiller disponibilité et interfaces."],
    },
    {
        "id": "hp-procurve", "label": "HP ProCurve / Aruba (ArubaOS-Switch)", "verified": False,
        "match": {"vendor": r"procurve|^aruba"},
        "gets": {
            "cpu": {"oid": "1.3.6.1.4.1.11.2.14.11.5.1.9.6.1.0", "label": "CPU (%) -- hpSwitchCpuStat", "unit": "%"},
            "mem_total": {"oid": "1.3.6.1.4.1.11.2.14.11.5.1.1.2.1.1.1.5.1", "label": "Mémoire totale (octets) -- hpLocalMemTotalBytes", "unit": "o"},
            "mem_free": {"oid": "1.3.6.1.4.1.11.2.14.11.5.1.1.2.1.1.1.6.1", "label": "Mémoire libre (octets) -- hpLocalMemFreeBytes", "unit": "o"},
        },
        "walks": {
            "sensor_status": {"oid": "1.3.6.1.4.1.11.2.14.11.1.2.6.1.4", "label": "État des capteurs (ventilateur, alimentation, température) -- hpicfSensorStatus", "enum": HP_SENSOR_STATUS},
            "sensor_descr": {"oid": "1.3.6.1.4.1.11.2.14.11.1.2.6.1.7", "label": "Description des capteurs -- hpicfSensorDescr"},
        },
        "notes": ["Les ProCurve anciens (révisions à une lettre, ex. F.05.x) n'ont pas tous hpicfSensor : l'absence n'est pas une panne.",
                  "LLDP est actif par défaut sur ProCurve ; CDP en lecture seule."],
    },
    {
        "id": "hp-comware", "label": "HP / H3C Comware", "verified": False,
        "match": {"os": r"^Comware", "vendor": r"comware|h3c"},
        "gets": {},
        "walks": {
            "cpu": {"oid": "1.3.6.1.4.1.25506.2.6.1.1.1.1.6", "label": "CPU par entité (%) -- hh3cEntityExtCpuUsage", "unit": "%"},
            "mem": {"oid": "1.3.6.1.4.1.25506.2.6.1.1.1.1.8", "label": "Mémoire par entité (%) -- hh3cEntityExtMemUsage", "unit": "%"},
            "temp": {"oid": "1.3.6.1.4.1.25506.2.6.1.1.1.1.12", "label": "Température par entité (°C) -- hh3cEntityExtTemperature", "unit": "°C"},
        },
        "notes": [],
    },
    {
        "id": "mikrotik", "label": "MikroTik RouterOS", "verified": False,
        "match": {"vendor": r"^mikrotik", "os": r"RouterOS"},
        "gets": {
            "version": {"oid": "1.3.6.1.4.1.14988.1.1.4.4.0", "label": "Version RouterOS -- mtxrLicVersion"},
            "serial": {"oid": "1.3.6.1.4.1.14988.1.1.7.3.0", "label": "Numéro de série -- mtxrSerialNumber"},
            "firmware": {"oid": "1.3.6.1.4.1.14988.1.1.7.4.0", "label": "Firmware RouterBOOT -- mtxrFirmwareVersion"},
            "temp_board": {"oid": "1.3.6.1.4.1.14988.1.1.3.10.0", "label": "Température carte (0,1 °C) -- mtxrHlTemperature", "unit": "0.1°C"},
            "temp_cpu": {"oid": "1.3.6.1.4.1.14988.1.1.3.11.0", "label": "Température CPU (0,1 °C) -- mtxrHlProcessorTemperature", "unit": "0.1°C"},
            "voltage": {"oid": "1.3.6.1.4.1.14988.1.1.3.8.0", "label": "Tension (0,1 V) -- mtxrHlVoltage", "unit": "0.1V"},
        },
        "walks": {
            "cpu": {"oid": "1.3.6.1.2.1.25.3.3.1.2", "label": "Charge par processeur (%) -- hrProcessorLoad", "unit": "%"},
            "storage_descr": {"oid": "1.3.6.1.2.1.25.2.3.1.3", "label": "Stockage/mémoire : description -- hrStorageDescr"},
            "storage_size": {"oid": "1.3.6.1.2.1.25.2.3.1.5", "label": "Stockage/mémoire : taille (unités) -- hrStorageSize"},
            "storage_used": {"oid": "1.3.6.1.2.1.25.2.3.1.6", "label": "Stockage/mémoire : utilisé (unités) -- hrStorageUsed"},
        },
        "notes": ["Le hub a aussi la tuile « Routeurs MikroTik » (API REST RouterOS, #485) : ce profil SNMP est le relevé générique, la tuile va plus loin.",
                  "Les capteurs (température, tension) n'existent que sur les cartes qui en ont : valeur absente = non équipé."],
    },
    {
        "id": "juniper", "label": "Juniper Junos", "verified": False,
        "match": {"vendor": r"^juniper"},
        "gets": {},
        "walks": {
            "descr": {"oid": "1.3.6.1.4.1.2636.3.1.13.1.5", "label": "Composants -- jnxOperatingDescr"},
            "cpu": {"oid": "1.3.6.1.4.1.2636.3.1.13.1.8", "label": "CPU par composant (%) -- jnxOperatingCPU", "unit": "%"},
            "temp": {"oid": "1.3.6.1.4.1.2636.3.1.13.1.7", "label": "Température par composant (°C) -- jnxOperatingTemp", "unit": "°C"},
            "mem": {"oid": "1.3.6.1.4.1.2636.3.1.13.1.11", "label": "Mémoire par composant (%) -- jnxOperatingBuffer", "unit": "%"},
            "state": {"oid": "1.3.6.1.4.1.2636.3.1.13.1.6", "label": "État par composant -- jnxOperatingState", "enum": JUNIPER_OPERATING_STATE},
        },
        "notes": [],
    },
    {
        "id": "generic-host", "label": "Hôte net-snmp / HOST-RESOURCES (Linux, BSD, appliances)", "verified": False,
        "match": {"os": r"^(Linux|FreeBSD|OpenBSD|NetBSD)", "vendor": r"net-snmp|ucd"},
        "gets": {
            "load1": {"oid": "1.3.6.1.4.1.2021.10.1.3.1", "label": "Charge 1 min -- laLoad.1"},
            "load5": {"oid": "1.3.6.1.4.1.2021.10.1.3.2", "label": "Charge 5 min -- laLoad.2"},
            "mem_total": {"oid": "1.3.6.1.4.1.2021.4.5.0", "label": "Mémoire totale (Ko) -- memTotalReal", "unit": "Ko"},
            "mem_avail": {"oid": "1.3.6.1.4.1.2021.4.6.0", "label": "Mémoire disponible (Ko) -- memAvailReal", "unit": "Ko"},
        },
        "walks": {
            "cpu": {"oid": "1.3.6.1.2.1.25.3.3.1.2", "label": "Charge par processeur (%) -- hrProcessorLoad", "unit": "%"},
            "storage_descr": {"oid": "1.3.6.1.2.1.25.2.3.1.3", "label": "Stockage : description -- hrStorageDescr"},
            "storage_size": {"oid": "1.3.6.1.2.1.25.2.3.1.5", "label": "Stockage : taille -- hrStorageSize"},
            "storage_used": {"oid": "1.3.6.1.2.1.25.2.3.1.6", "label": "Stockage : utilisé -- hrStorageUsed"},
        },
        "notes": [],
    },
    {
        "id": "generic-bridge", "label": "Switch / routeur générique (IF-MIB, BRIDGE-MIB, LLDP, ENTITY-MIB)", "verified": False,
        "match": {"kind": r"switch|routeur|équipement réseau|point d'accès|pare-feu"},
        "gets": {},
        "walks": {
            "cpu_hr": {"oid": "1.3.6.1.2.1.25.3.3.1.2", "label": "Charge par processeur (%) si HOST-RESOURCES -- hrProcessorLoad", "unit": "%"},
        },
        "notes": ["Constructeur sans profil dédié (3Com, Nortel, Netgear, D-Link, Zyxel, Alcatel…) : interfaces, table MAC, voisins LLDP et châssis ENTITY-MIB sont les relevés universels ; CPU/température demandent la MIB propriétaire -- à ajouter ici au premier besoin."],
    },
    {
        "id": "generic-snmp", "label": "SNMP générique (système et interfaces)", "verified": False,
        "match": {},
        "gets": {},
        "walks": {},
        "notes": ["Rien de plus que SNMPv2-MIB system et IF-MIB."],
    },
]


def _rx(pattern, value):
    return bool(pattern) and bool(re.search(pattern, value or "", re.I))


def match_profile(ident):
    """Choisit le profil d'après l'identification (vendor, os, kind) :
    le premier profil dont TOUTES les conditions présentes sont vraies
    (`vendor` OU `os` suffit quand les deux sont listés : l'un confirme
    l'autre), sinon le générique du genre, sinon generic-snmp."""
    ident = ident or {}
    vendor, os_name, kind = ident.get("vendor") or "", ident.get("os") or "", ident.get("kind") or ""
    for p in PROFILES:
        m = p["match"]
        if not m:
            continue
        if "kind" in m and not ("vendor" in m or "os" in m):
            if _rx(m["kind"], kind):
                return p
            continue
        ok_vendor = _rx(m.get("vendor"), vendor)
        ok_os = _rx(m.get("os"), os_name)
        if p["id"] in ("cisco-ios", "cisco-catos"):
            if ok_vendor and ok_os:
                return p
            continue
        if ok_vendor or ok_os:
            return p
    return PROFILES[-1]


def profile_by_id(profile_id):
    for p in PROFILES:
        if p["id"] == profile_id:
            return p
    return None


def profile_summary(p):
    return {"id": p["id"], "label": p["label"], "verified": p["verified"], "notes": p["notes"],
            "gets": {k: {"oid": v["oid"], "label": v["label"], "unit": v.get("unit")} for k, v in p["gets"].items()},
            "walks": {k: {"oid": v["oid"], "label": v["label"], "unit": v.get("unit")} for k, v in p["walks"].items()},
            "common": {k: {"oid": v["oid"], "label": v["label"]} for k, v in COMMON_WALKS.items()}}


def decode_value(spec, raw):
    """Valeur brute (texte prettyPrint) -> valeur lisible : énumération
    décodée, unités en dixièmes converties, entiers typés."""
    if raw is None:
        return None
    text = str(raw).strip()
    enum = spec.get("enum")
    if enum:
        try:
            return enum.get(int(text), text)
        except ValueError:
            return text
    unit = spec.get("unit")
    if unit in ("0.1°C", "0.1V"):
        try:
            return round(int(text) / 10.0, 1)
        except ValueError:
            return text
    try:
        return int(text)
    except ValueError:
        return text


def interpret(profile, gets, walks):
    """Synthèse lisible d'un relevé : {cpu_percent, memory_percent,
    temperature_c, alarms: [..], neighbors: [...]} -- calcul pur,
    tolérant aux absences (un équipement qui n'a pas la MIB n'est pas
    en panne)."""
    out = {"cpu_percent": None, "memory_percent": None, "temperature_c": None, "alarms": [], "components": []}
    gets = gets or {}
    walks = walks or {}

    def first_int(*keys):
        for k in keys:
            v = gets.get(k)
            if isinstance(v, (int, float)):
                return v
            rows = walks.get(k) or []
            for r in rows:
                if isinstance(r.get("value"), (int, float)):
                    return r["value"]
        return None

    pid = profile["id"]
    if pid == "cisco-ios":
        out["cpu_percent"] = first_int("cpu_5min", "cpu_5min_legacy")
        used = [r["value"] for r in walks.get("mem_used") or [] if isinstance(r.get("value"), int)]
        free = [r["value"] for r in walks.get("mem_free") or [] if isinstance(r.get("value"), int)]
        if used and free and sum(used) + sum(free) > 0:
            out["memory_percent"] = round(100.0 * sum(used) / (sum(used) + sum(free)), 1)
        temps = [r["value"] for r in walks.get("temp_value") or [] if isinstance(r.get("value"), int)]
        if temps:
            out["temperature_c"] = max(temps)
        for key, label in (("temp_state", "température"), ("fan_state", "ventilateur"), ("psu_state", "alimentation")):
            for r in walks.get(key) or []:
                if r.get("value") in ("warning", "critical", "shutdown", "notFunctioning"):
                    out["alarms"].append("%s %s : %s" % (label, r.get("index", ""), r["value"]))
    elif pid in ("hp-procurve",):
        out["cpu_percent"] = first_int("cpu")
        total, free = gets.get("mem_total"), gets.get("mem_free")
        if isinstance(total, int) and isinstance(free, int) and total > 0:
            out["memory_percent"] = round(100.0 * (total - free) / total, 1)
        descr = {r.get("index"): r.get("value") for r in walks.get("sensor_descr") or []}
        for r in walks.get("sensor_status") or []:
            out["components"].append({"name": descr.get(r.get("index"), "capteur %s" % r.get("index")), "state": r.get("value")})
            if r.get("value") in ("bad", "warning"):
                out["alarms"].append("%s : %s" % (descr.get(r.get("index"), "capteur"), r["value"]))
    elif pid == "mikrotik":
        loads = [r["value"] for r in walks.get("cpu") or [] if isinstance(r.get("value"), int)]
        if loads:
            out["cpu_percent"] = round(sum(loads) / len(loads), 1)
        out["temperature_c"] = gets.get("temp_cpu") if isinstance(gets.get("temp_cpu"), (int, float)) else gets.get("temp_board")
        out["memory_percent"] = _hr_memory_percent(walks)
    elif pid in ("generic-host", "generic-bridge"):
        loads = [r["value"] for r in walks.get("cpu") or walks.get("cpu_hr") or [] if isinstance(r.get("value"), int)]
        if loads:
            out["cpu_percent"] = round(sum(loads) / len(loads), 1)
        total, avail = gets.get("mem_total"), gets.get("mem_avail")
        if isinstance(total, int) and isinstance(avail, int) and total > 0:
            out["memory_percent"] = round(100.0 * (total - avail) / total, 1)
        else:
            out["memory_percent"] = _hr_memory_percent(walks)
    elif pid == "juniper":
        cpus = [r["value"] for r in walks.get("cpu") or [] if isinstance(r.get("value"), int)]
        if cpus:
            out["cpu_percent"] = max(cpus)
        temps = [r["value"] for r in walks.get("temp") or [] if isinstance(r.get("value"), int) and r["value"] > 0]
        if temps:
            out["temperature_c"] = max(temps)
        descr = {r.get("index"): r.get("value") for r in walks.get("descr") or []}
        for r in walks.get("state") or []:
            if r.get("value") in ("down", "reset"):
                out["alarms"].append("%s : %s" % (descr.get(r.get("index"), "composant"), r["value"]))
    elif pid == "hp-comware":
        cpus = [r["value"] for r in walks.get("cpu") or [] if isinstance(r.get("value"), int)]
        if cpus:
            out["cpu_percent"] = max(cpus)
        mems = [r["value"] for r in walks.get("mem") or [] if isinstance(r.get("value"), int)]
        if mems:
            out["memory_percent"] = max(mems)
        temps = [r["value"] for r in walks.get("temp") or [] if isinstance(r.get("value"), int) and r["value"] > 0]
        if temps:
            out["temperature_c"] = max(temps)
    return out


def _hr_memory_percent(walks):
    """HOST-RESOURCES : la ligne hrStorage dont la description contient
    « memory »/« RAM » (RouterOS : « main memory »)."""
    descr = {r.get("index"): str(r.get("value") or "") for r in walks.get("storage_descr") or []}
    size = {r.get("index"): r.get("value") for r in walks.get("storage_size") or []}
    used = {r.get("index"): r.get("value") for r in walks.get("storage_used") or []}
    for idx, d in descr.items():
        if re.search(r"memory|ram\b", d, re.I) and not re.search(r"swap|virtual", d, re.I):
            s, u = size.get(idx), used.get(idx)
            if isinstance(s, int) and isinstance(u, int) and s > 0:
                return round(100.0 * u / s, 1)
    return None
