# imap-client

Client IMAP (livraisons #179/#189/#190/#191, backlog `BACKLOG.md`
#4, **volets 1, 2 et 3/4** de l'initiative "client IMAP +
interpréteur de messages → source"). Demandé pour recevoir des
messages provenant de systèmes qui ne savent notifier que par
e-mail.

## Portée (volets 1, 2 et 3/4)

1. **Client IMAP** ✅ **LIVRÉ (#179)** -- connexion, liste des
   dossiers, liste/lecture des messages (lecture seule).
2. **Interface de gestion de la boîte** ✅ **LIVRÉ (#189 puis #190)**
   -- création/suppression de dossiers, déplacement de message entre
   dossiers, filtres de recherche natifs IMAP au listage (#189),
   PUIS étiquettes et RÈGLES DE TRI avec actions déclenchées (#190,
   après précision de la personne : "c'est aussi l'idée de trier et
   poser des étiquettes, déplacer vers des dossiers, déclencher des
   actions" -- l'interprétation initiale de #189, recherche MANUELLE
   seule, était trop étroite).
3. **Gestionnaire d'interpréteur** ✅ **LIVRÉ (#191)** -- généralise
   en outil CONFIGURABLE ce que `pixel-grid/data-generator/
   parse_zenoss_emails.py` fait EN DUR pour un seul format (ce
   fichier reste INCHANGÉ, jamais remplacé -- juste une référence
   pour concevoir la généralisation). Voir plus bas pour le détail.
4. **Connecteur source** -- transformer le JSON produit par
   l'interpréteur en une SOURCE au sens du projet (`POST
   /ingest/<source>`) -- probablement le point d'arrivée naturel,
   **à confirmer avec la personne plutôt que présumé** (dixit
   `BACKLOG.md`).

## À distinguer de `parse_zenoss_emails.py`

`pixel-grid/data-generator/parse_zenoss_emails.py` (mentionné dans
le backlog comme précédent existant) est un parseur **HORS LIGNE**,
sur un export texte manuel (sélection Thunderbird + copier-coller),
**figé** sur un seul format d'alerte Zenoss précis. Ce module-ci
(`imap-client`) est une **connexion LIVE** à une vraie boîte IMAP,
générique -- n'importe quel message, pas seulement du Zenoss. La
généralisation vers un "gabarit configurable" reste le volet 3/4
ci-dessus, pas construit ici.

## Architecture

Service **SANS ÉTAT** -- pas de base de données locale,
contrairement à `ssh-tunnels-api`/`ged-api`. Une connexion IMAP
**neuve à chaque requête HTTP** (jamais gardée ouverte entre deux
requêtes) -- même raisonnement que les connecteurs SGBD de
`dba/api` : une connexion persistante pourrait avoir expiré côté
serveur (timeout d'inactivité IMAP, courant), et la complexité de
détection "encore valide" n'en vaut pas la peine pour ce volume
d'usage (diagnostic/consultation, pas un flux haute fréquence).

`imaplib` (bibliothèque **standard** Python) -- aucune dépendance
externe à installer pour la connexion elle-même, contrairement à
`ssh-tunnels` (`openssh-client`) ou `dba-api`
(`pymysql`/`psycopg2`).

## API

- `GET /folders` -- liste des dossiers IMAP (`["INBOX", "Archive",
  ...]`).
- `GET /messages?folder=X&limit=N&offset=M&subject=...&from=...&unseen=true`
  -- en-têtes seulement (sujet, expéditeur, date), le plus récent en
  premier (approximation, voir plus bas). `limit` plafonné à 200.
  Filtres (#189) tous OPTIONNELS -- recherche IMAP native, jamais un
  filtrage après coup côté Python.
- `GET /messages/<uid>?folder=X` -- message complet (en-têtes +
  corps texte/HTML).
- `POST /folders` (#189) -- corps `{"name": "..."}`, crée un dossier.
- `DELETE /folders?name=...` (#189) -- nom en PARAMÈTRE DE REQUÊTE,
  jamais un segment d'URL (peut contenir le séparateur hiérarchique
  IMAP, `/` ou `.` selon le serveur).
- `POST /messages/<uid>/move` (#189) -- corps
  `{"from_folder": "...", "to_folder": "..."}`, déplace un message
  (COPY + marquage supprimé + EXPUNGE sur l'original -- compatible
  avec tous les serveurs IMAP, jamais l'extension `MOVE`/RFC 6851,
  pas universellement supportée).
- `GET /logs`, `GET /health` -- même motif que tous les autres
  services de ce projet.

Un seul compte IMAP configuré (`.env` : `IMAP_HOST`, `IMAP_PORT`,
`IMAP_USER`, `IMAP_PASSWORD`, `IMAP_USE_SSL`, `IMAP_DEFAULT_FOLDER`)
-- pas de gestion multi-comptes, jamais demandée explicitement.
Toutes les routes renvoient `502` avec un message clair tant que
`IMAP_HOST`/`IMAP_USER` ne sont pas renseignés.

## Approximations assumées (mode adopté explicitement par la personne, #178)

1. **Tri "plus récent d'abord" par UID décroissant** -- jamais une
   garantie du protocole IMAP (RFC 3501). Les UID sont croissants
   avec le temps sur la vaste majorité des serveurs (Dovecot,
   Exchange...), mais rien ne l'impose absolument. Un vrai tri par
   `Date:` d'en-tête serait plus robuste mais demanderait de FETCHer
   tous les en-têtes avant de trier -- coûteux sur une grosse boîte,
   écarté pour cette première version. À reconsidérer si ça gêne en
   usage réel (ex. un serveur dont l'ordre des UID diverge
   nettement de l'ordre chronologique réel).
2. **Corps HTML jamais assaini** -- si aucune partie `text/plain`
   n'existe, le HTML brut est renvoyé tel quel (`body_html`) --
   jamais nettoyé ni échappé ici. Ce sera le rôle du volet 3/4
   (l'interpréteur) de décider quoi en faire -- ne JAMAIS afficher
   `body_html` directement dans une page sans échappement/
   assainissement côté consommateur.
3. **Règles de tri : APPLICATION à la demande, pas encore une tâche
   de fond automatique** -- `POST /rules/apply` doit être appelé
   explicitement (bouton dans l'écran, ou script externe) pour que
   les règles agissent. Une automatisation qui modifie la boîte
   toute seule (sans déclenchement explicite) est un pas plus
   risqué, laissé à une décision explicite plus tard plutôt que
   présumé maintenant.

## Règles de tri (livraison #190)

Précision apportée par la personne sur le sens de "filtres" (#189
n'avait construit qu'une recherche manuelle) : "c'est aussi l'idée de
trier et poser des étiquettes, déplacer vers des dossiers, déclencher
des actions".

**Une règle** = critères (tous optionnels, ET) + actions (toutes
optionnelles) :
- Critères : `watch_folder` (dossier surveillé), `match_subject`,
  `match_from`, `match_unseen_only`.
- Actions, exécutées dans cet ORDRE FIXE : `action_add_label`
  (étiquette = mot-clé IMAP personnalisé, `STORE +FLAGS`) et
  `action_mark_seen` D'ABORD, `action_move_to` EN DERNIER -- un
  message DÉPLACÉ change d'UID (nouveau message dans le dossier de
  destination), toute action ultérieure sur l'ancien UID échouerait.

**Étiquettes** = mots-clés IMAP personnalisés (`STORE +FLAGS`/
`-FLAGS`), PAS un système à part -- supporté par la plupart des
serveurs modernes (Dovecot, Gmail...) mais PAS universellement (le
serveur l'annonce via `PERMANENTFLAGS` au `SELECT`, jamais vérifié
explicitement ici -- l'erreur du serveur remonte telle quelle si le
serveur visé ne le supporte pas).

**Stockage** : PREMIÈRE base de données de ce module
(`rules_store.py`, SQLite) -- le reste du module reste SANS ÉTAT
(connexion IMAP neuve à chaque requête), mais les règles doivent
PERSISTER entre deux appels, rien dans IMAP lui-même pour ça
(contrairement à un vrai serveur Sieve, hors de portée ici).

**API** : `GET/POST /rules`, `PUT/DELETE /rules/<id>` (CRUD complet,
mise à jour PARTIELLE sur PUT -- usage principal : juste basculer
`enabled`), `POST /rules/apply` (applique TOUTES les règles
ACTIVÉES, une seule connexion IMAP réutilisée pour toutes, résumé
PAR règle : `{matched, moved, labeled, marked_seen, errors}` --
jamais un total agrégé qui masquerait quelle règle a échoué).

## Gestionnaire d'interpréteur (livraison #191)

Un **interpréteur** = critères de correspondance (`match_subject`/
`match_from`, optionnels, pour choisir AUTOMATIQUEMENT quel
interpréteur s'applique à un message donné, même esprit que les
règles du #190) + une liste de **champs** (`fields`) : chaque champ
applique un motif regex INDÉPENDANT à `subject` ou `body`, stocke le
résultat sous un nom. Choix : un champ = un motif indépendant, plutôt
qu'un seul motif géant à groupes nommés (comme
`parse_zenoss_emails.py`) -- plus simple à configurer sans expertise
regex poussée, un motif compliqué en moins à maintenir d'un coup.

**⚠️ PIÈGE CRITIQUE rencontré et corrigé en testant** : un motif
regex fourni par une personne, appliqué à un contenu externe (le
corps d'un email), peut causer un retour arrière catastrophique
("catastrophic backtracking") -- bloque l'exécution un temps
arbitrairement long. Un premier essai de protection par DÉLAI
D'ATTENTE dans un THREAD séparé (même motif que
`ssh-tunnels/mount_process.measure_latency`, #182) s'est révélé
**totalement inefficace** ici : contrairement à un appel système
(qui libère le GIL pendant l'attente), le moteur `re` en C NE LIBÈRE
JAMAIS le GIL pendant son propre calcul -- **mesuré RÉELLEMENT : 86
secondes d'attente malgré un délai demandé de 1 seconde**, sur un
motif catastrophique volontairement construit pour le test. Un
THREAD ne peut structurellement PAS protéger contre ce cas précis.
Corrigé avec un **VRAI PROCESSUS séparé**
(`multiprocessing.Process`) -- seul un processus peut être
interrompu de force (`terminate()`/`kill()`) au niveau du système
d'exploitation, indépendamment de ce que Python fait en interne --
**revérifié après correctif : 1.02 seconde pour le même motif**, sur
le même délai demandé.

**Stockage** : MÊME fichier SQLite que les règles (#190,
`RULES_DB_PATH` -- une seule base à sauvegarder/monter pour ce
module), table séparée `imap_interpreters`.

**API** : `GET/POST /interpreters`, `PUT/DELETE /interpreters/<id>`
(CRUD complet -- `fields`, si fourni sur `PUT`, est REVALIDÉ et
remplacé EN BLOC, jamais fusionné champ par champ). `POST
/messages/<uid>/interpret?folder=X` (corps optionnel
`{"interpreter_id": N}` -- sans lui, le premier interpréteur activé
dont les critères correspondent est choisi automatiquement ; `404`
si aucun ne correspond, jamais un résultat vide qui masquerait la
vraie raison) -- renvoie `{interpreter_id, interpreter_name, result:
{...}, errors: [...]}`.

## Vérifié réellement

Logique pure (`imap_wrapper.py`) testée directement, sans mock IMAP
bas niveau : décodage d'en-têtes RFC 2047 (accents français, réel
encodage base64/UTF-8), parsing de lignes IMAP LIST réelles (dossier
avec espace dans le nom, dossier avec crochets type `[Gmail]`),
extraction de corps contre de VRAIS messages MIME multipart
construits via `email.mime` (texte + HTML + pièce jointe, message
simple non-multipart, message HTML seul avec repli), échappement de
termes de recherche (guillemets, antislash). Fonctions appelant
`imaplib` (`list_folders`, `list_messages` avec et sans filtres,
`fetch_message`, `create_folder`, `delete_folder`, `move_message`,
`add_label`, `remove_label`, `mark_seen`, `safe_logout`) testées via
mock des méthodes `imaplib.IMAP4` (réponses au format réellement
documenté par la bibliothèque) -- y compris pagination réelle,
message disparu entre `SEARCH` et `FETCH` correctement sauté, pour
`move_message` : succès complet (COPY+STORE+EXPUNGE dans l'ordre),
échec de la COPY (jamais de STORE/EXPUNGE après), échec du STORE
APRÈS une COPY réussie (message explicite sur le doublon résultant,
jamais un échec silencieux) ; et pour les étiquettes : serveur ne
supportant pas les mots-clés personnalisés (erreur réelle remontée).

`rules_store.py` (CRUD des règles) testé contre une VRAIE base
SQLite (création, liste, mise à jour PARTIELLE confirmée -- seul le
champ transmis change, suppression, ids inexistants). `rule_engine.py`
(application d'une règle) testé en isolation : ORDRE des actions
confirmé (étiquette/lu avant déplacement), règle PARTIELLE (seule
l'action définie s'exécute, jamais les autres par erreur), erreur
sur UN message SANS bloquer les suivants de la même règle, critères
de la règle bien transmis à `list_messages`. `app.py` testé de bout
en bout (config absente -> 502 avec message clair ; CRUD complet des
règles, validation -- au moins une action requise à la création ;
`/rules/apply` : aucune règle activée -> aucune connexion IMAP
ouverte pour rien, une seule connexion réutilisée pour plusieurs
règles actives). Non-régression complète des volets 1 et 2/4
retestée en entier après chaque ajout (5 puis 6 cas).

`interpreters_store.py` testé contre une VRAIE base SQLite --
validation de champs (liste vide refusée, source invalide refusée,
motif regex invalide refusé AVANT stockage), création/lecture avec
aller-retour JSON confirmé, mise à jour partielle, et surtout : une
mise à jour avec des `fields` INVALIDES est refusée SANS RIEN changer
en base (les anciens champs valides restent intacts). `interpreter_engine.py`
: extraction réelle testée contre un texte proche d'une vraie alerte
Zenoss (device/sévérité/localisation tous corrects), champ sans
correspondance -> `None` sans erreur, `find_matching_interpreter`
(premier correspondant choisi, repli sur un interpréteur sans
critère, interpréteur désactivé jamais choisi). **Le délai d'attente
sur les motifs testé contre un VRAI motif catastrophique construit
pour l'occasion** -- a révélé l'inefficacité du premier essai (thread,
86s au lieu d'1s) et confirmé le correctif (processus séparé, 1.02s).
`app.py` testé de bout en bout : CRUD complet, validation à la
création, interprétation d'un vrai message simulé (auto-correspondance
ET `interpreter_id` explicite), `404` si aucun interpréteur ne
correspond ou si l'id demandé est introuvable. Non-régression
complète des volets 1, 2 et 3 retestée ensemble (8 cas).

**Non vérifié dans cet environnement** : contre un VRAI serveur
IMAP (aucun accès réseau externe ici) -- à tester en PRIORITÉ une
fois déployé, en particulier le support des mots-clés personnalisés
(étiquettes) par le serveur réel visé, et l'ordre de tri approximé.

## Connecteur source + interface hub (livraison #230)

Backlog item 4, volet "Connecteur source" -- transforme le JSON
produit par un interpréteur en une SOURCE au sens déjà connu du
projet (`POST /ingest/<source>` de l'`api` principal).

Champ `target_source` (nullable) ajouté aux interpréteurs -- migration
`ALTER TABLE ADD COLUMN` simple (contrairement à la migration
`ssh_key_id` de #210, aucune contrainte NOT NULL à lever). NULL =
comportement inchangé, strictement OPT-IN. Quand renseigné,
`POST /messages/<uid>/interpret` pousse AUSSI le résultat vers
`POST /ingest/<target_source>` (appel conteneur-à-conteneur,
`API_INTERNAL_URL`, même motif que `NEBULA_API_INTERNAL_URL` côté
GLPI, #208) -- BEST-EFFORT, jamais bloquant : un push qui échoue
n'empêche jamais l'interprétation elle-même de réussir, le résultat
est toujours renvoyé à l'appelant avec `push_ok`/`push_error` pour
signaler l'issue.

**Découverte importante en cherchant où câbler l'interface** :
`imap-client` n'avait ENCORE AUCUNE interface, pour AUCUN de ses
volets -- dossiers, messages, règles de tri, interpréteurs étaient
tous "livrés" côté backend uniquement (#179-191), jamais exposés dans
le hub. `hub/src/ImapView.jsx` + `imapClient.js` construits avec les
quatre sous-onglets d'un coup (Dossiers, Messages avec lecture/
déplacement/interprétation à la demande, Règles de tri, Interpréteurs
avec le nouveau champ `target_source`).

**Vérifié réellement** : migration testée contre une base simulant
l'état réel (interpréteur existant intact, `target_source=None` par
défaut). Route `/interpret` testée de bout en bout : sans
`target_source` (non-régression), avec push réussi (la vraie URL de
push vérifiée : `http://api:5000/ingest/<source>`), avec push en
échec (réponse toujours 200, résultat d'interprétation toujours
renvoyé). Traces debug ajoutées (cohérent avec #215-225) --
vérifié explicitement que le contenu du message n'apparaît jamais.
Structure JSX de `ImapView.jsx` revérifiée, logique de formulaire
(immutabilité, construction de requête) testée en isolation.

**⚠️ Interface jamais testée contre un vrai serveur IMAP** -- hérite
de la réserve déjà connue du backend, voir plus haut dans ce README.

## Branchement rights-api (livraison #310)

Suite de l'item 38 du backlog. Cette boîte est OPÉRATIONNELLE (reçoit
des notifications de systèmes qui ne savent alerter que par e-mail,
jamais une boîte personnelle) -- mais une règle ou un interprète
trafiqué pourrait faire disparaître silencieusement une alerte
critique (règle malveillante qui supprime/déplace les messages d'un
expéditeur précis avant que quiconque les voie).

Gardé sur les 10 routes d'ÉCRITURE qui changent l'état de la boîte
ou son traitement automatique : `POST/DELETE /folders`,
`POST /messages/<uid>/move`, `POST/PUT/DELETE /rules`,
`POST /rules/apply`, `POST/PUT/DELETE /interpreters`. JAMAIS sur la
lecture (dossiers/messages/règles/interprètes en liste), ni sur
`/messages/<uid>/interpret` -- fonctionnellement une lecture
(analyse un message déjà lisible sans y toucher) malgré le verbe
POST.

OPT-IN via `IMAP_CLIENT_RIGHTS_API_URL`, vide par défaut,
comportement inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 10
routes gardées avec un groupe non autorisé, routes de lecture
confirmées NON affectées même avec `rights-api` actif et refusant.
Non-régression complète reconfirmée.
