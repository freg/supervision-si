# Points de montage SSHFS -- dossier géré automatiquement

Ce dossier accueille les partages SSHFS montés par `ssh-tunnels-api`
(livraison #180) -- chaque montage actif apparaît ici sous son NOM
relatif (voir `ssh-tunnels/README.md`, `local_mount_path`).

**Rien à faire manuellement ici** -- ce fichier n'est qu'un
placeholder pour que ce dossier existe bien sur le disque au moment
où `docker compose` en a besoin (bind mount, voir
`docker-compose.yml`, `SSH_TUNNELS_MOUNTS_DIR`) : contrairement à la
syntaxe courte des volumes Docker, la syntaxe longue utilisée ici
(nécessaire pour `propagation: rshared`) ne crée PAS automatiquement
le répertoire hôte s'il est absent -- Docker refuse de démarrer avec
une erreur `bind source path does not exist` sans ça.

- Ce dossier est explicitement exclu de Git (`.gitignore`, racine du
  projet) à l'exception de ce fichier -- son contenu (les montages
  eux-mêmes) n'est jamais committé.
- `SSH_TUNNELS_MOUNTS_DIR` (`.env`) est OPTIONNELLE -- vide/absente
  = ce dossier (`./ssh-tunnels/mounts`) comme repli, même logique
  que `SSH_TUNNELS_KEYS_DIR`/`SSH_TUNNELS_DATA_DIR`.
