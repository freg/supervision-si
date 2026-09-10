# Analyse : vers une tuile unique « Découverte · Localisation · Causalité » (livraison #461, analyse seulement)

Demandé : « analyser toutes les fonctionnalités automatiques ou
semi-automatiques de localisation/géoloc, d'identification d'architecture
réseau, d'exploration des données à destination de la supervision pour en
faire une tuile unique avec un corollaire supervision et alerte,
statistiques et rapprochement de cascade d'évènements », autour de trois
idées : la découverte réseau (routes, services, rôles), la position (lieu,
géo, pour l'intervention ou l'éclairage carto), la détection et
l'anticipation de chaînes causales dans les dysfonctionnements. Ce
document est l'analyse du hub tel qu'il est (livraison #460), avec les
propositions d'évolution ; rien n'est construit ici.

## 1. Ce qui existe déjà — inventaire

### 1.1 Découverte et identification de l'architecture réseau

| Module | Ce qui est automatique | Ce qui est calculé | Limite actuelle |
|---|---|---|---|
| network-agent | capture passive permanente, DNS inverse toutes les 30 s, relevés horaires | appareils, services (destinataires seulement), liens et volumes, sous-réseaux observés, `external_relay_count` → **un seul rôle deviné** (« passerelle probable ») | `network_depth` (profondeur pN.M) est déclaratif ; aucune topologie déduite ; pas de fusion inter-segments |
| netmap-orchestrator | 3 règles au fil de l'eau (nouvel appareil, sans service → proposer nmap, port 161 → proposer SNMP) | suggestions persistantes et rafraîchies | pas de règle sur les routes ni les rôles ; rien sur les liens |
| netprobe | ordonnanceur (ping/smokeping, nmap, iperf3, tcpdump), 2 analyseurs (dégradation de latence, nouveaux ports ouverts) | comparaisons temporelles intra-cible | pas de corrélation inter-cibles |
| si-agent netview | par hôte, sans émettre : interfaces, **routes** (`ip route`), voisins ARP/NDP, pairs `ss` (ports, processus), DNS | résumé par agent | jamais consolidé entre agents ; les routes ne sont pas croisées avec network-agent |
| classifier-api | classification d'un nom d'hôte par dictionnaires (retour humain) | catégorie sémantique | catégorie ≠ rôle réseau ; pas de rapprochement avec les services vus |
| snmp-api, nebula-api, ipam/zenoss | interrogation à la demande, imports, listes d'IP | débits SNMP, référentiels | aucune découverte : cibles saisies ou suggérées |
| architecture-api | import idempotent depuis network-agent | équipements/interfaces/liens déclarés | aucun calcul topologique |
| Fusion IP/MAC, cycle agile | jointures côté navigateur, tableau de bord | — | rien de persisté, pas de graphe unifié |

Il manque donc : une **table de rôles** (routeur, passerelle, DHCP, DNS,
serveur applicatif, imprimante, poste, IoT, borne WiFi…) déduite de
plusieurs indices (ports servis, `external_relay_count`, routes vues par
les agents, classification du nom, OUI de la MAC, présence dans IPAM /
Nebula), une **table de routes** consolidée (ce que chaque hôte sait de
ses chemins de sortie, croisé avec les passerelles vues dans le trafic),
et un **graphe d'architecture** persistant (nœuds = équipements fusionnés
par IP/MAC, arêtes = liens observés, routes, tunnels, bastion) — le hub
sait déjà fusionner (`supervisedItems.mergeItems`, `buildLinks`) mais
seulement en mémoire du navigateur, sans historique.

### 1.2 Localisation

| Module | Automatique | Calculé | Limite |
|---|---|---|---|
| pixel-grid géolocalisations | résolution nom → localisation (alias, équivalences sémantiques, similarité avec contrainte sur les nombres, seuil 0,75 → statut `auto`) ; IP publique → GeoIP ; IP privée → « en attente » | correspondances `auto/suggested/validated/rejected/manual` | déclenchée par l'affichage, pas cadencée ; IP privée jamais positionnée seule |
| geo-catalog-api | `/sync` reconstruit le catalogue en gardant les décisions ; `catalog.interpret` combine références (commune, BAN, OSM) avec précision, confiance 0-100, accord, exclusion des incohérences (> 10 km) | position la plus sûre par lieu | synchronisation déclenchée à la main |
| Supervision SI (hub) | `knownPositions` puis `deducePositions` : moyenne pondérée des voisins positionnés sur le graphe des liens (sites = poids 1000, flux = log du volume), chaîne de déduction restituée | position d'un équipement sans coordonnées | recalculée à chaque affichage, jamais mémorisée ; pas de notion de bâtiment/salle/baie exploitée |
| geo-import-api | import SIG, corrélations sémantique / géographique / temporelle en SQL | couches PostGIS | front historique seulement, pas relié à la supervision |

