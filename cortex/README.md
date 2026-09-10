# Cortex (livraisons #462 à #466) — décloisonne, corrèle, relie, consolide

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

### Étape 4 (#465) : causalité apprise, anticipation, signaux faibles

- **occurrences** (table `occurrences`) : chaque ouverture ou réouverture
  d'événement est historisée (90 j), amorcée depuis l'historique du
  central si-agent ; jamais un simple rafraîchissement ;
- **séquences apprises** (`learn.py`, `mine_sequences`, table `rules`,
  `/rules`) : dans la fenêtre (10 min), les paires « A précède B » avec
  support ≥ 3, confiance ≥ 0,5 et ≥ 2 × l'attendu sous indépendance
  deviennent des règles **proposées**, avec délai typique (médiane, min,
  max) ; deux portées : entités nommées et généralisée par rôle (« sur
  batterie sur un onduleur » précède « agent-offline sur un hôte
  supervisé »). Une personne confirme / rejette / remet en proposition
  (`POST /rules/<id>/confirm|reject|reset`) — la décision est aussi un
  retour sur le principe `sequence-learned` ; les mesures d'une règle sont
  remises à jour à chaque collecte, l'état décidé et les annonces jugées
  sont conservés ;
- **anticipation** (`anticipate`, table `predictions`, `/predictions`) :
  quand A est ouvert et qu'une règle A → B existe, Cortex annonce « B suit
  habituellement A dans n min (x fois sur n) » avec échéance, tant que B
  n'est pas là et que l'échéance n'est pas dépassée de deux fois le délai
  maximal ; une seule annonce par B attendu ; l'annonce est visible dans
  l'incident qui contient A. Elle est ensuite **jugée** (`settle_predictions`)
  : B survenu = juste, délai dépassé = fausse ; le bilan remesure la règle
  (confiance affichée = confiance observée × principe, ajustée par les
  jugements) ;
- **signaux faibles** (`detect_drifts`, table `samples`, `/drifts`,
  `/samples`) : mesures relevées à chaque collecte (si-agent : CPU,
  mémoire, disque, charge ; netprobe : latence, pertes ; UPS : charge,
  batterie, tensions ; 3 j conservés) ; trois détecteurs, chacun un
  principe : écart de la dernière heure aux 24 h (`drift-zscore`, ≥ 3 σ
  avertissement, ≥ 5 σ critique, σ plancher 2 %), tendance linéaire vers
  un seuil (`drift-trend`, échéance < 7 j ; ignorée quand un saut brutal
  est déjà signalé), habitude horaire (`seasonality`, même créneau ± 1 h
  des jours précédents). Une dérive est un **événement normalisé de source
  `cortex`** : même empreinte, même cycle de vie (fermée quand elle cesse),
  donc regroupable dans les incidents.

### Étape 5 (#466) : politiques d'alerte, notifications par incident, silences, MTTA / MTTR

- **politiques d'alerte** (`policy.py`, table `policies`, `/policies`,
  `PUT /policies`, `DELETE /policies/<id>`) : liste ordonnée ; chaque
  politique se choisit par rôle de la cause, site, type d'entité, entités
  nommées, sévérité minimale et confiance minimale, et décide priorité
  (haute / normale / basse), canaux (sms, email, webhook), délai
  d'escalade et canaux d'escalade, notification de la résolution. Quatre
  politiques par défaut installées une fois (infrastructure de site →
  haute, SMS + courriel + webhook, escalade 15 min ; serveurs → normale,
  courriel + webhook, escalade 1 h ; postes → basse, webhook, critique
  seulement ; par défaut → critique). La raison de chaque décision est
  affichée (principe `policy-role-place`) ; `/policies/preview` dit ce qui
  partirait maintenant sans rien envoyer ;
- **notifications par incident** (`notify.py`, table `notifications`,
  `/notifications`, `POST /notify`) : une par incident et par moment —
  ouverture, escalade (non acquitté après le délai, une seule fois,
  principe `escalation`), résolution si la politique le veut — jamais par
  événement (`notify-per-incident`) ; canaux SMS et courriel par la copie
  de `shared/secrets_alert.py` (mêmes `SECRETS_ALERT_*` que le PRA,
  si-agent et UPS), webhook `CORTEX_NOTIFY_WEBHOOK_URL` (JSON : texte,
  moment, priorité, politique, incident avec hypothèses) ; `CORTEX_NOTIFY=0`
  journalise sans envoyer ; le résultat par canal est conservé ;
- **silences de maintenance** (table `silences`, `/silences`, `POST`,
  `DELETE`) : nom, ticket, plage horaire, cible (sites, entités, rôles ou
  tout) ; un incident couvert reste visible et compté mais n'est pas
  notifié, la raison « silence « … » (ticket) » est tracée
  (`silence-maintenance`) ;
- **statistiques** (`/kpis?days=`) : MTTA (accusé) et MTTR (clôture) —
  moyenne, médiane, max — par site, par rôle de la cause, par sévérité ;
  incidents par cause racine ; taux de faux positifs par règle (annonces
  jugées) et par principe (retours) ; couverture (entités sans
  supervision, sans position, sites sans position) ; évolution semaine
  par semaine (ouverts, critiques, clos) ;
