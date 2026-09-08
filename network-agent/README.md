# Agent d'exploration réseau (livraison #233)

Backlog item 20 -- "Agent d'exploration réseau ACTIF + tuile unifiée
(fusion de l'ancienne tuile 'big-brother' et de l'agent Nebula 'à
concevoir')". Par opposition à la supervision PASSIVE existante
(zenoss, cacti, ipam...).

**Clarifié explicitement avec la personne avant de coder** : "un
seul agent car je suis en réseau (VPN) avec le réseau interne géré
par nebula, une seule tuile même si on distinguera les sites et les
réseaux dans l'organisation des données." Un agent, en conteneur
Docker, déployé sur un poste ayant accès EN VPN au réseau interne --
pas un déploiement multi-points.

## Volets demandés, couverts dans cette première tranche

- Agent en conteneur Docker, accès VPN -- ✅ (l'agent lui-même ne
  gère PAS le VPN, il capture sur l'interface réseau du conteneur/de
  l'hôte, `network_mode: host` recommandé -- voir docker-compose.yml).
- Exploration à base de `tcpdump`, repérage PROGRESSIF -- ✅
  (`first_seen` jamais réécrit, voir `store.py`).
- Archivage des VOLUMES échangés -- ✅ (`bytes_total` par appareil).
- Identification des SERVICES -- ✅ (port TCP/UDP destination par
  appareil, voir limite assumée plus bas).
- Volet routeur/switch, RÔLES (NAT et autres) -- ✅ (heuristique de
  détection de passerelle, voir `capture.py`).
- Transmission RÉGULIÈRE vers UNE SEULE tuile, données organisées par
  site/réseau -- ✅ (`NetworkAgentView.jsx`, sélecteur site → segment,
  un seul écran).
- Statistiques des USAGERS -- **PAS fait** dans cette tranche
  (nécessiterait une notion d'identité utilisateur au-delà de
  l'adresse MAC, hors de portée du seul trafic réseau capturé ici).

Référence donnée par la personne (Tkined/Scotty, Jürgen Schönwälder,
années 1990) -- notée mais pas suivie en détail : ce socle est bâti
sur des principes similaires (découverte progressive par observation
du trafic) sans reprendre son architecture Tcl/Tk spécifique.

## Choix techniques -- décisions prises pour avancer

**Analyseur pcap en Python PUR** (`pcap_parser.py`) -- ni `dpkt` ni
`scapy` ne sont installables dans cet environnement de développement
(même famille de restriction que `pysnmp`/`sshpass`/`npm` rencontrée
plus tôt dans ce projet). Plutôt que de dépendre d'un paquet dont
même la présence côté déploiement final n'est pas garantie, ce module
réimplémente le format pcap et les en-têtes Ethernet/IPv4/ARP/TCP/UDP
-- des structures binaires de taille fixe, documentées depuis les
années 1990, ne nécessitant réellement aucune bibliothèque pour ce
sous-ensemble. **Portée volontairement limitée** : IPv4 seulement
(IPv6 détecté et ignoré proprement), pas de réassemblage de fragments,
pas de suivi de flux TCP complet -- un résumé par paquet, suffisant
pour l'inventaire progressif visé ici.

**Détection du rôle passerelle/routeur** (`capture.py`) -- heuristique
RÉSEAU, pas devinée : la résolution ARP ne peut résoudre qu'une IP du
MÊME sous-réseau -- pour toute IP destination HORS du sous-réseau
local (CIDR configuré), l'OS résout automatiquement la MAC de la
PASSERELLE PAR DÉFAUT à la place (mécanisme de routage IP standard
sur Ethernet). Une MAC destination qui reçoit régulièrement des
paquets dont l'IP finale sort du sous-réseau est donc très probablement
une passerelle -- comptée comme `external_relay_count`, seuil
volontairement bas (5), toujours signalée comme une HYPOTHÈSE
("passerelle probable"), jamais une certitude affichée.

**Simplification assumée pour les services** : un port TCP/UDP
destination est attribué à l'appareil identifié par sa MAC
destinataire, QUE ce trafic soit interne au segment OU relayé vers
l'extérieur. Un appareil déjà repéré comme passerelle accumulera donc
des services divers, reflet du trafic RELAYÉ plutôt que de services
qu'il offre lui-même -- limite connue, pas raffinée davantage dans
cette première tranche (nécessiterait de suivre des flux TCP/UDP
complets, pas seulement des paquets isolés).

**Modèle de données site → segment → appareil → services** -- reflète
directement la clarification de la personne ("on distinguera les
sites et les réseaux dans l'organisation des données") même si un
seul agent (donc généralement un seul site/segment actifs) tourne
réellement pour l'instant -- le modèle est prêt pour plusieurs agents
le jour où ce sera nécessaire, sans migration de schéma.

## Déploiement -- point à confirmer par la personne

`tcpdump` nécessite `CAP_NET_RAW`/`CAP_NET_ADMIN` (déjà ajoutés dans
`docker-compose.yml`). Pour capturer le VRAI trafic du réseau distant
(via le VPN de l'hôte) plutôt que seulement le trafic interne à Docker,
`network_mode: host` est probablement nécessaire -- **décision de
déploiement dépendant de l'environnement réel de la personne, jamais
présumée ici sans certitude** (non ajoutée par défaut dans
`docker-compose.yml`, à activer/adapter selon le poste de déploiement
réel).

`NETWORK_AGENT_SITE_NAME` et `NETWORK_AGENT_SEGMENT_LABEL` sont
REQUIS pour que la capture démarre réellement (sinon signalé
clairement via `GET /capture/status`, jamais un crash silencieux).
`NETWORK_AGENT_SEGMENT_CIDR` optionnel mais FORTEMENT recommandé --
sans lui, aucune détection de passerelle n'est possible.

## API

- `GET /capture/status` -- état du thread de capture en arrière-plan
  (`running`, `last_error`, `started_at`, `packets_processed`).
- `GET /sites` -- structure imbriquée site → segments.
- `GET /devices?segment_id=N` -- appareils découverts dans un segment.
- `GET /devices/<id>/services` -- services observés pour un appareil.

## Vérifié réellement, en profondeur

**`pcap_parser.py`** -- testé exhaustivement avec des paquets
synthétiques construits selon la spécification exacte du format :
TCP, UDP, ARP, IPv6 (rejeté proprement, jamais confondu avec IPv4),
paquets tronqués/malformés (jamais une exception), flux invalides,
**les deux boutismes** (little/big-endian) -- ⚠️ deux vrais pièges de
construction rencontrés en écrivant CE TEST (pas dans l'analyseur
lui-même) autour du calcul de boutisme inversé, corrigés avant de
conclure.

**`store.py`** -- découverte VRAIMENT progressive confirmée
(`first_seen` jamais réécrit sur un appareil déjà connu), dédoublonnage
par MAC, gestion d'un changement d'IP (DHCP) sans dupliquer l'appareil,
détection de rôle au seuil configuré, cumul correct des services.

**`capture.py`** -- scénario réseau complet et réaliste simulé :
poste local parlant à un serveur local (service HTTPS correctement
attribué), poste local relayant du trafic vers Internet via une
passerelle (détectée avec le bon compteur de relais), appareil
découvert PAR ARP SEUL (jamais vu autrement en IP), broadcast JAMAIS
traité comme un appareil -- tout confirmé en un seul passage.

**`app.py`** -- testé en conditions RÉELLEMENT dégradées : `tcpdump`
est absent de cet environnement de développement, confirmé que
l'application entière reste pleinement fonctionnelle, l'échec est
signalé clairement via `/capture/status`, jamais un crash du service
ni du thread de fond (qui continue de réessayer).

**`NetworkAgentView.jsx`** -- structure JSX vérifiée, logique de
formatage des volumes et de sélection de segment testée en isolation.

## Premier retour de déploiement réel (livraison #234)

**Bug réel trouvé au tout premier test en conditions réelles** (merci
à la personne d'avoir testé immédiatement) : `capture.py` capturait
`stderr` de `tcpdump` mais ne le LISAIT jamais en cas d'échec précoce
-- `GET /capture/status` affichait alors le message générique de
`pcap_parser` ("flux vide -- aucun en-tête pcap"), techniquement
vrai mais masquant la VRAIE raison (permission refusée, interface
inexistante...), toujours disponible sur `stderr` de `tcpdump`
lui-même. Corrigé : même motif que
`ssh-tunnels/api/tunnel_process.py` (#210) -- courte fenêtre
d'observation (0,5s) après le lancement, lecture de `stderr` si
`tcpdump` s'est arrêté pendant cette fenêtre, message REMONTÉ
TEL QUEL à `GET /capture/status` plutôt que l'erreur de parsing en
aval. Testé avec le cas RÉEL rencontré ("You don't have permission to
capture on that device") -- confirmé que la vraie raison est
désormais visible.

## Deuxième retour de déploiement réel (livraison #238)

**`network_mode: host` CONFIRMÉ nécessaire** -- capture d'écran
fournie par la personne : `tcpdump: ens18: No such device exists`.
Exactement le point resté incertain dans `docker-compose.yml`
(commentaire "RECOMMANDÉ... à confirmer"). Appliqué : `ens18` (et
plus généralement toute interface RÉELLE de l'hôte) est désormais
visible depuis le conteneur.

**Conséquence en cascade, traitée dans la même livraison** : un
conteneur en `network_mode: host` quitte le réseau Docker interne
partagé -- `network-agent-api:5000` (le nom Docker habituel) n'était
donc plus joignable par la passerelle (`tls-proxy`). Corrigé en deux
temps :
- `gateway/docker-compose.yml` : `extra_hosts:
  ["host.docker.internal:host-gateway"]` sur `tls-proxy`.
- `tls-proxy/render_nginx_conf.py` : nouveau gabarit
  `API_LOCATION_TEMPLATE_STATIC` (résolution système classique, au
  CHARGEMENT de la config) réservé aux services en
  `network_mode: host` -- **trouvaille vérifiée AVANT d'écrire une
  seule ligne de config**, pas après coup : le résolveur DYNAMIQUE de
  nginx (`resolver 127.0.0.11`, utilisé par tous les AUTRES services
  via `set $backend` + variable) ne consulte JAMAIS `/etc/hosts` --
  `extra_hosts` seul serait resté SANS EFFET avec le gabarit
  dynamique existant (confirmé par la documentation nginx/Docker et
  un incident réel équivalent chez un tiers, nginx-proxy-manager
  #5344, recherché avant de conclure).

**Vérifié réellement** : configuration nginx complète régénérée et
inspectée -- la route `/api/network-agent/` utilise bien un
`proxy_pass` LITTÉRAL (`http://host.docker.internal:5000...`, jamais
`$backend`). Non-régression confirmée : les 30 AUTRES routes (api +
spa + keycloak) gardent toutes leur résolution dynamique inchangée,
un seul service utilise le nouveau mode statique.

## ⚠️ Jamais vérifié dans cet environnement (mais CONFIRMÉ en déploiement réel, voir #240 plus bas)

- La capture RÉELLE elle-même (`tcpdump` non exécutable ici, aucune
  interface réseau exploitable dans ce sandbox) -- **CONFIRMÉE
  FONCTIONNELLE en #240**, voir plus bas.
- Le comportement en conditions réelles de charge (volume de trafic
  réel, performance du thread de fond sur une longue durée) --
  toujours pas vérifié, seulement un premier fonctionnement confirmé.
- `network_mode: host` et l'articulation réelle avec un VPN --
  `network_mode: host` lui-même confirmé nécessaire et fonctionnel
  (#238-239) ; l'articulation avec un VPN spécifiquement reste à
  observer dans la durée.

À tester en PRIORITÉ une fois déployé, en commençant par
`GET /capture/status` pour confirmer que `tcpdump` tourne
effectivement avec les capacités accordées.

## Troisième retour de déploiement réel : collision de port (livraison #239)

**`host.docker.internal` NE FONCTIONNE PAS EN PRATIQUE** malgré la
correction #238 -- vrai retour de la personne : `nginx` renvoyait
`host.docker.internal could not be resolved (3: Host not found)`.
Recherché ce qui se passait réellement : même un `proxy_pass`
LITTÉRAL (le gabarit `api-static` de #238) passe par le résolveur
`resolver 127.0.0.11` dès qu'il est déclaré dans le bloc englobant
nginx -- l'hypothèse initiale (littéral = résolution système,
consultant `/etc/hosts`) était FAUSSE. Ce résolveur ne consulte
JAMAIS `/etc/hosts`, quelle que soit la façon dont la cible est
écrite dans la config.

**Corrigé définitivement** : `tls-proxy/render_nginx_conf.py` utilise
désormais directement l'ADRESSE IP réelle de l'hôte (`HOST_IP`, déjà
configuré par la personne pour les URLs publiques du hub -- jamais
une deuxième variable à maintenir) -- une IP littérale ne nécessite
AUCUNE résolution DNS, contournant le problème à la racine plutôt que
de chercher un autre nom à faire résoudre. `extra_hosts` (ajouté en
#238, devenu inutile) retiré de `gateway/docker-compose.yml`.

**Deuxième trouvaille dans les mêmes logs** : `network-agent-api`
plantait en boucle ("Connection in use: ('0.0.0.0', 5000)") --
`network_mode: host` (#238) fait que ce service se lie DIRECTEMENT
sur un port de l'hôte, plus un port Docker isolé -- port 5000 déjà
occupé par un `docker-registry` tournant sur la même machine.
Corrigé : port configurable (`NETWORK_AGENT_HOST_PORT`, défaut 15000,
bien moins disputé que 5000) -- Dockerfile passé en forme SHELL pour
permettre l'interpolation de cette variable dans la commande
`gunicorn`.

**Vérifié réellement** : configuration régénérée avec un `HOST_IP`
réaliste -- `proxy_pass http://192.0.2.10:15000...` confirmé (IP
littérale, port 15000, plus aucune trace de `host.docker.internal`).
Repli sur `127.0.0.1` si `HOST_IP` absent testé. Non-régression
confirmée : les 30 autres routes inchangées.

## Première capture réelle CONFIRMÉE fonctionnelle (livraison #240)

Après les correctifs de #238-239 (`network_mode: host`, port 15000,
routage `HOST_IP`) : confirmation directe de la personne -- la
capture tourne, des appareils sont découverts, **et la détection de
passerelle a correctement identifié une vraie passerelle sur son
réseau**.

C'est la partie la plus significative à retenir : cette détection
reposait sur un raisonnement RÉSEAU (la résolution ARP ne peut
résoudre qu'une IP du même sous-réseau -- pour une IP hors
sous-réseau, l'OS résout la MAC de la passerelle par défaut à la
place, voir `capture.py`) testé jusqu'ici uniquement avec des
scénarios synthétiques construits à la main. Sa validation contre du
VRAI trafic, sur un VRAI réseau, avec une VRAIE passerelle, est la
confirmation la plus importante de tout ce module -- le cœur de ce
qui était demandé ("routeur/switch dédié -- identifier et évaluer
leurs RÔLES") fonctionne bien tel que conçu, pas seulement tel que
testé.

Reste à observer dans la durée (comportement de charge, stabilité du
thread de fond) -- mais le socle fonctionnel du module n'est plus une
hypothèse.

## Six demandes d'ergonomie/fonctionnalités (livraison #250)

Demandées explicitement par la personne après un premier usage réel,
sur deux captures d'écran (statut de capture réelle, résultats réels
de Rétro-ingénierie sur son code).

**Échanges entre appareils ("qui parle à qui")** -- nouvelle table
`na_device_links`, DIRECTIONNELLE (device_a = source, device_b =
destination) plutôt qu'un lien normalisé -- garde l'information la
plus riche, une conversation bidirectionnelle apparaît naturellement
comme deux lignes (A→B et B→A), révélant les motifs asymétriques
(client qui envoie beaucoup, réponse plus légère) plutôt que de les
fondre en une moyenne. Enregistré automatiquement dans `capture.py`
quand les DEUX bouts d'un paquet sont des appareils identifiés (un
ARP source-seule, ou un broadcast en destination, ne créent jamais
d'échange). Nouvelle route `GET /links?segment_id=N`. Rejoint
directement l'idée de graphe d'architecture réseau/inspiration
Tkined-Scotty déjà discutée avec la personne.

**Résolution DNS** -- nouveau `dns_resolver.py`, DEUX mécanismes :
résolveur SYSTÈME par défaut (`socket.gethostbyaddr`, bibliothèque
standard, "depuis l'hôte" au mieux) ; serveur DNS SPÉCIFIQUE si
`NETWORK_AGENT_DNS_SERVER` est configuré ("le faire paramétrer") --
`dnspython` NON installable dans cet environnement de développement
(vérifié explicitement), donc client DNS minimal fait main, MÊME
approche que `pcap_parser.py` pour le format pcap : une seule requête
PTR par UDP, rien d'autre, jamais présenté comme un client DNS
complet. Gère la compression de noms DNS (RFC 1035 §4.1.4, le point
le plus piégeux du protocole) -- testé avec de vraies réponses
construites octet par octet. `NETWORK_AGENT_DEFAULT_DOMAIN` retire un
suffixe des noms résolus pour un affichage plus court. Colonnes
`hostname`/`hostname_resolved_at` ajoutées par migration idempotente
(même motif que `imap-client` #230) -- **testée sur une base
existante simulée** pour confirmer qu'aucune donnée n'est perdue.
Thread de résolution en arrière-plan DISTINCT du thread de capture
(les appels DNS sont lents, jamais mêlés à la boucle par paquet qui
doit rester rapide) -- re-résolution périodique (6h par défaut,
`NETWORK_AGENT_DNS_STALE_SECONDS`) pour suivre un bail DHCP qui
change.

**Limite honnêtement signalée** : ce service tourne en
`network_mode: host` (#238-239) -- son `/etc/resolv.conf` reste celui
géré PAR LE CONTENEUR, Docker ne le fait pas correspondre
automatiquement à celui de l'hôte même en `network_mode: host` --
donc "depuis l'hôte" reste un best-effort, pas une garantie, d'où
l'intérêt réel de `NETWORK_AGENT_DNS_SERVER` en repli fiable.

**Ergonomie de l'interface** -- en-tête global du hub désormais fixe
au défilement (`position: sticky`, appliqué GLOBALEMENT à
`.hub-header` plutôt que par vue -- bénéfice pour tout le hub, pas
seulement cette tuile). Liste des appareils dans un conteneur
défilant propre (`.na-device-list-wrap`) avec en-têtes de colonnes
fixes à l'intérieur. Services représentés par de petits points
colorés (bleu = TCP, ambre = UDP, palette du thème existant) avec le
nom/port/compteur au survol (natif, attribut `title`, aucune
bibliothèque de tooltip ajoutée) -- nouvelle route groupée `GET
/devices/services?segment_id=N` (tous les services de tous les
appareils d'un segment EN UNE SEULE requête, évite un appel par
appareil pour afficher les points sur chaque ligne simultanément).
Détails d'un appareil (services complets + échanges le concernant)
affichés dans un pied de page fixe au clic sur une ligne, plutôt
qu'un panneau qui décale le reste de l'écran.

**Vérifié réellement** : logique d'échanges testée en profondeur
(accumulation vs duplication, direction A→B distincte de B→A, jamais
un échange depuis un ARP ou un broadcast). Client DNS testé avec des
réponses construites à la main, compression ET sans compression, ID
de requête différent jamais associé à tort, réponse vide (NXDOMAIN)
gérée proprement, paquet corrompu jamais une exception. Migration
testée sur une base SQLite existante simulée (ligne préservée,
nouvelles colonnes à NULL). Route groupée de services testée (aucune
collision avec la route existante par appareil malgré des chemins
proches). Logique JSX (sélection/désélection au clic, filtrage des
échanges pour un appareil, repli d'affichage nom d'hôte→MAC) testée
en isolation. Structure JSX complète revérifiée.

**Un vrai bug d'édition trouvé et corrigé en cours de route** : un
remplacement de texte a accidentellement supprimé la ligne de
signature de `apply_role_hints` (le corps de la fonction restait,
orphelin) -- repéré immédiatement par la suite de tests
(`NameError` à l'exécution), corrigé, toute la base de `store.py`
retestée pour confirmer qu'aucune autre régression ne s'était
glissée.

## Reste à faire (issu des six demandes)

- Placement "espace libre à droite" envisagé mais le pied de page a
  été retenu comme solution PRINCIPALE (fonctionne quelle que soit la
  largeur d'écran, contrairement à une colonne latérale qui suppose
  un espace horizontal disponible) -- à ajuster si la personne
  préfère effectivement une colonne latérale après usage réel.
- Détection des échanges jamais testée contre un VRAI volume de
  trafic (uniquement des paquets synthétiques) -- la table pourrait
  croître vite sur un réseau chargé, aucune purge/agrégation
  construite pour l'instant.

## Rémanence -- historique dans le temps (livraison #251)

Demandé explicitement : "j'aimerais beaucoup voir dans le temps des
choses comme : présence des ip/mac, les volumes échangés/usages par
paire d'ip, les services connectés par paire d'ip". Précédé d'une
observation de la personne sur la perte de données au redémarrage --
confirmé : les logs (Memcached) sont VOLONTAIREMENT sans persistance
par conception ; les données `network-agent` (SQLite) DEVRAIENT en
revanche survivre grâce au volume monté, sauf si l'emplacement de
déploiement change à chaque extraction du zip livré (cause probable
la plus courante).

**Toutes les tables existantes (`na_devices`, `na_device_links`)
étaient CUMULATIVES** -- une seule ligne par entité, jamais
d'évolution dans le temps. Corrigé par un mécanisme de RELEVÉS
PÉRIODIQUES :

- Nouvelle table `na_device_link_services` -- services utilisés PAR
  PAIRE d'appareils (table SÉPARÉE de `na_device_links`, additive,
  aucun risque de migration sur une table livrée en #250 pas encore
  confirmée en usage réel). Alimentée automatiquement dans
  `capture.py`, même condition que `na_device_services`.
- Nouvelles tables `na_history_snapshots`/`na_device_presence_history`/
  `na_link_history` -- un relevé = une COPIE PONCTUELLE des compteurs
  cumulatifs à un instant donné (jamais un delta stocké -- garde la
  flexibilité d'interroger n'importe quel intervalle a posteriori).
  Nouveau thread de fond `_run_snapshot_forever`, DISTINCT des deux
  autres (capture, résolution DNS) -- prend un relevé toutes les
  heures par défaut (`NETWORK_AGENT_SNAPSHOT_INTERVAL_SECONDS`), puis
  purge les relevés de plus de 30 jours
  (`NETWORK_AGENT_HISTORY_RETENTION_DAYS`) -- retenue VOLONTAIREMENT
  bornée, jamais une croissance illimitée.

Nouvelles routes : `GET /links/services` (services entre deux
appareils précis, les deux sens confondus), `GET
/devices/<id>/presence-history` (évolution de la présence/volume
d'un appareil), `GET /links/history` (évolution du volume échangé
entre deux appareils).

Côté hub : section "Présence dans le temps" ajoutée au pied de page
de détail d'un appareil (déjà construit en #250) -- un tableau
simple (relevé/IP/volume cumulé), PAS un graphique -- aucune
bibliothèque de graphique disponible côté hub (`package.json` ne
liste que React/oidc, cohérent avec la limite npm déjà rencontrée
ailleurs dans ce projet, "npm inaccessible (403)").

**Vérifié réellement** : service par paire testé (accumulation,
recherche symétrique A↔B). Relevés testés avec une VRAIE PROGRESSION
dans le temps (deux relevés successifs avec du trafic entre les deux,
confirmé que l'évolution est bien visible -- 100→500 puis 500→600,
pas seulement la dernière valeur répétée). Purge testée (retire
l'historique, GARDE les données cumulatives elles-mêmes intactes).
`capture.py` retesté de bout en bout avec un vrai paquet TCP.
Non-régression complète de TOUTES les routes existantes reconfirmée
après cette troisième extension du module dans la même journée.

## Reste à faire (rémanence)

- Volume de relevés jamais testé sur un VRAI réseau chargé (beaucoup
  d'appareils × beaucoup de paires × relevés horaires -- la
  croissance réelle de la base reste à observer, la purge à 30 jours
  est un point de départ raisonnable, pas une valeur validée en
  conditions réelles).
- ~~Pas de graphique -- tableau simple pour l'instant, faute de
  bibliothèque disponible côté hub.~~ **Livré en #400** (barres de delta
  SVG maison, voir section dédiée plus bas).
- ~~Historique du VOLUME PAR PAIRE (`/links/history`) construit et
  testé côté backend, mais PAS ENCORE affiché côté hub~~ **Livré en
  #400** -- clic sur une ligne "Échanges".

## Correctif : fichier manquant au déploiement (livraison #252)

`dns_resolver.py` (résolution DNS, #250) était importé par `app.py`
mais jamais copié par le `Dockerfile` -- oubli réel, confirmé par les
vrais logs `gunicorn` partagés par la personne (`ModuleNotFoundError`).
Corrigé. Une vérification systématique de TOUS les `Dockerfile` du
projet a suivi cette découverte (voir `glpi/README.md` et
`snmp/README.md` pour les deux autres cas trouvés par la même
occasion).

## Découverte de sous-réseaux depuis le trafic observé (livraison #256)

Demandé explicitement, dans le cadre de la préparation GLPI Inventory
(backlog item 21, "combien de segments réseau distincts faut-il
couvrir ?") : "notre module d'exploration doit répondre à cette
question" -- avec le vrai réseau de la personne en exemple : LAN
192.168.0.0/16 avec au moins 3 plages en usage (0.0/24, 1.0/24,
100.0/24), pas encore toutes recensées.

Plutôt que d'exiger un recensement préalable, ce module REGROUPE
maintenant les appareils déjà découverts par sous-réseau -- une
manière de laisser la structure interne réelle du LAN apparaître
d'elle-même, à mesure que la capture avance.

**AUCUNE nouvelle table, aucun nouveau chemin d'écriture dans
`capture.py`** -- calcul PUREMENT en lecture depuis `na_devices` déjà
rempli, groupé côté Python (SQLite n'a pas de fonction CIDR native)
via le module standard `ipaddress`, déjà utilisé ailleurs dans ce
module. Nouvelle fonction `store.list_observed_subnets` + route
`GET /observed-subnets?segment_id=N&prefix_length=24` (granularité
paramétrable, /24 par défaut). Côté hub : section dépliable "Sous-
réseaux découverts depuis le trafic", avec sélecteur de granularité
(/16 à /28).

**Recommandation de configuration pour un LAN structuré comme celui
de la personne** -- `NETWORK_AGENT_SEGMENT_CIDR` devrait être réglé
sur le SUPERNET le plus large pertinent (ex. `192.168.0.0/16`) plutôt
qu'un seul `/24` : la détection de passerelle (voir `capture.py`,
#233) compare le trafic contre CE périmètre pour repérer un relais
externe -- avec un `/16` configuré, le trafic ENTRE deux `/24`
internes (ex. 192.168.0.x vers 192.168.100.x, qui passe forcément par
un routeur/switch L3) reste identifié comme "interne" par cette
comparaison, mais la nouvelle découverte de sous-réseaux révèle
quand même, INDÉPENDAMMENT, que ce sont deux segments distincts --
les deux signaux se complètent, jamais confondus l'un avec l'autre.

**Vérifié réellement** : testé avec un scénario reproduisant
EXACTEMENT le réseau réel décrit (3 plages, tailles différentes) --
les 3 sous-réseaux correctement découverts, triés par nombre
d'appareils décroissant (le plus peuplé en tête -- signal direct de
"où est le trafic réel"), total d'appareils cohérent. Granularité
différente testée (`/16` regroupe tout en un seul, confirmant le
comportement attendu). Segment sans aucun appareil géré proprement
(liste vide, jamais une exception). Route testée de bout en bout, y
compris le paramètre de granularité personnalisé et le rejet propre
d'un `segment_id` manquant. Non-régression complète de toutes les
routes existantes reconfirmée après cette quatrième extension du
module.

## Correctifs d'ergonomie en conditions réelles (livraison #257)

Capture d'écran réelle à l'appui, un appareil (probablement une
passerelle relayant un trafic très divers, voir `capture.py`)
affichait 234 services distincts -- plus de 200 points de couleur
sur une seule ligne du tableau, étalés sur 8+ lignes visuelles :
"très beau mais à travailler pour réduire l'espace pris... il
faudra filtrer intelligemment pour que ça soit utilisable et
visible".

Corrigé -- `MAX_VISIBLE_SERVICE_DOTS = 15` : au-delà, les services
les MOINS significatifs sont résumés par un compteur "+N" plutôt
qu'un point de plus. Les services les PLUS utilisés (déjà triés par
volume décroissant côté backend, voir `store.list_services_by_segment`
#250) restent toujours visibles en premier -- jamais une troncature
arbitraire qui masquerait le signal le plus utile. Conteneur des
points aussi plafonné visuellement (`max-width: 220px`) pour rester
compact quel que soit le nombre affiché. Le tableau détaillé des
services (pied de page, au clic sur une ligne) reçoit le même
traitement -- défilement propre borné à 220px de haut plutôt qu'un
panneau qui grandit sans limite avec un appareil très actif.

Vérifié réellement : logique de limitation testée avec un volume
reproduisant la capture d'écran (234 services) -- exactement 15
points affichés, le plus utilisé en tête, 219 correctement résumés
par le compteur ; avec peu de services (5), aucun compteur inutile
affiché. Structure JSX/CSS revérifiée.

## Intégration avec la classification sémantique (livraison #261)

Suite naturelle du module `classifier/` (#260, backlog item 34) --
un badge de classification apparaît maintenant à côté du nom d'hôte
de chaque appareil découvert, quand `classifier-api` en trouve une
(prénom connu, motif `dhcpNNN`, terme d'un dictionnaire importé).

**Intégration côté HUB, pas côté backend** -- `network-agent-api`
lui-même ne connaît RIEN de `classifier-api` (aucun couplage entre
les deux services) -- `NetworkAgentView.jsx` appelle les deux API en
parallèle et fusionne l'affichage, même logique que
`architecture-api` croisant plusieurs sources, mais ici entièrement
côté client plutôt que server-to-server (plus simple, aucune
dépendance nouvelle entre deux backends déjà indépendants).

Best-effort explicite -- `classifier-api` indisponible ou non
configuré (`VITE_CLASSIFIER_API_BASE_URL` absent) ne bloque JAMAIS
l'affichage des appareils eux-mêmes, juste l'absence de badge. Seuls
les appareils AVEC un nom d'hôte résolu sont soumis à
classification -- un appel groupé (`POST /classify/batch`), jamais un
appel par appareil.

**Vérifié réellement** : logique de filtrage/construction de la
charge utile testée en isolation (seuls les appareils avec hostname
retenus, appel évité si aucun/si `classifier-api` non configuré).
Structure JSX/CSS revérifiée.

## Visualisations des flux -- graphe alluvial + radial tree pondéré (livraison #389)

Backlog item 58, suite de `netmap-orchestrator` (#388) : "les rendus
visuels seront nombreux... démarrons sur des vues connues radial
tree, pixelgrid et ajoutons : graphe alluvial (flux tcpip/udp),
radial tree augmenté avec des liens d'épaisseur proportionnelle au
volume échangé". Section repliable ajoutée dans cette même tuile,
à partir des données `devices`/`links` DÉJÀ chargées (aucun nouvel
appel réseau) :

- **Graphe alluvial** (`hub/src/alluvialLayout.js` +
  `hub/src/components/AlluvialFlowChart.jsx`) -- 2 colonnes (sources
  à gauche, destinations à droite), épaisseur des flux proportionnelle
  au volume. Calcul MANUEL (pas de `d3-sankey` -- confirmé
  INACCESSIBLE depuis l'environnement de développement, réseau
  restreint, 403 même sur `d3` lui-même) -- logique de layout séparée
  du rendu, testable sans navigateur ni `d3`.
- **Radial tree augmenté** (`hub/src/weightedRadialLayout.js` +
  `hub/src/components/WeightedRadialTree.jsx`) -- structure racine ->
  segment -> appareil (même hiérarchie naturelle que
  network-agent-api lui-même), liens croisés entre appareils
  (communications réelles) avec épaisseur proportionnelle au volume,
  PAR-DESSUS la structure. Rendu calqué fidèlement sur
  `OptickRadialTree.jsx` (frontend, déjà établi et présumé
  fonctionnel) -- même bibliothèque `d3.hierarchy`/`d3.tree`/
  `d3.linkRadial`.

**⚠️ Contrainte d'environnement énumérée et vérifiée, pas supposée** :
`d3` (le paquet lui-même, pas seulement `d3-sankey`) a été testé
directement (`npm install d3`) -- 403 Forbidden confirmé, aucun accès
au registre npm pour ce paquet précis depuis cet environnement de
développement. Conséquence assumée : la construction de données
(hiérarchie, échelles de largeur) EST testée en isolation (fonctions
pures, sans `d3`), mais l'appel `d3` lui-même dans les deux
composants de rendu n'a PAS pu être exécuté ici -- à vérifier en
priorité au premier rendu réel, particulièrement `WeightedRadialTree.jsx`
qui réutilise l'API `d3.hierarchy`/`d3.tree`/`d3.linkRadial` déjà
utilisée par `OptickRadialTree.jsx` (motif suivi fidèlement, jamais
deviné).

**Vérifié réellement** : `alluvialLayout.js` (13 scénarios --
répartition proportionnelle au volume, filtrage des liens à 0 octet,
repli sur `#id` si aucun libellé, positions X cohérentes) ;
`weightedRadialLayout.js` (15 scénarios -- hiérarchie construite
correctement par segment, priorité hostname > IP > MAC, échelle de
largeur linéaire correcte y compris aux bornes, liens à 0 octet
filtrés). Syntaxe JSX des deux composants de rendu vérifiée
(`tsc --jsx`). **Non vérifié** : rendu visuel réel (voir contrainte
`d3` ci-dessus).

## Données de démonstration + filtres profondeur/géographie/volume (livraison #392)

Demandé explicitement : "génère des données d'exemple en volume
suffisant et sur une période de plusieurs mois afin d'affiner la mise
au point de l'interface", avec des filtres "période temporelle /
profondeur de voisinage / volume de trafic / géographie".

### Générateur de données (`scripts/seed_demo_data.py`)

```bash
python3 network-agent/scripts/seed_demo_data.py [--db-path CHEMIN]
```

Écrit directement en SQL (PAS via les fonctions `upsert_*` de
`store.py`, qui codent toutes en dur `now_iso()` -- horodatage RÉEL,
jamais paramétrable) -- nécessaire pour contrôler précisément les
dates et simuler plusieurs mois d'historique réaliste. Génère : 1
site clairement étiqueté "Démo — généré automatiquement (#392)"
(jamais confondu avec un site réel), 4 segments représentant des
niveaux de profondeur ET des zones géographiques distincts, 165
appareils au total, 25 relevés hebdomadaires sur 6 mois, ~577 liens
avec volumes croissants réalistes (jamais une progression parfaitement
linéaire). **Reproductible** (graine aléatoire fixe) et **idempotent**
(une ré-exécution supprime d'abord toute donnée précédemment générée
par ce script, jamais une accumulation de doublons).

### Nouveaux attributs sur `na_devices` (migration `_ensure_topology_columns`)

`network_depth` (notation "pN.M" -- N = routeurs traversés depuis le
point d'observation, M = commutateurs à ce niveau -- ex. "p0" =
direct, "p0.1" = 1 commutateur, "p1" = 1 routeur), `building`/`room`/
`zone` (géographie déclarative), `latitude`/`longitude` (coordonnées,
pas systématiques). **Ce module ne DÉDUIT aucune de ces valeurs**
depuis le trafic réel -- toutes NULL par défaut, renseignées
manuellement ou par le générateur de démonstration ci-dessus.

### Filtres ajoutés (routes + interface)

`GET /devices` accepte désormais `depth` (répétable, OU logique),
`building`, `room`, `zone` (correspondance exacte), `min_bytes_total`
-- tous optionnels, `segment_id` reste inchangé. Nouvelle route
`GET /filter-options?segment_id=` -- valeurs DISTINCTES réellement
présentes, pour peupler les filtres avec ce qui existe vraiment
plutôt qu'une liste devinée.

Interface (`NetworkAgentView.jsx`) : cases à cocher pour la
profondeur (plusieurs sélectionnables), menus déroulants bâtiment/
zone, champ volume minimum (Ko), bouton de réinitialisation --
réinitialisés automatiquement à chaque changement de segment.

### ✅ Filtre "période temporelle" LIVRÉ (livraison #394)

Dernier des 4 filtres demandés. `store.list_devices_for_period` --
pour CHAQUE appareil du segment, calcule le volume ÉCHANGÉ PENDANT la
période choisie PAR DIFFÉRENCE entre le relevé le plus proche de la
fin de période et celui le plus proche du début (même principe que
`/traffic-rate` sur `snmp-api`, #384 -- un cumul brut ne répond pas à
"combien PENDANT cette période"). Un appareil apparu PENDANT la
période utilise 0 comme référence de départ ; un appareil SANS
relevé dans l'intervalle est omis (jamais une valeur inventée).

Nouvelle route `GET /devices/for-period?segment_id=&start=&end=`
(ISO 8601, tous requis). Interface : deux sélecteurs de date --
convertis en ISO 8601 complet côté client AVANT l'appel (minuit pour
le début, fin de journée pour la fin) -- une comparaison de CHAÎNES
brutes "YYYY-MM-DD" côté serveur aurait décalé la borne d'un jour
(une date sans heure est toujours "inférieure" à la même date avec
heure, en comparaison lexicographique). **Les 3 autres filtres
(profondeur/géographie/volume) s'appliquent alors CÔTÉ CLIENT** sur
le résultat de cette route (qui ne les connaît pas nativement -- nature
de requête différente) -- chaque appareil renvoyé porte déjà ses
attributs statiques en plus de `bytes_total_period`.

### Vérifié réellement

Générateur exécuté réellement (pas seulement en isolation) --
165 appareils, 4 segments, 25 relevés/segment confirmés, profondeurs
correctement variées (7 valeurs distinctes observées), géographie
peuplée, taux de résolution DNS conforme à la cible (~65%),
progression du volume confirmée MONOTONE et réaliste (pas linéaire)
sur l'appareil le plus actif. Idempotence confirmée (une seconde
exécution ne duplique ni le site ni les appareils).
`list_devices`/`list_filter_options` (store.py) testés en profondeur
contre cette vraie base générée (filtres simples et combinés, tous
corrects). Routes Flask testées de bout en bout (5 scénarios).
Client hub testé avec `fetch` simulé (rétrocompatibilité confirmée
pour les appels existants sans filtre). Syntaxe JSX de
`NetworkAgentView.jsx` vérifiée. **Non vérifié** : rendu visuel réel
de la nouvelle ligne de filtres (aucun navigateur ici).

**`list_devices_for_period` (livraison #394)** testée en profondeur
contre la vraie base générée : période complète cohérente, volume
d'une première moitié TOUJOURS inférieur ou égal au volume de la
période complète (propriété vérifiée pour chaque appareil commun),
période hors de toute donnée renvoie une liste vide, deuxième moitié
seule strictement inférieure au cumul total (confirme que ce n'est
PAS juste le cumul brut renvoyé). Route Flask testée (3 scénarios).
Client hub testé (paramètres correctement encodés).

## Historique du volume par paire + barres de delta (livraison #400)

Lève les deux points restés "reste à faire (rémanence)" depuis #251.

**Volume d'une paire dans le temps** -- chaque ligne du tableau
"Échanges (qui parle à qui)" du pied de page est désormais cliquable :
elle charge `/links/history` (route existante depuis #251, jamais
appelée côté hub jusqu'ici) et affiche l'évolution du volume entre ces
deux appareils sous le tableau. Un second clic sur la même ligne referme.
Sélectionner un autre appareil réinitialise la paire. Une réponse qui
arriverait après un autre clic entre-temps est ignorée (garde sur
l'identité de la paire courante).

**Barres de delta** (`HistoryBars`, `NetworkAgentView.jsx`) -- SVG maison
comme les visualisations de flux (#389), aucune bibliothèque. Utilisées
pour la présence d'un appareil (au-dessus du tableau existant, conservé)
ET pour le volume d'une paire. L'API stocke des relevés CUMULATIFS
("calculer un delta entre deux points est la responsabilité de la
lecture", `store.take_snapshot`) -- cette responsabilité est tenue dans
`hub/src/networkAgentHistory.js`, module PUR sans React, testé sous Node
(`hub/tests/networkAgentHistory.test.mjs`, 10 tests). Trois choix à
connaître :

1. **Le premier relevé n'a pas de barre** (delta `null`, jamais 0) -- un
   0 se lirait "rien n'a été échangé", ce qui est faux. Son créneau reste
   occupé pour garder l'axe du temps régulier.
2. **Un recul du compteur** (redémarrage de capture, purge) donnerait un
   delta négatif : le point est marqué `reset`, dessiné en couleur
   d'avertissement avec le nouveau cumul comme estimation, et compté dans
   la légende ("N remise(s) à zéro") -- jamais lissé silencieusement.
3. **`/links/history` renvoie une ligne par (relevé, protocole, port)** :
   agrégation par `snapshot_at` avant tout calcul (`aggregateBySnapshot`),
   inoffensive pour `/presence-history`.

Survol d'une barre : date du relevé, volume sur l'intervalle, cumul.
Légende sous le graphique : nombre de relevés, total échangé, pic par
intervalle.

**`network-explorer/Dockerfile`** : `networkAgentHistory.js` ajouté à la
liste des fichiers recopiés depuis `hub/src` -- sans quoi le build du
front autonome casse (piège "nouveau fichier oublié dans le COPY").

**Vérifié** : 10 tests Node de la logique pure (agrégation, deltas, reset,
disposition des barres, hauteur minimale visible, cadres vides), syntaxe
JSX, aucun setter orphelin, tous les imports relatifs de
`NetworkAgentView.jsx` présents dans le `COPY` de network-explorer.
**Non vérifié ici** : rendu visuel réel, et surtout le comportement sur un
VRAI historique (les seules données disponibles restent synthétiques ou
de démonstration, #392).

## Services de la paire (livraison #403)

« Services connectés par paire d'ip » faisait partie de la demande de
rémanence (#251) et la route `/links/services` existe depuis -- mais elle
n'avait **jamais de client côté hub**, donc jamais affichée. Ajouté au
panneau de la paire ouvert en #400 : sous les barres de volume, tableau
Protocole / Port / Paquets / Volume / Dernier, trié par volume décroissant
(ordre de l'API), les deux sens confondus (voulu : par PAIRE, pas par
direction, `store.list_device_link_services`). Historique et services sont
chargés en parallèle ; la garde contre une réponse tardive couvre les deux.

`hub/tests/networkAgentClient.test.mjs` (nouveau) : URLs construites par
`fetchLinkServices`/`fetchLinkHistory` et repli en tableau vide sur erreur
API, JSON invalide ou réseau coupé -- `fetch` simulé, aucun réseau.

## Identité de l'hôte de supervision dans `/capture/status` (livraison #412)

`GET /capture/status` renvoie en plus `interface`, `interface_mac` et
`interface_ip` (`capture.interface_identity`) : la MAC est lue dans
`/sys/class/net/<iface>/address`, l'IPv4 par l'ioctl `SIOCGIFADDR` (Linux).
Meilleur effort : chaque champ vaut `null` quand il n'est pas connu (conteneur
sans `network_mode: host`, interface absente), jamais une erreur. Le hub s'en
sert pour reconnaître l'hôte de supervision parmi les appareils découverts et
proposer de masquer ses échanges avec la passerelle dans les visualisations de
flux. Tests : `python3 -m unittest test_capture_identity.py` (5 tests, dont
la lecture réelle de l'IP de `lo` sous Linux).

## `/links` sur une période (livraison #414)

`GET /links?segment_id=<id>&start=<ISO>&end=<ISO>` : volumes échangés
PENDANT la période, par différence de relevés (`na_link_history`, relevé de
`na_device_link_services`) sommée par paire -- même principe que
`/devices/for-period` (#394). `start` et `end` vont ensemble et dans l'ordre
(400 sinon) ; sans eux, cumul actuel comme avant. Lignes de même forme que
le cumul (`device_a_id`, `device_b_id`, `bytes_total`, `packet_count`) avec
`period: true` et un `id` synthétique `period-<a>-<b>`. Tests :
`python3 -m unittest test_links_period.py` (base SQLite temporaire).

## Fiche récapitulative d'un sous-réseau, IP distantes derrière un relais (livraison #427)

Constat remonté : « dans sous-réseaux je vois autre chose que le LAN
immédiat, mais aucune IP de ce LAN dans les appareils découverts, pas plus
que ce sous-réseau dans la table des découvertes ». Cause dans `capture.py` :
un paquet **venant de l'extérieur** arrive avec la MAC de la passerelle et
l'IP distante comme source ; `upsert_device(src_mac, src_ip)` attribuait
donc l'IP distante (8.8.8.8, 10.20.0.5…) à la passerelle -- sa vraie IP
était écrasée à chaque paquet relayé, et les sous-réseaux « observés »
n'étaient que le reflet de ces IP baladeuses. Et un appareil qui ne fait
que **recevoir** (NAS, imprimante) n'avait jamais d'IP (seules les sources
en donnaient une).

Corrections :

- une IP source **hors du CIDR du segment** n'est plus l'adresse de la MAC
  qui la porte : elle est rangée dans la nouvelle table `na_remote_ips`
  (segment, relais `via_device_id`, IP, sens `in`/`out`, compteurs), et la
  MAC est comptée comme relais (`external_relay_count`) ; les destinations
  distantes y sont rangées aussi (sens `out`) ;
- une destination **dans** le CIDR est bien l'adresse de la MAC
  destinataire (livraison locale sur le L2) : les appareils passifs ont
  désormais une IP ; sans CIDR configuré rien n'est déduit ;
- sans CIDR, une IP **publique** est traitée comme distante (elle ne peut
  pas être celle d'un appareil du LAN capté) ; le privé reste attribué à
  la MAC (impossible de distinguer) -- configurer `NETWORK_AGENT_SEGMENT_CIDR`
  reste la vraie réponse.

`GET /observed-subnets` distingue maintenant les deux origines :
`device_count` (appareils du segment), `remote_ip_count` (IP distantes),
`origin` = `local` | `relais` | `mixte`, `via` (relais), `in_segment`
(dans le CIDR configuré ; `null` sans CIDR), `packet_count`. Nouvelle route
`GET /observed-subnet?segment_id=&subnet=<cidr>` : la **fiche** -- segment
et CIDR, dans/hors segment avec l'explication en clair, d'où viennent les
adresses (appareils / trafic relayé), relais (MAC, IP, nom, rôle, nombre
d'IP, volume), chaque IP (appareil ou distante, MAC ou relais, nom, sens,
paquets, volume, première/dernière vue), services des appareils du
sous-réseau, échanges concernés (200 max).

Hub, tuile Exploration réseau : colonnes Origine / IP distantes / Via dans
le tableau des sous-réseaux, flèche ⇢ pour un sous-réseau hors segment, et
**clic sur une ligne** → la fiche sous le tableau.

Migration : `CREATE TABLE IF NOT EXISTS` (schéma), aucune reprise des
données passées -- les IP déjà attribuées à tort à une passerelle sont
corrigées au prochain paquet local de celle-ci (COALESCE), les IP
distantes se reconstituent au fil de la capture.

Vérifié : 4 tests (`test_observed_subnets.py` : IP distante jamais
attribuée au relais, deux origines, fiche, sans CIDR), non-régression des
tests existants (14), rendu hub sur faux back-end. Non vérifié : capture
réelle (à confirmer au prochain déploiement : la passerelle doit garder
son IP et le LAN immédiat apparaître en `local`).
