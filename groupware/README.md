# Groupware « façon eGroupware » — tranche 1 : noyau + CalDAV/CardDAV (livraison #664, item 115)

Cadrage : `docs/groupware-egroupware-python.md`. Cette tranche apporte les **mécanismes transverses** d'eGroupware et la
**synchronisation** des agendas et carnets ; les applications (agenda dans le hub, carnet d'adresses, InfoLog) viennent
par tranches suivantes.

## Services

- **groupware-api** (`groupware/api`, Flask, SQLite dans `/data`) :
  - `GET/POST/DELETE /grants` — partages : `{owner, app, grantee_kind: user|group|all, grantee, rights: r|rae|raed|raedp}` ;
    `GET /grants?user=&groups=` renvoie aussi les droits **effectifs** par propriétaire (`effective[app][owner]`) et les
    partages reçus ; `GET /grants/effective?app=&user=&groups=` pour les applications.
  - `GET/POST/PUT/DELETE /categories` — globales (`app: *`) ou par application, partagées (`owner: ""`) ou personnelles, parent.
  - `GET/POST/DELETE /links` — liens universels `{app1, id1, app2, id2, remark}`, lus dans les deux sens (`other`).
  - `GET/PUT/DELETE /prefs` — préférences `level: default|group|user|forced` ; `GET /prefs?app=&user=&groups=` = valeur résolue.
  - `GET /dav/me?user=` — URLs CalDAV/CardDAV et consignes clients ; `POST /dav/rights/rebuild` — régénère le fichier de
    droits de Radicale (fait automatiquement à chaque partage agenda / carnet).
  - Les partages de **groupe** sont développés en membres via LDAP (`LDAP_URL`, `LDAP_BIND_DN`, `LDAP_BIND_PASSWORD`,
    `LDAP_GROUPS_DN` : groupOfNames / posixGroup / groupOfUniqueNames).
- **radicale** (`groupware/radicale`, Radicale 3.5) : CalDAV/CardDAV sous `https://<hub>:6443/dav/`, authentification
  **LDAP** (mêmes identifiants que le hub ; sans `LDAP_URL` : `htpasswd` bcrypt dans `/config/users`), droits `from_file`
  = fichier généré par groupware-api (volume `GROUPWARE_DAV_CONFIG_DIR`), collections dans `GROUPWARE_DAV_DATA_DIR`,
  interface web `/dav/.web/` (créer une collection, importer .ics / .vcf).

## Tranche 2 : carnet d'adresses dans le hub (#665)

groupware-api dialogue avec Radicale en CardDAV (`carddav.py`, stdlib : PROPFIND, MKCOL étendu, PUT, DELETE) avec un
**compte de service** (`GROUPWARE_DAV_SERVICE_USER` / `PASSWORD` : compte LDAP dédié, ou htpasswd créé par l'entrypoint
sans LDAP ; règle `[service]` en tête du fichier de droits) et vérifie lui-même les partages avant chaque opération.
vCard 3.0 (`vcard.py`) : UID, FN, N, ORG, TITLE, TEL, EMAIL, ADR, URL, NOTE, CATEGORIES, REV ; les champs inconnus d'une
carte écrite par un autre client (PHOTO…) sont conservés.

- `GET /addressbooks?user=&groups=` — mes carnets + partagés (droits effectifs) ; `POST /addressbooks {user, name}` (nommé `contacts-…`).
- `GET /contacts?user=&groups=&q=&owner=&book=` — contacts de tous les carnets lisibles, recherche multi-mots ;
  `POST /contacts {user, groups, owner, book, contact}` (droit `a`) ; `PUT/DELETE /contacts/<owner>/<book>/<uid>` (droits `e` / `d`).
- Tuile Groupware → onglet **Carnet d'adresses** : liste, recherche, fiche, création / modification dans un carnet où
  j'ai le droit, création de carnet ; ce qui est créé ici apparaît dans les clients CardDAV et inversement.

Vérifié contre un **Radicale réel** (`test_live.py`, `GROUPWARE_LIVE_DAV=http://…` + compte de service) : carnet créé,
contact ajouté, lecture refusée sans partage, partage lecture → lecture seule (API et Radicale lui-même : PUT 403),
partage écriture → création et modification, retrait du partage → plus rien.

## Tranche 3 : agenda dans le hub (#666)

`ical.py` (icalendar + dateutil) : VEVENT ↔ dict, récurrences (`rrule {freq, interval, until, count, byday}`) développées sur
une fenêtre, créneaux occupés fusionnés (hors événements « transparents »), conflits. Routes :

- `GET /calendars?user=&groups=` — mes agendas, partagés (droits effectifs) et agendas des **ressources** ; `POST /calendars`.
- `GET /events?user=&groups=&from=&to=&owner=&book=` — occurrences de tous les agendas lisibles ; `POST /events` (droit `a`) ;
  `PUT/DELETE /events/<owner>/<book>/<uid>` (droits `e` / `d` ; champs non fournis conservés, récurrence comprise).
- `GET /freebusy?users=a,b&resources=salle-1&from=&to=` — créneaux occupés **sans détail**, tous agendas confondus,
  quels que soient les partages (le free/busy d'eGroupware).
- Ressources (`/resources`, administration) : salle, véhicule, matériel ; chaque ressource a un agenda sous le principal
  `GROUPWARE_RESOURCE_OWNER` (`ressources`) ; **réservation ouverte à tous** = événement dans cet agenda, **chevauchement
  refusé (409)**, modification / suppression réservées au demandeur (`X-SI-BOOKED-BY`) ou à l'administrateur.
- Compte de service : lu dans le **coffre des accès** (entrée `groupware-dav`, tuile Accès d'équipements) avant les variables
  d'environnement ; `GET /health` dit d'où il vient (`service_source`).

Tuile Groupware → onglet **Agenda** : jour / semaine (grille horaire, double-clic = nouvel événement) / mois / liste, agendas
affichés à cocher, fiche, formulaire (journée entière, répétition quotidienne / hebdomadaire par jours / mensuelle / annuelle
jusqu'à une date, « ne bloque pas mes disponibilités »), disponibilités de plusieurs personnes et ressources (hachures sur la
grille + créneaux libres communs 8h–19h), ressources réservables.

Vérifié contre un Radicale réel (`test_live_cal.py`) : agenda créé, hebdomadaire développé (4 lundis), partage lecture
(lecture oui, ajout 403), modification conservant la récurrence, free/busy sans détail, ressource réservée puis conflit 409,
suppression réservée au demandeur.

## Tranche 4 : InfoLog (#668)

Notes, appels et tâches **liées à tout** (contact du carnet, ticket, autre application via `app:id`), le journal partagé
d'eGroupware. Table `infolog` (SQLite) : `owner`, `type` (note / call / task), `title`, `description`, `status`
(open / ongoing / done / cancelled), `priority` (0-3), `due`, `start`, `responsible`, `private`, `categories`, liens
(table `links`, `app1 = infolog`). Routes :

- `GET /infolog?user=&groups=&q=&type=&status=active|…&scope=all|mine|responsible&linked=app:id` — entrées visibles :
  les miennes et celles dont je suis responsable toujours ; celles des autres selon les partages (`r`, et `p` pour les
  privées) ; chaque entrée porte ses droits effectifs (`rights`).
- `POST /infolog {user, groups, entry}` (créer pour quelqu'un d'autre demande `a` sur son InfoLog) ;
  `GET/PUT/DELETE /infolog/<id>` (`e` / `d` ; champs non fournis conservés, liens remplacés si fournis, `done_at` posé
  au passage à « terminé »).

Tuile Groupware → onglet **InfoLog** : liste (filtres type / statut / portée, recherche) ou **Kanban** par statut,
formulaire (liens : recherche de contact dans le carnet, n° de ticket, `app:id` libre), boutons de changement de
statut, fiche. Les entrées en retard (échéance passée, non terminées) sont marquées.

Reste (tranches suivantes) : le Kanban de l'ENT devient une vue d'InfoLog ; invitations / participants (ATTENDEE) ;
alarmes ; test réel des clients DAV et de l'auth LDAP.

## Invitations et rappels (#669)

Radicale n'a pas de *scheduling* (iTIP) : le hub le fait lui-même, à la manière d'eGroupware. Un événement avec des
**participants** (identifiants du hub, séparés par des virgules) est écrit dans l'agenda de l'organisateur avec
`ORGANIZER` / `ATTENDEE;PARTSTAT=…` (`mailto:identifiant@GROUPWARE_MAIL_DOMAIN`), puis **copié dans l'agenda de chaque
participant** (son agenda `agenda`, créé au besoin ; marqueur `X-SI-INVITE-FROM:organisateur/agenda`). Le participant
répond depuis sa fiche — `POST /events/<owner>/<book>/<uid>/reply {user, partstat: accepted|declined|tentative}` —
la réponse est reportée dans l'événement maître et dans sa copie (déclinée = ne bloque plus ses disponibilités) ;
supprimer sa copie revient à décliner. Les modifications de l'organisateur sont propagées (réponses conservées),
un participant retiré perd sa copie, la suppression par l'organisateur retire toutes les copies.
`GET /events` renvoie `attendees`, `organizer`, `invite_from` et `my_partstat`.

**Rappel** : `alarm` = minutes avant le début (`VALARM` DISPLAY, lu par les clients CalDAV : Thunderbird, DAVx5, iOS).
Le hub ne notifie pas lui-même (à faire : rappel dans le bandeau du hub).

Vérifié contre un Radicale réel (`test_live_invite.py`) : copie chez chaque participant, réponse propagée dans les deux
sens, participant retiré, suppression de la copie = déclin, suppression maître = plus rien nulle part.

## Convention de nom des collections

Radicale ne connaît pas le type d'une collection dans ses droits : un partage **agenda** s'applique aux collections
`<propriétaire>/agenda…`, `cal…`, `calendar…` ; un partage **carnet** à `contacts…`, `carnet…`, `ab…`, `addressbook…`.
Nommer ses collections ainsi (la tuile le rappelle).

## Tuile « Groupware » (Documents & ENT)

Mon agenda / mes contacts (URL du principal, interface Radicale, consignes Thunderbird / DAVx5 / iOS-macOS) ; Partages
(donnés par application, reçus avec droits effectifs ; régénération des droits DAV pour l'administrateur) ; Catégories ;
Préférences (niveaux groupe / défaut / forcée réservés à l'administrateur).

## Règle de composition des droits

La matrice des droits du hub (#559) ouvre ou ferme la tuile ; les partages (grants) décident de ce qu'on voit *dedans*
et sur le serveur DAV. Le propriétaire a toujours tout sur ses données.

## Vérifié / non vérifié

`groupware/api/test_core.py` (droits, effectifs avec groupes, validation, préférences, fichier Radicale, URLs, visibilité InfoLog),
`groupware/api/test_app.py` (routes), `hub/tests/groupwareLib.test.mjs`, rendu nginx (`render_nginx_conf.py --check`).
Non vérifié : Radicale réel derrière tls-proxy (hrefs `/dav/…`, clients Thunderbird/DAVx5/iOS), authentification LDAP réelle,
développement des groupes sur l'annuaire réel.

## Tranches suivantes (voir la note de cadrage)

Les quatre tranches de la note de cadrage sont livrées (#664-#668), invitations et rappels en #669. Suite : Kanban ENT
comme vue d'InfoLog, rappels affichés par le hub, test réel des clients DAV / LDAP.
