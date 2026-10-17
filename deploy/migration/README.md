# Migration 2026-2027 : suivi et pilotage pas à pas (#774)

Tuile du hub **Migration 2026-2027** (Infrastructure). Le plan est un fichier JSON d'étapes, importé dans la tuile.
Le plan réel (adresses, noms des nœuds) reste **hors dépôt** (`migration-2026.local.json`) ; `plan-exemple.json` montre
la forme avec des valeurs fictives.

- Une étape = un **type connu** (`check_ssh`, `check_space`, `check_file`, `zfs_create`, `rsync_pull`, `rsync_pull_all`,
  `zfs_pull`, `zfs_send_file`, `verify_rsync`, `verify_zfs`, `manual`), jamais une commande libre, exécutée par l'agent
  de l'hôte indiqué, détachée (`systemd-run`, unité `si-mig-<id>`), journal et code de sortie dans
  `/var/lib/si-agent/migration/`.
- La sonde **migration** de l'agent renvoie l'état toutes les minutes (en cours, en pause, réussie, en erreur), la
  taille copiée, le débit, la fin estimée et la fin du journal.
- Boutons : Démarrer, Étape suivante, Pause, Reprendre, Arrêter, **automatique** (l'étape suivante part dès que la
  précédente réussit ; une erreur suspend l'enchaînement). Par étape : Relancer, Fait (étape à la main), Sauter, Remettre
  à faire.
- Chaque erreur est classée (clé SSH refusée, empreinte changée, DNS, liaison coupée, place, autre copie en cours, volume
  absent, copie incomplète, agent trop ancien…), avec le détail, la fin du journal et le bouton **Solution** :
  relance avec reprise, ou commande exacte à lancer et sur quel hôte.

## Mettre les agents à jour depuis la maison (Linux)
```bash
cd ~/supervision-si/deploy/migration && ./agent-ssh.sh root@pve10 root@pve11
```
Télécharge l'agent depuis le central de chaque hôte, `install.sh --upgrade` (configuration conservée), active les
sondes `migration` et `node-activity`, relance le service et affiche la version.
