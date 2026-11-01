# -*- coding: utf-8 -*-
"""Supervision des entrées de services (#531) -- la partie RÉSEAU :
résolution DNS, ports TCP, certificat TLS, HTTP (statut, redirections,
titre, serveur, page d'hébergeur), scénario HTTP avec compte de test du
coffre, canari mail (SMTP sortant -> IMAP). Trafic identifié (User-Agent
`si-service-watch`), délais courts, aucun secret dans les résultats."""
import email
import imaplib
import re
import smtplib
import socket
import ssl
import time
import uuid
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

import requests

import checks

UA = "si-service-watch/1 (supervision-si ; test de service)"
HOSTING_PATTERNS = [
    (re.compile(r"parking|domaine? (?:en )?parking|this domain (?:is|has been) (?:parked|registered)", re.I), "parking"),
    (re.compile(r"page par d[ée]faut|default (?:web )?page|it works!|welcome to nginx|apache2 (?:debian|ubuntu) default", re.I), "page par défaut du serveur"),
    (re.compile(r"site (?:en )?construction|under construction|coming soon", re.I), "en construction"),
    (re.compile(r"suspended|compte suspendu|account has been suspended", re.I), "compte suspendu"),
]


def resolve(name, timeout=5):
    try:
        socket.setdefaulttimeout(timeout)
        infos = socket.getaddrinfo(name, None)
        ips = sorted({i[4][0] for i in infos})
        return True, ips
    except socket.gaierror:
        return False, []
    finally:
        socket.setdefaulttimeout(None)


def tcp_open(ip, port, timeout=3):
    try:
        with socket.create_connection((ip, port), timeout=timeout):
            return True
    except OSError:
        return False


def tls_info(host, port=443, timeout=5):
    out = {"issuer": None, "names": [], "not_after": None, "days_left": None, "error": None}
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as s:
            with ctx.wrap_socket(s, server_hostname=host) as ss:
                cert = ss.getpeercert()
        out["issuer"] = " ".join(v for rdn in cert.get("issuer", ()) for k, v in rdn if k in ("organizationName", "commonName"))[:80]
        out["names"] = [v for k, v in cert.get("subjectAltName", ()) if k == "DNS"][:20]
        out["not_after"] = cert.get("notAfter")
        out["days_left"] = checks.days_until(cert.get("notAfter"))
    except ssl.SSLCertVerificationError as exc:
        out["error"] = "certificat non valide : %s" % (exc.verify_message or str(exc))[:80]
    except (OSError, ssl.SSLError) as exc:
        out["error"] = str(exc)[:80] or exc.__class__.__name__
    return out


def http_get(url, timeout=10, session=None, verify=True):
    s = session or requests.Session()
    out = {"url": url, "status": None, "final_url": None, "title": None, "server": None, "elapsed_ms": None, "error": None, "hosting_page": None, "text": ""}
    t0 = time.monotonic()
    try:
        r = s.get(url, timeout=timeout, headers={"User-Agent": UA}, allow_redirects=True, verify=verify)
        out["elapsed_ms"] = round((time.monotonic() - t0) * 1000.0, 1)
        out["status"], out["final_url"], out["server"] = r.status_code, r.url, (r.headers.get("Server") or "")[:60]
        text = r.text[:200000] if "html" in (r.headers.get("Content-Type") or "").lower() or r.text[:200].lstrip().lower().startswith("<") else r.text[:2000]
        out["text"] = text
        m = re.search(r"(?is)<title[^>]*>(.*?)</title>", text)
        out["title"] = re.sub(r"\s+", " ", m.group(1)).strip()[:120] if m else None
        head = text[:20000]
        for rx, label in HOSTING_PATTERNS:
            if rx.search(head) or (out["title"] and rx.search(out["title"])):
                out["hosting_page"] = label
                break
    except requests.exceptions.SSLError as exc:
        out["error"] = "TLS : %s" % str(exc)[:80]
    except requests.RequestException as exc:
        out["error"] = (str(exc)[:80] or exc.__class__.__name__)
    return out


def qualify(entry, timeout=5):
    """Qualification complète d'une entrée -> résultat (sans secrets)."""
    name = entry["name"]
    ok, ips = resolve(name, timeout)
    res = {"name": name, "resolved": ok, "ips": ips, "open_ports": [], "ports_tested": [], "tls": None, "http": None, "kind": None}
    if not ok or not ips:
        res["kind"] = "silencieux"
        return res
    ports = sorted(set((entry.get("ports") or []) + checks.ALL_PORTS))
    res["ports_tested"] = ports
    ip = ips[0]
    res["open_ports"] = [p for p in ports if tcp_open(ip, p, 3)]
    if 443 in res["open_ports"]:
        res["tls"] = tls_info(name, 443, timeout)
    if 443 in res["open_ports"] or 80 in res["open_ports"]:
        url = entry.get("url") or ("https://%s/" % name if 443 in res["open_ports"] else "http://%s/" % name)
        h = http_get(url, timeout=max(timeout, 10))
        res["http"] = {k: v for k, v in h.items() if k != "text"}
        res["_text"] = h.get("text") or ""
    res["kind"] = entry.get("kind_override") or checks.classify(res)
    return res


