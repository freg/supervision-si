# Bastion si-proxy (livraisons #452 à #455)

Accès **réservé à freg** (pour l'instant), depuis le Mac, à trois choses via
le hub :

1. un **shell sur le host de la VM** du hub, ouvert **sous `freg`** (non-root ;
   `sudo` reste à ta main dans ce shell) ;
2. la **navigation HTTPS sur le hub** ;
3. par le hub, la **navigation sur le LAN**.

## Principe

Trois composants, un protocole minimal (une ligne JSON de HELLO puis des
octets bruts) :

- **relais** (`siproxy.relay`) — un **aiguilleur TLS** qui n'exécute *rien*.
  Il apparie, par identifiant de session, la connexion du client Mac et
  celle ouverte en retour par le shim host, puis pompe les octets. Tourne
  dans un conteneur (`docker compose`, service `si-proxy`), seul point
  d'entrée exposé (l'« agent-proxy »), joignable de l'extérieur comme le
  reste du hub.
- **shim host** (`siproxy.hostshim`) — sur la VM « super » (systemd,
  `si-proxy-host`). Il **appelle le relais en sortant** (donc le host
  n'ouvre aucun port entrant, et le conteneur n'a aucun accès au host) et,
  sur ordre du relais, ouvre par session soit un **PTY sous freg**, soit une
  **connexion TCP** vers la cible (hub ou LAN). C'est le *seul* composant qui
  exécute quelque chose.
- **client Mac** (`siproxy.client`) — `shell` (shell interactif) ou `proxy`
  (un proxy HTTP local que tu règles dans le navigateur ; chaque CONNECT
  ressort côté hub, d'où l'accès au hub et au LAN).

```
 Mac (client) ──TLS──▶ relais (conteneur hub) ◀──TLS── shim host (VM, sortant)
                         │ apparie la session │            │
   shell / navigateur ◀──┘   (pompe d'octets) └──▶ PTY freg / TCP hub·LAN
```

## Sécurité

- **TLS partout** ; certificats émis par la **PKI interne** du projet
  (`si-proxy/setup-certs.sh`). Réservé à freg par **jeton client dédié** et,
  en durcissement, **TLS mutuel** avec liste blanche de CN (`SI_PROXY_MTLS=1`,
  `SI_PROXY_ALLOW_CN=freg`).
- Le **relais n'exécute rien** ; le shim est le seul à ouvrir un shell/TCP.
- Shell **sous freg**, jamais root (drop de privilèges par session).
- Cibles interdites même pour freg : boucle locale du host, lien-local,
  métadonnées cloud ; liste de refus additionnelle par `--deny`.
