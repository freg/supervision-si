"""
Parseur ICS minimal, sans dépendance externe — volontairement autonome
pour rester testable sans installer de librairie tierce. Gère le
sous-ensemble suffisant pour ce module : VEVENT simples.

Limite assumée : pas d'expansion des événements récurrents (RRULE) —
le DTSTART/DTEND du "maître" est pris tel quel, chaque occurrence
n'est pas générée individuellement. Fuseaux horaires non convertis :
un DTSTART se terminant par Z est traité comme UTC, sinon la valeur
est prise telle quelle (naïve), comme pour le parseur d'e-mails Zenoss.
"""
import re
from datetime import datetime, timezone


def unfold_lines(raw_text: str) -> list[str]:
    """RFC 5545 : une ligne commençant par un espace/tab est la
    continuation de la ligne précédente ("line folding")."""
    raw_text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    lines = raw_text.split("\n")
    unfolded = []
    for line in lines:
        if line.startswith(" ") or line.startswith("\t"):
            if unfolded:
                unfolded[-1] += line[1:]
            continue
        unfolded.append(line)
    return unfolded


def parse_property_line(line: str):
    """'DTSTART;TZID=Europe/Paris:20260815T090000' -> (name, params, value)"""
    if ":" not in line:
        return None, {}, None
    prop_part, value = line.split(":", 1)
    parts = prop_part.split(";")
    name = parts[0].upper()
    params = {}
    for p in parts[1:]:
        if "=" in p:
            k, v = p.split("=", 1)
            params[k.upper()] = v
    return name, params, value


def parse_ics_datetime(value: str, params: dict) -> int:
    """Convertit une valeur DTSTART/DTEND ICS en epoch UTC (secondes)."""
    value = value.strip()
    if params.get("VALUE") == "DATE" and "T" not in value:
        dt = datetime.strptime(value, "%Y%m%d").replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    if value.endswith("Z"):
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    dt = datetime.strptime(value, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def unescape_ics_text(value: str) -> str:
    return (
        value.replace("\\n", "\n").replace("\\N", "\n")
        .replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")
    )


def parse_ics(raw_text: str) -> list[dict]:
    """Renvoie une liste de dicts {uid, summary, description, start_ts, end_ts}."""
    lines = unfold_lines(raw_text)
    events = []
    current = None

    for line in lines:
        stripped = line.strip()
        if stripped == "BEGIN:VEVENT":
            current = {}
            continue
        if stripped == "END:VEVENT":
            if current is not None and current.get("uid") and current.get("start_ts") is not None:
                events.append({
                    "uid": current.get("uid"),
                    "summary": current.get("summary", ""),
                    "description": current.get("description", ""),
                    "start_ts": current.get("start_ts"),
                    "end_ts": current.get("end_ts"),
                })
            current = None
            continue
        if current is None:
            continue

        name, params, value = parse_property_line(line)
        if name is None:
            continue

        if name == "UID":
            current["uid"] = value.strip()
        elif name == "SUMMARY":
            current["summary"] = unescape_ics_text(value)
        elif name == "DESCRIPTION":
            current["description"] = unescape_ics_text(value)
        elif name == "DTSTART":
            try:
                current["start_ts"] = parse_ics_datetime(value, params)
            except ValueError:
                pass
        elif name == "DTEND":
            try:
                current["end_ts"] = parse_ics_datetime(value, params)
            except ValueError:
                pass

    return events
