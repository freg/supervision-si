# file-manager -- gestionnaire de fichiers (livraison #396, backlog item 26)

Nouvelle tuile/outil du hub. Trois volets :

1. **Espace protégé du hub** -- répertoire sur l'hôte, accessible aussi bien
   depuis le hub (via ce module) que directement par la machine hôte.
   Protégé par rights-api : seuls les groupes autorisés (admin_hub par défaut)
   peuvent lister/parcourir. Métadonnées uniquement (jamais de contenu de
   fichier lu par l'API) -- conforme au périmètre "inventaire de fichiers
   jamais leur contenu" de rights-api.

2. **Documents GED** -- agrégé depuis ged-api (lecture seule). Vue arborescente
   par dossier/entité liée/type. L'écriture reste le rôle de GedView.jsx.

3. **Partages SSHFS** -- systèmes de fichiers montés via ssh-tunnels-api.
   Agrégé depuis ssh-tunnels-api (lecture seule). Statistiques d'espace/inodes
   via `/mounts/<id>/stats`.

## Architecture

```
file-manager-api (Flask)
├── Espace protégé (volet 3)
│   ├── Montage hôte : FILE_MANAGER_PROTECTED_DIR -> /protected-space
│   ├── Scan arborescent : os.scandir() (métadonnées uniquement)
│   ├── SQLite local : index des métadonnées (chemins/tailles/dates)
│   └── Protection : rights-api (groupe admin_hub par défaut)
├── Documents GED (volet 1)
│   └── HTTP interne -> ged-api (lecture seule)
└── Partages SSHFS (volet 2)
    └── HTTP interne -> ssh-tunnels-api (lecture seule)
```

**Pas d'état propre persisté pour les documents/montages** -- ce module
agrège les sources existantes. Son seul état persistant est l'index SQLite
de l'espace protégé (métadonnées uniquement).

## Sécurité

- **Espace protégé** : protégé par rights-api (OPT-IN via
  `FILE_MANAGER_RIGHTS_API_URL`). Sans rights-api configuré, l'accès est
  ouvert à tout utilisateur authentifié (même posture que le reste du hub).
- **Traversale de chemin** : bloquée explicitement (refuse `..` et vérifie
  que le chemin résolu reste sous `FILE_MANAGER_PROTECTED_DIR`).
- **Métadonnées uniquement** : `os.scandir()` + `os.stat()`, jamais de lecture
  de contenu de fichier. Conforme au périmètre "inventaire de fichiers
  jamais leur contenu" de rights-api.
- **Appels internes** : file-manager-api appelle ged-api et ssh-tunnels-api
  via HTTP interne (réseau Docker partagé), jamais via tls-proxy. Filet de
  sécurité sur `.json()` (même motif que shared/safe_json.py).

## Variables d'environnement

| Variable | Défaut | Description |
|----------|--------|-------------|
| `FILE_MANAGER_PROTECTED_DIR` | `/protected-space` | Répertoire protégé sur l'hôte |
| `FILE_MANAGER_DATA_DIR` | `./file-manager/data` | Répertoire pour la SQLite |
| `FILE_MANAGER_DB_PATH` | `/data/file-manager.db` | Chemin de la SQLite dans le conteneur |
| `FILE_MANAGER_MAX_LISTING_ITEMS` | `1000` | Limite d'éléments par listing |
| `FILE_MANAGER_MAX_TREE_DEPTH` | `50` | Profondeur max de l'arborescence |
| `GED_API_INTERNAL_URL` | `http://ged-api:5000` | URL interne de ged-api |
| `SSH_TUNNELS_API_INTERNAL_URL` | `http://ssh-tunnels-api:5000` | URL interne de ssh-tunnels-api |
| `RIGHTS_API_URL` | (vide) | URL de rights-api (OPT-IN) |
| `FILE_MANAGER_API_PORT` | `6091` | Port exposé via tls-proxy |

## Routes

| Méthode | Chemin | Description |
|---------|--------|-------------|
| `GET` | `/health` | Vérifie que le service est en ligne |
| `POST` | `/sources` | Liste les sources disponibles |
| `POST` | `/browse/<source_id>` | Parcourt un dossier dans une source |
| `POST` | `/browse/<source_id>/<item_id>` | Explore un élément spécifique |
| `POST` | `/stats/<source_id>` | Statistiques agrégées |
| `GET` | `/logs` | Logs du service (tampon partagé) |

## Sources

| ID | Type | Description |
|----|------|-------------|
| `protected-space` | `protected-space` | Espace protégé du hub (arborescent) |
| `ged` | `ged` | Documents GED (plat, organisé par entité liée) |
| `ssh-mounts` | `ssh-mounts` | Partages SSHFS (plat, avec stats) |

## Tests

```bash
# Tests backend (logique pure)
cd file-manager/api
python3 -c "
import store, os, tempfile
# ... voir tests dans le code source
"
```

## Bugs rencontrés / limites assumées

- **Non vérifié dans cet environnement** : accès réseau réel aux services
  ged-api/ssh-tunnels-api (réseau restreint). Logique testée en profondeur
  avec des scénarios simulés (clients mockés).
- **Non vérifié** : montage réel de l'espace protégé sur l'hôte (dépend de
  la configuration de l'hôte).
- **Limite assumée** : l'espace protégé est un répertoire unique (pas de
  multi-racines). Si plusieurs espaces sont nécessaires à l'avenir, étendre
  le modèle de données.
- **Limite assumée** : pas de recherche plein texte dans l'espace protégé
  (pas d'indexation de contenu). La recherche reste possible côté GED
  (via owncloud-search-api) et côté documents (via ged-api).

## Fichiers

```
file-manager/
├── README.md              # ce fichier
└── api/
    ├── app.py             # routes Flask, logique d'agrégation
    ├── store.py           # SQLite (index espace protégé)
    ├── Dockerfile         # image Gunicorn 2 workers
    └── requirements.txt   # dépendances Python
```

## Intégration hub

- Tuile ajoutée dans `hub/src/App.jsx` (bouton "Gestionnaire de fichiers")
- Composant : `hub/src/FileManagerView.jsx`
- Client API : `hub/src/fileManagerClient.js`
- Variable d'environnement hub : `VITE_FILE_MANAGER_API_BASE_URL`
