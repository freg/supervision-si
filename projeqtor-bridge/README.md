# projeqtor-bridge — pont OPTLINE / ProjeQtOr / hub

Livraison #484. Pont entre le **format Excel imposé par la société**
(« Tableau des suivis des demandes — Support OPTLINE »), **ProjeQtOr**
(source de vérité des demandes) et la **gestion de tickets du hub**
(file « imports à valider », même mécanisme que les imports ICS #273).

## Ce que fait le module

| Besoin (demandé) | Réponse |
| --- | --- |
| Module d'import prenant le format en entrée | `POST /demande/import` (upload xlsx) + bouton sur `/demande/admin` |
| Module d'export agrégé au même format | `GET /demande/export` — toutes les demandes ProjeQtOr, colonnes/listes/formules identiques au fichier imposé |
| Interface simplifiée non authentifiée (LAN) | `GET /demande/` — formulaire public, URI à part, sans authentification (confirmé explicitement) |
| Les demandes saisies vont dans ProjeQtOr | Création via l'API REST ProjeQtOr (compte dédié, jamais admin) |
| Les demandes ProjeQtOr arrivent dans les imports à valider du hub | Boucle de sync → `POST /tickets/import-external` de tickets-api (`pending_validation=1`) |
| Import des utilisateurs depuis le LDAP central | `docker compose exec projeqtor-bridge python ldap_import.py [--dry-run]` |

## Principe structurant : ProjeQtOr est la source de vérité

Tout ce qui entre (formulaire public, import xlsx) est **écrit dans
ProjeQtOr** ; le hub n'importe rien directement. La synchronisation
ProjeQtOr → hub lit `/api/Ticket/updated/...` et pousse chaque nouvelle
demande vers tickets-api — qui **déduplique** par
`source_type + source_nom` (« ProjeQtOr #<id> »). L'état local du pont
(`data/sync_state.json`) n'est qu'une optimisation de trafic : sa perte
ne crée jamais de doublon.

## Format OPTLINE

Source unique : `optline_format.py` (colonnes, listes de référence,
validations, formules J/K/L/M, table `Tableau1` A8:K104). Le même code
sert à l'import **et** à l'export — les deux ne peuvent pas dériver.

Correspondance ProjeQtOr (voir `mapping.py`) :

| Colonne OPTLINE | Champ ProjeQtOr |
| --- | --- |
| Sujet | `name` |
| Commentaire | `description` + ligne récap `[OPTLINE]` |
| Demandeur | `idContact` (résolu par nom) |
| Niveau de priorité | `idUrgency` (résolu par nom) |
| Catégorie | `idTicketType` (résolu par nom) |
| Date de demande | `creationDateTime` |
| Date de clôture | `done=1` + `doneDateTime` |
| Id | `externalReference` (`OPTLINE:<id>`) |

**Rien de perdu** : durée (j) et accomplissement n'ont pas de colonne
ProjeQtOr native — ils sont inscrits dans la ligne `[OPTLINE]` de la
description et relus par l'export. Un nom non résolu (absent des
référentiels ProjeQtOr) n'empêche jamais la création : il est signalé
dans le compte rendu et conservé en clair.

## Mise en route

1. Créer dans ProjeQtOr un utilisateur dédié (ex. `bridge`) avec le
   profil suffisant pour créer des tickets (profil « Gestionnaire de
   projet » ou équivalent).
2. Reporter son mot de passe dans `.env` (`PROJEQTOR_API_PASSWORD` —
   `sync-env.py` insère les clés automatiquement depuis #479).
3. `./scripts/chantier.sh` — le service est routé par tls-proxy sous
   `/demande/` (penser au `restart tls-proxy` après le premier
   déploiement, piège #151).
4. Formulaire public : `https://<hôte>:6443/demande/` ; import/export :
   `/demande/admin`.

## Import LDAP central

Adresse et compte de lecture dans `.env` (`CENTRAL_LDAP_*` — secret,
renseigné à la main). Attributs par défaut `uid`/`cn`/`mail`,
surchargeables. Toujours `--dry-run` d'abord :

```bash
docker compose exec projeqtor-bridge python ldap_import.py --dry-run
docker compose exec projeqtor-bridge python ldap_import.py
```

Un utilisateur existant (même login, insensible à la casse/accents)
n'est jamais écrasé ni dupliqué. Le mot de passe local créé est
aléatoire et inutilisable — l'authentification réelle se fait par LDAP
(paramLdap_*, voir projeqtor/README.md) ; ProjeQtOr exige simplement
qu'un mot de passe local existe.

## Posture de sécurité (assumée, confirmée par la personne)

`/demande/` est **sans authentification sur le LAN** : quiconque sur le
réseau peut déposer une demande, importer ou exporter. C'est le même
niveau de confiance que le reste du hub côté client (aucune
vérification de rôle côté serveur, voir prefs-api/README). Ne jamais
exposer `/demande/` hors du LAN sans reconsidérer ce choix.

## Tests

`tests/smoke_test.py` — app Flask contre un faux ProjeQtOr et un faux
tickets-api en mémoire : formulaire, référentiels, dépôt (résolu, non
résolu, validations), import du fichier OPTLINE réel, export relu,
synchronisation avec déduplication (état local **et** côté hub).
Le format xlsx a en plus son propre round-trip vérifié
(parse → régénère → reparse) pendant le développement.
