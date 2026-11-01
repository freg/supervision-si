#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « audit d'application web » (livraison #617, famille explorer) --
depuis le poste de l'utilisateur, rejoue l'accès à une application web et
décompose ce qu'il subit, pour objectiver un « ça marche à moitié » :

par URL : résolution DNS (durée, adresses), connexion TCP, poignée de main
TLS (version, expiration du certificat, erreur), premier octet (TTFB),
téléchargement complet (durée, taille, code, type, serveur), chaîne de
redirections ; puis les sous-ressources de la page (scripts, styles, images,
au plus --max-sub) chacune avec son code et sa durée -- une page « qui
s'affiche » mais dont l'API ou le script échoue se voit ici.

Constats : dns-failed, connect-failed, tls-failed, http-error (5xx),
http-client-error (4xx), slow-ttfb (> --slow-ttfb s), slow-total (> --slow
s), sub-errors (sous-ressources en échec), sub-slow, cert-expiring (< 15 j),
redirect-chain (> 3), empty-body, mixed-content (http dans une page https).
Lecture seule, aucune authentification : une application derrière une
connexion renverra sa page de connexion (302/401), ce qui est déjà une
information. Stdlib seulement (Windows sans dépendance).

Usage : web_audit.py --urls https://a/,https://b/ [--timeout 10] [--max-sub 25]
        [--slow 5] [--slow-ttfb 1.5] [--no-sub] ; ou --urls-file chemin.txt
        (une URL par ligne, # commentaires) ; sans --urls : %ProgramData%\\si-agent\\web-audit.txt
        ou /etc/si-agent/web-audit.txt s'il existe.
"""
import argparse
import http.client
import json
import os
import socket
import ssl
import sys
import time
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

MAX_REDIRECTS = 5
SUB_TAGS = {"script": "src", "link": "href", "img": "src", "iframe": "src"}


class _SubParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = []
        self.title = ""
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "title":
            self._in_title = True
        if tag == "link" and (a.get("rel") or "").lower() not in ("stylesheet", "preload", "icon", "shortcut icon"):
            return
        attr = SUB_TAGS.get(tag)
        if attr and a.get(attr) and not a[attr].startswith(("data:", "javascript:", "#")):
            self.found.append((tag, a[attr]))

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data.strip()[:120]


def parse_subresources(html, base_url, limit=25):
    """-> [(tag, url absolue)] dédoublonnés, dans l'ordre du document."""
    p = _SubParser()
    try:
        p.feed(html)
    except Exception:  # noqa: BLE001 -- HTML cassé : on garde ce qui a été lu
        pass
    seen, out = set(), []
    for tag, ref in p.found:
        u = urljoin(base_url, ref.strip())
        if u.startswith(("http://", "https://")) and u not in seen:
            seen.add(u); out.append((tag, u))
        if len(out) >= limit:
            break
    return out, p.title


def _cert_days_left(cert):
    try:
        exp = ssl.cert_time_to_seconds(cert.get("notAfter"))
        return int((exp - time.time()) // 86400)
    except (TypeError, ValueError, AttributeError):
        return None


def fetch_one(url, timeout=10.0, method="GET", max_body=2_000_000, want_body=True, clock=time.perf_counter):
    """Une requête HTTP(S) décomposée. -> dict (jamais d'exception)."""
    r = {"url": url, "method": method, "dns_ms": None, "connect_ms": None, "tls_ms": None, "ttfb_ms": None, "total_ms": None,
         "status": None, "bytes": 0, "content_type": None, "server": None, "location": None, "error": None, "tls": None, "addresses": []}
    parts = urlsplit(url)
    host = parts.hostname
    if not host:
        r["error"] = "URL invalide"; return r, None
    port = parts.port or (443 if parts.scheme == "https" else 80)
    path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
    t0 = clock()
    try:
        infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        r["addresses"] = sorted({i[4][0] for i in infos})[:4]
        r["dns_ms"] = round((clock() - t0) * 1000, 1)
    except socket.gaierror as exc:
        r["error"] = "dns-failed: %s" % exc; r["dns_ms"] = round((clock() - t0) * 1000, 1); return r, None
    t1 = clock()
    sock = None
    try:
        sock = socket.create_connection((host, port), timeout=timeout)
        r["connect_ms"] = round((clock() - t1) * 1000, 1)
    except OSError as exc:
        r["error"] = "connect-failed: %s" % exc; r["connect_ms"] = round((clock() - t1) * 1000, 1); return r, None
    conn = None
    try:
        if parts.scheme == "https":
            t2 = clock()
            ctx = ssl.create_default_context()
            try:
                ssock = ctx.wrap_socket(sock, server_hostname=host)
            except (ssl.SSLError, OSError) as exc:
                r["error"] = "tls-failed: %s" % getattr(exc, "reason", None) or str(exc); r["tls_ms"] = round((clock() - t2) * 1000, 1); return r, None
            r["tls_ms"] = round((clock() - t2) * 1000, 1)
            cert = ssock.getpeercert() or {}
            r["tls"] = {"version": ssock.version(), "cert_days_left": _cert_days_left(cert), "issuer": " ".join(v for t in cert.get("issuer", ()) for k, v in t if k == "organizationName")[:80]}
            conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
            conn.sock = ssock
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
            conn.sock = sock
        t3 = clock()
        conn.putrequest(method, path or "/", skip_accept_encoding=True)
        conn.putheader("Host", parts.netloc)
        conn.putheader("User-Agent", "si-agent web-audit/1")
        conn.putheader("Accept", "*/*")
        conn.putheader("Connection", "close")
        conn.endheaders()
        resp = conn.getresponse()
        r["ttfb_ms"] = round((clock() - t3) * 1000, 1)
        r["status"] = resp.status
        r["content_type"] = (resp.getheader("Content-Type") or "").split(";")[0].strip() or None
        r["server"] = (resp.getheader("Server") or "")[:60] or None
        r["location"] = resp.getheader("Location")
        body = b""
        if want_body:
            while True:
                chunk = resp.read(65536)
                if not chunk:
                    break
                body += chunk
                if len(body) >= max_body:
                    break
        else:
            resp.read(1)
        r["bytes"] = len(body)
        r["total_ms"] = round((clock() - t0) * 1000, 1)
        return r, body
    except (OSError, http.client.HTTPException) as exc:
        r["error"] = "http-failed: %s" % exc; r["total_ms"] = round((clock() - t0) * 1000, 1); return r, None
    finally:
        try:
            (conn.close() if conn else sock.close())
        except Exception:  # noqa: BLE001
            pass


def audit_url(url, timeout=10.0, max_sub=25, with_sub=True, fetch=fetch_one):
    """URL -> {final_url, chain, main, subresources, title}."""
    chain, current, body, main = [], url, None, None
    for _ in range(MAX_REDIRECTS + 1):
        main, body = fetch(current, timeout=timeout)
        chain.append({"url": current, "status": main.get("status"), "ms": main.get("total_ms")})
        if main.get("status") in (301, 302, 303, 307, 308) and main.get("location"):
            current = urljoin(current, main["location"]); body = None
            continue
        break
    out = {"url": url, "final_url": current, "chain": chain, "main": main, "subresources": [], "title": ""}
    if with_sub and body and (main.get("content_type") or "").startswith("text/html"):
        try:
            html = body.decode("utf-8", "replace")
        except Exception:  # noqa: BLE001
            html = ""
        subs, title = parse_subresources(html, current, limit=max_sub)
        out["title"] = title
        for tag, su in subs:
            sr, _ = fetch(su, timeout=timeout, want_body=False)
            out["subresources"].append({"tag": tag, "url": su, "status": sr.get("status"), "ms": sr.get("total_ms") or sr.get("ttfb_ms"), "error": sr.get("error")})
    return out


def findings_for(res, slow=5.0, slow_ttfb=1.5):
    """Constats d'une URL auditée -> [{code, severity, detail}]."""
    f = []
    m = res.get("main") or {}
    err = m.get("error") or ""
    if err.startswith("dns-failed"):
        f.append({"code": "dns-failed", "severity": "critical", "detail": err})
    elif err.startswith("connect-failed"):
        f.append({"code": "connect-failed", "severity": "critical", "detail": err})
    elif err.startswith("tls-failed"):
        f.append({"code": "tls-failed", "severity": "critical", "detail": err})
    elif err:
        f.append({"code": "http-failed", "severity": "critical", "detail": err})
    st = m.get("status")
    if st is not None and st >= 500:
        f.append({"code": "http-error", "severity": "critical", "detail": "code %s" % st})
    elif st is not None and st >= 400:
        f.append({"code": "http-client-error", "severity": "warning", "detail": "code %s" % st})
    if (m.get("ttfb_ms") or 0) > slow_ttfb * 1000:
        f.append({"code": "slow-ttfb", "severity": "warning", "detail": "premier octet en %.1f s" % (m["ttfb_ms"] / 1000)})
    if (m.get("total_ms") or 0) > slow * 1000:
        f.append({"code": "slow-total", "severity": "warning", "detail": "page en %.1f s" % (m["total_ms"] / 1000)})
    if st == 200 and not m.get("bytes"):
        f.append({"code": "empty-body", "severity": "warning", "detail": "réponse vide"})
    if len(res.get("chain") or []) > 4:
        f.append({"code": "redirect-chain", "severity": "info", "detail": "%d redirections" % (len(res["chain"]) - 1)})
    days = (m.get("tls") or {}).get("cert_days_left")
    if days is not None and days < 15:
        f.append({"code": "cert-expiring", "severity": "warning" if days >= 0 else "critical", "detail": "certificat expire dans %d j" % days})
    subs = res.get("subresources") or []
    bad = [s for s in subs if s.get("error") or (s.get("status") or 0) >= 400]
    if bad:
        f.append({"code": "sub-errors", "severity": "warning" if len(bad) < len(subs) else "critical",
                  "detail": "%d/%d sous-ressource(s) en échec : %s" % (len(bad), len(subs), ", ".join(urlsplit(s["url"]).path.rsplit("/", 1)[-1][:40] or s["url"] for s in bad[:5]))})
    slow_subs = [s for s in subs if (s.get("ms") or 0) > slow_ttfb * 1000]
    if slow_subs:
        f.append({"code": "sub-slow", "severity": "info", "detail": "%d sous-ressource(s) > %.1f s" % (len(slow_subs), slow_ttfb)})
    if res.get("final_url", "").startswith("https://") and any(s["url"].startswith("http://") for s in subs):
        f.append({"code": "mixed-content", "severity": "warning", "detail": "ressources http dans une page https"})
    return f


def collect(urls, timeout=10.0, max_sub=25, with_sub=True, slow=5.0, slow_ttfb=1.5, fetch=fetch_one):
    results, all_f = [], []
    for u in urls:
        res = audit_url(u, timeout=timeout, max_sub=max_sub, with_sub=with_sub, fetch=fetch)
        res["findings"] = findings_for(res, slow=slow, slow_ttfb=slow_ttfb)
        res["state"] = "critical" if any(x["severity"] == "critical" for x in res["findings"]) else "warning" if any(x["severity"] == "warning" for x in res["findings"]) else "ok"
        results.append(res); all_f.extend(dict(x, url=u) for x in res["findings"])
    return {"urls": results, "findings": all_f, "collected_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "summary": {"total": len(results), "ok": sum(1 for r in results if r["state"] == "ok"), "warning": sum(1 for r in results if r["state"] == "warning"),
                        "critical": sum(1 for r in results if r["state"] == "critical"),
                        "state": "critical" if any(r["state"] == "critical" for r in results) else "warning" if any(r["state"] == "warning" for r in results) else "ok"}}


def load_urls(args):
    urls = [u.strip() for u in (args.urls or "").split(",") if u.strip()]
    path = args.urls_file
    if not urls and not path:
        for cand in (os.path.join(os.environ.get("ProgramData", ""), "si-agent", "web-audit.txt") if os.name == "nt" else "/etc/si-agent/web-audit.txt",):
            if cand and os.path.exists(cand):
                path = cand
    if path and os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            urls += [l.strip() for l in fh if l.strip() and not l.startswith("#")]
    return [u if u.startswith(("http://", "https://")) else "https://" + u for u in urls]


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("--urls", default="")
    ap.add_argument("--urls-file", default="")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--max-sub", type=int, default=25)
    ap.add_argument("--no-sub", action="store_true")
    ap.add_argument("--slow", type=float, default=5.0)
    ap.add_argument("--slow-ttfb", type=float, default=1.5)
    args = ap.parse_args(argv)
    urls = load_urls(args)
    if not urls:
        print(json.dumps({"error": "aucune URL : --urls a,b ou fichier web-audit.txt", "urls": [], "findings": [], "summary": {"total": 0, "state": "unknown"}}))
        return 0
    try:
        print(json.dumps(collect(urls, timeout=args.timeout, max_sub=args.max_sub, with_sub=not args.no_sub, slow=args.slow, slow_ttfb=args.slow_ttfb)))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": "audit échoué : %s" % exc}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