- **Aucun secret journalisé** (les jetons ne sont jamais tracés, ni dans les
  logs ni dans le journal d'audit).
- **Fail2ban maison** (#453) : le relais compte lui-même les échecs
  d'authentification par IP (jeton refusé, CN non autorisé, rôle inconnu) et
  **bannit** l'IP au-delà de `SI_PROXY_BAN_THRESHOLD` échecs (défaut 5) dans
  `SI_PROXY_BAN_WINDOW` secondes (défaut 300) pendant `SI_PROXY_BAN_MINUTES`
  (défaut 15). Une IP bannie est fermée avant même la lecture du HELLO, bon
  jeton ou pas. Levée manuelle via l'interface de contrôle (`/unban/<ip>`).

## Journal d'audit et interface de contrôle (#453)

Le relais tient un **journal d'audit JSONL** (`/data/si-proxy-audit.jsonl`
dans le conteneur, soit `si-proxy/data/` sur la VM, jamais versionné) : un
événement par ligne -- `session-start` (identifiant, client `cn:<CN>` ou
`token:client`, IP, type shell/connect/http, cible), `session-end` (durée,
octets montés/descendus, issue) et `refused` (motif, IP, ce qui était demandé).
**Uniquement des métadonnées** : jamais le contenu des sessions, jamais un
jeton. Le journal est exploitable tel quel par un vrai fail2ban ou un SIEM si
on préfère taper dans le pare-feu du host.

L'**interface de contrôle** est un mini-serveur HTTPS sur un **port séparé**
(6452, publié uniquement sur `127.0.0.1` de la VM ; le hub y accède par le
réseau Docker). Chaque requête exige l'en-tête `X-Si-Proxy-Admin: <jeton>`
(`SI_PROXY_ADMIN_TOKEN` ; sans jeton, l'interface n'est pas démarrée).

| Route | Effet |
|---|---|
| `GET /status` | host connecté ?, bastion actif ?, sessions en cours, compteurs, IP bannies |
| `GET /audit?limit=N` | N derniers événements du journal |
| `POST /sessions/<id>/kill` | ferme une session en cours (client et host) |
| `POST /disable` / `POST /enable` | refuse / réautorise les nouvelles sessions (les sessions ouvertes continuent) |
| `POST /unban/<ip>` | lève un bannissement |

```sh
# depuis la VM du hub
curl -s --cacert pki/ca/ca.crt -H "X-Si-Proxy-Admin: $SI_PROXY_ADMIN_TOKEN" https://super:6452/status
curl -s --cacert pki/ca/ca.crt -H "X-Si-Proxy-Admin: $SI_PROXY_ADMIN_TOKEN" -X POST https://super:6452/disable
```
(`super` = le nom du cert du relais ; en local `--resolve super:6452:127.0.0.1`.)

## Tuile « Bastion » du hub et pont si-proxy-admin-api (#454)

Le jeton d'administration ne doit **jamais** être dans le navigateur. Un
petit service **`si-proxy-admin-api`** (`si-proxy/admin/`, routé
`/api/si-proxy/` par la passerelle) fait le pont : il garde le jeton
côté serveur et n'accepte que les requêtes portant le **jeton d'accès
Keycloak** de la personne (`Authorization: Bearer`), qu'il **vérifie
réellement** (signature RS256 contre les clés publiques du realm, URL
interne `KEYCLOAK_INTERNAL_URL`, expiration) et dont le
`preferred_username` doit être dans **`SI_PROXY_ADMIN_USERS`** (défaut
`freg`). C'est le premier service du projet à vérifier le jeton OIDC
plutôt qu'à faire confiance à des `groups` envoyés par le client — le
bastion le justifie. Routes : `/whoami`, `/status`, `/audit`,
`/summary?hours=`, `POST /sessions/<id>/kill`, `/disable`, `/enable`,
`/unban/<ip>` ; `/health` et `/version` seuls sans jeton. Le pont
vérifie le certificat de l'interface de contrôle (`https://si-proxy:6452`,
CA du projet) : le cert du relais doit porter `DNS:si-proxy` dans son
SAN — `setup-certs.sh` l'ajoute depuis #454 (réémettre un cert émis
avant).

La **tuile « Bastion »** (`hub/src/SiProxyView.jsx`) n'apparaît qu'aux
personnes de `VITE_SI_PROXY_ADMIN_USERS` (confort d'affichage ; le
contrôle réel est le pont) : bandeau d'état (relais, shim host, TLS
mutuel, compteurs), **pause / reprise**, **sessions en cours** avec
fermeture, **fail2ban maison** (IP bannies, levée, refus par IP),
**cibles jointes** sur 24 h / 7 j / 30 j, **journal d'audit** filtrable.
Rafraîchissement toutes les 5 s.

Dans la **tuile Supervision SI**, une catégorie **Bastion** (🛡) ajoute
deux supervisés — le relais et le shim host (états : injoignable =
critique, shim absent ou pause = avertissement) — et, dans l'analyse des
liens, des liens de type **`bastion`** « hub → cible (N sessions,
types) », source `si-proxy`, pondérés par les octets échangés (tracés en
orange sur la carte). Visible seulement pour les personnes autorisées
(le pont refuse les autres, sans erreur affichée).

## Console Bastion élargie : entrées, sorties, autorisations, partages (#455)

Demandé : « une passe sur l'ensemble des outils et des tuiles pour mettre
dans bastion tout ce qui concerne les entrées, sorties, autorisations,
partages ». La tuile devient une **console de sécurité** à cinq onglets
(`hub/src/BastionView.jsx`, logique pure `bastionInventory.js`, sondes
`bastionClient.js`). Rien n'est dupliqué : chaque onglet agrège ce que les
tuiles d'origine exposent déjà, offre les **actions de coupure** qui
existent et renvoie vers la tuile pour le reste. Un compteur d'attention
par onglet signale ce qui mérite un regard.

