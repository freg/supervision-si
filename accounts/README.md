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
