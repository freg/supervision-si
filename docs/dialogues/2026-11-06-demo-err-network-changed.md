# 2026-11-06 — outil de démonstration : net::ERR_NETWORK_CHANGED (#989)

**Freg** : création du parcours `idruide` depuis la tour (job demo lancé par test) — échec dans `connecter()` :
`Page.goto: net::ERR_NETWORK_CHANGED at https://supervision.optline.fr/`.

**Claude** : le conteneur de démonstration tourne en `--network host` ; Chromium voit les interfaces de l'hôte et
abandonne la navigation dès qu'un conteneur Docker démarre/s'arrête (veth créée/supprimée). Correctif : `aller()` dans
`demo/tour.py` réessaie 5 fois les erreurs réseau passagères ; `DEMO_RESEAU=bridge` possible dans le .env pour isoler
Chromium si le hub est joignable depuis un conteneur ordinaire. Relancer le parcours après déploiement.

**Freg** : le parcours passe, mais les diapositives (ex. 5/6 « Les alertes ») montrent l'accueil non connecté.

**Claude** (#990) : la connexion initiale réussit (sinon arrêt), c'est le rechargement de chaque vue qui retombe sur
l'accueil. Chaque étape attend la vérification de session, se reconnecte et rouvre la vue si besoin ; sinon remarque
sur la diapositive. Demande : le `journal.txt` du prochain passage pour trouver la cause (session non gardée).

**Freg** : le PowerPoint téléchargé est toujours bloqué sur l'authentification (compte de démo créé) ; capture de la
page Démonstrations.

**Claude** (#991) : le fichier venait de la visite de 10:12 (#984, avant le correctif de connexion) ; les visites
14:39 / 14:51 (#989) sont connectées. Captures en clair (thème du compte) → thème sombre imposé par défaut.

**Freg** : `git push` refusé (non-fast-forward). **Claude** : le premier commit #989 était déjà sur GitHub avant
correction du format de hubUpdates.json → fusion `-s ours` d'origin/dev, version locale conservée.

**Freg** : ajouter « supprimer » dans les cases diaporama. **Claude** (#992) : bouton « 🗑 Supprimer » par visite,
`DELETE /demos/<dossier>` côté services-api.

**Freg** : liste des réseaux en menu déroulant pour les parcours qui en demandent ; où trouve-t-on les réseaux dans le
hub ? **Claude** (#993) : les variables `terminal` / `nom_reseau` désignent une tablette ; menu des terminaux du registre
Équipements du site (nom réseau = nom annoncé vu par Nebula). Réseaux au sens SSID / VLAN : Nebula (onglets).

**Freg** : NAS — volumes / évolution / disques en tête, les deux NAS côte à côte, simple rappel avec lien vers
« Propositions et conseils (SNMP) » en onglet plutôt qu'en défilement. **Claude** (#994) : onglets Vue d'ensemble /
Conseils / Détails, NAS en grille côte à côte, rappel d'une ligne avec lien vers l'onglet Conseils.
