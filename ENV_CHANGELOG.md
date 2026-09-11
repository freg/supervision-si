# Journal des clés `.env`

Liste, du plus récent au plus ancien, ce qui a changé dans `.env`/
`.env.example` à chaque session — pour fusionner rapidement un `.env`
existant contre une nouvelle livraison sans repasser par un diff
complet à chaque fois. `.env.example` reste la référence exhaustive
des valeurs par défaut ; ce fichier ne donne que ce qui a **changé**,
avec le pourquoi.

**Mode d'emploi** : après avoir dézippé une nouvelle livraison,
regarder l'entrée la plus récente en haut — si elle correspond à ce
que vous avez déjà en `.env`, rien à faire. Sinon, copier/ajouter les
clés listées, dans votre `.env` existant.

## 2026-09-11 — VITE_ALLOWED_HOSTS="*" par défaut (livraison #478)

`VITE_ALLOWED_HOSTS` vaut désormais `*` dans `.env.example` (vide
avant) : vérifié qu'AUCUN des 6 fronts Vite ne publie de port direct —
ils ne sont joignables que via tls-proxy, donc la liste blanche Vite
n'apportait aucune protection mais bloquait tout nom non listé
(« Blocked request. This host ("super") is not allowed », signalé en
test via redirection X11 et par l'entrée externe). **Si votre `.env`
existe déjà** : ajoutez `VITE_ALLOWED_HOSTS=*` (ou une liste explicite
de noms) puis `./scripts/chantier.sh build` — la variable est lue par
Vite au démarrage du conteneur, pas au simple `restart`.

## 2026-09-11 — PROJEQTOR_* (livraison #476)

Nouveau module `projeqtor` (fork de ProjeQtOr V13.1.0, gestion de
projets, tuile hub visible de tous) : `PROJEQTOR_DB_NAME` (projeqtor),
`PROJEQTOR_DB_USER` (projeqtor), `PROJEQTOR_DB_PASSWORD` et
`PROJEQTOR_DB_ROOT_PASSWORD` (**générés aléatoirement** par
`scripts/generate-env.sh` — relancer ce script dans chaque nouvelle
extraction, comme toujours), `PROJEQTOR_DATA_DIR` (vide =
`./projeqtor/data`), `PROJEQTOR_DEFAULT_LOCALE` (fr),
`PROJEQTOR_DEFAULT_TIMEZONE` (Europe/Paris). L'authentification LDAP
réutilise les variables `LDAP_*` existantes, rien de nouveau à
renseigner.

## 2026-09-08 — SI_AGENT_* sécurité / notifications, SECRETS_ALERT_* passés au central (livraison #422)

`si-agent-api` : `SI_AGENT_LOG_LEVEL` (INFO), `SI_AGENT_EVENTS_RETENTION_DAYS`
(365), `SI_AGENT_NOTIFY_MIN_SEVERITY` (warning), `SI_AGENT_NOTIFY_COOLDOWN_SECONDS`
(900), `SI_AGENT_NOTIFY_WEBHOOK_URL` (vide). Les canaux SMS / courriel
réutilisent les variables `SECRETS_ALERT_*` du PRA (#206), désormais
listées dans `.env.example` et transmises au conteneur ; un canal
incomplet est ignoré. Le certificat `pki/ca/ca.crt` est monté en lecture
seule dans le conteneur (amorçage TLS des agents par empreinte). Rien à
faire si les défauts conviennent.

## 2026-09-07 — SI_AGENT_* (livraison #421)

Nouveau service `si-agent-api` (central des agents hôtes Linux, tuile
« Agents hôtes ») : `SI_AGENT_API_PORT` (6129), `SI_AGENT_DATA_DIR`
(vide = `./si-agent/data`), `SI_AGENT_PUBLIC_URL` (vide = passerelle
`https://HOST_IP:GATEWAY_PORT/api/si-agent`, affichée dans la commande
d'installation), `SI_AGENT_OFFLINE_SECONDS` (300),
`SI_AGENT_RETENTION_DAYS` (90). Rien à faire si les défauts conviennent.

## 2026-09-05 — KEYCLOAK_SERVICE_CLIENT_ID/SECRET, nouvelles variables (livraison #361)

Nouveau : `KEYCLOAK_SERVICE_CLIENT_ID` (défaut `supervision-si-service`)
et `KEYCLOAK_SERVICE_CLIENT_SECRET` (auto-généré par
`generate-env.sh`) -- compte de SERVICE de bootstrap Keycloak, EN
PLUS de `KEYCLOAK_ADMIN_USER`/`_PASSWORD` existants (jamais à leur
place). Utilisé par `keycloak-backup`, l'import de groupe
`tickets-api` et `keycloak/group_memberships.py` pour s'authentifier
auprès de l'API Admin REST Keycloak -- `grant_type=client_credentials`,
recommandé par Keycloak lui-même pour ce type d'usage automatisé.
Voir `keycloak/README.md` pour le raisonnement complet.

## 2026-09-05 — OWNCLOUD_LONG_PATH_CACHE_TTL, nouvelle variable (version: 1a3daffdfd88)

Nouveau : `OWNCLOUD_LONG_PATH_CACHE_TTL` (livraison #354) -- cache
dédié pour la nouvelle route `GET /long-paths` (owncloud-api,
détection des chemins trop longs pour Windows) -- requête coûteuse
(balaie ~2,5M lignes sans index exploitable), vide = 900s (15 min)
par défaut, bien plus long que `OWNCLOUD_CACHE_TTL` général.

## 2026-09-05 — Annuaire LDAP de test, nouvelle variable + défauts LDAP_* changés (version: 9b057d24cb9d)

Nouveau service `openldap-test` (gateway/docker-compose.yml,
livraison #348) -- répond à "as tu prévu des données ldap ou un
bouchon ldap ?" -- sans lui, aucune connexion possible au hub
(Keycloak n'a aucun utilisateur local humain par défaut).

Nouvelle variable : `LDAP_TEST_ADMIN_PASSWORD` (mot de passe du
compte `cn=admin` de l'annuaire de test -- généré par
`scripts/generate-env.sh`, IDENTIQUE à `LDAP_BIND_PASSWORD`).

**Défauts LDAP_* CHANGÉS** (pointaient vers un hôte fictif
`ldap.example.local`, pointent désormais vers l'annuaire de test
local par défaut) : `LDAP_URL`, `LDAP_BIND_DN`, `LDAP_USERS_DN`,
`LDAP_ROLES_DN`, `LDAP_ADMIN_BIND_DN`, `LDAP_ADMIN_BASE_DN`. Si vous
avez DÉJÀ un `.env` pointant vers un LDAP réel, RIEN à faire --
seules les valeurs de `.env.example` (jamais votre `.env` existant)
changent. Pour un `.env` fraîchement généré, ce nouvel annuaire de
test est actif par défaut -- voir `gateway/README.md` pour les
identifiants (3 comptes, même mot de passe "password").

## 2026-09-05 — 13 variables manquantes ajoutées, trouvées via scripts/check-env.py (version: c6e9ea36668a)

Référencées par `docker-compose.yml` mais jamais documentées dans
`.env.example` jusqu'à cette livraison -- trouvé en diagnostiquant un
déploiement macOS, `check-env.py` les signalait "absentes de .env"
sur un `.env` pourtant complet par ailleurs. Toutes vides = valeur
par défaut du docker-compose (comportement inchangé) :
`SCHEMA_ANALYZER_DATA_DIR`, `NETPROBE_DATA_DIR`, `GEO_DB_NAME`,
`GEO_DB_USER`, `GEO_DB_PASSWORD`, `GEO_DB_PORT`,
`GEO_IMPORT_MAX_MB`, `ELASTICSEARCH_URL`, `ELASTICSEARCH_INDEX`,
`ELASTICSEARCH_TIMEOUT_SECONDS`, `SEARCH_CACHE_TTL`,
`ELASTICSEARCH_HOST_PORT`, `ELASTICSEARCH_JAVA_OPTS`.

## 2026-09-04 — tickets-api : rights-api, passe 7/N -- OAuth Google résolue + balayage GET (version: 46392412f21e)

Livraison #330 -- pas de nouvelle clé (réutilise `TICKETS_RIGHTS_API_URL`).
Limite de la passe 4 résolue : GET /oauth/google/start gardée
(groups en paramètres de requête), protège indirectement le
callback via son contrôle CSRF. Balayage systématique des 37 routes
GET restantes (recherche automatisée de mots-clés SQL d'écriture) --
confirme qu'aucune n'a d'effet de bord caché hormis le callback déjà
traité.

## 2026-09-04 — tickets-api : rights-api, passe 6/N -- contournement via /raw_tables évité (version: 225e0c622cda)

Livraison #329 -- pas de nouvelle clé (réutilise `TICKETS_RIGHTS_API_URL`).
DÉCOUVERTE CRITIQUE : PUT /raw_tables/<table>/<id> est un accès
générique qui aurait pu contourner toute la protection posée sur les
tables déjà gardées ailleurs (users/types/levels/statuts/règles/
matching_config). Corrigé avec une garde CONDITIONNELLE selon la
table ciblée -- reste cohérente avec chaque décision déjà prise,
jamais en bloc. Toutes les routes d'écriture du module sont
désormais examinées.

## 2026-09-04 — tickets-api : rights-api, passe 5/N -- import global + réglages (version: e2196999942c)

Livraison #328 -- pas de nouvelle clé (réutilise `TICKETS_RIGHTS_API_URL`).
Gardé POST /import (même sévérité que le cluster DB/SQL -- mode=replace
vide toute la base) et POST /settings (pilote le moteur de détection
auto). Deux vrais bugs trouvés et corrigés en cours de route : les
deux routes traitaient tout le corps JSON sans filtre, `groups`
aurait fuité dans les données réelles.

## 2026-09-04 — tickets-api : rights-api, passe 4/N -- import calendrier (version: 4c98313f2153)

Livraison #327 -- pas de nouvelle clé (réutilise `TICKETS_RIGHTS_API_URL`).
Gardé les 3 routes d'import calendrier (upload .ics, Google OAuth,
URL secrète iCal) -- même raisonnement que pour les règles de
filtrage : l'entrée du pipeline mérite sa propre protection, pas
seulement sa sortie déjà gardée. Cas particulier : /calendar/import
accepte du contenu brut (ni JSON ni formulaire), `groups` lu depuis
les paramètres de requête pour cette route spécifique.

## 2026-09-04 — tickets-api : rights-api, passe 3/N -- conclusion sur le cœur ticket + règles de configuration (version: 342fb6e2b50b)

Livraison #326 -- pas de nouvelle clé (réutilise `TICKETS_RIGHTS_API_URL`).
Conclusion importante : rien à garder sur le cœur ticket lui-même
(création/édition/messages/temps = actions normales ouvertes à tous
les rôles) -- gardé en revanche les 3 clusters de règles de
configuration partagée (filter_rules/exclusion_rules/priority_keywords,
6 routes) affectant le traitement automatique pour tout le monde.

## 2026-09-04 — tickets-api : rights-api, passe 2/N -- CRUD données de référence (version: dac8fad8fd01)

Livraison #325 -- pas de nouvelle clé (réutilise `TICKETS_RIGHTS_API_URL`
déjà ajoutée en #324). Gardé les 20 routes de gestion des 6 tables
de référence (users/types/sites/levels/statuts/deadline_escalation_rules),
dont 12 couvertes par deux fonctions génériques partagées
(update_reference_row/delete_reference_row).

## 2026-09-04 — tickets-api : branchement rights-api opt-in, passe 1/N -- cluster console DB/SQL (version: 70d0e88b8f7d)

Livraison #324 -- nouvelle clé optionnelle `TICKETS_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). GROS
CHANTIER (85 routes) traité en plusieurs passes. Cette première
passe garde le cluster le plus dangereux : POST /db/sql/execute
(SQL arbitraire), PUT /db/tables/<t>/rows/<id> (édition brute),
POST /backups/<file>/restore (destructif), POST /backups. Jamais
/db/sql/check (confirmé lecture pure). Les ~80 autres routes restent
à traiter dans de futures passes -- voir tickets/README.md.

## 2026-09-04 — vigilance-api : branchement rights-api opt-in (version: d5166ffc3b50)

Livraison #321 -- nouvelle clé optionnelle `VIGILANCE_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Gardé sur
/analyze uniquement -- la seule route d'écriture de ce module
(déclenchement immédiat d'un passage d'analyse, hors du rythme
périodique).

## 2026-09-04 — api centrale : branchement rights-api opt-in, 4 routes gardées, /ingest DÉLIBÉRÉMENT exclu (version: b31af2e84634)

Livraison #320 -- nouvelle clé optionnelle
`CENTRAL_API_RIGHTS_API_URL`, vide par défaut (gating désactivé,
comportement inchangé). Gardé UNIQUEMENT sur la gestion des sources
(from-selection/register/delete/restore) -- JAMAIS POST
/ingest/<source>, appelé par plusieurs pipelines automatisés
(pipeline/, pixel-grid/bridge, imap-client-api, connectors/
zenoss_legacy) sans contexte utilisateur -- le garder aurait cassé
ces flux. Voir api/README.md pour le détail complet.

## 2026-09-04 — schema-analyzer-api : branchement rights-api opt-in, 4 routes gardées (version: e50bbfc8eef5)

Livraison #319 -- nouvelle clé optionnelle
`SCHEMA_ANALYZER_RIGHTS_API_URL`, vide par défaut (gating désactivé,
comportement inchangé). Gardé sur create/update/delete_relation +
import-proposals, jamais /analyze ni /relations/validate (confirmées
lecture pure, aucun effet de bord, malgré le verbe POST).

## 2026-09-04 — geo-import-api : branchement rights-api opt-in, 3 routes gardées (version: 43ca5468683d)

Livraison #318 -- nouvelle clé optionnelle `GEO_IMPORT_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Service
EXPLICITEMENT en écriture -- gardé sur import/fusion/connectors-
geolocations-sync, jamais /correlate (confirmé purement lecture,
uniquement des SELECT, malgré le verbe POST).

## 2026-09-04 — pixel-grid-api : branchement rights-api opt-in, 4 routes gardées (version: 0199da11a653)

Livraison #317 -- nouvelle clé optionnelle `PIXEL_GRID_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Gardé sur
les 4 routes d'écriture (géolocalisations, scan, enregistrement d'IP)
-- jamais la lecture/agrégation.

## 2026-09-04 — architecture-api : branchement rights-api opt-in, 8 routes gardées (version: aa6e8f76e380)

Livraison #316 -- nouvelle clé optionnelle `ARCHITECTURE_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Topologie
DÉCLARÉE (jamais de configuration d'équipement réel) -- gardé sur les
8 routes d'écriture (équipements, import network-agent, interfaces,
liens), jamais la lecture.

## 2026-09-04 — classifier-api : branchement rights-api opt-in, 4 routes gardées (version: c71a44fc69be)

Livraison #315 -- nouvelle clé optionnelle `CLASSIFIER_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Service
CENTRAL (dictionnaire utilisé par d'autres modules) -- gardé sur
import/delete_term/delete_source/confirm (mutation du dictionnaire
partagé), jamais classify/classify_batch.

## 2026-09-04 — nebula-api : branchement rights-api opt-in, 5 routes gardées (version: 33328a9eda55)

Livraison #314 -- nouvelle clé optionnelle `NEBULA_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Gardé sur
les 3 routes d'import CSV (mutualisées) et les 2 routes de
suppression de lots importés -- jamais la consultation. Ce module ne
configure jamais Nebula lui-même, seulement un cache local.

## 2026-09-04 — snmp-api : branchement rights-api opt-in, scope étroit (version: 8c889c6d1498)

Livraison #313 -- nouvelle clé optionnelle `SNMP_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Scope
volontairement étroit : gardé UNIQUEMENT sur create_target/
delete_target -- jamais /query ni /walk-interfaces (limite connue et
assumée, voir snmp/README.md).

## 2026-09-04 — tasks-api : branchement rights-api opt-in, scope étroit (version: 3eedad061e2b)

Livraison #312 -- nouvelle clé optionnelle `TASKS_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Scope
volontairement étroit : kanban délibérément collaboratif (aucune
notion de propriétaire), gardé UNIQUEMENT sur `DELETE /tasks/<id>`
-- jamais create/update/move, usage normal de l'outil.

## 2026-09-04 — ged-api : branchement rights-api opt-in, 5 routes gardées (version: d593ff11850c)

Livraison #311 -- nouvelle clé optionnelle `GED_RIGHTS_API_URL`, vide
par défaut (gating désactivé, comportement inchangé). Gardé sur les
5 routes d'écriture (créer/supprimer un document, nouvelle version,
créer/supprimer un lien), jamais la lecture. `groups` lu depuis
`request.form` pour les 2 routes multipart (upload de fichier).

## 2026-09-04 — imap-client-api : branchement rights-api opt-in, 10 routes gardées (version: e5e82abf47aa)

Livraison #310 -- nouvelle clé optionnelle `IMAP_CLIENT_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Boîte
OPÉRATIONNELLE (notifications système, jamais personnelle) -- gardé
sur les 10 routes d'écriture (dossiers, déplacement, règles,
interprètes), jamais la lecture ni `/interpret` (fonctionnellement
une lecture malgré le verbe POST).

## 2026-09-04 — backup-restore-api : branchement rights-api opt-in (version: ec3128344224)

Livraison #309 -- nouvelle clé optionnelle `BACKUP_RESTORE_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Gardé sur
`create_image`/`delete_image` uniquement -- `/coverage` et `/logs`
restent en lecture libre.

## 2026-09-04 — vault-api : branchement rights-api opt-in, scope étroit (version: 6483dc98a07a)

Livraison #308 -- nouvelle clé optionnelle `VAULT_API_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Contrairement
aux branchements précédents, SCOPE VOLONTAIREMENT ÉTROIT (voir
vault/api/app.py) : seules `revoke_collection_access` et `reset_user`
sont gardées -- jamais `grant_collection_access` (déjà bornée par le
chiffrement de bout en bout, exige de connaître la clé réelle de la
collection) ni les actions self-service (créer son propre compte/
collection, changer son propre mot de passe).

## 2026-09-04 — ssh-tunnels-api : branchement rights-api opt-in (version: bfa83cc2d82f)

Livraison #289 -- nouvelle clé optionnelle `SSH_TUNNELS_RIGHTS_API_URL`,
vide par défaut (gating désactivé, comportement inchangé). Voir
ssh-tunnels/README.md pour la marche à suivre avant de l'activer
(groupe admin_hub à assigner dans Keycloak au préalable).

## 2026-09-04 — ldap-admin-api : branchement rights-api opt-in (version: efe86466c875)

Livraison #290 -- nouvelle clé optionnelle `LDAP_ADMIN_RIGHTS_API_URL`,
même principe que ci-dessus. Voir ldap-admin/README.md.

## 2026-09-04 — vault-admin-api : branchement rights-api opt-in, portail pas encore prêt (version: 38f2e2f5a853)

Livraison #291 -- nouvelle clé optionnelle `VAULT_ADMIN_RIGHTS_API_URL`.
⚠️ Laisser VIDE pour l'instant : vault-admin-portal n'a pas
d'authentification Keycloak, l'activer bloquerait tout le monde.
Voir vault/README.md et BACKLOG.md item 42.

## 2026-09-04 — dba-api : branchement rights-api opt-in (version: db8347e982cc)

Livraison #292 -- nouvelle clé optionnelle `DBA_RIGHTS_API_URL`,
même principe. Candidat sensible : /sql exécute du SQL libre contre
des bases externes. Voir dba/README.md.

## 2026-09-04 — glpi-api : branchement rights-api opt-in (version: c0391175de4f)

Livraison #294 -- nouvelle clé optionnelle `GLPI_RIGHTS_API_URL`,
même principe (suppression d'item, imports vers GLPI). Voir
glpi/README.md.

## 2026-09-04 — rights-api : nouveau module, nouvelle clé (version: d2b5bdd7a866)

Nouveau module -- livraison #283 (service central de droits, groupe
admin_hub, inventaire de fichiers). `RIGHTS_DATA_DIR` (volume de
données, défaut ./rights/data). Voir rights/README.md.

**Chaque nouveau bloc de clés dans `.env.example` porte désormais un
commentaire "Version : au moins depuis {hash}"** (même hash que le
badge affiché sur les 5 fronts, voir `shared/README.md`) — permet de
savoir directement, en lisant `.env.example`, depuis quand une clé
existe, sans repasser par ce journal. `.env.example` est volontairement
exclu du calcul du hash lui-même (sinon y écrire le hash le
changerait) — un bloc annoté "depuis X" restera annoté ainsi même
après d'autres livraisons. Les blocs antérieurs à ce mécanisme
(introduit après coup) ne portent qu'un hash approximatif — "au moins
depuis", jamais l'origine exacte, ce journal reste la source
d'information la plus précise pour ceux-là.

## 2026-09-03 — tasks-api : nouveau module, nouvelles clés (version: c9bf1e636d73)

Nouveau module -- livraisons #271-272 (gestion de tâches Kanban
indépendante des tickets + tuile "ENT"). `TASKS_DATA_DIR` (volume de
données, défaut ./tasks/data). Voir tasks/README.md.

## 2026-09-03 — vigilance-api : nouveau module, nouvelles clés (version: 34e77f1e09d7)

Nouveau module -- livraison #262 (automates d'analyse cyber-vigilance/
santé du parc, backlog item 34, suite de classifier/#260).
`VIGILANCE_DATA_DIR` (volume de données). `VIGILANCE_SERVICE_DIVERSITY_THRESHOLD`
(défaut 10), `VIGILANCE_VOLUME_GROWTH_PERCENT_THRESHOLD` (défaut 200),
`VIGILANCE_ANALYSIS_INTERVAL_SECONDS` (défaut 1800 = 30 min),
`VIGILANCE_RETENTION_DAYS` (défaut 30). ⚠️ Utilise aussi
NETWORK_AGENT_API_URL (nécessite HOST_IP, network-agent-api tourne en
network_mode: host). Voir vigilance/README.md.

## 2026-09-03 — classifier-api : nouveau module, nouvelles clés (version: a008d8a10bc8)

Nouveau module -- livraison #260 (classification sémantique des
identités découvertes, backlog item 34, "à prioriser fort car
central"). `CLASSIFIER_DATA_DIR` (volume de données).
`CLASSIFIER_MAX_IMPORT_MB` (taille max d'un import de dictionnaire,
défaut 5 Mo). Voir classifier/README.md.

## 2026-09-03 — memory-api : nouveau module, nouvelles clés (version: a54e5007166d)

Nouveau module -- livraison #259 (tuile "Mémoire", rémanence du
tampon de logs Memcached, backlog item 32). `MEMORY_DATA_DIR`
(volume de données). `MEMORY_COLLECTION_INTERVAL_SECONDS` (fréquence
de collecte, défaut 300 = 5 min), `MEMORY_RETENTION_DAYS` (défaut
30 jours), `MEMORY_REPOPULATE_COUNT` (défaut 50 -- nombre d'entrées
réinjectées dans Memcached après un redémarrage détecté). Voir
memory/README.md.

## 2026-09-03 — architecture-api : nouveau module, nouvelles clés (version: 43f113664bd4)

Nouveau module -- livraisons #253-254 (vue/outil de parcours de
l'architecture réseau + supervision/usage). `ARCHITECTURE_DATA_DIR`
(volume de données). `GED_API_INTERNAL_URL`/
`SSH_TUNNELS_API_INTERNAL_URL` (croisement direct, valeurs par
défaut déjà correctes). `NETWORK_AGENT_API_URL` (croisement des
niveaux d'usage, ⚠️ nécessite `HOST_IP` -- même piège que
`backup-restore-api`/#249, `network-agent-api` tourne en
`network_mode: host`). Voir architecture/README.md.

## 2026-09-03 — network-agent-api : nouvelles clés pour les relevés périodiques (version: 5e901ac97706)

Nouvelles clés -- livraison #251 ("voir dans le temps... présence des
ip/mac, volumes échangés/usages par paire d'ip") :
`NETWORK_AGENT_SNAPSHOT_INTERVAL_SECONDS` (fréquence des relevés,
défaut 3600 = 1h) et `NETWORK_AGENT_HISTORY_RETENTION_DAYS` (durée de
conservation, défaut 30 jours). Voir network-agent/README.md.

## 2026-09-03 — network-agent-api : nouvelles clés pour la résolution DNS (version: 9d2d88c9de6e)

Nouvelles clés -- livraison #250 ("récupérer le dns et le domain par
défaut depuis l'hôte OU le faire paramétrer") : `NETWORK_AGENT_DNS_SERVER`
(vide = résolveur système par défaut, une IP = serveur DNS précis
interrogé via un client DNS minimal maison) et
`NETWORK_AGENT_DEFAULT_DOMAIN` (suffixe retiré des noms résolus pour
un affichage plus court). Voir network-agent/README.md.

## 2026-09-03 — backup-restore-api : nouvelle clé pour le répertoire de données (version: dff697a4d2c5)

Nouvelle clé -- livraison #249 (suivi/couverture des images de
sauvegarde, backlog item 27, sous-volet Clonezilla marqué urgent) :
`BACKUP_RESTORE_DATA_DIR` (volume de données, vide = valeur par
défaut `./backup-restore/data`). Voir backup-restore/README.md.

---

## 2026-09-02 (suite) — network-agent-api : nouvelles clés pour l'agent d'exploration réseau (version: 90ca3706f044)

Nouvelles clés -- livraison #233 (agent d'exploration réseau unifié,
backlog item 20) : `NETWORK_AGENT_DATA_DIR` (volume de données),
`NETWORK_AGENT_INTERFACE` (interface à capturer, défaut `eth0`),
`NETWORK_AGENT_SITE_NAME`/`NETWORK_AGENT_SEGMENT_LABEL` (REQUIS pour
que la capture démarre réellement), `NETWORK_AGENT_SEGMENT_CIDR`
(optionnel mais fortement recommandé -- sans lui, aucune détection de
passerelle possible), `NETWORK_AGENT_CAPTURE_ENABLED` (désactivable
explicitement). Voir network-agent/README.md.

