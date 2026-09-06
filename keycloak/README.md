# Keycloak — SSO du projet (login/mot de passe via LDAP)

**Depuis la livraison #135, le service `keycloak` (avec `tls-proxy` et
`keycloak-backup`) vit dans `gateway/docker-compose.yml`, un stack
Docker SÉPARÉ du reste de la plateforme — voir `gateway/README.md`
pour le raisonnement complet (pourquoi, réseau Docker partagé,
procédure de migration). Tout ce qui suit dans ce fichier (realm,
rôles, groupes, clients OIDC...) reste inchangé -- seul l'EMPLACEMENT
du service Keycloak lui-même a changé, jamais son contenu.**

Service `keycloak` (port `KEYCLOAK_PORT=6180`), realm **supervision-si**
pré-peuplé et **entièrement paramétré depuis `.env`** : il ne reste
qu'à renseigner les variables de ton annuaire LDAP pour que les
mots de passe soient vérifiés par lui.

## Ce qui est pré-peuplé dans le realm

- **4 rôles realm** — `admin`, `demandeur`, `technicien`, `politique`
  (les mêmes que la colonne `users.role` du portail tickets, pour un
  mapping 1:1 au moment du branchement applicatif).
- **4 groupes** — un par rôle, avec le rôle realm déjà attaché
  (`administrateurs`→`admin`, `demandeurs`→`demandeur`,
  `techniciens`→`technicien`, `direction`→`politique`). Assigner un
  rôle à quelqu'un devient "le mettre dans le groupe" (Users →
  Groups dans la console), plutôt que d'attribuer le rôle un par un.
  Distinct de la fédération LDAP→rôles (`LDAP_ROLES_ENABLED`) : ces
  groupes sont natifs à Keycloak, ne dépendent d'aucune structure de
  groupes déjà existante côté annuaire.
