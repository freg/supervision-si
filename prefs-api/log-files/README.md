# Fichiers de logs -- dossier à peupler manuellement

Déposez ou liez ici les fichiers de logs plats que `prefs-api` doit
suivre en incrémental pour une source de type "file" (voir
`prefs-api/file_source_poller.py`). Ce module ne modifie ni ne
supprime jamais un fichier lui-même -- lecture seule stricte,
volume monté `:ro` dans `docker-compose.yml`.

- Une source "file" (`POST /log-sources`) référence un chemin
  RELATIF à ce dossier via `config.path` -- jamais un chemin absolu
  ni une traversée (`../`), refusé explicitement des deux côtés
  (validation à la création ET au sondage).
- Ce dossier peut contenir de VRAIS fichiers copiés ICI, ou des
  LIENS SYMBOLIQUES vers des fichiers ailleurs sur l'hôte (ex. vers
  `/var/log/mail.log`) -- les deux fonctionnent, la résolution suit
  les liens symboliques avant de vérifier qu'elle reste bien à
  l'intérieur de ce dossier.
- Pour suivre un vrai répertoire système (ex. `/var/log` en entier),
  définir `LOG_FILES_HOST_DIR=/var/log` dans `.env` plutôt que
  d'utiliser ce dossier de repli -- voir `docker-compose.yml`.
- Ce dossier est explicitement exclu de Git (`.gitignore`, racine du
  projet) -- son contenu dépend de l'environnement de déploiement,
  jamais versionné.

Une fois une source créée et son fichier présent, ses nouvelles
lignes apparaissent dans le gestionnaire de logs du hub au rythme de
son `interval_seconds` (30s par défaut) -- rien à redémarrer.
