#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Visite automatisée du hub (livraison #982) : parcours -> captures -> diaporama HTML autonome + présentation .pptx.

  python3 tour.py <parcours> [--var nom=valeur ...] [--sortie /sortie] [--sans-connexion]

Environnement : DEMO_HUB_URL (adresse du hub), DEMO_USER / DEMO_PASSWORD (compte Keycloak de démonstration, lecture
seule de préférence -- JAMAIS en argument de commande), DEMO_LIVRAISON (numéro affiché sur la page de titre).
Une étape qui ne trouve pas un élément à cliquer est capturée quand même, avec une remarque dans le manifeste.
"""
import argparse
import json
import os
import sys
import time

import demo_lib as L
import build

ICI = os.path.dirname(os.path.abspath(__file__))


ERREURS_PASSAGERES = ("ERR_NETWORK_CHANGED", "ERR_NETWORK_IO_SUSPENDED", "ERR_INTERNET_DISCONNECTED",
                      "ERR_CONNECTION_RESET", "ERR_CONNECTION_REFUSED", "ERR_ADDRESS_UNREACHABLE")


def aller(page, url, journal, essais=5):
    """#989 : avec --network host, Chromium voit les interfaces de l'hôte ; un conteneur Docker qui démarre ou s'arrête
    (tour de contrôle, reconstruction) change le réseau et Chromium abandonne la navigation (net::ERR_NETWORK_CHANGED).
    Erreur passagère : on réessaie quelques fois avec un délai croissant."""
    for n in range(1, essais + 1):
        try:
            return page.goto(url, wait_until="domcontentloaded", timeout=60000)
        except Exception as exc:  # noqa: BLE001 -- playwright Error
            code = next((c for c in ERREURS_PASSAGERES if c in str(exc)), None)
            if not code or n == essais:
                raise
            journal.append("%s sur %s, nouvel essai %d/%d" % (code, url, n + 1, essais))
            time.sleep(2 * n)


def connecter(page, base, user, mdp, journal):
    """#985 : le hub affiche d'abord « Connexion en cours… » puis, sans session, un accueil avec un bouton de connexion :
    on attend l'un des trois états (connecté, formulaire Keycloak, accueil), on clique la connexion si besoin, on remplit
    le formulaire, et on vérifie qu'on est bien connecté (bouton « Se déconnecter »)."""
    import re as _re
    aller(page, base, journal)
    connecte = 'button:has-text("Se déconnecter")'
    fin = time.time() + 90
    clique, rempli = False, False
    while time.time() < fin:
        if page.query_selector(connecte):
            journal.append("connecté%s" % (" en %s" % user if rempli else " (session existante)"))
            return
        if page.query_selector("#username") and not rempli:
            if not user or not mdp:
                raise SystemExit("connexion Keycloak demandée : renseigner DEMO_USER et DEMO_PASSWORD dans le .env")
            page.fill("#username", user)
            page.fill("#password", mdp)
            page.click("#kc-login")
            rempli = True
        elif rempli and page.query_selector("#username") and page.query_selector(".kc-feedback-text, #input-error, .alert-error"):
            raise SystemExit("connexion refusée par Keycloak pour %s (mot de passe ? compte désactivé ?)" % user)
        elif not clique and not rempli:
            b = page.get_by_role("button", name=_re.compile(r"connecter|connexion|s.identifier", _re.I))
            if b.count():
                b.first.click()
                clique = True
        page.wait_for_timeout(1000)
    page.screenshot(path="/tmp/connexion-echec.png")
    raise SystemExit("connexion au hub impossible en 90 s (ni bouton « Se déconnecter », ni formulaire Keycloak) : vérifier DEMO_HUB_URL")


