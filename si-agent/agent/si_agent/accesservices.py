# -*- coding: utf-8 -*-
"""#928 : mesure, depuis le poste, du temps d'accès aux sites de service de l'entreprise (GED, cloud, annuaire,
tickets…). Pour chaque cible : temps d'accès BRUT (requête simple, sans authentification -- DNS, connexion, TLS,
premier octet, total, code) PUIS, si un accès du coffre est fourni, temps de chargement en PASSANT l'authentification
(formulaire avec jeton anti-CSRF, HTTP Basic, ou en-tête de jeton), jusqu'à la page connectée.

Principe de sécurité : le secret n'arrive ici qu'en mémoire (injecté par le hub depuis le coffre dans la commande) ;
il n'est JAMAIS écrit en sortie, ni dans une trace, ni sur une ligne de commande (pas de sous-processus). Les messages
d'erreur sont nettoyés de toute chaîne de requête. Stdlib seulement (Windows sans dépendance).

Entrée : cibles = [{"nom", "url", "auth": {"type": "aucun"|"form"|"basic"|"token", …}}].
  form  : {"url_login"?, "champ_user", "champ_pass", "user", "secret", "champs"?: {...}, "marqueur_connecte"?, "marqueur_echec"?}
  basic : {"user", "secret"}
  token : {"entete"?: "Authorization", "valeur": "Bearer <secret>"}  (le hub compose la valeur avec le secret)
Sortie : {"at", "sites": [{"nom", "hote", "brut": {...}, "authentifie": {...}|None, "constats": [...]}]}.
"""
import base64
import http.cookiejar
import json
import re
import socket
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from urllib.parse import urlsplit, urljoin

TIMEOUT = 10.0
MAX_BODY = 1_000_000
SLOW_BRUT = 2.0      # s : accès brut lent
SLOW_AUTH = 5.0      # s : chargement authentifié lent


def _hote(url):
    try:
        return urlsplit(url).hostname or url
    except ValueError:
        return url


def _sans_requete(url):
    """URL sans la chaîne de requête ni le fragment (une erreur ne doit pas recracher un éventuel jeton d'URL)."""
    try:
        p = urlsplit(url)
        return "%s://%s%s" % (p.scheme, p.netloc, p.path)
    except ValueError:
        return "(url)"


def _err(exc, url):
    return ("%s: %s" % (type(exc).__name__, exc)).replace(url, _sans_requete(url))[:200]


def mesure_brute(url, timeout=TIMEOUT, clock=time.perf_counter):
    """Requête HTTP(S) simple, SANS authentification et SANS suivre les redirections : temps d'accès brut décomposé.
    -> {dns_ms, connect_ms, tls_ms, ttfb_ms, total_ms, status, location, serveur, tls, erreur}."""
    r = {"dns_ms": None, "connect_ms": None, "tls_ms": None, "ttfb_ms": None, "total_ms": None,
         "status": None, "location": None, "serveur": None, "tls": None, "erreur": None}
    try:
        parts = urlsplit(url)
    except ValueError as exc:
        r["erreur"] = "url-invalide: %s" % exc
        return r
    host, scheme = parts.hostname, parts.scheme
    if not host or scheme not in ("http", "https"):
        r["erreur"] = "url-invalide"
        return r
    port = parts.port or (443 if scheme == "https" else 80)
    path = (parts.path or "/") + (("?" + parts.query) if parts.query else "")
    import http.client
    t0 = clock()
    try:
        socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
        r["dns_ms"] = round((clock() - t0) * 1000, 1)
    except socket.gaierror as exc:
        r["erreur"] = "dns-echec: %s" % exc
        r["dns_ms"] = round((clock() - t0) * 1000, 1)
        return r
    conn = None
    try:
        t1 = clock()
        if scheme == "https":
            ctx = ssl.create_default_context()
            conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
            conn.connect()
            r["connect_ms"] = round((clock() - t1) * 1000, 1)
            try:
                cert = conn.sock.getpeercert()
                r["tls"] = {"version": conn.sock.version()}
                r["tls_ms"] = r["connect_ms"]
                _ = cert
            except (AttributeError, ValueError):
                pass
        else:
            conn = http.client.HTTPConnection(host, port, timeout=timeout)
            conn.connect()
            r["connect_ms"] = round((clock() - t1) * 1000, 1)
        t2 = clock()
        conn.putrequest("GET", path, skip_accept_encoding=True)
        conn.putheader("Host", parts.netloc)
        conn.putheader("User-Agent", "si-agent/acces-services")
        conn.putheader("Accept", "*/*")
        conn.putheader("Connection", "close")
        conn.endheaders()
        resp = conn.getresponse()
        r["ttfb_ms"] = round((clock() - t2) * 1000, 1)
        r["status"] = resp.status
        r["location"] = resp.getheader("Location")
        r["serveur"] = resp.getheader("Server")
        resp.read(MAX_BODY)
        r["total_ms"] = round((clock() - t1) * 1000, 1)
    except (OSError, ssl.SSLError, http.client.HTTPException) as exc:
        r["erreur"] = _err(exc, url)
    finally:
        if conn is not None:
            try:
                conn.close()
            except OSError:
                pass
    return r