| Onglet | Contenu | Actions |
|---|---|---|
| Bastion si-proxy | #454 inchangé | pause, kill, déban |
| Entrées | **Exposition du SI** : routes de la passerelle, ports publiés **directement** sur l'hôte (contournent la passerelle ; base/index sur toutes les interfaces = critique, API/portail = avertissement, boucle locale = info), services en `network_mode: host` ; agents hôtes (si-agent) et sondes (netprobe) entrants, TLS non vérifié signalé | **coupe-circuit** : bloquer / débloquer toutes les sondes de la flotte |
| Sorties | tunnels SSH (état, via, vers), connecteurs vers des services externes (Nebula, GLPI, IMAP, ownCloud, sauvegardes, GeoIP, notifications) d'après leur `/health` | arrêter / démarrer un tunnel |
| Autorisations | permissions rights-api par type de ressource, types restés ouverts (contrôle opt-in), liens externes du hub et leurs rôles (« tout le monde » signalé), mes groupes | révoquer une permission (admin_hub) |
| Partages | sources du gestionnaire de fichiers (espace protégé gardé par rights-api, GED, montages), montages SSHFS | démonter |

L'inventaire d'exposition est **`shared/EXPOSURE.json`**, généré par
`scripts/render-exposure.py` (à chaque `run.sh`, comme `VERSION.json`)
d'après `docker-compose.yml` (`ports:`, `network_mode`) et la liste des
routes de `tls-proxy` — jamais maintenu à la main — et servi par le pont
(`GET /exposure`). Premier constat réel à la génération : **cinq bases /
index (PostgreSQL ×4, Elasticsearch) publiés sur toutes les interfaces de
la VM**, hors passerelle et hors Keycloak — noté au backlog (les lier à
`127.0.0.1` dans le compose si aucun client externe n'en a besoin).

Hors console (portails dédiés) : coffre-fort (ACL par collection),
annuaire, console Keycloak. Partages ownCloud (`oc_share`) : non exploités.

## Mise en place (sur la VM du hub)

```bash
# 1. certificats (cert serveur du relais, signé par la PKI ; + jetons)
#    (PKI_DIR est lue dans .env si elle n'est pas exportée -- PKI déplacée hors du dépôt)
./si-proxy/setup-certs.sh super           # ou l'IP/nom par lequel tu joins le hub
#   copie les trois jetons affichés dans .env : SI_PROXY_HOST_TOKEN / SI_PROXY_CLIENT_TOKEN / SI_PROXY_ADMIN_TOKEN

# 2. relais (conteneur)
docker compose up -d --build si-proxy     # écoute sur SI_PROXY_PORT (6450)

# 3. shim host (systemd sur la VM)
sudo ./si-proxy/install-host.sh --relay localhost:6450 --token "$SI_PROXY_HOST_TOKEN" --shell-user freg
```

## Utilisation (sur le Mac)

Récupère `si-proxy/siproxy/` et `si-proxy/certs/ca.crt`, puis :

```bash
# shell sur le host du hub (sous freg)
python3 -m siproxy.client shell --relay super:6450 --ca ca.crt --token "$SI_PROXY_CLIENT_TOKEN"

# proxy local pour le navigateur (hub + LAN par le hub)
python3 -m siproxy.client proxy --listen 127.0.0.1:6451 --relay super:6450 --ca ca.crt --token "$SI_PROXY_CLIENT_TOKEN"
#   règle le proxy HTTP du navigateur sur 127.0.0.1:6451, puis va sur https://super ou https://<hôte-du-LAN>
```

`super` = le nom/IP par lequel tu joins le hub sur le LAN. **Depuis
l'extérieur**, une adresse LAN ne mène nulle part : il faut soit publier le
port 6450 de la VM sur la box (NAT) derrière un nom public / DynDNS, soit
faire tourner le relais ailleurs (voir ci-dessous). Dans les deux cas le
certificat du relais doit porter TOUS les noms utilisés :
`setup-certs.sh super --san hub.exemple.dyndns.org --san <IP publique>`
(#469), et le client Mac connaît les deux adresses (`SI_PROXY_RELAY` pour
le LAN, `SI_PROXY_RELAY_WAN` pour l'extérieur, essayée si le LAN ne répond
pas).

### Relais hors du LAN (rendez-vous, aucun port ouvert chez soi)

Le relais n'est qu'un aiguilleur TLS sans état : il peut tourner sur
n'importe quelle machine joignable des deux côtés (VPS, petit hébergement).
Le shim host de la VM l'appelle en sortant, le Mac aussi — rien n'est
publié sur la box. Sur cette machine : `python3 -m siproxy.relay --cert
relay.crt --key relay.key --host-token … --client-token … --control-port
6452 --admin-token …` (ou l'image `si-proxy/relay/Dockerfile`), certificat
émis pour son nom public ; sur la VM : `install-host.sh --relay
<vps>:6450 …` ; la tuile Bastion pointe dessus par `SI_PROXY_CONTROL_URL`
du service `si-proxy-admin-api`. Le port de contrôle 6452 doit alors être
protégé (jeton + TLS + fail2ban maison, ou restreint à l'IP du hub).

## Durcissement TLS mutuel (recommandé ensuite)

```bash
./si-proxy/setup-certs.sh super --clients   # émet freg.crt/key (Mac) et host.crt/key (shim)
# .env : SI_PROXY_MTLS=1  ; docker compose up -d si-proxy
# shim  : install-host.sh ... --cert si-proxy/certs/host.crt --key si-proxy/certs/host.key
# Mac   : client ... --cert freg.crt --key freg.key
```

Le relais n'accepte alors que les certificats dont le CN est dans
`SI_PROXY_ALLOW_CN` (défaut `freg`).

## Vérifié

- Tests purs du protocole (`tests/test_proto.py`) : HELLO, jetons, cibles,
  liste de refus (loopback / lien-local / métadonnées), CONNECT / HTTP absolu.
- **Essai de bout en bout** (`tests/e2e_local.py`, TLS + jetons, vrais
  processus relais + shim + client) : shell qui exécute une commande sur le
  host, proxy CONNECT (https), proxy HTTP absolu, rejet d'un mauvais jeton —
  tout vert.
- #453 (`tests/test_audit_guard.py`, 10 tests purs) : cycle de vie d'une
  session dans le journal (octets, durée, issue), refus sans secret, tail du
  journal, bannissement au seuil / fenêtre glissante / expiration / succès qui
  efface / levée manuelle, parseur HTTP de l'interface de contrôle. L'essai
  de bout en bout couvre en plus : `/status` (host connecté, compteurs),
  `/audit` (refus + start/end présents, aucun jeton dans le fichier), 403
  sans jeton admin, **ban réel après 3 échecs** (le bon jeton est alors
  rejeté, l'IP est listée) puis `/unban` rétablissant l'accès, `/disable`
  qui refuse une nouvelle session et `/enable` qui la rétablit, et une
  session ouverte listée dans `/status` puis **tuée** par
  `/sessions/<id>/kill` (le client sort) -- tout vert.
- #454 (`si-proxy/admin/test_admin_api.py`, 17 tests) : vérification du
  jeton avec une paire RSA jetable (valide, mauvaise clé, `kid` inconnu
  puis rechargement, expiré, utilisateur hors liste = 403, casse, `azp`,
  JWKS injoignable = 503), routes protégées (401 sans jeton, aucune
  action transmise sans jeton), actions relayées, synthèse (fenêtre,
  cibles, dernier refus, relais injoignable = critique). Hub : 6 tests
  Node (`hub/tests/siProxy.test.mjs`, 150 au total). **Chaîne réelle** :
  relais + shim + contrôle, JWKS factice, pont Flask, jeton signé ->
  `/status` 200 pour freg, 401 sans jeton, 403 pour un autre
  utilisateur ; tuile rendue sous Chromium sur cette chaîne (session
  shell listée puis **fermée depuis la tuile**, **pause** puis reprise),
  catégorie Bastion et lien `bastion` rendus dans la tuile Supervision SI.
- #455 : 3 tests du parseur d'exposition (`scripts/test_render_exposure.py`),
  2 tests du pont (`/exposure`, fichier absent explicite), 6 tests Node
  (`hub/tests/bastionInventory.test.mjs`, 156 au total) ; inventaire
  généré sur le vrai `docker-compose.yml` (47 routes, 17 ports directs,
  1 service en réseau hôte) ; les cinq onglets rendus sous Chromium sur
  la chaîne réelle (pont + relais) et les API simulées des tuiles.

Non vérifié : le déploiement réel sur la VM « super » (systemd, certs de la
PKI du hub, accès depuis l'extérieur), le TLS mutuel bout-à-bout, et le pont
contre le vrai Keycloak (JWKS réel) — premier essai à faire côté hub. Le shell sous freg (drop setuid) n'est exercé ici que
sous l'utilisateur courant de l'environnement de test.