def etape(page, base, e, masquer_css, journal):
    remarques = []
    aller(page, L.url_etape(base, e), journal)
    try:
        page.wait_for_load_state("networkidle", timeout=20000)
    except Exception:  # noqa: BLE001 -- vues qui interrogent en continu : on capture quand même
        pass
    if masquer_css:
        page.add_style_tag(content=masquer_css)
    for s in e.get("saisir") or []:
        try:
            page.fill(s["selecteur"], s["texte"], timeout=5000)
        except Exception:  # noqa: BLE001
            remarques.append("champ introuvable : %s" % s.get("selecteur"))
    for sel in e.get("cliquer") or []:
        try:
            page.locator(sel).first.click(timeout=6000)
            page.wait_for_timeout(600)
        except Exception:  # noqa: BLE001
            remarques.append("élément introuvable : %s" % sel)
    if e.get("attendre"):
        try:
            page.wait_for_selector(e["attendre"], timeout=15000)
        except Exception:  # noqa: BLE001
            remarques.append("attendu sans succès : %s" % e["attendre"])
    if e.get("defiler"):
        try:
            page.locator(e["defiler"]).first.scroll_into_view_if_needed(timeout=5000)
        except Exception:  # noqa: BLE001
            remarques.append("défilement impossible : %s" % e["defiler"])
    page.wait_for_timeout(int(e.get("pause_ms") or 1200))
    for r in remarques:
        journal.append("  ⚠ %s" % r)
    return remarques


def main():
    ap = argparse.ArgumentParser(description="Démonstration automatisée du hub")
    ap.add_argument("parcours", nargs="?")
    ap.add_argument("--var", action="append", default=[], help="nom=valeur (variables du parcours)")
    ap.add_argument("--sortie", default=os.environ.get("DEMO_SORTIE_INTERNE", "/sortie"))
    ap.add_argument("--sans-connexion", action="store_true")
    a = ap.parse_args()
    dossier_p = os.path.join(ICI, "parcours")
    if not a.parcours:
        print("Parcours disponibles :")
        for pid, titre in L.lister(dossier_p):
            print("  %-16s %s" % (pid, titre))
        return 0
    variables = dict(v.split("=", 1) for v in a.var if "=" in v)
    p, err = L.charger(os.path.join(dossier_p, a.parcours + ".json"), variables)
    if err:
        raise SystemExit("parcours invalide : " + " ; ".join(err))
    base = os.environ.get("DEMO_HUB_URL", "").strip()
    if not base:
        raise SystemExit("DEMO_HUB_URL vide : renseigner l'adresse du hub dans le .env")
    if not base.startswith(("http://", "https://")):   # #985 : « supervision.exemple.fr » -> https://…
        base = "https://" + base
    horo = time.strftime("%Y%m%d-%H%M")
    out = os.path.join(a.sortie, L.nom_dossier(p["id"], horo))
    os.makedirs(out, exist_ok=True)
    journal = ["parcours %s — %s" % (p["id"], p["titre"])]
    masquer_css = "\n".join("%s { visibility: hidden !important; }" % s for s in p.get("masquer") or [])
    etapes = []
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        nav = pw.chromium.launch()
        ctx = nav.new_context(viewport={"width": int(p.get("largeur") or 1600), "height": int(p.get("hauteur") or 900)},
                              device_scale_factor=1, ignore_https_errors=True, locale="fr-FR", color_scheme="dark")
        page = ctx.new_page()
        if not a.sans_connexion:
            connecter(page, base, os.environ.get("DEMO_USER"), os.environ.get("DEMO_PASSWORD"), journal)
        for i, e in enumerate(p["etapes"], 1):
            journal.append("%02d %s" % (i, e["titre"]))
            rem = etape(page, base, e, masquer_css, journal)
            img = "%02d.png" % i
            if e.get("zone") and page.query_selector(e["zone"]):
                page.locator(e["zone"]).first.screenshot(path=os.path.join(out, img))
            else:
                page.screenshot(path=os.path.join(out, img))
            etapes.append({"image": img, "titre": e["titre"], "legende": e.get("legende", ""), "remarques": rem})
        nav.close()
    manifeste = {"id": p["id"], "titre": p["titre"], "sous_titre": p.get("sous_titre", ""), "public": p.get("public", ""),
                 "date": time.strftime("%d/%m/%Y %H:%M"), "livraison": os.environ.get("DEMO_LIVRAISON", ""), "etapes": etapes}
    with open(os.path.join(out, "manifeste.json"), "w", encoding="utf-8") as fh:
        json.dump(manifeste, fh, ensure_ascii=False, indent=1)
    html, pptx = build.construire(out)
    with open(os.path.join(out, "journal.txt"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(journal) + "\n")
    print("\n".join(journal))
    print("\nFINI : %s\n  diaporama : %s\n  présentation : %s" % (out, html, pptx))
    return 0


if __name__ == "__main__":
    sys.exit(main())
