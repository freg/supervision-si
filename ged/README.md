# ged — gestion électronique de documents

Livraison #157-#158, demandé explicitement : "ajouter à la gestion de
ticket : une gestion de documents liés/joints" + "ajouter au hub une
interface/API GED permettant d'accéder et gérer les versions des
documents".

## Décision d'architecture : Mayan EDMS (livraison #158)

**#157** : fondation homemade (stockage disque + métadonnées SQLite),
choix d'une vraie GED tierce explicitement DÉFÉRÉ ("on travaillera
cet aspect plus tard") -- une recherche rapide avait fait ressortir
**Mayan EDMS** comme candidat le plus solide (Python/Django,
versioning natif, API REST complète, PostgreSQL/MySQL/SQLite, mature
depuis 2010).

**#158** : "allons-y pour Mayan EDMS" -- décision prise. Le stockage
et le versioning des fichiers sont désormais **relayés vers une vraie
instance Mayan EDMS** (nouveau stack séparé `mayan/`, voir
`mayan/README.md`), remplaçant la fondation homemade de #157.
`ged-api` devient un ADAPTATEUR entre Mayan et le reste de ce projet
-- l'API HTTP exposée par `ged-api` reste STABLE malgré ce changement
de backend (objectif explicite dès #157) : l'onglet hub et
l'intégration côté tickets (encore à construire) n'auront pas besoin
de changer si le backend change à nouveau plus tard.

### Ce que Mayan gère, ce que ged-api gère encore lui-même

Mayan n'a **pas d'équivalent direct** à "lier un document à
N'IMPORTE QUEL type d'entité externe" (répondait à "accès polymorphe
aux documents" demandé explicitement en #157) -- `ged-api` continue
donc de gérer sa table de liaison POLYMORPHE (`document_links`,
SQLite locale, `ged/api/documents_store.py`) lui-même, en référençant
désormais des **IDs de documents Mayan** (pas des IDs locaux comme en
#157).

- **Mayan** : stockage des fichiers, versioning (chaque envoi =
  une "version"), métadonnées de base (label, type de document).
- **ged-api (local)** : liaisons polymorphes uniquement
  (`document_id` Mayan ↔ `linked_type`/`linked_id`, ex. `"ticket"`/`42`).

## Architecture d'accès -- `mayan_client.py`

`ged/api/mayan_client.py` -- client HTTP vers l'API REST de Mayan
(`GET/POST /api/v4/documents/...`), authentification Basic Auth avec
le compte admin auto-créé par Mayan
(`MAYAN_AUTOADMIN_USERNAME`/`PASSWORD`, voir `mayan/docker-compose.yml`
-- MÊMES identifiants réutilisés côté `ged-api` via
`MAYAN_USERNAME`/`MAYAN_PASSWORD`, à garder synchronisés
manuellement entre les deux stacks).

**⚠️ Connaissance PARTIELLE de l'API réelle** -- vue uniquement via
des extraits de documentation glanés en ligne (pas la référence REST
complète, aucune instance Mayan réelle accessible pour vérifier dans
cet environnement). Confirmé avec un degré de confiance raisonnable
(plusieurs sources concordantes) :
- `POST /api/v4/documents/` (`document_type_id`+`label`) crée le
  conteneur document (métadonnées, pas de fichier).
- `POST /api/v4/documents/<id>/files/` (`files={'file_new': ...}`)
  envoie le premier fichier ; le MÊME endpoint avec
  `data={'action_name': 'replace'}` crée une NOUVELLE version.
- Réponse `202 Accepted` -- traitement Celery **ASYNCHRONE** en
  arrière-plan, le fichier n'est PAS immédiatement disponible juste
  après l'appel (`ged-api` ne fait aucune attente/polling, signalé
  tel quel dans sa propre réponse : `"processing": "..."`).
- `GET /api/v4/document_types/` liste les types, `"Default"` existe
  toujours après une première initialisation.

**MOINS CERTAIN** (déduit, pas confirmé par une source directe) : la
forme exacte de la réponse de listage des fichiers d'un document, et
le mécanisme précis de téléchargement (`download_url` dans les
métadonnées du fichier). **À vérifier en priorité contre l'instance
réelle une fois déployée.**

## API HTTP exposée par ged-api (stable depuis #157)

- `POST /documents` -- `multipart/form-data` : `file` (requis),
  `name`, `actor`, `linked_type`+`linked_id` (optionnels, ENSEMBLE --
  lie immédiatement le document créé).
- `GET /documents` -- `linked_type`+`linked_id` optionnels pour
  filtrer sur une entité précise. SANS filtre : tous les documents
  CONNUS de `ged-api` (au moins une liaison enregistrée) -- PAS
  littéralement tous les documents de Mayan (qui pourrait contenir
  des documents créés directement via l'interface Mayan, sans
  rapport avec ce module).
- `GET /documents/<id>` -- détail (nom, versions, liaisons).
- `DELETE /documents/<id>` -- supprime côté Mayan ET les liaisons
  locales.
- `POST /documents/<id>/versions` -- nouvelle version.
- `GET /documents/<id>/versions/<version_spec>/download` --
  `version_spec` : un entier (POSITION dans la liste des fichiers
  Mayan, TRIÉE PAR ID CROISSANT PAR CE MODULE -- jamais présumé de
  l'ordre renvoyé par Mayan lui-même), ou `"latest"`.
- `POST /documents/<id>/links` / `DELETE /documents/<id>/links/<id>`
  -- gérer les liaisons indépendamment.

## Archivage versionné et graphe d'évolution des versions (livraison #460)

Demandé : « un mécanisme d'archivage versionné pour le dépôt de document,
et un visualiseur de graphe d'évolution des versions », en pensant aux
gestions documentaires Novell des années 90. Ce qui est repris de
**SoftSolutions / GroupWise Document Management** (WordPerfect 1993, Novell
1994, intégré à GroupWise 1998 — voir les sources dans le CHANGELOG #460) :
profil de document, versions numérotées avec **une seule version
officielle** (*Document Life Cycle status*), **check-out / check-in**
(*Document In-Use* : celui qui a sorti le document est le seul à en
déposer une version, les autres consultent), édition de plusieurs versions
en parallèle — donc des **branches** —, archivage vers un emplacement
dédié ; et d'**ARCserve** : une archive = copie immuable + catalogue.

Mayan garde les fichiers (suite linéaire) ; `ged/api/versioning.py` ajoute
une couche locale (SQLite du ged-api) :

| Objet | Contenu |
|---|---|
| `version_meta` | par version Mayan : **parent** (défaut : la précédente ; une autre = branche), branche, statut `draft / official / superseded / archived`, auteur, commentaire |
| `checkouts` | document sorti : par qui, depuis quand, à partir de quelle version |
| `archive_entries` | copie **immuable** (`GED_ARCHIVE_DIR`, défaut `/data/archive/<doc>/v<N>-<sha8>-<nom>`, fichier en 0440, sha256, `catalogue.jsonl`) — indépendante de Mayan, jamais ré-archivable, intégrité vérifiée à chaque lecture |

Routes : `GET /documents/<id>/graph` (nœuds, arêtes, voies, officielle,
check-out), `POST /documents/<id>/versions/<n>/meta` (parent, branche,
auteur, commentaire, statut — promouvoir en officielle rétrograde
l'ancienne en `superseded` ; `archived` est terminal), `POST
/documents/<id>/checkout` / `checkin` (`force` réservé au droit manage),
`GET /checkouts`, `POST /documents/<id>/versions/<n>/archive`, `GET
/archive`, `GET /archive/<doc>/<n>/download` (refus si altérée). Le dépôt
d'une version (`POST /documents/<id>/versions`) accepte désormais `actor`,
`parent_version`, `branch`, `comment`, `checkin` et **refuse** une version
d'un autre que le détenteur du check-out.

Hub : bouton « 🌳 graphe des versions » sur chaque document
(`VersionGraphView.jsx`, logique pure `versionGraph.js`) — SVG façon
`git log --graph` (voies = branches, lignes = versions, fourches en
orange, officielle cerclée de noir, archive en pointillé), sortie / retour
du document, promotion, archivage, profil (parent, branche, commentaire),
dépôt d'une version dérivée ; onglet « Archive & sorties » (catalogue avec
intégrité, documents sortis).

## Vérifié réellement

#460 : 6 tests purs (graphe linéaire et branché, voies, cycle de vie,
store, check-out/in, archive WORM et détection d'altération) ; routes
exercées avec un Mayan simulé (graphe, check-out refusé à un autre, dépôt
refusé hors détenteur puis accepté avec branche et check-in, officielle
unique, parent invalide, archive puis ré-archive refusée, catalogue,
téléchargement, statut figé) ; graphe rendu sous Chromium. **Non vérifié**
contre un vrai Mayan (comme le reste de ce module ici).



`mayan_client.py` testé contre un VRAI petit serveur Flask simulant
les réponses documentées de l'API Mayan (thread réel, vraies
requêtes HTTP, 15 cas -- création, upload premier fichier ET nouvelle
version, listage, téléchargement, suppression, erreurs réseau).
`documents_store.py` (liaisons uniquement désormais) testé
directement (9 cas). Application complète (`app.py`) testée de bout
en bout contre un mock Mayan à ÉTAT RÉEL (pas des réponses fixes --
17 cas) : cycle complet création→versions→téléchargement par
position/`latest`→filtre par entité liée→suppression. **Bug réel
trouvé et corrigé en cours de route** : la vérification qu'un
document existe se fait maintenant EXPLICITEMENT (`GET
/api/v4/documents/<id>/`), plus jamais déduite indirectement d'une
liste de fichiers vide (qui pourrait aussi bien signifier "document
sans aucun fichier" qu'"document inexistant" -- ambiguïté non levée
par la documentation glanée).

**Non vérifié dans cet environnement** : contre une VRAIE instance
Mayan (aucun moteur Docker disponible ici, comme pour tout ce qui
touche Docker dans ce projet) -- **à tester en PRIORITÉ absolue une
fois déployé**, la connaissance partielle de l'API réelle (voir
ci-dessus) rend cette vérification plus importante encore que pour
les autres intégrations de ce projet.

## Correctifs #163-#168 : de "400 muet" au téléchargement fonctionnel

**#163-#164** : messages d'erreur détaillés + contexte (ticket/fichier/demandeur) dans les logs -- voir plus haut.

**#166, la vraie cause enfin visible grâce à #163** : le message
détaillé a montré `{'action_name': ['This field is required.']}` --
`action_name` est en réalité TOUJOURS requis par Mayan sur
`POST /documents/<id>/files/`, y compris pour le PREMIER fichier
d'un document flambant neuf. L'hypothèse initiale de #158 (ce champ
optionnel hors nouvelle version) reposait sur une documentation
glanée qui ne le mentionnait QUE dans le contexte "nouvelle
version" -- jamais confirmé qu'il était FACULTATIF pour un premier
envoi, juste jamais démenti non plus avant ce test réel.

Corrigé : `action_name=replace` envoyé SYSTÉMATIQUEMENT, y compris
pour le premier fichier -- aucune AUTRE valeur documentée nulle part
pour ce champ, y compris pour un document sans fichier préexistant
("replace" semble décrire la façon d'incorporer le fichier -- pages
correspondant directement au nouveau fichier -- pas "est-ce le
premier ou le Nième").

**Vérifié réellement** : testé contre un mock REPRODUISANT
EXACTEMENT le comportement rapporté (exige `action_name` sur
CHAQUE appel, y compris le premier, renvoie le même message
`{'action_name': ['This field is required.']}` sinon) -- confirmé
que le premier envoi ET l'ajout de version réussissent désormais
tous les deux. Parcours complet retesté de bout en bout contre ce
mock strict (5 cas, création→version→téléchargement→filtre→
suppression).

**Non vérifié dans cet environnement** : contre la VRAIE instance
Mayan -- ce sera le test décisif, la personne ayant maintenant
confirmé le message d'erreur exact qui a permis ce correctif ciblé.

**#168, l'upload fonctionne (#166 confirmé en conditions réelles) --
mais le téléchargement échouait à son tour** : une fois le fichier
envoyé avec succès (visible dans l'interface Mayan), cliquer sur
"télécharger" renvoyait `réponse Mayan sans 'download_url'`.
Diagnostiqué avec la personne via `curl` direct contre Mayan (pas de
nouvelle hypothèse à l'aveugle) :
- `GET .../files/<id>/` (métadonnées) ne contient AUCUN champ lié au
  téléchargement -- juste des URLs vers l'aperçu/les pages.
- `GET .../files/<id>/download/` (URL simplement CONSTRUITE, jamais
  devinée depuis une métadonnée) répond `200 OK` avec le fichier,
  ET fournit déjà `Content-Disposition: attachment;
  filename="..."`.

Corrigé : `download_file` construit directement l'URL de
téléchargement (un appel réseau de MOINS que l'approche précédente),
et extrait le nom de fichier depuis `Content-Disposition` plutôt que
de le redemander séparément -- plus simple ET plus robuste que
l'hypothèse initiale de #158.

**Vérifié réellement** : extraction du nom de fichier testée avec
l'en-tête `Content-Disposition` EXACT renvoyé par la vraie instance
de la personne (accents, espaces compris), plus plusieurs variantes
courantes et cas limites (8 cas). `download_file` et le parcours
upload+téléchargement complet retestés contre un mock reproduisant
fidèlement le comportement réel confirmé (`action_name` requis,
URL de téléchargement construite, `Content-Disposition` fourni).

## Correctifs antérieurs (#163-#164) : message d'erreur muet, document orphelin, contexte de log

Premier test réel contre une vraie instance Mayan (4.11) : l'envoi
d'un fichier a échoué (`400 Bad Request`), mais le message affiché
côté hub était totalement muet ("400 Client Error: Bad Request for
url: ...") -- `raise_for_status()` seul ne donne QUE la ligne de
statut générique, jamais le corps de la réponse, alors que Django
REST Framework (utilisé par Mayan) renvoie normalement un détail
PRÉCIS par champ (ex. `{"file_new": ["..."]}`), la seule information
réellement utile pour diagnostiquer QUOI corriger.

Corrigé : `mayan_client._raise_with_detail` remplace tous les
`raise_for_status()` isolés -- capture et inclut le corps de la
réponse Mayan dans le message d'erreur, désormais visible jusque
dans l'interface. **Le format de requête lui-même
(`files={'file_new': ...}`) correspond textuellement à la
documentation officielle** (vérifié sur deux versions, 4.9 et 4.11)
-- le 400 rencontré vient donc probablement d'un détail non visible
dans les extraits de documentation glanés (champ requis en plus,
contrainte du type de document...) -- le message désormais détaillé
doit permettre de trancher au prochain essai.

Profité de l'occasion pour corriger un effet de bord réel constaté :
un document dont le conteneur est créé côté Mayan mais dont l'envoi
du fichier échoue restait comme une coquille VIDE et orpheline
("Pages: 0" dans l'interface Mayan) -- `POST /documents` nettoie
désormais AUTOMATIQUEMENT ce document orphelin en cas d'échec
(best-effort, ne fait jamais échouer la réponse pour ça). Au passage,
`delete_document` traite un `404` comme un succès silencieux
(idempotent), même raisonnement que `file_store.py` en #157.

**Vérifié réellement** : `_raise_with_detail` testé contre un mock
renvoyant un détail DRF réaliste (le champ ET le message précis bien
visibles jusque dans la réponse HTTP). Nettoyage automatique testé
avec un mock à état réel (document confirmé supprimé côté Mayan
après un échec d'envoi simulé, aucune liaison locale créée). Parcours
nominal complet retesté sans régression (10 cas).

## Intégration côté tickets (livraison #160)

## Onglet hub (livraison #167)

`GedView.jsx` (bouton d'en-tête 📁) -- navigation/gestion GÉNÉRALE
des documents, pas limitée à un ticket en particulier (contrairement
à `TicketDocuments.jsx`) : envoi d'un document (avec liaison
immédiate optionnelle), filtre par entité liée, liste des documents
connus (au moins une liaison enregistrée), versions (téléchargement,
ajout), gestion des liaisons (ajout/retrait indépendant). Nouveau
`hub/src/gedClient.js`, même motif que `tickets/portal/src/gedApi.js`
(#160), étendu avec la gestion des liaisons.

**Vérifié réellement** : `gedClient.js` testé avec un `fetch` simulé
en Node (26 cas -- bonnes URLs/méthodes/corps pour chaque fonction,
y compris la gestion des liaisons, préservation des messages
d'erreur réels). Structure JSX de `GedView.jsx` et de `App.jsx`
vérifiée par un contrôle d'équilibre accolades/parenthèses/balises.

**Non vérifié dans cet environnement** : compilation Vite réelle
(`npm install` bloqué ici, réseau restreint) ni rendu visuel dans un
vrai navigateur.

## Branchement rights-api (livraison #311)

Suite de l'item 38 du backlog. Documents liés aux tickets,
potentiellement du contenu métier sensible -- gardé sur les 5 routes
d'ÉCRITURE (créer un document, le supprimer, ajouter une version,
créer/supprimer un lien polymorphe), jamais la lecture (liste,
détail, téléchargement de version).

`groups` lu depuis `request.form` pour les deux routes multipart
(`create_document`, `add_version` -- upload de fichier, jamais de
corps JSON) et depuis le corps JSON pour les trois autres
(`delete_document`, `create_link`, `delete_link`), même motif déjà
établi pour glpi/api/app.py (#294).

OPT-IN via `GED_RIGHTS_API_URL`, vide par défaut, comportement
inchangé tant qu'elle n'est pas configurée.

**Vérifié réellement** : comportement opt-in par défaut confirmé,
FAIL CLOSED si `rights-api` injoignable, 403 confirmé sur les 5
routes gardées (multipart et JSON) avec un groupe non autorisé,
lecture confirmée non affectée. Non-régression complète reconfirmée.
