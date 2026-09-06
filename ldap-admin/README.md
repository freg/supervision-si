# Front de gestion OpenLDAP (administrateurs)

Chantier #4 de la file, sensible par nature (annuaire externe à
l'organisation, potentiellement le même que celui fédéré par
Keycloak pour l'authentification de toute la plateforme) — traité
avec le même niveau de soin que le chiffrement du coffre-fort en son
temps : décisions clarifiées explicitement avec la personne avant
tout code, vérifications empiriques avant de construire dessus,
tests exhaustifs à chaque étape.

## Décisions prises avec la personne

- **Annuaire** : externe, potentiellement le même que celui de
  Keycloak, mais **configurable séparément** — jamais supposé être
  la même instance.
- **Compte de liaison** : celui de Keycloak est en lecture seule
  (`LDAP_EDIT_MODE=READ_ONLY`, voir `.env.example`) — ce module
  utilise ses propres variables `LDAP_ADMIN_*`, un compte capable
  d'écriture, à configurer explicitement (jamais de valeur par
  défaut pour des identifiants d'écriture).
- **Qui peut réinitialiser un mot de passe** : tous les
  administrateurs (groupe Keycloak `administrateurs`), vérifié côté
  interface (pas encore construite) — même posture de confiance que
  le reste du projet, aucune deuxième couche d'autorisation côté
  serveur.
- **Format des sauvegardes** : LDIF standard (RFC 2849), **jamais**
  un format maison — réinjectable directement avec `ldapmodify`/
  `ldapadd` depuis un shell, indépendamment de cette interface.
- **Historique** : "façon git" — diff entre deux sauvegardes,
  construit PAR-DESSUS le format LDIF standard, pas à sa place.

## Architecture

**Aucune bibliothèque LDAP Python** (`ldap3`, `python-ldap`) —
impossible à installer ni tester dans l'environnement de
développement (pas de réseau, pas de serveur LDAP réel disponible).
À la place : sous-processus vers les **vrais binaires**
`ldapsearch`/`ldapmodify` (paquet `ldap-utils`), même motif déjà
établi et éprouvé dans `tickets/api/backup_manager.py` pour
PostgreSQL (`pg_dump`/`psql`) — dépendances (exécuteur de
sous-processus) injectées en paramètre, jamais un appel direct en
dur.

- `ldif_tools.py` — parsing et diff LDIF (RFC 2849), pur Python,
  testé intégralement sans dépendance externe (24 tests) : multi-
  valués, base64 (texte et binaire), repliement de ligne, `dn::`
  encodé, diff "façon git" (ajouts/suppressions/modifications,
  détail attribut par attribut).
