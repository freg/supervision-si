# Bastion si-proxy (livraisons #452, #453)

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
La tuile « Bastion » du hub (#454) s'appuie sur ces routes.

## Mise en place (sur la VM du hub)

```bash
# 1. certificats (cert serveur du relais, signé par la PKI ; + jetons)
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

`super` = le nom/IP par lequel tu joins le hub (depuis l'extérieur, c'est la
même adresse que pour le reste du hub — le bastion ne demande pas d'ouverture
supplémentaire côté host).

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

Non vérifié : le déploiement réel sur la VM « super » (systemd, certs de la
PKI du hub, accès depuis l'extérieur) et le TLS mutuel bout-à-bout — premier
essai à faire côté hub. Le shell sous freg (drop setuid) n'est exercé ici que
sous l'utilisateur courant de l'environnement de test.
