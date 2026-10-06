# -*- coding: utf-8 -*-
"""Audit extérieur NON INTRUSIF des applications en ligne (livraison #687) --
exécuté par l'agent du « point d'observation » (CT/VM chez l'hébergeur, vue
Internet), jamais par un agent ordinaire : `audit_enabled: true` dans
agent.json est requis, et le central n'accepte que des cibles de sa liste
blanche (`SI_AGENT_AUDIT_ALLOWED`).

Contrôles (stdlib seule, une connexion à la fois, pause entre deux ports) :
résolution DNS ; ports TCP d'une courte liste ; TLS (certificat, échéance,
nom, chaîne, version négociée, acceptation de TLS 1.0/1.1) ; en-têtes de
sécurité HTTP et redirection http → https. Aucun envoi de charge, aucune
tentative d'authentification.

`findings(result)` est pure (testée) ; `audit_target` prend ses primitives
réseau en paramètres pour les tests.
"""
import datetime as _dt
import socket
import ssl
import time

DEFAULT_PORTS = (21, 22, 25, 80, 443, 3306, 3389, 5432, 6443, 8080, 8443)
MAX_PORTS = 32
EXPECTED_OPEN = {80, 443}
RISKY_PORTS = {21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL", 6379: "Redis",
               9200: "Elasticsearch", 27017: "MongoDB", 11211: "Memcached", 2375: "Docker API"}
SECURITY_HEADERS = {
    "strict-transport-security": ("warning", "HSTS absent : un premier accès en http reste interceptable"),
    "content-security-policy": ("info", "CSP absente : pas de restriction des scripts chargés"),
    "x-content-type-options": ("info", "X-Content-Type-Options absent (nosniff)"),
    "x-frame-options": ("info", "X-Frame-Options absent (ou frame-ancestors dans la CSP) : intégration en iframe possible"),
    "referrer-policy": ("info", "Referrer-Policy absente"),
}


def findings(r, now=None):
    """Résultat brut d'une cible -> [{"severity", "check", "message"}]. Pure."""
    out = []

    def add(sev, check, msg):
        out.append({"severity": sev, "check": check, "message": msg})
    if r.get("error"):
        add("critical", "dns", r["error"])
        return out
    for p, st in sorted((r.get("ports") or {}).items(), key=lambda kv: int(kv[0])):
        p = int(p)
        if st == "open" and p not in EXPECTED_OPEN:
            name = RISKY_PORTS.get(p)
            add("warning" if name else "info", "ports", "port %d ouvert depuis Internet%s" % (p, " (%s)" % name if name else ""))
    if 443 in [int(p) for p, st in (r.get("ports") or {}).items() if st == "open"] or r.get("tls"):
        t = r.get("tls") or {}
        if t.get("error"):
            add("critical", "tls", "TLS : %s" % t["error"])
        else:
            if not t.get("verified"):
                add("critical", "tls", "chaîne de certificat non reconnue par le magasin système (%s)" % (t.get("verify_error") or "?"))
            if t.get("hostname_ok") is False:
                add("critical", "tls", "le certificat ne couvre pas %s" % r.get("host"))
            days = t.get("days_left")
            if days is not None:
                if days < 0:
                    add("critical", "tls", "certificat expiré depuis %d jour(s)" % -days)
                elif days < 14:
                    add("warning", "tls", "certificat expire dans %d jour(s)" % days)
            for v in t.get("legacy_accepted") or []:
                add("warning", "tls", "%s encore accepté" % v)
        h = r.get("https") or {}
        if h.get("error"):
            add("warning", "http", "https : %s" % h["error"])
        elif h.get("headers") is not None:
            present = {k.lower() for k in h["headers"]}
            csp = (h["headers"].get("content-security-policy") or h["headers"].get("Content-Security-Policy") or "")
            for name, (sev, msg) in SECURITY_HEADERS.items():
                if name == "x-frame-options" and "frame-ancestors" in csp:
                    continue
                if name not in present:
                    add(sev, "headers", msg)
            server = h["headers"].get("server") or h["headers"].get("Server")
            if server and any(ch.isdigit() for ch in server):
                add("info", "headers", "en-tête Server révèle une version (%s)" % server[:60])
    hp = r.get("http") or {}
    if hp and not hp.get("error") and hp.get("status") is not None:
        loc = hp.get("location") or ""
        if not (300 <= hp["status"] < 400 and loc.lower().startswith("https://")):
            add("warning", "http", "http (port 80) ne redirige pas vers https (statut %s)" % hp["status"])
    return out


def score(fs):
    """Compte par gravité. Pure."""
    out = {"critical": 0, "warning": 0, "info": 0}
    for f in fs:
        out[f["severity"]] = out.get(f["severity"], 0) + 1
    return out


