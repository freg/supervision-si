## 2026-09-06 — Images Raspberry Pi : sonde Zero W et collecteur 3B, premier démarrage automatique (livraison #408)

`netprobe/agent/image/build-image.sh` : à partir de l'image OFFICIELLE
Raspberry Pi OS Lite 32 bits (téléchargée en cache, ou fournie), injecte
sur la partition de boot -- avec mtools, sans montage ni root -- le paquet
`netprobe_agent`, la configuration de l'appareil (récupérée du central par
`/agents/<id>/provision`, ou d'un fichier), `userconf.txt` (utilisateur +
hash SHA-512), le fichier `ssh`, une clé SSH optionnelle, et
`firstrun.sh` lancé une fois par `systemd.run=` (mécanisme de Raspberry Pi
Imager). Au premier boot : hostname, fuseau, WiFi (`raspi-config nonint`),
adresse fixe (NetworkManager sur Bookworm, dhcpcd sur Bullseye),
installation dans `/opt/netprobe-agent`, services systemd (sonde :
`netprobe-agent` + désactivation de l'économie d'énergie WiFi ;
collecteur : `netprobe-collector` sous un utilisateur système), iperf3
optionnel, nettoyage (directive retirée de `cmdline.txt`, clé WiFi effacée
de la FAT), redémarrage. Point de montage `/boot/firmware` (Bookworm) ou
`/boot` (Bullseye) détecté d'après `issue.txt`, forçable.

`docs/supervision-wifi.md` : **vérification de la proposition de #303**
(architecture 4 couches confirmée ; Pi Zero W sous-estimé -- `iw` suffit
pour l'itinérance et l'occupation des canaux sans mode moniteur ; limite
BSSID de #385 levée ; Pi 3B collecteur justifié par le VPN ; sparrow-wifi
écarté sur les Pi), état couche par couche, ordre de mise en route.

**Vérifié** : construction des deux rôles sur une image SYNTHÉTIQUE au
format Raspberry Pi OS (MBR + FAT32 + cmdline/issue), inspection mtools de
tout ce qui est injecté (dont une clé WiFi avec apostrophes relue intacte
par bash), image de base intacte, provisionnement de bout en bout contre un
`netprobe-api` réel lancé localement, syntaxe bash. **Non vérifié :
aucun Raspberry Pi n'a démarré** -- le téléchargement de l'image
officielle est bloqué depuis l'environnement de développement (proxy,
non contourné). Points à regarder au premier essai : `image/README.md`.

Fichiers : `netprobe/agent/image/{build-image.sh,firstrun.sh,README.md}`,
`netprobe/agent/systemd/netprobe-wifi-powersave.service`,
`docs/supervision-wifi.md`, `netprobe/README.md`, `BACKLOG.md` (47, 51),
`.gitignore` (cache et images).

## 2026-09-06 — Hub : onglet « 📶 Sondes WiFi » dans la tuile Sondes réseau (livraison #407)

Interface de #405/#406 (`hub/src/NetprobeAgentsTab.jsx`, composant séparé
— `NetprobeView.jsx` était déjà long) :
- **Flotte** : une ligne par appareil (rôle, site, libellé, vivacité —
  vue il y a N via collecteur/direct), lecture compacte de la dernière
  mesure : WiFi (SSID, bande/canal, dBm avec tonalité > -67 / -75, débit),
  ping, voisinage (bornes visibles, co-canal), Pi (température, charge,
  sous-tension). Filtre par site. Actions : désactiver, régénérer le
  secret, supprimer (douce).
- **Création** derrière « + » ; le secret est affiché UNE fois avec la
  commande `build-image.sh` correspondante.
- **Détail d'une sonde** : courbe du signal reçu (300 derniers
  `wifi_link`, SVG maison), **changements de borne** — le suivi
  d'itinérance demandé en #303 et laissé hors de portée en #385 :
  itinérance sans coupure / après coupure / reconnexion sur la même
  borne (listée à part, ce n'est pas une itinérance) — édition des
  tâches en JSON (reprise par le collecteur puis la sonde, jamais de
  reflash), dernière mesure par tâche en brut.
- Rafraîchissement toutes les 60 s, nettoyé au démontage.

Logique pure dans `hub/src/netprobeAgents.js` (7 tests Node :
vivacité, regroupement, lectures compactes, `detectBssidChanges` sur un
historique en désordre avec erreurs et coupures, ligne de signal sans
division par zéro). Client : 7 fonctions ajoutées à `netprobeClient.js`.

**Vérifié** : build Vite réel du hub (679 modules), 37 tests hub, aucune
couleur en dur (tonalités via `--ok`/`--warning`/`--danger`), aucun
setter orphelin. **Non vérifié** : rendu dans un navigateur.

## 2026-09-06 — netprobe-api : flotte des sondes distribuées et mesures remontées (livraison #406)

Côté CENTRAL de #405. Nouveau module `netprobe/api/agents_store.py` (même
base SQLite, tables `probe_agents` et `agent_measurements`, déduplication
sur (sonde, tâche, instant)) et routes sur `netprobe-api` :
- flotte : `GET/POST /agents`, `GET/PUT/DELETE /agents/<id>`,
  `POST /agents/<id>/rotate-secret`, `GET /agents/<id>/provision`
  (configuration prête pour l'image, secret compris — consommée par
  `build-image.sh`). Le secret n'est renvoyé qu'à la création, à la
  rotation et au provisionnement, jamais en liste.
- `GET /fleet?site=` **signé par un collecteur** : sondes actives de SON
  site avec secrets et tâches (401 sinon, 403 pour un autre site).
- `POST /agents/measurements/bulk` **signé** par un collecteur (mesures de
  ses sondes, périmètre = son site) ou par une sonde en direct (ses
  mesures seulement — l'identité vient de la signature, jamais du corps).
- lectures pour le hub : `GET /agents/latest?site=` (dernière mesure par
  sonde × tâche, une seule requête), `GET /agents/<id>/measurements?task=&since=&limit=`.

Le protocole (`protocol.py`) reste dans `netprobe/agent/` : le Dockerfile
en COPIE une instance (`netprobe_protocol.py`), l'import retombe sur le
dépôt en développement — jamais deux implémentations. Le chemin signé est
celui APRÈS retrait du préfixe `/api/netprobe` par tls-proxy (rewrite
explicite déjà en place), query string comprise.

**Vérifié** : 8 tests `app.test_client()` — création/validation/liste sans
secret, provisionnement et rotation, flotte signée (rôle, site, secret
faux, sans en-têtes), ingestion par collecteur (doublon, hors site,
inconnue, invalide ; dernier contact « via »), ingestion directe par une
sonde limitée à elle-même, sonde désactivée refusée, corps altéré refusé,
suppression avec purge. **Non vérifié** : build Docker de netprobe-api
(deux COPY ajoutés, vérifiés à la lecture), collecteur réel vers le central.

## 2026-09-06 — Sondes distribuées : agent Pi Zero W + collecteur Pi 3B (items 45/47/48, livraison #405)

Demandé explicitement : « dans le backlog il y a un agent à déployer,
reprend cette partie ; prépare une image raspi0W comme sonde wifi ; idem
pour un agent sur raspi3b pour collecter ». Première tranche : le LOGICIEL
des deux rôles, testé ; les images et le central suivent (#406-#408).

`netprobe/agent/` — un seul paquet Python **bibliothèque standard
uniquement** (cible Pi Zero W, ARMv6, 512 Mo), deux rôles :
- **sonde** (`agent.py`) : tâches `wifi_link` (BSSID/SSID/canal/signal/
  débits + compteurs d'erreurs du pilote), `wifi_scan` (bornes visibles,
  occupation par canal, plus fort voisin co-canal), `ping`, `dns`, `http`,
  `iperf3` si présent, `sys` (charge, température, sous-tension du Pi) ;
  liste de tâches TIRÉE du collecteur (jamais reflashée), file locale
  SQLite store-and-forward, envoi par lots signés.
- **collecteur** (`collector.py`, http.server) : réception authentifiée
  et dédupliquée, statut/dernières mesures consultables SUR PLACE même VPN
  coupé, flotte du site en cache local, relais par lots vers le central.

**Questions ouvertes des items 45/48 tranchées** (défauts annoncés, voir
`netprobe/agent/README.md`) : agent propre plutôt que sparrow-wifi (Pi Zero
W sans mode moniteur, couche « expérience client » = client ordinaire),
provisionnement à la construction de l'image, configuration tirée, push
par lots, HMAC-SHA256 par appareil (identité prise de la signature, jamais
du corps), pas de fenêtre temporelle stricte (Pi sans horloge) mais
déduplication (agent, tâche, instant).

**Lève la limite notée en #385** : le suivi de BSSID/itinérance « hors de
portée » depuis un conteneur devient une simple tâche `wifi_link` native.

**Vérifié** : 58 tests (Python 3.11 cloud ET 3.10 sur le Mac) — analyseurs
sur sorties réelles d'iw/ping, signature et toutes ses altérations, file
locale (purge, corruption), tâches simulées, boucle de la sonde,
collecteur, et **chaîne HTTP réelle sonde → collecteur** sur 127.0.0.1.
Deux vrais défauts attrapés par les tests : SSID vide (borne masquée)
capturant la ligne suivante comme nom de réseau ; instant `at` pris de
l'horloge murale au lieu de celle de l'agent (clé de déduplication).
**Non vérifié** : aucun Raspberry Pi ni carte WiFi ici.

**Fichiers** : `netprobe/agent/netprobe_agent/{protocol,parsers,localqueue,
tasks,agent,collector}.py`, `tests/` (4 fichiers), `systemd/` (2 unités),
`examples/` (3 configurations), `README.md`.

## 2026-09-06 — Cycle agile réseau : tendances entre deux rafraîchissements (livraison #404)

Les métriques de chaque étape sont comparées au rafraîchissement précédent :
marqueur `▲`/`▼`/`±` sur le nœud, détail `avant → après` dans l'infobulle,
polarité explicite par métrique (`METRIC_POLARITY`). Aucun stockage ni API.
Logique pure dans `networkCycleGraph.js` (+5 tests, 30 tests hub au vert).
Détail et piège (référence qui glisserait à chaque réponse d'API) dans
`docs/cycle-agile-reseau.md`. Fichiers : `NetworkCycleView.jsx`,
`networkCycleGraph.js`, `hub.css`, tests, docs.

**Build Vite VÉRIFIÉ pour l'ensemble #399-#404** (ce qui n'avait pas pu
l'être jusqu'ici) : les `node_modules` du Mac étant inexécutables dans le
shell de la session, `hub/` et `network-explorer/` ont été transférés
(sans `node_modules`) dans un environnement Linux avec accès npm, puis
construits pour de vrai — `npm ci` + `vite build` pour le hub (677 modules,
617 Ko, avertissement de taille de chunk préexistant), `npm install` +
`vite build` pour network-explorer en reproduisant les `COPY` de son
Dockerfile (608 modules). Aucune erreur. Reste non vérifié : le rendu et
les gestes dans un navigateur réel.

## 2026-09-06 — Exploration réseau : services de la paire (livraison #403)

`/links/services` (« services connectés par paire d'ip », demandé en #251,
servi par l'API depuis) n'avait jamais de client côté hub. Affiché dans le
panneau de la paire (#400), sous les barres de volume : protocole, port,
paquets, volume, dernier contact. Chargé en parallèle de l'historique, même
garde contre les réponses tardives. Client testé (`fetch` simulé, 3 tests) ;
25 tests hub au vert. Fichiers : `networkAgentClient.js`,
`NetworkAgentView.jsx`, `hub/tests/networkAgentClient.test.mjs` (nouveau),
`network-agent/README.md`.

## 2026-09-06 — Fin des variables de thème `--hub-*` inexistantes (item 60, livraison #402)

Suite de #399 : les 11 usages restants de variables jamais définies dans
`shared/theme.css` (donc toujours sur leur repli en dur, identique en thème
sombre) remplacés par les variables réelles — `--hub-ok`/`--hub-ok-bg` →
`--ok`/`--ok-bg`, `--hub-border` → `--border`, `--hub-bg` → `--panel`
(fond de boîte de dialogue), `--hub-selected` → `--bg` (convention existante
des lignes sélectionnées). Thème clair inchangé ou imperceptiblement
(#ddd → #d8dee4), thème sombre corrigé. Plus aucun `var(--hub-` dans
`hub/src`. Fichiers : `SchemaAnalyzerView`, `ImapView`, `NetworkAgentView`,
`NebulaView`, `CalendarView`, `BACKLOG.md`.

## 2026-09-06 — Rattrapage du journal (#395, #398) et hygiène du dépôt (livraison #401)

- Deux entrées **reconstruites a posteriori** pour les livraisons de la tuile
  Cycle agile réseau qui n'en avaient jamais eu (commits `17ab5ce` et
  `cc69fd3`) — insérées à leur place chronologique, marquées comme telles,
  avec l'explication de l'écart entre les numéros des messages de commit
  (#396, #401) et ceux du journal/badge (#395, #398).
- `hub/dist/` et `hub/src/{theme.css,preferences.js,VERSION.json}` retirés de
  l'index git (`git rm --cached`, fichiers conservés sur disque) : artefacts
  de build et copies que `run.sh` régénère depuis `shared/` — le hub était le
  seul front à les versionner. `.gitignore` complété pour tous les fronts.
- Aucun changement de code.

## 2026-09-06 — Exploration réseau : historique du volume par paire + barres de delta (livraison #400)

Suite de l'interface « Exploration réseau » : les deux points restés
"reste à faire (rémanence)" dans `network-agent/README.md` depuis #251.

- **Volume d'une paire dans le temps** — clic sur une ligne « Échanges »
  du pied de page → `/links/history` (route existante, jamais affichée
  côté hub) → barres de delta sous le tableau.
- **Barres de delta SVG maison** (`HistoryBars`) pour la présence d'un
  appareil ET le volume d'une paire — remplace « tableau simple faute de
  bibliothèque » (le tableau est conservé en dessous). Premier relevé sans
  barre (pas de base), recul du compteur signalé en avertissement et
  jamais lissé, agrégation par relevé pour les lignes par protocole/port.
- `hub/src/networkAgentHistory.js` — logique pure (agrégation, deltas,
  disposition), `formatBytes` y déménage ; 10 tests Node.
- `network-explorer/Dockerfile` — nouveau module ajouté au `COPY`.

**Vérifié** : 10/10 tests, syntaxe, setters, imports copiés par
network-explorer. **Non vérifié** : rendu visuel, données réelles.

**Fichiers** : `hub/src/NetworkAgentView.jsx`, `hub/src/networkAgentHistory.js`
(nouveau), `hub/tests/networkAgentHistory.test.mjs` (nouveau),
`hub/src/hub.css`, `network-explorer/Dockerfile`, `network-agent/README.md`.

## 2026-09-06 — Graphique du cycle réseau interactif + menu Réseau complété (livraison #399)

Deux volets, sur la tuile et le menu réseau.

**1. Graphique du cycle agile réseau** (suite de l'onglet livré précédemment) :
- **Zoom et déplacement** — molette (ancrée sous le curseur), glisser à la
  souris, boutons `+` / `−` / `⟲` et niveau de zoom affiché. Le dessin vit
  désormais dans un `<g>` transformé : le viewBox ne bouge pas, donc les
  marqueurs de flèche déclarés dans `<defs>` restent valables.
- **Infobulles au survol** des nœuds — détail par étape (suggestions,
  capture, tunnels/SNMP, sondes, signaux/sauvegardes), en complément du
  texte compact déjà affiché sous chaque nœud.
- **Rafraîchissement** — bouton manuel `⟳`, bascule automatique (30 s) et
  horodatage de la dernière mise à jour. La minuterie ne tourne QUE sur
  l'onglet graphique et est nettoyée au démontage.
- `hub/src/networkCycleGraph.js` — logique pure extraite dans son propre
  module (même motif que `ldapTree.js`), 12 tests Node dans
  `hub/tests/networkCycleGraph.test.mjs`.

**2. Menu Réseau ▾ complété** — « Exploration réseau » et « Sondes réseau »
n'existaient QUE comme tuiles d'accueil alors que tout le reste de
l'écosystème réseau vit dans ce menu. Ajoutées (mêmes `viewMode`, jamais de
vue dupliquée) et conditionnées à leur variable d'API, contrairement aux sept
autres entrées : `NetworkAgentView`/`NetprobeView` appellent leur API dès le
montage sans garde-fou sur une base absente. La liste des `viewMode` qui
allument le menu a été complétée en conséquence.

**3. Correction de thème `--hub-danger`** — cette variable n'était **définie
nulle part** : les 32 usages du hub retombaient tous sur leur repli en dur
(`#c0392b` / `#fdecea`), donc restaient identiques en thème sombre alors que
le reste de l'interface changeait. Remplacés par `var(--danger)` /
`var(--danger-bg)` — les replis valaient EXACTEMENT les valeurs du thème
clair, le rendu clair est donc inchangé et seul le sombre est corrigé.
Même correction sur `.nc-status-dot` et la légende du graphe
(`#00b894`/`#fdcb6e`/`#c0392b` → `var(--ok)`/`var(--warning)`/`var(--danger)`).

**Vérifié réellement** : 12 tests de la logique pure passent sous Node
(zoom ancré sans dérive, butée de zoom, échelle commune aux deux axes du
déplacement, bornage de l'infobulle, contenu des infobulles sur données
partielles) ; analyse syntaxique @babel/parser des 74 fichiers de `hub/src`,
0 échec ; aucun `setXxx` orphelin ; plus aucun `--hub-danger` dans l'arbre.

**⚠️ Non vérifié dans cet environnement** : rendu visuel réel et gestes
souris/molette réels (pas de navigateur ici) ; `npm run build` impossible —
les `node_modules` présents sont ceux d'un macOS (binaire esbuild
« Exec format error » dans ce shell Linux), la vérification syntaxique a donc
été faite avec `@babel/parser` (JS pur) à la place.

**⚠️ Écart de numérotation constaté** : `shared/DELIVERY_NUMBER` était resté à
398 alors que les messages de commit mentionnent #398 à #401. Le badge affiché
suit le FICHIER (`run.sh` le lit tel quel) et affichait donc bien #398 —
incrémenté à #399 ici. Les livraisons #398-#401 des commits ne sont documentées
dans aucune entrée de ce fichier, à rattraper.

**Fichiers** :
- `hub/src/networkCycleGraph.js` — NOUVEAU, logique pure du graphique
- `hub/tests/networkCycleGraph.test.mjs` — NOUVEAU, 12 tests Node
- `hub/src/NetworkCycleView.jsx` — zoom/déplacement, infobulles, rafraîchissement
- `hub/src/App.jsx` — deux entrées de plus dans le menu Réseau
- `hub/src/hub.css` — barre d'outils, infobulle, curseurs, couleurs de thème
- `docs/cycle-agile-reseau.md` — documentation des nouvelles interactions
- `hub/README.md` — journal du module
- 15 fichiers `hub/src/*.jsx` — `--hub-danger` → `--danger`

## 2026-09-06 — Onglet graphique du cycle agile réseau (livraison #398 — entrée reconstruite a posteriori en #401, commit `cc69fd3`)

**Entrée absente au moment de la livraison**, reconstruite depuis le
commit. Le message de commit annonçait « #401 » mais `shared/DELIVERY_NUMBER`
était resté à 398 : le badge affiché à l'écran était donc **#398**, numéro
retenu ici pour rester fidèle à ce que la personne a testé.

Second onglet « 🔄 Graphique » dans la tuile Cycle agile réseau
(`NetworkCycleView.jsx`, +494 lignes ; `hub.css`, +128) :
- cinq nœuds SVG en pentagone (`NODE_POSITIONS`), un par étape, avec
  pastille de statut temps réel (ok/attention/critique/inconnu) et texte
  compact sous le nœud ;
- flèches de flux animées (`stroke-dasharray` + `@keyframes nc-flow`) ;
- clic sur un nœud = sélection de l'étape et retour en mode classique ;
- chargement en parallèle des données des cinq étapes à l'activation de
  l'onglet (le mode classique reste à la demande, étape par étape) ;
- `docs/cycle-agile-reseau.md` complété (+124 lignes).

Zoom/déplacement, infobulles et rafraîchissement automatique sont venus en
#399.

## 2026-09-06 — Nouvelle tuile/outil "gestionnaire de fichiers" (item #26, version: 88fda222b4ad4278, livraison #397)

Trois volets livrés d'un coup :
1. **Espace protégé du hub** -- répertoire sur l'hôte accessible aussi bien
   depuis le hub que directement par la machine hôte. Protégé par rights-api
   (groupe admin_hub par défaut, OPT-IN via `FILE_MANAGER_RIGHTS_API_URL`).
2. **Documents GED** -- agrégé depuis ged-api (lecture seule), organisé par
   entité liée.
3. **Partages SSHFS** -- agrégé depuis ssh-tunnels-api (lecture seule),
   avec stats espace/inodes/latence.

**Backend** (`file-manager/api/app.py`) : Flask, agrégation de ged-api et
ssh-tunnels-api via HTTP interne, scan arborescent de l'espace protégé
(métadonnées uniquement via `os.scandir()` -- jamais de contenu). SQLite
locale pour l'index espace protégé (chemins/taizes/dates).

**Frontend** (`hub/src/FileManagerView.jsx`) : tuile hub avec onglets par
source, navigation arborescente (dossiers d'abord, puis fichiers), stats.

**Sécurité** : protection traversale de chemin (refuse `..`), accès protégé
gated par rights-api, filet de sécurité sur `.json()` pour les appels
internes.

**⚠️ Non vérifié dans cet environnement** : accès réseau réel à ged-api/
ssh-tunnels-api (réseau restreint). Logique testée en profondeur avec des
scénarios simulés.

**Fichiers** :
- `file-manager/api/app.py` -- routes Flask, logique d'agrégation
- `file-manager/api/store.py` -- SQLite (index espace protégé)
- `file-manager/api/Dockerfile` -- image Gunicorn 2 workers
- `file-manager/api/requirements.txt` -- dépendances
- `file-manager/README.md` -- documentation complète
- `hub/src/FileManagerView.jsx` -- composant React
- `hub/src/fileManagerClient.js` -- client API
- `hub/src/App.jsx` -- intégration tuile + viewMode
- `docker-compose.yml` -- service file-manager-api + variable hub
- `.env.example` -- variables FILE_MANAGER_*, GED_API_INTERNAL_URL,
  SSH_TUNNELS_API_INTERNAL_URL
- `tls-proxy/render_nginx_conf.py` -- routage `/api/file-manager/`

## 2026-09-06 — Vérification et documentation complètes du chiffrement des secrets de démarrage (item #22, version: 88fda222b4ad4278, livraison #396)

Vérification systématique de l'ensemble du chantier #22 (points 2/3
de l'urgence matrice de risque -- "mots de passe stockés en clair ->
chiffrer et imposer une réinjection de la clé à chaque déploiement").

**Aucun nouveau code livré** -- toutes les étapes étaient déjà livrées
précédemment (#202-#206, #386-#387) et l'item était marqué "entièrement
complété" dans `BACKLOG.md`. Cette livraison formalise la vérification
complète et la documentation de l'état final.

**Vérifications effectuées** :
- Syntaxe bash de tous les scripts (migrate-env-to-encrypted.sh,
  migrate-ssh-keys-to-encrypted.sh, run.sh)
- Syntaxe Python de tous les modules (secret_crypto.py, secrets_tool.py,
  verify_env_migration.py, verify_file_migration.py, secrets_alert.py)
- Cohérence du câblage run.sh (détection automatique de .env.encrypted,
  déchiffrement à chaque lancement, injection via eval)
- Cohérence des fichiers de documentation (chiffrement-secrets.md,
  pra-secrets-demarrage.docx)
- Cohérence des scripts de migration (séquence sûre : sauvegarde ->
  chiffrement -> déchiffrement de vérification -> comparaison)

**État final de l'item #22** :
- `shared/secret_crypto.py` : primitives PBKDF2-HMAC-SHA256 + Fernet
  (600k itérations, sel 16 octets)
- `scripts/secrets_tool.py` : CLI complète (init-salt, encrypt-value,
  decrypt-value, encrypt-file, decrypt-file, encrypt-env, decrypt-env)
- `scripts/run.sh` : câblage automatique (.env.encrypted détecté et
  déchiffré à chaque lancement, phrase de passe jamais stockée)
- `shared/secrets_alert.py` : alertes PRA (SMS Teltonika TRB140 +
  SMTP, best-effort, jamais bloquant)
- `scripts/migrate-env-to-encrypted.sh` : migration guidée .env
- `scripts/migrate-ssh-keys-to-encrypted.sh` : migration guidée clés SSH
- `scripts/verify_env_migration.py` : comparaison clé par clé
- `scripts/verify_file_migration.py` : comparaison octet par octet
- `docs/chiffrement-secrets.md` : documentation technique complète
- `docs/pra-secrets-demarrage.docx` : procédure PRA (3 canaux)

**Limites connues (assumées et documentées)** :
- La saisie de phrase de passe interactive à travers plusieurs
  invocations Python enchaînées sur un pipe unique a montré des
  instilités dans cet environnement sandboxé (EOFError) -- artefact
  du harnais de test, pas de l'usage interactif normal.
- Le basculement réel (remplacer .env par .env.encrypted, câbler
  ssh-tunnels-api pour lire les clés .enc) reste une décision
  manuelle et séparée de la personne.

`BACKLOG.md` (item 22) confirme : **entièrement complété** — plus aucun
point resté ouvert.

# Changelog

Vue d'ensemble chronologique, du plus récent au plus ancien — le
détail complet de chaque sujet reste dans son README dédié
(`keycloak/README.md`, `tls-proxy/README.md`, `hub/README.md`,
`tickets/README.md`...). Pour les clés `.env` spécifiquement, voir
`ENV_CHANGELOG.md`.

## 2026-09-06 — Tuile « Cycle agile réseau », mode classique (livraison #395 — entrée reconstruite a posteriori en #401, commit `17ab5ce`)

**Entrée absente au moment de la livraison**, reconstruite depuis le
commit. Le message de commit annonçait « #396 », numéro déjà pris par la
vérification du chiffrement des secrets ci-dessous ; #395 est le seul
numéro manquant dans la séquence du journal (394 → 396) et correspond à la
position chronologique de ce commit, juste après l'import initial
(« v#395 »).

Nouvelle tuile hub sous le menu Réseau ▾ : cycle en cinq étapes
Décider → Explorer → Déployer → Mesurer → Apprendre, chaque étape résumant
l'état des outils existants et donnant accès direct à ceux-ci.
- `hub/src/NetworkCycleView.jsx` (476 lignes) — navigation du cycle,
  contenu par étape (KPI, tableaux), boutons précédent/suivant ;
- `hub/src/networkCycleClient.js` — agrège sept API (netmap-orchestrator,
  network-agent, ssh-tunnels, snmp, netprobe, vigilance, backup-restore) ;
- `hub/src/hubEvents.js` (nouveau), `App.jsx`, `hub.css` ;
- `docs/cycle-agile-reseau.md` (146 lignes).

⚠️ Ce commit a aussi versionné par erreur `hub/dist/` (artefacts de build
Vite) et les copies `hub/src/{theme.css,preferences.js,VERSION.json}` que
`run.sh` régénère depuis `shared/` à chaque lancement — retirés de l'index
en #401 (`.gitignore` complété), les fichiers restent sur disque.

## 2026-09-06 — Filtre "période temporelle", les 4 filtres demandés sont désormais tous livrés (version: 1f80f9b25ee9, livraison #394)

Suite de #392 (reste volontairement différé à l'époque) : dernier des
4 filtres demandés ("période temporelle / profondeur de voisinage /
volume de trafic / géographie").

Nouvelle `store.list_devices_for_period` -- pour CHAQUE appareil du
segment, calcule le volume ÉCHANGÉ PENDANT la période choisie PAR
DIFFÉRENCE entre le relevé le plus proche de la fin de période et
celui le plus proche du début (même principe que `/traffic-rate` sur
`snmp-api`, #384 -- un cumul brut ne répond pas à "combien PENDANT
cette période"). Un appareil apparu PENDANT la période utilise 0
comme référence de départ ; un appareil sans relevé dans l'intervalle
est omis (jamais une valeur inventée). Un seul aller-retour base de
données pour tous les appareils du segment, jamais une requête par
appareil.

Nouvelle route `GET /devices/for-period?segment_id=&start=&end=`
(ISO 8601, tous requis). Interface (`NetworkAgentView.jsx`) : deux
sélecteurs de date -- convertis en ISO 8601 complet CÔTÉ CLIENT avant
l'appel (minuit pour le début, fin de journée pour la fin) : une
comparaison de chaînes brutes "YYYY-MM-DD" côté serveur aurait décalé
la borne d'un jour (une date sans heure est toujours "inférieure" à
la même date avec heure, en comparaison lexicographique -- piège
identifié et corrigé AVANT tout test, pas après). Les 3 autres
filtres (profondeur/bâtiment/zone/volume) s'appliquent alors CÔTÉ
CLIENT sur le résultat de cette route, qui ne les connaît pas
nativement (nature de requête différente) -- chaque appareil renvoyé
porte déjà ses attributs statiques en plus de `bytes_total_period`.
Colonne "Volume" du tableau bascule automatiquement en "Volume
(période)" quand ce filtre est actif.

`network-agent/README.md` et `BACKLOG.md` (item 59) mis à jour -- les
4 filtres demandés sont désormais tous livrés.

Vérifié réellement : `list_devices_for_period` testée en profondeur
contre la vraie base générée par `seed_demo_data.py` -- période
complète cohérente, volume d'une première moitié TOUJOURS inférieur
ou égal à celui de la période complète (propriété vérifiée pour
chaque appareil commun), période hors de toute donnée renvoie une
liste vide, deuxième moitié seule strictement inférieure au cumul
total (confirme que ce n'est PAS juste le cumul brut renvoyé). Route
Flask testée (3 scénarios -- période normale, paramètres manquants,
période hors données). Client hub testé (paramètres correctement
encodés). Syntaxe JSX de `NetworkAgentView.jsx` reconfirmée après
l'ajout des sélecteurs de date. **Non vérifié dans cet
environnement** : rendu visuel réel (aucun navigateur ici).

## 2026-09-06 — Données de démo + frontend autonome network-explorer (version: d3ff002c6bc5, livraisons #392-393)

Demandé explicitement : "génère des données d'exemple en volume
suffisant et sur une période de plusieurs mois afin d'affiner la mise
au point de l'interface", avec des filtres "période temporelle /
profondeur de voisinage / volume de trafic / géographie" -- puis,
après une première tentative mal comprise (page HTML statique à
données figées), corrigée par la personne : "je veux un docker front
qui se branche sur le/les dockers api".

### #392 -- Générateur de données + filtres

Nouveau `network-agent/scripts/seed_demo_data.py` -- écrit
directement en SQL (les fonctions `upsert_*` de `store.py` codent
toutes en dur `now_iso()`, jamais paramétrable, donc inutilisables
pour simuler un historique dans le passé). Génère un site "Démo"
clairement étiqueté (jamais confondu avec un site réel), 4 segments
représentant des profondeurs et géographies distinctes, 165
appareils, 25 relevés hebdomadaires sur 6 mois, ~577 liens à volumes
croissants réalistes (jamais linéaires). Reproductible (graine fixe)
et idempotent (ré-exécution supprime d'abord les données précédentes
de ce script).

Migration `_ensure_topology_columns` (même motif que
`_ensure_hostname_columns`, #250) -- nouveaux attributs sur
`na_devices` : `network_depth` (notation "pN.M" -- N = routeurs
traversés depuis le point d'observation, M = commutateurs à ce niveau
-- ex. "p0" direct, "p0.1" 1 commutateur, "p1" 1 routeur),
`building`/`room`/`zone`/`latitude`/`longitude`. Ce module ne DÉDUIT
JAMAIS ces valeurs du trafic réel -- toujours NULL par défaut,
renseignées manuellement ou par ce générateur.

`list_devices` étendu (`depth` répétable, `building`/`room`/`zone`,
`min_bytes_total`) + nouvelle `list_filter_options` (valeurs
distinctes réellement présentes, jamais devinées) -- routes Flask
`/devices` (étendue) et `/filter-options` (nouvelle). Interface
(`NetworkAgentView.jsx`) : cases à cocher profondeur, menus
déroulants bâtiment/zone, champ volume minimum, réinitialisation
automatique au changement de segment.

**Reste HORS de portée, volontairement** : filtre "période
temporelle" -- nature de requête différente (historique à un instant
T passé, pas l'état actuel des compteurs cumulatifs), mérite sa
propre itération plutôt qu'être ajoutée à la hâte.

### #393 -- network-explorer, frontend autonome

Nouveau module `network-explorer` -- frontend React/Vite AUTONOME,
SANS Keycloak ni passerelle (contrairement au hub principal), branché
DIRECTEMENT sur `network-agent-api`/`netmap-orchestrator-api` déjà
exposées (`VITE_NETWORK_AGENT_API_BASE_URL`/
`VITE_NETMAP_ORCHESTRATOR_API_BASE_URL` pointent vers leurs ports
directs, jamais la passerelle).

Réutilise TELLES QUELLES les vues déjà construites pour le hub
(`NetworkAgentView.jsx`, `NetmapOrchestratorView.jsx` + leurs clients/
composants de visualisation/CSS) -- copiées depuis `hub/src` au
moment du build (voir `Dockerfile`), jamais forkées -- même motif
déjà établi dans ce projet pour `vault-admin-portal`
(`vaultOps.js`/`api.js` copiés depuis `vault/portal`). Bandeau
d'onglets minimal entre les deux vues, `onBack` en no-op (pas de
navigation hub à faire ici).

**Aucune protection d'accès** -- même précaution que
`vault-admin-portal`/`launcher` : jamais routé par `tls-proxy`
(vérifié absent de `tls-proxy/render_nginx_conf.py`), LAN de
confiance uniquement. Port 6126 (`NETWORK_EXPLORER_LAN_PORT`).

`network-agent/README.md` et `network-explorer/README.md` créés/mis
à jour, `BACKLOG.md` (nouvel item 59).

Vérifié réellement : générateur exécuté réellement (pas seulement en
isolation) -- 165 appareils confirmés, profondeurs correctement
variées (7 valeurs distinctes), géographie peuplée, progression du
volume confirmée monotone et réaliste. Idempotence confirmée (seconde
exécution ne duplique ni site ni appareils). `list_devices`/
`list_filter_options` testés en profondeur contre cette vraie base
(filtres simples et combinés). Routes Flask testées de bout en bout
(5 scénarios). Client hub testé (rétrocompatibilité confirmée pour
les appels sans filtre). Syntaxe JSX de tous les fichiers touchés
vérifiée, validité YAML du câblage `docker-compose.yml` confirmée.
**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici), `npm install` réel pour `network-explorer` (aucun
`node_modules` construit ici), connexion réelle entre les conteneurs.

## 2026-09-06 — Interface hub pour netmap-orchestrator (version: 6e108accd5a0, livraison #391)

Demandé explicitement ("construis l'interface maintenant") : nouvelle
tuile hub pour consulter les suggestions de `netmap-orchestrator-api`
(#388-390).

`hub/src/netmapOrchestratorClient.js` -- client HTTP même motif que
les autres clients hub. `hub/src/NetmapOrchestratorView.jsx` (menu
"Réseau" -> "Orchestrateur réseau") : filtrage par statut (ouvertes/
rejetées/traitées/toutes), bouton "Lancer une analyse maintenant"
(`POST /run`), tableau des suggestions (message, règle, action
suggérée + contexte, date de détection), boutons rejeter/marquer
traité/rouvrir par ligne. Cette vue n'exécute AUCUNE action elle-même
-- affiche seulement le contexte pour une action manuelle via le
module concerné.

`netmap-orchestrator/README.md` et `BACKLOG.md` (item 58) mis à jour.

Vérifié réellement : syntaxe JSX (`tsc --jsx`) de `App.jsx` et de la
nouvelle vue. Client testé avec `fetch` simulé (8 scénarios --
paramètres de filtrage transmis correctement, absence de query
string sans filtre, méthodes HTTP correctes pour chaque action,
transmission correcte du nouveau statut). **Non vérifié dans cet
environnement** : rendu visuel réel (aucun navigateur ici), et
l'appel réseau réel contre une vraie instance de
`netmap-orchestrator-api`.

## 2026-09-06 — netmap-orchestrator-api routé via la passerelle (version: d2d5a79223f8, livraison #390)

Anticipation d'un besoin futur (interface hub de consultation des
suggestions) : contrairement à `docker-monitor-api` (#376, jamais
routé -- accès au socket Docker, équivaut à un accès root sur
l'hôte), rien ne justifiait de garder `netmap-orchestrator-api` hors
passerelle -- ce module lit seulement `network-agent-api` en HTTP,
aucun privilège particulier.

Ajouté à `tls-proxy/render_nginx_conf.py` (`/api/netmap-orchestrator/`)
et `VITE_NETMAP_ORCHESTRATOR_API_BASE_URL` côté hub -- prêt pour une
future interface, jamais construite ici (pas demandée). Port direct
(6125) conservé EN PLUS, pratique pour un test rapide en `curl` sans
passer par le certificat auto-signé de la passerelle.

`netmap-orchestrator/README.md` mis à jour.

Vérifié réellement : syntaxe Python et YAML, `render_nginx_conf.py --check`
exécuté avec succès (aucune collision de chemin avec les ~25 autres
routes déjà enregistrées).

## 2026-09-06 — Graphe alluvial + radial tree pondéré, premières visualisations de flux (version: 84307414d287, livraison #389)

Suite de #388 (fondation `netmap-orchestrator`) : "les rendus visuels
seront nombreux... démarrons sur des vues connues radial tree,
pixelgrid et ajoutons : graphe alluvial (flux tcpip/udp), radial tree
augmenté avec des liens d'épaisseur proportionnelle au volume
échangé".

Section repliable ajoutée dans `NetworkAgentView.jsx` (hub), à partir
des données `devices`/`links` déjà chargées par cette tuile (aucun
nouvel appel réseau) :

- **Graphe alluvial** -- `hub/src/alluvialLayout.js` (calcul de
  layout pur, testable) + `hub/src/components/AlluvialFlowChart.jsx`
  (rendu SVG). 2 colonnes (sources/destinations), épaisseur des flux
  proportionnelle au volume. Calcul MANUEL, pas de `d3-sankey`.
- **Radial tree augmenté** -- `hub/src/weightedRadialLayout.js`
  (construction de hiérarchie + échelle de largeur, pur) +
  `hub/src/components/WeightedRadialTree.jsx` (rendu). Hiérarchie
  racine -> segment -> appareil, liens croisés entre appareils
  (communications réelles) par-dessus, épaisseur proportionnelle au
  volume. Rendu calqué fidèlement sur `OptickRadialTree.jsx`
  (frontend, motif déjà établi -- même `d3.hierarchy`/`d3.tree`/
  `d3.linkRadial`).

**Contrainte d'environnement ÉNUMÉRÉE et VÉRIFIÉE, pas supposée**
(suite directe de la remarque de méthode faite en #387) : `d3-sankey`
ET `d3` lui-même (le paquet de base, pas seulement l'extension)
testés directement (`npm install`) -- 403 Forbidden confirmé sur les
deux, aucun accès au registre npm pour ces paquets depuis cet
environnement de développement. Conséquence assumée : la
construction de données (hiérarchie, échelles, layout) EST testée en
isolation (fonctions pures, sans `d3`), mais l'appel `d3` lui-même
dans les deux composants de rendu n'a PAS pu être exécuté ici -- à
vérifier en priorité au premier rendu réel.

`network-agent/README.md` et `BACKLOG.md` (item 58) mis à jour.

Vérifié réellement : `alluvialLayout.js` testé avec 13 scénarios
(répartition proportionnelle au volume, filtrage des liens à 0 octet,
repli sur `#id` si aucun libellé, positions X cohérentes) ;
`weightedRadialLayout.js` testé avec 15 scénarios (hiérarchie par
segment, priorité hostname > IP > MAC, échelle de largeur correcte y
compris aux bornes, liens à 0 octet filtrés). Syntaxe JSX des deux
composants de rendu et de `NetworkAgentView.jsx` vérifiée
(`tsc --jsx`), insertion confirmée unique (pas de duplication).
**Non vérifié dans cet environnement** : le rendu visuel réel (voir
contrainte `d3` ci-dessus) -- particulièrement `WeightedRadialTree.jsx`,
dont l'appel `d3.hierarchy`/`d3.tree`/`d3.linkRadial` n'a jamais pu
être exécuté directement ici, même s'il reprend fidèlement l'API déjà
utilisée par `OptickRadialTree.jsx`.

## 2026-09-06 — Nouveau module netmap-orchestrator : fondation de l'orchestrateur d'analyse réseau (version: 78ac1defab8e, livraison #388)

Recentrage explicite du volet Nebula : "définitivement limité à
l'import de fichiers de données. En revanche le besoin d'analyse et
de supervision d'un environnement réseau comme celui contrôlé par
nebula est prioritaire". Scénario de départ demandé : liste IP/MAC/
DNS/ports confirmée dans le temps, liste des flux/volumes/paquets
échangés dans le temps, puis un orchestrateur proposant des étapes
d'analyse.

**Découverte majeure faite avant de coder** : les deux listes
demandées existent DÉJÀ intégralement dans `network-agent-api` --
`na_devices` (IP/MAC/hostname DNS, `first_seen` jamais réécrit),
`na_device_services` (ports), `na_device_links`/
`na_device_link_services` (flux/volumes/paquets), tables d'historique
par relevés périodiques (#251) pour le suivi dans le temps. Rien
reconstruit en double.

Nouveau module `netmap-orchestrator` construit PAR-DESSUS ces
données (lues via l'API HTTP de network-agent-api, jamais dupliquées) :

- `store.py` -- suggestions stockées SANS DOUBLON (une ligne par
  règle/sujet, même motif accumulatif que network-agent lui-même),
  réouvertes automatiquement si la condition revient après une
  clôture (dismissed/done).
- `network_agent_client.py` -- client HTTP best-effort, même motif
  déjà établi (netprobe -> network-agent-api).
- `rules/` (3 règles de départ) -- `no_services` (appareil sans
  service détecté depuis 30 min, suggère un scan actif nmap),
  `new_device` (appareil apparu depuis moins de 15 min, informatif),
  `snmp_candidate` (trafic sur le port 161 observé, suggère un
  enregistrement dans snmp-api). Architecture calquée sur
  `netprobe/api/analyzer_engine.py` (#307) -- calcul pur séparé de
  l'écriture, une règle en échec n'empêche jamais les autres.
- `engine.py`/`app.py` -- orchestration, routes API (`/rules`,
  `/run`, `/run/<nom>`, `/suggestions`, `/summary`).

Ce module ne lance rien lui-même -- chaque suggestion porte le
contexte nécessaire (`suggested_action`/`action_params`) pour qu'une
action réelle soit déclenchée via le module concerné.

Câblé dans `docker-compose.yml` (port 6125). **UN SEUL worker
Gunicorn** -- même raisonnement que `docker-monitor-api` (#376) : la
boucle de fond (passage périodique des règles) tournerait en double
avec 2 workers séparés.

`netmap-orchestrator/README.md` créé, `BACKLOG.md` (nouvel item 58).

**Reste à construire, itérations suivantes** (annoncé explicitement
comme un "cycle permanent de retour") : graphe alluvial (flux TCP/
IP/UDP) et radial tree augmenté (liens d'épaisseur proportionnelle
au volume) -- toutes les données nécessaires sont déjà accessibles
via network-agent-api.

Vérifié réellement : syntaxe Python (8 fichiers) et YAML.
`store.py` testé en profondeur (création, mise à jour sans doublon,
comptage par statut) -- **un vrai bug trouvé et corrigé en
testant** : une mise à jour qui ne fournissait pas de nouveaux
`action_params` effaçait ceux déjà enregistrés -- corrigé en les
préservant explicitement dans ce cas. `engine.py` testé avec
`network_agent_client` mocké sur des données réalistes (3 règles
déclenchées correctement, aucun doublon après un second passage).
Routes Flask testées de bout en bout (12 scénarios). **Non vérifié
dans cet environnement** : l'appel réseau réel contre un vrai
`network-agent-api` (aucune instance disponible ici).

## 2026-09-06 — Script de migration guidée pour les clés SSH, item 22 entièrement complété (version: 6e795ec3bc1b, livraison #387)

Suite directe de #386 (migration `.env`) : dernier point resté ouvert
de l'item 22 -- les clés SSH de `ssh-tunnels/keys/`.

Nouveau `scripts/migrate-ssh-keys-to-encrypted.sh` -- même séquence
sûre que `migrate-env-to-encrypted.sh` (sauvegarde -> chiffrement ->
déchiffrement de vérification), adaptée aux fichiers BINAIRES :
nouveau `scripts/verify_file_migration.py` compare OCTET PAR OCTET
(pas clé=valeur, une clé SSH n'a pas cette structure). Découvre
TOUTES les clés de `ssh-tunnels/keys/` automatiquement, même
convention que ce module lui-même (un fichier = une clé, `README.md`/
`*.pub` exclus). Phrase de passe redemandée séparément pour chaque
clé, jamais stockée ni réutilisée automatiquement.

**Bug réel trouvé et corrigé en écrivant ce script** : les arguments
`path` de `encrypt-file`/`decrypt-file` sont POSITIONNELS, pas
`--path` -- confondu une première fois avec la convention `--input`/
`--output` de `encrypt-env`/`decrypt-env` (qui eux SONT nommés).
Corrigé avant tout test.

**Point de méthode appliqué suite à une remarque directe de la
personne pendant cette livraison** : les contraintes d'environnement
(ex. compatibilité bash 3.2, cible macOS de ce projet) doivent être
énumérées clairement et testées quand c'est possible, plutôt que
contournées par des suppositions prudentes non vérifiées. Vérifié
concrètement ici : bash 3.2 n'est disponible par AUCUNE voie
accessible dans cet environnement de développement (ni apt, ni
archives sources -- réseau restreint aux dépôts Ubuntu modernes,
5.2.21 seulement). Pour l'itération sur un tableau bash potentiellement
vide sous `set -u`, résolu en choisissant un motif UNIVERSELLEMENT
sûr (vérifier `${#TABLEAU[@]}` avant d'itérer) plutôt que de compter
sur un comportement `${TABLEAU[@]:-}` non vérifiable dans cet
environnement.

`ssh-tunnels/README.md` et `docs/chiffrement-secrets.md` mis à jour.
`BACKLOG.md` (item 22) marqué entièrement complété.

Vérifié réellement : syntaxe bash et Python, `verify_file_migration.py`
testé (identique, différent). Script d'orchestration testé de bout
en bout avec les VRAIS outils de chiffrement sur une clé de test
réaliste (échoue en pratique à l'étape de vérification à cause d'une
limite du harnais de test lui-même -- même artefact que #386, saisie
de phrase de passe à travers plusieurs invocations Python enchaînées
sur un pipe unique), PUIS avec des remplaçants factices pour isoler
la logique d'orchestration : succès, écart détecté (clé d'origine
confirmée INTACTE), dossier sans clé à migrer (`README.md`/`*.pub`
correctement exclus de la découverte) -- les trois cas se comportent
comme prévu.

## 2026-09-05 — Script de migration guidée .env -> .env.encrypted (version: 0a874dfcff6d, livraison #386)

Backlog item 22, demandé explicitement ("continue sur le 22") : la
seule étape non franchie restait la migration des VRAIS secrets --
volontairement séquencée, jamais improvisée, avec sauvegarde et
retour arrière clairs.

Nouveau `scripts/migrate-env-to-encrypted.sh` -- orchestre les
primitives déjà existantes et testées (`secrets_tool.py encrypt-env`/
`decrypt-env`, #204/#205) dans une séquence SÛRE :
1. Sauvegarde horodatée du `.env` d'origine (jamais écrasée).
2. Chiffrement vers `.env.encrypted`.
3. Déchiffrement DE VÉRIFICATION immédiat + comparaison clé par clé
   avec l'original (nouveau `scripts/verify_env_migration.py`,
   dé-quotage `shlex` correct, réutilise `parse_env_file` de
   `check-env.py` plutôt qu'un second analyseur) -- pas une confiance
   aveugle dans le chiffrement, une vérification RÉELLE que
   l'aller-retour est fidèle à 100 %.

`.env` d'origine et sa sauvegarde ne sont JAMAIS touchés par ce
script, quel que soit le résultat (succès ou écart détecté). Le
BASCULEMENT réel (renommer `.env`, confirmer qu'un déploiement
fonctionne, supprimer la sauvegarde) reste une décision et une action
MANUELLES et séparées de la personne -- ce script prépare et vérifie,
il ne bascule jamais tout seul.

`docs/chiffrement-secrets.md` (nouvelle section "voie recommandée")
et `BACKLOG.md` (item 22) mis à jour.

Vérifié réellement : `verify_env_migration.py` testé avec 3 scénarios
(tout correspond, valeur différente, clé manquante -- y compris une
valeur avec apostrophe, dé-quotage confirmé correct). Script
d'orchestration testé de bout en bout avec les VRAIS outils de
chiffrement (`cryptography` disponible dans cet environnement,
contrairement à `ping`/`iperf3`/`pysnmp`) sur un `.env` de test
réaliste, ET séparément avec des remplaçants factices pour isoler la
logique d'orchestration (sauvegarde créée, cas de succès, cas
d'incohérence détectée -- `.env` original confirmé INTACT dans les
deux cas, refus d'écraser un `.env.encrypted` déjà présent). **Limite
du test avec les vrais outils** : la saisie de phrase de passe
interactive à travers plusieurs invocations Python enchaînées via un
seul pipe stdin s'est révélée peu fiable spécifiquement dans cet
environnement sandboxé (`EOFError` sur la 3e invite) -- comportement
d'un harnais de test automatisé, pas de la vraie utilisation
interactive -- à confirmer malgré tout au premier usage réel.

**Reste NON traité par ce script** : clés SSH de
`ssh-tunnels/keys/` (mentionnées dans la demande d'origine --
`encrypt-file`/`decrypt-file` de `secrets_tool.py` déjà prêtes, mais
pas encore orchestrées de façon aussi guidée que le `.env`).

## 2026-09-05 — Débit réel (iperf3) sur netprobe-api, sans matériel RF (version: ba5faa365bc5, livraison #385)

Suite de #384 (reformulation item 47) : "voyons ce qu'on peut déjà
faire sans RF simplement avec un client wifi et la couche IP et le
snmp". Nouveau `iperf3_probe.py` (`netprobe-api`) -- même motif que
`ping_probe.py`/`nmap_probe.py` (appelle le VRAI binaire `iperf3` via
sous-processus, format JSON `-J` pour un parsing fiable, schéma
confirmé par recherche multi-sources avant d'écrire le code, jamais
deviné). Nouvelle table `iperf3_tests` (même motif que `nmap_scans`
-- à la demande, jamais programmé automatiquement : un test consomme
de la vraie bande passante pendant plusieurs secondes).

Routes : `POST /iperf3/test` (`target_id`, `port`? défaut 5201,
`duration_seconds`? 1-30, défaut 5), `GET /iperf3/tests?target_id=`.
La cible doit être un serveur iperf3 déjà en écoute, enregistré comme
n'importe quelle autre cible de ce module.

**⚠️ Limite architecturale IMPORTANTE, découverte en construisant ce
module -- PAS résolue ici** : ce conteneur n'a PAS
`network_mode: host` -- le débit mesuré reflète le chemin réseau réel
(traverse la vraie interface de l'hôte), MAIS ce module ne peut PAS
voir le BSSID/l'itinérance WiFi de l'hôte (propriété du pilote WiFi,
invisible depuis un namespace réseau Docker isolé). Le suivi de
roaming reste HORS de portée tant que l'architecture d'agents
multi-hôtes (items 45/48 du backlog, volontairement non tranchée)
n'est pas décidée avec la personne.

**Bug réel trouvé et corrigé en testant** : `duration_seconds=0`
était interprété comme "non fourni" à cause de l'évaluation Python
`0 or 5` (0 est faux) -- MÊME piège déjà rencontré et corrigé sur
`snmp-api`/`sample_interval` quelques livraisons plus tôt (#384) --
corrigé en distinguant explicitement l'absence de la valeur (`None`)
de zéro.

`iperf3` ajouté à l'installation du Dockerfile `netprobe-api`.
`netprobe/README.md` et `BACKLOG.md` (item 47) mis à jour.

Vérifié réellement : syntaxe Python (3 fichiers touchés),
`iperf3_throughput()` testée avec `subprocess.run` simulé (6
scénarios -- succès, erreur de connexion serveur, binaire
introuvable, délai dépassé, JSON invalide, réponse incomplète),
routes Flask testées de bout en bout (création de cible réelle via
`store.add_target`, test normal, `target_id` manquant/inconnu, bornes
de `duration_seconds` -- y compris le cas limite qui a révélé le bug
ci-dessus). **Non vérifié dans cet environnement**, comme le reste de
ce module : l'appel réseau réel contre un vrai serveur iperf3
(`iperf3` non installable ici, réseau restreint).

## 2026-09-05 — Reformulation items 47/49 + POST /traffic-rate sur snmp-api (version: 3b2698f5fac4, livraison #384)

Redirection explicite de la personne sur deux items du backlog liés
au volet WiFi :

- **Item 49** recentré : "télémétrie d'un réseau/site il s'agit
  d'analyser le trafic" -- l'objectif réel est le volume/pattern de
  trafic, pas le statut en ligne/hors ligne des bornes (déjà couvert
  par l'API Nebula, mais bloquée sur une licence Pro Pack). SNMP
  standard (`IF-MIB`) devient la piste principale, sans ce prérequis
  administratif.
- **Item 47** reformulé : "voyons ce qu'on peut déjà faire sans RF
  simplement avec un client wifi et la couche IP et le snmp" --
  priorité changée pour commencer par ce qui NE dépend PAS du
  matériel RF (RTL8812AU/HackRF, achetés mais toujours pas reçus).

**Implémenté** : `POST /traffic-rate` sur `snmp-api` -- débit réel
par interface (octets/s, entrant et sortant), calculé par différence
entre deux relevés des compteurs 64 bits IF-MIB
(`ifHCInOctets`/`ifHCOutOctets`, RFC 2863/3273 -- préférés aux
compteurs 32 bits historiques pour éviter un rebouclage sur un lien
gigabit+) espacés de `sample_interval` secondes (1-60, défaut 5).
Fonction de parcours (`_walk_interfaces`) généralisée
(`_walk_table`) pour être partagée avec la nouvelle
`_walk_traffic_counters`, plutôt que dupliquer la boucle GETBULK.
Rebouclage de compteur détecté (delta négatif) -- interface omise
plutôt qu'un débit négatif absurde.

**Bug réel trouvé et corrigé en testant** : `sample_interval=0`
était interprété comme "non fourni" à cause de l'évaluation Python
`0 or 5` (0 est faux) -- retombait silencieusement sur la valeur par
défaut (5) au lieu d'être rejeté par la vérification de bornes.
Corrigé en distinguant explicitement l'absence de la valeur (`None`)
de zéro.

`snmp/README.md` et `BACKLOG.md` (items 47/49) mis à jour.

Vérifié réellement : syntaxe Python, logique de calcul de débit
testée EN ISOLATION avec 4 scénarios (cas normal, rebouclage,
interface nouvelle/absente, valeur non numérique) -- comparée ligne
à ligne au code réel pour confirmer l'identité. Route Flask testée
avec `snmp_client.get_interface_traffic_rate` mocké (bornes 1-60,
valeur par défaut, cas limite `sample_interval=0` qui a révélé le
bug ci-dessus). **Non vérifié dans cet environnement**, comme le
reste de ce module : le prélèvement réel des compteurs contre un vrai
équipement SNMP (`pysnmp` non installable ici, réseau restreint).

## 2026-09-05 — Tuile hub pour docker-monitor-api construite PUIS ANNULÉE (version: 060aa89657a0, livraison #383)

Reprise du backlog : `docker-monitor-api` n'a pas de tuile hub,
construite (`DockerMonitorView.jsx`, `dockerMonitorClient.js`, câblage
`App.jsx` complet) -- puis ANNULÉE avant livraison en réalisant un
problème réel : le hub principal est servi en HTTPS (via `tls-proxy`),
mais `docker-monitor-api` n'est délibérément JAMAIS routé par la
passerelle publique (précaution sécurité, socket Docker monté) --
un appel HTTP simple depuis une page HTTPS est bloqué par les
navigateurs ("contenu mixte"), rendant l'intégration non fonctionnelle
telle que construite. Même contrainte que `vault-admin-api`, qui la
résout avec son PROPRE portail séparé (HTTP direct, jamais intégré au
hub) -- solution non construite ici, hors du périmètre "à minima"
demandé à l'origine.

Fichiers créés puis supprimés (`hub/src/DockerMonitorView.jsx`,
`hub/src/dockerMonitorClient.js`), câblage `App.jsx` entièrement
retiré (import, constante d'URL, entrée de menu, rendu conditionnel)
-- vérifié aucune trace résiduelle, syntaxe confirmée propre après
retrait. `docker-monitor/README.md` complété avec une note explicite
pour éviter de retomber dans le même piège plus tard.

## 2026-09-05 — Authentification LDAP confirmée fonctionnelle en conditions réelles (version: 5756c24d036c, livraison #382)

Clôture de la saga LDAP #359-#381 : la personne confirme que
l'authentification via le hub fonctionne après le correctif de
chemin de montage (#381) et un dernier `reset-ldap-test`. `alice`/
`bob`/`admin_test` sont désormais correctement créés dans l'annuaire
de test et reconnus par Keycloak.

## 2026-09-05 — La vraie cause du bootstrap LDAP jamais appliqué : chemin de montage mal résolu (version: e36150d8a7d5, livraison #381)

Conclusion de la saga #368/#375/#378/#379 : `docker exec
supervision-si-gateway-openldap-test-1 ls -la /container/service/slapd/
assets/config/bootstrap/ldif/custom/` (demandé après un premier
amorçage confirmé avec `--loglevel debug` toujours sans trace de
traitement du fichier personnalisé, contrairement à TOUS les autres
fichiers de bootstrap) a montré ce dossier **VIDE** à l'intérieur du
conteneur.

**Vraie cause** : `--project-directory "$PROJECT_ROOT"`
(`gateway/scripts/run.sh`) pointe DÉLIBÉRÉMENT vers la racine du
projet PRINCIPAL (pas `gateway/`), pour que d'autres chemins relatifs
de `gateway/docker-compose.yml` (`./keycloak/import`, `./pki/server`
-- dossiers PARTAGÉS avec le stack principal, à la racine) résolvent
correctement. Mais `./ldap-seed` (le dossier contenant
`bootstrap.ldif`) suivait AUSSI cette même résolution vers la racine,
alors que ce dossier vit DANS `gateway/` (`gateway/ldap-seed/`) --
erreur introduite dès la création de ce montage (#348), jamais
remarquée depuis. **Docker Compose crée SILENCIEUSEMENT un dossier
vide quand la source d'un bind mount est introuvable sur l'hôte, sans
jamais signaler d'erreur** -- exactement pourquoi aucune trace
d'échec n'apparaissait nulle part, dans aucun journal, à aucun niveau
de verbosité, quel que soit le correctif tenté sur
`--copy-service`/`LDAP_REMOVE_CONFIG_AFTER_SETUP` (aucun des deux
n'était FAUX en soi pour le problème qu'il visait -- juste sans
rapport avec CE problème précis).

**Corrigé** : `./ldap-seed` → `./gateway/ldap-seed` dans
`gateway/docker-compose.yml`. `--loglevel debug` (diagnostic
temporaire de #379) retiré, plus nécessaire.

`gateway/README.md` (section dédiée, conclusion de la saga complète)
et `BACKLOG.md` (item 56) mis à jour.

**Leçon retenue, notée pour la suite** : deux correctifs successifs
ont été tentés sur la mauvaise hypothèse (mécanismes internes de
l'image osixia) avant de remettre en question le montage lui-même --
une vérification directe (`docker exec ... ls`) aurait révélé le
problème dès le début, plus vite qu'une recherche sur le comportement
interne de l'image. Pour un chemin de bind mount qui semble "ne rien
faire" silencieusement, vérifier D'ABORD sa VISIBILITÉ réelle depuis
l'intérieur du conteneur avant de chercher plus loin.

⚠️ **`reset-ldap-test` À REFAIRE une dernière fois** pour repartir
d'un bootstrap réellement propre, cette fois avec le fichier
RÉELLEMENT visible depuis le conteneur.

Vérifié réellement : validité YAML, absence de doublon sur la ligne
de montage. **Non vérifié dans cet environnement** : confirmation
que ce correctif résout effectivement l'authentification LDAP en
conditions réelles -- à confirmer au prochain `reset-ldap-test` de la
personne.

## 2026-09-05 — Route /containers/<nom>/logs sur docker-monitor-api (version: 26d39fcd39d8, livraison #380)

Demandé implicitement -- "c'était le but du moniteur" : le
visualiseur de logs Portainer ne permettait pas de remonter avant un
certain point, empêchant de voir le passage "Add custom bootstrap
ldif..." nécessaire au diagnostic en cours (#379). Nouvelle route
`GET /containers/<nom>/logs?tail=N` sur `docker-monitor-api` --
renvoie les logs BRUTS complets d'un conteneur via l'API Docker
directement (même mécanisme `container.logs()` que la boucle
d'analyse), contournant toute limite de pagination d'un visualiseur
tiers. Testée avec le module `docker` simulé (contenu correct
renvoyé, 404 propre sur conteneur inexistant). `docker-monitor/README.md`
mis à jour.

## 2026-09-05 — LDAP_REMOVE_CONFIG_AFTER_SETUP=false n'a pas suffi : diagnostic debug temporaire (version: 86b708e92d85, livraison #379)

Suite directe de #378 : logs partagés en conditions réelles après le
correctif -- "err=32 nentries=0" persiste sur `ou=users`, EXACTEMENT
le même symptôme qu'avant, malgré le remplacement de
`--copy-service`.

**Reconsidéré après recherche plus approfondie** : un rapport
similaire (`osixia/docker-openldap#179`) montre la MÊME séquence de
log ("Add custom bootstrap ldif..." suivi immédiatement de l'étape
suivante, sans rien entre les deux) dans un cas où le bootstrap
personnalisé FONCTIONNAIT correctement -- ce silence est donc NORMAL
à `CONTAINER_LOG_LEVEL=3` (info), pas une preuve d'échec. Le
diagnostic de #378 attribuant la cause à `--copy-service` était
probablement HÂTIF -- la vraie cause reste à confirmer.

Ajouté temporairement `command: ["--loglevel", "debug"]` sur
`openldap-test` pour voir ce qui se passe RÉELLEMENT à l'intérieur de
cette étape -- à retirer une fois la vraie cause trouvée (verbeux,
pas destiné à la configuration normale).

**Non résolu à ce stade** -- en attente des logs debug de la
personne après un nouveau `reset-ldap-test`.

## 2026-09-05 — --copy-service avait lui-même un bug : remplacé par LDAP_REMOVE_CONFIG_AFTER_SETUP=false (version: aa3f752aaed4, livraison #378)

Suite directe de #375 : après avoir utilisé `reset-ldap-test`,
Keycloak échouait avec une NOUVELLE erreur -- "LDAP: error code 32 -
No Such Object" sur `ou=users,dc=supervision-si,dc=local` (recherche
renvoyant 0 résultat), alors que l'authentification du compte de
liaison elle-même RÉUSSISSAIT cette fois (progrès réel par rapport à
#368/#375).

Logs du conteneur `openldap-test` demandés et obtenus -- confirmé :
"Add custom bootstrap ldif..." s'affiche, mais AUCUNE trace d'ajout
réel derrière (contrairement à un bootstrap qui fonctionne). Fichier
LDIF (`gateway/ldap-seed/bootstrap.ldif`) vérifié correct -- crée bien
`ou=users` avant les comptes.

**Cause RÉELLEMENT trouvée** : `--copy-service` (ajouté en #364 pour
corriger "Device or resource busy", #359) a LUI-MÊME un bug CONNU et
documenté (`osixia/docker-openldap#310`, 2019) : quand le dossier de
bootstrap personnalisé est LUI-MÊME un point de montage séparé (notre
cas exact), la copie interne
(`/container/service` → `/container/run/service`) échoue
SILENCIEUSEMENT à recopier ce sous-dossier précis -- le bootstrap
personnalisé tournait alors sur un dossier vide, sans jamais signaler
d'erreur bloquante.

**Corrigé** : remplacé par `LDAP_REMOVE_CONFIG_AFTER_SETUP=false`
(variable d'environnement, pas un changement de commande) --
contournement DIFFÉRENT trouvé dans la même recherche
(`osixia/docker-openldap#660`) : évite le problème à la racine en
désactivant l'étape de suppression des fichiers de config après
amorçage (celle qui échouait à l'origine sur le point de montage) --
sans jamais passer par un mécanisme de copie qui a ses propres angles
morts avec des points de montage imbriqués.

⚠️ **`reset-ldap-test` À REFAIRE** après ce correctif -- les volumes
existants ont un bootstrap personnalisé jamais réellement appliqué
malgré ce que leur journal suggérait.

`gateway/README.md` (section réécrite), `BACKLOG.md` (item 56, suite)
et les notes de suivi internes mis à jour pour refléter ce
remplacement -- l'ancienne mention de `--copy-service` comme
solution "recommandée par le mainteneur" reste vraie pour LE
problème qu'elle visait, mais s'avère elle-même bogguée pour notre
cas d'usage précis (point de montage imbriqué).

**Leçon retenue, notée pour la suite** : un contournement "recommandé
par le mainteneur" pour un bug peut avoir SON PROPRE bug documenté
séparément -- toujours chercher `<mécanisme de contournement> bug`
en plus de `<symptôme original> known issue` avant de considérer un
correctif définitivement clos.

Vérifié réellement : validité YAML. **Non vérifié dans cet
environnement** : confirmation que ce nouveau correctif résout
effectivement l'authentification en conditions réelles -- à confirmer
au prochain `reset-ldap-test` de la personne.

## 2026-09-05 — docker-monitor-api confirmé en conditions réelles (version: 32b32ceac441, livraison #377)

Suite directe de #376 : la personne a déployé `docker-monitor-api` et
partagé le fichier d'analyse réel après quelques minutes de
fonctionnement -- confirme que TOUT ce qui restait "non vérifié"
dans #376 fonctionne réellement :

- `docker.from_env()` joint bien le socket Docker monté (le worker
  Gunicorn démarre proprement, aucun plantage au chargement du
  module -- si la connexion avait échoué, le worker n'aurait jamais
  fini de démarrer).
- La boucle d'arrière-plan tourne correctement -- 13 conteneurs
  examinés à chaque passage, intervalle ~60s respecté.
- Le mécanisme incrémental (`container.logs(since=...)`) fonctionne
  exactement comme conçu : le PREMIER passage a examiné l'historique
  existant (avertissements bénins trouvés chez
  `supervision-si-tickets-postgres-1` et
  `supervision-si-gateway-keycloak-1` -- probablement liés aux
  locales manquantes et au mode développement, déjà rencontrés
  ailleurs dans ce projet), les passages SUIVANTS ne réexaminent PAS
  ces mêmes lignes (elles auraient sinon réapparu à chaque passage
  dans le fichier réel observé -- ce n'est PAS le cas).
- `docker-monitor-api` lui-même n'apparaît jamais avec une entrée
  d'anomalie -- attendu, ses propres logs de démarrage Gunicorn sont
  propres (confirme "y compris lui-même" sans pour autant produire de
  fausses alertes sur son propre fonctionnement normal).

`docker-monitor/README.md` et `BACKLOG.md` (item 57) mis à jour pour
refléter cette confirmation réelle, retirant la mention "non vérifié"
qui ne tient plus.

## 2026-09-05 — Nouveau module docker-monitor-api : contrôle minimal + analyse de logs externalisée (version: 18aeb2ee5afa, livraison #376)

Demandé explicitement : "extraire de portainer.io de quoi construire
un docker qui contrôle les autres stacks/containers à minima qui lise
et analyse les logs de tous les container y compris lui-même et
publie son analyse dans un fichier log externe".

Recherche menée sur l'architecture RÉELLE de Portainer avant de coder
-- confirmé par plusieurs sources indépendantes : Portainer monte
`/var/run/docker.sock` pour parler à l'API Docker via SDK, ce qui
ÉQUIVAUT À UN ACCÈS ROOT sur la machine hôte (un conteneur avec ce
socket peut créer un autre conteneur montant `/` de l'hôte). Nouveau
module `docker-monitor/` reprend ce même principe -- documenté très
explicitement dans le code, le README et docker-compose.yml, jamais
caché.

**Chevauchement partiel trouvé EN CONSTRUISANT ce service** : ce
projet a DÉJÀ `launcher` (contrôle start/stop/status par groupe de
services nommé, interface web) -- `docker-monitor-api` refait une
partie de ce contrôle (start/stop/restart PAR CONTENEUR individuel,
interface JSON plutôt qu'UI). Gardé quand même ("à minima" demandé
pour ce service précis, une interface JSON restant utile en soi --
consommable par une future tuile hub sans parser de HTML) -- mais
documenté explicitement plutôt que silencieusement dupliqué.

**Ce qui est GENUINEMENT nouveau** (ni `launcher` ni aucun autre
service de ce projet ne le fait) : boucle d'arrière-plan périodique
(`DOCKER_MONITOR_INTERVAL_SECONDS`, défaut 60s) qui, pour CHAQUE
conteneur (`docker_client.containers.list(all=True)` -- inclut CE
conteneur lui-même, "y compris lui-même" demandé explicitement, aucun
traitement spécial requis côté API Docker), récupère les lignes de
log NOUVELLES depuis le dernier passage (`container.logs(since=...)`,
jamais un ré-examen des mêmes lignes), cherche des motifs d'erreur/
avertissement choisis à partir d'incidents RÉELLEMENT rencontrés dans
CE projet au fil des livraisons (`ERROR`, `CRITICAL`, `Exception`,
`Traceback`, `Killed`, `FATAL`, `OOMKilled`, `WARN`/`WARNING` --
jamais une liste générique improvisée), et écrit un résumé en AJOUT
dans un fichier **EXTERNE** (volume monté, survit à un redémarrage/
une reconstruction de ce conteneur lui-même).

**Concurrence** : tourne avec **UN SEUL worker Gunicorn**
(`--workers 1`), contrairement aux 2 workers habituels des autres
backends de ce projet -- DÉLIBÉRÉ : la boucle d'analyse tournerait en
DOUBLE avec 2 workers séparés (2 process Python distincts, chacun sa
propre boucle) -- double écriture dans le fichier externe, double
charge sur l'API Docker.

Routes : `GET /containers`, `POST /containers/<nom>/start|stop|restart`,
`GET /analysis?limit=N`, `GET /health`, `GET /logs`, `GET /version`.
Volontairement absent : suppression/création/pull d'image (hors du
périmètre "à minima").

Nouvelles variables `.env` : `DOCKER_MONITOR_API_PORT` (défaut 6124),
`DOCKER_MONITOR_ANALYSIS_DIR`, `DOCKER_MONITOR_INTERVAL_SECONDS`,
`DOCKER_MONITOR_TAIL_LINES`. **Jamais routé par la passerelle
publique** (vérifié absent de `tls-proxy/render_nginx_conf.py`) --
même précaution que `launcher`/`vault-admin-api`, accès direct LAN
uniquement. `docker-monitor/README.md` créé (détail complet, y
compris le raisonnement sécurité), `BACKLOG.md` (item 57), `.gitignore`
(motif `docker-monitor/analysis/*` + `!README.md`, même convention
que `ssh-tunnels/keys`/`mounts`).

Vérifié réellement : syntaxe Python, module `docker` (docker-py)
ENTIÈREMENT simulé pour tester en profondeur (paquet réel non
installable, réseau restreint dans cet environnement) -- listage de
conteneurs avec détection correcte de soi-même, start/stop/restart,
404 sur conteneur inexistant, `/health` reflétant la connectivité
Docker (dégradé si `ping()` échoue), analyse testée avec des journaux
simulés réalistes (conteneur sain correctement absent du fichier
d'analyse, conteneur avec erreurs LDAP + "Killed" correctement détecté
et résumé -- jamais les lignes brutes recopiées telles quelles),
`/version`/`/logs` confirmés fonctionnels après intégration.
**Non vérifié dans cet environnement** : exécution contre un VRAI
socket Docker (aucun disponible ici) -- en particulier le comportement
réel de `container.logs(since=...)` et `docker.from_env()` contre un
vrai démon, à vérifier en priorité au premier déploiement réel.

## 2026-09-05 — reset-ldap-test : script de nettoyage pour annuaire de test mal amorcé (version: fb297622da72, livraison #375)

Demandé explicitement ("peux tu préparer une script de nettoyage ?")
après un cas RÉEL signalé en conditions réelles, suite directe de
#368 : `.env` avait `LDAP_BIND_PASSWORD` et `LDAP_TEST_ADMIN_PASSWORD`
identiques et corrects (vérifié par la personne), mais Keycloak
refusait quand même l'authentification LDAP -- "LDAP: error code 49 -
Invalid Credentials".

**Cause la plus probable, jamais confirmée à 100 % (aucun accès
direct aux conteneurs de la personne pour vérifier)** : l'annuaire
`openldap-test`, comme Keycloak (voir #368), n'amorce ses données
QU'À LA CRÉATION de ses volumes -- jamais relues ensuite même si
`.env` change après coup. Si l'annuaire a été démarré une première
fois quand `.env` portait ENCORE un autre mot de passe, ce mot de
passe reste figé indéfiniment côté annuaire, quoi que `.env`
contienne désormais.

Nouvelle commande `./gateway/scripts/run.sh reset-ldap-test` -- même
motif de sécurité que `reset-keycloak` déjà existant (confirmation
stricte "RESET"), mais cible SEULEMENT le service `openldap-test`
(arrêt + suppression du conteneur, pas tout le stack gateway) --
contrairement à `keycloak_data` (volume `external: true`), les
volumes `openldap-test` sont NORMAUX, mais trouvés ici par le MÊME
filtre d'étiquette Compose que `find_keycloak_volume()` (jamais un
nom de volume en dur, le préfixe dépend de `COMPOSE_PROJECT_NAME`).
Relancer `gateway` ensuite réamorce l'annuaire entièrement neuf avec
le mot de passe ACTUEL de `.env`.

`gateway/README.md` (nouvelle section) et `BACKLOG.md` (item 56) mis
à jour.

Vérifié réellement : syntaxe bash, logique testée avec Docker/compose
simulés (confirmation refusée -- rien touché ; confirmation acceptée
-- arrêt du conteneur puis suppression des deux volumes trouvés
correctement par leur étiquette). **Non vérifié dans cet
environnement** : confirmation que cette commande résout
effectivement l'authentification LDAP de la personne en conditions
réelles -- hypothèse de cause non confirmée à 100 %, comme documenté.

## 2026-09-05 — install.sh : déploiement automatisé adapté à l'environnement (version: 8d3f0856be3b, livraison #374)

Demandé explicitement, après une session de déploiement
particulièrement difficile (OOM Keycloak, LDAP mal configuré, volume
externe non purgé...) : "une archive et un script qui déploie sans
intervention manuelle avec une config complète d'exemples et une
évaluation initiale de l'environnement pour cadrer les services
déployés qui s'adapte à l'os".

Nouveau `install.sh` à la racine du projet :
- Vérifie Docker présent/démarré/plugin compose v2 -- message clair
  et sortie propre sinon, jamais un plantage silencieux.
- Détecte la mémoire RÉELLEMENT disponible pour Docker via `docker
  info --format '{{.MemTotal}}'` -- confirmé par recherche (plusieurs
  sources indépendantes) que cette commande reflète l'allocation de
  la VM Docker Desktop sur macOS ET la RAM hôte réelle sur Linux
  natif : UNE SEULE commande, valable identiquement sur les deux OS,
  sans détection d'OS manuelle nécessaire.
- Choisit un périmètre de déploiement selon cette mémoire détectée
  (`gateway`+`main` minimal / `gateway`+`main` complet / tous les
  stacks) -- seuils choisis par PRUDENCE à partir de l'observation
  réelle d'un déploiement à 4 Go (pas une science exacte, documenté
  comme tel, ajustable).
- Génère `.env` automatiquement si absent (sans risque sur une
  première installation -- `generate-env.sh` ne demande confirmation
  que si `.env` existe déjà).
- Déploie SANS AUCUNE INVITE INTERACTIVE -- vérifié explicitement que
  les deux garde-fous destructifs existants de ce projet (purge
  Keycloak, placeholder LDAP, `gateway/scripts/run.sh`) sont tous les
  deux gated derrière un état PRÉEXISTANT (volume Keycloak déjà là,
  ou placeholder resté dans un `.env` déjà présent) -- IMPOSSIBLE sur
  un premier déploiement, donc jamais déclenchés ici.

**Bug latent trouvé et corrigé au passage** : `scripts/run-all.sh` ET
`scripts/launcher.sh` utilisaient tous les deux `declare -A` (tableau
associatif) -- fonctionnalité BASH 4+, absente de bash 3.2 (celui
livré par défaut sur macOS, `/bin/bash`, jamais mis à jour par Apple
pour des raisons de licence GPLv3). `#!/usr/bin/env bash` en tête de
ces fichiers résout vers CE bash 3.2 si aucune version plus récente
n'est explicitement avant lui dans le PATH -- jamais signalé avant
cette livraison malgré leur usage à chaque déploiement macOS de ce
projet depuis le début. Corrigés -- remplacés par une fonction de
correspondance (`case`), bash 3.2-compatible, `TARGETS_ORDER`/
`MODULE_ORDER` (tableaux/chaînes déjà simples) restent les seules
listes à maintenir. Recherche systématique confirmant qu'aucun autre
script du projet n'utilise `declare -A`.

**Commentaire obsolète corrigé au passage** :
`scripts/generate-env.sh` affirmait dans son en-tête ne jamais
toucher `LDAP_BIND_PASSWORD` (reste "change-me") -- en réalité le
code (plus bas dans le même fichier) le génère bien, identique à
`LDAP_TEST_ADMIN_PASSWORD` -- vérifié, le COMPORTAMENT réel est
correct, seul le commentaire d'en-tête était resté faux après un
changement ultérieur (ajout de l'annuaire de test, #348) jamais
répercuté dans ce commentaire précis.

`README.md` mis à jour (nouvelle section "Installation rapide" en
tête) et `BACKLOG.md` (nouvel item 55).

Vérifié réellement : syntaxe bash des quatre fichiers touchés,
`install.sh` testé avec un `docker` simulé sur 4 paliers de mémoire
(2/4/8/16 Go -- bons périmètres choisis à chaque fois), cas `.env`
déjà présent (pas de régénération), cas Docker non démarré (échec
propre, bon code de sortie), permissions d'exécution confirmées
préservées à travers un cycle zip/dézip complet. `run-all.sh` et
`launcher.sh` corrigés retestés (4 scénarios chacun -- cible/module
connu, inconnu, `all`/`start all`, usage sans argument) avec des
scripts cibles et `docker compose` simulés -- même comportement
qu'avant correction sur tous les cas. **Non vérifié dans cet
environnement** : exécution contre un vrai Docker (aucun disponible
ici).

## 2026-09-05 — Item 15 du backlog : texte obsolète corrigé (version: 7de8cf5f0ad7, livraison #373)

Poursuite de la revue systématique du backlog pour du texte devenu
obsolète (même motif que les items 8/18/52 déjà corrigés). Trouvé :
l'item 15 (GLPI) affirmait que "la tuile elle-même" restait à faire
-- en réalité `GlpiInventoryView.jsx` existe depuis #231 (résumé
d'inventaire + import multi-sources avec sélection, enrichi en #269),
câblée dans `App.jsx`, jamais mis à jour dans ce texte après coup.
Corrigé -- seule reste réellement ouverte : l'exposition de données
GLPI À L'INTÉRIEUR d'autres tuiles du hub (ex. afficher l'actif GLPI
lié depuis la tuile Tickets), différente de la tuile GLPI dédiée
elle-même qui existe et fonctionne.

## 2026-09-05 — Mode de coloration "activité", backlog item 10 entièrement complété (version: 2aa115669acd, livraison #372)

Second et dernier point resté ouvert de l'item 10 : un mode de
coloration distinct du "taux d'erreur" existant, pour une lecture en
volume d'activité plutôt qu'en sévérité d'incidents.

Construit ENTIÈREMENT côté client (`PixelGridApp.jsx`) -- `total` est
déjà présent sur chaque bucket renvoyé par `/aggregate`/
`/aggregate_range` (aucun changement backend nécessaire). Nouvelle
fonction `activityTier(total, maxTotal)` : échelle RELATIVE au
maximum observé dans la vue courante (`useMemo` sur `buckets`) plutôt
qu'un seuil absolu -- un même total signifie "beaucoup" sur une vue
clairsemée et "peu" sur une vue dense. 4 paliers (`none`/`low`/
`medium`/`high`), palette BLEUE (`color-mix` sur `--color-select`)
volontairement distincte du vert/orange/rouge existant, pour
qu'aucune des deux échelles ne soit jamais confondue avec l'autre.
Bouton "Erreurs / Activité" ajouté à la barre d'outils, affichages de
survol et de détail mis à jour pour refléter le mode actif.

`pixel-grid/README.md` et `BACKLOG.md` (item 10) mis à jour -- item
10 entièrement complété, plus aucun point resté ouvert.

Vérifié réellement : syntaxe (`tsc --jsx`), `activityTier` testée
isolément avec 9 cas (zéro, null, garde division par zéro, paliers,
frontières exactes 0.33/0.66). **Non vérifié dans cet environnement** :
rendu visuel réel (aucun navigateur ici).

## 2026-09-05 — Filtrage utilisateur réel dans pixel-grid, backlog item 10 (version: bf797eb9e22b, livraison #371)

Reprise du backlog sur un point resté "à faire" plusieurs sessions :
la grille pixel-grid ne pouvait montrer qu'UNE personne/équipement à
la fois en cliquant un événement puis en consultant sa timeline
séparée -- jamais un vrai filtre sur la grille principale elle-même.

Backend (`pixel-grid/api/app.py`) : `/aggregate` et
`/aggregate_range` acceptent désormais un paramètre optionnel `nom`,
ajoutant `AND nom = ?` à la clause `WHERE` déjà construite pour
`type`/plage temporelle -- un seul point d'ajout, partagé par les
deux "kind" (`integer_enum`/`continuous`) dans chaque route. Absent =
comportement inchangé.

Frontend (`PixelGridApp.jsx`/`pixelGridApi.js`) : `fetchAggregateRange`
accepte un 5e paramètre `nom` (optionnel, rétrocompatible -- vérifié
qu'aucun autre appel dans le projet n'utilise cette fonction).
Nouveaux états `nomFilter`/`availableNoms` (rechargés à chaque
changement de type via `fetchDevices`, déjà existant, jamais
dupliqué), sélecteur "Filtrer : Tous / nom (N points)..." ajouté à
la barre d'outils -- la grille entière se recolore sur la personne/
l'équipement choisi, sans changer de vue ni perdre le zoom courant.

`pixel-grid/README.md` et `BACKLOG.md` (item 10) mis à jour. Reste
HORS de portée, volontairement : le mode de coloration "activité"
distinct du "taux d'erreur" existant (second point de l'item 10,
jamais construit).

Vérifié réellement : syntaxe (`ast.parse`, `node --check`,
`tsc --jsx`), les deux routes backend testées avec curseur simulé
(avec/sans filtre, bonne clause SQL, bon paramètre), le client
frontend testé avec `fetch` simulé (avec/sans/nom explicitement nul).
**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici).

## 2026-09-05 — Item 8 du backlog : dernière occurrence oubliée de l'erreur "aucune interface" corrigée (version: a12517a1e4ec, livraison #370)

Recherche systématique d'autres occurrences de l'erreur déjà corrigée
en #358 ("aucune interface hub ne consulte l'historique persisté de
memory-api") -- trouvée UNE occurrence oubliée, dans le texte de
l'item 8 du backlog lui-même (distinct de l'item 52, déjà corrigé).
Corrigée dans le même sens : `MemoryView.jsx` consulte bien cet
historique depuis sa création (#259). Une seconde occurrence
candidate (item 37, ligne ~1508 -- "consultation jamais câblée")
vérifiée : correctement formulée au passé, pas une erreur.

## 2026-09-05 — Backlog item 18 : texte obsolète corrigé, ImapView complété (version: 7c0a8ac5a230, livraison #369)

Reprise du backlog après la session de dépannage en conditions
réelles. Vérification systématique de la couverture `/health`+`/logs`
sur les 34 services API du projet -- confirmé complète, aucun cas
manquant trouvé cette fois.

En revue de l'item 18 (indicateur visuel d'action en cours), trouvé
un texte OBSOLÈTE : affirmait qu'imap-client/GLPI/Nebula n'avaient
"pas encore de tuile hub" -- en réalité, les trois ont depuis reçu
leur tuile (`ImapView.jsx`, `GlpiInventoryView.jsx`,
`NebulaView.jsx`, toutes câblées dans `App.jsx`), jamais mis à jour
dans ce texte après coup. Corrigé.

En vérifiant si ces trois tuiles avaient bien des indicateurs
adéquats pour leurs actions à délai variable (l'esprit original de
l'item 18) : `GlpiInventoryView.jsx` et `NebulaView.jsx` en ont déjà
("Chargement…", "Import en cours…"). `ImapView.jsx` avait un gap réel
-- le bouton "Interpréter" restait juste désactivé (`disabled={busy}`)
sans jamais changer de texte pendant l'appel, le `busy` étant partagé
par TOUTES les actions du composant (créer/activer/supprimer une
règle...), jamais assez précis pour distinguer quel message est en
cours d'interprétation. Corrigé : nouveau suivi `interpretingUid`,
texte "Interprétation…" affiché spécifiquement sur le bouton du
message concerné pendant l'appel.

Vérifié réellement : syntaxe (`tsc --jsx`). **Non vérifié dans cet
environnement** : rendu visuel réel (aucun navigateur ici).

## 2026-09-05 — Garde-fou LDAP_URL ajouté à check_ldap_placeholder_and_block (version: 5f3d89e079bf, livraison #368)

Signalé en conditions réelles par la personne : connexion LDAP
échouant avec `UnknownHostException: ldap.example.local`, MALGRÉ
`.env` corrigé et `docker compose down -v` + relance -- l'erreur
persistait à l'identique.

Deux causes distinctes trouvées en creusant `gateway/scripts/run.sh` :

1. **`keycloak_data` est `external: true`** -- `docker compose down
   -v` ne le touche JAMAIS, quel que soit le projet Compose ciblé --
   le realm déjà importé restait donc figé avec l'ancienne URL, quoi
   que `.env` contienne désormais.
2. **`check_ldap_placeholder_and_block()` (existant depuis longtemps)
   ne vérifiait QUE `LDAP_BIND_PASSWORD`, jamais `LDAP_URL`** -- un
   `.env` créé avant l'ajout de l'annuaire de test (#348) garde
   `ldap://ldap.example.local:389` (placeholder d'origine, jamais mis
   à jour puisque `generate-env.sh` demande confirmation avant
   d'écraser un `.env` existant) -- ce garde-fou existant laissait ce
   cas passer inaperçu jusqu'à l'échec de connexion.

**Découverte connexe, importante** : ce projet a DÉJÀ une commande
dédiée et SÛRE pour ce cas exact --
`./gateway/scripts/run.sh reset-keycloak` (confirmation stricte
"RESET", capture des appartenances aux groupes avant purge) -- plus
sûre qu'un `docker volume rm` manuel, qui perdrait cette capture
silencieusement. Pas reconstruite, seulement mise en avant --
existait déjà avant cette livraison.

Corrigé : `check_ldap_placeholder_and_block()` détecte désormais AUSSI
`LDAP_URL=ldap://ldap.example.local`, avec le même mécanisme de
blocage/confirmation que pour le mot de passe -- bénéficie à la fois
à `reset-keycloak` et au prompt automatique de changement de realm
(`check_keycloak_realm_change`), la fonction étant partagée entre les
deux. Limite assumée : ce garde-fou reste spécifique à CETTE valeur
de placeholder précise, pas une détection générique de tout décalage
`.env`/`.env.example` -- documenté comme tel dans `gateway/README.md`.

Vérifié réellement : syntaxe bash, logique testée isolément avec 3
scénarios (mot de passe OK + URL placeholder -- le cas exact de la
personne ; les deux corrects ; mot de passe encore placeholder) --
les 3 se comportent comme attendu. **Non vérifié dans cet
environnement** : confirmation que ce garde-fou, combiné à
`reset-keycloak`, résout effectivement la connexion en conditions
réelles.

## 2026-09-05 — `chantier.sh build --minimal` : déploiement ciblé pour machine à mémoire limitée (version: c4ee5f025c03, livraison #367)

Demandé explicitement, suite directe de #366 (mémoire Docker Desktop
limitée) : "à chaque livraison fais en sorte que je puisse tester
avec le minimum déployé les nouvelles livraisons et ce qui doit être
préservé". Clarifié avec la personne ce qu'elle entend par
"minimum" : le hub ET ses fonctionnalités les plus utilisées
(tickets, tâches, GED) opérationnelles -- pas juste un hub vide qui
charge sans plus.

Nouvelle option `--minimal` sur `./scripts/chantier.sh build` --
déploie SEULEMENT `memcached tickets-postgres hub prefs-api
tickets-api tasks-api ged-api` au lieu des ~20 services du stack
main au complet. Liste construite en vérifiant explicitement les
dépendances RÉELLES de chaque service (aucun des services ci-dessus
sauf `tasks-api` n'a de `depends_on` complet dans
`docker-compose.yml` -- rien n'est automatiquement entraîné par
Docker Compose, chaque dépendance a dû être listée à la main).
Combinable avec un service supplémentaire explicite (`--minimal
relations-api`) -- s'ajoute à la liste minimale, pensé pour tester
la livraison EN COURS sans redéployer tout le stack.

⚠️ `ged-api` répond mais ne stocke/lit aucun document réel sans la
stack `mayan` SÉPARÉE (`MAYAN_BASE=http://mayan-app:8000`) --
`chantier.sh` ne gère que `main` par conception, ne peut donc pas
démarrer `mayan` à sa place -- avertissement affiché explicitement
à l'usage plutôt que silencieux.

**Piège bash 3.2/macOS évité, pas réintroduit** : la combinaison
`MINIMAL_SERVICES` + service supplémentaire optionnel expansait
initialement `"${ARGS[@]}"` sans vérifier `${#ARGS[@]}` au
préalable -- exactement le piège déjà corrigé une fois dans ce même
fichier (#340, tableau vide + `set -u` = "unbound variable" sur bash
3.2). Repéré et corrigé avant de finaliser, testé avec 6 combinaisons
d'arguments isolément (sans Docker) pour confirmer chaque cas.

**Engagement de maintenance ajouté, demandé explicitement** : à
chaque livraison future qui ajoute/modifie un service testable "à la
carte", se demander si `MINIMAL_SERVICES` a besoin d'un ajout, ou a
minima rappeler la commande `--minimal <service>` pour tester cette
livraison précise -- documenté dans `scripts/chantier.sh` (en-tête)
et `README.md`.

Vérifié réellement : syntaxe bash, logique de combinaison des
arguments testée isolément (6 cas : build seul, --all, --minimal
seul, --minimal + service, --minimal + --all, service seul sans
flag). **Non vérifié dans cet environnement** : déploiement réel
contre Docker (aucun Docker disponible ici).

## 2026-09-05 — OOM Keycloak persistant malgré mem_limit : cause racine confirmée, documentation ajoutée (version: 1d3a1972dcb3, livraison #366)

Suite directe de #363 : la personne a signalé que Keycloak continuait
d'être tué par OOM (code de sortie 137) MALGRÉ le `mem_limit: 1536m`
fixé -- diagnostic affiné avec elle en conditions réelles : Docker
Desktop n'avait que 4 Go alloués au total (Mac de 8 Go de RAM
physique). Confirmé : un OOM système (pas seulement cgroup) peut
tuer un conteneur même s'il reste DANS sa propre limite, si la
demande CUMULÉE de tous les conteneurs dépasse ce qui est réellement
alloué à la VM Docker Desktop -- avec les 40+ conteneurs de ce
projet, 4 Go est nettement insuffisant.

**Aucun correctif de code possible ici** -- la cause est
l'allocation mémoire de la machine de la personne, pas un réglage de
ce projet. Documenté dans `README.md` (section démarrage des 4
cibles) : recommandation de démarrer uniquement `gateway` + `main`
plutôt que `all` sur une machine à mémoire limitée (`mayan`/
`vault-standalone` restant optionnels, à démarrer seulement en cas de
besoin spécifique), et d'augmenter l'allocation Docker Desktop si la
RAM physique le permet -- en laissant toujours quelques Go pour
macOS lui-même.

## 2026-09-05 — Onglet Cacti construit, backend prêt depuis longtemps mais jamais relié (version: 69a5ca4c9211, livraisons #362-365)

En vérifiant systématiquement quels services API du projet n'avaient
AUCUN consommateur frontend évident (même démarche que la découverte
OwnCloud côté hub, #354), trouvé : `cacti-api` -- module backend
complet, son propre docstring disant explicitement "pour alimenter
l'onglet Cacti du frontend" -- mais cet onglet n'avait jamais été
construit, dans aucun des deux frontends de ce projet. Confirmé en
listant tous les modules réellement câblés dans
`frontend/src/App.jsx` : "cacti" était le seul absent parmi tous les
bridges MySQL similaires (ipam, optick, tts-gu, zenoss, owncloud sont
tous présents).

Construit : `frontend/src/apps/cactiApi.js` (client, même contrat
`/roots`+`/tree/<id>` que `cacti-api`, arbre COMPLET en un seul appel
contrairement à `owncloud-api`), `CactiApp.jsx` (arbre SIMPLE à
déplier/replier -- choix délibéré, pas de visualisation radiale
complète comme `OptickApp`/`OwncloudApp`, le coût de développement
n'était pas justifié puisque l'API ne demande pas de chargement
paresseux par niveau), `frontend/src/components/CactiJsonPanel.jsx`
(fiche JSON, réutilise les classes CSS `optick-json-*` existantes
plutôt que d'en dupliquer). Réutilise aussi directement les
utilitaires génériques d'`optickLib.js`
(`normalizeText`/`findPathToNode`/`computeRelevantIds`) après
vérification qu'ils ne présument rien de spécifique à Optick.
Onglet ajouté dans `TopNav.jsx`, nouvelle variable
`VITE_CACTI_API_BASE_URL` (`docker-compose.yml`, service `frontend`).

`cacti/README.md` créé -- n'existait pas du tout jusqu'ici,
inhabituel pour ce projet où chaque module a normalement le sien dès
sa création. Documente en particulier l'encodage `order_key` (schéma
Cacti ancien, ~0.8.x, pas de colonne `parent` sur
`graph_tree_items`) et la jointure hôte→graphes (jamais des items
d'arbre séparés). `frontend/README.md` et `BACKLOG.md` (item 54)
mis à jour.

Vérifié réellement : syntaxe de tous les fichiers touchés (`tsc
--jsx`, `node --check`, YAML), `cactiApi.js` testé en profondeur avec
`fetch` simulé (racines, arbre imbriqué avec hôte+graphe enfant
attaché, gestion d'erreur réseau). **Non vérifié dans cet
environnement** : rendu visuel réel (aucun navigateur ici), et
surtout aucune base Cacti réelle disponible pour confirmer
l'algorithme `order_key` au-delà des exports communautaires déjà
cités dans le code d'origine.

## 2026-09-05 — Keycloak tué par OOM, openldap-test "Device or resource busy" (version: eeb384c59cbb, livraisons #363-364)

Deux nouveaux blocages signalés en conditions réelles, corrigés
séparément.

**#363 — Keycloak tué par manque de mémoire (OOM).** Journal du
conteneur `keycloak` : le process Java de l'étape de build
("build-and-exit=true", avant même le démarrage réel) se faisait
tuer -- "Killed", signature Linux d'un OOM killer. Cause : ni
`gateway/docker-compose.yml` ni `vault-standalone/docker-compose.yml`
ne fixaient de limite mémoire de conteneur pour leurs services
Keycloak respectifs. Keycloak (Quarkus, depuis la 24.0) calcule son
tas JVM en POURCENTAGE de la mémoire du conteneur
(`-XX:MaxRAMPercentage=70`) plutôt qu'une valeur absolue -- confirmé
par recherche que sans limite de conteneur, ce pourcentage se
calcule sur la mémoire TOTALE visible (celle de la VM Docker Desktop
entière), et qu'avec les 40+ conteneurs de ce projet tournant
simultanément, la demande cumulée peut dépasser ce qui est
réellement disponible à un instant donné. Corrigé : `mem_limit: 1536m`
ajouté aux deux services Keycloak du projet. Elasticsearch vérifié
par précaution (utilise déjà des valeurs absolues fixes, jamais
affecté par ce risque) -- aucun autre service JVM trouvé dans le
projet. Si l'OOM persiste malgré cette limite, la cause probable est
l'allocation mémoire GLOBALE de Docker Desktop lui-même (à
augmenter côté personne) -- voir `keycloak/README.md` pour le détail
complet et les options si l'augmentation n'est pas possible.

**#364 — `openldap-test` : "Device or resource busy" puis échec
différent au redémarrage.** Signalé juste après le correctif #359
(qui restait nécessaire mais pas suffisant) : "rm: cannot remove
'.../bootstrap/ldif/custom': Device or resource busy". Cause : le
script de démarrage de l'image `osixia/openldap` essaie de SUPPRIMER
ce dossier une fois le bootstrap terminé -- un point de montage ne
peut PAS être supprimé par le conteneur (erreur EBUSY, comportement
du noyau). Confirmé par recherche -- problème CONNU et documenté de
longue date (`osixia/docker-openldap#179`, 2017, journal identique
au nôtre) ; `command: ["--copy-service"]` est le contournement
recommandé par le mainteneur lui-même. Un second journal de la
personne (retentative après le premier échec) montrait un échec
DIFFÉRENT ("tls-enable.ldif: No such file or directory") --
conséquence probable d'un volume laissé dans un état incohérent par
le premier arrêt en plein bootstrap : recommandation ajoutée de
supprimer `openldap_test_data`/`openldap_test_config` si le problème
persiste malgré `--copy-service`. Voir `gateway/README.md`.

Vérifié réellement : validité YAML des deux fichiers
`docker-compose.yml` touchés. **Non vérifié dans cet environnement**
(comme pour tout ce qui touche un vrai Keycloak/OpenLDAP) :
confirmation que ces deux correctifs éliminent effectivement les
échecs observés en conditions réelles.

## 2026-09-05 — Compte de service Keycloak, résout les échecs répétés de keycloak-backup (version: f8e262dfc9ee, livraison #361)

Suite directe de #359 : la personne a elle-même trouvé, en explorant
l'image `keycloak/keycloak:26.0` en local, la commande
`bootstrap-admin service` -- correspond exactement à ce que la
documentation officielle Keycloak recommande pour ce type d'usage
("a temporary admin SERVICE ACCOUNT can be a more suitable
alternative... for automated scenarios"), par opposition à
l'utilisateur de bootstrap actuellement utilisé, documenté
"temporaire" (mécanisme exact jamais confirmé à 100 % en #359).

Avant de basculer, vérifié si d'autres points du projet partageaient
la même fragilité -- trouvé deux de plus, en plus de
`keycloak-backup` : l'import de groupe Keycloak dans `tickets-api`
(`_keycloak_admin_token()`) et `keycloak/group_memberships.py`. Les
trois basculent sur `grant_type=client_credentials` (compte de
service) au lieu de `grant_type=password` (utilisateur de bootstrap).

Nouvelles variables `.env` : `KEYCLOAK_SERVICE_CLIENT_ID` (défaut
`supervision-si-service`) et `KEYCLOAK_SERVICE_CLIENT_SECRET`
(auto-généré par `generate-env.sh`, même mécanisme que les autres
secrets). Bootstrap ajouté EN PLUS de l'utilisateur existant
(`gateway/docker-compose.yml`,
`KC_BOOTSTRAP_ADMIN_CLIENT_ID`/`_CLIENT_SECRET`), jamais à sa place
-- l'utilisateur reste utile pour un premier accès humain à la
console d'admin.

Vérifié réellement : syntaxe de tous les fichiers touchés (YAML,
`sh -n`, `ast.parse`) ; les trois fonctions d'authentification
modifiées testées avec `requests`/`urllib` simulés (bon grant_type,
bons paramètres transmis, `username`/`password` bien absents de la
requête) ; le fragment Python de `generate-env.sh` testé isolément
avec des arguments réels (décalage d'index vérifié après ajout d'un
11e argument) ; recherche systématique confirmant qu'aucun autre
`grant_type=password` vers Keycloak ne subsiste dans le projet.
**Non vérifié dans cet environnement** : confirmation que ce
changement élimine effectivement les échecs observés en conditions
réelles -- fondé sur la recommandation officielle Keycloak plutôt
que sur une cause confirmée à 100 %, comme documenté dans
`keycloak/README.md`.

## 2026-09-05 — Correction de méthode (suite) : ssh-tunnels/keys/mounts README.md aussi exclus à tort du hash (version: d73ba344cd25, livraison #360)

**Aucun fichier livrable changé dans cette entrée** -- pure
correction de méthode, dans la continuité directe de #359. En
vérifiant si d'autres dossiers du projet avaient le même risque
(mélange code source committé + artefacts d'exécution, `.gitignore`
comme référence), trouvé : `ssh-tunnels/keys/` et
`ssh-tunnels/mounts/` contiennent chacun un `README.md` RÉELLEMENT
committé (`.gitignore` les préserve déjà explicitement via
`!ssh-tunnels/keys/README.md`/`!ssh-tunnels/mounts/README.md`) --
mais mon propre calcul de hash pruneait ces DEUX dossiers en BLOC,
exactement la même erreur que celle de #359 pour `keycloak/backup/`.
Confirmé un impact RÉEL, pas seulement théorique :
`ssh-tunnels/mounts/README.md` a été ajouté dans une livraison
passée (le CHANGELOG le mentionne) -- son hash de l'époque ne
reflétait donc déjà pas cet ajout.

Autres dossiers audités par précaution (`pki/ca`, `pki/server`,
`tls-proxy/generated`, `apache/generated`, `keycloak/import`,
`prefs-api/log-files`) -- confirmé vides de tout code source commis
(aucun `Dockerfile`/script n'y est jamais copié par un build Docker,
vérifié par recherche systématique) ou jamais exclus dans mon
calcul en premier lieu (`prefs-api/log-files`) -- aucun autre cas
similaire trouvé.

Motif corrigé : au lieu de pruneer `ssh-tunnels/keys`/
`ssh-tunnels/mounts` en bloc, exclusion précise de tout fichier sous
ces chemins SAUF `README.md` -- même logique que `.gitignore`,
appliquée cette fois à mon propre calcul.

## 2026-09-05 — openldap-test :ro corrigé, diagnostic keycloak-backup amélioré (version: c873fe2ffa44, livraison #359)

Signalé en conditions réelles par la personne (journaux complets du
stack) : deux problèmes distincts.

**`openldap-test` ne démarrait jamais** -- "chown: changing ownership
of '.../bootstrap/ldif/custom': Read-only file system",
"/container/run/startup/slapd failed with status 1". Cause : le
montage du LDIF de test (`gateway/docker-compose.yml`) était marqué
`:ro`, ajouté par précaution lors de sa création (#348) pour protéger
le fichier source d'une écriture accidentelle -- empêchait en réalité
l'image `osixia/openldap` d'ajuster la propriété (`chown`) de ce
volume à CHAQUE démarrage, comme elle le fait pour tous ses volumes
montés. Retiré -- annuaire de TEST mono-utilisateur, sans enjeu de
sécurité réel ici.

**`keycloak-backup` échoue à chaque cycle après un premier succès** --
diagnostic AMÉLIORÉ, cause pas encore confirmée. La toute première
sauvegarde réussit juste après l'import du realm, puis échoue à
CHAQUE cycle suivant (~30 min), sur la MÊME instance Keycloak sans
redémarrage entre les deux -- écarte l'hypothèse d'un `.env`
régénéré entre deux imports. Piste sérieuse mais PAS confirmée :
Keycloak documente son compte admin de bootstrap comme "temporaire",
mais la recherche menée donne des signaux contradictoires sur le
mécanisme exact (aucune expiration automatique documentée après un
seul usage ; une discussion GitHub du projet confirme qu'une
extension prévue pour ça a été abandonnée) -- jamais présumé de
conclusion sans confirmation. Corrigé en attendant : `backup-loop.sh`
capture désormais la VRAIE réponse OAuth de Keycloak
(`error`/`error_description`) au lieu du message générique précédent
-- devrait révéler la cause exacte au prochain échec. Voir
`keycloak/README.md` pour le détail complet et la piste de fond
envisagée (compte de service plutôt qu'utilisateur temporaire,
recommandation officielle Keycloak pour ce type d'usage -- pas
construite avant confirmation de la vraie cause).

**Correction de méthode, distincte des deux points ci-dessus** : le
calcul de hash de version utilisé pour CETTE livraison (et
vraisemblablement les précédentes) excluait `keycloak/backup/` en
BLOC -- exactement la même erreur qu'un `.gitignore` déjà corrigé une
fois pour cette même raison (voir `.gitignore`, correctif du
2026-09-04) : `keycloak/backup/` contient du VRAI code source
(`Dockerfile`, `backup-loop.sh`), pas seulement l'artefact de
sauvegarde écrit à l'exécution. Corrigé pour ne plus exclure QUE
`keycloak/backup/*.json` (motif déjà correct côté `.gitignore`,
jamais reproduit côté calcul de hash jusqu'ici) -- les livraisons
antérieures qui auraient touché `backup-loop.sh` (aucune trouvée en
relisant CHANGELOG.md) auraient eu un hash ne reflétant pas ce
changement précis.

## 2026-09-05 — Correction d'une erreur de ma part : l'interface de consultation des archives existait déjà (version: f6699339de83, livraison #358)

**Erreur reconnue.** En reprenant le backlog pour chercher un point
déjà scopé à traiter, relecture complète de `MemoryView.jsx` avant de
conclure quoi que ce soit cette fois (plutôt qu'une supposition) --
révèle que cette vue appelle DÉJÀ `fetchStats`/`fetchServices`/
`fetchEntries` (`hub/src/memoryClient.js`) sur exactement `/stats`/
`/services`/`/entries` (`memory-api`), avec filtres service/niveau et
affichage tabulaire des statistiques ET de l'historique -- livré
depuis la création même de cette tuile (livraison #259).

Ceci contredit directement une affirmation faite dans les livraisons
#352/#353 ("aucune interface hub ne consulte l'historique persisté
de memory-api") et l'item 52 du backlog créé sur cette base -- erreur
venue d'avoir vérifié UNIQUEMENT `LogsManagerView.jsx` (qui, lui,
n'interroge effectivement que le tampon Memcached en direct) sans
vérifier `MemoryView.jsx`, la tuile pourtant explicitement dédiée à
ce sujet.

**Aucun code changé** -- rien à construire, l'interface fonctionne
déjà. Corrigé uniquement la documentation qui répétait cette erreur :
`BACKLOG.md` (item 52, réécrit pour expliquer la correction plutôt
que supprimé -- numérotation jamais réutilisée dans ce projet),
`hub/README.md`, `memory/README.md`.

**Leçon retenue** : avant d'affirmer qu'une fonctionnalité "n'existe
pas encore", vérifier TOUS les composants raisonnablement candidats
(ici, `MemoryView.jsx` était nommément le bon endroit "déjà
conceptuellement" d'après mon propre item 52 -- et pourtant jamais
ouvert pour vérifier avant d'écrire cette affirmation).

## 2026-09-05 — vault-standalone : repli HOST_IP corrigé, "localhost" invalide comme adresse de liaison (version: f598779ce763, livraison #357)

Signalé en conditions réelles par la personne : `vault-standalone/
scripts/run.sh up -d --build` progressait jusqu'au rendu complet
(realm isolé, CA, certificat serveur, config nginx) puis échouait
avec "invalid IP address: localhost".

Cause : `VAULT_STANDALONE_HOST_IP` non définie retombe (dans le
script) sur la chaîne littérale `"localhost"` -- correcte pour
construire des URLs (`KC_HOSTNAME`, `VITE_*_URL`), mais CETTE MÊME
variable sert AUSSI d'adresse de LIAISON de port Docker
(`vault-standalone/docker-compose.yml`, service `keycloak-standalone` :
`"${VAULT_STANDALONE_HOST_IP:-127.0.0.1}:...:8080"`) -- Docker exige
une VRAIE adresse IP pour cet usage précis (ou `0.0.0.0`), jamais un
nom d'hôte. `docker-compose.yml` avait déjà son PROPRE repli correct
(`127.0.0.1`), mais jamais utilisé : le script exporte la variable
AVANT l'appel à `docker compose`, ce qui prend toujours le dessus sur
le repli `:-` de docker-compose.yml.

Corrigé : repli du script changé de `"localhost"` à `"127.0.0.1"` --
valide pour les DEUX usages de cette même variable (liaison de port
ET composant d'URL), jamais besoin de les distinguer.

Vérifié réellement : recherche systématique de tout AUTRE usage de
`HOST_IP`/`VAULT_STANDALONE_HOST_IP` comme adresse de liaison de port
dans les trois `docker-compose.yml` du projet (principal, gateway,
vault-standalone) -- un seul cas trouvé (celui corrigé ici), toutes
les autres occurrences construisent des URLs, jamais affectées par ce
piège précis.

## 2026-09-05 — Bouton "🔗 Relations" intégré à GED et Tâches (version: 3c437b91bb23, livraison #356)

Reprise du backlog sur les fonctionnalités. Plutôt qu'un nouveau
chantier spéculatif, recherche d'un point déjà scopé et documenté --
trouvé dans `relations/README.md` ("reste GED (`GedView.jsx`) et
Tâches (`KanbanView.jsx`), pas encore intégrées") : le bouton "🔗
Relations" (livré pour Calendrier en #339) manquait sur les deux
autres vues de la super tuile ENT.

`KanbanView.jsx` et `GedView.jsx` acceptent désormais une prop
`onViewRelations` optionnelle (même motif défensif que
`CalendarView.jsx` -- rendu conditionnel, jamais un plantage si la
prop est absente), câblée à la fonction `viewRelations` déjà
existante dans `EntView.jsx` (bascule vers l'onglet Relations +
pré-remplit la cible). Types d'entité utilisés : `"task"` et
`"document"`, correspondant à `KNOWN_ENTITY_TYPES` (relations-api),
vérifié ne pas avoir dérivé (liste délibérément scopée à 4 types,
déjà documentée comme telle -- pas un bug, contrairement à d'autres
listes trouvées en #351-352).

L'appel autonome de `GedView` (tuile GED seule, hors ENT,
`App.jsx`) ne passe volontairement PAS cette prop -- pas d'onglet
Relations vers lequel basculer en dehors du contexte ENT, le bouton
n'apparaît alors simplement pas (comportement défensif déjà en
place).

Vérifié réellement : syntaxe des trois fichiers touchés (`tsc
--jsx`). **Non vérifié dans cet environnement** : rendu visuel réel
(aucun navigateur ici).

relations/README.md mis à jour ("reste à faire" réduit au graphe
visuel/navigation entre deux entités déjà liées, seul point restant).

## 2026-09-05 — Séparation GED interne/externe + chemins trop longs + correctif macOS ssh-tunnels (version: 1a3daffdfd88, livraisons #354-355)

Deux volets distincts, dans la continuité de la même conversation.

**#354 — Sous-onglets OwnCloud/Recherche dans la tuile GED.** Demandé
explicitement : "vérifie bien que la tuile ged donne un accès séparé
visuellement d'un coté à la ged externe et au dépôt interne, car par
la ged externe on ne doit pas toucher aux fichiers internes... ajoute
une recherche toutes sources et viens greffer l'elasticsearch...
parcourir les index d'elasticsearch et accéder aux données sources".

Constat : OwnCloud n'avait AUCUNE interface dans le hub (uniquement
dans "Supervision SI", `frontend/` -- bien plus riche, arbre radial/
chronologie de versions, jamais dupliqué ici, juste référencé par un
lien puisqu'aucun lien profond n'est possible, son routage interne
étant un simple état React). `GedView.jsx` gagne 2 sous-onglets
("☁️ OwnCloud", "🔍 Recherche") en plus de "📁 Dépôt interne" (inchangé)
-- séparation VISUELLE appuyée (bordure orange, bannière permanente
"lecture seule -- dépôt EXTERNE"), jamais une simple différence de
libellé. Nouveaux fichiers : `hub/src/ownCloudClient.js`,
`OwnCloudTreeView.jsx` (navigation fil d'ariane sur `/roots`+
`/children`, déjà existants côté backend), `OwnCloudSearchView.jsx`
(recherche structurée sur `owncloud-search-api`, déjà construit et
testé depuis longtemps mais jamais relié à une interface -- champs
proposés depuis le vrai mapping Elasticsearch, jamais supposés en
dur -- affichage des données sources brutes de chaque résultat).

Puis, en cours de discussion, priorité signalée par la personne :
"erreur de synchronisation des drives (ça c'est la priorité)...
identifier les chemins trop longs pour windows ou autres". Nouvelle
route `GET /long-paths?threshold=260&limit=200` (owncloud-api) --
seul point du sujet synchronisation actionnable SANS nouvel accès
(métadonnées déjà lues en lecture seule). ⚠️ Requête COÛTEUSE (`WHERE
LENGTH(path) > ...` sans index exploitable sur ~2,5M lignes) --
nouveau cache dédié `OWNCLOUD_LONG_PATH_CACHE_TTL` (900s par défaut),
déclenchement manuel uniquement, jamais automatique.

**Reste PAS COMMENCÉ, À CLARIFIER** (voir BACKLOG.md item 53) : le
reste du sujet synchronisation (erreurs probablement LOCALES à
chaque poste client sur ownCloud/Nextcloud, jamais remontées au
serveur par défaut -- à confirmer côté personne) et l'agent de
supervision de l'hôte ownCloud (rejoint les items 44/45 déjà notés
"à clarifier"). Proposition de compte admin lecture seule écartée par
la personne pour l'instant.

**#355 — Correctif macOS : `ssh-tunnels-api` ne démarrait plus.**
Signalé en conditions réelles par la personne : `docker compose up`
échouait sur "path .../ssh-tunnels/mounts is mounted on
/host_mnt/Users but it is not a shared mount". Cause : `bind:
propagation: rshared` (déjà marqué "non vérifié... à confirmer au
premier vrai montage" dans le code d'origine) -- confirmé par
recherche être une limitation CONNUE et ANCIENNE de Docker Desktop
(`moby/moby#39093`, 2019) : contrairement à Linux natif, où `mount
--make-rshared` sur l'hôte résout le problème, plusieurs retours
concordants confirment que ça ne fonctionne PAS de façon fiable sur
Docker Desktop pour Mac/Windows -- limitation de fond de sa
virtualisation, pas un réglage à ajuster.

Corrigé : propagation RETIRÉE par défaut -- le conteneur démarre
désormais partout. Compromis assumé et documenté : un montage SSHFS
fait DANS le conteneur n'est plus visible depuis l'explorateur de
fichiers de l'hôte (reste consultable depuis l'intérieur du
conteneur) -- la gestion des tunnels/montages via l'API n'est PAS
affectée. Un hôte Linux NATIF qui veut retrouver ce comportement
peut réintroduire le bloc `bind: propagation: rshared` -- voir le
commentaire dans `docker-compose.yml`. Recherche systématique
confirmant qu'aucun autre volume de ce projet n'utilise ce réglage.

Vérifié réellement : syntaxe de tous les fichiers touchés (`tsc
--jsx`, `ast.parse`, YAML), `ownCloudClient.js` testé en profondeur
avec `fetch` simulé (dont gestion d'erreur réseau), route
`/long-paths` testée de bout en bout (paramètres par défaut/
explicites, plafond, erreur de validation) ainsi que `fetch_long_paths`
directement (SQL généré, garde-fou SELECT-only). **Non vérifié dans
cet environnement** : rendu visuel réel (aucun navigateur, ni accès à
une vraie instance OwnCloud/Elasticsearch/SSHFS).

owncloud/README.md, ssh-tunnels/README.md, hub/README.md,
BACKLOG.md (items 44, 53) et .env.example mis à jour.

## 2026-09-05 — Fusion des deux systèmes d'archivage de logs (version: 01ad51bf062d, livraison #353)

Demandé explicitement par la personne suite à la découverte
documentée en #351-352 : `prefs-api/log_archiver.py` (livraison #198,
antérieur) et `memory-api` (livraison #259, plus complet --
repopulation, statistiques, garbage collector) archivaient tous les
deux le même tampon Memcached, en parallèle, chacun avec sa propre
liste de services à sa propre dérive.

**`log_archiver.py` SUPPRIMÉ** -- fichier retiré, route
`/persisted-logs` retirée de `prefs-api/app.py`, appel de schéma au
démarrage retiré, thread d'archivage retiré. `memory-api` reste
désormais la SEULE source d'archivage persistant pour ce projet.

**Un seul écart de fonctionnalité trouvé et comblé AVANT suppression** :
`log_archiver.query_persisted_logs` filtrait `since`/`until`
(timestamps Unix) sur la colonne `timestamp` -- l'horodatage RÉEL du
log. `memory-api` ne filtrait que sur `since_iso` (chaîne ISO), sur
`collected_at` -- quand CE service avait archivé l'entrée, sémantique
DIFFÉRENTE, pas un simple format différent. Redessiné :
`list_entries`/`compute_stats_by_service` (`memory/api/store.py`)
acceptent désormais `since`/`until` (timestamps Unix, filtrant
`entry_timestamp`, colonne déjà indexée) -- reprend exactement la
sémantique de l'ancien système. Changement sûr : `since_iso` n'était
consommé par aucune interface avant cette fusion (vérifié en
cherchant dans tout le hub avant de toucher à cette signature).

**Bug de build trouvé et corrigé en cours de route** : le `Dockerfile`
de prefs-api contenait `COPY prefs-api/log_archiver.py .` -- aurait
cassé le build (fichier introuvable) sans ce nettoyage.

Vérifié réellement : `list_entries`/`compute_stats_by_service`
retestés en profondeur après refonte (since seul, until seul, fenêtre
combinée, filtre service+since, stats since, sans filtre -- 6 cas),
routes HTTP `/entries`/`/stats` retestées avec les nouveaux
paramètres. `prefs-api` retesté après suppression complète :
`/logs` (tampon partagé, jamais touché) toujours fonctionnel,
`/persisted-logs` correctement absent (404), `/push-log` non affecté.

**Reste explicitement HORS de portée de cette fusion** : aucune
interface hub ne consulte encore l'historique persisté de
`memory-api` (`LogsManagerView.jsx` n'interroge que le tampon
Memcached en direct) -- la fusion élimine la redondance backend, ne
construit pas la vue manquante. Sujet distinct, à reprendre
séparément si utile.

memory/README.md, hub/README.md et BACKLOG.md (item 8) mis à jour.

## 2026-09-05 — LOG_SERVICES (hub) complété, deux systèmes d'archivage parallèles découverts (version: 31cd9745a56a, livraison #352)

Suite directe de #351 (couverture `memory-api`). En reprenant le même
recoupement systématique, trouvé que `hub/src/logsLib.js`
(`LOG_SERVICES`, la liste qui pilote ce que le gestionnaire de logs
du hub AFFICHE réellement, pas seulement l'archivage backend) avait
la MÊME dérive -- 12 services invisibles dans cette vue depuis leur
création respective (architecture, classifier, memory, netprobe,
network-agent, relations, retro, rights, snmp, tasks, vigilance,
backup-restore), aucune ligne d'erreur remontée nulle part pour eux.
Corrigé (34 entrées, ordre alphabétique par libellé préservé) --
`pixel-grid-bridge`/`vault-admin-api` volontairement EXCLUS de cette
liste précise (aucune route HTTP atteignable pour eux depuis le
navigateur).

**Découverte connexe plus large** : ce même recoupement a révélé
`prefs-api/log_archiver.py` (livraison #198), un système d'archivage
persistant ANTÉRIEUR à `memory-api` (#259), toujours actif en
parallèle -- même tampon Memcached source, même finalité, mais deux
implémentations séparées avec chacune sa propre liste de services
(également corrigée ici, `KNOWN_LOG_SERVICES`, 36/36 confirmé --
celle-ci inclut `pixel-grid-bridge`/`vault-admin-api`, lecture directe
de Memcached plutôt que HTTP). Plus significatif encore : **aucun des
deux systèmes n'est actuellement consulté par une interface** --
`LogsManagerView.jsx` n'interroge que le tampon Memcached en direct,
jamais `/persisted-logs` (prefs-api) ni les routes historiques de
`memory-api`. Documenté dans `hub/README.md` et `BACKLOG.md` (item 8)
sans trancher unilatéralement -- sujet à reprendre avec la personne.

Vérifié réellement : syntaxe Python (`ast.parse`) et JavaScript
(`node --check`) des deux fichiers modifiés, recoupement final
confirmant `KNOWN_LOG_SERVICES` à 36/36 et `LOG_SERVICES` (hub) à 34
entrées sans doublon.

## 2026-09-05 — memory-api : couverture complétée à 36/36 services (version: 5b44b7194242, livraison #351)

Reprise du backlog item 8 ("archiver TOUS les logs, en dehors des
conteneurs Docker") -- déjà LIVRÉ en #259 (`memory-api`) mais jamais
marqué comme tel dans BACKLOG.md, même schéma de dérive documentation/
code déjà rencontré plusieurs fois dans ce projet.

Recoupement systématique (script Python, pas un comptage visuel)
entre les services réels de `docker-compose.yml` et
`KNOWN_SERVICE_NAMES` (memory-api) : 8 services sur 36 n'étaient
jamais archivés, ajoutés au projet après #259.

**3 étaient déjà correctement câblés au tampon partagé, juste absents
de la liste** : classifier-api, vigilance-api, tasks-api -- ajout
simple.

**4 nécessitaient le câblage complet** (aucune intégration au tampon
partagé, certains comme rights-api n'avaient même aucun logging du
tout) : rights-api, netprobe-api, relations-api, vault-admin-api --
même motif que classifier-api reproduit sur chacun (handler attaché
au logger racine, route `/logs`), testé individuellement.

**1 cas différent** : `pixel-grid-bridge`, script en arrière-plan
(pas un service Flask, pas de route HTTP) -- handler seul, sans
route `/logs` (memory-api lit directement Memcached). Découverte en
cours de route : son `docker-compose.yml` pointait vers un contexte
de build LOCAL (`./pixel-grid/bridge`), jamais d'accès à `shared/` --
corrigé (contexte racine + `dockerfile:` explicite, même motif que
les services récents), `pymemcache` ajouté à ses dépendances,
`Dockerfile` mis à jour en conséquence (chemins COPY corrigés pour le
nouveau contexte -- erreur trouvée et corrigée avant la vérification
finale, aurait cassé le build réel).

Vérifié réellement : syntaxe de tous les fichiers Python touchés,
YAML de docker-compose.yml, chaque route `/logs` testée
individuellement (clients de test Flask), `pixel-grid-bridge` testé
par import direct (handler correctement attaché au logger racine
avec le stub pymemcache, dégradation gracieuse confirmée sans lui).
Recoupement final : 36 services applicatifs, 36 dans
`KNOWN_SERVICE_NAMES`, aucun manquant.

BACKLOG.md (item 8) et memory/README.md mis à jour.

## 2026-09-05 — nebula-api : route online-status exposée, backlog item 49 avancé (version: a57944c28317, livraison #350)

Reprise du backlog sur les fonctionnalités (la personne a mis de
côté la mire/l'habillage pour l'instant). Items 40-45 explicitement
marqués "à cadrer avant tout code" dans le backlog lui-même -- item
46 (skin) mis en pause à la demande de la personne. Item 49 identifié
comme le point d'entrée le plus direct de la chaîne WiFi/réseau
(47-51) -- "l'étape la moins coûteuse... à vérifier en premier".

Vérification avant tout nouveau code : `nebula_client.get_online_status`
existait DÉJÀ depuis #196 ([{"devId", "currentStatus"}, ...], répond
directement à "les bornes plantent-elles réellement ?") mais n'était
JAMAIS exposée via une route HTTP. Ajoutée : `GET /sites/<siteId>/
online-status?type=AP`, même style que les routes existantes de ce
module, filtrage par type CÔTÉ SERVEUR (l'API Nebula le supporte
nativement, contrairement à `/devices` qui filtre côté client faute
d'endpoint dédié).

Nombre de clients connectés : déjà couvert par `/sites/<siteId>/
clients` (existant, #196) -- se dérive de la longueur de la liste,
aucune nouvelle route nécessaire. "Charge" par borne : PAS couverte,
aucun champ de ce type trouvé dans la spécification OpenAPI
consultée -- à confirmer une fois un accès réel obtenu, jamais
présumé qu'un tel champ existe.

Rappel honnête, déjà documenté dans ce module mais qui mérite d'être
répété : ce qui reste RÉELLEMENT hors de portée n'est pas du code --
licence Nebula Pro Pack + clé API non self-service (support Zyxel)
restent des prérequis administratifs, sans lien avec le travail
effectué ici.

Vérifié réellement : nouvelle route testée de bout en bout (client
Nebula simulé) -- transmission correcte de site_id/type, erreur
claire (502, mentionnant le prérequis Pro Pack) si NEBULA_API_KEY
absent.

nebula/README.md et BACKLOG.md mis à jour.

## 2026-09-05 — BACKLOG.md : item 46 (skin Keycloak) confirmé livré à 3/4 points (version: 169ee63db161, livraison #349)

Reprise du backlog suite au déploiement réussi de la personne.
Vérification avant de coder quoi que ce soit sur l'item 46 (skin
Keycloak) -- items 40-45 explicitement marqués "à cadrer avant tout
code" dans le backlog lui-même, jamais présumés.

Relecture directe de keycloak/themes/hub(-dark)/login/resources/css/
login.css : 3 des 4 points d'origine étaient déjà entièrement livrés
(mise en page #296, centrage/réduction des champs #281/#296/#300,
menu déroulant langue avec une VRAIE investigation en #296 -- le
gabarit officiel Keycloak confirmé contre le dépôt keycloak/keycloak
n'a jamais eu de classe .pf-m-expanded, la supposition de #281 était
fausse, l'état ouvert/fermé est porté par l'attribut ARIA standard
aria-expanded) -- le backlog n'avait simplement jamais été mis à jour
après ces livraisons, même schéma déjà rencontré plusieurs fois dans
ce projet (badge mots-clés #333, file d'attente #333...).

Seul le bouton de bascule jour/nuit EN PAGE reste réellement "pas
commencé" -- nécessiterait du JavaScript nouveau et probablement une
modification du gabarit template.ftl lui-même (jamais fait jusqu'ici
dans ces thèmes, convention CSS-seule respectée partout). Question
explicitement laissée ouverte dans le backlog, jamais tranchée :
bascule automatique (media query CSS prefers-color-scheme, aucun
JS requis) ou manuelle (bouton réel) ? Combien de skins au total ?
-- posée à la personne plutôt que présumée.

BACKLOG.md mis à jour, item 46 condensé en conséquence.

## 2026-09-05 — Annuaire LDAP de test pour un package autonome complet (version: 9b057d24cb9d, livraison #348)

Demandé explicitement par la personne, en plein test de déploiement :
"as tu prévu des données ldap ou un bouchon ldap ?". Vérifié : aucun
bouchon LDAP n'existait, et Keycloak n'a AUCUN utilisateur local
humain défini dans son realm (uniquement un compte de service
technique) -- sans LDAP fonctionnel, aucune connexion possible au hub
du tout, ni fédération Keycloak ni ldap-admin-api n'ayant quoi que ce
soit à consulter.

Nouveau service `openldap-test` (image osixia/openldap, standard)
ajouté à gateway/docker-compose.yml, démarrant avec `gateway` --
amorcé automatiquement au tout premier lancement (LDIF, jamais
réimporté aux démarrages suivants même si le fichier change,
comportement de l'image) avec 3 comptes de test
(gateway/ldap-seed/bootstrap.ldif) : alice/bob/admin_test, même mot
de passe "password" pour tous -- clairement des données de TEST,
jamais un usage réel.

.env.example mis à jour : LDAP_URL/BIND_DN/USERS_DN/ROLES_DN/
ADMIN_BIND_DN/ADMIN_BASE_DN pointent désormais par défaut vers ce
nouvel annuaire local plutôt qu'un hôte fictif (ldap.example.local).
Nouvelle variable LDAP_TEST_ADMIN_PASSWORD (mot de passe du compte
cn=admin, utilisé à la fois pour la fédération Keycloak en lecture
seule ET comme mot de passe de liaison pour ldap-admin en écriture --
jamais stocké côté serveur pour ce module, la personne le saisit à
chaque accès).

scripts/generate-env.sh génère désormais ce mot de passe aléatoirement
(synchronisé entre LDAP_BIND_PASSWORD et LDAP_TEST_ADMIN_PASSWORD,
même compte), l'ajoute à .env.generated-secrets.txt avec les
identifiants des 3 comptes de test, et corrige le message final (LDAP
n'apparaît plus dans la liste des modules "non configurés").

Vérifié réellement : YAML valide (gateway/docker-compose.yml), flux
complet de generate-env.sh retesté de bout en bout -- confirmé que
LDAP_BIND_PASSWORD et LDAP_TEST_ADMIN_PASSWORD reçoivent bien la
MÊME valeur générée, toutes les URLs/DN résolues correctement, résumé
des secrets généré affiche bien les 3 comptes de test ET le mot de
passe de liaison admin. Docker non disponible dans cet environnement
de développement pour un test direct du conteneur lui-même (image,
amorçage LDIF) -- configuration vérifiée par relecture attentive
plutôt que testée en conditions réelles.

gateway/README.md et README.md mis à jour (identifiants de connexion
documentés, section "reste non configuré" corrigée).

## 2026-09-05 — gateway : création automatique du volume Keycloak au premier déploiement (version: b3740c3a7940, livraison #347)

Signalé par la personne : `./scripts/run-all.sh all up -d --build`
progressait jusqu'à la construction des images (réussie) puis
échouait avec "external volume 'supervision-si_keycloak_data' not
found".

Diagnostic : `gateway/docker-compose.yml` référence ce volume en
`external: true` -- pensé pour une MIGRATION depuis l'architecture
pré-#135 (le volume existait déjà, créé par l'ancien stack principal
avant la séparation gateway/main). Pour un tout PREMIER déploiement
(jamais de stack principal lancé avant), ce volume n'a jamais existé
-- `external: true` exige qu'il existe déjà, Docker Compose ne le
crée JAMAIS lui-même dans ce cas.

Trouvaille en creusant : gateway/README.md documentait DÉJÀ ce
scénario exact, avec un contournement manuel identique à ce qui est
maintenant automatisé (`docker volume create
supervision-si_keycloak_data`) -- resté une étape manuelle à ne pas
oublier plutôt qu'automatisé, jusqu'à cette livraison.

Corrigé : `gateway/scripts/run.sh` crée désormais ce volume de façon
IDEMPOTENTE (même motif déjà en place pour le réseau Docker partagé
juste au-dessus dans ce même script) avant tout appel à `docker
compose` -- couvre les deux cas (premier déploiement neuf, ou
migration où le volume existe déjà) sans distinction explicite
nécessaire, `docker volume create` ne faisant rien si le volume
existe déjà.

Vérifié réellement : résolution de `KEYCLOAK_DATA_VOLUME_NAME`
confirmée identique entre le `.env` généré et le repli du
docker-compose (les deux résolvent à `supervision-si_keycloak_data`).
Docker non disponible dans cet environnement de développement pour
un test direct de `docker volume create` -- comportement idempotent
confirmé par la documentation Docker établie plutôt que testé
directement ici, même motif déjà en confiance pour `docker network
create` dans ce projet. gateway/README.md mis à jour (le
contournement manuel documenté n'est plus nécessaire).

## 2026-09-05 — Vérification précoce de .env dans les trois run.sh (version: b586d0bfbe8a, livraison #346)

Signalé par la personne : `./scripts/run-all.sh all up -d --build`
progressait loin (CA, certificat serveur, config nginx tous générés
avec succès) puis échouait tout à la fin avec un message Docker cru
et peu clair -- "couldn't find env file:
~/supervision-si/.env".

Diagnostic : `.env` n'est JAMAIS inclus dans une livraison (secret,
exclu par `.gitignore` du zip) -- chaque nouvelle extraction d'archive
nécessite de relancer `scripts/generate-env.sh` avant tout démarrage.
Sans lui, `get_env()` (keycloak/render.py) retombe silencieusement sur
ses valeurs par défaut codées en dur partout où `.env` est absent --
d'où les avertissements "LDAP_BIND_PASSWORD/PREFS_API_SERVICE_SECRET
vaut encore change-me" qui semblaient indiquer un .env mal généré,
alors qu'en réalité AUCUN .env n'existait du tout à ce stade. Le
script continuait alors à rendre realm/PKI/nginx avec ces valeurs de
repli, jusqu'à ce que `docker compose --env-file .env` échoue
finalement, LOIN du symptôme réel et sans message clair.

Corrigé : vérification EXPLICITE de l'existence de `.env` ajoutée en
tête des trois scripts qui en dépendent (`scripts/run.sh`,
`gateway/scripts/run.sh`, `mayan/scripts/run.sh`) -- échoue
IMMÉDIATEMENT avec un message actionnable ("./scripts/generate-env.sh"
à lancer) plutôt que de limper jusqu'à un échec Docker tardif et
confus.

Vérifié réellement : les trois scripts testés SANS .env -- échec
immédiat confirmé (code de sortie 1, message clair, avant tout autre
traitement) ; puis retestés AVEC un .env généré -- aucune régression,
progression normale jusqu'au point habituel (docker absent de cet
environnement de développement, sans rapport avec ce correctif).

## 2026-09-05 — pki/scripts/generate-server-cert.sh : piège macOS LibreSSL corrigé (version: 818d5ae5be03, livraison #345)

Signalé par la personne : `./scripts/run-all.sh all up -d --build`
bloqué après la génération RÉUSSIE du certificat serveur (CA générée,
CSR signé, certificat écrit sur disque) -- la toute dernière ligne du
script, purement informative (`openssl x509 ... -dates -ext
subjectAltName`), échouait avec "unknown option -ext". Cause : macOS
fournit LibreSSL comme binaire système `openssl` par défaut
(contrairement à Linux, où c'est réellement OpenSSL) -- LibreSSL ne
supporte pas le flag `-ext` sur `x509`.

Corrigé : retiré `-ext subjectAltName` de cette ligne d'affichage
finale (l'information SAN était de toute façon DÉJÀ affichée plus tôt
via la variable shell `$SAN_LIST`, la source de vérité réelle
puisque c'est exactement ce qui a été demandé à openssl -- jamais une
relecture du certificat généré). Gardé uniquement `-dates` (portable
partout) pour afficher la fenêtre de validité du certificat serveur.
Ajouté `|| true` par précaution -- cette ligne reste purement
informative, ne doit plus jamais pouvoir arrêter le déploiement.

Vérifié réellement : chaîne complète (génération CA + certificat
serveur) rejouée de bout en bout dans un répertoire isolé avec un
vrai OpenSSL -- confirmé que le script va désormais jusqu'au bout
(code de sortie 0), dates affichées correctement. Recherche
systématique de tout autre usage d'openssl dans le projet -- aucun
autre flag potentiellement incompatible LibreSSL trouvé
(`generate-ca.sh` n'utilise que des options universellement
supportées, déjà confirmé par sa propre réussite dans le journal de
la personne avant ce point de blocage).

## 2026-09-05 — keycloak/realm-template.json : description du rôle admin_hub raccourcie (version: cb4e908a730c, livraison #344)

Signalé par la personne : `./scripts/run-all.sh all up -d --build`
bloqué par une vérification déjà en place dans keycloak/render.py
(garde-fou existant depuis un incident réel antérieur, jamais
touché ici) -- `.roles.realm[16]` (`admin_hub`) : description à 285
caractères, au-delà de la limite de 250 fixée avec marge sous la
vraie limite Keycloak (colonne DESCRIPTION VARCHAR(255)).

Raccourcie à 157 caractères, en conservant l'essentiel : ce que fait
le rôle (administration du hub, droits + listing de fichiers), sa
distinction avec le rôle "admin" (portail tickets, pas le hub), et
sa conséquence (tous les droits, y compris gérer ceux des autres).

Vérifié réellement : JSON valide après modification, ET la vraie
fonction find_oversized_descriptions() de render.py (pas une
approximation) exécutée contre le fichier complet -- confirme
qu'AUCUNE autre description, nulle part dans tout l'arbre du realm
(rôles, clients, groupes...), ne dépasse la limite.

## 2026-09-05 — check-env.py : faux positif gateway/mayan corrigé, 13 variables manquantes ajoutées à .env.example (version: c6e9ea36668a, livraison #343)

Vérification proactive après le diagnostic du déploiement macOS
(#342) -- avant d'attendre un nouveau signalement, testé
scripts/check-env.py (appelé automatiquement par scripts/run.sh)
contre un .env réellement généré par scripts/generate-env.sh.

Deux trouvailles réelles distinctes, aucune n'étant la cause du
problème macOS déjà corrigé, mais toutes deux valables :

1. **Faux positif** : KEYCLOAK_DATA_VOLUME_NAME (gateway/) et les
   MAYAN_* -- RABBITMQ/REDIS/DATABASE/AUTOADMIN_EMAIL/PORT (mayan/)
   signalées à tort "jamais référencées, probablement obsolètes".
   Même bug déjà corrigé une fois pour vault-standalone/ (dont son
   propre docker-compose.yml n'est pas lu par find_compose_vars, qui
   ne scanne QUE le docker-compose.yml principal) -- gateway/ et
   mayan/ n'avaient simplement jamais reçu le même traitement.
   Corrigé : gateway/docker-compose.yml, gateway/scripts/run.sh et
   mayan/docker-compose.yml ajoutés à OTHER_CONSUMER_FILES.

2. **13 variables réellement manquantes** de .env.example (référencées
   par docker-compose.yml, jamais documentées) : SCHEMA_ANALYZER_DATA_DIR,
   NETPROBE_DATA_DIR, GEO_DB_NAME/USER/PASSWORD/PORT,
   GEO_IMPORT_MAX_MB, ELASTICSEARCH_URL/INDEX/TIMEOUT_SECONDS/
   HOST_PORT/JAVA_OPTS, SEARCH_CACHE_TTL. Ajoutées avec leurs valeurs
   par défaut réelles (lues directement dans docker-compose.yml),
   toutes vides dans .env.example (comportement inchangé, comme la
   convention déjà établie partout ailleurs dans ce fichier).

Vérifié réellement : premier test contre un .env généré révélait
des centaines de "variables manquantes" -- panique de courte durée,
vite identifiée comme un artefact de MON PROPRE test (cp * exclut
les fichiers cachés comme .env, pas un vrai bug) -- refait
proprement (cp -r .) avant de conclure quoi que ce soit. Après
correctif des deux points ci-dessus, `python3 scripts/check-env.py`
sur un .env fraîchement généré affiche désormais "✓ .env cohérent
avec docker-compose.yml et le disque." -- sortie complètement propre.

ENV_CHANGELOG.md mis à jour.

## 2026-09-05 — Diagnostic déploiement macOS : hostname -I absent, guidage incomplet corrigé (version: 9b5382e1c07e, livraison #342)

Suite du signalement de la personne ("scripts/chantiers.sh et run
sont silencieuses", puis le script de données d'exemple échouant
partout avec "Connection refused" sur le port GATEWAY_PORT).

**Deux causes réelles distinctes trouvées** :

1. `hostname -I` (utilisé pour détecter HOST_IP dans scripts/run.sh,
   gateway/scripts/run.sh, mayan/scripts/run.sh) N'EXISTE PAS sur
   macOS -- BSD hostname ne supporte pas ce flag (spécifique GNU
   coreutils/Linux). Échouait silencieusement (stderr supprimé),
   laissant HOST_IP vide -- chaque script affichait ensuite SON
   PROPRE message d'erreur "impossible de détecter", jamais un vrai
   crash silencieux, mais un dénominateur commun jamais corrigé
   avant cette livraison malgré son usage à 4 endroits distincts (le
   4e, scripts/generate-env.sh, avait déjà son propre repli robuste
   depuis #340 -- jamais reproduit ailleurs).

   Corrigé : nouvelle fonction PARTAGÉE (shared/detect-host-ip.sh,
   ordre d'essai macOS d'abord -- ipconfig -- puis Linux -- ip
   route/hostname -I en dernier recours), réutilisée par les 4
   scripts (les 3 corrigés + generate-env.sh refactoré pour ne plus
   dupliquer sa propre copie). Testé de bout en bout après refactor,
   comportement identique confirmé.

2. **Guidage incomplet donné par erreur (moi-même, dans README.md et
   les scripts précédents)** : `./scripts/run.sh up -d --build`
   démarre SEULEMENT le stack principal, jamais `gateway/` (Keycloak
   + tls-proxy, qui écoute sur GATEWAY_PORT). Sans gateway/ démarré,
   RIEN n'écoute sur ce port -- le stack principal tourne
   parfaitement de son côté, mais reste entièrement injoignable de
   l'extérieur. La section "Plusieurs stacks" de README.md
   elle-même était OBSOLÈTE : ne documentait que 2 cibles de
   run-all.sh (main + vault-standalone) alors que le script en gère
   réellement 4 (gateway + mayan + main + vault-standalone, ajoutés
   depuis) -- explique directement pourquoi ce guidage erroné a été
   donné.

   Corrigé : README.md réécrit pour documenter les 4 cibles réelles
   et recommander explicitement `./scripts/run-all.sh all up -d
   --build` pour un premier démarrage complet, avec un avertissement
   explicite dans la section "Stack unique" (qui reste utile pour
   d'autres cas, mais insuffisante seule pour un premier essai).
   scripts/generate-env.sh, scripts/README-seed.md et le docstring de
   scripts/seed-sample-data.py corrigés de la même façon (prochaine
   étape recommandée, prérequis documenté).

Vérifié réellement : syntaxe de tous les scripts modifiés (bash -n),
generate-env.sh retesté de bout en bout après refactor (comportement
identique, HOST_IP toujours détecté correctement).

## 2026-09-05 — scripts/seed-sample-data.py : ajout de la GED (version: a906a77fe04f, livraison #341)

Suite de la livraison #340 -- ged-api ajoutée au script de données
d'exemple (2 documents texte). Nécessite le stack Mayan SÉPARÉ
démarré en plus (./mayan/scripts/run.sh up -d --build) -- ged-api
appelle Mayan de façon synchrone pour créer chaque document, jamais
un crash si Mayan est injoignable, mais une erreur 502 par document,
comptée en échec sans bloquer le reste du script.

Vérifié réellement : payload testé directement contre create_document
(client de test Flask, mayan_client simulé puisque Mayan lui-même
n'est pas disponible dans cet environnement de développement) --
confirmé code 201 en sortie de route (le "202" mentionné dans son
propre docstring décrit la réponse INTERNE de l'API Mayan, pas celle
renvoyée par ged-api à son appelant -- distinction vérifiée plutôt
que supposée). Script complet retesté en conditions d'échec réseau
(URL /api/ged/documents correctement construite, erreurs 502 gérées
sans interrompre le reste).

scripts/README-seed.md mis à jour.

## 2026-09-05 — Correctif bash 3.2 (macOS), génération auto de .env, données d'exemple (version: 02a5f7335645, livraison #340)

Trois demandes distinctes traitées dans la même livraison, suite à
un déploiement tenté sur macOS.

**Correctif réel signalé par la personne en plein déploiement** :
`./scripts/chantier.sh build --all` échouait avec `unbound variable`
sur macOS. Cause précise : macOS fournit par défaut bash 3.2 (dernière
version compatible GPLv2, 2007) -- un tableau VIDE (`ARGS=()`) suivi
d'une expansion `"${ARGS[@]}"` sous `set -u` y déclenche cette erreur,
contrairement à bash 4+ (Linux) où la même expansion renvoie
simplement zéro argument. Corrigé en testant `${#ARGS[@]}` (comptage,
jamais affecté par ce piège même en bash 3.2) avant l'expansion --
vérifié n'être le seul cas dans ce script ni dans les autres scripts
`set -u` du projet (recherche systématique du motif `tableau=()`
suivi d'une expansion, un seul résultat). Testé dans les 4 cas d'usage
possibles (avec/sans --all, avec/sans argument de service).

**scripts/generate-env.sh** -- demandé explicitement : générer un
.env complet et fonctionnel sans remplir à la main les ~237 variables
de .env.example. Détecte automatiquement HOST_IP (macOS via ipconfig,
Linux via ip route/hostname -I en repli) et COMPOSE_PROJECT_NAME
(nom du dossier), génère aléatoirement les secrets INTERNES à ce
docker-compose (Keycloak, prefs-api, Mayan, SSH_TUNNELS et SNMP
passphrase+sel) -- préserve LDAP_BIND_PASSWORD=change-me à l'identique
(un garde-fou existant dans gateway/scripts/run.sh en dépend), laisse
vides tous les systèmes externes réels (LDAP, IPAM/Optick/Zenoss/
TTS-GU/OwnCloud/Cacti, GLPI, IMAP réel, Google OAuth) -- un secret
généré ne correspondrait à aucun système réel. Remplacement via
python3 plutôt que sed -i, pour éviter toute divergence BSD/GNU sed
supplémentaire le même jour. Testé de bout en bout (intégrité des 237
variables avant/après, refus/acceptation d'écrasement, régénération).

**scripts/seed-sample-data.py** -- suite de la demande ("un package
complet autonome... des données exemples pour tous les modules").
Peuple les modules NATIFS sans dépendance externe : tickets-api
(types/sites/niveaux/tickets/événement calendrier), tasks-api (3
tâches), architecture-api (3 équipements), snmp-api (1 cible),
classifier-api (1 dictionnaire, 6 termes). Découverte en cours de
route : aucun de ces services ne publie de port direct sur l'hôte --
cible donc la passerelle unique (tls-proxy), confirmé sans
authentification Keycloak requise sur ces chemins. GED (nécessite
Mayan démarré) et tous les modules pont vers un système externe réel
restent explicitement hors de portée -- voir scripts/README-seed.md.
pixel-grid a déjà son propre générateur dédié, réutilisé tel quel.

Vérifié réellement : chaque payload testé directement contre son
module (clients de test Flask) avant d'écrire le script définitif.
snmp-api : pysnmp non installable dans cet environnement de
développement (dépendance réelle du conteneur) -- logique de
chiffrement+stockage vérifiée en contournant l'import complet de
app.py. Script complet testé en conditions d'échec réseau (URL
correctement construite, erreurs gérées proprement, code de sortie
1 si tout échoue).

README.md, scripts/README-seed.md, .gitignore mis à jour.

## 2026-09-04 — Vue "relations" : intégration directe depuis le Calendrier (version: e3b0c753a721, livraison #339)

Suite du "reste à faire" de relations/README.md -- premier bouton
"voir les relations" (🔗) intégré directement dans une vue existante,
plutôt que de laisser la vue Relations comme un formulaire isolé où
il faut ressaisir manuellement type+identifiant.

EntView.jsx porte désormais l'état de navigation (relationsTarget)
et un callback viewRelations(type, id) transmis aux onglets enfants
-- change d'onglet vers "Relations" ET pré-remplit sa cible en un
seul geste. CalendarView.jsx reçoit ce callback (onViewRelations,
prop optionnelle -- rétrocompatible si absente) et affiche un bouton
🔗 sur chaque ligne de la file d'attente (tickets) ET chaque ligne de
la liste d'événements calendrier -- les deux premiers types
d'entités que relations-api sait déjà interroger.

RelationsView.jsx accepte désormais initialEntityType/initialEntityId
-- déclenche la recherche automatiquement à l'arrivée, via un
useEffect dépendant explicitement de ces deux valeurs (jamais du
simple changement d'onglet, pour ne pas relancer une recherche déjà
affichée si la personne navigue ailleurs puis revient sans repasser
par un bouton).

Reste à faire : mêmes boutons pour GED et Tâches (pas encore
intégrées dans leurs vues respectives).

Vérifié réellement : structure JSX de RelationsView.jsx, EntView.jsx
et CalendarView.jsx revérifiée après l'intégration. Confirmé
qu'aucun autre composant du hub n'utilise CalendarView en dehors
d'EntView.jsx -- le nouveau prop optionnel reste rétrocompatible
partout ailleurs.

hub/README.md et relations/README.md mis à jour.

## 2026-09-04 — relations-api : quatrième et dernière forme de relation directe (proximité géographique) -- les 4 formes sont livrées (version: 7e9d1e46bae6, livraison #338)

Suite du point 2 de l'item 38 du backlog, quatrième et dernière passe
sur les formes de relation directe de relations-api. Proximité
géographique construite en réutilisant pixel-grid-api (déjà
existant, gère des géolocalisations par nom de lieu) plutôt qu'en
inventant une nouvelle source de coordonnées -- les tickets ont déjà
un site_label disponible via /queue, seul des quatre types d'entités
à porter une notion de lieu dans ce projet.

Distance calculée par la formule de Haversine, seuil de 2 km choisi
comme ordre de grandeur raisonnable pour un contexte "même campus" --
jamais vérifié contre un vrai jeu de données ni discuté avec la
personne, à ajuster une fois un usage réel observé.

pixel-grid-api traité comme une source OPTIONNELLE, contrairement aux
trois autres (tickets/ged/tasks-api, essentielles -- sans elles rien
à mettre en relation) : injoignable ou sans localisation
cartographiée, la proximité géographique est simplement absente des
résultats, jamais une erreur qui bloquerait les trois autres
critères. Vérifié explicitement par test.

Vérifié réellement : haversine_km en isolation (distance Paris-Lyon
plausible, distance nulle pour un même point, deux points proches
sous le seuil). Scénario à trois tickets testé de bout en bout (deux
sites proches géographiquement sans aucun mot/nom en commun -- liés ;
un troisième site distant -- jamais lié) -- un premier test contenait
un mot partagé accidentel entre les textes de test, créant une
relation sémantique en plus de la géographique (comportement correct,
assertion de test erronée), repéré et corrigé avant de conclure.
Dégradation gracieuse confirmée par test explicite : pixel-grid-api
injoignable -> toujours 200 avec simplement aucune relation
géographique. Non-régression complète reconfirmée sur tous les
scénarios des passes #335-337.

**Les QUATRE formes de relation directe mentionnées par la personne
sont désormais toutes construites** : nom exact (#335), IP (#336),
proximité sémantique (#337), proximité géographique (#338).

relations/README.md créé/mis à jour à chaque passe, BACKLOG.md
consolidé en conséquence (détail complet de chaque passe renvoyé
vers relations/README.md, jamais répété dans le backlog une fois le
travail terminé).

## 2026-09-04 — relations-api : troisième forme de relation directe (proximité sémantique), déduplication nom/sémantique (version: ec9d9a7a32fa, livraison #337)

Suite du point 2 de l'item 38 du backlog, troisième passe sur
relations-api. Troisième critère de relation DIRECTE construit : au
moins un mot significatif commun entre les textes de deux entités --
même technique déjà établie dans ce projet pour une tâche apparentée
(tickets/api/suggestion_engine.py, "score de similarité par mots
significatifs partagés"), jamais un vrai modèle NLP (aucun accès
réseau pour en télécharger un pendant le développement, même
contrainte documentée là-bas). STOPWORDS et la logique d'extraction
dupliquées à l'identique dans relation_engine.py (service séparé,
jamais un import inter-conteneurs pour une si petite fonction pure).
Seuil minimal (1 mot partagé) repris tel quel du précédent établi,
jamais un chiffre inventé sans précédent dans ce projet.

Contrairement au regroupement O(n) des critères nom/IP, la
comparaison sémantique nécessite une comparaison par paires -- O(n²),
acceptable tant que le volume reste modeste.

Déduplication ajoutée : un nom identique implique presque toujours un
recouvrement de mots significatifs (les mots du nom lui-même
comptent) -- ajouter aussi un marqueur sémantique pour la même paire
aurait été une redondance quasi systématique. Supprimée explicitement
pour les paires déjà justifiées par le nom. Pas la même suppression
pour IP+sémantique, qui reste un signal double genuinement
informatif -- vérifié par test que les deux marqueurs distincts sont
bien conservés dans ce cas.

Vérifié réellement : extraction de mots significatifs en isolation
(mots vides exclus, normalisation des accents confirmée -- un premier
test contenait une erreur, un mot supplémentaire non voulu dans l'un
des deux textes comparés, repérée par l'échec et corrigée avant de
conclure). Scénario purement sémantique confirmé de bout en bout.
Déduplication nom/sémantique vérifiée ET conservation du double
signal IP+sémantique vérifiée sur un cas distinct. Non-régression
complète reconfirmée sur tous les scénarios des passes #335-336.

Seule la proximité géographique reste à construire des quatre formes
de relation directe mentionnées par la personne.

relations/README.md et BACKLOG.md mis à jour.

## 2026-09-04 — relations-api : deuxième forme de relation directe (IP), limite structurelle levée (version: c150150dd3ac, livraison #336)

Suite du point 2 de l'item 38 du backlog, deuxième passe sur
relations-api. Deuxième critère de relation DIRECTE construit : une
adresse IPv4 identique trouvée dans le texte (libellé + description
combinés) de deux entités différentes. Validation des octets
(0-255) pour réduire le bruit d'un faux positif type numéro de
version.

entity_fetchers.py étendu pour combiner libellé et description dans
un champ "text" par entité (déjà disponible côté API sources, jamais
un nouveau champ créé) -- utilisé pour la détection d'IP, jamais pour
la correspondance de nom qui reste sur le libellé seul.

relation_engine.py refactoré : compute_direct_relations combine
désormais deux dictionnaires intermédiaires (marqueurs de nom,
marqueurs d'IP) via une fonction factorisée (_pairs_by_marker) --
même logique de regroupement pour les deux critères.

La limite structurelle documentée en #335 est désormais LEVÉE,
confirmée par test dans les deux sens plutôt que simplement
supposée : une entité porte désormais potentiellement deux
marqueurs distincts (son nom ET une IP mentionnée dans son texte).
Si cette IP est partagée avec une troisième entité qui n'a pas le
même nom, cette troisième entité devient une relation INDIRECTE de
la première, via la seconde comme pont -- premier cas de relation
indirecte réellement observé (pas seulement théorique).

Vérifié réellement : extraction d'IP en isolation (IP simple, aucune
IP, IP répétée comptée une fois, octet invalide >255 rejeté).
Scénario à trois entités testé de bout en bout (A-B par nom, B-C par
IP, A-C indirecte via B) -- confirmé symétriquement dans les deux
sens. Non-régression complète reconfirmée sur les scénarios "nom
seul" de la passe précédente, y compris description: None (pas
seulement absent) géré sans exception.

relations/README.md et BACKLOG.md mis à jour.

## 2026-09-04 — Nouveau service relations-api, première passe sur la vue "relations" de la super tuile ENT (version: 6276886a4bab, livraison #335)

Suite du point 2 de l'item 38 du backlog -- modèle clarifié par la
personne le 2026-09-04 : relation DIRECTE = marqueur commun identique
(chaîne identique dans un champ nom/label, IP, proximité géographique,
proximité sémantique) ; relation INDIRECTE = un attribut associé à un
élément direct ou à un ensemble -- deux éléments d'un même ensemble
sont en relation indirecte entre eux.

Nouveau service relations-api, SANS ÉTAT PROPRE -- interroge
tickets-api/ged-api/tasks-api à la volée à chaque requête via leur
API HTTP déjà publique, calcule les relations en mémoire, aucun
cache ni persistance dans cette première passe.

Portée de cette première passe : relations DIRECTES par
correspondance EXACTE de texte uniquement (nom/label/sujet/titre,
normalisé). IP, proximité géographique et proximité sémantique
explicitement hors de portée ici, à construire dans des passes
ultérieures.

Limite structurelle découverte par test, pas supposée : avec un seul
critère de relation directe et un seul marqueur par entité, aucune
relation indirecte ne peut jamais se produire -- toutes les entités
partageant un marqueur forment une clique totalement connectée en
direct. Le code de composantes connexes reste correct et prêt --
redevient pertinent dès qu'un deuxième critère direct est ajouté.

Sixième onglet de EntView.jsx (RelationsView.jsx) -- interface
volontairement minimale, formulaire type+identifiant, sans graphe
visuel ni navigation cliquable pour cette première passe. Route
passerelle nginx ajoutée dès cette livraison (piège déjà rencontré
pour netprobe-api en #301, jamais reproduit ici).

Vérifié réellement : relation_engine.py testé en isolation (moteur
pur, sans réseau) -- normalisation, détection de relation directe
entre types différents, seuil de longueur minimale, composantes
connexes, confirmation de la limite structurelle. app.py testé de
bout en bout avec les trois services amont simulés -- bonnes
relations sur un scénario à 3 entités, 404 sur entité inconnue, 400
sur entity_type invalide, 502 si un service amont est injoignable.
Un premier jeu de test contenait une erreur (libellés pas réellement
identiques) -- repérée par l'échec, corrigée avant de conclure.

Corrigé au passage : hub/README.md et BACKLOG.md référençaient tous
deux #333 au lieu de #334 pour l'ajout de l'onglet GED -- trouvé et
corrigé en documentant cette livraison.

relations/README.md créé, hub/README.md et BACKLOG.md mis à jour.

## 2026-09-04 — Tuile ENT : premier pas vers la "super tuile", onglet GED ajouté (version: 804bae4c0e6a, livraison #334)

Suite des clarifications de la personne sur l'item 38 du backlog
(point 2, "la tuile ENT devient une super tuile").

Premier morceau concret : GedView.jsx (interface complète pour
ged-api, déjà construite et déjà utilisée comme tuile autonome
depuis #167) ajoutée comme quatrième onglet de EntView.jsx, aux
côtés de Calendrier/Tâches/Validation déjà en place -- confirmé par
la personne comme réponse au "dépôt de fichiers interne" mentionné
dans les spécifications pour le webmail éventuel. Réutilisée telle
quelle, aucune reconstruction.

App.jsx : EntView reçoit désormais aussi gedApiBase
(GED_API_BASE_URL, déjà défini) et login (profile.preferred_username,
déjà utilisé ailleurs) -- aucune nouvelle variable d'environnement.

Webmail délibérément pas ajouté -- explicitement noté "à voir" par
la personne, jamais présumé décidé.

Vue "relations" transversale toujours pas commencée, mais le modèle
est désormais clarifié par la personne : relation DIRECTE = marqueur
commun identique (chaîne identique dans un champ nom/label, IP,
proximité géographique, proximité sémantique) ; relation INDIRECTE =
un attribut associé à un élément direct ou à un ensemble -- deux
éléments d'un même ensemble sont en relation indirecte entre eux.
Chantier à part entière touchant potentiellement tickets/calendrier/
GED/tasks, à traiter par passes successives.

Vérifié réellement : structure JSX de EntView.jsx et App.jsx
revérifiée après l'ajout de l'onglet.

hub/README.md et BACKLOG.md mis à jour.

## 2026-09-04 — Item 39 du backlog (ergonomie ENT/Calendrier) confirmé livré, un déclenchement manquant complété (version: 47d37d62666b, livraison #333)

Suite des clarifications de la personne sur les items 38-39 du
backlog. Avant de coder quoi que ce soit sur les points explicitement
"prêts à construire", relecture systématique contre le code existant.

Résultat : les points 1, 2, 3 et 5 des cinq points explicites de
l'item 39 étaient déjà entièrement livrés en #284 (badge mots-clés
simplifié, liste de retour en arrière sur création de ticket, file
d'attente répliquant fidèlement la tuile Tickets, validation groupée
des changements de statut avec journal persistant) -- jamais
explicitement rapprochés de leur point précis du backlog jusqu'à
cette relecture. Aucun code modifié pour ces quatre points.

Le point 4 (statut automatique selon le moment de l'événement
calendrier) avait son BACKEND déjà livré en #284
(determine_calendar_statut_label/ensure_calendar_statuts, création
automatique des 3 statuts Clos/En cours/Planifié au démarrage sans
doublon) -- mais recalculateTicketStatus, déjà exportée côté client,
n'était jamais appelée nulle part côté interface. La clarification de
la personne a confirmé la création des statuts (déjà faite) ; le
"moment de consultation" restait à trancher.

Câblé dans hub/src/CalendarView.jsx:load() -- retenu comme moment de
consultation : chaque ouverture/rafraîchissement de la vue Calendrier,
uniquement pour les tickets déjà liés à un événement
(assigned_ticket_ids), en best-effort.

Vérifié réellement : chaîne complète testée de bout en bout côté
backend -- un ticket lié à un événement futur passe en file d'attente
avec le statut "Planifié" proposé, puis réellement appliqué après
validation groupée (jamais appliqué directement au recalcul lui-même,
conforme à la conception documentée). Un même ticket dont l'événement
devient passé recalcule bien vers "Clos". Structure JSX de
CalendarView.jsx revérifiée après l'ajout.

tickets/README.md et BACKLOG.md mis à jour -- item 39 marqué
entièrement livré.

## 2026-09-04 — BACKLOG.md : item 39 point 1 confirmé déjà livré (version: d8fb7accfed5, livraison #332)

Passage au point suivant du backlog après la clôture du chantier
rights-api -- item 38 point 2 (tuile ENT) et item 39 points 2-5
nécessitent tous une clarification avec la personne avant tout code
(explicitement noté dans le backlog lui-même), jamais présumé.
Item 39 point 1 ("Badge Mot-clé détecté simplifié"), lui, était
explicitement marqué "bien scopé, prêt à construire tel quel".

Vérification avant de coder : ce point est en réalité DÉJÀ LIVRÉ --
`hub/src/CalendarView.jsx` implémente déjà exactement le
comportement demandé (point orange conservé, mini-liste tronquée à
15 caractères des mots-clés trouvés au lieu du texte permanent,
liste complète au survol), construit dans le cadre de la livraison
#284 mais jamais explicitement confirmé contre ce point précis du
backlog. Aucune trace de l'ancien texte "Mot-clé détecté" nulle part
dans le projet -- recherche exhaustive avant de conclure.

BACKLOG.md mis à jour pour refléter cet état, aucun code modifié.

## 2026-09-04 — Chantier tickets-api CLOS, item 38 du backlog TERMINÉ (version: 93f579b7b77b, livraison #331)

Passe finale (8/8) sur tickets-api : vérification des 34 dernières
routes GET, échantillonnage ciblé sur les moins explicites
(/terms/synthesis, /portal/profile, confirmées comme de simples
vues d'agrégation/consultation) en complément du balayage
systématique déjà fait en passe 7. Aucune route GET du module ne
justifie de garde rights-api, cohérent avec la convention appliquée
sans exception sur les 20 services de ce chantier.

Bilan complet de tickets-api (8 passes, #324-331) : 19 routes gardées
sur 85, jamais un branchement en bloc -- cluster console DB/SQL (le
plus dangereux), CRUD des 6 tables de référence via deux fonctions
partagées, conclusion délibérée de NE RIEN garder sur le cœur ticket
(self-service par conception), 3 clusters de règles de configuration
partagée, import calendrier et import global de base (2 vrais bugs
de fuite de groups trouvés et corrigés), une DÉCOUVERTE CRITIQUE
(/raw_tables aurait pu contourner toute la protection posée,
corrigée avec une garde conditionnelle), et la connexion OAuth
Google.

Ce chantier clôt l'item 38 du backlog dans son ensemble : les ~32
services API du projet sont désormais tous soit branchés sur
rights-api, soit confirmés sans rien à y brancher. BACKLOG.md
condensé en conséquence -- l'historique complet de chaque décision
reste dans le README de chaque service concerné, jamais perdu, juste
plus répété dans le backlog une fois le travail terminé.

tickets/README.md et BACKLOG.md mis à jour.

## 2026-09-04 — Chantier tickets-api, passe 7/N -- OAuth Google résolue + balayage systématique des routes GET (version: 46392412f21e, livraison #330)

Suite de l'item 38 du backlog, septième passe sur tickets-api.

Limite de la passe 4 (#327) enfin résolue : GET /oauth/google/start
est une redirection navigateur (aucun corps de requête possible),
gardée avec groups lu depuis les paramètres de requête, même motif
que /calendar/import en passe 4. Connecter un compte Google
différent redéfinit la source calendrier pour tout le monde.

Protéger /start protège indirectement /oauth/google/callback aussi,
sans avoir besoin de le garder directement : son contrôle CSRF
(state) exige qu'un /start autorisé ait déjà généré ce state -- un
appel direct au callback échoue de toute façon sans state valide,
avec ou sans rights-api. Vérifié explicitement par test.

Balayage systématique des 37 routes GET restantes -- recherche
automatisée de mots-clés d'écriture SQL dans le corps de chaque
fonction, pas une relecture au jugé. Deux résultats : /oauth/google/
callback (effet de bord réel confirmé, déjà traité) et
/stats/reopenings (faux positif -- le mot "UPDATE" provenait d'une
mention de update_ticket() dans un commentaire, pas d'une vraie
requête SQL, vérifié avant de conclure). Aucune autre route GET du
module n'a d'effet de bord caché.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur oauth_google_start,
/oauth/google/status confirmée toujours libre, dépendance du
callback vis-à-vis d'un start autorisé confirmée par test.
Non-régression complète reconfirmée.

tickets/README.md et BACKLOG.md mis à jour.

## 2026-09-04 — Chantier tickets-api, passe 6/N -- contournement possible via /raw_tables évité (version: 225e0c622cda, livraison #329)

Suite de l'item 38 du backlog, sixième passe sur tickets-api --
toutes les routes d'écriture du module sont désormais examinées.

DÉCOUVERTE CRITIQUE en examinant la dernière route d'écriture non
encore vue : PUT /raw_tables/<table_name>/<row_id> est une route
générique par liste blanche (RAW_EDITABLE_TABLES) qui recouvre à la
fois des tables déjà protégées PAR LEUR PROPRE ROUTE dans des passes
précédentes (users/types/levels/statuts via update_reference_row,
calendar_filter_rules/exclusion_rules/priority_keywords, matching_config
via /settings) ET des tables délibérément laissées ouvertes
(tickets/calendar_events/ticket_time_entries, cœur ticket
self-service).

Sans garde adaptée, cette route aurait contourné silencieusement
toute la protection déjà posée : PUT /raw_tables/users/5 aurait pu
modifier un utilisateur sans passer par la garde de PUT /users/5,
rendant le travail des passes précédentes inutile pour quiconque
découvre cette route alternative.

Corrigé avec une garde CONDITIONNELLE, jamais en bloc : un ensemble
PROTECTED_RAW_TABLES recense les tables déjà gardées ailleurs -- la
garde rights-api ne s'applique que si la table ciblée y figure.
Reste cohérente avec chaque décision déjà prise séparément.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED confirmé dans les DEUX sens -- une table protégée refuse même
pour admin_hub si rights-api est injoignable, ET une table non
protégée reste toujours accessible même dans ce même cas.
Non-régression complète reconfirmée.

Toutes les routes d'écriture (POST/PUT/DELETE) du module ont
désormais été examinées. Les ~44 routes restantes sont toutes en
lecture (GET), à confirmer une par une plutôt que présumées sans
risque.

tickets/README.md et BACKLOG.md mis à jour.

## 2026-09-04 — Chantier tickets-api, passe 5/N -- import global de base + réglages (version: e2196999942c, livraison #328)

Suite de l'item 38 du backlog, cinquième passe sur tickets-api.

Gardé deux routes de sévérité élevée. POST /import -- même sévérité
que le cluster console DB/SQL de la passe 1 : mode=replace vide
entièrement les tables concernées avant réinsertion (destructeur),
même mode=merge permet d'injecter/écraser des lignes arbitraires
dans n'importe quelle table via JSON brut, contournant toute
validation métier. POST /settings -- alimente matching_config (dont
trigger_keyword), qui pilote le moteur de détection automatique
calendrier->ticket, même famille que les règles déjà gardées en
passe 3.

Deux vrais bugs trouvés et corrigés en cours de route, avant de
tester quoi que ce soit (pas après un échec de test) : les deux
routes traitaient tout le corps JSON reçu comme des données métier
sans filtre -- groups (ajouté pour la vérification des droits)
aurait été soit inséré comme une clé de configuration bidon dans
matching_config, soit confondu avec un nom de table inconnu dans
import_database. Corrigé en excluant explicitement "groups" du corps
avant qu'il touche la logique métier dans les deux cas -- vérifié
positivement par test que groups n'apparaît jamais dans les données
réelles après un appel autorisé.

Jamais gardé : GET /export -- lecture pure, cohérent avec la
convention établie dans tout ce chantier.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 2 routes
gardées, GET /export confirmée toujours libre, et confirmation
positive que groups n'apparaît jamais dans les données réelles après
un import/réglage accepté. Non-régression complète reconfirmée.

tickets/README.md et BACKLOG.md mis à jour.

## 2026-09-04 — Chantier tickets-api, passe 4/N -- import calendrier (version: 4c98313f2153, livraison #327)

Suite de l'item 38 du backlog, quatrième passe sur tickets-api.

Gardé les 3 routes qui font entrer de nouvelles données dans le
pipeline calendrier partagé : POST /calendar/import (upload .ics),
POST /calendar/import_google_api (depuis le compte Google déjà
connecté), POST /calendar/import_url (depuis une URL secrète iCal).
Même raisonnement que pour les règles de filtrage/exclusion (passe
3) : même protégées en aval, un import massif de faux événements
pourrait exploiter des règles légitimes pour générer des tickets
parasites -- l'entrée du pipeline mérite sa propre protection.

Particularité technique : POST /calendar/import accepte soit un
fichier multipart, soit le contenu ICS brut directement en corps de
requête -- ni JSON ni formulaire garanti. Résolu en lisant groups
depuis les paramètres de requête pour cette route spécifique, seule
exception à la convention établie jusqu'ici.

Délibérément pas gardé dans ce même cluster : POST /calendar/assign
(même famille que /time_entries, action de travail normale) ; POST
/calendar/suggest_name (confirmé lecture pure) ; POST
/calendar/create_ticket (famille du cœur ticket, self-service).

Limite CONNUE et assumée, à reprendre séparément : les routes de
connexion OAuth Google elles-mêmes sont des redirections navigateur,
le motif de garde établi ne s'applique pas proprement à ce flux --
pourtant connecter un compte différent est arguablement plus
consequential qu'un simple import.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 3 routes
gardées (y compris le cas du corps brut ICS), /calendar/assign et
/calendar/suggest_name confirmés toujours libres. Non-régression
complète reconfirmée.

tickets/README.md et BACKLOG.md mis à jour.

## 2026-09-04 — Chantier tickets-api, passe 3/N -- conclusion sur le cœur ticket + règles de configuration (version: 342fb6e2b50b, livraison #326)

Suite de l'item 38 du backlog, troisième passe sur tickets-api.

Conclusion importante après examen complet du cœur ticket (création,
édition, suppression, validation, messages, temps passé) : RIEN n'a
été gardé dans ce sous-groupe, décision délibérée. POST /tickets, PUT
/tickets/<id> ("édition libre" selon son propre commentaire), les
messages et les saisies de temps sont des actions de travail normales
ouvertes à tous les rôles (demandeur, technicien) par conception --
les gater aurait cassé le fonctionnement du système pour tout le
personnel non-admin. DELETE /tickets/<id> est déjà scopée par le code
aux seuls tickets jamais confirmés. Le cluster de validation
calendrier (/validate, /recalculate_status, /status-changes/
validate_all) n'a aucune restriction de rôle côté frontend
(hub/src/ValidationView.jsx) -- cohérent avec un usage normal du
personnel, laissé ouvert par cohérence.

En revanche, gardé les 3 clusters de règles de configuration partagée
affectant le traitement automatique pour tout le monde :
POST/DELETE /filter_rules, /exclusion_rules, /priority_keywords (6
routes) -- même raisonnement que classifier-api (#315) et
nebula-api/geo-import-api (#314/#318).

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 6 routes
gardées, ET confirmation EXPLICITE (pas juste absence de test) que
create_ticket/update_ticket/messages/temps restent TOUJOURS libres
même avec rights-api actif et refusant. Non-régression complète
reconfirmée -- une première erreur de test (payload incomplet)
repérée et corrigée avant de conclure.

Reste environ 50 routes (calendrier/OAuth Google, export/import
global, réglages) pour de futures passes.

tickets/README.md et BACKLOG.md mis à jour.

## 2026-09-04 — Chantier tickets-api, passe 2/N -- CRUD des données de référence (version: dac8fad8fd01, livraison #325)

Suite de l'item 38 du backlog, deuxième passe sur tickets-api.
Gestion des 6 tables de référence : users, types, sites, levels,
statuts, deadline_escalation_rules.

Trouvaille utile : les routes PUT et DELETE de ces 6 tables passent
TOUTES par deux fonctions génériques partagées
(update_reference_row/delete_reference_row) -- une seule garde posée
dans chacune couvre les 12 routes PUT/DELETE d'un coup, vérifiée
explicitement contre plusieurs tables différentes (types, sites,
statuts -- y compris la variante spéciale update_statut qui
pré-valide son corps avant de le transmettre) pour confirmer que le
motif fonctionne pour tous les appelants.

Gardé : POST /users, POST /users/import-keycloak-group, POST /types,
POST /sites, POST /sites/import-text (multipart), POST /levels,
POST /deadline-escalation-rules, POST /statuts, plus les 12 routes
PUT/DELETE via les deux fonctions communes -- 20 routes au total.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 8 routes POST
individuelles ET sur les deux fonctions communes testées contre 3
tables différentes chacune, lecture confirmée non affectée.
Non-régression complète reconfirmée.

Reste environ 60 routes (tickets eux-mêmes, règles, calendrier/OAuth
Google, messages, export/import, réglages) pour de futures passes.

tickets/README.md, BACKLOG.md et ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Chantier tickets-api démarré : branchement rights-api, passe 1/N -- cluster console DB/SQL (version: 70d0e88b8f7d, livraison #324)

Suite de l'item 38 du backlog. Premier passage sur tickets-api (85
routes, le plus large service du projet, de loin) -- traité en
PLUSIEURS PASSES distinctes plutôt que d'un coup, chaque passe
testée et documentée séparément.

Cette première passe cible le cluster console DB/SQL -- de loin le
plus dangereux du module, comparable ou supérieur à dba-api /sql
(déjà signalé "particulièrement sensible" dans ce projet) :

- POST /db/sql/execute -- exécution SQL arbitraire, y compris
  DROP/DELETE/UPDATE. Sauvegarde automatique avant toute requête
  non-SELECT déjà en place, mais reste une porte ouverte totale sans
  garde supplémentaire.
- PUT /db/tables/<table>/rows/<row_id> -- édition générique de
  n'importe quelle ligne éditable de n'importe quelle table,
  contourne toute validation métier des routes typées normales.
- POST /backups/<filename>/restore -- DESTRUCTIF, vide la base
  actuelle puis rejoue le dump choisi.
- POST /backups -- moins critique, gardé par cohérence.

Jamais gardé : POST /db/sql/check -- confirmé PUREMENT lecture dans
son propre commentaire (EXPLAIN, rollback systématique, "vérifié
empiriquement"), ni aucune route GET du cluster.

OPT-IN comme tous les branchements précédents -- TICKETS_RIGHTS_API_URL
vide par défaut, comportement inchangé tant qu'elle n'est pas
configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 4 routes
gardées avec un groupe non autorisé, /db/sql/check et les routes GET
du cluster confirmées toujours libres. Non-régression complète
reconfirmée. Une première erreur d'URL dans les tests (chemin
incomplet) a été repérée par l'échec et corrigée avant de conclure.

Les ~80 autres routes du module (CRUD tickets/users/types/sites/
levels/statuts, règles, calendrier et son OAuth Google, import/
export, messages, validation de statut) restent à examiner dans de
futures sessions dédiées.

tickets/README.md, BACKLOG.md, .env.example et ENV_CHANGELOG.md mis
à jour.

## 2026-09-04 — Item 38 : recoupement complet, correction d'un compte erroné (version: 1c15719c1a62, livraison #323)

Recoupement systématique de la liste complète des ~32 services API
du projet contre tout ce qui a été branché ou confirmé sans rien à
brancher depuis #289. Résultat : une estimation "~16 restants"
maintenue par inadvertance sur plusieurs livraisons était erronée --
en réalité, SEUL tickets-api reste à évaluer. Tous les autres
services du projet sont soit branchés (19), soit confirmés sans rien
à brancher (10, lecture seule ou sans état persisté), soit des cas
particuliers hors périmètre (netprobe -- module propre, rights --
est rights-api lui-même).

BACKLOG.md (item 38) corrigé en conséquence.

## 2026-09-04 — Item 38 : cinq services évalués, aucun branchement nécessaire (version: 8d3251c9dd57, livraison #322)

Suite de l'item 38 du backlog -- passage d'évaluation pure, aucun
code modifié dans aucun service.

memory-api, cacti-api, tts-gu-api : confirmés lecture seule par
conception (même famille que ipam/optick/zenoss/owncloud), aucune
route d'écriture.

rsyslog-listener-api : lecture seule côté HTTP -- l'écoute UDP
syslog elle-même est un socket séparé, hors de portée de rights-api.

retro-api : /scan analyse un ZIP entièrement EN MÉMOIRE (jamais
décompressé sur disque), ne persiste jamais rien -- lecture/calcul
pur malgré le verbe POST, même famille que geo-import-api /correlate
(#318) et schema-analyzer-api /analyze (#319).

BACKLOG.md (item 38, 5 services de plus évalués -- ~16 restent hors
tickets-api) mis à jour.

## 2026-09-04 — Dix-neuvième branchement de rights-api : vigilance-api (version: d5166ffc3b50, livraison #321)

Suite de l'item 38 du backlog. Une seule route d'écriture dans ce
module -- /analyze déclenche un passage IMMÉDIAT (hors du rythme
périodique déjà en place) et PERSISTE les signaux détectés. Sans
garde, n'importe qui aurait pu déclencher des passages répétés à
volonté (bruit dans l'historique des signaux, charge supplémentaire
sur network-agent-api en cascade).

OPT-IN comme tous les branchements précédents --
VIGILANCE_RIGHTS_API_URL vide par défaut, comportement inchangé tant
qu'elle n'est pas configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé pour un groupe non
autorisé, /signals confirmée non affectée. Non-régression complète
reconfirmée.

vigilance/README.md, BACKLOG.md (item 38, 19 services désormais
branchés), .env.example et ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Dix-huitième branchement de rights-api : api centrale, exclusion critique de /ingest (version: b31af2e84634, livraison #320)

Suite de l'item 38 du backlog.

DÉCOUVERTE CRITIQUE avant d'agir : POST /ingest/<source> (le "chemin
de confiance" documenté en tête de fichier) est appelé PAR D'AUTRES
SERVICES en conteneur-à-conteneur -- imap-client-api (résultats
d'interprétation), pixel-grid/bridge/bridge.py, pipeline/main.py,
connectors/zenoss_legacy/zenoss_connector.py. Aucun de ces appelants
n'a de contexte utilisateur/groupes Keycloak à transmettre -- ce sont
des pipelines automatisés, pas des actions déclenchées par une
personne connectée. Le garder aurait cassé ces flux dès l'activation
de rights-api -- /ingest reste DÉLIBÉRÉMENT et DÉFINITIVEMENT jamais
gardé.

Gardé UNIQUEMENT sur les 4 routes de gestion des sources
(from-selection, register, delete, restore) -- confirmé qu'aucun
autre service Python ni aucun composant du hub ne les appelle
actuellement (même situation que revoke_collection_access/reset_user
en #308).

OPT-IN comme tous les branchements précédents --
CENTRAL_API_RIGHTS_API_URL vide par défaut, comportement inchangé
tant qu'elle n'est pas configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 4 routes
gardées avec un groupe non autorisé, /ingest confirmé TOUJOURS
fonctionnel -- y compris quand rights-api est actif ET injoignable
simultanément (double vérification explicite, étant donné les
conséquences réelles d'une régression sur cette route précise).
Non-régression complète reconfirmée.

api/README.md créé (ce service n'en avait aucun jusqu'ici), BACKLOG.md
(item 38, 18 services désormais branchés), .env.example et
ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Dix-septième branchement de rights-api : schema-analyzer-api, 4 routes gardées (version: e50bbfc8eef5, livraison #319)

Suite de l'item 38 du backlog. /analyze et /relations/validate sont
EXPLICITEMENT documentées comme lecture pure (aucun effet de bord)
-- jamais gardées. Gardé UNIQUEMENT sur les 4 routes qui PERSISTENT
des relations (create/update/delete_relation + import-proposals en
masse) -- une relation trafiquée pourrait faire croire à tort qu'une
colonne référence une autre.

OPT-IN comme tous les branchements précédents --
SCHEMA_ANALYZER_RIGHTS_API_URL vide par défaut, comportement
inchangé tant qu'elle n'est pas configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 4 routes
gardées avec un groupe non autorisé, /analyze et /relations/validate
confirmées toujours libres. Non-régression complète reconfirmée.

schema-analyzer/README.md, BACKLOG.md (item 38, 17 services
désormais branchés), .env.example et ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Seizième branchement de rights-api : geo-import-api, 3 routes gardées (version: 43ca5468683d, livraison #318)

Suite de l'item 38 du backlog. Ce module est EXPLICITEMENT en
écriture (le seul de ce type parmi tous les branchements jusqu'ici) --
import de shapefiles, fusion de couches, synchronisation depuis
pixel-grid-api.

Gardé sur /import (multipart, groups lu depuis request.form),
/fusion et /connectors/geolocations/sync (corps JSON). Jamais sur
/correlate -- confirmé PUREMENT lecture (uniquement des SELECT,
aucune écriture) malgré le verbe POST utilisé pour transmettre
stratégie/options, ni /layers.

OPT-IN comme tous les branchements précédents --
GEO_IMPORT_RIGHTS_API_URL vide par défaut, comportement inchangé
tant qu'elle n'est pas configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 3 routes
gardées (multipart et JSON) avec un groupe non autorisé, /correlate
confirmée toujours libre. Non-régression complète reconfirmée.
Testé avec le stub psycopg2 déjà présent (module non installable
ici).

geo-import/README.md, BACKLOG.md (item 38, 16 services désormais
branchés), .env.example et ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Quinzième branchement de rights-api : pixel-grid-api, 4 routes gardées (version: 0199da11a653, livraison #317)

Suite de l'item 38 du backlog. Coordonnées de carte pour la
visualisation -- une entrée trafiquée ne configure rien de réel mais
peut égarer la lecture d'une carte (mauvais lieu affiché).

Gardé sur les 4 routes d'ÉCRITURE (créer/modifier/supprimer une
géolocalisation, scan pour détecter de nouveaux lieux, enregistrement
d'IP) -- jamais la lecture/agrégation.

OPT-IN comme tous les branchements précédents --
PIXEL_GRID_RIGHTS_API_URL vide par défaut, comportement inchangé
tant qu'elle n'est pas configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 4 routes
gardées avec un groupe non autorisé, lecture confirmée non affectée.
Non-régression complète reconfirmée.

pixel-grid/README.md, BACKLOG.md (item 38, 15 services désormais
branchés), .env.example et ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Quatorzième branchement de rights-api : architecture-api, 8 routes gardées (version: aa6e8f76e380, livraison #316)

Suite de l'item 38 du backlog. Ce module ne configure JAMAIS
d'équipement réel -- topologie amont/aval DÉCLARÉE, documentation
pure. Une donnée trafiquée n'endommage aucun équipement, mais
pourrait égarer un technicien en plein dépannage.

Gardé sur les 8 routes d'ÉCRITURE (créer/modifier/supprimer un
équipement, import depuis network-agent, créer/supprimer une
interface, créer/supprimer un lien topologique) -- jamais la
lecture. Faux problème vérifié en passant : `**body` transmis à
`store.update_equipment(**fields)` filtre déjà silencieusement les
clés inconnues (dont `groups`), confirmé par un test isolé avant de
continuer.

OPT-IN comme tous les branchements précédents --
ARCHITECTURE_RIGHTS_API_URL vide par défaut, comportement inchangé
tant qu'elle n'est pas configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 8 routes
gardées avec un groupe non autorisé, lecture confirmée non affectée.
Non-régression complète reconfirmée.

architecture/README.md, BACKLOG.md (item 38, 14 services désormais
branchés), .env.example et ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Treizième branchement de rights-api : classifier-api, 4 routes gardées (version: c71a44fc69be, livraison #315)

Suite de l'item 38 du backlog. Service CENTRAL ("à prioriser fort",
#260) -- son dictionnaire est utilisé par d'autres modules (ex.
Exploration réseau). Tamponner/vider le dictionnaire partagé
corromprait silencieusement les classifications de TOUS les
consommateurs.

Gardé sur import_dictionary/delete_term/delete_source (mutation
directe du dictionnaire) et confirm (peut aussi ajouter au
dictionnaire via add_to_dictionary -- gardé en BLOC plutôt qu'une
garde conditionnelle sur ce seul paramètre, même prudence que pour
snmp-api #313). Jamais sur classify/classify_batch.

OPT-IN comme tous les branchements précédents --
CLASSIFIER_RIGHTS_API_URL vide par défaut, comportement inchangé
tant qu'elle n'est pas configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 4 routes
gardées (multipart et JSON) avec un groupe non autorisé, classify/
classify_batch confirmés TOUJOURS libres. Non-régression complète
reconfirmée.

classifier/README.md, BACKLOG.md (item 38, condensé -- 13 services
désormais branchés, détail complet dans chaque README plutôt que
répété dans le backlog), .env.example et ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Douzième branchement de rights-api : nebula-api, 5 routes gardées (version: 33328a9eda55, livraison #314)

Suite de l'item 38 du backlog. Ce module ne configure JAMAIS Nebula
lui-même (connexion et consultation seulement) -- les routes
d'écriture touchent UNIQUEMENT le cache LOCAL (import de CSV
exportés depuis Nebula, suppression de lots importés). Un import
falsifié ou une suppression pourrait quand même induire en erreur.

Gardé sur les 3 routes d'import CSV (mutualisées via
_import_csv_route, groups lu depuis request.form -- multipart) et
les 2 routes de suppression (groups lu depuis le corps JSON) --
jamais la consultation.

OPT-IN comme tous les branchements précédents -- NEBULA_RIGHTS_API_URL
vide par défaut, comportement inchangé tant qu'elle n'est pas
configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 5 routes
gardées (multipart et JSON) avec un groupe non autorisé, lecture
confirmée non affectée. Non-régression complète reconfirmée.

nebula/README.md, BACKLOG.md (item 38), .env.example et
ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Onzième branchement de rights-api : snmp-api, scope volontairement étroit (version: 8c889c6d1498, livraison #313)

Suite de l'item 38 du backlog. Gardé UNIQUEMENT sur create_target/
delete_target (gestion des cibles enregistrées) -- jamais sur
/query ni /walk-interfaces.

Raison de cette limite, assumée explicitement plutôt que devinée à
l'aveugle : ces deux routes acceptent soit une communauté fournie à
la volée (self-service, rien à gater), soit un target_id enregistré
dont la communauté chiffrée est utilisée côté serveur sans jamais
être révélée à l'appelant -- ce second cas mériterait une garde
CONDITIONNELLE, plus fine qu'un simple gate en tête de route. Pas
construite ici, faute de temps pour la bâtir ET la tester
correctement dans cette même session -- noté explicitement comme
limite connue plutôt que bâclée.

Vérifié au passage : network-agent-api, comme owncloud-api
précédemment, est déjà lecture seule par conception -- rien à
brancher, aucune route d'écriture n'existe.

OPT-IN comme tous les branchements précédents -- SNMP_RIGHTS_API_URL
vide par défaut, comportement inchangé tant qu'elle n'est pas
configurée.

Vérifié réellement : comportement opt-in par défaut confirmé,
/query et /walk-interfaces confirmés TOUJOURS libres même avec
rights-api actif et refusant, FAIL CLOSED sur les deux routes
gardées, 403 confirmé pour un groupe non autorisé. Testé avec des
stubs minimaux pour pysnmp/credential_crypto (non installables dans
cet environnement, même limite déjà documentée).

snmp/README.md, BACKLOG.md (item 38), .env.example et
ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Dixième branchement de rights-api : tasks-api, scope volontairement étroit (version: 3eedad061e2b, livraison #312)

Suite de l'item 38 du backlog. Ce kanban est délibérément
COLLABORATIF (aucune notion de propriétaire dans le schéma --
créer/déplacer/modifier une carte est l'usage normal de l'outil, pas
une élévation de privilège). Gardé UNIQUEMENT sur DELETE /tasks/<id>
-- suppression définitive, sans mécanisme d'archive, la seule action
qualitativement différente du fonctionnement collaboratif attendu.

Vérifié au passage : tickets-api identifié comme un GROS chantier
séparé (85 routes, très au-dessus de tout ce qui a été branché
jusqu'ici) -- jamais abordé dans la même session qu'un autre
service, mérite sa propre session dédiée.

OPT-IN comme tous les branchements précédents -- TASKS_RIGHTS_API_URL
vide par défaut, comportement inchangé tant qu'elle n'est pas
configurée.

Vérifié réellement : comportement opt-in par défaut confirmé,
create/update/move confirmés TOUJOURS libres même avec rights-api
actif et refusant, FAIL CLOSED sur delete_task si rights-api
injoignable, 403 confirmé pour un groupe non autorisé. Non-régression
complète reconfirmée.

tasks/README.md, BACKLOG.md (item 38), .env.example et
ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Neuvième branchement de rights-api : ged-api, 5 routes gardées (version: d593ff11850c, livraison #311)

Suite de l'item 38 du backlog. Documents liés aux tickets,
potentiellement du contenu métier sensible -- gardé sur les 5 routes
d'ÉCRITURE (créer/supprimer un document, ajouter une version, créer/
supprimer un lien polymorphe), jamais la lecture.

groups lu depuis request.form pour les deux routes multipart
(create_document, add_version -- upload de fichier, jamais de corps
JSON) et depuis le corps JSON pour les trois autres, même motif déjà
établi pour glpi-api (#294).

Vérifié au passage : owncloud-api n'a rien à brancher, déjà lecture
seule par conception (même motif que ipam/optick/zenoss) -- aucune
route d'écriture n'existe.

OPT-IN comme tous les branchements précédents -- GED_RIGHTS_API_URL
vide par défaut, comportement inchangé tant qu'elle n'est pas
configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 5 routes
gardées (multipart et JSON) avec un groupe non autorisé, lecture
confirmée non affectée. Non-régression complète reconfirmée.

ged/README.md, BACKLOG.md (item 38), .env.example et
ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Huitième branchement de rights-api : imap-client-api, 10 routes gardées (version: e5e82abf47aa, livraison #310)

Suite de l'item 38 du backlog. Cette boîte est OPÉRATIONNELLE (reçoit
des notifications de systèmes qui ne savent alerter que par e-mail,
jamais une boîte personnelle) -- mais une règle ou un interprète
trafiqué pourrait faire disparaître silencieusement une alerte
critique.

Gardé sur les 10 routes d'ÉCRITURE qui changent l'état de la boîte
ou son traitement automatique : POST/DELETE /folders,
POST /messages/<uid>/move, POST/PUT/DELETE /rules, POST /rules/apply,
POST/PUT/DELETE /interpreters. JAMAIS sur la lecture, ni sur
/messages/<uid>/interpret -- fonctionnellement une lecture (analyse
un message déjà lisible sans y toucher) malgré le verbe POST.

OPT-IN comme tous les branchements précédents --
IMAP_CLIENT_RIGHTS_API_URL vide par défaut, comportement inchangé
tant qu'elle n'est pas configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 confirmé sur les 10 routes
gardées avec un groupe non autorisé, routes de lecture confirmées
NON affectées même avec rights-api actif et refusant. Non-régression
complète reconfirmée.

imap-client/README.md, BACKLOG.md (item 38), .env.example et
ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Septième branchement de rights-api : backup-restore-api (version: ec3128344224, livraison #309)

Suite de l'item 38 du backlog. Service de SUIVI de couverture
uniquement (jamais l'automatisation réelle de Clonezilla/BackupPC,
voir docstring en tête de fichier) -- mais falsifier ou supprimer un
enregistrement de sauvegarde pourrait masquer un vrai trou de
couverture (créer un enregistrement pour prétendre qu'une sauvegarde
existe, ou en supprimer un pour cacher qu'elle a échoué).

Gardé sur les deux routes d'ÉCRITURE (create_image, delete_image)
uniquement -- /coverage et /logs restent en lecture libre, même
motif que partout ailleurs dans ce projet.

OPT-IN comme tous les branchements précédents --
BACKUP_RESTORE_RIGHTS_API_URL vide par défaut, comportement
inchangé tant qu'elle n'est pas configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 sur les deux routes gardées,
/coverage confirmée non affectée (même code de statut avant/après
activation -- corrige une première assertion de test erronée qui
supposait /coverage fonctionnelle sans NETWORK_AGENT_API_URL
configurée, sans rapport avec rights-api). Non-régression complète
reconfirmée.

backup-restore/README.md, BACKLOG.md (item 38), .env.example et
ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Sixième branchement de rights-api : vault-api, scope volontairement étroit (version: 6483dc98a07a, livraison #308)

Suite de l'item 38 du backlog -- vault-api (le coffre-fort lui-même,
distinct de vault-admin-api déjà branché en #291) restait le service
le plus sensible parmi ceux cités à l'origine (coffre-fort, clés
SSH, LDAP) sans branchement.

Ce module a une posture différente du reste du projet (chiffrement
de bout en bout borne déjà la confidentialité même sans vérification
d'identité réseau, voir docstring en tête de fichier) -- chaque
route examinée individuellement plutôt qu'un branchement en bloc.

Gardées : revoke_collection_access et reset_user (DELETE) -- aucune
des deux n'implique la moindre clé de chiffrement, une simple
suppression en base suffit à l'action. Confirmé qu'aucune des deux
n'a d'appelant actuel dans le portail -- pas un risque exploité
aujourd'hui via l'interface, mais un vrai trou pour un appel API
direct.

Délibérément PAS gardées : grant_collection_access (exige déjà de
connaître la clé réelle de la collection, borné par le chiffrement
lui-même) et les actions self-service confirmées (create_user,
create_collection, rotate-password -- l'utilisateur agit sur son
propre compte/collection, jamais au nom d'un tiers).

OPT-IN comme tous les branchements précédents -- VAULT_API_RIGHTS_API_URL
vide par défaut, comportement inchangé tant qu'elle n'est pas
configurée.

Vérifié réellement : comportement opt-in par défaut confirmé, FAIL
CLOSED si rights-api injoignable, 403 sur les deux routes gardées,
confirmation explicite que grant_collection_access reste à 404
(jamais 403). Non-régression complète reconfirmée.

vault/README.md, BACKLOG.md (item 38), .env.example et
ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — netprobe : quatrième et dernier volet actif, analyseur multi-scripts (version: a38b63c0efe3, livraison #307)

Dernier volet ACTIF de netprobe -- les 6 points de la demande
initiale (#295) sont désormais tous construits. Ordonnanceur de
scripts d'analyse des données des volets précédents.

analyzers/ -- un module par analyseur, chacun exposant analyze(db_path)
-> list de findings, PUR (aucun effet de bord) -- testable en
isolation, séparé du moteur d'orchestration. Registre explicite dans
analyzers/__init__.py, jamais de découverte automatique.

Deux analyseurs livrés : latency_degradation.py (compare une fenêtre
récente à une fenêtre de référence, hausse RELATIVE jamais un seuil
absolu) et new_open_ports.py (compare les deux derniers scans nmap,
pertinence sécurité directe).

analyzer_engine.py sépare calcul et enregistrement -- un analyseur en
panne n'empêche jamais les autres de tourner.

Intégré au système de contrôle existant -- analyzer était déjà présent
dans PROBE_TYPES depuis la fondation (#295), jamais branché avant
cette livraison. Configuration globale uniquement, réutilise
get_effective_config/is_within_schedule déjà écrits pour smokeping.

Nouvel onglet "Analyse" dans le hub (liste des constats + lancement
à la demande).

Vérifié réellement : 7 tests sur le stockage, 7+7 tests sur les deux
analyseurs, 6 tests sur le moteur d'orchestration (dont la résilience),
8 tests sur le tick de l'ordonnanceur, 8 tests d'intégration sur les
routes. Structure JSX revérifiée -- toutes les cartes suivent
désormais le motif hub-card/hub-settings-section appris en #306.
Non-régression complète reconfirmée.

netprobe/README.md mis à jour.

## 2026-09-04 — Interface hub netprobe : 3 bugs réels corrigés (version: adeaf06ebc3d, livraison #306)

Trois bugs signalés par la personne sur les onglets Cibles et Sondes.

Débordement horizontal -- aucune règle CSS existante ne gérait le
défilement horizontal des tableaux. Nouvelle classe réutilisable
hub-table-scroll ajoutée, appliquée aux 7 tableaux de
NetprobeView.jsx.

Cartes plafonnées à 420px et texte centré -- piège DÉJÀ documenté
dans hub.css (commentaire existant sur .hub-settings-section, jamais
lu avant d'écrire ce composant) : .hub-card seule plafonne à 420px
et centre le texte, le correctif établi (combiner avec
.hub-settings-section) n'avait pas été appliqué. Corrigé sur les 7
cartes du composant.

Suppression et bascule rapide d'une configuration de sonde -- manque
réel confirmé (aucune route de suppression n'existait, même côté
backend). Ajouté : DELETE /probe-config/<id> et PUT /probe-config/<id>
(bascule sans resoumettre tout le formulaire), jamais de cascade sur
les échantillons déjà enregistrés. Colonne Actions ajoutée au tableau.

Vérifié réellement : 9 tests sur le stockage, 7 tests d'intégration
sur les routes. Structure JSX revérifiée. Non-régression complète
reconfirmée.

netprobe/README.md mis à jour.

## 2026-09-04 — netprobe : troisième volet actif, tcpdump partagé sans stockage (version: 1d06e051e53f, livraison #305)

Troisième volet ACTIF de netprobe -- capture partagée à la demande,
utilisable par d'autres modules (point 3 de la demande initiale).

tcpdump_probe.py -- appelle le vrai binaire tcpdump système via
sous-processus, même motif que ping_probe.py/nmap_probe.py.
Extraction par motifs robustes (adresses IP, mots-clés de protocole)
plutôt qu'un parsing ligne-par-ligne fragile, vu la variabilité du
format tcpdump selon le protocole.

Piège réel trouvé et corrigé en testant : TimeoutExpired.stdout reste
en bytes même avec text=True sur le subprocess.run() qui a levé
l'exception -- décodage explicite ajouté, sinon échec silencieux sur
le parsing. Un timeout sur une interface calme traité comme résultat
partiel valide, jamais une erreur.

Sans stockage, volontairement -- aucune table en base pour ce volet,
le résultat est renvoyé à l'appelant, jamais persisté.

cap_add: NET_ADMIN ajouté en plus de NET_RAW -- même motif déjà
établi pour network-agent-api en #238. Nouvel onglet "Capture" dans
NetprobeView.jsx.

Vérifié réellement : 13 tests sur le parsing (dont le piège bytes/
timeout spécifiquement reproduit puis confirmé corrigé), 6 tests
d'intégration sur les routes (dont la confirmation explicite qu'aucune
table tcpdump n'existe en base). Non-régression complète reconfirmée.

netprobe/README.md mis à jour.

## 2026-09-04 — Bug réel : build netprobe-api instable, résilience réseau ajoutée (version: 00b281079886, livraison #304)

Le build de netprobe-api échouait systématiquement (DeadlineExceeded)
au sein du stack complet, confirmé reproductible même en isolation --
réussi seulement à la 3ème tentative. Cause identifiée avec la
personne : nmap tire des dépendances (scripts NSE, libpcap) assez
lourdes pour être exposées à une coupure réseau transitoire lors de
apt-get, dans un environnement de build au réseau instable.

Corrigé avec une boucle de reprise (3 essais, 5s de pause) autour de
apt-get, et --retries 5 --timeout 60 sur pip install -- jamais une
boucle infinie qui masquerait un vrai problème de configuration.
Syntaxe shell de la boucle vérifiée isolément avant application.

netprobe/README.md mis à jour.

## 2026-09-04 — Backlog : supervision WiFi Campus Alpha, 5 items (version: ed6a81eaa297, livraison #303)

Suite à la note d'architecture livrée (docx, hors dépôt) proposant
une supervision WiFi continue à quatre couches corrélées (RF,
infrastructure, expérience client, backend/WAN) -- achats matériel
décidés (adaptateur RTL8812AU, HackRF One), backlog préparé en
conséquence. 5 nouveaux items (47-51) : volet WiFi dans netprobe,
agent de sonde distribué pour Raspberry Pi (évolution concrète de
l'item 45, appuyée sur le modèle sparrow-wifi), intégration API
ZYXEL Nebula (étape la moins coûteuse, à faire en premier),
rapprochement sparrow-wifi/HackRF pour l'analyse de spectre,
interface hub de corrélation multi-couches et guidage technicien.

Aucun code touché -- uniquement BACKLOG.md, questions ouvertes
volontairement non tranchées (agent sparrow-wifi réutilisé ou agent
netprobe propre, intégration ou système indépendant pour
sparrow-wifi).

**Chaque entrée référence le hash de version** (badge affiché sur les
5 fronts, voir `shared/README.md`) correspondant à l'état du dépôt à
ce moment-là — permet de savoir précisément quelles entrées sont
comprises dans une version donnée. `CHANGELOG.md`/`ENV_CHANGELOG.md`
sont volontairement exclus du calcul de ce hash (sinon y écrire le
hash changerait le hash lui-même) : une entrée référence donc TOUJOURS
le hash tel qu'il sera affiché une fois `run.sh` relancé, même après
avoir ajouté cette entrée.

## 2026-09-04 — netprobe : deuxième volet actif, nmap à la demande (version: a787835a3e41, livraison #302)

Deuxième volet ACTIF de netprobe -- scan de ports à la demande
(point 2 de la demande initiale).

nmap_probe.py -- appelle le vrai binaire nmap système via
sous-processus, même motif que ping_probe.py. Sortie XML (-oX -)
plutôt que texte -- structure documentée et stable, parsée avec
xml.etree.ElementTree (bibliothèque standard). Non vérifié contre un
vrai nmap (binaire absent de cet environnement) -- logique de
parsing testée contre de vraies structures XML (multi-ports, host
down, XML malformé).

Volontairement à la demande -- jamais programmé automatiquement
(contrairement à smokeping) : un scan de ports est bien plus
intrusif qu'un ping, peut déclencher des alertes côté cible.

Table nmap_scans (open_ports en JSON, pas de table normalisée
séparée -- nombre de ports variable et petit par scan). Nouvel
onglet "Scans" dans NetprobeView.jsx (lancement + historique par
cible).

Vérifié réellement : 10 tests sur le parsing, 4 sur le stockage, 8
sur les routes. Structure JSX revérifiée après l'ajout de l'onglet.
Non-régression complète reconfirmée. Route passerelle déjà en place
depuis #301 (même API netprobe-api) -- vérifiée, pas de nouveau
manque cette fois.

netprobe/README.md mis à jour et consolidé (sections "reste à
faire" dupliquées/obsolètes nettoyées).

## 2026-09-04 — netprobe : interface hub, et une route passerelle manquante trouvée en finalisant (version: 7627f009dad7, livraison #301)

Interface hub pour netprobe (#295/#297) -- NetprobeView.jsx (trois
onglets : Cibles/Sondes/Suivi) + netprobeClient.js, câblés dans
App.jsx (tuile "Sondes réseau"). Cette livraison avait été commencée
puis interrompue avant finalisation -- reprise et complétée
maintenant.

Manque critique trouvé et corrigé en vérifiant la chaîne complète :
la route passerelle /api/netprobe/ -> netprobe-api n'existait PAS
dans tls-proxy/render_nginx_conf.py -- le hub aurait appelé dans le
vide, 404 systématique sur toute action. Même classe de manque déjà
rencontrée pour schema-analyzer (#151) et ged (#157/#160) --
reconfirme l'utilité de toujours vérifier la table de routage en
dernière étape d'une livraison qui ajoute un nouveau service.

Vérifié réellement : structure JSX revérifiée, netprobeClient.js
vérifié en syntaxe, chaîne complète confirmée (constante d'API
définie, tuile conditionnelle, route passerelle présente et
confirmée par render_nginx_conf.py --check).

netprobe/README.md mis à jour.

## 2026-09-04 — La vraie cause du menu langue/bouton invisible enfin trouvée : "restart" ne recrée jamais un conteneur (version: b8199e348555, livraison #300)

Diagnostic complet mené en conditions réelles sur plusieurs échanges,
chaque fausse piste éliminée méthodiquement avant de trouver la
vraie cause -- cache serveur Keycloak (start-dev le désactive déjà
par défaut), cache navigateur (fenêtre privée neuve, aucun
changement), cache nginx (aucune directive proxy_cache), mauvais
thème sélectionné (confirmé "hub" actif) : tous écartés un à un.

VRAIE CAUSE, confirmée par docker exec ... cat login.css montrant le
contenu du TOUT PREMIER login.css (#275), jamais mis à jour depuis :
"restart" ne RECRÉE JAMAIS un conteneur -- il relance le MÊME
conteneur, dont les montages restent figés à sa création INITIALE.
keycloak vit dans gateway/docker-compose.yml, jamais ciblé par
scripts/run.sh (donc jamais par l'alias deploie habituel) -- son
conteneur n'avait donc jamais été RECRÉÉ depuis sa toute première
création, quel que soit le nombre de "restart" lancés depuis. Seul
"up -d" relit la config actuelle et recrée le conteneur si
nécessaire (montages compris).

Correctif appliqué et confirmé fonctionnel par la personne (capture
d'écran) : docker compose ... up -d a bien recréé le conteneur, tous
les correctifs empilés depuis #281 (bouton visible, carte à largeur
bornée, menu langue qui reste fermé) sont enfin apparus.

scripts/chantier.sh corrigé -- la fonction --all (#299) utilisait
elle-même "restart" au lieu de "up -d", aurait échoué pour la même
raison : corrigée, renommée recreate_keycloak() pour plus de clarté.
Un vrai bug bash trouvé et corrigé en passant : "${ARGS[@]:-}"
injectait un argument vide superflu sur un tableau vide sous set -u
-- confirmé par test isolé, corrigé en retirant le ":-" (bash 4.4+
gère nativement un tableau vide sans lui).

Dernier point signalé après vérification visuelle réussie : les
étiquettes de formulaire restaient alignées à gauche sur toute la
largeur de la carte, ne correspondant plus aux champs centrés/réduits
de #296. Corrigé en appliquant le même centrage aux étiquettes, sur
les deux thèmes.

keycloak/themes/README.md entièrement réécrit sur la section
redémarrage -- corrige la documentation de #298/#299 qui recommandait
encore la mauvaise commande (restart au lieu de up -d).

## 2026-09-04 — Badge de version sur la mire Keycloak + couverture /version complétée sur 8 services (version: 55f523d31ba0, livraison #298)

Deux demandes explicites en cours de session, pendant l'investigation
non résolue du menu langue Keycloak (toujours bloqué ouvert malgré
#296 et un vrai redémarrage confirmé -- cause encore non identifiée).

Badge de numéro de livraison sur la mire Keycloak (hub et hub-dark)
-- CSS pur (::after sur .card-pf), jamais une réécriture de gabarit
FreeMarker, cohérent avec le principe déjà établi. Mis à jour
manuellement à chaque livraison qui touche ce thème.

Suggestion de la personne ("les modules doivent pouvoir être
interrogé et donner leur version") -- vérification a révélé que le
mécanisme version_endpoint.py existait déjà, mais que 8 services
n'étaient jamais câblés dessus : owncloud-api, pixel-grid-api,
ipam-api, cacti-api, geo-import-api, tts-gu-api, optick-api,
zenoss-api. Corrigé pour les 8 -- câblage app.py ET les deux lignes
COPY manquantes dans chaque Dockerfile (sans elles, le câblage
Python aurait échoué au démarrage réel).

Vérifié réellement : les 8 modules s'importent sans erreur, /version
testé directement sur 2 d'entre eux, les 8 Dockerfile vérifiés
systématiquement. Couverture désormais complète sur tout le projet.

keycloak/themes/README.md et shared/README.md mis à jour.

## 2026-09-04 — netprobe : premier volet actif, smokeping (version: 516bfa495503, livraison #297)

Premier volet ACTIF de netprobe (#295) -- sondage de latence
permanent (point 1 de la demande initiale).

ping_probe.py -- appelle le vrai binaire ping système via
sous-processus, même motif déjà établi ailleurs dans ce projet
(ssh-keygen, ldapsearch, mysqldump). Non vérifié contre un vrai ping
(binaire absent de cet environnement) -- logique de parsing testée
contre de vraies sorties ping avec repli de format. Un seul ping par
échantillon par défaut -- décision de charge cohérente avec la
préoccupation à l'origine du module séparé (#295).

scheduler.py -- une passe testable en isolation, enveloppée dans une
boucle de fond (thread daemon, jamais bloquant au démarrage).
Respecte le système de contrôle (#295) à chaque cible : désactivée,
hors fenêtre horaire, ou fréquence pas encore écoulée -- jamais
sondée dans ces cas.

Table smokeping_samples (permanent, jamais recalculé à la volée,
même raisonnement que le journal de vigilance) + purge (écrite,
pas encore câblée à un appel périodique).

cap_add: NET_RAW ajouté à docker-compose.yml -- requis par ping en
conteneur non privilégié.

Vérifié réellement : 8 tests sur le parsing, 9 sur le stockage (dont
la purge), 12 sur l'ordonnanceur (activation, fréquence, override
par cible, fenêtre horaire), 4 sur les routes. Non-régression
complète reconfirmée.

netprobe/README.md mis à jour.

## 2026-09-04 — Skin Keycloak : menu langue vraiment corrigé, mise en page, thème sombre par défaut (version: 63c219e0186b, livraison #296)

Reprise du 4ème point signalé en #281 (jamais éclairci à l'époque) --
demandé explicitement "pour les démos internes".

Menu de langue CORRIGÉ, cette fois avec le vrai gabarit Keycloak en
main (dépôt officiel keycloak/keycloak, base/login/template.ftl) --
la supposition de #281 (classe .pf-m-expanded) était fausse, aucune
trace de cette classe dans le vrai gabarit. L'état ouvert/fermé est
porté par l'attribut ARIA standard aria-expanded sur le bouton --
corrigé avec un sélecteur de fratrie CSS ciblant directement cet
état plutôt qu'une classe devinée.

Champs et boutons centrés/réduits (max-width 320px, centrage) --
n'avaient aucune largeur propre avant, héritaient de 100% de la
carte (480px).

Thème par défaut changé vers hub-dark (demandé explicitement),
keycloak/realm-template.json. Vérifié : vault-standalone n'a pas de
réglage équivalent, rien à synchroniser.

Les trois correctifs appliqués identiquement aux deux thèmes (hub et
hub-dark) -- cohérence entre les deux, pas seulement celui devenu
défaut.

Reste à faire : bouton de bascule jour/nuit EN PAGE (sans passer par
l'admin Keycloak) -- demanderait du JavaScript nouveau, jamais
testable ici sur un écran de connexion, volontairement pas construit
à l'aveugle sur une page sensible par nature.

keycloak/themes/README.md et BACKLOG.md (item 46) mis à jour.

## 2026-09-04 — netprobe : fondation du sondage réseau actif, module séparé de network-agent (version: d4c5af4e740e, livraison #295)

Demandé explicitement : smokeping permanent, nmap à la demande,
tcpdump partagé sans stockage, collecteur d'IP, analyseur multi-
scripts, système de contrôle (activer/désactiver/fréquence/
programmer). Décision d'architecture tranchée avec la personne ("à
toi de décider en fonction de l'impact de charge") : module SÉPARÉ
de network-agent -- celui-ci fait de la capture passive continue
dans son propre conteneur, y ajouter du sondage actif créerait une
concurrence CPU/mémoire risquant de dégrader sa précision existante.

Portée de cette livraison : la fondation dont tout le reste dépend
-- collecteur d'IP (table targets, idempotent, import best-effort
depuis network-agent) et système de contrôle (table probe_config,
override précis vs configuration globale par type de sonde, fenêtre
horaire avec gestion du passage minuit).

Bug réel trouvé et corrigé en testant : SQLite ne considère jamais
deux NULL comme égaux dans une contrainte UNIQUE -- chaque
reconfiguration globale créait une nouvelle ligne au lieu de mettre
à jour l'existante. Corrigé avec une sentinelle interne, traduite
en/depuis None à la frontière de l'API Python.

Deux notes d'évolution capturées au backlog en cours de
développement : modularisation en services séparés par type de
sonde + répartition en agents multi-hôtes (item 45), et supervision
de charge des modules du hub eux-mêmes (item 44) -- aucune des deux
tranchée en détail, questions ouvertes documentées.

Les volets actifs eux-mêmes (smokeping, nmap, tcpdump partagé,
analyseur) restent à construire -- chantier trop vaste pour une
seule livraison.

Vérifié réellement : 19 tests sur store.py (dont le bug NULL/UNIQUE
spécifiquement reproduit puis confirmé corrigé), 15 tests
d'intégration sur les routes.

netprobe/README.md (nouveau), BACKLOG.md (items 44, 45, 46),
docker-compose.yml mis à jour.

## 2026-09-04 — Cinquième branchement de rights-api : glpi-api (version: c0391175de4f, livraison #294)

Suite au backlog item 38, cinquième service branché après
ssh-tunnels-api (#289), ldap-admin-api (#290), vault-admin-api
(#291), dba-api (#292). Aucune décision explicite préexistante
trouvée dans ce module contraire à ce branchement.

6 routes protégées (suppression d'item, 5 imports vers GLPI --
excel, nebula-devices, nebula-clients, network-agent-devices,
snmp-targets), y compris en mode dry_run (gating au niveau de la
route, pas de l'effet réel). Cas particulier : /import/excel reçoit
un envoi multipart, groups extrait d'un champ de formulaire, même
motif que dba-api (#292).

Incident évité en cours de route : une édition mal formée a d'abord
tronqué la docstring d'import_nebula_devices_route -- repéré en
relisant le résultat immédiatement après chaque édition, corrigé
avant de continuer.

Même motif que les services précédents pour le reste : gating au
niveau du service entier, FAIL CLOSED, OPT-IN via GLPI_RIGHTS_API_URL.

Vérifié réellement : câblage testé sur les 6 routes (refusé) et sur
delete_item_route (autorisé). Non-régression reconfirmée.

glpi/README.md, .env.example et ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Authentification Keycloak de vault-admin-portal : comble le manque de #291 (version: 94047146ca18, livraison #293)

Comble le manque signalé en #291 (backlog item 42) : vault-admin-portal
gagne une authentification Keycloak réelle, rendant enfin utilisable
en pratique le gating rights-api construit en #291.

Découverte importante en cours de route : contrairement à ce que
laissait penser la description initiale ("un nom en texte libre"),
le champ login/password existant sert en réalité à dériver une vraie
clé privée cryptographique (unlockWithPassword) pour débloquer
certaines fonctions -- pas du texte libre sans conséquence. Keycloak
s'ajoute donc en plus, délibérément jamais en remplacement de ce
mécanisme existant, laissé totalement intact.

Client Keycloak vault-admin-portal ajouté à
keycloak/realm-template.json -- seulement dans le realm du
déploiement principal, jamais dans vault-standalone (confirmé :
aucun portail admin n'y existe). Nouvelle variable de gabarit
VAULT_ADMIN_PORTAL_PUBLIC_URL (keycloak/render.py) -- sans chemin
/vault, ce portail tournant sur un port direct dédié.

Porte de connexion Keycloak ajoutée dans App.jsx, après tous les
hooks React existants (règles de hooks respectées), avant le garde
de déverrouillage par mot de passe existant. Les groupes Keycloak
vérifiés sont désormais transmis à POST /users/.../roles (le seul
endpoint protégé par #291).

Vérifié réellement : rendu complet du realm testé -- le nouveau
client se substitue correctement, aucun jeton non substitué nulle
part après ce changement. Structure JSX revérifiée. Confirmé
qu'aucun hook n'est appelé après le nouveau garde.

Backlog item 42 marqué comme livré. vault/README.md, .env.example,
keycloak/realm-template.json et keycloak/render.py mis à jour.

## 2026-09-04 — Quatrième branchement de rights-api : dba-api, le plus sensible techniquement (version: db8347e982cc, livraison #292)

Suite au backlog item 38, quatrième service branché après
ssh-tunnels-api (#289), ldap-admin-api (#290), vault-admin-api
(#291). Candidat particulièrement sensible : /connections/<id>/sql
exécute du SQL LIBRE contre des bases EXTERNES à ce projet,
potentiellement de production. Aucune décision explicite préexistante
trouvée dans ce module contraire à ce branchement -- procédé
directement.

12 routes protégées (connexions créer/modifier/supprimer/tester,
lignes modifier/ajouter/supprimer, colonnes ajouter/supprimer/
modifier, exécution SQL, import de dump MySQL). Les routes de
consultation restent ouvertes.

Cas particulier traité : import-mysql-dump reçoit un envoi MULTIPART
(fichier), jamais de corps JSON comme les autres routes -- groups
extrait d'un champ de formulaire ordinaire plutôt que du body JSON
habituel.

Même motif que les trois services précédents pour le reste : gating
au niveau du service entier, FAIL CLOSED, OPT-IN via
DBA_RIGHTS_API_URL.

Vérifié réellement : _check_manage_right testé en isolation (FAIL
CLOSED confirmé). Câblage réel testé sur les 12 routes (refusé) et
sur /sql (autorisé -- confirmé qu'on retombe sur le comportement
normal, jamais un 403 résiduel une fois le droit accordé). Non-
régression des routes de consultation reconfirmée.

dba/README.md, .env.example et ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Troisième branchement de rights-api : vault-admin-api, avec un manque signalé (version: 38f2e2f5a853, livraison #291)

Suite au backlog item 38, troisième service branché après
ssh-tunnels-api (#289) et ldap-admin-api (#290). Confirmé
explicitement par la personne avant de coder : même évolution que
pour LDAP, pour réserver la gestion des rôles (dont
is_system_master, accès permanent à chaque collection) à une
catégorie d'utilisateurs plus précise que le garde-fou existant
(LAN + acteur déclaré).

Portée volontairement limitée à POST /users/<login>/roles -- les
routes de lecture de l'archive de récupération gardent leur
protection cryptographique de fond, jamais touchées.

Ordre de vérification différent de #290 : require_lan_and_actor
(qui journalise CHAQUE tentative, documenté comme important) reste
en premier, le droit rights-api vérifié ensuite, avant l'écriture
réelle.

Manque réel trouvé et signalé clairement plutôt que passé sous
silence : vault-admin-portal n'a aucune authentification Keycloak
(juste un nom en texte libre) -- activer ce gating sans adapter
aussi le portail bloquerait tout le monde. Backend prêt et testé ;
l'activation reste à ne PAS faire tant que le portail n'a pas
d'évolution séparée (backlog item 42, pas commencé).

Vérifié réellement : _check_manage_right testé en isolation (gating
désactivé, autorisé, refusé, FAIL CLOSED). Câblage réel testé sur
set_user_roles -- confirmé qu'un refus n'écrit rien en base. Non-
régression des routes de lecture reconfirmée.

vault/README.md, BACKLOG.md (item 42), .env.example et
ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Deuxième branchement de rights-api : ldap-admin-api, une évolution voulue (version: efe86466c875, livraison #290)

Suite au backlog item 38, deuxième service branché après
ssh-tunnels-api (#289). Point clarifié explicitement avec la
personne avant de coder : ldap-admin/README.md documentait une
décision antérieure ("groupe administrateurs vérifié côté front,
jamais une deuxième couche d'autorisation côté serveur") --
confirmé que ce n'est PAS une contradiction mais une évolution
voulue, pour réserver les actions d'écriture à un groupe plus précis
que "administrateurs" (trop large), les mêmes personnes restant
concernées pour longtemps.

4 routes protégées (reset mot de passe, édition d'entrée, sauvegarde
manuelle, apply LDIF) ; les routes de consultation restent ouvertes.

Bug trouvé et corrigé EN COURS de test : trois des quatre routes
vérifiaient la configuration LDAP AVANT le droit d'accès, empêchant
le refus 403 de s'exprimer tant que la config n'était pas prête
(503 à la place) -- corrigé en vérifiant les droits en premier,
pour ne jamais révéler l'état de configuration à un appelant non
autorisé.

Même motif que #289 pour le reste : gating au niveau du service
entier, FAIL CLOSED, OPT-IN via LDAP_ADMIN_RIGHTS_API_URL.

Vérifié réellement : _check_manage_right testé en isolation, y
compris qu'un membre du groupe "administrateurs" seul ne suffit
plus. Câblage réel testé sur les 4 routes après correction de
l'ordre. Non-régression des routes de consultation reconfirmée.

ldap-admin/README.md, .env.example et ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Premier branchement réel de rights-api : ssh-tunnels-api (version: bfa83cc2d82f, livraison #289)

Suite au backlog item 38 ("brancher rights-api sur les ~40 autres
API du projet") -- ssh-tunnels-api choisi comme prévu (clés SSH,
génération/suppression réelle depuis #277). vault-api délibérément
écarté comme premier candidat : modèle d'accès cryptographique par
utilisateur déjà en place, brancher les droits par groupes aurait
fait doublon.

Gating au niveau du service entier (resource_type
"ssh-tunnels-api", action "manage"), pas par ressource individuelle
-- choix délibéré pour ce premier branchement. 12 routes protégées
(génération/suppression de clé, connexions, tunnels, montages) ;
les routes de simple consultation restent ouvertes.

FAIL CLOSED, jamais fail-open : rights-api injoignable, HTTP
inattendu ou réponse illisible -- refuse systématiquement, même pour
admin_hub. OPT-IN via SSH_TUNNELS_RIGHTS_API_URL, jamais actif par
défaut -- un premier essai avait activé le gating en dur dans
docker-compose.yml, corrigé avant livraison : aurait bloqué les
actions de la personne sans prévenir, faute de groupe admin_hub déjà
assigné dans Keycloak.

Vérifié réellement : _check_manage_right testé en isolation (gating
désactivé, autorisé, refusé, et les trois scénarios de panne
confirmant le fail closed). Câblage réel testé sur delete_key/
create_connection -- confirmé qu'un refus n'exécute jamais l'action.
Non-régression complète reconfirmée (gating désactivé = comportement
identique à #277).

ssh-tunnels/README.md, .env.example et ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — Correctif réel : crash React sur l'aperçu GLPI depuis NebulaView (version: 256d30c70e6f, livraison #288)

Signalé par la personne en plein test réel : le bouton d'aperçu
dry-run du pont Nebula → GLPI menait à un écran vide, avec un crash
React "Objects are not valid as a React child (found: object with
keys {detail, itemtype, key, name})".

Cause : NebulaView.jsx intègre depuis #228 un raccourci de
prévisualisation vers GLPI, construit à une époque où "created"
était toujours une liste de chaînes. La livraison #269 (cases à
cocher côté GlpiInventoryView.jsx) a changé la forme de "created" EN
MODE APERÇU vers des objets {key, name, itemtype, detail} --
GlpiInventoryView.jsx adapté à ce moment-là, NebulaView.jsx (même
route) jamais mis à jour -- oubli de propagation à tous les
consommateurs existants d'un changement de forme de réponse
partagée.

Corrigé : NebulaView.jsx gère désormais les deux formes, jamais un
objet rendu directement. Vérifié réellement : logique de formatage
testée en isolation pour les deux formes. GlpiInventoryView.jsx
revérifié en parallèle -- déjà correct, aucun changement nécessaire.

nebula/README.md mis à jour, avec la leçon retenue sur la
propagation des changements de forme d'API partagée.

## 2026-09-04 — Erreurs systématiquement explicites : audit rétroactif des 16 appels .json() du projet (version: 8b130c8288a8, livraison #287)

Demandé explicitement, généralisant le correctif #286 : "rend
systématiquement les erreurs plus explicites, ça doit être le
comportement général des remontées d'erreur".

Nouvel utilitaire partagé shared/safe_json.py pour les appels
internes (service à service) -- les clients de systèmes tiers
(glpi_client.py, mayan_client.py, nebula_client.py, google_oauth.py,
schema_client.py) gardent leur propre variante locale, liée à leur
classe d'erreur spécifique, jamais unifiée de force.

Audit mené sur les 16 fichiers du projet appelant .json() sur une
réponse HTTP -- la majorité (11) déjà protégée par un except
ValueError existant (bonne discipline déjà en place). Cinq vrais
trous trouvés et corrigés : mayan_client.py (4 points, dont une clé
"id" pouvant aussi manquer), nebula_client.py (corrigé à la source,
_get/_post), zenoss_connector.py, google_oauth.py (3 points),
schema_client.py (4 points, dont un chemin volontairement silencieux
qui ne capturait en réalité que les erreurs réseau, pas les erreurs
JSON -- contredisait sa propre intention documentée, corrigé en
élargissant le filtre plutôt qu'en le remplaçant),
architecture/api/app.py (localisation Zenoss), glpi/api/app.py
(enrichissement classifier best-effort, même piège que
schema_client.py), pipeline/main.py (isolé du chemin de succès,
pour qu'un corps non-JSON ne fasse jamais remonter un push HTTP
réussi comme un échec), tickets/api/app.py (appels admin Keycloak).

Vérifié réellement : chaque correctif testé avec une VRAIE
simulation de réponse 2xx + corps non-JSON, confirmant le message
d'erreur détaillé ET la non-régression du cas de succès. Non-
régression complète de architecture-api, tickets-api, glpi-api et
schema-analyzer-api reconfirmée.

Nebula : confirmé en passant que l'import CSV clients (livraison
#200) couvre déjà exactement le format demandé par la personne --
testé contre un vrai fichier fourni (155/155 lignes exploitables),
rien à construire, déjà utilisable via la tuile Nebula.

shared/README.md mis à jour.

## 2026-09-04 — GLPI : erreur détaillée sur une réponse HTTP 200 inattendue à initSession (version: 4d16ce74a318, livraison #286)

Signalé par la personne en plein test réel contre un vrai GLPI :
/inventory-summary plantait avec une JSONDecodeError brute et
inexploitable ("Expecting value: line 8 column 1 (char 25)"), sans
jamais révéler ce que GLPI avait réellement répondu. Après un premier
correctif (guidage pour créer l'App-Token GLPI, Configuration >
Générale > API), la même erreur EXACTE est réapparue au caractère
près -- signe que la réponse de GLPI n'avait pas changé, donc que
deviner une nouvelle cause à l'aveugle n'aurait pas aidé.

Cause du bug (pas de la panne GLPI elle-même, qui reste à
diagnostiquer par la personne) : init_session() ne gérait le cas
d'erreur QUE pour un code HTTP différent de 200 (_raise_with_detail,
déjà existant, bien conçu) -- un 200 avec un corps NON-JSON (ou sans
la clé "session_token" attendue) tombait tout droit dans
resp.json()["session_token"], provoquant une exception Python brute
jamais interceptée proprement.

Corrigé : capture explicitement ce cas, lève une GlpiError avec un
aperçu du VRAI corps de réponse renvoyé par GLPI (tronqué à 300
caractères, jamais les identifiants) -- déjà interceptée proprement
par /inventory-summary (route existante, aucun changement
nécessaire là), donnant enfin un message exploitable côté personne
au lieu d'un traceback Python brut.

Vérifié réellement : reproduit le cas exact (200 + corps HTML/texte
non-JSON), reproduit le cas d'une clé "session_token" manquante,
non-régression du chemin d'erreur HTTP existant ET du cas de succès
confirmés. Non-régression complète de glpi-api reconfirmée.

## 2026-09-04 — Correctif réel : dépendance requests manquante dans imap-client-api (version: b0763b5706f9, livraison #285)

Signalé par la personne en plein test réel : 502 en ouvrant la tuile
IMAP du hub. Logs du conteneur transmis directement, cause exacte
immédiatement visible : ModuleNotFoundError: No module named
'requests' -- app.py (livraison #179, antérieure à cette session)
importe requests pour POST /ingest/<source> (volet 4/4, connecteur
source), mais requirements.txt ne le listait pas -- jamais détecté
avant faute d'environnement Docker réel pour construire l'image
pendant le développement initial.

Vérifié qu'aucun autre import tiers ne manquait dans les 6 fichiers
Python de ce module avant de considérer le correctif complet.

Ajouté requests==2.32.3 à imap-client/api/requirements.txt.

## 2026-09-04 — Cinq points d'ergonomie ENT/Calendrier : statuts auto, historique permanent, validation groupée (version: ece7ce5d805d, livraison #284)

Cinq demandes explicites, en plein test réel de déploiement : badge
mot-clé au survol, retour en arrière sur création de ticket, File
d'attente fidèle à la vraie tuile Tickets, statut automatique selon
le moment de l'événement source, changements de statut journalisés
avec validation groupée.

Nouvelle table permanente ticket_status_changes, distincte de
ticket_status_log déjà existante (portée différente, jamais
détournée). Statuts Clos/En cours/Planifié créés automatiquement s'ils
n'existent pas. determine_calendar_statut_label() -- fonction pure,
compare un instant de référence à la fenêtre de l'événement source.

Deux moments d'application : à la création (statut posé directement,
déjà validé de facto via #273) et à la consultation
(POST /tickets/<id>/recalculate_status, un changement réel entre
dans la file d'attente, jamais appliqué directement).

Suppression réelle (DELETE /tickets/<id>) strictement limitée aux
tickets non validés -- refusée sur un ticket déjà confirmé, même
prudence que partout ailleurs dans ce projet contre les vrais
DELETE.

Validation groupée (GET /status-changes/pending,
POST /status-changes/validate_all) -- applique tout à la fois,
jamais un écran par changement. Lien vers la tuile Tickets (vue
technicien) réutilisant le contrôle d'accès par rôle déjà existant
côté portail -- rien de nouveau à coder pour ça.

File d'attente -- remplace "Tickets par échéance" (#282), reprend
fidèlement les colonnes de TechnicienView.jsx en réutilisant les
données déjà chargées via /queue, aucun nouvel appel réseau.

Un vrai bug trouvé et corrigé en cours de route : setError utilisé
sans jamais avoir été déclaré dans CalendarView.jsx -- aurait
provoqué une erreur d'exécution au premier clic sur "Annuler" pour
un ticket déjà validé ailleurs.

Vérifié réellement : 36 assertions sur la chaîne statuts/
suppression/recalcul/validation groupée, dont un scénario simulant
le temps qui passe pour confirmer que rien n'est appliqué avant
validation groupée et que l'historique complet reste intact après.
Non-régression complète reconfirmée. Structure JSX des trois vues
modifiées revérifiée.

Deux notes complémentaires (backup/purge des logs avec BLOB chiffré,
automates IMAP/ENT) capturées au backlog (items 39 sous-note et 40),
pas commencées -- questions de conception réelles non tranchées.

BACKLOG.md (items 39-40) et tickets/README.md mis à jour.

## 2026-09-04 — Fondation d'un système de droits : groupe admin_hub, rights-api, inventaire de fichiers (version: d2b5bdd7a866, livraison #283)

Demandé explicitement, en complément d'une question sur l'absence
des fichiers du hub dans la GED (relayée entièrement vers Mayan
EDMS externe depuis #158, jamais couvert les fichiers du hub
lui-même) : "une gestion de droit incluant la visibilité en
listing", "un nouveau groupe admin_hub donnera les tous les droits...
notamment celui de gérer les droits", "la gestion des droits devient
une tuile et impacte toutes les api".

Fondation vérifiée avant de construire : le hub est déjà authentifié
via Keycloak OIDC, et le mapper de claim "groups" existait déjà côté
client supervision-hub (jamais utilisé pour du contrôle d'accès,
seulement un affichage de débogage) -- la brique d'identification
existait déjà, restait à construire la couche de droits.

Nouveau service rights-api -- court-circuit admin_hub (toujours
vrai, avant toute requête SQL, y compris pour gérer les droits
eux-mêmes), refus par défaut (absence d'octroi = refus), octrois
précis ou larges, actions cloisonnées. Modèle de confiance identique
au reste du projet : reçoit la liste des groupes de l'appelant
directement, jamais un jeton à décoder lui-même.

Inventaire de fichiers (file_inventory.py) -- liste chemin/taille/
date, JAMAIS le contenu, même pour un fichier marqué "secret". Liste
de chemins surveillés OUVERTE (pas prétendument exhaustive), point
de départ couvrant .env, imports/sauvegardes Keycloak, clés SSH,
certificats PKI.

Groupe admin_hub ajouté au realm Keycloak. Tuile "Droits" (deux
onglets Fichiers/Permissions), affichée uniquement si admin_hub
présent dans les groupes -- confort d'affichage, jamais LA sécurité
(revérifié côté API à chaque action de toute façon).

Vérifié réellement : 18 assertions sur le cœur du système de
sécurité (store.py), 18 assertions supplémentaires sur les routes
(app.py), scanner de fichiers testé avec un vrai contenu de clé
privée factice confirmant qu'il ne fuit jamais. Structure JSX
revérifiée.

Portée de cette livraison : les points 1-3 des spécifications
(fondation, groupe, tuile). Les points 4 (brancher les ~40 autres
API du projet) et 5 (ENT en "super tuile" avec sous-tuiles) restent
à faire -- notés au backlog (item 38), jamais bâclés en une seule
livraison vu les risques de régression sur autant de services à la
fois.

rights/README.md (nouveau), BACKLOG.md (item 38), .env.example et
ENV_CHANGELOG.md mis à jour.

## 2026-09-04 — ENT Calendrier : retour visuel, filtre à joker, vue tickets par échéance (version: fb4420d60023, livraison #282)

Trois demandes explicites, notées au backlog (item 37) puis
construites sur "lance-toi", en plein test réel de déploiement.

Retour visuel sur "Importer" -- le bouton avait déjà un état de
chargement mais visiblement trop discret. Renforcé avec un encart de
résultat nettement plus visible (fond coloré vert/rouge), champ
désactivé pendant l'import.

Filtre par motif à joker (*SAV*DEV*, interrupteur sensibilité à la
casse) -- appliqué côté hub sur les événements déjà chargés, jamais
un nouveau paramètre d'API. Conversion motif vers regex testée en
isolation.

Vue "Tickets par échéance" à droite de la liste d'événements --
choix par défaut faits sans cadrage complet préalable (deadline_ts,
tickets ouverts avec échéance définie, vue liste triée croissante,
aucun lien vers l'événement source dans cette première version).
Aucune donnée supplémentaire chargée -- /queue renvoyait déjà
deadline_ts, simple filtrage/tri côté hub des tickets déjà en
mémoire par ailleurs.

Vérifié réellement : logique de filtrage par motif et de tri/
filtrage des tickets par échéance testées en isolation. Structure
JSX revérifiée après la disposition à deux colonnes.

BACKLOG.md (item 37) et tickets/README.md mis à jour.

## 2026-09-04 — Skin Keycloak : quatre bugs réels corrigés après le premier vrai rendu (version: bf7d5db13069, livraison #281)

Le skin "hub" (#275) n'avait jamais pu être vérifié visuellement
(aucun navigateur disponible en développement) -- quatre bugs
réels signalés par la personne au premier vrai déploiement, corrigés
une fois le vrai code source HTML de la page de connexion transmis.

Bug principal, cause du texte blanc sur fond blanc du bouton
"Connexion" : #kc-login avait été pris pour l'ID de la carte de
connexion (documentation décrivant apparemment une version
différente de Keycloak) -- dans cette version 26, #kc-login est en
réalité l'ID du bouton lui-même. La règle de carte lui donnait un
fond blanc qui l'emportait par spécificité CSS sur le bleu voulu par
la règle de bouton. Corrigé : .card-pf seule pour la carte, #kc-login
dédié au bouton avec background-color + !important pour battre le
CSS PatternFly v4 fourni.

Largeur de la carte non bornée (prenait tout l'écran) -- max-width
ajouté. Menu de langue resté ouvert en permanence -- correctif
défensif ajouté, pas confirmé comme la cause réelle (pourrait être
menu-button-links.js, hérité du thème parent, jamais modifié ici).
Un quatrième point signalé par la personne reste à éclaircir.

hub-dark corrigé par analogie directe (mêmes bugs structurels très
probables), lui-même toujours non vérifié en conditions réelles.

Leçon retenue, documentée dans keycloak/themes/README.md : la
documentation externe sur les sélecteurs Keycloak peut décrire une
version différente de celle réellement déployée -- le vrai code
source HTML de la page rendue est la seule source fiable.

## 2026-09-04 — Correctif réel : diff + set -euo pipefail faisait planter la question interactive Keycloak (version: 5639c3efab00, livraison #280)

Signalé par la personne en plein déploiement réel, poursuite du
diagnostic sur le realm Keycloak (#275) : après correction des
chemins .env absolus (#279 et au-delà), le script gateway/scripts/
run.sh affichait bien le diff attendu ("+loginTheme: hub") puis
s'arrêtait immédiatement avec le code 1, sans jamais présenter la
question interactive [oui/non/marquer]. Un contournement
`< /dev/tty` tenté d'abord (hypothèse d'entrée standard fermée) --
sans effet, signe que la vraie cause était ailleurs.

Cause réelle trouvée et confirmée par reproduction directe : `diff`
renvoie le code 1 quand il trouve des différences -- comportement
NORMAL et attendu ici (c'est précisément ce qu'on cherche à
détecter), mais sous `set -euo pipefail` (actif dans ce script),
ce code 1 fait sortir tout le script AVANT d'atteindre le `read`
interactif plus bas, sans jamais l'afficher. Reproduit isolément
avec un test minimal (deux fichiers différents, même pipe, même
set -euo pipefail) : confirmé que le script s'arrête juste après le
diff SANS le correctif, et continue normalement AVEC -- validé par
exécution réelle, pas seulement une relecture de code.

Corrigé -- `(diff ... || true) | grep | ...` neutralise explicitement
le code de sortie de `diff`, jamais laissé se propager comme un
échec de pipeline. Commande de correctif immédiat (sed) transmise
directement à la personne pour un déblocage sans attendre un
nouveau zip.

## 2026-09-04 — Correctif réel : .gitignore effaçait le code source de keycloak-backup (version: 6f71fff8751f, livraison #279)

Signalé par la personne en plein déploiement réel :
`docker compose build` (stack gateway/) échouait avec "path
.../keycloak/backup not found", puis après création manuelle du
dossier, "failed to read dockerfile: open Dockerfile: no such file
or directory".

Cause réelle trouvée : .gitignore excluait keycloak/backup/ en BLOC
-- ce dossier contient pourtant du VRAI code source committé
(Dockerfile, backup-loop.sh) EN PLUS d'être le point de montage où
les sauvegardes du realm sont écrites À L'EXÉCUTION
(supervision-si-realm-backup.json). Un git clone frais perdait donc
silencieusement le Dockerfile et le script, jamais visible avant un
vrai déploiement depuis un dépôt git (jamais reproduit dans cet
environnement de développement, qui n'est pas un checkout git).

Corrigé -- seuls les artefacts de sauvegarde réels sont désormais
exclus (keycloak/backup/*.json et le fichier temporaire), jamais le
dossier entier. Contenu des deux fichiers manquants transmis
directement à la personne pour un déblocage immédiat, sans attendre
un nouveau zip.

## 2026-09-04 — Documentation cyber : enrichissement charte d'usage SI + rattachement ISO 27001:2022 (version: 68b6961a8a4a, livraison #278)

Demandé explicitement : "peux tu trouver des exemple de charte et de
conseil cyber/iso27000 pour enrichir notre version ?".

Lecture préalable de l'existant (docs/charte-usage-si.docx,
docs/cyber-risques-resume.md) pour cibler ce qui manque réellement
plutôt que dupliquer. Recherche externe menée avant tout ajout.

Charte d'usage du SI -- trois enrichissements, chacun avec citation
juridique vérifiée : opposabilité de la charte (Code du travail
L1321-1 à L1321-5, annexion au règlement intérieur ou signature
individuelle), distinction fichiers professionnels/personnels
(jurisprudence Cass. soc. 18 octobre 2006 n°04-48.025, "arrêt
Nikon"), délibération CNIL n°2022-100 sur les mots de passe, clauses
RGPD recommandées par la CNIL pour la manipulation de données
personnelles.

Édition XML directe (docx-js ne peut pas ouvrir un fichier
existant) -- un vrai bug trouvé et corrigé au passage : des
antislashs d'échappement markdown insérés par erreur dans le texte
XML brut, rendus littéralement à l'affichage. Détecté par
vérification visuelle page par page (rendu PDF), jamais supposé
correct sans regarder.

cyber-risques-resume.md -- rattachement des 14 risques existants aux
4 thèmes de l'Annexe A ISO/CEI 27001:2022 (93 mesures depuis la
révision du 25 octobre 2022, transition achevée le 31 octobre 2025,
les certificats 2013 ne sont plus valides). Rattachement fait au
niveau du thème, jamais un numéro de mesure précis inventé faute de
l'avoir vérifié dans le détail. Observation qui en ressort : la
quasi-totalité des risques déjà notés touche le thème Technologique,
angle mort côté gouvernance/Organisationnel si l'objectif devient
une vision ISO 27001 complète.

Vérifié réellement : validation XML/structure du docx (script du
skill docx), rendu PDF inspecté visuellement page par page après
correctif. Sources de recherche multiples et convergentes citées
dans les deux documents.

## 2026-09-04 — ssh-tunnels : génération et suppression réelle de clés SSH (version: d7cd26586a9e, livraison #277)

Deux notes explicites de la personne, restées en attente depuis
#210 : "permettre la suppression des clés ssh sans aucune
sauvegarde surtout" et "permettre de générer des clés sans
passphrase ou avec".

Point capital trouvé en creusant AVANT de coder : les deux
contredisaient une décision explicite prise avec la personne en
#159 -- SSH_KEYS_DIR monté en LECTURE SEULE, "ce service ne génère
ni ne stocke jamais de clé lui-même". Signalé explicitement plutôt
qu'inversé silencieusement -- la personne a confirmé le changement
de posture sécurité (montage passé en lecture-écriture).

DELETE /keys/<id> -- fichier ET registre supprimés, aucune copie
conservée, exactement comme demandé. Garde-fou ajouté malgré tout :
refuse (409) si la clé est encore référencée par une connexion
active -- la demande portait sur l'absence de copie, jamais sur
l'absence de vérification de sécurité élémentaire.

POST /keys/generate -- ssh-keygen -t/-N via key_scanner.generate_key.
Limite assumée et documentée plutôt que cachée : ssh-keygen n'offre
aucun mécanisme par variable d'environnement pour la passphrase
(contrairement à sshpass -e déjà utilisé ailleurs) -- vérifié auprès
de la documentation officielle, -N reste la seule voie non
interactive, exposant brièvement la phrase dans la liste des
processus du conteneur (jamais journalisée ni persistée).

Vérifié réellement : ssh-keygen non installable ici (tentative
confirmée échouée), generate_key testée avec un sous-processus
simulé -- validation défensive, construction exacte de la commande,
et vérification spécifique que la passphrase ne fuit jamais dans un
message d'erreur. Suppression testée de bout en bout avec un vrai
fichier sur disque -- fichier et registre supprimés en l'absence
d'usage, refus confirmé avec fichier et registre intacts quand une
connexion référence encore la clé. Non-régression complète
reconfirmée. Structure JSX revérifiée.

BACKLOG.md (item 2) et ssh-tunnels/README.md mis à jour.

## 2026-09-04 — Traçabilité DEBUG : extension de l'audit #225 aux modules récents (version: 9882555b26b0, livraison #276)

Suite à l'item 25 du backlog (traçabilité DEBUG systématique,
"rien ne doit être silencieux") : vérification que les modules
construits depuis l'audit #225 respectent la même convention.

classifier-api et tasks-api vérifiés SANS aucun appel réseau/
subprocess propre (services purement locaux, SQLite) -- rien à
tracer là, cohérent avec la convention, pas un oubli.

Trouvaille plus large que prévu en vérifiant glpi-api et zenoss-api :
glpi/api/app.py avait six appels réseau directs (nebula-api,
network-agent-api, classifier-api, snmp-api, ajoutés #264-#270) sans
aucune trace DEBUG sur leurs échecs. zenoss/api/app.py était
silencieux sur SES SIX ROUTES avec connexion MySQL -- pas seulement
la nouvelle route de localisation #268, un angle mort qui préexistait
à cette session.

Douze points de passage tracés au total (six + six), avec le même
style déjà établi (_log.debug("fonction : description -- %s", exc)).

Vérifié réellement : chaque trace confirmée en injectant une VRAIE
panne (connexion refusée, statut HTTP erroné) et en capturant les
logs pour confirmer qu'elle apparaît effectivement -- pas seulement
que l'appel est syntaxiquement présent. Non-régression complète des
deux services reconfirmée.

BACKLOG.md (item 25) mis à jour.

## 2026-09-04 — Skins de connexion Keycloak, cohérents avec le hub (version: 0b132a7a3743, livraison #275)

Demandé explicitement : "peux tu proposer des skins pour la mire
keycloak ? et intégrer un skin par défaut qui soit cohérent avec le
hub".

Deux skins -- "hub" (clair, palette exacte du hub via
shared/theme.css, INTÉGRÉ PAR DÉFAUT dans keycloak/realm-template.json)
et "hub-dark" (sombre, alternatif, à sélectionner manuellement dans
la console d'administration si préféré).

parent=keycloak dans chaque theme.properties -- hérite de tous les
gabarits FreeMarker et toute la logique du thème classique Keycloak,
seul le CSS est remplacé. Sélecteurs CSS vérifiés AVANT d'écrire quoi
que ce soit, contre plusieurs sources convergentes (dépôt officiel
keycloak/keycloak, documentation Red Hat 26.0) -- jamais devinés.

Piège réel évité : chaque thème est monté INDIVIDUELLEMENT sur son
propre sous-chemin Docker, jamais tout /opt/keycloak/themes d'un
coup -- un montage sur le dossier parent aurait remplacé entièrement
son contenu côté conteneur, effaçant les thèmes intégrés dont
parent=keycloak dépend, cassant la connexion et les consoles en même
temps.

Non vérifié dans cet environnement : aucun rendu visuel possible
(pas de navigateur, pas d'instance Keycloak réelle disponible ici)
-- couleurs/sélecteurs corrects sur le papier, le premier
déploiement réel reste le seul vrai test.

keycloak/themes/README.md (nouveau) et keycloak/README.md mis à
jour.

## 2026-09-04 — ENT : écran de validation, correction complète type/niveau/statut (version: 4ac071c9717e, livraison #274)

Complète un point noté "reste à faire" à la livraison précédente :
POST /tickets/<id>/validate acceptait déjà les quatre champs
(demandeur/type/niveau/statut) depuis #273, seule l'interface
n'exposait que la correction du demandeur.

ValidationView.jsx affiche désormais quatre menus déroulants par
ticket en attente, avec un objet d'état unique par ticket plutôt
que quatre useState séparés.

Vérifié réellement : logique de construction du payload testée en
isolation -- un champ non renseigné n'est jamais transmis (évite
d'écraser une valeur par erreur), le demandeur deviné automatiquement
et une correction manuelle d'un autre champ se combinent
correctement, et choisir explicitement "aucun" efface bien un champ
deviné plutôt que de le laisser tel quel silencieusement. Structure
JSX revérifiée.

tasks/README.md mis à jour.

## 2026-09-03 — ENT : création automatique de ticket depuis un événement + écran de validation (version: 709e2f30cc51, livraison #273)

Demandé explicitement en réponse au point noté "reste à faire" de la
livraison précédente : "Oui branche la création auto. Ajouté un
écran de validation des tickets automatique".

Nouvelle colonne tickets.pending_validation (migration douce, même
motif que les migrations déjà existantes) -- 0 par défaut, 1
uniquement pour un ticket créé automatiquement, en attente de
confirmation humaine. Même esprit que suggestion_engine.py déjà en
place : jamais d'exécution automatique silencieuse.

POST /calendar/create_ticket -- sujet et description repris de
l'événement, demandeur deviné via le mécanisme heuristique déjà
existant, appliqué seulement sur correspondance exacte avec un
utilisateur connu. GET /tickets/pending_validation et POST
/tickets/<id>/validate (avec correction optionnelle du demandeur)
-- l'écran de validation demandé. Le rejet réutilise le mécanisme
d'archivage déjà existant, jamais un vrai DELETE.

ValidationView.jsx -- troisième onglet de la tuile ENT. Bouton
"+ Créer un ticket" ajouté dans CalendarView.jsx.

Un vrai bug trouvé et corrigé en testant : la première version de
la route omettait deux colonnes obligatoires de ticket_time_entries
(created_at, et le repli end_ts vers start_ts) -- corrigé en
reprenant exactement le motif déjà établi côté /calendar/assign.

Un cas révélateur confirmé par le test : sur un événement où le
détecteur a deviné à tort un mot comme nom de demandeur, aucune
fausse affectation n'a eu lieu -- ne correspondant à aucun login
réel, le champ est resté vide, correctement laissé à un humain.

Vérifié réellement : chaîne complète testée de bout en bout (tous
les cas nominaux et d'erreur). Non-régression complète de
tickets-api reconfirmée. Structure JSX revérifiée.

tasks/README.md mis à jour.

## 2026-09-03 — Tuile ENT : calendrier connecté aux tickets + gestion de tâches Kanban indépendante (version: c9bf1e636d73, livraisons #271-272)

Reprise d'un sujet abordé puis écarté : la connexion à un agenda
Google. Question posée honnêtement sur l'accès aux sources
Thunderbird -- clarifié (pas d'accès permanent, recherche web
utilisée pour confirmer factuellement que Thunderbird embarque des
identifiants OAuth propres à SA propre identité, dont la réutilisation
pour le hub aurait violé les conditions Google). Deux pistes
légitimes présentées, la personne a choisi l'URL secrète iCal
(lecture seule, aucune clé API).

Découverte en cours de route : tickets/api/ contenait déjà un
parseur ICS maison, les routes d'import (dont /calendar/import_url,
exactement l'approche choisie), un moteur de suggestion
événement→ticket et l'affectation elle-même -- travail antérieur non
couvert par le résumé de compaction reçu en début de session.
Vérifié avec prudence que ce n'était pas du contenu injecté avant de
s'y fier (inspection du style, confirmation des imports réels dans
app.py). Chaîne complète testée de bout en bout avant de construire
quoi que ce soit par-dessus -- import ICS réel, dédoublonnage par
UID, détection par mot-clé, affectation à un ticket, tout confirmé
fonctionnel sans aucune régression trouvée.

Nouveau module tasks/ -- gestion de tâches INDÉPENDANTE des tickets
(aucune table partagée), trois colonnes Kanban fixes (todo/doing/
done), déplacement par boutons plutôt que glisser-déposer (choix
délibéré, plus fiable à vérifier sans navigateur réel disponible
dans cet environnement). Logique de repositionnement testée en
profondeur (intra-colonne, inter-colonnes, bornes, suppression qui
comble le trou laissé) -- tout confirmé au premier passage.

CalendarView.jsx (hub) -- vue agenda (liste triée par date, pas une
grille semaine/jour, report délibéré) réutilisant entièrement le
backend existant côté tickets-api. EntView.jsx -- tuile "ENT"
(Environnement numérique de travail), conteneur à onglets réunissant
Calendrier et Tâches, promue en tuile d'accueil (même mécanisme que
GED/#172 et Exploration réseau/#265).

Vérifié réellement : socle tasks/store.py testé en profondeur (13
scénarios). Routes tasks-api testées de bout en bout. Dockerfile
vérifié avec le script de contrôle systématique développé en #252.
Structure JSX des trois nouvelles vues revérifiée, y compris après
correction d'un doublonnage de barre de titre (résolu avec une prop
embedded).

tickets/README.md (chantier précédemment marqué "non livré" corrigé)
et tasks/README.md (nouveau) mis à jour.

## 2026-09-03 — GLPI : correctif, sélection de segment pour l'import network-agent (version: bb0a789815b0, livraison #270)

Manque trouvé en relisant l'interface tout juste construite en #269 :
le sélecteur de source "Exploration réseau" ne permettait pas de
choisir un segment réseau précis -- sans ce choix, l'aperçu/import
aurait mélangé tous les segments connus, y compris potentiellement
le réseau de la structure de la personne et celui d'un client comme
Alpha (172.x.x.x) -- exactement la confusion déjà corrigée côté
architecture-api/vigilance-api (#264, #268).

Corrigé -- previewImport/commitImport (côté hub) acceptent
désormais un segment_id optionnel. Sélecteur de segment affiché
uniquement pour la source "Exploration réseau", peuplé depuis
network-agent-api. Avertissement explicite si aucun segment n'est
choisi.

Vérifié réellement : logique de transmission de segment_id testée
en isolation, logique de construction de la liste de segments à
plat testée. Structure JSX complète revérifiée.

glpi/README.md mis à jour.

## 2026-09-03 — GLPI : audit complet, clients Nebula, sélection multiple, annuler/supprimer (version: 7636dc2987c7, livraison #269)

Suite à quatre questions explicites de la personne, posées comme un
audit : memory a-t-il une interface de consultation (oui, déjà
complète) ; les données network-agent et Nebula sont-elles prêtes à
être exportées vers GLPI (le backend l'était, mais aucune interface
hub ne permettait de les déclencher) ; les clients Nebula
connectés peuvent-ils être injectés dans GLPI avec une sélection
multiple (trouvaille : nebula-api suit déjà les clients séparément
des équipements, mais rien ne les exportait) ; existe-t-il un moyen
d'annuler/supprimer individuellement partout (non, le client GLPI
n'avait même pas de méthode de suppression).

Suppression individuelle -- delete_item ajouté à glpi_client.py,
comportement vérifié contre la documentation officielle GLPI :
sans force_purge (le défaut), GLPI déplace l'objet dans sa propre
corbeille, récupérable nativement -- l'équivalent exact d'un
"annuler" sans mécanisme de undo maison. Nouvelles routes GET
/items/<itemtype> et DELETE /items/<itemtype>/<id>.

Nouveau module nebula_clients_import.py -- type GLPI Computer (pas
NetworkEquipment, ces lignes décrivant des appareils utilisateurs
finaux). Nouvelle route POST /import/nebula-clients.

Sélection multiple étendue aux quatre modules d'import (only_macs ou
only_ids selon la source) -- None par défaut, comportement inchangé,
non-régression vérifiée. Un vrai problème de conception trouvé en
construisant l'interface : les aperçus renvoyaient des chaînes de
texte formatées, inexploitables pour des cases à cocher -- corrigé
en structurant created en objets {key, name, itemtype, detail} en
mode aperçu seulement, l'import réel reste inchangé.

GlpiInventoryView.jsx entièrement reconstruite -- sélecteur de
source, aperçu à cocher par candidat, import de la sélection,
section de gestion des actifs existants avec suppression
individuelle.

Vérifié réellement : delete_item testé contre les réponses réelles
documentées par GLPI. Routes testées de bout en bout. Sélection
multiple testée sur les quatre modules, y compris combinée avec le
filtrage par catégorie existant. glpiClient.js testé de bout en bout
avec un fetch simulé, y compris la distinction only_macs/only_ids
selon la source. Structure JSX complète revérifiée.

glpi/README.md mis à jour.

## 2026-09-03 — Architecture réseau : croisement de localisation Zenoss, les quatre volets d'origine désormais livrés (version: fc60feab2663, livraison #268)

Complète les quatre volets de la demande d'origine du module
Architecture réseau (#253) -- dernier restant, volontairement
différé jusqu'ici faute d'une route adaptée côté zenoss-api
(localisation exposée uniquement sous forme d'arbre, pas de
recherche directe par équipement).

Plus simple que prévu à l'origine : la localisation d'un équipement
précis n'a en réalité jamais eu besoin de parcourir tout l'arbre --
une requête SQL ciblée directement sur les colonnes déjà utilisées
pour construire l'arbre suffit. Nouvelle route GET /device_location
côté zenoss-api (device ou ip). architecture-api l'appelle par nom
d'abord, puis par IP si rien trouvé -- best-effort, comme les autres
croisements de ce module.

Section "Lieu d'intervention" côté hub, entre la topologie et les
accès de gestion -- même ordre que la demande d'origine.

Vérifié réellement : route /device_location testée en profondeur
côté zenoss-api (recherche par nom, par IP, aucun résultat, base
injoignable). Croisement testé côté architecture-api -- localisation
trouvée et affichée correctement, et confirmé que zenoss-api
injoignable ne fait jamais échouer les autres croisements de la
même vue d'ensemble. Non-régression complète des deux services
reconfirmée. Structure JSX revérifiée.

architecture/README.md, zenoss/README.md et backlog (item 31) mis à
jour -- les quatre volets de la demande d'origine sont désormais
tous livrés.

## 2026-09-03 — Analyse de schémas : sélection graphique dans l'éditeur de relations (version: fe76456f432a, livraison #267)

Demandé explicitement : "je n'ai pas trouvé l'interface me
permettant graphiquement d'attribuer à un champ d'une table un lien
relationnel vers l'index d'une autre table".

En creusant : l'éditeur de relations existait déjà ("Ajouter une
relation manuellement", #152), mais avec seulement des champs texte
libre -- la personne devait taper exactement le nom de la table et
de la colonne, rien de graphique à proprement parler. D'où la
confusion.

Corrigé -- les quatre champs deviennent des menus déroulants,
peuplés depuis analysis.tables déjà chargé côté état du composant
(aucun nouvel appel réseau). La colonne cible affiche explicitement
"(clé primaire)" pour les colonnes concernées. Choisir une nouvelle
table réinitialise la colonne correspondante. Repli sur les champs
texte libre conservé si aucune analyse n'est encore disponible,
avec message explicite.

Vérifié réellement : logique de peuplement des menus testée en
isolation (tri des tables, extraction des colonnes, réinitialisation
au changement de table, cas limites gérés sans exception). Structure
JSX complète revérifiée.

schema-analyzer/README.md mis à jour.

## 2026-09-03 — Vigilance : quatrième signal, infrastructure silencieuse (version: dbd524d6f855, livraison #266)

Reprise d'une piste explicitement notée "reste à faire" dès la
livraison initiale du module (#262) : "un équipement d'infrastructure
qui cesse subitement d'émettre du trafic pourrait aussi être un
signal de santé du parc à part entière".

Nouveau signal "infrastructure silencieuse" (critical) -- un
appareil classé equipement_infrastructure dont le dernier trafic
observé remonte à plus de VIGILANCE_SILENCE_THRESHOLD_HOURS (24h par
défaut). Contrairement aux trois premiers signaux (ciblés sur les
clients DHCP dynamiques), celui-ci cible les équipements
d'infrastructure -- un silence prolongé peut signaler une panne, une
coupure réseau, ou un signe de compromission.

Un vrai bug trouvé et corrigé en testant ce nouveau signal :
analyze_segment avait un retour anticipé (if not dhcp_macs: return 0)
qui empêchait toute analyse dès qu'un segment n'avait aucun client
DHCP connu -- correct pour les signaux 1-3 (qui en dépendent tous),
mais bloquait aussi le nouveau signal 4, qui lui est indépendant des
clients DHCP. Corrigé en restructurant : les signaux 1-3 restent
conditionnés à la présence de clients DHCP, le signal 4 s'exécute
désormais toujours.

Vérifié réellement : signal 4 testé isolément (segment avec
seulement de l'infrastructure, aucun client DHCP) -- confirme que le
correctif fonctionne. Non-régression complète des quatre signaux
testés ensemble sur un scénario complet -- confirmé que les 4 types
se déclenchent correctement simultanément, et qu'un appareil au
profil normal n'est toujours jamais signalé à tort quel que soit le
nombre de signaux actifs. Date au format inattendu gérée sans
exception.

vigilance/README.md, docker-compose.yml, .env.example et l'interface
hub (libellé du nouveau signal) mis à jour.

## 2026-09-03 — Exploration réseau promue en tuile d'accueil (version: cd927ea7415a, livraison #265)

Demandé explicitement : "peux tu transformer l'explorateur réseau en
tuile ?". Même mécanisme que GED (#172) -- ajoutée au tableau
fronts avec un onClick interne plutôt qu'une URL externe, puisque
NetworkAgentView.jsx vit lui aussi à l'intérieur du hub. Conditionnée
à NETWORK_AGENT_API_BASE_URL configurée -- jamais une tuile morte si
le service n'est pas déployé, même garde que GED.

Retirée du menu déroulant Réseau où elle vivait jusqu'ici -- même
convention que GED, qui n'apparaît elle non plus dans aucun menu une
fois promue en tuile.

Vérifié réellement : logique de construction du tableau fronts
testée en isolation. Structure JSX complète revérifiée.

hub/README.md mis à jour.

## 2026-09-03 — GLPI : export des appareils découverts par network-agent, ciblé par segment (version: 8fe54ef880e4, livraison #264)

Demandé explicitement, dans le sens inverse de l'import GLPI
envisagé un temps : "je veux exporter vers glpi tout ce qu'on va
découvrir par l'exploration réseau" -- confirmé pertinent après que
la personne ait précisé que l'inventaire GLPI actuel est "presque
vide".

Contexte donné explicitement, déterminant pour la conception :
"L'important pour mon client c'est Alpha (nebula) mais nebula ne
connait pas directement les 200 clients plus ou moins mobiles actifs
dans son réseau, à nous de les identifier et de les traiter dans
glpi". Puis précision cruciale après un premier échange : "attention
ce que le dns te donne qui match le motif dhcp123 ce sont les
clients wifi du lan de ma structure pas le lan de alpha, tu
identifiera alpha avec des adresses 172...".

Deux réseaux distincts peuvent être surveillés par network-agent
(un seul agent, plusieurs segments possibles) -- celui de la
structure de la personne (192.168.x.x, ses propres clients WiFi
dhcpNNN) et celui d'un client comme Alpha (172.x.x.x). D'où
segment_id en paramètre optionnel mais fortement recommandé de la
nouvelle route -- cible un seul segment, jamais un mélange des deux
réseaux par défaut.

Nouveau module network_agent_import.py, même esprit que
nebula_import.py (#208) -- dédoublonnage par adresse MAC, tous les
appareils mappés vers NetworkEquipment. Nouvelle route POST
/import/network-agent-devices -- dry_run (défaut true), segment_id,
exclude_dynamic (défaut false volontairement -- côté Alpha les
clients DHCP dynamiques sont justement les 200 clients mobiles que
Nebula ne voit pas lui-même, la donnée la plus utile à remonter,
jamais du bruit à filtrer par défaut).

Vérifié réellement : testé avec un scénario reproduisant exactement
la clarification reçue -- deux segments simulés, confirmé que
segment_id ciblant Alpha exporte seulement ses appareils, jamais
ceux de la structure de la personne, et inversement. Dédoublonnage
par MAC testé. Exclusion optionnelle par classification testée. Cas
d'échec testés -- toujours un 502 propre, jamais un crash. Dockerfile
vérifié avec le script de contrôle systématique développé en #252 --
un fichier réellement manquant trouvé et corrigé immédiatement
(network_agent_import.py lui-même). Non-régression complète de
glpi-api reconfirmée.

glpi/README.md et docker-compose.yml (NETWORK_AGENT_API_URL pour
glpi-api) mis à jour.

## 2026-09-03 — Architecture réseau : import automatique depuis Exploration réseau (version: e8d07915e2b3, livraison #263)

Reprise d'un point noté "reste à faire" dans architecture/README.md
dès la livraison initiale (#253) : "actuellement, un équipement se
crée entièrement à la main ici, aucun pré-remplissage depuis ces
sources".

Nouvelle route POST /import/network-agent -- IDEMPOTENTE, matchée
par adresse MAC, jamais de doublon sur des imports répétés. Un
équipement DÉJÀ PRÉSENT (même MAC) voit SEULEMENT son IP mise à jour
si elle a changé (plausible via DHCP) -- son NOM, TYPE et NOTES
restent INTACTS, potentiellement personnalisés par la personne après
un premier import, JAMAIS écrasés par un réimport. Un NOUVEL
équipement est créé avec le nom d'hôte comme nom (ou l'adresse MAC si
aucun nom d'hôte connu), avec une note signalant son origine.

Bouton "⤵ Importer depuis Exploration réseau" côté hub, à côté de la
recherche/création manuelle.

Vérifié réellement : testé avec un scénario reproduisant les vraies
données de la personne -- premier import (création), réimport
identique (rien ne change, jamais de doublon), personnalisation
manuelle du nom/notes APRÈS import puis réimport (confirmé
préservée, jamais écrasée), changement d'IP simulé (confirmé
synchronisé, mais le nom personnalisé reste intact malgré tout).
Route testée de bout en bout, y compris l'URL réellement appelée
(HOST_IP, network-agent-api tourne toujours en network_mode: host)
et les cas d'échec (network-agent injoignable, URL non configurée)
-- toujours un 502 propre, jamais un crash. Non-régression complète
d'architecture-api reconfirmée. Structure JSX revérifiée.

architecture/README.md et backlog (item 31) mis à jour -- l'import
GLPI reste à faire.

## 2026-09-03 — Nouveau module Vigilance : premiers automates d'analyse cyber-vigilance/santé du parc (version: 34e77f1e09d7, livraison #262)

Backlog item 34, suite du module Classification (#260). Proposé un
premier automate concret pour la catégorie "client DHCP dynamique"
(croiser avec les niveaux d'usage pour repérer les postes WiFi qui
consomment anormalement) -- confirmé par la personne : "OUI j'aime
c'est tout à fait le genre d'analyse que je veux, sois créatif et si
possible cible les éléments de cyber vigilance et de santé du parc
et du réseau".

Ce module ne collecte rien lui-même -- il croise, en lecture, ce qui
existe déjà (network-agent : appareils, échanges, services,
historique de volume ; classifier : catégorie sémantique d'un nom
d'hôte). La seule donnée propre à ce module est le journal des
signaux détectés, pour permettre de voir une tendance dans le temps.

Trois premiers signaux, ciblés sur les clients DHCP dynamiques (la
catégorie la plus risquée par nature -- appareils non identifiés
individuellement, potentiellement invités/BYOD/WiFi) : contact avec
de l'infrastructure (violation de segmentation potentielle, sévérité
critique -- un invité qui parle directement à un NMS/onduleur/
serveur), diversité de services élevée (s'écarte du profil "invité
normal"), croissance de volume anormale (usage intensif inattendu
pour un profil transitoire).

Thread de fond, analyse périodique de tous les segments connus
(30 min par défaut), déclenchement manuel possible, rétention bornée
(même motif que network-agent/#251 et memory/#259). Best-effort
explicite à chaque étape -- une source indisponible réduit ce que
l'analyse peut détecter, ne la fait jamais planter.

Vérifié réellement : testé avec un scénario réaliste reproduisant
les vraies données de la personne (nms.intranet, dhcp139.intranet en
contact avec nms, dhcp144.intranet au profil normal) -- les TROIS
signaux correctement détectés pour l'appareil anormal, et confirmé
qu'AUCUN signal n'est levé pour l'appareil au profil normal -- la
distinction la plus importante à vérifier pour un outil de ce type,
jamais de faux-positif sur un cas normal. Détails textuels de chaque
signal vérifiés exacts. Cas limites testés (aucun client DHCP dans
le segment, network-agent injoignable) -- jamais une erreur, jamais
un crash. Dockerfile vérifié avec le script de contrôle systématique
développé en #252 -- aucun fichier manquant. Structure JSX revérifiée.

Tuile hub "Vigilance" (menu Général, à côté de "Cyber" -- distinct de
ce tableau de bord existant qui reste un outil de gouvernance manuel
pour un public non-technique, #187).

vigilance/README.md, .env.example, ENV_CHANGELOG.md et backlog (item
34) mis à jour.

## 2026-09-03 — Intégration : classification affichée dans Exploration réseau (version: 279b5a33a68e, livraison #261)

Suite naturelle du module Classification (#260) -- un badge de
classification apparaît maintenant à côté du nom d'hôte de chaque
appareil découvert, quand classifier-api en trouve une (prénom
connu, motif dhcpNNN, terme d'un dictionnaire importé).

Intégration côté HUB, pas côté backend -- network-agent-api lui-même
ne connaît rien de classifier-api, aucun couplage entre les deux
services. NetworkAgentView.jsx appelle les deux API en parallèle et
fusionne l'affichage côté client -- plus simple qu'un appel
server-to-server, aucune dépendance nouvelle entre deux backends
déjà indépendants.

Best-effort explicite -- classifier-api indisponible ou non
configuré ne bloque jamais l'affichage des appareils eux-mêmes, juste
l'absence de badge. Seuls les appareils avec un nom d'hôte résolu
sont soumis à classification, via un appel groupé plutôt qu'un appel
par appareil.

Vérifié réellement : logique de filtrage/construction de la charge
utile testée en isolation (appareils avec hostname uniquement, appel
évité si classifier-api non configuré). Structure JSX/CSS
revérifiée.

network-agent/README.md, classifier/README.md et backlog (item 34)
mis à jour pour refléter cette intégration désormais livrée.

## 2026-09-03 — Nouveau module Classification : dictionnaires importables et classification sémantique (version: a008d8a10bc8, livraison #260)

Backlog item 34, signalé explicitement "à prioriser fort car
central" par la personne, après observation sur de vraies données
réseau (Exploration réseau, résolution DNS #250) : des noms d'hôte
comme "ups", "alice", "bob", "nms", "dhcp139" portent chacun
un sens différent -- personnes/login, clients IP dynamique (WiFi),
services névralgiques.

Décisions prises en cours de conception, avec la personne. Proposé
d'abord "une lib python nltk" -- vérifié NON installable dans cet
environnement (pip install nltk échoue), et de toute façon non
pertinent : ses corpus linguistiques généralistes ne couvrent pas le
vocabulaire réseau/télécom/informatique demandé
("plein de dictionnaires métiers"). Puis question explicite de la
personne : "une interface d'import de dictionnaires ?" -- architecture
retenue en conséquence, dictionnaires IMPORTABLES par catégorie,
jamais des listes codées en dur. Puis "je veux pouvoir accéder aux
stats d'usage des mots, lexèmes et d'orienter" -- ajouté au schéma
dès la conception, pas après coup.

Nouveau module classifier/ -- import de dictionnaires (un terme par
ligne, upload multipart), motif structurel dhcpNNN reconnu
directement (pas un dictionnaire), recherche en dictionnaire token
par token (jamais une sous-chaîne, pour éviter les faux-positifs).
Stats d'usage par terme (total de correspondances, termes jamais
utilisés). Orientation manuelle -- confirmer ou corriger une
classification, avec enrichissement du dictionnaire sur action
explicite.

Testé en profondeur contre le VRAI jeu de données partagé par la
personne (20 lignes de sa liste d'appareils découverts, copiées
directement) -- deux vrais bugs trouvés et corrigés en cours de
route : le motif dhcp était ancré sur la chaîne entière, ne matchait
donc jamais un vrai nom d'hôte avec son suffixe de domaine (corrigé
pour tester token par token, comme le dictionnaire) ; l'orientation
manuelle n'ajoutait que le premier mot d'un nom composé (corrigé
pour enrichir avec chaque partie significative, hors mots
génériques comme "intranet").

Tuile hub "Classification" (menu Data) -- import de dictionnaire,
statistiques par catégorie, testeur de classification en direct avec
orientation manuelle. Dockerfile vérifié avec le script de contrôle
systématique développé en #252 -- aucun fichier manquant.

Une vraie erreur d'édition du backlog trouvée et corrigée en cours
de route : la mise à jour de l'item 34 a d'abord atterri en tête de
fichier (même type d'erreur qu'en #251), repérée immédiatement,
réparée, puis refaite en vérifiant explicitement la position avant
d'écrire.

classifier/README.md, .env.example, ENV_CHANGELOG.md et backlog
(item 34) mis à jour.

## 2026-09-03 — Nouveau module Mémoire : rémanence du tampon de logs Memcached (version: a54e5007166d, livraison #259)

Backlog item 32, demandé explicitement : collecter régulièrement les
clés/valeurs de Memcached, les stocker en base, avec repopulation de
Memcached et rétention bornée, plus une interface de navigation et
de calcul -- puis explicitement "en faire une tuile pas simplement
un outil".

Vérification technique faite AVANT de coder : Memcached n'offre pas
de "lister les clés existantes" (limitation native). Sans une liste
de clés connue à l'avance, "récupérer les kv du memcached" de façon
générique n'est pas réalisable. Portée donc scopée au tampon de logs
partagé (shared/log_buffer.py, #145) -- la seule utilisation de
Memcached dans ce projet dont les clés sont énumérables de façon
fiable, via deux sources combinées : 28 SERVICE_NAME internes
recensés directement dans le code de chaque backend, et le registre
pushed_log_sources déjà existant pour les sources /push-log
externes. Le cache de requêtes court de zenoss-api reste
délibérément hors de portée -- recalculable à la demande,
fondamentalement différent en nature.

Nouveau module memory/ -- collecte périodique (5 min par défaut),
dédoublonnage par repère de collecte par service (évite de
retraiter tout le tampon à chaque passage), repopulation de
Memcached si un tampon est trouvé vide (cas le plus probable :
Memcached vient de redémarrer), rétention bornée (30 jours par
défaut, même motif que network-agent/#251). Tuile hub "Mémoire"
(menu Général) -- statistiques par service (le calcul demandé) et
navigateur d'historique filtrable.

Vérifié réellement : testé avec le stub Memcached fonctionnel déjà
présent dans cet environnement (état partagé en mémoire, simulant un
vrai serveur) -- dédoublonnage confirmé sur plusieurs passages
successifs, calcul de statistiques confirmé exact, rétention testée
(purge les entrées, conserve le repère de collecte). Repopulation
testée avec un VRAI aller-retour Memcached -- clé supprimée
(simulation de redémarrage), tampon vide confirmé, repopulation
déclenchée, tampon reconstruit dans le bon ordre chronologique
depuis l'historique persisté, et confirmé qu'aucune repopulation
n'a lieu quand le tampon n'est pas vide. Dockerfile vérifié avec le
script de contrôle systématique développé en #252 -- aucun fichier
manquant dès la première livraison. Structure JSX revérifiée.

memory/README.md, .env.example, ENV_CHANGELOG.md et backlog (item
32) mis à jour.

Deux nouvelles notes ajoutées au backlog dans la foulée (items 33 et
34, aucun code) : collecte transversale d'informations d'identité
(nom d'équipement, IP, lieu) à travers les différents modules ;
classification sémantique des identités découvertes (noms d'hôte
comme "ups"/"alice"/"nms" portant chacun un sens différent) avec
mise en relation vers des automates d'analyse de risque/usage --
cette dernière signalée comme prioritaire par la personne.

## 2026-09-03 — Correctif du correctif : le vrai fond du problème de défilement (version: 55e949aaea09, livraison #258)

Le correctif #257 pour le débordement du footer était incomplet --
confirmé par une capture d'écran réelle montrant une page de
plusieurs milliers de pixels de haut, le problème toujours présent
après déploiement.

Cause exacte trouvée : flex:1 sur .hub-settings n'a d'effet que si
le parent flex (.hub-shell) a lui-même une hauteur bornée -- or
.hub-shell n'a que min-height:100vh (un plancher, jamais un
plafond), donc rien n'empêchait la page entière de continuer à
grandir avec son contenu.

Envisagé de border .hub-shell lui-même -- écarté après avoir trouvé
un commentaire déjà présent sur .hub-grid-view prévenant
explicitement que .hub-shell n'avait jamais été touché pour cette
raison précise (les autres vues n'ont jamais été vérifiées avec un
défilement interne forcé, livraison #132). Modifier .hub-shell
aurait risqué de casser des vues jamais auditées pour ce
comportement.

Corrigé en reprenant le motif déjà validé de .hub-grid-view
lui-même -- hauteur explicite calc(100vh - 60px) plutôt qu'un
flex:1 dépendant d'un parent jamais borné. Fonctionne
indépendamment de la hauteur de .hub-shell, jamais besoin d'y
toucher.

hub/README.md mis à jour, section dédiée expliquant honnêtement
pourquoi le premier correctif était insuffisant plutôt que de
réécrire l'historique.

## 2026-09-03 — Correctifs d'ergonomie : points de service et défilement du footer (version: cdff8fc517c1, livraison #257)

Deux captures d'écran réelles à l'appui, trois problèmes signalés
explicitement : "très beau mais à travailler pour réduire l'espace
pris... il faudra filtrer intelligemment pour que ça soit utilisable
et visible" ; "le design du footer a toujours le même souci, la page
déborde sur le footer au lieu de rester en dessous et de proposer le
défilement".

Points de service : un appareil réel affichait 234 services
distincts (probablement une passerelle relayant un trafic très
divers) -- plus de 200 points sur une seule ligne, étalés sur 8+
lignes visuelles. Corrigé -- au-delà de 15 points, les services les
MOINS significatifs sont résumés par un compteur "+N" plutôt qu'un
point de plus. Les plus utilisés (déjà triés par volume décroissant
côté backend) restent toujours visibles en premier -- jamais une
troncature arbitraire. Le tableau détaillé du pied de page reçoit le
même traitement (défilement propre borné à 220px).

Défilement du footer : cause réelle identifiée -- les vues
.hub-settings rendent comme enfants directs de .hub-shell, sans
AUCUN conteneur borné entre elles et l'en-tête sticky. Un panneau
position:sticky;bottom:0 a besoin d'un ancêtre à hauteur BORNÉE avec
son propre défilement pour avoir la marge de manœuvre nécessaire à
réellement se figer -- sans ça, il reste un bloc normal du flux,
poussé hors champ par tout contenu qui grandit. Corrigé en donnant à
.hub-settings le même motif déjà éprouvé que .hub-grid-scroll (la
grille d'accueil, qui n'avait jamais ce problème) -- flex:1;
overflow-y:auto; min-height:0. Affecte TOUTES les vues utilisant
.hub-settings, pas seulement Exploration réseau -- cohérent avec
"toujours le même souci" signalé par la personne, un correctif
central plutôt qu'une rustine par vue.

Vérifié réellement : logique de limitation des points testée avec un
volume reproduisant la capture d'écran (234 services -- exactement
15 affichés, le plus utilisé en tête, 219 résumés ; peu de services
-- aucun compteur inutile). Structure JSX/CSS revérifiée. Non
vérifié dans cet environnement : rendu visuel réel du correctif de
défilement (aucun navigateur disponible ici) -- raisonnement appuyé
sur un motif déjà fonctionnel ailleurs, comportement exact à
confirmer par la personne après déploiement.

network-agent/README.md et hub/README.md mis à jour.

## 2026-09-03 — Exploration réseau : découverte automatique de sous-réseaux (version: 6f01efe03425, livraison #256)

Demandé explicitement dans le cadre de la préparation GLPI Inventory
(backlog item 21, "combien de segments réseau distincts faut-il
couvrir ?") : "notre module d'exploration doit répondre à cette
question" -- avec le vrai réseau de la personne en exemple : LAN
192.168.0.0/16 avec au moins 3 plages en usage (0.0/24, 1.0/24,
100.0/24), pas encore toutes recensées.

Plutôt que d'exiger un recensement préalable, network-agent regroupe
maintenant les appareils déjà découverts par sous-réseau -- la
structure interne réelle du LAN apparaît d'elle-même à mesure que la
capture avance. Aucune nouvelle table, aucun nouveau chemin
d'écriture dans capture.py -- calcul purement en lecture depuis
na_devices déjà rempli, groupé côté Python via le module standard
ipaddress. Nouvelle route GET /observed-subnets?segment_id=N,
granularité paramétrable (/24 par défaut). Côté hub : section
dépliable avec sélecteur de granularité (/16 à /28).

Recommandation de configuration documentée pour un LAN structuré
comme celui de la personne : NETWORK_AGENT_SEGMENT_CIDR sur le
supernet le plus large pertinent (ex. un /16) plutôt qu'un seul /24
-- la détection de passerelle et la découverte de sous-réseaux se
complètent alors, jamais confondues l'une avec l'autre.

Vérifié réellement : testé avec un scénario reproduisant exactement
le réseau réel décrit (3 plages, tailles différentes) -- les 3
sous-réseaux correctement découverts, triés par nombre d'appareils
décroissant, total cohérent. Granularité /16 confirmée regrouper
tout en un seul. Segment sans appareil géré proprement. Route testée
de bout en bout. Non-régression complète de toutes les routes
existantes reconfirmée après cette quatrième extension du module.

network-agent/README.md et backlog (item 21) mis à jour.

## 2026-09-03 — Correctif : seuil de désynchronisation d'horloge relevé à 15 minutes (version: 0293a5295b91, livraison #255)

Demandé explicitement, capture d'écran à l'appui montrant deux
horloges quasi identiques affichées en permanence ("16:35:44 ·
16:35:44") : "quand les valeurs sont proches pas besoin d'afficher
les 2, mettons une dérive acceptable de 15mn".

L'horloge permanente navigateur/serveur (#137) avait un seuil de 3
secondes -- beaucoup trop bas en pratique : un aller-retour réseau
normal dépasse presque toujours 3s, rendant la seconde horloge
visible EN PERMANENCE, jamais l'effet recherché à l'origine (un
signal de désynchronisation RÉELLE, pas un affichage systématique de
deux valeurs quasi identiques).

Corrigé : seuil relevé à 900s (15 minutes). Sous ce seuil, une seule
horloge affichée (les deux sont considérées "la même heure" pour un
usage pratique) -- la seconde horloge et l'écart (⚠ +Xs / -Xs) ne
s'affichent QUE si le seuil est dépassé. L'info-bulle au survol
continue de montrer les deux valeurs même quand synchronisées.

Vérifié réellement : logique de seuil testée explicitement -- 899s
(juste sous 15mn) -> une seule horloge, 900s pile -> désynchronisé,
1h -> désynchronisé, dérive en sens inverse (valeur négative) aussi
détectée (valeur absolue), heure serveur indisponible (null) gérée
sans exception. Structure JSX revérifiée.

hub/README.md mis à jour.

## 2026-09-03 — Architecture réseau : niveaux d'usage et supervision (version: 43f113664bd4, livraison #254)

Suite immédiate de #253, demandée dans la foulée : "l'aspect
supervision et suivi de fonctionnement est aussi très important :
pouvoir identifier les niveaux d'usage et anticiper les
engorgements... pouvoir justifier des investissements en présentant
les taux d'usages et les variations".

Croisement ajouté avec network-agent-api (⚠️ HOST_IP requis, ce
service tourne en network_mode: host, même piège déjà rencontré pour
backup-restore-api #249) -- par correspondance d'adresse IP contre
les appareils déjà découverts, réutilise directement l'historique de
présence/volume construit en #251. Taux de variation calculé entre
le premier et le dernier relevé -- le signal le plus direct pour
repérer une tendance (croissance soutenue = engorgement à anticiper,
ou argument concret pour justifier un investissement).

Best-effort explicite, même discipline que les autres croisements de
ce module : IP non surveillée par network-agent -> pas d'erreur,
juste rien à afficher (cas normal, la plupart des équipements ne
seront pas nécessairement surveillés) ; network-agent injoignable ->
erreur signalée clairement, mais GED et ssh-tunnels continuent de
fonctionner sans interruption.

Nouvelle section "Niveaux d'usage" dans la vue de détail côté hub --
volume cumulé actuel, taux de variation en couleur si positif,
tableau de l'historique complet.

Vérifié réellement : correspondance IP testée (le bon appareil
identifié parmi plusieurs), taux de croissance calculé et confirmé
correct (1000 -> 5000 = +400%), IP non surveillée gérée sans erreur,
équipement sans IP géré sans crash, échec réseau isolé (network-agent
injoignable) signalé clairement sans affecter les autres
croisements. Structure JSX revérifiée.

## 2026-09-03 — Architecture réseau : vue et outil de parcours (livraison #253, groupée avec #254 ci-dessus -- jamais livrée séparément)

Nouveau chantier, demandé explicitement après une pause sur
Rétro-ingénierie ("mon souci de rétro ingénierie urgente est réglé...
ça sera utile dans l'avenir, on y reviendra donc pause pour ça") :
identifier, à partir d'un équipement remontant dans Zenoss ou lors
d'un dysfonctionnement (saturation, abus de protocole, DDoS), ses
interfaces amont/aval, ses accès de gestion, ses lieux
d'intervention, et sa documentation liée (contrats, spécifications,
paramètres).

Reconnaissance faite AVANT de coder quoi que ce soit, pour ne jamais
avoir deux sources de vérité qui divergent : localisation physique
déjà dans zenoss-api (/location_tree, différée à une prochaine
tranche -- structure en arbre côté Zenoss, pas de recherche directe
par équipement) ; accès de gestion déjà dans ssh-tunnels-api (croisé
en direct par IP) ; documents liés réutilisant le mécanisme de
liaison polymorphe déjà existant côté GED (document_links,
linked_type/linked_id, #158, linked_type="equipment" ici).

Ce module apporte la pièce réellement manquante : la topologie
amont/aval DÉCLARÉE. network-agent (#250) enregistre déjà des
échanges entre appareils, mais ce sont des paires "qui a parlé à
qui" observées sur le trafic réel -- jamais une hiérarchie
amont/aval, une connaissance métier qui ne se déduit pas fiablement
du trafic seul.

Nouveau module architecture/ -- arch_equipment -> arch_interfaces ->
arch_links (lien directionnel, upstream_* en amont de downstream_*).
Route centrale GET /equipment/<id>/overview -- en un seul appel :
topologie amont/aval avec équipement distant complet (navigation
directe), accès SSH croisés par IP, documents liés croisés depuis la
GED. Chaque croisement BEST-EFFORT, signale sa propre erreur sans
faire échouer les autres.

Tuile hub "Architecture réseau" (menu Réseau) -- recherche/création
d'équipements, vue de détail avec navigation cliquable vers les
équipements voisins, formulaires pour déclarer interfaces et liens.

Vérifié réellement : scénario réaliste routeur -> switch -> serveur
testé depuis les trois positions (sommet, milieu, extrémité),
suppression en cascade confirmée (équipement -> interfaces -> liens
orphelins), recherche par nom et par IP, lien dupliqué rejeté
proprement (contrainte UNIQUE, jamais un 500 nu), overview testée de
bout en bout avec GED et ssh-tunnels simulés y compris le cas GED
injoignable (confirmé que ssh-tunnels continue de fonctionner).
Logique de direction du lien côté hub testée en isolation. Dockerfile
vérifié avec le script de contrôle systématique développé en #252 --
aucun fichier manquant dès la première livraison de ce module.

architecture/README.md, .env.example et backlog (items 30 -- note de
pause sur Rétro-ingénierie -- et nouvel item 31) mis à jour.

## 2026-09-03 — Correctif majeur : quatre services crashés au déploiement réel (version: 18ea95ffbef3, livraison #252)

La personne a partagé de vrais logs gunicorn de quatre services
crashés au démarrage -- premier retour de déploiement massif après
plusieurs livraisons rapprochées.

Trois services (schema-analyzer-api, network-agent-api, plus un
quatrième non signalé mais trouvé par vérification systématique --
glpi-api) partageaient EXACTEMENT le même bug : un fichier Python
nouvellement créé (relation_validator.py #241, dns_resolver.py #250,
snmp_import.py #232) était importé par app.py mais jamais ajouté à
la liste COPY du Dockerfile correspondant -- ModuleNotFoundError au
démarrage, systématiquement. Trois erreurs distinctes de ma part,
au fil de trois livraisons différentes.

Un quatrième cas trouvé par la même vérification, moins grave
(dégradation silencieuse, jamais un crash) : prefs-api,
file_source_poller.py -- protégé par un try/except ImportError
existant, mais la fonctionnalité de sources "file" restait de facto
inerte sans que ça se voie. Corrigé aussi.

Après ces quatre corrections, vérification EXHAUSTIVE de tous les
Dockerfile du projet (comparaison automatisée entre chaque liste
COPY et les fichiers .py réellement présents dans le dossier source)
-- deux faux positifs identifiés et écartés après lecture (ldap-admin
et tickets utilisent une syntaxe COPY multi-fichiers par ligne,
pixel-grid/bridge et pipeline ont leur propre contexte de build
local, glpi/cli_import.py est un script CLI autonome jamais importé
par app.py) -- confirmé qu'aucun autre cas similaire ne subsiste
nulle part dans le projet.

Un quatrième service crashé (snmp-api) avait une cause DIFFÉRENTE :
ImportError: cannot import name 'ContextData' from
'pysnmp.hlapi.v1arch.asyncio'. Recherché avant de corriger : ContextData
n'existe QUE dans v3arch (SNMPv3, système de contextes/moteurs) --
absent de v1arch (SNMPv1/v2c, ce module), qui n'en avait d'ailleurs
jamais eu besoin dans les appels réels get_cmd/bulk_cmd du fichier
(jamais passé en argument). Un import résiduel, jamais utilisé,
faisait planter tout le module au chargement -- corrigé en le
retirant, aucune autre modification nécessaire, le code appelant
était déjà correct. Corrige au passage une affirmation trop
optimiste de la docstring du module ("exemples vérifiés un par un")
-- cet import précis avait échappé à cette vérification, corrigé
honnêtement plutôt que laissé tel quel.

snmp/README.md, glpi/README.md, schema-analyzer/README.md et
network-agent/README.md mis à jour avec le détail de chaque
correctif.

## 2026-09-03 — Exploration réseau : rémanence, historique dans le temps (version: 5e901ac97706, livraison #251)

Demandé explicitement, précédé d'une observation sur la perte de
données au redémarrage (log via Memcached, volontairement sans
persistance par conception ; network-agent via SQLite, devrait
survivre au redémarrage grâce au volume monté) : "j'aimerais
beaucoup voir dans le temps des choses comme : présence des ip/mac,
les volumes échangés/usages par paire d'ip, les services connectés
par paire d'ip".

Toutes les tables existantes (na_devices, na_device_links) étaient
CUMULATIVES -- une seule ligne par entité, jamais d'évolution dans
le temps. Corrigé par un mécanisme de relevés périodiques.

Nouvelle table na_device_link_services -- services utilisés PAR
PAIRE d'appareils (table séparée de na_device_links, additive,
aucun risque de migration sur une table livrée en #250 pas encore
confirmée en usage réel). Alimentée automatiquement dans
capture.py, même condition que na_device_services.

Nouvelles tables na_history_snapshots/na_device_presence_history/
na_link_history -- un relevé = une copie ponctuelle des compteurs
cumulatifs à un instant donné, jamais un delta stocké -- garde la
flexibilité d'interroger n'importe quel intervalle a posteriori.
Nouveau thread de fond dédié, distinct de la capture et de la
résolution DNS -- un relevé par heure par défaut
(NETWORK_AGENT_SNAPSHOT_INTERVAL_SECONDS), purge des relevés de
plus de 30 jours (NETWORK_AGENT_HISTORY_RETENTION_DAYS) -- retenue
volontairement bornée.

Nouvelles routes GET /links/services, GET
/devices/<id>/presence-history, GET /links/history. Côté hub :
section "Présence dans le temps" dans le pied de page de détail
d'un appareil -- tableau simple, aucune bibliothèque de graphique
disponible côté hub (cohérent avec la limite npm déjà rencontrée
ailleurs dans ce projet).

Une vraie erreur d'édition trouvée et corrigée en cours de
route : une mise à jour du backlog a d'abord atterri au tout début
du fichier (position mal calculée), coupant un mot en deux --
repéré immédiatement en vérifiant le résultat, restauré, puis
refait correctement en confirmant la correspondance avant d'écrire.

Vérifié réellement : service par paire testé (accumulation,
recherche symétrique A↔B). Relevés testés avec une vraie
progression dans le temps (deux relevés successifs avec du trafic
entre les deux, évolution confirmée visible). Purge testée (retire
l'historique, garde les données cumulatives intactes). capture.py
retesté de bout en bout. Non-régression complète de toutes les
routes reconfirmée après cette troisième extension du module dans
la même journée.

network-agent/README.md, .env.example, ENV_CHANGELOG.md et backlog
(item 20) mis à jour.

## 2026-09-03 — Exploration réseau : six demandes d'ergonomie/fonctionnalités (version: 9d2d88c9de6e, livraison #250)

Demandées explicitement par la personne après un premier usage réel,
sur deux captures d'écran (statut de capture réelle, résultats réels
de Rétro-ingénierie sur son code).

Échanges entre appareils ("qui parle à qui") -- nouvelle table
na_device_links, DIRECTIONNELLE (device_a = source, device_b =
destination) -- garde l'information la plus riche, une conversation
bidirectionnelle apparaît comme deux lignes distinctes (A→B et B→A),
révélant les motifs asymétriques plutôt que de les fondre en une
moyenne. Enregistré automatiquement dans capture.py quand les deux
bouts d'un paquet sont des appareils identifiés. Nouvelle route GET
/links?segment_id=N. Rejoint directement l'idée de graphe
d'architecture réseau/inspiration Tkined-Scotty déjà discutée avec
la personne.

Résolution DNS -- nouveau dns_resolver.py, deux mécanismes :
résolveur système par défaut (socket.gethostbyaddr) ; serveur DNS
spécifique si NETWORK_AGENT_DNS_SERVER configuré -- dnspython non
installable dans cet environnement (vérifié explicitement), client
DNS minimal fait main, même approche que pcap_parser.py pour le
format pcap : une seule requête PTR par UDP. Gère la compression de
noms DNS (RFC 1035, le point le plus piégeux du protocole) -- testé
avec de vraies réponses construites octet par octet.
NETWORK_AGENT_DEFAULT_DOMAIN retire un suffixe des noms résolus.
Colonnes hostname/hostname_resolved_at ajoutées par migration
idempotente, testée sur une base existante simulée pour confirmer
qu'aucune donnée n'est perdue. Thread de résolution en arrière-plan
distinct du thread de capture (appels DNS lents, jamais mêlés à la
boucle par paquet). Limite honnêtement signalée : network_mode: host
(#238-239) fait que le résolveur système reste un best-effort, pas
une garantie -- d'où l'intérêt réel du serveur DNS configurable.

Ergonomie de l'interface -- en-tête global du hub désormais fixe au
défilement (appliqué GLOBALEMENT, bénéfice pour tout le hub). Liste
des appareils dans un conteneur défilant propre avec en-têtes de
colonnes fixes à l'intérieur. Services en petits points colorés
(bleu=TCP, ambre=UDP) avec nom/port/compteur au survol (attribut
title natif) -- nouvelle route groupée GET /devices/services évitant
un appel par appareil pour afficher les points sur chaque ligne
simultanément. Détails d'un appareil affichés en pied de page fixe
au clic, plutôt qu'un panneau qui décale la mise en page.

Un vrai bug d'édition trouvé et corrigé en cours de route : un
remplacement de texte a accidentellement supprimé la ligne de
signature de apply_role_hints (le corps de la fonction restait,
orphelin) -- repéré immédiatement par la suite de tests, corrigé,
toute la base de store.py retestée pour confirmer qu'aucune autre
régression ne s'était glissée.

Vérifié réellement : logique d'échanges testée en profondeur
(accumulation vs duplication, direction, jamais un échange depuis un
ARP ou un broadcast). Client DNS testé avec des réponses construites
à la main, compression et sans compression, ID de requête différent
jamais associé à tort, réponse vide gérée proprement, paquet corrompu
jamais une exception. Migration testée sur base existante simulée.
Route groupée testée sans collision avec la route existante. Logique
JSX testée en isolation. Structure JSX et non-régression complète
des routes reconfirmées.

network-agent/README.md, .env.example, ENV_CHANGELOG.md et backlog
(item 20) mis à jour -- les six demandes marquées livrées.

## 2026-09-03 — Backup-restore : suivi/couverture des images système (version: dff697a4d2c5, livraison #249)

Backlog item 27, sous-volet marqué URGENT par la personne plus tôt
dans la session : "Clonezilla (ou équivalent) pour produire une
image système complète -- objectif immédiat = future virtualisation
de postes Windows existants".

Note backlog ajoutée au passage, sans code : demandes d'ergonomie et
de fonctionnalités pour network-agent (en-têtes/menu fixes au
défilement, services affichés en points colorés avec survol,
détection des échanges entre appareils -- rejoint l'idée de graphe
d'architecture réseau/Tkined déjà discutée --, résolution DNS,
DNS/domaine par défaut depuis l'hôte ou paramétrable) -- notées à
l'item 20, pas encore traitées.

Portée volontairement limitée au SUIVI/COUVERTURE, jamais
l'automatisation réelle de Clonezilla (PXE/DRBL) -- nécessite une
infrastructure matérielle/réseau réelle qu'aucun test dans cet
environnement ne peut valider, même raisonnement que pour l'agent
réseau (#233). Répond d'abord à l'exigence explicite du backlog :
"toute machine détectée doit avoir une image prête à la
restauration".

Nouveau module backup-restore/ -- registre des images connues
(saisie manuelle pour l'instant), croisé via GET /coverage avec les
appareils DÉCOUVERTS par network-agent (comparaison MAC insensible à
la casse) -- renvoie par appareil s'il a une image, sa date, et
depuis combien de jours (calculé côté serveur). Les machines sans
image apparaissent en tête du tri.

Point d'architecture anticipé dès la conception : network-agent-api
tourne en network_mode: host (#238-239) -- backup-restore-api le
joint via HOST_IP, jamais le nom de service Docker habituel, qui ne
résoudrait pas depuis un conteneur normal comme celui-ci. Même piège
déjà rencontré et corrigé pour la passerelle nginx, reproduit ici en
connaissance de cause plutôt que découvert après un déploiement raté.

Tuile hub "Sauvegardes" (menu Général) -- onglet Couverture (vue
croisée) et onglet Images enregistrées (formulaire de saisie +
liste).

Vérifié réellement : normalisation de casse des adresses MAC testée
(création et filtrage), regroupement "la plus récente par machine"
confirmé correct, image sans MAC gérée sans exception, suppression
d'un id inexistant sans exception. Route /coverage testée de bout en
bout avec de vrais appareils simulés et avec network-agent-api
injoignable (502 propre). Validation des champs requis testée.
Structure JSX revérifiée après câblage dans App.jsx.

backup-restore/README.md, .env.example, ENV_CHANGELOG.md et backlog
(items 20 et 27) mis à jour.

## 2026-09-03 — Rétro-ingénierie : second volet, schéma fonctionnel (version: 8c1c405081ce, livraison #248)

Le volet demandé à l'origine de ce chantier (proposer un schéma
fonctionnel de l'interface), jamais commencé jusqu'ici -- repris
pendant que la personne ne pouvait pas tester en conditions réelles
(pas au bureau). En cours de route, la personne a signalé un doute
sur la version de Fat-Free utilisée (pense qu'il s'agit de la lignée
2.x, sans certitude) -- recherché explicitement avant de continuer :
aucune conversation ni fichier de ce projet ne mentionnait de numéro
de version précis jusqu'ici.

Recherche complémentaire sur les spécificités 2.x : F3 a
historiquement proposé à la fois un appel STATIQUE (F3::route(...),
vu dans du code datant de 2011-2012) ET un appel par INSTANCE
($f3->route(...), la forme la plus documentée aujourd'hui) -- les
deux syntaxes semblent avoir coexisté sur une large part de
l'historique F3, pas strictement l'une en 2.x et l'autre en 3.x
comme d'abord supposé. Aucune documentation officielle spécifique à
la lignée 2.x n'a pu être trouvée (le site officiel n'archive plus,
semble-t-il, que 3.6 et versions ultérieures) -- signalé honnêtement
plutôt que présumé.

Nouveau route_scanner.py -- extrait les routes déclarées via
$f3->route(...) OU F3::route(...) (les deux syntaxes couvertes sans
distinction de version), regroupées par CONTRÔLEUR. Pour chaque
route : méthode(s) HTTP, chemin, alias éventuel (distingué du jeton
de paramètre d'URL malgré la même syntaxe @), jetons de paramètre,
et le handler (méthode d'instance, méthode statique, fonction
globale, ou "closure inline" signalée sans tentative d'extraction du
corps -- fragile par expression régulière, la personne retrouve le
détail au fichier:ligne indiqué).

Intégré dans /scan aux côtés des deux scanners existants (relations
SQL, structures de vues) -- les trois tournent simultanément sur
chaque fichier retenu. Côté hub : nouvelle section "Schéma
fonctionnel -- écrans et actions" dans RetroView.jsx.

Vérifié réellement : toutes les variantes documentées testées
(handler instance/statique, méthodes HTTP multiples, jeton de
paramètre, alias distingué du jeton malgré la syntaxe identique,
closure signalée sans extraction, ancien style F3::route, argument
de cache TTL ignoré proprement, regroupement par contrôleur, fonction
globale). Route /scan retestée de bout en bout avec les trois
scanners actifs simultanément, non-régression confirmée. Un artefact
d'échappement shell dans le script de test (déjà rencontré
précédemment dans ce module) a de nouveau causé un faux échec,
reconfirmé propre avec une chaîne Python brute.

retro/README.md et backlog (item 30) mis à jour, incertitude de
version documentée explicitement plutôt que masquée.

## 2026-09-03 — Rétro-ingénierie : envoi direct vers l'éditeur de relations (version: d3adad9cb5cf, livraison #247)

Reprise d'un point noté "reste à faire" dans le README du module --
aucune nouvelle demande explicite, ferme la boucle "repérer ici,
confirmer là-bas" déjà décrite à la personne dans une réponse
précédente.

RetroView.jsx : sélecteur de connexion DBA (optionnel, réutilise
fetchDbaConnections déjà existant côté hub). Une fois une connexion
choisie, bouton "→ Envoyer" sur chaque relation candidate du tableau
-- crée directement la relation comme PROPOSÉE dans schema-analyzer
(POST /relations, source="manual", réutilise createRelation déjà
existant). Plus besoin de recopier à la main table/colonne/table/
colonne dans l'éditeur.

Aucune confirmation automatique -- la relation créée reste au statut
"proposée", exactement comme une relation détectée par
relation_detector.py : la personne la confirme/rejette elle-même
après avoir vu le résultat de la validation contre les données
(#241), qui reste une étape manuelle ensuite. Statut par ligne
affiché immédiatement (✔ envoyée / ⚠️ échec avec le message).

App.jsx : dbaApiBase et schemaApiBase désormais passés à RetroView.

Vérifié réellement : logique de statut d'envoi testée en isolation
(succès/échec par ligne indépendants). Structure JSX de RetroView.jsx
et App.jsx revérifiée après le câblage des nouvelles props.

retro/README.md et backlog (item 30) mis à jour.

## 2026-09-03 — Rétro-ingénierie : correctif auto-jointure hiérarchique (version: 4a7273091e94, livraison #246)

Reprise d'une limite connue signalée dans le README du module --
aucune nouvelle demande explicite, initiative directement liée au
problème d'origine de la personne (structures hiérarchiques
manquantes dans une vieille application).

Une auto-jointure HIÉRARCHIQUE légitime (ex. employes e1 JOIN
employes e2 ON e1.manager_id = e2.id -- exactement le genre de
structure visée à l'origine de ce chantier) était exclue à tort :
le filtre table_a == table_b, pensé pour écarter une comparaison
TRIVIALE (le même alias des deux côtés, ex. e.manager_id = e.id dans
un WHERE qui n'est pas une vraie jointure), excluait aussi le cas
légitime où deux alias DIFFÉRENTS pointent vers la même table.

Corrigé dans php_sql_scanner.py : le test porte désormais sur les
alias eux-mêmes (alias_a == alias_b), pas sur la table résolue --
une auto-jointure avec deux alias distincts est maintenant capturée,
marquée is_self_reference: true pour la distinguer clairement d'une
relation inter-tables ordinaire. Fonctionne aussi bien pour le style
moderne (JOIN ... ON) que pour le style ancien (virgules dans le
FROM, condition dans le WHERE).

Côté hub, RetroView.jsx : nouvelle colonne "Type" dans le tableau
des relations candidates, badge "🔀 hiérarchique" sur les
auto-références.

Vérifié réellement : cas hiérarchique moderne ET ancien style testés
et confirmés capturés, comparaison triviale (même alias) confirmée
toujours exclue, non-régression complète des relations ordinaires
(is_self_reference: false) et de la déduplication (le nouveau champ
survit correctement au regroupement). Structure JSX revérifiée.

retro/README.md et backlog (item 30) mis à jour.

## 2026-09-03 — Rétro-ingénierie : structures de données depuis les vues HTML (version: 8cad3f3d5545, livraison #245)

Extension demandée explicitement, juste après le volet 1 (#243) et
la confirmation d'urgence (#244) : "j'aimerais disposer d'un outil
qui me permette d'importer du php et des vues d'écran en html puis
d'en déduire une partie des structures de données".

Vérifié via recherche AVANT de coder (jamais deviné) : la syntaxe
réelle du moteur de gabarits Fat-Free natif -- {{@variable}} (espaces
optionnels), avec <repeat group="{{@array}}" value="{{@item}}"> pour
les boucles -- confirmée par la documentation officielle F3 ("item
contains the array of data retrieved from the database table...
accessed using the column name as the array key").

Nouveau html_view_scanner.py, trois signaux distincts : champs de
FORMULAIRE (name="..." sur input/select/textarea dans un <form>, le
signal le plus fiable) ; accès aux champs en gabarit F3 natif
({{@item.champ}} ou {{@item['champ']}}) ; accès aux champs en PHP
BRUT AFFICHÉ (<?= $row['champ'] ?> ou <?php echo $row->champ; ?>) --
les applications Fat-Free plus anciennes utilisent souvent des vues
PHP classiques plutôt que le moteur natif, la personne ayant signalé
explicitement que le code varie "selon les époques de l'évolution".

Restreint volontairement aux motifs d'AFFICHAGE (echo/<?=), jamais
tout accès PHP à un tableau/objet -- un tableau PHP sert à mille
choses (config, session...) sans rapport avec une structure de
données métier ; se limiter à ce qui est réellement affiché à
l'écran garde le signal propre.

/scan balaie désormais aussi .phtml/.html/.htm en plus de .php --
les DEUX scanners (SQL + vues) tournent sur chaque fichier retenu,
un fichier .php pouvant contenir à la fois une requête SQL et du
HTML affiché directement (mélange courant en PHP ancien style). Les
résultats de plusieurs écrans sont fusionnés par variable de gabarit
-- une même variable apparaît généralement dans plusieurs écrans,
chacun n'en révélant qu'une partie.

Côté hub : nouvelles sections "Structures de champs déduites des
vues" et "Formulaires trouvés" dans RetroView.jsx.

Vérifié réellement : testé avec des fragments réalistes couvrant les
trois signaux, y compris un fichier MÉLANGEANT les deux styles de
gabarit dans le même texte (exactement le cas "évolution du code"
décrit par la personne), la fusion de plusieurs écrans révélant
progressivement une structure complète, un formulaire sans champ
nommé correctement ignoré. Route /scan retestée de bout en bout avec
une archive mélangeant .php/.html/.phtml. Non-régression du motif
Fat-Free Mapper confirmée (un premier échec de test était un artefact
d'échappement shell dans le script de test lui-même, pas un bug du
code -- reconfirmé proprement).

retro/README.md et backlog (item 30) mis à jour.

## 2026-09-03 — Urgence confirmée sur Rétro-ingénierie (version: 95e41405a68f, livraison #244)

Note pure, aucun code touché -- la personne confirme explicitement
que le chantier Rétro-ingénierie (item 30) est urgent au même titre
que le sous-volet Clonezilla de l'item 27, pas un chantier
secondaire. BACKLOG.md mis à jour.

## 2026-09-03 — Rétro-ingénierie : analyse de code PHP, volet 1 (version: 59897edc6849, livraison #243)

Backlog item 30, demandé EN URGENCE juste après sa création (#242) --
contexte réel donné par la personne : vieille application de gestion
Fat-Free (F3), demande de modification de données pressante, aucune
documentation, le prédécesseur développeur gardait les schémas "en
tête" et préparait le SQL à la main. Clarifié via question tappable :
la hiérarchie manquante varie selon les époques du code -- jointures
faciles (id->tbl_id), colonnes-listes ("set"), et des motifs encore
incompris.

Nouveau module retro/ -- php_sql_scanner.py extrait des relations SQL
CANDIDATES depuis du code PHP par expression régulière (jamais un
vrai parseur PHP/SQL, démesuré pour ce besoin précis de repérage à
valider humainement). Couvre les jointures explicites modernes (FROM
... JOIN ... ON ...) ET le style ANCIEN avec plusieurs tables
séparées par des virgules dans le FROM (jointure implicite dans le
WHERE) -- exactement le motif décrit par la personne comme présent
dans son code hérité.

Vrai bug de couverture trouvé et corrigé en testant : une première
version ne capturait QUE la première table après FROM, ratant
complètement le style ancien (plusieurs tables séparées par des
virgules). Corrigé en extrayant la clause FROM entière avant de
l'éclater sur la virgule. Un alias jamais déclaré dans le FROM/JOIN
du même fragment est ignoré, jamais deviné -- mieux vaut manquer un
candidat que d'en proposer un avec un nom de table faux. Motif
Fat-Free Mapper (new \DB\SQL\Mapper($db, 'table')) également détecté.
Déduplication avec compteur d'occurrences -- une même relation
copiée-collée des dizaines de fois dans un vieux code n'apparaît
qu'une fois, avec sa fréquence.

Nouvelle route POST /scan (archive ZIP de code source PHP), bornée
en sécurité (5000 fichiers max, 200 Mo décompressés max), jamais de
décompression sur disque (zip slip structurellement écarté). Onglet
hub "Rétro-ingénierie" (menu Data, RetroView.jsx) -- dépôt d'une
archive ZIP, tableau des relations candidates avec occurrences et
origine (fichier:ligne), liste des tables Mapper identifiées.

Portée volontairement limitée à ce premier volet ("déterminer les
relations dans une base SQL à partir du code") -- le second volet
demandé ("schéma fonctionnel de l'interface") reste hors de portée
de cette livraison d'urgence, à cadrer séparément.

Vérifié réellement : logique testée en profondeur avec des fragments
PHP/SQL réalistes et variés (jointure moderne, ancien style corrigé,
motif Mapper, alias non résolu, piège WHERE/alias, déduplication,
texte non-SQL, ligne/fichier exacts sur plusieurs requêtes). Route
/scan testée de bout en bout avec une vraie archive ZIP en mémoire
(fichiers mélangés, ZIP invalide, tentative de chemin hors archive).
Structure JSX revérifiée. Jamais testé contre une vraie archive de
code Fat-Free réelle -- à confirmer au premier usage.

retro/README.md et backlog (item 30) mis à jour.

## 2026-09-03 — Clarifications backlog + nouvel item Rétro-ingénierie (version: f5f0f9e4004a, livraison #242)

Note pure, aucun code touché -- retour de la personne sur le point
d'ensemble fait plus tôt dans la session, plusieurs clarifications
et un nouvel item.

Clarifications appliquées :
- Item 9 (promouvoir ged, étape 2) et item 26 (gestionnaire de
  fichiers) confirmés IDENTIQUES -- cross-référencés mutuellement,
  plus deux chantiers distincts à traiter séparément.
- Item 27 (backup-restore) -- URGENCE signalée sur un sous-volet
  précis : Clonezilla (ou équivalent) pour produire une image
  système complète, objectif immédiat = future virtualisation de
  postes Windows existants. Le reste du chantier (BackupPC, solution
  alternative, API de statistiques, agent courrier) reste à cadrer
  ensemble.
- Item 28 (référentiel SI) -- cadrage donné : construction
  PROGRESSIVE, en suivant les prescriptions ISO/IEC 27001.
- Item 29 (main2dieu) -- objectifs clarifiés : objectif FONDAMENTAL
  = couper les entrées/liens critiques sur alerte ou sur commande
  (jamais seulement ouvrir/superviser) ; objectif NATUREL = identifier
  et superviser ces mêmes liens. Confirmé que ce chantier recoupe
  directement ssh-tunnels (#210-213) et trb140-sms-relay (#206).
- Items 1, 5, 19, 23 -- confirmés tels quels, aucune information
  nouvelle, pas de modification.

Nouvel item 30 -- tuile "Rétro-ingénierie" : outil d'analyse de code
PHP, deux volets (déterminer les relations SQL depuis le CODE plutôt
que le schéma/les données comme schema-analyzer ; proposer un schéma
FONCTIONNEL de l'interface). Noté fidèlement, portée technique et
articulation avec schema-analyzer à cadrer ensemble avant tout code.

BACKLOG.md mis à jour -- 30 items désormais.

## 2026-09-03 — Validation des relations contre les vraies données (version: 57d6c957e64c, livraison #241)

Backlog #5 -- demandé explicitement en urgence, pendant un test réel
de la personne sur un dump de la base qui l'intéresse : "à partir du
schéma et des données (pour conforter la relation)... relier un
champ numérique ou set avec l'id d'une autre table".

Recherche préalable : trouvé Linkifier (Java), un outil dédié à ce
cas précis (sniffing de FK implicites contre les données), mais vu
la mention explicite de "vue JSON" côté personne, vérification de
l'existant dans schema-analyzer d'abord -- confirmé que beaucoup
était déjà en place (relation_detector.py par nom, list_detector.py
par motif de valeur, tout un éditeur de relations avec CRUD). Ce qui
manquait précisément : confronter une relation candidate aux VRAIES
données, jamais fait jusqu'ici (les deux détecteurs existants
regardent le nom ou le motif, jamais si les valeurs correspondent à
de vraies lignes).

Nouveau schema-analyzer/api/relation_validator.py -- approche
VOLONTAIREMENT PORTABLE (MySQL/PostgreSQL/SQLite sans code
spécifique par moteur) : plutôt que d'éclater une colonne-liste EN
SQL (fonctions différentes par moteur) ou de CASTer les types pour
comparer (syntaxe différente par moteur), tout l'éclatement et la
comparaison se font EN PYTHON après deux lectures SQL universelles
(SELECT DISTINCT ... LIMIT N, réutilisant la route générique
POST /connections/<id>/sql déjà existante côté dba-api).

Nouvelle route POST /relations/validate -- AUCUN effet de bord sur
les relations stockées, pure lecture : renvoie un taux de couverture
(% des valeurs échantillonnées qui correspondent à une ligne
existante de la table cible) + les valeurs SANS correspondance
(utile pour repérer une fausse piste). La personne décide ensuite,
au vu du résultat, de confirmer/rejeter via les routes /relations
existantes -- jamais une confirmation automatique même à 100% de
couverture.

Côté hub, SchemaAnalyzerView.jsx : bouton "🔍 Valider les données"
par relation dans l'éditeur, résultat affiché juste en dessous.

Vérifié réellement : logique de validation testée en profondeur --
cas réel (couverture 100%), vrais mismatches détectés et signalés,
colonne-liste correctement éclatée ("1,2,5" -> 3 candidats),
colonne entièrement vide (jamais de division par zéro ni un taux
trompeur), injection SQL bloquée par la validation stricte des
identifiants (les valeurs, elles, ne sont jamais interpolées --
toujours comparées en Python après lecture). Route testée de bout
en bout, y compris la propagation propre d'un échec dba-api.
Structure JSX revérifiée.

Reste à faire, noté explicitement plutôt que présumé construit : la
"vue JSON" avec valeurs RÉSOLUES (afficher la ligne liée complète,
pas seulement un lien "aller à") -- rejoint un chantier déjà noté au
backlog ("interface de gestion -- affectation des relations sur les
données"), jamais construit non plus, à cadrer ensemble.

schema-analyzer/README.md et backlog (item 5) mis à jour.

## 2026-09-03 — Première capture réelle confirmée fonctionnelle (version: 965dc4ac32c8, livraison #240)

Note pure, aucun code touché -- confirmation directe de la personne
après les correctifs #238-239 : la capture tourne, des appareils sont
découverts, et la détection de passerelle a correctement identifié
une vraie passerelle sur son réseau.

C'est la confirmation la plus significative de tout ce module :
l'heuristique de détection de passerelle (résolution ARP hors
sous-réseau, capture.py) reposait sur un raisonnement réseau testé
jusqu'ici uniquement avec des scénarios synthétiques construits à la
main. Sa validation contre du vrai trafic, sur un vrai réseau, avec
une vraie passerelle, confirme que le cœur de ce qui était demandé
("routeur/switch dédié -- identifier et évaluer leurs RÔLES")
fonctionne bien tel que conçu, pas seulement tel que testé.

network-agent/README.md et backlog (item 20) mis à jour -- reste à
observer : comportement en conditions de charge/durée, articulation
avec les modules de supervision existants.

## 2026-09-03 — Deux correctifs supplémentaires nés de tests réels successifs (version: ba5dc694b08d, livraison #239)

Suite directe de #238 -- deux nouveaux retours de la personne en
quelques minutes, chacun révélant un vrai problème que je n'avais
pas anticipé.

**Bug de l'interface trouvé au passage** : NetworkAgentView.jsx
n'affichait JAMAIS l'erreur de connexion vers network-agent-api
lui-même (status.error, renvoyé par fetchJson en cas d'échec de
requête) -- seulement status.last_error (l'échec interne DE tcpdump,
une fois la vraie réponse reçue). L'écran montrait donc un statut
"arrêtée" trompeur, sans nombre de paquets ni date, sans jamais dire
QUE la requête avait échoué. Corrigé : les deux cas sont maintenant
clairement distingués et affichés.

**host.docker.internal ne fonctionne pas en pratique** -- logs nginx
fournis par la personne : "host.docker.internal could not be
resolved (3: Host not found)". L'hypothèse de #238 était fausse :
même un proxy_pass LITTÉRAL passe par resolver 127.0.0.11 dès qu'il
est déclaré dans le bloc englobant -- ce résolveur ne consulte jamais
/etc/hosts, quelle que soit la façon dont la cible est écrite.
Corrigé définitivement en contournant le problème plutôt qu'en
cherchant un autre nom à faire résoudre : tls-proxy/render_nginx_conf.py
utilise désormais directement HOST_IP (déjà configuré ailleurs dans
ce projet) comme adresse IP LITTÉRALE, sans aucune résolution DNS
nécessaire. extra_hosts (ajouté en #238, devenu inutile) retiré de
gateway/docker-compose.yml.

**Collision de port réelle** -- logs gunicorn fournis par la
personne : "Connection in use: ('0.0.0.0', 5000)", en boucle.
network_mode: host (#238) fait que network-agent-api se lie
DIRECTEMENT sur un port de l'hôte, plus isolé comme les autres
services Docker -- port 5000 déjà occupé par un docker-registry
tournant sur la même machine. Corrigé : port configurable
(NETWORK_AGENT_HOST_PORT, défaut 15000, bien moins disputé que
5000) -- Dockerfile passé en forme SHELL pour permettre
l'interpolation de cette variable dans la commande gunicorn.

Vérifié réellement : configuration nginx régénérée avec un HOST_IP
réaliste -- proxy_pass http://192.0.2.10:15000... confirmé (IP
littérale, port 15000, plus aucune trace de host.docker.internal).
Repli sur 127.0.0.1 si HOST_IP absent testé. Non-régression
confirmée : les 30 autres routes inchangées.

network-agent/README.md, tls-proxy/README.md, .env.example et
backlog (item 20) mis à jour.

## 2026-09-03 — network_mode: host confirmé + correctif de routage en cascade (version: de53df18c445, livraison #238)

Troisième retour de test réel de la personne sur l'agent
d'exploration réseau (#233/#234) -- capture d'écran fournie :
"tcpdump: ens18: No such device exists". Exactement le point resté
incertain dans docker-compose.yml ("RECOMMANDÉ... à confirmer").

network_mode: host appliqué à network-agent-api -- ens18 (interface
réelle de l'hôte, nommage Proxmox) désormais visible depuis le
conteneur. Vérifié AVANT d'agir que la dégradation Memcached
(memcached ne résout plus hors du réseau Docker partagé) est SANS
RISQUE : shared/log_buffer.py encapsule déjà toute écriture dans un
except Exception: pass, seul le partage du journal /logs de ce
service en pâtit, jamais la capture elle-même.

Conséquence en cascade, traitée dans la même livraison : la
passerelle (tls-proxy) ne pouvait plus joindre network-agent-api par
son nom Docker habituel, sorti du réseau partagé. Recherché AVANT
d'écrire une seule ligne de config -- confirmé par la documentation
nginx/Docker et un incident réel équivalent chez un tiers
(nginx-proxy-manager#5344) : le résolveur DYNAMIQUE de nginx
(resolver 127.0.0.11, utilisé par tous les autres services via set
$backend + variable) ne consulte JAMAIS /etc/hosts -- un simple
extra_hosts: host.docker.internal serait resté sans effet avec le
gabarit existant.

Corrigé avec un troisième gabarit nginx (api-static,
API_LOCATION_TEMPLATE_STATIC) -- proxy_pass LITTÉRAL résolu au
chargement de la config via le résolveur système classique (qui
consulte bien /etc/hosts), réservé aux services en network_mode:
host. extra_hosts: host.docker.internal:host-gateway ajouté à
tls-proxy (gateway/docker-compose.yml).

Vérifié réellement : configuration nginx complète régénérée et
inspectée, route /api/network-agent/ confirmée en proxy_pass
littéral (jamais $backend). Non-régression confirmée : les 30 autres
routes (api + spa + keycloak) gardent toutes leur résolution
dynamique inchangée -- un vrai faux positif de test corrigé au
passage (comptage initial oubliant le kind "keycloak", qui partage
aussi le gabarit dynamique).

network-agent/README.md, tls-proxy/README.md et backlog (item 20)
mis à jour.

## 2026-09-03 — Nebula : archivage GED des imports + suppression par sélection (version: 8143d41cb241, livraison #237)

Demandé explicitement, après le correctif #235 -- "tu as bien ajouté
annuler l'import sur nebula mais pas supprimer... une sélection et
un bouton, un archivage des imports (fichiers à rendre visible dans
l'espace fichiers du hub/ged)".

Nouvelle table nebula_import_batches (un lot = un import complet).
Chaque fichier CSV importé est désormais aussi poussé vers ged-api
(POST /documents, liaison polymorphe linked_type="nebula-import"
déjà existante côté GED depuis #158) -- BEST-EFFORT, jamais bloquant
pour l'import lui-même : testé avec archivage réussi ET en échec,
dans les deux cas les données sont importées, l'erreur d'archivage
est signalée clairement plutôt que masquée.

Nouvelles routes GET /import-batches (historique des lots) et DELETE
/import-batches (plusieurs lots à la fois via {"batch_ids": [...]})
-- supprime les lignes importées mais garde VOLONTAIREMENT le
fichier archivé dans la GED, l'archivage servant justement à
conserver une trace même après suppression des données parsées.

Un vrai bug trouvé en testant : ORDER BY imported_at seul ne
distingue pas deux imports survenus dans la même seconde (résolution
de now_iso()), l'ordre devenait arbitraire. Corrigé avec id DESC en
critère secondaire, qui reflète toujours l'ordre réel d'insertion.

Côté hub, NebulaView.jsx : section "Historique des imports"
dépliable, tableau avec case à cocher par lot, statut d'archivage
GED visible (✅/⚠️), bouton "Supprimer la sélection". Le bouton
"Annuler cet import" existant (#235) reste disponible pour le cas le
plus courant (annuler ce qu'on vient tout juste d'importer).
GED_API_INTERNAL_URL ajouté à docker-compose.yml, dépendance
nebula-api -> ged-api ajoutée.

Vérifié réellement : archivage GED réussi/échoué testés, liaison
polymorphe vérifiée (bon linked_type/linked_id), suppression par
sélection testée de bout en bout (lot ciblé disparaît avec ses
lignes, les autres lots restent intacts, lot inexistant signalé sans
planter), tri stable confirmé même avec deux imports dans la même
seconde. Logique de sélection multiple testée en isolation côté hub.

nebula/README.md et backlog (item 16) mis à jour.

## 2026-09-03 — Réorganisation de l'en-tête du hub (version: 1ed266f31f2a, livraison #236)

Demandé explicitement -- "il y a trop d'outils maintenant" : 12
boutons plats accumulés au fil des livraisons récentes (#227-233
notamment) rendaient la barre de navigation illisible.

Structure demandée par la personne, appliquée telle quelle : deux
boutons permanents (Aide, Onglets), trois menus déroulants par
catégorie -- Général (Logs, Cyber, Historique), Réseau (Tunnels SSH,
SNMP, Nebula, GLPI Inventory, Exploration réseau), Data (Analyse de
schémas). Le menu Paramètres (#173) reste inchangé.

Point à confirmer par la personne : "Client IMAP" n'était mentionné
dans AUCUNE des trois catégories demandées -- placé par défaut sous
Général, signalé explicitement comme un choix par défaut.

Réutilise tel quel le motif de menu déroulant déjà en place pour
Paramètres (hub-nav-dropdown/hub-nav-dropdown-panel, CSS déjà
générique, inchangé). Remplace showSettingsMenu (booléen unique) par
openNavMenu (chaîne unique parmi les 4 menus, ou null) -- un seul
menu ouvert à la fois désormais.

Vérifié réellement : les 12 destinations de navigation originales
toutes retrouvées dans la nouvelle structure. Structure JSX complète
revérifiée. Logique d'état testée en isolation : bascule d'un menu à
l'autre, calcul de la classe active du déclencheur, fermeture
automatique à la sélection d'un item.

hub/README.md mis à jour.

## 2026-09-03 — Correctif : validation du type CSV Nebula + annulation d'un import (version: 0d822c4d1bc8, livraison #235)

Deuxième retour de test réel de la personne, immédiatement après le
premier (#234) -- un vrai bug d'ergonomie/sécurité des données
trouvé au tout premier usage de l'import Nebula.

Bug réel signalé : importer un export CSV Devices via l'onglet Sites
du hub ne provoquait AUCUNE erreur -- les deux formats partagent une
colonne "Name" (le nom de l'appareil devient interprété comme un nom
de site), des données FAUSSES étaient insérées silencieusement. La
personne a demandé comment annuler, et de rendre le bon type de
fichier plus visible ou détecté automatiquement.

Corrigé en deux temps :
- nebula/api/csv_import.py : nouvelle detect_csv_type(), basée sur
  des colonnes VRAIMENT distinctives vérifiées contre les 3 formats
  réels déjà documentés dans ce module ("Device type" unique à
  Devices, "Connected to" unique à Clients, absence de "MAC address"
  + présence de "Offline devices"/"Template"/"Devices" pour Sites).
  _import_csv_route refuse désormais l'import AVANT toute insertion
  si le fichier ne correspond pas au type attendu par l'onglet actif,
  avec un message indiquant le bon onglet à utiliser.
- nebula/api/app.py : nouvelle route DELETE /imported/<type>,
  ?imported_at=X cible un lot précis (le cas le plus courant : annuler
  ce qu'on vient d'importer par erreur), sans paramètre vide tout
  l'historique du type.

Testé de bout en bout avec le SCÉNARIO EXACT rencontré : import
Devices via /import/sites refusé, 0 ligne insérée (contre des
données fausses avant ce correctif), import correct accepté,
annulation ciblée confirmée (le lot visé disparaît, les autres types
restent intacts).

Côté hub, NebulaView.jsx : bouton renommé "Importer un CSV des
{type}" (précis par onglet actif, plus jamais un libellé générique
ambigu qui a directement causé la confusion), bouton "Annuler cet
import" affiché juste après un import réussi.

nebula/README.md et backlog (item 16) mis à jour.

## 2026-09-03 — Correctif : diagnostic clair sur l'échec de tcpdump (version: 7e97e28bff09, livraison #234)

Premier retour de test en conditions RÉELLES sur le déploiement de la
personne (#233) -- exactement le genre de validation impossible à
faire dans cet environnement de développement, et ça a immédiatement
payé : `GET /capture/status` renvoyait "flux vide -- aucun en-tête
pcap" au lieu de la vraie raison de l'échec de tcpdump.

Bug réel trouvé : capture.py capturait stderr de tcpdump mais ne le
lisait JAMAIS en cas d'échec précoce -- le message remonté était
celui, générique, du parseur pcap en aval (techniquement vrai : le
flux stdout était bien vide), masquant la VRAIE cause (toujours sur
stderr). Corrigé avec le même motif déjà établi dans
ssh-tunnels/api/tunnel_process.py (#210) : courte fenêtre
d'observation (0,5s) après le lancement, lecture de stderr si tcpdump
s'est arrêté pendant cette fenêtre, message remonté tel quel.

Testé avec le cas RÉEL rencontré par la personne ("You don't have
permission to capture on that device") -- confirmé que la vraie
raison est désormais visible via /capture/status. Non-régression
complète du chemin normal (capture qui démarre correctement)
reconfirmée.

network-agent/README.md mis à jour avec ce premier retour de terrain.

## 2026-09-02 (suite) — Agent d'exploration réseau unifié, première tranche (version: 90ca3706f044, livraison #233)

Backlog item 20 -- "un scan réseau plus large, l'agent unifié". La
personne a explicitement clarifié l'architecture avant ce chantier
(session précédente) : un seul agent (le VPN existant sert de
passerelle vers le réseau interne Nebula), une seule tuile hub.

Ni dpkt ni scapy ne sont installables dans cet environnement de
développement (même famille de restriction que pysnmp/sshpass/npm
rencontrée plus tôt) -- nouveau network-agent/api/pcap_parser.py,
analyseur de format pcap en PYTHON PUR, réimplémentant le strict
nécessaire (en-têtes Ethernet/IPv4/ARP/TCP/UDP, structures binaires
de taille fixe documentées depuis les années 1990). Testé
exhaustivement avec des paquets synthétiques : TCP, UDP, ARP, IPv6
(rejeté proprement), paquets tronqués, flux invalides, les deux
boutismes -- deux vrais pièges de construction rencontrés en écrivant
CE TEST (le calcul de boutisme inversé), pas dans l'analyseur
lui-même, corrigés avant de conclure.

network-agent/api/capture.py -- détection du rôle passerelle/routeur
par heuristique RÉSEAU réelle : la résolution ARP ne peut résoudre
qu'une IP du même sous-réseau, donc pour toute IP destination hors du
sous-réseau local, l'OS résout automatiquement la MAC de la
passerelle par défaut -- une MAC qui reçoit régulièrement ce genre de
trafic est très probablement une passerelle. Testé sur un scénario
réseau complet et réaliste (poste local, serveur local, passerelle
relayant vers Internet, découverte par ARP seul, exclusion du
broadcast) -- tout confirmé en un seul passage.

network-agent/api/store.py -- modèle site → segment → appareil →
services, reflétant directement la clarification de la personne.
Découverte VRAIMENT progressive confirmée (first_seen jamais réécrit
sur un appareil déjà connu).

network-agent/api/app.py -- thread de capture en arrière-plan, même
motif que rsyslog-listener (#177). Testé en conditions RÉELLEMENT
dégradées : tcpdump est absent de cet environnement, confirmé que
l'application entière reste pleinement fonctionnelle, l'échec
signalé clairement via /capture/status, jamais un crash.

Nouveaux hub/src/networkAgentClient.js et NetworkAgentView.jsx -- la
tuile UNIQUE demandée, sélecteur site/segment, tableau des appareils
avec rôle détecté, détail des services par appareil. Dockerfile
(tcpdump + CAP_NET_RAW/CAP_NET_ADMIN), docker-compose.yml, routage
passerelle, .env.example tous câblés et vérifiés.

network-agent/README.md et backlog (item 20) mis à jour -- première
tranche livrée, avec un compte-rendu honnête de ce qui reste
(network_mode: host à confirmer selon l'environnement réel de
déploiement, statistiques des usagers hors de portée du seul trafic
capturé, jamais vérifié contre une vraie capture réseau).

## 2026-09-02 (suite) — Pont SNMP → GLPI, deuxième source d'import automatique (version: eb0cc9b6b2a0, livraison #232)

Demandé explicitement : "notre GLPI est quasiment vide, je veux le
remplir plus ou moins automatiquement avec à la fois nos futurs
outils d'exploration et avec les extractions de Nebula". Le pont
Nebula→GLPI existait déjà (#208) -- complété avec un pont SNMP→GLPI
équivalent, suivant fidèlement le même motif.

Nouveau glpi/api/snmp_import.py -- interroge chaque cible SNMP
enregistrée (GET /targets + POST /query par cible, appels
conteneur-à-conteneur vers snmp-api) et crée/complète une entrée GLPI
NetworkEquipment par cible joignable. sysName -> nom (repli sur le
label de la cible si vide), sysLocation -> Location GLPI (dropdown,
même mécanisme que le site Nebula), hôte (IP) -> otherserial (MÊME
champ que Nebula, MAC non disponible depuis le groupe System
interrogé ici). Nouvelle route POST /import/snmp-targets (dry_run par
défaut, comme tous les imports GLPI du projet).

Un vrai bug trouvé et corrigé en testant : un retour inattendu (None)
de la fonction d'interrogation SNMP faisait planter TOUT l'import --
corrigé pour traiter ce cas comme une simple erreur sur la cible
concernée, jamais bloquant pour les autres (même philosophie
qu'ailleurs dans ce projet, #215-225 notamment).

Bouton "Import vers GLPI" ajouté dans SnmpView.jsx (#227), même
section que celle déjà en place côté NebulaView.jsx (#228). Aucune
variable d'environnement nécessaire côté glpi-api -- SNMP_API_INTERNAL_URL
suit le même motif que NEBULA_API_INTERNAL_URL (valeur par défaut
résolue via le DNS interne Docker, jamais explicitement câblée dans
docker-compose.yml, cohérent avec l'existant).

Vérifié réellement : logique d'import testée en isolation (dry-run,
dédoublonnage par hôte, résolution de Location, cas d'échec SNMP
isolé). Route testée de bout en bout : aperçu, confirmation réelle,
échec de snmp-api propagé proprement en 502.

snmp/README.md et backlog (item 15) mis à jour.

## 2026-09-02 (suite) — GLPI Inventory : résumé en lecture seule (version: 6c61699add19, livraison #231)

Cinquième et dernier des cinq chantiers de démonstration -- item 21
(GLPI Inventory), le plus incertain des cinq.

Recherche réelle faite avant de coder : l'inventaire natif de GLPI
10+ a remplacé l'ancien mécanisme FusionInventory par autre chose,
dont l'itemtype exact pour créer/piloter une tâche de découverte via
l'API REST n'a jamais été vérifié dans ce projet. Plutôt que
présenter un formulaire de configuration non vérifié qui pourrait
sembler fonctionnel sans l'être dans une démonstration, portée
volontairement limitée à un résumé EN LECTURE SEULE de ce que GLPI
sait déjà (ordinateurs, équipements réseau déjà inventoriés).

Nouvelle route GET /inventory-summary (glpi/api/app.py) -- comptage +
échantillon de 20 pour Computer et NetworkEquipment, honnête sur le
plafond (capped: true au-delà de 999, jamais un faux total
approximé). Nouveaux hub/src/glpiClient.js et GlpiInventoryView.jsx
-- renvoie vers la note de préparation (#222) pour les questions
toujours ouvertes sur l'infrastructure réelle.

Vérifié réellement : route testée avec des données simulées (comptage
exact, échantillon limité, cas plafonné, échec de connexion propagé
proprement en 502). Structure JSX revérifiée. Aucune nouvelle
variable d'environnement nécessaire (GLPI_API_BASE_URL déjà câblé
depuis #228).

glpi/README.md et backlog (item 21) mis à jour -- item TOUJOURS PAS
COMMENCÉ côté configuration effective de découverte/inventaire, en
attente du recensement des segments réels avec la personne.

---

**Les cinq chantiers demandés pour la démonstration interne (items
16, 21, 4, 11, 13) sont maintenant tous traités** -- quatre
entièrement livrés côté interface (16, 13, 11, 4), le cinquième (21)
livré dans la limite de ce qui est raisonnablement construisible sans
présumer de faits réels sur l'infrastructure de la personne.

## 2026-09-02 (suite) — Connecteur source IMAP + PREMIÈRE interface client IMAP (version: a0179dd43379, livraison #230)

Quatrième des cinq chantiers de démonstration -- item 4 (client IMAP)
désormais complété.

Connecteur source : nouveau champ target_source (nullable) sur les
interpréteurs -- migration ALTER TABLE ADD COLUMN simple (contrairement
à la migration ssh_key_id de #210, aucune contrainte NOT NULL à
lever). NULL = comportement inchangé, strictement OPT-IN. Quand
renseigné, POST /messages/<uid>/interpret pousse aussi le résultat
vers POST /ingest/<target_source> de l'api principal (appel
conteneur-à-conteneur, API_INTERNAL_URL, même motif que
NEBULA_API_INTERNAL_URL côté GLPI #208) -- BEST-EFFORT, jamais
bloquant.

Découverte majeure en cherchant où câbler l'interface : imap-client
n'avait ENCORE AUCUNE interface, pour AUCUN de ses volets --
dossiers, messages, règles de tri, interpréteurs étaient tous
"livrés" côté backend uniquement (#179-191, jamais exposés dans le
hub, contrairement à ce que le backlog laissait entendre). Nouveaux
hub/src/ImapView.jsx et imapClient.js construits avec les quatre
sous-onglets d'un coup.

Vérifié réellement : migration testée contre une base simulant l'état
réel (interpréteur existant intact). Route /interpret testée de bout
en bout : sans target_source (non-régression), avec push réussi (URL
vérifiée : http://api:5000/ingest/<source>), avec push en échec
(réponse toujours 200, résultat toujours renvoyé). Traces debug
ajoutées (cohérent avec #215-225), vérifié explicitement que le
contenu du message n'apparaît jamais. Structure JSX revérifiée,
logique de formulaire testée en isolation.

Route /api/imap-client/ déjà présente côté passerelle -- seul
VITE_IMAP_CLIENT_API_BASE_URL ajouté côté hub, et API_INTERNAL_URL +
dépendance vers le service api ajoutés côté imap-client-api.

imap-client/README.md et backlog (item 4) mis à jour.

## 2026-09-02 (suite) — Catalogue SGBD : extension au portail DBA (version: 6bd2619afb7a, livraison #229)

Troisième des cinq chantiers de démonstration -- item 11 (catalogue
SGBD) désormais entièrement complété.

Découverte importante en investiguant : le module "DBA" n'est PAS une
vue interne au hub principal comme supposé au départ -- c'est un
portail React ENTIÈREMENT SÉPARÉ (dba/portal/), sa propre appli Vite,
son propre App.jsx, son propre client API avec des conventions
différentes ({ok, status, data} plutôt que {error}).

Nouveau dba/portal/src/sshTunnelsApi.js -- client dédié respectant
les conventions de CE portail, pas un copier-coller du client hub.
Nouvel onglet "🗂️ Catalogue SGBD" dans dba/portal/src/App.jsx --
même logique de référence croisée par hôte+port que la version hub
(#221), volontairement dupliquée plutôt que partagée entre les deux
codebases frontend distinctes.

VITE_SSH_TUNNELS_API_BASE_URL ajouté au service dba-portal dans
docker-compose.yml -- les routes passerelle (/api/ssh-tunnels/,
/dba/) existaient déjà, rien à modifier côté tls-proxy.

Vérifié réellement : logique de correspondance hôte/port retestée en
isolation avec les mêmes cas limites que la version hub, gestion
d'erreur testée, structure JSX revérifiée, recherche textuelle
explicite confirmant l'absence du mot de passe (stocké en clair côté
dba-api, caractéristique déjà existante) dans le nouvel onglet.

dba/README.md et backlog (item 11) mis à jour -- item ENTIÈREMENT
LIVRÉ (hub + portail), reste seulement les "autres" modules non
précisés et l'historique du paramétrage.

## 2026-09-02 (suite) — Interface hub Nebula (version: af699f16cab8, livraison #228)

Deuxième des cinq chantiers de démonstration -- item 16 (Nebula)
complété côté interface, en vue intérimaire (le backlog notait
explicitement que la présentation "définitive" serait la tuile
unifiée de l'item 20, agent réseau fusionné, pas encore construit).

Nouveaux hub/src/nebulaClient.js et NebulaView.jsx -- trois
sous-onglets (Sites/Appareils/Clients) avec import CSV par sélection
de fichier, section dédiée pour déclencher l'import vers GLPI (#208)
avec aperçu (dry_run) systématique avant confirmation. Voie CSV
uniquement -- la voie API directe non câblée, pour ne pas présenter
un bouton qui échouerait systématiquement sans le Pro Pack Nebula ni
la clé support Zyxel (deux prérequis bloquants, jamais réunis ici).

Erreur d'inattention repérée et corrigée immédiatement : la
documentation a d'abord été insérée par erreur dans snmp/README.md
au lieu de nebula/README.md -- retirée et replacée au bon endroit
avant de continuer.

Point corrigé avant même de tester : la forme exacte de la réponse du
pont GLPI supposée initialement à tort (compteurs created/updated/
skipped) -- vérifiée contre le vrai code (nebula_import.py) : ce sont
en réalité des LISTES de messages descriptifs (created,
skipped_existing, errors, warnings), jamais des compteurs -- corrigé
avant de livrer.

Nebula-api et glpi-api étaient déjà routés dans la passerelle depuis
#196/#192 -- seuls VITE_NEBULA_API_BASE_URL et VITE_GLPI_API_BASE_URL
ont été ajoutés côté hub.

Vérifié réellement : structure JSX revérifiée, logique de
construction d'URL et de calcul du résumé (comptage par longueur de
liste, y compris avec des clés absentes de la réponse) testée en
isolation.

nebula/README.md et backlog (item 16) mis à jour.

## 2026-09-02 (suite) — Interface hub SNMP (version: ebc4ac2c9a9c, livraison #227)

Premier des cinq chantiers demandés en vue d'une démonstration
interne (items 16, 21, 4, 11, 13) -- item 13 (SNMP) complété côté
interface.

Nouveaux hub/src/snmpClient.js et SnmpView.jsx -- gestion des cibles
enregistrées (créer/supprimer, communauté chiffrée côté serveur,
jamais exposée), interrogation (informations système ou table des
interfaces) sur une cible enregistrée OU un host+communauté en
direct. Câblé dans App.jsx (nouvel onglet "SNMP" dans la barre de
navigation, même motif que Tunnels SSH).

Découverte en câblant l'accès réseau : snmp-api n'était pas encore
routé dans la passerelle (tls-proxy/render_nginx_conf.py) --
contrairement à nebula-api, déjà présent depuis #196. Route
/api/snmp/ ajoutée à la table déclarative, VITE_SNMP_API_BASE_URL
ajouté à docker-compose.yml pour le service hub.

Vérifié réellement : structure JSX revérifiée, logique de
construction des paramètres de requête et de validation testée en
isolation, non-régression du générateur de configuration nginx
confirmée après ajout de la route (33 routes au total, dont
ssh-tunnels/snmp/nebula vérifiées présentes).

snmp/README.md et backlog (item 13) mis à jour.

## 2026-09-02 (suite) — Quatre nouveaux chantiers notés au backlog (version: 775960673516, livraison #226)

Note pure, aucun code touché -- quatre nouvelles tuiles/outils
demandés par la personne, ajoutés au backlog (items 26-29) :
- 26 : gestionnaire de fichiers (GED en arborescence, navigation des
  montages, brique protégée accessible aussi par l'hôte).
- 27 : backup-restore (BackupPC, Clonezilla, comparatif d'une
  solution plus récente, agents multi-OS, statistiques/versions/
  graphe d'historique, indexation de courrier Thunderbird/IMAP).
- 28 : référentiel SI / recherche type Elasticsearch (intégration
  automatique de toutes les API, réseau d'agents pour ne pas saturer
  les systèmes, index IP/localisations/documents sensibles) -- le
  plus vaste des quatre, touche potentiellement tous les modules
  existants.
- 29 : "main2dieu", tour de contrôle des liens sensibles (double
  validation, temporisation, automate SMS) -- recoupe directement
  ssh-tunnels (#210-213) et trb140-sms-relay (#206) déjà construits.

Les quatre sont volumineux et touchent à des faits/décisions qui
dépendent de choix à faire ensemble (architecture, périmètre exact,
priorisation) -- notés fidèlement tels que formulés, sans rien
présumer ni cadrer seul à ce stade.

## 2026-09-02 (suite) — Traçabilité debug : audit rétroactif TERMINÉ (version: 1b0e73ad1692, livraison #225)

Clôture du chantier "généralise le niveau de log" ouvert en #215 --
les 19 modules antérieurs identifiés au démarrage de l'audit
rétroactif (#223) sont désormais tous traités : tts-gu (connexion
MySQL, motif identique aux 5 précédents), pixel-grid/api (GeoIP,
géocodage, communes), schema-analyzer/api/schema_client.py (client
dba-api), tickets/api/backup_manager.py (dump/restauration
PostgreSQL).

Deux points notables trouvés en construisant ce dernier lot, tous
deux vérifiés explicitement avec des valeurs distinctives injectées
dans le VRAI chemin de code plutôt que simplement supposés sûrs :
- pixel-grid/api : les URLs des trois fournisseurs géo (GeoIP,
  géocodage, communes) sont surchargeables via .env -- un
  déploiement pourrait un jour configurer un fournisseur alternatif
  dont l'URL embarque une clé d'API. Traces limitées aux paramètres
  d'entrée (IP, requête, code postal), jamais l'URL résolue -- testé
  avec une clé hypothétique injectée dans une URL de test, confirmée
  absente des traces produites.
- tickets/backup_manager.py : le mot de passe PostgreSQL transite via
  la variable d'environnement PGPASSWORD (même motif que SSHPASS côté
  ssh-tunnels) -- jamais dans la commande elle-même, jamais dans env
  qui n'est jamais tracé.

Décision assumée pour dba/api/connectors/postgres.py : seule
_connect (déjà tracée en #223, le point le plus à risque) reste
couverte -- les 13 méthodes CRUD restantes en bénéficient
indirectement (elles délèguent toutes à _connect), tracer chacune
individuellement représentait un effort disproportionné pour une
valeur marginale, cohérent avec la philosophie pragmatique adoptée
dès le début de cet audit.

Vérifié réellement, à chaque module de ce dernier lot : non-régression
complète et RÈGLE ABSOLUE confirmée par recherche explicite du secret
dans le texte des traces -- mot de passe tts-gu, clé d'API
hypothétique dans une URL géo, mot de passe PostgreSQL de sauvegarde
-- aucun trouvé nulle part.

shared/LOGGING_CONVENTIONS.md et backlog (item 25) mis à jour --
chantier de traçabilité debug ("rien ne doit être silencieux")
ENTIÈREMENT TERMINÉ pour les 19 modules identifiés, en plus de la
chaîne construite pendant cette session (#215-217). Au-delà de cette
liste initiale, la discipline reste à appliquer au fil de l'eau pour
tout nouveau travail.

## 2026-09-02 (suite) — Traçabilité debug : audit rétroactif, deuxième lot (version: a54bbaee46b6, livraison #224)

Suite de #223 -- 7 modules supplémentaires traités : cacti/api,
owncloud/api, owncloud/search-api, ipam/api, optick/api, zenoss/api
(connexion MySQL, motif identique dans 5 d'entre eux, plus
Elasticsearch pour search-api), geo-import/api, rsyslog-listener.
15 des 19 modules identifiés désormais couverts.

Point le plus critique de ce lot, trouvé en lisant geo-import/api/app.py
avant d'écrire quoi que ce soit : le DSN PostgreSQL passé à ogr2ogr
(pg_dsn(), comportement EXISTANT non modifié) contient le mot de
passe EN CLAIR, intégré directement dans la commande subprocess.
Traces ajoutées avec un luxe de précaution : jamais cmd ni dsn
eux-mêmes, seulement table/mode/chemin de fichier -- vérifié
explicitement avec un mot de passe distinctif injecté dans le VRAI
DSN et la VRAIE commande que rien ne fuit dans les traces produites.

rsyslog-listener a demandé une approche différente : c'est un
listener UDP à volume potentiellement élevé (un paquet syslog à la
fois) -- tracer chaque paquet aurait noyé le tampon partagé de bruit
sans valeur ajoutée. Traçage volontairement limité au démarrage du
socket et au ré-enregistrement périodique (déjà throttlé à 300s côté
code existant) -- vérifié explicitement qu'aucune trace supplémentaire
n'apparaît même après plusieurs paquets traités.

Vérifié réellement, à chaque module : non-régression complète, et
RÈGLE ABSOLUE confirmée par recherche explicite du secret dans le
texte des traces capturées -- mots de passe MySQL (5 services),
mot de passe PostgreSQL dans le DSN ogr2ogr (le cas le plus à risque
de ce lot) -- aucun trouvé nulle part.

shared/LOGGING_CONVENTIONS.md et backlog (item 25) mis à jour --
15/19 modules de l'audit rétroactif couverts. Reste : postgres.py
(CRUD), pixel-grid/api, schema-analyzer/api, tts-gu,
tickets/backup_manager.py.

## 2026-09-02 (suite) — Traçabilité debug : audit rétroactif, premier lot (version: 795471d15128, livraison #223)

Reprise du chantier #215-217 ("généralise le niveau de log") --
extension aux modules antérieurs à cette session, explicitement
notée "pas encore couverte" à l'époque. Inventaire des 19 modules
avec des opérations réseau/subprocess identifiés, 8 traités dans ce
premier lot, priorisés sur ceux gérant des identifiants (le plus
utile pour "identifier vite les points de blocage") :
ldap_client.py, glpi_client.py, nebula_client.py, mayan_client.py,
imap_wrapper.py, dba/connectors/mysql.py+postgres.py, vault/admin-api
send_alert_email, tickets/google_oauth.py.

Couverture volontairement PRAGMATIQUE, différente de la profondeur
donnée à la chaîne de #215-217 : les points de passage réseau
UNIQUES (_get/_post chez Nebula, _raise_with_detail chez GLPI/Mayan,
qui couvrent d'un coup TOUTES les méthodes qui en dépendent) et les
fonctions d'établissement de connexion/session -- pas un traçage
exhaustif méthode par méthode, pour pouvoir avancer sur davantage de
modules dans le temps disponible.

Un vrai bug trouvé et corrigé en testant (ldap_client.py) : les
traces utilisaient config.get("host") alors que la vraie clé du dict
de configuration est "url" -- auraient toujours affiché None.

Contrainte d'environnement récurrente rencontrée : psycopg2 et
pymysql non installables ici (même famille de restriction que
sshpass/pysnmp/npm plus tôt cette session) -- testé avec des stubs
minimaux permettant de vérifier la logique réelle (le vrai mot de
passe atteint bien le driver, jamais loggé) sans dépendre de la
présence du driver complet.

Vérifié réellement, à chaque module : non-régression complète (tous
les chemins de succès et d'échec déjà en place retestés), et RÈGLE
ABSOLUE confirmée par recherche explicite du secret dans le texte des
traces capturées -- mot de passe de liaison LDAP, jetons de session
GLPI, clé d'API Nebula, mot de passe Mayan, mot de passe IMAP, mots
de passe MySQL/PostgreSQL, identifiants SMTP du coffre-fort, jetons
OAuth Google (code, client_secret, access_token, refresh_token) --
aucun trouvé nulle part.

shared/LOGGING_CONVENTIONS.md et backlog (item 25) mis à jour avec la
liste précise de ce qui reste : postgres.py (CRUD), cacti, owncloud
(x2), ipam, optick, geo-import, rsyslog-listener, pixel-grid/api,
schema-analyzer/api, tts-gu, zenoss, tickets/backup_manager.py.

## 2026-09-02 (suite) — Note de préparation GLPI Inventory (version: a7f5b68ecac0, livraison #222)

Backlog item 21 -- différent des items précédemment tranchés seul
cette session : les inconnues portent ici sur des FAITS RÉELS
d'infrastructure (combien de segments réseau, lesquels sont isolés),
pas sur des choix de conception que je peux raisonnablement arbitrer
moi-même. Plutôt que d'inventer une topologie, construit le document
de préparation qui organise ce qui est déjà su (recherche réelle sur
GLPI Inventory déjà faite plus tôt cette session) et pose clairement,
dans un tableau, les questions dont les réponses dépendent du terrain.

Nouveau docs/preparation-glpi-inventory.docx -- contexte, les deux
tâches distinctes (discovery puis inventory SNMP), configuration
côté serveur, le point clé sur l'accès réseau direct requis par
segment, la piste ToolBox/glpi-netinventory pour les segments
totalement isolés, et un tableau de 6 questions à trancher avec la
personne avant de pouvoir configurer quoi que ce soit concrètement.

Rendu vérifié visuellement (conversion PDF + capture des deux pages)
avant livraison, comme pour tout document de ce projet.

Backlog (item 21) mis à jour -- reste explicitement PAS COMMENCÉ côté
configuration effective, en attente du recensement des segments
réels avec la personne.

## 2026-09-02 (suite) — Catalogue SGBD : tunnels SSH ↔ connexions DBA (version: 703c8115fc9f, livraison #221)

Backlog item 11 -- demande explicite de faire apparaître les tunnels
SSH comme sources utilisables dans DBA/Analyse de schémas, avec
contrôle et historique. Trois aspects que la personne avait
elle-même signalés comme "à trancher ensemble" -- décisions prises
pour avancer, documentées dans hub/README.md.

Périmètre limité à Analyse de schémas -- ce module reçoit déjà
dbaApiBase ET sshTunnelsApiBase en props depuis App.jsx (cette
dernière jamais utilisée jusqu'ici), point d'intégration le plus
naturel. Modèle en RÉFÉRENCE CROISÉE par hôte+port
(127.0.0.1/localhost + port local du tunnel), jamais une fusion --
aucune modification du schéma dba-api existant, en production.
Historique réutilisant TEL QUEL ssh_credential_usage_history (#210),
aucune nouvelle table.

Nouvelle section "🗂️ Catalogue SGBD" en haut de
SchemaAnalyzerView.jsx (masquée par défaut, chargée à la demande) :
tunnels avec statut, connexions DBA correspondantes, démarrer/arrêter,
historique par tunnel.

Sécurité : dba-api stocke le mot de passe des connexions EN CLAIR
(caractéristique déjà existante, pas introduite ici) -- vérifié
explicitement par recherche textuelle que ce champ n'apparaît nulle
part dans le nouveau catalogue, seul le label est utilisé.

Vérifié réellement : logique de correspondance hôte/port testée en
isolation avec des cas limites (connexion directe jamais confondue
avec un tunnel au même port, 127.0.0.1 et localhost tous deux
reconnus, robustesse chaîne/nombre sur le port). Structure JSX
revérifiée après intégration.

Reste à faire : extension au module DBA lui-même, "autres" modules
non précisés par la personne, historique du PARAMÉTRAGE (pas
seulement l'usage).

## 2026-09-02 (suite) — Calendrier partagé : automatisation de l'export (version: 0d3f13c493fc, livraison #220)

Complète #218-219 -- "reste à faire : automatisation de l'export
périodique" noté explicitement dans ces deux livraisons.

Nouveau run_all_exports.sh -- orchestre les trois exports (SSH,
tickets, GED) + chargements en un seul appel, support SQLite ET
PostgreSQL (PIXEL_GRID_BACKEND, même variable que .env.example,
défaut postgres). Chaque source est indépendante : une base absente
ou un échec d'export n'empêche jamais les deux autres de s'exécuter.
Pensé pour une tâche cron, jamais un ordonnanceur intégré (ce projet
n'en a nulle part ailleurs).

Bug bash RÉEL trouvé et corrigé en testant : la première version
appelait "run_one ... || true" pour qu'un échec d'une source
n'arrête pas les deux autres -- mais dès qu'un appel de FONCTION est
suivi de ||, bash désactive errexit (set -e) pour TOUTE la durée de
cet appel, y compris À L'INTÉRIEUR du corps de la fonction. Résultat
: un export Python en échec (base corrompue) laissait quand même le
chargeur être appelé juste après, sur un CSV absent ou incomplet --
confirmé en testant avec une base SQLite volontairement corrompue.
Corrigé par une vérification EXPLICITE du code de sortie plutôt que
de compter sur la propagation implicite de set -e -- retesté après
correction, confirmé qu'aucun chargement n'est tenté pour la source
en échec.

jq/sqlite3 (CLI) absents de cet environnement de développement --
testé avec des chargeurs SIMULÉS pour isoler et vérifier la logique
d'orchestration elle-même : 3 bases absentes -> aucune erreur
bloquante ; 2 présentes + 1 absente -> exactement les 2 bonnes
sources chargées ; le cas critique (1 base corrompue, décrit
ci-dessus) -> confirmé après correction.

pixel-grid/README.md et backlog (item 10) mis à jour.

## 2026-09-02 (suite) — Calendrier partagé : les trois sources sont connectées (version: 1b95cdf5b709, livraison #219)

Complète #218 -- backlog item 10, les deux sources restantes
(tickets, GED).

Nouveau export_ticket_time_entries.py -- découverte en lisant le
schéma avant d'écrire quoi que ce soit : ticket_time_entries (#115)
est une MEILLEURE source que tickets directement, avec déjà
start_ts/end_ts précis ET technician_login -- exactement la
combinaison utilisateur+plage horaire demandée. Chaque segment
(toujours complet, start_ts/end_ts jamais NULL) devient une paire
ouverture/fermeture, aucune ambiguïté "toujours en cours" à gérer
contrairement à l'export SSH.

Nouveau export_document_links.py -- découverte en vérifiant : les
documents GED vivent dans Mayan (système externe), ged-api n'a AUCUNE
table locale de documents, seulement les liens (document_links).
mayan_client.py n'a d'ailleurs aucune fonction de LISTE de documents
(seulement get_document(id) un par un) -- lister tous les documents
aurait demandé une nouvelle capacité Mayan, pas construite ici.
document_links a en revanche linked_by/linked_at, suffisant sans
appel réseau à Mayan. Modélisation différente assumée : un lien est
un événement PONCTUEL (pas de fin) -- une seule ligne valeur=1 par
lien, pixel-grid l'affichera "EN COURS" (comportement par défaut,
imprécis sémantiquement mais exploitable visuellement).

Les trois exports utilisent déjà le VRAI utilisateur comme nom
(technicien, personne ayant lié un document) -- exploite la "Vue
timeline équipement" déjà en place dans pixel-grid (clic sur un nom
= sa timeline complète) en attendant un vrai filtrage utilisateur
construit dans l'interface elle-même (toujours hors de portée,
vérifié : la table users n'est qu'une ébauche).

Vérifié réellement, pour les deux nouveaux exports : testés contre
des bases simulant le VRAI schéma de chaque service, dont les cas
limites (segment/lien non attribué à un utilisateur). Testés en
sous-processus réel, format CSV vérifié ligne par ligne.

pixel-grid/README.md et backlog (item 10) mis à jour -- les trois
sources explicitement nommées par la personne sont maintenant toutes
connectées. Reste : filtrage utilisateur réel dans l'interface,
automatisation de l'export périodique, mode de coloration "activité"
distinct du "taux d'erreur" réutilisé tel quel.

## 2026-09-02 (suite) — Calendrier partagé : première source connectée (activité tunnels SSH) (version: acd092fd2383, livraison #218)

Backlog item 10 -- demande explicite d'un calendrier partagé
agrégeant plusieurs sources (tickets, GED, activité tunnels SSH)
filtrées par utilisateur et par temps, dans l'esprit de pixel-grid
(module existant). Trois aspects que la personne avait elle-même
signalés comme "à trancher ensemble" -- décisions prises pour
avancer, documentées en détail dans pixel-grid/README.md.

Découverte importante en vérifiant l'architecture existante avant de
construire quoi que ce soit : pixel-grid n'a PAS d'API d'ingestion
temps réel -- "l'écriture ne passe que par generate.sh" -- un export
par lot à rejouer périodiquement, jamais un flux continu. Ce nouveau
script suit donc le même motif déjà établi que parse_zenoss_emails.py.

Nouveau pixel-grid/data-generator/export_ssh_tunnel_activity.py --
lit directement ssh_credential_usage_history (#210), transforme
chaque tentative RÉUSSIE en paire ouverture(1)/fermeture(0),
exploitant l'appariement automatique déjà en place côté pixel-grid
pour les types integer_enum. Les échecs sont délibérément exclus de
cette paire (jamais une connexion fantôme jamais établie représentée
comme "ouverte") -- comptés séparément dans le résumé de sortie.

La dimension "utilisateur" explicitement demandée reste HORS PORTÉE
de cette livraison -- vérifié : la table users de pixel-grid n'est
qu'une ébauche structurelle, aucun filtrage réel n'existe dans
l'interface actuelle aujourd'hui. created_by conservé dans les
données de chaque événement pour ne pas perdre l'information, mais
son exploitation reste à construire séparément dans pixel-grid
lui-même.

Vérifié réellement, en profondeur : testé contre une base simulant le
VRAI schéma de ssh_credential_usage_history -- connexion réussie et
fermée, connexion réussie mais toujours en cours (confirmé
explicitement : aucune fermeture fantôme générée), échec exclu de
toute paire, résumé de sortie honnête. Un point de rigueur corrigé
avant même de tester : la conversion de date utilisait initialement
time.mktime (sensible au fuseau local et à l'heure d'été) -- remplacée
par calendar.timegm, la méthode correcte pour un timestamp UTC.
Testé aussi en sous-processus réel (CLI complet), format CSV exact
vérifié ligne par ligne.

pixel-grid/README.md et backlog (item 10) mis à jour. Reste à faire :
sources tickets et GED, filtrage utilisateur réel (nécessite
d'étendre pixel-grid lui-même), automatisation de l'export périodique.

## 2026-09-02 (suite) — Traçabilité debug : secrets_tool.py et secrets_alert.py, chantier de session terminé (version: 284126d0c59e, livraison #217)

Suite et clôture de #215-216 -- couverture des deux derniers modules
récents non encore tracés.

secrets_tool.py : cet outil tourne HORS Docker, sur la machine de la
personne, pas connecté au tampon partagé Memcached des autres
services -- mécanisme différent nécessaire. Nouveau flag --debug en
ligne de commande, configure un handler console dédié pointé sur
STDERR uniquement (jamais STDOUT, qui doit rester composé
UNIQUEMENT de lignes export pour decrypt-env et son eval dans
scripts/run.sh). Une fois activé, les traces internes de
secret_crypto.py remontent automatiquement (logger enfant du logger
racine que --debug configure) -- vérifié explicitement en conditions
réelles : sous-processus réel, entrée pipée, recherche textuelle du
secret et de la phrase de passe dans TOUTES les sorties (stdout ET
stderr) -- confirmé absentes partout, y compris avec un secret et
une phrase de passe volontairement très distinctifs pour exclure
toute coïncidence.

secrets_alert.py : traces sur les deux canaux (SMS, courriel) --
durée de chaque tentative, présence (booléen) des identifiants
configurés, jamais leur valeur (clé d'API SMS, mot de passe SMTP).

Vérifié réellement : non-régression complète sur les deux modules
(tous les cas déjà testés en #204-206 rejoués avec succès). Règle
absolue vérifiée explicitement par recherche du secret dans le texte
des traces capturées, à chaque module.

shared/LOGGING_CONVENTIONS.md et backlog (item 25) mis à jour --
chantier de traçabilité de CETTE SESSION désormais terminé (toute la
chaîne chiffrement/SSH/SNMP/alertes). Reste un chantier à part, noté
et volontairement reporté : l'audit rétroactif des ~25 modules
antérieurs à cette session.

## 2026-09-02 (suite) — Traçabilité debug : extension à snmp_client.py (version: 25d3451cb4ae, livraison #216)

Suite directe de #215 -- couverture des appels réseau SNMP (GET/WALK),
tout aussi susceptibles de bloquer/échouer silencieusement que les
lancements de processus SSH déjà couverts (cible injoignable,
communauté refusée, délai réseau). Durée de chaque échange tracée,
chaque tour de WALK numéroté (repère précis en cas de blocage sur une
cible qui répond partiellement).

RÈGLE ABSOLUE respectée : la communauté SNMP (fonctionnellement un
mot de passe) n'apparaît jamais dans les traces, seule sa longueur.
Vérifié explicitement par un test dédié -- un faux positif rencontré
en testant (assertion attendant "31 caractères" au lieu de "30") :
confirmé qu'il s'agissait d'une erreur de comptage dans mon propre
test, pas un défaut du code -- le code traçait déjà la bonne longueur
réelle. Non-régression complète vérifiée (get_system_info,
walk_interfaces, cas d'erreur réseau).

shared/LOGGING_CONVENTIONS.md et backlog (item 25) mis à jour.
Restent sans traçabilité renforcée : secrets_tool.py/secrets_alert.py
et l'ensemble des modules antérieurs à cette session.

## 2026-09-02 (suite) — Traçabilité debug systématique, "rien ne doit être silencieux" (version: 52f57be98522, livraison #215)

Demandé explicitement : "vérifier que toutes les étapes soient
logguées en debug, de façon à tracer l'ensemble des étapes à risque
et identifier vite les points de blocage, rien ne doit être
silencieux -- on fera des passes d'optimisation ensuite".

Trouvaille de fond, corrigée en premier lieu : aucun service de ce
projet ne configurait explicitement le niveau du logger racine
Python -- il restait à sa valeur par défaut (WARNING). Le niveau du
LOGGER filtre AVANT même qu'un enregistrement n'atteigne un handler
quelconque : tout appel logging.debug(...) était donc SILENCIEUSEMENT
REJETÉ, quelle que soit la valeur de LOG_CAPTURE_LEVEL (qui ne filtre
qu'au niveau du handler, en aval -- beaucoup trop tard). Confirmé
explicitement par un test reproduisant le problème AVANT correctif.

Corrigé de façon CENTRALISÉE dans shared/log_buffer.py --
make_shared_log_handler positionne désormais le logger racine à
DEBUG -- s'applique automatiquement aux ~30 services de ce projet qui
appellent déjà cette fonction, sans modification individuelle de
chacun. LOG_CAPTURE_LEVEL (toujours WARNING par défaut) continue de
déterminer ce qui est réellement conservé dans le tampon partagé --
le comportement par défaut reste inchangé, silencieux comme avant,
mais élever LOG_CAPTURE_LEVEL=DEBUG pour un service précis suffit
désormais à voir immédiatement toute sa trace fine.

Traces DEBUG ajoutées sur la chaîne chiffrement/authentification la
plus critique (modules récents, #202-210, à plus haut risque de
blocage silencieux) : shared/secret_crypto.py (durée de la
dérivation PBKDF2 tracée, utile pour détecter un ralentissement
anormal), les deux credential_crypto.py (ssh-tunnels et snmp),
tunnel_process.py/mount_process.py (lancement/arrêt de vrais
processus OS externes -- PID, code retour, contenu de stderr
systématiquement tracés).

RÈGLE ABSOLUE respectée et vérifiée explicitement par des tests
dédiés à chaque module touché : aucun secret (phrase de passe, mot de
passe, communauté SNMP, contenu déchiffré) n'apparaît JAMAIS dans un
message de log, à aucun niveau -- recherche du secret dans le texte
des traces capturées à chaque test. Non-régression complète vérifiée
à chaque étape (tunnel_process.py, mount_process.py, les deux
credential_crypto.py, et un test de bout en bout sur prefs-api --
service qui utilise le plus intensément ce mécanisme -- confirmant
que le correctif central n'a rien cassé).

Nouveau shared/LOGGING_CONVENTIONS.md documentant la convention
complète. Item 25 ajouté au backlog. Portée volontairement limitée à
la chaîne la plus critique -- un audit rétroactif complet des ~30
services (snmp_client.py, secrets_tool.py, et tous les modules
antérieurs à cette livraison) reste un chantier à part, à traiter au
fil de l'eau plutôt que d'un bloc.

## 2026-09-02 (suite) — Détection et aperçu du HTML dans DBA (version: be1ef214bfa3, livraison #214)

Backlog item 7 -- tickets d'anciennes gestions (importés en dump
MySQL dans DBA) rédigés en HTML, affichés tels quels jusqu'ici
(balises brutes), illisibles en l'état. Décision prise pour le
déclencheur resté ouvert ("bouton par cellule ? icône dans
l'en-tête ?") : icône "📄 Aperçu" dans la cellule dès détection d'un
contenu HTML plausible, à côté d'un extrait de texte brut (balises
retirées, tronqué), ouvrant une fenêtre volante centrée avec le rendu
complet.

Nouveau hub/src/htmlContentUtils.js -- détection par expression
régulière, assainissement léger fait main avant tout rendu
(dangerouslySetInnerHTML) : scripts/styles retirés entièrement
(contenu compris), iframe/object/embed retirés, attributs on*
retirés, javascript: neutralisé.

npm install dompurify tenté -- npm est INACCESSIBLE dans cet
environnement de développement (403 même en simple consultation via
npm view, pas seulement à l'installation) -- pas de bibliothèque de
référence disponible ici. Assainissement fait main documenté comme
volontairement léger, proportionné au contexte réel (données
internes déjà importées, pas de contenu externe non fiable) --
jamais présenté comme une défense contre un contenu réellement
hostile.

Vérifié réellement, en profondeur : détection et assainissement
testés de façon exhaustive. Un vrai bug trouvé et corrigé en
testant : les balises auto-fermantes (<br/>) n'étaient PAS détectées,
l'expression régulière ne prévoyait pas le / sans espace avant le >.
Script/style retirés avec leur contenu, attributs on* retirés sur
n'importe quel élément, javascript: neutralisé en conservant la
structure du lien, iframe retiré entièrement, entrées non-chaîne
gérées sans exception. Aperçu tronqué testé avec un exemple réaliste
de ticket. Structure JSX revérifiée après intégration.

## 2026-09-02 (suite) — Module SNMP : gestion des cibles enregistrées (version: 70459c108719, livraison #213)

Complète #212 -- volet 2 de la demande d'origine ("gestion des
paramètres d'accès sécurisés"). Nouveau credential_crypto.py +
targets_store.py, même motif que ssh-tunnels/api/credential_crypto.py
(#210) : une cible = hôte+port+communauté nommé et réutilisable,
communauté chiffrée via secret_crypto.py (#202-206), jamais stockée
ni exposée en clair. /query et /walk-interfaces acceptent toujours
host+community en direct pour un usage ponctuel (comportement de
#212 inchangé).

API : GET/POST /targets, DELETE /targets/<id>. community_encrypted
jamais exposé (défense en profondeur, même motif que
password_encrypted côté ssh-tunnels-api).

Vérifié réellement : CRUD testé en profondeur. Bout en bout via l'app
réelle : un vrai piège de monkey-patching Python rencontré et corrigé
en testant -- patcher stub.get_cmd après que snmp_client.py ait déjà
fait "from ... import get_cmd" n'affecte pas sa référence déjà liée ;
corrigé en patchant snmp_client.get_cmd directement. Une fois corrigé,
confirmé explicitement que la VRAIE communauté déchiffrée (pas un
jeton, pas une valeur factice) atteint bien l'appel pysnmp sous-jacent.
Non-régression du mode direct (host+community) reconfirmée.

## 2026-09-02 (suite) — Nouveau module SNMP : premier socle (version: f7efe3df8800, livraison #212)

Backlog item 13, demande explicite avec trois volets et trois aspects
que la personne a elle-même signalés comme "à trancher ensemble le
moment venu" (portée du "déploiement automatisé", quelles
informations analyser, niveau de scan). Décisions prises pour
avancer plutôt que d'attendre -- documentées en détail, à corriger si
elles ne conviennent pas (voir snmp/README.md) : SNMPv1/v2c
seulement (SNMPv3 reporté), groupe System + table des interfaces
(SNMPv2-MIB/IF-MIB, les deux MIB les plus universellement
supportées), pas de scan de ports (volet 1 de la demande, chantier à
part), pas de "déploiement automatisé" (terme resté ambigu, rien
construit dessus plutôt que deviné).

Bibliothèque retenue : pysnmp, fork lextudio/pysnmp -- vérifié ACTIF
avant de le choisir (l'original etingof/pysnmp est à l'abandon depuis
2022, décès du mainteneur). Version 7.1.21 confirmée réellement
publiée par deux sources indépendantes avant d'être fixée.

Nouveau module snmp/ : snmp_client.py (GET du groupe System, WALK de
la table des interfaces avec traduction ifOperStatus selon RFC 2863),
app.py (POST /query, POST /walk-interfaces), Dockerfile, câblage
docker-compose.yml.

pysnmp n'étant pas installable dans cet environnement (réseau
restreint), tout le code a été écrit à partir de la documentation
OFFICIELLE (docs.lextudio.com/pysnmp/v7.1), exemples vérifiés un par
un avant d'écrire quoi que ce soit. Vérifié réellement : la logique
d'enveloppe (formatage, traduction des erreurs et des codes de
statut) testée contre une SIMULATION FIDÈLE de l'API réelle
reconstruite d'après ces exemples exacts -- succès, erreur réseau,
erreur SNMP, walk multi-lignes avec fin de MIB, route Flask de bout
en bout. PAS vérifié : l'appel réseau réel contre un vrai équipement
-- à confirmer en priorité au premier usage réel.

Reste à faire : SNMPv3, scan de ports, gestion/stockage des
identifiants d'accès (pourrait réutiliser secret_crypto.py comme
fait pour ssh-tunnels en #210), interface hub (backend seul).

## 2026-09-02 (suite) — Authentification SSH par mot de passe : interface hub, item 12 complet (version: ee2285625af6, livraison #211)

Complète #210 -- interface hub pour l'authentification SSH par mot
de passe (backlog item 12).

Correctif trouvé AVANT même de construire l'écran : la route
POST /connections exigeait ssh_user ET password_username séparément
en mode mot de passe pour la même information -- confusion repérée en
concevant le formulaire (pourquoi remplir deux champs redondants ?),
corrigée dans app.py : ssh_user requis SEULEMENT en mode clé,
password_username porte seul ce rôle en mode mot de passe (stocké
aussi comme ssh_user en base pour satisfaire la contrainte NOT NULL,
de façon cohérente). Non-régression du mode clé reconfirmée après ce
correctif.

sshTunnelsClient.js : createConnection étendu (auth_method,
password_username, password), nouvelle fonction
fetchConnectionUsageHistory. SshTunnelsView.jsx : sélecteur clé/mot
de passe dans le formulaire de création, champs conditionnels sans
redondance, indicateur 🔑/🔒 par connexion dans la liste, historique
d'usage consultable par connexion (chargé à la demande, jamais tout
récupéré d'un coup), durée calculée à partir de started_at/ended_at.

Vérifié réellement : correctif ssh_user/password_username retesté de
bout en bout (création sans ssh_user redondant réussie, non-régression
du mode clé reconfirmée). Logique de calcul de durée et de bascule
d'affichage testée en isolation. Structure JSX revérifiée après
chaque édition.

Backlog item 12 (authentification SSH par mot de passe) désormais
ENTIÈREMENT LIVRÉ, backend (#210) et interface (#211).

## 2026-09-02 (suite) — Authentification SSH par mot de passe : backend complet (version: 8d63c52ff725, livraison #210)

Backlog item 12, contexte donné par la personne : certains vieux
systèmes refusent la connexion par clé SSH. Demande explicite :
gestion sécurisée de couples utilisateur/mot de passe (jamais en
clair), avec un historique d'usage. Chantier touchant du code SSH
déjà en production (tunnel_process.py/mount_process.py, plusieurs
bugs réels déjà corrigés dessus -- #184, #185, #188) -- procédé par
étapes, non-régression vérifiée à chaque changement.

tunnel_process.py/mount_process.py : nouveau auth_method="password",
commande enveloppée dans sshpass -e (BatchMode=yes désactivé
seulement en mode mot de passe), mot de passe transmis UNIQUEMENT via
la variable d'environnement SSHPASS du sous-processus -- jamais sur
la ligne de commande. Non-régression du mode par clé (par défaut)
vérifiée : commande strictement identique à avant.

tunnels_store.py : migration ssh_key_id (NOT NULL à l'origine) rendu
NULLABLE -- SQLite ne permet pas de modifier une contrainte NOT NULL
directement, reconstruction de table dans une transaction explicite.
Testée contre une base SIMULANT EXACTEMENT l'état réel déjà en
production (connexions et tunnels existants) : rien perdu, rien
dupliqué, auth_method rétro-rempli à 'key' pour toutes les connexions
existantes. Nouvelle table ssh_credential_usage_history (succès ET
échecs, durée calculable via ended_at).

Nouveau credential_crypto.py (enveloppe secret_crypto.py, #202-206) --
SSH_TUNNELS_CRED_PASSPHRASE/SALT fournis EN CONTINU à ce conteneur
(différence assumée avec les secrets de démarrage .env.encrypted,
déchiffrés une seule fois au lancement -- un mot de passe SSH stocké
doit pouvoir être déchiffré bien après le déploiement).

app.py : routes connexions/tunnels/montages étendues pour les deux
modes d'authentification. password_encrypted JAMAIS exposé via l'API
(repéré et corrigé avant même de tester, défense en profondeur).

Vérifié réellement, en profondeur : non-régression rigoureuse du mode
par clé (commande SSH identique, migration testée contre une base
réelle simulée, démarrage/arrêt testés via l'app réelle dont le cas
clé désactivée -> 409). Mode mot de passe testé de bout en bout :
création, rédaction confirmée à la liste ET à la création, VRAI mot
de passe déchiffré transmis au bon endroit, échec correctement
historisé (jamais un faux succès trouvé et corrigé avant même de
livrer), fermeture d'historique à l'arrêt.

Reste à faire : interface hub (SshTunnelsView.jsx) -- backend
construit et testé, pas encore câblé côté écran.

## 2026-09-02 (suite) — Extension de l'indicateur "action en cours" à GED et Analyse de schémas (version: d3820ef4377c, livraison #209)

Reprise de l'item 18 du backlog (diode orange, #197) -- extension aux
écrans qui en manquaient encore. GedView.jsx : envoi de document
(bouton "Envoyer" -> "🟠 Envoi en cours…") et envoi de nouvelle
version (par document, même motif de state dédié que
SshTunnelsView.jsx -- aucune fuite d'état entre documents, testé).
SchemaAnalyzerView.jsx : import des propositions détectées ("🟠 Import
en cours…") -- et harmonisation du préfixe sur l'indicateur d'analyse
qui existait déjà avant #197 mais sans le 🟠.

Vérifié réellement : logique de calcul testée en isolation (état "en
cours" correctement isolé par document, aucune fuite vers un autre
document). Structure JSX des deux fichiers revérifiée après édition.

Documentation (ssh-tunnels/README.md, qui centralise le suivi de cet
indicateur transversal) et backlog (item 18) mis à jour. Reste sans
objet : imap-client/GLPI/Nebula n'ont pas de tuile hub (backend
seul) -- rien à indiquer visuellement tant que ces écrans n'existent
pas.

## 2026-09-02 (suite) — Import Nebula vers GLPI (version: 712122599845, livraison #208)

Backlog item 16, endpoint déjà repéré depuis #200. Nouveau
glpi/nebula_import.py : importe les appareils Nebula déjà importés
côté nebula-api (#200, GET /imported/devices) vers GLPI. Route
POST /import/nebula-devices (dry_run par défaut), appel conteneur-à-
conteneur vers nebula-api (NEBULA_API_INTERNAL_URL, jamais l'API
Nebula publique directement).

Types réels rencontrés dans les fichiers fournis par la personne
(#200) : Access point, Switch, Firewall -- tous mappés vers
NetworkEquipment, le type GLPI dédié au matériel réseau.

Point vérifié PUIS corrigé AVANT même de tester : l'adresse MAC n'est
PAS une colonne directe de glpi_networkequipments -- confirmé en
recherchant (une requête SQL réelle vue dans un rapport de bug GLPI
référence port.mac depuis glpi_networkports, un sous-objet séparé).
Créer ce sous-objet par appareil ajouterait un appel API
supplémentaire par appareil -- complexité volontairement reportée,
même raisonnement que les adresses MAC multiples déjà différées dans
l'import Excel (#192). Utilisée à la place : otherserial (champ texte
libre générique GLPI) pour le dédoublonnage -- plus prudent qu'un
champ mac direct qui n'existe probablement pas, mais ce choix de
repli lui-même pas vérifié contre un vrai GLPI, à confirmer en
priorité au premier import réel.

Vérifié réellement : mapping testé (3 vrais types Nebula, type
inconnu correctement signalé jamais silencieux), MAC dans otherserial
confirmé, cache de dropdown Location efficace (un seul appel pour
deux appareils du même site), dédoublonnage testé (appareil déjà
présent -> sauté, jamais de doublon), dry-run confirmé sans aucun
appel réseau vers GLPI. Route testée de bout en bout avec nebula-api
simulé : succès avec 2 appareils réalistes, nebula-api injoignable
(502, message clair), erreur HTTP de nebula-api propagée proprement.

## 2026-09-02 (suite) — Vue graphique de l'architecture du projet (version: aa876001534e, livraison #207)

2e volet de la demande "transparence" (le 1er, l'historique versionné
de la matrice de risques, livré en #199) : "une vue graphique de
l'architecture large du projet incluant : les ressources/supports,
les clés de conf et chemins, les stacks et les projets liés externes
(Passerelle SMS, ...)".

Nouveau docs/architecture-projet.svg, généré à partir des VRAIES
données du projet (services réels de docker-compose.yml, préfixes de
clés de .env.example, README des modules) -- jamais improvisé.
Quatre régions du stack principal (interfaces, modules métier,
sécurité/secrets, données/stockage), le stack gateway/ séparé
(Keycloak/tls-proxy), et sept systèmes EXTERNES clairement distingués
par une bordure pointillée : GLPI existant, Zyxel Nebula, passerelle
SMS Teltonika TRB140, annuaire LDAP/AD, GED Mayan, bases de données
distantes, équipements réseau supervisés.

Bug réel trouvé et corrigé AVANT même de livrer : converti le SVG en
image (LibreOffice) pour le regarder réellement, plutôt que de faire
confiance aux coordonnées calculées seules -- deux régions (Modules
métier, Sécurité et secrets) débordaient nettement de leur cadre.
Corrigé en recalculant précisément les hauteurs à partir du nombre
réel de lignes de texte, avec des rangées de grille alignées plutôt
que des hauteurs disparates -- revérifié visuellement après
correction, plus aucun débordement.

Nouvelle route GET /architecture-diagram (prefs-api) -- sert le SVG
avec le vrai type MIME (image/svg+xml), lu depuis
PROJECT_ROOT_PATH/docs/ (même montage que /docs existant). Chemin
FIXE, jamais fourni par le client -- aucune surface d'attaque par
chemin contrairement à /docs/<path>. Nouvel onglet "Architecture"
dans l'écran Cyber (CyberView.jsx), simple <img>.

Vérifié réellement : SVG inspecté visuellement à deux reprises (avant
et après correction du débordement). Route testée -- type MIME
correct, contenu identique octet pour octet au fichier réel sur
disque. Structure JSX de CyberView.jsx revérifiée après ajout du
4e onglet.

Non vérifié dans cet environnement : rendu réel dans un navigateur
(vérifié via conversion LibreOffice, pas via un moteur de rendu SVG
de navigateur -- généralement plus permissif, risque résiduel faible).

Fichier statique -- à régénérer manuellement si l'architecture du
projet évolue significativement (pas de mécanisme de mise à jour
automatique, le script générateur n'est pas conservé dans le dépôt).

Item 24 du backlog ajouté, récapitulant les deux volets transparence
(#199 + #207) désormais tous deux livrés.

## 2026-09-02 (suite) — Alertes SMS/courriel du PRA, entièrement câblées (version: a0d93a73f34c, livraison #206)

Suite directe du chantier chiffrement : automatisation des deux
canaux d'alerte décrits dans le PRA (docs/pra-secrets-demarrage.docx
section 4 -- "une passe phrase et un SMS avec code au travers de la
partie non authentifiée de la passerelle sms, plus une alerte mail
sur des adresses non personnelles").

Nouveau shared/secrets_alert.py -- deux canaux indépendants,
entièrement optionnels (variable d'environnement absente = canal
ignoré silencieusement, jamais une erreur). Canal SMS : appelle
réellement la route /send de la passerelle Teltonika TRB140 (clé de
service, indépendante de Keycloak -- conforme à la vérification faite
en #203). Canal courriel : SMTP direct en bibliothèque standard
uniquement (smtplib) -- jamais de nouvelle dépendance à installer sur
le poste de la personne, ce module tournant hors Docker via
scripts/run.sh. Câblé dans secrets_tool.py decrypt-env : les deux
canaux sont tentés en best-effort après un déchiffrement réussi.

Vérifié réellement, y compris avec de VRAIS échecs réseau (noms
d'hôte inexistants, pas seulement des simulations) : confirmé qu'un
échec des deux canaux d'alerte ne contamine jamais stdout (qui doit
rester composé uniquement de lignes "export" pour l'eval de run.sh)
et ne fait jamais échouer le déchiffrement par ailleurs réussi --
condition de sécurité nécessaire, testée explicitement plutôt que
supposée. Suite de tests complète aussi en mode simulé : URL
correctement construite pour l'appel SMS, réponse HTTP non-200
gérée proprement, SMTP avec/sans échec, les deux canaux ensemble.

État du chantier chiffrement (points 2/3 + PRA, urgence matrice de
risque) : primitives, PRA, CLI, câblage run.sh, et maintenant les
deux canaux d'alerte -- tous livrés et testés. Ne reste que la
migration des VRAIS secrets du projet, qui nécessite un accès aux
fichiers réels de la personne (hors de portée de cet environnement)
et une décision consciente de sa part sur le moment de la faire.

## 2026-09-02 (suite) — Câblage réel du chiffrement dans scripts/run.sh (version: d9a8536551c4, livraison #205)

Suite directe du chantier chiffrement (points 2/3 urgence matrice de
risque) : nouvelles commandes encrypt-env/decrypt-env dans
scripts/secrets_tool.py, et câblage dans scripts/run.sh. Fichier
.env.encrypted optionnel à la racine du projet : absent = comportement
RIGOUREUSEMENT inchangé (aucune invite, aucun message). Présent : la
phrase de passe maîtresse est resaisie à chaque lancement (jamais
stockée sur disque), les secrets déchiffrés sont exportés dans le
seul processus shell en cours, pour la durée du seul appel à docker
compose -- rien ne survit après la fin du script.

Bug réel trouvé et corrigé en testant : une valeur VIDE dans un .env
source (motif courant de ce projet -- .env.example en contient
beaucoup) faisait échouer TOUT le déchiffrement dès la première
rencontrée. Corrigé pour traiter une valeur vide symétriquement à
l'écriture (jamais chiffrée) et à la lecture (jamais déchiffrée).

Vérifié réellement, en profondeur :
- Sécurité du passage par le shell : fichier de test contenant
  volontairement $, ', ", backtick et espaces dans une valeur --
  confirmé identique après le cycle complet chiffrement -> .env.encrypted
  -> déchiffrement -> eval bash, aucune interprétation shell indésirable
  (protection shlex.quote). Confirmé aussi que le prompt et les
  messages d'état de decrypt-env passent par stderr, jamais stdout
  (condition nécessaire pour un eval sûr).
- scripts/run.sh testé de bout en bout avec un FAUX docker compose
  (script substitué, affichant les variables reçues) : sans
  .env.encrypted, comportement inchangé confirmé ; avec, les secrets
  déchiffrés atteignent bien docker compose avec leur valeur exacte
  d'origine, testé sur deux secrets réalistes dont un avec espaces.

Documentation (docs/chiffrement-secrets.md) et backlog (item 22) mis
à jour avec l'état d'avancement complet et la procédure de migration.
Reste volontairement pas fait : migration des VRAIS secrets du projet
(l'outil est prêt et testé, la décision de l'utiliser reste à prendre
consciemment), et les deux canaux d'alerte du PRA (SMS/courriel).

## 2026-09-02 (suite) — CLI de chiffrement des secrets + note backlog coquille Docker distante (version: cfac1b049842, livraison #204)

Note ajoutée au backlog (item 23, aucun code) : coquille Docker
générique à déployer sur un serveur distant (Proxmox chez OVH),
reliée au hub par un canal VPN sortant, à gérer aux côtés des
tunnels SSH dans une nouvelle section VPN -- but annoncé : héberger
un kanban+dépôt de fichiers pour les spécifications, et un
environnement de test/déploiement à distance type notebook avec
pseudo bureau web. Très en amont, rien tranché sur la technologie.

Suite du chantier chiffrement (points 2/3 urgence matrice de risque)
: nouveau scripts/secrets_tool.py -- CLI (init-salt, encrypt-value,
decrypt-value, encrypt-file, decrypt-file) au-dessus des primitives
de shared/secret_crypto.py (#202). Ne touche JAMAIS un secret réel du
projet -- produit des valeurs/fichiers chiffrés que la personne
choisit ensuite d'utiliser ou non. Phrase de passe jamais acceptée en
argument de commande (fuiterait dans l'historique shell) -- toujours
saisie masquée via getpass.

Nouveau docs/chiffrement-secrets.md -- suivi technique consolidé de
tout ce chantier (état d'avancement, usage du CLI), complète le PRA
formel (#203) sans le dupliquer.

Vérifié réellement : cycle complet chiffrement/déchiffrement d'une
valeur ET d'un fichier (simulant une vraie clé SSH) testé. Protections
critiques confirmées : un sel déjà existant n'est JAMAIS régénéré
(même si init-salt est rappelée), une tentative de déchiffrement sans
sel existant échoue proprement sans en inventer un, mauvaise phrase
de passe échoue proprement (code 1, jamais un plantage), fichier
original jamais modifié après chiffrement. Testé aussi en
SOUS-PROCESSUS RÉEL avec entrée pipée (pas seulement en import direct
des fonctions) -- confirme que le câblage argparse/getpass fonctionne
de bout en bout.

## 2026-09-02 (suite) — PRA secrets de démarrage : procédure documentée et vérifiée contre le vrai code TRB140 (version: d1239d21c891, livraison #203)

Réponse au point 4 de l'urgence matrice de risque, enrichie par la
personne : "une passe phrase et un SMS avec code au travers de la
partie non authentifiée de la passerelle sms, plus une alerte mail
sur des adresses non personnelles". La personne a fourni l'archive
complète du projet trb140-sms-relay (projet séparé) pour vérification.

Nouveau docs/pra-secrets-demarrage.docx (3e document de gouvernance,
même famille que la charte et la notice #194) : procédure à 3 canaux,
scénarios de reprise (personne indisponible, Keycloak indisponible,
perte de la phrase de passe -- irrécupérable, aucune porte dérobée).

Vérifié RÉELLEMENT contre le vrai code fourni, jamais présumé à
partir de la seule mémoire de conversations précédentes : la route
/send de la passerelle SMS accepte bien une clé de service ou des
identifiants applicatifs, indépendamment de Keycloak -- confirme
l'hypothèse de conception du PRA. Point corrigé après vérification :
la fonction d'envoi de courriel du projet existe mais est strictement
interne à la redistribution des SMS reçus, pas exposée comme service
réutilisable -- le canal courriel de cette procédure reste donc à
construire, contrairement à ce qu'une première version du document
aurait pu laisser croire.

Nouvelle fonction ensure_governance_document_present(name) (prefs-api)
-- migration GÉNÉRALE (pas spécifique à ce document) pour ajouter un
document précis à une base déjà peuplée sans toucher aux documents
existants ni créer de doublon. Testée contre une base SIMULANT
EXACTEMENT l'état réel déjà déployé (2 documents sans le PRA) :
confirmé, le troisième document s'ajoute proprement, les métadonnées
des deux autres restent inchangées, contenu téléchargé identique
octet pour octet, migration rejouée sans effet.

## 2026-09-02 (suite) — Chiffrement des secrets de démarrage : primitives (version: 7764d315cd31, livraison #202)

Reprise des points 2/3 de l'urgence matrice de risque ("mots de
passe stockés en clair -> chiffrer et imposer une réinjection de la
clé à chaque déploiement", "clés de connexion SSH non chiffrées :
chiffrer avec la clé d'admin"). Conclusion du point 4 (déjà actée en
#198) appliquée : ces secrets de démarrage restent indépendants du
coffre-fort et de Keycloak, pour éviter la boucle identifiée.

Nouveau shared/secret_crypto.py -- primitives de chiffrement
symétrique : PBKDF2-HMAC-SHA256 (600 000 itérations, valeur vérifiée
via l'OWASP Password Storage Cheat Sheet le jour de cette livraison,
jamais choisie de mémoire) dérive une clé à partir d'une phrase de
passe + un sel non secret, Fernet (AES-128-CBC + HMAC authentifié)
pour le chiffrement effectif. Versions chaîne (encrypt_value/
decrypt_value, pour les secrets .env) et binaire (encrypt_bytes/
decrypt_bytes, pour les clés SSH).

Portée volontairement limitée à ces primitives, testées de façon
exhaustive (21 cas : aller-retour, déterminisme de la dérivation,
mauvaise phrase de passe et mauvais sel rejetés proprement, jeton
altéré rejeté, phrase de passe vide refusée, sel invalide refusé,
salage confirmé effectif, sémantique de sécurité Fernet confirmée
-- chiffrer deux fois le même contenu produit des jetons différents
--, unicode, chaîne vide vs None, contenu binaire long simulant une
vraie clé SSH). Un vrai faux-positif trouvé et corrigé dans MON
PROPRE test (pas l'implémentation) : `b"trop court"` fait en réalité
10 octets, au-dessus du seuil de validation -- corrigé avec un sel
réellement court pour confirmer le rejet.

PAS ENCORE fait, volontairement : le câblage dans scripts/run.sh
(réinjection de la phrase de passe à chaque déploiement), la
migration des secrets RÉELS déjà en place (.env, clés SSH
existantes), et le CLI pour chiffrer une valeur donnée. Un sujet où
une erreur peut rendre des secrets définitivement inaccessibles
mérite d'être validé étape par étape -- cette livraison est la
fondation, pas le résultat final.

## 2026-09-02 (suite) — Clarification : agent réseau unifié + tuile unique (version: e89995ae72f2, livraison #201)

Documentation uniquement, aucun code -- réponse à la question posée
en #200 ("l'agent Nebula à concevoir et la tuile big-brother
décrivent-ils la même chose ?"). Réponse de la personne : "un seul
agent car je suis en réseau (VPN) avec le réseau interne géré par
nebula, une seule tuile même si on distinguera les sites et les
réseaux dans l'organisation des données".

Item 20 du backlog réécrit pour fusionner l'ancienne tuile
"big-brother" (item 20 d'origine) et l'agent Nebula "à concevoir"
(évoqué en #200) en un seul chantier cohérent : UN agent (conteneur
Docker sur un poste ayant accès VPN au réseau interne Nebula, pas un
déploiement multi-points), UNE tuile (données organisées par site et
par réseau à l'intérieur de cet écran unique, pas plusieurs tuiles
séparées). Item 16 mis à jour en conséquence (la future présentation
Nebula dans le hub SERA cette tuile unifiée, pas une tuile Nebula
distincte).

Toujours PAS COMMENCÉ côté code -- l'articulation agent unique/tuile
unique est actée, mais l'architecture technique de l'agent, le
modèle de données précis (site/réseau), et l'articulation avec
`nebula/api/csv_import.py` (#200, dont le schéma pourrait servir de
point de départ) restent à cadrer.

## 2026-09-02 (suite) — Persistance des logs, historique versionné, import CSV Nebula (version: 7f9a4ee6a29e, livraisons #198-#200)

**Note sur le regroupement** : ces trois livraisons ont été codées
et testées en continu au fil d'une session chargée, sans finalisation
(zip/changelog) entre chacune -- regroupées ici en une seule entrée
plutôt que de laisser les commentaires de code (déjà écrits avec les
numéros individuels #198/#199/#200) diverger du compteur réel.

### #198 -- Urgence matrice de risque, point 1 : persistance des logs

Demande explicite ("urgence à la prochaine livraison... conservation
des journaux -> à pérenniser/rendre rémanent", risque R8). Nouveau
prefs-api/log_archiver.py : thread de fond qui relit périodiquement
(30s) le tampon Memcached VOLATIL de chaque service connu et
l'archive dans une table SQLite durable, dédoublonnage par
contrainte UNIQUE (service, timestamp, message) plutôt qu'un suivi
de position fragile. Un service en panne n'arrête jamais l'archivage
des autres. Nouvelle route GET /persisted-logs (historique
consultable, filtres service/level/since/until).

Bug réel de condition de course trouvé et corrigé EN RELISANT avant
même de tester : le thread démarrait immédiatement et pouvait appeler
des fonctions définies plus loin dans le fichier (même famille de
piège que now_iso()/PROJECT_ROOT_PATH déjà rencontrés) -- corrigé en
déplaçant le démarrage du thread après ses vraies dépendances.

Réponse donnée (pas encore codée) au point 4 de la même urgence
(coffre-fort vs secrets de démarrage, risque de boucle Keycloak) :
le coffre-fort n'est pas le bon outil pour les secrets de démarrage
(conçu pour un humain via une interface, pas des machines avant tout
démarrage) -- confirmé une vraie boucle possible si Keycloak dépend
de secrets qui dépendraient eux-mêmes du coffre-fort. À documenter
comme PRA dans le volet Cyber -- pas encore fait. Points 2 et 3
(chiffrement mots de passe et clés SSH) : pas commencés, volontai-
rement laissés pour un traitement dédié plutôt que bâclés en fin de
session.

### #199 -- Volet transparence : historique versionné + convention d'ordre

Demande explicite ("volet transparence... un historique des matrices
/ versionné"). Nouvelle table cyber_risks_history : un instantané
COMPLET (jamais un diff) enregistré à chaque création/modification/
suppression d'un risque, dans la MÊME transaction que l'écriture
principale. Un risque supprimé reste consultable dans son historique.
Nouvel onglet "Historique" dans CyberView.jsx, chargé à la demande.
Honnêteté testée explicitement : les 14 risques de départ n'ont
AUCUN historique rétroactif (le mécanisme n'existait pas encore à
leur création).

Note pratique de la personne appliquée : "par défaut ordonner les
listes par ordre alphabétique, à commencer par Logs/services" --
LOG_SERVICES (hub/src/logsLib.js) réordonnée, avec ajout au passage
de glpi/nebula qui manquaient de cette liste depuis #192/#196.
KNOWN_LOG_SERVICES (log_archiver.py) alignée par cohérence.

Volet 2 de la demande transparence (vue graphique de l'architecture
large du projet -- ressources, clés de conf, stacks/projets externes)
PAS COMMENCÉ -- portée trop large pour être improvisée en fin de
session, à reprendre avec le temps nécessaire.

### #200 -- Évolution Nebula : import des exports CSV du portail web

Demande explicite ("note et évolution nebula... import et
présentation des csv sur le modèle ci-joint"), trois vrais fichiers
fournis par la personne (Sites/Devices/Clients, export réel du
portail "Pavillon A"). Nouveau nebula/api/csv_import.py
-- format déterminé en INSPECTANT les vrais fichiers (UTF-8 avec BOM,
valeurs entre guillemets y compris les nombres, "Usage" en format
libre converti en octets). Premier stockage PERSISTANT de ce module
(jusqu'ici purement passe-plat vers l'API Nebula) -- chaque import
AJOUTE des lignes (jamais un remplacement), permettant une vue dans
le temps. Routes POST /import/{sites,devices,clients} et GET
/imported/{sites,devices,clients} (dernier état par défaut,
?history=true pour tout l'historique).

Testé contre les VRAIS fichiers via de vraies requêtes HTTP
multipart : 18 appareils / 1 site / 100 clients importés
correctement, ré-import du même fichier confirmé sans doublon sur le
"dernier état", historique complet confirmé intact (36 lignes après
2 imports de 18).

Note ajoutée au backlog (pas codée) : l'agent de collecte "à
concevoir" décrit par la personne (conteneur Docker, analyse réseau
locale, transmission régulière) recoupe peut-être la tuile
"big-brother" déjà notée (item 20) -- jamais clarifié explicitement,
à faire avant de construire l'un ou l'autre. Note GLPI également
ajoutée (item 21), avec une vraie recherche sur GLPI Inventory : un
agent doit avoir un accès réseau DIRECT à chaque segment ciblé, point
clé pour "les réseaux accessibles plus ou moins directement" évoqués
par la personne.

## 2026-09-02 (suite) — Indicateur "action en cours" (diode orange) + clarification du tableau de bord des logs (version: 929df4298ca8, livraison #197)

Reprise des items 18 et 19 du backlog, notés lors de la livraison
Nebula avec priorité donnée à ce volet.

Item 18 : "ajouter une prise en compte visuel des tentatives de
lancement (diode orange ?)", "idem partout où un délai est normal".
Premier terrain (le cas explicitement nommé) : démarrage/arrêt de
tunnel SSH ET montage/démontage SSHFS (SshTunnelsView.jsx). `busy`
existant est un booléen global, insuffisant pour distinguer
visuellement quelle ligne est concernée -- quatre nouveaux Set()
séparés par type d'action, l'id y est ajouté au clic et retiré à la
réponse HTTP (succès ou échec), affiché prioritairement sur le
statut réel pendant ce laps. Reste à faire : étendre aux autres
écrans à délai variable (import GLPI, règles IMAP...).

Item 19 : doute sur le tableau de bord des logs affichant "vert et à
0" au premier chargement alors que des logs existent. Revue du code
: le "Chargement…" est bien affiché tant que les vraies données
n'arrivent pas, aucun bug trouvé dans cette logique précise.
Hypothèse retenue (probable, pas confirmée) : le tableau ne compte
que les événements >= WARNING (LOG_CAPTURE_LEVEL=WARNING, #145) --
un service sans souci récent affiche donc légitimement 0/0 vert,
visuellement indiscernable d'un chargement ou d'un problème. État "0
événement confirmé" rendu explicite plutôt que silencieux (note sous
"joignable" + phrase d'explication au-dessus du tableau). À
confirmer avec la personne une fois testé en conditions réelles.

Vérifié réellement : logique de calcul de l'état affiché (diode
orange) testée en isolation, dont l'absence de fuite d'état entre
deux lignes distinctes. Logique "trulyQuiet" (logs) testée avec 6
cas représentatifs. Structure JSX des deux fichiers revérifiée après
restructuration du corps de fonction .map() (retour implicite ->
corps de bloc pour permettre le calcul intermédiaire).

Non vérifié dans cet environnement : rendu visuel réel (aucun
navigateur ici).

## 2026-09-02 (suite) — Nouveau module nebula : connexion/consultation Zyxel Nebula (version: 7021ddd80da2, livraison #196)

Second "besoin immédiat" de la demande GLPI (#192) : "importer les
données d'un site sous nebula.zyxel.com". Recherche RÉELLE effectuée
avant d'écrire quoi que ce soit (spécification OpenAPI officielle
Zyxel, consultée le jour de cette livraison).

Deux prérequis BLOQUANTS trouvés en recherchant, confirmés par la
documentation officielle elle-même (pas une supposition) : licence
Nebula Pro Pack requise sur l'organisation visée, ET une clé d'API
qui s'obtient via un dossier support Zyxel plutôt qu'en libre-
service. Signalés explicitement dans le README et dans la réponse
de /test-connection (avertissement si une organisation détectée
n'est pas en mode PRO).

Nouveau module nebula/ : nebula_client.py (authentification par clé
statique dans l'en-tête X-ZyxelNebula-API-Key, PAS de session
contrairement à GLPI -- hiérarchie Organisation/Site/Appareil),
app.py (test-connection, organizations, sites, devices d'un site,
clients réseau). Endpoint clé repéré pour un futur import :
sites/devices (numéro de série + MAC par appareil, groupés par
site) -- filtrage côté client sur un site précis, l'API Nebula n'a
pas d'endpoint isolé pour ça. Détail amusant mais réel : le corps de
requête des endpoints clients (v2) attend un champ nommé "featrues"
(faute de frappe RÉELLE dans l'API Zyxel elle-même) -- reproduit tel
quel, jamais "corrigé".

Portée volontairement limitée à la connexion/consultation -- PAS
l'import vers GLPI, laissé pour une étape suivante une fois la
connexion validée en conditions réelles (empiler un import non
testé sur une connexion non testée aurait démultiplié le risque).

Note backlog ajoutée sans être traitée (nouvelle tuile "big-brother",
exploration active du SI par tcpdump et agents distribués, référence
Tkined/Scotty donnée par la personne) -- très en amont, ni
l'architecture de déploiement ni l'articulation avec les modules
réseau existants (ipam-api, cacti-api, zenoss-api) ne sont tranchés.

Vérifié réellement : nebula_client.py testé via mock des réponses
HTTP reconstituées fidèlement d'après la spécification OpenAPI
officielle (organizations, sites, devices_for_site avec filtrage
côté client sur un site inexistant, get_site_clients AVEC la vraie
faute de frappe featrues vérifiée explicitement non corrigée).
Format d'erreur documenté testé. app.py testé de bout en bout, dont
l'avertissement Pro Pack.

Non vérifié dans cet environnement : tout ce qui nécessite une VRAIE
API Nebula -- impossible à tester ici de toute façon (aucun accès
réseau externe, et les deux prérequis ne peuvent pas être satisfaits
depuis ce sandbox).

## 2026-09-02 (suite) — Documents ISO 27000 versionnés dans Aide et Cyber (version: df368bc78b7e, livraison #195)

Demande explicite (correction apportée par la personne juste après
#194) : "les deux documents (charte et notice) sont à présenter
versionnés dans l'aide et dans iso27000".

Nouvelle table governance_documents (prefs-api), distincte du
mécanisme /docs existant (README.md, markdown en ligne) -- fichiers
BINAIRES (.docx) à télécharger, avec version/date affichés. Contenu
lu depuis de VRAIS fichiers au démarrage
(PROJECT_ROOT_PATH/docs/*.docx, même montage lecture seule déjà
utilisé par _discover_readmes, aucun nouveau volume), encodé en
base64, stocké en base -- jamais codé en dur dans le source. Départ
automatique une seule fois, comme les 14 risques cyber (#187).

Bug réel trouvé et corrigé en testant (même piège que now_iso()
précédemment) : PROJECT_ROOT_PATH utilisé dans le bloc try de
démarrage AVANT sa propre ligne de définition plus bas dans le
fichier -- NameError au tout premier démarrage. Corrigé en
déplaçant la définition plus tôt, le commentaire de sécurité détaillé
restant à sa place d'origine.

Nouvelles routes GET /governance-documents (liste sans le contenu)
et GET /governance-documents/<id>/download. Affichage : panneau
"Documents officiels"/"Documents ISO/IEC 27000" dans AideView ET
CyberView (nom cliquable, version, date). Détail complet dans
hub/README.md.

Trois points par ailleurs notés au backlog sans être traités,
priorité donnée au volet Nebula : indicateur visuel d'action en
cours (diode orange) pour les tunnels SSH et ailleurs, doute sur les
logs affichés verts à 0 au premier chargement de l'interface.

Vérifié réellement : départ testé contre le VRAI dépôt, 2 documents
réels chargés. Téléchargement vérifié OCTET PAR OCTET (hash SHA256)
contre les fichiers originaux -- contenu identique confirmé. Départ
idempotent sur ré-appel. Non-régression complète de /docs retestée
après le déplacement de PROJECT_ROOT_PATH. Structure JSX revérifiée.

Non vérifié dans cet environnement : rendu visuel réel des deux
nouveaux panneaux.

## 2026-09-02 (suite) — Deux documents de sensibilisation ISO/IEC 27000 (charte + notice) (version: 7294383c8e7c, livraison #194)

Demande explicite, dans la série ISO 27000 : préparer des documents
à destination des utilisateurs/employés -- une charte d'usage du SI
avec un volet sécurité du poste de travail en premier (exemple donné
explicitement : branchement USB d'un mobile pour rechargement ou
transfert), et une notice avec des liens vers des outils
d'autoformation aux bonnes pratiques numériques.

docs/charte-usage-si.docx : section 2 "Sécurité du poste de travail"
en premier comme demandé, avec un encart dédié distinguant les deux
risques USB (recharger un appareil compromis sur un port qui
transporte aussi des données ; transférer des données vers/depuis un
support non maîtrisé) -- puis réseau/Internet, messagerie, données,
télétravail/nomadisme, signalement d'incident, responsabilités,
section de signature. 9 pages, rendu vérifié (conversion PDF +
inspection visuelle de chaque page).

docs/notice-autoformation-cybersecurite.docx : recherche RÉELLE
effectuée avant rédaction (jamais de lien inventé) -- trouvaille
importante : le MOOC de référence ANSSI (SecNumacadémie) est
actuellement FERMÉ pour refonte complète, retour prévu courant 2026
-- signalé explicitement dans un encart dédié plutôt que de pointer
vers un lien mort, avec des ressources de repli vérifiées (guides
ANSSI hors MOOC, kit de sensibilisation Cybermalveillance.gouv.fr,
tous deux actuellement disponibles). Tableau de ressources avec
liens hypertexte réels, organisé "pour commencer" / "pour aller plus
loin".

Les deux documents utilisent [NOM DE L'ORGANISATION] en placeholder
-- à personnaliser avant diffusion, de même que les contacts
support/RSSI laissés à compléter.

## 2026-09-02 (suite) — Écran Cyber : évolution ISO/IEC 27001, vue mixte HUB/SI supervisé (version: d914a4ea48fc, livraison #193)

Demande explicite, lien Wikipedia ISO/IEC 27001 fourni et consulté
avant de coder : "la matrice devra présenter 2 aspects : le HUB et
ses risques, les impacts risques du HUB sur le SI supervisé, avec
une vue mixte".

Ancrage ISO/IEC 27001 : la norme exige d'examiner les risques "en
tenant compte des menaces, vulnérabilités ET IMPACTS" -- la
distinction demandée EST cette dimension d'impact, rendue explicite.
Interprétation volontairement pragmatique (jamais une implémentation
complète d'un SMSI, hors de portée d'un écran de dashboard) : chaque
risque porte désormais un scope ("hub" = intrinsèque à
supervision-si, "si_supervise" = impact du hub sur les systèmes
qu'il gère -- le hub comme vecteur, pas comme cible).

Vue mixte : filtre 3 positions au-dessus de la matrice (Vue mixte /
HUB seul / SI supervisé seul), mixte par défaut -- montre les deux
catégories dans la MÊME grille, chaque point préfixé de son icône de
portée (🏠/🔗).

Backend : nouvelle colonne scope sur cyber_risks (prefs-api),
validée à la création/mise à jour. Migration CRITIQUE (la personne
utilise déjà l'écran depuis #187) : ajoute la colonne sans toucher
aux statuts/notes d'avancement déjà saisis, reclasse les 14 risques
de départ connus par leur libellé exact (jamais par position) --
répartition 8 HUB / 6 SI supervisé, un risque ajouté depuis par la
personne garde le défaut "hub". Détail complet dans hub/README.md.

Bug réel trouvé et corrigé en testant : createCyberRisk (client JS)
ne déstructurait pas scope, qui aurait été silencieusement perdu à
l'envoi malgré sa présence dans le formulaire.

Vérifié réellement : migration testée contre une base SIMULANT
EXACTEMENT l'état réel de la personne (statut "en_cours" et notes
d'avancement déjà saisis sur un risque) -- confirmé préservés,
scope correctement reclassé, migration idempotente. Validation
testée (scope invalide refusé à la création ET la mise à jour, sans
corrompre la ligne existante en cas de refus). Logique de filtrage
testée en isolation. Structure JSX revérifiée.

Non vérifié dans cet environnement : rendu visuel réel -- en
particulier si la double icône (portée + statut) reste lisible sans
surcharger l'affichage pour un public non technique.

## 2026-09-02 (suite) — Nouveau module glpi : import Excel vers GLPI (version: 9d98527d64b7, livraison #192)

Demande explicite : "évolution d'intégration GLPI... une tuile et
une api pour utiliser l'api glpi et ses données dans les autres
tuiles du hub", avec deux besoins immédiats (import inventaire Excel
+ site Zyxel Nebula). Cette livraison couvre le PREMIER besoin
immédiat (import Excel) -- le second (Nebula) nécessite sa propre
recherche d'API, traité comme un chantier séparé (item 16 du
backlog). La vision "tuile+api" plus large n'est pas commencée non
plus.

Recherche préalable : GLPI 11 propose deux API -- l'historique
(apirest.php, éprouvée, bien documentée) et une nouvelle API v2
encore "work in progress" pour les actifs au moment de cette
livraison (confirmé via la doc officielle). Choix délibéré :
l'historique, plus fiable pour un import maintenant.

Nouveau module glpi/ : glpi_client.py (session, CRUD, résolution de
dropdown, traitement d'erreur DÉFENSIF -- le format exact des
réponses d'erreur GLPI n'est pas garanti à 100% sans essai réel),
excel_import.py (mapping Type Excel -> itemtype GLPI, dédoublonnage
par numéro de série via searchText sur le NOM DE CHAMP réel plutôt
qu'un id de searchoption deviné), app.py (service Flask, POST
/import/excel en dry-run par défaut), cli_import.py (alternative en
ligne de commande). Détail complet dans glpi/README.md.

Fichier Inventaire.xlsx inspecté en détail (220 lignes, feuille
Devices) : plusieurs problèmes de qualité de données RÉELLEMENT
trouvés et signalés plutôt que traités silencieusement -- 12 lignes
"Borne-001" à "Borne-012" et "Bras Niryo"/"Bras NIryo" avec la
colonne Nom vide (l'identifiant était dans Type à la place),
variantes "Amphi Immersif"/"Amphi immersif" et
"Mediateurs"/"Médiateurs" dans Lab (normalisées avant recherche/
création de la localisation GLPI).

Bug réel trouvé et corrigé en testant : kill_session ne rattrapait
que requests.RequestException, pas une erreur générique, contraire
à l'intention documentée ("jamais bloquant, peu importe la cause").

Vérifié réellement : glpi_client.py testé via mock des réponses HTTP
reconstituées fidèlement d'après les exemples de la documentation
officielle. excel_import.py testé unitairement PUIS en dry-run RÉEL
contre le VRAI fichier fourni (220 lignes, 0 erreur, 14
avertissements -- exactement les cas de qualité de données
identifiés). Orchestration complète testée avec un client GLPI
entièrement simulé (cache de dropdown confirmé efficace). app.py
testé de bout en bout via de vraies requêtes HTTP multipart, upload
du vrai fichier inclus.

Non vérifié dans cet environnement : tout ce qui nécessite un VRAI
GLPI (aucun accès réseau externe ici) -- à tester en PRIORITÉ, en
dry-run d'abord, une fois déployé.

## 2026-09-02 (suite) — imap-client : volet 3/4 "Gestionnaire d'interpréteur" -- piège critique sur les motifs regex corrigé (version: 5f2c55d55ee2, livraison #191)

Backlog BACKLOG.md #4, troisième des 4 volets, construit en
autonomie. Généralise en outil CONFIGURABLE ce que
parse_zenoss_emails.py fait en dur pour un seul format (fichier
existant resté inchangé, juste une référence de conception -- motifs
nommés déjà utilisés là-bas). Un interpréteur = critères de
correspondance (match_subject/match_from) + une liste de champs,
chaque champ = un motif regex INDÉPENDANT appliqué au sujet ou au
corps (choix : plus simple à configurer qu'un seul motif géant à
groupes nommés).

PIÈGE CRITIQUE trouvé et corrigé en testant : un motif regex fourni
par une personne, appliqué à un contenu externe, peut causer un
retour arrière catastrophique. Premier essai de protection par délai
d'attente dans un THREAD séparé (même motif que
mount_process.measure_latency, #182) -- révélé TOTALEMENT
INEFFICACE ici : contrairement à un appel système, le moteur regex
en C ne libère jamais le GIL pendant son calcul -- mesuré RÉELLEMENT
86 secondes d'attente malgré un délai demandé de 1 seconde, sur un
motif catastrophique construit pour le test. Corrigé avec un VRAI
PROCESSUS séparé (multiprocessing.Process, terminate()/kill() en
escalade) -- seul moyen d'interrompre de force un calcul CPU pur,
indépendamment de ce que Python fait en interne. Revérifié après
correctif : 1.02 seconde pour le même motif.

Nouveaux interpreters_store.py (validation de champs AVANT stockage,
motif regex vérifié compiler réellement) et interpreter_engine.py.
Stockage : même fichier SQLite que les règles (#190), table séparée.
Nouvelles routes : GET/POST /interpreters, PUT/DELETE
/interpreters/<id>, POST /messages/<uid>/interpret (auto-correspondance
ou interpreter_id explicite, 404 si aucun ne correspond). Détail
complet dans imap-client/README.md.

Vérifié réellement : interpreters_store.py testé contre une VRAIE
base SQLite, dont une mise à jour avec des champs invalides refusée
SANS corrompre les données existantes. interpreter_engine.py testé
avec une extraction réelle proche d'une vraie alerte Zenoss (device/
sévérité/localisation tous corrects), ET surtout contre un VRAI motif
catastrophique (a révélé puis confirmé le correctif). app.py testé
de bout en bout, dont l'interprétation d'un vrai message simulé.
Non-régression complète des volets 1, 2 et 3 retestée ensemble
(8 cas).

Non vérifié dans cet environnement : contre un vrai serveur IMAP
(réseau restreint ici, même limitation que les volets précédents).

## 2026-09-02 (suite) — imap-client : règles de tri avec étiquettes et actions déclenchées (version: c047f0eb4a8d, livraison #190)

Précision apportée par la personne sur le sens de "filtres" (#189) :
"c'est aussi l'idée de trier et poser des étiquettes, déplacer vers
des dossiers, déclencher des actions" -- l'interprétation initiale
(recherche manuelle seule) était trop étroite. Construit en
autonomie pendant que la personne teste #189.

Nouveau rules_store.py -- PREMIÈRE base de données de ce module
(SQLite, le reste reste sans état). Une règle = critères (dossier
surveillé, sujet/expéditeur/non-lu, tous optionnels) + actions
(étiquette, marquage lu, déplacement, toutes optionnelles). Nouveau
rule_engine.py -- applique une règle : ordre FIXE des actions
(étiquette/lu D'ABORD, déplacement EN DERNIER -- un message déplacé
change d'UID). Étiquettes = mots-clés IMAP personnalisés
(add_label/remove_label, STORE +FLAGS/-FLAGS) -- pas universellement
supportés selon le serveur, erreur réelle remontée si absent.

Application des règles VOLONTAIREMENT à la demande (POST
/rules/apply), pas encore une tâche de fond automatique -- une
automatisation qui modifie la boîte toute seule est un pas plus
risqué, décision reportée plutôt que présumée. Nouvelles routes :
GET/POST /rules, PUT/DELETE /rules/<id> (CRUD complet), POST
/rules/apply (toutes les règles activées, une seule connexion IMAP
réutilisée, résumé PAR règle). Nouveau volume IMAP_CLIENT_DATA_DIR.
Détail complet dans imap-client/README.md.

Vérifié réellement : rules_store.py testé contre une VRAIE base
SQLite (CRUD complet, mise à jour partielle confirmée). rule_engine.py
testé en isolation : ORDRE des actions confirmé, règle partielle
(seule l'action définie s'exécute), erreur sur un message sans
bloquer les suivants, critères bien transmis. add_label/remove_label/
mark_seen testées via mock imaplib, y compris le cas d'un serveur ne
supportant pas les mots-clés personnalisés. Routes app.py testées de
bout en bout (validation -- au moins une action requise ; aucune
connexion IMAP ouverte si aucune règle activée ; une seule connexion
réutilisée pour plusieurs règles). Non-régression complète des
volets 1 et 2 retestée (6 cas).

Non vérifié dans cet environnement : contre un vrai serveur IMAP
(réseau restreint ici), en particulier le support des mots-clés
personnalisés par le serveur réel visé.

## 2026-09-02 (suite) — imap-client : volet 2/4 "Interface de gestion de la boîte" (version: 5803d8f777d4, livraison #189)

Backlog BACKLOG.md #4, deuxième des 4 volets, construit en autonomie
pendant que la personne teste #188. Création/suppression de dossiers
IMAP (create_folder/delete_folder), déplacement de message entre
dossiers (move_message -- COPY puis marquage supprimé + EXPUNGE sur
l'original, compatible avec tous les serveurs IMAP, jamais
l'extension MOVE/RFC 6851 pas universellement supportée), filtres de
recherche natifs (SUBJECT/FROM/UNSEEN) ajoutés à list_messages.

PREMIÈRES actions d'ÉCRITURE de ce module -- volet 1 (#179) restait
entièrement lecture seule. "Filtres" interprété comme recherche
MANUELLE (la personne trie elle-même via déplacement), PAS un moteur
de règles automatiques façon Sieve -- distinction non tranchée dans
le backlog, approximation documentée (mode adopté depuis #178), à
confirmer si un tri automatique était réellement attendu.

Nouvelles routes : POST /folders, DELETE /folders (nom en paramètre
de requête, jamais un segment d'URL -- un nom de dossier IMAP peut
contenir le séparateur hiérarchique), POST /messages/<uid>/move.
GET /messages étendue avec subject/from/unseen (tous optionnels).
Détail complet dans imap-client/README.md.

Vérifié réellement : échappement de termes de recherche testé.
Fonctions d'écriture testées via mock imaplib réaliste, y compris
les cas d'échec les plus délicats pour move_message (échec de la
COPY -- jamais de STORE/EXPUNGE après ; échec du STORE APRÈS une
COPY réussie -- message explicite sur le message resté en double,
jamais un échec silencieux). Filtres de recherche testés seuls et
combinés, critères IMAP générés confirmés corrects. Routes app.py
testées de bout en bout, dont un nom de dossier contenant un '/' via
paramètre de requête. Non-régression complète du volet 1 retestée
(5 cas).

Non vérifié dans cet environnement : contre un vrai serveur IMAP
(réseau restreint ici, même limitation que le volet 1).

## 2026-09-02 (suite) — scripts/run.sh : correctif #185 insuffisant en conditions réelles -- -prune au lieu de -not -path (version: 205fec47ca16, livraison #188)

Bug réel rapporté par la personne : après #185 (confirmé bien
déployé, correctif présent), le déploiement bloquait TOUJOURS
exactement au même endroit, avec exactement le même symptôme (rien
après check-env.py). Diagnostic demandé sans masquer les erreurs
cette fois (le script les cache normalement avec 2>/dev/null) :
confirmé que le montage FUSE mort (ssh-tunnels/mounts/tts-gu-fr)
était toujours présent, ET que la commande find elle-même échouait
dessus MALGRÉ le filtre -not -path déjà en place.

Cause RÉELLE, plus subtile que le correctif #185 ne le supposait :
`-not -path` ne fait que FILTRER le résultat APRÈS COUP -- find
tente quand même de LIRE (stat) chaque entrée d'un dossier PENDANT
qu'il le parcourt, AVANT d'appliquer ce filtre. Sur un montage FUSE
mort, cette simple tentative de lecture échoue déjà ("Transport
endpoint is not connected"), qu'elle soit ensuite filtrée du
résultat ou non -- confirmé par le message d'erreur réel de la
personne, qui citait explicitement le point de montage mort malgré
le filtre.

Corrigé : `-prune` remplace `-not -path` pour les exclusions de
DOSSIERS (node_modules, __pycache__, .git, keycloak/import,
keycloak/backup, pki/ca, pki/server, tls-proxy/generated,
apache/generated, data, ssh-tunnels/keys, ssh-tunnels/mounts) --
`-prune` empêche find de même ENTRER dans le dossier ciblé, jamais
de tentative de lecture sur son contenu, montage mort ou non.
Motif classique `find \( -path A -o -path B \) -prune -o -type f
-print` plutôt qu'une chaîne de `-not -path`.

Vérifié réellement : test structurel confirmant que -prune
n'énumère MÊME PAS le dossier ciblé (contrairement à -not -path, qui
le liste puis le filtre) -- reproduit avec une structure simulant le
vrai projet (11 cas, dont un nom "geo-import-api" volontairement
proche de "data" pour confirmer l'absence de faux positif par
sous-chaîne, et un test avec un chemin ABSOLU comme point de départ,
comme dans le vrai script).

## 2026-09-02 (suite) — Écran hub "Cyber" : matrice + suivi des risques (version: f97078fcf5d6, livraison #187)

Demandé explicitement, en prolongement de #186 : "au même niveau que
Logs", "une matrice en premier", "à destination en premier lieu des
politiques et des béotiens" -- design volontairement simple, code
couleur explicite, jargon technique réservé à l'onglet secondaire.

Nouveau menu "Cyber" (CyberView.jsx). Onglet "Matrice" (par défaut,
lecture seule) : grille probabilité × gravité 3x3, vert/orange/rouge
selon un score probabilité×gravité, chaque point cliquable pour sa
description en clair, section séparée pour les risques "à évaluer"
(évolutions prévues, pas encore construites). Onglet "Suivi" : liste
complète groupée par statut, statut modifiable (à traiter/en cours/
traité/accepté), notes d'avancement éditables, ajout d'un nouveau
point.

Backend : nouvelles routes /cyber-risks (CRUD complet) ajoutées à
prefs-api (pas un nouveau service -- CRUD simple, cohérent avec son
rôle de paramétrage transversal). Départ automatique avec les 14
risques de docs/cyber-risques-resume.md (#186), reformulés en
langage accessible, n'insère qu'une seule fois. Nouveau jeton de
thème --warning/--warning-bg ajouté à la Famille 1 (shared/theme.css,
hub/tickets/DBA) -- absent jusqu'ici, jamais emprunté à la Famille 2
(réservée à Supervision SI/frontend/, "jamais mélangées"). Détail
complet dans hub/README.md.

Vérifié réellement : CRUD testé de bout en bout contre une vraie
base SQLite (14 risques de départ, pas de doublon au second appel,
mise à jour PARTIELLE confirmée, création/suppression, validation).
Bug réel trouvé et corrigé en testant : now_iso() appelée avant sa
propre définition (ordre du fichier) -- déplacée. Logique de
classement (probabilité×gravité -> couleur) testée avec les 14
risques RÉELS un par un, conforme à la matrice attendue. Structure
JSX de CyberView.jsx et App.jsx vérifiée.

Non vérifié dans cet environnement : rendu visuel réel -- la
lisibilité de la matrice pour un public non technique, objectif
premier de cet écran, ne peut se juger que devant un vrai écran.

## 2026-09-02 (suite) — Résumé des risques cyber + proposition de tableau de bord (version: 1b12a62f8d7a, livraison #186)

Demandé explicitement pendant que la personne teste #185 :
docs/cyber-risques-resume.md -- vue d'ensemble rapide (14 risques
identifiés à travers le stack : segmentation réseau, authentification
inter-services, secrets en clair dans .env, clés SSH non chiffrées,
privilèges FUSE, filtrage SQL basique, rémanence des logs, GED
tierce, futurs modules backlog SNMP/auth mot de passe, dépendances
non auditées, UDP syslog non authentifié), matrice probabilité×impact,
et proposition de tableau de bord de surveillance par risque
(certaines lignes nécessitant des mécanismes pas encore construits,
noté explicitement).

Volontairement concis (demande explicite : "pas besoin de trop de
détails explicatifs") -- une esquisse pour orienter la conception,
pas une analyse exhaustive ("on refera l'analyse en fin de
conception" dixit la personne).

## 2026-09-02 (suite) — scripts/run.sh : correctif bug réel -- déploiement bloqué silencieusement (version: be939986cff3, livraison #185)

Bug réel rapporté par la personne : après #184, sudo
./scripts/chantier.sh build s'arrêtait net juste après l'affichage
de check-env.py (purement informatif, jamais bloquant, confirmé par
lecture du code), sans jamais atteindre docker compose -- aucun
message d'erreur visible, juste un code de sortie 1 sur l'invite
suivante. Capture complète du journal (tee) confirmée : rien
n'apparaît après les listes de check-env.py.

Cause RÉELLE : scripts/run.sh calcule un hash de version en
parcourant TOUT le projet (find | sha256sum, juste après
check-env.py) -- CONTRAIREMENT au calcul de hash de LIVRAISON
(utilisé pour chaque paquet zip livré dans cette conversation), ce
calcul-ci n'excluait PAS ssh-tunnels/keys/ ni ssh-tunnels/mounts/.
Avec set -euo pipefail actif, UN SEUL fichier faisant échouer
sha256sum dans ce pipe (clé privée illisible, ou un montage FUSE
mort sous ssh-tunnels/mounts/ d'un essai précédent) fait échouer
TOUT le script silencieusement -- symptôme déroutant, aucun message
d'erreur visible.

Corrigé : mêmes exclusions ajoutées à ce calcul que celui déjà en
place pour les livraisons. Ces deux dossiers ne représentent de
toute façon jamais du CODE (clés/points de montage, contenu variable
et sensible) -- les exclure est cohérent avec leur traitement
ailleurs dans le projet, pas seulement un contournement.

Vérifié réellement : exclusion testée contre une VRAIE structure de
répertoires simulant le cas rapporté (clé privée chmod 600, fichier
sous mounts/) -- confirmé que ces deux dossiers sont bien absents de
la liste de fichiers hashés après correctif. Syntaxe bash
revérifiée.

## 2026-09-02 (suite) — ssh-tunnels : correctif bug réel -- mode proxy réellement inatteignable (version: 4dcaaf44c570, livraison #184)

Bug réel rapporté par la personne : connexion MySQL refusée depuis
l'onglet DBA sur un tunnel fraîchement créé (port distant 3306,
port local 5306), test de connexion bloquant.

Cause RÉELLE : build_ssh_command construisait -L
{local_port}:{remote_host}:{remote_port} SANS adresse de liaison
explicite -- ssh lie alors le port forwardé par défaut à 127.0.0.1,
le LOOPBACK DU CONTENEUR ssh-tunnels-api LUI-MÊME, invisible depuis
n'importe quel autre conteneur (dba-api compris), même sur le
réseau Docker interne partagé. Casse directement le "mode proxy"
promis dès #159 -- jamais vérifié contre un vrai second conteneur
consommateur avant ce rapport réel, seul ssh-tunnels-api lui-même
avait été testé contre son propre processus.

Corrigé : liaison EXPLICITE 0.0.0.0:{local_port}:... -- toutes les
interfaces du conteneur, donc atteignable via le réseau Docker par
son nom de service. Aucun port exposé vers l'hôte pour ce service
(pas de ports: dans docker-compose.yml) -- élargit seulement
l'accès au réseau Docker interne déjà partagé, jamais vers
l'extérieur. Détail complet dans ssh-tunnels/README.md (section
restaurée après une perte de contenu accidentelle lors d'une édition
précédente, corrigée dans la foulée).

Vérifié réellement : commande générée confirmée
(0.0.0.0:5306:127.0.0.1:3306), principe de liaison 0.0.0.0 vérifié
avec un VRAI socket TCP. Non-régression complète retestée (création/
démarrage/arrêt de tunnel, paramètres transmis correctement).

Absence de logs constatée par la personne pendant le diagnostic
expliquée : une connexion refusée au niveau noyau (port non écouté
sur l'interface visée) n'atteint jamais le processus ssh ni
l'application -- rien à logger, cohérent avec la cause identifiée.

## 2026-09-02 (suite) — ssh-tunnels : correctif déploiement -- dossier mounts/ manquant (version: 7d71a6635a65, livraison #183)

Bug réel rencontré par la personne au premier déploiement de #180 :
"Error response from daemon: invalid mount config for type bind:
bind source path does not exist:
.../supervision-si/ssh-tunnels/mounts". Cause : la syntaxe LONGUE
des volumes Docker (nécessaire pour propagation: rshared, voir
#180) ne crée PAS automatiquement le répertoire hôte s'il est
absent, contrairement à la syntaxe courte utilisée pour
ssh-tunnels/data et ssh-tunnels/keys. ssh-tunnels/keys/ avait déjà
un README.md placeholder pour cette même raison (livraison #159) --
ssh-tunnels/mounts/ n'en avait jamais eu.

Corrigé : ssh-tunnels/mounts/README.md ajouté (même motif exact que
keys/README.md), .gitignore mis à jour en conséquence
(ssh-tunnels/mounts/* ignoré sauf ce README). Ce dossier existera
désormais automatiquement à l'extraction d'un nouveau zip -- plus
besoin de le créer à la main.

Clarifié en réponse à la personne (aucun code à ce sujet) :
SSH_TUNNELS_MOUNTS_DIR (.env) est OPTIONNELLE -- vide/absente =
./ssh-tunnels/mounts comme repli, même logique que
SSH_TUNNELS_KEYS_DIR/SSH_TUNNELS_DATA_DIR.

## 2026-09-02 (suite) — ssh-tunnels : supervision des montages (espace/inodes/latence) (version: f81fb1453bf7, livraison #182)

Demandé explicitement en prolongement d'un résumé informationnel sur
les possibilités de supervision SSHFS ("transforme ça en vraie
fonctionnalité de supervision"). Nouveau GET /mounts/<id>/stats sur
un montage ACTIF : espace/inodes distants (os.statvfs à travers le
montage, aucun coût réseau supplémentaire -- inodes pertinents
seulement selon le système de fichiers distant réel), confirmation
que le chemin EST un point de montage actif (os.path.ismount(),
signal complémentaire au PID vivant, jamais substituable), latence
d'un accès (mesurée dans un thread avec timeout, ?latency=false pour
l'ignorer). 409 si le montage n'est pas actif -- jamais des stats
trompeuses du conteneur lui-même.

Deux pièges réels trouvés en testant : with ThreadPoolExecutor()
bloque à la sortie du bloc jusqu'à ce que le thread termine
réellement (2s d'attente malgré un timeout de 0.3s demandé) --
corrigé avec shutdown(wait=False) explicite. mount --bind ne change
jamais st_dev (invisible pour ismount()) -- pas représentatif d'un
montage FUSE, validé à la place contre un vrai tmpfs. Hub
(SshTunnelsView.jsx) : bouton Stats par montage actif, résultat
formaté (formatBytes). Corrigé au passage : handleMountAction/
handleUnmountAction n'actualisaient jamais la liste après action.
Détail complet dans ssh-tunnels/README.md.

Vérifié réellement : les trois fonctions testées contre de VRAIES
ressources (statvfs sur un vrai répertoire, ismount() contre un vrai
montage tmpfs monté puis démonté, measure_latency avec un vrai stat
chronométré ET un blocage simulé confirmant le timeout réellement
respecté après correctif). Route testée de bout en bout contre un
vrai montage tmpfs. formatBytes testée en isolation (9 cas).

Non vérifié dans cet environnement : contre un vrai montage SSHFS
(binaire non installable ici) -- les valeurs d'inodes en particulier.

## 2026-09-02 (suite) — Trois notes de backlog : catalogue SGBD, auth SSH par mot de passe, module SNMP (version: 42c8e0992bde, livraison #181)

Aucun code livré -- trois nouveaux items ajoutés à BACKLOG.md (et au
skill utilisateur), demandés explicitement pendant que la personne
teste #180.

Item #11 : catalogue SGBD disponible (nouvel onglet) -- faire
apparaître les tunnels SSH vers MySQL comme des sources utilisables
dans DBA/analyse de schémas/autres modules, plus un contrôle
(fermer/ouvrir) et un historique (connexion et paramétrage).

Item #12 : authentification SSH par mot de passe pour ssh-tunnels,
en plus des clés -- certains vieux systèmes refusent la connexion
par clé. Gestion sécurisée user/password + historique d'usage
(quand, quelle API/connexion, durée).

Item #13 : nouveau module/tuile SNMP -- découverte de ce qui est
ouvert sur une cible IPv4/MAC, gestion des paramètres d'accès
sécurisés, analyse des informations disponibles (SNMP walk/MIB).

Les trois : juste notés, pas encore cadrés en détail.

## 2026-09-02 — ssh-tunnels : montage SSHFS réel (version: d1a60887d4d0, livraison #180)

Backlog BACKLOG.md #2, dernier volet -- demandé explicitement par la
personne ("j'en ai besoin pour concevoir la suite"), explicitement
reporté en #159 ("privilèges élevés requis"). Item 2 désormais
ENTIÈREMENT livré.

Nouveau mount_process.py, même motif que tunnel_process.py : sshfs
-f (premier plan, condition pour que le PID du sous-processus
Python soit le montage lui-même, contrairement à sshfs par défaut
qui se détache en démon). Démontage via fusermount -u (idempotent).
Réutilise le récolteur de zombies déjà en place, jamais dupliqué.

Sécurité : local_mount_path devient un NOM RELATIF (jamais un
chemin absolu ni de traversée ..) -- résolu et restreint à
SSH_MOUNTS_BASE_DIR, même motif exact que
prefs-api/file_source_poller._resolve_safe_path (#176). Validé DÈS
LA CRÉATION du montage. Migration de schéma (pid/last_error ajoutées
à ssh_mounts, ancien statut not_implemented reclassé unmounted).

Docker : privilèges FUSE ajoutés (cap_add SYS_ADMIN, /dev/fuse,
security_opt apparmor:unconfined -- nécessaire en pratique sur un
hôte Ubuntu/Debian avec AppArmor actif même avec SYS_ADMIN). Nouveau
volume SSH_TUNNELS_MOUNTS_DIR avec propagation rshared (nécessaire
pour qu'un montage FUSE fait dans le conteneur devienne visible côté
hôte). Paquet sshfs ajouté au Dockerfile. Hub (SshTunnelsView.jsx) :
libellé de champ corrigé (nom relatif), statut affiché. Détail
complet dans ssh-tunnels/README.md.

Vérifié réellement, malgré l'absence du binaire sshfs (réseau
restreint ici, même limitation déjà documentée pour ssh) :
fusermount et /dev/fuse SONT présents -- unmount_path testée contre
le VRAI binaire (a corrigé une hypothèse initialement fausse sur le
vocabulaire d'erreur : "Invalid argument", pas "not mounted").
stop_mount_process testée avec un vrai processus ignorant SIGTERM
(filet SIGKILL confirmé). Migration testée contre une vraie base
SQLite simulant l'ancien schéma, idempotente sur double application.
Orchestration app.py testée de bout en bout (création avec
validation de chemin, montage, remontage idempotent, démontage,
réconciliation d'un processus mort) avec les fonctions nécessitant
sshfs lui-même simulées. Non-régression confirmée sur tunnels/
connexions/clés.

Non vérifié dans cet environnement : le montage lui-même (nécessite
sshfs) ; les privilèges Docker (cap_add/devices/security_opt) --
déduits de la documentation FUSE-in-Docker, jamais confirmés contre
un vrai docker compose up ; la propagation rshared. À tester en
PRIORITÉ une fois déployé.

## 2026-09-01 (suite) — imap-client : nouveau module, volet 1/4 "Client IMAP" (version: a8a5cc98d391, livraison #179)

Backlog BACKLOG.md #4, premier des 4 volets ("Client IMAP" ->
"Interface de gestion de la boîte" -> "Gestionnaire d'interpréteur"
-> "Connecteur source", ordre donné par la personne). Nouveau
module imap-client -- connexion IMAP LECTURE SEULE (imaplib,
bibliothèque standard Python, aucune dépendance externe) : liste des
dossiers, liste/lecture des messages. Aucune écriture (marquage lu,
déplacement, suppression, dossiers) -- volontairement réservé au
volet 2/4, pas construit ici pour rester dans l'ordre annoncé.

À distinguer explicitement de pixel-grid/data-generator/
parse_zenoss_emails.py (référencé dans le backlog comme précédent) :
CE fichier-là est un parseur HORS LIGNE sur un export texte manuel,
figé sur un seul format Zenoss -- imap-client est une connexion LIVE
générique, n'importe quel message. Service SANS ÉTAT (connexion
neuve à chaque requête, même raisonnement que les connecteurs SGBD
de dba/api). Deux approximations assumées et documentées (mode
adopté en #178) : tri "plus récent d'abord" par UID décroissant
(pas une garantie du protocole IMAP) ; corps HTML jamais assaini si
aucune partie texte pur n'existe. Détail complet dans
imap-client/README.md.

Câblé : docker-compose.yml (nouveau service imap-client-api, sans
volume -- sans état), route tls-proxy (/api/imap-client/),
hub/src/logsLib.js, nouvelles clés .env (IMAP_HOST/PORT/USER/
PASSWORD/USE_SSL/DEFAULT_FOLDER, voir ENV_CHANGELOG.md).

Vérifié réellement : logique pure (imap_wrapper.py) testée SANS
mock IMAP bas niveau -- décodage RFC 2047 (accents français, vrai
encodage base64/UTF-8), parsing de lignes IMAP LIST réelles (nom de
dossier avec espace, avec crochets), extraction de corps contre de
VRAIS messages MIME multipart (email.mime -- texte+HTML+pièce
jointe, message simple, HTML seul). Fonctions imaplib testées via
mock des méthodes IMAP4 (format réellement documenté) -- pagination
réelle, message disparu entre SEARCH et FETCH correctement sauté.
app.py testé de bout en bout (config absente -> 502 clair ; parcours
complet des 3 routes).

Non vérifié dans cet environnement : contre un VRAI serveur IMAP
(réseau restreint ici) -- à tester en PRIORITÉ une fois déployé,
l'approximation sur l'ordre de tri en particulier mérite
vérification contre le serveur réel visé.

## 2026-09-01 (suite) — schema-analyzer : onglet Données, APPROXIMATION notée (version: 90f67230e773, livraison #178)

Nouveau mode de travail adopté explicitement par la personne :
approximer et aller jusqu'au bout plutôt que de s'arrêter sur une
demande imprécise, en notant clairement l'approximation. Backlog
BACKLOG.md #5, "Proposition d'interface d'édition des données,
générée à partir du graphe relationnel validé" -- demande restée
vague, jamais confirmée précisément.

Interprétation retenue : navigateur/éditeur de lignes appuyé
DIRECTEMENT sur le CRUD déjà existant de dba-api (jamais reconstruit)
-- schema-analyzer enrichit avec les relations CONFIRMÉES pour un
"aller à la ligne liée". Nouveau sous-onglet "Données"
(SchemaAnalyzerView.jsx) : sélecteur de table, pagination, édition
de cellule en ligne, ajout/suppression de lignes.

Approximation technique notable : dba-api n'expose pas de requête
filtrée paramétrée sur /rows -- "aller à la ligne liée" s'appuie sur
l'endpoint /sql existant, avec un échappement SQL basique
(sqlLiteral, testé contre une tentative d'injection). Un vrai filtre
WHERE paramétré côté dba-api serait plus robuste, à reconsidérer si
fragile en usage réel. Détail complet dans hub/README.md.

Second volet du même item backlog ("affectation des relations")
reste flou même après tentative d'interprétation -- traité
séparément plutôt que forcé dans la même approximation.

Vérifié réellement : nouvelles fonctions du client testées avec un
fetch simulé (bonnes URLs/méthodes/corps, préservation des messages
d'erreur réels). sqlLiteral testée spécifiquement contre une
tentative d'injection SQL (neutralisée). Structure JSX vérifiée par
contrôle d'équilibre après un ajout conséquent.

Non vérifié dans cet environnement : rendu visuel réel, et surtout
"aller à la ligne liée" contre un vrai dba-api/SGBD.

## 2026-09-01 (suite) — Logs de toutes sortes, étape 4/4 (DERNIÈRE) : rsyslog distant/UDP (version: 0a76a49676f8, livraison #177)

Backlog BACKLOG.md #3, dernière étape de l'initiative -- construite
en autonomie. Nouveau service SÉPARÉ rsyslog-listener/ (pas une
extension de prefs-api comme les étapes précédentes) : syslog est un
protocole réseau UDP brut, jamais HTTP -- ne peut pas transiter par
tls-proxy. Port UDP exposé DIRECTEMENT sur l'hôte
(RSYSLOG_LISTENER_PORT, .env).

rsyslog-listener/syslog_parser.py -- logique PURE, distingue RFC
3164 (BSD) de RFC 5424 (moderne) via le marqueur de VERSION juste
après le PRI. Sévérité syslog mappée sur les 3 niveaux déjà en place
(0-3->ERROR, 4->WARNING, 5-7->INFO). Ligne hors des deux formats
reconnus retombe en "brut", jamais perdue. UN SEUL worker Gunicorn --
même raisonnement que ssh-tunnels-api (#159) : un port UDP ne peut
être bound que par un seul processus.

Même tampon/registre Memcached partagés que les 3 étapes
précédentes -- le hub affiche cette source automatiquement (entrée
ajoutée à LOG_SERVICES pour les logs INTERNES du service, distincts
du flux syslog relayé). Enregistrement de la source throttlé (5 min,
pas à chaque paquet -- register_shared_log_source fait un
aller-retour Memcached même quand la source est déjà connue).
Détail complet dans rsyslog-listener/README.md.

Vérifié réellement : parseur testé contre les exemples CANONIQUES
des deux RFC (17 cas, dont sévérités limites, tag avec PID, vrai
caractère BOM distinct du texte littéral "BOM" de l'exemple RFC
5424). listener.py testé contre un VRAI socket UDP local (thread
réel, paquets envoyés depuis un client séparé, UTF-8/accents
confirmés). app.py testé de bout en bout avec le VRAI thread démarré
au chargement du module -- un paquet UDP réel confirmé visible dans
/logs ET le tampon partagé ET le registre de sources.

Initiative "logs de toutes sortes" TERMINÉE, 4/4 étapes livrées
(push #142, URL #147, fichier plat #176, rsyslog/UDP #177). Non
vérifié dans cet environnement : contre un vrai serveur
rsyslog/syslog-ng distant (réseau restreint ici).

## 2026-09-01 (suite) — Logs de toutes sortes, étape 3/4 : sources fichier plat (version: cd73aad85a3b, livraison #176)

Backlog BACKLOG.md #3, construite en autonomie -- le CRUD
log_sources acceptait déjà type="file" depuis #147 (schéma anticipé,
resté inerte) -- validation réelle ajoutée (config.path RELATIF,
interval_seconds, jamais un chemin absolu ni une traversée "..",
refusé dès la création).

Nouveau prefs-api/file_source_poller.py -- lecture INCRÉMENTALE
(position suivie), coordonnée via MEMCACHED (pas un dict en mémoire
par processus comme le suivi des sources URL) : une lecture de
fichier est intrinsèquement à état, contrairement à un GET URL --
avec 2 workers Gunicorn suivant chacun sa propre position, chaque
ligne nouvelle serait lue en double SYSTÉMATIQUEMENT. N'avance la
position que jusqu'à la dernière ligne COMPLÈTE -- une ligne encore
en cours d'écriture est relue en entier au cycle suivant, jamais
coupée en deux. Rotation détectée (inode différent OU taille <
position connue, couvre aussi logrotate "copytruncate") -- repart de
zéro. Chemins RESTREINTS à LOG_FILES_HOST_DIR (.env, lecture seule,
même motif que SSH_TUNNELS_KEYS_DIR #159) -- résolution via
realpath, un lien symbolique pointant hors du répertoire autorisé
est refusé comme tout autre chemin hors périmètre.

Dispatch intégré au MÊME sondeur que les sources URL
(log_sources_poller.poll_all_due_sources, désormais générique par
type) -- poll_file_fn/base_dir injectés, jamais un import en dur.
Toujours sans interface d'administration (comme les sources URL).
Détail complet dans README.md racine.

Vérifié réellement : lecture incrémentale testée sur un VRAI fichier
disque (13 cas -- ligne complète vs incomplète jamais coupée,
rotation ET copytruncate, traversée de chemin refusée y compris via
un lien symbolique). Dispatch testé (source URL non régressée,
source fichier bien sondée, aucune exception si le module est
indisponible). CRUD /log-sources retesté de bout en bout pour
type="file" (6 cas).

## 2026-09-01 (suite) — ssh-tunnels : onglet hub (version: d25d18884f6f, livraison #175)

Backlog BACKLOG.md #2, dernier volet -- construit en autonomie
pendant l'absence de la personne. SshTunnelsView.jsx (menu "Tunnels
SSH", ajouté au menu horizontal texte de #173) -- 4 sections dans
l'ordre logique : Clés (consultation/activation seulement) ->
Connexions (host/user/clé) -> Tunnels (démarrage/arrêt de vrais
processus ssh, statut + dernière erreur visible) -> Montages SSHFS
(interface complète, mais boutons monter/démonter affichent le 501
de l'API tel quel -- action réelle toujours pas implémentée,
reportée explicitement par la personne). Nouveau
hub/src/sshTunnelsClient.js, même motif que gedClient.js/
schemaAnalyzerClient.js. VITE_SSH_TUNNELS_API_BASE_URL ajoutée au
service hub (docker-compose.yml, route tls-proxy déjà existante
depuis #159). Détail complet dans ssh-tunnels/README.md.

Vérifié réellement : sshTunnelsClient.js testé avec un fetch simulé
en Node (20 cas -- bonnes URLs/méthodes/corps pour chaque fonction
des 4 sections, préservation du message 501 tel quel, repli sur
liste vide en cas d'erreur réseau). Structure JSX de
SshTunnelsView.jsx et de App.jsx vérifiée par un contrôle
d'équilibre accolades/parenthèses/balises. YAML de
docker-compose.yml revérifié valide.

Non vérifié dans cet environnement : compilation Vite réelle ni
rendu visuel -- et, comme pour ged, ce sera aussi le premier test de
bout en bout réel du backend #159 (processus ssh, récolte des
zombies), pas seulement de cette interface.

## 2026-09-01 (suite) — schema-analyzer : correctif message d'erreur muet sur les échecs dba-api (version: ca3e7c7a6b74, livraison #174)

La personne a signalé un 502 muet ("impossible de lister les tables
via dba-api : 502 Server Error: BAD GATEWAY for url:
http://dba-api:5000/connections/7/tables") en s'absentant -- même
piège que ged/api/mayan_client.py avant #163 : dba-api renvoie
DÉLIBÉRÉMENT un 502 avec le vrai message du connecteur externe dans
le corps JSON (voir dba/api/app.py, list_tables et routes voisines),
mais raise_for_status() seul dans schema_client.py ne donnait que la
ligne de statut générique.

Corrigé en autonomie (personne absente le temps du diagnostic) :
_raise_with_detail remplace tous les raise_for_status() isolés sur
les appels dont l'échec est surfacé à la personne (jamais sur
l'échantillonnage best-effort de fetch_full_schema). Vérifié en
parallèle que les deux connecteurs SGBD (mysql.py, postgres.py) ont
déjà connect_timeout=5 correctement configuré -- écarte le scénario
"worker Gunicorn bloqué", le 502 était bien la réponse délibérée de
dba-api avec son détail avalé. Détail complet dans
schema-analyzer/README.md.

Vérifié réellement : testé contre un mock reproduisant EXACTEMENT le
comportement rapporté (502 + message du connecteur MySQL dans le
corps JSON) -- confirmé le message réel visible jusque dans la
réponse HTTP de /analyze. Non-régression du chemin de succès
retestée (7 cas).

## 2026-09-01 (suite) — Refonte de la navigation d'en-tête : menu horizontal texte + hiérarchie Paramètres (version: 90b8e88dbecd, livraison #173)

Demandé explicitement : "je n'aime pas trop le bandeau d'icônes
actuel... il y en a trop... hiérarchie d'inclusion, les liens
devraient être dans paramétrage". Le bandeau (11 icônes en une
rangée après l'ajout de GED en #172) devient un menu horizontal en
texte.

Directement visibles : Aide, Logs, Analyse de schémas, Onglets,
Historique -- chacun actif (fond accentué) selon viewMode, même
motif visuel que .tabs ailleurs dans ce projet. Regroupés sous
"Paramètres ▾" (hiérarchie d'inclusion demandée explicitement) :
Paramètres généraux, Personnaliser l'accueil, Liens externes (admin
uniquement), Diagnostic (jeton Keycloak) -- le déclencheur n'ouvre
QUE le sous-menu, ne navigue jamais lui-même. GED retirée du menu --
redondante avec la tuile d'accueil (#172), réduit le compte plutôt
que de le déplacer. Identité/thème/déconnexion inchangés.

Nouvelles classes CSS (.hub-nav, .hub-nav-dropdown/-panel).
Détail complet dans hub/README.md.

Vérifié réellement : structure JSX de App.jsx vérifiée par un
contrôle d'équilibre accolades/parenthèses/balises après la refonte
complète de l'en-tête. Confirmé que --text (nouveau CSS) existe pour
les deux thèmes (shared/theme.css).

Non vérifié dans cet environnement : rendu visuel réel (aucun
navigateur ici) -- en particulier le sous-menu Paramètres (pas de
fermeture au clic extérieur pour cette première version, choix
volontairement simple).

## 2026-09-01 (suite) — GED promue en tuile de front, étape 1 (version: 0f31edfb5a9b, livraison #172)

Backlog BACKLOG.md #9, étape 1 -- demandé explicitement : "GED
devrait être au même niveau que les applis du hub", en commençant
par le plus simple : une tuile sur l'accueil (même rang visuel que
Supervision SI/Portail tickets/DBA/Coffre-fort) qui bascule vers
GedView.jsx. Le vrai front "façon portail" (URL dédiée, plein écran)
reste explicitement pour plus tard ("on y reviendra").

Fronts (buildFrontsList, lib.js) supposent une URL de portail
EXTERNE -- GedView.jsx vit à l'intérieur du hub (un viewMode
interne). Tuile GED ajoutée directement dans App.jsx avec onClick au
lieu de url, concaténée APRÈS buildFrontsList pour bénéficier de la
MÊME personnalisation (réordonnancement/regroupement) que les autres
fronts. renderFrontTile accepte désormais f.onClick (rendu comme un
bouton stylé identiquement aux liens existants, nouvelle classe CSS
.hub-front-tile-button pour les quelques propriétés qu'un <button>
n'hérite pas par défaut contrairement à un <a>). Détail complet dans
hub/README.md.

Vérifié réellement : confirmé qu'applyHubLayout (hubLayoutLib.js) ne
dépend que de front.id, jamais de url -- compatible sans
modification avec une tuile onClick. Structure JSX de App.jsx
vérifiée par un contrôle d'équilibre accolades/parenthèses/balises.

Non vérifié dans cet environnement : rendu visuel réel (aucun
navigateur ici), en particulier le style du bouton face aux tuiles
existantes.

## 2026-09-01 (suite) — Deux notes de backlog : ged en front principal, calendrier partagé type pixel-grid (version: 024024133d30, livraison #171)

Aucun code livré -- deux nouveaux items ajoutés à BACKLOG.md (et au
skill utilisateur), demandés explicitement ("évol:").

Item #9 : promouvoir ged au même niveau que les fronts principaux du
hub (Supervision SI, Portail tickets, Administration, DBA,
Coffre-fort) -- actuellement juste une icône d'en-tête. Point de
conception noté : les fronts (buildFrontsList, hub/src/lib.js) sont
construits autour d'URLs de portails EXTERNES, alors que ged vit à
l'intérieur du hub (GedView.jsx, un viewMode interne) -- promouvoir
en front demandera probablement d'étendre ce mécanisme.

Item #10 : calendrier partagé présentant toutes les données liées à
un utilisateur ET une date/heure/plage horaire, avec une
visualisation correspondant au module pixel-grid existant (grille
temporelle dense année→minute, zoom par clic, actuellement pour les
alertes Zenoss). Demande d'agréger plusieurs sources (tickets,
documents ged, activité tunnels SSH) filtrées par utilisateur et
temps.

Les deux : juste notés, pas encore cadrés en détail.

## 2026-09-01 (suite) — Lien direct GED -> ticket, en rôle technicien si possible sinon repli demandeur (version: 82af3bed1015, livraison #170)

Demandé explicitement : depuis les "Liaisons" d'un document dans
GedView.jsx (hub), un lien ticket#N doit ouvrir la fiche du ticket
"en rôle technicien si possible et sinon un mode lecture seule". Et
en passant : un demandeur doit voir sa liste de tickets.

Implémenté : ?ticket=<id> dans l'URL du portail tickets, lu une
seule fois au montage. Si la personne a accès technicien, FORCE ce
rôle (prioritaire sur un choix manuel) et initialise
TechnicienView.jsx avec ce ticket (nouveau prop initialTicketId --
loadDetail fait un fetch direct par id, jamais filtré par la file
affichée, le ticket s'ouvre même hors des filtres par défaut).
Sinon, repli sur la vue demandeur (montre sa PROPRE liste de
tickets -- répond directement à la remarque complémentaire, c'est
exactement le mode "sans droits techniciens" demandé, pas une vue
séparée à construire) accompagné d'un bandeau explicite.

Côté hub, GedView.jsx rend désormais chaque liaison "ticket#N"
comme un lien cliquable vers cette URL. Détail complet dans
tickets/README.md.

Vérifié réellement : logique d'extraction du paramètre d'URL et de
calcul du rôle actif extraite et testée en isolation via Node (10
cas) -- y compris la confirmation que le comportement SANS lien
reste totalement inchangé. Structure JSX des 3 fichiers touchés
(App.jsx portail, TechnicienView.jsx, GedView.jsx) vérifiée par un
contrôle d'équilibre accolades/parenthèses/balises.

## 2026-09-01 (suite) — hub : badge groupes redondant retiré de l'en-tête (version: 690ef89b94d6, livraison #169)

Bug d'affichage signalé par la personne : répétition dans l'en-tête
du hub, les "beaux labels" de gauche (nom/rôles) et de droite
(boutons) écrasés par un débordement sur 2 lignes. Cause : `roles`
(affiché en clair, ex. "Administrateur, Demandeur...") est
littéralement `formatUserRoles(groups)` -- un badge séparé
affichait ENSUITE `groups` en brut (ex. "administrateurs,
demandeurs..."), la MÊME donnée deux fois de suite, dans deux
formats différents.

Corrigé : badge `hub-groups-chip` retiré de l'en-tête -- les
groupes Keycloak bruts restent consultables via le panneau
diagnostic existant (bouton 🔍, déjà prévu pour ça, aucune perte
d'information). Règle CSS `.hub-groups-chip` devenue inutile
retirée aussi. `groups` (la variable) reste utilisée telle quelle
partout ailleurs (permissions admin, panneau diagnostic) -- seul
l'affichage redondant dans l'en-tête a changé.

Vérifié réellement : confirmé par lecture du code que `roles`
dérive bien de `groups` (`formatUserRoles(groups)`, lib.js) --
répétition confirmée avant correctif. Structure JSX de App.jsx
vérifiée par contrôle d'équilibre accolades/parenthèses après
retrait. Confirmé que `groups` reste utilisé ailleurs (isAdmin,
panneau diagnostic) -- aucune régression fonctionnelle.

## 2026-09-01 (suite) — ged/Mayan : téléchargement corrigé -- URL construite directement (version: 393b135693f2, livraison #168)

L'upload fonctionne enfin (#166 confirmé en conditions réelles,
document visible dans Mayan), mais le téléchargement échouait à son
tour ("réponse Mayan sans 'download_url'"). Diagnostiqué avec la
personne via curl direct contre Mayan plutôt qu'une nouvelle
hypothèse à l'aveugle : les métadonnées du fichier
(GET .../files/<id>/) ne contiennent AUCUN champ lié au
téléchargement, mais GET .../files/<id>/download/ (URL simplement
CONSTRUITE) répond 200 OK avec le fichier ET fournit déjà
Content-Disposition avec le nom de fichier.

Corrigé : download_file construit directement l'URL (un appel
réseau de MOINS que l'approche précédente), extrait le nom de
fichier depuis Content-Disposition plutôt que de le redemander
séparément. Détail complet dans ged/README.md.

Vérifié réellement : extraction du nom de fichier testée avec
l'en-tête Content-Disposition EXACT renvoyé par la vraie instance de
la personne (accents, espaces compris), plus variantes et cas
limites (8 cas). Parcours upload+téléchargement complet retesté
contre un mock reproduisant fidèlement le comportement réel
confirmé (action_name requis + URL de téléchargement construite).

## 2026-09-01 (suite) — ged : onglet hub (version: 160fbbb22d08, livraison #167)

Backlog BACKLOG.md #6, dernier volet du module ged : GedView.jsx
(bouton d'en-tête 📁) -- navigation/gestion GÉNÉRALE des documents,
pas limitée à un ticket en particulier (contrairement à
TicketDocuments.jsx, #160) : envoi d'un document (liaison immédiate
optionnelle), filtre par entité liée, liste des documents connus,
versions (téléchargement, ajout), gestion des liaisons
(ajout/retrait indépendant).

Nouveau hub/src/gedClient.js, même motif que
tickets/portal/src/gedApi.js (#160), étendu avec la gestion des
liaisons (créer/supprimer) -- utile pour une navigation générale,
pas nécessaire côté tickets (une liaison unique à la création
suffit là-bas). VITE_GED_API_BASE_URL ajoutée au service hub
(docker-compose.yml), calculée comme les autres
VITE_*_API_BASE_URL existantes. Détail complet dans ged/README.md.

Vérifié réellement : gedClient.js testé avec un fetch simulé en
Node (26 cas -- bonnes URLs/méthodes/corps pour chaque fonction, y
compris la gestion des liaisons, préservation des messages
d'erreur réels). Structure JSX de GedView.jsx et de App.jsx
vérifiée par un contrôle d'équilibre accolades/parenthèses/balises.

Non vérifié dans cet environnement : compilation Vite réelle (npm
install bloqué, réseau restreint) ni rendu visuel dans un vrai
navigateur.

## 2026-09-01 (suite) — ged/Mayan : vraie cause du 400 identifiée et corrigée -- action_name toujours requis (version: ac4a4f397113, livraison #166)

Grâce au message d'erreur détaillé rendu visible en #163, la personne
a pu remonter le VRAI détail Mayan : {'action_name': ['This field is
required.']}. Confirme que action_name est en réalité TOUJOURS requis
par Mayan sur POST /documents/<id>/files/, y compris pour le PREMIER
fichier d'un document flambant neuf -- l'hypothèse initiale de #158
(ce champ optionnel hors nouvelle version) reposait sur une
documentation glanée qui ne le mentionnait QUE dans le contexte
"nouvelle version", jamais explicitement confirmée comme facultative
pour un premier envoi.

Corrigé : mayan_client.upload_file envoie désormais
action_name=replace SYSTÉMATIQUEMENT, y compris pour le premier
fichier -- aucune autre valeur documentée nulle part pour ce champ.
Détail complet dans ged/README.md.

Vérifié réellement : testé contre un mock REPRODUISANT EXACTEMENT le
comportement rapporté (exige action_name sur CHAQUE appel, même
message d'erreur si absent) -- confirmé que le premier envoi ET
l'ajout de version réussissent désormais tous les deux. Parcours
complet retesté de bout en bout contre ce mock strict (5 cas).

Non vérifié dans cet environnement contre la vraie instance Mayan --
ce sera le test décisif, la personne ayant fourni le message d'erreur
exact qui a permis ce correctif ciblé (plutôt qu'une nouvelle
hypothèse à l'aveugle).

## 2026-09-01 (suite) — tls-proxy : message clair sur permission refusée au lieu d'une trace Python brute (version: a00edd5ed351, livraison #165)

Bug réel rencontré au premier usage du rechargement automatique de
tls-proxy (#162) : PermissionError brute avec trace Python complète
en essayant d'écrire tls-proxy/generated/services.conf. Cause
probable : ce fichier avait été créé une première fois via `sudo
gateway/scripts/run.sh ...` (appartient donc à root), puis
scripts/chantier.sh (sans sudo) ne peut plus l'écraser.

Corrigé : render_nginx_conf.py capture désormais PermissionError
spécifiquement et affiche un message clair en français (cause
probable + commande de correction `sudo chown $(id -u):$(id -g)
...`) plutôt qu'une trace Python effrayante et incompréhensible pour
qui ne lit pas le code. Comportement NON BLOQUANT de
scripts/chantier.sh inchangé (le build principal continue malgré
cet échec). Piège documenté dans l'en-tête de scripts/chantier.sh.

Vérifié réellement : logique de gestion d'erreur testée via mock
(root, présent dans cet environnement, ignore les permissions Unix
classiques -- chmod ne suffit pas à reproduire une vraie
PermissionError ici) -- confirmé le message clair, la commande de
correction suggérée, et l'absence de trace Python. Cas normal
(succès) retesté sans régression contre le vrai fichier du projet.

## 2026-09-01 (suite) — ged : contexte dans les logs d'erreur + note de backlog archivage persistant (version: 491b55d19f43, livraison #164)

Deux points distincts, groupés dans cette livraison.

**Contexte dans les logs** : la personne a remarqué que le log de
l'échec Mayan précédent ("Création de document Mayan échouée :
...") ne disait ni quel ticket, ni quel fichier, ni qui avait tenté
l'envoi -- impossible à rattacher à une action précise si plusieurs
essais ont lieu sur des tickets différents. Corrigé : les logs
d'échec de create_document/add_version/delete_document/
download_version incluent désormais le fichier, l'entité liée
(ex. "ticket#42") et le demandeur quand disponibles -- nouveau
helper _link_context() (ged/api/app.py) qui retrouve les liaisons
connues d'un document même sur les routes qui n'ont que
document_id en paramètre direct.

**Note de backlog** (BACKLOG.md #8, sans code) : en testant ged/Mayan,
la personne a remarqué la non-rémanence des logs captés par le hub --
le tampon partagé (Memcached, #145) est volontairement en mémoire,
sans aucune persistance. Demande explicite : archiver TOUS les logs
(~18 services) à l'extérieur des conteneurs, SQL ou fichiers plats
au choix. Juste noté, pas encore cadré en détail.

Vérifié réellement : contexte de log testé avec un mock Mayan et une
CAPTURE RÉELLE des logs émis (pas juste une inspection du code) --
confirmé que fichier/ticket/demandeur ET le détail Mayan (DRF, #163)
apparaissent bien ensemble dans la même ligne. Parcours nominal
complet retesté sans régression (5 cas).

⚠️ Cette livraison est SÉPARÉE et POSTÉRIEURE à #163, que la
personne teste actuellement en isolation (demandé explicitement,
"c'est bien la version 163 pas la suivante") -- ne pas confondre les
deux zips lors du prochain essai.

## 2026-09-01 (suite) — ged/Mayan : correctif message d'erreur muet + nettoyage document orphelin (version: 808d3dcd7762, livraison #163)

Premier test RÉEL contre une vraie instance Mayan (4.11, déployée
correctement, 4 conteneurs sains, authentification fonctionnelle,
document créé avec succès) : l'envoi du fichier a échoué (400 Bad
Request), mais le message affiché était totalement muet --
raise_for_status() seul ne donne que la ligne de statut générique,
jamais le corps de la réponse, alors que Django REST Framework
(utilisé par Mayan) renvoie normalement un détail précis par champ.

Corrigé : mayan_client._raise_with_detail remplace tous les
raise_for_status() isolés du module -- capture et inclut le corps de
la réponse Mayan dans le message d'erreur, désormais visible jusque
dans l'interface. Confirmé au passage que le format de requête
lui-même (files={'file_new': ...}) correspond textuellement à la
documentation officielle (vérifié sur deux versions, 4.9 et 4.11) --
le 400 vient donc probablement d'un détail non visible dans les
extraits de doc glanés, le message désormais détaillé permettra de
trancher au prochain essai plutôt que de deviner à nouveau à
l'aveugle.

Effet de bord réel corrigé au passage : un document dont le
conteneur est créé côté Mayan mais dont l'envoi du fichier échoue
juste après restait une coquille VIDE orpheline ("Pages: 0" dans
l'interface Mayan, constaté réellement lors du premier essai) --
POST /documents nettoie désormais automatiquement ce document
orphelin en cas d'échec (best-effort). delete_document traite aussi
un 404 comme un succès silencieux (idempotent), même raisonnement
que file_store.py en #157. Détail complet dans ged/README.md.

Vérifié réellement : _raise_with_detail testé contre un mock
renvoyant un détail DRF réaliste (champ ET message précis visibles
jusque dans la réponse HTTP). Nettoyage automatique testé avec un
mock à état réel (document confirmé supprimé côté Mayan après un
échec simulé, aucune liaison locale créée). Parcours nominal complet
retesté sans régression (10 cas).

## 2026-09-01 (suite) — scripts/chantier.sh : rechargement automatique de tls-proxy après build (version: 1dc531f95669, livraison #162)

Demandé explicitement : "ajouter au script chantier toutes les
nouvelles parties dont on doit forcer le démarrage ou l'arrêt en
déploiement". Analyse des nouveautés récentes (schema-analyzer, ged,
ssh-tunnels) : toutes des services ORDINAIRES du stack main, déjà
bien gérés par up -d --build. Le SEUL élément qui échappe
structurellement à chantier.sh : tls-proxy (gateway/), qui lit sa
config depuis un fichier monté en VOLUME -- Docker ne détecte pas ce
genre de changement comme justifiant un redémarrage de conteneur.
Une route nouvellement ajoutée reste donc invisible tant que
tls-proxy n'est pas explicitement relancé -- bug réel rencontré DEUX
fois (schema-analyzer #151, ged #157/#160), diagnostiqué à la main
à chaque fois.

Corrigé : "build" régénère désormais la config nginx PUIS redémarre
tls-proxy automatiquement -- appel DIRECT à render_nginx_conf.py +
docker compose restart, JAMAIS via gateway/scripts/run.sh (qui
déclencherait aussi le prompt de changement de realm Keycloak, sans
rapport ici). Échec de ce rechargement NON BLOQUANT (gateway/ peut
être arrêté ou pas encore lancé) -- un avertissement clair, jamais
un build principal en échec à cause de ça. gateway/ et
vault-standalone/ restent par ailleurs intacts et jamais reconstruits
ni arrêtés, comme avant (#149).

Vérifié réellement : testé avec run.sh et docker FACTICES (le vrai
render_nginx_conf.py, lui, exécuté réellement) -- confirmé que build
appelle bien run.sh PUIS le rechargement tls-proxy avec les bons
arguments docker compose (mêmes flags que gateway/scripts/run.sh),
que down reste inchangé, qu'un service précis (build prefs-api)
déclenche aussi le rechargement, et que l'échec du redémarrage
tls-proxy (gateway arrêté, simulé) reste un avertissement NON
BLOQUANT (code de sortie du script global toujours 0).

## 2026-09-01 (suite) — Note de backlog : détection HTML dans DBA (version: d99d49443c63, livraison #161)

Aucun code livré -- ajout d'un nouvel item #7 à BACKLOG.md (et au
skill utilisateur), demandé explicitement par la personne ("note
pour le backlog"). Contexte : les tickets d'anciennes gestions
(importées en dump MySQL dans DBA) sont rédigés en HTML, affichés
tels quels aujourd'hui (balises brutes, illisibles). Besoin :
détecter le HTML dans N'IMPORTE QUEL champ (pas une liste de
colonnes connues à l'avance) et proposer un mode d'affichage rendu
(fiche ou fenêtre volante) -- mécanisme de déclenchement précis pas
encore cadré, à discuter ensemble le moment venu.

## 2026-09-01 (suite) — ged : intégration "Documents joints" côté tickets (version: 2315853424be, livraison #160)

Backlog BACKLOG.md #6, dernier volet restant après l'adoption de
Mayan EDMS (#158) : section "📎 Documents joints" dans les 4 vues du
portail tickets (Demandeur, Technicien, Politique, Admin ×2 --
réouvertures et archivage), juste à côté du fil de discussion
existant (TicketThread.jsx) à chaque fois.

Nouveau gedApi.js (tickets/portal/src/) -- client dédié vers ged-api
EN DIRECT (jamais via tickets-api, couplage faible), gère les envois
multipart/form-data (fichiers) que api.js existant ne supportait pas
(JSON uniquement). Nouveau composant TicketDocuments.jsx, même motif
autonome que TicketThread.jsx (ticketId/me en props, chargement/
état propres). Lister, envoyer (lié immédiatement au ticket en un
appel), ajouter une nouvelle version, télécharger, retirer un
document.

VITE_GED_API_BASE_URL ajoutée au service tickets-portal
(docker-compose.yml), calculée comme les autres VITE_*_API_BASE_URL
existantes -- pas une nouvelle clé .env, aucune entrée
ENV_CHANGELOG.md nécessaire (même motif que #156). Détail complet
dans tickets/README.md et ged/README.md.

Vérifié réellement : gedApi.js testé avec un fetch simulé en Node
(17 cas -- bonnes URLs/méthodes, construction correcte du FormData
pour les fichiers, préservation des messages d'erreur réels).
Structure JSX des 5 fichiers touchés (TicketDocuments.jsx + 4 vues)
vérifiée par un contrôle d'équilibre accolades/parenthèses/balises.

**Non vérifié dans cet environnement** : compilation Vite réelle
(npm install bloqué, réseau restreint) ni rendu visuel dans un vrai
navigateur -- et, en amont, ged-api/Mayan EDMS eux-mêmes restent non
vérifiés contre une vraie instance (#158) : ce sera donc le premier
test de bout en bout de toute la chaîne, pas seulement de cette
intégration.

## 2026-09-01 (suite) — Nouveau module ssh-tunnels : supervision de tunnels SSH, backend (version: dc729e962194, livraison #159)

Backlog BACKLOG.md #2, "à cadrer avant de coder" -- cadré avec la
personne en amont : connexions SORTANTES uniquement (ssh -L
classique, pas de scénario NAT/backward comme envisagé à l'origine
dans le backlog), clés = chemin protégé paramétré (jamais
générées/stockées ici), SSHFS = interface préparée mais PAS ENCORE
fonctionnelle (montage FUSE réel reporté, privilèges élevés
requis), mode proxy confirmé (type rinetd/proxy-delegated -- le
tunnel ouvre son port local sur ce conteneur, les autres API du
réseau Docker partagé s'y connectent directement par son nom).

Nouveau module ssh-tunnels/api -- tunnels_store.py (clés/connexions/
tunnels/montages SQLite), key_scanner.py (découverte de fichiers +
empreinte via ssh-keygen en sous-processus, jamais le contenu de la
clé), tunnel_process.py (lance/arrête de vrais processus ssh -L,
commande TOUJOURS construite par liste d'arguments, jamais
shell=True). UN SEUL worker Gunicorn pour ce service -- gérer de
vrais processus OS pose le même problème que les logs avant #145 (2
workers ne partagent pas leur mémoire) mais sans équivalent
Memcached possible pour un processus en cours d'exécution ; PID
stocké en base par prudence supplémentaire.

Bug réel trouvé et corrigé en testant : un enfant ssh arrêté reste un
processus ZOMBIE tant qu'il n'est jamais "récolté" (waitpid) par ce
processus Python -- un zombie répond TOUJOURS os.kill(pid, 0) avec
succès, is_process_alive le verrait à tort comme vivant
indéfiniment. Corrigé par un gestionnaire SIGCHLD
(install_reaper()) installé une fois au démarrage. Détail complet
dans ssh-tunnels/README.md.

Câblé dans docker-compose.yml (nouveau service ssh-tunnels-api,
volume clés en LECTURE SEULE), tls-proxy (/api/ssh-tunnels/, ordre
set/rewrite #146 vérifié), hub/src/logsLib.js (18e service de
logs), .gitignore (ssh-tunnels/keys/ explicitement exclu, plus
sensible que les autres dossiers de données déjà couverts par *.db).

Vérifié réellement : tunnels_store.py (23 cas -- contraintes FOREIGN
KEY et UNIQUE, upsert idempotent). key_scanner.py testé directement
(découverte, 4 défenses anti-traversée de chemin) -- empreinte
testée avec un ssh-keygen SIMULÉ (non disponible ici, réseau
restreint). tunnel_process.py testé avec un ssh SIMULÉ (démarrage,
arrêt propre, échec rapide avec message réel capturé, zombie détecté
ET corrigé, confirmé aucune accumulation sur 5 cycles). Application
complète testée de bout en bout (25 cas) -- cycle complet clés/
connexion/tunnel/démarrage-arrêt réels/échec réel/montages
(interface, 501 explicite)/contraintes de suppression.

**Non vérifié dans cet environnement** : contre un VRAI serveur SSH
distant (ssh/ssh-keygen simulés, openssh-client non installable ici,
réseau restreint) -- à tester en PRIORITÉ une fois déployé, avec de
vraies clés et un vrai hôte distant. Onglet hub et intégration DBA
restent à construire (backend seul cette livraison, même découpage
incrémental que schema-analyzer/ged).

## 2026-09-01 (suite) — ged : adoption de Mayan EDMS, adaptateur remplaçant le stockage homemade (version: 059cd78cb8fe, livraison #158)

"Allons-y pour Mayan EDMS" -- décision tranchée après la recherche
rapide de #157. Nouveau stack séparé mayan/ (même motif que
gateway/vault-standalone) -- 4 conteneurs vérifiés nécessaires contre
le docker-compose.yml OFFICIEL de Mayan (certaines sources
secondaires laissent penser à tort que 3 suffisent) : l'appli,
PostgreSQL, Redis, RabbitMQ. Adapté/simplifié pour ce projet (retrait
du mécanisme profiles:, retrait d'elasticsearch/traefik/workers
séparés non nécessaires pour un usage modeste). scripts/run.sh
propre (aucune dance d'import manuel, Mayan s'initialise seul via
MAYAN_AUTOADMIN_*). Ajouté comme cible dans scripts/run-all.sh.

ged-api réécrit en ADAPTATEUR vers Mayan (nouveau mayan_client.py) --
le stockage/versioning homemade de #157 (fichiers disque +
document_versions SQLite) disparaît, remplacé par de vrais appels à
l'API REST Mayan. La table de liaison POLYMORPHE (document_links)
reste LOCALE -- Mayan n'a pas cet équivalent, référence désormais des
IDs de documents Mayan. L'API HTTP EXPOSÉE par ged-api reste STABLE
malgré ce changement de backend (objectif tenu depuis #157) -- futur
onglet hub et intégration tickets n'auront pas à changer.

Connaissance PARTIELLE de l'API Mayan réelle (documentation glanée
par fragments, aucune instance accessible ici) -- confirmé avec
confiance raisonnable (création document, upload avec
action_name=replace pour une nouvelle version, réponse 202
asynchrone, types de documents) ; moins certain (forme exacte du
listage de fichiers, mécanisme de téléchargement) -- documenté
explicitement comme tel dans le code et ged/README.md.

Vérifié réellement : mayan_client.py testé contre un VRAI serveur
Flask simulant les réponses documentées (15 cas). documents_store.py
simplifié testé (9 cas). Application complète testée de bout en bout
contre un mock Mayan à ÉTAT RÉEL, pas des réponses fixes (17 cas) --
cycle complet création/versions/téléchargement/filtre/suppression.
Bug réel trouvé et corrigé en cours de route : vérification
d'existence d'un document désormais EXPLICITE (GET
/api/v4/documents/<id>/), plus jamais déduite d'une liste de fichiers
vide (ambiguïté non levée par la documentation glanée). Détail
complet dans ged/README.md et mayan/README.md.

**Non vérifié dans cet environnement, comme tout ce qui touche
Docker dans ce projet** : contre une VRAIE instance Mayan (aucun
moteur Docker disponible ici) -- à tester en PRIORITÉ ABSOLUE une
fois déployé, la connaissance partielle de l'API réelle rend cette
vérification plus importante encore que pour les autres intégrations
de ce projet.

## 2026-09-01 (suite) — Nouveau module ged : gestion électronique de documents, backend (version: b071e1198519, livraison #157)

Demandé explicitement : "gestion de documents liés/joints" pour les
tickets + "interface/API GED" dans le hub. Choix d'une vraie GED
tierce EXPLICITEMENT DÉFÉRÉ par la personne ("on travaillera cet
aspect plus tard") -- fondation homemade construite en attendant
(stockage disque + SQLite), API pensée pour rester stable si un vrai
backend GED (Mayan EDMS pressenti après recherche rapide -- Python/
Django, versioning natif, API REST, PostgreSQL/MySQL/SQLite, mature
depuis 2010) la remplace plus tard.

Table de liaison POLYMORPHE (document_links) -- répond directement à
"accès polymorphe aux documents" même sans GED tierce : un document
peut être lié à N'IMPORTE QUEL type d'entité (linked_type="ticket"
aujourd'hui), jamais une clé étrangère SQL vers un autre service
(couplage faible, juste un identifiant).

POST /documents (multipart, avec liaison immédiate optionnelle),
POST /documents/<id>/versions (numérotation automatique),
téléchargement par version précise ou "latest", GET /documents avec
filtre par entité liée, gestion des liaisons indépendante. Fichiers
sur disque (nommage opaque uuid4), métadonnées SQLite séparées
volontairement. Détail complet dans ged/README.md.

Câblé dans docker-compose.yml (nouveau service ged-api), tls-proxy
(/api/ged/, ordre set/rewrite #146 vérifié), hub/src/logsLib.js
(17e service de logs).

Vérifié réellement : documents_store.py (22 cas -- versions,
liaisons polymorphes multiples, filtre, suppression en cascade),
file_store.py (11 cas -- écriture par morceaux, 4 tentatives de
traversée de chemin toutes rejetées), application complète testée
de bout en bout avec de VRAIS envois multipart/form-data (25 cas --
upload, versions, téléchargement contenu vérifié octet pour octet,
suppression confirmée PHYSIQUEMENT sur le disque).

Cette livraison couvre le BACKEND uniquement -- onglet hub et
intégration côté tickets restent à faire (même découpage incrémental
que schema-analyzer, #151→#156).

## 2026-09-01 (suite) — schema-analyzer : onglet hub (version: 261ea00bcb48, livraison #156)

Backlog BACKLOG.md #5, dernier volet du "cœur technique" : interface
complète pour schema-analyzer-api (#151-#154), jusqu'ici accessible
seulement via curl. Nouveau SchemaAnalyzerView.jsx (bouton d'en-tête
🧬) -- sélecteur de connexion DBA (LECTURE SEULE via dba-api, créer
une connexion reste le rôle de l'onglet DBA), lancement d'analyse,
3 sous-onglets : Schéma (tables/colonnes repliables + colonnes-listes
détectées), Relations (l'éditeur complet -- import des propositions,
confirmer/rejeter/supprimer, ajout manuel), Export (téléchargement
direct JSON/XML des relations confirmées).

Nouveau schemaAnalyzerClient.js -- contrairement à logsClient.js
(échecs silencieux), préserve le message d'erreur RÉEL renvoyé par
le serveur plutôt qu'un message générique. Deux nouvelles variables
d'environnement (VITE_DBA_API_BASE_URL, VITE_SCHEMA_ANALYZER_API_BASE_URL)
ajoutées au service hub dans docker-compose.yml. Détail complet dans
hub/README.md et schema-analyzer/README.md.

Vérifié réellement : schemaAnalyzerClient.js testé avec un fetch
simulé en Node (bonnes URLs/méthodes/corps, préservation des messages
d'erreur, listes vides plutôt qu'exception). Structure JSX de
SchemaAnalyzerView.jsx vérifiée par un contrôle d'équilibre
accolades/parenthèses/balises. **Non vérifié dans cet environnement**
(réseau restreint, npm install bloqué comme pip ailleurs) : compilation
Vite réelle, rendu visuel dans un vrai navigateur.

## 2026-09-01 (suite) — gateway : option "marquer" pour le prompt de realm Keycloak qui redemandait à chaque exécution (version: d7780b53f949, livraison #155)

En diagnostiquant l'injoignabilité de schema-analyzer (routage
tls-proxy jamais régénéré depuis son ajout -- résolu par la personne
via gateway/scripts/run.sh restart tls-proxy), la personne a demandé
à désactiver le prompt "vider le volume Keycloak et réimporter ?"
qui revenait à chaque exécution malgré un realm inchangé depuis
longtemps.

Comportement EXISTANT volontaire (bug corrigé en #128) : répondre
"non" ne met jamais à jour le marqueur, pour ne jamais perdre de vue
un changement réel en attente -- donc ça redemande à chaque fois tant
qu'on ne répond pas "oui" (irréversible : vide + réimporte). Sans
troisième option, la personne n'avait aucun moyen de dire "ce
contenu est bon, arrête de demander" sans accepter une purge
destructive à laquelle elle ne voulait pas consentir.

Ajout d'une troisième réponse au prompt : "marquer" -- accepte l'état
actuel du volume TEL QUEL (rien vidé, rien réimporté), mais enregistre
quand même le marqueur. L'alerte ne revient plus pour CE contenu exact
de realm-template.json, seulement si le fichier change réellement par
la suite. Détail complet dans gateway/README.md et l'en-tête de
gateway/scripts/run.sh.

Vérifié réellement : logique extraite et testée isolément (8 cas) --
"marquer" met à jour le marqueur sans purger ; "non"/"oui" gardent
exactement leur comportement existant (non-régression) ; confirmé
qu'après un "marquer" réussi, une exécution suivante avec un contenu
réellement identique ne déclenche plus AUCUN prompt.

## 2026-09-01 (suite) — schema-analyzer : export du graphe relationnel JSON/XML (version: de57c3bed2ba, livraison #154)

Backlog BACKLOG.md #5, volet suivant après l'éditeur de relations
(#152-#153) : GET /relations/graph?connection_id=X&database=Y&format=json|xml
(défaut json) -- exporte les tables (noeuds) et les relations
CONFIRMÉES UNIQUEMENT (arêtes) -- jamais les propositions
proposed/rejected, qui ne représentent pas encore un schéma validé
par une personne. XML produit avec xml.etree.ElementTree (bibliothèque
standard, aucune dépendance externe).

Petit refactor de schema_client.py au passage : fetch_tables_and_columns
extrait de fetch_full_schema, réutilisé par l'export du graphe pour
éviter un GET /rows par table (échantillonnage de lignes inutile pour
cet usage). Non-régression de fetch_full_schema vérifiée. Détail
complet dans schema-analyzer/README.md.

Vérifié réellement : build_graph et graph_to_xml testés directement
(seules les relations confirmed deviennent des arêtes, XML confirmé
BIEN FORMÉ en le reparsant réellement avec ElementTree, pas
seulement inspecté comme texte). Route /relations/graph testée de
bout en bout (JSON et XML, content-type correct, 400 sur format
invalide, 502 sur connexion dba-api en erreur) contre un vrai
serveur Flask simulant dba-api.

## 2026-09-01 (suite) — schema-analyzer : bug corrigé (protection database=None inopérante) + signal explicite (version: b88a8b4ead2f, livraison #153)

La personne a demandé si la protection contre l'écrasement (#152)
était signalée quelque part -- en vérifiant, bug réel trouvé : la
contrainte UNIQUE de la table relations inclut database_name, or en
SQL NULL n'est JAMAIS égal à un autre NULL. Pour une connexion SANS
base précise (database=None, cas fréquent -- ex. SQLite côté DBA), la
protection contre l'écrasement était donc SILENCIEUSEMENT
inopérante : chaque réimport dupliquait indéfiniment la même
relation au lieu d'être bloqué. Cas non couvert par les tests
initiaux de #152.

Corrigé en normalisant database=None vers une chaîne vide AVANT
stockage/comparaison (_normalize_database) -- une chaîne vide EST
comparable pour l'unicité, contrairement à NULL. Vérifié
explicitement (le bug était reproductible avant, confirmé absent
après).

Profité de l'occasion pour répondre à la vraie question posée :
rendre le signal de protection VISIBLE. POST /relations/import-proposals
renvoie désormais {"imported": [...], "skipped": [...]} -- chaque
élément de skipped porte existing_id et existing_status (statut
ACTUEL de la relation qui a bloqué l'import), plutôt qu'un simple
delta de compteur à déduire soi-même. Détail complet dans
schema-analyzer/README.md.

Vérifié réellement : non-régression du CRUD confirmée, nouveau
comportement testé (rejet puis réimport -> signalé "rejected" ;
confirmation puis réimport -> signalé "confirmed", statuts jamais
modifiés), le tout aussi testé de bout en bout contre un vrai
serveur Flask simulant dba-api jusque dans la réponse HTTP.

## 2026-09-01 (suite) — schema-analyzer : éditeur de relations (version: 9b375a1dcb6f, livraison #152)

Backlog BACKLOG.md #5, volet suivant après #151 : persistance +
validation manuelle des relations proposées. Jusqu'ici /analyze
produisait des propositions FRAÎCHES à chaque appel, jamais stockées
-- aucune validation persistante possible ("proposition automatique
et validation manuelle" demandé explicitement). Nouvelle table
SQLite relations (relations_store.py, même motif que dba-api/
prefs-api) -- chaque relation a un status
(proposed/confirmed/rejected) et une source (auto/manual), rattachée
à un (connection_id, database) précis.

POST /relations/import-proposals relance l'analyse et ENREGISTRE
chaque proposition (status="proposed") -- pont EXPLICITE entre
diagnostic et éditeur, jamais automatique. Les relations déjà
connues (même rejetées/confirmées entre-temps) ne sont JAMAIS
écrasées par un réimport -- vérifié explicitement. CRUD complet :
GET /relations (liste), POST /relations (création manuelle,
status="confirmed" par défaut), PUT /relations/<id> (correction ou
changement de statut), DELETE /relations/<id>. Détail complet dans
schema-analyzer/README.md.

Vérifié réellement : relations_store.py testé directement (21 cas --
CRUD, isolation par connexion/base, doublons rejetés proprement,
réimport sans écrasement). Application complète testée de bout en
bout (20 cas) contre un vrai serveur Flask simulant dba-api, y
compris le cycle complet import -> validation -> correction ->
suppression. Non-régression de /analyze confirmée. Non vérifié :
contre un vrai dba-api réel ni une vraie vieille base tickets.

## 2026-09-01 (suite) — Nouveau module schema-analyzer : accès + analyse + reconnaissance de relations (version: 7f787dcda561, livraison #151)

Backlog BACKLOG.md #5 (accès/migration/interfaçage vieilles bases
tickets), premier volet livré : nouveau module dédié (onglet + API,
onglet pas encore construit), décision d'architecture prise avec la
personne avant de coder -- s'appuie sur dba-api en HTTP pour tout
l'accès (connexions MySQL/Postgres/SQLite + import de dump déjà
gérés là-bas), jamais d'accès direct à une base SGBD depuis ce
nouveau module.

Un seul endpoint POST /analyze : introspection de schéma via
dba-api, relations proposées par le NOM des champs (suffixe _id +
correspondance de table, confiance haute/moyenne), et détection de
colonnes TEXTE utilisées comme liste d'identifiants (ex. sites:
"1,2,5", cas explicitement signalé par la personne, invisible dans
le type de colonne -- détecté en échantillonnant les valeurs
réelles, avec une table cible devinée par nom). Aucune proposition
n'est jamais appliquée/stockée -- diagnostic en lecture seule,
validation manuelle prévue à l'étape suivante (éditeur de relations,
pas commencé). Détail complet dans schema-analyzer/README.md.

Câblé dans docker-compose.yml (nouveau service schema-analyzer-api,
dépend de dba-api + memcached), tls-proxy (/api/schema-analyzer/,
ordre set/rewrite #146 vérifié programmatiquement), et
hub/src/logsLib.js (LOG_SERVICES, 16e service).

Vérifié réellement : les modules purs (relation_detector.py,
list_detector.py) et le client HTTP (schema_client.py) testés
directement -- schema_client.py contre un VRAI petit serveur Flask
simulant dba-api (thread réel, vraies requêtes HTTP), y compris les
cas d'erreur. Application complète testée de bout en bout (/analyze
réussi, /analyze en échec -> 502 avec message réel, /logs confirmant
la journalisation via le tampon Memcached partagé #145). Non
vérifié : contre un vrai dba-api réel ni une vraie vieille base
tickets (pymysql/psycopg2/pymemcache réels non installables ici).

## 2026-09-01 (suite) — Backlog : accès/migration/interfaçage vieilles bases tickets (doc seule) (version: c39c0da6f01f, livraison #150)

Ajout demandé au backlog, aucun code écrit. Décision d'architecture
prise avec la personne avant l'ajout : nouveau module dédié (onglet +
API), en s'appuyant sur dba/api pour la couche accès (connexion MySQL
directe + import de dump, déjà fonctionnel) plutôt que de la
reconstruire. Volets décrits par la personne : module d'analyse,
reconnaissance de relations par le nom des champs (proposition
automatique + validation manuelle), éditeur de relations, cas
particulier des champs listes/ensembles/texte-utilisé-comme-liste
(ex. "sites: 1,2,5"), export XML+JSON "graphe relationnel",
proposition d'interface d'édition des données, interface de gestion
des affectations de relations. Détail complet dans BACKLOG.md.

## 2026-09-01 (suite) — Nouveau script scripts/chantier.sh : redéploiement rapide sans toucher à Keycloak (version: 004606b25667, livraison #149)

Demandé explicitement : une commande "chantier" avec deux
sous-commandes down/build, pour redéployer SEULEMENT le stack main
(~20 services applicatifs) pendant le développement, en laissant
gateway/ (Keycloak + tls-proxy) et vault-standalone/ intacts et en
fonctionnement -- Keycloak change rarement, inutile de le
redémarrer à chaque livraison, et un down/up --build involontaire
dessus romprait l'authentification de tout le monde pour rien.

Simple raccourci sur scripts/run.sh (qui ne gère déjà QUE le stack
main) -- aucune logique dupliquée :
  ./scripts/chantier.sh down             # arrête seulement main
  ./scripts/chantier.sh down -v          # idem + supprime les volumes
  ./scripts/chantier.sh build            # reconstruit + relance seulement main
  ./scripts/chantier.sh build prefs-api  # un seul service

"build" = toujours up -d --build (jamais un simple "docker compose
build" qui laisserait les anciens conteneurs tourner avec l'ancienne
image). Détail complet dans README.md racine.

Vérifié réellement : testé avec un run.sh factice affichant les
arguments reçus -- délégation confirmée correcte pour down, down -v,
build, build <service>, --help, et rejet propre d'une sous-commande
inconnue (exit 1, message clair).

## 2026-09-01 (suite) — Bug corrigé : gestionnaire de logs affiché trop étroit malgré max-width:1800px (version: 89799c0405e3, livraison #148)

Investigation multi-échanges (largeur d'écran, Box Model, script de
détection de débordement, remontée de tout l'arbre des ancêtres) --
la personne a fini par fournir la preuve directe qui a permis de
trouver la vraie cause : .hub-settings-wide mesurée à 538px de large
réel malgré max-width: 1800px confirmé gagnant dans les DevTools,
alors que .hub-shell (parent direct) fait bien 1920px.

Cause réelle : .hub-shell est display:flex/flex-direction:column.
.hub-settings porte margin: 0 auto -- sur un élément FLEX, des
marges horizontales à auto DÉSACTIVENT le comportement d'étirement
par défaut (align-items: stretch) : la boîte revient à un calcul
"ajustée au contenu" façon inline-block, plafonnée par max-width
mais jamais poussée à l'atteindre. max-width n'a donc jamais été
écrasé par une autre règle (comme les hypothèses précédentes le
supposaient) -- il n'avait simplement jamais l'occasion de
s'appliquer, faute d'un width explicite.

Corrigé : ajout de width: 100% à .hub-settings, restaure le
remplissage jusqu'à max-width (comportement attendu depuis #109,
jamais remarqué avant car le contenu des écrans existants dépassait
déjà naturellement 1400px -- le tableau de bord du gestionnaire de
logs, avec peu de colonnes, l'a rendu visible pour la première
fois). .hub-card (carte de connexion, censée rester ajustée à son
contenu) volontairement non touchée.

## 2026-09-01 (suite) — Logs de toutes sortes, étape 2/4 : sources URL (version: b83b6388ea6e, livraison #147)

Backlog BACKLOG.md #3, ordre choisi par la personne (push livré en
#142, URL ensuite). Nouvelle table log_sources dans prefs-api
(SQLite), unifiée pour les 4 types à venir (url fonctionnel,
file/rsyslog acceptés mais encore inertes). CRUD complet
(GET/POST/PUT/DELETE /log-sources), sans interface d'administration
pour l'instant -- à configurer via l'API directement.

Sondage en tâche de fond (prefs-api/log_sources_poller.py, thread
démon) -- relit log_sources à chaque cycle, respecte l'intervalle
propre à chaque source. Formats jsonl et plain (niveau déduit par
mots-clés français ET anglais -- découverte en cours de test que
"ERREUR" français ne contient pas "ERROR" anglais, corrigée). Écrit
dans le MÊME tampon Memcached partagé que /push-log (#145) et le
MÊME registre de sources -- le hub affiche les sources URL
automatiquement, sans aucune modification frontend. Détail complet
dans README.md racine.

Vérifié réellement : CRUD testé (20 cas), détection de niveau
bilingue testée, et un VRAI thread de fond démarré avec un vrai
cycle de sondage attendu (12s), confirmant qu'un échec réseau réel
est correctement journalisé sans jamais planter le thread.

## 2026-09-01 (suite) — Bug corrigé : la VRAIE cause complète du 500 systématique sur toutes les APIs (version: 0a082c00bf82, livraison #146)

Le 500 persistait après #136 malgré un correctif juste mais
insuffisant. La personne a fourni les vraies traces du conteneur
tls-proxy (docker compose logs) -- seule preuve qui a permis de
trouver la cause réelle : "using uninitialized backend variable",
"no host in upstream". Dans API_LOCATION_TEMPLATE, `rewrite ...
break;` était placé AVANT `set $backend ...;` -- or `break` interrompt
tout le traitement de la phase de réécriture nginx pour cette
requête, y compris les `set` qui suivraient. `$backend` restait donc
perpétuellement non initialisée sur les 15 routes "api" (jamais
"spa"/"keycloak", sans rewrite -- explique pourquoi le hub et
Keycloak ont toujours fonctionné pendant toute cette période).
Corrigé en inversant l'ordre : set doit toujours précéder rewrite.
Piège nginx connu et documenté, raté deux fois de suite (#134, #136)
faute de pouvoir observer un vrai nginx tourner dans cet
environnement. Détail complet dans tls-proxy/README.md.

Vérifié réellement : régénération + vérification exhaustive des 15
locations "api" -- set confirmé avant rewrite dans chacune (position
textuelle vérifiée programmatiquement). **Non vérifié dans cet
environnement, comme pour les deux tentatives précédentes** : le
comportement réel d'un vrai nginx -- cette fois appuyé sur une preuve
directe plutôt qu'une hypothèse depuis le code, mais reste à
confirmer par un nouveau déploiement.

## 2026-09-01 (suite) — Tampon de logs partagé via Memcached sur les 15 backends + prefs-api (version: a0601d549d08, livraison #145)

Corrige un problème réel découvert en investigant la panne du 01/09 :
les 15 APIs + prefs-api tournent avec 2 workers Gunicorn (processus
séparés, mémoire NON partagée) -- tout le mécanisme de logs (/logs,
/hub-log, /push-log) était un tampon EN MÉMOIRE PAR PROCESSUS, une
entrée capturée par un worker restait invisible selon le worker qui
traitait la lecture suivante. Choix assumé : les 2 workers restent à
2 (pas réduits à 1), corrigé via Memcached (déjà présent dans le
projet) plutôt qu'en sacrifiant la concurrence.

Nouveau module central shared/log_buffer.py (copié dans chaque
backend au build) -- lecture-modification-écriture avec CAS, jamais
un read-modify-write naïf. /push-log (sources externes, #142) avait
la même faille jumelle, corrigée en même temps. Conséquence
collatérale : 9 des 15 backends avaient un contexte de build Docker
trop étroit pour accéder à shared/ -- élargi à la racine du projet.
Détail complet dans README.md.

Vérifié réellement, service par service : 14 sur 15 testés de bout
en bout (vrai warning émis, lu via /logs, ET confirmé visible depuis
une connexion Memcached INDÉPENDANTE simulant un second worker --
preuve directe que le problème d'origine est résolu). vault-api
bloqué par un bug préexistant sans rapport (déjà documenté en #135).
Cœur de la logique CAS testé avec une VRAIE collision simulée entre
deux écritures concurrentes -- aucune entrée perdue. pymemcache et un
vrai Memcached non installables ici (réseau restreint) -- stub
fonctionnel construit pour ces tests. **Non vérifié dans cet
environnement** : comportement contre un vrai Memcached en
conditions réelles.

## 2026-09-01 (suite) — Backlog : client IMAP + interpréteur de messages → source (doc seule) (version: a3079ce53c21, livraison #144)

Ajout demandé au backlog, aucun code écrit -- 4 volets, dans l'ordre
donné par la personne : client IMAP (recevoir des messages de
différents systèmes), interface de gestion de boîte (dossiers/filtres),
gestionnaire d'interpréteur (message -> bloc JSON structuré,
généralise en outil configurable ce qui existe aujourd'hui figé sur
un seul format -- voir connectors/zenoss_legacy/,
parse_zenoss_emails.py), connecteur source (transforme le JSON en
source au sens déjà connu, POST /ingest/<source> potentiellement le
point d'arrivée naturel, à confirmer). Détail complet dans
BACKLOG.md.

## 2026-09-01 (suite) — Hub : écran d'aide, s'enrichit des README du projet (version: 7862c0b08546, livraison #143)

Demandé explicitement : "une aide qui s'enrichit des readme et des
exemples". Nouveau bouton ❓, écran à deux colonnes réutilisant le
rendu markdown déjà en place pour Historique du projet. "S'enrichit"
au sens littéral : GET /docs (prefs-api) redécouvre en direct tous
les README.md du dépôt à chaque appel -- un nouveau document apparaît
sans code à modifier. "Les exemples" : déjà dans les README existants,
pas de base séparée à maintenir.

Point de sécurité traité avec le plus grand soin : prefs-api monte
désormais la racine ENTIÈRE du dépôt en lecture seule (chemin séparé
de /data), incluant potentiellement .env/clés PKI/realms exportés.
Seule protection : liste blanche stricte (uniquement des fichiers
nommés EXACTEMENT README.md, dossiers sensibles exclus en défense en
profondeur, revalidation en direct à chaque lecture + normalisation
anti-traversée). Détail complet et raisonnement de sécurité dans
hub/README.md.

Vérifié réellement, avec un soin particulier : arborescence de test
fictive avec vrais pièges (.env, clés PKI, realm exporté avec faux
secret, node_modules contenant un VRAI README.md) -- confirmé que
seuls les README légitimes sont découverts, que toute lecture directe
d'un fichier sensible échoue en 404, et que 3 variantes de traversée
de chemin échouent proprement. Rejoué contre la VRAIE arborescence :
23 README découverts, zéro suspect, lecture réelle confirmée (81970
caractères). Syntaxe, YAML, accolades, classes CSS tous vérifiés.
**Non vérifié dans cet environnement** : rendu visuel réel, montage
Docker en conditions réelles.

## 2026-09-01 (suite) — Hub : sources de logs externes, push API (étape 1/4) (version: f00e5e6ba707, livraison #142)

Backlog "suivre des logs de toutes sortes" (fichier plat, rsyslog/UDP,
URL, push) -- étape 1 choisie par la personne, la plus simple,
prolonge /hub-log déjà en place. Nouvelles routes sur prefs-api :
POST /push-log (dépôt générique, source arbitraire créée
implicitement au premier push), GET /push-log/sources, GET
/push-log/<source> (même forme que /logs). Tampon par source, en
mémoire, même philosophie que les 15 services internes.

Généralisation nécessaire côté hub : mergeLogEntries/summarizeLogEntries
(logsLib.js) et fetchAllServiceLogs (logsClient.js) prennent
désormais la liste de services en paramètre OBLIGATOIRE (plus de
repli implicite sur LOG_SERVICES) -- LogsManagerView.jsx construit la
liste combinée (15 fixes + sources découvertes) et l'utilise partout,
une source externe se comporte exactement comme un service interne
dans les 3 présentations. Détail complet, limite connue acceptée
(léger sur-rafraîchissement) et backlog des 3 étapes restantes dans
hub/README.md et BACKLOG.md.

Vérifié réellement : les 3 nouvelles routes testées (création
implicite, isolation entre sources ET avec les warnings internes de
prefs-api, défensifs). Généralisation testée en profondeur --
non-régression complète sur les 15 services fixes, source externe
correctement intégrée. Test de bout en bout confirmant l'isolation.
Syntaxe, accolades, setters tous vérifiés. **Non vérifié dans cet
environnement** : rendu visuel réel, et surtout un vrai usage (aucun
script/outil externe n'a encore poussé de log réel).

## 2026-09-01 (suite) — Hub : écran de logs élargi + journalisation des propres erreurs de liaison du hub (version: 87170b597cbe, livraison #141)

Retours après le premier vrai test du gestionnaire de logs (#139).
1) Écran trop étroit sur grand écran : nouvelle classe
.hub-settings-wide (1800px), réservée au gestionnaire de logs, sans
toucher aux écrans formulaire (Paramètres/Liens externes/Personnaliser).
2) Le hub ne journalisait pas ses propres erreurs de liaison
(indicateurs de présence, accès aux 15 APIs) -- signalé comme "utile
actuellement" en plein test où tout apparaissait injoignable.

Nouvelle route POST /hub-log sur prefs-api (réutilise le même tampon
que /logs, pas un 16e service). Nouveau hub/src/hubLogClient.js :
logPresenceTransitions journalise UNE ligne PAR TRANSITION seulement
(jamais à chaque sondage) -- sans ça, un incident prolongé remplirait
le tampon de 200 entrées en quelques minutes. Câblé dans App.jsx
(indicateurs Keycloak/gateway, vault-standalone) et LogsManagerView.jsx
(tableau de bord/vue combinée + par service, refs séparés). Détail
complet dans hub/README.md.

Vérifié réellement : /hub-log testée (niveaux, préfixe [hub], message
vide -> 400, corps non-JSON -> 400 propre). logPresenceTransitions
testée en profondeur -- premier sondage/aucun changement -> rien
journalisé, transitions individuelles/multiples correctement
comptées, **état stable rejoué plusieurs fois -> aucune ligne
supplémentaire** (point le plus important). Syntaxe, accolades,
classe CSS toutes vérifiées. **Non vérifié dans cet environnement** :
rendu visuel réel, comportement sur un vrai flux d'événements
prolongé.

## 2026-09-01 (suite) — Hub : personnalisation de l'accueil, étape 3 -- écran + glisser-déposer (chantier terminé) (version: e48660c35b50, livraison #140)

Livre les 2 derniers points d'un coup (l'écran et le glisser-déposer
partagent la même infrastructure). Nouveau PersonalizeHomeView.jsx,
bouton 🎨 accessible à tout utilisateur (pas réservé aux admins).
7 nouvelles mutations pures dans hubLayoutLib.js (createGroup,
renameGroup, deleteGroup, setTileGroup, setTileHidden, moveTile,
moveGroup) -- jamais de mutation en place. Piège traité : ne jamais
réinitialiser silencieusement une tuile jamais personnalisée
(getEffectiveTileState résout sa position naturelle avant toute
mutation). Contrôles explicites (flèches, menu déroulant) restent la
méthode fiable pour tout ; glisser-déposer en couche additionnelle
pour le cas le plus courant (assigner à un cadre), appelle
exactement les mêmes fonctions de mutation -- jamais un second
mécanisme séparé. Chaque action enregistre immédiatement, mise à
jour optimiste. Détail complet dans hub/README.md.

Vérifié réellement : les 7 mutations testées en profondeur via Node
-- 21 vérifications dont les cas les plus subtils (moveTile sur des
tuiles jamais personnalisées, deleteGroup ne perd jamais de tuiles,
préservation d'état, bords de panier). Un bug de PORTÉE trouvé et
corrigé pendant l'écriture des TESTS eux-mêmes (pas le code).
Syntaxe, accolades, classes et variables CSS toutes vérifiées, bouton
confirmé accessible à tous. **Non vérifié dans cet environnement** :
rendu visuel réel, et en particulier le glisser-déposer natif lui-même
(seule la logique qu'il déclenche a pu être testée) -- si un souci
survient, les contrôles explicites restent pleinement fonctionnels en
repli.

## 2026-09-01 — Hub : gestionnaire de logs, 3 présentations (tableau de bord, par service, vue combinée) (version: 7402ca086205, livraison #139)

Demandé explicitement, venu en pleine panne réelle (500 systématique,
toujours en investigation). 3 présentations validées par la personne,
construites dans l'ordre demandé, sous-onglets d'un même écran
(bouton 📋). Prérequis traité en premier : /logs ajouté aux 4 APIs
qui ne l'avaient pas (dba-api, ldap-admin-api, prefs-api, vault-api),
motif repris exactement d'api/app.py. Chemins relatifs (/api/<segment>/logs),
aucune nouvelle variable d'environnement. Nouveaux hub/src/logsLib.js
(logique pure) et hub/src/logsClient.js (sondage des 15 services en
parallèle). Défensif de bout en bout : un service en panne n'affecte
jamais les 14 autres, distingué explicitement d'un service sain sans
erreur récente. Détail complet dans hub/README.md.

Vérifié réellement : les 4 nouveaux /logs (2 testés directement,
2 testés de façon isolée faute de dépendances dans cet environnement,
sans rapport avec l'ajout). logsLib.js testée en profondeur via
Node. logsClient.js testée avec fetch simulé -- parallélisme
RÉELLEMENT mesuré (~12ms pour 15 appels vs ~150ms si séquentiel).
Syntaxe, accolades, classes et variables CSS toutes vérifiées.
**Non vérifié dans cet environnement** : rendu visuel réel, et le
comportement contre les vrais 15 services -- notamment utile pour la
panne en cours, pas encore confirmé si l'outil lui-même fonctionne
tant que cette panne n'est pas résolue.

## 2026-08-31 (suite) — Hub : indicateurs de présence Keycloak/gateway/vault-standalone (version: 1e5024a12790, livraison #138)

Demandé explicitement, à côté de l'horloge et de la version. Nouvelle
route GET /status sur prefs-api -- vérification CÔTÉ SERVEUR (évite
CORS et certificat auto-signé non approuvé par le navigateur pour
vault-standalone), en parallèle (ThreadPoolExecutor), timeout 3s par
sonde. "gateway" reflète exactement "keycloak" (choix assumé,
expliqué : tls-proxy n'a rien de propre à sonder, sa disponibilité
est déjà prouvée par le chargement de la page). vault_standalone
sondé via son port publié sur l'hôte, HOST_IP exposé explicitement à
prefs-api (piège évité : localhost aurait désigné le conteneur
lui-même, pas la machine hôte). Détail complet dans hub/README.md.

Vérifié réellement : /status testé (repli propre même si rien n'est
joignable, gateway=keycloak confirmé, parallélisme mesuré).
_check_reachable() testée contre de VRAIS serveurs HTTP locaux (200,
503, port fermé, timeout court) -- jamais juste mocké. Syntaxe,
accolades, classes et variables CSS toutes vérifiées. **Non vérifié
dans cet environnement** : rendu visuel réel, et la sonde contre une
vraie instance vault-standalone (jamais démarrée ici).

## 2026-08-31 (suite) — Hub : horloge permanente navigateur/serveur, à côté de la version (version: bcde54c2dc65, livraison #137)

Demandé explicitement : "tout semble désynchronisé sous docker".
prefs-api (/health) renvoie désormais server_time. Hub : nouveau
badge permanent (jamais masquable, contrairement au pied de page de
la grille) à côté du badge de version -- horloge navigateur (tique
chaque seconde) + heure serveur (sondée toutes les 30s, extrapolée
entre deux sondages), écart signalé au-delà de 3s. Comparaison contre
UNE SEULE référence (prefs-api) -- choix assumé, suffisant pour le
cas le plus probable (horloge VM/démon Docker désynchronisée de
l'hôte, partagée par tous les conteneurs Linux), facile à étendre à
d'autres services si besoin. Détail complet dans hub/README.md.

Vérifié réellement : /health testé (server_time présent, numérique).
Logique de dérive/extrapolation testée via Node -- synchro parfaite,
avance/retard détectés dans le bon sens, seuil de 3s respecté (pas de
bruit sous le seuil), extrapolation entre deux sondages vérifiée
précisément, absence d'heure serveur jamais NaN/exception. Syntaxe,
accolades, classes et variables CSS toutes vérifiées. **Non vérifié
dans cet environnement** : rendu visuel réel, et la vraie
désynchronisation rapportée -- cet outil permet de la CONSTATER,
sans garantir d'en révéler la cause exacte.

## 2026-08-31 (suite) — Bug corrigé : 500 systématique sur toutes les APIs (proxy_pass ambigu) (version: 9abbf5ab5c0b, livraison #136)

Rapporté par la personne sur la version #134 : GET /api/<service>/logs
retournait 500 sur les 11 APIs Flask, identique et simultané. 500 (pas
502) = nginx atteignait bien chaque backend, le problème était ce qui
lui était transmis, pas l'accès réseau.

Cause réelle : proxy_pass http://$backend; (variable NUE) laissait une
ambiguïté nginx jamais vérifiable ici faute de binaire nginx
installable -- transmet-elle $uri (reflète le rewrite) ou $request_uri
(original, préfixe compris) ? En pratique : $request_uri -- chaque API
recevait son propre préfixe en plus de ses routes internes, le rewrite
de #134 ne servait à rien.

Corrigé : proxy_pass http://$backend$uri$is_args$args; explicite,
plus aucune ambiguïté à trancher sans pouvoir tester -- $uri reflète
TOUJOURS les rewrite par définition documentée. Appliqué aux 22
locations (API et SPA/Keycloak, même risque potentiel des deux côtés).
Détail complet dans tls-proxy/README.md.

Vérifié réellement : régénération + vérification exhaustive des 22
locations, forme explicite partout, plus aucune trace de l'ancienne
forme ambiguë. **Toujours non vérifié dans cet environnement** :
syntaxe nginx réelle, nginx toujours pas installable ici (dépôts
Ubuntu bloqués, 403).

## 2026-08-31 (suite) — Keycloak + tls-proxy sortis vers un stack gateway/ séparé (version: 545f4e68194f, livraison #135)

Extraction demandée par la personne, priorisée après relecture du
plan détaillé : trb140-sms-relay dépend maintenant de Keycloak, qui
ne devait plus subir les redémarrages du reste du stack. Nouveau
stack gateway/ (docker-compose.yml + scripts/run.sh), troisième
cible de scripts/run-all.sh aux côtés de main/vault-standalone. MÊME
realm Keycloak que le stack principal (pas une duplication comme
vault-standalone) -- volume Keycloak existant référencé external:true
pour préserver le realm à la migration.

Trois obstacles réels résolus : depends_on ne fonctionne pas
cross-stack (6 références retirées, recherche systématique, rendu
acceptable par la résolution DNS dynamique de #134) ; réseau Docker
partagé obligatoire (nommé explicitement, external:true des deux
côtés, créé de façon idempotente par les deux run.sh) ; résolution de
.env/chemins relatifs entre deux docker-compose.yml (résolu via
--env-file/--project-directory pointant vers la racine). Un bug de
contexte de build trouvé et corrigé au passage (keycloak-backup).
Détail complet dans gateway/README.md, keycloak/README.md et
tls-proxy/README.md mis à jour avec un renvoi.

Vérifié réellement : YAML valide (les deux fichiers), recherche
EXHAUSTIVE programmatique (parsing YAML, pas juste grep) confirmant
zéro depends_on résiduel vers keycloak/tls-proxy/keycloak-backup,
syntaxe bash des 3 scripts touchés. gateway/scripts/run.sh exécuté de
bout en bout (Docker simulé via stub, mais render.py/PKI/
render_nginx_conf.py RÉELLEMENT exécutés) -- réseau créé, HOST_IP,
realm rendu, CA/certificat réels générés, config nginx 22 services,
détection de changement de realm avec REALM_PURGE_DECLINED (#128)
correctement reprise (chemin "non" ET "oui" testés séparément,
marqueur vérifié dans les deux cas), invocation docker compose finale
confirmée avec les 4 bons indicateurs dans le bon ordre
(-p/--env-file/--project-directory/-f). scripts/run.sh (principal,
simplifié) et scripts/run-all.sh testés de la même façon.

**Non vérifié dans cet environnement, faute de Docker et de nginx
réels disponibles ici** : le comportement RÉEL du réseau Docker
partagé et de la référence external:true au volume Keycloak existant
-- jamais exécutés contre un vrai démon Docker. Premier test réel à
faire, sur une machine de test : gateway d'abord, puis main, vérifier
l'accès complet avant de considérer la migration terminée. Point de
rollback le plus précis : revenir à la livraison #134 (docker-compose.yml
à un seul fichier, testé depuis le début de ce projet).

## 2026-08-31 (suite) — tls-proxy : résolution DNS dynamique, prérequis à la séparation Keycloak/tls-proxy (version: ffa1bfac5356, livraison #134)

Prérequis demandé par la personne avant de sortir Keycloak+tls-proxy
du stack principal (backlog). Problème réel rencontré deux fois :
proxy_pass littéral force nginx à résoudre chaque nom UNE SEULE FOIS
au chargement -- un seul service pas encore créé fait REFUSER LE
DÉMARRAGE ENTIER de nginx (incident 2026-08-26, bug keycloak_admin.py
#125). Séparer les stacks aurait aggravé ce risque (depends_on ne
fonctionne pas entre deux docker-compose.yml distincts).

Corrigé : resolver 127.0.0.11 (DNS interne Docker) + variable dans
chaque proxy_pass -- nginx démarre désormais toujours, 502 le temps
qu'un service apparaisse plutôt qu'un refus de démarrer. Piège nginx
compensé : proxy_pass avec variable ne retire plus automatiquement le
préfixe -- rewrite explicite ajouté pour les 15 locations "api"
(jamais pour les 7 "spa"/keycloak, qui doivent le conserver).
vault-standalone a sa propre copie séparée, pas touchée (hors
périmètre, risque moindre). Détail complet dans tls-proxy/README.md.

Vérifié réellement : syntaxe Python, génération réelle puis
vérification EXHAUSTIVE du fichier généré pour les 22 services
(accolades, resolver unique, rewrite exact par API, absence de
rewrite + en-têtes WebSocket par SPA, aucun résidu de l'ancien
style). **Non vérifié dans cet environnement** : syntaxe nginx
elle-même jamais validée par nginx -t (dépôts Ubuntu inaccessibles
depuis ce bac à sable, 403) ni par un nginx réellement démarré --
premier vrai test à faire avant de poursuivre vers la séparation des
stacks.

## 2026-08-31 (suite) — Hub : personnalisation de l'accueil, étape 2 (modèle de données + fusion + rendu en cadres) (version: f3e9caf4181c, livraison #133)

Suite de la personnalisation de l'accueil (#132). Nouveau
hub/src/hubLayoutLib.js (logique pure) : applyHubLayout(fronts,
hubLayout) regroupe/trie/filtre pour l'affichage, défensif sur toute
forme malformée. Stocké dans le blob /preferences déjà existant
(clé hubLayout) -- aucun changement de schéma prefs-api, PUT
/preferences fait déjà une fusion superficielle côté serveur.
fetchHubLayout/saveHubLayout ajoutées à settingsClient.js. App.jsx :
hubLayout chargé avant les retours anticipés (lu depuis auth
directement, pas la variable profile pas encore fiable à ce stade),
grille rendue en tuiles sans cadre + cadres titrés créés par
l'utilisateur (renderFrontTile factorisé). Aucun changement de
comportement visible tant que l'écran de personnalisation (étape
suivante) n'existe pas. Détail complet dans hub/README.md.

Vérifié réellement : syntaxe (tsc --jsx) sur 4 fichiers, accolades
CSS/JSX équilibrées, classes présentes des deux côtés, setters
cohérents. applyHubLayout testée en profondeur via Node (import
direct du vrai fichier) -- 17 vérifications dont groupId fantôme
(cadre supprimé), cadre devenu vide (masqué du résultat), entrées/
types corrompus -- toujours un repli propre, jamais une exception.

## 2026-08-31 (suite) — Hub : personnalisation de l'accueil, étape 1 (pied de page fixe/masquable) (version: 6c6bb71af3bd, livraison #132)

Chantier large cadré avant de coder : masquer/réorganiser/grouper les
tuiles par utilisateur, avec contrôles explicites ET glisser-déposer
en complément (utilisateurs Mac). Étape 1 : grille défilante
indépendamment, pied de page fixe en bas masquable (bouton toujours
atteignable), état mémorisé par appareil -- même principe que la
timeline masquable (#130). Scopé à cet écran uniquement, .hub-shell
non touché pour ne pas risquer les autres vues. Détail complet et
plan des 4 étapes restantes dans hub/README.md.

Vérifié réellement : syntaxe (tsc --jsx), accolades CSS/JSX
équilibrées, .hub-note confirmée absente après remplacement, classes
présentes des deux côtés. Logique de préférence testée via Node.
**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici.

## 2026-08-31 (suite) — Backlog : sortir Keycloak/tls-proxy du stack principal, discuté et reporté (version: 2afcb286586e, livraison #131)

Aucun code touché -- mise à jour de documentation seule (BACKLOG.md).
Discussion : une application externe (trb140-sms-relay) dépend
maintenant de la disponibilité de Keycloak, qui ne devrait pas subir
les redémarrages fréquents du reste du stack principal. Piste
explorée (vault-standalone dupliquant l'instance Keycloak ne convient
pas ici, le vrai obstacle est le réseau Docker partagé dont tls-proxy
a besoin pour router vers les autres services) -- personne a choisi
de reporter explicitement plutôt que de se lancer maintenant.

Au passage, clarifié que la sauvegarde/restauration des appartenances
aux groupes Keycloak (autre demande de la personne) existe déjà de
longue date (export automatique avant toute purge, commande dédiée
./scripts/run.sh restore-groups) -- rien à construire de ce côté.

## 2026-08-31 (suite) — Hub : timeline masquable dans la coquille à onglets (version: a5b03a9a73be, livraison #130)

Retouche ciblée demandée après coup sur la timeline (#118-#120).
Nouveau bouton 🕒 dans la barre d'onglets, état mémorisé par appareil
(localStorage, même principe que la mémorisation des onglets ouverts,
#112) -- visible par défaut. Détail complet dans hub/README.md.

Vérifié réellement : syntaxe (tsc --jsx), accolades CSS/JSX
équilibrées. Logique de chargement de la préférence testée via Node
-- défaut visible, valeurs stockées respectées, JSON corrompu (jamais
une exception), valeur inattendue non strictement true traitée comme
masquée. **Non vérifié dans cet environnement** : rendu visuel réel,
aucun navigateur disponible ici.

## 2026-08-31 (suite) — Hub : tuiles de la grille d'accueil plus compactes (version: e34ffa989b56, livraison #129)

Demande de design explicite : description sur une ligne (ellipsis),
lien "Ouvrir →" retiré (redondant, toute la tuile est cliquable),
rembourrage haut/bas divisé par 2, densité de grille doublée
(minmax 260px -> 180px), zone centrale élargie (max-width 900px ->
1400px). Choix assumé : cet écran n'a aujourd'hui aucune colonne
latérale réelle -- plafond simplement remonté plutôt que d'inventer
des colonnes qui n'existent pas. Détail complet dans hub/README.md.

Vérifié réellement : syntaxe (tsc --jsx), accolades CSS équilibrées,
hub-front-link confirmé absent des deux fichiers après retrait, ordre
de cascade CSS vérifié. **Non vérifié dans cet environnement** :
rendu visuel réel, aucun navigateur disponible ici.

## 2026-08-31 (suite) — Bug corrigé : refus de réimport Keycloak oublié dès le lancement suivant (version: f2bd5dd19615, livraison #128)

Rapporté par la personne juste après le correctif #127 : répondre
"non" à la confirmation de réimport une seule fois faisait
disparaître la question définitivement, alors que Keycloak tournait
toujours sur l'ancien realm (prefs-api-service absent).

Cause réelle : le marqueur (keycloak/.last-imported-realm.json) était
copié inconditionnellement en fin de scripts/run.sh dès que "up"
figurait dans la commande -- y compris quand la purge avait été
explicitement refusée. Le refus était donc silencieusement annulé dès
le lancement suivant.

Corrigé : indicateur REALM_PURGE_DECLINED, copie du marqueur
seulement si la purge n'a pas été refusée. Détail complet dans
keycloak/README.md.

Vérifié réellement : simulation en 4 lancements séparés (4 vrais
processus bash) sur le code réel extrait (jamais retapé) -- refus,
re-confirmation que la question revient bien, acceptation, silence
une fois réellement synchronisé. Contre-preuve : l'ancien code
reproduit fidèlement le bug en rejouant la même simulation. Syntaxe
(bash -n). **Non vérifié dans cet environnement** : flux réel complet
avec un vrai Docker/Keycloak, aucun disponible ici.

## 2026-08-31 (suite) — Bug corrigé : détection de changement du realm Keycloak inopérante avec KEYCLOAK_IMPORT_DIR personnalisé (version: 6169b4b5b8b8, livraison #127)

Rapporté par la personne : ./scripts/run.sh up -d --build keycloak
tournait sans jamais afficher le diff/la confirmation de réimport
attendue après #124, laissant Keycloak sur l'ancien realm
(prefs-api-service absent, d'où les 401 en testant le SSO).

Cause réelle : REALM_JSON codé en dur dans scripts/run.sh sur le
chemin par défaut, ignorant KEYCLOAK_IMPORT_DIR personnalisé (.env)
-- render.py écrivait bien au bon endroit, mais [ -f "$REALM_JSON" ]
échouait systématiquement contre le mauvais chemin, faisant sortir
check_keycloak_realm_change() immédiatement et SILENCIEUSEMENT, sans
diff ni confirmation. Même classe de bug déjà rencontrée et corrigée
pour KEYCLOAK_BACKUP_DIR (voir render.py, resolve_dir()).

Corrigé : REALM_JSON dérivé en appelant directement
resolve_import_dir()/parse_env() depuis render.py (jamais une seconde
implémentation de cette résolution en bash), repli sur le défaut
seulement si python3 absent ou KEYCLOAK_IMPORT_DIR invalide. Détail
complet dans keycloak/README.md.

Vérifié réellement : les 3 cas de résolution (absent/personnalisé/
invalide) testés directement en bash, dont une reproduction EXACTE du
cas réel rencontré (KEYCLOAK_IMPORT_DIR=keycloak-secrets). Scénario
de bout en bout confirmant le court-circuit AVANT correctif et sa
résolution APRÈS. Recherché toute autre référence codée en dur au
même chemin ailleurs dans le projet -- aucune trouvée. Syntaxe
(bash -n). **Non vérifié dans cet environnement** : le flux complet
réel avec confirmation interactive et purge (aucun Docker/Keycloak
disponible ici).

## 2026-08-31 (suite) — Hub/Keycloak : adopter un client Keycloak déjà existant (version: 7aaeebad69b6, livraison #126)

Découvert en testant en conditions réelles (Passerelle SMS/
trb140-sms-relay) : l'identifiant du client OIDC est parfois déjà
fixé côté application externe -- le même client que celui provisionné
à la main en #123. Le 409 systématique sur collision (protection
nécessaire contre un doublon accidentel) forçait un contournement
gênant dans ce cas légitime.

POST /external-links/<id>/keycloak accepte désormais adopt: true --
rattache le lien au client Keycloak EXISTANT (UUID + redirectUris
relus DEPUIS Keycloak, jamais réécrits depuis le formulaire) plutôt
que d'en créer un nouveau. Le 409 normal renvoie maintenant
existing_client/existing_redirect_uris pour que l'écran propose
directement l'adoption. Panneau dédié dans ExternalLinksAdminView.
Détail complet dans keycloak/README.md.

Vérifié réellement : app.test_client() -- collision avec les bons
champs renvoyés, adoption réussie (création jamais appelée),
redirect_uri = la vraie valeur Keycloak, adopt sans client à adopter
-> 404 (jamais un repli silencieux), client sans redirectUris (cas
limite) sans exception, non-régression sur le provisionnement normal.
Bug repéré et corrigé pendant la vérification croisée : une variable
CSS inventée (--border-warning, inexistante dans shared/theme.css).

## 2026-08-31 — Bug corrigé : prefs-api/tls-proxy plantaient au démarrage (module Dockerfile manquant) (version: b2fc94582519, livraison #125)

Rapporté par la personne avec les vrais logs de démarrage. Un seul bug,
effet domino : prefs-api en crash-loop (ModuleNotFoundError:
keycloak_admin) rendait son nom injoignable côté Docker DNS, ce qui
faisait échouer tls-proxy entièrement au chargement (ses upstream
nginx sont statiques, résolus une fois au démarrage) -- pas un second
bug côté proxy, juste sa conséquence pour TOUS les fronts qu'il sert.

Cause réelle : prefs-api/keycloak_admin.py (nouveau fichier, #124)
jamais ajouté à la liste COPY explicite du Dockerfile -- fonctionnait
dans cet environnement de développement (fichiers voisins sur disque)
mais jamais testé contre une vraie image Docker construite, faute de
Docker disponible ici. Vérifié : seul fichier .py réellement nouveau
de la session, aucun autre même bug ailleurs. Corrigé : ligne COPY
ajoutée. Détail complet et leçon retenue dans keycloak/README.md.

## 2026-08-28 (suite) — Hub/Keycloak : interface d'intégration Keycloak en direct (compte de service, écran admin) (version: b691e8f0a8fd, livraison #124)

Backlog #2 traité -- avec une approche différente de la piste
initialement esquissée (.env pilotant render.py à chaque redémarrage) :
la personne a demandé un mécanisme TOTALEMENT paramétrable en ligne,
réservé au groupe administrateurs, depuis l'écran "Liens externes" du
hub déjà existant (#121).

Compte de service Keycloak dédié `prefs-api-service` (confidentiel,
serviceAccountsEnabled), droits `manage-clients` UNIQUEMENT -- choix
explicite de la personne face à réutiliser le mot de passe admin
complet comme group_memberships.py. Limite technique découverte et
assumée : manage-clients couvre les CLIENTS OIDC, pas la création de
nouveaux RÔLES REALM (relève de manage-realm, plus large,
volontairement pas donné) -- les rôles applicatifs propres à une appli
externe (type send/full/compose de trb140-sms-relay) restent donc un
ajout manuel.

Nouveau module prefs-api/keycloak_admin.py (stdlib urllib, grant
client_credentials -- pas le grant password du compte admin complet).
Deux routes POST/DELETE /external-links/<id>/keycloak. external_links
gagne keycloak_client_id/keycloak_internal_id/keycloak_redirect_uri.
Côté hub, ExternalLinksAdminView gagne une colonne Keycloak et un
panneau dépliable par lien (formulaire ou affichage des valeurs à
transmettre à l'appli externe). Détail complet dans
keycloak/README.md.

Vérifié réellement : keycloak_admin.py testé en mockant
urllib.request.urlopen (aucun Keycloak réel ici) -- requêtes
construites correctement, extraction UUID, gestion d'erreur (401/404
avalé/500 propagé). Routes Flask testées avec app.test_client() en
mockant keycloak_admin -- provisionnement, doublons (base ET
Keycloak), panne (502), retrait idempotent. Bug trouvé et corrigé en
cours de route : keycloak_redirect_uri pas effacée au retrait dans un
premier jet. Scénario de migration dédié, non-régression explicite sur
tout prefs-api. Syntaxe, JSON/YAML valides, classes CSS toutes
présentes, setters cohérents, accolades équilibrées. **Non vérifié
dans cet environnement** : tout appel RÉEL à l'API Admin Keycloak
(aucun réseau/Keycloak démarré ici), rendu visuel réel (aucun
navigateur).

## 2026-08-28 (suite) — Keycloak : client OIDC + rôles realm pour trb140-sms-relay (projet séparé) (version: a3fa0af001b3, livraison #123)

Demande concrète relayée depuis une autre session travaillant sur le
projet séparé trb140-sms-relay (passerelle SMS Teltonika, déjà doté
de son propre support OIDC côté application) : 3 prérequis côté
Keycloak supervision-si.

Client `trb140-sms-relay` (`realm-template.json`) -- public,
Authorization Code + PKCE, mais redirectUri PRÉCISE
(`.../auth/callback`, demandée telle quelle) plutôt qu'un wildcard
comme nos propres fronts ; pas de mapper audience-apis (appli externe,
n'appelle jamais nos APIs internes). Nouvelle variable
TRB140_SMS_RELAY_URL (`.env`) -- PAS routée par notre tls-proxy,
contrairement aux autres *_PUBLIC_URL, défaut placeholder explicite.
9 rôles realm ajoutés tels quels (vocabulaire exact demandé) :
send/full/compose/history/cron/event/logs/inbox/filters -- aucun
groupe créé pour eux (pas demandé). Détail complet, y compris les
valeurs exactes à transmettre au `./setup.sh` de ce projet-là
(issuer/client-id/redirect-uri) et un point de vigilance sur un bug
Keycloak déjà rencontré ici (rôles hérités d'un groupe pas toujours
fiables) si l'attribution se fait par groupe côté trb140-sms-relay :
voir keycloak/README.md.

Item #2 du backlog mis à jour en conséquence (premier cas concret
traité à la main, la généralisation `.env`-pilotée reste non
commencée). **Corrigé au passage** : l'item #2 du backlog s'était
retrouvé tronqué en fin de phrase lors d'une édition précédente
(livraison #122) -- repéré en le relisant, corrigé ici.

Vérifié réellement : `render.py --check` et rendu complet (écriture
réelle, fichier supprimé ensuite -- jamais livré) -- JSON valide,
nouveau client substitué correctement, 9 rôles présents. Non-
régression confirmée explicitement sur les 4 clients existants et les
7 rôles "maison". Syntaxe (`ast.parse`).

## 2026-08-28 (suite) — Backlog : gestion de tunnels SSH vers des services distants (version: 7fe705c32b30, livraison #122)

Aucun code touché -- mise à jour de documentation seule (BACKLOG.md).
Nouvel item, initiative multi-phases signalée par la personne comme
"à cadrer ensemble avant de coder" : gestion de tunnels SSH (liste/
coupure, admin uniquement, utilisateur spécial pour le sens
"backward") pour joindre sporadiquement des services distants (ex.
mysqld sur de vieilles machines portant des applis métiers
névralgiques, mal supervisées). Phase 1 envisagée : supervision/
alertes/stats. Phase 2 : interfaces de gestion modernisées.

Skill projet également resynchronisé -- rattrapage d'une mise à jour
laissée incomplète lors de la livraison #121 (le backlog synchronisé
dans le skill référençait encore l'état #120).

## 2026-08-28 (suite) — Hub : gestion d'URI externes (liens simples, sans SSO) (version: 68f7005d2d6a, livraison #121)

Backlog #2 traité. Scope volontairement simple (décidé avec la
personne) : liste d'URI ajoutées par les administrateurs, visibilité
par rôle, PAS de pont d'authentification/SSO (la piste SSO pour les
applis compatibles Keycloak reste au backlog, #3).

prefs-api : nouvelle table external_links + CRUD complet
(GET/POST /external-links, PUT/DELETE /external-links/<id>).
allowed_roles vide/absent = visible de tout le monde, mêmes clés de
rôle que hub/src/lib.js. Aucune vérification de rôle côté serveur
(même posture que le reste de cette API) -- le filtrage réel se fait
côté hub. hub/src/lib.js : buildFrontsList gagne externalLinks,
fusionne les liens filtrés par rôle avec les fronts internes
existants (marqués external: true). Nouvel écran d'administration
ExternalLinksAdminView (bouton 🔗, admin uniquement) dans App.jsx --
chargé AVANT les retours anticipés (contrainte des règles de hooks).
Détail complet dans hub/README.md.

Vérifié réellement : app.test_client() -- validation, rôle invalide
filtré silencieusement, mise à jour partielle (autres champs
inchangés), name/url jamais vidés par une valeur blanche, 404,
suppression idempotente, non-régression sur tout prefs-api, scénario
de migration dédié. buildFrontsList testé via Node EN IMPORTANT
DIRECTEMENT le vrai lib.js (ESM natif) -- visibilité par rôle (OR),
entrées malformées, et non-régression confirmée sur tous les fronts
internes existants. Syntaxe (tsc --jsx, ast.parse), classes CSS
toutes présentes, setters cohérents, accolades JS/CSS équilibrées.
**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici -- en particulier le comportement
d'embeddable: true si l'appli visée refuse réellement l'iframe malgré
la case cochée (espace vide silencieux, aucun message d'erreur prévu
pour ce cas).

## 2026-08-28 (suite) — Hub : timeline du hub, étape 3 (composant visuel) — chantier terminé (version: 5118013a91f3, livraison #120)

Dernière étape de la timeline hub (#118 backend, #119 émission).
Choix de conception assumé (non vérifiable visuellement ici) : liste
chronologique GROUPÉE PAR CRÉNEAU plutôt qu'une timeline
proportionnelle façon Gantt -- plus robuste à construire/vérifier
sans navigateur.

hubTimelineLib.js (logique pure, testée séparément) :
granularityWindowSeconds/granularityBucketSeconds (fenêtre 1h à
1 mois, "demi-jour" par défaut) et groupEventsByBucket (regroupe par
créneau puis catégorie, compteur si plusieurs événements du même type
au même endroit -- demandé explicitement). HubTimeline.jsx :
rafraîchie toutes les 60s, sélecteur de granularité. Rendue en colonne
DROITE fixe dans TabShell.jsx (nouveau conteneur .hub-tabshell-body),
4 couleurs par catégorie. Détail complet dans hub/README.md.

Vérifié réellement : hubTimelineLib.js testé via Node -- granularités
connues/inconnues, regroupement simple, LE CAS DU COMPTEUR (plusieurs
événements même type même créneau), tri, événements malformés,
listes vides, bucketSeconds<=0. Syntaxe (tsc --jsx) sur 6 fichiers,
setters cohérents, accolades JS/CSS équilibrées, 4 classes de couleur
par catégorie confirmées correctes malgré construction dynamique par
template literal. Bug trouvé et corrigé pendant la vérification
croisée : .hub-timeline-marker-icon référencée sans règle CSS,
ajoutée (un str_replace maladroit avait aussi écrasé une règle de
couleur au passage, repéré et corrigé immédiatement). **Non vérifié
dans cet environnement** : rendu visuel complet, aucun navigateur
disponible ici -- largeur de colonne, lisibilité, choix "liste
groupée" vs "proportionnelle" à confirmer en conditions réelles.

Chantier timeline du hub considéré terminé pour cette itération (3
étapes annoncées livrées).

## 2026-08-28 (suite) — Hub : timeline du hub, étape 2 (émission des 4 événements) (version: 90bd20540183, livraison #119)

Suite de la timeline hub (#118). Nouveau module partagé
shared/hubEvents.js (postHubEvent, jamais bloquant) -- copié au build
dans hub/ ET tickets/portal/ (les deux Dockerfile modifiés), même
mécanisme que shared/preferences.js.

rappel_sans_reaction : émis SEULEMENT sur la fermeture automatique
(timeout) du rappel, jamais sur Fermer/snooze (actions explicites).
changement_activite : émis seulement si la confirmation change
réellement de ticket par rapport à la session en cours. mouvement_onglet
(TabShell.jsx, gagne login/prefsApiBase) : émis à l'ouverture d'une
app et à la bascule vers un onglet existant, jamais sur l'onglet déjà
actif. ticket_cree (3 points, AdminView.jsx + DemandeurView.jsx x2) :
attribué au véritable acteur (actedBy?.login || me.login si
usurpation d'un demandeur, même raisonnement que acted_by_user_id déjà
existant). Détail complet dans hub/README.md.

Vérifié réellement : syntaxe (tsc --jsx) sur les 5 fichiers React et
le nouveau module partagé, correspondance setters useState sur
chacun (écarts identifiés = faux positifs déjà connus ou triviaux),
accolades JSX équilibrées. Gardes anti-doublon (onglet déjà actif,
même ticket reconfirmé) triviales, revues manuellement. **Non
vérifié dans cet environnement** : comportement de bout en bout
(émission -> stockage -> lecture), aucun service réellement démarré
ici. **Non fait, étape restante** (voir hub/README.md) : le composant
de timeline lui-même.

## 2026-08-28 (suite) — Hub : timeline du hub, étape 1 (backend) — table hub_events dans prefs-api (version: 64a1860dcfbc, livraison #118)

Proposition cadrée avant de coder (même esprit que la coquille à
onglets). Fork posé et tranché : rémanence côté serveur/infra
(réponse de la personne), pas juste "depuis l'ouverture de cet
onglet".

Nouvelle table hub_events dans prefs-api (PAS un nouveau service, PAS
pixel-grid-api malgré un schéma générique déjà très proche -- son
accès API est délibérément lecture seule pour cette table précise,
l'écriture y est réservée au générateur bash/awk ; réutiliser ce
service aurait violé une limite volontaire plutôt que la généraliser).
POST /events (dépose, ts toujours côté serveur) + GET /events
(fenêtre glissante, login/since/until/limit). 4 catégories connues
(rappel_sans_reaction/changement_activite/mouvement_onglet/ticket_cree),
une catégorie hors liste rejetée en 400. Scope personnel par login
(3 des 4 catégories déjà intrinsèquement liées à une session
personnelle) -- décidé sans reposer la question, à confirmer/corriger
si ce n'est pas voulu. Détail complet dans hub/README.md.

Vérifié réellement : app.test_client() -- 4 catégories acceptées,
catégorie inconnue rejetée, ts toujours serveur, filtrage login (sans
fuite), filtrage since/until, login inconnu -> vide, JSON data
reparsé correctement. Non-régression explicite sur /preferences,
/app-settings, /changelog, /backlog, /health. Syntaxe (ast.parse).
**Non fait, étapes restantes** (voir hub/README.md) : émission des 4
événements depuis leurs points d'origine, puis le composant de
timeline lui-même -- le plus visuel, à construire ensuite.

## 2026-08-28 (suite) — Coffre-fort : ajout d'observation depuis l'onglet Observations + backlog reprécisé (version: 513fa9cffbf8, livraison #117)

Backlog traité : ajouter une observation directement depuis l'écran
"📝 Observations" (jusqu'ici possible uniquement depuis un secret
ouvert/révélé). Réutilise addSecretObservation tel quel, clé de
collection déjà disponible sur chaque secret (loadAllDecryptedSecretLabels).
Formulaire dans la ligne dépliée, masqué en lecture seule (nouvelle
prop isReadOnly sur ObservationsScreen). Mise à jour optimiste :
recharge seulement les observations de la ligne concernée, met à jour
le résumé localement (jamais un fetchObservationsSummary complet pour
une seule ligne modifiée).

Backlog aussi reprécisé (discussion avant construction, item non
traité ici) : l'item "gestion d'URI externes" du hub volontairement
recadré en scope simple -- liste d'URI gérée par les admins avec
visibilité par utilisateur/rôle, SANS pont d'authentification/SSO
(jugé prématuré par la personne -- développements internes très
anciens à session PHP/FatFree, une passerelle d'authentification
unique envisagée mais remise à plus tard).

Vérifié réellement : syntaxe (tsc --jsx), classe CSS présente,
correspondance setters useState (aucun faux positif), accolades JSX
équilibrées. Logique de mise à jour locale du résumé testée via Node
-- première observation d'un secret qui n'en avait aucune, secret qui
en avait déjà, et non-régression explicite sur les AUTRES secrets du
tableau (jamais écrasés par erreur). **Non vérifié dans cet
environnement** : rendu visuel réel, aucun navigateur disponible ici.

## 2026-08-28 (suite) — Backlog : gestion d'APIs/URI externes dans le hub (version: 555c70a25383, livraison #116)

Aucun code touché -- mise à jour de documentation seule (BACKLOG.md).
Nouvel item ajouté : permettre aux administrateurs d'ajouter des
API/URI externes comme nouvelles entrées du hub (en plus des
applications internes actuelles), avec attribution des droits d'accès
aux autres utilisateurs par les administrateurs.

## 2026-08-28 (suite) — Tickets : attribution par technicien, Gantt et timeline pour le technicien (version: 7045faa55e84, livraison #115)

Suite du bug tickets/rappels (#114). Découverte en creusant la
timeline : ticket_time_entries n'était jamais rattaché à un
technicien précis (aucune colonne d'attribution nulle part). Question
ciblée posée avant de construire (timeline de toute la file sans
toucher au schéma, ou ajouter l'attribution d'abord) -- réponse :
ajouter l'attribution.

ticket_time_entries.technician_login (nullable) ajouté aux 3 endroits
définissant ce schéma (SQLITE_SCHEMA embarqué + les deux fichiers
data-generator, gardés synchronisés) + migration douce (même patron
que ensure_weight_column, dual-backend via get_connection). POST
/tickets/<id>/time_entries accepte technician_login (optionnel,
rétrocompatible). Nouvelle route GET /time_entries?technician_login=.
Trois points de création de segment identifiés : rappel d'activité et
saisie manuelle désormais attribués ; /calendar/assign délibérément
PAS touché (connecteur OAuth/ICS mono-opérateur, attribuer
proprement demanderait de le revoir en profondeur -- documenté comme
gap assumé, pas silencieux).

Gantt technicien : réutilise TEL QUEL /tickets/parallel et les
fonctions pures de l'écran politique, scopé aux tickets actuellement
filtrés dans la file du technicien (ticket_ids=...). Timeline
technicien : nouveau panneau, liste chronologique plate des propres
segments du technicien (distinct du Gantt, ticket-centrique). Détail
complet dans tickets/README.md.

Vérifié réellement : app.test_client() -- création avec/sans
attribution, filtrage par technicien (y compris sans aucun segment),
non-régression explicite sur /calendar/assign (jamais touché,
segments restent bien non attribués), scénario de migration dédié
(colonne retirée puis migration rejouée sur une base réaliste,
segment pré-existant jamais perdu). Syntaxe (tsc --jsx sur 4
fichiers, ast.parse sur app.py), classes CSS toutes présentes,
setters cohérents, accolades JSX/CSS équilibrées. **Non vérifié dans
cet environnement** : rendu visuel réel, aucun navigateur disponible
ici -- particulièrement le Gantt technicien (réutilisation dans un
nouveau contexte) et la timeline (nouveau panneau).

## 2026-08-28 (suite) — Hub : bug corrigé, un ticket confirmé depuis le rappel n'apparaissait jamais "en cours" (version: 24e4426c314d, livraison #114)

Constaté sur la version #105. Diagnostic : deux mécanismes distincts
en jeu. La "clôture différée" (settingsClient.js) est un comportement
VOULU (pas un bug) -- chaque confirmation clôt la période du ticket
PRÉCÉDENT, jamais celui qu'on vient de choisir (tickets-api n'a pas de
notion de segment ouvert). Le vrai bug : confirmer un ticket ne
touchait jamais son statut, or "en cours" (first_in_progress_ts,
panneau technicien) ne se déclenche que sur un changement de statut
vers un type "en_cours". Question ciblée posée avant de construire
(bascule automatique ou juste indicatif ?) -- réponse : bascule
automatique.

pickAutoInProgressStatutId (pure, settingsClient.js) : ne bascule
jamais si déjà sur un statut en_cours (peuvent être plusieurs, jamais
écrasé), premier par id si plusieurs candidats, null si aucun
configuré. handleConfirm (ReminderWidget.jsx) réutilise TEL QUEL PUT
/tickets/<id> (même route que l'écran technicien) -- aucune logique
dupliquée, aucun nouvel endpoint backend nécessaire (GET /statuts
retournait déjà `type`). Note ajoutée dans le popup pour rendre la
clôture différée visible plutôt que silencieuse. Détail complet dans
hub/README.md.

Vérifié réellement : logique pure testée via Node (statut déjà bon,
plusieurs en_cours configurés, aucun configuré, cas limites
string/number). Syntaxe (tsc --jsx), setters cohérents, accolades
équilibrées, classe CSS présente. **Non vérifié dans cet
environnement** : comportement réel -- en particulier si le Gantt
politique affiche bien le segment du 1er ticket (aucun changement de
code nécessaire de ce côté, /tickets/parallel étant déjà basé sur le
temps saisi et non le statut, mais à confirmer en conditions
réelles). Backlog : Gantt et timeline pour le technicien restent à
faire (item séparé), le bug lui-même est retiré de la file.

## 2026-08-28 (suite) — Tickets : mise en page adaptative, la colonne "Demandeurs" oubliée du premier passage (version: 18d241d1fec7, livraison #113)

Ce chantier avait déjà été largement livré lors d'une session
précédente (QueueTable, colonne priorités masquée, correctif
DemandeurView -- voir tickets/README.md) mais restait marqué non
traité dans le backlog : la colonne LATÉRALE de la vue Technicien
affichait encore "👥 Demandeurs" en PERMANENCE (300px fixes) même
sans ticket sélectionné, oubliée dans ce premier passage -- la file
ne prenait donc jamais VRAIMENT toute la largeur.

Corrigé : quand rien n'est sélectionné, une seule colonne pleine
largeur regroupe la file (QueueTable, inchangé) et l'accès aux
Demandeurs, replié par défaut dans un panneau "+" (même motif que
partout ailleurs dans le projet) plutôt qu'une colonne dédiée
mangeant de la place même sans jamais s'en servir. Disposition à 3
colonnes inchangée dès qu'un ticket est sélectionné. Détail complet
en complément de l'entrée existante dans tickets/README.md.

Vérifié : syntaxe (tsc --jsx), classes CSS toutes présentes, setters
useState cohérents, accolades JSX équilibrées, media query
responsive existante compatible sans modification. **Non vérifié
dans cet environnement** : rendu visuel réel, aucun navigateur
disponible ici.

## 2026-08-28 (suite) — Hub : mémorisation des onglets ouverts (version: 0bde2cdde0e2, livraison #112)

Backlog #1 ("mémorisation des onglets ouverts... pour les retrouver à
la réouverture"). Interprété comme un état de SESSION sur cet
appareil (localStorage, même principe que le thème), pas un réglage
de compte à synchroniser entre appareils (prefs-api) -- choix assumé
plutôt que tranché avec la personne (fork jugé mineur), documenté
dans hub/README.md pour qu'elle puisse le corriger si besoin.

tabs.js gagne serializeOpenTabs/restoreOpenTabs (pure) --
applications manquantes depuis (retirées/permission perdue) omises
proprement, index actif recalé automatiquement. TabShell.jsx charge
l'état UNE SEULE FOIS au montage via une ref mémoïsée -- piège réel
évité en construisant ceci : deux useState séparés appelant chacun la
fonction de restauration auraient généré des id DIFFÉRENTS
(createTab), l'onglet "actif" restauré n'aurait alors correspondu à
AUCUN onglet réel. Sauvegarde à chaque changement, jamais bloquant.

Vérifié réellement : logique pure testée via Node -- aller-retour
complet, application manquante avec recalage d'index, onglet actif
manquant, formes corrompues, ET deux onglets sur la même application
(restaurés séparément, id distincts, le bon reste actif). Syntaxe
(tsc --jsx), setters vérifiés, accolades équilibrées. **Non vérifié
dans cet environnement** : comportement réel à travers un vrai cycle
de montage React et un vrai localStorage, aucun navigateur disponible
ici.

## 2026-08-28 (suite) — Hub : protocole postMessage coquille <-> application embarquée (version: e2015ed951f0, livraison #111)

Backlog #1. beforeunload (déjà construit) ne couvre que fermer/
recharger TOUT le navigateur -- fermer un ONGLET précis dans la
coquille (juste un retrait DOM/masquage CSS de l'iframe) ne le
déclenche jamais. shared/useUnsavedChangesWarning.js envoie désormais
aussi un postMessage au hub parent à chaque changement d'état
(targetOrigin explicite, jamais "*"). TabShell.jsx écoute, vérifie
event.origin, valide la forme du message, puis retrouve QUEL onglet a
envoyé le message par comparaison de référence sur .contentWindow
(jamais par URL/titre -- distingue 2 onglets ouverts sur la MÊME
application). Fermeture d'un onglet avec modification non
enregistrée -> window.confirm avant de fermer réellement ; point
indicateur direct sur l'onglet concerné. Dégradation propre : seule
dba/portal appelle ce hook actuellement, toute autre application se
comporte exactement comme avant (câbler d'autres modules reste un
chantier séparé). Détail complet dans hub/README.md.

Vérifié réellement : logique pure testée via Node
(isValidUnsavedChangesMessage -- formes invalides ; findTabIdForWindow
-- fenêtre inconnue, ET le cas de deux onglets sur la même
application, correctement distingués). Syntaxe (tsc --jsx) sur les 3
fichiers touchés, classe CSS vérifiée présente, accolades CSS
équilibrées. **Non vérifié dans cet environnement** : comportement
réel du postMessage entre une vraie iframe et son parent, aucun
navigateur disponible ici -- mérite particulièrement un test en
conditions réelles (modifier une cellule DBA, tenter de fermer cet
onglet précis).

## 2026-08-28 (suite) — Coffre-fort : format (modèle) associé à une collection (version: 0c1afefc4a3c, livraison #110)

Backlog #1, "le plus gros morceau". Question ciblée posée avant de
construire (obligatoire bloquant ou indicatif ?) -- réponse :
indicatif seulement, jamais bloquant. A considérablement simplifié le
design (aucune validation serveur à l'enregistrement d'un secret,
juste ordre d'affichage + marqueur visuel).

secret_templates gagne collection_id (nullable, NULL = global,
inchangé) et required_labels via migration douce. GET /templates
accepte ?collection_id= (global + collection ciblée, jamais les
modèles d'une autre). Nouvelles fonctions pures
(defaultRequiredLabels, orderFieldsRequiredFirst) dans
vaultFieldsLib.js. FieldsEditor.jsx : case "obligatoire" par champ +
choix de portée au moment d'enregistrer un modèle, marqueur "*"
indicatif sinon. Câblé dans les DEUX endroits où un secret peut être
créé (écran Collections et le formulaire de la Recherche, livraison
#106) -- modèles proposés toujours scopés à la collection concernée,
jamais de fuite entre collections. Détail complet dans vault/README.md.

Vérifié réellement : app.test_client() (base isolée) -- création
globale/scopée, filtrage silencieux d'un required_labels incohérent,
isolation stricte entre collections, ET un scénario dédié de
migration sur une base simulant l'ancien schéma (modèle existant
jamais perdu, nouveau modèle scopé créable immédiatement après).
Logique pure testée via Node (casse, tri stable, cas vides). Syntaxe
(tsc --jsx) sur les 5 fichiers touchés, classes CSS toutes présentes,
setters useState vérifiés. **Non vérifié dans cet environnement** :
rendu visuel réel, aucun navigateur disponible ici. **Non fait,
assumé** : l'onglet "📋 Modèles" (parcours cross-collection, écran
Recherche) n'affiche pas encore la portée d'un modèle -- omission
mineure pour contenir la portée de ce chantier.

## 2026-08-28 (suite) — Supervision SI : en-tête recouvert par les contrôles fixes du menu (version: 31de356a648a, livraison #109)

Signalé par capture d'écran (titre "SUPERVISION SI — VUE CENTRALISÉE"
tronqué en "...ENTRALISÉE", lettres isolées visibles dans les
interstices). Cause : .top-nav-fixed-controls (🏠 Hub / ⚙️ Paramètres
/ 🌙, position: fixed, top-gauche, z-index: 1001) recouvre .app-header
(en flux normal, même coin haut-gauche) -- ce dernier n'avait jamais
reçu le même traitement que .top-nav (padding-left: 300px, déjà en
place suite à un bug similaire). Corrigé en reprenant la même marge
sur .app-header. Mécanisme propre au module frontend seul (vérifié :
absent des autres modules), pas d'audit transversal nécessaire.
frontend/README.md créé (absent jusqu'ici malgré l'ancienneté du
module) pour journaliser ce correctif et les suivants.

Vérifié : équilibre des accolades CSS, seule occurrence JSX de la
classe confirmée, recouvrement recalculé au pixel près (correspond
précisément au symptôme). **Non vérifié dans cet environnement** :
rendu visuel réel, aucun navigateur disponible ici.

## 2026-08-28 (suite) — Backlog : détail du bug tickets/rappels remonté sur la version #105 (version: a518506d766f, livraison #108)

Aucun code touché -- mise à jour de documentation seule (BACKLOG.md),
republiée pour éviter que le BACKLOG.md du dépôt ne redevienne
désynchronisé de ce qui a été acté en conversation (leçon de la
livraison #106 : le BACKLOG.md livré en #105 était resté vide malgré
la file déjà actée). L'item #6, jusqu'ici noté de façon vague ("tests
et évolution sur la version #105"), remplacé par le détail concret
donné par la personne : bug signalé (deux tickets acquittés depuis
des rappels successifs n'apparaissent "en cours" ni dans l'écran
technicien ni dans l'écran politique/Gantt) + deux évolutions liées
(Gantt et timeline pour le technicien, jusqu'ici réservés/absents de
cet écran). Pas encore d'investigation du bug lui-même -- prochain
item FIFO.

## 2026-08-28 (suite) — Coffre-fort : présentation "révéler"/"historique"/"versions" en tableau (version: f110c2a195cb, livraison #107)

Backlog #2 (initialement #1 avant réorganisation #106). Question
ciblée posée avant de construire (les deux écrans concernés,
Historique 🕒 et Versions ⏱️, ont des garanties différentes -- voir
vault/README.md) : réponse "les deux écrans". Décision prise : les
TROIS présentations (révéler/FieldsDisplay, Versions, Historique)
sont maintenant de vrais `<table>`, mais le contenu n'a PAS été ajouté
à Historique -- Versions couvre déjà exactement ce besoin
(label/contenu/date, restaurable), le dupliquer aurait recréé un
mécanisme parallèle tout en touchant un choix de sécurité documenté
(secret_history jamais décrypté/stocké en clair côté serveur, portée
délibérément limitée pour le tableau de bord cross-collection du
maître_système). Détail complet et alternative possible (fusion
assumée) documentés dans vault/README.md.

FieldsDisplay devient un tableau Libellé/Contenu (cas "simple" un
seul champ sans libellé inchangé).
Versions : une ligne par CHAMP (secret multi-champs = plusieurs
lignes par version), métadonnées (auteur/date/motif/bouton restaurer)
affichées sur la première ligne du groupe seulement. **Bug réel
corrigé au passage** : le contenu d'une version n'était jamais
reparsé via parseFields avant affichage -- un secret multi-champs
affichait du JSON brut sérialisé dans l'ancienne présentation,
jamais remarqué faute d'avoir eu un cas réel. Historique : tableau
Action/Auteur/Date/Motif, aucune colonne "Contenu" inventée.

Vérifié : syntaxe (tsc --jsx), toutes les classes CSS utilisées
présentes une par une, aucune classe orpheline laissée par l'ancienne
présentation (grep vérifié), logique pure (parseFields/serializeFields/
isSimpleSingleField) testée réellement via Node avec des cas réels
(ancien format simple chaîne, nouveau format multi-champs round-trip,
un champ avec libellé explicite, chaîne vide/undefined, JSON valide
mais de forme inattendue -- jamais d'exception). **Non vérifié dans
cet environnement** : rendu visuel réel, aucun navigateur disponible
ici -- la disposition du tableau "révéler" dans la ligne flex du
secret (écran Collections) mérite particulièrement une confirmation.

## 2026-08-28 (suite) — Coffre-fort : ajout de collection/secret depuis la Recherche (version: 0ab77f4a2e6b, livraison #106)

Backlog #1. Jusqu'ici, créer une collection ou un secret n'était
possible que depuis l'écran Collections, en naviguant jusqu'à la
bonne collection -- pas pratique en train de chercher depuis l'écran
Recherche. Deux formulaires repliés ("+" 📁/🔑) ajoutés dans l'en-tête
de la colonne centrale de VaultSearchScreen, réutilisant entièrement
createCollection/createSecret/unlockCollectionKey (vaultOps.js,
inchangés) -- aucune logique parallèle. FieldsEditor, jusqu'ici
défini localement dans App.jsx sans être exporté, extrait dans son
propre fichier FieldsEditor.jsx pour permettre cette réutilisation
sans import circulaire. Liste des collections cibles rechargée à
chaque ouverture du formulaire secret (inclut celles encore vides,
absentes de allSecrets) ; clé de collection déverrouillée seulement à
la sélection, jamais toutes d'un coup. Détail complet dans
vault/README.md.

Vérifié : syntaxe (tsc --jsx), classes CSS toutes présentes,
correspondance setters useState déclarés/appelés. **Non vérifié dans
cet environnement** : aucun test automatisé exécuté (pas de
node_modules ni d'accès réseau pour npm install ici) ni rendu visuel
réel -- à confirmer en conditions réelles avant de considérer ce
chantier acquis. Backlog synchronisé avec le dépôt (resté vide dans
la précédente livraison malgré la file déjà actée) et complété de 3
nouvelles demandes (tests/évolution v#105, ajout d'observation
depuis l'onglet Observations, timeline verticale de gestion du temps
en mode onglets) -- voir BACKLOG.md.

## 2026-08-28 (suite) — Numéro de livraison incrémental (version: 0994810b58b3, livraison #105)

Demandé explicitement : un hash ne permet pas de voir d'un coup d'œil
"est-ce plus récent que ce que j'ai testé avant ?" -- confusion
réelle rencontrée ("version -1" testée sans certitude). Nouveau
shared/DELIVERY_NUMBER -- simple fichier texte committé, jamais
recalculé automatiquement (contrairement au hash), incrémenté
manuellement à chaque livraison. Numérotation démarrée à 105 (104
entrées déjà dans ce changelog à ce moment-là), pour rester dans la
continuité plutôt que repartir de 1. run.sh le lit et l'inclut dans
VERSION.json (delivery_number). Badge mis à jour sur les 6 fronts :
#105 comme texte principal, hash de contenu toujours disponible en
info-bulle. Non-régression complète.

## 2026-08-28 (suite) — Supervision SI : menu masquable toujours derrière les contrôles fixes (version: ac5c43a3fa5e)

Signalé une deuxième fois -- le premier correctif ne réglait que le
chevauchement entre 🏠/⚙️/🌙 eux-mêmes, jamais leur chevauchement avec
le menu de navigation (nav.top-nav). Menu démarrant à top:0 avec
seulement 1rem de marge -- même bande verticale que les contrôles
fixes. Corrigé : padding-left: 300px sur le menu, overflow-x: auto +
flex-shrink:0/white-space:nowrap sur les boutons en filet de
sécurité. Équilibre CSS et syntaxe vérifiés.

## 2026-08-28 (suite) — Vault : espace toujours perdu malgré l'élargissement précédent (version: 6e9427bbf7bc)

.vault-main-wide restait plafonné à 1400px fixe, redevenu trop
étroit sur un grand moniteur. Corrigé : max-width: 97vw (relatif à
la fenêtre) -- s'aligne vraiment sur le bord de l'écran.

## 2026-08-28 (suite) — LDAP : JSON complet et navigable (version: 4a6a122de817)

Le mode "{ } JSON" ne montrait que le nœud sélectionné dans la
navigation en colonnes, jamais l'arbre entier. JsonTreeNode (nouveau
composant récursif) -- affiche tout l'arbre LDIF depuis la/les
racine(s), +/- par nœud pour développer/réduire. État d'expansion
levé au niveau du parent (Set partagé) -- "Tout déplier"/"Tout
replier" manipulent directement cet ensemble. Racines pré-dépliées
au chargement. Non-régression complète sur tout le module LDAP.

## 2026-08-28 (suite) — DBA : boutons d'édition invisibles sur table large (version: a27df7dfcc13)

Signalé après test : boutons valider/annuler/✏️/🗑️ nécessitaient un
défilement horizontal sur une table à beaucoup de colonnes. Corrigé :
.dba-row-actions/.dba-row-actions-col en position: sticky right: 0
(cellule ET en-tête), background: inherit (reprend la couleur de la
ligne selon son état). .dba-main élargi (1200px -> 1600px). Syntaxe
et CSS vérifiés, non-régression complète.

## 2026-08-28 (suite) — DBA : modification de schéma, ALTER TABLE (version: 76be9ade3c3f)

add_column/drop_column/rename_column/modify_column ajoutés aux trois
connecteurs. SQLite 3.45.1 vérifié -- DROP/RENAME COLUMN natifs, mais
MODIFY COLUMN (type/nullabilité) hors de portée (pas d'ALTER COLUMN
SQLite) -- NotImplementedError explicite (501) plutôt qu'une
reconstruction de table risquée. MySQL combine type+nullabilité en
une clause, Postgres les sépare en deux instructions -- vérifié
précisément pour chaque moteur. Trois routes POST/DELETE/PUT
.../columns, clé primaire jamais accessible. Interface : formulaire
d'ajout inline, actions ✏️/🗑️ par colonne. 41 tests. Non-régression
complète. Reste dans la liste : JSON LDAP complet, 4 points vault.

## 2026-08-28 (suite) — Trois bugs réels sur la coquille à onglets (version: 24961d0a9362)

Signalés en testant la coquille. (1) Page Paramètres pas vraiment
élargie : .hub-settings-section combine .hub-card (max-width 420px
jamais écrasé) -- max-width: none ajouté. (2) Le "+" ne faisait
visiblement rien : le menu se rendait mais overflow-x: auto sur
.hub-tabbar recadrait implicitement le débordement vertical -- menu
déplacé hors de ce conteneur, positionné sur .hub-tabshell. (3) Dans
Supervision SI elle-même, "🏠 Hub" et "⚙️ Paramètres" partageaient
EXACTEMENT la même classe/position fixe, littéralement superposés,
débordant sur le thème et le libellé -- regroupés dans un conteneur
flexible commun, espacement naturel. Syntaxe et CSS vérifiés,
non-régression complète.

## 2026-08-28 (suite) — DBA : ajout/suppression/sélection multiple/duplication de lignes (version: 2f127515863c)

Liste d'évolutions "mineures" notée par la personne, priorisée avec
son accord. insert_row/delete_rows ajoutés aux trois connecteurs
(RETURNING pour Postgres, pas de lastrowid natif). Routes POST/DELETE
.../rows. Duplication sans route séparée -- réutilise l'ajout normal
avec les valeurs de la ligne source, sans sa clé primaire. Interface :
cases à cocher + tout sélectionner, barre d'outils Dupliquer/Supprimer
avec confirmation, formulaire d'ajout inline. isBusy généralisé
(édition OU ajout), alerte de fermeture étendue aux deux cas. 35
tests. Non-régression complète. Reste dans la liste : ALTER TABLE,
JSON LDAP complet, 4 points vault.

## 2026-08-28 (suite) — Hub : coquille à onglets, étape 1 (version: cee952e7ac92)

Première étape de la proposition d'évolution, cadrée et découpée
avec la personne avant de coder. hub/src/tabs.js (pur, testé) --
createTab/openTab/closeTab, plusieurs onglets sur la même application
possibles, convention de fermeture façon navigateur (l'onglet qui
glisse à la place du fermé devient actif). TabShell.jsx -- iframes
TOUJOURS montées (jamais démontées au changement d'onglet), même
origine pour toutes les applications donc aucun souci cross-origin,
vérifié qu'aucun en-tête X-Frame-Options/CSP ne bloque l'intégration.
embeddable ajouté à chaque front (lib.js) -- Keycloak et
l'administration du coffre-fort restent des liens classiques (X-Frame
natif / origine différente). Nouveau bouton 🗂️, lien profond
?view=tabs. 27 tests. Non-régression complète. Prochaines étapes
(protocole postMessage, mémorisation des onglets) pas commencées.

## 2026-08-28 (suite) — Alerte de fermeture d'onglet (version: d80e1860b1f4)

Premier morceau, isolé et volontairement scopé, d'une proposition
plus large (coquille à onglets pour tout le hub, historique
versionné, rémanence complète) -- discuté ouvertement : les autres
points impliquent une refonte architecturale majeure (chaque
application est aujourd'hui un site indépendant), mis de côté pour
l'instant. shared/useUnsavedChangesWarning.js (nouveau, copié comme
theme.css/preferences.js) -- hook générique sur beforeunload, câblé
dans DBA (BrowseTab, réutilise l'état d'édition déjà existant). 6
tests sur la logique du gestionnaire. Non-régression complète. Prêt
à être réutilisé par les autres applications.

## 2026-08-28 (suite) — DBA : édition de cellule avec validation par ligne (version: 87156942a8db)

Demandé explicitement. update_row() ajouté aux trois connecteurs
(SQLite, MySQL, Postgres) -- requêtes toujours paramétrées pour les
valeurs. Nouvelle route PUT /connections/<id>/tables/<table>/rows --
colonnes validées contre le vrai schéma, clé primaire jamais
modifiable. Interface : cliquer une cellule passe toute la ligne en
édition, boutons Valider/Annuler, navigation bloquée (pagination et
sélecteurs désactivés) tant que le choix n'est pas fait. 50 tests sur
ce chantier, dont injection SQL vérifiée sur une vraie base SQLite.
Non-régression complète.

## 2026-08-28 (suite) — LDAP : racine manquante, attributs des feuilles inaccessibles (version: 52c694caec42)

Signalé par deux captures d'écran. LDAP_ADMIN_BASE_DN repliait
silencieusement sur LDAP_USERS_DN (Keycloak, une seule OU) --
masquait tout ce qui est en dehors sans message d'erreur. Repli
retiré, réglage désormais explicite requis. buildColumns
(ldapTree.js) produit une colonne même pour une feuille sans
enfants (ex. cn=Parapheur avec member) -- permet d'y afficher ses
attributs. EntryDetailPanel intégré en tête de chaque colonne (mode
compact) plutôt qu'un panneau séparé en bas -- demandé explicitement.
Sélectionner un utilisateur dans la liste finale affiche aussi son
détail (colonne séparée). 9 tests supplémentaires. Non-régression
complète.

## 2026-08-28 — Vault : page "Observations" (version: 0f798737679b)

Dernier point du backlog, clarifié puis livré (redesign convenu avec
la personne plutôt que de deviner sur une formulation ambiguë).
Nouvelle route POST /secrets/observations-summary -- résumé agrégé
(nombre + date la plus récente) par lot d'identifiants, jamais de
texte déchiffré. Trois fonctions pures (vaultSearchLib.js) : fusion,
filtre (tous/avec/sans), tri (récence/nombre/alpha). Nouvel écran
ObservationsScreen.jsx, onglet "📝 Observations" -- tableau unique
filtrable/triable, détail dépliable par ligne, déchiffrement différé
au dépli uniquement. 39 tests sur ce chantier. Bug corrigé en cours
de route : fragment <> sans key dans .map() (interdit par React),
remplacé par <Fragment key={...}>. Non-régression complète. Backlog
désormais vide.

## 2026-08-27 (suite) — Vault : "Top 10" remplacé par une liste complète triée par usage (version: ef01615fcd7c)

Demandé explicitement. topUsedSecrets(secrets, n=10) renommée
usedSecretsByFrequency(secrets, n) -- n optionnel, absent = tous les
codes utilisés sans plafond. Dashboard garde un résumé limité à 10
(cohérent), l'écran de recherche reçoit la liste complète. Widget
"Top 10" devient "Utilisation des codes" -- vrai tableau, défilable
horizontalement, colonnes Collection/Localisation/Dernier accès
optionnelles via cases à cocher. Colonne droite élargie (260px ->
380px). Préférence de colonnes en localStorage (jamais prefs-api,
préférence purement cosmétique). 9 tests supplémentaires, test
existant mis à jour pour le renommage. Non-régression complète.

## 2026-08-27 (suite) — Vault : modale trop étroite, débordement CSS, collections élargies (version: 7c8796009e84)

Signalé par captures d'écran. Modale de révélation plafonnée à 420px
(.vault-card, pensée pour un écran de connexion) -- élargie
explicitement (min(92vw, 1100px)). Débordement corrigé : jeton long
sans espace (hash Docker) ne pouvait jamais se couper -- overflow-wrap:
break-word ajouté. Vue Collections élargie (vault-main-wide, jusque-là
réservée à search/dashboard) -- l'ajout d'observations y était déjà
fonctionnel, seule la largeur manquait. Non-régression confirmée
(vaultCrypto.js temporairement copié depuis shared/ pour le test,
absent par défaut de ce bac à sable).

## 2026-08-27 (suite) — LDAP : édition d'attributs à tous les niveaux (version: a09081995671)

Signalé par capture d'écran (comparaison phpLDAPadmin) : impossible
d'accéder au contenu du dernier élément sélectionné -- une feuille
sans uid (groupe cn=Parapheur, attributs description/member) n'apparaissait
nulle part. ldap_client.build_modify_ldif(dn, attr_changes) -- pure,
remplace entièrement les valeurs par attribut, delete: si liste vide,
séparateur - entre attributs (RFC 2849). Nouvelle route PUT
/entries/<dn> -- sauvegarde avant écriture, attributs sensibles
refusés explicitement (toujours passer par la réinitialisation de mot
de passe dédiée). Nouveau panneau "📋 Détail de la sélection", toujours
visible, montre et permet d'éditer TOUTE entrée sélectionnée, valeurs
multiples ajoutables/retirables individuellement. 24 tests
supplémentaires (170 au total sur le chantier LDAP). Non-régression
complète.

## 2026-08-27 (suite) — Hub : mise en page trop étroite, deux styles incohérents (version: 24102795cd4a)

Signalé par capture d'écran : colonne étroite (~1/5 de l'écran) avec
cadres surchargés, à côté d'une barre pleine largeur -- "Historique"
en était l'exemple le plus caricatural. Cause : .hub-settings limité
à 640px, pensé pour des champs de formulaire courts, réutilisé tel
quel pour du contenu de prose. Corrigé : conteneur élargi à 1400px,
nouvelle classe .hub-settings-grid (grille CSS auto-fit) -- les
sections s'organisent en lignes selon la largeur disponible plutôt
qu'empilées dans une colonne fixe, demandé explicitement. Largeur du
texte markdown 780px -> 900px. Vérifié : syntaxe, équilibre des
balises div, classes CSS, non-régression complète. Non vérifié :
rendu visuel réel, aucun navigateur disponible ici.

## 2026-08-27 (suite) — DBA : "SSL is required" persistait sur l'import mysqldump (version: d4463eaf59cd)

Signalé par la personne : erreur SSL toujours présente après le
premier correctif (ssl_disabled=True côté PyMySQL). Cause : l'import
mysqldump utilise un chemin de code entièrement séparé (client mysql
en ligne de commande, jamais PyMySQL) que le premier correctif ne
couvrait pas. Corrigé : --ssl-mode=DISABLED ajouté à la commande
mysql construite. Nouveau test explicite sur le contenu exact de la
commande (19 tests au total sur cette route). Non-régression complète.

## 2026-08-27 (suite) — DBA : modification d'une connexion (version: 0669eca42b09)

Backend (PUT /connections/<id>) déjà générique et complet depuis le
départ -- seule l'interface manquait. Mot de passe jamais renvoyé par
l'API (has_password booléen seulement) -- formulaire d'édition ne le
préremplit jamais, champ vide = conservation, vérifié explicitement
qu'un changement de libellé seul ne touche jamais au mot de passe
existant. Formulaire replié sous chaque connexion, champs adaptés au
moteur. 8 tests sur la route backend (jamais testée jusqu'ici).
Classes CSS déjà toutes couvertes. Non-régression complète.

## 2026-08-27 (suite) — Navigateur LDAP en colonnes façon phpLDAPadmin/Finder (version: 5ce6615b9968)

Demandé après aperçu de la vraie structure d'annuaire (captures
phpLDAPadmin). Nouvelle route GET /entries -- toute l'arborescence
(pas seulement uid), attributs sensibles systématiquement exclus.
ldapTree.js (pur, testé sans backend) -- construction d'arbre depuis
les DN à plat, usersUnder() descend récursivement et distingue
groupes/utilisateurs. LdapBrowser remplace UsersTab : navigation en
colonnes en cascade, dernière colonne = utilisateurs filtrés par la
sélection, bascule Arbre/JSON, réinitialisation de mot de passe
conservée à l'identique. Bug réel trouvé et corrigé avant livraison :
res.error au lieu de res.data.error. 36 tests supplémentaires, testés
contre une structure représentative de la vraie capture d'écran.
Classes CSS vérifiées une par une, y compris celles en littéral de
gabarit. Non-régression complète. Non vérifié : rendu visuel réel.

## 2026-08-27 (suite) — Vue "Historique du projet" dans le hub (version: e821fd160225)

Chantier suivant de la file. CHANGELOG.md/BACKLOG.md servis EN DIRECT
par prefs-api (nouvelles routes GET /changelog, GET /backlog) --
volumes montés en lecture seule depuis la racine du dépôt, jamais une
copie figée au build : toujours le contenu réel du moment. Rendu
markdown maison (hub/src/markdown.js, pas de bibliothèque externe) --
titres/gras/code/listes, testé contre les deux vrais fichiers complets
du dépôt (82 Ko pour CHANGELOG.md) sans exception. Nouveau bouton
"📜" dans le hub à côté de "⚙️ Paramètres", deux sous-onglets
(Historique/Backlog), lien profond ?view=history. 34 tests réels,
non-régression complète sur le hub et prefs-api. Front OpenLDAP
retiré du backlog (chantier terminé).

## 2026-08-27 (suite) — Front OpenLDAP : interface + mot de passe jamais stocké (version: 78d10f3f63cd)

Chantier #4 terminé. Modification de sécurité demandée en cours de
route : LDAP_ADMIN_BIND_PASSWORD retiré entièrement (.env.example,
docker-compose.yml) -- remplacé par en-tête X-LDAP-Bind-Password
exigé à chaque requête, jamais mémorisé côté serveur (vérifié :
requête sans en-tête refusée même juste après un accès réussi).
Nouveau ldap-admin/portal/ (React) : écran de déverrouillage (mot de
passe en état React uniquement, jamais localStorage, re-verrouillage
au reload ou sur toute 401), onglet Utilisateurs (liste + reset avec
confirmation par saisie du uid), onglet Sauvegardes (liste, création,
téléchargement LDIF brut, diff façon git). Vigilance renforcée post-
incident : vérification fichier par fichier des Dockerfile, toutes
les classes CSS vérifiées présentes par script automatisé. Câblage
complet : service docker-compose, routage tls-proxy, carte Hub (admin
uniquement). 23 tests supplémentaires -- 110 au total sur ce chantier.
Non vérifié : rendu visuel réel et toute connexion LDAP réelle (aucun
serveur/binaires disponibles ici).

## 2026-08-27 (suite) — Front OpenLDAP : backend complet (version: 6418c3cdf89b)

Chantier #4. Nouveau module ldap-admin/ -- aucune bibliothèque LDAP
Python (aucune installable/testable ici), sous-processus vers les
vrais binaires ldapsearch/ldapmodify à la place, même motif que
pg_dump/psql dans backup_manager.py. ldif_tools.py (parsing/diff LDIF
RFC 2849, pur Python, 24 tests). ldap_client.py (construction des
commandes, hachage SSHA pur Python, mot de passe jamais en ligne de
commande -- fichier temporaire 600 toujours supprimé, 33 tests).
ldap_backup.py (sauvegardes LDIF horodatées, rétention, 9 tests).
app.py (routes Flask complètes -- liste utilisateurs, reset mot de
passe avec sauvegarde automatique avant, sauvegardes, diff façon git,
application LDIF, 21 tests). 87 tests réels au total. Configuration :
LDAP_ADMIN_* séparées de celles de Keycloak (lecture seule), nouveau
service docker-compose, routage tls-proxy. Bonus sécurité : depends_on
de tls-proxy complété (dba-api/dba-portal/prefs-api/vault-api/
vault-portal manquaient -- exactement le mécanisme de l'incident du
26/08). Réserve honnête : aucun serveur LDAP réel disponible ici,
tout testé via simulations. Reste : l'interface.

## 2026-08-27 — Bug réel : "SSL is required" sur connexions MySQL (version: 03b803931201)

Signalé par capture d'écran. Certains serveurs MySQL/MariaDB
annoncent la capacité SSL sans la supporter pleinement -- PyMySQL
tentait le chiffrement de façon opportuniste. ssl_disabled=True
ajouté à pymysql.connect() (dba/api/connectors/mysql.py) -- paramètre
officiel PyMySQL, confirmé via sa documentation. Non vérifié en
conditions réelles (aucun serveur MySQL disponible ici) -- seule la
syntaxe est validée.

## 2026-08-26 (suite) — Bug réel : erreur 413 systématique sur import mysqldump (version: e0b048e20b6f)

Signalé par capture d'écran. Cause : nginx (tls-proxy) n'avait aucune
directive client_max_body_size -- limite par défaut 1 Mo, bien en
dessous de tout dump réel, alors que Flask (dba/api/app.py) autorisait
déjà 2 Go. Corrigé : client_max_body_size 2G ajoutée au gabarit nginx
partagé (HEADER_TEMPLATE). vault-standalone importe ce même gabarit
par référence directe -- corrigé automatiquement pour les deux
instances par ce seul changement. Vérifié en générant réellement les
deux configurations (--check puis génération complète), directive
confirmée présente dans les deux fichiers produits.

## 2026-08-26 (suite) — Mise en page adaptative : colonne centrale pleine largeur (version: 7835130159f2)

Dernière des 4 demandes groupées. Vue Technicien : nouveau QueueTable
(vrai tableau, colonnes #/Sujet/Demandeur/Site/Type/Niveau/Statut/
Attente) remplace les cartes QueueItem quand rien n'est sélectionné.
Colonne priorités masquée dans ce cas (redondante avec le tableau
plein largeur trié), redevient visible dès sélection d'un ticket --
point à confirmer avec la personne après test réel. Vue Demandeur :
demandeur-detail-col (toujours rendue même vide) rendue uniquement
si detail existe -- flex:1 sur demandeur-table-col fait le reste
automatiquement. Media query responsive existante vérifiée
compatible sans modification. Syntaxe (tsc) validée sur les deux
vues. Non vérifié : rendu visuel réel, aucun navigateur disponible
ici -- particulièrement à confirmer vu qu'il s'agit uniquement de
mise en page.

## 2026-08-26 (suite) — Coffre-fort : observations dans le popup de recherche + ajout unifié (version: 9a4db5096122)

Demandé en priorité (premier client/collègue en attente). Mini-
tableau d'observations dans le popup "🔓" (recherche) -- réutilise
addSecretObservation/fetchSecretObservations déjà existants,
collectionKey déjà porté par les résultats de recherche. Toujours
affiché (pas de bascule, popup déjà centré sur un secret).
Chargement des observations indépendant de la révélation de la
valeur. Ajout unifié par bouton "+" (remplace les panneaux toujours
visibles) : à droite de "Vos collections (n)" et "Secrets (n)",
formulaire replié par défaut, fermé après création réussie, même
motif CSS aux deux endroits. Syntaxe (tsc) validée, équilibre CSS.
Non vérifié : rendu visuel réel, aucun navigateur disponible ici.
Reste noté en backlog : page "Observations" dédiée, mise en page à
clarifier avant de commencer.

## 2026-08-26 (suite) — Console SQL directe, chantier #3 complet (version: 855d1db746e4)

Dernier morceau du gestionnaire de BDD. Vérifié EMPIRIQUEMENT avant
tout code : EXPLAIN ne modifie jamais réellement les données, même
sur DELETE/DROP TABLE (testé avec du vrai SQLite) -- c'est le
mécanisme du test de syntaxe. cur.execute() refuse nativement les
instructions empilées -- protection native contre l'injection par ;.
Nouveau sql_console.py (is_select_statement/check_syntax/
execute_sql). run_backup("avant-sql") déclenché pour tout ce qui
n'est pas un SELECT, jamais pour une lecture seule -- vérifié
réellement (0 sauvegarde sur SELECT, 1 sur UPDATE, fichier tracé).
Interface : sous-onglet "💻 SQL" (Admin → Base), vérification et
exécution séparées, confirmation explicite exigée hors SELECT. 45
tests réels sur cette tranche, non-régression complète. Chantier #3
(sauvegardes, éditeur générique, relations, SQL) intégralement livré.

## 2026-08-26 (suite) — Éditeur générique de lignes + arborescence des relations (version: fa21a2d83320)

Suite du chantier BDD. Nouveau db_explorer.py -- introspection pure
(curseur injecté), testable sans connexion réelle. Tout nom de table
venant du HTTP validé contre la liste réellement introspectée AVANT
interpolation SQL. Clé primaire jamais éditable, quelle que soit la
table. "Contraintes ou non" -- relations déclarées ET probables
(déduites du nom de colonne), vérifiées sur le VRAI schéma tickets :
15 relations trouvées, dont tickets.site_id -> sites.id repérée comme
NON déclarée (ajoutée via ALTER TABLE sans vraie contrainte) --
validation concrète de l'heuristique. run_backup("avant-edition")
déclenché avant chaque modification, édition annulée si la sauvegarde
échoue. Interface : onglet Base gagne "Parcourir/éditer" (pagination,
édition au blur) et "Relations" (liste groupée). 60 tests réels,
non-régression complète. Reste : console SQL avec test de syntaxe.

## 2026-08-26 (suite) — Champ "site" sur le ticket, import en masse (version: da372f4ec68a)

Demandé en cours de test. Nouvelle table sites (SQLite+PostgreSQL
synchronisés), tickets.site_id (migration douce), CRUD générique via
REFERENCE_TABLES. POST /sites/import-text -- fichier signalé "Non-ISO
extended-ASCII text" (pas UTF-8) : decode_uploaded_text() essaie
UTF-8 puis CP1252 (Windows français) puis Latin-1 (jamais d'échec).
Fichier envoyé brut côté interface (FormData avec File direct, jamais
file.text() qui forcerait un décodage prématuré). Déduplique via
contrainte UNIQUE. Interface : section Sites dans Admin → Référentiel
avec import fichier, menu déroulant Site dans la création (vue
Demandeur) et le détail éditable (vue Technicien), repris par
"Recopier". Vérifié avec du vrai CP1252 : accents français
correctement retrouvés depuis les octets bruts. 32 tests réels,
non-régression complète.

## 2026-08-26 (suite) — DBA : couleurs codées en dur invisibles en thème sombre (version: 52c6a1997104)

Signalé par capture d'écran : texte quasi illisible sur une ligne de
connexion sélectionnée en thème sombre. Cause : .dba-conn-item.selected
utilisait #eff6ff (bleu très clair) codé en dur -- texte clair du
thème sur fond accidentellement clair, contraste quasi nul. Même
motif trouvé et corrigé dans les couleurs succès/échec (test de
connexion, import mysqldump, .dba-success) -- toutes remplacées par
var(--ok)/var(--danger)/var(--ok-bg)/var(--danger-bg). --ok-bg
ajoutée à shared/theme.css (manquait, asymétrie avec --danger-bg qui
existait déjà) -- bénéficie à tous les fronts partageant ce thème.
Recherché explicitement ailleurs (hub, tickets, coffre) -- semble
isolé à DBA.

## 2026-08-26 (suite) — Sauvegardes versionnées de la base tickets (version: c112f491157a)

Chantier #3 (gestionnaire de BDD généralisé), commencé par la
fondation de sécurité avant les fonctionnalités risquées (éditeur
générique de lignes, console SQL) -- demandé explicitement en
prévention. Deux déclencheurs : périodique (24h par défaut) et avant
chaque action risquée (pas encore câblé, ces routes n'existent pas
encore). Dump SQL natif (pas JSON) -- iterdump() en SQLite, pg_dump/
psql en PostgreSQL. Nouveau module backup_manager.py, dépendances
injectées, testable sans vrai serveur PostgreSQL. Restauration :
copie de sécurité automatique restaurée si l'opération échoue en
cours de route -- jamais un état pire qu'avant, vérifié avec un dump
corrompu. Traversée de chemin refusée avant tout accès disque. Bug
réel trouvé et corrigé AVANT déploiement : plusieurs workers gunicorn
auraient créé des sauvegardes périodiques en double -- garde-fou par
âge de fichier. 52 tests réels (dont un test bout en bout avec du
vrai SQLite : dump → modification → restauration → état exact
retrouvé). Non-régression complète. Suite : éditeur générique,
console SQL, arborescence des relations.

## 2026-08-26 — Statuts paramétrables avec type, "prise en charge" enfin résolue (version: 2c685e8e3929)

Chantier #2 de la file. Décision finale après plusieurs allers-
retours : "clos" éliminé comme type -- ts_closed reste le seul
mécanisme de fermeture/réouverture (déjà robuste, historique testé).
Le type (en_cours/en_pause/en_attente) ne catégorise que le travail
actif ; les statuts de clôture réels (résolu/livré/abandonné...)
n'ont délibérément pas de type. statuts.type (validé création+
modification) et tickets.first_in_progress_ts (posé une seule fois,
jamais réécrit) -- nouvelles colonnes, migrations douces. PUT
/tickets/<id> restructuré pour calculer la prise en charge (premier
passage à un statut en_cours) avant la construction de l'UPDATE,
même écriture atomique. Nouveau StatutsEditor (AdminView) -- aucune
gestion des statuts n'existait côté portail jusqu'ici. Nouvelle
section "🔧 En cours depuis" (vue Technicien, perspective 2 du
"élastique de temps", enfin disponible). 26 tests réels (18 backend
dont non-régression complète de l'existant, 8 sur le tri), non-
régression complète sur tout le projet.

## 2026-08-25 (suite) — Groupe local demandeurs, configurable (version: 76021d9179a6)

Premier point de la file de demandes. app_settings de tickets renommé
DEFAULT_TICKETS_APP_SETTINGS/mergeTicketsAppSettings (portée élargie
au-delà du seul rappel, d'autres réglages métier vont s'y ajouter).
Nouveau champ local_requester_group -- groupe Keycloak LOCAL
complémentaire à "demandeurs" (LDAP), configurable depuis "⚙️
Paramètres" du hub. Le bouton d'import (AdminView, portail tickets)
importe désormais ce groupe local EN PLUS de "demandeurs", jamais à
la place -- un échec sur le local ne fait jamais perdre le succès
déjà acquis. mergeImportResults (lib.js) fusionne et dédoublonne
l'affichage. 7 tests réels supplémentaires, non-régression complète
(y compris le test backend existant sur l'import Keycloak).

## 2026-08-25 (suite) — Liens "⚙️ Paramètres" sur tous les fronts + backlog (version: 54d0b649494c)

Dernier morceau du chantier paramétrage/rappel. Lien "⚙️ Paramètres"
ajouté sur tous les fronts (tickets-portal, vault-portal,
vault-admin-portal x2 écrans, dba-portal, frontend/TopNav.jsx --
repéré après recherche plus large, le lien Hub y vivait dans un
composant séparé). Lien profond /?view=settings -- le hub ouvre
directement la page de paramètres au montage. Nouveau BACKLOG.md à
la racine : demande notée pour plus tard (gestionnaire de base de
données généralisé, arborescence relations + édition tableaux + SQL
direct) -- à clarifier avec la personne (évolution de DBA existant ou
outil séparé) avant de commencer. Syntaxe validée sur les 5 fronts,
non-régression complète.

## 2026-08-25 (suite) — Widget de rappel d'activité (version: 5e3622c0dd94)

Suite directe de la fondation paramétrage. ReminderWidget.jsx (hub) --
intégré au hub lui-même, s'affiche par-dessus n'importe quel onglet.
tickets-api n'a pas de notion de segment ouvert -- suivi "en direct"
par clôture différée : chaque confirmation clôt la période depuis la
DERNIÈRE confirmation (sur l'ancien ticket) et démarre le suivi du
nouveau choix (computeSegmentToSubmit/nextSession, testés avec un
cycle complet). Deux minuteries séparées (fréquence vs durée
d'affichage, demandé explicitement) -- jamais confondues. Snooze 60
min ou jusqu'à reconnexion. Popup avec liste des tickets ouverts
(/queue?state=open) et lien vers le portail. VITE_TICKETS_API_BASE_URL
ajouté au service hub. 17 tests supplémentaires (56 au total sur tout
le chantier). Non vérifié : rendu visuel réel et déclenchement des
minuteries en conditions réelles, aucun navigateur disponible ici --
la logique métier est en revanche testée à fond. Reste : les liens ⚙️
sur les autres fronts.

## 2026-08-25 (suite) — Fondation du paramétrage transversal (version: 835845939f5b)

Demandé explicitement : commencer une interface de paramétrage
couvrant toutes les applications -- administrateurs ont tous les
droits, chacun configure ses propres préférences. Nouvelle table
app_settings (prefs-api, paramétrage global par application, fusion
superficielle sûre) complète preferences (déjà existante, personnel).
Nouveau SettingsView (hub) : bouton ⚙️ dans l'en-tête, section
"Général" (admin uniquement) et "Mes préférences" (tout le monde).
Premier cas d'usage concret : rappel d'activité technicien (message,
fréquence, durée), avec override personnel prioritaire sur le défaut
applicatif (effectiveTechReminderConfig centralise cette règle).
Logique de snooze centralisée (shouldShowReminder) -- activation,
"pas pour N minutes", "jusqu'à reconnexion". 39 tests réels sur cette
fondation, non-régression complète. Reste : le widget de rappel
lui-même (minuteries, popup tickets), le démarrage réel du suivi de
temps, et les liens ⚙️ sur les autres fronts -- chantier en cours.

## 2026-08-25 (suite) — Octroi séquestre depuis le portail + barre "nouvelle demande" corrigée (version: cc11335997a9)

Coffre-fort : suite demandée après le chantier séquestre -- pouvoir
étendre l'accès à d'autres comptes de confiance directement depuis le
portail admin. grantEscrowAccess(targetLogin, myLogin, myPrivateKey)
(réutilise grantAccess tel quel), nouvelle section dans "🔓 Débloquer
un compte". Reste un octroi cryptographique normal, jamais un
raccourci. 5 tests réels (avant/après octroi, refus si pas d'accès
soi-même, cible inexistante).

Tickets : retour réel -- la barre "nouvelle demande" (pseudo-ligne de
tableau) ne s'alignait jamais sur les colonnes réelles en dessous,
décalage visuel gênant. Sortie du tableau entièrement, devient sa
propre barre collante juste au-dessus de l'en-tête -- celui-ci touche
désormais directement les données. Imperfection mineure assumée :
empilement pixel-parfait en état déplié non vérifiable sans
navigateur réel.

## 2026-08-25 (suite) — Coffre-fort : séquestre maître_clefs jamais initialisé + nav/thème portail admin (version: 916fec82d686)

Retour de test réel : "Vous n'êtes pas membre de maitre_clefs"
s'affichait pour francois alors que Keycloak confirmait bien son
appartenance au groupe. Cause trouvée : usurpMaitrePrincipal ne
vérifie JAMAIS le groupe Keycloak, uniquement un accès cryptographique
explicite à une collection de séquestre (grantAccess), mécanisme
totalement indépendant -- message d'erreur trompeur. En creusant avec
la personne (requêtes SQL directes, sans mot de passe requis) :
cette collection n'avait JAMAIS été créée sur ce déploiement.
createMasterKeyEscrow() existait, testée en isolation, mais jamais
reliée à aucun bouton accessible. Corrigé : message d'erreur
reformulé, nouvelle route GET /escrow-status (distingue "jamais
amorcé" de "pas encore d'accès"), bootstrapMasterKeyEscrow(password,
alsoGrantToLogin) -- amorce en un appel ET accorde l'accès immédiat à
la personne qui amorce (point corrigé après relecture, sinon étape
séparée nécessaire), nouvelle section "🔑 Initialiser le séquestre"
dans le portail admin. Testé bout en bout avec la vraie cryptographie :
amorçage → accès immédiat à l'usurpation, sans étape intermédiaire.

Au passage : lien Hub obsolète (http:// au lieu de https://) corrigé ;
liens Hub/Coffre-fort perdus lors d'une réécriture précédente,
rétablis sur les DEUX écrans (connexion et connecté) ; sélecteur de
thème clair/foncé ajouté (même mécanisme que les 3 autres fronts,
limite assumée : pas de synchronisation croisée immédiate avec eux,
origine différente).

## 2026-08-25 (suite) — Coffre-fort : portail admin en HTTPS (bug bloquant réel) (version: ebec33b7cf5b)

Signalé en plein test réel : mot de passe systématiquement refusé sur
vault-admin-portal malgré un mot de passe correct (fonctionnait sur
vault-portal). Cause trouvée via la trace réseau du navigateur : la
requête GET /users/<login> réussissait, l'échec venait du
DÉCHIFFREMENT (crypto.subtle) -- ce portail est servi en HTTP simple,
or Web Crypto est volontairement indisponible par les navigateurs
hors contexte sécurisé (HTTPS ou localhost). Depuis la refonte
"débloquer un compte", ce portail utilise la même cryptographie que
le coffre principal -- chaque déverrouillage échouait donc
silencieusement, mal interprété en "mot de passe incorrect". Corrigé :
vite.config.js sert désormais en HTTPS, réutilisant le certificat de
la passerelle principale (montage pki/server/, un certificat n'encode
jamais de port). Accès change : https://<ip>:6120 (plus http://).
Repli propre sur HTTP si le certificat n'est pas monté. Logique de
repli testée dans les deux cas ; comportement réel en navigateur à
confirmer, aucun navigateur disponible dans cet environnement.

## 2026-08-25 (suite) — Tickets : "élastique de temps" clarifié, contresens corrigé (version: b504533647a3)

Retour explicite : trois perspectives à combiner, pas juste
l'échéance. Contresens réel trouvé et corrigé -- le mécanisme
d'escalade backend (`apply_deadline_escalations`) ne s'appuie QUE sur
`deadline_ts`, rarement saisi en pratique ; l'urgence perçue vient
aujourd'hui du NIVEAU seul (Forte=J+0, Moyenne=J+1, Faible=J+10).
`deadlineUrgency` utilise désormais `deadline_ts` s'il est saisi,
sinon une échéance IMPLICITE déduite du niveau -- par POSITION de
rang, jamais par libellé (reste correct si les niveaux sont
renommés), marquée "≈" dans l'interface. Nouvelle section "⏳ En
attente" (perspective 1, wait_seconds déjà disponible). Perspective 2
("temps depuis la prise en charge") laissée EN ATTENTE d'arbitrage --
aucun événement "pris en charge" n'est tracé aujourd'hui, plusieurs
déclencheurs possibles avec des implications différentes. 22 tests
réels (dont la vérification centrale : échéance explicite prioritaire
sur l'implicite, calcul par rang jamais par texte).

## 2026-08-25 (suite) — Tickets : vue technicien redessinée (version: c642b557e894)

Dernier morceau de la série de retours de design. Disposition en 3
colonnes changeant selon le contexte : sans sélection, gauche =
demandeurs (usurpation), centre = file d'attente, droite = priorités/
échéances ; ticket sélectionné, la file bascule à gauche (compacte),
le détail prend le centre -- droite inchangée. Usurpation ("le
technicien retranscrit des demandes orales") réutilise le mécanisme
acted_by déjà existant (ActingForDemandeurView), jusqu'ici accessible
seulement comme repli pour un rôle non reconnu. Panneau "priorités et
élastiques de temps" : interprétation assumée (barre de proximité
d'échéance par ticket, rouge une fois dépassée) faute de définition
plus précise -- à corriger si besoin. Logique pure testée
(deadlineUrgency/ticketsByDeadlineUrgency/groupByLevel, 19 tests).
Ancien CSS .columns/.col-list/.col-detail retiré (plus aucun usage,
vérifié). Toute la série de retours tickets est traitée.

## 2026-08-25 (suite) — Tickets : débordement CSS + vue demandeur redessinée (version: 4fc81c6b92c8)

Retour réel, capture d'écran à l'appui. Débordement CSS corrigé :
`.role-chip` (badge groupes Keycloak) sans limite de largeur --
plusieurs groupes concaténés débordait tout le header ; nouvelle
classe `.role-chip-groups` (troncature propre, liste complète au
survol) + `flex-wrap` en repli. Vue demandeur redessinée selon
retour de design : tableau au CENTRE (large) au lieu de la gauche,
détail devient colonne secondaire à droite ; ligne "nouvelle demande"
désormais COLLANTE en tête du tableau (jamais un panneau séparé),
reste visible en défilant les anciennes demandes ; bouton "📋
Recopier vers une nouvelle demande" préremplit la ligne collante
depuis un ticket sélectionné (jamais un envoi automatique). Logique
d'extraction (`ticketToDraftFields`) pure, testée (8 tests). Aucune
suite de non-régression automatisée n'existe pour ce module dans cet
environnement (contrairement au coffre-fort) -- vérifié par syntaxe
et équilibre CSS uniquement. Reste : la vue technicien (chantier
séparé, pas commencé).

## 2026-08-25 (suite) — Coffre-fort : réinitialiser un compte sans perdre les collections (version: b977c0ef0677)

Bug de conception réel découvert : `collections.created_by` avait une
contrainte FK stricte (contrairement à secrets.created_by/
secret_history.changed_by, volontairement non contraints) --
supprimer un compte ayant créé une collection échouait avec
IntegrityError, bloquant exactement ce que cette évolution devait
permettre. Corrigé (schéma + migration structurelle automatique au
démarrage, `ensure_collections_created_by_not_fk`, même technique que
la migration UUID). `DELETE /users/<login>` (vault-api) capture la
liste des collections avant nettoyage. `resetAccount`/
`previewResetImpact`/`reassignAccessAfterReset` (vaultOps.js).
Interface : aperçu avant confirmation (distingue réattribuable/perdu),
puis flux de réattribution en deux temps. Testé bout en bout avec la
vraie cryptographie -- le nouveau trousseau déchiffre réellement les
anciennes collections après réattribution. 34 tests réels,
non-régression complète.

## 2026-08-25 (suite) — Portail admin : refonte "débloquer un compte" (version: af4c1567df14)

Retour de test réel : le champ "nom" ne filtrait rien (confusion),
et surtout aucun moyen concret de débloquer un compte ayant perdu mot
de passe ET clé de récupération -- alors que c'était l'utilité
première décrite pour cet écran. Toute la mécanique cryptographique
existait déjà (`usurpMaitrePrincipal`, `decryptArchivedRecoveryKey`,
d'une session antérieure), jamais reliée à une interface. Connexion
unique (login+mot de passe de l'admin) remplace le champ nom isolé --
identifie ET déverrouille en une étape. Nouvelle section "🔓 Débloquer
un compte" -- révèle une clé de récupération archivée, déchiffrement
client-side, copie presse-papiers. Rôles conservés avec un vrai
filtre de recherche. `vaultOps.js`/`api.js` désormais copiés depuis
vault-portal (source canonique) au build, jamais un fork. Testé bout
en bout avec la vraie cryptographie : la victime se reconnecte
RÉELLEMENT avec la clé révélée (pas juste une comparaison d'octets),
plus le cas négatif (accès refusé sans appartenance à maitre_clefs).
Non-régression complète. Reste : les nombreux points sur le
coffre-fort lui-même (champ URL, révélation momentanée, presse-
papiers, fusion historique/versions, partage visible) -- chantier
séparé à venir.

## 2026-08-25 (suite) — Lanceur central (version: 38f3cb727d2d)

Nouveau `scripts/launcher.sh` -- vue d'état et start/stop/restart par
module, façon apachectl/service. 15 modules regroupant les 31
services de docker-compose.yml, cartographie construite à partir des
dépendances RÉELLEMENT déclarées (depends_on), pas d'une supposition
sur les noms. `scripts/launcher_status.py` (formatage du tableau,
séparé de la coquille bash pour rester testable sans Docker). 17
tests sur le formateur (dont le cas corrigé en cours de route : une
vue filtrée sur un seul module affichait auparavant les autres
modules comme "arrêtés" à tort, alors qu'ils n'avaient simplement
pas été interrogés). 2 tests supplémentaires vérifiant que la
cartographie bash et la cartographie Python (deux copies à
maintenir à la main) restent synchronisées -- détecte tout écart
futur automatiquement. Testé bout en bout avec un faux binaire
docker (statuts, start/stop/restart par module et "all", tous les
cas d'erreur).

## 2026-08-25 (suite) — Coffre-fort : archivage et retour en arrière (version: d1e931946c63)

Dernier et plus gros chantier de la liste de retours. `secret_versions`
(nouvelle table) capture un instantané chiffré complet AVANT chaque
modification -- coexiste avec secret_history (jamais le contenu,
inchangée). Suppression devenue archivage (`is_archived`, jamais une
vraie destruction), visible par tous les membres, restaurable par le
propriétaire. Retour en arrière lui-même annulable (capture l'état
remplacé avant de l'écraser). `last_changed_by` pour l'indicateur
"modifié par quelqu'un d'autre". Deux vrais bugs trouvés en testant :
le CASCADE des observations supposait une vraie suppression (corrigé,
survivent désormais à l'archivage) ; `deleteJson()` n'envoyait jamais
de corps de requête -- l'archivage aurait échoué à 100% en production,
trouvé uniquement grâce au test frontend bout en bout. 42 tests réels,
non-régression complète confirmée sur 3 passages. Toute la liste de
retours utilisateur est traitée.

## 2026-08-25 (suite) — Coffre-fort : survol-copie et copie partielle (version: a02e0d3b04da)

`CopyableValue.jsx` (nouveau) remplace l'affichage brut partout :
texte nativement sélectionnable (curseur/double-clic mot, comportement
navigateur natif, jamais bloqué), bouton de copie au survol, liste de
mots cliquables pour une copie partielle. Bug réel trouvé en
construisant ça : le modal de révélation de l'écran de recherche
affichait encore la valeur brute, jamais mis à jour depuis l'ajout des
champs multiples -- une fiche login/mot de passe y aurait montré du
JSON brut. Corrigé, réutilise FieldsDisplay comme l'onglet Collections.
7 tests réels sur le découpage en mots, non-régression complète.
Reste de la liste initiale : archivage/versions avec retour en
arrière, interface responsive.

## 2026-08-25 (suite) — Coffre-fort : sélecteur de localisation, masquage, is_read_only (version: 8a4e2e648a5c)

Trois points de la liste. Masquage par défaut des localisations sans
code dans l'écran de recherche (`filterTreeToUsedOnly`, préserve les
ancêtres ayant un descendant utilisé), avec case pour tout montrer.
Vrai sélecteur de localisation dans l'onglet Collections
(`LocationPicker.jsx`, `LocationTreeNode` extrait pour être partagé)
-- remplace le champ texte libre, toujours la hiérarchie complète
(contrairement à la recherche). `is_read_only` appliqué côté
interface : masque toutes les actions d'écriture (ajout/modification
de secret, observation, octroi d'accès, nouvelle collection,
maintenance) tout en gardant consultation/révélation/historique
accessibles. Rappel : masquage interface seulement, jamais une
garantie serveur (vault-api ne vérifie aucun jeton). 8 tests réels
sur le masquage, non-régression complète (24 fichiers).

## 2026-08-25 (suite) — vault-admin-portal : retour vers hub et coffre-fort (version: 077203f97e45)

Retour réel : le portail admin était un cul-de-sac, aucun lien de
retour. `href="/"` (motif de vault-portal) ne suffit pas ici -- port
LAN séparé, origine différente du gateway. URLs absolues injectées
via docker-compose.yml (`VITE_HUB_URL`, `VITE_VAULT_PORTAL_URL`),
ouvertes en nouvel onglet. Vide = lien masqué plutôt que cassé.

## 2026-08-25 (suite) — Deux corrections après premier test réel (version: 70e0439c6d0a)

1. **`scripts/run.sh` intercepte maintenant "all"/"main"/"vault-standalone"**
   avec un message clair vers `run-all.sh` -- utilisés par erreur sur
   l'ancien script (`./scripts/run.sh all ...` au lieu de
   `./scripts/run-all.sh all ...`), ils étaient silencieusement
   transmis à `docker compose`, qui échouait avec "unknown docker
   command", peu clair. 3 cas testés + confirmation que l'usage normal
   n'est jamais intercepté par erreur.
2. **`scripts/check-env.py` signalait à tort les variables
   `VAULT_STANDALONE_*`** comme obsolètes -- ne regardait que le
   docker-compose.yml PRINCIPAL, jamais celui de l'instance isolée où
   elles sont réellement utilisées. `OTHER_CONSUMER_FILES` étendu avec
   les 4 fichiers de `vault-standalone/`. 2 nouveaux tests (le cas
   réel signalé, et confirmation qu'une variable VRAIMENT inutilisée
   reste bien détectée).

## 2026-08-25 (suite) — Script central run-all.sh (version: e35fd689adac)

Nouveau `scripts/run-all.sh` -- point d'entrée unique déléguant vers
`scripts/run.sh` (stack principal) et `vault-standalone/scripts/run.sh`
(instance isolée), sans dupliquer leur logique. Cibles : `main`,
`vault-standalone`, `all` (les deux dans l'ordre, arrêt au premier
échec). 7 tests réels avec de faux scripts tracés (délégation
correcte, cible inconnue, script manquant, arrêt au premier échec
confirmé -- la seconde cible n'est jamais appelée après un échec de
la première).

## 2026-08-25 (suite) — Hub : lien vers l'administration du coffre-fort (version: 3c9586b61bd3)

Manquait après la livraison du portail admin des rôles. Ajouté au
hub, visible pour les groupes Keycloak `administrateurs` ou
`maitre_clefs`. Découverte importante en cherchant où l'accrocher :
le groupe Keycloak `maitre_clefs` (mécanisme d'escrow existant) et le
nouveau `is_recovery_controller` (base du coffre) sont deux systèmes
"contrôle de récupération" qui coexistent SANS se parler pour
l'instant -- signalé dans vault/README.md, pas réconcilié dans cette
livraison. 5 tests réels sur la visibilité conditionnelle du lien,
non-régression complète sur le hub.

## 2026-08-25 (suite) — Coffre-fort : tableau de bord maître_système (version: f8e1a2e29a86)

Dernière pièce du chantier rôles. Simplification reconnue : "afficher
pour transmission orale" ne nécessitait rien de nouveau -- le
maître_système utilise l'écran de recherche existant, ayant accès
permanent via l'escrow. Ce qui manquait réellement : `GET /history`
(nouvelle route, journal à travers tout le coffre, jamais le contenu)
et un nouvel onglet "📊 Tableau de bord" (visible si is_system_master),
avec stats + top10 global + journal annoté -- calculés côté client
(réutilise loadAllDecryptedSecretLabels), techniquement impossible
côté serveur (libellés chiffrés). 16 tests réels, non-régression
complète. Chantier rôles/maître_système terminé pour cette série de
retours -- reste : sélecteur de localisation, masquage des
localisations inutilisées, archivage/versions avec retour en arrière.

## 2026-08-25 (suite) — Coffre-fort : rattrapage + portail admin des rôles (version: a8f31ffdac26)

Rattrapage (`backfillSystemMasterAccess`) : bouton dans l'onglet
Collections, accorde l'accès maître_système aux collections
existantes qui ne l'ont pas encore -- comble le trou signalé dans la
livraison précédente. Idempotent, testé avec la vraie cryptographie
(11 tests, dont la confirmation que le maître_système peut réellement
déchiffrer après coup). Nouveau service `vault-admin-portal` --
interface pour gérer les rôles, jusqu'ici seulement accessible par
curl direct. Même discipline de sécurité que `vault-admin-api` :
jamais routé par la passerelle publique, port LAN dédié
(`VAULT_ADMIN_PORTAL_LAN_PORT`, 6120). Non-régression complète.

## 2026-08-25 — Coffre-fort : fondation des rôles (version: efcba71aa2ea)

Premier chantier d'une nouvelle série. Trois capacités indépendantes
et cumulables sur les comptes coffre : `is_read_only`,
`is_recovery_controller` (contrôle des clés de récupération, existant
sous une autre forme), `is_system_master` (accès permanent -- décision
prise avec la personne : volontairement séparé de
`is_recovery_controller`, jamais fusionnés, pour réduire ce qu'il y a
à perdre si un compte est compromis). Escrow systématique : chaque
nouvelle collection enveloppe désormais aussi sa clé pour tout compte
`is_system_master`. Gestion des rôles ajoutée à `vault-admin-api`
(jamais `vault-api` public -- action sensible). 32 tests réels, dont
la vérification cryptographique centrale (la clé déchiffrée par le
maître_système est bien identique à celle du créateur). Non-régression
complète. Reste : rattrapage pour les collections existantes, écran
de déchiffrement/tableau de bord, écran de gestion, application de
is_read_only côté interface, sélecteur de localisation, versions/
archivage.

## 2026-08-24 (suite) — Coffre-fort : largeur et densité de l'écran de recherche (version: 9ec320c85afc)

Deux bugs réels signalés par capture d'écran. Largeur : `.vault-main`
plafonnait à 720px pour tous les écrans, y compris la recherche
(agencement 3 colonnes) -- `VaultView` notifie maintenant son mode
actif au parent, qui élargit à 1400px uniquement pour la recherche,
les formulaires restant inchangés. Densité : chaque fiche de la
colonne centrale passe de 3 lignes empilées à une seule ligne
(libellé qui tronque si besoin, localisation/collection toujours
visibles) -- environ 3× plus de fiches visibles sans défiler, demandé
explicitement ("d'un coup d'œil voir un maximum de fiches"). Non-régression complète sur le coffre-fort.

## 2026-08-24 (suite) — scripts/run.sh : export HERE_DIR (version: 6e16a00a2fed)

Retour terrain : `docker compose build` échouait sur
`COPY shared/VERSION.json .` (tous les services, même erreur) malgré
une génération réussie confirmée ("Version (hash du contenu) : ..."
bien affiché) et le fichier présent au bon endroit une fois vérifié
manuellement. `HERE_DIR` passé en variable exportée dans
`scripts/run.sh` -- a résolu le problème dans l'environnement
concerné. Mécanisme exact non identifié avec certitude (recherché
dans tout le projet : `HERE_DIR` n'est référencé nulle part ailleurs
que dans ce script), mais changement sans risque, adopté pour tous.

## 2026-08-24 (suite) — Coffre-fort : modèles de fiche (version: 0193fada455e)

Évolution directe des champs multiples : `secret_templates` (nom +
libellés de champs, EN CLAIR -- pure structure, même raisonnement que
keyword/localisation), globaux à travers tout le coffre. Interface :
"Utiliser un modèle" (préremplit les libellés) et "💾 Enregistrer
comme modèle" (extrait les libellés actuels d'une fiche créée à la
volée). Nouvel onglet "📋 Modèles" dans l'écran de recherche, portée
volontairement différente des mots-clés (compte seulement l'accessible,
pas étendu cross-collection -- choix assumé, outil d'organisation pas
d'urgence). `template_id` sur les secrets : référence logique, jamais
une contrainte FK stricte, testé explicitement (supprimer un modèle
ne casse jamais les secrets qui le référençaient). 44 tests réels sur
ce chantier, non-régression complète.

## 2026-08-24 (suite) — Coffre-fort : champs multiples et observations (version: 4a040e653e5f)

Premier chantier d'une série de retours utilisateur final : codes à
plusieurs champs (login/mot de passe, préréglage), champs personnalisés
ajoutables, observations horodatées en liste. Simplification trouvée
en concevant : le contenu chiffré étant déjà opaque côté serveur,
aucun changement de schéma vault-api pour les champs -- uniquement
`vaultFieldsLib.js` (nouveau) et l'interface. Rétrocompatibilité
assumée sans migration en masse (impossible côté E2E de toute façon) :
un ancien secret reste lisible tel quel, testé contre des cas piège
(valeur legacy qui ressemble par coïncidence à du JSON). Observations
dans une nouvelle table `secret_observations`, avec CASCADE à la
suppression (contrairement à `secret_history`, volontairement
différent -- testé explicitement). 39 tests réels au total,
non-régression complète. Reste : interface responsive, copie
partielle, super-utilisateur maître_système (accès permanent assumé
avec la personne, chantiers séparés à venir).

## 2026-08-24 (suite) — Coffre-fort : instance isolée livrée (version: 33461e64ef72)

Stack Docker séparé (`vault-standalone/`), même code applicatif
(`context: ..`, aucun fichier dupliqué), infrastructure minimale :
propre entrée IP/DNS, propre certificat, propre Keycloak (allégé, un
seul client, fédération LDAP identique au realm principal). But :
pérenniser le coffre vis-à-vis du hub, en constante évolution. Trois
scripts réutilisent leurs équivalents du stack principal PAR IMPORT
(chargement explicite par chemin, jamais par nom de module — deux
fichiers `render.py` dans des dossiers différents entraient en
collision dans le cache Python, bug réel trouvé en écrivant les
tests) : tous les garde-fous déjà durcis cette session s'appliquent
donc ici automatiquement. Port par défaut (7443, plage 7xxx) choisi
après vérification qu'un premier essai (6543) était déjà pris par
`PIXEL_GRID_POSTGRES_PORT`. PKI testée en conditions réelles avec
openssl (CA et certificat séparés, bon SAN). 23 tests réels. Reste :
export/import avec priorité à l'isolée en cas de conflit, pilotage
depuis le hub — pour une prochaine tranche.

## 2026-08-24 (suite) — Coffre-fort : localisations utilisées mises en priorité (version: 181f872a7f35)

Demandé : la localisation saisie dans un code doit apparaître dans
l'arbre en priorité sur les autres. `enrichLocationTreeWithUsage()`
(`vaultSearchLib.js`) — localisations absentes de la hiérarchie
connue remontent quand même (marquées "non répertoriée", en tête),
et à chaque niveau de l'arbre les nœuds ayant des codes passent avant
ceux qui n'en ont aucun. Bug évité, trouvé en écrivant les tests :
`collectLocationDescendants` était appelée sur l'arbre brut, qui ne
connaît pas les nœuds "non répertoriés" ajoutés par l'enrichissement
— sélectionner l'un d'eux n'aurait retrouvé aucun code. Corrigé avant
livraison. 14 tests réels.

## 2026-08-24 (suite) — Coffre-fort : édition, historique, mot-clé de navigation (version: d31eadd7274c)

Modification de secret avec historique qui/quand/motif
(`secret_history`, jamais le contenu avant/après, `changed_by`
obligatoire). Correction en cours de route sur le mot-clé
personnalisé : d'abord chiffré, revu après retour explicite —
contradictoire avec l'objectif même du champ (retrouver un code en
urgence, y compris sans accès à la collection). Passé en clair, comme
la localisation. Nouvelle route `GET /keywords` — navigation par
mot-clé à travers TOUTES les collections, peu importe l'accès ;
testée avec le scénario réel (Alice retrouve un mot-clé d'une
collection de Bob à laquelle elle n'a jamais eu accès). Bug réel
trouvé et corrigé : la contrainte FK sur `secret_history.secret_id`
empêchait de supprimer un secret ayant un historique — retirée,
devenue une référence logique (l'historique doit survivre à la
suppression de son sujet). 43 tests réels, non-régression complète
sur tout le coffre-fort, y compris un test préexistant adapté à
`changed_by` désormais obligatoire.

## 2026-08-24 (suite) — Coffre-fort : fondation UUID pour l'instance isolée (version: 41522377d0ec)

Premier chantier vers un coffre déployable isolément (Docker stack
séparé, sync ponctuelle avec le hub, isolée prioritaire en cas de
conflit — décidé avec la personne). `collections.id`/`secrets.id`
migrés d'entiers auto-incrémentés (locaux à chaque base, collision
silencieuse garantie entre deux instances) vers UUID v4, générés
côté serveur. Migration structurelle testée à fond : 25 tests dédiés,
dont une **panne simulée en plein milieu** qui a révélé une découverte
sérieuse — le module `sqlite3` de Python ne place pas les instructions
DDL dans la transaction annulable par défaut, un `rollback()` n'aurait
rien défait malgré les apparences. Corrigé (`isolation_level=None` +
`BEGIN` explicite) avant que ça ne touche des données réelles. 7
routes API adaptées, aucun changement frontend nécessaire
(`vaultOps.js` n'a jamais fait d'hypothèse sur le format des ID).
Toute la suite de tests existante du coffre rejouée sans régression.

## 2026-08-24 (suite) — Coffre-fort : IP dans l'arbre + déchiffrement cassé, deux bugs réels corrigés (version: 7478b795c25d)

Retour après capture d'écran sur le nouvel écran de recherche.
**IP réseau visibles dans l'arbre** : `looksLikeIpAddress()` exclut
précisément le format `\d+.\d+.\d+.\d+`, jamais l'absence de
hiérarchie — précision explicite de la personne : une entrée orpheline
peut être un nom abrégé ou un numéro d'équipement légitime, jamais à
exclure pour cette seule raison. **"Déchiffrement impossible" à la
révélation** : bug réel dans `loadAllDecryptedSecretLabels()` —
l'objet transformé pour la liste jetait les champs chiffrés bruts de
la VALEUR, gardant seulement le libellé déjà déchiffré. Réparé
(`encrypted_value_iv`/`ciphertext` conservés, nouvelle
`decryptSecretValueOnly()`). 18 tests réels au total, dont 4
reproduisant exactement le scénario rapporté par la personne.

## 2026-08-24 (suite) — OwnCloud : dossiers récurrents, trois catégories distinctes (version: 377ac7f79ccc)

Retour réel après capture : le panneau précédent mélangeait structure
ownCloud connue (files, cache, thumbnails...) et vraies découvertes
utilisateur dans une seule liste, chacune montrée à "1 occurrence"
comme si c'était déjà récurrent. Corrigé : `KNOWN_OWNCLOUD_STRUCTURAL_NAMES`
(6 noms, exclue du comptage dynamique — connue d'avance, jamais
"détectée") + `splitOccurrencesByThreshold()` (seuil ≥2 pour
"récurrent", sinon "unique" — dit explicitement : "1 occurrence c'est
pas récurrent"). Panneau à trois sections distinctes. 15 tests réels
sur la nouvelle logique, 2 tests d'intégration existants corrigés
(testaient l'ancien comportement, désormais intentionnellement
différent).

## 2026-08-24 (suite) — Coffre-fort : écran de recherche par localisation, enfin livré (version: 51c97567dd83)

Reprise du chantier "recherche par localisation" — la personne a
signalé que l'écran manquait, jamais construit après la pose du
modèle de données (les urgences ont pris le pas entre-temps). `VaultView`
a désormais deux onglets : **🔍 Recherche** (nouveau, par défaut, priorité
demandée explicitement) et **📁 Collections** (existant, préservé).
Trois colonnes comme spécifié : arbre bâtiments/étages/pièces/points
d'accès + recherche (gauche), liste triable/filtrable (centre), top
10 par usage réel (droite). Mode Carte visiblement présent mais
désactivé ("bientôt") plutôt que caché — nécessiterait Leaflet,
absent de ce front. Trou comblé au passage : `record-access` existait
côté backend depuis la pose du modèle mais n'était jamais appelé — le
top 10 serait resté vide pour toujours, câblé maintenant aux deux
endroits où une valeur est révélée. 39 tests réels (30 sur la
logique pure `vaultSearchLib.js`, 9 sur le chargement agrégé à
travers toutes les collections, dont une collection corrompue qui
n'empêche jamais le reste de charger).

## 2026-08-24 (suite) — OwnCloud : dictionnaire de dossiers récurrents, toute profondeur (version: a36e4dc34093)

Généralise l'ancienne case à cocher (3 noms figés, niveau 1
seulement) en un dictionnaire dynamique {nom → occurrences},
**accumulé au fil du chargement, jamais remis à zéro en changeant de
racine** — le but est de repérer ce qui revient d'un compte à
l'autre, impossible avec un état remis à zéro à chaque racine.
Pruning généralisé à toute profondeur (`Archive`/`Trash` niveau 2+
enfin masquables, pas seulement les 3 noms niveau 1 connus d'avance).
Panneau repliable avec bascule individuelle par nom et code couleur
par fréquence. 21 tests réels (16 sur la logique pure, 5
d'intégration bout en bout sur deux racines successives).

## 2026-08-24 (suite) — OwnCloud : tri des racines par nombre d'éléments (version: c06289bfdfeb)

Demandé : nombre d'éléments décroissant par défaut pour la colonne de
gauche, plus pratique qu'un ordre d'arrivée API sans signification.
`sortRoots()` extraite dans `owncloudLib.js` (deux modes, count-desc
par défaut / alpha en alternative) plutôt que laissée en logique
inline dans le composant — testable, 9 tests réels.

## 2026-08-24 (suite) — Coffre-fort : changer le mot de passe, trou d'interface comblé (version: d81dfd9bf8dc)

`vaultOps.js:changePassword()` existait déjà mais n'était appelée
nulle part — aucun bouton, aucun écran. Nouveau bouton "🔑 Mot de
passe" dans l'en-tête (déverrouillé seulement), ouvre une modale
(premier motif overlay de ce front). Pas de ressaisie de l'ancien mot
de passe demandée : la clé privée est déjà déchiffrée en mémoire à ce
stade, la repreuve serait redondante. 7 tests réels, dont la
comparaison directe des octets bruts confirmant que la clé RSA ne
change jamais — seule son enveloppe est reconstruite, la clé de
récupération continue de fonctionner exactement pareil.

## 2026-08-24 (suite) — OwnCloud : chargement infini corrigé (version: 7a962b1d3a09)

Bug réel introduit par la livraison précédente : `chooseRoot()`
appelait encore `setFilterQuery("")`, une référence à l'ancien état
remplacé par `filterTerms`/`filterCombineMode` — jamais retouchée à
l'époque, hors du périmètre édité. Cette fonction n'existant plus,
l'exception levée interrompait `chooseRoot()` juste après
`setTreeLoading(true)`, avant `setTreeLoading(false)` : chargement
bloqué indéfiniment à chaque sélection de racine. Ma propre
vérification précédente (`grep filterQuery`) n'avait pourtant rien
trouvé — contredit en la relançant maintenant, signe qu'elle n'avait
pas couvert tout le fichier à l'époque. Corrigé, et vérification
systématique ajoutée à ma méthode : script comparant TOUS les
setters `useState` déclarés contre TOUS ceux utilisés dans le
fichier, plus fiable qu'un grep ponctuel ou que `tsc` seul (qui n'a
pas non plus détecté cette erreur).

## 2026-08-24 (suite) — OwnCloud : filtre à termes combinables + vue arbre classique (version: 56723ecdbf28)

Demandé : filtrer sur plusieurs motifs (ex. `*.zip` + "analyse"),
chacun en inclusion/exclusion, combinés au choix par ET ou OU — plus
une vue arbre classique (liste indentée) en alternative au radial.
`nodeMatchesGlob()` (joker `*`, ancré sur le nom entier ; sans `*`,
sous-chaîne classique rétrocompatible) et
`buildCombinedGlobPredicate()` (exclure = négation du terme, puis
combinaison ET/OU uniforme, généralise à n'importe quel nombre de
termes) réutilisent telle quelle la mécanique de propagation
ancêtres/descendants déjà en place — aucune duplication.
`OwncloudClassicTree.jsx` partage exactement l'interface de props de
`OwncloudRadialTree` pour permuter librement entre les deux. 23 tests
réels sur la logique pure.

## 2026-08-24 (suite) — Coffre-fort : fondation du modèle "recherche par localisation" (version: 033d3df3bee9)

Demandé : recentrer le coffre autour de sa vraie raison d'être —
retrouver un code par sa localisation géographique, pas une liste de
secrets en collections abstraites. Cette tranche pose **uniquement le
modèle de données**, avant tout écran, décidé explicitement avec la
personne vu l'ampleur du sujet (3 écrans à venir : recherche,
ajout/modif avec corrélation assistée, partage).

**Deux décisions de sécurité tranchées avec la personne, dites
clairement plutôt que devinées** :
- Le lien secret↔localisation est stocké **en clair**
  (`secrets.localisation`) — jamais le libellé ni la valeur, qui
  restent chiffrés de bout en bout. Compromis assumé : recherche/arbre
  rapide côté serveur, au prix que le serveur voie "tel bâtiment a des
  codes" (jamais lesquels).
- La corrélation libellé↔localisation devra tourner **côté client
  uniquement** (le libellé est chiffré, le serveur ne le voit jamais)
  — pas construite dans cette tranche, la fondation l'accueillera.

**Hiérarchie bâtiments/étages/pièces/points d'accès** : extension des
géolocalisations *existantes* de Supervision SI (`pixel-grid`),
partagée entre les deux outils plutôt que dupliquée — migration douce
(`ALTER TABLE`, jamais une recréation qui perdrait les données réseau
déjà géocodées), `COALESCE` côté mise à jour (ne pas fournir la
hiérarchie sur une simple correction de coordonnées la préserve,
jamais un écrasement silencieux).

**"Partage à tous" par défaut** (`collections.is_public`) — **limite
cryptographique assumée, dite clairement** : accorder l'accès exige
toujours que quelqu'un qui a déjà la clé en clair fasse l'enveloppement
pour le nouveau venu, personne ne peut se l'auto-accorder. Fonctionne
pour tous ceux qui ont un compte au moment de la création du code ; un
arrivant plus tard nécessite un geste de quelqu'un qui a déjà accès
(via `maître_clefs`, probablement) — pas encore construit.

**Suivi d'usage** (`access_count`, `last_accessed_at`) pour le futur
top 10 — compteur simple, incrémenté quand la VALEUR est révélée, ne
révèle jamais ce qu'est le secret.

43 tests réels (14 sur la hiérarchie de localisation, 20 sur les
nouvelles routes/colonnes vault-api, non-régression complète
confirmée sur tout le projet).

## 2026-08-24 (suite) — Bouton "Se déconnecter" quasi invisible : sur 3 fronts (version: 21912d14f4eb)

Retour resté en suspens depuis une session précédente. Cause : la
règle CSS générique `button { ... }` (hub, portail tickets) définissait
`background`/`border` via les variables de thème, mais jamais `color`
— un `<button>` n'hérite pas de la couleur de texte de son parent par
défaut dans les navigateurs, contrairement au texte normal. Texte
quasi invisible en mode sombre sur tout bouton sans classe explicite
("Se déconnecter", bascule de thème, diagnostic...). Coffre-fort :
même symptôme, cause légèrement différente — aucune règle générique
`button` du tout, deux boutons ("Verrouiller", "Se déconnecter")
totalement sans style. Vérification systématique (script, pas un
grep naïf) plutôt qu'un correctif au cas par cas : DBA indemne
(tous ses boutons déjà classés), confirmé. 6 tests réels verrouillant
la présence de `color: var(--text)` dans chaque règle générique.

## 2026-08-24 (suite) — Keycloak refusait de démarrer : description trop longue (version: b7e411ccbb3f)

Conséquence directe de la correction précédente : `render.py` rendant
désormais réellement depuis `realm-template.json`, le groupe
`maitre_clefs` (jamais importé pour de vrai jusqu'ici, masqué par le
bug de la sauvegarde) s'est heurté à la colonne interne Keycloak
`DESCRIPTION VARCHAR(255)` — sa description faisait 351 caractères.
Keycloak plantait au démarrage avec une erreur SQL H2 obscure (502
côté nginx, aucune piste évidente sans aller lire les logs du
conteneur). Raccourci à 191 caractères. Vérification systématique
ajoutée à `render.py` : toute description dépassant 250 caractères
(marge sous la vraie limite) fait désormais échouer le rendu
clairement, AVANT écriture, plutôt que de laisser Keycloak planter au
démarrage sans piste. 8 tests réels sur la détection, plus un test
d'intégration confirmant l'échec propre contre une version
délibérément cassée.

## 2026-08-24 — La vraie cause, enfin : render.py préférait un export Keycloak masqué (version: 34d9b16288e9)

Rouvert lundi : vault-portal toujours "client inconnu" malgré la
purge de vendredi. Diagnostic en plusieurs étapes avec la personne
(vérification du fichier importé, de la console Keycloak avec
pagination à 100/page, de `KEYCLOAK_IMPORT_DIR` personnalisée, des
permissions du fichier) a fini par révéler la vraie cause :
`render.py` avait une logique **jamais testée** qui préférait un
export périodique de Keycloak (`keycloak-backup`) au gabarit dès que
cet export existait — intention initialement raisonnable (préserver
les retouches faites à la main dans la console), mais Keycloak
**masque les identifiants sensibles dans ses propres exports**. Cette
logique réinjectait donc silencieusement un mot de passe LDAP cassé
depuis des sessions — très probablement LA vraie cause de l'incident
du 21 août, pas le montage en lecture-écriture corrigé ce jour-là
(correctif resté valide, mais visait le mauvais coupable). Et une
fois l'export présent, plus aucun nouveau client ajouté à
`realm-template.json` n'avait d'effet — `vault-portal` invisible
depuis son ajout, plusieurs sessions plus tôt.

**Retiré entièrement** — `render.py` rend désormais toujours depuis
`realm-template.json` + `.env`, sans exception ni compromis cachés.
La préservation des appartenances aux groupes (le seul besoin
légitime derrière l'idée de départ) reste couverte par
`keycloak/group_memberships.py`, qui ne passe jamais par un export
masquant les identifiants. 6 tests réels reproduisant le scénario
exact rencontré (sauvegarde présente sans vault-portal ni le bon mot
de passe → le rendu final les a quand même correctement).

## 2026-08-21 — Trouvé : le vrai bug LDAP (volume d'import en écriture) (version: 0a2925ba548f)

Résolu, enfin. Confirmation de la personne : `LDAP_BIND_PASSWORD` a
toujours été correct dans son `.env` réel — mes deux tentatives
précédentes (garde-fou sur le placeholder) traitaient donc un
symptôme, jamais la cause. Demandé de vérifier directement le fichier
réellement importé : `bindCredential` y était remplacé par des
astérisques — Keycloak masque les identifiants sensibles dans ses
propres exports (comportement documenté), et le volume d'import était
monté en **lecture-écriture** sans qu'aucun code de ce projet n'en ait
besoin côté Keycloak. Passé en `:ro` — élimine toute la classe de bug,
quel qu'en soit le mécanisme exact déclencheur. `render.py` relit
maintenant le fichier juste après l'avoir écrit et compare au mot de
passe attendu, en renvoyant un code d'échec explicite en cas
d'anomalie plutôt que de laisser échouer l'authentification en
conditions réelles sans piste. 8 tests réels, dont le scénario exact
rencontré (fichier corrompu entre écriture et relecture, bien
détecté).

## 2026-08-21 — Garde-fou LDAP réellement bloquant, sur les deux chemins de purge (version: 61eb64d3cf15)

Retour réel : le mot de passe LDAP a resauté une deuxième fois malgré
l'avertissement ajouté précédemment. Cause trouvée : cet avertissement
n'existait QUE sur le chemin `up` (détection automatique de
changement), jamais sur `reset-keycloak` — précisément celui qui a dû
servir pour la purge liée à `vault-portal`. Extrait en fonction
réutilisable, appelée sur les deux chemins désormais, et rendue
VRAIMENT bloquante (`exit 0` si refusé, pas juste un texte affiché à
côté d'une autre confirmation qu'on peut valider sans le lire) —
confirmation séparée, dédiée à ce risque précis. 3 nouveaux tests
réels (refus → arrêt avant tout le reste, confirmation explicite →
continue, vraie valeur → jamais de prompt).

## 2026-08-21 — Vérification .env pré-déploiement + logs d'erreur centralisés (version: 1d4b6a2a26ae)

Demandé après une session passée à naviguer conteneur par conteneur
dans Portainer sans jamais être sûr du bon. **`scripts/check-env.py`**
(appelé automatiquement par `run.sh`, jamais bloquant) : chemins
`*_DIR` référencés mais absents du disque, variables utilisées mais
manquantes dans `.env`, ou l'inverse. Bug réel corrigé en le testant
contre le vrai projet : 40 faux positifs au premier passage
("obsolètes" alors qu'utilisées par `render.py`/`render_nginx_conf.py`/
`apache/render_apache_conf.py`, pas directement dans
`docker-compose.yml`) — élargi pour scanner aussi ces fichiers
consommateurs, plus aucun faux positif après correction. **
`scripts/logs-errors.sh`** : `docker compose logs` préfixe déjà
chaque ligne par le service — juste un filtre dessus (erreurs,
exceptions, refus...), aucun nouvel outil de supervision nécessaire.
7 tests réels sur `check-env.py`, filtrage vérifié contre des lignes
de log représentatives (reconnaît notamment l'erreur LDAP 49 déjà
rencontrée).

## 2026-08-21 — `run.sh` : hash de version, changelogs ET .env.example exclus du calcul (version: c75acd5f0d12)

Suite directe de l'entrée précédente. Demandé : que chaque entrée de
changelog référence sa version, et pareil en commentaire sur les
nouvelles clés `.env`. Problème auto-référentiel identifié avant
d'écrire quoi que ce soit : si `CHANGELOG.md` ou `.env.example`
comptaient dans le hash, y inscrire ce hash le changerait aussitôt.
`CHANGELOG.md`, `ENV_CHANGELOG.md` et `.env.example` exclus du calcul
(traités comme des métadonnées À PROPOS du code — `.env.example`
n'est jamais déployé ni exécuté par aucun service, un vrai changement
fonctionnel nécessitant une nouvelle clé passe de toute façon par du
code qui la LIT, déjà capturé par le hash via ce code-là) — 4 tests
réels (écrire dans l'un ou l'autre ne change jamais le hash, une
vraie modification de code le change toujours).

## 2026-08-21 — Numéro de version affiché sur les 5 fronts + 6 API

Demandé après une confusion réelle, deux fois de suite ("j'ai peut-être
pas la bonne version"). `scripts/run.sh` génère un hash du **contenu
réel des fichiers** (pas un horodatage brut — corrigé en cours de
route après remarque : un horodatage change à chaque `--build` même
sans rien changer, rendant le numéro inutile). Badge discret, même
motif dans les 5 fronts ; route `/version` sur les 6 API les plus
actives cette session. Bug réel rencontré et corrigé : l'import
devenu obligatoire cassait silencieusement d'autres harnais de test
existants qui importent `app.py` directement — rendu défensif. 47
tests réels au total (hash, endpoint partagé, intégration 6 backends
dans les deux états présent/absent).

## 2026-08-21 — Keycloak : appartenances aux groupes capturées et restaurables

Retour réel après la purge du volume pour vault-portal : les groupes
ont aussi sauté (bug déjà rencontré une première fois après un
incident LDAP, jamais résolu structurellement jusqu'ici). Nouveau
`keycloak/group_memberships.py` (export/restore via l'API Admin REST,
même mécanisme que `keycloak-backup` existant, qui ne couvre PAS ça —
son `partial-export` capture la structure des groupes, jamais les
appartenances individuelles). `run.sh` capture automatiquement avant
toute purge (le seul moment où c'est encore possible) ; nouvelle
sous-commande `restore-groups` pour réappliquer manuellement une fois
Keycloak redémarré et LDAP resynchronisé. 11 tests réels, y compris
des échecs individuels (utilisateur pas encore synchronisé, groupe
supprimé) qui n'empêchent jamais de traiter le reste correctement.

Au passage : avertissement ciblé ajouté dans `run.sh` si
`LDAP_BIND_PASSWORD` est encore au placeholder `change-me` au moment
précis où une purge est proposée — cas réel rencontré juste avant
(correctif fait à la main dans la console, écrasé par un réimport).

## 2026-08-20 (suite) — `run.sh` : détection automatique du realm Keycloak modifié

Demandé explicitement : automatiser les commandes manuelles répétées
plusieurs fois cette session (régénérer le realm, purger le volume
Keycloak, relancer). `run.sh up` compare désormais le realm rendu
contre un marqueur stocké hors du volume Keycloak (survit à sa
suppression) — aucun changement détecté = démarrage normal, rien
demandé ; un changement détecté = résumé des différences affiché puis
**confirmation explicite** avant toute purge, jamais silencieuse (ce
volume porte des réglages qui n'existent nulle part ailleurs). Nouvelle
sous-commande `reset-keycloak` pour forcer une purge volontaire,
confirmation par la phrase exacte "RESET" plutôt qu'un simple oui/non.
16 tests réels sur la logique (bash, avec docker/docker compose
simulés), y compris la découverte réelle du nom de volume par
étiquette Docker Compose plutôt qu'un nom supposé fixe.

## 2026-08-20 (suite) — Coffre-fort : maître_clefs, backend complet et testé

Reprise après l'interruption CHANGELOG — une bonne partie du travail
existait déjà (service `vault-admin-api` séparé, jamais routé par
tls-proxy, jamais testé encore ; `vaultOps.js` déjà étendu avec
`archiveRecoveryKeyForMaster`/`createMasterKeyEscrow`/
`usurpMaitrePrincipal`/`decryptArchivedRecoveryKey`). Nettoyage d'une
tentative parallèle moins aboutie que j'avais recommencée par erreur
directement dans `vault/api/app.py` (doublons retirés).

**Testé pour la première fois** : `vault-admin-api` (23 tests — CIDR
configurables, **journalisation ET email des tentatives refusées, pas
seulement les autorisées**). Le scénario de bout en bout qui justifie
toute cette fonctionnalité (13 tests) : Bob perd son mot de passe ET
sa copie personnelle de la clé de récupération, un membre autorisé de
`maitre_clefs` retrouve et déchiffre sa clé archivée, la récupération
fonctionne réellement — et Eve, jamais autorisée, ne peut rien faire
même avec son propre compte coffre parfaitement valide.

**Reste** : aucune interface pour ce mécanisme (configuration du
maître_principal, panneau de récupération pour les membres de
`maitre_clefs`) — le backend est prêt, rien à cliquer encore.

## 2026-08-20 (suite) — Supervision SI : bannette d'interaction (1ʳᵉ tranche)

Premier morceau d'un chantier plus large (accompagnement visuel
inter-onglets, couches carte, graphe de dépendances amont/aval),
séquencé volontairement. Registre des sources étendu avec une notion
d'origine (`external`/`selection`) — une sélection versée depuis la
corbeille existante devient une nouvelle source, non auto-enregistrée
(reste "proposée" jusqu'à promotion explicite), affichée dans une
section dédiée "Bannette d'interaction". 20 tests Python, non-
régression du chemin `/ingest` existant confirmée explicitement.
Simplification assumée : données brutes non filtrées pour cette
version — le filtrage fin par sélection est reporté (logique
récursive jugée trop risquée à reproduire sans vérification visuelle
possible dans cet environnement).

## 2026-08-20 (suite) — Coffre-fort : interface web complète, branchée

Suite de la fondation cryptographie+stockage. Client OIDC
`vault-portal` (Keycloak), nouvelle couche d'orchestration
`vaultOps.js` (chiffrement + appels réseau, séparée de React pour
rester testable — 21 tests, dont un scénario complet à deux
utilisateurs réels), interface complète (création de compte avec
affichage unique de la clé de récupération, déverrouillage,
collections, secrets cachés par défaut, gestion des accès). Câblage
Docker complet, lien réel depuis le hub. 87 tests réels au total sur
l'ensemble du coffre. Rendu visuel non vérifiable dans cet
environnement de développement (pas de navigateur).

## 2026-08-20 (suite) — DBA : correctif MySQL 8 + connexions par défaut

Retour de test réel. **Correctif** : `cryptography` manquant dans les
dépendances — PyMySQL en a besoin pour l'authentification par défaut
de MySQL 8+ (`caching_sha2_password`), sans quoi toute connexion vers
un serveur MySQL 8 récent échouait. **Nouveau** : connexion(s) par
défaut pré-configurées via un bloc `.env` dédié (`HUB_SGBD_MYSQL_*`/
`HUB_SGBD_POSTGRES_*`, distinct des identifiants IPAM/Optick/Zenoss
déjà présents ailleurs — écarté après discussion, ces comptes restent
réservés à leurs modules), amorçage idempotent au démarrage (15 tests
réels, dont la propriété la plus importante : jamais de duplication
au redémarrage, jamais d'interférence avec une connexion créée à la
main).

## 2026-08-20 (suite) — DBA : import de sauvegarde mysqldump --all-databases

Bouton sur chaque connexion MySQL, s'appuie sur le client `mysql`
officiel (ajouté à l'image Docker) plutôt qu'un reparsing SQL maison
— plus robuste face aux subtilités réelles d'un dump (littéraux avec
points-virgules, DELIMITER des routines...). Identifiants jamais en
argument de commande ni en variable d'environnement — fichier
temporaire à permissions restrictives, supprimé y compris en cas
d'erreur, vérifié explicitement. 19 tests réels sur la logique
(fichiers temporaires, permissions, nettoyage, gestion d'erreurs) ;
non vérifié contre un vrai serveur MySQL (aucun client ni serveur
disponible dans cet environnement de développement).

## 2026-08-20 (suite) — Coffre-fort : groupe/rôle "service" dédié

Réponse à la question ouverte de la session précédente. Nouveau
groupe Keycloak "service", distinct de "techniciens" et
"administrateurs" (décidé avec la personne : tous les techniciens
n'ont pas forcément besoin des codes d'accès physiques, ni les
administrateurs par défaut). Carte hub "Coffre-fort" câblée et
testée (21 tests), mais reste invisible tant qu'aucun front réel
n'existe derrière (`VITE_VAULT_PORTAL_URL` non fournie
volontairement — le service n'est pas encore déployé, rien de
prématuré ajouté à `docker-compose.yml`). Bug de test trouvé et
corrigé au passage : un décompte figé du nombre de rôles connus,
cassé par cet ajout, symptôme sain d'une vraie non-régression.

## 2026-08-20 (suite) — Nouveau chantier : coffre-fort de codes/secrets (fondation)

Chiffrement de bout en bout (le serveur ne voit et ne stocke jamais
rien en clair — vérifié structurellement, aucune bibliothèque de
chiffrement importée côté backend). Schéma hybride RSA+AES (comme les
vrais gestionnaires de secrets audités) permettant un accès fin
partagé entre plusieurs personnes, chacune avec son propre mot de
passe maître jamais transmis au serveur. Clé de récupération (256
bits, affichée une seule fois) pour la contrepartie assumée du
chiffrement de bout en bout (mot de passe oublié = irrécupérable,
sauf via cette clé). 66 tests réels au total (30 Node avec la vraie
API Web Crypto du navigateur — disponible nativement en Node ≥ 19,
aucune simulation —, 36 Python sur le stockage), dont la propriété la
plus critique : un utilisateur non autorisé ne peut déchiffrer ni
même voir l'existence d'une collection à laquelle il n'a pas accès.
Volontairement arrêté à cette fondation (cryptographie + stockage)
avant toute interface — l'application Android reportée (aucun moyen
de compiler/tester un APK dans cet environnement, livrer du code non
vérifiable serait dangereux pour ce sujet précis).

## 2026-08-20 (suite) — Supervision SI : carte réductible à la demande

Bouton "⤡ Réduire" / "⤢ Agrandir" sur la carte — manuel, jamais
automatique (décidé avec la personne, plutôt qu'une réduction
implicite liée à l'état de la corbeille). Réduit d'environ un quart
de hauteur ("le quart inférieur" signalé comme superflu sans
sélection active). `align-self: start` nécessaire : sans ça, la
grille CSS de la page réétire quand même la colonne à pleine hauteur,
annulant toute réduction visible.

## 2026-08-20 (suite) — Supervision SI : liste compacte, sélection groupée, résumé arbre volumineux

Trois retours de tests réels traités ensemble.

**Arbre radial** : comptage AVANT tout calcul D3 (`treeStats.js`, itératif — vérifié sans dépassement de pile sur un arbre pathologique à 20000 niveaux), résumé (nombre de nœuds/niveaux) au-delà de 300 nœuds plutôt qu'un rendu complet inutilisable — échappatoire explicite pour forcer l'affichage si voulu, jamais un blocage strict. 9 tests Node, y compris le cas exact rencontré (5000 nœuds larges, pas profonds).

**Liste des sources** : cartes compactes (une ligne), déploiement à 3 lignes au survol (CSS pur, `max-height`/`opacity`, jamais un état React — pas de scintillement possible). Sélection groupée réutilisant la case à cocher existante (déjà liée à la corbeille, pas de deuxième mécanisme redondant) : barre d'actions groupées (télécharger, verser vers la bannette, supprimer) dès qu'une source est cochée — suppression groupée rendue strictement séquentielle (jamais un `forEach` non attendu sur des appels API).

## 2026-08-20 (suite) — Thème : synchronisation croisée entre les 4 fronts

Trou réel dans la première version (compte et local traités comme
deux mécanismes cloisonnés). Corrigé : `localStorage` devient le bus
de synchronisation unique et immédiat entre les 4 fronts (déjà
partagé de fait, même origine), `prefs-api` reste une couche de
durabilité qui n'écrase jamais un choix local plus frais. 31 tests
Node, y compris la simulation d'un changement fait "depuis un autre
onglet" (évènement `storage`, jamais déclenché nativement dans le
même contexte JS).

## 2026-08-20 (suite) — Supervision SI : retours de tests (colonnes, survol)

Correctifs suite à des tests réels : même bug d'écrasement de boutons
que les sources (colonne détail Pixel Grid, renforcé par prévention) ;
carte réduite intégrée dans le module Géolocalisation avec centrage au
survol d'une ligne (case à cocher pour désactiver) — piège Leaflet
classique anticipé (hauteur de conteneur explicite requise, sinon
carte invisible).

## 2026-08-20 (suite) — Design partagé : thème clair/foncé + préférences

Chantier cosmétique demandé en début de nouvelle session. Fondation
posée pour les 4 fronts : `shared/theme.css` (deux familles de
jetons — hub/portail/DBA convergent vers un socle commun, Supervision
SI garde sa propre identité visuelle avec sa propre paire clair/foncé,
décision volontaire pour ne pas risquer de casser son CSS dense non
audité). Préférences liées au compte pour hub/portail tickets (nouveau
service `prefs-api`), locales au navigateur pour DBA/Supervision SI
(pas d'authentification chez eux aujourd'hui) — décidé avec la
personne. Contextes de build Docker changés pour les 4 fronts
(nécessaire pour copier les fichiers partagés depuis la racine du
dépôt). 33 tests réels (21 Node sur la logique de préférences, 12
Python sur `prefs-api`), non-régression complète revérifiée après les
changements de contexte de build. Rendu visuel réel non vérifiable
dans cet environnement de développement.

## 2026-08-20 (suite) — Nouveau module : DBA (administration multi-SGBD)

Front séparé complet (`dba/api/` + `dba/portal/`, lien depuis le hub)
— PostgreSQL, MySQL (PyMySQL, prioritaire dans la demande), SQLite.
S'ajoute à côté de l'onglet "Gestion base" existant (bases internes à
ce projet), ne le remplace pas — ce nouveau module gère l'écosystème
DBA plus large de la personne, y compris des bases externes/production.
Portée : connexions + parcours de tables + SQL libre (couvre nativement
la gestion de schéma, DDL = juste du SQL, pas de formulaires séparés).

**Décisions de sécurité assumées** : mots de passe de connexion en
clair dans la base locale de l'outil (même posture que le reste du
projet), aucune authentification sur ce front (comme Supervision SI),
protection réelle = visibilité de la carte hub, volontairement plus
stricte que les autres (groupe `administrateurs` seul, pas
`techniciens`). Détail complet dans `dba/README.md`.

**Vérifié réellement (SQLite, bout en bout, 33 tests) vs. non
vérifiable ici** : PostgreSQL et MySQL — code écrit et relu, syntaxe
validée, mais aucune connexion réelle testée (pas de serveur externe
ni bibliothèques installables dans cet environnement de
développement) — premier vrai test contre un serveur réel à faire par
la personne.

## 2026-08-20 (suite) — Renommage du hub : "Hub SI"

Décision finale tranchée (en attente depuis un moment). Titres
(écran de connexion + en-tête), titre d'onglet navigateur, titre du
README du hub. **Distinction respectée** : "Supervision SI" garde son
nom pour l'application de monitoring séparée (la carte qui y mène,
le realm Keycloak, le sous-chemin `/app/`) — seul le hub lui-même
change de nom. Point resté ouvert, pas tranché unilatéralement : le
nom d'affichage du **realm Keycloak** lui-même (`displayName`, visible
sur l'écran de connexion Keycloak, pas celui du hub) est toujours
"Supervision SI" — à voir si ça doit changer aussi.

## 2026-08-20 (suite) — Portail tickets : échéance + escalade automatique d'urgence

Nouveau champ échéance sur les tickets, indépendant du niveau initial
— `deadline_escalation_rules` (configurable, onglet Admin) fait monter
automatiquement l'urgence à mesure que l'échéance approche, sans
jamais redescendre un niveau déjà supérieur. Évalué à chaque appel de
`/queue`, pas de tâche de fond séparée. 17 tests Python, y compris
l'idempotence et le branchement réel (pas juste la fonction isolée).

## 2026-08-20 (suite) — SSO véritablement unique entre hub et portail tickets

Bug réel rencontré : authentifié sur le portail tickets (page reprise
du cache), "Se connecter" quand même redemandé en revenant sur le hub
— chaque front ne vérifiait que son propre stockage local pour savoir
s'il était connecté, jamais l'existence d'une session Keycloak déjà
valide ailleurs dans le même realm. Corrigé : `signinSilent()`
(iframe cachée, `prompt=none`) tentée au montage avant d'afficher
"Se connecter" — grâce à l'entrée unique par chemin, Keycloak vit sur
la MÊME origine que ces deux fronts, donc cette iframe est de même
origine : aucun souci de cookies tiers, contrairement à la plupart des
architectures Keycloak+React documentées en ligne (recherché avant
d'implémenter, pas deviné).

## 2026-08-20 (suite) — Supervision SI : géolocalisations sur la carte

Nouveau bouton "🗺️ Voir sur la carte" dans le module Géolocalisation —
envoie tous les lieux géocodés comme marqueurs sur `MapPanel`,
cadrage automatique sur l'ensemble (`fitBounds`). Nouvelle couche
`markers` additive sur `MapPanel`, coexiste avec le mécanisme de
recentrage existant (Fusion IP/MAC) sans le modifier. **Piège
React-Leaflet + Vite anticipé** : l'icône de marqueur par défaut se
casse à l'empaquetage sans reconfiguration explicite — corrigé,
mais **non vérifié en conditions réelles** (pas de `node_modules`
dans cet environnement de développement, donc pas de build réel
possible ici — à confirmer visuellement au premier test).

## 2026-08-20 (suite) — Portail tickets : "pour le compte de", pas d'usurpation Keycloak

Reconsidéré en cours de discussion — la demande initiale ("usurpation"
façon vraie impersonation Keycloak) s'est révélée plus lourde que
nécessaire une fois le vrai cas d'usage creusé (technicien au
téléphone qui saisit pour un demandeur). Mécanisme plus simple et
local au portail : `acted_by_user_id` (tickets + messages), le
personnel choisit un demandeur et voit sa vue normale, tout reste
tracé "saisi par X pour le compte de Y" sans jamais toucher à
Keycloak. Bouton "Se déconnecter" retiré pour le personnel
(groupes `administrateurs`/`techniciens`/`direction`/`supervision`).
14 tests Python, 2 bugs de harnais de test (fichiers écrits avant
cette migration) trouvés et corrigés au passage.

## 2026-08-20 (suite) — Portail tickets : types/niveaux, import Keycloak

Première tranche d'une demande à 4 volets — les deux plus clairs
livrés maintenant, les deux plus lourds (calendrier ICS, usurpation)
séquencés volontairement pour la suite plutôt que bâclés :
- **Interface types & niveaux** (onglet Admin) — le backend avait déjà
  tout le CRUD, il ne manquait que l'interface. Testé réellement
  (cycle complet + protection d'intégrité référentielle).
- **Import direct du groupe Keycloak "demandeurs"** — nouvelle route
  API, n'écrase jamais un compte déjà présent localement (testé
  explicitement : un rôle changé à la main survit à un réimport).

## 2026-08-20

- **Bug Keycloak documenté (KEYCLOAK-3469) contourné** : les rôles
  hérités via l'appartenance à un groupe ne remontent pas toujours de
  façon fiable dans `realm_access.roles` du jeton, contrairement à
  l'appartenance aux groupes elle-même. Pivot complet : toute la
  logique de visibilité (carte Supervision SI, carte Administration
  Keycloak, sélecteur de vues du portail tickets) repose désormais sur
  les GROUPES Keycloak directement (`GROUP_TO_ROLE`), plus jamais sur
  les rôles calculés — `realm_access.roles` reste affiché dans le
  panneau 🔍 à titre de comparaison seulement.
- **Emails LDAP en double, assumé plutôt que contourné** : deux
  comptes LDAP différents peuvent légitimement partager un email dans
  un annuaire d'entreprise réel — Keycloak refuse ça par défaut,
  provoquant une vraie panne en cascade (import refusé, puis
  `IllegalStateException` sur toute opération touchant le compte
  jamais importé). Décidé avec la personne : corrigé côté réglages du
  realm (`duplicateEmailsAllowed: true` + `loginWithEmailAllowed: false`,
  les deux ensemble pour éviter une ambiguïté de connexion), jamais en
  touchant à l'annuaire — l'intérêt même de la fédération LDAP est de
  ne pas avoir à le faire.
- **Bug réel confirmé et corrigé (CA)** : `SEC_ERROR_REUSED_ISSUER_AND_SERIAL`
  côté navigateur — même mécanisme que la base tickets ci-dessous, une
  CA régénérée à chaque redéploiement complet entre en collision avec
  une ancienne CA encore présente dans le navigateur (même nom
  d'émetteur, même numéro de série de départ). `PKI_DIR` (`.env`) sort
  `pki/ca/`+`pki/server/` de l'arborescence. Un second bug (celui-là
  évité avant livraison, pas rencontré en conditions réelles) :
  `generate-ca.sh` ne lisait que la variable d'environnement déjà
  exportée, jamais `.env` — aurait rendu `PKI_DIR` silencieusement
  inopérant si renseigné seulement dans `.env` (l'usage normal).
- **Bug réel confirmé et corrigé (tickets)** : la base tickets (`tickets.db`)
  vivait dans l'arborescence du projet — un déploiement qui supprime
  puis réextrait le projet à chaque livraison (plutôt que d'extraire
  par-dessus l'existant) la perdait à chaque fois, comptes créés
  compris. Diagnostiqué en éliminant méthodiquement les fausses pistes
  (montage éphémère ? non — bind mount persistant. Schéma détruit à
  chaque démarrage ? non — idempotent depuis un moment. Permissions
  root ? non — le conteneur tourne aussi en root). `TICKETS_DATA_DIR`
  (`.env`) permet de sortir ce dossier de l'arborescence, même
  mécanisme que `KEYCLOAK_IMPORT_DIR`/`KEYCLOAK_BACKUP_DIR`.
- **Nouveau groupe/rôle Keycloak "supervision"** : Supervision SI n'est
  plus visible par défaut sur le hub — conditionné à ce groupe.
  "Administration Keycloak" étendue à "admin" OU "technicien" (avant :
  admin seul).
- **Correctif de découvrabilité** (hub → fronts) : le lien "retour au
  hub" était une icône seule (🏠), jamais repérée en conditions
  réelles — la personne pensait n'avoir que "Se déconnecter" comme
  porte de sortie. Corrigé dans le portail tickets ET Supervision SI :
  libellé texte ajouté, bouton visible en permanence. Pour Supervision
  SI spécifiquement, sujet plus profond qu'un problème de style : le
  lien vivait dans une barre de navigation entièrement masquée par
  défaut (n'apparaît qu'au survol d'une bande invisible tout en haut,
  pensée pour les 13 boutons de module) — sorti de ce mécanisme,
  repositionné en élément fixe indépendant.

- **Correctif** : texte périmé sur le hub ("le portail tickets aura sa
  propre connexion Keycloak...") — datait d'avant que ce chantier soit
  fait, jamais mis à jour depuis. Corrigé.
- **Accès multi-rôles** (portail tickets) : sélecteur de vue si une
  personne appartient à plusieurs groupes Keycloak à la fois (compte
  de test/admin) — invisible pour les comptes à un seul rôle.
- **Hub** : carte "Administration Keycloak" conditionnelle (rôle
  "admin" requis), lien "🏠 retour au hub" ajouté dans les autres fronts.
- **Keycloak** : accès direct de secours réservé au LAN
  (`KEYCLOAK_PORT`, contourne `tls-proxy`), sauvegarde automatique et
  périodique du realm (`keycloak-backup`, API Admin REST), dossier de
  sauvegarde rendu configurable (`KEYCLOAK_BACKUP_DIR`, cohérent avec
  `KEYCLOAK_IMPORT_DIR`).
- **`ENV_CHANGELOG.md`** et **`CHANGELOG.md`** (ce fichier) créés.

## 2026-08-19

- **Bascule d'architecture** : entrée unique par chemin (`GATEWAY_PORT`)
  plutôt qu'un port par service — suggestion de la personne en cours
  de session, actée. Apache (point d'entrée réseau existant, machine
  séparée) passe de 15 `VirtualHost` à 1.
- **HTTPS autonome** : autorité de certification interne (`pki/`, sans
  Let's Encrypt), proxy TLS (`tls-proxy/`, nginx), config Apache
  générée (`apache/`) — plusieurs bugs réels trouvés et corrigés en
  testant (SAN invalide sur `HOST_IP=localhost`, syntaxe bash non
  portable sous `sh`/dash, sortie `openssl` masquée par erreur,
  `KC_HOSTNAME`/`KC_PROXY_HEADERS` absents, `redirect_uri` sans le bon
  préfixe de chemin selon le front).
- **Keycloak branché** : hub et portail tickets consomment réellement
  OIDC (Authorization Code + PKCE) — le realm/les clients existaient
  déjà côté config depuis plus longtemps, sans code applicatif dessus.
  4 groupes Keycloak créés (alignés sur les 4 rôles du portail).

## Avant (résumé, détail dans les README dédiés)

- **Hub** (`hub/`) — portail d'accès séparé du frontend principal.
- **Portail tickets** (`tickets/portal/`) — 4 vues par rôle
  (demandeur/technicien/politique/admin), réouvertures, archivage,
  priorisation par mots-clés.
- **Géomatique** (`geo-import/`) — PostGIS de staging, import
  shapefile, moteur de corrélation (sémantique/géographique/temporel),
  connecteur `geolocations`.
- **Modules internes** (`frontend/`, une vingtaine de services
  backend) — supervision, IPAM, Zenoss, Optick, TTS-GU, OwnCloud,
  Cacti, Fusion IP/MAC, recherche Elasticsearch, logs centralisés.
