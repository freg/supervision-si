# Sauvegarde totale, restauration sur un autre host, régénération (livraison #458)

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
CA inchangée, liste d'actions). 5 tests purs. **Non vérifié** : la partie
Docker (volumes, `pg_dumpall`) et le shim côté host — à faire sur « super ».
