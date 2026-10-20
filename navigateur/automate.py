#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Navigateur de l'hôte (livraison #798) : petite API locale qui pilote LE Chromium visible (écran web noVNC) par
Playwright (CDP, 127.0.0.1:9222). Ce que fait l'automate se voit en direct dans l'écran du hub, et on peut reprendre
la main à la souris à tout moment. Appelée par l'agent si-agent de l'hôte (commande « navigateur »), jamais exposée :
écoute 127.0.0.1 seulement, jeton obligatoire (NAV_JETON).

GET  /etat                         navigateur joignable, onglet courant (URL, titre), taille de l'écran
POST /aller {url}                  ouvre l'adresse dans l'onglet courant
GET  /capture?qualite=60           capture JPEG de l'onglet courant (base64)
POST /etapes {base_url?, etapes[]} joue des étapes au format QA (goto, click, fill, select, check, press, wait,
                                   expect_visible|absent|text|url|value, screenshot), capture à l'échec et à la fin
Pur (testé sans navigateur) : verifier_etapes, jouer (page injectée)."""
import base64
import hmac
import json
import os
import re
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from threading import Lock
from urllib.parse import parse_qs, urlparse

CDP = os.environ.get("NAV_CDP", "http://127.0.0.1:9222")
JETON = os.environ.get("NAV_JETON", "")
DELAI_MS = int(os.environ.get("NAV_DELAI_MS", "15000"))
ACTIONS = {
    "goto": ("value",), "click": ("selector",), "fill": ("selector", "value"), "select": ("selector", "value"), "check": ("selector",),
    "press": ("selector", "value"), "wait": ("value",), "expect_visible": ("selector",), "expect_text": ("value",),
    "expect_url": ("value",), "expect_value": ("selector", "value"), "expect_absent": ("selector",), "screenshot": (),
}
VERROU = Lock()   # un seul automate à la fois sur le navigateur visible


def abs_url(base, v):
    return v if re.match(r"^[a-z]+://", v or "") else (base or "").rstrip("/") + "/" + (v or "").lstrip("/")


def verifier_etapes(etapes):
    """Liste d'étapes au format QA -> liste nettoyée, ou ValueError (numéro, champ manquant)."""
    if not isinstance(etapes, list) or not etapes:
        raise ValueError("etapes : liste non vide attendue")
    if len(etapes) > 200:
        raise ValueError("200 étapes au plus")
    out = []
    for i, s in enumerate(etapes, 1):
        if not isinstance(s, dict):
            raise ValueError("étape %d : objet attendu" % i)
        a = str(s.get("action") or "").strip()
        if a not in ACTIONS:
            raise ValueError("étape %d : action inconnue « %s »" % (i, a))
        st = {"action": a, "selector": str(s.get("selector") or "").strip(), "value": "" if s.get("value") is None else str(s.get("value")),
              "note": str(s.get("note") or "")[:200], "ecrit": bool(s.get("ecrit"))}
        for f in ACTIONS[a]:
            if f == "selector" and not st["selector"]:
                raise ValueError("étape %d (%s) : sélecteur manquant" % (i, a))
            if f == "value" and st["value"] == "" and a != "expect_text":
                raise ValueError("étape %d (%s) : valeur manquante" % (i, a))
        if a == "wait" and not re.fullmatch(r"\d{1,6}", st["value"]):
            raise ValueError("étape %d : durée en millisecondes attendue" % i)
        out.append(st)
    return out


def capture(page, qualite=60):
    try:
        return base64.b64encode(page.screenshot(type="jpeg", quality=max(20, min(90, int(qualite))))).decode()
    except Exception:  # noqa: BLE001
        return ""


