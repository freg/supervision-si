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

`groupware/api/test_core.py` (droits, effectifs avec groupes, validation, préférences, fichier Radicale, URLs),
`groupware/api/test_app.py` (routes), `hub/tests/groupwareLib.test.mjs`, rendu nginx (`render_nginx_conf.py --check`).
Non vérifié : Radicale réel derrière tls-proxy (hrefs `/dav/…`, clients Thunderbird/DAVx5/iOS), authentification LDAP réelle,
développement des groupes sur l'annuaire réel.

## Tranches suivantes (voir la note de cadrage)

2. Carnet d'adresses dans le hub (contacts partagés, vCard, lien avec les contacts des tickets) ;
3. Agenda dans le hub sur Radicale (vues jour/semaine/mois, récurrences `icalendar`, disponibilités, ressources) ;
4. InfoLog (notes, appels, tâches liées à tout) — le Kanban ENT devient une vue d'InfoLog.