## 2026-09-02 (suite) — snmp-api : nouvelles clés pour les cibles enregistrées (version: 70459c108719)

Nouvelles clés -- livraison #213 (gestion des paramètres d'accès
SNMP, backlog item 13 volet 2) : `SNMP_DATA_DIR` (volume de données),
`SNMP_CRED_PASSPHRASE`/`SNMP_CRED_SALT` (optionnels -- absent = seul
l'usage ponctuel host+community en direct fonctionne). Voir
snmp/README.md.

## 2026-09-02 (suite) — ssh-tunnels-api : nouvelles clés pour l'authentification SSH par mot de passe (version: 8d63c52ff725)

Nouvelles clés -- livraison #210 (authentification SSH par mot de
passe, backlog item 12) : `SSH_TUNNELS_CRED_PASSPHRASE` (optionnel --
absent = seul le mode par clé fonctionne, comportement inchangé),
`SSH_TUNNELS_CRED_SALT` (généré une seule fois, base64, JAMAIS
régénérer ensuite). Voir ssh-tunnels/README.md pour le détail complet.

## 2026-09-02 (suite) — nebula-api : nouvelle clé pour le stockage des imports CSV (version: 7f9a4ee6a29e)

Nouvelle clé -- livraisons #198-#200 (regroupées, voir CHANGELOG.md
pour le détail complet) : `NEBULA_DATA_DIR` (optionnel, chemin de
stockage du volume SQLite des imports CSV Sites/Devices/Clients --
vide = valeur par défaut `./nebula/data`).

