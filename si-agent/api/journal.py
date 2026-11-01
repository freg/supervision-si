# -*- coding: utf-8 -*-
"""#795 : tuile « Journal des chantiers » -- actes, surveillances, relances et interventions, avec date, heures de début /
fin, nature, description non technique, résultat, statut et source ; par chantier.

- saisie dans le hub, import (JSON ou CSV au format de l'export), export CSV (Excel, `;`, UTF-8 avec BOM) ;
- suggestions tirées des événements du central (pilotage de la migration, rapatriements, PRA, sauvegardes, agents
  hors ligne, constats critiques des sondes) : un clic les ajoute au journal, une fois chacun ;
- indicateurs : actes le week-end et hors heures de bureau (8 h 30 - 12 h 15, 14 h - 18 h, lundi au vendredi).
Les entrées réelles (noms de serveurs, clients) sont saisies ou importées dans le hub, jamais dans le dépôt.
Pur : validate, row_key, weekday_fr, off_hours, duration_min, stats, to_csv, parse_csv, guess_chantier, suggestion_for."""
import csv
import datetime
import io
import json
import os
import re

SCHEMA = (
    "CREATE TABLE IF NOT EXISTS journal (id INTEGER PRIMARY KEY AUTOINCREMENT, chantier TEXT NOT NULL, day TEXT, start TEXT, "
    "end_ TEXT, nature TEXT NOT NULL DEFAULT 'Acte', acte TEXT NOT NULL, description TEXT, resultat TEXT, statut TEXT NOT NULL DEFAULT 'Fait', "
    "source TEXT, event_id INTEGER UNIQUE, created_at TEXT, created_by TEXT, updated_at TEXT, updated_by TEXT)",
    "CREATE INDEX IF NOT EXISTS idx_journal_day ON journal (chantier, day, start)",
)
NATURES = ("Acte", "Surveillance", "Relance", "Intervention")
STATUTS = ("Fait", "En cours", "Planifié", "À faire")
JOURS = ("lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche")
CSV_COLS = ("Chantier", "Date", "Jour", "Début", "Fin", "Durée", "Nature", "Acte", "Description", "Résultat", "Statut", "Source")
FIELDS = ("chantier", "day", "start", "end", "nature", "acte", "description", "resultat", "statut", "source")
DAY_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
HM_RE = re.compile(r"^([01]?\d|2[0-3])[:hH]([0-5]\d)$")
BUREAU = ((8 * 60 + 30, 12 * 60 + 15), (14 * 60, 18 * 60))
# événements du central proposés au journal : préfixe de type -> (chantier, nature)
SUGGEST = (("migration", "Migration des serveurs", "Intervention"), ("repatriation", "Migration des serveurs", "Intervention"),
           ("pra", "Serveurs (reprise d'activité)", "Intervention"), ("maint", "Serveurs (maintenance)", "Intervention"),
           ("backup", "Sauvegardes", "Surveillance"), ("agent-offline", "Supervision", "Surveillance"),
           ("probe-alert", "Supervision", "Surveillance"))


def norm_day(v):
    """« 2026-10-20 », « 20/10/2026 » -> « 2026-10-20 » ; vide -> None ; illisible -> False."""
    v = str(v or "").strip()
    if not v:
        return None
    if DAY_RE.match(v):
        try:
            datetime.date.fromisoformat(v)
            return v
        except ValueError:
            return False
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", v)
    if m:
        try:
            return datetime.date(int(m.group(3)), int(m.group(2)), int(m.group(1))).isoformat()
        except ValueError:
            return False
    return False


def norm_hm(v):
    """« 9:05 », « 09h05 », « 17:50:00 » -> « 09:05 » ; vide -> None ; illisible -> False."""
    v = str(v or "").strip()
    if not v:
        return None
    v = re.sub(r":\d{2}$", "", v) if v.count(":") == 2 else v
    m = HM_RE.match(v)
    return "%02d:%s" % (int(m.group(1)), m.group(2)) if m else False


