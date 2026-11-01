# projeqtor/data

Données d'exécution de `projeqtor-app` (montées sur `/data` dans le
conteneur, voir `docker-compose.yml`) : `config/parameters.php`
(généré au premier démarrage), `attachments/`, `documents/`, `logs/`,
`tmp/`.

**Jamais versionnées** (`.gitignore`), **jamais supprimées à la main**
sans sauvegarde : `config/parameters.php` contient le mot de passe de
la base et les éventuelles retouches faites via l'écran de
configuration de ProjeQtOr.

Sortable de l'arborescence du projet via `PROJEQTOR_DATA_DIR` dans
`.env` — même logique que `DBA_DATA_DIR` / `TICKETS_DATA_DIR`.
