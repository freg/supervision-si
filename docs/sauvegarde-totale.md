# Sauvegarde totale et incrémentale, restauration sur un autre host, régénération, gestionnaire (livraisons #458, #459)

Trois scripts dans `scripts/`, un seul moteur (`scripts/full_backup.py`,
logique pure testée par `scripts/test_full_backup.py`) :

| Script | Rôle |
|---|---|
| `backup-full.sh` | archive **chiffrée** (AES-256, `openssl enc -pbkdf2`) de TOUT ce qui fait le hub |
| `restore-full.sh` | dépose l'archive dans un dossier cible sur le nouveau host, sans rien démarrer |
| `regenerate-host.sh` | régénère ce qui est **propre au host** et liste ce qui reste à faire à la main |

## Ce que contient une sauvegarde totale

- `repo.bundle` : le dépôt git complet (toutes les branches) — pas besoin
  de GitHub pour restaurer ;
- `env/` : `.env` (et `.env.encrypted` s'il existe) — c'est pour lui que
  l'archive est chiffrée ;
- `bind.tar` : tous les **montages hôte** des quatre compose
  (`docker-compose.yml`, `gateway/`, `mayan/`, `vault-standalone/`),
  découverts dans les fichiers eux-mêmes — jamais une liste maintenue à la
  main : `*/data`, `si-agent/data`, `ssh-tunnels/keys` et `mounts`,
  `si-proxy/certs` et `data`, `prefs-api/log-files`, `keycloak/backup`,
  `file-manager/protected`, `vault/data`… et la **PKI entière** (`PKI_DIR`
  ou `pki/`, CA comprise). Les montages générés au lancement ou versionnés
  (`tls-proxy/generated`, `keycloak/import`, schémas SQL, thèmes) sont
  écartés : ils reviennent avec le dépôt ou la régénération ;
- `volumes/<nom>.tgz` : les **volumes Docker nommés** présents sur le host
  (PostgreSQL ×4, Elasticsearch, Keycloak, Mayan, OpenLDAP de test),
  copiés tels quels depuis un conteneur `alpine` ;
- `sql/` : en plus, un `pg_dumpall` de chaque PostgreSQL en cours
  d'exécution (portable si la version d'image change) ;
