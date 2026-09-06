# Coffre-fort — instance isolée

Stack Docker **séparé** du hub principal, sur la même infrastructure
mais avec sa propre entrée IP/DNS et son propre certificat. Réutilise
le **même code applicatif** (`vault/api`, `vault/admin-api`,
`vault/portal` — `context: ..` dans `docker-compose.yml`, aucun
fichier dupliqué) avec une orchestration/infrastructure minimale et
séparée.

## But

Décidé avec la personne : **pérenniser le projet coffre-fort
vis-à-vis du hub principal, en constante évolution**. Un réimport
Keycloak lié à une tout autre application du hub (nouveau client,
nouveau groupe, correction LDAP...) ne doit jamais pouvoir affecter la
disponibilité du coffre — d'où une instance Keycloak **entièrement
séparée**, jamais partagée avec le hub, même si la fédération LDAP
qu'elle interroge reste la même.

## Ce que cette instance NE contient PAS (volontairement)

- **`prefs-api`** — le thème reste local au navigateur, jamais
  synchronisé entre appareils via un compte. Dégradation déjà prévue
  côté frontend (`shared/preferences.js`), pas un manque.
- **`pixel-grid`** (géolocalisations) — la navigation par arbre de
  localisation (écran de recherche) reste indisponible, message clair
  affiché plutôt qu'un plantage (`VaultSearchScreen.jsx`). La
  recherche par libellé et par mot-clé fonctionnent normalement, elles
  ne dépendent jamais de ce service.
- Tout le reste du hub (tickets, DBA, supervision réseau...) —
  évidemment hors sujet ici.

## Démarrage

```bash
cd supervision-si
VAULT_STANDALONE_HOST_IP=<ip_ou_dns_dediee> ./vault-standalone/scripts/run.sh up -d --build
```

`VAULT_STANDALONE_HOST_IP` peut aussi être renseignée dans `.env`
(racine du projet, section "Instance isolée du coffre-fort") plutôt
que passée à chaque lancement.

Ce script :
1. Rend le realm Keycloak isolé (`vault-standalone/keycloak/render.py`).
2. Génère une CA et un certificat **séparés** de ceux du stack
   principal (réutilise `pki/scripts/generate-ca.sh` et
   `generate-server-cert.sh` **tels quels**, juste avec `PKI_DIR` et
   `HOST_IP` surchargés pour cette seule invocation).
3. Rend la config nginx isolée
   (`vault-standalone/tls-proxy/render_nginx_conf.py`).
4. Lance `docker compose up -d --build` dans ce dossier.

```bash
./vault-standalone/scripts/run.sh down    # arrêt
```

## Authentification — LDAP réutilisé, jamais un second mot de passe

Décision prise avec la personne : le LDAP de l'organisation est déjà
joignable depuis l'extérieur (utilisé par des applications clientes
distantes) — pas de raison de faire saisir un second mot de passe
séparé pour cette instance. Le realm isolé
(`vault-standalone/keycloak/realm-template.json`) reprend la **même
fédération LDAP** que le realm principal (mêmes `LDAP_*` du `.env`
commun), juste allégée par ailleurs :

- **Un seul client** (`vault-portal`), pas les 5 du realm principal.
- **Aucun groupe/rôle complexe** — le contrôle d'accès réel se fait
  déjà au niveau du coffre lui-même (qui a la clé de quelle
  collection), Keycloak ne sert qu'à prouver l'identité.

Le même identifiant/mot de passe LDAP fonctionne donc sur les deux
instances.

## Ports (plage 7xxx — jamais en collision avec le hub)

| Variable | Défaut | Usage |
|---|---|---|
| `VAULT_STANDALONE_GATEWAY_PORT` | 7443 | Entrée unique HTTPS (comme `GATEWAY_PORT` côté hub) |
| `VAULT_STANDALONE_KEYCLOAK_PORT` | 7180 | Accès direct de secours à la console Keycloak (LAN) |
| `VAULT_STANDALONE_ADMIN_LAN_PORT` | 7119 | `vault-admin-api` (maître_clefs) — **jamais routé par le proxy**, LAN uniquement |

Choisis délibérément hors de la plage 6xxx déjà utilisée par le hub
(6543 notamment était déjà pris par `PIXEL_GRID_POSTGRES_PORT` —
collision évitée avant livraison). Si l'instance tourne sur sa propre
IP dédiée, les ports pourraient être identiques à ceux du hub sans
collision réelle ; gardés distincts ici par prudence, pour rester
sans risque même en test sur `localhost`.

## Réutilisation par import, pas par copie

Trois scripts de ce dossier réutilisent leurs équivalents du stack
principal **par import** (chargement explicite par chemin via
`importlib`, jamais par nom de module — deux fichiers `render.py`
dans des dossiers différents entreraient en collision dans le cache
des modules Python, rencontré réellement en écrivant les tests) :

- `vault-standalone/keycloak/render.py` réutilise
  `keycloak/render.py` (substitution, détection de description trop
  longue, vérification post-écriture du mot de passe LDAP).
- `vault-standalone/tls-proxy/render_nginx_conf.py` réutilise les
  gabarits de `tls-proxy/render_nginx_conf.py`.
- `vault-standalone/scripts/run.sh` invoque `pki/scripts/` du projet
  principal directement, sans copie.

Tous les garde-fous déjà durcis sur le stack principal cette session
s'appliquent donc ici automatiquement — aucune double maintenance à
faire diverger avec le temps.

## Base de données — séparée, jamais partagée

`vault-standalone/data/vault.db` est un fichier **distinct** de celui
du stack principal. Les deux instances n'écrivent jamais concurremment
dans la même base — c'est tout l'intérêt d'un mécanisme d'export/
import à sens contrôlé plutôt qu'un partage direct.

## Reste à construire

- **Export/import** entre le hub et cette instance, avec priorité à
  l'instance isolée en cas de conflit (décidé avec la personne :
  aller-retour ponctuel, pas une synchronisation continue) — pas
  commencé.
- **Pilotage depuis le hub** ("commander depuis le hub") — démarrer/
  arrêter cette instance depuis l'interface du hub plutôt qu'en ligne
  de commande. Mérite une discussion de portée à part (fonctionnalité
  sensible : le hub déclenchant des opérations Docker sur l'hôte).

Vérifié réellement : 23 tests (12 sur le rendu du realm Keycloak isolé,
dont le bug de collision de modules Python évité ; le reste sur le
rendu nginx et la génération PKI, testée en conditions réelles avec
`openssl` — CA et certificat séparés, bon SAN, aucune collision avec
le stack principal).
