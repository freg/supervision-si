# rsyslog-listener

Écoute UDP syslog (RFC 3164 et RFC 5424) — livraison #177, backlog
`BACKLOG.md` #3, **étape 4/4 — dernière étape** de l'initiative
"logs de toutes sortes" (push #142 → URL #147 → fichier plat #176 →
rsyslog/UDP #176-#177).

## Pourquoi un service séparé

Contrairement à tous les autres backends de ce projet (atteints via
`tls-proxy`, HTTP/HTTPS uniquement), syslog est un protocole réseau
**brut** (UDP) — il ne peut pas transiter par un reverse proxy HTTP.
Une machine distante qui pousse ses logs syslog doit joindre le port
UDP **directement**, jamais via `GATEWAY_PORT`.

Un **seul worker Gunicorn** (voir `Dockerfile`) — même raisonnement
que `ssh-tunnels-api` (#159) : un port UDP ne peut être **bound**
que par un seul processus à la fois. Un second worker échouerait au
démarrage.

## Architecture

- `syslog_parser.py` — logique **pure**, testable sans réseau.
  Distingue RFC 3164 (`<PRI>Mmm dd hh:mm:ss host tag: message`) de
  RFC 5424 (`<PRI>1 timestamp host app-name procid msgid
  [structured-data] message`) en détectant le marqueur de VERSION
  ("1") juste après le PRI — absent en RFC 3164, aucun horodatage
  RFC 3164 valide ne pouvant commencer par "1 " (le premier
  composant est toujours un nom de mois abrégé). Sévérité syslog
  (0-7) mappée sur les 3 niveaux déjà utilisés partout ailleurs dans
  ce mécanisme de logs : 0-3 → ERROR, 4 → WARNING, 5-7 → INFO. Une
  ligne qui ne correspond à AUCUN des deux formats retombe en "brut"
  (jamais perdue silencieusement).
- `listener.py` — mécanique socket UDP + écriture dans le tampon
  partagé (`shared/log_buffer.py`, #145), même mécanisme que les
  autres sources (push/url/file) : le hub affiche cette source
  automatiquement, aucune modification frontend. Enregistrement de
  la source dans le registre partagé **throttlé** (5 min), pas à
  chaque paquet — `register_shared_log_source` fait un aller-retour
  Memcached même quand la source est déjà connue, inutile de le
  refaire à chaque datagramme sur un flux à fort volume.
- `app.py` — Flask minimal (`/health`, `/logs` pour le diagnostic du
  service LUI-MÊME, distinct du flux syslog relayé), démarre le
  thread d'écoute UDP **une seule fois**, au chargement du module.

## Configuration (`.env`)

- `RSYSLOG_LISTENER_PORT` — port UDP **publié sur l'hôte** (repli
  `5514` — `514`, le port syslog standard, demande des privilèges
  root sur l'hôte, évité par défaut).
- `RSYSLOG_SOURCE_NAME` — nom sous lequel les messages relayés
  apparaissent dans le gestionnaire de logs du hub (repli
  `rsyslog`).

Côté machine distante, pointer son `rsyslog`/`syslog-ng` (ou
`logger -n <host> -P <port> -u ...`) vers `<host>:<RSYSLOG_LISTENER_PORT>` en UDP.

## Vérifié réellement

Parseur testé contre les exemples **canoniques des deux RFC**
(RFC 3164 section 5.4, RFC 5424 section 6.5), plus cas limites :
tag avec PID, sévérités 0 et 7 (bornes), vrai caractère BOM (U+FEFF,
distinct du texte littéral "BOM" que l'exemple de la RFC 5424 utilise
comme simple annotation descriptive), ligne malformée (repli, jamais
perdue), PRI hors plage (0-191), ligne vide (17 cas au total).

`listener.py` testé contre un **vrai socket UDP local** (thread réel,
port éphémère, paquets envoyés depuis un socket client séparé) —
RFC 3164, RFC 5424 et UTF-8/accents tous confirmés bout en bout,
registre throttlé vérifié (3 paquets → 1 seul enregistrement).

`app.py` testé de bout en bout avec le **vrai thread démarré au
chargement du module** (`/health` répond, un paquet UDP réel envoyé
depuis l'extérieur du processus Flask apparaît dans `/logs` ET dans
le tampon partagé sous `SOURCE_NAME`, la source apparaît dans le
registre partagé — confirmant que le hub la découvrirait
automatiquement).

**Non vérifié dans cet environnement** : contre un vrai serveur
`rsyslog`/`syslog-ng` réel envoyant depuis une autre machine (réseau
restreint ici) — à tester en priorité une fois déployé, notamment le
comportement sous un VRAI volume de trafic (le throttle
d'enregistrement et la taille du tampon, 200 entrées par défaut,
n'ont été exercés qu'avec un faible nombre de paquets ici).