def jouer(page, etapes, base_url="", arret_avant_ecriture=False, delai_ms=DELAI_MS):
    """Joue les étapes sur `page` (Playwright ou simulée). -> {statut, resultats[], url, titre, capture}.
    arret_avant_ecriture : s'arrête (statut « confirmation ») AVANT la première étape marquée `ecrit`."""
    page.set_default_timeout(delai_ms)
    res = []
    statut = "ok"
    for i, st in enumerate(etapes, 1):
        if arret_avant_ecriture and st.get("ecrit"):
            statut = "confirmation"
            res.append({"index": i, "action": st["action"], "ok": None, "attente": True, "note": st.get("note") or "étape qui écrit : confirmation attendue"})
            break
        t0 = time.time()
        ok, err = True, ""
        a, sel, val = st["action"], st.get("selector", ""), st.get("value", "")
        try:
            if a == "goto":
                page.goto(abs_url(base_url, val), wait_until="domcontentloaded")
            elif a == "click":
                page.click(sel); page.wait_for_load_state("domcontentloaded")
            elif a == "fill":
                page.fill(sel, val)
            elif a == "select":
                page.select_option(sel, val)
            elif a == "check":
                page.check(sel)
            elif a == "press":
                page.press(sel, val); page.wait_for_load_state("domcontentloaded")
            elif a == "wait":
                page.wait_for_timeout(int(val))
            elif a == "expect_visible":
                page.wait_for_selector(sel, state="visible")
            elif a == "expect_absent":
                page.wait_for_selector(sel, state="detached")
            elif a == "expect_text":
                txt = page.inner_text(sel or "body")
                if val not in txt:
                    ok, err = False, "texte « %s » absent" % val
            elif a == "expect_url":
                if val not in page.url:
                    ok, err = False, "URL « %s » ne contient pas « %s »" % (page.url, val)
            elif a == "expect_value":
                v = page.input_value(sel)
                if v != val:
                    ok, err = False, "valeur « %s » au lieu de « %s »" % (v, val)
        except Exception as e:  # noqa: BLE001 -- délai dépassé, sélecteur introuvable…
            ok, err = False, "%s : %s" % (type(e).__name__, str(e).split("\n")[0][:200])
        r = {"index": i, "action": a, "ok": ok, "error": err, "duree_ms": int((time.time() - t0) * 1000)}
        if not ok or a == "screenshot":
            r["capture"] = capture(page)
        res.append(r)
        if not ok:
            statut = "ko"
            break
    fin = {"statut": statut, "resultats": res, "url": getattr(page, "url", ""), "capture": capture(page)}
    try:
        fin["titre"] = page.title()
    except Exception:  # noqa: BLE001
        fin["titre"] = ""
    return fin


class Navigateur:
    """Connexion CDP au Chromium visible, refaite si le navigateur a été relancé."""
    def __init__(self, cdp=CDP):
        self.cdp, self._pw, self._b = cdp, None, None

    def page(self):
        from playwright.sync_api import sync_playwright
        if self._b is None or not self._b.is_connected():
            if self._pw is None:
                self._pw = sync_playwright().start()
            self._b = self._pw.chromium.connect_over_cdp(self.cdp)
        ctx = self._b.contexts[0] if self._b.contexts else self._b.new_context()
        pages = [p for p in ctx.pages if not p.url.startswith("devtools://")]
        return pages[-1] if pages else ctx.new_page()


def servir(port=8094, nav=None):
    if len(JETON) < 16:
        raise SystemExit("NAV_JETON (16 caractères au moins) requis")
    nav = nav or Navigateur()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _rep(self, code, obj):
            b = json.dumps(obj, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def _ok(self):
            return hmac.compare_digest(self.headers.get("Authorization", ""), "Bearer " + JETON)

        def _traiter(self, m):
            if not self._ok():
                return self._rep(401, {"error": "jeton requis"})
            u = urlparse(self.path)
            try:
                corps = {}
                if m == "POST":
                    n = int(self.headers.get("Content-Length") or 0)
                    corps = json.loads(self.rfile.read(n) or b"{}") if n else {}
                with VERROU:
                    p = nav.page()
                    if m == "GET" and u.path == "/etat":
                        return self._rep(200, {"ok": True, "url": p.url, "titre": p.title(), "ecran": p.viewport_size})
                    if m == "GET" and u.path == "/capture":
                        q = int((parse_qs(u.query).get("qualite") or ["60"])[0])
                        return self._rep(200, {"ok": True, "url": p.url, "capture": capture(p, q)})
                    if m == "POST" and u.path == "/aller":
                        url = str(corps.get("url") or "")
                        if not re.match(r"^https?://", url):
                            raise ValueError("adresse http(s) attendue")
                        p.goto(url, wait_until="domcontentloaded", timeout=DELAI_MS)
                        return self._rep(200, {"ok": True, "url": p.url, "titre": p.title(), "capture": capture(p)})
                    if m == "POST" and u.path == "/etapes":
                        et = verifier_etapes(corps.get("etapes"))
                        r = jouer(p, et, str(corps.get("base_url") or ""), bool(corps.get("arret_avant_ecriture")))
                        return self._rep(200, dict(r, ok=r["statut"] != "ko"))
                return self._rep(404, {"error": "inconnu"})
            except ValueError as e:
                return self._rep(400, {"error": str(e)})
            except Exception as e:  # noqa: BLE001
                return self._rep(502, {"error": "navigateur : %s" % str(e).split("\n")[0][:300]})

        def do_GET(self):
            self._traiter("GET")

        def do_POST(self):
            self._traiter("POST")

    print("automate du navigateur sur 127.0.0.1:%d (CDP %s)" % (port, CDP), flush=True)
    HTTPServer(("127.0.0.1", port), H).serve_forever()   # un seul fil : Playwright (sync) reste dans le fil qui l'a démarré


if __name__ == "__main__":
    servir(int(sys.argv[1]) if len(sys.argv) > 1 else 8094)
