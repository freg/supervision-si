# Géolocalisation par le nom (livraison #426)

Demande : « quand on clique sur un équipement de la table des supervisés
et que son nom inclut une localisation et un type, ex. `UPS-Arobase-5`, je
veux que ça ne soit pas une position de repli mais la géolocalisation de
l'Arobase-5, site @5 ; une liste de localisations à valider, persistée,
l'automatisation validée par défaut (référence orthographiquement ou
sémantiquement proche = position) ».

## Où se prend la décision : pixel-grid-api

`pixel-grid/api/name_resolver.py` (logique pure, 9 tests) reconnaît une
localisation de la table `geolocations` dans un nom d'équipement ou un nom
de site, dans cet ordre :

1. **alias déclarés** (table `location_aliases`, ex. `@5` → `Parc/Batiment 5`) ;
2. **équivalences sémantiques** intégrées : `@` ↔ `arobase` ↔ `at`,
   `tp` ↔ `batiment`, `bat` ↔ `bâtiment`, `st` ↔ `saint`, `etg` ↔ `étage`,
   `cinq` ↔ `5`, `05` → `5`… (accents et casse ignorés) ;
3. **proximité orthographique** (difflib) entre les jetons du nom — les
   jetons de *type* (`ups`, `sw`, `srv`, `ap`, `imp`, `nas`…) sont retirés du
   nom, jamais du site — et ceux de chaque localisation (chemin complet et
   dernier segment), les mots génériques (`agence`, `site`, `bâtiment`…)
   pesant peu. **Contrainte sur les nombres** : un `5` côté site exige un
   `5` côté nom, sinon `Arobase-5` collerait à `Arobase 3` ; un nom sans
   nombre (`UPS-Arobase`) n'obtient qu'une suggestion.

Score ≥ 0,75 → statut **auto** (appliqué d'office) ; 0,5 ≤ score < 0,75 →
**suggested** (proposé, pas appliqué) ; en dessous, rien. Le site déclaré
sur l'équipement est essayé avant le nom et prime à score égal ; un alias
prime sur une correspondance calculée.

Persistance : table `location_matches` (`subject`, `name`, `site`,
`localisation`, `score`, `method`, `status`, dates). Statuts : `auto`,
`suggested`, `validated`, `rejected`, `manual`. Une décision humaine n'est
jamais recalculée ; une entrée `auto` est réévaluée à chaque résolution
(et retirée si plus rien n'est crédible).

Routes :

- `GET /geolocations/resolve?name=…&site=…` — essai ou usage par un autre
  service, sans persistance ;
- `POST /geolocations/resolve` `{subjects: [{subject, name, site}], persist}`
  — résolution en lot persistée (au plus 2000 sujets), renvoie pour chaque
  sujet la correspondance (avec coordonnées, `mapped`) et les candidats ;
  pas de droit requis : rien n'y vient de la personne ;
- `GET /geolocations/matches` ; `PUT /geolocations/matches/<subject>`
  `{status: validated|rejected|manual, localisation?, groups}` (droit
  *manage* sur pixel-grid-api, comme les autres écritures) ;
  `DELETE /geolocations/matches/<subject>` → retour à l'automatique ;
- `GET|POST|DELETE /geolocations/aliases` (`{alias, localisation, groups}`).

Les sujets sont les **identités du hub** (`ip:<ip>`, `mac:<mac>`,
`name:<nom>`), plus `site:<nom>` pour les nœuds de site et `path:<chemin>`
pour le pont pixel-grid : une décision prise dans une vue vaut partout.

## La passe sur les fronts et les API

- **Hub, tuile Supervision SI** (`supervisedItems.js`, `SupervisionSiView.jsx`,
  `geoMatchesClient.js`) : à chaque changement de la liste des supervisés
  (identités, noms, sites), résolution en lot ; une correspondance appliquée
  avec coordonnées devient une position de source **« nom »** (cercle à
  liseré gris sur la carte) — avant la déduction par les liens et le
  repli. Les nœuds de site (`site:`) sont résolus de la même façon (site
  déclaré `Annexe-Nord` ≈ localisation `Agence Annexe Nord`). La colonne
  Site de la table affiche la localisation résolue *(auto / validée /
  manuelle)* quand aucun site n'est déclaré ; le cadre « Liens et positions »
  montre, pour l'équipement sélectionné, la correspondance, les autres
  candidats et les actions ; le nouveau cadre **« Localisations »** est la
  liste à valider : filtres à traiter / appliquées / rejetées / toutes,
  compteurs (localisés, à confirmer, sans correspondance, lieux sans
  coordonnées, lieux en attente de coordonnées), boutons ✓ valider,
  ✕ rejeter, ↺ auto, « choisir… » (localisation manuelle), et les alias
  déclarés (ajout / suppression). Les décisions passent le groupe de la
  personne (`groups`) pour le contrôle *manage*.
- **Ancienne maquette, Fusion IP/MAC** (`fusionLib.js`, `FusionApp.jsx`,
  `pixelGridApi.js`) : troisième bouton de géocodage « via le nom d'hôte »,
  à côté du géo-IP et du code postal ; la colonne Position montre
  « ≈ localisation » pour une position d'après le nom ; sujets `ip:<ip>`,
  donc les mêmes correspondances que le hub.
- **relations-api** (`entity_fetchers.resolve_sites`) : les sites de
  tickets absents de la table à l'identique sont résolus en un appel
  (sans persistance) avant le calcul de proximité géographique.
- **pixel-grid-bridge** : un chemin `localisation` d'événement inconnu de
  la table est résolu (persisté, sujet `path:`) avant le repli sur
  `__default__` ; propriété `localisation_resolue` sur la feature.
- Inchangés, vérifiés : vault (référence logique vers `localisation`,
  pas de nom d'équipement), geo-import (connecteur `geolocations`,
  reprendra les correspondances via le catalogue de positions à venir),
  network-agent (coordonnées déclarées des appareils, déjà prioritaires).

## Vérifié / non vérifié

Vérifié : 9 tests du résolveur, 5 tests de routes (SQLite temporaire :
résolution, persistance, rejet non recalculé, manuel avec contrôle de la
localisation, validation, retour auto, alias, lieu sans coordonnées),
121 tests Node du hub, build Vite du hub, chaîne réelle hub ↔ pixel-grid-api
(Flask réel sur SQLite dans le harnais : `UPS-Arobase-5` → `@5`,
`sw-tp5-core` → `Parc/Batiment 5`, `Annexe-Nord` → `Agence Annexe
Nord`, `ap-arobase` à confirmer, clic « valider » → statut validé), rendu
Chromium clair/sombre, syntaxe des fichiers de l'ancienne maquette
(esbuild), `resolve_sites` et le pont sous mock. Non vérifié : PostgreSQL
(`CREATE TABLE IF NOT EXISTS` relu, même dialecte que la table
`geolocations`), build Docker (source `COPY` ajoutée au Dockerfile de
pixel-grid-api), build complet de l'ancienne maquette, vrais noms du parc —
les jetons de type et les équivalences sémantiques sont à enrichir avec
les noms réels (fichier `name_resolver.py`, listes `TYPE_TOKENS`,
`SEMANTIC`, `GENERIC_TOKENS`).
