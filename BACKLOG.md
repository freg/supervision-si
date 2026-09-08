# Backlog — demandes notées, pas encore commencées

Chantiers explicitement mis de côté pour plus tard (contrairement aux
"chantiers en cours" documentés dans les README de chaque module,
ceux-ci n'ont pas encore de code écrit du tout). Ordre FIFO ("dans
l'ordre d'arrivée des demandes"), sauf mention explicite de priorité
qui fait alors sauter la file.

1. Hub — historique versionné des modifications, "annuler" —
   **chantier majeur en soi**, discuté et VOLONTAIREMENT reporté
   (touche potentiellement chaque backend séparément). Ne pas s'y
   lancer sans en reparler d'abord.
2. Hub/DBA — gestion de tunnels SSH pour joindre des services distants
   (ex. `mysqld` sur de vieilles machines). Contexte donné par la
   personne : beaucoup de vieilles machines avec de vieux MySQL,
   portant des applications métiers NÉVRALGIQUES mais mal
   supervisées et très difficiles à utiliser au quotidien.
   **Cadré avec la personne en #159** (le scénario "utilisateur
   spécial backward/NAT" envisagé plus haut à l'origine ne
   s'applique PAS : connexions SORTANTES uniquement, `ssh -L`
   classique, clés déjà autorisées côté distant) :
   - Clés SSH : chemin protégé PARAMÉTRÉ, jamais générées/stockées
     par ce module.
   - SSHFS : interface préparée, PAS ENCORE fonctionnelle (montage
     FUSE réel reporté explicitement -- privilèges élevés requis).
   - Mode proxy CONFIRMÉ (type rinetd/proxy-delegated) : le tunnel
     ouvre son port local sur le conteneur `ssh-tunnels-api`, les
     autres API du réseau Docker partagé s'y connectent directement
     par son nom.
   - **Backend (clés, connexions, tunnels démarrage/arrêt réels,
     montages en interface seule)** **LIVRÉ en #159** -- voir
     `ssh-tunnels/README.md`. **⚠️ `ssh`/`ssh-keygen` simulés lors
     des tests (réseau restreint dans cet environnement) -- non
     vérifié contre un vrai serveur SSH distant, à tester en
     PRIORITÉ une fois déployé.**
   - **Onglet hub** **LIVRÉE en #175** -- `SshTunnelsView.jsx`
     (menu "Tunnels SSH"), 4 sections (clés/connexions/tunnels/
     montages). Voir `ssh-tunnels/README.md`.
   - **Montage/démontage SSHFS réel** **LIVRÉ en #180** (demandé
     explicitement, "j'en ai besoin pour concevoir la suite") --
     nouveau `mount_process.py` (même motif que `tunnel_process.py`),
     privilèges FUSE Docker (`SYS_ADMIN`/`/dev/fuse`/AppArmor),
     volume `SSH_TUNNELS_MOUNTS_DIR` avec propagation `rshared`. **⚠️
     Non vérifié contre un vrai `sshfs` (réseau restreint ici) -- à
     tester en PRIORITÉ une fois déployé.** **Item 2 désormais
     ENTIÈREMENT LIVRÉ.**
   - **Supervision des montages** **LIVRÉE en #182** -- `GET
     /mounts/<id>/stats` (espace/inodes distants, confirmation de
     montage actif, latence bornée par timeout), demandé
     explicitement en prolongement d'un résumé informationnel des
     possibilités. Voir `ssh-tunnels/README.md`.
   - **Correctif #184 (bug réel)** : mode proxy réellement
     inatteignable -- `-L` liait le port forwardé à `127.0.0.1` DANS
     le conteneur `ssh-tunnels-api`, jamais atteignable depuis un
     AUTRE conteneur (dont `dba-api`) via le réseau Docker, malgré
     la promesse de #159. Rapporté par la personne (connexion MySQL
     refusée depuis DBA sur un tunnel fraîchement créé). Corrigé :
     liaison explicite `0.0.0.0:`.
   **LES DEUX NOTES CI-DESSOUS LIVRÉES EN #277.** Point capital
   trouvé en creusant AVANT de coder : elles contredisaient une
   décision explicite prise avec la personne en #159 (montage
   LECTURE SEULE, "ce service ne génère ni ne stocke jamais de clé
   lui-même") -- signalé explicitement, la personne a CONFIRMÉ
   l'inversion de ce choix (montage passé en lecture-écriture, un
   vrai changement de posture sécurité assumé, pas silencieux).
   -- "permettre la suppression des clés ssh sans aucune sauvegarde
   surtout" -- `DELETE /keys/<id>` : fichier ET registre supprimés,
   AUCUNE copie conservée, comme demandé. Garde-fou ajouté malgré
   tout (pas contraire à la demande, qui portait sur l'absence de
   COPIE, pas l'absence de vérification) : refuse si la clé est
   encore référencée par une connexion active (409, jamais une
   connexion cassée silencieusement).
   -- "permettre de générer des clés sans passphrase ou avec" --
   `POST /keys/generate` (`ssh-keygen -t/-N`, `key_scanner.py`).
   Limite ASSUMÉE et documentée plutôt que cachée : `ssh-keygen`
   n'offre aucun mécanisme par variable d'environnement pour la
   passphrase (contrairement à `sshpass -e` déjà utilisé ailleurs
   dans ce module) -- vérifié auprès de la documentation officielle,
   `-N` reste la seule voie non interactive, exposant BRIÈVEMENT la
   phrase dans la liste des processus du conteneur (jamais journalisé
   ni persisté). Testé spécifiquement que la passphrase ne fuit
   JAMAIS dans un message d'erreur. Voir `ssh-tunnels/README.md`.
3. Hub — gestion de logs de toutes sortes (fichier plat, rsyslog
   distant, UDP, URL) -- **initiative multi-étapes, ordre choisi par la
   personne**. **TERMINÉE, 4/4 étapes livrées.** Étape 1 (push API)
   **LIVRÉE en #142**. Étape 2 (URL, sondage périodique) **LIVRÉE en
   #147**. Étape 3 (fichier plat) **LIVRÉE en #176** -- lecture
   incrémentale, rotation/copytruncate gérées, chemins restreints à
   `LOG_FILES_HOST_DIR` (`.env`). Étape 4 (rsyslog distant/UDP)
   **LIVRÉE en #177** -- nouveau service séparé `rsyslog-listener/`
   (port UDP exposé DIRECTEMENT sur l'hôte, `RSYSLOG_LISTENER_PORT`
   dans `.env` -- syslog ne transite pas par `tls-proxy`), parsing
   RFC 3164/5424 testé contre les exemples canoniques des deux RFC,
   même tampon/registre partagés que les 3 étapes précédentes (le
   hub affiche la source automatiquement). Voir
   `rsyslog-listener/README.md`. Toujours sans interface
   d'administration pour la CONFIGURATION des sources fichier/URL,
   configuration via l'API directement.
4. Hub — client IMAP + interpréteur de messages → source -- **initiative
   à 4 volets, dans l'ordre donné par la personne** :
   - **Client IMAP** **LIVRÉ en #179** -- nouveau module `imap-client`
     (connexion lecture seule, liste des dossiers, liste/lecture des
     messages, `imaplib` standard). Voir `imap-client/README.md`
     pour la distinction avec `parse_zenoss_emails.py` (parseur
     hors-ligne existant, figé sur un format) et les approximations
     assumées (tri par UID, HTML jamais assaini). **⚠️ Non vérifié
     contre un vrai serveur IMAP dans cet environnement (réseau
     restreint) -- à tester en PRIORITÉ une fois déployé.**
   - **Interface de gestion de la boîte** **LIVRÉE en #189, précisée
     en #190** -- création/suppression de dossiers, déplacement de
     message, filtres de recherche natifs IMAP (#189), PUIS
     étiquettes (mots-clés IMAP) et RÈGLES DE TRI avec actions
     déclenchées (#190, après précision de la personne : "trier et
     poser des étiquettes, déplacer vers des dossiers, déclencher
     des actions" -- l'interprétation initiale de #189, recherche
     manuelle seule, était trop étroite). Application des règles à
     la DEMANDE (`POST /rules/apply`), pas encore une tâche de fond
     automatique -- décision volontairement reportée. Voir
     `imap-client/README.md`. **⚠️ Non vérifié contre un vrai
     serveur IMAP -- à tester en PRIORITÉ une fois déployé.**
   - **Gestionnaire d'interpréteur** **LIVRÉ en #191** -- généralise
     en outil CONFIGURABLE ce qui existait seulement en dur (voir
     `pixel-grid/data-generator/parse_zenoss_emails.py`, resté
     inchangé, juste une référence de conception). Un interpréteur =
     critères de correspondance + champs (chaque champ = un motif
     regex indépendant appliqué à sujet ou corps). **⚠️ Piège
     CRITIQUE trouvé et corrigé en testant** : protection contre un
     motif catastrophique d'abord tentée par thread (même motif que
     `mount_process.measure_latency`, #182) -- totalement inefficace
     ici (86s d'attente mesurées malgré un délai d'1s demandé, le
     moteur regex en C ne libère jamais le GIL) -- corrigé avec un
     VRAI processus séparé (`multiprocessing.Process`, seul moyen
     d'interrompre de force). Voir `imap-client/README.md`. **⚠️ Non
     vérifié contre un vrai serveur IMAP -- à tester en PRIORITÉ une
     fois déployé.**
   - **Connecteur source** **LIVRÉ en #230** -- champ optionnel
     `target_source` sur un interpréteur (migration `ALTER TABLE`,
     nullable, comportement inchangé si absent) : quand renseigné,
     `POST /messages/<uid>/interpret` pousse AUSSI le résultat vers
     `POST /ingest/<target_source>` (`api` principal, chemin de
     confiance déjà établi) -- BEST-EFFORT, jamais bloquant si le
     push échoue. **INTERFACE HUB LIVRÉE en #230** -- découverte en
     cherchant où l'ajouter : `imap-client` n'avait ENCORE AUCUNE
     interface du tout (dossiers/messages/règles/interpréteurs tous
     backend seul, malgré "livré" plus haut) -- `ImapView.jsx`
     construite avec les quatre sous-onglets d'un coup.
5. Nouveau module — accès/migration/interfaçage avec de vieilles
   bases/applis tickets -- **initiative à plusieurs volets, décision
   d'architecture déjà prise avec la personne** : NOUVEAU module dédié
   (onglet + API), pas plaqué sur DBA ni sur `tickets`, mais
   **s'appuyant sur `dba/api` pour la couche accès** plutôt que de la
   reconstruire.
   - **Accès, module d'analyse, reconnaissance de relations par le
     NOM des champs, cas des colonnes-listes** **LIVRÉS en #151** --
     voir `schema-analyzer/README.md`. Nouveau module `schema-analyzer`
     (onglet + API, onglet pas encore construit), s'appuyant sur
     `dba-api` en HTTP (jamais d'accès direct à une base -- `dba-api`
     couvre déjà connexion MySQL directe + import de dump). Un seul
     endpoint `POST /analyze` : introspection de schéma, relations
     proposées par nom de champs (suffixe `_id` + correspondance de
     table), colonnes-listes détectées par échantillonnage (ex.
     `sites: "1,2,5"`) avec table cible devinée. PROPOSITIONS
     uniquement, jamais appliquées/stockées -- validation manuelle
     obligatoire (étape suivante).
   - **Éditeur de relations** **LIVRÉ en #152** -- voir
     `schema-analyzer/README.md`. Nouvelle table SQLite `relations`
     (`status` proposed/confirmed/rejected, `source` auto/manual),
     `POST /relations/import-proposals` (pont explicite entre
     `/analyze` et l'éditeur, ne écrase jamais une décision déjà
     prise), CRUD complet (`GET`/`POST`/`PUT`/`DELETE /relations`).
   - **Production d'un schéma XML et JSON "graphe relationnel"**
     **LIVRÉ en #154** -- voir `schema-analyzer/README.md`.
     `GET /relations/graph?connection_id=X&database=Y&format=json|xml`,
     tables (noeuds) + relations CONFIRMÉES uniquement (arêtes) --
     jamais les propositions non validées.
   - **Onglet hub** **LIVRÉ en #156** -- voir `hub/README.md`.
     `SchemaAnalyzerView.jsx` (bouton d'en-tête 🧬) : sélecteur de
     connexion DBA (lecture seule), lancement d'analyse, 3
     sous-onglets (Schéma, Relations -- l'éditeur complet, Export).
     Jusqu'ici l'API n'était accessible que via `curl`.
   - **Interface d'édition des données** **LIVRÉE en #178 (⚠️
     APPROXIMATION, demande restée vague)** -- onglet "Données"
     (`SchemaAnalyzerView.jsx`) : navigateur/éditeur de lignes appuyé
     sur le CRUD existant de `dba-api`, enrichi d'un "aller à la
     ligne liée" via les relations confirmées. Voir `hub/README.md`
     pour l'interprétation retenue et ses limites (échappement SQL
     basique via `/sql`, pas un vrai filtre paramétré).
   - **Validation des relations CONTRE LES VRAIES DONNÉES** **LIVRÉE
     en #241** -- demandé explicitement, en urgence, pendant un test
     réel sur un dump : "à partir du schéma et des données (pour
     conforter la relation)... relier un champ numérique ou set avec
     l'id d'une autre table". Nouveau `relation_validator.py` --
     approche VOLONTAIREMENT PORTABLE (MySQL/PostgreSQL/SQLite sans
     code spécifique par moteur, tout l'éclatement/comparaison en
     PYTHON, jamais du SQL par moteur). `POST /relations/validate`
     (aucun effet de bord, pure lecture) renvoie un taux de
     couverture + les valeurs sans correspondance. Bouton "🔍 Valider
     les données" dans l'éditeur hub. Voir
     `schema-analyzer/README.md`.
   - **Interface de gestion (affectation des relations)** -- distincte
     de l'éditeur de relations ci-dessus (celui-ci corrige le SCHÉMA
     déduit ; celle-ci gère l'AFFECTATION des relations sur les
     données elles-mêmes). **LIVRÉE** -- voir
     `schema-analyzer/README.md`.
6. Nouveau module `ged` — gestion électronique de documents,
   demandé pour deux usages : "documents liés/joints" pour les
   tickets, ET une interface/API GED dans le hub pour accéder/gérer
   les versions -- **choix de GED tierce TRANCHÉ en #158 : Mayan
   EDMS** ("allons-y pour Mayan EDMS", après une recherche rapide en
   #157 -- Python/Django, versioning natif, API REST, Postgres/
   MySQL/SQLite, mature depuis 2010). Table de liaison POLYMORPHE
   restée LOCALE (Mayan n'a pas cet équivalent) -- répond directement
   à "accès polymorphe aux documents".
   - **Backend homemade (#157)** puis **adaptateur vers Mayan EDMS
     (#158)** **LIVRÉS** -- voir `ged/README.md` et `mayan/README.md`.
     Nouveau stack séparé `mayan/` (4 conteneurs : app, PostgreSQL,
     Redis, RabbitMQ, voir `mayan/README.md`). `ged-api` relaie
     désormais vers l'API REST Mayan (`ged/api/mayan_client.py`) --
     API HTTP EXPOSÉE par `ged-api` restée STABLE malgré ce
     changement de backend (objectif tenu depuis #157).
     **⚠️ Connaissance partielle de l'API Mayan réelle (voir
     ged/README.md) -- non vérifié contre une vraie instance dans cet
     environnement, à tester en PRIORITÉ une fois déployé.**
   - **Onglet hub** **LIVRÉE en #167** -- `GedView.jsx` (bouton 📁),
     navigation/gestion générale des documents (pas limitée à un
     ticket), filtre par entité liée, versions, liaisons. Voir
     `ged/README.md`.
   - **Intégration côté tickets** **LIVRÉE en #160** -- section
     "📎 Documents joints" dans les 4 vues du portail tickets
     (`linked_type="ticket"`), voir `tickets/README.md`.
7. Hub/DBA — détection de HTML dans les champs de données affichées,
   avec proposition d'un mode d'affichage FICHE/FENÊTRE VOLANTE.
   Contexte donné par la personne : les tickets d'anciennes gestions
   (importées en dump MySQL dans DBA) sont rédigés en HTML -- affichés
   tels quels aujourd'hui (balises brutes), illisibles en l'état.
   Demande explicite : détecter le HTML dans N'IMPORTE QUEL champ
   (pas une liste de colonnes connues à l'avance -- l'import couvrant
   des schémas hérités variés), et proposer de l'afficher rendu
   (fiche ou fenêtre volante). **LIVRÉ en #214** -- décision prise
   pour le déclencheur resté ouvert (icône "📄 Aperçu" dans la
   cellule dès détection, ouvre une fenêtre volante). Voir
   `hub/README.md`. **⚠️ Assainissement HTML fait main, volontairement
   léger** -- `npm` inaccessible dans cet environnement (tenté
   `dompurify`, 403 même en consultation) -- pas de bibliothèque de
   référence disponible ici, proportionné au contexte (données
   internes, pas de contenu externe non fiable). Un vrai bug trouvé
   et corrigé en testant (balises auto-fermantes non détectées).
8. Hub — archivage PERSISTANT de tous les logs, en dehors des
   conteneurs Docker. Constat de la personne, en testant `ged`/Mayan
   (#163-#164) : le tampon de logs partagé (`shared/log_buffer.py`,
   Memcached, livraison #145 -- introduit pour résoudre le problème
   des 2 workers Gunicorn qui ne partagent pas leur mémoire) est
   VOLONTAIREMENT en mémoire, donc SANS AUCUNE rémanence -- un
   redémarrage de conteneur (service concerné OU Memcached
   lui-même), voire une simple éviction sous pression mémoire, fait
   disparaître les logs sans laisser de trace. Demande explicite :
   archiver TOUS les logs à l'EXTÉRIEUR des conteneurs, choix
   technique laissé libre ("comme tu veux").

   **✅ LIVRÉ en #259** (`memory-api`, tuile "Mémoire", item 32) --
   le backlog n'avait jamais été mis à jour après cette livraison.
   SQLite persistant, collecte périodique du tampon Memcached,
   rétention configurable, mécanisme de repopulation/GC -- exactement
   la demande d'origine. Voir `memory/README.md`.

   **Couverture COMPLÉTÉE en #351** -- en reprenant cet item, trouvé
   que 8 des ~36 services applicatifs actuels n'étaient jamais
   archivés (ajoutés au projet après #259, jamais recensés dans
   `KNOWN_SERVICE_NAMES`) : classifier-api/vigilance-api/tasks-api
   étaient déjà correctement câblés au tampon partagé, juste absents
   de la liste ; rights-api/netprobe-api/relations-api/vault-admin-api
   n'avaient AUCUN câblage au tampon partagé (certains, comme
   rights-api, n'avaient même aucun logging du tout) -- câblage
   complet ajouté à chacun (même motif que `classifier-api`, route
   `/logs` incluse) ; `pixel-grid-bridge` (script en arrière-plan,
   pas un service Flask) découvert avec un vrai problème de contexte
   de build docker-compose (pointait vers un répertoire local, jamais
   accès à `shared/`) -- corrigé en même temps que son câblage.
   Recoupement systématique contre `docker-compose.yml` confirmant
   les 36 services applicatifs désormais tous couverts (script de
   vérification, pas un simple comptage visuel).

   **Suite du même recoupement, découverte plus large (#352)** :
   `hub/src/logsLib.js` (LOG_SERVICES, la liste qui pilote ce que le
   gestionnaire de logs du hub AFFICHE réellement) avait la MÊME
   dérive -- 12 services invisibles dans cette vue depuis leur
   création (mêmes que ci-dessus, sans compter pixel-grid-bridge/
   vault-admin-api, sans route HTTP atteignable pour eux) -- corrigé.
   Et surtout : **DEUX systèmes d'archivage persistant tournaient en
   parallèle** (`prefs-api/log_archiver.py`, #198, antérieur ;
   `memory-api`, #259, plus complet) -- même liste de services
   corrigée dans les deux avant fusion.

   **✅ FUSIONNÉS en #353** (demandé explicitement par la personne) --
   `log_archiver.py` SUPPRIMÉ (fichier, route `/persisted-logs`,
   thread d'archivage, ligne `Dockerfile` correspondante), `memory-api`
   reste la SEULE source d'archivage persistant. Un seul écart de
   fonctionnalité trouvé et comblé avant suppression : `since`/`until`
   (timestamps Unix, filtrant l'horodatage RÉEL du log) redessinés
   sur `list_entries`/`compute_stats_by_service`, remplaçant l'ancien
   `since_iso` qui filtrait une colonne différente (quand collecté,
   pas quand survenu) et n'était de toute façon consommé par aucune
   interface. Voir `memory/README.md` pour le détail complet.
   **❌ Phrase suivante corrigée (2026-09-05)** : affirmait à tort
   "aucune interface hub ne consulte l'historique persisté" -- en
   réalité `MemoryView.jsx` le fait déjà depuis sa création (#259,
   `/stats`/`/services`/`/entries`) -- même erreur déjà corrigée dans
   l'item 52, `hub/README.md` et `memory/README.md`, cette occurrence
   précise avait été oubliée lors de cette correction. Voir item 52
   pour le détail complet de l'erreur et sa correction.
9. Hub — promouvoir `ged` au même niveau que les fronts principaux
   (Supervision SI, Portail tickets, Administration, DBA,
   Coffre-fort...) -- la personne anticipe que `ged` va devenir "un
   outil central". **Étape 1 (la plus simple, dixit la personne)
   LIVRÉE en #172** : tuile sur l'accueil (même rang visuel que les
   autres fronts, personnalisable comme eux), qui bascule vers
   `GedView.jsx` (`onClick`, pas une URL externe) -- voir
   `hub/README.md`. **Étape 2, PAS COMMENCÉE, "on y reviendra"
   dixit la personne** : un vrai front "façon portail" -- URL
   dédiée, plein écran, probablement une extension de
   `buildFrontsList` (`hub/src/lib.js`) pour accepter des vues
   INTERNES au hub comme fronts à part entière, pas seulement des
   URLs de portails externes comme aujourd'hui. **CONFIRMÉ
   IDENTIQUE À L'ITEM 26** par la personne -- l'extension du front
   GED côté hub EST le "gestionnaire de fichiers" demandé en 26, pas
   deux chantiers séparés.
10. Hub — calendrier partagé, présentant TOUTES les données liées à
    un utilisateur ET une date/heure/plage horaire précise, avec un
    outil de visualisation correspondant à `pixel-grid` (module
    existant, grille temporelle dense année → mois → jour → heure →
    minute, zoom par clic, actuellement utilisé pour les données
    d'alertes Zenoss -- voir `pixel-grid/README.md`). Demande
    explicite : agréger des données de PLUSIEURS SOURCES (tickets,
    documents `ged`, activité tunnels SSH, et potentiellement
    d'autres) filtrées par utilisateur ET par temps, dans une
    interface de type grille/pixel comme celle déjà en place.
    **LES TROIS SOURCES NOMMÉES SONT LIVRÉES en #218-219** --
    `pixel-grid/data-generator/export_ssh_tunnel_activity.py` (#218),
    `export_ticket_time_entries.py` et `export_document_links.py`
    (#219), réutilisant pixel-grid TEL QUEL. **Découverte importante
    en vérifiant** : pixel-grid n'a PAS d'API d'ingestion temps réel
    -- export par lot à rejouer périodiquement, jamais un flux
    continu. **Le FILTRAGE réel par utilisateur reste HORS PORTÉE**
    -- vérifié : la table `users` de pixel-grid n'est qu'une ébauche
    structurelle, aucun filtrage n'existe dans l'interface
    aujourd'hui -- chaque export utilise néanmoins déjà le VRAI
    utilisateur (technicien, personne ayant lié un document) comme
    `nom`, exploitant la "Vue timeline équipement" déjà en place
    (clic = timeline complète de cette personne) en attendant un
    vrai filtrage construit dans pixel-grid lui-même. Voir
    `pixel-grid/README.md`. **AUTOMATISATION LIVRÉE en #220** --
    `run_all_exports.sh` orchestre les trois exports + chargements en
    un seul appel (SQLite ou PostgreSQL), pensé pour une tâche cron.
    ⚠️ Piège bash réel trouvé et corrigé en testant : `run_one ...
    || true` désactivait `set -e` À L'INTÉRIEUR de la fonction pour
    tout l'appel -- un export en échec laissait quand même le
    chargeur être invoqué sur un CSV absent/incomplet. **Reste à
    faire** : filtrage utilisateur réel dans l'interface, mode de
    coloration "activité" distinct du "taux d'erreur" existant
    (réutilisé tel quel, potentiellement trompeur visuellement).
    **✅ FILTRAGE RÉEL LIVRÉ en #371** -- `/aggregate`/
    `/aggregate_range` (pixel-grid-api) acceptent un paramètre
    optionnel `nom`, `PixelGridApp.jsx` expose un sélecteur "Filtrer :
    Tous / nom (N points)..." qui recolore la grille entière sur UNE
    seule personne/équipement, sans changer de vue. Voir
    `pixel-grid/README.md` pour le détail complet. **Reste HORS
    portée, volontairement** : le mode de coloration "activité"
    distinct (second point ci-dessus, jamais construit).
    **✅ COLORATION "ACTIVITÉ" LIVRÉE en #371** -- calculée ENTIÈREMENT
    côté client à partir de `total` (déjà présent sur chaque bucket),
    aucun changement backend. Bouton "Erreurs/Activité" dans la barre
    d'outils, échelle bleue relative au maximum de la vue courante,
    volontairement distincte du vert/orange/rouge existant. Item 10
    entièrement complété.
11. Hub/DBA — catalogue SGBD disponible, nouvel onglet. Demande
    explicite (deux volets) :
    - Faire apparaître les tunnels SSH vers MySQL (`ssh-tunnels`,
      #159/#180) comme des SOURCES utilisables dans DBA, l'analyse
      de schémas et "d'autres" (modules précis non listés) --
      aujourd'hui, un tunnel créé dans `ssh-tunnels` n'est PAS relié
      aux connexions `dba-api`, chacune se configure indépendamment.
    - Ce catalogue pourra aussi CONTRÔLER les connexions (fermer/
      ouvrir) et garder un HISTORIQUE (connexion ET paramétrage).
    **LIVRÉ en #221** -- décisions prises pour avancer : périmètre
    limité à Analyse de schémas (module qui reçoit déjà les deux API
    en props, point d'intégration naturel) ; modèle en RÉFÉRENCE
    CROISÉE par hôte+port, jamais une fusion (aucune modification du
    schéma `dba-api` en production) ; historique réutilisant TEL
    QUEL celui déjà construit pour SSH (#210). Nouvelle section
    "🗂️ Catalogue SGBD" (démarrer/arrêter tunnels, historique par
    connexion). Voir `hub/README.md`. **EXTENSION AU PORTAIL DBA
    LIVRÉE en #229** -- même onglet "🗂️ Catalogue SGBD" directement
    dans `dba/portal/` (portail React SÉPARÉ du hub, découvert en
    creusant -- pas une vue interne au hub comme supposé au départ),
    logique volontairement dupliquée plutôt que partagée entre les
    deux codebases frontend. Voir `dba/README.md`. **Reste à faire** :
    "d'autres" modules non précisés, historique du PARAMÉTRAGE (pas
    seulement l'usage).
12. `ssh-tunnels` — authentification par mot de passe, en plus des
    clés. Contexte donné par la personne : certains vieux systèmes
    refusent la connexion par clé SSH. Demande explicite : gestion
    SÉCURISÉE de couples utilisateur/mot de passe (jamais en clair),
    avec un historique d'USAGE (quand, via quelle API/connexion,
    durée). **BACKEND LIVRÉ en #210** -- stockage via
    `shared/secret_crypto.py` (#202-206, pas le coffre-fort, même
    raisonnement d'indépendance que le PRA #203) ; `sshpass -e` pour
    la connexion réelle, mot de passe jamais sur la ligne de commande ;
    migration de `ssh_key_id` en NULLABLE testée contre une base
    simulant l'état réel en production ; table
    `ssh_credential_usage_history` (succès ET échecs, durée
    calculable) ; non-régression RIGOUREUSEMENT vérifiée sur le mode
    par clé existant. Voir `ssh-tunnels/README.md`. **INTERFACE HUB
    LIVRÉE en #211** -- sélecteur clé/mot de passe, indicateur 🔑/🔒,
    historique d'usage consultable par connexion avec durée calculée.
    Item ENTIÈREMENT LIVRÉ.
13. Nouveau module/tuile SNMP -- découverte et déploiement
    automatisé. Demande explicite, trois volets sur une cible
    IPv4/MAC :
    - Découverte de ce qui est ouvert sur la cible (scan de
      ports/services).
    - Gestion des paramètres d'accès sécurisés (communautés SNMP ou
      identifiants SNMPv3).
    - Analyse des informations disponibles sur la cible (SNMP
      walk/MIB).
    **PREMIER SOCLE LIVRÉ en #212** -- nouveau module `snmp/`
    (`pysnmp`, fork actif `lextudio/pysnmp` -- l'original est à
    l'abandon depuis 2022). `POST /query` (groupe System, SNMPv2-MIB),
    `POST /walk-interfaces` (table des interfaces, IF-MIB, statut
    traduit RFC 2863). Décisions de portée prises pour avancer,
    documentées et à corriger si besoin (voir `snmp/README.md`) :
    SNMPv1/v2c seulement (pas SNMPv3), pas de scan de ports, pas de
    "déploiement automatisé" (terme resté ambigu). **⚠️ Jamais testé
    contre un vrai équipement** -- `pysnmp` non installable dans cet
    environnement -- logique d'enveloppe testée contre une simulation
    fidèle de l'API réelle (d'après la documentation officielle),
    l'appel réseau lui-même reste à valider en priorité au premier
    usage réel. **Gestion des paramètres d'accès (volet 2) LIVRÉE en
    #213** -- `snmp/api/credential_crypto.py` + `targets_store.py`,
    même motif que `ssh-tunnels` (#210) : communauté chiffrée via
    `secret_crypto.py`, jamais exposée via l'API. Vérifié
    explicitement que la vraie communauté déchiffrée atteint bien
    `pysnmp`. **INTERFACE HUB LIVRÉE en #227** -- onglet "SNMP"
    (`SnmpView.jsx`), gestion des cibles + interrogation. **Reste à
    faire** : SNMPv3, scan de ports (volet 1, volontairement pas
    construit).
14. Hub — écran "Cyber", résumé et suivi des risques cyber du
    projet. **LIVRÉ en #187** -- demandé explicitement, "au même
    niveau que Logs", "une matrice en premier", "à destination en
    premier lieu des politiques et des béotiens" : nouveau menu
    "Cyber" (`CyberView.jsx`), onglet "Matrice" (grille probabilité
    × gravité, code couleur, lecture seule) par défaut, onglet
    "Suivi" (statut/avancement modifiables). Nouvelles routes
    `/cyber-risks` sur `prefs-api`, départ automatique avec les 14
    risques de `docs/cyber-risques-resume.md` (#186). **Évolution
    ISO/IEC 27001 LIVRÉE en #193** -- demandé explicitement, lien
    Wikipedia fourni : "la matrice devra présenter 2 aspects : le
    HUB et ses risques, les impacts risques du HUB sur le SI
    supervisé, avec une vue mixte". Nouveau champ `scope` par risque
    (`hub`|`si_supervise`), filtre 3 positions au-dessus de la
    matrice (mixte par défaut). Migration testée contre une base
    SIMULANT l'état réel déjà en production (statuts/notes
    préservés, 14 risques connus reclassés par libellé). Voir
    `hub/README.md`.
15. Intégration GLPI (11.0.6) -- demande explicite : "une tuile et
    une api pour utiliser l'api glpi et ses données dans les autres
    tuiles du hub". **Besoin immédiat (import Excel) LIVRÉ en #192**
    -- nouveau module `glpi`, `glpi_client.py` (API historique
    `apirest.php`, choix délibéré face à la nouvelle API v2 encore
    incomplète pour les actifs), `excel_import.py` (mapping
    Type->itemtype, dédoublonnage par numéro de série, plusieurs
    problèmes de qualité de données RÉELLEMENT trouvés dans le
    fichier fourni et signalés plutôt que traités silencieusement --
    voir `glpi/README.md`). Route `POST /import/excel` (dry-run par
    défaut) + script CLI autonome. **⚠️ Non vérifié contre un vrai
    GLPI (aucun accès réseau externe ici) -- à tester en PRIORITÉ,
    en dry-run d'abord, une fois déployé.**
    **❌ Texte corrigé (2026-09-05)** : affirmait que "la tuile
    elle-même" restait à faire -- en réalité `GlpiInventoryView.jsx`
    EXISTE depuis #231 (résumé d'inventaire + import multi-sources
    avec sélection, enrichi en #269), câblée dans `App.jsx`, jamais
    mis à jour ici après coup. Seule reste réellement ouverte :
    l'exposition de données GLPI À L'INTÉRIEUR d'AUTRES tuiles du hub
    (ex. afficher l'actif GLPI lié depuis la tuile Tickets) --
    différent de la tuile GLPI dédiée elle-même, qui existe et
    fonctionne. Adresses MAC multiples et date de mise en service
    (Infocom) pas encore importées non plus.
    **PONTS D'IMPORT AUTOMATIQUE demandés explicitement** ("notre
    GLPI est quasiment vide, je veux le remplir plus ou moins
    automatiquement avec nos futurs outils d'exploration et les
    extractions de Nebula") -- Nebula→GLPI **LIVRÉ en #208**
    (`nebula_import.py`, voir item 16) ; SNMP→GLPI **LIVRÉ en #232**
    (`snmp_import.py`, interroge chaque cible SNMP enregistrée et
    crée/complète une entrée `NetworkEquipment` -- même motif que
    Nebula, `sysLocation`→Location, hôte→`otherserial`). Résumé
    d'inventaire en lecture seule (`GET /inventory-summary`, #231)
    permet de voir l'effet de ces imports sans configurer de tâche
    GLPI native. **Reste à faire** : pont pour de "futurs outils
    d'exploration" au-delà de SNMP (item 20, agent réseau unifié, pas
    encore construit), exposition plus large aux autres tuiles.
16. Import de site Zyxel Nebula (nebula.zyxel.com) -- second besoin
    immédiat de la demande GLPI (#15). **Connexion/consultation
    LIVRÉE en #196** -- nouveau module `nebula`, `nebula_client.py`
    (API OpenAPI officielle Zyxel, clé statique, hiérarchie
    Organisation→Site→Appareil). **⚠️ DEUX PRÉREQUIS BLOQUANTS trouvés
    en recherchant, à réunir côté personne avant tout test réel** :
    licence Nebula Pro Pack sur l'organisation visée, ET une clé
    d'API obtenue via un dossier support Zyxel (jamais en
    libre-service). `GET /test-connection` signale explicitement une
    organisation sans Pro Pack. **Import CSV LIVRÉ en #200** --
    "note et évolution nebula : import et présentation des csv" --
    voie COMPLÉMENTAIRE à l'API (accessible sans Pro Pack ni clé,
    export direct depuis le portail web) : `csv_import.py` (Sites/
    Devices/Clients, testé contre 3 VRAIS fichiers fournis par la
    personne), stockage SQLite persistant (premier de ce module),
    routes `/import/*` + `/imported/*` (dernier état ou historique
    complet). Voir `nebula/README.md`. **IMPORT vers GLPI LIVRÉ en
    #208** -- `glpi/nebula_import.py`, route `POST /import/nebula-devices`
    (appel conteneur-à-conteneur vers `nebula-api`), types réels
    (Access point/Switch/Firewall) mappés vers `NetworkEquipment`.
    **⚠️ MAC stockée dans `otherserial`** (champ générique) après
    avoir vérifié qu'un champ `mac` direct n'existe probablement pas
    sur `NetworkEquipment` (vit normalement dans un sous-objet
    `NetworkPort`, pas créé ici) -- ce choix de repli LUI-MÊME pas
    vérifié contre un vrai GLPI, à confirmer en priorité. **Reste à
    faire** : PRÉSENTATION dans le hub -- **VUE INTÉRIMAIRE LIVRÉE en
    #228** (`NebulaView.jsx`, import CSV + pont GLPI avec aperçu
    systématique) en attendant LA tuile unifiée définitive de l'item
    20 (agent réseau fusionné, pas encore construit) ; l'AGENT
    lui-même (voir item 20 -- **CLARIFIÉ avec la personne** : un seul
    agent, fusionné avec l'ancienne tuile "big-brother", pas deux
    chantiers distincts). **VALIDATION DE TYPE +
    ANNULATION LIVRÉES en #235** -- bug réel signalé par la personne
    au premier usage réel : un export Devices importé via l'onglet
    Sites ne provoquait AUCUNE erreur (les deux formats partagent une
    colonne "Name"), des données FAUSSES étaient insérées
    silencieusement. Corrigé : `csv_import.detect_csv_type()` refuse
    désormais un fichier qui ne correspond pas au type attendu par
    l'onglet actif (message actionnable, quel onglet utiliser à la
    place) ; `DELETE /imported/<type>?imported_at=X` permet d'annuler
    un lot précis. Bouton hub renommé "Importer un CSV des {type}"
    (précis par onglet) + bouton "Annuler cet import" après un import
    réussi. Voir `nebula/README.md`. **ARCHIVAGE GED + SUPPRESSION
    PAR SÉLECTION LIVRÉS en #237** -- demandé explicitement ("tu as
    bien ajouté annuler l'import... mais pas supprimer... une
    sélection et un bouton, un archivage des imports"). Nouvelle
    table `nebula_import_batches` (un lot = un import) ; chaque CSV
    importé est aussi poussé vers la GED (`ged-api`, liaison
    polymorphe `linked_type="nebula-import"` déjà existante, #158) --
    BEST-EFFORT, jamais bloquant pour l'import lui-même. Nouvelles
    routes `GET /import-batches` (historique) et
    `DELETE /import-batches` (plusieurs lots à la fois, garde
    VOLONTAIREMENT le fichier archivé même après suppression des
    données). Section "Historique des imports" côté hub, cases à
    cocher + bouton "Supprimer la sélection". Un vrai bug trouvé en
    testant : deux imports dans la même seconde avaient le même tri
    (résolution `imported_at` à la seconde) -- corrigé avec `id DESC`
    en critère secondaire.
17. Documents de sensibilisation ISO/IEC 27000 à destination des
    utilisateurs/employés. **LIVRÉ en #194** -- demande explicite,
    deux documents : `docs/charte-usage-si.docx` (charte d'usage du
    SI, volet "Sécurité du poste de travail" en premier comme
    demandé, avec l'exemple explicite du branchement USB d'un mobile
    -- rechargement vs transfert de données, les deux risques
    distingués) et `docs/notice-autoformation-cybersecurite.docx`
    (liens vers des ressources d'autoformation) -- RECHERCHE RÉELLE
    effectuée avant rédaction (jamais de lien inventé), incluant une
    trouvaille importante : le MOOC de référence ANSSI (SecNumacadémie)
    est actuellement FERMÉ pour refonte (retour prévu courant 2026)
    -- signalé explicitement dans la notice plutôt que de pointer
    vers un lien mort, avec des ressources de repli (ANSSI hors MOOC,
    kit de sensibilisation Cybermalveillance.gouv.fr). Les deux
    documents utilisent `[NOM DE L'ORGANISATION]` en placeholder, à
    personnaliser avant diffusion. **Reste à faire** : personnaliser
    les placeholders (nom de l'organisation, contacts support/RSSI).
    Le volet "présentés versionnés dans l'aide et dans iso27000"
    **LIVRÉ en #195** -- nouvelle table `governance_documents`
    (`prefs-api`), contenu lu depuis de vrais fichiers `docs/*.docx`
    au démarrage, `GET /governance-documents` + `.../download`,
    panneau affiché dans `AideView` ET `CyberView` (nom, version,
    date). Voir `hub/README.md`.
18. Indicateur visuel d'action EN COURS (état intermédiaire), demandé
    explicitement -- "tunnels ssh : ajouter une prise en compte
    visuel des tentatives de lancement (diode orange ?)", "idem
    partout où un délai est normal". **PREMIER TERRAIN LIVRÉ en
    #197** -- démarrage/arrêt de tunnel SSH ET montage/démontage
    SSHFS (`SshTunnelsView.jsx`). **ÉTENDU en #209** --
    `GedView.jsx` (envoi de document, envoi de nouvelle version par
    document) et `SchemaAnalyzerView.jsx` (import des propositions
    détectées, préfixe harmonisé sur l'indicateur d'analyse déjà
    existant). Voir `ssh-tunnels/README.md`.
    **❌ TEXTE CORRIGÉ (2026-09-05)** : affirmait à tort qu'imap-client/
    GLPI/Nebula n'avaient "pas encore de tuile hub" -- en réalité,
    les trois ont depuis reçu leur tuile (`ImapView.jsx`,
    `GlpiInventoryView.jsx`, `NebulaView.jsx`, toutes câblées dans
    `App.jsx`), jamais mis à jour ici après coup. Vérifié :
    `GlpiInventoryView.jsx` a déjà des indicateurs textuels adéquats
    pour ses actions à délai variable ("Chargement…", "Import en
    cours…") -- l'esprit de la demande semble déjà satisfait là,
    même sans le style "diode" visuel exact des tunnels SSH.
    `ImapView.jsx`/`NebulaView.jsx` pas encore vérifiés sur ce point
    précis -- à faire si le sujet revient.
    **`ImapView.jsx` vérifié et corrigé (2026-09-05)** : bouton
    "Interpréter" restait juste désactivé sans jamais changer de
    texte pendant l'appel -- ajouté "Interprétation…" pendant l'appel,
    suivi par message (`interpretingUid`) plutôt que le `busy`
    générique partagé par toutes les actions du composant.
    `NebulaView.jsx` a déjà `loading`/`busy` avec texte "Chargement…"
    -- pas d'autre gap trouvé à ce stade.
19. Bug potentiel : gestionnaire de logs affiche "vert et à 0" au
    tout premier chargement de l'interface alors que des logs
    existent réellement, dixit la personne ("j'ai le même doute").
    **INVESTIGUÉ en #197** -- revue du code : le "Chargement…" est
    bien affiché tant que les vraies données n'arrivent pas, aucun
    bug trouvé dans cette logique précise. Hypothèse retenue (la
    plus probable, PAS confirmée par un test réel) : le tableau ne
    compte que les événements ≥ WARNING (`LOG_CAPTURE_LEVEL=WARNING`,
    #145) -- un service sans souci récent affiche donc LÉGITIMEMENT
    0/0 vert, visuellement indiscernable d'un chargement ou d'un
    problème. État "0 événement confirmé" rendu EXPLICITE plutôt que
    silencieux (voir `hub/README.md`). **À confirmer avec la
    personne** que c'est bien ce qu'elle a observé, une fois testé
    en conditions réelles.
20. Agent d'exploration réseau ACTIF + tuile unifiée (fusion de
    l'ancienne tuile "big-brother" et de l'agent Nebula "à concevoir"
    -- **CLARIFIÉ EXPLICITEMENT avec la personne** : "un seul agent
    car je suis en réseau (VPN) avec le réseau interne géré par
    nebula, une seule tuile même si on distinguera les sites et les
    réseaux dans l'organisation des données"). Par opposition à la
    supervision PASSIVE existante (zenoss, cacti, ipam...). Volets
    demandés explicitement (les deux discussions réunies) :
    - Un agent, en conteneur Docker, déployé sur un poste local qui a
      accès **en VPN** au réseau interne déjà géré par Nebula --
      **PAS un déploiement multi-points séparé du réseau Nebula**,
      confirmé par la personne : le VPN existant sert de passerelle
      vers ce réseau, un seul agent suffit pour l'instant.
    - Exploration du réseau à base de `tcpdump` et repérage PROGRESSIF
      des équipements (découverte qui s'enrichit avec le temps, pas
      un scan ponctuel).
    - Archivage/statistiques des VOLUMES échangés, identification des
      SERVICES, archivage/statistiques des USAGES et USAGERS.
    - Volet routeur/switch dédié -- identifier et évaluer leurs RÔLES
      (NAT et autres).
    - Transmission RÉGULIÈRE des résultats vers UNE SEULE tuile du
      hub -- les données y seront ORGANISÉES par site et par réseau
      (segment), mais présentées dans UN écran unifié, pas plusieurs
      tuiles séparées.
    Référence donnée par la personne : **Tkined/Scotty** -- suite
    historique (Jürgen Schönwälder, années 1990) de découverte et
    visualisation réseau par SNMP scripté en Tcl/Tk.
    **PREMIÈRE TRANCHE LIVRÉE en #233** -- nouveau module
    `network-agent/` : analyseur pcap en PYTHON PUR (`pcap_parser.py`
    -- ni `dpkt` ni `scapy` installables ici, réimplémente le format
    pcap et les en-têtes Ethernet/IPv4/ARP/TCP/UDP), orchestration
    `tcpdump` (`capture.py`), stockage site → segment → appareil →
    services (`store.py`), API + thread de capture en arrière-plan
    (`app.py`, même motif que rsyslog-listener #177), tuile hub
    unique (`NetworkAgentView.jsx`). **Détection du rôle passerelle/
    routeur** : heuristique RÉSEAU réelle (résolution ARP hors
    sous-réseau = MAC de la passerelle), pas devinée. **Services**
    identifiés par port TCP/UDP destination (limite assumée : un
    appareil-passerelle accumule des services divers, reflet du
    trafic relayé). Statistiques des VOLUMES ✅, des SERVICES ✅, des
    RÔLES ✅ ; des USAGERS **PAS fait** (hors de portée du seul trafic
    capturé). Voir `network-agent/README.md` pour le détail complet
    des décisions et de ce qui est vérifié. **⚠️ Jamais vérifié en
    conditions réelles** (aucun accès à `tcpdump`/une interface
    réseau capturable dans cet environnement) -- toute la LOGIQUE de
    traitement est testée en profondeur avec des paquets/scénarios
    synthétiques précis, l'appel réel à `tcpdump` reste à valider en
    priorité au premier déploiement. **`network_mode: host` CONFIRMÉ NÉCESSAIRE en #238** -- premier
    test réel de la personne : sans lui, `ens18` (interface de
    l'hôte, nommage Proxmox) est invisible depuis le conteneur
    ("No such device exists"). **DEUX PROBLÈMES EN CASCADE trouvés et
    corrigés en #239, via deux AUTRES retours de test réels** :
    (1) `host.docker.internal` (la correction de #238) ne fonctionnait
    PAS non plus -- même un `proxy_pass` littéral passe par le
    résolveur dynamique nginx dès qu'il est déclaré dans le bloc
    englobant, qui ne consulte jamais `/etc/hosts` -- corrigé en
    utilisant directement `HOST_IP` (déjà configuré ailleurs dans ce
    projet) comme adresse IP littérale, sans résolution DNS nécessaire ;
    (2) le port 5000 par défaut entrait en collision RÉELLE avec un
    `docker-registry` déjà présent sur l'hôte de la personne
    (`network_mode: host` expose directement ce port sur l'hôte,
    jamais isolé) -- corrigé avec un port configurable
    (`NETWORK_AGENT_HOST_PORT`, défaut 15000). Voir
    `network-agent/README.md` et `tls-proxy/README.md` pour le détail
    complet des trois livraisons de correctifs (#238-239) nées de
    tests réels successifs. **CAPTURE RÉELLE CONFIRMÉE FONCTIONNELLE
    en #240** -- confirmation directe de la personne : appareils
    découverts, ET la détection de passerelle (heuristique ARP hors
    sous-réseau, voir `capture.py`) a correctement identifié une
    vraie passerelle sur son réseau -- le point le plus incertain de
    tout ce module, jusqu'ici validé seulement par des scénarios
    synthétiques, fonctionne bien tel que conçu. **Reste à faire** :
    articulation avec `ipam-api`/`cacti-api`/`zenoss-api`/le module
    SNMP existants, stockage CSV Nebula (#200) comme éventuelle autre
    source pour cette même tuile, comportement en conditions de
    charge/durée non encore observé.
    **Demandes d'ergonomie/fonctionnalités ajoutées par la personne
    (2026-09-03) -- TOUTES LES SIX LIVRÉES EN #250** :
    - En-têtes de colonnes ET barre de menu haute restent visibles
      au défilement ✅ (en-tête global `.hub-header` fixe -- bénéfice
      pour tout le hub --, liste des appareils dans un conteneur
      défilant propre avec en-têtes de colonnes fixes à l'intérieur).
    - Services affichés dans l'espace libre/pied de page ✅ (pied de
      page fixe au clic sur une ligne -- retenu comme solution
      principale plutôt qu'une colonne latérale, fonctionne quelle
      que soit la largeur d'écran, à ajuster si préférence contraire
      après usage réel).
    - Petits points colorés, nom au survol ✅ (bleu=TCP/ambre=UDP,
      attribut `title` natif, nouvelle route groupée
      `GET /devices/services` pour éviter un appel par appareil).
    - Détection des ÉCHANGES entre appareils ✅ (nouvelle table
      `na_device_links`, DIRECTIONNELLE, enregistrée automatiquement
      dans `capture.py` -- rejoint directement l'idée de graphe
      d'architecture réseau/inspiration Tkined-Scotty déjà discutée).
    - Résolution DNS affichée ✅ (colonne "Nom d'hôte").
    - DNS/domaine par défaut depuis l'hôte OU paramétrable ✅ (les
      DEUX : résolveur système par défaut, `NETWORK_AGENT_DNS_SERVER`
      pour un serveur précis -- `dnspython` non installable ici,
      client DNS minimal fait main, même approche que `pcap_parser.py`
      -- `NETWORK_AGENT_DEFAULT_DOMAIN` pour retirer un suffixe).
    Voir `network-agent/README.md` pour le détail complet, ce qui
    est vérifié, et les deux points laissés "reste à faire"
    (échanges jamais testés contre un vrai volume de trafic, choix
    pied-de-page-vs-colonne à confirmer après usage réel).
    **RÉMANENCE/HISTORIQUE LIVRÉE EN #251** -- demandé explicitement :
    "voir dans le temps... présence des ip/mac, volumes échangés/
    usages par paire d'ip, services connectés par paire d'ip".
    Nouveau mécanisme de RELEVÉS PÉRIODIQUES (toutes les tables
    existantes étaient cumulatives, jamais d'évolution dans le
    temps) -- un relevé par heure par défaut, conservé 30 jours,
    thread de fond dédié DISTINCT de la capture et de la
    résolution DNS. Nouvelle table `na_device_link_services`
    (services PAR PAIRE d'appareils). Section "Présence dans le
    temps" côté hub (tableau simple, pas de bibliothèque de
    graphique disponible). Voir `network-agent/README.md`.

21. Organiser et préparer les configurations serveur et agents GLPI
    pour compléter la supervision des réseaux "accessibles plus ou
    moins directement". Demande explicite ("note et évolution
    glpi"). **PAS COMMENCÉ** -- juste noté, avec une recherche réelle
    déjà faite sur le fonctionnement RÉEL de GLPI Inventory (plugin
    serveur, anciennement FusionInventory) pour cadrer la suite :
    - Deux tâches DISTINCTES et SÉQUENTIELLES : "Network discovery"
      (scan ARP/ICMP/NetBIOS/SNMP d'une plage IP, détection minimale
      -- MAC, nom) PUIS "Network inventory (SNMP)" (uniquement sur les
      équipements déjà découverts, identifiants SNMP requis, collecte
      détaillée).
    - Configuration CÔTÉ SERVEUR (Administration > GLPI Inventory) :
      plage IP cible, planification, et surtout un "acteur" -- un
      agent GLPI désigné pour exécuter la tâche.
    - **Point clé pour "réseaux accessibles plus ou moins
      directement"** : l'agent-acteur doit avoir un accès RÉSEAU
      DIRECT à la plage ciblée -- pour un réseau segmenté (VLAN,
      sites distants...), ça implique un agent DÉPLOYÉ SUR CHAQUE
      segment autrement inaccessible depuis un point central, pas un
      agent unique qui scannerait tout depuis un seul endroit.
    - Piste pour les segments qui ne peuvent PAS du tout joindre le
      serveur GLPI : le plugin ToolBox (interface web embarquée dans
      l'agent, fonctionne SANS serveur) ou l'outil `glpi-netinventory`
      en ligne de commande (résultats injectés après coup via
      `glpi-injector`).
    Rien de tranché avec la personne sur l'ARCHITECTURE de déploiement
    réelle (combien de segments, lesquels sont vraiment isolés,
    combien d'agents il faudra concrètement) -- à cadrer ensemble.
    **NOTE DE PRÉPARATION livrée en #222** --
    `docs/preparation-glpi-inventory.docx` organise ce qui est déjà su
    et pose clairement, dans un tableau, les questions qui dépendent
    de faits sur l'infrastructure RÉELLE (jamais devinés ni présumés
    ici -- contrairement à d'autres items de ce backlog, les inconnues
    portent sur le terrain, pas sur des choix de conception). **RÉSUMÉ
    D'INVENTAIRE EN LECTURE SEULE LIVRÉ en #231** -- `GET
    /inventory-summary` (Computer + NetworkEquipment déjà connus de
    GLPI) et `GlpiInventoryView.jsx` -- volontairement PAS un
    formulaire de configuration de tâche (l'itemtype exact de l'API
    REST GLPI pour l'inventaire natif 10+ n'a jamais été vérifié dans
    ce projet, jamais présenté une action non vérifiée). Voir
    `glpi/README.md`. Item TOUJOURS PAS COMMENCÉ côté configuration
    effective (découverte/inventaire réels) -- en attente du
    recensement des segments réels avec la personne.
    **DÉCOUVERTE AUTOMATIQUE DE SEGMENTS LIVRÉE EN #256** -- la
    première question du tableau ("combien de segments réseau
    distincts ?") n'a plus besoin d'un recensement manuel préalable :
    `network-agent` regroupe désormais les appareils déjà découverts
    par sous-réseau (granularité paramétrable), révélant la structure
    interne réelle du LAN depuis le trafic observé. Vérifié avec le
    réseau réel de la personne (192.168.0.0/16, 3 plages en usage).
    Voir `network-agent/README.md`. Les AUTRES questions du tableau
    (isolation réelle vis-à-vis du serveur GLPI, nombre d'agents à
    déployer, hébergement, identifiants SNMP, planification) restent
    À TRANCHER -- cette découverte automatique aide à y répondre,
    elle ne les tranche pas seule.

22. Chiffrement des secrets de démarrage (mots de passe `.env`,
    clés SSH) -- points 2/3 de l'urgence matrice de risque. **Primitives
    LIVRÉES en #202** -- `shared/secret_crypto.py` (PBKDF2-HMAC-SHA256
    600k itérations + Fernet, testé de façon exhaustive : 21 cas).
    **Documentation PRA (point 4) LIVRÉE en #203** --
    `docs/pra-secrets-demarrage.docx`, procédure à 3 canaux détaillée
    avec la personne (phrase de passe + SMS via la route machine de
    la passerelle SMS Teltonika TRB140, vérifiée contre le VRAI code
    fourni par la personne + alerte courriel institutionnelle),
    versionnée dans Aide/Cyber comme les 2 autres documents (#194).
    **CLI LIVRÉ en #204** -- `scripts/secrets_tool.py`
    (init-salt/encrypt-value/decrypt-value/encrypt-file/decrypt-file),
    voir `docs/chiffrement-secrets.md` pour le suivi technique
    complet. **CÂBLAGE `scripts/run.sh` LIVRÉ en #205** --
    `.env.encrypted` optionnel, détecté automatiquement (absent =
    comportement rigoureusement inchangé), phrase de passe resaisie
    à CHAQUE lancement, secrets déchiffrés injectés dans le seul
    processus `docker compose` en cours. Testé de bout en bout avec
    un faux `docker compose` (avec et sans `.env.encrypted`). Un vrai
    bug trouvé et corrigé en testant : une valeur VIDE dans le `.env`
    source faisait échouer tout le déchiffrement. Ces secrets restent
    volontairement INDÉPENDANTS du coffre-fort/Keycloak.
    **✅ SCRIPT DE MIGRATION GUIDÉ LIVRÉ en #386** -- demandé
    explicitement ("continue sur le 22") : `scripts/migrate-env-to-encrypted.sh`
    automatise la séquence sûre déjà prévue ici (sauvegarde horodatée
    -> chiffrement -> déchiffrement de vérification immédiat ->
    comparaison clé par clé avec `scripts/verify_env_migration.py`,
    jamais une confiance aveugle dans le chiffrement) -- `.env`
    d'origine et sa sauvegarde JAMAIS touchés par ce script, quel que
    soit le résultat. Le BASCULEMENT réel (renommer `.env`, confirmer
    qu'un déploiement fonctionne, supprimer la sauvegarde) reste une
    décision et une action MANUELLES et SÉPARÉES de la personne --
    ce script prépare et vérifie, il ne bascule jamais tout seul. Voir
    `docs/chiffrement-secrets.md` pour le détail complet, y compris
    ce qui reste NON vérifié (usage interactif réel -- testé de bout
    en bout avec les vrais outils de chiffrement dans cet
    environnement, mais la saisie de phrase de passe à travers
    plusieurs invocations enchaînées s'est révélée peu fiable
    spécifiquement dans ce sandbox de test, sans lien avec un usage
    interactif normal).
    **✅ CLÉS SSH LIVRÉES en #387** --
    `scripts/migrate-ssh-keys-to-encrypted.sh` + nouveau
    `scripts/verify_file_migration.py` (comparaison octet par octet,
    compagnon binaire de `verify_env_migration.py`) -- même séquence
    sûre que `.env` (sauvegarde -> chiffrement -> vérification),
    découverte automatique des clés dans `ssh-tunnels/keys/` (même
    convention que ce module -- un fichier = une clé, `README.md`/
    `*.pub` exclus). Un vrai bug trouvé et corrigé en écrivant ce
    script : `path` de `encrypt-file`/`decrypt-file` est POSITIONNEL,
    pas `--path`. Voir `ssh-tunnels/README.md` et
    `docs/chiffrement-secrets.md` pour le détail complet. **Item 22
    entièrement complété** -- plus aucun point resté ouvert. Comme
    pour `.env`, le BASCULEMENT réel (câblage de `ssh-tunnels-api`
    pour lire des clés `.enc`) reste un sujet séparé, non traité ici.
    **Alertes SMS/courriel de la procédure PRA LIVRÉES en #206** --
    `shared/secrets_alert.py`, canaux entièrement optionnels
    (variable absente = ignoré silencieusement), déclenchés
    automatiquement après un déchiffrement réussi. Canal SMS via la
    vraie route `/send` de la passerelle Teltonika TRB140. Canal
    courriel en SMTP direct (bibliothèque standard uniquement, aucune
    nouvelle dépendance). Testé avec de VRAIS échecs réseau (noms
    d'hôte inexistants) -- confirmé : un échec d'alerte ne contamine
    jamais la sortie destinée à l'`eval` de `run.sh`, et ne fait
    jamais échouer le déchiffrement par ailleurs réussi.
23. Coquille Docker générique à déployer sur un serveur DISTANT
    (Proxmox chez OVH), reliée au hub par un canal VPN SORTANT DU HUB
    (le hub initie la connexion vers ce serveur, pas l'inverse).
    Demande explicite, plusieurs volets :
    - Une nouvelle section "VPN" dans le hub, à gérer AUX CÔTÉS des
      tunnels SSH existants (`ssh-tunnels`) -- articulation exacte
      avec ce module existant (fusion, extension, ou section
      séparée ?) pas précisée.
    - But annoncé : déployer deux applications/services sur ce
      serveur distant, à travers ce canal :
      1. Un kanban + un dépôt de fichiers, pour permettre à la
         personne de poursuivre son travail de spécifications "sans
         contrainte" (environnement de travail indépendant de l'outil
         actuel).
      2. Un environnement de test/déploiement à distance dans le même
         esprit qu'un notebook Jupyter, avec un "pseudo navigateur" /
         "pseudo bureau web" accessible à travers le VPN et propulsé
         par cette même coquille Docker -- pour déployer et tester à
         distance depuis ce serveur en ligne.
    **PAS COMMENCÉ** -- juste noté, très en amont : ni la technologie
    VPN retenue, ni le choix des outils kanban/dépôt de fichiers/
    bureau web, ni l'architecture réseau précise (comment le canal
    sortant s'articule avec le reste du stack, sécurité de ce canal)
    ne sont tranchés -- à cadrer ensemble le moment venu.
24. Volet "transparence" de l'écran Cyber -- deux volets demandés
    explicitement ("suite des travaux d'urgence par un volet
    transparence"), **TOUS DEUX LIVRÉS** :
    1. Historique versionné de la matrice de risques -- **LIVRÉ en
       #199** -- table `cyber_risks_history`, instantané complet à
       chaque création/modification/suppression, nouvel onglet
       "Historique" dans `CyberView.jsx`. Voir `hub/README.md`.
    2. Vue graphique de l'architecture large du projet (ressources,
       clés de conf, stacks et projets externes) -- **LIVRÉ en
       #207** -- `docs/architecture-projet.svg`, route
       `GET /architecture-diagram` (`prefs-api`), nouvel onglet
       "Architecture" dans `CyberView.jsx`. Un vrai débordement de
       texte trouvé et corrigé en vérifiant VISUELLEMENT le rendu
       (jamais fait confiance aux coordonnées calculées seules).
       Fichier statique -- à régénérer manuellement si l'architecture
       évolue significativement (pas de mécanisme de mise à jour
       automatique).
25. Traçabilité DEBUG systématique ("rien ne doit être silencieux"),
    demandé explicitement -- "vérifier que toutes les étapes soient
    logguées en debug... identifier vite les points de blocage".
    **TROUVAILLE DE FOND corrigée en #215** : aucun service ne
    configurait le niveau du logger racine Python -- tout appel
    `logging.debug()` était silencieusement rejeté AVANT même
    d'atteindre un handler, quel que soit `LOG_CAPTURE_LEVEL`.
    Corrigé de façon CENTRALISÉE dans `shared/log_buffer.py` --
    s'applique automatiquement aux ~30 services existants. Voir
    `shared/LOGGING_CONVENTIONS.md` pour la convention complète
    (règle absolue : jamais un secret dans un log, à aucun niveau).
    **Couvert en #215-217** : toute la chaîne chiffrement/
    authentification de cette session (`secret_crypto.py`, les deux
    `credential_crypto.py`, `tunnel_process.py`/`mount_process.py`,
    `snmp_client.py`, `secrets_tool.py`/`secrets_alert.py`) --
    chantier de cette session TERMINÉ. **Audit rétroactif TERMINÉ en #225** -- les 19 modules antérieurs
    identifiés (#223) avec des opérations réseau/subprocess sont tous
    traités (#223 : ldap_client.py, glpi_client.py, nebula_client.py,
    mayan_client.py, imap_wrapper.py, dba/connectors/mysql.py+
    postgres.py (connexion), vault/admin-api send_alert_email,
    tickets/google_oauth.py ; #224 : cacti, owncloud (x2), ipam,
    optick, zenoss, geo-import, rsyslog-listener ; #225 : tts-gu,
    pixel-grid/api, schema-analyzer/api, tickets/backup_manager.py)
    -- couverture PRAGMATIQUE (points de passage réseau uniques +
    établissement de connexion/session, pas un traçage exhaustif
    méthode par méthode comme pour la chaîne de #215-217).
    `dba/connectors/postgres.py` reste PARTIELLEMENT couvert par choix
    assumé (seule `_connect`, le point le plus à risque, est tracée --
    les 13 méthodes CRUD restantes en bénéficient déjà indirectement).
    Deux points critiques trouvés et vérifiés explicitement avec des
    valeurs distinctives injectées dans le VRAI chemin de code :
    le DSN PostgreSQL d'ogr2ogr (#224, `geo-import`, mot de passe en
    clair dans la commande) et les URLs de fournisseurs géo
    surchargeables via `.env` (#225, `pixel-grid`, clé d'API
    hypothétique). Un vrai bug trouvé et corrigé en testant (#223,
    `ldap_client.py` : mauvaise clé de config utilisée dans une
    trace). Voir `shared/LOGGING_CONVENTIONS.md`.

    **Extension #276** -- en continuant ce chantier après plusieurs
    nouveaux modules construits depuis #225 : `classifier-api` et
    `tasks-api` vérifiés SANS aucun appel réseau/subprocess propre
    (services purement locaux, SQLite) -- rien à tracer là, cohérent
    avec la convention (pas un oubli). En revanche, `glpi/api/app.py`
    (les SIX appels directs vers nebula-api/network-agent-api/
    classifier-api/snmp-api ajoutés #264-#270) et **`zenoss/api/app.py`
    dans SON ENSEMBLE** (SIX routes avec une connexion MySQL sans
    AUCUNE trace, pas seulement la nouvelle route #268 -- trouvaille
    plus large que prévu en vérifiant) étaient silencieux sur leurs
    échecs réseau/DB. Corrigé -- douze points de passage tracés au
    total, vérifiés en injectant une VRAIE panne (connexion refusée,
    statut HTTP erroné) et en confirmant la trace dans les logs
    capturés, pas seulement la présence syntaxique de l'appel.

26. Nouvelle tuile/outil "gestionnaire de fichiers". Demandé
    explicitement, trois volets :
    - Vue de la GED organisée comme une exploration arborescente
      (par opposition à la présentation actuelle -- à voir ce que ça
      change concrètement côté `ged`/Mayan).
    - Navigation en accès arborescent aux systèmes de fichiers
      MONTÉS (lesquels précisément -- volumes Docker, montages
      SSHFS via `ssh-tunnels`, autre chose ?).
    - Une brique "espace/système de fichiers protégé du HUB",
      accessible AUSSI par l'hôte (donc pas seulement depuis
      l'intérieur d'un conteneur -- implique un montage/volume
      partagé avec la machine hôte elle-même).
    **✅ LIVRÉ en #397** -- trois volets livrés d'un coup :
    - Espace protégé du hub (répertoire hôte, navigation arborescente,
      protégé par rights-api, métadonnées uniquement).
    - Documents GED (agrégé depuis ged-api, lecture seule).
    - Partages SSHFS (agrégé depuis ssh-tunnels-api, stats espace/inodes).
    **⚠️ Non vérifié dans cet environnement** : accès réseau réel à
    ged-api/ssh-tunnels-api (réseau restreint). Logique testée en profondeur
    avec des scénarios simulés.
    **CONFIRMÉ IDENTIQUE À L'ITEM 9 (étape 2)** par la personne --
    à trancher ensemble le moment venu.
    **CONFIRMÉ IDENTIQUE À L'ITEM 9 (étape 2)** par la personne --
    ce chantier ET "promouvoir ged au même niveau que les fronts
    principaux, étape 2" sont LA MÊME chose, pas deux items
    distincts à traiter séparément.

27. Nouvelle tuile "backup-restore". Demandé explicitement, plusieurs
    volets :
    - Connecteur BackupPC (3.2.1) -- vue HUB du contenu + versions ;
      lié à l'exploration LAN existante (Nebula, GLPI) : toute
      machine détectée doit avoir un backup identifié.
    - Connecteur Clonezilla -- gestion automatisée liée à la
      détection sur le LAN : toute machine doit avoir une image
      prête à la restauration.
    - Proposer une AUTRE solution de backup open source plus récente
      (comparatif fonctionnalités + apparence/ergonomie à fournir).
    - Fonctionnalités ATTENDUES : agent Windows 10/11, Linux, Mac ;
      API pour développer une vision propre au projet ; restauration
      TFTP/SFTP ou boot clé USB.
    - Fonctionnalités ESPÉRÉES : image complète RAW.
    - Fonctionnalités À DÉVELOPPER PAR L'API (au-delà de ce que les
      outils backup fournissent nativement) :
      - Statistiques/versions de fichiers sur l'ensemble des
        sauvegardes -- navigation dans les versions locales,
        reconstitution des versions/forks et de l'historique sous
        forme de graphe.
      - Agent/service dédié courrier électronique : indexation/
        recherche sur les boîtes locales Thunderbird (AVEC accord de
        l'utilisateur) ; indexation/recherche sur les boîtes IMAP
        côté serveur ; archivage pour rémanence des boîtes avec
        gestion de l'oubli et export pour extraction physique.
    **PAS COMMENCÉ, MAIS URGENCE SIGNALÉE PAR LA PERSONNE (2026-09-03)**
    sur UN sous-volet précis : Clonezilla (ou équivalent) pour
    produire une IMAGE SYSTÈME complète -- objectif immédiat = future
    VIRTUALISATION de postes Windows existants (10/11). Chantier vaste
    avec plusieurs sous-parties de tailles très différentes -- ce
    sous-volet EST la priorité si ce chantier démarre, le reste (BackupPC,
    solution alternative, API de statistiques, agent courrier) reste à
    cadrer et prioriser ensemble le moment venu, jamais présumé d'un bloc.

    **SUIVI/COUVERTURE LIVRÉ EN #249** (le sous-volet urgent lui-même,
    PAS l'automatisation réelle de Clonezilla -- hors de portée
    sans infrastructure matérielle à tester, même raisonnement que
    pour #233) -- nouveau module `backup-restore/` : registre des
    images connues (saisie manuelle pour l'instant), `GET /coverage`
    croise les appareils DÉCOUVERTS par `network-agent` avec ce
    registre -- répond directement à "toute machine détectée doit
    avoir une image". Tuile hub "Sauvegardes" (menu Général).
    ⚠️ Point d'architecture : `network-agent-api` tourne en
    `network_mode: host` (#238-239) -- `backup-restore-api` le
    joint via `HOST_IP`, jamais le nom de service Docker habituel
    (même piège déjà rencontré pour la passerelle, reproduit ici en
    connaissance de cause). Voir `backup-restore/README.md`.

28. Nouvelle tuile "référentiel SI" / recherche type Elasticsearch.
    Demandé explicitement, plusieurs volets :
    - Intégrer SYSTÉMATIQUEMENT et AUTOMATIQUEMENT toutes les API du
      projet dans les index (chaque nouveau module s'y retrouverait
      sans câblage manuel -- mécanisme à concevoir).
    - Générateur / aide à la conception de requêtes.
    - Menus de recherche + vision thématique des données.
    - Analyse/indexation des métadonnées ET du contenu des documents
      lisibles.
    - Interface de recherche "full text" tous supports/systèmes.
    - Interface/menu sur un index mots et expressions.
    - Interface/menu sur titre, chemin/dossier, date, révisions,
      auteur, sources, format -- et thèmes.
    - Interface type "big data" : réponse progressive/différée, push
      de notification. Objectif explicite : NE PAS saturer les
      systèmes/services impactés par la recherche elle-même.
      Implique la conception d'agents avec gestion de disponibilité
      (de l'information -- type `locate` Unix -- de la charge
      système, de la progression/reprise de recherche) et un RÉSEAU
      D'AGENTS avec interactions directes inter-agents pour diffuser
      une recherche.
    - Intégrer l'index des adresses IP.
    - Intégrer l'index des localisations.
    - Construire un index des contrats/dossiers/propositions/
      factures à partir de l'analyse des titres de répertoire,
      chemins, documents.
    - Détecter et centraliser les documents référençant des mots de
      passe, accès, URL... à des fins de protection, indexation et
      alerte.
    - Proposer un référentiel des données cyber sensibles.
    **PAS COMMENCÉ** -- juste noté. Chantier le plus vaste de ce
    backlog, touche potentiellement TOUS les modules existants --
    architecture d'ensemble (moteur de recherche retenu, mécanisme
    d'intégration automatique, réseau d'agents) à concevoir et
    valider ensemble avant tout code, jamais présumée seule vu
    l'ampleur.
    **Cadrage donné par la personne (2026-09-03)** : à construire
    PROGRESSIVEMENT, en suivant les prescriptions ISO/IEC 27001 (pas
    un chantier monolithique -- une trame de référence existe déjà pour
    prioriser les étapes, à mettre en regard de la conception
    d'ensemble ci-dessus le moment venu).

29. Nouvelle tuile "main2dieu" -- tour de contrôle. Demandé
    explicitement :
    - Centraliser la gestion des liens sensibles (tunnels SSH,
      SSHFS, agents).
    - Double validation de l'ouverture d'un lien (courriel, SMS,
      application mobile).
    - Temporisation avec alerte de fermeture.
    - Tableau de bord on/off + erreurs sur tous les services/liens.
    - Automate : gestion cron/activation/script/désactivation +
      alerte + commande SMS (réception d'un accord/interdiction via
      la passerelle SMS, avec clé SSL).
    **Objectifs clarifiés par la personne (2026-09-03)** :
    - Objectif FONDAMENTAL : pouvoir couper les entrées/liens
      critiques SUR ALERTE ou SUR COMMANDE (jamais seulement les
      ouvrir/superviser -- la coupure rapide est le cœur du besoin).
    - Objectif NATUREL (découle du premier) : identifier et
      superviser ces mêmes liens en continu.
    **PAS COMMENCÉ** -- juste noté. **CONFIRMÉ par la personne** :
    recoupe directement des briques déjà construites cette session
    (`ssh-tunnels` #210-213 pour les tunnels/authentification,
    `trb140-sms-relay` #206 pour le canal SMS) -- s'appuiera dessus
    plutôt que de les dupliquer. Le modèle de "double validation"/
    temporisation reste entièrement à concevoir.

<!-- Keycloak/tls-proxy hors du stack principal : LIVRÉ en #134 (prérequis
     résolution DNS dynamique) + #135 (extraction vers gateway/) -- voir
     gateway/README.md et tls-proxy/README.md pour le détail complet. -->

30. Nouvelle tuile "Rétro-ingénierie" -- demandée explicitement
    (2026-09-03), un outil d'analyse de code PHP, deux volets :
    - Déterminer les relations dans une base SQL à partir du code
      PHP (là où `schema-analyzer` déduit les relations depuis le
      SCHÉMA + les DONNÉES -- #151, #241 -- cet outil les déduirait
      depuis le CODE lui-même : requêtes SQL embarquées, jointures
      explicites, usages de clés étrangères dans les requêtes
      applicatives).
    - Proposer un schéma FONCTIONNEL de l'interface -- reconstituer,
      à partir du code, la structure/l'organisation fonctionnelle de
      l'application (écrans, actions, flux) plutôt que seulement sa
      structure de données.
    **PAS COMMENCÉ** -- juste noté. Portée technique (quel(s)
    framework(s)/style(s) PHP visés -- procédural ancien style,
    orienté objet, un framework précis type Symfony/Laravel ?
    parsing réel du PHP ou heuristiques par expression régulière sur
    les requêtes SQL ?), articulation avec `schema-analyzer`
    (chantier complémentaire ou fusionné ?) et modèle de rendu du
    "schéma fonctionnel" (texte, diagramme, les deux ?) -- tout reste
    à cadrer ensemble avant de coder.

    **VOLET 1 LIVRÉ EN URGENCE en #243** -- contexte réel donné par
    la personne : vieille appli Fat-Free (F3), aucune documentation,
    prédécesseur qui gardait les schémas "en tête". Nouveau module
    `retro/` : `php_sql_scanner.py` extrait des relations SQL
    CANDIDATES depuis du code PHP par expression régulière (jointures
    modernes ET ancien style avec virgules dans le FROM -- un vrai bug
    de couverture trouvé et corrigé en testant ce second motif,
    exactement celui décrit par la personne comme présent dans son
    code), plus le motif Fat-Free `Mapper`. `POST /scan` (archive
    ZIP), onglet hub "Rétro-ingénierie" (menu Data). **Volet 2
    ("schéma fonctionnel de l'interface") LIVRÉ en #441** par l'usage
    réel : extension Firefox + agent relais + API « parcours » (étapes,
    routes, tables du code et du journal SQL via dba-api, carte
    fonctionnelle) ; #443 : rejeu pas à pas, rejeu réel, sous-parcours,
    comparaison ; #444 : (2) interface générée au design du hub (spec
    par application, listes/fiches sur les tables réelles) ; #445 : (3) outil
    unique (fonctions communes entre applications, spec unifiée rendue sur
    les données de chaque application) ; #448 : (4) méta-graphe des
    entités et relations (code, journal SQL, noms), équivalences et
    références inter-gestions, proposition de fusion. Les quatre phases
    demandées sont livrées ; suite possible : DDL cible généré depuis la
    proposition.
    Reste : premier parcours réel dans Firefox, vrai general_log. Voir
    `retro/README.md`.

    **EXTENSION LIVRÉE EN #245** -- demandé explicitement juste
    après le volet 1 : "importer du php et des vues d'écran en html
    puis d'en déduire une partie des structures de données". Vérifié
    via recherche AVANT de coder : syntaxe réelle du moteur de
    gabarits Fat-Free natif (`{{@variable}}`, `<repeat>`) confirmée
    par la documentation officielle. Nouveau `html_view_scanner.py`,
    trois signaux : champs de FORMULAIRE (le plus fiable), accès aux
    champs en gabarit F3 natif, accès aux champs en PHP BRUT AFFICHÉ
    (les applications plus anciennes utilisent souvent des vues PHP
    classiques -- la personne a signalé que le code varie "selon les
    époques"). `/scan` balaie désormais aussi `.phtml`/`.html`/`.htm`
    en plus de `.php`, les DEUX scanners tournant sur chaque fichier.
    Fusion des résultats de plusieurs écrans par variable de gabarit.
    **URGENCE CONFIRMÉE par la personne (2026-09-03)**, au même titre
    que le sous-volet Clonezilla de l'item 27 -- ce chantier n'est pas
    secondaire, priorité immédiate le temps de la tâche de
    modification de données en cours.

    **CORRECTIF LIVRÉ EN #246** -- limite connue corrigée : une
    auto-jointure HIÉRARCHIQUE légitime (ex. `employes e1 JOIN
    employes e2 ON e1.manager_id = e2.id` -- exactement le genre de
    structure visée à l'origine de ce chantier) était exclue à tort
    par le filtre anti-doublon trivial. Corrigé : le test porte
    désormais sur les alias eux-mêmes, pas sur la table résolue --
    une auto-jointure légitime est capturée et marquée
    `is_self_reference: true`, badge "🔀 hiérarchique" côté hub.

    **LIAISON DIRECTE VERS SCHEMA-ANALYZER LIVRÉE EN #247** -- ferme
    la boucle "repérer ici, confirmer là-bas" : bouton "→ Envoyer"
    par relation candidate (sélection préalable d'une connexion
    DBA), crée directement une relation PROPOSÉE dans
    `schema-analyzer` -- plus besoin de recopier à la main. Aucune
    confirmation automatique, la validation contre les données
    (#241) reste une étape manuelle ensuite.

    **SECOND VOLET ("SCHÉMA FONCTIONNEL") LIVRÉ EN #248** -- le
    volet demandé à l'origine, jamais commencé jusqu'ici. Nouveau
    `route_scanner.py` : extrait les routes déclarées
    (`$f3->route(...)` OU `F3::route(...)`), regroupées par
    CONTRÔLEUR -- la vue "quels écrans/actions gère ce
    contrôleur". **⚠️ Version de Fat-Free NON CONFIRMÉE** -- la
    personne pense qu'il s'agit de la lignée 2.x, sans certitude ;
    recherché explicitement, les deux syntaxes d'appel semblent
    avoir coexisté sur une large part de l'historique F3 (pas
    strictement l'une en 2.x et l'autre en 3.x comme d'abord
    supposé), ce scanner couvre donc les deux -- aucune
    documentation officielle spécifique à la lignée 2.x trouvée,
    les résultats réels sur le vrai code restent le meilleur
    signal. Voir `retro/README.md`.

    **PAUSE DEMANDÉE PAR LA PERSONNE (2026-09-03)** -- "mon souci de
    rétro ingénierie urgente est réglé, c'était du code bricolé avec
    des clauses aberrantes sûrement dû à du débogage non nettoyé,
    mais ça sera utile dans l'avenir on y reviendra donc pause pour
    ça". Chantier VOLONTAIREMENT mis en pause, pas abandonné -- les
    deux volets demandés à l'origine sont livrés et fonctionnels
    (#243-248), reste ouvert pour y revenir plus tard.

31. Nouvelle tuile "Architecture réseau" -- demandée explicitement
    (2026-09-03), en deux temps :
    - **Vue/outil de parcours** (#253) : "quand un équipement remonte
      dans la supervision zenoss je dois pouvoir identifier les
      interfaces en amont, en aval et les accès pour agir sur
      l'équipement, je dois aussi identifier les lieux d'intervention
      si des déplacements sont nécessaires, je dois pouvoir trouver
      les documentations liées aux contrats, aux spécifications
      techniques et aux paramètres spécifiques" -- même besoin pour
      un dysfonctionnement (saturation, abus de protocole, DDoS...).
    - **Supervision/suivi de fonctionnement** (#254) : "pouvoir
      identifier les niveaux d'usage et anticiper les engorgements...
      pouvoir justifier des investissements en présentant les taux
      d'usages et les variations".
    **LIVRÉ EN #253-254** -- reconnaissance faite AVANT de coder :
    localisation déjà dans `zenoss-api` (`/location_tree`),
    accès déjà dans `ssh-tunnels-api`, documents déjà via le
    mécanisme de liaison polymorphe de la GED (#158) -- ce module
    n'apporte QUE la pièce manquante : la topologie amont/aval
    DÉCLARÉE (connaissance métier, jamais déduite automatiquement du
    trafic, contrairement aux échanges observés par `network-agent`
    #250) et les niveaux d'usage croisés depuis l'historique déjà
    construit en #251 (taux de variation calculé entre premier et
    dernier relevé). Nouveau module `architecture/` -- registre
    d'équipements/interfaces/liens, route centrale
    `GET /equipment/<id>/overview` agrégeant tout en un seul appel,
    chaque croisement BEST-EFFORT et signalé indépendamment (une
    source indisponible ne masque jamais les autres). Tuile hub
    (menu Réseau). Voir `architecture/README.md` pour le détail
    complet, y compris la localisation Zenoss volontairement
    différée (structure en arbre côté Zenoss, pas de recherche
    directe par équipement -- **LIVRÉ EN #268**, plus simple que prévu :
    requête ciblée `GET /device_location`, jamais besoin de parcourir
    l'arbre complet. Les QUATRE volets de la demande d'origine sont
    désormais TOUS livrés). **Import automatique depuis
    Exploration réseau LIVRÉ EN #263** (`POST /import/network-agent`,
    idempotent, personnalisations jamais écrasées) -- import GLPI
    VOLONTAIREMENT non entamé, confirmé par la personne (2026-09-03) :
    "glpi n'est pas encore utilisé il est presque vide" -- rien à en
    tirer tant que cet inventaire n'est pas réellement peuplé.

32. Nouvelle tuile "Mémoire" (hub) + api/service de rémanence du
    memcached. Demandé explicitement (2026-09-03) : "api/service de
    rémanence du memcached, tuile mémoire du hub : un outil à faible
    impact et simplement supervisé qui va récupérer les kv du
    memcached régulièrement et les stocke en base... avec un
    mécanisme de repopulation du memcached et avec un garbage
    collector ou un timeout de remise en ligne, avec une interface
    d'accès et de calcul pour naviguer dans les historiques et
    calculer dessus... à relier aux autres données". **PAS COMMENCÉ**
    -- rejoint directement la limite déjà documentée ailleurs dans ce
    projet (logs via `shared/log_buffer.py`, volontairement SANS
    persistance par conception -- perte confirmée à chaque redémarrage
    du conteneur `memcached`, voir échange avec la personne du
    2026-09-03 sur ce sujet précis). Plusieurs volets distincts à
    cadrer :
    - Collecte PÉRIODIQUE des clés/valeurs de `memcached` vers un
      stockage persistant (SQLite, cohérent avec le reste du projet) --
      "à faible impact" et "simplement supervisé" à préciser
      concrètement (fréquence, ce qui compte comme un incident à
      signaler).
    - REPOPULATION de `memcached` depuis cet historique -- après un
      redémarrage du service memcached, réinjecter les valeurs
      récentes plutôt que repartir strictement à vide.
    - Nettoyage/rétention -- "garbage collector ou timeout de remise
      en ligne" : mécanisme à définir précisément (purge des entrées
      trop anciennes ? détection qu'une clé n'a plus été vue en
      mémoire depuis X temps ?).
    - Interface de navigation ET DE CALCUL sur l'historique -- pas
      seulement consulter, mais calculer (agrégations, tendances ?)
      -- à préciser à quoi ressemblent les calculs voulus.
    - "À relier aux autres données" -- rejoint l'esprit des
      croisements déjà pratiqués ailleurs (GED/ssh-tunnels/
      network-agent depuis `architecture-api`, #253-254) -- lien
      exact à définir une fois le socle de collecte en place.
    **LIVRÉ EN #259** -- nouveau module `memory/`. Portée
    VOLONTAIREMENT SCOPÉE au tampon de logs partagé
    (`shared/log_buffer.py`, #145), jamais un "tout Memcached"
    générique -- raison technique réelle : Memcached n'offre pas
    de "lister les clés existantes", donc seules les clés
    ÉNUMÉRABLES (28 `SERVICE_NAME` internes recensés + registre
    `pushed_log_sources` déjà existant pour les sources externes)
    sont collectées. Collecte périodique (5 min par défaut),
    repopulation testée avec un vrai aller-retour Memcached
    (redémarrage simulé, tampon reconstruit dans le bon ordre),
    rétention bornée (30 jours par défaut, même motif que
    `network-agent`/#251). Tuile hub "Mémoire" (menu Général) --
    statistiques par service (le "calcul" demandé) + navigateur
    d'historique filtrable. Voir `memory/README.md`.


33. Collecte transversale d'informations d'identité (nom
    d'équipement, IP, lieu) apparaissant dans les différents
    modules. Demandé explicitement (2026-09-03), immédiatement après
    l'item 32 (Mémoire) : "je voudrais collecter toutes les
    informations du type nom d'équipement, ip, lieu qui apparaissent
    dans les différents modules". **PAS COMMENCÉ**. Rejoint l'esprit
    de `architecture-api` (#253-254, qui croise déjà GED/ssh-tunnels/
    network-agent EN DIRECT pour UN équipement précis) mais en
    sens inverse : PLUTÔT qu'interroger plusieurs sources pour UN
    équipement connu, ici il s'agit de PARCOURIR les sources
    (GLPI, Zenoss, network-agent, Nebula, IPAM, architecture-api
    elle-même...) pour EN EXTRAIRE toutes les identités rencontrées
    (nom/IP/lieu), probablement pour les rapprocher/dédupliquer
    entre elles. Rejoint aussi l'esprit de l'item 28 (référentiel
    SI/recherche type Elasticsearch, jamais commencé) -- à cadrer
    ensemble si les deux se recoupent, jamais présumé d'un bloc.

34. Classification sémantique/relationnelle des identités découvertes
    -- **PRIORITÉ FORTE SIGNALÉE PAR LA PERSONNE ("à prioriser fort
    car central")**, 2026-09-03. Observation concrète de la personne,
    en copiant du texte depuis la liste des appareils découverts par
    Exploration réseau (#250, résolution DNS) : des noms d'hôte comme
    "ups", "alice", "bob", "nms", "dhcp139" (avec l'IP se
    terminant en .139) portent chacun un SENS différent -- "tout ça a
    du sens : des personnes/login, des clients IP dynamique (à priori
    wifi), des services névralgiques...". **PAS COMMENCÉ**. Rejoint
    directement l'item 33 (collecte transversale d'identités) mais
    va plus loin -- deux volets distincts demandés :
    - **Classification AUTOMATIQUE** des noms/identités découverts en
      catégories sémantiques (ex. login/personne, client DHCP
      dynamique probablement WiFi, équipement d'infrastructure comme
      un onduleur/"ups", service névralgique comme "nms"). Reste à
      définir COMMENT (motifs de nommage ? rapprochement avec un
      annuaire existant -- LDAP/Keycloak pour les logins ? liste de
      motifs connus pour les équipements type "ups"/"nms" ?).
    - **Mise en relation vers des "automates d'analyse spécifique"**
      SELON la classification obtenue -- "pour évaluer le risque, les
      usages, les ressources consommées". Nature exacte de ces
      automates d'analyse non précisée -- à cadrer avec la personne
      (des analyses déjà existantes dans le projet à réutiliser ? de
      nouveaux outils à construire par catégorie ?).
    Source de données la plus immédiate : les noms d'hôte résolus par
    `network-agent` (#250), mais l'item 33 (collecte transversale)
    suggère une portée plus large, à travers plusieurs modules -- les
    deux items à cadrer ensemble avant de commencer, jamais présumé
    d'un bloc.

    **PREMIER AUTOMATE LIVRÉ EN #260** -- classification
    automatique + interface d'import de dictionnaires (demandée
    explicitement en cours de conception). NLTK vérifié NON
    installable dans cet environnement (et de toute façon non
    pertinent -- ses corpus généralistes ne couvrent pas le
    vocabulaire réseau/télécom demandé). Nouveau module
    `classifier/` -- dictionnaires importables par catégorie
    (jamais codés en dur), motif structurel dhcpNNN reconnu
    directement, stats d'usage PAR TERME ("quels mots servent
    vraiment"), orientation manuelle (confirmer/corriger une
    classification, avec enrichissement du dictionnaire sur
    action explicite). Testé contre le VRAI jeu de données
    partagé par la personne (20 appareils réels de sa liste
    Exploration réseau) -- un bug de motif dhcp trouvé et corrigé
    au passage (ancrage sur la chaîne entière au lieu du token).
    Tuile hub "Classification" (menu Data). **Intégration avec
    Exploration réseau LIVRÉE EN #261** -- badge de classification
    affiché à côté de chaque nom d'hôte découvert, côté hub (aucun
    couplage backend-à-backend). Voir `classifier/README.md`.
    **Reste PAS COMMENCÉ** : la mise en relation vers des "automates
    d'analyse spécifique" (risque/usage/ressources) SELON la
    classification -- volet suivant, nature exacte encore à cadrer.

    **PREMIERS AUTOMATES LIVRÉS EN #262** -- nouveau module
    `vigilance/`, ciblé sur la catégorie "client DHCP dynamique"
    (confirmé par la personne : "OUI j'aime c'est tout à fait le
    genre d'analyse que je veux, sois créatif et si possible cible
    les éléments de cyber vigilance et de santé du parc et du
    réseau"). Trois signaux : contact avec de l'infrastructure
    (violation de segmentation potentielle, sévérité critique),
    diversité de services élevée, croissance de volume anormale.
    Croise `network-agent` et `classifier` EN LECTURE, aucune
    nouvelle collecte. Testé avec un scénario reproduisant les
    vraies données de la personne -- confirmé qu'un appareil au
    profil NORMAL n'est jamais signalé à tort. Tuile hub
    "Vigilance" (menu Général, à côté de "Cyber"). Voir
    `vigilance/README.md`. Seuils non validés sur un vrai réseau
    chargé, signaux supplémentaires et autres catégories
    envisageables pour une prochaine tranche.

35. Docker de tunnel SSH + front de commande de déploiement/tests,
    à exécuter sur la MACHINE PERSONNELLE de la personne pour
    atteindre son infrastructure réelle depuis un endroit où elle ne
    peut rien déployer directement. Demandé explicitement
    (2026-09-03) : "là où je suis je ne peux rien déployer... un
    docker permettant de créer un tunnel ssh et un front de commande
    de déploiement et de tests qui donnera à un client web sécurisé
    local déployé sur ma machine perso". **PAS COMMENCÉ**. Rejoint
    l'esprit de l'item 23 (coquille Docker générique + VPN) mais dans
    le SENS INVERSE -- l'item 23 étend la portée du hub VERS un
    serveur distant (Proxmox OVH), initié PAR le hub ; ici c'est la
    personne qui a besoin d'ATTEINDRE son infrastructure réelle
    (où tourne le vrai `docker-compose`) DEPUIS un endroit où elle
    n'a pas la main directement, via un outil local sur sa PROPRE
    machine. Plusieurs volets à cadrer avant de commencer, aucun
    tranché pour l'instant : quelle machine/serveur le tunnel SSH
    cible-t-il exactement (probablement là où `docker-compose` tourne
    réellement) ; quelles commandes le "front de déploiement et de
    tests" doit-il exposer précisément (rebuild d'un service, lecture
    de logs, exécution de tests -- ou plus) ; niveau de sécurité
    attendu pour ce client web local ("sécurisé" mentionné
    explicitement, sans détail) ; articulation avec l'item 23 si les
    deux se recoupent effectivement une fois cadrés plus précisément.

36. Générateur de code/front/api à partir d'un schéma relationnel --
    créerait automatiquement les interfaces de gestion (CRUD) pour
    manipuler les données d'un schéma donné. Demandé explicitement
    (2026-09-03), en complément de l'éditeur de relations
    (`schema-analyzer`) : "un générateur de code/front/api qui à
    partir d'un schéma relationnel crée les interfaces de gestion
    pour manipuler les données d'un schéma relationnel. ex: l'appli
    actuellement fatfree/php/mysql qui gère des tickets complexes".
    **PAS COMMENCÉ** -- chantier de taille bien plus large qu'une
    simple extension, plusieurs décisions structurantes à cadrer
    ensemble avant de commencer, aucune tranchée pour l'instant :
    - **Portée du "CRUD généré"** : simple liste/formulaire par table
      (comme l'éditeur de lignes déjà existant dans `dba-api`), ou
      des écrans plus élaborés reflétant les RELATIONS entre tables
      (ex. une fiche "ticket" montrant directement son contact lié,
      comme le fait l'application FatFree citée en exemple) ?
    - **Technologie de sortie** : le code généré vise-t-il à
      remplacer/moderniser une appli FatFree/PHP existante dans SON
      propre langage, ou à produire un nouveau module dans la pile
      technique DÉJÀ utilisée par ce projet (Flask + React, comme
      tous les autres modules) ?
    - **Mode de fonctionnement** : génère-t-il du code SOURCE à
      relire/adapter ensuite (un vrai "scaffold", point de départ
      modifiable), ou une application VIVANTE générique pilotée par
      le schéma en configuration (jamais de fichiers générés,
      readaptée dynamiquement si le schéma change) ?
    - **Source du schéma** : réutilise-t-il directement les relations
      déjà confirmées dans `schema-analyzer` (#152, tout juste
      enrichi en #267 d'une sélection graphique) comme point de
      départ, ou un mécanisme de définition de schéma séparé ?
    Rejoint l'esprit de plusieurs chantiers déjà réalisés dans ce
    projet (rétro-ingénierie #243-248 pour EXTRAIRE un schéma depuis
    du code existant, éditeur de relations #152/#267 pour le
    CONFIRMER) -- celui-ci irait plus loin, jusqu'à PRODUIRE une
    interface de gestion utilisable, jamais tenté jusqu'ici.

37. ENT — Calendrier (`CalendarView.jsx`, import par adresse secrète
    iCal, #272) : deux demandes explicites (2026-09-04), en plein
    test réel de déploiement. **LIVRÉ en #282** -- les trois points
    ci-dessous, voir `tickets/README.md` pour le détail complet du
    raisonnement (choix par défaut faits sans attendre un cadrage
    complet, la personne ayant dit "lance-toi").
    - Le bouton "Importer" est silencieux et invariant pendant
      l'appel réseau -- aucun retour visuel (ni indicateur de
      chargement, ni changement d'état du bouton) pendant que
      l'import est en cours, seul le résultat final (compteurs
      créé/déjà connu) apparaît après coup. Demande explicite : une
      prise en compte VISIBLE dès le clic (ex. bouton désactivé +
      libellé "Import…" pendant l'appel, motif déjà utilisé ailleurs
      dans ce même fichier pour d'autres actions -- à vérifier
      pourquoi CE bouton précis n'a pas le même traitement, avant de
      corriger).
    - Un filtre par motif à joker sur le titre des événements, du
      genre `*SAV*DEV*` (astérisques = n'importe quoi entre/autour),
      avec un interrupteur ON/OFF pour la sensibilité à la casse.
      Emplacement exact à cadrer : un filtre supplémentaire à côté du
      filtre déjà existant (non affectés/affectés/tous), appliqué
      côté hub (sur les événements déjà chargés) ou côté API
      (nouveau paramètre sur `GET /calendar/events`) -- à trancher
      selon le volume réel d'événements en jeu, jamais présumé pour
      l'instant. Conversion `*SAV*DEV*` -> expression régulière à
      construire (échapper les caractères spéciaux du motif SAUF les
      `*`, les remplacer par `.*`) -- même famille de motif que la
      recherche par mot-clé déjà existante (`matching_config`,
      `trigger_keyword`) mais un usage DISTINCT (filtrer l'AFFICHAGE,
      pas détecter un ticket à suggérer) -- jamais présumé que c'est
      la même chose sans le vérifier avec la personne.
    - **Suite de note (2026-09-04)** : à droite de la liste des
      événements calendrier importés, une VUE CALENDRIER des tickets
      (pas juste une liste comme les événements à gauche). Points à
      cadrer avant de coder, jamais présumés : quel CHAMP de date
      afficher (`deadline_ts` déjà existant sur `tickets`, semble le
      plus naturel pour une vue "calendrier", mais pourrait aussi
      être `ts_created` ou les deux) ; le périmètre de tickets à
      afficher (tous ? seulement ouverts ? avec échéance définie
      uniquement, en excluant silencieusement ceux qui n'en ont
      pas ?) ; la granularité de la vue (jour/semaine/mois -- une
      vraie grille calendrier, pas la vue agenda en liste déjà
      choisie à gauche pour les raisons de vérifiabilité expliquées
      dans `tickets/README.md`, donc peut-être un choix différent ici
      si une vraie grille est explicitement voulue pour CETTE
      colonne) ; et si un lien visuel/interaction est voulu entre un
      ticket affiché ici et l'événement calendrier qui l'a
      potentiellement créé (traçabilité déjà existante côté
      backend via `ticket_time_entries`, jamais exposée comme telle
      dans l'interface pour l'instant).

38. Suite de la gestion des droits (#283) -- deux points des
    spécifications originales :
    - **Brancher rights-api sur les ~40 autres API du projet**
      ("la gestion des droits... impacte toutes les api"). ✅
      **TERMINÉ** (#289-331, 43 livraisons) -- les ~32 services du
      projet sont désormais soit branchés (20, dont tickets-api à
      lui seul avec 19 routes gardées sur ses 85, en 8 passes
      distinctes), soit confirmés sans rien à y brancher (lecture
      seule ou sans état persisté). Détail complet de chaque
      décision dans le README de CHAQUE service concerné (jamais
      répété ici) -- `tickets/README.md`, section "Branchement
      rights-api", pour le chantier le plus large. Limite CONNUE et
      assumée, non résolue : `snmp-api` (`/query`/`/walk-interfaces`
      avec `target_id` enregistré mériterait une garde conditionnelle
      plus fine, voir `snmp/README.md`).
    - **La tuile ENT devient une "super tuile"** contenant des
      sous-tuiles dédiées : calendrier partagé, webmail (la personne
      elle-même note "à voir" -- pas encore décidé), GED, et une vue
      "relations" (liens événement-utilisateur-document-message-
      ticket). **GED ✅ ajoutée en #334** -- réutilise `GedView.jsx`
      telle quelle (dépôt de fichiers interne déjà existant,
      confirmé par la personne comme réponse au besoin webmail),
      quatrième onglet de `EntView.jsx` aux côtés de Calendrier/
      Tâches/Validation. **Webmail** toujours "à voir", pas ajouté.
      **Vue "relations" -- LES 4 FORMES DE RELATION DIRECTE ✅
      LIVRÉES** (#335-338, service `relations-api` sans état propre
      -- interroge tickets-api/ged-api/tasks-api/pixel-grid-api à la
      volée). Modèle CLARIFIÉ par la personne (2026-09-04) : relation
      DIRECTE = marqueur commun identique (nom/label, IP, proximité
      géographique, proximité sémantique) ; relation INDIRECTE = un
      attribut associé à un élément direct ou à un ENSEMBLE -- deux
      éléments d'un même ensemble sont en relation indirecte l'un
      avec l'autre, RÉELLEMENT observable depuis qu'une entité peut
      porter plusieurs marqueurs distincts (#336). Détail complet de
      chaque passe (nom exact #335, IP #336, sémantique #337,
      géographique #338 -- seule forme sans correspondance exacte,
      via `pixel-grid-api` en source optionnelle) dans
      `relations/README.md`, jamais répété ici. Interface toujours
      minimale (formulaire type+identifiant), sans graphe visuel ni
      navigation cliquable -- reste à faire, voir "Interface" dans
      `relations/README.md`.

39. Ergonomie ENT/Calendrier — cinq points explicites (2026-09-04).
    ✅ **TOUS LIVRÉS** -- les cinq points, l'écrasante majorité
    construite dès #284 mais jamais explicitement rapprochée de
    chaque point précis du backlog jusqu'à une relecture systématique
    (livraison #333) ; seul le point 4 avait un vrai morceau manquant
    (déclenchement frontend), complété à cette occasion. Voir
    `tickets/README.md` pour le détail complet.

    1. **Badge "Mot-clé détecté" simplifié** -- ✅ déjà livré en #284
       (`hub/src/CalendarView.jsx`) : point orange conservé,
       mini-liste tronquée à 15 caractères au lieu du texte
       permanent, liste complète au survol.

    2. **Liste de retour en arrière sur "Créer un ticket"** -- ✅ déjà
       livré en #284 (`handleCreateTicket`/`handleUndoCreateTicket`,
       `hub/src/CalendarView.jsx`) : "retour en arrière" = suppression
       réelle du ticket créé (`deleteTicket`, scopée aux tickets
       jamais validés côté backend). Liste propre à la session,
       jamais persistée -- confirmé cohérent avec la clarification
       de la personne ("annuler l'opération, une création→suppression").

    3. **"File d'attente" fonctionne comme la tuile Tickets** -- ✅
       déjà livré en #284 (`hub/src/CalendarView.jsx`) : réutilise
       directement `/queue`, mêmes colonnes (# / Sujet / Demandeur /
       Type / Niveau / Statut / Attente) et même tri côté serveur que
       la vraie tuile Tickets. Confirmation VISUELLE par la personne
       encore à faire (son propre point d'attention), mais l'examen
       du code montre une correspondance fidèle.

    4. **Statut automatique selon le moment de l'événement calendrier
       source** -- ✅ backend déjà livré en #284
       (`determine_calendar_statut_label`/`ensure_calendar_statuts`,
       `tickets/api/app.py`) : "Clos"/"En cours"/"Planifié" créés
       automatiquement au démarrage si absents (jamais de doublon à
       chaque redémarrage, vérifié), catégorisation `statuts.type`
       cohérente avec la convention déjà établie (`en_cours`/
       `en_attente`, jamais un statut de clôture). "Planifié" retenu
       -- jamais "En attente" comme option distincte, ambiguïté déjà
       tranchée par le code lui-même à #284. **Manquait le
       déclenchement frontend** ("consultation" jamais câblée en
       pratique, `recalculateTicketStatus` du client jamais appelé
       nulle part) -- complété en #333 : déclenché à chaque
       ouverture/rafraîchissement de la vue Calendrier
       (`hub/src/CalendarView.jsx:load()`), uniquement pour les
       tickets déjà liés à un événement (`assigned_ticket_ids`,
       jamais un appel au hasard sur tout ticket ouvert), en
       best-effort (une erreur individuelle n'empêche jamais
       l'affichage du reste).

    5. **Changements de statut journalisés + validation groupée** --
       ✅ déjà livré en #284 (`hub/src/ValidationView.jsx`, onglet
       "Validation" étendu depuis #273 plutôt qu'une nouvelle tuile)
       : `fetchPendingStatusChanges`/`validateAllStatusChanges`,
       journal PERSISTANT en base (`ticket_status_changes`,
       `validated_at` NULL tant que non validé, jamais supprimé).

    **Vérifié réellement en #333** : chaîne complète recalcul→file
    d'attente→validation groupée→application testée de bout en bout
    (un ticket lié à un événement futur passe bien en attente avec
    le statut "Planifié" proposé, puis réellement appliqué après
    validation groupée -- 4 assertions). Structure JSX de
    `CalendarView.jsx` revérifiée après l'ajout du déclenchement.

40. IMAP/ENT — automates de traitement de messages (2026-09-04).
    **PAS COMMENCÉ**, chantier sensible en sécurité (exécution de
    code utilisateur), à cadrer sérieusement avant de coder quoi que
    ce soit.
    - Un utilisateur doit pouvoir connecter un (ou plusieurs)
      automate de traitement des messages sur un dossier de son (ou
      ses) compte(s) IMAP : adresse/mot de passe/serveur/port/type
      de sécurité/dossier. Note explicite : le mot de passe IMAP
      devra suivre la même discipline que partout ailleurs dans ce
      projet (chiffrement `shared/secret_crypto.py`, jamais en
      clair, jamais loggé) -- déjà établi, pas à réinventer.
    - Proposer un pseudo-shell Python pour construire l'automate
      (Jupyter ou IPython, au choix de Claude selon investigation) +
      des mécanismes de test automatique. **À investiguer avant de
      choisir** : lequel des deux s'intègre le plus proprement dans
      ce projet (conteneurisation, exposition via le hub, sécurité
      d'un noyau Jupyter exposé à un utilisateur non administrateur).
    - Les automates devront pouvoir :
      - créer/modifier des fichiers dans un `home` + chemin propre à
        l'utilisateur (isolation à concevoir -- jamais un accès
        filesystem non borné, même réflexe que
        `_resolve_safe_path`/`_resolve_key_path` déjà établi
        ailleurs dans ce projet)
      - créer/modifier des événements calendrier (rattachement
        probable à l'infrastructure calendrier déjà existante côté
        `tickets-api`, #272 -- à confirmer, jamais présumé)
      - exécuter du SQL sur une base COMMUNE et une base PERSONNELLE
        créée À LA VOLÉE (première utilisation) -- risque réel
        d'injection/d'évasion si mal isolé, à concevoir avec le même
        soin que `dba-api`/`schema-analyzer-api` déjà existants
        (échappement, pas de requête multi-instructions, etc.)

    **Points de sécurité à trancher AVANT tout code**, jamais
    présumés : quel niveau d'isolement entre l'automate d'un
    utilisateur et le reste du système (conteneur dédié par
    utilisateur ? Quota CPU/mémoire/temps d'exécution ? Accès réseau
    sortant autorisé ou non depuis l'automate ?) ; la base
    "personnelle créée à la volée" vit sur quel SGBD, avec quelles
    limites de volumétrie ; le lien exact avec ce module ENT/IMAP et
    les modules déjà existants (GLPI, calendrier, tâches) reste à
    clarifier.

41. Évolution IMAP -- deux points explicites (2026-09-04). **PAS
    COMMENCÉ**.
    - Un mécanisme d'AUTO-CONFIGURATION et de choix GRAPHIQUE du
      dossier IMAP à traiter comme racine -- à cadrer avant de coder
      (jamais présumé) : "auto-configuration" désigne-t-elle la
      détection automatique des serveurs IMAP courants (Gmail,
      Outlook/Office365, etc. -- serveur/port/sécurité déjà connus,
      seuls adresse/mot de passe à saisir), le choix graphique du
      DOSSIER racine (parcourir l'arborescence IMAP existante plutôt
      que de taper un nom à la main), ou les deux à la fois ?
    - Un mécanisme de RECHERCHE dans les dossiers -- "recherche des
      messages qui match... regex, wildcard, texte". À cadrer : la
      recherche porte-t-elle sur le sujet, le corps, l'expéditeur, ou
      une combinaison configurable ? Recherche native IMAP (SEARCH,
      plus rapide côté serveur mais moins expressive) ou récupération
      puis filtrage côté `imap-client-api` (regex/wildcard complets,
      mais plus lent sur une grosse boîte) -- les deux approches ont
      un coût différent selon le volume de messages, jamais présumé
      laquelle convient sans en discuter.

42. Authentification de vault-admin-portal -- **LIVRÉ en #293**,
    trouvé en branchant rights-api sur vault-admin-api (#291). Voir
    vault/README.md pour le détail complet (client Keycloak ajouté,
    porte de connexion, groupes transmis à POST /users/.../roles,
    le mécanisme de déverrouillage crypto existant laissé intact).

43. Évolution "big brother" -- deux IA de sécurité (2026-09-04).
    **PAS COMMENCÉ**, chantier d'une ampleur considérable, aucun des
    deux volets ne peut être cadré sans une discussion approfondie
    au préalable -- jamais présumé quoi que ce soit ici.

    1. **IA de veille sur les failles connues** -- "analyser les
       failles connues en se tenant à jour des alertes cyber et
       bonnes pratiques". À CLARIFIER avant tout cadrage technique :
       "IA interne" désigne-t-elle un agrégateur programmé (flux
       CVE/CERT-FR/NVD croisés avec l'inventaire logiciel déjà suivi
       ailleurs dans ce projet -- GLPI, network-agent, Nebula...),
       un usage de LLM pour résumer/prioriser des bulletins de
       sécurité, ou autre chose ? Où les alertes détectées
       remonteraient-elles (nouveau module, tickets GLPI existants,
       tuile hub dédiée) ? Quelle fréquence de veille ?

    2. **IA de détection comportementale (applications + utilisateurs)**
       -- "apprenne sur le comportement des applications et des
       utilisateurs pour détecter les déviances signes d'intrusion".
       Chantier de machine learning à part entière (modélisation
       d'une ligne de base "normale", ingénierie de signaux, seuils
       d'alerte, gestion des faux positifs) -- rien de tout cela
       cadré. **Point d'attention distinct, pas seulement technique** :
       la surveillance du comportement des UTILISATEURS (par
       opposition aux seules applications/systèmes) touche à de la
       surveillance de salariés -- sujet encadré en droit du travail
       français (principe de proportionnalité, information/
       consultation des représentants du personnel le cas échéant,
       obligations CNIL) -- à examiner AVANT tout développement,
       jamais traité comme un simple détail d'implémentation.

    Aucun périmètre technique, aucune source de données, aucun
    mécanisme d'alerte défini pour l'un ou l'autre volet -- à
    reprendre en profondeur avec la personne le moment venu.

44. Supervision de charge des modules du hub et services externes
    associés (2026-09-04). **PAS COMMENCÉ**. Distinct du nouveau
    module de sondage réseau actif (voir #45 -- même préoccupation
    de charge à l'origine des deux, mais deux chantiers séparés :
    celui-ci porte sur la santé APPLICATIVE des ~40 services de ce
    projet et de leurs dépendances externes, pas sur le réseau
    lui-même). À CLARIFIER avant cadrage technique, jamais présumé :
    "charge" désigne-t-elle CPU/mémoire des conteneurs (docker stats
    ou équivalent), temps de réponse des routes HTTP, ou les deux ?
    "Services associés externe" -- GLPI/LDAP/Nebula/bases DBA (les
    systèmes tiers déjà intégrés), ou plus large ? Où les données
    remonteraient-elles (nouvelle tuile dédiée, extension de
    `vigilance`, autre) ? Lien naturel avec le futur module de
    sondage réseau (#45) : le nouveau module devrait probablement
    être l'un des premiers surveillés par ce chantier-ci, vu sa
    charge potentiellement élevée. **Cas concret apporté en #354** :
    agent de supervision de l'hôte ownCloud, à brancher sur son
    superviseur pour croiser pics de charge système et activité --
    voir item 53 pour les questions précises posées à la personne.

45. Architecture netprobe -- modularisation et agents répartis
    multi-hôtes (2026-09-04).
    **✅ AGENTS RÉPARTIS LIVRÉS en #405** (`netprobe/agent/`, voir item 48
    pour les choix) -- les quatre questions ouvertes ci-dessous sont
    tranchées avec des défauts annoncés dans `netprobe/agent/README.md`.
    La modularisation multi-services du CENTRAL (un conteneur par type
    de sonde) reste NON faite : sans besoin concret constaté, netprobe-api
    reste un seul conteneur. Réaction de la personne en plein
    développement de la fondation (#295) : "prévoir une
    modularisation des outils de sonde pas simplement de la tuile et
    prévoir sa répartition sur plusieurs host en mode agents
    répartis". **PAS COMMENCÉ** au-delà de la fondation déjà posée
    (#295 -- collecteur d'IP + système de contrôle, un seul
    conteneur). Deux principes retenus pour la SUITE de ce chantier,
    à cadrer plus précisément le moment venu, jamais présumés en
    détail ici :
    - **Modularisation réelle** -- chaque type de sonde (smokeping/
      nmap/tcpdump/analyseur) comme brique INDÉPENDANTE, pas
      seulement des onglets d'une même interface adossés à un seul
      backend monolithique. Implique probablement un service Docker
      distinct par type de sonde plutôt qu'un unique `netprobe-api`
      -- à confirmer une fois les volets actifs eux-mêmes abordés.
    - **Agents répartis multi-hôtes** -- plusieurs points de
      sondage physiques (pas un seul conteneur centralisé), chacun
      remontant vers une base commune. Questions ouvertes,
      volontairement pas tranchées à l'avance : comment un agent
      s'enregistre-t-il (déclaration manuelle, découverte
      automatique) ? Comment récupère-t-il sa configuration
      (interroge le système de contrôle central, ou config poussée) ?
      Quel protocole de remontée des données (push périodique vers
      l'API centrale, ou l'inverse) ? Authentification agent-vers-
      central à prévoir (jamais un agent anonyme pouvant écrire
      n'importe quoi dans la base commune).

46. Skin Keycloak — modes jour/nuit, mise en page, menu langue
    (2026-09-04). **3 des 4 points ✅ LIVRÉS**, confirmé par relecture
    directe du code (2026-09-05) -- le backlog n'avait jamais été mis
    à jour après ces livraisons :
    - Mise en page (thème par défaut `hub-dark`) -- LIVRÉ en #296.
    - Centrer/réduire les champs et boutons de connexion (`.card-pf`
      et enfants borné à 480px depuis #281, champs/boutons à 320px
      centrés depuis #296, étiquettes réalignées en cohérence en
      #300) -- LIVRÉ, largement au-delà de la demande d'origine.
    - Menu déroulant langue -- LIVRÉ en #296, avec une VRAIE
      investigation (pas un correctif défensif) : le gabarit officiel
      Keycloak (`base/login/template.ftl`, confirmé contre le dépôt
      `keycloak/keycloak`) n'a JAMAIS eu de classe `.pf-m-expanded`
      (la supposition de #281 était fausse) -- l'état ouvert/fermé
      est porté par l'attribut ARIA standard `aria-expanded` sur le
      bouton, ciblé par un sélecteur de fratrie CSS. Voir
      `keycloak/themes/hub(-dark)/login/resources/css/login.css`
      pour le détail complet, dans les deux thèmes.

    **Reste PAS COMMENCÉ, À CLARIFIER avant tout code** : bouton de
    bascule jour/nuit EN PAGE (sans passer par l'admin Keycloak) --
    demanderait du JavaScript nouveau ET probablement une
    modification du gabarit `template.ftl` lui-même (pas seulement du
    CSS, convention respectée partout ailleurs dans ces thèmes
    jusqu'ici, `parent=keycloak` préservé). Question explicitement
    laissée ouverte, jamais tranchée : bascule AUTOMATIQUE (média
    query CSS `prefers-color-scheme`, aucun bouton ni JS requis) ou
    MANUELLE (bouton réel, JS + probablement modification de gabarit) ?
    Combien de skins au total, au-delà de hub/hub-dark ?

47. Volet WiFi dans netprobe — supervision continue Campus Alpha
    **✅ COUCHE « EXPÉRIENCE CLIENT » ET RF LÉGÈRE LIVRÉES en #405-#408**
    (sondes Pi Zero W + collecteur Pi 3B + central + hub + images) :
    signal/canal/BSSID/itinérance, bornes visibles et voisins co-canal,
    ping/DNS/HTTP/iperf3 depuis chaque point, santé du Pi. Le suivi de
    BSSID « hors de portée » en #385 est levé. Voir docs/supervision-wifi.md.
    Reste HORS de portée tant que le matériel RF n'est pas reçu : voir
    ci-dessous (inchangé).
    (2026-09-04, reformulé le 2026-09-05 -- demandé explicitement :
    "voyons ce qu'on peut déjà faire sans RF simplement avec un
    client wifi et la couche IP et le snmp"). Objectif inchangé :
    distinguer la CAUSE du SYMPTÔME (RF réelle / borne en panne /
    roaming raté / WAN saturé), jamais visible séparément. Priorité
    changée -- commencer par ce qui NE dépend PAS du matériel RF
    (adaptateur RTL8812AU/HackRF One, achetés mais toujours pas
    reçus) :
    - **Couche expérience client, SANS RF** -- un client WiFi
      STANDARD (carte réseau normale, aucun mode moniteur requis)
      peut déjà mesurer : débit réel (iperf3) vers un serveur de
      référence, changements de BSSID dans le temps (détection de
      roaming) -- device déjà connecté au WiFi, aucun matériel
      supplémentaire nécessaire.
      **✅ DÉBIT RÉEL LIVRÉ en #385** -- `POST /iperf3/test` sur
      `netprobe-api` (`iperf3_probe.py`), même motif que `ping_probe.py`/
      `nmap_probe.py`. **Suivi de BSSID/itinérance TOUJOURS HORS de
      portée** -- limite architecturale RÉELLE découverte en
      construisant #385 : ce conteneur n'a pas `network_mode: host`,
      ne peut PAS voir l'état WiFi de l'hôte (BSSID) depuis
      l'intérieur -- nécessiterait un agent natif sur l'hôte, dépend
      de l'architecture multi-hôtes non tranchée (items 45/48). Voir
      `netprobe/README.md` pour le détail complet.
    - **Couche infrastructure via SNMP DIRECT** -- pas besoin
      d'attendre l'API Nebula (bloquée sur licence, voir item 49) si
      les bornes/switches exposent SNMP : compteurs de trafic par
      interface (voir item 49, extension `walk_interfaces`),
      statut/vitesse déjà couverts.
    - **Couche IP** -- déjà couverte par `network-agent` (#233 et
      suites), rien de nouveau à construire ici.
    - **Couche backend/WAN** -- probablement déjà couvert par
      smokeping/nmap existants (#297/#302), à vérifier : suffit-il
      de pointer des cibles vers les services distants concernés.

    **Reste HORS de portée tant que le matériel RF n'est pas reçu**
    -- lecture RSSI/bruit périodique, capture passive de trames de
    désassociation/désauthentification (mode moniteur, nécessite
    RTL8812AU). Questions ouvertes sur CE volet spécifique,
    volontairement pas tranchées : format de stockage des trames
    capturées, fréquence réaliste de capture sans saturer les Pi
    Zero W.

48. Agent de sonde distribué pour Raspberry Pi — évolution de
    l'item 45 (2026-09-04). **✅ LOGICIEL LIVRÉ en #405** (`netprobe/agent/`,
    58 tests, chaîne HTTP réelle sonde→collecteur vérifiée) -- option
    « agent netprobe propre » retenue (pas sparrow-wifi : Pi Zero W sans
    mode moniteur, item 47 reformulé « sans RF »). Deux rôles : sonde
    (Pi Zero W) et collecteur de site (Pi 3B). Images et central : voir
    #406-#408. Historique de la décision ci-dessous. Cas d'usage concret
    maintenant disponible pour trancher les questions ouvertes de
    l'item 45 (agents multi-hôtes) : la flotte de Pi Zero W achetée
    pour la supervision WiFi. `sparrow-wifi` (voir item 50) fournit
    DÉJÀ un modèle de référence testé -- agent headless
    (`sparrowwifiagent.py`) explicitement pensé pour déploiement Pi,
    API REST interrogeable à distance. Deux options à trancher, PAS
    décidées ici :
    - Réutiliser l'agent sparrow-wifi tel quel sur les Pi, netprobe
      interrogeant son API REST pour rapatrier les mesures --
      réutilisation directe, moins de code à maintenir.
    - Construire un agent netprobe propre, plus léger, suivant le
      principe pmoteur/pcode discuté (interpréteur minimal qui
      s'enrichit des tâches reçues plutôt que redéployé à chaque
      évolution) -- plus de contrôle, plus de travail.
    Dans les deux cas : authentification agent-vers-central à
    prévoir (jamais un agent anonyme pouvant écrire dans la base
    commune, point déjà soulevé en #45), et une convention de
    traçabilité (quel agent a mesuré quoi, quand) avant tout
    déploiement réel.

49. Analyse du TRAFIC d'un réseau/site (2026-09-05, reformulé --
    demandé explicitement : "télémétrie d'un réseau/site il s'agit
    d'analyser le trafic", corrige le cadrage initial trop centré
    sur l'API Nebula ci-dessous). L'objectif RÉEL est le volume/
    pattern de trafic réseau, pas seulement le statut en ligne/hors
    ligne des bornes -- l'API Nebula EST bloquée sur un prérequis
    administratif (licence, voir plus bas), donc PAS le bon chemin
    principal pour cet objectif précis. **Piste retenue** : compteurs
    de trafic SNMP standard (`IF-MIB` -- `ifHCInOctets`/
    `ifHCOutOctets`, 64 bits, RFC 2863/3273, préférés aux compteurs
    32 bits `ifInOctets`/`ifOutOctets` pour éviter un rebouclage sur
    un lien gigabit+) -- `snmp-api` (`walk_interfaces`) ne les
    récupère PAS encore aujourd'hui (seulement `ifDescr`/
    `ifOperStatus`/`ifSpeed`), extension directe et sans nouveau
    prérequis administratif, sur n'importe quel équipement SNMP déjà
    interrogeable par ce module -- pas seulement les bornes Nebula.

    **Historique conservé -- volet API Nebula, statut inchangé** :
    **API CONFIRMÉE CAPABLE, route exposée (#349)** --
    `nebula_client.get_online_status` (existant depuis #196, jamais
    branché à une route HTTP jusqu'ici) exposé via `GET
    /api/nebula/sites/<siteId>/online-status?type=AP` -- renvoie
    `[{"devId", "currentStatus"}, ...]`, répond directement à "les
    bornes plantent-elles réellement ?". Nombre de clients connectés
    déjà couvert par `GET /sites/<siteId>/clients` (existant, #196) --
    se dérive de la longueur de la liste. "Charge" par borne : PAS
    couverte, aucun champ de ce type dans la spécification OpenAPI
    consultée -- confirme que cette API répond au statut, pas au
    trafic. Voir nebula/README.md pour le détail complet.

    **Reste RÉELLEMENT hors de portée côté Nebula** (pas du code, un
    vrai prérequis administratif) : licence Nebula Pro Pack + clé API
    obtenue via le support Zyxel (jamais en libre-service) -- sans
    ça, aucun test réel possible contre ces routes, quel que soit le
    code déjà écrit des deux côtés (client + route HTTP). Aucun
    polling périodique/stockage historique construit non plus --
    appel à la demande uniquement pour l'instant.

    **✅ PISTE SNMP LIVRÉE en #384** -- `POST /traffic-rate`
    (`snmp-api`) : débit réel par interface (octets/s, entrant et
    sortant), calculé par différence entre deux relevés des
    compteurs 64 bits IF-MIB espacés de quelques secondes -- sur
    N'IMPORTE QUEL équipement déjà interrogeable en SNMP par ce
    module, sans dépendre de la licence Nebula. Voir
    `snmp/README.md` pour le détail complet, y compris un vrai bug
    trouvé et corrigé en testant (`sample_interval=0` mal géré).

50. Analyse de spectre et rapprochement sparrow-wifi (2026-09-04).
    **PAS COMMENCÉ**. Une fois le HackRF One reçu : installation et
    premier test de `sparrow-wifi` (dépôt ghostop14/sparrow-wifi) en
    conditions réelles sur le mini PC. Question ouverte centrale,
    jamais tranchée : sparrow-wifi tourne-t-il en système
    INDÉPENDANT (son propre Elasticsearch/Kibana, consulté à part),
    ou son API REST est-elle interrogée DEPUIS netprobe pour
    intégrer ses mesures dans la même corrélation que les autres
    couches (RF léger, infra, client) ? La seconde option sert mieux
    l'objectif de corrélation multi-couches mais demande d'écrire le
    connecteur ; la première est immédiate mais laisse la
    corrélation manuelle, à la charge du technicien.

51. Interface hub — vue de corrélation multi-couches et guidage
    technicien (2026-09-04). **SOCLE LIVRÉ en #407** (onglet « Sondes
    WiFi » : ce que chaque sonde voit, quand -- courbe de signal,
    itinérance, ping, voisinage, santé) ; la CORRÉLATION entre couches
    reste à concevoir sur de vraies séries, après un premier déploiement
    (voir docs/supervision-wifi.md, « mise en route »). Dépend des items
    47-50 (rien à afficher tant que les couches sous-jacentes ne
    produisent pas de données). Objectif exprimé explicitement :
    "proposer et mettre en place des outils permettant de superviser
    l'activité wifi et de guider les techniciens" -- pas seulement
    des graphiques par couche, mais une vue qui CROISE RF/infra/
    client/WAN au même lieu et au même instant pour distinguer la
    cause de l'apparence (principe déjà illustré dans la note
    d'architecture). Forme précise à définir une fois qu'il y a de
    vraies données à afficher -- prématuré de la concevoir dans le
    vide. Probablement une nouvelle tuile ou un nouvel onglet dans la
    tuile "Sondes réseau" existante (#301) plutôt qu'un module hub
    séparé, à confirmer une fois le contenu clair.

52. Hub — interface de consultation de l'historique de logs archivé.
    **❌ ERREUR DE MA PART, CORRIGÉE (2026-09-05)** -- cet item
    affirmait "AUCUNE interface hub ne consulte l'historique persisté
    de memory-api", en me fiant uniquement à `LogsManagerView.jsx`
    (qui, lui, n'interroge effectivement que le tampon Memcached en
    direct) SANS vérifier `MemoryView.jsx` -- qui, en réalité, appelle
    déjà `fetchStats`/`fetchServices`/`fetchEntries`
    (`hub/src/memoryClient.js`) sur EXACTEMENT `/stats`/`/services`/
    `/entries` (`memory-api`), avec filtres service/niveau et
    affichage tabulaire des statistiques ET de l'historique -- livré
    depuis la création même de cette tuile (#259), jamais depuis
    #351-353 comme l'affirmait ce texte à tort. Vérifié en relisant
    `MemoryView.jsx` en entier avant de conclure, cette fois. **Rien
    à construire ici** -- l'affirmation initiale (répétée dans
    CHANGELOG.md #352/#353 et hub/README.md/memory/README.md,
    également corrigées) était simplement fausse.

53. Hub — séparation GED interne/externe, recherche étendue et
    supervision OwnCloud (2026-09-05). Demandé explicitement :
    "vérifie bien que la tuile ged donne un accès séparé visuellement
    d'un coté à la ged externe et au dépôt interne... ajoute une
    recherche toutes sources et viens greffer l'elasticsearch...
    parcourir les index d'elasticsearch et accéder aux données
    sources". Puis, en cours de discussion, priorité signalée :
    "erreur de synchronisation des drives (ça c'est la priorité)...
    identifier les chemins trop longs pour windows ou autres", et
    "un agent de supervision du host du owncloud... relier les pics
    de charge système... avec l'activité owncloud".

    **✅ LIVRÉ en #354-355** :
    - Constat initial confirmé : OwnCloud n'avait AUCUNE interface
      dans le hub (uniquement dans "Supervision SI", `frontend/` --
      bien plus riche, arbre radial/chronologie de versions, jamais
      dupliqué ici, juste référencé par un lien).
    - Sous-onglets "OwnCloud"/"Recherche" ajoutés à la tuile GED
      (`hub/src/GedView.jsx`) -- séparation VISUELLE appuyée (bordure
      orange, bannière permanente "lecture seule -- dépôt EXTERNE")
      du dépôt interne (Mayan, écriture).
    - Navigateur d'arbre OwnCloud en lecture seule
      (`OwnCloudTreeView.jsx`) et recherche Elasticsearch
      structurée, champs dynamiques depuis le vrai mapping de l'index
      (`OwnCloudSearchView.jsx`, `owncloud-search-api`, déjà construit
      depuis longtemps mais jamais relié à une interface avant ceci)
      -- affichage des données sources brutes de chaque résultat.
    - Détection des chemins trop longs pour Windows (`GET
      /long-paths`, owncloud-api) -- seul point du sujet
      synchronisation actionnable SANS nouvel accès (lecture seule
      déjà en place) ; requête coûteuse (~2,5M lignes sans index),
      mise en cache 15 min, déclenchée manuellement jamais
      automatiquement. Voir owncloud/README.md pour le détail complet.

    **PAS COMMENCÉ, À CLARIFIER avec la personne** (réponses en
    attente) : le reste du sujet synchronisation, marqué comme LA
    priorité --
    - Les erreurs de synchronisation détectées côté client desktop
      (conflit, permission refusée, chemin trop long) sont
      généralement LOCALES à chaque poste sur ownCloud/Nextcloud,
      jamais remontées au serveur par défaut -- à confirmer : une app
      "Activité"/"Notifications" est-elle installée côté ownCloud
      (table potentiellement lisible), ou faut-il envisager une
      collecte différente (journaux clients) ?
    - Agent de supervision de l'hôte ownCloud, à brancher sur son
      superviseur pour croiser pics de charge système et activité --
      rejoint directement les items 44/45 (déjà notés "à clarifier",
      jamais cadrés). Questions posées, réponses attendues : OS de la
      machine hôte, accès de déploiement disponible (SSH/RDP/admin
      local), mécanisme de remontée des métriques (agent qui pousse,
      ou système interrogé depuis ce projet).
    - Proposition de compte admin OwnCloud en lecture seule, écartée
      par la personne pour l'instant ("on oublie le user/drive") --
      possibilité de compte admin réellement restreint en écriture
      par la plateforme elle-même (pas seulement une discipline de
      code) jamais vérifiée, resterait à examiner si le sujet revient.

54. Frontend "Supervision SI" — onglet Cacti manquant, construit
    (2026-09-05). **✅ LIVRÉ en #362**. Trouvé en vérifiant
    systématiquement quels services API du projet n'avaient AUCUN
    consommateur frontend évident (même démarche que la découverte
    OwnCloud côté hub, item 53) : `cacti-api` était un module
    backend complet depuis longtemps, son propre docstring disant
    explicitement "pour alimenter l'onglet Cacti du frontend" -- mais
    cet onglet n'avait jamais été construit, dans aucun des deux
    frontends. Construit avec un arbre simple à déplier/replier
    (pas de visualisation radiale complète comme Optick/OwnCloud --
    choix délibéré, `cacti-api` renvoie déjà tout l'arbre en un seul
    appel, une liste dépliable suffit sans le coût de développement
    d'un rendu radial). `cacti/README.md` créé -- n'existait pas du
    tout jusqu'ici, inhabituel pour ce projet.

55. Script d'installation automatisée, sans intervention manuelle,
    adapté à l'environnement (2026-09-05). **✅ LIVRÉ en #374**.
    Demandé explicitement après une session de déploiement
    particulièrement difficile (OOM Keycloak, LDAP mal configuré,
    volume externe non purgé...) : "une archive et un script qui
    déploie sans intervention manuelle avec une config complète
    d'exemples et une évaluation initiale de l'environnement pour
    cadrer les services déployés qui s'adapte à l'os".
    `install.sh` (racine du projet) : vérifie Docker présent/démarré,
    détecte la mémoire RÉELLEMENT disponible pour Docker (`docker
    info --format '{{.MemTotal}}'` -- confirmé par recherche refléter
    l'allocation VM Docker Desktop sur macOS ET la RAM hôte réelle sur
    Linux natif, une seule commande valable identiquement sur les deux
    OS), choisit un périmètre de déploiement adapté (gateway+main
    minimal / gateway+main complet / tous les stacks) selon des seuils
    prudents (pas une science exacte), génère `.env` automatiquement
    si absent, déploie SANS AUCUNE INVITE INTERACTIVE -- vérifié que
    les garde-fous destructifs existants (purge Keycloak, placeholder
    LDAP) sont tous gated derrière un état préexistant, impossible sur
    un premier déploiement.
    **Bug latent trouvé et corrigé au passage** : `scripts/run-all.sh`
    ET `scripts/launcher.sh` utilisaient tous les deux `declare -A`
    (tableau associatif, fonctionnalité BASH 4+) -- absente de bash
    3.2 (celui livré par défaut sur macOS, jamais mis à jour par
    Apple) -- remplacés par une fonction de correspondance (`case`),
    bash 3.2-compatible, jamais signalé avant cette livraison malgré
    leur usage à chaque déploiement macOS de ce projet. Recherche
    systématique confirmant qu'aucun autre script du projet n'utilise
    `declare -A`. **Commentaire obsolète corrigé aussi** :
    `scripts/generate-env.sh` affirmait à tort ne jamais toucher
    `LDAP_BIND_PASSWORD` -- en réalité le code le génère bien,
    identique à `LDAP_TEST_ADMIN_PASSWORD` (vérifié, comportement
    RÉEL correct, seul le commentaire d'en-tête était resté faux après
    un changement ultérieur jamais répercuté dans ce commentaire).
    Vérifié réellement : syntaxe bash, logique testée avec Docker
    simulé (4 paliers de mémoire, cas `.env` déjà présent, cas Docker
    non démarré, code de sortie), `run-all.sh` corrigé retesté sur
    les 4 scénarios (cible connue/inconnue/all/usage). **Non vérifié
    dans cet environnement** : exécution contre un vrai Docker (aucun
    disponible ici).

56. Script de nettoyage pour annuaire de test LDAP mal amorcé
    (2026-09-05). **✅ LIVRÉ en #375**. Demandé explicitement
    ("peux tu préparer une script de nettoyage ?") après un cas RÉEL
    signalé en conditions réelles : `.env` avait `LDAP_BIND_PASSWORD`
    et `LDAP_TEST_ADMIN_PASSWORD` identiques et corrects, mais
    Keycloak refusait quand même l'authentification LDAP avec
    "error code 49 - Invalid Credentials". Cause la plus probable
    (jamais confirmée à 100 %, aucun accès direct aux conteneurs de
    la personne) : l'annuaire `openldap-test`, comme Keycloak,
    n'amorce ses données QU'À LA CRÉATION de ses volumes -- si
    bootstrappé quand `.env` portait ENCORE un autre mot de passe, ce
    mot de passe reste figé indéfiniment, quoi que `.env` contienne
    désormais. Nouvelle commande
    `./gateway/scripts/run.sh reset-ldap-test` -- même motif de
    sécurité que `reset-keycloak` (confirmation stricte "RESET"),
    mais cible SEULEMENT `openldap-test` (pas tout le stack gateway),
    volumes trouvés par filtre d'étiquette Compose (jamais un nom en
    dur). Testé avec Docker simulé (confirmation refusée/acceptée,
    bonne suppression des deux volumes). Voir `gateway/README.md`
    pour le détail complet.
    **Suite en #378** : après avoir utilisé `reset-ldap-test`,
    Keycloak échouait avec une AUTRE erreur ("LDAP: error code 32 -
    No Such Object" sur `ou=users`) -- diagnostic initial : bug connu
    de `--copy-service` (#364), remplacé par
    `LDAP_REMOVE_CONFIG_AFTER_SETUP=false`.
    **Suite en #379** : ce remplacement N'A PAS résolu le problème --
    même erreur persistante après un nouveau `reset-ldap-test`,
    signalé en conditions réelles. Diagnostic de #378 reconsidéré
    comme probablement HÂTIF (le silence dans les logs n'est pas une
    preuve d'échec à ce niveau de verbosité). `--loglevel debug`
    ajouté temporairement pour identifier la VRAIE cause.
    **✅ VRAIE CAUSE TROUVÉE et RÉSOLUE en #381** : `docker exec ...
    ls` a montré le dossier `custom/` VIDE à l'intérieur du conteneur
    -- `--project-directory` (gateway/scripts/run.sh) pointe
    délibérément vers la racine du projet PRINCIPAL, mais le montage
    `./ldap-seed` n'avait pas le préfixe `gateway/` nécessaire --
    Docker Compose crée SILENCIEUSEMENT un dossier vide quand la
    source d'un bind mount est introuvable, sans jamais signaler
    d'erreur. Corrigé : `./gateway/ldap-seed:...`. Les deux
    correctifs précédents (`--copy-service`, puis
    `LDAP_REMOVE_CONFIG_AFTER_SETUP=false`) n'étaient PAS faux en soi
    (l'un comme l'autre reste une bonne pratique pour le problème
    #359 qu'ils visaient), mais aucun des deux ne pouvait résoudre
    CE problème précis, sans rapport. Voir `gateway/README.md` pour
    le détail complet et la leçon retenue sur le diagnostic des
    montages Docker.
    **✅ CONFIRMÉ RÉSOLU en #382** -- authentification LDAP
    fonctionnelle en conditions réelles, confirmée par la personne.
    Saga #359-#381 définitivement close.

57. Nouveau module `docker-monitor` -- contrôle minimal des
    conteneurs + analyse de logs de TOUS les conteneurs (y compris
    lui-même) publiée dans un fichier externe (2026-09-05).
    **✅ LIVRÉ en #376**. Demandé explicitement : "extraire de
    portainer.io de quoi construire un docker qui contrôle les
    autres stacks/containers à minima qui lise et analyse les logs
    de tous les container y compris lui-même et publie son analyse
    dans un fichier log externe". Recherche menée sur l'architecture
    réelle de Portainer avant de coder -- confirmé : monte
    `/var/run/docker.sock` pour parler à l'API Docker via SDK, ÉQUIVAUT
    À UN ACCÈS ROOT sur l'hôte (documenté clairement, jamais caché).
    **Chevauchement partiel trouvé EN CONSTRUISANT** : ce projet a
    déjà `launcher` (contrôle start/stop/status par groupe de
    services, UI web) -- `docker-monitor-api` refait une partie de ce
    contrôle (par conteneur individuel, interface JSON) -- gardé
    quand même ("à minima" demandé pour ce service précis + interface
    JSON utile en soi), mais documenté explicitement plutôt que
    silencieusement dupliqué. La partie GENUINEMENT nouvelle :
    analyse périodique (thread d'arrière-plan, UN SEUL worker Gunicorn
    -- délibéré, évite une double boucle) des logs de CHAQUE
    conteneur (`since=<epoch>`, jamais un ré-examen des mêmes lignes),
    motifs d'erreur choisis à partir d'incidents RÉELLEMENT rencontrés
    dans ce projet (OOM Killed, erreurs LDAP...), résumé écrit en
    AJOUT dans un fichier EXTERNE (volume monté). Testé en profondeur
    avec un module `docker` (docker-py) entièrement simulé (paquet
    réel non installable, réseau restreint) -- listage/contrôle/santé/
    analyse tous vérifiés avec des scénarios réalistes. Voir
    `docker-monitor/README.md` pour le détail complet.
    **✅ CONFIRMÉ EN CONDITIONS RÉELLES en #377** -- déployé et
    vérifié par la personne : `docker.from_env()` joint bien le
    socket monté, la boucle d'arrière-plan tourne (13 conteneurs
    examinés, ~60s d'intervalle), le mécanisme incrémental
    fonctionne (premier passage examine l'historique, passages
    suivants n'y retouchent pas). Fichier d'analyse réel observé :
    avertissements bénins détectés chez `tickets-postgres`/`keycloak`
    au premier passage, "aucune anomalie" ensuite -- exactement le
    comportement attendu.

58. Orchestrateur d'analyse et de supervision réseau (2026-09-06).
    **FONDATION LIVRÉE en #388**. Demandé explicitement après
    recentrage du volet Nebula : "définitivement limité à l'import
    de fichiers de données. En revanche le besoin d'analyse et de
    supervision d'un environnement réseau comme celui contrôlé par
    nebula est prioritaire". Scénario de départ demandé : (1) liste
    IP/MAC/DNS/ports confirmée dans le temps, (2) liste des flux/
    volumes/paquets échangés dans le temps, puis un orchestrateur
    proposant des étapes d'analyse.
    **Découverte majeure faite avant de coder** : les deux listes
    demandées existent DÉJÀ intégralement dans `network-agent-api`
    (`na_devices` -- IP/MAC/hostname DNS/first_seen jamais réécrit ;
    `na_device_services` -- ports ; `na_device_links`/
    `na_device_link_services` -- flux/volumes/paquets ; tables
    d'historique par relevés périodiques pour le suivi dans le temps,
    déjà construites en #251) -- rien reconstruit en double, voir
    `netmap-orchestrator/README.md` pour le détail complet de cette
    correspondance.
    Nouveau module `netmap-orchestrator` construit PAR-DESSUS ces
    données (lues via l'API HTTP de network-agent-api, jamais
    dupliquées) : 3 règles de départ (`no_services` -- appareil sans
    service détecté, suggère un scan actif ; `new_device` -- appareil
    récent, informatif ; `snmp_candidate` -- trafic SNMP observé,
    suggère un enregistrement dans snmp-api), architecture calquée
    sur le moteur d'analyse déjà existant de netprobe (#307, calcul
    pur séparé de l'écriture). Suggestions stockées sans doublon
    (une ligne par règle/sujet), réouvertes automatiquement si la
    condition revient après clôture. Ce module ne lance rien lui-même
    -- fournit le contexte nécessaire pour qu'une action réelle soit
    déclenchée via le module concerné.
    Testé en profondeur : `store.py` (dont un vrai bug trouvé et
    corrigé -- préservation du contexte d'action sur une mise à jour
    qui n'en fournit pas de nouveau), `engine.py` avec
    `network_agent_client` mocké (3 règles, pas de doublon après un
    second passage), routes Flask (12 scénarios). Câblé dans
    `docker-compose.yml` (port 6125, UN SEUL worker Gunicorn -- même
    raisonnement que docker-monitor-api, évite une double boucle de
    fond).
    **✅ DEUX PREMIÈRES VISUALISATIONS LIVRÉES en #389** -- graphe
    alluvial (flux TCP/IP/UDP, calcul manuel -- `d3-sankey` ET `d3`
    lui-même confirmés INACCESSIBLES depuis l'environnement de
    développement, 403 sur npm) et radial tree augmenté (liens
    d'épaisseur proportionnelle au volume, rendu calqué sur
    `OptickRadialTree.jsx` déjà établi) -- ajoutées dans la tuile
    `NetworkAgentView.jsx` existante, à partir des données déjà
    chargées. Logique de construction de données testée en isolation
    (28 scénarios au total) ; le rendu `d3` lui-même N'A PAS pu être
    exécuté ici (contrainte réseau vérifiée, pas supposée) -- à
    confirmer au premier rendu réel. Voir `network-agent/README.md`
    pour le détail complet.
    **✅ ROUTÉ VIA LA PASSERELLE en #390**, **✅ INTERFACE HUB LIVRÉE
    en #391** -- demandé explicitement ("construis l'interface
    maintenant"). `NetmapOrchestratorView.jsx` (menu "Réseau") :
    filtrage par statut, bouton "Lancer une analyse maintenant",
    tableau des suggestions avec contexte d'action, boutons rejeter/
    marquer traité/rouvrir. Client testé (8 scénarios -- paramètres
    de filtrage, méthodes HTTP, transmission du statut). N'exécute
    AUCUNE action elle-même. Voir `netmap-orchestrator/README.md`
    pour le détail complet.
    **Reste à construire, itérations suivantes ("cycle permanent de
    retour" annoncé par la personne)** : d'autres vues de flux (au
    choix de la personne au fil de l'usage réel) -- pixel-grid déjà
    disponible séparément (#153+, #371).

59. Données de démonstration + frontend autonome pour les modules
    réseau (2026-09-06). **✅ LIVRÉ en #392-393**. Demandé
    explicitement : "génère des données d'exemple en volume
    suffisant et sur une période de plusieurs mois afin d'affiner la
    mise au point de l'interface", avec des filtres "période
    temporelle / profondeur de voisinage / volume de trafic /
    géographie" -- puis, après une première tentative mal comprise
    (page HTML statique à données figées, corrigée par la personne :
    "je veux un docker front qui se branche sur le/les dockers api").
    **#392** : `network-agent/scripts/seed_demo_data.py` -- génère un
    site "Démo" clairement étiqueté, 4 segments (profondeurs +
    géographies distinctes), 165 appareils, 25 relevés hebdomadaires
    sur 6 mois, ~577 liens à volumes croissants réalistes.
    Reproductible (graine fixe) et idempotent (ré-exécution supprime
    d'abord les données précédemment générées). Nouveaux attributs
    sur `na_devices` (`network_depth` notation "pN.M", `building`/
    `room`/`zone`/`latitude`/`longitude`) -- ce module ne les DÉDUIT
    jamais du trafic réel, toujours NULL par défaut. Trois filtres
    fonctionnels ajoutés (profondeur, géographie, volume minimum) --
    route `/devices` étendue + nouvelle route `/filter-options`.
    **✅ 4e FILTRE ("PÉRIODE TEMPORELLE") LIVRÉ en #394** --
    `store.list_devices_for_period` calcule le volume ÉCHANGÉ PENDANT
    une période choisie PAR DIFFÉRENCE entre deux relevés (même
    principe que `/traffic-rate` sur snmp-api, #384) -- nouvelle
    route `GET /devices/for-period`, interface avec deux sélecteurs
    de date (convertis en ISO 8601 complet côté client, évite un
    décalage d'un jour par comparaison de chaînes). Les 3 autres
    filtres s'appliquent alors côté client sur le résultat. **Les 4
    filtres demandés sont désormais TOUS livrés.** Voir
    `network-agent/README.md` pour le détail complet.
    **#393** : nouveau module `network-explorer` -- frontend React/Vite
    AUTONOME, SANS Keycloak ni passerelle (contrairement au hub
    principal), branché DIRECTEMENT sur `network-agent-api`/
    `netmap-orchestrator-api` déjà exposées. Réutilise TELLES QUELLES
    les vues déjà construites pour le hub (copiées depuis `hub/src`
    au build, jamais forkées -- même motif que `vault-admin-portal`).
    Aucune protection d'accès -- LAN de confiance uniquement, jamais
    routé publiquement (vérifié absent de `tls-proxy/render_nginx_conf.py`).
    Voir `network-agent/README.md` et `network-explorer/README.md`
    pour le détail complet des deux volets.

60. Variables de thème `--hub-*` inexistantes, replis en dur (2026-09-06).
    **✅ TRAITÉ en #402** -- les 11 usages restants remplacés :
    `--hub-ok`/`--hub-ok-bg` → `--ok`/`--ok-bg` (neutre), `--hub-border`
    → `--border` (#ddd → #d8dee4 en clair, imperceptible), `--hub-bg` →
    `--panel` (c'était le fond d'une boîte de dialogue, #fff = --panel
    clair), `--hub-selected` → `--bg` (convention existante des lignes
    sélectionnées, `.na-device-row.active`). Plus aucun `var(--hub-` dans
    `hub/src`. Reste valable : le contrôle `grep` ci-dessous.
    Constaté en livrant #399, PAS demandé -- noté ici plutôt que corrigé
    en passant, parce que ces cas-là ne sont PAS neutres visuellement
    contrairement à `--hub-danger` (déjà corrigé en #399, ses replis
    valaient exactement les valeurs du thème clair).

    Aucune de ces variables n'est définie dans `shared/theme.css` : chaque
    usage retombe silencieusement sur son repli en dur, donc reste
    identique en thème sombre alors que le reste de l'interface change.

    - `var(--hub-ok, #27ae60)` (2 usages) et `var(--hub-ok-bg, #eafaf1)`
      (1 usage) -- replis EXACTEMENT égaux à `--ok` / `--ok-bg` du thème
      clair : remplacement neutre, corrige uniquement le sombre. À faire
      en premier, sans risque.
    - `var(--hub-border, #ddd)` (6 usages) -- `--border` vaut `#d8dee4` en
      clair, PAS `#ddd` : le remplacement change (très légèrement) aussi
      le thème clair. À valider visuellement.
    - `var(--hub-bg, #fff)` (1 usage) -- ambigu : `--panel` vaut `#ffffff`,
      `--bg` vaut `#f4f6f8`. Regarder l'usage avant de trancher.
    - `var(--hub-selected, #e8f0fe)` (1 usage) -- aucune variable
      équivalente au thème, il en faudrait une nouvelle.

    Contrôle systématique à ajouter avant de considérer un module du hub
    terminé : `grep -rn -- 'var(--[a-z-]*, #' hub/src` -- un repli en dur
    sur une variable jamais définie est indétectable à la lecture du JSX
    seul, il faut vérifier que la variable EXISTE dans `shared/theme.css`.

61. Charte d'icônes du hub -- décision et extension (2026-09-07, #410).
    Trois jeux proposés dans le cycle agile (`hub/src/icons.js`,
    `docs/charte-icones-hub.md`) ; Déployer et Apprendre déjà changés
    (📦, 📚). Reste à trancher par la personne : (1) le jeu par défaut
    (emoji sobres / symboles monochromes / pictogrammes au trait) ;
    (2) si la préférence devient un réglage de COMPTE (comme le thème,
    `shared/preferences.js`) plutôt que de navigateur ; (3) l'extension
    aux tuiles de l'accueil et au menu (`App.jsx` porte encore ses emoji
    en dur) -- ajouter une clé par tuile dans chaque jeu, le test
    `icons.test.mjs` impose qu'aucun jeu ne l'oublie. Si le jeu « au
    trait » est retenu, dessiner les pictogrammes manquants (une
    soixantaine de tuiles) plutôt que de mélanger emoji et traits.

62. Tuile UPS -- suite de la version 0 (2026-09-07, #415). #433 : alertes
    (alarme, injoignable, seuils) et notifications livrées ; #434 : SNMP
    UPS-MIB (à confirmer sur une vraie carte) ; #435 : pages supplémentaires
    et dérive lente. Reste : historique de la carte, remontée vers
    vigilance. Livré :
    liste, automate HTTP (Basic) 1 h, fiche extraite de la page Socomec
    NETYS, archive, timeline (`ups-monitor/README.md`). À faire, dans
    l'ordre proposé : (1) confronter le parseur à un onduleur RÉEL et
    aux autres pages de la carte (`info_battery.htm`, `info_io.htm`,
    `hist_log1.htm`) -- « plusieurs pages par onduleur » ; (2) poser
    `UPS_CRED_PASSPHRASE` / `UPS_CRED_SALT` en production (sans eux,
    mots de passe en clair, signalé) ; (3) alertes (passage en alarme,
    injoignable depuis N relevés) vers vigilance / SMS ; (4) seuils
    tension / charge / batterie ; (5) seconde méthode de relevé SNMP
    (RFC 1628 UPS-MIB) via snmp-api, plus fiable que l'HTML.

63. Agent Linux d'audit et de sondes extensibles (2026-09-07, demandé
    avec #418). Demande : « un agent qui permette d'auditer le host et la
    zone réseau accessible autour ; qui permette de déployer des sondes
    futures en Python ou en shell/bash ; par défaut un relais pour
    l'exploration réseau mais désactivé ; inventaire des sondes (logiciels
    disponibles et installés) ; inventaire des agents pointant sur un
    tableau de bord / de commande de l'agent ; sondes Linux / RPi Zero W… ;
    sondes Windows (à explorer) ; agents GLPI ». État : l'agent
    `netprobe/agent` (#405-#408, Python stdlib, tâches tirées, HMAC, file
    store-and-forward, images Pi) EST déjà un agent Linux -- la demande
    est sa généralisation, pas un second agent. Découpage proposé :
    (a) audit de l'hôte : tâche `sys` étendue (OS, paquets, services,
    interfaces, routes, ports à l'écoute, disques) ; (b) audit de la zone
    réseau : tâche `neighbors` (table ARP, `ip neigh`, ping-sweep du /24,
    nmap si présent) ; (c) sondes extensibles : tâche `script` exécutant
    un script Python ou shell fourni par le central avec signature (même
    HMAC), sortie JSON normalisée -- jamais d'exécution non signée ;
    (d) inventaire des capacités : l'agent déclare les binaires
    disponibles (nmap, iperf3, tcpdump, iw, snmpwalk…) et les sondes
    installées, affiché dans le tableau de bord de flotte (onglet « Sondes
    WiFi » renommé « Agents ») ; (e) relais d'exploration : tâche
    `capture` qui envoie des relevés tcpdump vers network-agent-api,
    DÉSACTIVÉE par défaut, activable par agent ; (f) tableau de bord /
    commande par agent (tâches, dernier contact, capacités, journal) ;
    (g) Windows : à explorer -- Python embarqué + service, ou WMI/PowerShell
    via un agent minimal ; (h) agents GLPI : inventaire GLPI Agent déjà
    déployé → lecture via glpi-api plutôt qu'un doublon. À trancher avant
    de coder : ordre (a→f proposé), et si l'agent Linux généraliste doit
    être un paquet distinct (`si-agent`) ou rester `netprobe_agent`.
    **Tranché par la personne (2026-09-07)** : NOUVEAU paquet `si-agent`,
    distinct de `netprobe_agent` (qui reste la sonde WiFi/réseau). Rôle
    précisé : « l'agent host surveille le host (CPU, disque, mémoire,
    logs, risques internes) et il sert de machine-moteur pour la gestion
    de plugins / sondes ». Donc : (1) collecteurs hôte de base (CPU,
    charge, mémoire, disques, uptime, services en échec, journaux
    d'erreurs, risques internes : disque plein, redémarrage requis, ports
    exposés, comptes sudo…) ; (2) moteur de plugins = sondes Python ou
    shell déposées/signées par le central, ordonnancées par l'agent,
    sortie JSON normalisée ; (3) le relais d'exploration réseau et l'audit
    de zone deviennent des plugins livrés avec l'agent (désactivés par
    défaut) ; (4) central `si-agent-api` (flotte, enrôlement HMAC comme
    netprobe, catalogue de plugins, tableau de bord / commande par agent)
    et tuile hub « Agents ». Le protocole HMAC / file de netprobe est
    réutilisé (copie au build depuis la source canonique, jamais une
    seconde implémentation).
    Avancement (#420) : agent `si-agent/agent/` livré -- points (1) et
    (2), plugin `network-neighbors` livré désactivé pour (3). Reste :
    (4) central `si-agent-api` + tuile hub « Agents » (#421), relais
    d'exploration, sondes Windows, agents GLPI.
    Avancement (#422) : réponses du central signées, sondes confinées
    (nobody, limites, délai), blocage général / individuel (commande,
    configuration, fichier local), amorçage TLS par empreinte de CA,
    traces verbeuses, journal d'événements + notifications (SMS /
    courriel du PRA, webhook) + synthèse sur l'accueil du hub.
    Avancement (#436) : relais d'exploration livré (plugin capture-relay ->
    central -> network-agent-api). GLPI livré en #437 (hôtes si-agent ->
    Computer GLPI, comparaison avec les agents GLPI Agent). Premier hôte
    réel (Docker, #430) en ligne le 8 sept. ; premier retour traité en #438
    (montages sshfs/FUSE listés avec leur raison, propagation rslave) et
    #439 (FUSE mesuré comme l'utilisateur du montage, sans configuration).
    Agent Windows 10/11 livré en #440 (winhost.py + scripts PowerShell,
    install.ps1, tâche planifiée) -- à tester sur un poste réel ; #446 :
    lanceurs install.cmd/uninstall.cmd et commande avec -ExecutionPolicy
    Bypass (premier retour du poste de test) ; #447 : .cmd silencieux
    généré par le central (double-clic, UAC, OK, effacement) ; #449 : racine
    de l'archive cherchée autour du script ; #450 : CA lue par délégué C# sous
    PowerShell 5.1 (Bitdefender entreprise : exclusion de stratégie à prévoir). #442 :
    montages lecture seule / amovibles jamais « disque plein ». Reste :
    archive sans Docker (systemd) à tester, retours des premiers hôtes.

    #451 : agent macOS livré (machost.py, LaunchDaemon install-macos.sh, agent 0.5.0) -- premier Mac de test à venir.
64. Refonte de la tuile Supervision SI (2026-09-07, demandé avec #418).
    « La tuile actuelle était la maquette initiale de la dataviz du hub ;
    elle doit changer radicalement et ses outils actuels se retrouveront
    distribués dans les tuiles (on garde la tuile, rôle central). »
    Spécification reçue : colonne de gauche à onglets « Propositions »,
    « Supervisés », « Liens », peuplée par défaut de tout ce qu'on
    supervise (onglet Supervisés) avec filtre et priorisation des
    équipements/lieux ; page centrale découpée en 1 à 4 cadres (défaut 2 :
    carte + table des équipements supervisés ; 3 cadres : le troisième
    prend la largeur en bas ; 4 : répartition équilibrée). Découpage
    proposé : (1) API d'agrégation « supervisés » (nouveau service ou
    route hub) qui réunit netprobe (cibles, sondes), UPS, network-agent
    (appareils), snmp (cibles), ssh-tunnels, docker-monitor… en une liste
    homogène {type, nom, site/lieu, état, dernier relevé, tuile d'origine}
    ; (2) colonne gauche (onglets, filtre, priorisation persistée) ;
    (3) page centrale en cadres (1-4, disposition, choix du contenu de
    chaque cadre parmi : carte, table, timeline, pixel-grid, radial…) ;
    (4) redistribution des outils actuels (calendrier, corbeille, radial,
    fusion IP/MAC…) vers leurs tuiles.
    **Tranché par la personne (2026-09-07)** : la nouvelle tuile vit DANS
    LE HUB (composant React, carte Leaflet réimportée) ; « Propositions »
    = suggestions de l'orchestrateur + signaux de vigilance + appareils
    découverts non supervisés, les trois à cocher/décocher par
    l'utilisateur ; « Liens » = liens construits AUTOMATIQUEMENT entre
    équipements : « cette colonne régit l'affichage sur la carte, il faut
    une accroche géographique aux données présentées ; en période
    d'exploration, seule l'analyse des liens offre une position » -- un
    équipement sans coordonnées est positionné par ses liens (ce à quoi
    il parle, le site/segment auquel il appartient), et l'onglet montre
    cette chaîne de déduction.
    Avancement (#423) : points (1) agrégation, (2) colonne gauche
    (Propositions à cocher / Supervisés avec filtre et priorisation /
    Liens avec positions déduites) et (3) page centrale en 1 à 4 cadres
    (carte, table, liens, propositions, synthèse) livrés dans le hub
    (`SupervisionSiView.jsx`, `docs/supervision-si-tuile.md`). Reste :
    Avancement (#424) : point (4) -- timeline, mosaïque pixel-grid,
    calendrier de densité, arbre radial et corbeille de sélection sont
    des contenus de cadre de la tuile, nourris par les tuiles.
    Avancement (#425) : IPAM, Zenoss, Optick, TTS-GU et Cacti promus en
    UNE tuile générique « Bases externes » (docs/bases-externes.md).
    Avancement (#431) : Fusion IP/MAC en tuile (docs/fusion-ip-mac.md) ;
    OwnCloud est dans la tuile GED depuis #354. Reste : la géomatique
    (GeoImportApp), puis retrait de l'ancien front.
    Avancement (#426) : géolocalisation par le nom (« UPS-Arobase-5 » →
    @5), correspondances persistées dans pixel-grid, cadre
    « Localisations » (docs/geolocalisation-par-nom.md).
65. Exploration réseau -- fiche récapitulative d'un sous-réseau
    (2026-09-08, demandé avec #426). Constat : dans « sous-réseaux » on
    voit autre chose que le LAN immédiat, mais aucune IP de ce LAN dans
    les appareils découverts ni ce sous-réseau dans la table des
    découvertes. Demandé : au clic sur un sous-réseau, un récapitulatif de
    tout ce qui le concerne -- d'où il a été pris (source, segment,
    agent), quelles IP y ont été vues, appareils, flux, découvertes -- et
    expliquer/corriger l'absence du LAN immédiat.
    LIVRÉ en #427 (fiche, IP distantes derrière leur relais, IP des
    appareils passifs) -- à confirmer en capture réelle.
66. Agent hôte -- premier exemplaire réel (2026-09-08, demandé avec #426) :
    un Linux dans un sous-réseau isolé/filtré mais accessible par route
    directe. (1) découverte passive du réseau depuis l'hôte (voisins ARP /
    ND, connexions établies, écoute, sans scan actif) remontée au central ;
    (2) revue de l'hôte : matériel, niveaux des ressources, activités
    (processus, services, connexions), présentée dans la tuile Agents
    hôtes et reprise par Supervision SI.
    LIVRÉ en #428 (mesure netview passive, matériel et activité, sections
    dans la tuile, procédure du premier hôte réel) ; #432 : voisins/pairs
    repris par Supervision SI (propositions, liens). Reste : Exploration
    réseau (fusionner les voisins d'agent avec les découvertes de capture).
    #430 : archive de déploiement (make-archive.sh) avec variante conteneur
    Docker (deploy-docker.sh) et variante systemd (install.sh).
67. Catalogue de positions (2026-09-08, demandé avec #426). Docker dédié
    ou complément du PostGIS existant (geo-import) -- orientation :
    complément de `geo-postgres` (pg_trgm, connecteurs). Charger les
    référentiels OSM et data.gouv.fr (BAN/Géoplateforme, découpage
    administratif) ; interface listant, par position : la ou les données
    de référence (fiches avec agrégation ou extraction), l'interprétation
    géographique la plus précise, longitude/latitude, l'estimation en % de
    véracité/justesse, un bouton Corriger, un bouton Valider ; un
    catalogue de positions avec les liens vers les objets positionnés sur
    chacune. S'appuie sur les correspondances de #426 (location_matches,
    aliases) et la table geolocations.
    LIVRÉ en #429 (module geo-catalog, base PostGIS dédiée déplaçable,
    tuile) -- reste : appels réels aux référentiels et import OSM à
    confirmer en déploiement ; autres objets à positionner (tickets,
    documents) au-delà des géolocalisations.

## Bastion si-proxy (2026-09-08, #452) -- réservé freg
Depuis le Mac, via le hub : shell sur le host de la VM (sous freg),
navigation HTTPS sur le hub et, par le hub, sur le LAN. Relais TLS
(conteneur), shim host systemd sortant, client Mac (shell + proxy
HTTP). Réservé freg : jeton + TLS, mTLS+CN optionnel. Vérifié en
bout-à-bout local ; reste : déploiement réel sur « super », mTLS,
puis élargissement éventuel à d'autres utilisateurs. Voir si-proxy/README.md.
#453 : journal d'audit JSONL (si-proxy/data), fail2ban maison (ban par IP
au seuil d'échecs d'auth), interface de contrôle HTTPS 6452 (status,
audit, kill, disable/enable, unban ; jeton SI_PROXY_ADMIN_TOKEN).
#454 : tuile « Bastion » (sessions/kill, pause, bans, audit, cibles) via le
pont si-proxy-admin-api (jeton Keycloak VÉRIFIÉ, SI_PROXY_ADMIN_USERS),
catégorie Bastion dans Supervision SI + liens « bastion ».
#455 : console Bastion à cinq onglets (si-proxy, Entrées = exposition
EXPOSURE.json + agents/sondes avec coupe-circuit, Sorties = tunnels +
connecteurs externes, Autorisations = rights-api + liens externes,
Partages = gestionnaire de fichiers + montages SSHFS).
#456 : les 5 bases/index sont liés à 127.0.0.1 (SI_DB_BIND). Reste : 11 API et
portails hors passerelle (vault-admin, network-explorer, launcher,
docker-monitor, netmap-orchestrator, ups, si-agent, geo-catalog...) à
passer derrière tls-proxy ou à restreindre. Partages ownCloud (oc_share)
non exploités ; coffre/annuaire/Keycloak restent des portails dédiés.

## Accueil par thématiques (2026-09-08, #457)
Cinq super-tuiles (hubThemes.js) remplacent la trentaine de tuiles et les
menus Général/Réseau/Data ; ancien accueil conservé (Réglages). À suivre :
retour réel derrière Keycloak, éventuel réglage de la composition des
thématiques, retrait de l'ancien mode si inutile.

## Sauvegarde totale / restauration / régénération host (2026-09-08, #458)
backup-full.sh (archive chiffrée : dépôt, .env, PKI, montages, volumes, dumps,
shim), restore-full.sh, regenerate-host.sh (CA et sels jamais touchés). Voir
docs/sauvegarde-totale.md. #459 : incrémentale + gestionnaire (catalogue,
chaînes, GFS, export, planification) façon ARCserve (Cheyenne/NetWare, confirmé).
#460 : archivage versionné de la GED (parent/branches, officielle unique,
check-out/in, archive immuable) + graphe des versions. Reste : essai contre le
vrai Mayan sur « super » ; archivage planifié (GroupWise « scheduled archival »)
et sécurité par version si besoin.
