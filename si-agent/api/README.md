# si-agent-api


## Installation depuis le poste, sans accès à python.org (livraison #648)

Pour un poste (souvent Windows) qui ne joint que le hub public en 443 (VLAN
cloisonné, pas d'accès Internet général) :

- **`GET /deploy/python`** : le hub sert la distribution Python « embeddable ».
  Le serveur (qui a Internet) la récupère une fois de python.org
  (`SI_AGENT_PYTHON_EMBED_URL`) et la met en cache
  (`SI_AGENT_PYTHON_EMBED_CACHE`, défaut `/data/python-embed.zip`). Le poste la
  télécharge donc **depuis le hub**, pas depuis python.org. Fichier public,
  comme `/package`.
- Le bootstrap Windows (`/deploy/windows?token=`) et le `.cmd` silencieux
  passent désormais **`-PythonUrl <base>/deploy/python`** à `install.ps1` :
  toute l'install (agent + Python) vient du hub.
- **`GET /install?token=<jeton>`** : page atteignable **depuis le navigateur du
  poste** (443), protégée par le jeton d'enrôlement. Elle affiche la ligne à
  coller (script **téléchargé puis exécuté**, pas de `iex` → compatible
  antivirus) et les liens de téléchargement (script, agent, Python). Aucune
  option à saisir ; l'agent communique ensuite via l'URL du central (`-Central`,
  modifiable).

Tests : `test_si_agent_api.DeployInstallTests` (service Python simulé, présence
de `-PythonUrl` dans le bootstrap, page /install avec jeton valide/invalide).

## Journal des chantiers (livraison #795)

`journal.py` : table `journal` (chantier, jour, début, fin, nature, acte, description, résultat, statut, source,
`event_id` si l'entrée vient d'un événement). Routes : `GET|PUT /journal`, `DELETE /journal/<id>`, `POST /journal/import`
(`{rows}` JSON ou `{csv, chantier}`), `GET /journal/export.csv` (Excel : `;`, UTF-8 avec BOM), `GET /journal/suggestions`,
`POST /journal/suggestions/<event_id>`. Heures des suggestions en `JOURNAL_TZ` (défaut Europe/Paris, paquet `tzdata`).
Hors heures de bureau = samedi / dimanche, ou début / fin hors 8 h 30 - 12 h 15 et 14 h - 18 h. Les entrées réelles sont
saisies ou importées dans le hub, jamais dans le dépôt.