## 2026-09-02 (suite) — nebula-api : nouvelles clés pour la connexion Zyxel Nebula (version: 7021ddd80da2)

Nouvelles clés -- livraison #196 (connexion/consultation Zyxel
Nebula, second besoin immédiat de la demande GLPI) : `NEBULA_API_KEY`
(⚠️ prérequis bloquants avant de la renseigner -- licence Nebula Pro
Pack sur l'organisation ET clé obtenue via un dossier support Zyxel,
jamais en libre-service, voir nebula/README.md), `NEBULA_BASE_URL`
(optionnel, endpoint de staging si fourni par Zyxel).

## 2026-09-02 (suite) — glpi-api : nouvelles clés pour la connexion GLPI (version: 9d98527d64b7)

Nouvelles clés -- livraison #192 (intégration GLPI, import Excel) :
`GLPI_BASE_URL` (vers `apirest.php` d'un GLPI EXISTANT, externe à ce
projet), `GLPI_APP_TOKEN` (optionnel), et UN SEUL des deux modes
d'authentification : `GLPI_USER_TOKEN` (recommandé) OU
`GLPI_LOGIN`+`GLPI_PASSWORD`.

## 2026-09-02 (suite) — imap-client : nouvelle clé pour la base des règles de tri (version: c047f0eb4a8d)