- **rattachement des tuiles d'origine** : le détail d'un incident propose
  « ↗ tuile si-agent / ups / … » d'après ses sources, la fiche
  d'intervention de la cause, acquitter, clore ; il affiche la politique
  appliquée avec sa raison, le silence en cours et les notifications
  envoyées.

## Principes (partis pris) — `cortex/api/principles.py`

Quarante principes nommés, chacun avec sa confiance de base, son énoncé
et sa limite connue : identité (IP, MAC, nom), relations (passerelle,
relais, port servi → rôle, même site, onduleur du site, sonde, borne d'un
client WiFi, route déclarée), rôle (OUI du constructeur, classification du
nom, référentiel déclaré), position (les huit barreaux de l'échelle +
héritage de lieu), causalité (amont d'abord, fenêtre + relation,
regroupement par site, événement isolé, séquence apprise, règle
confirmée, anticipation), signaux faibles (écart, tendance, habitude
horaire), alerte (politique par rôle et lieu, une notification par
incident, escalade, silence), présentation (sévérité max, changement
entre deux collectes, non supervisée). La confiance **mesurée** d'un principe
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
`/entities/<clé>/intervention`, `/layers?only=` ; depuis #465 : `/rules`,
`POST /rules/<id>/confirm|reject|reset`, `/predictions?pending=`,
`/drifts`, `/samples?entity&metric`, `POST /learn` ; depuis #466 :
`/policies`, `PUT /policies`, `DELETE /policies/<id>`, `/policies/preview`,
`/silences`, `POST /silences`, `DELETE /silences/<id>`, `/notifications`,
`POST /notify`, `/kpis?days=`.

## Tuile

Thématique Supervision, premier onglet : incidents (cause proposée,
confiance en mots et en %, détail avec politique appliquée et sa raison,
notifications envoyées, silence, actions — tuiles d'origine, fiche
d'intervention de la cause, acquitter, clore —, hypothèses votables,
annonces en cours, entités, relations utilisées, événements), **Alertes &
KPI** (statistiques MTTA / MTTR par site, rôle et sévérité, causes
racines, semaine par semaine, couverture, faux positifs ; politiques
d'alerte modifiables ; silences de maintenance ; journal des
notifications ; aperçu des décisions), **Anticipation**
(annonces avec échéance et issue, exactitude ; règles apprises avec
confirmer / rejeter ; dérives en cours et séries suivies avec
mini-courbe), **Architecture** (SVG : une colonne par
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

Étape 4 (#465) : 18 tests purs (les trois nouveaux : extraction des
règles — entités et par rôle, bruit écarté, pas de A → A ; annonce avec
message, échéance et confiance, rien si B est déjà là ou trop tard,
jugement juste / fausse, confiance qui baisse avec les fausses ; dérives
— saut de CPU critique, tendance disque vers 90 % en ~30 h, série stable
et série trop courte muettes — et mesures depuis les trois sources) ;
chaîne réelle : l'historique du central produit à lui seul 10 règles
proposées (ex. « agent-offline sur vm suit config-applied sur vm dans
5 min, 7 fois sur 8 ») ; avec un historique semé (4 surcharges d'onduleur
suivies de la perte de srv-fichiers-01) et une surcharge ouverte
maintenant : annonce « agent-offline sur srv-fichiers-01 suit
habituellement ups:overload sur UPS-Siege dans 5 min (4 fois sur 5) »,
confirmation de la règle → confiance 48 % → 72 %, principe
`sequence-learned` mesuré à 68 % ; mesures semées (disque +0,4 %/h, CPU
20 % → 85 %) → deux dérives ouvertes, intégrées à l'incident de vm ;
onglet Anticipation sous Chromium ; 171 tests Node. **Non vérifié** :
apprentissage sur un vrai historique long, netprobe réel.

Étape 5 (#466) : 21 tests purs (les trois nouveaux : choix de politique
par rôle / site / sévérité et validation ; plan de notifications —
ouverture, canal indisponible filtré, pas de doublon, escalade une seule
fois après le délai, rien si acquitté, « résolu » après clôture, silence
avec ticket tracé puis expiré, silence par rôle non couvrant ; MTTA /
MTTR par site, rôle, sévérité, causes racines, faux positifs, couverture,
semaines, tuiles d'origine) ; chaîne réelle avec un webhook récepteur :
5 incidents → 5 notifications d'ouverture (une chacune), priorité haute
pour les onduleurs, normale pour les hôtes ; notification d'ouverture
antidatée → une escalade « non acquitté 114 min après notification » et
une seule ; silence sur le site bureau (ticket T-4512) → l'incident de
l'onduleur du bureau est tu avec sa raison ; politique modifiée par
`PUT` ; accusé d'un incident → MTTA 10,5 h dans `/kpis` ; onglet Alertes
& KPI sous Chromium ; 172 tests Node. **Non vérifié** : SMS et courriel
réels (module partagé déjà éprouvé par le PRA, si-agent et UPS).

## Suite

Les cinq étapes du découpage #461 sont livrées (#462 à #466). Reste, hors
découpage : déploiement réel sur « super » et lecture des sources réelles
(classifier, Nebula, IPAM, geo-catalog, netprobe), SMS / courriel réels,
filtrage syslog à l'entrée (point de vigilance de l'analyse), et les
tuiles d'origine gardées en onglets de la thématique Supervision.