def cert_dates(cert, now=None):
    """Certificat décodé (dict de getpeercert) -> échéance, jours restants, émetteur. Pure."""
    out = {}
    na = cert.get("notAfter")
    if na:
        exp = _dt.datetime.utcfromtimestamp(ssl.cert_time_to_seconds(na))
        out["not_after"] = exp.strftime("%Y-%m-%d")
        out["days_left"] = (exp - (now or _dt.datetime.utcnow())).days
    out["issuer"] = ", ".join("=".join(x) for rdn in cert.get("issuer") or () for x in rdn)[:160]
    return out


def _decode_der(der):
    """Décode un certificat que la vérification a refusé (pour son échéance)."""
    import os
    import tempfile
    fd, path = tempfile.mkstemp(suffix=".pem")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write(ssl.DER_cert_to_PEM_cert(der))
        return ssl._ssl._test_decode_cert(path)  # noqa: SLF001 -- seul décodeur X.509 de la stdlib
    except (AttributeError, OSError, ssl.SSLError):
        return None
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _tcp(host, port, timeout):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return "open"
    except socket.timeout:
        return "filtered"
    except ConnectionRefusedError:
        return "closed"
    except OSError:
        return "filtered"


def _tls(host, port, timeout, now=None):
    out = {}
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((host, port), timeout=timeout) as raw:
            with ctx.wrap_socket(raw, server_hostname=host) as s:
                cert = s.getpeercert()
                out.update(verified=True, hostname_ok=True, version=s.version(), cipher=(s.cipher() or [None])[0])
    except ssl.SSLCertVerificationError as exc:
        out.update(verified=False, verify_error=getattr(exc, "verify_message", None) or str(exc)[:120],
                   hostname_ok=False if "hostname" in str(exc).lower() else None)
        cert = None
    except (OSError, ssl.SSLError) as exc:
        return {"error": str(exc)[:160]}
    if cert is None:  # chaîne refusée : on relit le certificat sans vérifier pour l'échéance
        try:
            u = ssl._create_unverified_context()  # noqa: SLF001 -- lecture seule du certificat présenté
            with socket.create_connection((host, port), timeout=timeout) as raw:
                with u.wrap_socket(raw, server_hostname=host) as s:
                    out["version"] = s.version()
                    der = s.getpeercert(binary_form=True)
            cert = _decode_der(der) if der else None
        except (OSError, ssl.SSLError):
            pass
    if cert:
        out.update(cert_dates(cert, now))
    legacy = []
    for label, ver in (("TLS 1.0", "TLSv1"), ("TLS 1.1", "TLSv1_1")):
        tv = getattr(ssl.TLSVersion, ver, None)
        if tv is None:
            continue
        try:
            c = ssl._create_unverified_context()  # noqa: SLF001 -- test d'acceptation d'un protocole, aucun échange applicatif
            c.minimum_version = tv
            c.maximum_version = tv
            with socket.create_connection((host, port), timeout=timeout) as raw:
                with c.wrap_socket(raw, server_hostname=host):
                    legacy.append(label)
        except (OSError, ssl.SSLError, ValueError):
            pass
    out["legacy_accepted"] = legacy
    return out


def _http(url, timeout):
    import http.client
    import urllib.parse
    u = urllib.parse.urlsplit(url)
    cls = http.client.HTTPSConnection if u.scheme == "https" else http.client.HTTPConnection
    kw = {"timeout": timeout}
    if u.scheme == "https":
        kw["context"] = ssl._create_unverified_context()  # noqa: SLF001 -- en-têtes seulement ; la chaîne est jugée par _tls
    try:
        c = cls(u.hostname, u.port, **kw)
        c.request("HEAD", u.path or "/", headers={"User-Agent": "si-agent-audit/1 (observation)"})
        r = c.getresponse()
        out = {"status": r.status, "headers": {k.lower(): v for k, v in r.getheaders()}, "location": r.getheader("Location")}
        c.close()
        return out
    except (OSError, http.client.HTTPException) as exc:
        return {"error": str(exc)[:160]}


def audit_target(target, timeout=5, pause=0.2, resolve=socket.getaddrinfo, tcp=_tcp, tls=_tls, http=_http, sleep=time.sleep):
    host = str(target.get("host") or "").strip().lower()
    ports = [int(p) for p in (target.get("ports") or DEFAULT_PORTS)][:MAX_PORTS]
    r = {"host": host, "at": int(time.time()), "ports": {}, "addresses": []}
    try:
        r["addresses"] = sorted({ai[4][0] for ai in resolve(host, None)})
    except (OSError, UnicodeError) as exc:
        r["error"] = "résolution DNS impossible : %s" % exc
    if not r.get("error"):
        for p in ports:
            r["ports"][str(p)] = tcp(host, p, timeout)
            sleep(pause)
        if r["ports"].get("443") == "open":
            r["tls"] = tls(host, 443, timeout)
            r["https"] = http("https://%s/" % host, timeout)
        if r["ports"].get("80") == "open":
            r["http"] = http("http://%s/" % host, timeout)
    r["findings"] = findings(r)
    r["score"] = score(r["findings"])
    return r