Nouvelle clé -- livraison #190 (règles de tri IMAP, précision de la
personne sur le sens de "filtres") : `IMAP_CLIENT_DATA_DIR` (dossier
optionnel hors de l'arborescence du projet pour la base des règles
-- vide = `./imap-client/data` comme repli, même logique que les
autres `*_DATA_DIR`).

## 2026-09-02 (suite) — ssh-tunnels : nouvelle clé pour le montage SSHFS réel (version: d1a60887d4d0)

Nouvelle clé -- livraison #180 (montage SSHFS réel, backlog
BACKLOG.md #2, demandé explicitement) : `SSH_TUNNELS_MOUNTS_DIR`
(dossier RÉEL sur l'hôte où les partages SSHFS montés deviennent
visibles depuis l'extérieur du conteneur -- vide = `./ssh-tunnels/mounts`
comme repli). Le service lui-même a aussi gagné des privilèges Docker
supplémentaires (`cap_add`/`devices`/`security_opt`, voir
`docker-compose.yml` et `ssh-tunnels/README.md`) -- pas des clés
`.env`, mais à savoir avant un premier `docker compose up` avec cette
version.

## 2026-09-01 (suite) — imap-client : nouvelles clés (version: a8a5cc98d391)

Nouvelles clés -- livraison #179 (client IMAP, backlog BACKLOG.md #4,
volet 1/4) : `IMAP_HOST`/`IMAP_PORT`/`IMAP_USER`/`IMAP_PASSWORD`
(identifiants du compte IMAP consulté, un seul compte pour
l'instant), `IMAP_USE_SSL` (vide = TLS implicite/IMAPS comme repli,
le comportement sûr par défaut), `IMAP_DEFAULT_FOLDER` (vide =
"INBOX" comme repli). Service INACTIF (erreurs 502 explicites) tant
que `IMAP_HOST`/`IMAP_USER` ne sont pas renseignés -- aucune valeur
par défaut fonctionnelle possible ici (pas de serveur IMAP public
générique).