def validate(e):
    """Entrée brute -> (entrée propre, erreur)."""
    e = e or {}
    out = {k: str(e.get(k) or "").strip() for k in FIELDS}
    out["chantier"] = out["chantier"][:80]
    out["acte"] = out["acte"][:200]
    for k in ("description", "resultat"):
        out[k] = out[k][:2000]
    out["source"] = out["source"][:200]
    if not out["chantier"]:
        return None, "chantier requis"
    if not out["acte"]:
        return None, "intitulé de l'acte requis"
    d = norm_day(out["day"])
    if d is False:
        return None, "date illisible : %s (AAAA-MM-JJ ou JJ/MM/AAAA)" % out["day"]
    out["day"] = d
    for k in ("start", "end"):
        h = norm_hm(out[k])
        if h is False:
            return None, "heure illisible : %s (HH:MM)" % out[k]
        out[k] = h
    out["nature"] = out["nature"] or "Acte"
    out["statut"] = out["statut"] or "Fait"
    if out["nature"] not in NATURES:
        return None, "nature inconnue : %s (%s)" % (out["nature"], ", ".join(NATURES))
    if out["statut"] not in STATUTS:
        return None, "statut inconnu : %s (%s)" % (out["statut"], ", ".join(STATUTS))
    if "id" in e and str(e["id"]).isdigit():
        out["id"] = int(e["id"])
    return out, None


def row_key(e):
    """Doublon à l'import : même chantier, même jour, même heure de début, même acte."""
    return (e.get("chantier") or "", e.get("day") or "", e.get("start") or "", (e.get("acte") or "").lower())


def weekday_fr(day):
    return JOURS[datetime.date.fromisoformat(day).weekday()] if day else ""


def _minutes(hm):
    return int(hm[:2]) * 60 + int(hm[3:5]) if hm else None


def duration_min(e):
    a, b = _minutes(e.get("start")), _minutes(e.get("end"))
    if a is None or b is None:
        return None
    return b - a if b >= a else b + 24 * 60 - a      # fin après minuit


def off_hours(e):
    """Acte un samedi / dimanche, ou dont le début ou la fin tombe hors 8 h 30 - 12 h 15 / 14 h - 18 h."""
    if not e.get("day"):
        return False
    if datetime.date.fromisoformat(e["day"]).weekday() >= 5:
        return True
    for hm in (e.get("start"), e.get("end")):
        m = _minutes(hm)
        if m is not None and not any(a <= m <= b for a, b in BUREAU):
            return True
    return False


def stats(entries):
    """Par chantier : lignes, réalisées, en cours / planifiées, à faire, week-end, hors heures, temps tracé (min), natures."""
    out = {}
    for e in entries:
        s = out.setdefault(e["chantier"], {"chantier": e["chantier"], "lignes": 0, "fait": 0, "en_cours": 0, "a_faire": 0, "weekend": 0,
                                           "hors_heures": 0, "minutes": 0, "natures": {n: 0 for n in NATURES}, "premier": None, "dernier": None})
        s["lignes"] += 1
        s["fait"] += e["statut"] == "Fait"
        s["en_cours"] += e["statut"] in ("En cours", "Planifié")
        s["a_faire"] += e["statut"] == "À faire"
        if e.get("day"):
            s["weekend"] += datetime.date.fromisoformat(e["day"]).weekday() >= 5
            s["premier"] = min(filter(None, (s["premier"], e["day"])))
            s["dernier"] = max(filter(None, (s["dernier"], e["day"])))
        s["hors_heures"] += off_hours(e)
        s["minutes"] += duration_min(e) or 0
        s["natures"][e["nature"]] = s["natures"].get(e["nature"], 0) + 1
    return sorted(out.values(), key=lambda s: s["chantier"].lower())


def _fr_day(d):
    return "%s/%s/%s" % (d[8:10], d[5:7], d[0:4]) if d else ""


