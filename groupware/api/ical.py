# -*- coding: utf-8 -*-
"""iCalendar (livraison #666) : VEVENT <-> dict, développement des récurrences sur une fenêtre, disponibilités, conflits.
Bibliothèques : icalendar (analyse / sérialisation) et dateutil (RRULE). Dates en ISO 8601 ; les événements « journée entière »
portent des dates sans heure (all_day = true). Fuseau : celui des dates reçues (par défaut TZ, env, ou UTC)."""
import os, re, uuid
from datetime import datetime, date, timedelta, timezone
from zoneinfo import ZoneInfo
from icalendar import Calendar, Event, vRecur
from dateutil.rrule import rrulestr
from dateutil import parser as dtparser

TZ = ZoneInfo(os.environ.get("TZ", "Europe/Paris"))
FREQ = ("DAILY", "WEEKLY", "MONTHLY", "YEARLY")


def _aware(d):
    if isinstance(d, datetime):
        return d if d.tzinfo else d.replace(tzinfo=TZ)
    return d


def parse_dt(s, all_day=False):
    """'2026-10-03' | '2026-10-03T14:00' | '…+02:00' -> date (all_day) ou datetime conscient."""
    if isinstance(s, (datetime, date)):
        return s if not isinstance(s, datetime) or not all_day else s.date()
    if all_day or re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(s)):
        return date.fromisoformat(str(s)[:10])
    return _aware(dtparser.isoparse(str(s)))


def iso(d):
    if isinstance(d, datetime):
        return d.isoformat(timespec="minutes")
    return d.isoformat()


def validate(body):
    """Corps d'événement {title, start, end, all_day, location, description, categories, rrule: {freq, interval, until, count, byday}} -> (dict normalisé, erreur)."""
    b = body or {}
    title = str(b.get("title") or "").strip()
    if not title:
        return None, "title requis"
    all_day = bool(b.get("all_day"))
    try:
        start = parse_dt(b.get("start"), all_day)
        end = parse_dt(b.get("end"), all_day) if b.get("end") else (start + timedelta(days=1) if all_day else start + timedelta(hours=1))
    except (ValueError, TypeError, AttributeError) as e:
        return None, "start / end : dates ISO (%s)" % e
    if all_day and isinstance(end, date) and end <= start:
        end = start + timedelta(days=1)
    if not all_day and end <= start:
        return None, "end doit suivre start"
    rr = b.get("rrule") or None
    rrule = None
    if rr:
        freq = str(rr.get("freq") or "").upper()
        if freq not in FREQ:
            return None, "rrule.freq : " + ", ".join(FREQ)
        rrule = {"FREQ": freq, "INTERVAL": max(1, int(rr.get("interval") or 1))}
        if rr.get("until"):
            u = parse_dt(rr["until"], all_day)
            rrule["UNTIL"] = u if all_day else u.astimezone(timezone.utc)
        if rr.get("count"):
            rrule["COUNT"] = int(rr["count"])
        if rr.get("byday"):
            days = [d.strip().upper() for d in str(rr["byday"]).split(",") if d.strip()]
            if not all(d in ("MO", "TU", "WE", "TH", "FR", "SA", "SU") for d in days):
                return None, "rrule.byday : MO,TU,…"
            rrule["BYDAY"] = days
    return {"uid": str(b.get("uid") or ""), "title": title[:200], "start": start, "end": end, "all_day": all_day, "location": str(b.get("location") or "")[:200],
            "description": str(b.get("description") or "")[:4000], "categories": [str(c).strip() for c in (b.get("categories") or []) if str(c).strip()], "rrule": rrule,
            "transparent": bool(b.get("transparent"))}, None


def serialize(ev, uid=None):
    cal = Calendar(); cal.add("prodid", "-//supervision-si//groupware//FR"); cal.add("version", "2.0")
    e = Event(); e.add("uid", uid or ev.get("uid") or str(uuid.uuid4())); e.add("summary", ev["title"])
    e.add("dtstart", ev["start"]); e.add("dtend", ev["end"]); e.add("dtstamp", datetime.now(timezone.utc))
    if ev.get("location"): e.add("location", ev["location"])
    if ev.get("description"): e.add("description", ev["description"])
    if ev.get("categories"): e.add("categories", ev["categories"])
    if ev.get("transparent"): e.add("transp", "TRANSPARENT")
    if ev.get("rrule"): e.add("rrule", vRecur(ev["rrule"]))
    for line in ev.get("extra") or []:
        try:
            k, v = line.split(":", 1); e.add(k.split(";")[0].lower(), v)
        except ValueError:
            pass
    cal.add_component(e)
    return cal.to_ical().decode("utf-8")