## 2026-09-01 (suite) — rsyslog-listener : nouvelles clés (version: 0a76a49676f8)

Nouvelles clés -- livraison #177 (logs de toutes sortes, étape 4/4,
DERNIÈRE de l'initiative) : `RSYSLOG_LISTENER_PORT` (port UDP
publié DIRECTEMENT sur l'hôte -- syslog ne transite pas par
tls-proxy, protocole réseau brut, pas HTTP -- vide = 5514 comme
repli) et `RSYSLOG_SOURCE_NAME` (nom d'affichage dans le
gestionnaire de logs du hub, vide = "rsyslog").

---

## 2026-09-01 (suite) — prefs-api : sources de logs fichier (version: cd73aad85a3b)

Nouvelle clé -- livraison #176 (logs de toutes sortes, étape 3/4) :
`LOG_FILES_HOST_DIR` (chemin RÉEL sur l'hôte contenant les fichiers
de logs plats à suivre, ex. `/var/log`, monté en LECTURE SEULE --
vide = `./prefs-api/log-files` comme repli, dossier à peupler
manuellement). Même logique que `SSH_TUNNELS_KEYS_DIR` (#159) --
protège contre un accès libre au système de fichiers, un chemin
choisi explicitement plutôt qu'un montage large par défaut.

---

## 2026-09-01 (suite) — ssh-tunnels : nouvelles clés (version: dc729e962194)

Nouvelles clés -- livraison #159 (supervision de tunnels SSH) :
`SSH_TUNNELS_KEYS_DIR` (chemin RÉEL sur l'hôte contenant les clés
privées autorisées, monté en LECTURE SEULE -- vide = ./ssh-tunnels/keys
comme repli, dossier à peupler manuellement) et
`SSH_TUNNELS_DATA_DIR` (base SQLite, même logique que les autres
`*_DATA_DIR`). Voir `ssh-tunnels/README.md`.

---

## 2026-09-01 (suite) — Mayan EDMS + ged : nouvelles clés (version: 059cd78cb8fe)

Nouvelles clés -- stack séparé `mayan/` (livraison #158, "allons-y
pour Mayan EDMS") : `MAYAN_AUTOADMIN_USERNAME`/`PASSWORD`/`EMAIL`
(compte admin créé automatiquement au premier démarrage -- MÊMES
identifiants réutilisés par `ged-api` pour s'authentifier auprès de
l'API REST, garder synchronisé manuellement si l'un des deux change),
`MAYAN_PORT` (port publié sur l'hôte, défaut 8100),
`MAYAN_DATABASE_PASSWORD`/`MAYAN_REDIS_PASSWORD`/`MAYAN_RABBITMQ_PASSWORD`
(mots de passe internes, réseau Docker uniquement). Plus
`GED_MAX_UPLOAD_MB`/`GED_DATA_DIR` pour `ged-api` (livraison #157,
inchangées depuis). Voir `mayan/README.md` et `ged/README.md`.

---

## 2026-08-28 (suite) — PREFS_API_SERVICE_SECRET : compte de service Keycloak pour le provisionnement de clients OIDC en direct (version: b691e8f0a8fd)

Nouvelle clé -- secret du compte de service Keycloak dédié
`prefs-api-service` (droits `manage-clients` UNIQUEMENT, décidé
explicitement plutôt que de réutiliser le mot de passe admin complet).
Permet à l'écran "🔗 Liens externes" du hub de créer/retirer des
clients OIDC en direct, sans redémarrage ni réimport du realm. Voir
keycloak/README.md ("Interface d'intégration Keycloak en direct") pour
la procédure complète et la limite assumée (les rôles realm propres à
une appli externe restent, eux, un ajout manuel).

DOIT être identique ici et dans le secret que Keycloak importe pour ce
même client (généré depuis cette même valeur par `render.py`) --
sinon l'authentification du compte de service échoue silencieusement
côté prefs-api (message d'erreur clair renvoyé à l'admin cela dit, pas
une exception opaque).

## 2026-08-28 (suite) — TRB140_SMS_RELAY_URL : nouveau client OIDC pour le projet séparé trb140-sms-relay (version: a3fa0af001b3)

Nouvelle clé, ajoutée pour intégrer le projet SÉPARÉ trb140-sms-relay
(passerelle SMS Teltonika) au realm Keycloak supervision-si -- client
OIDC dédié + 9 rôles realm (send/full/compose/history/cron/event/
logs/inbox/filters). Voir keycloak/README.md pour la procédure
complète et les valeurs exactes à transmettre au `./setup.sh` de ce
projet-là (issuer/client-id/redirect-uri).

**PAS routée par notre tls-proxy**, contrairement aux autres
`*_PUBLIC_URL` -- renseigner l'adresse RÉELLE où trb140-sms-relay est
déployé, défaut placeholder explicite sinon (même esprit que
`LDAP_URL`).

## 2026-08-28 (suite) — LDAP_ADMIN_BASE_DN : plus de repli silencieux sur LDAP_USERS_DN (version: 52c694caec42)

**Bug réel rencontré**, remonté par la personne (deux captures d'écran
comparant le navigateur LDAP au vrai phpLDAPadmin de son annuaire) :
`LDAP_ADMIN_BASE_DN`, vide par défaut, retombait silencieusement sur
`LDAP_USERS_DN` (variable de Keycloak, une seule unité
organisationnelle comme `ou=accounts`) -- avait du sens tant que ce
module ne servait qu'à réinitialiser des mots de passe utilisateur,
mais masquait tout ce qui est en dehors de cette branche (`cn=admin`,
`cn=keycloak`, `cn=replicator`...) sans qu'aucun message n'indique
pourquoi, maintenant que c'est un vrai navigateur/éditeur d'annuaire
complet.

**Retiré** : ce repli n'existe plus. `LDAP_ADMIN_BASE_DN` doit
désormais être réglée explicitement -- absente, un message d'erreur
clair (503) le dit, plutôt qu'une portée silencieusement trop
restreinte. `LDAP_ADMIN_URL` garde son repli sur `LDAP_URL` (probable
même serveur), c'est uniquement `base_dn` qui perd le sien.

**Chez qui ce bug est déjà là** : tout déploiement existant du front
OpenLDAP qui n'avait jamais réglé `LDAP_ADMIN_BASE_DN` explicitement
doit désormais le faire -- y mettre la RACINE COMPLÈTE de l'annuaire
(ex. `dc=exemple,dc=fr`), pas une seule unité organisationnelle,
puis reconstruire (`--build`).

## 2026-08-27 (suite) — Port de secours Keycloak : plus jamais lié à HOST_IP (version: 1a188afafcad)

**Bug réel rencontré et corrigé**, à la suite du bug `HOST_IP`
ci-dessus : le port de secours Keycloak (`KEYCLOAK_PORT`, accès
direct contournant tls-proxy) était lié spécifiquement à `HOST_IP`.
Si cette IP n'était pas une interface réellement liable par Docker à
l'instant du démarrage, cette liaison échouait et empêchait **tout
le conteneur Keycloak** de démarrer -- 502 Bad Gateway sur
l'authentification entière du projet, alors que `HOST_IP` était par
ailleurs correcte pour les URLs. Vérifié explicitement avec la
personne avant de corriger (une seule carte réseau, LAN uniquement,
aucune interface publique) : lié désormais sur toutes les interfaces
(aucune IP précisée dans `docker-compose.yml`) -- ne peut plus jamais
échouer à la liaison, reste accessible depuis le LAN exactement comme
avant. À reconsidérer si ce projet est un jour déployé sur une
machine à plusieurs cartes réseau (où `0.0.0.0` exposerait aussi ce
port sur une éventuelle interface publique).

## 2026-08-27 (suite) — HOST_IP enfin déclarée dans .env.example (version: e821fd160225)

**Bug réel rencontré**, remonté par la personne (erreur CORS bloquant
toute authentification) : `HOST_IP` est utilisée **36 fois** dans
`docker-compose.yml` pour construire toutes les URLs `VITE_*_URL`
(Keycloak compris), mais n'a **jamais** figuré comme ligne dans ce
fichier de référence -- seulement mentionnée en commentaire. Un
`.env` copié depuis `.env.example` n'avait donc jamais cette clé,
retombant silencieusement sur `localhost` -- fonctionne tant qu'on
accède au hub via `https://localhost:6443/`, casse dès qu'on y
accède par l'IP réelle de la machine (le navigateur traite
`localhost` et une IP comme deux origines DIFFÉRENTES, même sur la
même machine -- blocage CORS sur les échanges avec Keycloak).

**Ajoutée** : `HOST_IP=` (vide par défaut, comme avant -- le
comportement de repli sur `localhost` reste inchangé pour qui n'a
jamais eu besoin d'y toucher). **À renseigner explicitement** avec
l'IP LAN réelle de la machine dès qu'on y accède autrement que par
`localhost` -- symétrique à `VAULT_STANDALONE_HOST_IP`, déjà présente
et déjà correctement utilisée par la personne pour l'instance isolée
du coffre-fort.

**Chez qui ce bug est déjà là** : tout déploiement existant en a
besoin manuellement -- ajouter `HOST_IP=<IP réelle>` à son `.env`
existant PUIS reconstruire (`--build`, pas juste `up`) puisque les
variables `VITE_*` sont figées dans le JS au moment du build, jamais
relues au démarrage.

## 2026-08-24 (suite) — Instance isolée du coffre-fort (version: 33461e64ef72)

Nouvelles clés, toutes optionnelles (vide = valeurs par défaut sans
risque de collision avec le hub) :
- `VAULT_STANDALONE_HOST_IP` — IP/entrée DNS dédiée à cette instance.
  Vide = repli sur "localhost", peu utile en dehors des tests (le but
  même de cette instance est une entrée séparée du hub).
- `VAULT_STANDALONE_GATEWAY_PORT` (7443), `VAULT_STANDALONE_KEYCLOAK_PORT`
  (7180), `VAULT_STANDALONE_ADMIN_LAN_PORT` (7119) — plage 7xxx,
  entièrement libre, jamais en collision avec le hub (6543 notamment
  était déjà pris par `PIXEL_GRID_POSTGRES_PORT`).
- `VAULT_STANDALONE_DATA_DIR`, `VAULT_STANDALONE_PKI_DIR`,
  `VAULT_STANDALONE_KEYCLOAK_IMPORT_DIR` — chemins optionnels, même
  logique que leurs équivalents côté hub.

Aucune nouvelle clé `LDAP_*` : la fédération LDAP existante est
réutilisée telle quelle par cette instance (voir
`vault-standalone/README.md`).

## 2026-08-20 (suite) — Coffre-fort : maître_clefs (accès de secours)

**Nouvelles clés :**
- `VAULT_ADMIN_LAN_PORT=6119` — port du service `vault-admin-api`,
  exposé **directement sur l'hôte** (jamais via la passerelle
  publique tls-proxy, absent de son routage par conception). À ne
  JAMAIS rediriger vers l'extérieur (Apache, pare-feu...).
- `VAULT_ADMIN_ALLOWED_CIDRS=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8`
  — plages IP autorisées à interroger ce service (défense en
  profondeur, en plus du port jamais proxié).
- `VAULT_ADMIN_SMTP_HOST=`, `_PORT=587`, `_USER=`, `_PASSWORD=`,
  `_FROM=`, `_TO=` — alerte email à CHAQUE accès (autorisé ou
  refusé) au dépôt des clés de récupération archivées. Vide = pas
  d'email envoyé (mais l'accès reste journalisé en base dans tous
  les cas).

## 2026-08-20 (suite) — Coffre-fort de codes/secrets

**Nouvelles clés :**
- `VAULT_API_PORT=6117`, `VAULT_PORTAL_PORT=6178` — ports du nouveau
  module coffre-fort (chiffrement de bout en bout, voir
  `vault/README.md`).
- `VAULT_DATA_DIR=` (vide par défaut) — même logique que
  `TICKETS_DATA_DIR`/`DBA_DATA_DIR` : sort `vault.db` de
  l'arborescence du projet. Contient uniquement des blobs chiffrés (le
  serveur ne détient jamais de quoi les déchiffrer), mais reste hors
  de l'arborescence par cohérence avec le reste.