def run_scenario(entry, steps, credentials=None, timeout=15):
    """Scénario HTTP déclaratif : [{name, method, url|path, form|json,
    login: {user_field, password_field, credential}, expect: {...}}]. Les
    identifiants viennent du coffre (credentials = {nom: (user, pwd)}) et
    ne sont jamais recopiés dans le résultat."""
    s = requests.Session()
    s.headers["User-Agent"] = UA
    base = entry.get("url") or "https://%s/" % entry["name"]
    out = {"ok": True, "steps": [], "failed_step": None, "reasons": []}
    for i, st in enumerate(steps or [], 1):
        url = st.get("url") or requests.compat.urljoin(base, st.get("path") or "/")
        method = (st.get("method") or ("POST" if st.get("form") or st.get("login") else "GET")).upper()
        data, js = dict(st.get("form") or {}), st.get("json")
        if st.get("login"):
            lg = st["login"]
            up = (credentials or {}).get(lg.get("credential"))
            if not up:
                rec = {"name": st.get("name") or "pas %d" % i, "ok": False, "reasons": ["compte de test « %s » absent du coffre" % lg.get("credential")]}
                out["steps"].append(rec); out.update(ok=False, failed_step=rec["name"], reasons=rec["reasons"])
                break
            data[lg.get("user_field") or "username"] = up[0]
            data[lg.get("password_field") or "password"] = up[1]
        t0 = time.monotonic()
        try:
            r = s.request(method, url, data=data or None, json=js, timeout=timeout, allow_redirects=st.get("follow", True))
            resp = {"status": r.status_code, "text": r.text[:200000], "headers": dict(r.headers), "url": r.url, "elapsed_ms": round((time.monotonic() - t0) * 1000.0, 1)}
        except requests.RequestException as exc:
            resp = {"status": None, "text": "", "headers": {}, "url": url, "elapsed_ms": round((time.monotonic() - t0) * 1000.0, 1), "error": str(exc)[:80]}
        ev = checks.evaluate_step(st, resp)
        if resp.get("error"):
            ev = {"ok": False, "reasons": [resp["error"]] + ev["reasons"]}
        rec = {"name": st.get("name") or "pas %d" % i, "ok": ev["ok"], "status": resp.get("status"), "elapsed_ms": resp.get("elapsed_ms"), "url": resp.get("url"), "reasons": ev["reasons"]}
        out["steps"].append(rec)
        if not ev["ok"]:
            out.update(ok=False, failed_step=rec["name"], reasons=ev["reasons"])
            break
    return out


# --- canari mail ---------------------------------------------------------------

def canary_send(c, smtp_user, smtp_pwd, token):
    """Envoie le message canari ; renvoie (message_id, erreur)."""
    msg = EmailMessage()
    msg["From"] = c.get("from") or smtp_user
    msg["To"] = c["to"]
    msg["Subject"] = "[canari %s] %s" % (c.get("name") or "mail", token)
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain=(c.get("from") or smtp_user).split("@")[-1])
    msg["X-SI-Canary"] = token
    msg.set_content("Message de test automatique de supervision-si.\nJeton : %s\nCe message est supprimé automatiquement.\n" % token)
    host, port = c.get("smtp_host"), int(c.get("smtp_port") or 587)
    try:
        if port == 465:
            srv = smtplib.SMTP_SSL(host, port, timeout=20)
        else:
            srv = smtplib.SMTP(host, port, timeout=20)
            srv.ehlo()
            if c.get("smtp_starttls", True):
                srv.starttls(context=ssl.create_default_context())
        if smtp_user and smtp_pwd:
            srv.login(smtp_user, smtp_pwd)
        srv.send_message(msg)
        srv.quit()
        return msg["Message-ID"], None
    except (OSError, smtplib.SMTPException) as exc:
        return None, (str(exc)[:120] or exc.__class__.__name__)


def canary_wait(c, imap_user, imap_pwd, token, wait_s=300, poll_s=20, delete=True):
    """Attend le message porteur du jeton dans la boîte IMAP ; renvoie
    {received, delay_s, auth, hops, altered, error}."""
    host, port = c.get("imap_host"), int(c.get("imap_port") or 993)
    t0 = time.monotonic()
    deadline = t0 + wait_s
    out = {"received": False, "delay_s": None, "auth": None, "hops": None, "altered": False, "error": None, "waited_s": wait_s}
    while True:
        try:
            m = imaplib.IMAP4_SSL(host, port, timeout=20) if c.get("imap_ssl", True) else imaplib.IMAP4(host, port, timeout=20)
            m.login(imap_user, imap_pwd)
            m.select(c.get("imap_folder") or "INBOX")
            typ, data = m.search(None, "HEADER", "X-SI-Canary", token)
            ids = data[0].split() if typ == "OK" and data and data[0] else []
            if ids:
                typ, raw = m.fetch(ids[-1], "(RFC822)")
                msg = email.message_from_bytes(raw[0][1]) if typ == "OK" and raw and raw[0] else None
                headers_text = "".join("%s: %s\n" % (k, v) for k, v in (msg.items() if msg else []))
                out.update(received=True, delay_s=int(time.monotonic() - t0), auth=checks.parse_auth_results(headers_text), hops=checks.received_hops(headers_text))
                body = msg.get_body(preferencelist=("plain",)) if msg else None
                out["altered"] = bool(msg) and ("Jeton : %s" % token) not in ((body.get_content() if body else "") or "")
                if delete:
                    m.store(ids[-1], "+FLAGS", "\\Deleted"); m.expunge()
                m.logout()
                return out
            m.logout()
        except (OSError, imaplib.IMAP4.error) as exc:
            out["error"] = str(exc)[:120] or exc.__class__.__name__
            return out
        if time.monotonic() >= deadline:
            out["delay_s"] = None
            return out
        time.sleep(poll_s)


def new_token():
    return uuid.uuid4().hex[:16]
