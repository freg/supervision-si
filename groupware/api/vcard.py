# -*- coding: utf-8 -*-
"""vCard 3.0 minimal (livraison #665) : dict <-> texte, sans dépendance. Champs gérés : UID, FN, N (nom;prénom), ORG, TITLE,
TEL (plusieurs, type), EMAIL (plusieurs), ADR (une, type), URL, NOTE, CATEGORIES, REV. Les lignes inconnues sont conservées
(`extra`) pour ne rien perdre d'une carte écrite par un autre client (photo, etc.)."""
import re, time

KNOWN = ("UID", "FN", "N", "ORG", "TITLE", "TEL", "EMAIL", "ADR", "URL", "NOTE", "CATEGORIES", "REV", "BEGIN", "END", "VERSION", "PRODID")


def unfold(text):
    return re.sub(r"\r?\n[ \t]", "", text.replace("\r\n", "\n"))


def _unescape(v):
    return v.replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\;", ";").replace("\\\\", "\\")


def _escape(v):
    return str(v or "").replace("\\", "\\\\").replace("\n", "\\n").replace(",", "\\,").replace(";", "\;")


def parse(text):
    """-> {uid, fn, last, first, org, title, tels: [{type, value}], emails: [{type, value}], adr: {street, city, zip, country, type}, url, note, categories: [], rev, extra: [lignes]}"""
    c = {"uid": "", "fn": "", "last": "", "first": "", "org": "", "title": "", "tels": [], "emails": [], "adr": None, "url": "", "note": "", "categories": [], "rev": "", "extra": []}
    for line in unfold(text).split("\n"):
        if not line.strip() or ":" not in line:
            continue
        head, value = line.split(":", 1)
        parts = head.split(";")
        name = parts[0].upper()
        params = {}
        for p in parts[1:]:
            k, _, v = p.partition("=")
            params[k.upper()] = v or "TRUE"
        typ = params.get("TYPE", "").lower().replace("\"", "")
        if name == "UID": c["uid"] = value.strip()
        elif name == "FN": c["fn"] = _unescape(value)
        elif name == "N":
            f = [_unescape(x) for x in value.split(";")] + ["", ""]
            c["last"], c["first"] = f[0], f[1]
        elif name == "ORG": c["org"] = _unescape(value.split(";")[0])
        elif name == "TITLE": c["title"] = _unescape(value)
        elif name == "TEL": c["tels"].append({"type": typ or "voice", "value": value.strip()})
        elif name == "EMAIL": c["emails"].append({"type": typ or "internet", "value": value.strip()})
        elif name == "ADR":
            f = [_unescape(x) for x in value.split(";")] + [""] * 7
            c["adr"] = {"type": typ or "work", "street": f[2], "city": f[3], "region": f[4], "zip": f[5], "country": f[6]}
        elif name == "URL": c["url"] = value.strip()
        elif name == "NOTE": c["note"] = _unescape(value)
        elif name == "CATEGORIES": c["categories"] = [_unescape(x).strip() for x in re.split(r"(?<!\\),", value) if x.strip()]
        elif name == "REV": c["rev"] = value.strip()
        elif name in ("BEGIN", "END", "VERSION", "PRODID"): pass
        else: c["extra"].append(line)
    if not c["fn"]:
        c["fn"] = " ".join(x for x in (c["first"], c["last"]) if x) or c["org"]
    return c


def serialize(c):
    """dict (mêmes clés que parse, tolérant) -> texte vCard 3.0 (CRLF)."""
    uid = c.get("uid") or ""
    fn = c.get("fn") or " ".join(x for x in (c.get("first"), c.get("last")) if x) or c.get("org") or "Sans nom"
    lines = ["BEGIN:VCARD", "VERSION:3.0", "PRODID:-//supervision-si//groupware//FR", "UID:" + uid, "FN:" + _escape(fn), "N:%s;%s;;;" % (_escape(c.get("last")), _escape(c.get("first")))]
    if c.get("org"): lines.append("ORG:" + _escape(c["org"]))
    if c.get("title"): lines.append("TITLE:" + _escape(c["title"]))
    for t in c.get("tels") or []:
        if (t.get("value") or "").strip(): lines.append("TEL;TYPE=%s:%s" % ((t.get("type") or "voice").upper(), t["value"].strip()))
    for e in c.get("emails") or []:
        if (e.get("value") or "").strip(): lines.append("EMAIL;TYPE=%s:%s" % ((e.get("type") or "internet").upper(), e["value"].strip()))
    a = c.get("adr")
    if a and any(a.get(k) for k in ("street", "city", "zip", "country")):
        lines.append("ADR;TYPE=%s:;;%s;%s;%s;%s;%s" % ((a.get("type") or "work").upper(), _escape(a.get("street")), _escape(a.get("city")), _escape(a.get("region")), _escape(a.get("zip")), _escape(a.get("country"))))
    if c.get("url"): lines.append("URL:" + c["url"].strip())
    if c.get("note"): lines.append("NOTE:" + _escape(c["note"]))
    if c.get("categories"): lines.append("CATEGORIES:" + ",".join(_escape(x) for x in c["categories"] if x))
    lines.append("REV:" + time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()))
    lines += [l for l in (c.get("extra") or []) if l and not l.upper().startswith(("BEGIN:", "END:", "VERSION:"))]
    lines.append("END:VCARD")
    return "\r\n".join(_fold(l) for l in lines) + "\r\n"


def _fold(line):
    b = line.encode("utf-8")
    if len(b) <= 75:
        return line
    out, cur = [], ""
    for ch in line:
        if len((cur + ch).encode("utf-8")) > 74:
            out.append(cur); cur = " " + ch
        else:
            cur += ch
    out.append(cur)
    return "\r\n".join(out)


def matches(c, q):
    q = (q or "").strip().lower()
    if not q:
        return True
    hay = " ".join([c.get("fn", ""), c.get("org", ""), c.get("title", ""), c.get("note", ""), " ".join(c.get("categories") or []),
                    " ".join(t["value"] for t in c.get("tels") or []), " ".join(e["value"] for e in c.get("emails") or []), " ".join((c.get("adr") or {}).values()) if c.get("adr") else ""]).lower()
    return all(w in hay for w in q.split())