## 2026-08-20 (suite) — DBA : connexion(s) par défaut pré-configurées

**Nouvelles clés :**
- `HUB_SGBD_MYSQL_HOST=`, `HUB_SGBD_MYSQL_PORT=3306`,
  `HUB_SGBD_MYSQL_USER=`, `HUB_SGBD_MYSQL_PASSWORD=`,
  `HUB_SGBD_MYSQL_DATABASE=` — et l'équivalent
  `HUB_SGBD_POSTGRES_*` (port 5432). Amorce une connexion par défaut
  au démarrage de `dba-api`, idempotent (reconnu par un libellé
  réservé, jamais dupliqué ni confondu avec une connexion créée à la
  main). Vide par défaut = rien d'amorcé, comportement inchangé.
  **Distinct des identifiants IPAM/Optick/Zenoss/OwnCloud/Cacti**
  (ceux-là restent réservés à leurs modules respectifs, jamais
  réutilisés ici — envisagé puis explicitement écarté).

## 2026-08-20 (suite) — Préférences liées au compte (thème clair/foncé)

**Nouvelles clés :**
- `PREFS_API_PORT=6115` — port du nouveau service `prefs-api`
  (préférences liées au compte Keycloak, hub et portail tickets).
- `PREFS_DATA_DIR=` (vide par défaut) — même logique que
  `TICKETS_DATA_DIR` ci-dessus.

