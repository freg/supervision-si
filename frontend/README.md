# Frontend — Supervision SI + Pixel Grid (application historique)

Application d'origine du projet : carte Leaflet/OSM, sources
externes (colonne gauche), synthèse (colonne droite), et plusieurs
sous-applications accessibles via `TopNav.jsx` (IPAM, Optick, TTS-GU,
Zenoss, Cacti, OwnCloud, Fusion IP/MAC, Logs, Recherche, Géo-import).
Jusqu'ici sans `README.md` dédié malgré son ancienneté -- créé à
l'occasion du premier bug documenté ci-dessous.

## Bug réel — en-tête "Supervision SI" recouvert par les contrôles fixes du menu

Signalé par capture d'écran : le titre `.app-header` ("SUPERVISION
SI — VUE CENTRALISÉE") apparaissait tronqué en "...ENTRALISÉE", avec
des lettres isolées ("R", "V") visibles dans les interstices entre
les boutons.

**Cause** : `.top-nav-fixed-controls` (🏠 Hub / ⚙️ Paramètres / 🌙,
voir `TopNav.jsx`) est en `position: fixed; top: 8px; left: 8px;
z-index: 1001` -- flotte au-dessus de TOUT le contenu de la page,
quel que soit le flux normal du document. Ce même groupe avait déjà
nécessité un correctif pour ne pas recouvrir `.top-nav` (le menu
coulissant, `padding-left: 300px` déjà en place) -- mais `.app-header`
(l'en-tête de la page elle-même, en flux normal, tout en haut à
gauche comme lui) n'avait jamais reçu le même traitement. Recoupement
vérifié au pixel près (largeur cumulée des 3 contrôles fixes ≈
250px, correspond exactement à la coupure observée sur "SUPERVISION
SI — VUE CENTRALISÉE").

**Corrigé** : même marge généreuse reprise sur `.app-header`
(`padding-left: 300px`, valeur identique et déjà éprouvée contre ce
chevauchement précis) -- une seule occurrence de la classe dans tout
le module (`SupervisionApp.jsx`), changement contenu. Ce mécanisme de
contrôles fixes (`top-nav-fixed-controls`) est propre à ce module
seul (vérifié : absent des autres modules du dépôt), pas d'audit
transversal nécessaire.

Vérifié : équilibre des accolades CSS, seule occurrence JSX de la
classe confirmée (`grep`), calcul de recouvrement au pixel
correspondant précisément au symptôme observé. **Non vérifié dans cet
environnement** : rendu visuel réel, aucun navigateur disponible ici
-- ce correctif mérite particulièrement une confirmation en
conditions réelles (capture d'écran de suivi bienvenue).
