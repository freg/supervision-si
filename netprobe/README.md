# netprobe — sondage réseau actif (livraison #295)

Demandé explicitement : "un service type smokeping permanent sur
potentiellement tous les IP relevés -> bdd, nmap à la demande -> bdd,
tcpdump sans stockage utilisable par d'autres modules, un collecteur
d'IP -> bdd, une analyse multi scripts (un ordonnanceur de scripts
d'analyse des données des services précédent), un système de
contrôle permettant d'activer, désactiver, temporiser (fréquence
d'échantillonnage), programmer".

## Décision d'architecture : module séparé de network-agent

Tranchée avec la personne ("à toi de décider en fonction de l'impact
de charge sur le reste") : `network-agent` fait de la capture
PASSIVE continue (`tcpdump`) dans son propre conteneur
(`network_mode: host`). Y ajouter du sondage ACTIF (smokeping en
continu, tcpdump partagé pour d'autres modules) créerait une
concurrence CPU/mémoire risquant de dégrader sa précision de capture
existante. `netprobe` reste donc un conteneur ISOLÉ, limitable ou
éteignable indépendamment sans affecter `network-agent`.

## Portée de CETTE livraison (#295) : la fondation

Seulement les deux briques dont tout le reste dépend :

**Collecteur d'IP** (point 4 de la demande) -- table `targets`,
ajout manuel ou import depuis `network-agent` (`GET /devices`,
best-effort -- son indisponibilité ne bloque jamais ce module).
Idempotent sur `ip_address` : un ajout répété de la même IP ne crée
jamais de doublon.

**Système de contrôle** (point 6) -- table `probe_config`, un
niveau GLOBAL par type de sonde (s'applique à toutes les cibles) et
un niveau PRÉCIS par cible en override (prioritaire sur le global).
Désactivé par défaut -- un nouveau type de sonde ne démarre jamais
tout seul sans configuration explicite. Fenêtre horaire optionnelle
(`schedule_start_hour`/`schedule_end_hour`), gère le passage minuit
(ex. 22h-6h).

**Bug réel trouvé et corrigé en testant** : SQLite ne considère
JAMAIS deux `NULL` comme égaux dans une contrainte `UNIQUE`
(comportement SQL standard, pas une particularité de ce moteur) --
`target_id NULL` pour représenter "configuration globale" aurait
laissé chaque reconfiguration globale créer une NOUVELLE ligne au
lieu de mettre à jour l'existante. Corrigé avec une sentinelle
interne (0, jamais une vraie clé de `targets` qui commence à 1) --
traduite en/depuis `None` à la frontière de l'API Python, jamais
exposée telle quelle à l'appelant.

## Ce qui N'EST PAS construit ici

Les volets ACTIFS eux-mêmes (points 1, 2, 3, 5 de la demande) --
chantier trop vaste pour une seule livraison, jamais bâclé :
- Smokeping permanent (latence continue vers les cibles)
- nmap à la demande
- tcpdump partagé sans stockage, utilisable par d'autres modules
- Analyseur multi-scripts (ordonnanceur)

## Évolution architecture -- backlog item 45

Réaction de la personne en cours de développement : prévoir une
VRAIE modularisation (chaque type de sonde comme brique
indépendante, probablement un service Docker distinct par type
plutôt qu'un unique `netprobe-api` monolithique) ET une répartition
sur PLUSIEURS HÔTES en mode agents répartis. Aucune des deux
questions tranchée en détail -- voir `BACKLOG.md` item 45 pour les
questions ouvertes (enregistrement d'un agent, récupération de
config, protocole de remontée, authentification agent-vers-central).
La fondation actuelle (collecteur + contrôle, un seul conteneur)
reste compatible avec cette évolution -- rien à défaire, seulement à
étendre le moment venu.

## Vérifié réellement

19 tests unitaires sur `store.py` (collecteur d'IP : idempotence,
filtre actif, import best-effort, suppression en cascade ; système
de contrôle : défaut désactivé, override précis vs global, fenêtre
horaire avec passage minuit, ET le bug NULL/UNIQUE spécifiquement
reproduit puis confirmé corrigé). 15 tests d'intégration sur les
routes `app.py` (CRUD cibles, import network-agent avec panne
simulée, configuration de sondes, validation des `probe_type`
invalides).

## Résilience du build (livraison #304)

Bug réel rencontré en déploiement réel : le build de `netprobe-api`
échouait systématiquement (`DeadlineExceeded`) au sein du stack
complet, confirmé reproductible même en isolation (réussi seulement
à la 3ème tentative). Cause : `nmap` tire des dépendances (scripts
NSE, libpcap) assez lourdes pour être exposées à une coupure réseau
transitoire lors de `apt-get`. Corrigé avec une boucle de reprise (3
essais, 5s de pause) autour de `apt-get`, et `--retries 5 --timeout
60` sur `pip install` -- jamais une boucle infinie qui masquerait un
vrai problème de configuration (dépôt injoignable, proxy mal réglé).

## Interface hub — correctifs réels (livraison #306)

Deux bugs réels signalés par la personne, corrigés :

**Débordement horizontal (onglets Cibles et Sondes)** -- colonnes
Source/Actif/poubelle poussées hors du cadre visible sur viewport
étroit. Aucune règle CSS existante ne gérait ce cas
(`.na-device-list-wrap` gère le défilement VERTICAL, jamais
l'horizontal) -- nouvelle classe réutilisable `.hub-table-scroll`
ajoutée à `hub.css`, appliquée aux 7 tableaux de `NetprobeView.jsx`.

**Cartes plafonnées à 420px et texte centré** -- piège DÉJÀ
DOCUMENTÉ dans `hub.css` (commentaire existant sur
`.hub-settings-section`, jamais lu avant d'écrire ce composant) :
`.hub-card` seule plafonne à 420px et centre le texte (pensée à
l'origine pour un contexte type écran de connexion) -- le correctif
établi est de TOUJOURS combiner `.hub-card` avec
`.hub-settings-section` (`className="hub-card hub-settings-section"`)
qui redéclare `max-width: none` et `text-align: left`. Les 7 cartes
de `NetprobeView.jsx` utilisaient `.hub-card` SEULE -- corrigées
pour combiner les deux classes, comme partout ailleurs dans le hub.

**Suppression et bascule rapide d'une configuration de sonde** --
manque réel signalé ("supprimer une sonde ou la suspendre") :
confirmé qu'aucune route de suppression n'existait, même côté
backend. Ajouté : `DELETE /probe-config/<id>` et
`PUT /probe-config/<id>` (bascule activé/désactivé sans resoumettre
tout le formulaire) -- jamais de suppression en cascade des
échantillons déjà enregistrés par cette config (historique préservé).
Colonne Actions ajoutée au tableau (⏸/▶ et 🗑 par ligne).

**Vérifié réellement** : 9 tests sur le stockage (bascule,
suppression, confirmation explicite de l'absence de cascade sur les
échantillons), 7 tests d'intégration sur les nouvelles routes.
Structure JSX revérifiée après les 7 modifications de classe CSS.
Non-régression complète reconfirmée.

## Reste à faire

- Purge automatique périodique des échantillons smokeping (fonction
  déjà écrite dans `store.py`, jamais appelée depuis le scheduler).
- ~~Modularisation multi-services et agents répartis -- backlog item 45.~~
  **Agents répartis LIVRÉS en #405-#408** (voir section dédiée) ; la
  modularisation multi-conteneurs du central reste non faite, sans besoin
  constaté.
- Volet WiFi (Campus Alpha) -- backlog items 47-51, matériel RF en
  cours d'acquisition. **Débit réel (iperf3) LIVRÉ en #385** sans
  attendre ce matériel (voir section dédiée plus bas) -- reste HORS
  de portée : suivi de BSSID/itinérance (nécessite une visibilité sur
  l'état WiFi de l'hôte, impossible depuis ce conteneur sans
  `network_mode: host`, voir la section dédiée), lecture RSSI/bruit
  et capture passive (nécessitent le matériel RF).
- Analyseurs supplémentaires -- seuls 2 existent (`latency_degradation`,
  `new_open_ports`), aucun n'a été VÉRIFIÉ en conditions réelles
  (seuils choisis raisonnablement mais jamais confrontés à de vraies
  données de production).

## Volet "expérience client" WiFi, débit réel sans RF (livraison #385)

Backlog item 47 reformulé le 2026-09-05 -- demandé explicitement :
"voyons ce qu'on peut déjà faire sans RF simplement avec un client
wifi et la couche IP et le snmp". Nouveau `iperf3_probe.py` (même
motif que `ping_probe.py`/`nmap_probe.py` -- appelle le VRAI binaire
`iperf3` via sous-processus, format JSON `-J` pour un parsing fiable,
schéma confirmé par recherche avant d'écrire le code). Nouvelle table
`iperf3_tests` (même motif que `nmap_scans` -- un test = un passage,
PERMANENT, À LA DEMANDE jamais programmé automatiquement : un test
iperf3 consomme de la vraie bande passante pendant plusieurs
secondes, contrairement à un ping unique, jamais mis sur le même tick
périodique que smokeping).

Routes : `POST /iperf3/test` (`target_id`, `port`? défaut 5201,
`duration_seconds`? 1-30, défaut 5), `GET /iperf3/tests?target_id=`.
La CIBLE doit être un serveur iperf3 déjà en écoute (`iperf3 -s`),
enregistré comme n'importe quelle autre cible de ce module --
réutilise le système de cibles existant plutôt que d'en inventer un
second.

**⚠️ Limite architecturale IMPORTANTE, découverte en construisant ce
module -- PAS résolue ici** : ce conteneur n'a PAS
`network_mode: host` -- le débit mesuré reflète le chemin réseau
RÉEL (traverse la vraie interface de l'hôte), MAIS ce module ne peut
PAS voir le BSSID/l'itinérance WiFi de l'hôte (propriété du pilote
WiFi, invisible depuis un namespace réseau Docker isolé). Cette
partie du volet "expérience client" (suivi de roaming) reste HORS de
portée tant que l'architecture d'agents multi-hôtes (items 45/48,
volontairement non tranchée) n'est pas décidée avec la personne --
nécessiterait probablement un agent natif tournant DIRECTEMENT sur
l'hôte (pas dans ce conteneur), reportant vers ce module.

**Vérifié réellement** : syntaxe Python, `iperf3_throughput()` testée
avec `subprocess.run` simulé (6 scénarios -- succès, erreur de
connexion serveur, binaire introuvable, délai dépassé, JSON invalide,
réponse JSON incomplète), routes Flask testées de bout en bout
(création de cible, test normal, `target_id` manquant/inconnu,
bornes de `duration_seconds`). **Un vrai bug trouvé et corrigé en
testant** : `duration_seconds=0` était interprété comme "non fourni"
à cause de l'évaluation Python `0 or 5` (0 est faux) -- même piège
déjà rencontré et corrigé sur `snmp-api`/`sample_interval` (#384) --
corrigé en distinguant explicitement l'absence de la valeur (`None`)
de zéro. **PAS vérifié** : l'appel réseau réel (`iperf3` non
installable dans cet environnement de développement, même limitation
que `ping`).

## Volet 4 : analyseur multi-scripts (livraison #307) -- DERNIER VOLET ACTIF, les 6 points de la demande initiale sont désormais tous construits

Quatrième et dernier volet ACTIF -- ordonnanceur de scripts d'analyse
des données des volets précédents (point 5 de la demande initiale).

**`analyzers/`** -- un module par analyseur, chacun exposant
`analyze(db_path) -> list de {target_id, severity, message}`, PUR
(aucun effet de bord, jamais d'écriture directe en base) -- testable
en isolation, séparé du moteur d'orchestration qui décide COMMENT
enregistrer les constats. `analyzers/__init__.py` tient le registre
explicite (`ANALYZERS = {...}`) -- jamais de découverte automatique
par scan de fichiers, plus explicite, jamais un module oublié qui
tourne sans qu'on le sache.

**Deux analyseurs livrés** :
- `latency_degradation.py` -- compare une fenêtre récente
  d'échantillons smokeping à une fenêtre de référence plus ancienne
  pour la MÊME cible -- signale une hausse RELATIVE (jamais un seuil
  absolu, une cible normalement à 80ms n'est pas anormale en soi).
  Minimum d'échantillons requis dans les deux fenêtres -- jamais de
  constat sur une donnée trop clairsemée.
- `new_open_ports.py` -- compare les deux DERNIERS scans nmap d'une
  cible -- signale tout port apparu ouvert qui ne l'était pas avant
  (pertinence sécurité directe). Jamais de comparaison si le dernier
  scan est en échec (port manquant y signifierait "scan raté", pas
  "port fermé").

**`analyzer_engine.py`** -- sépare calcul (analyseurs purs) et
enregistrement (seul point qui écrit en base). Un analyseur en panne
n'empêche JAMAIS les autres de tourner.

**Intégré au système de contrôle existant** -- `analyzer` était déjà
présent dans `PROBE_TYPES` depuis la fondation (#295), jamais
branché avant cette livraison. Configuration GLOBALE uniquement
(jamais par cible : un analyseur regarde l'ensemble des cibles
lui-même) -- réutilise `get_effective_config`/`is_within_schedule`
déjà écrits pour smokeping, aucun nouveau mécanisme de contrôle.

**Interface hub** -- nouvel onglet "Analyse" : liste des constats
(sévérité, analyseur, cible, message, horodatage) + bouton "Lancer
maintenant" pour une analyse à la demande sans attendre le prochain
tick programmé.

**Vérifié réellement** : 7 tests sur le stockage, 7 tests sur
`latency_degradation`, 7 tests sur `new_open_ports`, 6 tests sur le
moteur d'orchestration (dont la résilience -- un analyseur en panne
n'empêche pas les autres), 8 tests sur le tick de l'ordonnanceur
(activation, fréquence, fenêtre horaire), 8 tests d'intégration sur
les routes. Structure JSX revérifiée. Non-régression complète
reconfirmée.

## Volet 3 : tcpdump partagé, sans stockage (livraison #305)

Troisième volet ACTIF -- capture partagée à la demande, utilisable
par d'autres modules (point 3 de la demande initiale).

**`tcpdump_probe.py`** -- appelle le vrai binaire `tcpdump` système
via sous-processus, même motif que `ping_probe.py`/`nmap_probe.py`.
Le format texte par ligne de tcpdump VARIE selon le protocole
(TCP/UDP/ICMP/ARP) -- plutôt que de parser chaque format précisément
(fragile), extraction par MOTIFS robustes aux variations : adresses
IP par expression régulière, mots-clés de protocole recherchés comme
mots entiers. ⚠️ **NON VÉRIFIÉ contre un vrai `tcpdump`** -- binaire
absent de cet environnement de développement.

**Piège réel trouvé et corrigé en testant** : `TimeoutExpired.stdout`
reste en BYTES même avec `text=True` sur le `subprocess.run()` qui a
levé l'exception -- `text=True` ne s'applique qu'au retour NORMAL,
jamais à la capture partielle d'un timeout. Décodage explicite
ajouté, sinon échec silencieux sur le parsing (qui attend du `str`).
Un timeout sur une interface calme est traité comme un résultat
PARTIEL valide (`success: true` avec un message informatif), jamais
une erreur -- normal qu'une interface peu chargée n'atteigne pas le
nombre de paquets demandé.

**SANS STOCKAGE, VOLONTAIREMENT** -- aucune table en base pour ce
volet (contrairement à smokeping/nmap) : le résultat est renvoyé à
l'appelant, jamais persisté. Raison double : demandé explicitement,
et une capture réseau élargirait sans raison la surface de ce qui
doit être protégé si elle était conservée.

**`cap_add: NET_ADMIN`** ajouté en plus de `NET_RAW` (déjà présent
depuis #297) -- même motif déjà établi pour `network-agent-api`
en #238. Sans lui, `tcpdump` échoue proprement ("permission denied"),
géré par `tcpdump_probe.py`.

**Interface hub** -- nouvel onglet "Capture" dans `NetprobeView.jsx` :
interface et nombre de paquets optionnels, résultat affiché
immédiatement (répartition par protocole, IP les plus actives),
jamais d'historique puisque rien n'est stocké.

**Vérifié réellement** : 13 tests sur le parsing (`tcpdump_probe.py`,
dont le piège bytes/timeout spécifiquement reproduit puis confirmé
corrigé), 6 tests d'intégration sur les routes (dont la confirmation
explicite qu'aucune table tcpdump n'existe en base). Structure JSX
revérifiée après l'ajout de l'onglet. Non-régression complète
reconfirmée.

## Volet 2 : nmap à la demande (livraison #302)

Deuxième volet ACTIF -- scan de ports à la demande (point 2 de la
demande initiale).

**`nmap_probe.py`** -- appelle le VRAI binaire `nmap` système via
sous-processus, même motif que `ping_probe.py`. Sortie **XML**
(`-oX -`) plutôt que texte -- structure documentée et stable,
parsée avec `xml.etree.ElementTree` (bibliothèque standard, aucune
dépendance ajoutée). ⚠️ **NON VÉRIFIÉ contre un vrai `nmap`** --
binaire absent de cet environnement de développement -- logique de
parsing testée contre de vraies structures XML nmap (multi-ports,
host down, XML malformé).

**VOLONTAIREMENT à la demande** -- jamais programmé
automatiquement (contrairement à smokeping) : un scan de ports est
BEAUCOUP plus intrusif qu'un ping (peut déclencher des alertes IDS/
IPS côté cible) -- reste un geste explicite, jamais une action de
fond silencieuse.

**Table `nmap_scans`** -- `open_ports` stocké en JSON (TEXT), jamais
une table normalisée séparée (nombre de ports variable et petit par
scan, une jointure n'apporterait rien ici contrairement à
smokeping_samples).

**Interface hub** -- nouvel onglet "Scans" dans `NetprobeView.jsx`
(#301) : lancement d'un scan (cible + ports optionnels), résultat
immédiat, historique par cible.

**Vérifié réellement** : 10 tests sur le parsing (`nmap_probe.py`,
multi-ports/host down/binaire absent/timeout/XML malformé/paramètre
-p), 4 tests sur le stockage, 8 tests d'intégration sur les routes.
Structure JSX de `NetprobeView.jsx` revérifiée après l'ajout de
l'onglet Scans. Non-régression complète du reste du module
reconfirmée.

## Interface hub (livraison #301)

`NetprobeView.jsx` (quatre onglets : Cibles/Sondes/Suivi/Scans) +
`netprobeClient.js`, câblés dans `App.jsx` (tuile "Sondes réseau",
visible dès que `VITE_NETPROBE_API_BASE_URL` est configurée).

**Manque critique trouvé et corrigé en finalisant cette livraison** :
la route passerelle `/api/netprobe/` -> `netprobe-api` n'existait
PAS dans `tls-proxy/render_nginx_conf.py` -- le hub aurait appelé
dans le vide, 404 systématique sur toute action. Ce genre de manque
avait déjà été rencontré pour schema-analyzer (#151) et ged (#157/
#160), documenté dans `scripts/chantier.sh` -- reconfirme l'utilité
de toujours vérifier la table de routage en dernière étape d'une
livraison qui ajoute un nouveau service, jamais présumé fait sous
prétexte que le service backend existe déjà.

**Vérifié réellement** : structure JSX de `NetprobeView.jsx`
revérifiée (accolades/parenthèses équilibrées, aucune balise non
refermée), `netprobeClient.js` vérifié en syntaxe, câblage complet
de la chaîne (constante `NETPROBE_API_BASE_URL` définie, tuile
conditionnelle, route passerelle désormais présente et confirmée
par `render_nginx_conf.py --check`).

## Volet 1 : smokeping (livraison #297)

Premier volet ACTIF construit -- sondage de latence permanent
(point 1 de la demande initiale).

**`ping_probe.py`** -- appelle le VRAI binaire `ping` système via
sous-processus, même motif déjà établi ailleurs dans ce projet
(`ssh-keygen`, `ldapsearch`, `mysqldump`) plutôt que de réimplémenter
ICMP soi-même. ⚠️ **NON VÉRIFIÉ contre un vrai `ping`** -- binaire
absent de cet environnement de développement -- logique de PARSING
testée contre de vraies sorties `ping` (format Linux `iputils-ping`,
avec repli si la section `rtt` est absente).

**UN SEUL ping par échantillon par défaut** (pas les 20 envois
traditionnels de smokeping) -- décision de charge, cohérente avec la
préoccupation qui a motivé le choix "module séparé" en #295 :
"potentiellement tous les IP relevés" peut représenter beaucoup de
cibles.

**`scheduler.py`** -- une passe testable en isolation
(`run_smokeping_tick`), enveloppée dans une boucle de fond (thread
daemon, jamais bloquant au démarrage). Respecte le système de
contrôle (#295) à CHAQUE cible : désactivée → jamais sondée ; hors
fenêtre horaire → jamais sondée CETTE fois (revérifié au tick
suivant) ; fréquence → une cible n'est sondée que si
`frequency_seconds` s'est bien écoulé depuis son dernier échantillon.

**Table `smokeping_samples`** -- un échantillon = un passage, jamais
recalculé à la volée (même raisonnement que le journal de signaux de
`vigilance`). `latest_sample_per_target` pour une vue d'ensemble sans
charger tout l'historique ; `prune_old_samples` pour la purge
(jamais appelée automatiquement, prévue pour un appel périodique
séparé -- pas encore câblée).

**`cap_add: NET_RAW`** ajouté à `docker-compose.yml` -- requis par
`ping` en conteneur non privilégié (limitation Docker standard).

**Vérifié réellement** : 8 tests sur le parsing (`ping_probe.py`,
succès/échec/binaire absent/timeout/repli de format), 9 tests sur le
stockage (dont la purge -- conserve bien les plus récents), 12 tests
sur l'ordonnanceur (désactivé par défaut, activation globale,
respect de la fréquence, override précis par cible, fenêtre
horaire). 4 tests d'intégration sur les nouvelles routes.
Non-régression complète du reste du module reconfirmée.

(Purge automatique périodique -- fonction déjà écrite dans
`store.py`, jamais appelée depuis le scheduler -- voir "Reste à
faire" en tête de ce fichier pour l'état à jour.)

## Sondes distribuées Raspberry Pi -- agent, collecteur, central, images (livraisons #405-#408)

Items 45/47/48 du backlog, demandés explicitement le 2026-09-06. Tout le
détail vit dans `netprobe/agent/README.md` (logiciel), `netprobe/agent/image/README.md`
(images) et `docs/supervision-wifi.md` (vérification de la proposition
WiFi Alpha et état couche par couche). Résumé côté netprobe-api :

- `agents_store.py` : tables `probe_agents` (flotte, secrets, tâches) et
  `agent_measurements` (déduplication sur sonde/tâche/instant).
- Routes : `GET/POST /agents`, `GET/PUT/DELETE /agents/<id>`,
  `POST /agents/<id>/rotate-secret`, `GET /agents/<id>/provision`,
  `GET /fleet?site=` (signé collecteur), `POST /agents/measurements/bulk`
  (signé collecteur ou sonde), `GET /agents/latest?site=`,
  `GET /agents/<id>/measurements`.
- Le protocole de signature est **copié** de `netprobe/agent/netprobe_agent/protocol.py`
  par le Dockerfile (`netprobe_protocol.py`) -- source canonique unique.
- Hub : onglet « 📶 Sondes WiFi » de la tuile Sondes réseau.
- Tests : `test_agents_routes.py` (8, `app.test_client()`), à lancer depuis
  `netprobe/api` avec `NETPROBE_DB_PATH=/tmp/x.db PYTHONPATH=../../shared python3 -m unittest test_agents_routes`.

**Lève la limite de #385** : le suivi de BSSID/itinérance est désormais
une tâche `wifi_link` native sur la sonde, affichée dans le hub.

