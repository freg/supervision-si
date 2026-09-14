# -*- coding: utf-8 -*-
# Export de l'inventaire matériel Zenoss 2.5 (livraison #506) -- a lancer
# DANS zendmd sur le serveur Zenoss, jamais depuis le hub : les fiches
# constructeur / modele / OS / SNMP / numero de serie vivent dans la
# ZODB (objets Device), pas dans la base MySQL "events" que lit
# zenoss-api. Sortie : un fichier JSON a importer dans la facette
# "Equipements reseau" du hub (POST /import/zenoss, ou le bouton
# "Importer Zenoss" de la tuile).
#
# Python 2.4 (Zenoss 2.5) : pas de `with`, pas de `a if b else c`, pas
# de module json (2.6) -- un encodeur JSON minimal est inclus. Rien
# n'est modifie dans Zenoss (lecture seule, aucun commit).
#
# Utilisation (en tant qu'utilisateur zenoss) :
#   zendmd --script=/chemin/zendmd_export_devices.py
# ou, dans un zendmd interactif :
#   execfile('/chemin/zendmd_export_devices.py')
# Le fichier est ecrit dans /tmp/zenoss-devices.json (variable OUTPUT
# ci-dessous). Rapatrier le fichier (scp), puis l'importer dans le hub.
#
# Aucune valeur secrete n'est exportee : la communaute SNMP
# (zSnmpCommunity) est VOLONTAIREMENT omise.

import time

OUTPUT = "/tmp/zenoss-devices.json"


def _esc(s):
    out = []
    for ch in s:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ch == "\n":
            out.append("\\n")
        elif ch == "\r":
            out.append("\\r")
        elif ch == "\t":
            out.append("\\t")
        elif ord(ch) < 32:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    return "".join(out)


def to_json(obj):
    """Encodeur JSON minimal (dict, list, str/unicode, int, float, bool, None)."""
    if obj is None:
        return "null"
    if obj is True:
        return "true"
    if obj is False:
        return "false"
    if isinstance(obj, (int, long, float)):
        return str(obj)
    if isinstance(obj, unicode):
        return '"' + _esc(obj).encode("utf-8") + '"'
    if isinstance(obj, str):
        try:
            u = obj.decode("utf-8")
        except UnicodeDecodeError:
            u = obj.decode("latin-1")
        return '"' + _esc(u).encode("utf-8") + '"'
    if isinstance(obj, dict):
        items = []
        keys = obj.keys()
        keys.sort()
        for k in keys:
            items.append(to_json(str(k)) + ": " + to_json(obj[k]))
        return "{" + ", ".join(items) + "}"
    if isinstance(obj, (list, tuple)):
        return "[" + ", ".join([to_json(x) for x in obj]) + "]"
    return to_json(str(obj))


def safe(fn, default=None):
    try:
        v = fn()
        if v is None:
            return default
        return v
    except Exception:
        return default


def text(v):
    if v is None:
        return None
    try:
        return str(v)
    except Exception:
        return None


def export_device(d):
    hw = safe(lambda: d.hw)
    os_ = safe(lambda: d.os)
    item = {
        "id": text(safe(lambda: d.id)),
        "name": text(safe(lambda: d.titleOrId(), safe(lambda: d.id))),
        "ip": text(safe(lambda: d.manageIp)),
        "device_class": text(safe(lambda: d.getDeviceClassPath())),
        "production_state": text(safe(lambda: d.getProductionStateString())),
        "hw_manufacturer": text(safe(lambda: hw.getManufacturerName())),
        "hw_product": text(safe(lambda: hw.getProductName())),
        "serial": text(safe(lambda: hw.serialNumber)),
        "os_manufacturer": text(safe(lambda: os_.getManufacturerName())),
        "os_product": text(safe(lambda: os_.getProductName())),
        "snmp_sys_name": text(safe(lambda: d.snmpSysName)),
        "snmp_descr": text(safe(lambda: d.snmpDescr)),
        "snmp_oid": text(safe(lambda: d.snmpOid)),
        "snmp_contact": text(safe(lambda: d.snmpContact)),
        "snmp_location": text(safe(lambda: d.snmpLocation)),
        "location": text(safe(lambda: d.getLocationName())),
        "systems": [text(x) for x in safe(lambda: d.getSystemNames(), [])],
        "groups": [text(x) for x in safe(lambda: d.getDeviceGroupNames(), [])],
        "comments": text(safe(lambda: d.comments)),
        "last_change": text(safe(lambda: d.getLastChangeString())),
        "snmp_last_collection": text(safe(lambda: d.getSnmpLastCollectionString())),
        "interfaces": [],
    }
    for i in safe(lambda: list(os_.interfaces()), []):
        ips = []
        for a in safe(lambda: i.getIpAddresses(), []):
            ips.append(text(a))
        item["interfaces"].append({
            "id": text(safe(lambda: i.id)),
            "mac": text(safe(lambda: i.macaddress)),
            "ips": ips,
            "speed": safe(lambda: int(i.speed)),
            "oper_status": text(safe(lambda: i.getOperStatusString())),
            "type": text(safe(lambda: i.type)),
        })
    return item


def main():
    devices = []
    errors = 0
    for d in dmd.Devices.getSubDevices():
        try:
            devices.append(export_device(d))
        except Exception:
            errors += 1
    doc = {
        "exported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "zenoss_version": text(safe(lambda: dmd.About.getZenossVersionShort())),
        "count": len(devices),
        "errors": errors,
        "devices": devices,
    }
    fh = open(OUTPUT, "w")
    try:
        fh.write(to_json(doc))
        fh.write("\n")
    finally:
        fh.close()
    print "%d equipement(s) exporte(s) (%d en erreur) -> %s" % (len(devices), errors, OUTPUT)


main()
