# Note de cadrage — un groupware « façon eGroupware » en Python dans le hub (item 115)

Demande (3 oct. 2026) : ProjeQtOr est mis de côté ; préférence nette pour eGroupware, mis en place en 2004 dans
un cabinet de soins (« c'était parfait ») — s'en inspirer et le reproduire en Python. Cette note fixe ce qui faisait
la valeur d'eGroupware, ce que le hub possède déjà, les options, et les questions à trancher avant d'écrire du code.

## 1. Ce qui faisait eGroupware (version 1.0, 2004) — de mémoire, à confirmer par la personne

| Application | Ce qu'elle apportait | Pourquoi ça marchait dans un cabinet |
|---|---|---|
| **Agenda** | agendas personnels et de groupe, vue jour/semaine/mois/planning, récurrences, alarmes, **disponibilités (free/busy)**, ressources (salles, matériel) réservables | planning de l'équipe sur un écran, créneaux et salles sans conflit |
| **Carnet d'adresses** | contacts personnels et partagés, catégories, vCard, lien vers l'agenda et InfoLog | le dossier administratif du patient / du fournisseur à un seul endroit |
| **InfoLog** | notes, tâches, appels téléphoniques, **liés à n'importe quel objet** (contact, rendez-vous, projet, fichier), responsable, échéance, statut | le « journal » du cabinet : qui a appelé, ce qu'il reste à faire, rattaché à la bonne personne |
| **Gestion de projet / feuille de temps** | projets, éléments, temps passé (arrivés en 1.0/1.2) | suivi des heures |
| Courrier, fichiers, wiki, ressources | messagerie IMAP intégrée, gestionnaire de fichiers, wiki, inventaire des ressources | tout dans la même fenêtre |

Les **mécanismes transverses**, plus que les applications, faisaient la qualité :

- **ACL par « grants »** : chaque utilisateur (ou l'admin pour un groupe) accorde à d'autres utilisateurs / groupes des
  droits *lecture / ajout / modification / suppression / privé* sur **ses** données, application par application
  (« je donne à la secrétaire la modification de mon agenda, la lecture de mes contacts »).
- **Liens universels** (« links ») : tout objet se rattache à tout objet, dans les deux sens, affiché dans chaque fiche.
- **Catégories** globales et par application, hiérarchiques, personnelles ou partagées.
- **Préférences** à trois niveaux : défaut, par groupe, *forcées* par l'admin, sinon de l'utilisateur.
- **Un cadre unique** : navigation par icônes d'applications, tout dans la même page, thème (idots).
- Import/export iCal et vCard, puis SyncML ; aujourd'hui CalDAV/CardDAV (téléphones).

## 2. Ce que le hub possède déjà (à réutiliser, pas à refaire)

| Besoin groupware | Brique du hub | État |
|---|---|---|
| Comptes, groupes, authentification | Keycloak / OpenLDAP, tuile Comptes et groupes (#557) | en place |
| Droits par tuile et action × groupe / personne | matrice des droits `rights` (#559) | en place — mais par *tuile*, pas par *donnée* (pas de grants) |
| Agenda | tuile ENT : calendrier interne, flux iCal (#271-272, `tasks/`) | basique (pas de récurrences riches, pas de free/busy, pas de ressources, pas de CalDAV) |
| Tâches | Kanban de la tuile ENT (#271-272) | en place |
| Tickets / demandes | tickets 4 profils, saisie publique (#497, #500), SAV | en place — l'équivalent du « journal » côté client |
| Liens entre objets | `relations-api` (#335-338 : tickets, tâches, GED, pixel-grid, proximité) | en place pour 4 familles d'objets — c'est l'embryon des « links » |
| Fichiers / documents | GED versionnée (#458-460), file-manager (#396) | en place |
| Courrier | imap-client / imap-connectors (#489-493) | en place (lecture, cloche) |
| Notifications | notify-api (#590) | en place |
| Contacts | aucune brique centrale (contacts des tickets, annuaire LDAP seulement) | **manque** |
| Notes / appels / InfoLog | aucune | **manque** |
| Feuille de temps, ressources réservables | aucune | **manque** |
| Catégories partagées | par module, pas globales | **manque** |
| CalDAV / CardDAV | aucun | **manque** |
| Cadre unique, tout sur une page | espace de travail, vue Simple (#541-545), arbre du hub (#516) | en place |

## 3. Options

| Option | Description | Pour | Contre |
|---|---|---|---|
| **A. Réécriture complète en Python** | un module `groupware/` reproduisant eGroupware 1.0 : agenda, contacts, InfoLog, temps, ressources, grants, liens, catégories | fidèle au souvenir ; maîtrise totale ; cohérent avec le portage-kit | très gros (eGroupware = des années de travail) ; refait ce que le hub a déjà (agenda, tâches, droits, liens) |
| **B. Composition sur les briques du hub + noyau groupware** | un module `groupware/` qui apporte **ce qui manque** (grants par donnée, liens universels, catégories, contacts, InfoLog, temps, ressources) et un serveur **CalDAV/CardDAV** (Radicale, Python, mature) comme stockage de l'agenda et des contacts ; l'agenda ENT existant migre dessus ; le front = cadre du hub | incrémental, chaque étape utile seule ; synchronisation téléphones/Thunderbird gratuite ; réutilise relations-api, rights, GED, notify | deux modèles de droits à réconcilier (tuile vs donnée) ; Radicale = dépendance supplémentaire (petite, stdlib-friendly) |
| C. eGroupware actuel (PHP, 23.x) en conteneur | installer le vrai eGroupware, l'intégrer au hub par son API (CalDAV, REST) | immédiat, complet | c'est du PHP qu'on cherche à quitter ; double référentiel de comptes ; ergonomie à part — c'est exactement le reproche fait à ProjeQtOr |

**Recommandation : B**, avec le vocabulaire d'eGroupware (grants, links, catégories, InfoLog) comme cahier des
charges fonctionnel, et une première tranche volontairement étroite.

## 4. Première tranche proposée (si B)

1. **Noyau** (`groupware/api`, Flask + Postgres) : *grants* (propriétaire → utilisateur/groupe → droits par application),
   *catégories* globales, *liens* universels (délégués à relations-api quand l'objet est déjà connu de lui), préférences
   à trois niveaux. Tests purs sur la résolution des droits (le point délicat).
2. **Carnet d'adresses** : contacts personnels et partagés (grants), catégories, vCard, CardDAV via Radicale ; les
   contacts des tickets y pointent.
3. **Agenda** : Radicale (CalDAV) comme stockage, front dans l'ENT : agendas personnels / de groupe, récurrences
   (bibliothèques `icalendar` + `dateutil`), disponibilités, **ressources réservables** ; migration du calendrier
   interne actuel.
4. **InfoLog** : notes, appels, tâches liées à tout (contact, rendez-vous, ticket, document), responsable, échéance ;
   le Kanban existant devient une vue d'InfoLog.
5. Plus tard : feuille de temps, projets légers, wiki (la GED versionnée en tient lieu ?).

Chaque tranche = une livraison testée, dans le cadre du hub (tuile « Groupware » ou intégration dans ENT), sans
interface à part.

## 5. Risques et points durs

- **Modèle de droits** : les grants (par donnée) et la matrice des droits du hub (par tuile) doivent se composer sans
  surprise ; règle proposée : la matrice ouvre ou ferme l'application, les grants décident de ce qu'on voit dedans.
- **Agenda** : récurrences, fuseaux, exceptions, invitations — ne pas réécrire, s'appuyer sur `icalendar`/Radicale.
- **Périmètre** : eGroupware avait une dizaine d'applications ; la valeur de 2004 tenait à trois (agenda, contacts,
  InfoLog) et aux mécanismes transverses — commencer là.
- **Données personnelles** (contacts de patients en 2004 ; contacts clients ici) : droits, journal des accès, export
  et effacement dès la conception.

## 6. Questions à trancher avant de coder

1. Pour qui ? L'équipe interne, des clients, les deux ?
2. Les trois applications de départ : agenda + contacts + InfoLog — d'accord, ou autre priorité (temps ? ressources ?) ?
3. Synchronisation téléphones / Thunderbird (CalDAV/CardDAV) : indispensable dès le début, ou plus tard ?
4. Qu'est-ce qui, dans eGroupware 2004, manquait ou agaçait ? (pour ne pas le reproduire)
5. L'agenda ENT actuel : à migrer, ou à remplacer ?
6. Le vocabulaire : garder les noms d'eGroupware (InfoLog, grants) ou les noms du hub (journal, partages) ?

Une fois ces réponses données, la tranche 1 (noyau : grants, catégories, liens, préférences) peut être livrée en
une itération, avec ses tests, avant toute interface.