## 2026-08-20 (suite) — Module DBA (administration multi-SGBD)

**Nouvelles clés :**
- `DBA_API_PORT=6114`, `DBA_PORTAL_PORT=6176` — ports du nouveau
  module DBA (PostgreSQL/MySQL/SQLite, voir `dba/README.md`).
- `DBA_DATA_DIR=` (vide par défaut) — même logique que
  `TICKETS_DATA_DIR` ci-dessus. Contient `dba.db` — connexions SGBD
  configurées, **identifiants en clair** (décision de sécurité
  assumée, voir `dba/README.md`).

## 2026-08-20 (suite) — CA/certificat, dossier configurable

**Nouvelle clé :**
- `PKI_DIR=` (vide par défaut) — dossier contenant `ca/` et `server/`
  (CA interne + certificat serveur), même mécanisme que
  `KEYCLOAK_IMPORT_DIR`/`KEYCLOAK_BACKUP_DIR`/`TICKETS_DATA_DIR`. **Bug
  réel confirmé** : `SEC_ERROR_REUSED_ISSUER_AND_SERIAL` côté
  navigateur — un déploiement qui supprime puis réextrait le projet
  régénère une CA neuve à chaque fois (même nom d'émetteur, même
  numéro de série de départ), collision garantie si une CA plus
  ancienne traîne encore dans le navigateur. Vide = comportement
  historique, rien à changer si vous n'êtes pas concerné.
