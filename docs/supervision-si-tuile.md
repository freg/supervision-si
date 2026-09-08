# Tuile « Supervision SI » refondue (livraison #423, backlog 64)

« La tuile actuelle était la maquette initiale de la dataviz du hub ; elle
doit changer radicalement et ses outils actuels se retrouveront distribués
dans les tuiles (on garde la tuile, rôle central). » Tranché : la nouvelle
tuile vit **dans le hub** (`hub/src/SupervisionSiView.jsx`, logique pure
`supervisedItems.js` testée par `hub/tests/supervisedItems.test.mjs`).
L'ancien front reste joignable (« ancienne maquette ↗ » et mode onglets)
tant que ses outils (calendrier, corbeille, radial, fusion IP/MAC…) ne
sont pas redistribués — point (4) du backlog, à suivre.

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

Vérifié : 8 tests de logique pure (normalisation par source, fusion,
propositions, filtre/priorisation, liens et déduction de position avec
chaîne, dispositions, préférences, écartement des points) ; build Vite du
hub ; rendus Chromium sur un faux back-end (2, 3 et 4 cadres, onglets
Propositions et Liens avec chaîne de déduction, thème sombre) — les tuiles
OpenStreetMap ne se chargent pas dans le bac à sable (sans réseau), la
carte réelle est à confirmer au déploiement.

Non vérifié : vraies API réunies, volume réel (flux network-agent sur
plusieurs segments), redistribution des anciens outils (à venir).
