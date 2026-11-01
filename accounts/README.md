# accounts-api — Comptes et groupes (livraison #557)

Tuile **Comptes et groupes** du hub (thématique Sécurité & accès, réservée
aux groupes `administrateurs` / `admin_hub`) : gestion des utilisateurs et
des groupes en **pilotant Keycloak** par son API Admin REST, sans passer
par la console Keycloak.

## Ce que fait la tuile

- **Comptes** : liste (identifiant, nom, e-mail, groupes, actif, source
  Keycloak ou annuaire LDAP), recherche large et filtre par groupe ;
  création (identifiant, nom, e-mail, groupes, mot de passe temporaire à
  changer à la première connexion, ou invitation par e-mail Keycloak
  « UPDATE_PASSWORD ») ; activation / désactivation ; modification des
  groupes (cases à cocher, appartenance rendue égale à la sélection) ;
  réinitialisation du mot de passe ; suppression (jamais son propre compte).
- **Groupes** : liste avec nombre de membres, création, suppression (refusée
  tant qu'il reste des membres), membres à la demande.
- Les **droits** d'un groupe sur les tuiles et actions du hub restent dans
  la tuile Droits (#558 : matrice complète).

## Annuaire LDAP

Les comptes fédérés viennent de l'annuaire (`federationLink`). Keycloak
n'écrit dans l'annuaire que si `LDAP_EDIT_MODE=WRITABLE` ; en `READ_ONLY`
(défaut) un compte créé ici n'existe que dans Keycloak, ce que la tuile
annonce et fait confirmer. Les groupes sont des groupes Keycloak (pas des
groupes LDAP) : c'est ce que le hub lit dans le jeton.

## API

`GET /info`, `GET /users?search=`, `POST /users` (`username`, `email`,
`first_name`, `last_name`, `password`, `temporary`, `member_of`), `PUT
/users/<id>` (`email`, `first_name`, `last_name`, `enabled`), `DELETE
/users/<id>`, `PUT /users/<id>/groups` (`member_of`), `PUT
/users/<id>/password` (`password`, `temporary`), `POST /users/<id>/send-reset`,
`POST /users/<id>/logout`, `GET /groups`, `POST /groups` (`name`), `DELETE
/groups/<id>`, `GET /groups/<id>/members`, `GET /logs`.

Toute écriture exige dans le corps `groups` (groupes de l'appelant)
contenant `administrateurs` ou `admin_hub` (`ACCOUNTS_ADMIN_GROUPS`) — même
modèle de confiance que rights-api. `groups` (appelant) et `member_of`
(groupes donnés au compte) ne sont jamais confondus. Aucun mot de passe
n'est renvoyé ni journalisé ; le journal (Journaux du hub) trace « compte X
créé par Y (groupes …) ».

## Authentification

Compte de service de bootstrap `KEYCLOAK_SERVICE_CLIENT_ID` / `SECRET`
(realm master, grant client_credentials) — le même que tickets-api,
keycloak-backup et `keycloak/group_memberships.py`, jamais une nouvelle
variable. Il doit porter les droits `manage-users` (et `query-groups`) du
realm : c'est le cas du compte de bootstrap actuel.

## Tests

`accounts/tests/test_accounts.py` : Keycloak simulé en mémoire (users,
groups, membership, mots de passe) — cycle complet de la bibliothèque et
droits des routes (refus sans groupe d'appelant, `member_of` distinct de
`groups`, mot de passe jamais renvoyé). **Non vérifié contre un vrai
Keycloak** dans cet environnement.

## Utilisateurs de démonstration (livraison #608)

Tuile Comptes → **Démo** : profils `demo-*` (`api/demo.py`, 2 tests ;
`ACCOUNTS_DEMO_PROFILES` en JSON, sinon demo-admin / demo-technicien /
demo-lecture) créés comme comptes Keycloak **locaux** (l'annuaire LDAP
n'est pas touché), rattachés aux groupes du hub (créés au besoin), adresse
`@demo.invalid`, mot de passe généré (14 caractères lisibles, sans 0/O/1/l)
affiché **une seule fois** à l'activation, jamais stocké ni renvoyé
ensuite. `GET /demo` (état), `POST /demo/enable` (`reset_passwords`),
`POST /demo/disable` (comptes désactivés + sessions fermées),
`DELETE /demo` — écriture réservée aux groupes administrateurs. Les comptes
se connectent par le processus normal (Keycloak) et voient le hub selon
leurs groupes.

## Journal des connexions (livraison #612)

Onglet « Connexions » : événements Keycloak du realm — connexions, échecs,
déconnexions, échecs des clients de service, échecs de rafraîchissement —
avec date, utilisateur, adresse IP, client OIDC et raison traduite
(`invalid_redirect_uri` → « URL de retour non autorisée (origine du hub
inconnue de Keycloak) », `invalid_user_credentials` → « mot de passe
incorrect »…). Filtre début de mot (utilisateur, IP, client, raison),
sélecteur de type ou « échecs seulement », en-tête de tableau fixé.

Keycloak ne conserve pas ses événements par défaut : l'onglet le signale et
propose « Activer la conservation (30 jours) » (`POST /events/enable`,
administrateurs) — `PUT /events/config` du realm avec `eventsEnabled`,
types utiles ajoutés aux existants et expiration de 30 jours si absente,
sans purge ni redémarrage. `accounts/api/events.py` (pur, 4 tests) :
normalisation, filtre, résumé, plan de configuration.

Le journal du frontal public (Apache sur la VM frontale) n'est pas ici :
`/var/log/apache2/hub-<nom>-access.log` sur cette VM (voir
docs/acces-public-frontal.md) ; rapatriement par l'agent hôte / rsyslog au
backlog.

## Réglages Keycloak depuis le hub, liste blanche (livraison #614, item 98)

Onglet « Réglages Keycloak » (Comptes). Modifiables : nom affiché, thème et
langue, page de connexion (se souvenir de moi, mot de passe oublié, connexion
par e-mail), sessions et jetons (inactivité, durée maximale, jeton d'accès,
session hors ligne), protection force brute (activation, blocage permanent,
échecs, attentes, fenêtre), politique de mots de passe, conservation des
événements. Chaque champ a un type et des bornes (`accounts/api/kcsettings.py`,
5 tests) ; une clé hors liste est refusée et signalée, jamais transmise.
Parcours : « Simuler » (avant / après) → « Appliquer » (`PUT
/keycloak-settings`, corps partiel du realm = seuls les champs changés) ;
tracé dans les Journaux avec l'auteur.

Origines des clients OIDC : liste des URL de retour / origines web ; « Ajouter
cette origine » (`POST /keycloak-settings/origins`) dérive pour chaque client
les entrées existantes de l'origine interne (`HUB_INTERNAL_ORIGIN` =
https://HOST_IP:GATEWAY_PORT) vers la nouvelle, aperçu puis application —
équivalent de `KEYCLOAK_EXTRA_ORIGINS` + `keycloak/sync_clients.py`, sans
redémarrage. Aucun retrait possible d'ici.

Fédération LDAP : URL, DN, mode, périodes, boutons « synchroniser les
changements » / « synchronisation complète » (`POST
/keycloak-settings/ldap-sync`). Le mot de passe de liaison n'est ni lu ni
modifiable.

Hors de portée par construction : realm master, nom / suppression du realm,
clients de service et secrets, rôles realm-management, comptes, OTP requis.