class _Formulaire(HTMLParser):
    """Récupère le premier <form> et ses champs cachés (jeton anti-CSRF compris)."""
    def __init__(self):
        super().__init__()
        self.action = None
        self.method = "post"
        self.champs = {}
        self._dans = False
        self._fini = False

    def handle_starttag(self, tag, attrs):
        if self._fini:
            return
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "form" and not self._dans:
            self._dans = True
            self.action = a.get("action") or ""
            self.method = (a.get("method") or "post").lower()
        elif tag == "input" and self._dans and a.get("name"):
            self.champs[a["name"]] = a.get("value", "")

    def handle_endtag(self, tag):
        if tag == "form" and self._dans:
            self._fini = True


def _opener(timeout):
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "si-agent/acces-services")]
    return op


def _lire(op, url, timeout, data=None, entetes=None):
    req = urllib.request.Request(url, data=data, headers=entetes or {})
    with op.open(req, timeout=timeout) as resp:
        corps = resp.read(MAX_BODY)
        return resp.getcode(), resp.geturl(), corps.decode("utf-8", "replace")


def mesure_auth(url, auth, timeout=TIMEOUT, clock=time.perf_counter, opener_factory=_opener):
    """Chargement en passant l'authentification, jusqu'à la page connectée.
    -> {total_ms, status, connecte, url_finale, erreur}. Le secret n'apparaît jamais en sortie."""
    r = {"total_ms": None, "status": None, "connecte": None, "url_finale": None, "erreur": None}
    typ = str((auth or {}).get("type") or "aucun")
    op = opener_factory(timeout)
    t0 = clock()
    try:
        if typ == "basic":
            jeton = base64.b64encode(("%s:%s" % (auth.get("user", ""), auth.get("secret", ""))).encode()).decode()
            code, fin, corps = _lire(op, url, timeout, entetes={"Authorization": "Basic " + jeton})
        elif typ == "token":
            entete = auth.get("entete") or "Authorization"
            code, fin, corps = _lire(op, url, timeout, entetes={entete: auth.get("valeur", "")})
        elif typ == "form":
            url_login = auth.get("url_login") or url
            _, fin_login, page = _lire(op, url_login, timeout)
            f = _Formulaire()
            try:
                f.feed(page)
            except Exception:  # noqa: BLE001 -- HTML cassé : on poste ce qu'on a
                pass
            donnees = dict(f.champs)                       # champs cachés (CSRF) conservés
            donnees[auth["champ_user"]] = auth.get("user", "")
            donnees[auth["champ_pass"]] = auth.get("secret", "")
            donnees.update(auth.get("champs") or {})       # champs fixes supplémentaires (domaine…)
            action = urljoin(fin_login, f.action) if f.action else url_login
            donnees_enc = urllib.parse.urlencode(donnees).encode()
            code, fin, corps = _lire(op, action, timeout, data=donnees_enc,
                                     entetes={"Content-Type": "application/x-www-form-urlencoded"})
            if fin == url or url in (fin, action):         # déjà sur la cible
                pass
            else:
                code, fin, corps = _lire(op, url, timeout)  # charger la page protégée avec la session ouverte
        else:
            code, fin, corps = _lire(op, url, timeout)
        r["total_ms"] = round((clock() - t0) * 1000, 1)
        r["status"] = code
        r["url_finale"] = _sans_requete(fin)
        r["connecte"] = _connecte(auth, code, fin, url, corps)
    except urllib.error.HTTPError as exc:
        r["total_ms"] = round((clock() - t0) * 1000, 1)
        r["status"] = exc.code
        r["connecte"] = False
        r["erreur"] = "http-%d" % exc.code
    except (urllib.error.URLError, OSError, ssl.SSLError, ValueError) as exc:
        r["total_ms"] = round((clock() - t0) * 1000, 1)
        r["erreur"] = _err(exc, url)
    return r


