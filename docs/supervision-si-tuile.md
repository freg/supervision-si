# Tuile « Supervision SI » refondue (livraisons #423 et #424, backlog 64)

« La tuile actuelle était la maquette initiale de la dataviz du hub ; elle
doit changer radicalement et ses outils actuels se retrouveront distribués
dans les tuiles (on garde la tuile, rôle central). » Tranché : la nouvelle
tuile vit **dans le hub** (`hub/src/SupervisionSiView.jsx`, logique pure
`supervisedItems.js` testée par `hub/tests/supervisedItems.test.mjs`).
Point (4), livraison #424 : les outils de dataviz de l'ancienne maquette
reviennent dans cette tuile comme **contenus de cadre**, nourris par les
tuiles (voir ci-dessous). L'ancien front reste joignable (« ancienne
maquette ↗ » et mode onglets) pour ses onglets sur bases externes (IPAM,
Optick, TTS-GU, Zenoss, Cacti, OwnCloud, Fusion IP/MAC, géomatique) qui
relèvent de tuiles à part entière — inscrit au backlog.

## Colonne de gauche : trois onglets

- **Supervisés** (défaut) : tout ce que les tuiles supervisent, agrégé
  côté hub et **fusionné par identité** (même IP ou même MAC = un seul
  équipement, plusieurs origines) : sondes réseau (netprobe, dernier
  relevé smokeping), sondes WiFi (netprobe/agents), onduleurs (UPS),
  agents hôtes (si-agent : contact + risques + blocage), cibles SNMP
  (déclarées, interrogation à la demande), tunnels SSH. État homogène
  `critique / avertissement / inconnu / ok` — un état seulement déclaré
  ne dégrade jamais un état mesuré. Filtre texte, par type, par état, par
  site ; **priorisation** persistée (★ puis ▲▼) : les priorisés en tête,
  puis les critiques, puis le nom.
- **Propositions** : suggestions ouvertes de l'orchestrateur, signaux de
  vigilance, appareils **découverts non supervisés** (network-agent, non
  rapprochés par IP/MAC d'un supervisé) — chacun **à cocher** (retenu) ou
  décocher (écarté), persisté ; ↗ ouvre la tuile d'origine où l'action
  se fait réellement.
- **Liens** : liens construits **automatiquement** (flux captés par
  network-agent, tunnels SSH, appartenance à un site) ; cet onglet régit
  la carte : un équipement sans coordonnées est **positionné par ses
  liens** (moyenne pondérée des voisins positionnés, itérée en largeur,
  profondeur ≤ 3, l'appartenance à un site pèse plus qu'un flux), sinon
  par la position de repli `__default__` des géolocalisations. Sources de
  position connues : coordonnées déclarées de l'appareil (network-agent),
  table des géolocalisations de pixel-grid (par IP, nom ou site). La
  **chaîne de déduction** est affichée pour chaque équipement.

## Page centrale : 1 à 4 cadres

Défaut : **carte + table**. `+ cadre` jusqu'à 4 ; 3 cadres = deux en haut,
le troisième pleine largeur en bas ; 4 = 2 × 2 (`frameLayout`). Contenu de
chaque cadre au choix : carte (Leaflet/OSM, marqueurs colorés par état,
pointillé = position déduite, translucide = repli, liens tracés, popup
avec la chaîne de déduction ; points superposés écartés en spirale),
table des supervisés (origines cliquables → tuile), liens et positions
(de l'équipement sélectionné, ou tous), propositions, synthèse par état
(cartes cliquables = filtre). Disposition et contenus persistés
(`hub.supervision.*` dans le stockage local, même motif que le cycle agile).

## Outils redistribués (livraison #424, point 4)

Même idée que dans l'ancienne maquette, mais **données vivantes** : les
historiques viennent des tuiles (relevés smokeping de netprobe, relevés
UPS, mesures `risks` des agents hôtes) au lieu de JSON versés à la main.
Logique pure dans `hub/src/supervisedHistory.js` (6 tests), chargement
dans `supervisedHistoryClient.js`.

- **Corbeille de sélection** : case à cocher devant chaque supervisé
  (persistée, « vider ») ; sans coche, les priorisés, sinon les premiers
  visibles — bornée à 12 équipements pour ne jamais charger tout
  l'historique. Fenêtre 6 h / 24 h / 7 j / 30 j commune aux outils.
- **Timeline des états** : une ligne par équipement, segments contigus
  colorés par état, trou sans relevé = inconnu (gris) ; zoom et
  déplacement (`ZoomableChart`), info-bulle par segment, clic = sélection.
- **Mosaïque (pixel-grid)** : matrice équipements × créneaux (15 min à
  1 j selon la fenêtre), couleur = pire état du créneau, gris = aucun
  relevé.
- **Calendrier de densité** : un jour = nombre de relevés « pas ok » sur
  les équipements retenus, seuils vert = 0 / orange ≥ 1 / rouge ≥ 3 (comme
  la vue calendrier d'origine), 30 jours au moins.
- **Arbre radial** : sites → types → équipements (tous les supervisés
  visibles), disposition radiale sans dépendance (feuilles réparties
  uniformément, nœuds internes au centre angulaire de leurs feuilles),
  couleur = état, clic = sélection, zoom / déplacement.

## Sources d'API

`VITE_NETPROBE_API_BASE_URL`, `VITE_UPS_API_BASE_URL`,
`VITE_SI_AGENT_API_BASE_URL`, `VITE_SNMP_API_BASE_URL`,
`VITE_SSH_TUNNELS_API_BASE_URL`, `VITE_NETWORK_AGENT_API_BASE_URL`,
`VITE_NETMAP_ORCHESTRATOR_API_BASE_URL`, `VITE_VIGILANCE_API_BASE_URL`,
`VITE_PIXEL_GRID_API_BASE_URL` (nouveau côté hub). Chaque source absente ou
injoignable est simplement signalée (« n source(s) injoignable(s) »),
jamais bloquante. Dépendances hub ajoutées : `leaflet`, `react-leaflet`
(mêmes versions que le front historique).

## Vérifié / non vérifié

Vérifié (#424) : 6 tests de logique pure (normalisation des historiques,
segments avec trous et fusion, créneaux, calendrier et seuils, hiérarchie
et disposition radiale, corbeille) ; rendu Chromium des quatre outils en
4 cadres sur un faux back-end avec historiques (incident au milieu de la
fenêtre visible sur la timeline, la mosaïque et le calendrier), thème
sombre ; un défaut de contrat trouvé au rendu (`ZoomableChart` attend un
`viewBox`, pas `width`/`height` — cadres vides sinon).

Vérifié (#423) : 8 tests de logique pure (normalisation par source, fusion,
propositions, filtre/priorisation, liens et déduction de position avec
chaîne, dispositions, préférences, écartement des points) ; build Vite du
hub ; rendus Chromium sur un faux back-end (2, 3 et 4 cadres, onglets
Propositions et Liens avec chaîne de déduction, thème sombre) — les tuiles
OpenStreetMap ne se chargent pas dans le bac à sable (sans réseau), la
carte réelle est à confirmer au déploiement.

Non vérifié : vraies API réunies, volume réel (flux network-agent sur
plusieurs segments), redistribution des anciens outils (à venir).
