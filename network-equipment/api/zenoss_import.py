# -*- coding: utf-8 -*-
"""Import de l'inventaire Zenoss 2.5 (#506) -- deux formats, comme demandé
(« les deux ») :

  1. JSON produit par `connectors/zenoss_legacy/zendmd_export_devices.py`
     (lancé dans zendmd sur le serveur Zenoss : lit la ZODB, où vivent
     les fiches matériel/OS/SNMP que la base MySQL `events` n'a pas) ;
  2. CSV « Export to CSV » de la liste des équipements de l'interface
     Zenoss (colonnes Device / IP / Device Class / Prod State, parfois
     plus) -- moins riche, la classe Zenoss sert alors d'indice de
     constructeur et de genre.

Logique pure : `parse(content, filename)` -> liste de fiches
normalisées {name, ip, device_class, production_state, hw_manufacturer,
hw_product, os_manufacturer, os_product, serial, sys_name, sys_descr,
sys_object_id, location, systems, groups, interfaces: [{mac, ips}], …}.
Jamais d'exception sur une ligne : elle est ignorée et comptée.
"""
import csv
import io
import json
import re

HEADER_SYNONYMS = {
    "name": ("device", "name", "devicename", "id", "titleorid", "hostname", "equipement", "équipement", "nom"),
    "ip": ("ip", "ipaddress", "ip address", "manageip", "adresse ip", "adresse"),
    "device_class": ("device class", "deviceclass", "class", "classe", "getdeviceclasspath", "devicerpath"),
    "production_state": ("prod state", "production state", "productionstate", "prodstate", "état de production", "etat"),
    "hw_manufacturer": ("hw manufacturer", "hardware manufacturer", "manufacturer", "constructeur", "hwmanufacturer"),
    "hw_product": ("hw product", "hardware product", "hardware", "model", "modèle", "modele", "product", "hwproduct"),
    "os_manufacturer": ("os manufacturer", "osmanufacturer"),
    "os_product": ("os product", "os", "osproduct", "operating system"),
    "serial": ("serial", "serial number", "serialnumber", "série", "serie", "numéro de série"),
    "location": ("location", "lieu", "localisation", "site"),
    "sys_descr": ("snmpdescr", "snmp descr", "sysdescr", "description"),
    "sys_object_id": ("snmpoid", "snmp oid", "sysobjectid"),
    "sys_name": ("snmpsysname", "sysname"),
    "comments": ("comments", "commentaires", "commentaire"),
}
FIELDS = tuple(HEADER_SYNONYMS.keys()) + ("systems", "groups", "interfaces", "snmp_contact", "snmp_location", "last_change", "snmp_last_collection", "zenoss_id")


def _norm_header(h):
    return re.sub(r"[\s_]+", " ", str(h or "").strip().lower())


def _map_headers(headers):
    mapping = {}
    for i, h in enumerate(headers):
        n = _norm_header(h)
        for field, syns in HEADER_SYNONYMS.items():
            if n in syns and field not in mapping:
                mapping[field] = i
                break
    return mapping


def _empty():
    return {f: None for f in FIELDS} | {"systems": [], "groups": [], "interfaces": []}


def parse_csv(text):
    """CSV (séparateur , ; ou tabulation, détecté) -> (fiches, ignorées)."""
    text = str(text or "").lstrip("﻿")
    if not text.strip():
        return [], 0
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    rows = [r for r in reader if any((c or "").strip() for c in r)]
    if not rows:
        return [], 0
    mapping = _map_headers(rows[0])
    if "name" not in mapping and "ip" not in mapping:
        return [], len(rows)
    out, skipped = [], 0
    for r in rows[1:]:
        d = _empty()
        for field, idx in mapping.items():
            if idx < len(r):
                v = (r[idx] or "").strip()
                d[field] = v or None
        if not d.get("name") and not d.get("ip"):
            skipped += 1
            continue
        if d.get("name") and not d.get("ip") and re.match(r"^\d+\.\d+\.\d+\.\d+$", d["name"]):
            d["ip"] = d["name"]
        out.append(d)
    return out, skipped


def parse_json(text):
    """JSON du script zendmd : {"devices": [...]} ou une liste. Clés
    tolérantes (les noms du script, ou les noms d'attributs Zenoss)."""
    data = json.loads(text)
    devices = data.get("devices") if isinstance(data, dict) else data
    if not isinstance(devices, list):
        return [], 0
    out, skipped = [], 0
    for item in devices:
        if not isinstance(item, dict):
            skipped += 1
            continue
        d = _empty()
        d["zenoss_id"] = item.get("id")
        d["name"] = item.get("name") or item.get("title") or item.get("id")
        d["ip"] = item.get("ip") or item.get("manageIp")
        d["device_class"] = item.get("device_class") or item.get("deviceClass") or item.get("getDeviceClassPath")
        d["production_state"] = item.get("production_state") or item.get("productionState")
        d["hw_manufacturer"] = item.get("hw_manufacturer") or item.get("hwManufacturer")
        d["hw_product"] = item.get("hw_product") or item.get("hwProduct")
        d["os_manufacturer"] = item.get("os_manufacturer") or item.get("osManufacturer")
        d["os_product"] = item.get("os_product") or item.get("osProduct")
        d["serial"] = item.get("serial") or item.get("serialNumber")
        d["sys_name"] = item.get("snmp_sys_name") or item.get("snmpSysName")
        d["sys_descr"] = item.get("snmp_descr") or item.get("snmpDescr")
        d["sys_object_id"] = item.get("snmp_oid") or item.get("snmpOid")
        d["snmp_contact"] = item.get("snmp_contact") or item.get("snmpContact")
        d["snmp_location"] = item.get("snmp_location") or item.get("snmpLocation")
        d["location"] = item.get("location") or item.get("getLocationName")
        d["systems"] = list(item.get("systems") or [])
        d["groups"] = list(item.get("groups") or [])
        d["comments"] = item.get("comments")
        d["last_change"] = item.get("last_change")
        d["snmp_last_collection"] = item.get("snmp_last_collection")
        ifaces = []
        for i in item.get("interfaces") or []:
            if not isinstance(i, dict):
                continue
            ifaces.append({"id": i.get("id"), "mac": i.get("mac") or i.get("macaddress"), "ips": list(i.get("ips") or []),
                           "speed": i.get("speed"), "oper_status": i.get("oper_status") or i.get("operStatus"), "type": i.get("type")})
        d["interfaces"] = ifaces
        if not d["name"] and not d["ip"]:
            skipped += 1
            continue
        out.append(d)
    return out, skipped


def parse(content, filename=None):
    """Détecte le format (JSON si le contenu commence par { ou [, sinon
    CSV) -> (fiches, ignorées, format)."""
    if isinstance(content, bytes):
        for enc in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
            try:
                content = content.decode(enc)
                break
            except UnicodeDecodeError:
                continue
    text = str(content or "")
    stripped = text.lstrip("﻿ \t\r\n")
    if stripped.startswith(("{", "[")) or (filename or "").lower().endswith(".json"):
        try:
            devices, skipped = parse_json(stripped)
            return devices, skipped, "json"
        except ValueError:
            if (filename or "").lower().endswith(".json"):
                return [], 0, "json"
    devices, skipped = parse_csv(text)
    return devices, skipped, "csv"


def primary_mac(device):
    """Première MAC d'interface non nulle -- la clé la plus sûre pour
    rapprocher la fiche Zenoss d'un appareil vu par l'exploration."""
    for i in device.get("interfaces") or []:
        mac = (i.get("mac") or "").strip()
        if mac and mac.upper() not in ("00:00:00:00:00:00",):
            return mac
    return None
