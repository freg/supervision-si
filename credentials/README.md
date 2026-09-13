# credentials — coffre des accès d'équipements (livraison #498)

Demandé explicitement : « je veux ajouter une gestion des user/password
des routeurs et autres accès de gestion d'équipement et retirer du .env
les clés mikrotik, ça doit être géré dans les secrets du hub ».

Un seul coffre pour les identifiants que des **services** du hub
utilisent eux-mêmes : API RouterOS des routeurs MikroTik (#485), SSH
d'équipements, pages HTTP de gestion, communautés SNMP. Il est distinct
du **coffre-fort de codes** (`vault/`, chiffré de bout en bout, destiné
aux humains) : ici le serveur doit pouvoir déchiffrer, sinon aucun
relevé automatique n'est possible.

## Ce qui est garanti

- Le mot de passe est **chiffré au repos** (`shared/secret_crypto.py`,
  Fernet, phrase de passe `CREDENTIALS_PASSPHRASE` fournie en continu
  au conteneur, sel généré une fois dans `/data/salt.b64` — sauvegardé
  avec la base, jamais régénéré ; `CREDENTIALS_SALT` le surcharge).
  **Sans phrase de passe, le service refuse d'enregistrer un mot de
  passe** (503) plutôt que de le stocker en clair.
- Le mot de passe n'est **jamais renvoyé au navigateur** : la liste
  ne donne que `has_password` / `password_encrypted` ; modifier un
  accès sans ressaisir le mot de passe le conserve.
- La **révélation** (`GET /credentials/reveal/<nom>`) est réservée aux
  services du réseau Docker : en-tête `X-Credentials-Token` égal à
  `CREDENTIALS_INTERNAL_TOKEN` (généré par `sync-env.py`), route
  inexistante (404) sans jeton configuré ou si la requête porte les
  en-têtes de la passerelle (`X-Forwarded-*`, donc un navigateur).
  Chaque révélation est **journalisée** (service consommateur, accès,
  date, succès — jamais la valeur) et visible dans la tuile.
- Aucune valeur secrète dans les traces.

## Utilisation

Tuile **« Accès d'équipements »** (thématique Sécurité & accès, servie
sous `/credentials/`) : créer un accès avec un **nom** (clé de
référence), un genre (routeros, ssh, http, snmp, other), l'identifiant,
le mot de passe, des notes.

Consommateurs :

| Service | Référence | Depuis |
|---|---|---|
| `mikrotik-api` | clé `"credential"` du registre `mikrotik/routers.json` = nom de l'accès ; `"default"` ou absente = accès nommé **`mikrotik`** | #498 (avant : `MIKROTIK_USER` / `MIKROTIK_PASSWORD` dans `.env`, supprimées) |

Un consommateur reçoit `{username, password}` et garde un cache
mémoire court (`CREDENTIALS_CACHE_SECONDS`, 60 s côté mikrotik,
invalidé sur refus d'authentification) — un accès corrigé dans la
tuile prend effet à la sonde suivante, sans redémarrage.

Ajouter un consommateur = un `GET` avec les deux en-têtes
(`X-Credentials-Token`, `X-Credentials-Consumer`) sur
`http://credentials-api:5000/credentials/reveal/<nom>` ; jamais de
mot de passe dans son `.env` ni dans un fichier versionné.

## Variables (`.env`)

- `CREDENTIALS_PASSPHRASE` — phrase de passe de chiffrement (générée
  par `sync-env.py` si `change-me` ; **à conserver dans le PRA** : la
  perdre rend les mots de passe illisibles, à ressaisir).
- `CREDENTIALS_INTERNAL_TOKEN` — jeton des services internes (généré).
- `CREDENTIALS_SALT` — optionnel (base64) ; sinon `/data/salt.b64`.
- `CREDENTIALS_DATA_DIR` (hôte) — dossier de la base et du sel.
- `CREDENTIALS_API_PORT` — variable historique du rendu tls-proxy.

## Routes

```
GET    /credentials/                 page du hub
GET    /credentials/health | /status
GET    /credentials/list             fiches sans mot de passe
POST   /credentials/list             {name, kind, username, password, notes}
PUT    /credentials/list/<name>      password absent = inchangé
DELETE /credentials/list/<name>
GET    /credentials/audit?limit=     journal des révélations
POST   /credentials/reencrypt        rechiffre les valeurs encore en clair
GET    /credentials/reveal/<name>    services internes seulement (jeton)
```

## Vérifié / non vérifié

Vérifié : `python3 credentials/api/tests/smoke_test.py` (chiffrement
réel : refus sans phrase de passe, base sans clair, révélation par
jeton / refus via passerelle / journal, modification sans ressaisie,
rechiffrement, phrase changée → 503 explicite) ;
`python3 mikrotik/tests/smoke_test.py` (faux coffre, cache, accès
absent signalé). Non vérifié : conteneurs reconstruits sur super
(`--build`), routeur réel.