- `ldap_client.py` — construction des commandes `ldapsearch`/
  `ldapmodify`, hachage SSHA pur Python (`{SSHA}`, le schéma
  standard OpenLDAP, calculé côté client plutôt que de compter sur
  un overlay serveur), mot de passe de liaison **jamais** en
  argument de ligne de commande (fichier temporaire, permissions
  600, toujours supprimé même en cas d'erreur) (33 tests).
- `ldap_backup.py` — sauvegardes LDIF horodatées, rétention, lecture
  sécurisée contre la traversée de chemin (9 tests).
- `app.py` — routes Flask : `/users` (liste), `/users/<dn>/password`
  (réinitialisation, sauvegarde automatique avant), `/backups`
  (liste/création/lecture), `/backups/diff` (historique façon git),
  `/apply` (application directe d'un LDIF, sauvegarde automatique
  avant) (21 tests).

**Total : 87 tests réels sur ce backend, tous passants.**

## Réserve honnête

Aucun serveur LDAP réel ni binaires `ldap-utils` disponibles dans
cet environnement de développement (pas de réseau). Tout ce qui
touche à la **construction** des commandes et à la **gestion des
réponses** est testé à fond avec des simulations (faux sous-
processus injecté), mais aucune vraie commande `ldapsearch`/
`ldapmodify` n'a pu être exécutée contre un vrai serveur — à
vérifier en conditions réelles, même réserve que pour le chemin
PostgreSQL de `backup_manager.py`.

## Configuration

Nouvelles variables (`.env.example`) : `LDAP_ADMIN_URL`,
`LDAP_ADMIN_BIND_DN`, `LDAP_ADMIN_BIND_PASSWORD`,
`LDAP_ADMIN_BASE_DN`, `LDAP_ADMIN_BACKUP_RETENTION_COUNT`,
`LDAP_ADMIN_DATA_DIR`. URL/base vides = repli sur
`LDAP_URL`/`LDAP_USERS_DN` (Keycloak) ; bind DN/mot de passe
**jamais** de repli, doivent être renseignés explicitement.

Nouveau service `ldap-admin-api` dans `docker-compose.yml`, routé
via `tls-proxy` (`/api/ldap-admin/`).

**Bonus de sécurité en marge de ce chantier** : la liste
`depends_on` de `tls-proxy` était incomplète depuis un moment
(`dba-api`, `dba-portal`, `prefs-api`, `vault-api`, `vault-portal`
manquaient, alors que le routage nginx généré les référence déjà
tous) — exactement le mécanisme ayant causé l'incident du
2026-08-26 (nginx refusant de démarrer, hôte non résolvable).
Complétée par prudence, `ldap-admin-api` y ajouté aussi.

## Interface — mot de passe de liaison jamais stocké

Suite directe du backend, avec une modification de sécurité demandée
explicitement en cours de route : **le mot de passe de liaison
n'est jamais pré-configuré ni conservé côté serveur** — retiré de
`.env.example`/`docker-compose.yml`, remplacé par un en-tête HTTP
(`X-LDAP-Bind-Password`) exigé à **chaque requête** qui a besoin
d'une vraie connexion LDAP. Vérifié explicitement : une requête sans
cet en-tête est refusée (401) **même juste après un accès réussi** —
rien n'est mémorisé côté serveur d'une requête à l'autre. Seuls
`url`/`bind_dn`/`base_dn` (des paramètres de connexion, jamais un
secret) restent configurés côté serveur.

**Nouveau module `ldap-admin/portal/`** (React, même structure que
`dba/portal/`) :
- **Écran de déverrouillage** — demande le mot de passe de liaison à
  l'ouverture, conservé uniquement en état React (mémoire), **jamais**
  dans `localStorage` ni un cookie. Rechargement de page = re-
  verrouillage automatique. Toute erreur d'authentification (401)
  reverrouille aussi l'écran, jamais un état "déverrouillé" trompeur
  si le mot de passe en mémoire ne fonctionne plus côté serveur.
- **Onglet Utilisateurs** — liste, réinitialisation de mot de passe
  avec confirmation renforcée (taper le `uid` de la personne pour
  confirmer une action irréversible, pas un simple `window.confirm`).
- **Onglet Sauvegardes** — liste, déclenchement manuel,
  téléchargement du LDIF brut (réinjectable tel quel avec
  `ldapmodify`/`ldapadd`), et la vue "historique façon git" (diff
  entre deux sauvegardes, ajouts/suppressions en évidence, détail
  attribut par attribut pour les entrées modifiées).

**Vigilance renforcée après l'incident du Dockerfile de la veille**
(`tickets-api` en boucle de plantage faute d'un fichier oublié dans
`COPY`) : vérification systématique, fichier par fichier, que tout
ce qui est importé par le code est bien copié dans l'image Docker.
Confirmé pour `ldap-admin/api` (liste explicite des 4 fichiers `.py`)
et `ldap-admin/portal` (copie large du dossier entier, aucun risque
d'oubli individuel).

**Câblage complet** : nouveau service `ldap-admin-portal`
(`docker-compose.yml`), routage `tls-proxy` (`/ldap-admin/`), carte
dans le Hub (`buildFrontsList`, admin uniquement — même motif que
DBA).

Vérifié réellement : 23 tests supplémentaires sur cette tranche (16
sur le nouveau comportement d'en-tête côté backend, 7 sur
l'injection côté client) -- **110 tests au total sur ce chantier**.
Toutes les classes CSS utilisées par le JSX vérifiées présentes une
par une (script automatisé). Non-régression complète sur tout le
projet.

## Reste à construire

- Chantier hors périmètre immédiat, noté explicitement par la
  personne comme secondaire lors de la demande initiale : restore
  "au sens strict" (revenir à l'état exact d'une sauvegarde
  antérieure) nécessiterait de calculer un LDIF de différences
  inverses — pas encore construit, `/apply` permet pour l'instant
  d'appliquer n'importe quel LDIF (dont un export antérieur tel
  quel, en changetype approprié), pas une vraie "restauration"
  automatisée.
- **Non vérifié dans cet environnement** : rendu visuel réel (aucun
  navigateur disponible ici) et bien sûr toute connexion LDAP réelle
  (aucun serveur LDAP ni binaires `ldap-utils` disponibles) — à
  confirmer par la personne en conditions réelles, une fois
  `LDAP_ADMIN_URL`/`LDAP_ADMIN_BIND_DN`/`LDAP_ADMIN_BASE_DN`
  configurés dans son `.env`.

## Navigateur en colonnes façon phpLDAPadmin/Finder

Demandé explicitement après un aperçu de la structure réelle de
l'annuaire de la personne (captures d'écran phpLDAPadmin) : la
simple liste plate d'utilisateurs ne rendait pas compte de la vraie
hiérarchie (`dc=racine` → `ou=accounts` → `ou=external`/`ou=groups`/
etc. → utilisateurs).

**Backend** : nouvelle route `GET /entries` -- expose **toute**
l'arborescence (structure ET utilisateurs), contrairement à `/users`
(conservée telle quelle) qui ne renvoyait que les entrées avec un
`uid`. Attributs sensibles (`userPassword`, clés Kerberos, mots de
passe Samba) systématiquement exclus de la réponse, vérifié
explicitement -- jamais envoyés au navigateur même s'ils sont
présents dans l'export LDIF sous-jacent.

**Construction de l'arbre côté client** (`ldapTree.js`, pur, testé
sans backend) : chaque DN encode déjà sa hiérarchie complète (ex.
`uid=bob,ou=external,ou=accounts,dc=exemple,dc=fr`) -- aucun
appel réseau supplémentaire nécessaire, l'arbre entier se déduit de
l'unique export déjà récupéré. `usersUnder(tree, dn)` -- le
mécanisme central de la colonne finale ("les filtres = les groupes
sélectionnés") : descend récursivement depuis n'importe quel nœud et
ne retient que les entrées ayant un `uid` -- distingue correctement
un groupe (`cn` sans `uid`) d'un utilisateur, même en profondeur.

**Interface** (`LdapBrowser`, remplace l'ancien `UsersTab`) :
- Une colonne par niveau de profondeur, la sélection dans une colonne
  détermine le contenu de la suivante (navigation en cascade, comme
  demandé).
- Dernière colonne : tous les utilisateurs sous le nœud actuellement
  sélectionné, peu importe la profondeur -- réinitialisation de mot
  de passe conservée à l'identique (confirmation par saisie du uid).
- Bascule "🌳 Arbre" / "{ } JSON" -- la vue JSON affiche les attributs
  bruts du nœud sélectionné, utile pour du diagnostic.
- Arbre chargé **une seule fois** au montage -- toute la navigation
  ensuite est locale (aucun aller-retour réseau par clic de colonne).

**Bug réel trouvé et corrigé avant livraison** : `res.error` au lieu
de `res.data.error` dans la gestion d'erreur du chargement (l'API
renvoie `{ok, status, data}`, jamais `{ok, status, error}`
directement) -- repéré en relisant, avant tout test.

Vérifié réellement : 36 tests supplémentaires sur cette tranche (10
sur `/entries`, y compris la garantie de sécurité la plus importante
-- aucun mot de passe ne fuit jamais ; 26 sur la construction de
l'arbre, contre une structure représentative de la vraie capture
d'écran fournie -- profondeur multiple, groupes correctement
distingués des utilisateurs, entrée orpheline jamais perdue).
Classes CSS vérifiées une par une par script automatisé, y compris
celles construites en littéral de gabarit. Non-régression complète
sur tout le module.

**Non vérifié dans cet environnement** : rendu visuel réel (aucun
navigateur ici) -- la navigation en colonnes mérite particulièrement
d'être testée en conditions réelles vu qu'il s'agit d'une interaction
riche.

## Édition d'attributs à tous les niveaux, y compris les feuilles

Signalé par capture d'écran (comparaison directe avec phpLDAPadmin) :
le navigateur en colonnes ne permettait pas d'accéder au contenu du
dernier élément sélectionné. Cause : une feuille sans `uid` (un
groupe comme `cn=Parapheur`, avec ses attributs `description` et
`member` multi-valué) n'apparaissait nulle part -- la colonne finale
ne montrait que les "utilisateurs sous cette sélection", jamais
l'entrée elle-même.

**Backend** : `ldap_client.build_modify_ldif(dn, attr_changes)` --
pure, remplace entièrement les valeurs de chaque attribut listé
(jamais un diff incrémental add/remove, plus simple et prévisible :
"voici l'état final voulu"). Une liste vide supprime complètement
l'attribut (`delete:`). Plusieurs attributs dans le même changement,
séparés par `-` (syntaxe LDIF standard, RFC 2849). Nouvelle route
`PUT /entries/<dn>` -- sauvegarde automatique avant toute écriture
(même principe que la réinitialisation de mot de passe), attributs
sensibles (mots de passe, clés) explicitement refusés ici -- toujours
passer par la route dédiée, qui seule garantit le hachage SSHA.

**Interface** : nouveau panneau "📋 Détail de la sélection", toujours
visible sous les colonnes (peu importe le mode arbre/JSON) --
affiche TOUTE entrée actuellement sélectionnée avec ses attributs
réels, chacun éditable (valeurs multiples ajoutables/retirables
individuellement, ex. `member`). Attributs sensibles affichés mais
non modifiables ici, avec renvoi explicite vers la réinitialisation
de mot de passe. Un bouton "Enregistrer" n'apparaît actif que si
quelque chose a réellement changé.

Vérifié réellement : 24 tests supplémentaires sur cette tranche (13
sur `build_modify_ldif`, dont le cas exact de la capture d'écran --
groupe multi-attributs avec `member` à 3 valeurs ; 11 sur la route
`PUT /entries/<dn>`, dont le refus explicite de `userPassword`
insensible à la casse). Classes CSS toutes vérifiées présentes.
Non-régression complète sur tout le module (170 tests désormais au
total sur ce chantier).

**Non vérifié dans cet environnement** : rendu visuel réel, aucune
vraie modification testée contre un serveur LDAP réel (toujours aucun
disponible ici) -- la construction du LDIF de modification est
correcte et testée à fond, mais son application réelle reste à
confirmer par la personne.

## Racine manquante, attributs inaccessibles sur les feuilles -- trois bugs corrigés

Signalé par deux captures d'écran (comparaison directe avec
phpLDAPadmin) : trois manques distincts.

**1. La racine réelle de l'annuaire n'apparaissait jamais.** Cause :
`LDAP_ADMIN_BASE_DN` repliait silencieusement sur `LDAP_USERS_DN`
(Keycloak, une seule unité organisationnelle) si non réglée --
avait du sens tant que cet outil ne servait qu'à réinitialiser des
mots de passe, mais masquait tout ce qui est en dehors (`cn=admin`,
`cn=keycloak`...) sans aucun message d'erreur. **Corrigé** : ce repli
est retiré -- `LDAP_ADMIN_BASE_DN` doit désormais être réglée
explicitement (typiquement la racine complète, ex.
`dc=exemple,dc=fr`), absente = message d'erreur clair (503) plutôt
qu'une portée silencieusement trop restreinte.

**2. Impossible de voir/éditer les attributs d'une feuille** (ex. un
groupe `cn=Parapheur` avec son attribut `member`, sans jamais de
sous-arbre LDAP). **Corrigé** : `buildColumns` (`ldapTree.js`)
produit désormais une colonne pour CHAQUE niveau de sélection, y
compris pour une feuille sans enfants -- cette colonne a un `parentDn`
(la feuille elle-même) mais une liste d'enfants vide, permettant d'y
afficher ses attributs.

