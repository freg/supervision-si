# Tuile « Bases externes » (livraison #425, backlog 64 point 4, suite)

Les onglets IPAM, Zenoss, Optick, TTS-GU et Cacti de l'ancienne maquette
(`frontend/`) partageaient la même disposition -- racines indépendantes à
gauche, arbre radial au centre, JSON brut à droite -- et le même contrat
d'API lecture seule. Ils deviennent UNE tuile générique du hub,
`hub/src/ExternalBasesView.jsx`, au lieu de cinq écrans quasi identiques.
OwnCloud (arbre paresseux `/children/<storage>/<fileid>`) et la fusion
IP/MAC restent dans l'ancienne maquette, atteignable par le bouton
« ancienne maquette ↗ » de la tuile.

## Contrat d'API commun

Chaque source expose, derrière `VITE_<SOURCE>_API_BASE_URL` :

- `GET /health` → `{status: "ok" | "degraded", ...}` (état affiché en haut à droite) ;
- `GET /roots` → `{roots: [{id, name, description?, ...compteurs numériques}]}` --
  tout champ numérique autre que `id` devient un compteur affiché
  (`subnetCount` → « 6 subnet », `childSectionCount` → « 1 child section ») ;
- `GET /tree/<id>` → `{tree: nœud}` avec nœud `= {id, type, name, children: [], raw: {}}`.

`hub/src/externalBasesClient.js` ne lève jamais : `{roots, error}` /
`{tree, error}`.

## La tuile

- **Onglets** : une source par onglet, seules celles dont l'URL est
  configurée apparaissent ; le dernier onglet ouvert est mémorisé
  (`localStorage` `hub.bases.source`). La tuile et le bouton « Bases
  externes » du menu Général n'existent que si au moins une URL est définie.
- **Colonne de gauche** : racines triées par nom (insensible à la casse et
  aux accents), filtre texte, compteurs. La première racine s'ouvre d'office.
- **Centre** : arbre radial (`radialLayout` de `supervisedHistory.js`, dans
  un `ZoomableChart` -- molette, double-clic, glisser), couleur par type de
  nœud, filtre texte (nom, identifiant, type, description, sous-réseau,
  libellé, chemin, hôte, IP ; un match conserve ses ancêtres ET ses
  descendants), « actifs seulement » pour IPAM (`raw.state === 1`, les
  sous-réseaux inactifs sans descendant actif sont retirés), profondeur
  bornée (1 / 2 / 3 / 4 / 6 / tout) avec nœud « … +N » cliquable pour
  déplier une branche, anneau d'occupation IPAM (`raw.usage` ou
  `raw.usedPercent` : vert < 70 %, orange < 90 %, rouge au-delà).
- **Fiche à droite** : chemin depuis la racine, type, descendants,
  profondeur, répartition par type, occupation, enfants directs (cliquables),
  JSON `raw` complet.

Logique pure dans `hub/src/externalBases.js` (aucun React), testée par
`hub/tests/externalBases.test.mjs` (`node --test hub/tests/*.test.mjs`).

## Configuration

`docker-compose.yml`, service `hub` : `VITE_IPAM_API_BASE_URL`,
`VITE_ZENOSS_API_BASE_URL`, `VITE_OPTICK_API_BASE_URL`,
`VITE_TTSGU_API_BASE_URL`, `VITE_CACTI_API_BASE_URL` (mêmes valeurs que
pour le service `frontend`, via la passerelle `/api/<source>`).

## Vérifié / non vérifié

Vérifié : tests Node (logique pure), build Vite du hub, rendu Chromium sur
harnais (faux back-end aux cinq sources, thèmes clair et sombre, filtre,
changement d'onglet, fiche). Non vérifié : les cinq API réelles derrière la
passerelle (le contrat est celui que l'ancienne maquette consommait déjà),
build Docker.

## Reste à faire (backlog 64)

OwnCloud et la fusion IP/MAC en tuiles, la géomatique, puis retrait de
l'ancien front.