- **Bug de synchronisation évité avant livraison** (pas rencontré en
  conditions réelles cette fois, repéré en relisant) :
  `pki/scripts/generate-ca.sh` ne lisait que la variable
  d'environnement déjà exportée, jamais `.env` lui-même — `scripts/run.sh`
  n'exporte que `HOST_IP` globalement, donc `PKI_DIR` renseigné
  uniquement dans `.env` (le cas d'usage normal) aurait été
  silencieusement ignoré. Corrigé (même fonction `get_env()` que
  `generate-server-cert.sh`, testé avec `env -u PKI_DIR` pour garantir
  qu'aucune variable d'environnement ne masquait le bug).

## 2026-08-20 (suite) — Base tickets, chemin configurable

**Nouvelle clé :**
- `TICKETS_DATA_DIR=` (vide par défaut) — dossier contenant
  `tickets.db` (base SQLite réelle, pas un secret rendu), même
  mécanisme que `KEYCLOAK_IMPORT_DIR`/`KEYCLOAK_BACKUP_DIR`. **Bug réel
  confirmé** : un déploiement qui supprime puis réextrait le projet à
  chaque livraison (plutôt que d'extraire par-dessus l'existant) perd
  cette base à chaque fois si elle reste dans l'arborescence du
  projet — comptes créés, tickets, tout. Vide = comportement
  historique (`tickets/data-generator/`), rien à changer si vous
  n'êtes pas concerné.

## 2026-08-20 — Sauvegarde Keycloak, dossier configurable

**Nouvelles clés :**
- `KEYCLOAK_BACKUP_INTERVAL_SECONDS=1800` — intervalle entre deux
  sauvegardes automatiques du realm Keycloak (voir `keycloak-backup`
  dans `docker-compose.yml`). 1800 = 30 min.
- `KEYCLOAK_BACKUP_DIR=` (vide par défaut) — dossier où cette
  sauvegarde est écrite. **Distincte** de `KEYCLOAK_IMPORT_DIR`
  (rôles différents, rien n'oblige à les garder au même endroit) —
  bug réel corrigé le même jour : ce chemin était codé en dur avant,
  ne suivait pas `KEYCLOAK_IMPORT_DIR` si celui-ci était personnalisé.
  Même garde-fou anti-`~` que `KEYCLOAK_IMPORT_DIR`.

**Rien à changer si vous n'avez pas personnalisé `KEYCLOAK_IMPORT_DIR`**
— ces deux clés ont un défaut qui reproduit le comportement précédent.

## 2026-08-19 — Entrée unique par chemin (bascule d'architecture)

**Nouvelle clé, la plus importante de cette entrée :**
- `GATEWAY_PORT=6443` — remplace le schéma "un port par service" par
  une entrée unique, routée par chemin (`/app/`, `/tickets/`, `/auth/`,
  `/api/<nom>/`) — voir `tls-proxy/README.md`. **Tous les anciens
  `*_PORT` de service restent dans `.env`** (marqués "historique" en
  commentaire) mais ne publient plus rien directement — seul
  `GATEWAY_PORT` est désormais exposé.

**Nouvelle clé :**
- `TLS_PROXY_UPSTREAM_HOST=` (vide par défaut, retombe sur `HOST_IP`)
  — IP/nom qu'un point d'entrée externe (Apache) utilise pour joindre
  `tls-proxy`, distincte de `HOST_IP` (qui sert au navigateur) si la
  machine Docker est elle-même multi-pattes.

**Clé dont le SENS a changé, pas la valeur — à ne pas manquer :**
- `KEYCLOAK_PORT=6180` — n'est plus vestigial : sert maintenant à
  l'accès direct de secours à Keycloak, réservé au LAN, ajouté le même
  jour (contourne `tls-proxy` entièrement en cas de panne).

## 2026-08-19 — HTTPS autonome (CA interne, sans Let's Encrypt)

**Nouvelles clés :**
- `KEYCLOAK_IMPORT_DIR=` (vide par défaut) — dossier où le realm
  Keycloak rendu (secret LDAP en clair inclus) est écrit,
  personnalisable pour le sortir de l'arborescence du projet. Garde-fou
  anti-`~` (Python/docker-compose ne l'étendent pas automatiquement).
- `TLS_EXTRA_SAN=` (vide par défaut) — noms/IP additionnels dans le
  certificat serveur généré par `pki/`, en plus de `HOST_IP`/
  `localhost`/`127.0.0.1` automatiques.
- `APACHE_SERVER_NAME=` / `APACHE_TLS_DIR=` — pour le générateur de
  config Apache (`apache/render_apache_conf.py`), point d'entrée
  réseau externe.

**Aucune clé existante modifiée** cette session-là — uniquement des
ajouts, votre `.env` d'avant reste valide, juste incomplet pour les
nouvelles fonctionnalités.

---

*Nouvelles entrées à ajouter en haut de ce fichier à chaque session
qui touche `.env` — même discipline que les autres journaux de ce
projet (`tickets/README.md`, `keycloak/README.md`...).*
