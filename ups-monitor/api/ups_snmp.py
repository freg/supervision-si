# -*- coding: utf-8 -*-
"""Relevé SNMP des onduleurs, UPS-MIB RFC 1628 (livraison #434, backlog 62)
-- seconde méthode de relevé à côté de la page HTML de la carte réseau.

Ce module ne parle pas SNMP lui-même : il passe par `snmp-api`
(`POST /get`, livraison #434) pour garder une seule implémentation pysnmp
dans le projet. Il produit EXACTEMENT la forme que `ups_parser` produit
pour une page HTML (`fields` {clé: {label, value, unit, number, section,
css}}, `sections`, `summary`) : le stockage, les alertes (#433), la tuile
et Supervision SI ne voient pas la différence.

Les OID sont les objets scalaires et la première ligne des tables
d'entrée / sortie (index 1 : onduleurs monophasés) ; un OID absent est
simplement ignoré (carte qui n'implémente qu'une partie de la MIB).
"""
import json
import logging
import urllib.error
import urllib.request

_log = logging.getLogger("ups_monitor_snmp")

UPS_MIB = "1.3.6.1.2.1.33.1"
# (clé de champ, OID, libellé, section, unité, facteur d'échelle, table de traduction)
OIDS = [
    ("manufacturer", UPS_MIB + ".1.1.0", "Manufacturer", "UPS Identification", None, None, None),
    ("model", UPS_MIB + ".1.2.0", "Model", "UPS Identification", None, None, None),
    ("firmware", UPS_MIB + ".1.3.0", "UPS Software Version", "UPS Identification", None, None, None),
    ("battery", UPS_MIB + ".2.1.0", "Battery", "UPS Status", None, None, {"1": "Unknown", "2": "Normal", "3": "Low", "4": "Depleted"}),
    ("seconds_on_battery", UPS_MIB + ".2.2.0", "Seconds On Battery", "Battery", "s", 1, None),
    ("battery_runtime", UPS_MIB + ".2.3.0", "Estimated Minutes Remaining", "Battery", "min", 1, None),
    ("battery_capacity", UPS_MIB + ".2.4.0", "Battery Capacity", "Battery", "%", 1, None),
    ("battery_voltage", UPS_MIB + ".2.5.0", "Battery Voltage", "Battery", "V", 0.1, None),
    ("battery_current", UPS_MIB + ".2.6.0", "Battery Current", "Battery", "A", 0.1, None),
    ("temperature", UPS_MIB + ".2.7.0", "Battery Temperature", "Battery", "°C", 1, None),
    ("input_line_bads", UPS_MIB + ".3.1.0", "Input Line Bads", "Input", None, 1, None),
    ("input_frequency", UPS_MIB + ".3.3.1.2.1", "Input Frequency", "Input", "Hz", 0.1, None),
    ("input_voltage", UPS_MIB + ".3.3.1.3.1", "Input Voltage", "Input", "V", 1, None),
    ("output_source", UPS_MIB + ".4.1.0", "Output Source", "UPS Status", None, None,
     {"1": "Other", "2": "None", "3": "Normal", "4": "Bypass", "5": "Battery", "6": "Booster", "7": "Reducer"}),
    ("output_frequency", UPS_MIB + ".4.2.0", "Output Frequency", "Output", "Hz", 0.1, None),
    ("output_voltage", UPS_MIB + ".4.4.1.2.1", "Output Voltage", "Output", "V", 1, None),
    ("output_current", UPS_MIB + ".4.4.1.3.1", "Output Current", "Output", "A", 0.1, None),
    ("output_power", UPS_MIB + ".4.4.1.4.1", "Output Power", "Output", "W", 1, None),
    ("output_load", UPS_MIB + ".4.4.1.5.1", "Output Loading", "Output", "%", 1, None),
    ("alarms_present", UPS_MIB + ".6.1.0", "Alarms Present", "UPS Status", None, 1, None),
]
# Statut d'alarme : upsAlarmsPresent > 0 = alarme, exposé comme un champ
# d'état que derive_state (ups_parser.STATE_FIELDS) comprend.
ALARM_FIELD = ("alarms", "Alarms", "UPS Status")


def parse_values(values):
    """{oid: texte | None} -> (fields, sections) au format ups_parser."""
    fields, sections = {}, []
    by_section = {}
    for key, oid, label, section, unit, scale, table in OIDS:
        raw = values.get(oid)
        if raw is None or raw == "":
            continue
        raw = str(raw).strip()
        number, value = None, raw
        if table is not None:
            value = table.get(raw, raw)
        elif scale is not None:
            try:
                number = round(float(raw) * scale, 1 if scale != 1 else 0)
                if scale == 1:
                    number = int(number)
                value = ("%s %s" % (number, unit)) if unit else str(number)
            except ValueError:
                number = None
        css = "normal"
        if key == "battery" and value != "Normal":
            css = "alarm"
        if key == "output_source" and value != "Normal":
            css = "alarm"
        fields[key] = {"key": key, "label": label, "value": value, "unit": unit, "number": number, "section": section, "css": css}
        by_section.setdefault(section, []).append(key)
    if "alarms_present" in fields:
        n = fields["alarms_present"]["number"] or 0
        fields["alarms"] = {"key": "alarms", "label": ALARM_FIELD[1], "value": "None" if n == 0 else "%d alarm(s)" % n, "unit": None,
                            "number": n, "section": ALARM_FIELD[2], "css": "normal" if n == 0 else "alarm"}
        by_section.setdefault(ALARM_FIELD[2], []).append("alarms")
    for section, keys in by_section.items():
        sections.append({"title": section, "keys": keys})
    return fields, sections


def snmp_state_fields():
    """Champs d'état de l'UPS-MIB compris par derive_state : `battery`
    (Normal), `output_source` (Normal) sont déjà dans STATE_FIELDS ;
    `alarms` s'y ajoute (None = normal)."""
    return {"alarms": ("none",)}


def build_getter(snmp_api_url, timeout=8):
    """Fonction (host, community, port) -> {oid: texte | None} via snmp-api."""
    def getter(host, community, port=161, snmp_timeout=5):
        payload = json.dumps({"host": host, "community": community, "port": port, "timeout": snmp_timeout, "oids": [o for _, o, *_ in OIDS]}).encode("utf-8")
        req = urllib.request.Request(snmp_api_url.rstrip("/") + "/get", data=payload, method="POST", headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            try:
                msg = json.loads(exc.read().decode("utf-8")).get("error")
            except Exception:  # noqa: BLE001
                msg = None
            raise RuntimeError("snmp-api : %s" % (msg or "HTTP %s" % exc.code))
        except (urllib.error.URLError, OSError, ValueError) as exc:
            raise RuntimeError("snmp-api injoignable : %s" % exc)
        return data.get("values") or {}
    return getter


def poll_snmp(device, getter):
    """Un relevé SNMP : (parsed | None, erreur). `parsed` = {fields,
    sections, system_time: None, flavor: "snmp"}."""
    try:
        values = getter(device["host"], device.get("snmp_community") or "public", int(device.get("snmp_port") or 161))
    except RuntimeError as exc:
        return None, str(exc)
    fields, sections = parse_values(values or {})
    if not fields:
        return None, "aucun objet UPS-MIB (RFC 1628) répondu : l'équipement n'implémente pas cette MIB, ou la communauté est refusée"
    return {"fields": fields, "sections": sections, "system_time": None, "flavor": "snmp"}, None
