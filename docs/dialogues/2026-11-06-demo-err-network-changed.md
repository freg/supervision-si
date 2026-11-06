# 2026-11-06 — outil de démonstration : net::ERR_NETWORK_CHANGED (#989)

**Freg** : création du parcours `idruide` depuis la tour (job demo lancé par test) — échec dans `connecter()` :
`Page.goto: net::ERR_NETWORK_CHANGED at https://supervision.optline.fr/`.

**Claude** : le conteneur de démonstration tourne en `--network host` ; Chromium voit les interfaces de l'hôte et
abandonne la navigation dès qu'un conteneur Docker démarre/s'arrête (veth créée/supprimée). Correctif : `aller()` dans
`demo/tour.py` réessaie 5 fois les erreurs réseau passagères ; `DEMO_RESEAU=bridge` possible dans le .env pour isoler
Chromium si le hub est joignable depuis un conteneur ordinaire. Relancer le parcours après déploiement.
