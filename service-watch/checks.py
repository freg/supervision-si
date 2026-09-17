# -*- coding: utf-8 -*-
"""Supervision des entrées de services (livraison #531, backlog item 80) --
logique PURE (testée sans réseau) : lecture d'une zone DNS ou d'une liste de
noms, classement d'une entrée d'après ce qui répond, empreinte de contenu
d'une page (masque des zones volatiles) et différence, évaluation d'un
scénario HTTP, lecture des en-têtes d'authentification d'un mail canari,
constats. Le réseau est dans probe.py, l'orchestration dans app.py."""
import difflib
import hashlib
import re
from datetime import datetime, timezone

DEFAULT_PORTS = {"web": [80, 443], "mail": [25, 465, 587, 993, 995, 143, 110], "ssh": [22]}
ALL_PORTS = [80, 443, 25, 465, 587, 993, 22]
VOLATILE = [
    (re.compile(r"\b\d{1,2}[/:.-]\d{1,2}[/:.-]\d{2,4}\b"), "<date>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}(?::\d{2})?)?\b"), "<date>"),
    (re.compile(r"\b\d{1,2}:\d{2}(?::\d{2})?\b"), "<heure>"),
    (re.compile(r"\b\d[\d\s.,]*\d\b"), "<n>"),
    (re.compile(r"[0-9a-f]{16,}", re.I), "<hash>"),
]


# --- inventaire ------------------------------------------------------------

def parse_zone(text, default_domain=""):
    """Zone BIND (export OVH/Online) ou simple liste de noms -> entrées
    candidates [{name, type, target}] dédupliquées par nom. Les lignes SOA,
    NS, TXT et les commentaires sont ignorés ; un nom relatif est complété
    par le domaine ($ORIGIN ou default_domain)."""
    origin = (default_domain or "").strip(".").lower()
    out, seen = [], set()
    for raw in (text or "").splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^\$ORIGIN\s+(\S+)", line, re.I)
        if m:
            origin = m.group(1).strip(".").lower()
            continue
        if line.startswith("$"):
            continue
        parts = line.split()
        rtype, name, target = None, None, None
        for i, p in enumerate(parts):
            if p.upper() in ("A", "AAAA", "CNAME", "MX", "SRV"):
                rtype = p.upper()
                name = parts[0] if i > 0 and not parts[0].isdigit() and parts[0].upper() != "IN" else "@"
                rest = parts[i + 1:]
                target = rest[-1] if rest else None
                break
            if p.upper() in ("SOA", "NS", "TXT", "CAA", "PTR", "DNSKEY", "DS", "SSHFP", "TLSA"):
                rtype = "skip"
                break
        if rtype == "skip":
            continue
        if rtype is None:
            # une liste de noms nus (un par ligne), éventuellement « nom  IP »
            cand = parts[0].strip(".").lower()
            if re.match(r"^[a-z0-9_.-]+\.[a-z]{2,}$", cand):
                rtype, name, target = "NAME", cand, parts[1] if len(parts) > 1 else None
            else:
                continue
        name = (name or "@").strip().lower()
        if name in ("@", ""):
            fqdn = origin
        elif name.endswith("."):
            fqdn = name.rstrip(".")
        elif "." in name and rtype == "NAME":
            fqdn = name
        else:
            fqdn = "%s.%s" % (name, origin) if origin else name
        if not fqdn or fqdn.startswith("*") or fqdn.startswith("_") and rtype != "SRV":
            continue
        if rtype == "SRV" and target:
            fqdn = target.rstrip(".").lower()  # la cible du SRV est le service
        if rtype == "MX" and target:
            fqdn = target.rstrip(".").lower()
        if fqdn in seen:
            continue
        seen.add(fqdn)
        out.append({"name": fqdn, "type": rtype if rtype != "NAME" else "A", "target": (target or "").rstrip(".") or None,
                    "hint": "mail" if rtype == "MX" else None})
    return out


def classify(result):
    """D'après la qualification (ports ouverts, HTTP, TLS) : web / mail / ged
    / ssh / autre / silencieux."""
    ports = set(result.get("open_ports") or [])
    http = result.get("http") or {}
    if not ports and not result.get("ips"):
        return "silencieux" if result.get("resolved") is False else "silencieux"
    if not ports:
        return "silencieux"
    title = (http.get("title") or "").lower()
    server = (http.get("server") or "").lower()
    if ports & {80, 443} and (http.get("status") or 0) > 0:
        if any(k in title or k in server or k in (http.get("final_url") or "").lower() for k in ("owncloud", "nextcloud", "mayan", "ged", "alfresco", "seafile")):
            return "ged"
        return "web"
    if ports & {25, 465, 587, 993, 995, 143, 110}:
        return "mail"
    if 22 in ports:
        return "ssh"
    return "autre"


# --- empreinte de contenu ----------------------------------------------------

