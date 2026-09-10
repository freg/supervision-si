# Sauvegardes -- couverture & connecteurs (livraison #270)

Backlog item 27 -- "backup-restore", extension de la livraison #249.

## Portée

Ce module répond à l'exigence explicite du backlog : "toute machine
[détectée sur le LAN] doit avoir une image prête à la restauration"
-- un registre des images connues, croisé avec les appareils DÉJÀ
découverts par `network-agent` (#233/#240), pour répondre à la question
"quelles machines n'ont PAS d'image récente ?".

**Extension livraison #270** : trois connecteurs de solutions de
sauvegarde open source sont ajoutés :
1. **BackupPC** -- vue hub contenu + versions (pool dédupliqué)
2. **Clonezilla** -- gestion automatisée (jobs, PXE, images)
3. **Restic** -- solution cloud-ready avec déduplication (snapshots, rétention)

## Connecteurs

### BackupPC

BackupPC est un système de sauvegarde réseau haute performance avec
déduplication, support de SMB/NFS/rsync/ftp, et une interface web
d'administration.

Fonctionnalités :
- Liste des hôtes BackupPC configurés
- Visualisation du contenu du hub (pool de fichiers dédupliqués)
- Historique des versions par hôte
- Statistiques de déduplication

Configuration : `BACKUPPC_API_URL` (vide = mode simulation)

### Clonezilla

Clonezilla est un outil d'imagerie de disque/clonage open source.
Ce connecteur gère le déclenchement automatisé via PXE/DRBL.

Fonctionnalités :
- Registre des images Clonezilla connues
- Déclenchement de jobs (sauvegarde/restauration)
- Suivi des jobs en cours
- Configuration PXE/DRBL
- Planification de sauvegardes

Configuration : `CLONAZILLA_API_URL` ou `CLONAZILLA_SSH_HOST`

### Restic

Restic est une solution de sauvegarde open source moderne avec
déduplication par blocs, chiffrement AES-256, compression, et
multi-backend (local, SFTP, S3, Azure, B2, rclone).

Fonctionnalités :
- Liste des snapshots
- Consultation du contenu d'un snapshot
- Politique de rétention (keep-last, daily, weekly, monthly, yearly)
- Vérification d'intégrité du dépôt
- Restauration de fichiers spécifiques

Configuration : `RESTIC_REPOSITORY` et `RESTIC_PASSWORD`

## Modèle de données

Un enregistrement = UNE image de sauvegarde connue. `device_mac`
optionnel -- une image peut être enregistrée avant que la machine
correspondante soit rapprochée d'un appareil découvert par
`network-agent` (ou si cette machine n'est pas/plus sur le réseau
surveillé). `tool` reste un champ libre extensible
(clonezilla/backuppc/restic/other).

Tables ajoutées en livraison #270 :
- `connector_configs` : configurations des connecteurs
- `backup_jobs` : jobs de sauvegarde automatisés
- `backup_schedules` : planifications récurrentes
- `file_versions` : historique des versions de fichiers

## Couverture -- le cœur de la demande

`GET /coverage` croise les appareils DÉCOUVERTS par `network-agent`
avec le registre local des images connues (par adresse MAC,
comparaison insensible à la casse). Renvoie, PAR APPAREIL, s'il a une
image, sa date, et depuis combien de jours -- calculé côté serveur
(une seule source de vérité pour "aujourd'hui"). Les machines SANS
image apparaissent EN TÊTE du tri, jamais une liste neutre à retrier.

**⚠️ Couverture nécessairement PARTIELLE et honnêtement signalée
comme telle** : une machine sans trafic réseau récent (éteinte,
débranchée du LAN surveillé) n'apparaît pas dans `network-agent`, donc
pas ici non plus -- ce n'est PAS un inventaire exhaustif du parc,
seulement des machines ACTIVEMENT vues sur le réseau surveillé.

## API

### Routes originales (livraison #249)
- `GET /images` (`?device_mac=X` optionnel) -- liste des images enregistrées.
- `POST /images` -- enregistre une nouvelle image.
- `DELETE /images/<id>` -- supprime un enregistrement.
- `GET /coverage` -- la vue croisée décrite ci-dessus.

### Routes connecteurs (livraison #270)
- `GET /connectors` -- liste des configurations de connecteurs
- `POST /connectors` -- crée une configuration
- `DELETE /connectors/<id>` -- supprime une configuration
- `GET /jobs` -- liste des jobs (filtres: connector_type, status)
- `POST /jobs` -- crée un job
- `GET /jobs/<id>` -- détails d'un job
- `PATCH /jobs/<id>/status` -- met à jour le statut
- `GET /schedules` -- liste des planifications
- `POST /schedules` -- crée une planification
- `DELETE /schedules/<id>` -- supprime une planification
- `GET /file-versions` -- versions de fichiers
- `POST /file-versions` -- ajoute une version

### Routes BackupPC
- `GET /backuppc/hosts` -- liste des hôtes
- `GET /backuppc/hosts/<host>/versions` -- versions d'un hôte
- `GET /backuppc/hosts/<host>/content` -- contenu d'une sauvegarde
- `GET /backuppc/pool/stats` -- statistiques du pool

### Routes Clonezilla
- `GET /clonezilla/images` -- liste des images
- `GET /clonezilla/jobs` -- jobs en cours
- `POST /clonezilla/jobs` -- crée un job (save/restore)
- `GET /clonezilla/pxe-config` -- configuration PXE

### Routes Restic
- `GET /restic/snapshots` -- liste des snapshots
- `GET /restic/snapshots/<id>/content` -- contenu d'un snapshot
- `GET /restic/stats` -- statistiques du dépôt
- `POST /restic/restore` -- déclenche une restauration
- `POST /restic/forget` -- applique la rétention
- `GET /restic/check` -- vérifie l'intégrité

## Vérifié réellement

Testé en profondeur (42 tests unitaires) :
- Création/liste/suppression de configurations de connecteurs
- Création/liste/filtrage de jobs (par statut, par connecteur)
- Mise à jour du statut des jobs (pending → running → completed/failed)
- Gestion des planifications (création, liste, suppression)
- Historique des versions de fichiers
- Mode simulation des trois connecteurs (BackupPC, Clonezilla, Restic)
- Non-régression des fonctionnalités originales (#249)

## Branchement rights-api (livraison #309)

Suite de l'item 38 du backlog -- service de SUIVI de couverture
uniquement (jamais l'automatisation réelle de Clonezilla/BackupPC),
mais falsifier ou supprimer un enregistrement pourrait masquer un vrai
trou de couverture. Gardé sur les deux routes d'ÉCRITURE
(`create_image`, `delete_image`) uniquement -- `/coverage` et
`/logs` restent en lecture libre, même motif que partout ailleurs
dans ce projet. OPT-IN via `BACKUP_RESTORE_RIGHTS_API_URL`, vide par
défaut, comportement inchangé tant qu'elle n'est pas configurée.

## Reste à faire

- Automatisation réelle de Clonezilla (PXE/DRBL) -- nécessite de
  cadrer l'infrastructure réelle avec la personne avant tout code,
  hors de portée de cette livraison d'urgence.
- Ingestion automatique des images (au lieu de la saisie manuelle
  actuelle) -- dépend de la façon dont Clonezilla sera concrètement
  piloté.
- Rapprochement automatique `device_label` <-> appareil réseau quand
  `device_mac` n'a pas été renseigné à la création.
- Intégration réelle avec les serveurs BackupPC/Restic/Clonezilla
  (actuellement en mode simulation).
