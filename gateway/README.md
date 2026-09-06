# Gateway (`gateway/`) — Keycloak + tls-proxy, stack séparé

Backlog, livraison #135. Demandé explicitement par la personne : une
application externe (trb140-sms-relay) dépend maintenant de la
disponibilité de Keycloak, qui ne devrait plus subir les
redémarrages/arrêts fréquents des ~20 services applicatifs du stack
principal (en évolution constante). `scripts/run-all.sh` est le point
d'entrée central déjà en place pour ce genre de dispatch — ce stack
en devient une troisième cible, aux côtés de `main` et
`vault-standalone`.

**MÊME realm Keycloak que le stack principal** — pas une instance
séparée comme `vault-standalone/` (qui duplique entièrement
Keycloak). Les clients OIDC déjà configurés (ex. `trb140-sms-relay`,
provisionné à la main en #123, adopté depuis l'écran "Liens externes"
en #126) doivent continuer à fonctionner **sans reconfiguration**.

## Pourquoi c'était plus compliqué qu'un simple déplacement de fichiers

Trois obstacles réels, découverts en construisant ce chantier, chacun
résolu avant d'écrire le moindre fichier :

1. **`depends_on` ne fonctionne pas entre deux `docker-compose.yml`
   séparés.** `tls-proxy` dépendait des 21 autres services ; 5 autres
   services (`tickets-api`, `tickets-portal`, `prefs-api`,
   `vault-portal`, `hub`) dépendaient directement de `keycloak`. Toutes
   ces références ont dû être retirées des `depends_on` respectifs
   (recherche SYSTÉMATIQUE dans tout `docker-compose.yml`, pas
   seulement `tls-proxy` — 5 références de plus trouvées que prévu).
   Rendu acceptable par le prérequis livré en #134 : la résolution DNS
   dynamique de `tls-proxy` (voir `tls-proxy/README.md`) fait que
   perdre cet ordonnancement ne fait plus planter quoi que ce soit —
   au pire un 502 transitoire le temps qu'un service démarre. Les
   appels directs à `keycloak` par son nom Docker (ex.
   `KEYCLOAK_INTERNAL_URL=http://keycloak:8080/auth` côté
   `prefs-api`/`tickets-api`) restent, eux, INCHANGÉS — ils
   fonctionnent toujours grâce au réseau partagé (point 2).

2. **Réseau Docker partagé, obligatoire.** Sans lui, `tls-proxy` (et
   les quelques services qui appellent Keycloak directement) ne
   pourraient plus joindre `keycloak`/`frontend`/`hub`/etc. par leur
   nom Docker interne — deux `docker-compose.yml` séparés créent deux
   réseaux ISOLÉS par défaut. Résolu par un réseau NOMMÉ explicitement
   (`SUPERVISION_SI_NETWORK_NAME`, voir `.env.example`), déclaré
   `external: true` des DEUX côtés (ni l'un ni l'autre fichier ne le
   "possède" au sens Compose — jamais supprimé par un `down`), créé de
   façon IDEMPOTENTE par les deux `run.sh` (`docker network create
   ... || true`) -- peu importe lequel démarre en premier.

3. **`.env` et chemins relatifs, ambigus une fois deux `docker-compose.yml`
   en jeu.** Docker Compose cherche `.env` et résout les chemins
   relatifs (`./keycloak/import`, etc.) par rapport au dossier du
   FICHIER compose invoqué, par défaut — un `KEYCLOAK_IMPORT_DIR`
   personnalisé en chemin RELATIF (cas réel rencontré : la personne a
   `KEYCLOAK_IMPORT_DIR=keycloak-secrets` dans son `.env`) se serait
   résolu DIFFÉREMMENT selon le fichier compose utilisé. Résolu avec
   `--env-file "$PROJECT_ROOT/.env" --project-directory "$PROJECT_ROOT"`
   dans `gateway/scripts/run.sh` (voir la fonction `compose()`) — fait
   que TOUS les chemins de `gateway/docker-compose.yml` (délibérément
   écrits SANS préfixe `../`, identiques à l'original) se résolvent
   EXACTEMENT comme s'ils vivaient à la racine, résultat IDENTIQUE
   côté principal et côté gateway, y compris avec un chemin
   personnalisé relatif -- aucun ajustement nécessaire pour ce cas.

## Démarrage

```bash
./scripts/run-all.sh gateway up -d --build
# ou directement :
cd gateway && ./scripts/run.sh up -d --build
```

Sous-commandes spéciales, REPRISES à l'identique de `scripts/run.sh`
(ce sont des opérations Keycloak, elles vivent maintenant ici) :
```bash
./gateway/scripts/run.sh reset-keycloak    # purge + réimport complet, IRRÉVERSIBLE
./gateway/scripts/run.sh reset-ldap-test   # purge + réamorçage de l'annuaire de test, IRRÉVERSIBLE
./gateway/scripts/run.sh restore-groups    # réapplique la dernière capture des groupes
```

**Prompt "realm Keycloak changé" qui revient à chaque exécution**
(livraison #155) : tant qu'aucun marqueur n'existe (jamais réimporté
depuis la création du volume) et que la réponse au prompt est "non",
le script redemande volontairement à CHAQUE exécution -- pour ne
jamais perdre de vue un changement réel en attente (comportement
voulu, bug corrigé en #128). Si le realm n'a en réalité pas changé
(juste jamais marqué comme importé), répondre **"marquer"** au
prompt plutôt que "non" : accepte l'état actuel du volume tel quel
(rien vidé, rien réimporté), mais enregistre le marqueur -- l'alerte
ne reviendra plus pour ce contenu exact.

**Garde-fou LDAP_URL ajouté (livraison #368)** : signalé en
conditions réelles par la personne -- son `.env`, créé AVANT l'ajout
de l'annuaire de test (#348), gardait `LDAP_URL=ldap://ldap.example.local:389`
(placeholder d'origine) -- ce nom ne résout NULLE PART dans le réseau
Docker de ce projet (`UnknownHostException` côté Keycloak à chaque
tentative de connexion). `check_ldap_placeholder_and_block()` ne
vérifiait jusqu'ici QUE `LDAP_BIND_PASSWORD` -- jamais l'URL --
laissant ce cas passer inaperçu jusqu'à l'échec de connexion. Étendu
pour détecter aussi ce placeholder spécifique, avec le même
mécanisme de blocage/confirmation (`reset-keycloak` ET le prompt
automatique de changement de realm en bénéficient tous les deux,
même fonction partagée) -- évite de purger/réimporter pour rien avec
une URL encore fausse. **Piège que ce garde-fou ne peut PAS
détecter** : un `.env` créé APRÈS #348 mais avant un futur
changement de valeur par défaut aurait la MÊME classe de problème
sous un texte de placeholder différent -- ce garde-fou reste
spécifique à CETTE valeur précise, pas une détection générique de
tout décalage `.env`/`.env.example`.

**Rappel important, découvert dans le même échange** : sur un realm
déjà importé, `docker compose down -v` ne suffit PAS à forcer un
réimport propre -- `keycloak_data` est un volume `external: true`
(voir plus haut), jamais touché par `-v` quel que soit le projet
Compose ciblé. Utiliser `reset-keycloak` (ci-dessus) est la manière
SÛRE de repartir propre -- gère la confirmation stricte ET capture
les appartenances aux groupes avant purge, contrairement à un
`docker volume rm` manuel qui perdrait cette capture silencieusement.

### Mot de passe LDAP correct mais authentification refusée quand même (livraison #375)

Signalé en conditions réelles par la personne, APRÈS les correctifs
ci-dessus (LDAP_URL corrigé, `.env` avec `LDAP_BIND_PASSWORD` =
`LDAP_TEST_ADMIN_PASSWORD`, confirmé identique) : Keycloak refusait
quand même l'authentification avec "LDAP: error code 49 - Invalid
Credentials".

**Cause la plus probable (jamais confirmée à 100 %, aucun accès
direct aux conteneurs de la personne pour vérifier)** : contrairement
à `keycloak_data`, les volumes `openldap-test` sont NORMAUX (pas
`external: true`) -- mais le MÊME principe de fond s'applique quand
même : l'image `osixia/openldap` n'amorce ses données QU'À LA
CRÉATION de ses volumes, jamais relue ensuite même si `.env` change
après coup. Si l'annuaire a été démarré une première fois à un moment
où `.env` portait ENCORE un AUTRE mot de passe, le compte admin de
l'annuaire garde CE mot de passe -- indéfiniment, quoi que `.env`
contienne désormais.

**Corrigé** : nouvelle commande `./gateway/scripts/run.sh
reset-ldap-test` -- arrête SEULEMENT `openldap-test` (pas tout le
stack gateway), supprime ses volumes (trouvés par le même filtre
d'étiquette Compose que `reset-keycloak` utilise pour `keycloak_data`
-- jamais un nom de volume en dur, le préfixe dépend de
`COMPOSE_PROJECT_NAME`), confirmation stricte "RESET" identique.
Relancer `gateway` ensuite réamorce l'annuaire entièrement neuf avec
le mot de passe ACTUEL de `.env`.

## Annuaire LDAP de test (`openldap-test`, livraison #348)

Demandé explicitement (2026-09-05, en plein test de déploiement) :
"as tu prévu des données ldap ou un bouchon ldap ?" -- sans un LDAP
fonctionnel, ni la fédération Keycloak (`LDAP_URL` pointant par
défaut vers un hôte fictif) ni `ldap-admin-api` n'ont quoi que ce
soit à consulter, et Keycloak n'a par ailleurs AUCUN utilisateur
local humain dans son realm (juste un compte de service technique) --
aucune connexion possible au hub sans un LDAP, même minimal.

Un conteneur `openldap-test` (image `osixia/openldap`, standard et
largement utilisée) démarre désormais avec `gateway`, amorcé
automatiquement au tout premier lancement avec 3 comptes de test
(`gateway/ldap-seed/bootstrap.ldif`) :

| Utilisateur   | Mot de passe | Usage prévu                          |
|---------------|--------------|---------------------------------------|
| `alice`       | `password`   | Connexion hub (à assigner un rôle Keycloak manuellement -- groupes LDAP désactivés par défaut, `LDAP_ROLES_ENABLED=false`) |
| `bob`         | `password`   | idem |
| `admin_test`  | `password`   | idem -- assigner `admin_hub` pour tester les fonctions réservées |

Compte de liaison (`cn=admin,dc=supervision-si,dc=local`, utilisé à
la fois par la fédération Keycloak en lecture seule ET par
`ldap-admin` en écriture) : mot de passe généré aléatoirement par
`scripts/generate-env.sh`, sauvegardé dans `.env.generated-secrets.txt`
(nécessaire pour se connecter à l'écran `ldap-admin`, jamais stocké
côté serveur pour ce module -- voir `ldap-admin/README.md`).

⚠️ **Données de TEST uniquement** -- même mot de passe trivial pour
les 3 comptes utilisateurs, jamais destiné à un usage réel. Pour du
LDAP réel, remplacer `LDAP_URL`/`LDAP_BIND_DN`/`LDAP_BIND_PASSWORD`/
`LDAP_USERS_DN` (et les `LDAP_ADMIN_*` correspondants) dans `.env`
par votre annuaire existant -- `openldap-test` reste alors simplement
inutilisé (aucun autre service n'en dépend), peut être retiré de
`gateway/docker-compose.yml` ou laissé tourner sans conséquence.

Amorçage LDIF automatique **UNIQUEMENT au tout premier démarrage**
(volume de données vide) -- comportement de l'image `osixia/openldap`,
pas de ce projet : modifier `bootstrap.ldif` après coup n'a AUCUN
effet sur un annuaire déjà initialisé, supprimer les volumes
`openldap_test_data`/`openldap_test_config` pour forcer un réamorçage.

**⚠️ Corrigé (livraison #359)** : le montage du LDIF était marqué
`:ro` (pensé comme protection contre une écriture accidentelle) --
empêchait en réalité le conteneur de démarrer DU TOUT ("path .../
bootstrap/ldif/custom is ... Read-only file system", "/container/
run/startup/slapd failed with status 1"). Signalé en conditions
réelles par la personne : l'image `osixia/openldap` ajuste elle-même
la propriété (`chown`) de CHAQUE volume monté au démarrage, y compris
celui-ci -- un montage lecture seule fait échouer cette étape.
Retiré -- annuaire de TEST mono-utilisateur, écriture techniquement
possible sur ce dossier depuis le conteneur, sans enjeu de sécurité
réel dans ce contexte précis.

**⚠️ Corrigé (livraison #364), puis SUPERSEDÉ (livraison #378)** :
signalé en conditions réelles juste après le correctif #359 -- "rm:
cannot remove '.../bootstrap/ldif/custom': Device or resource busy",
`/container/run/startup/slapd failed with status 1`. Cause : le
script de démarrage de cette image essaie de SUPPRIMER ce dossier
une fois le bootstrap terminé -- un point de montage ne peut PAS être
supprimé par le conteneur (erreur EBUSY, comportement du noyau, pas
un bug de ce projet). Confirmé par recherche -- problème CONNU et
documenté de longue date (`osixia/docker-openldap#179`, 2017,
journal identique au nôtre). `command: ["--copy-service"]` avait été
choisi comme contournement, recommandé par le mainteneur lui-même
(copie les fichiers de service en interne avant traitement plutôt que
d'opérer directement sur le point de montage) -- **mais ce mécanisme
a lui-même un bug CONNU et documenté**
(`osixia/docker-openldap#310`, 2019) : quand le dossier de bootstrap
personnalisé est LUI-MÊME un point de montage séparé (notre cas
exact), la copie interne échoue SILENCIEUSEMENT à recopier ce
sous-dossier précis -- confirmé en conditions réelles par la
personne : le bootstrap personnalisé (alice/bob/admin_test) n'était
PLUS jamais appliqué du tout après ce correctif, Keycloak échouait
ensuite avec "LDAP: error code 32 - No Such Object" sur `ou=users`
(recherche renvoyant 0 résultat).

**Remplacé par `LDAP_REMOVE_CONFIG_AFTER_SETUP=false`** (variable
d'environnement, PAS un changement de commande) -- contournement
DIFFÉRENT trouvé dans la même recherche
(`osixia/docker-openldap#660`) : évite le problème À LA RACINE en
désactivant l'étape de SUPPRESSION des fichiers de config après
amorçage (celle qui échouait à l'origine sur le point de montage,
#359) -- sans jamais passer par un mécanisme de copie qui a lui-même
ses propres angles morts avec des points de montage imbriqués.

⚠️ Les volumes existants (créés avec `--copy-service`, bootstrap
personnalisé JAMAIS réellement appliqué malgré ce que le journal
suggérait) sont dans un état incohérent -- **`reset-ldap-test` requis
après ce correctif** (voir plus haut) pour repartir d'un bootstrap
réellement propre, cette fois avec la configuration corrigée.

### ❌ Ce correctif N'ÉTAIT PAS la vraie cause (livraisons #379/#381)

Signalé en conditions réelles : le problème PERSISTAIT à l'identique
malgré ce remplacement. `--loglevel debug` ajouté temporairement --
même sur un VRAI premier amorçage confirmé (`Database and config
directory are empty...`), AUCUNE trace de "Processing file .../custom/
bootstrap.ldif" n'apparaissait, alors que TOUS les autres fichiers de
bootstrap (schémas, LDIF numérotés de l'image) s'affichaient
normalement à ce niveau de verbosité.

**Vraie cause, confirmée par `docker exec ... ls -la
/container/service/slapd/assets/config/bootstrap/ldif/custom/`
montrant ce dossier VIDE à l'intérieur du conteneur** :
`--project-directory "$PROJECT_ROOT"` (voir `gateway/scripts/run.sh`)
pointe DÉLIBÉRÉMENT vers la racine du projet PRINCIPAL (pas
`gateway/`), pour que d'autres chemins relatifs de ce fichier
(`./keycloak/import`, `./pki/server` -- dossiers PARTAGÉS, à la
racine) résolvent correctement. Mais `./ldap-seed` suivait AUSSI
cette même résolution, alors que ce dossier vit DANS `gateway/`
(`gateway/ldap-seed/`) -- jamais remarqué avant : **Docker Compose
crée SILENCIEUSEMENT un dossier vide quand la source d'un bind mount
n'existe pas sur l'hôte, sans jamais signaler d'erreur** -- exactement
pourquoi aucune trace d'échec n'apparaissait nulle part, dans aucun
journal, à aucun niveau de verbosité, quel que soit le correctif
tenté sur `--copy-service`/`LDAP_REMOVE_CONFIG_AFTER_SETUP`.

**Corrigé** : préfixe `gateway/` ajouté au chemin
(`./gateway/ldap-seed:...`). `reset-ldap-test` À REFAIRE une dernière
fois pour repartir d'un bootstrap réellement propre, cette fois avec
le fichier RÉELLEMENT visible depuis le conteneur.

**Leçon retenue** : deux correctifs successifs (`--copy-service` puis
`LDAP_REMOVE_CONFIG_AFTER_SETUP=false`) ont été tentés sur la
mauvaise hypothèse avant de remettre en question le montage
lui-même -- une vérification directe (`docker exec ... ls`) aurait
révélé le problème dès le début, plus vite qu'une recherche sur les
mécanismes internes de l'image. À généraliser : pour un chemin de
bind mount qui semble "ne rien faire", vérifier D'ABORD sa VISIBILITÉ
réelle depuis l'intérieur du conteneur avant de chercher plus loin.

## ⚠️ Migration depuis le stack principal — À FAIRE UNE SEULE FOIS

Si vous avez déjà un stack principal en fonctionnement (realm
Keycloak configuré, utilisateurs synchronisés, clients OIDC créés),
suivez cette procédure pour **préserver ce realm** plutôt que d'en
repartir vide :

1. **Arrêtez le stack principal** si Keycloak y tourne encore :
   `./scripts/run.sh down` (avec l'ANCIEN `docker-compose.yml`, avant
   cette livraison, si vous mettez à jour en plusieurs temps — sinon
   Keycloak n'y est de toute façon plus défini, rien à arrêter côté
   principal).
2. **Vérifiez le nom réel du volume Keycloak existant** :
   ```bash
   docker volume ls | grep keycloak_data
   ```
   Si le nom affiché n'est **pas exactement** `supervision-si_keycloak_data`
   (ex. votre dossier de projet ne s'appelle pas `supervision-si`),
   renseignez `KEYCLOAK_DATA_VOLUME_NAME` dans `.env` avec le nom
   réel AVANT l'étape suivante — `gateway/docker-compose.yml`
   référence ce volume `external: true`, Compose REFUSERA de démarrer
   si le nom ne correspond à rien.
3. **Démarrez gateway** : `./scripts/run-all.sh gateway up -d --build`
   — Keycloak redémarre en réutilisant le volume EXISTANT (realm,
   utilisateurs, sessions préservés), pas un volume neuf.
4. **Démarrez le reste** : `./scripts/run-all.sh main up -d --build`.
5. Vérifiez l'accès (`https://<HOST_IP>:6443/`, connexion Keycloak de
   bout en bout) avant de considérer la migration terminée.

**Si le volume n'existe pas encore** (tout premier déploiement,
jamais de stack principal lancé avant) : ✅ **géré automatiquement
depuis la livraison #347** -- `gateway/scripts/run.sh` crée désormais
ce volume de façon IDEMPOTENTE (`docker volume create`, ne fait rien
s'il existe déjà) avant tout appel à `docker compose`, couvrant les
deux cas (premier déploiement neuf, ou migration où le volume existe
déjà) sans distinction explicite nécessaire -- plus besoin de la
manipulation manuelle décrite ci-dessus. Trouvé en conditions réelles
(signalé par la personne, premier déploiement sur macOS) : sans
cette création préalable, `external: true` faisait échouer
`docker compose up` avec "external volume ... not found", ce
paragraphe documentait déjà le contournement manuel correspondant --
resté manuel jusqu'à cette livraison plutôt qu'automatisé.

## Vérifié depuis cet environnement / non vérifié

**Vérifié réellement** : YAML valide (`gateway/docker-compose.yml`),
comparaison SYSTÉMATIQUE champ par champ contre les définitions
originales (un vrai bug trouvé et corrigé au passage : le contexte de
build de `keycloak-backup` aurait cassé le `COPY backup-loop.sh` du
Dockerfile), recherche EXHAUSTIVE de toute référence pendante à
`keycloak`/`tls-proxy`/`keycloak-backup` dans le fichier racine (5
trouvées, toutes corrigées). Simulation de bout en bout de
`gateway/scripts/run.sh` (Docker simulé via une fonction, mais
`render.py`/PKI/`render_nginx_conf.py` RÉELLEMENT exécutés) --
confirmé : réseau créé, détection HOST_IP, rendu du realm au bon
chemin, génération CA/certificat réels, rendu nginx (22 services),
détection de changement de realm (garde-fou LDAP, capture des
groupes, purge du volume), et l'invocation `docker compose` finale
avec EXACTEMENT les indicateurs attendus (`-p`, `--env-file`,
`--project-directory`, `-f`) dans le bon ordre. Syntaxe bash
(`bash -n`) sur les deux scripts.

**Non vérifié dans cet environnement, faute de Docker et de nginx
disponibles ici** :
- Le comportement RÉEL du réseau Docker partagé (`external: true`
  des deux côtés, création idempotente) -- la logique a été
  raisonnée et documentée avec soin, jamais exécutée contre un vrai
  démon Docker.
- La référence `external: true` au volume Keycloak existant --
  jamais testée contre un vrai volume préexistant.
- Toute la syntaxe nginx (résolution DNS dynamique, livraison #134) --
  voir `tls-proxy/README.md`.
- Le comportement de `launcher` (démarrage/arrêt par service depuis
  le hub) vis-à-vis de ce second projet Compose -- PAS retouché dans
  cette livraison, hors périmètre de la demande ; `launcher` ne
  connaît aujourd'hui que le projet Compose principal
  (`COMPOSE_PROJECT_NAME`), pas `supervision-si-gateway` -- à
  reprendre séparément si utile.

**Premier test réel à faire, avant tout le reste** : sur une machine
de test (jamais en production directement, vu l'ampleur du
changement) -- `./scripts/run-all.sh gateway up -d --build`, vérifier
que Keycloak et tls-proxy démarrent, PUIS `./scripts/run-all.sh main
up -d --build` et vérifier que le hub/portail tickets/etc. démarrent
et restent joignables via `https://<HOST_IP>:6443/`. Si quelque chose
casse, cette livraison (#135) est le point de rollback le plus
précis -- revenir à la livraison #134 restaure l'ancien
`docker-compose.yml` à un seul fichier, testé et utilisé depuis le
début de ce projet.