def normalize_html(html, masks=None):
    """Texte visible d'une page, zones volatiles remplacées (dates, heures,
    nombres, hachages, motifs déclarés dans `masks`) -- pour comparer deux
    passages sans hurler à chaque horloge."""
    s = html or ""
    s = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", s)
    s = re.sub(r"(?is)<!--.*?-->", " ", s)
    s = re.sub(r"(?is)<[^>]+>", " ", s)
    s = re.sub(r"&nbsp;|&#160;", " ", s)
    s = re.sub(r"&amp;", "&", s)
    for pat in masks or []:
        try:
            s = re.sub(pat, "<masque>", s, flags=re.I)
        except re.error:
            continue
    for rx, rep in VOLATILE:
        s = rx.sub(rep, s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def fingerprint(text):
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:24]


def content_diff(before, after, max_lines=40):
    """Différence lisible (mots) entre deux textes normalisés + taux de changement."""
    a, b = (before or "").split(), (after or "").split()
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    ratio = round((1.0 - sm.ratio()) * 100.0, 1)
    lines = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            continue
        if tag in ("delete", "replace"):
            lines.append("- " + " ".join(a[i1:i2])[:200])
        if tag in ("insert", "replace"):
            lines.append("+ " + " ".join(b[j1:j2])[:200])
        if len(lines) >= max_lines:
            lines.append("…")
            break
    return {"change_pct": ratio, "lines": lines}


# --- scénarios HTTP -------------------------------------------------------------

def evaluate_step(step, response):
    """Un pas de scénario contre une réponse {status, text, headers, url,
    elapsed_ms} -> {ok, reasons}."""
    reasons = []
    exp = step.get("expect") or {}
    st = exp.get("status")
    if st is not None:
        ok = response.get("status") in (st if isinstance(st, list) else [st])
        if not ok:
            reasons.append("statut %s (attendu %s)" % (response.get("status"), st))
    text = response.get("text") or ""
    for needle in exp.get("text") if isinstance(exp.get("text"), list) else ([exp["text"]] if exp.get("text") else []):
        if needle.lower() not in text.lower():
            reasons.append("texte absent : « %s »" % needle[:60])
    for needle in exp.get("not_text") if isinstance(exp.get("not_text"), list) else ([exp["not_text"]] if exp.get("not_text") else []):
        if needle.lower() in text.lower():
            reasons.append("texte interdit présent : « %s »" % needle[:60])
    hdrs = {str(k).lower(): v for k, v in (response.get("headers") or {}).items()}
    for h, v in (exp.get("headers") or {}).items():
        got = hdrs.get(str(h).lower())
        if got is None or (v and str(v).lower() not in str(got).lower()):
            reasons.append("en-tête %s : %s (attendu %s)" % (h, got, v))
    if exp.get("url"):
        if exp["url"].lower() not in (response.get("url") or "").lower():
            reasons.append("URL finale %s (attendu contenant %s)" % (response.get("url"), exp["url"]))
    if exp.get("max_ms") is not None and (response.get("elapsed_ms") or 0) > exp["max_ms"]:
        reasons.append("%.0f ms (max %s)" % (response["elapsed_ms"], exp["max_ms"]))
    return {"ok": not reasons, "reasons": reasons}


# --- canaris mail ----------------------------------------------------------------

def parse_auth_results(headers_text):
    """En-tête Authentication-Results (et Received-SPF) -> {spf, dkim, dmarc}."""
    out = {"spf": None, "dkim": None, "dmarc": None}
    txt = headers_text or ""
    for key in out:
        m = re.search(r"\b%s=(pass|fail|softfail|neutral|none|temperror|permerror|policy)\b" % key, txt, re.I)
        if m:
            out[key] = m.group(1).lower()
    if out["spf"] is None:
        m = re.search(r"^Received-SPF:\s*(\w+)", txt, re.I | re.M)
        if m:
            out["spf"] = m.group(1).lower()
    return out


def received_hops(headers_text):
    return len(re.findall(r"^Received:", headers_text or "", re.M))


# --- constats ---------------------------------------------------------------------