- **3 clients OIDC publics** (Authorization Code + **PKCE S256**,
  pas d'implicit, pas de direct grant), **tous les trois câblés
  côté code applicatif désormais** :
  - `supervision-frontend` → redirige vers le frontend interne (6173)
    — client défini côté realm, **toujours pas consommé par le code**
    (frontend interne sans authentification à ce jour).
  - `tickets-portal` → redirige vers le portail tickets (6175) —
    **câblé** (`react-oidc-context`, voir `tickets/README.md`).
  - `supervision-hub` → redirige vers le hub d'accès (6174) —
    **câblé** (voir `hub/README.md`).
  Les trois embarquent un mapper d'audience vers `supervision-apis`.
- **1 client `supervision-apis`** (bearer-only) — l'audience que les
  APIs vérifieront dans les jetons. **Aucune API ne le fait encore.**
- **Fédération LDAP** `annuaire-ldap` : URL, bind DN/mot de passe,
  base utilisateurs, attributs (username/mail/givenName/sn), filtre
  optionnel, `READ_ONLY` par défaut (Keycloak ne modifie jamais
  l'annuaire).

## Hub d'accès (`hub/`) et portail tickets (`tickets/portal/`) — les deux fronts connectés

Même bibliothèque (`react-oidc-context`), même schéma de connexion
dans les deux — voir `hub/README.md` (premier construit, contient le
détail des deux vrais accrocs rencontrés : dossier d'import Keycloak
vide au premier démarrage, `crypto.subtle` qui exige HTTPS ou
`localhost`) et `tickets/README.md` (repris à l'identique, en plus de
la résolution `login LDAP` → `users.login` via `/portal/profile`
existant). Le frontend interne Supervision SI (`supervision-frontend`)
reste le seul des trois clients encore non consommé côté code.

**Rappel de sécurité, valable pour les deux** : ces portails
authentifient l'accès à eux-mêmes, pas encore aux APIs qu'ils
appellent ensuite (`tickets-api` compris, malgré son client OIDC
maintenant branché côté frontend) — aucune API du projet ne vérifie
de jeton à ce stade.

## Démarrage

```bash
# 1. Renseigner le bloc LDAP_* (et KEYCLOAK_ADMIN_PASSWORD) dans .env
# 2. Rendre le realm et lancer (run.sh fait le rendu automatiquement) :
./scripts/run.sh up -d --build keycloak
# ou à la main :
python3 keycloak/render.py && docker compose up -d keycloak
```

Console d'admin : `http://<hôte>:6180` (compte
`KEYCLOAK_ADMIN_USER`/`KEYCLOAK_ADMIN_PASSWORD`). Vérifier le
branchement annuaire : realm **supervision-si** → *User federation* →
*annuaire-ldap* → **Test connection** puis **Test authentication**,
puis *Users* → *Sync all users*.

`--import-realm` n'importe le realm **qu'au premier démarrage** (il
n'écrase jamais un realm existant). **`./scripts/run.sh up` détecte
maintenant ça automatiquement** (comparaison du realm rendu contre
`keycloak/.last-imported-realm.json`, un marqueur stocké hors du
volume Keycloak pour survivre à sa suppression) : si `.env` ou
`realm-template.json` ont changé depuis le dernier import, il affiche
un résumé des différences et **demande confirmation explicite** avant
de purger le volume — jamais une purge silencieuse, purger perd tout
ce qui n'existe QUE dans Keycloak lui-même (mot de passe LDAP corrigé
à la main dans la console, groupes réajustés après un incident,
sessions actives...). Répondre autre chose que "oui" (y compris juste
Entrée) laisse tout en l'état.

Pour forcer une purge complète volontairement, sans passer par cette
détection : `./scripts/run.sh reset-keycloak` (demande de taper
`RESET` en toutes lettres, plus strict qu'un simple oui/non vu que
c'est irréversible).

## Variables `.env`

| Variable | Rôle | Défaut (OpenLDAP) |
|---|---|---|
| `LDAP_URL` | `ldap://` ou `ldaps://hôte:port` | `ldap://ldap.example.local:389` |
| `LDAP_BIND_DN` / `LDAP_BIND_PASSWORD` | compte de lecture | `cn=lecture,...` / `change-me` |
| `LDAP_USERS_DN` | base de recherche des comptes | `ou=users,dc=example,dc=local` |
| `LDAP_USERNAME_ATTR` | attribut de login | `uid` |
| `LDAP_RDN_ATTR` / `LDAP_UUID_ATTR` | RDN / identifiant stable | `uid` / `entryUUID` |
| `LDAP_USER_OBJECT_CLASSES` | classes d'objet | `inetOrgPerson, organizationalPerson` |
| `LDAP_SEARCH_FILTER` | filtre additionnel optionnel | *(vide)* |
| `LDAP_VENDOR` | `other`, `ad`, `rhds`… | `other` |
| `LDAP_START_TLS` | StartTLS sur port 389 | `false` |
| `LDAP_EDIT_MODE` | `READ_ONLY` conseillé | `READ_ONLY` |

**Active Directory** : les valeurs typiques sont en commentaire dans
`.env.example` (`vendor=ad`, `sAMAccountName`, `objectGUID`, classes
`person, organizationalPerson, user`).

**Rôles via groupes LDAP** (facultatif) : `LDAP_ROLES_ENABLED=true`
ajoute un mapper qui lit les groupes (`LDAP_ROLES_DN`, attribut membre
`LDAP_ROLE_MEMBER_ATTR`) et les projette sur les rôles realm — des
groupes nommés exactement `admin`/`demandeur`/`technicien`/`politique`
donnent donc directement les bons rôles. Sinon, attribution manuelle
des rôles dans la console (Users → Role mapping).

## Sécurité du fichier rendu

`keycloak/import/supervision-si-realm.json` contient le **mot de passe
de bind en clair** (l'import Keycloak ne lit pas les variables
d'environnement) — le dossier `keycloak/import/` est ignoré par git,
seul le gabarit `realm-template.json` (sans secret) est versionné.
`.env` est ignoré aussi ; `​.env.example` sert de référence.

**Ce dossier n'a pas besoin d'être persistant en soi** — l'état réel
de Keycloak (une fois le realm importé) vit dans le volume Docker
`keycloak_data`, pas ici. `keycloak/import/` n'est qu'un artefact
**dérivé** de `.env`, régénérable à volonté par `render.py` — ce qui
mérite d'être protégé/sauvegardé, c'est `.env` lui-même, pas ce
dossier. Le sortir de l'arborescence du projet reste une bonne
pratique d'hygiène si `.env` est déjà géré ainsi (éviter qu'un secret
rendu traîne dans un répertoire qu'on pourrait supprimer/re-cloner
sans y penser) — voir `KEYCLOAK_IMPORT_DIR` juste en dessous.

## Chemin d'import personnalisable (`KEYCLOAK_IMPORT_DIR`)

Vide par défaut = comportement historique (`keycloak/import/` dans
l'arborescence du projet). Pour le sortir ailleurs (absolu ou relatif
à la racine du projet, les deux fonctionnent) :

```bash
# .env
KEYCLOAK_IMPORT_DIR=/etc/supervision-si/keycloak-secrets
```

**Point critique** : `render.py` (qui écrit le fichier) et
`docker-compose.yml` (qui monte le dossier dans le conteneur) lisent
la **même variable, avec le même défaut** — ils restent forcément
synchronisés tant que les deux passent par le même `.env`. Un chemin
divergent entre les deux reproduirait exactement le bug "dossier
d'import vide au premier démarrage" documenté ci-dessous (déjà
rencontré et diagnostiqué en conditions réelles) — c'est précisément
ce que cette contrainte "même variable des deux côtés" empêche.

**Jamais de `~`** (ex. `~/supervision-si/keycloak-secrets`) — rencontré
en conditions réelles : Python ne l'étend pas automatiquement
(contrairement au shell), et `docker-compose.yml` ne le ferait pas non
plus pour le montage de volume correspondant. `render.py` refuse
maintenant explicitement (erreur claire) plutôt que de produire
silencieusement un chemin cassé comme la première fois. Toujours un
chemin absolu explicite : `/home/<utilisateur>/...`, pas `~/...`.

```bash
python3 keycloak/render.py --check   # confirme la destination avant d'écrire
```

## Dépannage

**`AccessDeniedException: /opt/keycloak/data/h2/keycloakdb.mv.db` au
démarrage** : le volume `keycloak_data` a été créé par une version du
`docker-compose.yml` qui le montait sur un sous-chemin inexistant dans
l'image (`data/h2`) — Docker l'a créé appartenant à root, illisible
pour l'utilisateur `keycloak` (UID 1000). Corrigé depuis (montage sur
`/opt/keycloak/data`), mais le volume fautif doit être recréé — il est
vide (Keycloak n'a jamais pu y écrire), aucune perte :

```bash
docker compose rm -sf keycloak
docker volume ls | grep keycloak_data   # repérer le nom exact (<projet>_keycloak_data)
docker volume rm <projet>_keycloak_data
./scripts/run.sh up -d keycloak
```

Ne PAS utiliser `docker compose down -v` : cela supprimerait AUSSI les
volumes PostgreSQL de pixel-grid et des tickets.

**`ldapErrorInvalidCustomFilter` au démarrage** : `LDAP_SEARCH_FILTER`
doit être une expression LDAP **complète, parenthèses incluses** —
`(objectClass=inetOrgPerson)`, pas `objectClass=inetOrgPerson` (certaines
autres applis acceptent ce fragment nu et l'encadrent elles-mêmes ;
Keycloak ne le fait pas). Depuis `keycloak/render.py` : un fragment sans
aucune parenthèse est maintenant **auto-encadré** avec un message
`ℹ️` à l'écran ; des parenthèses présentes mais mal formées font échouer
le rendu avec une erreur claire (rien n'est écrit) plutôt que de laisser
Keycloak planter au démarrage. Si l'erreur revient malgré tout, relancer
`python3 keycloak/render.py` et regarder la valeur produite dans
`keycloak/import/supervision-si-realm.json` → `customUserSearchFilter`.

**Seul le realm `master` apparaît, `supervision-si` est absent — sans
aucune erreur dans les logs** : rencontré en conditions réelles.
`render.py` n'avait jamais tourné avant le tout premier démarrage de
Keycloak (ex. `docker compose up` lancé directement, sans passer par
`scripts/run.sh`) — le dossier d'import (bind mount, ignoré par git)
n'existait donc pas encore sur l'hôte. Docker, sur un bind mount vers
un chemin hôte inexistant, **crée silencieusement un dossier vide**
plutôt que d'échouer ; Keycloak importe zéro fichier et affiche
`Import finished successfully` — techniquement vrai, rien à importer,
mais trompeur si on s'attend à ce que ça confirme un vrai import.
Comme `supervision-si` n'existe pas encore à ce stade, pas de
suppression nécessaire pour corriger — un import réussira cette
fois :

```bash
python3 keycloak/render.py
ls keycloak/import/                       # confirme le fichier avant de relancer
docker compose up -d --force-recreate keycloak
```

Puis vérifier **dans la console** (sélecteur de realm en haut à
gauche), pas seulement dans les logs — `supervision-si` doit
apparaître à côté de `master`.

## Accès direct de secours (réservé au LAN)

`keycloak` publie désormais aussi son port sur `HOST_IP:${KEYCLOAK_PORT:-6180}`
(HTTP simple, lié spécifiquement à `HOST_IP` — jamais `0.0.0.0`, donc
jamais exposé sur une éventuelle patte réseau publique si la machine
est elle-même multi-pattes) — court-circuite `tls-proxy`/l'entrée
unique entièrement. Sans ça, une panne de `tls-proxy` (ou simplement
le temps que Keycloak finisse son démarrage à froid avant que
`tls-proxy` ne le sollicite — `502 Bad Gateway` rencontré en
conditions réelles) prive de tout accès à la console admin, même pour
diagnostiquer/réparer. `http://<HOST_IP>:6180/auth/admin/` — bien
choisir le realm **`master`** dans le sélecteur (pas `supervision-si`)
pour utiliser `admin`/`KEYCLOAK_ADMIN_PASSWORD`.

**Point de confusion classique, rencontré en conditions réelles** :
`admin`/`change-me` échoue si on essaie de l'utiliser pour se
connecter au **hub/portail** (`supervision-si`) — normal, ce compte
n'existe que dans le realm **`master`**, un realm entièrement séparé,
technique, pour administrer Keycloak lui-même. Aucun rapport
hiérarchique entre les deux, aucun écrasement par la fédération LDAP :
les vrais utilisateurs s'authentifient via LDAP contre
`supervision-si`, l'admin Keycloak via `admin`/`change-me` contre
`master` — deux portes différentes, jamais confondues.

## Sauvegarde automatique du realm (`keycloak-backup`)

Service dédié, en tâche de fond, sauvegarde périodique (30 min par
défaut, `KEYCLOAK_BACKUP_INTERVAL_SECONDS`) via l'API Admin REST de
Keycloak (`partial-export`). Écrit dans
`keycloak/backup/supervision-si-realm-backup.json` — snapshot de
secours en cas de besoin, à consulter/restaurer manuellement.

**`render.py` n'utilise PLUS cette sauvegarde comme source — retiré
après un bug réel à deux effets.** L'intention de départ ("préférer la
sauvegarde pour préserver ce qui a été retouché à la main dans la
console") semblait raisonnable, mais Keycloak **masque les
identifiants sensibles dans ses propres exports** (`bindCredential`
devient des astérisques) : utiliser cette sauvegarde comme source
réinjectait donc silencieusement un mot de passe LDAP cassé, peu
importe la vraie valeur dans `.env` — la cause réelle, jamais
identifiée sur le coup, d'un incident LDAP qui a fait perdre du temps
sur plusieurs sessions. Et une fois qu'une sauvegarde existait, un
nouveau client ajouté à `realm-template.json` (`vault-portal`, par
exemple) n'avait plus jamais d'effet tant qu'elle restait présente —
resté invisible plusieurs sessions à cause de ça aussi, avant d'être
repéré et corrigé.

`render.py` rend désormais **toujours** depuis `realm-template.json` +
`.env`, sans exception. Pour préserver un état qui n'existe
QUE dans Keycloak à travers un réimport (appartenances aux groupes,
notamment) : voir `keycloak/group_memberships.py`
(export/`restore-groups`), qui passe par l'API Admin REST listant
utilisateurs/groupes directement, jamais par un export qui masque les
identifiants.

**Dossier configurable** (`KEYCLOAK_BACKUP_DIR`, `.env`) — même
mécanisme que `KEYCLOAK_IMPORT_DIR` (même garde-fou anti-`~`),
délibérément une variable **séparée** : les deux dossiers ont des
rôles différents (l'un est lu par Keycloak au démarrage, l'autre écrit
en continu par le service de sauvegarde), rien n'oblige à les garder
au même endroit. Reste utilisée par `keycloak-backup` lui-même pour
savoir où écrire — seul `render.py` a cessé de la relire.

**Jamais les comptes utilisateurs fédérés LDAP eux-mêmes** dans cette
sauvegarde — ils vivent dans l'annuaire, pas dans Keycloak, rien à en
sauvegarder ici. Ce qui est capturé : configuration du realm, clients
OIDC, rôles, groupes, et la fédération LDAP elle-même (en tant que
composant du realm) — **identifiants masqués par Keycloak lui-même**,
voir plus haut, jamais utilisable tel quel pour restaurer un mot de
passe.

### Échecs répétés d'authentification (#359) → compte de service (#361)

Signalé en conditions réelles par la personne : la toute première
sauvegarde réussit (juste après l'import initial du realm), puis
CHAQUE cycle suivant (~30 min) échoue avec "authentification refusée"
-- sur la MÊME instance Keycloak, sans redémarrage entre les deux,
donc pas un simple décalage entre un `.env` régénéré et un mot de
passe déjà figé dans le realm (l'explication la plus évidente,
écartée par le calendrier exact des journaux).

**Piste envisagée en #359, jamais confirmée à 100 %** : le compte
admin de bootstrap de Keycloak 26 (`KC_BOOTSTRAP_ADMIN_USERNAME`/
`_PASSWORD`) est documenté comme "temporaire" par Keycloak lui-même,
mais la recherche menée à l'époque donnait des signaux
contradictoires sur le mécanisme exact -- diagnostic amélioré dans
`backup-loop.sh` en attendant une confirmation qui n'a finalement
pas été nécessaire (voir ci-dessous).

**Résolu en #361** : la personne a elle-même trouvé, en explorant
l'image Keycloak, la commande `bootstrap-admin service` --
correspond exactement à ce que la documentation officielle
recommande pour ce type d'usage ("a temporary admin SERVICE ACCOUNT
can be a more suitable alternative... for automated scenarios").
Les trois points qui authentifiaient jusqu'ici via
`grant_type=password` sur l'utilisateur de bootstrap
(`keycloak-backup/backup-loop.sh`, `tickets-api`
`_keycloak_admin_token()` pour l'import de groupe, et
`keycloak/group_memberships.py`) basculent tous sur
`grant_type=client_credentials`, compte de service
`KEYCLOAK_SERVICE_CLIENT_ID`/`KEYCLOAK_SERVICE_CLIENT_SECRET`
(nouvelles variables `.env`, secret auto-généré par
`generate-env.sh`). Bootstrap ajouté EN PLUS de l'utilisateur
existant dans `gateway/docker-compose.yml`
(`KC_BOOTSTRAP_ADMIN_CLIENT_ID`/`_CLIENT_SECRET`), jamais à sa place
-- l'utilisateur reste utile pour un premier accès humain à la
console d'admin.

**Non vérifié dans cet environnement** (comme pour tout ce qui touche
un vrai Keycloak) : confirmation que ce changement élimine
effectivement les échecs répétés -- fondé sur la recommandation
OFFICIELLE de Keycloak pour ce cas d'usage précis, plus robuste que
d'attendre une confirmation de cause qui n'était pas garantie
d'arriver. À surveiller au prochain déploiement réel.

## Emails en double dans l'annuaire — assumé, pas contourné

Rencontré en conditions réelles : deux comptes LDAP différents
(`francois`, `francois_ai`) partageant la même adresse email. Par
défaut, Keycloak refuse d'importer le second (`ModelDuplicateException`),
provoquant en cascade une vraie panne : les opérations qui référencent
ensuite ce compte jamais importé (ex. ajout à un groupe) plantent avec
`IllegalStateException: Not found in database`.

**Décidé avec la personne** : pas question de "nettoyer" l'annuaire
pour satisfaire Keycloak — l'intérêt même de la fédération LDAP est de
ne jamais avoir à curer les données à la main pour chaque système en
aval. Corrigé côté realm, pas côté annuaire :
```json
"loginWithEmailAllowed": false,
"duplicateEmailsAllowed": true,
```
**Les deux ensemble, jamais l'un sans l'autre** : activer seulement
`duplicateEmailsAllowed` en gardant `loginWithEmailAllowed: true`
créerait une ambiguïté réelle — si quelqu'un tente de se connecter en
tapant son email plutôt que son identifiant, Keycloak ne saurait pas
lequel des comptes partageant cet email authentifier. Sans impact sur
l'usage actuel : l'identifiant utilisé partout dans ce projet
(`preferred_username`, l'attribut LDAP `uid`) reste le nom
d'utilisateur, jamais l'email — vérifié, aucun code applicatif ne
suppose une connexion par email.

## Droits Keycloak réels pour "Administration Keycloak" (pas juste un lien)

**Bug réel rencontré** : cliquer la carte "Administration Keycloak"
depuis le hub menait à `HTTP 403 Forbidden` / `No realm access` —
attendu et déjà documenté (le rôle applicatif "admin" ne donne pas de
droits Keycloak), mais rencontré pour la première fois en conditions
réelles. Corrigé en accordant réellement ces droits via le client
`realm-management` (présent nativement dans chaque realm, porte les
permissions granulaires d'administration) — attaché aux GROUPES,
cohérent avec le reste du projet :
- **`administrateurs`** → `realm-admin` (droits complets : LDAP,
  clients, utilisateurs, tout).
- **`techniciens`** → lecture seule (`view-users`, `view-realm`,
  `view-clients`, `query-users`, `query-groups`) — peuvent chercher/
  vérifier un compte ou la configuration, jamais la modifier. Choix
  par défaut délibérément prudent, ajustable en un clic dans la
  console (Groups → techniciens → Role mapping) si besoin de plus.

**Non vérifié en conditions réelles** : aucun Keycloak disponible
dans cet environnement de développement pour confirmer que la carte
mène désormais réellement à la console (plutôt que "No realm access").
Nécessite un réimport complet du realm (comme pour tout changement
structurel de groupe).

## Appartenances aux groupes — perdues à chaque purge, capturées et restaurables

Retour réel : après la purge pour ajouter `vault-portal`, les
appartenances aux groupes ont sauté aussi (mais pas l'URL LDAP,
seulement le mot de passe de liaison — deux bugs distincts). Trou
structurel : ces appartenances vivent **uniquement** dans la base
interne de Keycloak — ni dans LDAP (rôles via groupes LDAP désactivé
dans ce projet), ni dans `realm-template.json` (qui définit les
groupes eux-mêmes, jamais qui en fait partie). `keycloak-backup`
existant ne comble pas ce trou : son `partial-export` capture la
structure des groupes, jamais les appartenances individuelles.

**`keycloak/group_memberships.py`** — capture et restaure via l'API
Admin REST (même mécanisme que `keycloak-backup`) :
- `export` : capture {login: [groupes]} dans
  `keycloak/backup/group-memberships.json` — appelé **automatiquement**
  par `run.sh` juste avant toute purge (le seul moment où c'est encore
  possible).
- `restore` : réapplique la dernière capture sur le realm actuel —
  résout les noms en identifiants à chaque appel (jamais des
  identifiants figés, ils changent à chaque réimport). Jamais bloquant
  sur un échec individuel (utilisateur pas encore synchronisé, groupe
  renommé...) — continue et rapporte ce qui a échoué plutôt que de
  s'arrêter au premier problème.

**`./scripts/run.sh restore-groups`** — nouvelle sous-commande, à
lancer manuellement une fois Keycloak redémarré ET la synchronisation
LDAP relancée. Jamais enchaînée automatiquement après un `up` : le
délai de démarrage de Keycloak et le bon moment pour relancer la sync
LDAP varient trop pour être fiables sans confirmation de la personne.

Vérifié réellement : 11 tests (export construit correctement le
mapping, aller-retour JSON fidèle, restauration avec succès ET échecs
mélangés — un utilisateur introuvable ou un groupe supprimé
n'empêchent jamais de traiter les autres correctement).

## Client OIDC pour trb140-sms-relay (projet séparé)

Le projet **trb140-sms-relay** (passerelle SMS Teltonika TRB140, voir
`/areas/trb140-sms-relay.md` côté mémoire -- pas un module de CE
dépôt) a développé son propre support OIDC côté application
(`./setup.sh --keycloak-issuer ... --keycloak-client-id ...
--keycloak-redirect-uri ...`) et avait besoin, côté Keycloak
supervision-si, de trois choses -- faites ici :

1. **Client dédié `trb140-sms-relay`** (`realm-template.json`) --
   public, Authorization Code + PKCE (même patron que les 3 autres
   clients publics), mais **redirectUri PRÉCISE**
   (`__TRB140_SMS_RELAY_URL__/auth/callback`, demandée telle quelle),
   pas un wildcard `/*` comme nos propres fronts -- une appli externe
   avec une spécification exacte mérite d'être prise au mot plutôt que
   d'élargir par habitude. Pas de mapper `audience-apis` : cette appli
   n'appelle jamais nos APIs internes, ce mapper n'aurait aucun sens
   ici. `TRB140_SMS_RELAY_URL` (`.env`) -- **PAS routée par notre
   tls-proxy**, contrairement aux autres `*_PUBLIC_URL` : défaut
   placeholder explicite (`https://trb140-sms-relay.example.local`,
   même esprit que `LDAP_URL`), à renseigner avec l'adresse RÉELLE de
   ce déploiement séparé.

2. **9 rôles realm** ajoutés tels quels, noms exacts demandés (même
   vocabulaire que `/users` côté trb140-sms-relay) : `send`, `full`,
   `compose`, `history`, `cron`, `event`, `logs`, `inbox`, `filters`.
   Descriptions génériques dans `realm-template.json` -- la sémantique
   exacte de chacun vit côté trb140-sms-relay, pas ici. **Aucun groupe
   créé pour ces rôles** (contrairement aux 7 rôles "maison" plus
   haut, chacun avec son groupe) : pas demandé, et cette appli gère
   probablement l'attribution à sa façon.
   ⚠️ **Point de vigilance à transmettre si l'attribution se fait par
   GROUPE côté trb140-sms-relay** : ce projet-ci s'appuie
   volontairement sur le claim `groups` plutôt que sur les rôles
   realm HÉRITÉS d'un groupe pour ses propres 7 rôles, à cause d'un
   bug Keycloak documenté (KEYCLOAK-3469 -- rôles hérités d'un groupe
   pas toujours fiables dans `realm_access.roles`). Si
   trb140-sms-relay lit directement `realm_access.roles` (ce qui
   fonctionne SANS ce risque si les rôles sont assignés DIRECTEMENT à
   l'utilisateur, jamais via un groupe), le même écueil pourrait s'y
   reproduire -- signalé, pas tranché ici, cette appli n'est pas ce
   dépôt.

3. **Valeurs à transmettre à trb140-sms-relay pour son
   `./setup.sh`** (à adapter avec le VRAI `HOST_IP`/`GATEWAY_PORT` du
   déploiement, voir `.env`) :
   ```
   --keycloak-issuer https://<HOST_IP>:<GATEWAY_PORT>/auth/realms/supervision-si
   --keycloak-client-id trb140-sms-relay
   --keycloak-redirect-uri https://<host-trb140-sms-relay>/auth/callback
   ```
   (Format de l'issuer confirmé dans `hub/src/authConfig.js` :
   `${KEYCLOAK_URL}/realms/${KEYCLOAK_REALM}`, avec
   `KEYCLOAK_URL = <passerelle>/auth`, chemin routé par tls-proxy --
   voir `tls-proxy/render_nginx_conf.py`.)

Vérifié réellement : `render.py --check` et rendu complet (écriture
réelle, fichier ensuite supprimé -- jamais livré, `keycloak/import/`
ignoré par git) -- JSON valide, le nouveau client se substitue
correctement (`redirectUris` = exactement l'URL précise attendue,
sans wildcard), les 9 rôles présents dans le realm rendu. Non-
régression confirmée explicitement sur les 4 clients existants (leurs
`redirectUris`/mappers inchangés) et sur les 7 rôles "maison"
(toujours tous là).

## Interface d'intégration Keycloak en direct (compte de service, écran admin du hub)

Backlog "interface d'intégration générique pour une nouvelle
application compatible Keycloak" -- traité différemment de la piste
initialement esquissée (`.env` pilotant `render.py`, voir historique
du cas trb140-sms-relay ci-dessus). Décidé avec la personne :
**totalement paramétrable en ligne**, réservé au groupe
administrateurs, depuis l'écran "🔗 Liens externes" du hub déjà
existant (livraison #121) -- plutôt qu'un mécanisme figé au
redémarrage.

**Compte de service dédié, droits volontairement limités** (choix
explicite de la personne, face à réutiliser directement le mot de
passe admin complet comme le fait
`keycloak/group_memberships.py`) : nouveau client confidentiel
`prefs-api-service` (`serviceAccountsEnabled`, secret `.env`
`PREFS_API_SERVICE_SECRET`), rôle `manage-clients` sur
`realm-management` UNIQUEMENT -- peut créer/modifier/supprimer des
CLIENTS OIDC, **mais pas créer de nouveaux rôles realm** (ça relève de
`manage-realm`, un droit plus large volontairement pas donné). Les
rôles applicatifs propres à une appli externe (comme les 9 rôles de
trb140-sms-relay, `send`/`full`/... ) restent donc un ajout MANUEL
dans `realm-template.json`, même après ce chantier -- limite assumée,
pas contournée.

**Mécanisme** : `prefs-api/keycloak_admin.py` (nouveau module, stdlib
`urllib` uniquement -- même choix que `group_memberships.py`, pas de
nouvelle dépendance) s'authentifie en `client_credentials` (PAS le
grant `password` du compte admin complet) contre
`KEYCLOAK_INTERNAL_URL` (adresse RÉSEAU DOCKER INTERNE,
`http://keycloak:8080/auth` -- jamais tls-proxy ; prefs-api et
keycloak vivent dans deux `docker-compose.yml` séparés depuis la
livraison #135, mais partagent le même réseau Docker explicitement
nommé, voir gateway/README.md). Deux nouvelles routes sur
`prefs-api` : `POST /external-links/<id>/keycloak` (crée le client,
vérifie D'ABORD qu'aucun autre client ne porte déjà ce `clientId` --
Keycloak ne l'empêcherait pas silencieusement) et
`DELETE /external-links/<id>/keycloak` (retire l'intégration,
IDEMPOTENT sur un client déjà absent -- jamais une erreur si supprimé
à la main dans la console Keycloak entretemps). `external_links`
gagne trois colonnes : `keycloak_client_id`, `keycloak_internal_id`
(l'UUID Keycloak, nécessaire pour la suppression -- différent du
`clientId` affiché), `keycloak_redirect_uri` (conservée pour
réaffichage à l'admin après coup, sans quoi elle serait perdue une
fois le formulaire refermé).

Le client créé suit le même patron que les clients internes du projet
(public, Authorization Code + PKCE) mais avec la redirectUri EXACTE
fournie par l'admin (pas un wildcard `/*`, même raisonnement que pour
trb140-sms-relay) et SANS mapper `audience-apis` (une appli externe
n'appelle jamais nos APIs internes).

Côté hub, `ExternalLinksAdminView` (`hub/src/App.jsx`) gagne une
colonne "Keycloak" et un panneau dépliable par lien (🔑, un seul
ouvert à la fois) : formulaire (URI de redirection + identifiant de
client optionnel) si pas encore intégré, ou affichage des trois
valeurs à transmettre à l'appli externe (émetteur/client_id/redirect
URI) si déjà intégré -- l'émetteur est calculé CÔTÉ CLIENT
(`KEYCLOAK_ISSUER`, même formule qu'`authConfig.js`) plutôt que
reconstruit depuis une réponse serveur à chaque affichage.

Vérifié réellement : `keycloak_admin.py` testé en MOCKANT
`urllib.request.urlopen` (aucun Keycloak réel dans cet environnement)
-- requêtes construites correctement (méthode, URL interne, grant
`client_credentials`, en-têtes, corps du client créé : PKCE, pas de
mapper audience-apis), extraction de l'UUID depuis l'en-tête
`Location`, gestion d'erreur (401 avec message orienté vers
`PREFS_API_SERVICE_SECRET`, réseau injoignable, 404 avalé
silencieusement par `delete_oidc_client` MAIS une vraie erreur 500
bien PROPAGÉE -- pas confondue). Routes Flask testées avec
`app.test_client()` en mockant `keycloak_admin` -- provisionnement
réussi, doublon détecté (409) tant côté base que côté Keycloak
(clientId déjà pris ailleurs), panne Keycloak (502, message transmis
tel quel), retrait idempotent, `keycloak_redirect_uri` bien persistée
ET bien effacée au retrait (bug trouvé et corrigé en cours de route :
un premier jet l'oubliait dans la clause d'effacement). Scénario de
migration dédié (base créée exactement à la livraison #121, sans les
3 nouvelles colonnes). Non-régression explicite sur tout le reste de
`prefs-api`. Syntaxe (`ast.parse`, `tsc --jsx`), JSON/YAML valides,
classes CSS toutes présentes, setters cohérents, accolades JS/CSS
équilibrées.

**Non vérifié dans cet environnement** : tout appel RÉEL à l'API Admin
Keycloak (aucun réseau, aucun Keycloak démarré ici) -- seule la
CONSTRUCTION des requêtes a pu être vérifiée, jamais leur exécution
contre un vrai serveur. Rendu visuel réel du nouveau panneau (aucun
navigateur disponible ici).

## Adopter un client Keycloak déjà existant (livraison #125)

Découvert en testant en conditions réelles le premier vrai cas SSO
(Passerelle SMS / trb140-sms-relay) : l'identifiant du client OIDC
est parfois déjà FIXÉ côté application externe (ici, `trb140-sms-relay`,
le même client provisionné À LA MAIN en #123 avec ses 9 rôles realm) --
changer l'identifiant pour éviter la collision casserait
l'application, pas une option.

Le comportement par défaut (409 si un client porte déjà cet
identifiant) reste une protection nécessaire contre une collision
ACCIDENTELLE -- mais un 409 systématique, même dans ce cas légitime,
aurait forcé un contournement gênant. `POST /external-links/<id>/keycloak`
accepte désormais `adopt: true` : au lieu de créer un nouveau client,
rattache le lien au client Keycloak EXISTANT sous cet identifiant --
`keycloak_internal_id` reprend son UUID réel, `keycloak_redirect_uri`
reprend sa VRAIE `redirectUris` relue depuis Keycloak (jamais ce que
l'admin a tapé dans le formulaire -- l'adoption reflète la
configuration réelle, elle ne l'écrase pas). Le 409 "normal" renvoie
maintenant aussi `existing_client: true` et `existing_redirect_uris`
pour que l'écran propose directement l'adoption plutôt qu'une simple
erreur bloquante -- panneau dédié dans `ExternalLinksAdminView`
(`hub/src/App.jsx`), effacé si l'admin change l'identifiant de client.

Vérifié réellement : `app.test_client()` en mockant `keycloak_admin`
-- collision avec `existing_client`/`existing_redirect_uris` bien
renvoyés, adoption réussie (`create_oidc_client` JAMAIS appelé dans ce
cas), `redirect_uri` persistée = la vraie valeur Keycloak et non celle
tapée dans le formulaire, `adopt: true` sans client à adopter -> 404
(jamais un repli silencieux vers une création), client existant sans
aucune `redirectUris` configurée (cas limite) -> retombe sur la
valeur du formulaire sans exception, non-régression explicite sur le
provisionnement normal (sans adoption). Syntaxe, classes CSS toutes
présentes -- y compris une variable CSS inventée (`--border-warning`,
qui n'existe pas dans `shared/theme.css`) repérée et corrigée par la
vérification croisée systématique avant livraison.

## Bug réel trouvé en déploiement (livraison #128) — refus de réimport oublié dès le lancement suivant

Constaté par la personne juste après le correctif de la livraison
#127 : elle a répondu "non" à la première demande de confirmation de
réimport (le temps de finir de préparer `PREFS_API_SERVICE_SECRET`),
puis relancé `./scripts/run.sh up` plus tard -- la question n'a plus
jamais été reposée, alors que Keycloak tournait toujours sur l'ancien
realm (`prefs-api-service` absent).

**Cause réelle** : en toute fin de `scripts/run.sh`, le marqueur
(`keycloak/.last-imported-realm.json`) était copié **inconditionnellement**
dès que "up" figurait dans les arguments de la commande --
**y compris quand la purge avait été explicitement refusée**
juste avant. Résultat : répondre "non" une seule fois suffisait à
faire croire au script, dès le lancement suivant, que le realm rendu
et le marqueur étaient déjà identiques (`cmp -s` ne trouvait plus de
différence) -- silence total, plus jamais de question, alors que le
volume Keycloak réel n'avait jamais été purgé/réimporté. Le refus
explicite de la personne était donc silencieusement annulé dès le
lancement suivant.

**Corrigé** : un indicateur (`REALM_PURGE_DECLINED`) suit désormais
si la purge a été refusée -- la copie du marqueur en fin de script ne
se fait plus que si ce n'est PAS le cas (purge acceptée, ou aucune
différence à traiter dès le départ). Un message explicite
("Marqueur de realm NON mis à jour...") remplace le silence quand le
refus est respecté.

Vérifié réellement : simulation de bout en bout en 4 lancements
séparés (4 vrais processus bash distincts, comme 4 vraies exécutions
successives de `run.sh`) sur le code RÉEL extrait du fichier (jamais
retapé à la main) -- lancement 1 "non" (marqueur non touché),
lancement 2 (la question revient bien -- **exactement le point qui
échouait avant ce correctif**), lancement 3 "oui" (marqueur mis à
jour), lancement 4 (silence, réellement synchronisé). **Contre-preuve**
: la même simulation rejouée avec l'ancien code (mise à jour
inconditionnelle) reproduit fidèlement le bug observé (silence dès le
lancement 2) -- confirme que le correctif cible bien la cause réelle,
pas une coïncidence. Syntaxe (`bash -n`).

**Non vérifié dans cet environnement** : le flux réel complet avec un
vrai Docker/Keycloak (aucun disponible ici) -- seule la logique de
décision (indicateur, copie conditionnelle du marqueur) a pu être
vérifiée par simulation fidèle.

## Bug réel trouvé en déploiement (livraison #127) — détection de changement du realm silencieusement inopérante avec KEYCLOAK_IMPORT_DIR personnalisé

Constaté par la personne : `./scripts/run.sh up -d --build keycloak`
tournait sans jamais afficher le diff/la demande de confirmation de
réimport attendue (voir "Démarrage" plus haut) après la livraison
#124 (nouveau client `prefs-api-service`) -- alors que ce mécanisme
existe précisément pour ce cas. Keycloak continuait de tourner sur
l'ancien realm, `prefs-api-service` absent de la console d'admin,
d'où les 401 rencontrés en testant le SSO.

**Cause réelle** : `KEYCLOAK_IMPORT_DIR` personnalisé dans `.env`
(`keycloak-secrets` chez la personne, au lieu du défaut
`keycloak/import`) -- `render.py` écrit bien le realm au bon endroit
personnalisé (confirmé, jamais en cause), mais
`check_keycloak_realm_change()` dans `scripts/run.sh` avait
`REALM_JSON` **codé en dur** sur l'ancien chemin par défaut. Le
fichier n'existant jamais à cet emplacement figé, `[ -f "$REALM_JSON" ]`
échouait systématiquement -- la fonction retournait alors
immédiatement (`return 0`, "rendu Keycloak indisponible -- rien à
comparer"), sans jamais atteindre le diff ni la demande de
confirmation. **Silencieux** : aucun message n'indiquait que la
détection avait été court-circuitée.

Exactement la MÊME classe de bug déjà rencontrée et corrigée pour
`KEYCLOAK_BACKUP_DIR` (voir commentaire de `resolve_dir()`,
`render.py`) -- un chemin dupliqué en dur plutôt que dérivé d'une
seule source de vérité, qui finit par diverger silencieusement.

**Corrigé** : `REALM_JSON` dérivé en appelant DIRECTEMENT
`resolve_import_dir()`/`parse_env()` depuis `render.py` (import
Python, jamais une seconde implémentation de cette résolution en
bash) -- repli sur le chemin par défaut uniquement si `python3` est
absent ou si `KEYCLOAK_IMPORT_DIR` est invalide (ex. `~`, refusé
explicitement par `render.py`), jamais une variable vide qui
reproduirait le même bug par un autre chemin.

Vérifié réellement : les 3 cas testés directement en bash --
`KEYCLOAK_IMPORT_DIR` absent (retombe sur le défaut), personnalisé
relatif (reproduit EXACTEMENT le cas réel rencontré,
`keycloak-secrets`), et invalide (`~`, retombe proprement sur le
défaut sans variable vide). Scénario de bout en bout reproduisant le
bug observé : fichier rendu SEULEMENT au chemin personnalisé, rien au
chemin par défaut -- confirmé que l'ancien code aurait bien
court-circuité silencieusement (`[ -f ]` échoue), et que le code
corrigé trouve maintenant le bon fichier. Recherché explicitement
toute AUTRE référence codée en dur au même chemin ailleurs dans le
projet -- aucune trouvée, `docker-compose.yml` respectait déjà
correctement `KEYCLOAK_IMPORT_DIR` pour le montage de Keycloak
lui-même. Syntaxe (`bash -n`).

**Non vérifié dans cet environnement** : le flux complet réel
`run.sh up` avec confirmation interactive et purge du volume (aucun
Docker/Keycloak disponible ici) -- seule la logique de résolution du
chemin et la condition `[ -f ]` qui en dépend ont pu être vérifiées
directement.

## Bug réel trouvé en déploiement (livraison #124) — module Python jamais copié dans l'image Docker

Constaté par la personne au premier vrai démarrage (logs réels) :
`prefs-api` plantait en boucle (`ModuleNotFoundError: No module named
'keycloak_admin'`), ce qui a ensuite fait échouer tls-proxy au
démarrage (`host not found in upstream "prefs-api"`) -- **un seul bug,
pas deux** : les `upstream` nginx de tls-proxy sont statiques
(résolus une fois au chargement de la config, voir
`tls-proxy/render_nginx_conf.py`), donc un service backend en
crash-loop rend son nom injoignable côté Docker DNS, ce qui fait
échouer nginx pour TOUS les fronts qu'il sert -- pas seulement celui
en cause. D'où l'impression que "tout le proxy est planté".

**Cause réelle** : `prefs-api/keycloak_admin.py` (nouveau fichier,
livraison #124) n'avait jamais été ajouté à la liste `COPY` explicite
du `Dockerfile` -- ce projet liste chaque fichier `.py` un par un dans
chaque Dockerfile (même motif que `tickets/api/Dockerfile`,
`ldap-admin/api/Dockerfile`...), jamais un `COPY *.py .`/`COPY . .`
générique. Le fichier fonctionnait dans cet environnement de
développement (les deux fichiers `app.py`/`keycloak_admin.py` sont
simplement voisins sur disque, `import keycloak_admin` résout sans
problème) -- mais l'image Docker RÉELLEMENT construite ne contenait
que les fichiers explicitement listés, jamais testée ici faute de
Docker disponible dans cet environnement. Un vrai point aveugle de ce
mode de développement (voir aussi plus haut : "jamais testé contre un
vrai Keycloak"), révélé seulement par un vrai démarrage réel.

**Corrigé** : `COPY prefs-api/keycloak_admin.py .` ajouté au
Dockerfile. Vérifié : c'était le SEUL fichier Python réellement
nouveau créé pendant cette session (les autres fichiers `.py`
touchés -- `app.py`, `render.py` -- étaient déjà listés dans leur
Dockerfile respectif avant modification) -- pas d'autre même bug
ailleurs dans le projet.

**Leçon pour la suite** : quand un nouveau fichier `.py` est créé pour
un backend de ce projet, vérifier SYSTÉMATIQUEMENT qu'il est ajouté à
la liste `COPY` du `Dockerfile` correspondant -- ne jamais se fier au
seul succès d'un `import` testé dans cet environnement de
développement (où tous les fichiers du dépôt sont déjà côte à côte
sur disque, contrairement à l'image Docker qui ne contient que ce qui
est explicitement copié).

## Ce qui n'est PAS encore fait (volontairement)

- **Le hub et le portail tickets consomment Keycloak, le frontend
  interne pas encore** : `supervision-frontend` (Supervision SI) est
  le seul des trois clients réalm sans code applicatif branché
  dessus. Aucune API ne vérifie de jeton, quel que soit le front —
  le realm est déjà taillé pour (client `supervision-apis`
  bearer-only, mapper d'audience sur les trois clients publics),
  reste à câbler côté APIs le jour où ce chantier sera repris.
- **Mode production Keycloak** : `start-dev` + base H2 embarquée
  suffisent pour brancher et valider l'annuaire ; le passage en
  `start` + PostgreSQL dédié + HTTPS reste à faire avant une vraie
  exposition.
- **Non testé contre un vrai Keycloak/LDAP** depuis l'environnement de
  développement (aucun réseau : image non téléchargeable, annuaire
  injoignable). Vérifié ici : JSON du realm valide et contrôlé champ à
  champ, rendu depuis `.env` testé y compris mot de passe à caractères
  spéciaux, YAML compose valide.
- **Sauvegarde automatique — vérifié/non vérifié** : logique de
  priorité sauvegarde-sur-gabarit testée réellement dans `render.py`
  (les deux chemins : présente/absente, copie verbatim confirmée par
  diff), syntaxe de `backup-loop.sh` validée avec `sh` (pas bash,
  comme l'environnement réel du conteneur alpine). **`jq` indisponible
  dans cet environnement de développement** (pas de réseau pour
  l'installer) — l'idiome `.access_token // empty` n'a donc jamais pu
  être exercé réellement, ni le moindre appel à l'API Admin REST de
  Keycloak (`partial-export` compris) contre un Keycloak réel. Premier
  geste utile une fois démarré : `docker compose logs keycloak-backup`
  après le délai initial de 30s, pour confirmer une première
  sauvegarde réussie avant de compter dessus.

## Thèmes de connexion personnalisés (livraison #275)

Skin "hub" intégré par défaut (cohérent avec la palette du hub),
plus une variante sombre "hub-dark" -- voir
`keycloak/themes/README.md` pour le détail complet (sélecteurs
vérifiés, piège de montage Docker évité, ce qui reste non vérifié
faute de navigateur/instance réelle disponible ici).

## Bug réel trouvé en déploiement (livraison #363) — process de build tué par manque de mémoire (OOM)

Signalé en conditions réelles par la personne (journal du conteneur
`keycloak`) : le process Java de l'étape de build Keycloak
("build-and-exit=true", avant même le démarrage réel du serveur) se
faisait tuer -- "Killed", signature Linux d'un OOM killer -- empêchant
tout démarrage.

**Cause** : ce service (comme `keycloak-standalone` de
`vault-standalone/`) n'avait AUCUNE limite mémoire de conteneur
définie. Keycloak (Quarkus, depuis la version 24.0 -- voir
`keycloak.org/2024/03/keycloak-2400-released`) calcule son tas JVM en
POURCENTAGE de la mémoire du conteneur
(`-XX:MaxRAMPercentage=70`/`-XX:InitialRAMPercentage=50`, visibles
dans le journal de build) plutôt qu'une valeur absolue -- confirmé
via recherche que SANS limite de conteneur (`mem_limit`/cgroup),
cette percentage se calcule sur la mémoire TOTALE visible par le
conteneur, qui peut être celle de la VM Docker Desktop entière plutôt
qu'une portion raisonnable. Avec les 40+ conteneurs de ce projet
tournant simultanément, la demande cumulée peut dépasser ce qui est
réellement disponible à un instant donné -- le noyau tue alors le
plus gros consommateur récent (le JVM de build, ici).

**Corrigé** : `mem_limit: 1536m` ajouté aux DEUX services Keycloak du
projet (`gateway/docker-compose.yml` et
`vault-standalone/docker-compose.yml`) -- borne le calcul en
pourcentage à une valeur prévisible (~1 Go de tas max) plutôt que de
laisser Keycloak présumer toute la mémoire de la machine hôte. Valeur
choisie par prudence : des retours communautaires Keycloak montrent
que même 512 Mo peut ne pas suffire pour ce mode développement avec
import de realm.

**Autres services JVM du projet vérifiés par précaution** :
Elasticsearch (`docker-compose.yml`) utilise déjà des valeurs
ABSOLUES fixes (`ES_JAVA_OPTS=-Xms512m -Xmx512m`), jamais affecté par
ce même risque de calcul en pourcentage non borné -- aucun autre
service JVM trouvé dans ce projet.

**⚠️ Si l'OOM persiste malgré cette limite** : le problème est
probablement l'allocation mémoire GLOBALE de Docker Desktop
elle-même (Réglages → Ressources → Mémoire), pas quelque chose que
ce fichier peut compenser -- aucun réglage de conteneur individuel ne
peut suffire si la VM Docker Desktop elle-même est trop limitée pour
faire tourner tous les conteneurs de ce projet à la fois. Réduire le
nombre de stacks lancés simultanément (`gateway`/`mayan`/`main`/
`vault-standalone` -- voir `scripts/run-all.sh`) reste une autre
option si augmenter la mémoire de Docker Desktop n'est pas possible.