def _connecte(auth, code, url_finale, url_cible, corps):
    """Heuristique « la session est ouverte » : marqueur de succès/échec explicite sinon code 2xx et pas renvoyé au login."""
    bas = (corps or "").lower()
    me = str((auth or {}).get("marqueur_echec") or "")
    if me and me.lower() in bas:
        return False
    mc = str((auth or {}).get("marqueur_connecte") or "")
    if mc:
        return mc.lower() in bas
    if code is None or code >= 400:
        return False
    login = str((auth or {}).get("url_login") or "")
    if login and _hote(url_finale) == _hote(login) and urlsplit(url_finale).path == urlsplit(login).path and url_finale != url_cible:
        return False      # ramené à la page de connexion -> échec
    return code < 400


def _constats(nom, brut, auth):
    out = []
    if brut.get("erreur"):
        out.append({"code": "acces-brut-echec", "severity": "critical", "message": "%s : accès injoignable (%s)" % (nom, brut["erreur"])})
    elif isinstance(brut.get("total_ms"), (int, float)) and brut["total_ms"] / 1000.0 >= SLOW_BRUT:
        out.append({"code": "acces-brut-lent", "severity": "warning", "message": "%s : accès brut lent (%.1f s)" % (nom, brut["total_ms"] / 1000.0)})
    if auth is not None:
        if auth.get("erreur"):
            out.append({"code": "acces-auth-echec", "severity": "critical", "message": "%s : authentification en échec (%s)" % (nom, auth["erreur"])})
        elif auth.get("connecte") is False:
            out.append({"code": "acces-auth-refuse", "severity": "critical", "message": "%s : identifiants refusés ou page de connexion renvoyée" % nom})
        elif isinstance(auth.get("total_ms"), (int, float)) and auth["total_ms"] / 1000.0 >= SLOW_AUTH:
            out.append({"code": "acces-auth-lent", "severity": "warning", "message": "%s : chargement authentifié lent (%.1f s)" % (nom, auth["total_ms"] / 1000.0)})
    return out


def mesurer(cibles, timeout=TIMEOUT, clock=time.perf_counter, opener_factory=_opener):
    """Mesure chaque cible (brut puis, si auth fournie, authentifié). Ne renvoie aucun secret."""
    sites, constats = [], []
    for c in cibles or []:
        nom = str(c.get("nom") or _hote(c.get("url") or "?"))
        url = str(c.get("url") or "")
        auth = c.get("auth") if isinstance(c.get("auth"), dict) else None
        brut = mesure_brute(url, timeout, clock)
        authm = None
        if auth and str(auth.get("type") or "aucun") != "aucun" and not brut.get("erreur"):
            authm = mesure_auth(url, auth, timeout, clock, opener_factory)
        cs = _constats(nom, brut, authm)
        constats += cs
        sites.append({"nom": nom, "hote": _hote(url), "url": _sans_requete(url),
                      "auth_type": (auth or {}).get("type") or "aucun", "brut": brut, "authentifie": authm, "constats": cs})
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "sites": sites, "alerts": constats}


if __name__ == "__main__":
    # Essai manuel : python3 -m si_agent.accesservices '[{"nom":"ex","url":"https://example.org/"}]'
    arg = sys.argv[1] if len(sys.argv) > 1 else "[]"
    print(json.dumps(mesurer(json.loads(arg)), ensure_ascii=False, indent=2))
