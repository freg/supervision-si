# imap-connectors — gestionnaire de connecteurs IMAP

Livraison #489. Demandé explicitement : « un gestionnaire de
connecteur imap chacun sur une adresse de réception pour plusieurs
api : demandes SAV/Tickets/ProjeQTor, alertes supervision ZenOS et
autres, SMS entrants sur les passerelles sms, notifications diverses
— le tout avec log et base de données, statistiques et vue
pixelgrid ». Vue « Connecteurs IMAP » du hub (thématique
**Documents**, après Client IMAP), API servie sous
`/api/imap-connectors/` par tls-proxy.

⚠️ **Jamais testé contre une vraie boîte IMAP** à la livraison —
tout est testé contre un faux IMAP et de faux HTTP
(`tests/test_api.py`, `tests/test_interpreters.py`). Le premier
relevé réel peut révéler des écarts (flags IMAP selon les serveurs,
formats de corps Zenoss variants) : surveiller `last_error` et les
`warnings` du journal.

## Principe

Chaque **connecteur** = une boîte (hôte, port, identifiants, dossier,
SSL) + une **cible** parmi :

| Cible | Routage |
|---|---|
| `tickets` | `POST $TICKETS_API_URL/tickets` (source_type `imap`, source_nom = nom du connecteur) — la demande arrive dans la liste des imports à valider du hub |
| `projeqtor` | `POST $PROJEQTOR_BRIDGE_URL/demande/demandes` (sujet, demandeur, commentaire) — inséré dans ProjeQtOr via le pont « suivi » |
| `zenoss` | interprétation du corps (équipement, message, sévérité) → événement pixel-grid `alerte_zenoss_email` (valeur 1 actif / 0 rétabli) — visible dans la vue pixelgrid |
| `sms` | journalisé (expéditeur = n° dans le sujet sinon le From) — socle pour une cible future |
| `notification` | journalisé seul |

La boucle de relevé (poller, thread du processus — **un seul worker
Gunicorn**, sinon double sondage) interroge chaque boîte activée à
son rythme (`interval_seconds`, minimum 30 s), interprète chaque
message non lu, le route et journalise TOUT dans SQLite : messages,
livraisons, erreurs.

**La boîte est la file de secours** : un message non interprété ou
dont le routage a échoué reste **non lu** — il sera retenté au
relevé suivant. Seul un message interprété ET routé avec succès est
marqué lu (et seulement si `mark_seen` est activé sur le connecteur).

## API (extraits)

- `GET /health` — état du service ;
- `GET/POST /connectors`, `PUT/DELETE /connectors/<id>` — CRUD ; le
  mot de passe est stocké en base mais **jamais exposé** par l'API ;
- `POST /connectors/<id>/test` — test de connexion à la demande ;
- `POST /connectors/<id>/run` — relevé immédiat (hors rythme) ;
- `GET /messages?connector_id=&limit=` — journal des messages avec
  leurs livraisons ;
- `GET /stats` — compteurs par connecteur + grille jour × connecteur
  (30 jours) pour la vue pixelgrid ;
- `GET /notifications?targets=sms,zenoss,notification` — la cloche
  du hub (#490) : compteur de non lus + derniers messages des cibles
  demandées (cibles filtrées sur les valeurs connues) ;
- `POST /notifications/ack` — accusé de réception : `{ids: [...]}`
  ou `{all: true, targets: ["sms"]}` ; l'état « lu » (`ack_at`) est
  en base, partagé entre navigateurs du LAN ;
- `GET /logs` — journal applicatif (300 dernières entrées).

## Cloche de notifications du hub (#490, généralisée #491 et #493)

Les messages des connecteurs de cible `sms`, `zenoss` ET
`notification` alimentent la **cloche** de la barre d'état du hub (à
côté de l'horloge et du n° de livraison) : compteur total de non lus
— **rouge** s'il y a des alertes supervision non lues, **ambre** s'il
ne reste que des SMS ou des notifications diverses. Panneau au clic,
trois sections : « Alertes supervision » (équipement, message,
sévérité avec ton par ligne — résolution en vert, jamais confondue
avec une alerte — et bascule directe vers la supervision SI dont la
mosaïque pixel-grid affiche l'état), « SMS entrants » (expéditeur,
extrait, temps relatif) et « Notifications diverses » (sujet en
titre, expéditeur en extrait, lien vers la tuile Connecteurs IMAP).
« Marquer lu » par message ou par section. L'état
lu (`ack_at`) est en base : partagé entre navigateurs du LAN.
Sondage 30 s, jamais bloquant (API injoignable = cloche discrète).
Migration automatique : `ack_at` est ajouté par `ensure_schema` aux
bases créées en #489.

## Auto-acquittement à la résolution (#492, paramétrable)

Sur un connecteur de cible `zenoss`, l'option **« acquitter à la
résolution »** (`auto_ack`, activée par défaut — y compris pour les
connecteurs créés avant #492, migrés automatiquement) fait qu'une
résolution Zenoss acquitte d'office les alertes **actives non lues
du même équipement**, ainsi qu'elle-même : la cloche reflète l'état
courant, pas l'historique. L'acquittement n'a lieu que si la
résolution a été interprétée ET livrée à pixel-grid avec succès —
une résolution mal routée reste non lue (file de secours). Option
décochée : alertes et résolutions restent visibles jusqu'à
acquittement manuel. Case présente dans le formulaire du connecteur
(cible `zenoss`) et rappelée dans le tableau des connecteurs.

## Configuration (.env)

- `IMAP_CONNECTORS_API_PORT` (6443 côté tls-proxy) ;
- `IMAP_CONNECTORS_DATA_DIR` (hôte, défaut `./imap-connectors/data`) —
  base SQLite `imap-connectors.db` ;
- `TICKETS_API_URL`, `PROJEQTOR_BRIDGE_URL` — cibles HTTP internes ;
- `PIXEL_GRID_BACKEND` (`sqlite` | `postgres`), `PIXEL_GRID_DB_PATH`,
  `PGHOST/PGPORT/PGUSER/PGPASSWORD/PGDATABASE` — écriture des
  événements Zenoss dans la base pixel-grid, même contrat que
  pixel-grid-api (les deux backends sont supportés car le `.env`
  réel utilise postgres).

Les identifiants des boîtes ne sont PAS dans `.env` : ils sont créés
par connecteur via l'API/la vue hub (posture UPS : en base, jamais
dans un fichier versionné, jamais ressortis par l'API).

## Tests

    python3 imap-connectors/tests/test_interpreters.py   # 11 tests, purs
    python imap-connectors/tests/test_api.py             # 4 tests de chaîne (venv avec flask)