- `host-side.tar` : le shim du bastion (`/etc/si-proxy`, unité systemd,
  `/opt/si-proxy`) si lisible (lancer en `sudo` pour l'inclure) ;
- `manifest.json` : host, IP, port passerelle, `PKI_DIR`, commit,
  livraison, liste des montages et volumes.

```sh
./scripts/backup-full.sh inventory                 # ce qui serait pris
sudo ./scripts/backup-full.sh --out /mnt/nas/hub    # phrase demandée deux fois
SI_BACKUP_PASSPHRASE=… ./scripts/backup-full.sh     # sans interaction (cron)
```

L'archive `supervision-si-backup-<host>-<date>.tar.gz.enc` est en `0600`.
`--no-encrypt` seulement vers un support déjà chiffré. `--no-docker`
(volumes et dumps omis) et `--no-sql` existent pour les cas particuliers.

## Sauvegarde incrémentale et gestionnaire (livraison #459)

Demandé : « un second incrémental et un gestionnaire avec export », en
souvenir d'ARCserve (Cheyenne, NetWare) : un **catalogue de sessions**,
des **chaînes** totale → incrémentales, une **rotation GFS** et la
restauration « à une date ».

`./scripts/backup-full.sh --incremental` (ou le gestionnaire) ne prend que
ce qui a changé depuis la dernière archive du même dossier : index des
fichiers des montages (`backups/.state.json`), commits git nouveaux (bundle
partiel), `.env`, `pg_dumpall` ; les fichiers supprimés sont listés dans le
manifeste et retirés à la restauration. Les **volumes Docker ne sont pris
qu'en totale** (les bases sont couvertes par les dumps SQL). Chaque archive
a un manifeste en clair à côté (`<nom>.manifest.json`, aucun secret) ;
`restore-full.sh <incrémentale>` retrouve et rejoue **toute la chaîne**
(totale puis incrémentales) automatiquement.

Le **gestionnaire** est l'onglet « Sauvegardes du hub » de la tuile
Sauvegardes (thématique Sécurité & accès) : catalogue par chaîne, taille,
livraison et commit de chaque session, **exécution** d'une totale ou d'une
incrémentale (une à la fois, journal du dernier run), **rotation GFS**
(`SI_BACKUP_KEEP_DAILY` totales récentes, `KEEP_WEEKLY` hebdomadaires,
`KEEP_MONTHLY` mensuelles ; les incrémentales suivent leur totale ;
aperçu puis purge confirmée), **export** (téléchargement de l'archive
chiffrée telle quelle -- la phrase reste dans `.env`), suppression, et
**point de restauration** (commande à lancer pour une session donnée).
Planification dans `.env` : `SI_BACKUP_INCR_HOURS` (incrémentale toutes
les N h) et `SI_BACKUP_FULL_WEEKDAY` / `SI_BACKUP_FULL_HOUR` (totale
hebdomadaire) ; `SI_BACKUP_PASSPHRASE` est obligatoire -- sans elle, le
gestionnaire refuse (jamais d'archive en clair). Le conteneur
`backup-restore-api` monte la racine du projet (`/project`) et le socket
Docker (volumes) ; `SI_BACKUP_HOST_ROOT` (`${PWD}`) traduit les chemins
pour `docker run -v`. Actions gardées par le droit `manage` (rights-api).

## Restaurer sur un autre host

Prérequis sur le nouveau host : `python3`, `git`, `openssl`, Docker (les
volumes sont recréés sur place ; sans Docker ils sont déposés dans
`_volumes-a-restaurer/` avec la commande à lancer ensuite).

```sh
scp supervision-si-backup-super-2026….tar.gz.enc scripts/full_backup.py scripts/restore-full.sh nouveau:/tmp/
ssh nouveau
cd /tmp && ./restore-full.sh supervision-si-backup-super-….tar.gz.enc --into /home/alice/supervision-si
```

Le script refuse un dossier cible non vide (`--force` pour passer outre),
clone le dépôt depuis le bundle sur la branche sauvegardée, restaure
`.env` (0600), les montages, recrée les volumes Docker en adaptant le
préfixe de projet Compose au nom du dossier cible (`--project-name` pour
l'imposer), dépose les fichiers côté host dans `_host-side/` et les dumps
dans `_sql-dumps/`. Un `PKI_DIR` externe (chemin absolu) est remis à sa
place d'origine avec `--absolute`, sinon sous `_absolute/`. Rien n'est
démarré.

## Régénérer ce qui est propre au host

```sh
cd /home/alice/supervision-si
./scripts/regenerate-host.sh --dry-run            # ce qui changerait
./scripts/regenerate-host.sh [--host-ip 10.0.0.9] [--hub-name super2] [--rotate-tokens]
```

Ce qui est régénéré : `HOST_IP` et **toute valeur de `.env` qui contenait
l'ancienne IP** (`SI_AGENT_PUBLIC_URL`, URLs publiques…) — sauvegarde en
`.env.avant-regen` ; le **certificat serveur** (SAN = nouvelle IP) ; le
realm Keycloak et la conf nginx (rendus depuis `.env`) ; le certificat du
relais si-proxy (`setup-certs.sh <hub>`) ; `EXPOSURE.json`.

Ce qui n'est **jamais** régénéré, et pourquoi : la **CA** (les agents
si-agent/netprobe épinglent son empreinte, le certificat client de freg
en dépend, les navigateurs l'ont déjà) ; les **sels et phrases de
chiffrement** (`*_SALT`, `*_PASSPHRASE` : les mots de passe UPS/SNMP/SSH
stockés deviendraient illisibles). Les jetons du bastion (`SI_PROXY_*`) ne
tournent que sur `--rotate-tokens`.

Le script imprime ensuite la liste de ce qui reste à faire à la main :
re-pointer les agents (`central_url`) ou les réenrôler, réinstaller le shim
si-proxy avec la nouvelle adresse du relais, accepter la purge/réimport
du realm Keycloak au prochain `gateway/scripts/run.sh` (les redirect URIs
contiennent l'ancienne IP), DNS / pare-feu, puis les `run.sh`.

## Vérifié

Chaîne réelle sans Docker : sauvegarde chiffrée du dépôt (bundle, `.env`
d'essai, PKI générée, 12 montages) → restauration dans un autre dossier
(clone sur la branche, `.env` 0600, CA identique octet pour octet) →
mauvaise phrase refusée → régénération avec une autre IP et
`--rotate-tokens` (`.env` réécrit sans toucher aux sels, certificat
serveur avec la nouvelle IP en SAN, relais `DNS:superbis,DNS:si-proxy`,
CA inchangée, liste d'actions). 5 tests purs. #459 : totale puis
incrémentale (1 fichier changé, 1 supprimé, commits nouveaux, 26 Ko) →
restauration de la chaîne dans un dossier neuf (commit récupéré, fichier
présent, fichier supprimé absent) ; 5 tests purs du gestionnaire
(catalogue, chaînes, orphelines, GFS, planification) ; API réelle
(catalogue, run incrémental avec le vrai moteur, refus d'un second run
simultané, export, suppression, rotation) ; onglet rendu sous Chromium.
**Non vérifié** : la partie Docker (volumes, `pg_dumpall`, image avec le
client docker) et le shim côté host — à faire sur « super ».