**3. Les attributs n'apparaissaient que dans un panneau séparé en
bas**, jamais intégrés à la navigation elle-même. **Corrigé** :
`EntryDetailPanel` (déjà existant) est maintenant intégré EN TÊTE de
chaque colonne (mode `compact`), juste au-dessus de la liste de ses
enfants -- demandé explicitement ("la colonne suivante doit montrer
en tête les attributs, et plus bas les nœuds fils"). L'ancien
panneau "📋 Détail de la sélection" en bas de page est retiré, devenu
redondant.

**Sélectionner un utilisateur dans la liste finale** (récursive, à
droite) affiche désormais aussi son détail -- dans une colonne
séparée de la navigation (`recursiveUserDetailDn`, distincte de
`selectedPath`), puisqu'un utilisateur listé là n'est pas forcément
un enfant direct du dernier niveau de navigation.

Vérifié réellement : 9 tests sur `buildColumns`, dont le cas exact
décrit (une feuille comme `cn=Parapheur` produit bien sa propre
colonne d'attributs malgré l'absence d'enfants), et la confirmation
que la racine apparaît bien seule en colonne 0 plutôt que sauter
directement à `ou=accounts`. Classes CSS toutes vérifiées présentes.
Non-régression complète (69 tests relancés sur les fichiers
concernés).

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur disponible ici -- cette refonte de l'interaction mérite
particulièrement votre retour en conditions réelles.

## JSON complet et navigable

Demandé explicitement : le mode "{ } JSON" ne montrait jusqu'ici que
les attributs du nœud sélectionné dans la navigation en colonnes --
jamais l'arbre entier, et rien de navigable dans cette vue-là
spécifiquement.

**`JsonTreeNode`** (nouveau composant récursif) -- affiche
l'intégralité de l'arbre LDIF depuis la/les racine(s), chaque nœud
avec un bouton `+`/`−` pour développer/réduire ses attributs et ses
enfants. État d'expansion levé au niveau du parent (`LdapBrowser`,
un `Set` de DN développés) plutôt qu'une state locale par nœud --
permet "Tout déplier"/"Tout replier" en manipulant directement cet
ensemble unique, sans redescendre dans chaque composant. Racines
pré-dépliées au premier chargement -- montre immédiatement quelque
chose plutôt qu'un arbre entièrement réduit et vide en apparence.

Aucune nouvelle logique pure isolable ici -- le composant s'appuie
entièrement sur `buildTree`/`tree.nodes`/`tree.roots`, déjà testés à
fond (arbre garanti acyclique par construction, dérivé de la
hiérarchie des DN). Classes CSS toutes vérifiées présentes.
Non-régression complète sur tout le module.

**Non vérifié dans cet environnement** : rendu visuel réel, aucun
navigateur ici -- et performance réelle sur un très grand annuaire
(les captures d'écran fournies plus tôt suggèrent des dizaines à
quelques centaines d'entrées, ce qui devrait rester confortable pour
React, mais reste à confirmer en conditions réelles).

## Évolution du modèle de confiance : branchement rights-api (livraison #290)

Suite au backlog item 38 ("brancher rights-api sur les ~40 autres
API du projet"), deuxième service branché après `ssh-tunnels-api`
(#289). **Clarifié explicitement par la personne** : ceci n'est PAS
une contradiction avec la décision initiale ("groupe Keycloak
`administrateurs` vérifié côté FRONT, jamais une deuxième couche
d'autorisation ici") -- c'est une ÉVOLUTION voulue, pour réserver les
actions d'écriture à une catégorie d'utilisateurs plus précise que
"administrateurs" (trop large), sachant que ce seront probablement
les mêmes personnes pendant longtemps.

**4 routes protégées** (les seules qui écrivent réellement dans
l'annuaire ou déclenchent une sauvegarde) : `PUT /users/<dn>/password`,
`PUT /entries/<dn>`, `POST /backups`, `POST /apply`. Les routes de
consultation (`GET /entries`, `/users`, `/backups`, `/backups/diff`)
restent ouvertes.

**Ordre de vérification important** : le droit est vérifié AVANT
même le contrôle de configuration LDAP (`require_ready_config`) --
jamais l'inverse, pour ne révéler aucun détail sur l'état du système
(configuré ou non) à un appelant non autorisé. Bug trouvé et corrigé
EN COURS de test : les trois routes autres que `create_backup_route`
vérifiaient d'abord la config, ne laissant JAMAIS le refus de droit
s'exprimer tant que la config n'était pas prête (503 au lieu de 403)
-- corrigé en réordonnant.

Même motif que `ssh-tunnels-api` pour le reste : gating au niveau du
SERVICE ENTIER (`resource_type: "ldap-admin-api"`), FAIL CLOSED
(refuse si rights-api est injoignable, même pour `admin_hub`),
OPT-IN via `LDAP_ADMIN_RIGHTS_API_URL` (vide = comportement
identique à avant #290).

**Vérifié réellement** : `_check_manage_right` testé en isolation
(gating désactivé, autorisé, refusé -- y compris qu'un membre du
groupe `administrateurs` SEUL ne suffit plus, conformément à
l'évolution voulue -- et FAIL CLOSED si rights-api est injoignable).
Câblage réel testé sur les 4 routes, confirmant le refus AVANT le
contrôle de configuration. Non-régression des routes de consultation
reconfirmée (jamais gatées, toujours 200/503 selon la config, jamais
403).