def evaluate_entry(entry, result, prev=None, cert_warn_days=21):
    """Constats d'une qualification (jamais d'action)."""
    al = []

    def add(sev, code, msg):
        al.append({"severity": sev, "code": code, "message": "%s : %s" % (entry.get("name"), msg)})

    if result.get("resolved") is False:
        add("critical", "dns-unresolved", "nom non résolu (trou DNS ou zone modifiée)")
        return al
    if not result.get("open_ports"):
        add("critical" if entry.get("expected") != "silencieux" else "info", "silent", "aucun port ne répond (%s testés)" % ", ".join(str(p) for p in result.get("ports_tested") or []))
        return al
    exp_ports = set(entry.get("ports") or [])
    closed = sorted(exp_ports - set(result.get("open_ports") or []))
    if closed:
        add("critical", "port-closed", "port(s) attendu(s) fermé(s) : %s" % ", ".join(str(p) for p in closed))
    http = result.get("http") or {}
    if http:
        if http.get("error"):
            add("critical", "http-error", "HTTP : %s" % http["error"])
        elif (http.get("status") or 0) >= 500:
            add("critical", "http-5xx", "HTTP %s" % http["status"])
        elif (http.get("status") or 0) >= 400 and http.get("status") not in (401, 403):
            add("warning", "http-4xx", "HTTP %s" % http["status"])
        if http.get("elapsed_ms") and http["elapsed_ms"] > (entry.get("max_ms") or 5000):
            add("warning", "http-slow", "réponse en %.1f s" % (http["elapsed_ms"] / 1000.0))
        if entry.get("expect_url") and entry["expect_url"].lower() not in (http.get("final_url") or "").lower():
            add("critical", "http-redirect", "redirigé vers %s" % http.get("final_url"))
        if http.get("hosting_page"):
            add("critical", "hosting-page", "page par défaut d'hébergeur / parking (%s)" % http["hosting_page"])
    tls = result.get("tls") or {}
    if tls.get("error"):
        add("critical", "tls-error", "TLS : %s" % tls["error"])
    elif tls.get("days_left") is not None:
        if tls["days_left"] < 0:
            add("critical", "cert-expired", "certificat expiré depuis %d j" % -tls["days_left"])
        elif tls["days_left"] <= cert_warn_days:
            add("warning", "cert-expiring", "certificat expire dans %d j" % tls["days_left"])
        if entry.get("name") and tls.get("names") and not any(_match_name(entry["name"], n) for n in tls["names"]):
            add("critical", "cert-name", "certificat pour %s, pas pour ce nom" % ", ".join(tls["names"][:3]))
    sc = result.get("scenario") or {}
    if sc and not sc.get("ok"):
        add("critical", "scenario-failed", "scénario en échec au pas %s : %s" % (sc.get("failed_step"), "; ".join(sc.get("reasons") or [])[:200]))
    diff = result.get("content_diff") or {}
    if diff.get("change_pct") is not None and diff["change_pct"] >= (entry.get("diff_threshold_pct") or 30):
        add("warning", "content-changed", "contenu de la page modifié à %.0f %% (référence du %s)" % (diff["change_pct"], diff.get("reference_at") or "?"))
    if prev and prev.get("kind") and result.get("kind") and prev["kind"] != result["kind"]:
        add("warning", "kind-changed", "service détecté « %s » (était « %s »)" % (result["kind"], prev["kind"]))
    return al


def _match_name(host, pattern):
    host, pattern = host.lower(), pattern.lower()
    if pattern.startswith("*."):
        return host.split(".", 1)[1:] == [pattern[2:]] if "." in host else False
    return host == pattern


def evaluate_canary(c, result):
    """Constats d'un canari mail : non arrivé, en retard, authentification en échec."""
    al = []
    tag = c.get("name") or "canari"
    if result.get("send_error"):
        al.append({"severity": "critical", "code": "canary-send-failed", "message": "%s : envoi impossible (%s)" % (tag, result["send_error"])})
        return al
    if not result.get("received"):
        al.append({"severity": "critical", "code": "canary-lost", "message": "%s : message non arrivé après %s s" % (tag, result.get("waited_s"))})
        return al
    if result.get("delay_s") is not None and result["delay_s"] > (c.get("max_delay_s") or 300):
        al.append({"severity": "warning", "code": "canary-late", "message": "%s : arrivé en %d s (max %s)" % (tag, result["delay_s"], c.get("max_delay_s") or 300)})
    auth = result.get("auth") or {}
    bad = [k for k, v in auth.items() if v in ("fail", "softfail", "permerror")]
    if bad:
        al.append({"severity": "warning", "code": "canary-auth", "message": "%s : %s en échec (%s)" % (tag, ", ".join(bad).upper(), ", ".join("%s=%s" % (k, auth[k]) for k in bad))})
    if result.get("altered"):
        al.append({"severity": "critical", "code": "canary-altered", "message": "%s : corps du message altéré en route" % tag})
    return al


def summarize(alerts):
    counts = {"critical": 0, "warning": 0, "info": 0}
    for a in alerts or []:
        counts[a.get("severity", "info")] = counts.get(a.get("severity", "info"), 0) + 1
    return {"state": "critical" if counts["critical"] else ("warning" if counts["warning"] else "ok"), "counts": counts}


def days_until(iso_or_ssl_date):
    """'Sep 17 12:00:00 2027 GMT' (ssl) ou ISO -> jours restants (entier)."""
    if not iso_or_ssl_date:
        return None
    for fmt in ("%b %d %H:%M:%S %Y %Z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d"):
        try:
            d = datetime.strptime(iso_or_ssl_date, fmt).replace(tzinfo=timezone.utc)
            return int((d - datetime.now(timezone.utc)).total_seconds() // 86400)
        except ValueError:
            continue
    return None
