# Cortex (livraisons #462 à #464) — décloisonne, corrèle, relie, consolide

Première étape du découpage de `docs/analyse-supervision-unifiee.md`
(#461) : un modèle commun et une file d'incidents corrélés, **totalement
transparents** — chaque hypothèse porte sa confiance, ses preuves et le
principe (parti pris) qu'elle applique, et chaque principe est évalué par
les retours humains.

## Modèle commun (`cortex-api`, SQLite)

- **entités** consolidées : clé stable `mac:` > `ip:` > `name:` ; les clés
  secondaires sont absorbées (`alias_map`, principes `identity-*`) ; type,
  nom, IP, MAC, site, origines (quelle source, quel identifiant), indices
  de rôle ;
- **relations** : `gateway_of` (route par défaut vue par un agent),
  `powers_site` (onduleur d'un site), `neighbor`, `talks_to`, `flow`
  (network-agent), `watches` (sonde) — chacune avec poids, principe,
  preuve et source ;
- **événements normalisés** : `{empreinte, source, type, sévérité, entité,
  site, message, référence brute, état open/acked/closed, premier/dernier,
  compteur}` — un événement répété est rafraîchi, jamais dupliqué ; une
  source lue avec succès qui ne le remonte plus le ferme ;
- **incidents** : regroupement par fenêtre glissante (`CORTEX_WINDOW_SECONDS`,
  300) + relation partagée, ou même entité, ou (faiblement) même site ;
  cause racine = entité la plus en **amont** (passerelle, onduleur) ;
  hypothèses, sévérité = pire événement, état (ouvert / acquitté / clos)
  conservé d'une collecte à l'autre ;
- **retours** (`feedback`) par principe et **journal des collectes**
  (`runs`) : quelle source a répondu, en combien de temps, ce qui en est
  sorti.

Sources lues (API internes, rien de modifié chez elles) : si-agent
(flotte, netviews, événements récents, état de la flotte), vigilance,
UPS, orchestrateur, netprobe, network-agent (+ services vus par
segment), sauvegardes du hub, et depuis #463 : classifier (catégories
de noms d'hôtes), Nebula (types, sites, clients attachés), IPAM (noms et
descriptions déclarés).

### Étape 2 (#463) : rôles enrichis, routes, architecture, changements

- **rôles enrichis** : le constructeur est déduit de l'OUI de la MAC
  (`oui.py`, table réduite — Cisco, Ubiquiti, MikroTik, HP, Brother,
  Synology, VMware, Raspberry…) et donne un indice de famille
  (`oui-vendor`) ; la catégorie classifier (`name-class`), le type Nebula
  et la description IPAM (`referential`) ; les services vus par
  network-agent (`serves-port`). Chaque entité porte constructeur, modèle,
  description, sous-réseau, OS quand une source les connaît ; les rôles
  restent pondérés et combinés (1-(1-a)(1-b)) ;
- **table de routes** (`routes`) : pour chaque hôte équipé d'un agent, sa
  route par défaut, ses sous-réseaux attachés et ceux joignables via une
  autre passerelle (`routes_from_netviews`, principe `route-known`),
  avec premier/dernier relevé ;
- **graphe d'architecture persistant** (`/graph`) : nœuds = entités
  (type, rôle dominant, site, constructeur), arêtes = relations ; la
  relation `uplink` (client WiFi → borne, Nebula, principe `attached-to`)
  s'ajoute à `gateway_of` ;
- **« ce qui a changé »** (`changes.py`) : un instantané est pris avant
  et après chaque collecte ; entité nouvelle ou plus vue, rôle dominant ou
  site qui bascule, relation nouvelle ou disparue, passerelle par défaut
  qui change sont journalisés (principe `change-since`). Les disparitions
  dues à une source en échec pendant la collecte ne sont **pas** comptées.
Collecte toutes les `CORTEX_INTERVAL_SECONDS` (300) et à la demande
(`POST /collect`, droit `manage` si `CORTEX_RIGHTS_API_URL`).

### Étape 3 (#464) : lieux, positions avec provenance, intervention, carto

- **hiérarchie de lieux** (`places.py`, table `places`) : site > bâtiment >
  étage > salle > baie, construite depuis les géolocalisations de
  pixel-grid (`parent_localisation`, `location_type`), les appareils
  network-agent (`building`, `room`, sites) et le catalogue geo-catalog
  (positions validées / corrigées, liens vers les sujets supervisés).
  « lieu:bureau » et « site:bureau » sont fusionnés ; une salle déclarée
  deux fois sous le même site racine est une seule salle ; un lieu sans
  coordonnées hérite de son parent (`place-hierarchy`, signalé « hérité
  de ») ; contact, accès et notes d'un lieu sont une saisie humaine
  (`place_notes`, `PUT /places/<clé>`) jamais écrasée par la collecte ;
- **position mémorisée par entité** (table `positions`) avec provenance,
  confiance, chaîne et date de changement, résolue à chaque collecte
  (et à la demande, `POST /positions/resolve`) par une échelle explicite
  dont chaque barreau est un principe : `pos-declared` (0,95, coordonnées
  portées par l'appareil) › `pos-validated` (0,9, correspondance validée
  ou manuelle) › `pos-place` (0,85, lieu déclaré le plus précis, 0,75 si
  hérité) › `pos-geolocation` (0,8, table par nom ou IP) ›
  `pos-resolved-name` (0,6 auto / 0,5 suggérée) › `pos-propagated` (≤ 0,7 :
  client → sa borne, hôte → sa passerelle du même site, onduleur → ce
  qu'il alimente) › `pos-neighbor` (0,5 / profondeur, moyenne pondérée
  des voisins, chaîne conservée) › `pos-fallback` (0,1, `__default__`).
  Les entités sans position ou en repli forment la **file de travail**
  (`/positions/queue`, par site). Un changement de provenance ou de
  position est journalisé dans « ce qui a changé » (`position-found`,
  `position-changed`, `position-moved`) ;
- **fiche d'intervention** (`/entities/<clé>/intervention`, bouton dans le
  détail d'une entité, depuis la table des positions et depuis la carte) :
  où aller (chaîne de lieux), position et provenance, amont (passerelle,
  borne, onduleur du site) avec l'état de chacun, incidents ouverts,
  supervisée ou vue par la découverte seule (`unsupervised`), entités du
  même lieu, accès bastion (IP privée joignable par si-proxy quand le
  relais est déployé — Cortex ne détient jamais le jeton d'administration),
  lien « ouvrir un ticket » (`CORTEX_TICKETS_PORTAL_URL`), contact et accès
  du site saisis sur place ;
- **éclairage carto** (`/layers`, onglet **Carte**, Leaflet) : couches
  activables — entités positionnées (couleur = provenance), halos
  d'incidents (rayon = sévérité × entités touchées), densité par lieu,
  zones sans supervision (cercle pointillé), chemins de dépendance
  (passerelle → hôte, borne → client, onduleur → site). GeoJSON réutilisable
  par la carte de Supervision SI (`?only=incidents,density`).

## Principes (partis pris) — `cortex/api/principles.py`

Trente principes nommés, chacun avec sa confiance de base, son énoncé et
sa limite connue : identité (IP, MAC, nom), relations (passerelle, relais,
port servi → rôle, même site, onduleur du site, sonde, borne d'un client
WiFi, route déclarée), rôle (OUI du constructeur, classification du nom,
référentiel déclaré), position (les huit barreaux de l'échelle + héritage
de lieu), causalité (amont d'abord, fenêtre + relation, regroupement par
site, événement isolé), présentation (sévérité max, changement entre deux
collectes, non supervisée). La confiance **mesurée** d'un principe
intègre les retours « juste / fausse » donnés sur les hypothèses qui s'en
réclament (lissage : la base vaut quatre retours). La confiance d'un
incident est celle de son hypothèse causale — jamais un maximum flatteur.

## Routes

`/status`, `POST /collect`, `/principles`, `/runs`, `/stats?days=`,
`/entities?q=`, `/entities/<clé>` (rôles pondérés, relations, événements),
`/relations?entity=`, `/events?state&severity&since&entity`,
`POST /events/<empreinte>/ack|close`, `/incidents?state=`,
`/incidents/<clé>` (détail : hypothèses, entités, relations, événements),
`POST /incidents/<clé>/ack|close`, `POST /incidents/<clé>/feedback
{principle, verdict}` ; depuis #463 : `/graph` (nœuds + arêtes),
`/routes?host=`, `/changes?since&kind&limit` ; depuis #464 : `/places`,
`PUT /places/<clé> {contact, access, notes}`, `/positions?provenance=`,
`/positions/queue`, `POST /positions/resolve`,
`/entities/<clé>/intervention`, `/layers?only=`.

## Tuile

Thématique Supervision, premier onglet : incidents (cause proposée,
confiance en mots et en %, détail avec hypothèses votables, entités,
relations utilisées, événements), **Architecture** (SVG : une colonne par
site, trois couches — amont / hôtes supervisés / reste — largeur de
colonne adaptée à l'étiquette la plus longue, arêtes colorées par type,
clic sur un nœud = fiche), **Carte** (couches activables, légende des
provenances, clic = fiche d'intervention), **Positions** (table par
provenance, file de travail, résolution à la demande),
**Ce qui a changé** (journal filtrable),
**Routes** (une ligne par hôte : passerelle, état, sous-réseaux
attachés, joignables via), entités (rôles pondérés, constructeur,
description, origines), événements ouverts, principes & évaluations,
statistiques, collecte.

## Vérifié

10 tests purs (principes, normalisation de chaque source, alias et fusion,
rôles pondérés, cause racine passerelle et onduleur, fenêtre, regroupement
faible, retour humain qui baisse la confiance, statistiques) ; API réelle
contre le central si-agent de l'environnement + UPS et vigilance simulés :
un onduleur sur batterie et un agent du même site hors ligne forment **un**
incident dont la cause proposée est l'onduleur (confiance annoncée faible,
22 %, parce que le lien onduleur → site n'est qu'une supposition) ; un
signal vigilance et un agent portant la même IP sont consolidés en une
entité (3 alias) ; acquittement, clôture, retour humain (la confiance
mesurée baisse), 6 onglets rendus sous Chromium ; 166 tests Node.
**Non vérifié** : la collecte contre les vraies API sur « super »
(network-agent en réseau hôte, netprobe, orchestrateur).

Étape 2 (#463) : 12 tests purs (les deux nouveaux : OUI → constructeur et
famille, classifier / Nebula / IPAM → rôles et relation `uplink`, routes
depuis les netviews, changements entre deux instantanés avec source en
échec ignorée) ; chaîne réelle central si-agent + UPS et vigilance
simulés : deux collectes, un onduleur ajouté entre les deux → `/changes`
remonte « nouvelle entité UPS-Siege (onduleur, siege) » et « nouvelle
relation UPS-Siege —powers_site→ site:siege », `/routes` donne 7 routes
(3 hôtes, passerelles 192.168.1.1 et 192.0.2.1), `/graph` 14 nœuds /
13 arêtes ; onglets Architecture, Ce qui a changé, Routes rendus sous
Chromium (168 tests Node). **Non vérifié** : classifier, Nebula et IPAM
réels (formats lus : `/results`, `/imported/devices|clients`, `/ip_list`).

Étape 3 (#464) : 15 tests purs (les trois nouveaux : hiérarchie et
héritage, fusion lieu/site et salle déclarée deux fois ; l'échelle de
résolution barreau par barreau — déclarée, lieu déclaré hérité, site
textuel, client → borne, nom résolu, voisinage — avec confiance
décroissante et file de travail ; fiche d'intervention et couches) ;
chaîne réelle central si-agent + UPS, vigilance, pixel-grid et
network-agent simulés : 17 entités toutes positionnées (1 déclarée,
11 lieu déclaré dont une salle héritée de son bâtiment, 1 résolue par le
nom, 4 voisinage), 4 lieux, un contact de site enregistré et relu dans
la fiche, `/layers` : 3 halos, 4 lieux, 3 sans supervision, 1 chemin ;
onglets Positions, Carte (fond OSM non chargé faute de réseau sortant
dans l'environnement de test — les couches, la légende et le cadrage
automatique sont rendus) et fiche d'intervention sous Chromium ; 170
tests Node. **Non vérifié** : geo-catalog réel (PostgreSQL), fond de
carte, bastion réel.

## Suite (découpage #461)

4. séquences apprises et anticipation, dérives ; 5. MTTA/MTTR, politiques
d'alerte, notifications par incident. (Étapes 1 à 3 livrées en #462, #463,
#464.)