def to_csv(entries):
    """CSV pour Excel : `;`, UTF-8 avec BOM, dates JJ/MM/AAAA, durée H:MM."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\r\n")
    w.writerow(CSV_COLS)
    for e in entries:
        d = duration_min(e)
        w.writerow([e["chantier"], _fr_day(e.get("day")), weekday_fr(e.get("day")), e.get("start") or "", e.get("end") or "",
                    "" if d is None else "%d:%02d" % (d // 60, d % 60), e["nature"], e["acte"], e.get("description") or "",
                    e.get("resultat") or "", e["statut"], e.get("source") or ""])
    return "﻿" + buf.getvalue()


def parse_csv(text, chantier=""):
    """CSV au format de l'export (séparateur `;` ou `,`) -> entrées brutes ; `chantier` sert si la colonne manque."""
    text = (text or "").lstrip("﻿")
    first = text.splitlines()[0] if text.strip() else ""
    dialect = ";" if first.count(";") >= first.count(",") else ","
    rows = list(csv.reader(io.StringIO(text), delimiter=dialect))
    if not rows:
        return []
    head = [h.strip().lower() for h in rows[0]]
    alias = {"chantier": "chantier", "date": "day", "début": "start", "debut": "start", "fin": "end", "nature": "nature", "acte": "acte",
             "description": "description", "résultat": "resultat", "resultat": "resultat", "statut": "statut", "source": "source"}
    idx = {alias[h]: i for i, h in enumerate(head) if h in alias}
    out = []
    for r in rows[1:]:
        if not any(c.strip() for c in r):
            continue
        e = {k: (r[i] if i < len(r) else "") for k, i in idx.items()}
        e.setdefault("chantier", chantier)
        if not e.get("chantier"):
            e["chantier"] = chantier
        out.append(e)
    return out


def guess_chantier(kind):
    for pre, ch, nat in SUGGEST:
        if kind == pre or kind.startswith(pre + "-") or kind.startswith(pre):
            return ch, nat
    return None, None


