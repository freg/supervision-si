# Équipements Cisco — supervision, configurations, urgence (livraison #508)

Module `cisco/` : `cisco-api` (Flask + paramiko, page servie sous
`/cisco/` par tls-proxy, tuile « Équipements Cisco » de la thématique
Réseau). Cible : Catalyst 3750 / 2970 (IOS 12.2) et Nexus 3064PQ (NX-OS)
— et tout IOS / NX-OS proche, par SSH en canal interactif (les vieux
IOS n'acceptent pas toujours `exec_command`), pagination désactivée,
`enable` automatique.

Demande d'origine : « compléter les outils de contrôle de routeur/switch
par un module Cisco intégrant a minima C3750, C3064PQ, c2970 : superviser
(disponibilité, état, charge, alertes, log), sauvegarder / restaurer les
configurations, agir en cas d'urgence ».

## Registre et identifiants

`cisco/switches.json` (versionné, monté en lecture seule, **jamais
d'identifiant dedans**) :
`{"switches": [{"name", "host", "port"?, "platform": "ios"|"nxos",
"credential": "<accès du coffre>", "enable_credential"?: "<accès>",
"site"?, "description"?}]}`. Les identifiants viennent du coffre des
accès d'équipements (#498) : un accès de genre **cisco** (ou ssh / telnet : le genre est
indicatif, utilisateur + mot de passe), révélé par jeton interne, jamais exposé au navigateur.
`enable_credential` = accès dont le mot de passe est le secret enable
s'il diffère. **`"transport": "telnet"`** (#579) pour un IOS ancien sans
SSH : port 23 par défaut, même accès du coffre (genre ssh : utilisateur +
mot de passe ; ligne vty sans `login local` = mot de passe seul, l'invite
`Username:` est alors absente et gérée), négociation telnet minimale
(options refusées), puis même canal interactif (enable, pagination,
show / configure / write). Le mot de passe passe **en clair sur le fil** :
uniquement sur une patte interne maîtrisée, jamais à travers un réseau
tiers — préférer SSH dès que l'IOS le permet (`crypto key generate rsa`,
`transport input ssh`). Test : équipement telnet simulé
(`tests/test_cisco.py`, `TelnetTests`).

## 1. Supervision (`GET /cisco/switches/<n>/summary`)

`show version` (modèle, version, série, uptime), CPU (`show processes
cpu` IOS / `show system resources` NX-OS), mémoire (`show memory
statistics` / idem NX-OS), capteurs (`show env all` / `show
environment` : lignes FAN / TEMP / POWER avec état OK / NOT OK / Failure
/ absent), interfaces (`show interfaces status` : connected, notconnect,
err-disabled…), journal (`show logging`, sévérité décodée). **Alertes
dérivées** (`parsers.alerts`) : CPU ≥ 70 / 90 %, mémoire ≥ 80 / 95 %,
capteur en défaut, port err-disabled, messages de sévérité ≤ 3 dans les
20 derniers. Disponibilité = SSH joignable (mémorisée dans la liste). Le
relevé est à la demande (chaque affichage ouvre une session SSH).

## 2. Configurations

`POST …/configs/backup` archive `show running-config` dans
`/data/configs/<switch>/<horodatage>.cfg` (+ `.cfg.json` : source, par
qui, sha256) **seulement si elle diffère** de la dernière (lignes
volatiles ignorées : horodatage de modification, `ntp clock-period`).
Sauvegarde **automatique** toutes les `CISCO_BACKUP_INTERVAL_HOURS` (24)
sur tout le registre, rétention `CISCO_KEEP_CONFIGS` (60). Différences
unifiées entre deux versions ou avec la courante (`…/configs/diff`).

**Restauration = fusion** (`POST …/configs/<id>/restore`) : les lignes de
la version choisie absentes de la configuration courante sont
réappliquées en mode configuration, bloc `interface …` par bloc, puis
`write memory`. L'**aperçu** (`dry_run`, défaut) liste exactement ce qui
serait envoyé et, à part, ce qui est présent sur l'équipement mais absent
de la sauvegarde — la fusion ne retire rien, c'est dit à l'écran. Une
sauvegarde « avant restauration » est prise juste avant. Ce n'est pas un
`configure replace` (fichier sur flash requis) : à faire à la main si un
remplacement strict est nécessaire.

## 3. Urgence

`shutdown` / `no shutdown` d'un port (err-disabled, isolement), `write
memory`, **redémarrage différé** (`reload in N`, 1-60 min, défaut 5,
`write` avant) et **annulation** (`reload cancel`) — jamais de reload
immédiat depuis le hub —, commande `show …` libre (`| include/exclude/
begin/section` acceptés, rien d'autre). Chaque geste exige `confirm` =
nom du switch (la page le demande) et est journalisé dans
`/data/actions.log` (qui — `login` du corps ou `X-Forwarded-User` —,
quoi, résultat) : `GET …/actions`.

## Sécurité

Mot de passe jamais dans les traces ni les messages d'erreur (paramiko :
« authentification refusée », classe d'exception seulement) ;
`look_for_keys=False`, `allow_agent=False` ; commandes libres limitées
à `show` ; noms de port validés (`Gi1/0/3`, `Ethernet1/1`…) ; registre en
lecture seule ; un seul worker.

## Vérifié / non vérifié

`python3 -m unittest cisco/tests/test_cisco.py` : 9 tests — parseurs sur
sorties représentatives (show version 3750 IOS 12.2 et Nexus 3064 NX-OS,
CPU/mémoire des deux, capteurs IOS et NX-OS, interfaces status,
logging, alertes, plan de restauration), canal SSH simulé (invite,
enable + mot de passe, `--More--`, écho retiré, erreurs `% Invalid`),
API avec fausse session (résumé, injoignable → 502, sauvegarde
dédupliquée, diff, aperçu puis restauration confirmée avec write memory
et sauvegarde préalable, shutdown/no shutdown, write, reload cancel,
show contrôlé, journal).

**Jamais exécuté contre un équipement réel** : formats des `show`
reproduits d'après la documentation et l'expérience des gammes ; la
première session réelle dira si l'invite (`PROMPT_RE`), les colonnes de
`show interfaces status` ou `show env` de vos matériels divergent —
envoyer la sortie brute (`POST …/show`) suffira pour ajuster. Sur un
IOS 12.2 ancien, SSH peut exiger des algorithmes obsolètes : paramiko
3.x les négocie encore (ssh-rsa, diffie-hellman-group1) — si la
connexion échoue en « SSHException », c'est ce point à regarder.

## Variables

`CISCO_SSH_TIMEOUT` (15 s), `CISCO_BACKUP_INTERVAL_HOURS` (24, 0 =
désactivé), `CISCO_KEEP_CONFIGS` (60), `CISCO_DATA_DIR`
(`./cisco/data`, **à sauvegarder** : configurations et journal),
`CISCO_API_PORT` (port hôte optionnel). Hub : `VITE_CISCO_URL`.

## Suites possibles (BACKLOG 74)

Relevé périodique + historique + alertes vers le journal d'événements
du hub, `configure replace` via SCP, sauvegarde sur PBS/GED, rapprochement
avec la facette Équipements réseau (#506, même IP → fiche), SNMP pour la
disponibilité sans session SSH, comptes TACACS.