def parse(text):
    """Texte iCalendar -> dict (premier VEVENT) ; `rrule_text` conservé tel quel pour le développement, `extra` = propriétés X-."""
    cal = Calendar.from_ical(text)
    for comp in cal.walk("VEVENT"):
        ds, de = comp.get("dtstart"), comp.get("dtend")
        start = ds.dt if ds else None
        all_day = isinstance(start, date) and not isinstance(start, datetime)
        end = de.dt if de else (start + timedelta(days=1) if all_day else start + timedelta(hours=1))
        if "duration" in comp and not de:
            end = start + comp["duration"].dt
        rr = comp.get("rrule")
        cats = comp.get("categories")
        if cats is not None and not isinstance(cats, list):
            cats = [cats]
        categories = []
        for c in cats or []:
            categories += [str(x) for x in (c.cats if hasattr(c, "cats") else [c])]
        return {"uid": str(comp.get("uid") or ""), "title": str(comp.get("summary") or ""), "start": _aware(start), "end": _aware(end), "all_day": all_day,
                "location": str(comp.get("location") or ""), "description": str(comp.get("description") or ""), "categories": categories,
                "rrule": dict(rr) if rr else None, "rrule_text": rr.to_ical().decode() if rr else "", "transparent": str(comp.get("transp") or "").upper() == "TRANSPARENT",
                "extra": ["%s:%s" % (k, comp[k].to_ical().decode() if hasattr(comp[k], "to_ical") else comp[k]) for k in comp.keys() if k.upper().startswith("X-")]}
    return None


def occurrences(ev, win_start, win_end, limit=500):
    """Instances d'un événement (récurrent ou non) chevauchant [win_start, win_end[ -> [(start, end)]."""
    start, end = ev["start"], ev["end"]
    dur = end - start
    ws, we = parse_dt(win_start, ev["all_day"]), parse_dt(win_end, ev["all_day"])
    if not ev.get("rrule_text") and not ev.get("rrule"):
        return [(start, end)] if start < we and end > ws else []
    rtext = ev.get("rrule_text") or vRecur(ev["rrule"]).to_ical().decode()
    dtstart = start if isinstance(start, datetime) else datetime(start.year, start.month, start.day, tzinfo=TZ)
    rule = rrulestr("RRULE:" + rtext, dtstart=dtstart)
    out = []
    lo = (ws if isinstance(ws, datetime) else datetime(ws.year, ws.month, ws.day, tzinfo=TZ)) - dur
    hi = we if isinstance(we, datetime) else datetime(we.year, we.month, we.day, tzinfo=TZ)
    for o in rule.between(lo, hi, inc=True):
        s = o.date() if ev["all_day"] else o
        out.append((s, s + dur))
        if len(out) >= limit:
            break
    return out


def busy_blocks(events, win_start, win_end):
    """Créneaux occupés (hors événements transparents) d'une liste d'événements développés -> [(start, end)] triés, fusionnés."""
    blocks = []
    for ev in events:
        if ev.get("transparent"):
            continue
        for s, e in occurrences(ev, win_start, win_end):
            if not isinstance(s, datetime):
                s = datetime(s.year, s.month, s.day, tzinfo=TZ); e = datetime(e.year, e.month, e.day, tzinfo=TZ)
            blocks.append((s, e))
    blocks.sort()
    merged = []
    for s, e in blocks:
        if merged and s <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], e))
        else:
            merged.append((s, e))
    return merged


def conflicts(candidate, events):
    """Événements (développés dans la fenêtre du candidat) qui chevauchent le candidat -- réservation de ressource."""
    cs, ce = candidate["start"], candidate["end"]
    if not isinstance(cs, datetime):
        cs = datetime(cs.year, cs.month, cs.day, tzinfo=TZ); ce = datetime(ce.year, ce.month, ce.day, tzinfo=TZ)
    hits = []
    for ev in events:
        if ev.get("uid") and ev["uid"] == candidate.get("uid"):
            continue
        for s, e in occurrences(ev, cs - timedelta(days=1), ce + timedelta(days=1)):
            if not isinstance(s, datetime):
                s = datetime(s.year, s.month, s.day, tzinfo=TZ); e = datetime(e.year, e.month, e.day, tzinfo=TZ)
            if s < ce and e > cs:
                hits.append(ev); break
    return hits


def rrule_to_form(rr):
    """vRecur (dict de listes) -> forme simple {freq, interval, until, count, byday} acceptée par validate()."""
    if not rr:
        return None
    g = lambda k: (rr.get(k) or [None])[0] if isinstance(rr.get(k), list) else rr.get(k)  # noqa: E731
    out = {"freq": str(g("FREQ") or "").upper(), "interval": int(g("INTERVAL") or 1)}
    if g("UNTIL") is not None: out["until"] = iso(_aware(g("UNTIL")))
    if g("COUNT"): out["count"] = int(g("COUNT"))
    bd = rr.get("BYDAY")
    if bd: out["byday"] = ",".join(str(x) for x in (bd if isinstance(bd, list) else [bd]))
    return out


def public(ev, s=None, e=None, **more):
    d = {k: ev.get(k) for k in ("uid", "title", "all_day", "location", "description", "categories", "transparent")}
    d["start"], d["end"] = iso(s if s is not None else ev["start"]), iso(e if e is not None else ev["end"])
    d["recurring"] = bool(ev.get("rrule") or ev.get("rrule_text")); d["rrule"] = rrule_to_form(ev.get("rrule")) if ev.get("rrule") else None; d["rrule_text"] = ev.get("rrule_text") or ""
    d.update(more)
    return d