def _tz():
    """Fuseau des heures du journal : JOURNAL_TZ (défaut Europe/Paris) ; heure locale du conteneur si la base des fuseaux manque."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(os.environ.get("JOURNAL_TZ", "Europe/Paris"))
    except Exception:  # noqa: BLE001 -- tzdata absent de l'image : repli
        return None


def suggestion_for(ev):
    """Événement du central -> proposition d'entrée (ou None si le type n'est pas retenu)."""
    ch, nat = guess_chantier(ev.get("kind") or "")
    if not ch:
        return None
    if ev["kind"] == "probe-alert" and ev.get("severity") != "critical":
        return None
    at = str(ev.get("at") or "")
    try:
        t = datetime.datetime.strptime(at[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=datetime.timezone.utc).astimezone(_tz())
        day, hm = t.date().isoformat(), t.strftime("%H:%M")
    except ValueError:
        day, hm = None, None
    return {"event_id": ev["id"], "chantier": ch, "day": day, "start": hm, "end": None, "nature": nat,
            "acte": (ev.get("message") or ev["kind"])[:200], "description": "", "resultat": "",
            "statut": "Fait" if ev.get("severity") != "critical" else "En cours",
            "source": "événement du hub #%s (%s%s)" % (ev["id"], ev["kind"], (", " + ev["agent_id"]) if ev.get("agent_id") else ""),
            "severity": ev.get("severity")}


# ---------------------------------------------------------------- base
def _row(r):
    d = dict(r)
    d["end"] = d.pop("end_", None)
    return d


def ensure(conn):
    for s in SCHEMA:
        conn.execute(s)


def list_entries(conn, chantier=None):
    ensure(conn)
    q = "SELECT * FROM journal" + (" WHERE chantier = ?" if chantier else "") + \
        " ORDER BY CASE WHEN day IS NULL THEN 1 ELSE 0 END, day, COALESCE(start, end_, ''), id"
    return [_row(r) for r in conn.execute(q, (chantier,) if chantier else ())]


def save(conn, entry, actor="", now=None):
    e, err = validate(entry)
    if err:
        return None, err
    ensure(conn)
    now = now or datetime.datetime.now().isoformat(timespec="seconds")
    vals = (e["chantier"], e["day"], e["start"], e["end"], e["nature"], e["acte"], e["description"], e["resultat"], e["statut"], e["source"])
    if e.get("id"):
        cur = conn.execute("UPDATE journal SET chantier=?, day=?, start=?, end_=?, nature=?, acte=?, description=?, resultat=?, statut=?, source=?, "
                           "updated_at=?, updated_by=? WHERE id=?", vals + (now, actor, e["id"]))
        if not cur.rowcount:
            return None, "entrée %s introuvable" % e["id"]
        eid = e["id"]
    else:
        ev = entry.get("event_id")
        cur = conn.execute("INSERT INTO journal (chantier, day, start, end_, nature, acte, description, resultat, statut, source, event_id, "
                           "created_at, created_by) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                           vals + (int(ev) if str(ev or "").isdigit() else None, now, actor))
        eid = cur.lastrowid
    return _row(conn.execute("SELECT * FROM journal WHERE id = ?", (eid,)).fetchone()), None


def delete(conn, eid):
    ensure(conn)
    return conn.execute("DELETE FROM journal WHERE id = ?", (int(eid),)).rowcount > 0


def import_rows(conn, rows, actor=""):
    """Ajoute les lignes valides ; ignore les doublons (row_key) ; renvoie {added, skipped, errors[]}."""
    ensure(conn)
    seen = {row_key(e) for e in list_entries(conn)}
    added, skipped, errors = 0, 0, []
    for i, raw in enumerate(rows or [], 1):
        e, err = validate(dict(raw, id=None))
        if err:
            errors.append("ligne %d : %s" % (i, err))
            continue
        if row_key(e) in seen:
            skipped += 1
            continue
        save(conn, e, actor)
        seen.add(row_key(e))
        added += 1
    return {"added": added, "skipped": skipped, "errors": errors[:50]}


def suggestions(conn, days=30, now=None):
    ensure(conn)
    since = (now or datetime.datetime.utcnow()) - datetime.timedelta(days=days)
    done = {r[0] for r in conn.execute("SELECT event_id FROM journal WHERE event_id IS NOT NULL")}
    out = []
    for r in conn.execute("SELECT id, at, agent_id, kind, severity, message FROM events WHERE at >= ? ORDER BY at DESC LIMIT 2000",
                          (since.strftime("%Y-%m-%dT%H:%M:%S"),)):
        ev = dict(r)
        if ev["id"] in done:
            continue
        s = suggestion_for(ev)
        if s:
            out.append(s)
    return out[:300]


def accept(conn, event_id, actor="", chantier=None):
    ensure(conn)
    r = conn.execute("SELECT id, at, agent_id, kind, severity, message FROM events WHERE id = ?", (int(event_id),)).fetchone()
    if not r:
        return None, "événement %s introuvable" % event_id
    s = suggestion_for(dict(r))
    if not s:
        return None, "type d'événement non retenu pour le journal"
    if conn.execute("SELECT 1 FROM journal WHERE event_id = ?", (int(event_id),)).fetchone():
        return None, "déjà au journal"
    if chantier:
        s["chantier"] = chantier
    return save(conn, s, actor)


def view(conn, chantier=None):
    entries = list_entries(conn, chantier)
    allc = sorted({r[0] for r in conn.execute("SELECT DISTINCT chantier FROM journal")}, key=str.lower)
    for e in entries:
        e["jour"] = weekday_fr(e.get("day"))
        e["duree_min"] = duration_min(e)
        e["hors_heures"] = off_hours(e)
    return {"entries": entries, "chantiers": allc, "stats": stats(entries if chantier else list_entries(conn)),
            "natures": list(NATURES), "statuts": list(STATUTS)}
