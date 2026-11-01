#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Navigateur de l'hôte (livraison #798) : petite API locale qui pilote LE Chromium visible (écran web noVNC) par
Playwright (CDP, 127.0.0.1:9222). Ce que fait l'automate se voit en direct dans l'écran du hub, et on peut reprendre
la main à la souris à tout moment. Appelée par l'agent si-agent de l'hôte (commande « navigateur »), jamais exposée :
écoute 127.0.0.1 seulement, jeton obligatoire (NAV_JETON).

GET  /etat                         navigateur joignable, onglet courant (URL, titre), taille de l'écran
POST /aller {url}                  ouvre l'adresse dans l'onglet courant
GET  /capture?qualite=60           capture JPEG de l'onglet courant (base64)
POST /enregistrer {etape: debut|etat|fin}  apprentissage : gestes faits dans l'écran -> étapes paramétrées (#799)
POST /etapes {base_url?, etapes[]} joue des étapes au format QA (goto, click, fill, select, check, press, wait,
                                   expect_visible|absent|text|url|value, screenshot), capture à l'échec et à la fin
Pur (testé sans navigateur) : verifier_etapes, jouer (page injectée), nettoyer_enregistrement, parametrer."""
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


# #799 : apprentissage d'un parcours -- script injecté dans chaque page du navigateur visible ; chaque geste (clic,
# saisie, choix, case, Entrée) devient une étape QA avec un sélecteur aussi stable que possible, envoyée à l'automate
# par la liaison « __qaEnregistre » (ignorée hors enregistrement).
RECORDER_JS = r"""
(() => {
  if (window.__qaRecInstalle || !window.__qaEnregistre) return;
  window.__qaRecInstalle = true;
  const ECRIT = /(enregistr|cr[ée]er|valid|envoy|soumet|supprim|ajout|confirm|save|create|submit|delete|send|publish|publier)/i;
  const dyn = (v) => !v || /\d{4,}|[0-9a-f]{8,}|^(ember|react|ng|mui|css)-/i.test(v);
  const esc = (v) => String(v).replace(/"/g, '\\"');
  const texte = (el) => (el.innerText || el.value || "").trim().replace(/\s+/g, " ").slice(0, 60);
  function etiquette(el) {
    if (el.id) { const l = document.querySelector('label[for="' + esc(el.id) + '"]'); if (l) return texte(l); }
    const p = el.closest("label"); if (p) return texte(p);
    return el.getAttribute("aria-label") || el.getAttribute("placeholder") || el.getAttribute("name") || "";
  }
  function selecteur(el) {
    for (const a of ["data-testid", "data-test", "data-qa"]) if (el.getAttribute(a)) return "[" + a + '="' + esc(el.getAttribute(a)) + '"]';
    if (el.id && !dyn(el.id)) return "#" + CSS.escape(el.id);
    const tag = el.tagName.toLowerCase();
    if (el.getAttribute("name") && !dyn(el.getAttribute("name"))) return tag + '[name="' + esc(el.getAttribute("name")) + '"]';
    if (el.getAttribute("aria-label")) return tag + '[aria-label="' + esc(el.getAttribute("aria-label")) + '"]';
    if (["button", "a"].includes(tag) || el.getAttribute("role") === "button") { const t = texte(el); if (t && t.length <= 40) return tag + ':has-text("' + esc(t) + '")'; }
    if (el.getAttribute("placeholder")) return tag + '[placeholder="' + esc(el.getAttribute("placeholder")) + '"]';
    const parts = []; let e = el;
    while (e && e.nodeType === 1 && parts.length < 5 && e !== document.body) {
      let s = e.tagName.toLowerCase();
      if (e.id && !dyn(e.id)) { parts.unshift("#" + CSS.escape(e.id)); break; }
      const freres = e.parentElement ? [...e.parentElement.children].filter((x) => x.tagName === e.tagName) : [];
      if (freres.length > 1) s += ":nth-of-type(" + (freres.indexOf(e) + 1) + ")";
      parts.unshift(s); e = e.parentElement;
    }
    return parts.join(" > ");
  }
  const envoyer = (st) => { try { window.__qaEnregistre(st); } catch (_) {} };
  document.addEventListener("click", (ev) => {
    const el = ev.target.closest("button, a, [role=button], input[type=submit], input[type=button], [onclick], summary, li, td, span, div");
    if (!el || ["INPUT", "TEXTAREA", "SELECT", "OPTION"].includes(ev.target.tagName) && !["submit", "button"].includes(ev.target.type)) return;
    if (ev.detail === 0 && Date.now() - (window.__qaEntree || 0) < 800) return;   // clic implicite d'Entrée (déjà relevée)
    const t = texte(el);
    const f = el.form || el.closest("form");
    const connexion = !!(f && f.querySelector("input[type=password]"));   // valider une connexion n'écrit rien
    envoyer({ action: "click", selector: selecteur(el), note: t || etiquette(el), ecrit: !connexion && (el.type === "submit" || ECRIT.test(t)) });
  }, true);
  document.addEventListener("change", (ev) => {
    const el = ev.target; if (!el || !el.tagName) return;
    const tag = el.tagName.toLowerCase(), ty = (el.type || "").toLowerCase();
    if (tag === "select") return envoyer({ action: "select", selector: selecteur(el), value: el.value, note: etiquette(el) });
    if (ty === "checkbox" || ty === "radio") return el.checked && envoyer({ action: "check", selector: selecteur(el), note: etiquette(el) });
    if (tag === "input" || tag === "textarea") envoyer({ action: "fill", selector: selecteur(el), value: el.value, note: etiquette(el),
      secret: ty === "password", champ: el.getAttribute("name") || el.id || "", type: ty });
  }, true);
  document.addEventListener("keydown", (ev) => {
    if (ev.key !== "Enter" || !ev.target || !["INPUT"].includes(ev.target.tagName)) return;
    const el = ev.target;
    window.__qaEntree = Date.now();
    envoyer({ action: "fill", selector: selecteur(el), value: el.value, note: etiquette(el), secret: el.type === "password", champ: el.getAttribute("name") || el.id || "", type: el.type || "" });
    const f = el.form || el.closest("form");
    envoyer({ action: "press", selector: selecteur(el), value: "Enter", note: "Entrée", ecrit: !(f && f.querySelector("input[type=password]")) });
  }, true);
})();
"""

IDENT = re.compile(r"(user|login|identifiant|email|courriel|mail|account|compte|pseudo)", re.I)


def _slug(t):
    t = re.sub(r"[^a-z0-9]+", "_", (t or "").lower().translate(str.maketrans("àâäéèêëîïôöùûüç", "aaaeeeeiioouuuc"))).strip("_")
    return t[:30] or "valeur"


def nettoyer_enregistrement(brut):
    """Gestes bruts -> étapes : fusion des saisies successives du même champ, suppression des doublons (fill + Entrée
    déjà saisi), clics sur un champ de saisie retirés."""
    out = []
    for st in brut:
        st = {k: v for k, v in st.items() if v not in (None, "")}
        if out and st.get("action") == "fill" and out[-1].get("action") == "fill" and out[-1].get("selector") == st.get("selector"):
            out[-1] = st
            continue
        if out and st == out[-1]:
            continue
        if st.get("action") == "fill" and any(o.get("action") == "fill" and o.get("selector") == st.get("selector") and o.get("value") == st.get("value")
                                              for o in out[-6:]):
            continue      # même saisie relevée deux fois (changement puis sortie du champ)
        out.append(st)
    return out


def parametrer(etapes):
    """Étapes enregistrées -> (étapes avec {{paramètres}}, paramètres [{nom, defaut, secret?, note}]).
    Mot de passe -> {{mot_de_passe}} (jamais de valeur gardée), champ d'identifiant -> {{identifiant}}, première adresse
    -> base {{site}} ; les autres saisies deviennent des paramètres nommés d'après le champ (valeur enregistrée par défaut)."""
    params, noms, out = [], set(), []
    par_selecteur = {}     # un même champ saisi plusieurs fois = un seul paramètre
    base = ""
    for st in etapes:
        st = dict(st)
        a = st.get("action")
        if a == "goto" and not base:
            m = re.match(r"^(https?://[^/]+)(/.*)?$", st.get("value") or "")
            if m:
                base = m.group(1)
                st["value"] = m.group(2) or "/"
        elif a in ("fill", "select") and not str(st.get("value", "")).startswith("{{"):
            if st.get("selector") in par_selecteur:
                nom = par_selecteur[st["selector"]]
                secret = any(p["nom"] == nom and p["secret"] for p in params)
                st.pop("secret", None)
                st["value"] = "{{%s}}" % nom
                if secret:
                    st["secret"] = True
                for k in ("champ", "type"):
                    st.pop(k, None)
                out.append(st)
                continue
            if st.pop("secret", False) or st.get("type") == "password":
                nom, defaut, secret = "mot_de_passe", "", True
            elif a == "fill" and IDENT.search((st.get("champ") or "") + " " + (st.get("note") or "")):
                nom, defaut, secret = "identifiant", st.get("value", ""), False
            else:
                nom, defaut, secret = _slug(st.get("note") or st.get("champ") or "valeur"), st.get("value", ""), False
            if nom in noms and nom not in ("mot_de_passe", "identifiant"):
                i = 2
                while "%s_%d" % (nom, i) in noms:
                    i += 1
                nom = "%s_%d" % (nom, i)
            if nom not in noms:
                noms.add(nom)
                params.append({"nom": nom, "defaut": "" if secret else defaut, "secret": secret, "note": st.get("note", "")})
            par_selecteur[st.get("selector")] = nom
            st["value"] = "{{%s}}" % nom
            if secret:
                st["secret"] = True
        for k in ("champ", "type"):
            st.pop(k, None)
        out.append(st)
    return out, params, base


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
    """Connexion CDP au Chromium visible, refaite si le navigateur a été relancé ; enregistrement des gestes (#799)."""
    def __init__(self, cdp=CDP):
        self.cdp, self._pw, self._b = cdp, None, None
        self.rec = {"actif": False, "brut": [], "debut": None}
        self._lie = None

    def _geste(self, source, st):
        if self.rec["actif"] and isinstance(st, dict) and len(self.rec["brut"]) < 500:
            st = {k: st.get(k) for k in ("action", "selector", "value", "note", "ecrit", "secret", "champ", "type")}
            if st.get("secret"):
                st["value"] = ""       # jamais de mot de passe gardé
            self.rec["brut"].append(st)

    def enregistrer(self, etape):
        p = self.page()
        ctx = p.context
        if etape == "debut":
            if self._lie is not ctx:      # une liaison et un script par contexte (rejoués à chaque navigation)
                ctx.expose_binding("__qaEnregistre", self._geste)
                ctx.add_init_script(script=RECORDER_JS)
                self._lie = ctx
            for pg in ctx.pages:
                try:
                    pg.evaluate(RECORDER_JS)
                except Exception:  # noqa: BLE001 -- page en cours de chargement : le script d'init la couvrira
                    pass
            self.rec = {"actif": True, "brut": [{"action": "goto", "value": p.url}] if p.url.startswith("http") else [], "debut": time.time()}
            return {"ok": True, "actif": True, "url": p.url}
        if etape == "etat":
            return {"ok": True, "actif": self.rec["actif"], "gestes": len(self.rec["brut"])}
        if etape == "fin":
            self.pomper()
            self.rec["actif"] = False
            etapes = nettoyer_enregistrement(self.rec["brut"])
            par, params, base = parametrer(etapes)
            return {"ok": True, "actif": False, "brut": etapes, "etapes": par, "parametres": params, "base_url": base,
                    "duree_s": int(time.time() - (self.rec["debut"] or time.time())), "capture": capture(p)}
        raise ValueError("enregistrer : debut, etat ou fin")

    def pomper(self):
        """Laisse Playwright traiter les gestes reçus pendant que l'API attendait (fil unique)."""
        if not self.rec["actif"] or self._b is None:
            return
        try:
            self.page().wait_for_timeout(30)
        except Exception:  # noqa: BLE001
            pass

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
                    if m == "POST" and u.path == "/enregistrer":
                        return self._rep(200, nav.enregistrer(str(corps.get("etape") or "")))
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
    srv = HTTPServer(("127.0.0.1", port), H)   # un seul fil : Playwright (sync) reste dans le fil qui l'a démarré
    srv.timeout = 0.3
    while True:                                # entre deux requêtes, les gestes enregistrés sont traités
        srv.handle_request()
        nav.pomper()


if __name__ == "__main__":
    servir(int(sys.argv[1]) if len(sys.argv) > 1 else 8094)