Il manque : une **hiérarchie de lieux** (site → bâtiment → étage → salle →
baie) stockée une fois et partagée par tous les modules (network-agent,
netprobe, si-agent, UPS n'ont qu'un « site » textuel), une **position
mémorisée avec sa provenance** (déclarée, résolue, déduite, GeoIP) et sa
date, un cadencement des résolutions, et deux usages distincts de la
position : l'**intervention** (où aller, qui est sur place, quel accès —
lié au bastion et aux tickets) et l'**éclairage carto** (couches, halos
d'incidents, densité, zones sans couverture de supervision).

### 1.3 Événements, alertes, analyse

Cinq schémas d'événements cloisonnés : `events` si-agent (kind, severity,
message, notified), `vig_signals` vigilance (4 signaux, croisement
network-agent × classifier), `ups_alerts` (hystérésis, dérive), `suggestions`
orchestrateur, constats netprobe ; plus le syslog brut (rsyslog-listener,
memory-api : statistiques descriptives) et la timeline du hub (événements
d'usage, déconnectée). Aucun bus commun, aucune corrélation « A puis B
dans N minutes », aucune fenêtre glissante inter-sources, pas d'escalade
ni d'accusé unifié (seul UPS a `acked_at`), pas d'anomalie statistique
(seuils fixes et comparaisons avant/après seulement), notifications
filtrées par sévérité + cooldown sans déduplication sémantique. Le seul
rapprochement transverse existant est `buildProposals` / `mergeItems`
(par identité d'équipement, en mémoire du navigateur).

## 2. Ce qu'on peut réutiliser tel quel

Les briques de fusion (`mergeItems` par IP/MAC, `buildLinks`,
`deducePositions` avec chaîne restituée), les résolveurs de noms
(`name_resolver`, `catalog.interpret`), les analyseurs temporels netprobe
(le motif « fenêtre récente vs ancienne, jamais de seuil absolu » est le
bon), l'hystérésis et la dérive UPS, les suggestions persistantes et
rafraîchies de l'orchestrateur (le bon modèle pour une « alerte vivante »),
la classification par dictionnaires avec retour humain, le bandeau
d'événements et `events_summary`. Rien de tout cela n'est à réécrire ;
il faut les **faire converger** derrière un modèle commun.

## 3. Proposition : une tuile « Cortex » (nom de travail) en trois volets et un corollaire

### 3.1 Modèle commun (nouveau service `cortex-api`, ou extension de vigilance-api)

Trois tables partagées, alimentées par des collecteurs qui lisent les API
existantes (aucun module d'origine modifié dans un premier temps) :

- **entités** : identité fusionnée (IP, MAC, nom, agent, cible UPS/SNMP,
  appareil Nebula, entrée IPAM), rôle(s) déduit(s) avec score et indices,
  lieu (référence à la hiérarchie), origines ;
- **relations** : lien observé (volume), route (hôte → passerelle →
  sous-réseau), dépendance déclarée ou déduite (serveur ↔ base, hôte ↔
  onduleur, site ↔ liaison WAN, service ↔ DNS), tunnel, accès bastion ;
- **événements normalisés** : `{at, source, kind, severity, entity,
  relation?, message, raw_ref, state (open/acked/closed), fingerprint}`,
  dédupliqués par empreinte, avec cycle de vie (ouverture, rafraîchi,
  fermeture, acquittement), quelle que soit la source (si-agent, vigilance,
  UPS, netprobe, orchestrateur, syslog filtré, bastion, sauvegardes).

### 3.2 Volet 1 — Découverte : routes, services, rôles

Automatique : une passe périodique (toutes les 30 min, comme vigilance)
qui croise network-agent (services, liens, passerelle probable), les
netviews si-agent (routes réelles des hôtes, voisins, processus derrière
les ports), les scans netprobe, le classificateur, l'OUI des MAC, IPAM et
Nebula, et en tire pour chaque entité une liste de **rôles pondérés**
(règles explicables : « sert 53/udp à > 5 clients → DNS », « passerelle
par défaut de 12 hôtes → routeur de site », « 161 ouvert + OUI Zyxel →
switch manageable », « 9100 → imprimante », « 443 + nom classé
"application" → serveur applicatif ») et une **table de routes** (qui sort
par où). Semi-automatique : les rôles à faible score deviennent des
propositions à confirmer (même mécanisme que `classify/confirm` et que
les suggestions de l'orchestrateur) ; une confirmation humaine alimente le
dictionnaire de règles. Sortie : un graphe d'architecture persistant
(remplace l'import manuel vers architecture-api, ou l'alimente), une vue
« ce qui a changé depuis hier » (nouvel appareil, nouveau service, route
qui a changé, rôle qui bascule), et l'analyse réseau du bastion y trouve
ses cibles.

### 3.3 Volet 2 — Position : lieu, géo, intervention, éclairage carto

Automatique : hiérarchie de lieux (site → bâtiment → étage → salle →
baie) dans geo-catalog, position mémorisée par entité avec provenance et
date (déclarée > validée > résolue par nom > déduite par voisinage >
GeoIP > repli), résolution cadencée (et non à l'affichage), déduction par
voisinage reprise de `deducePositions` mais **persistée** avec sa chaîne,
et propagation par relation (un hôte prend la salle de son switch d'accès,
un onduleur celle des hôtes qu'il alimente). Deux rendus : **intervention**
— fiche « où aller » pour une entité en défaut (site, bâtiment, salle,
accès bastion disponible, contact du site, ticket ouvert, matériel de
secours à proximité) ; **éclairage carto** — sur la carte de Supervision
SI, couches activables : halos d'incidents en cours pondérés par la
sévérité, densité d'équipements par lieu, zones sans supervision, chemins
de dépendance (site coupé quand la liaison WAN tombe). Les lieux sans
position deviennent une file de travail (déjà amorcée par geo-catalog
« todo »).

### 3.4 Volet 3 — Causalité : détection et anticipation des chaînes

Détection, en trois étages de complexité croissante, tous explicables :

1. **Fenêtre glissante et regroupement** : les événements normalisés qui
   tombent dans une même fenêtre (5 min, réglable) et partagent une
   relation (même passerelle, même site, même onduleur, même segment)
   forment un **incident** ; l'entité la plus « amont » dans le graphe des
   dépendances est proposée comme cause racine (ex. onduleur en alarme →
   10 hôtes hors ligne → 3 sondes silencieuses : un incident, une cause).
   C'est le rapprochement de cascade demandé, et il ne demande que le
   graphe du volet 1 et la file d'événements.
2. **Séquences apprises** : à partir de l'historique (memory-api, events),
   comptage des paires « A précède B en < N min » plus fréquentes que le
   hasard (test simple sur les co-occurrences) ; les motifs retenus
   deviennent des règles proposées, à confirmer, qui servent ensuite à
   **anticiper** : quand A se produit, le hub annonce « B suit
   habituellement dans 4 min (12 fois sur 15) » et pré-ouvre l'incident.
3. **Signaux faibles** : dérives (le motif UPS `drift_checks` généralisé
   aux mesures si-agent, latences netprobe, volumes network-agent),
   saisonnalité simple (même heure, même jour), pour signaler avant le
   seuil.

Chaque incident porte sa chaîne (événements, relations utilisées, règle
appliquée), un accusé et un état, et se retrouve dans la timeline du hub
et dans les notifications (une notification par incident, pas par
événement — c'est là que se règle la déduplication).

### 3.5 Corollaire : supervision, alertes, statistiques

Une seule file d'incidents avec sévérité, état, cause proposée, entités,
lieu, actions (ouvrir la tuile d'origine, créer un ticket, sortir un
accès bastion vers la cible, marquer faux positif — ce qui nourrit les
règles). Statistiques : MTTA/MTTR par site et par rôle, incidents par
cause racine, top des entités bruyantes, taux de faux positifs par règle,
couverture (entités sans supervision, lieux sans position), évolution
semaine par semaine. Alertes : politique par rôle et par lieu (un routeur
de site vaut plus qu'un poste), notifications par incident, escalade si
non acquitté, silence planifié (maintenance) hérité des tickets.

## 4. Découpage proposé (chaque étape utile seule)

1. **Modèle et collecte** : `cortex-api`, tables entités / relations /
   événements normalisés, collecteurs des cinq sources d'événements et des
   sources de découverte, empreintes et cycle de vie ; tuile « Cortex »
   minimale = file d'incidents (regroupement par fenêtre + relation).
2. **Rôles et routes** : règles de rôles pondérés, table de routes,
   propositions à confirmer, graphe d'architecture persistant, vue « ce qui
   a changé ».
3. **Positions** : hiérarchie de lieux, position mémorisée avec
   provenance, résolution cadencée, propagation par relation, fiche
   d'intervention, couches carto.
4. **Causalité apprise et anticipation** : séquences fréquentes, règles
   proposées, annonce anticipée, dérives généralisées.
5. **Statistiques et politiques d'alerte** ; rattachement des tuiles
   d'origine (elles restent, la thématique Supervision les garde en
   onglets ; Cortex devient l'entrée principale).

## 5. Points de vigilance

Le graphe d'architecture ne doit jamais devenir une saisie parallèle :
tout ce qui est déduit est marqué comme tel, révisable, et une décision
humaine l'emporte (motif déjà en place dans geo-catalog et location_matches).
Les règles de causalité doivent rester lisibles (pas de boîte noire) et
mesurées (taux de faux positifs affiché par règle). Les cadences
(découverte 30 min, positions 1 h, fenêtre d'incident 5 min) sont des
réglages `.env`. Le volume d'événements syslog impose un filtrage à
l'entrée (facility/sévérité, motifs) avant normalisation. Enfin, tout ce
qui touche aux accès (bastion, tickets, contacts de site) reste derrière
les droits existants.
