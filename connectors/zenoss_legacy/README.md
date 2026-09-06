# Connecteur Zenoss 2.5.2 (legacy) — inventaire des équipements "vivants"

## Contexte et sources

Zenoss 2.x stocke ses événements dans une base MySQL séparée (`events`),
tables `status` (événements actifs) et `history` (événements clos) —
confirmé pour cette branche de version via la documentation développeur
Zenoss ([copie archivée](https://docs.huihoo.com/zenoss/dev-guide/2.4.2/ch04s02.html),
exemple utilisant précisément MySQL 5.0.45). Le catalogue complet des
équipements (classes, hiérarchie complète) vit dans la ZODB (Zope Object
Database), **pas** dans MySQL — mais un équipement "vivant" au sens
défini ici (dernière info < N jours) se déduit entièrement des
événements (`device` + `lastTime`), donc pas besoin de la ZODB pour ce
v0.

**Ce qui n'est PAS confirmé** pour ta version 2.5.2 précisément : la
liste exacte des colonnes de `status`/`history` (je n'ai trouvé qu'un
`DESCRIBE` complet pour la table `log`, pas pour `status`/`history`).
Le vocabulaire de champs Zenoss (device, component, eventClass,
severity, summary, firstTime, lastTime, DeviceClass, Location...) est
bien documenté à travers les versions du produit, mais pas vérifié
littéralement pour cette instance — d'où l'introspection au démarrage.

## Principe : introspection d'abord, dry-run par défaut

Le script ne suppose rien : il interroge `INFORMATION_SCHEMA` pour
découvrir les colonnes réellement présentes, et n'utilise que celles
communes à `status` **et** `history`. Il n'écrit rien vers l'API tant
que `--push` n'est pas explicitement passé.

**Procédure recommandée** :

```bash
# 1. Juste voir ce que le script découvre, sans rien extraire
python3 zenoss_connector.py --introspect-only

# 2. Si le schéma semble cohérent, un dry-run complet (affiche, ne pousse pas)
python3 zenoss_connector.py --cutoff-days 365 --output-file inventaire_test.json

# 3. Une fois le JSON local vérifié, pousser réellement vers l'API
python3 zenoss_connector.py --cutoff-days 365 --push \
  --api-url http://localhost:6103 --api-source zenoss_inventory
```

Partage-moi la sortie de l'étape 1 (et si besoin l'étape 2) — on ajuste
le mapping de champs ensemble avant tout envoi réel, plutôt que de
découvrir un souci une fois les données déjà poussées.

## Configuration (variables d'environnement)

| Variable | Défaut | Description |
|---|---|---|
| `ZENOSS_MYSQL_HOST` | `localhost` | Hôte du serveur MySQL de Zenoss |
| `ZENOSS_MYSQL_PORT` | `3306` | Port MySQL |
| `ZENOSS_MYSQL_USER` | `zenoss` | Utilisateur (lecture seule recommandé) |
| `ZENOSS_MYSQL_PASSWORD` | *(vide)* | Mot de passe |
| `ZENOSS_MYSQL_DB` | `events` | Nom de la base événements |

## Installation

```bash
pip install -r requirements.txt --break-system-packages
```

## Points de vigilance connus

- **Authentification MySQL 5.0** : si `old_passwords` est activé côté
  serveur (fréquent sur des installs de cette ancienneté), les drivers
  Python récents peuvent échouer à se connecter. Le script affiche un
  message d'aide dans ce cas ; alternative à tester : le driver
  `mysql-connector-python`.
- **Hiérarchie des équipements (colonne de gauche)** : construite depuis
  le champ `DeviceClass` **si disponible** sur les événements de cette
  instance (découvert par l'introspection). Sinon, tous les équipements
  tombent dans un groupe unique `Unclassified` — une vraie hiérarchie
  demanderait une extraction complémentaire via `zendmd` (shell Python
  de Zenoss, accès direct à la ZODB), non couverte par ce script.
- **Datation par objet, pas de remontée** : chaque équipement n'apparaît
  qu'une fois, avec son événement le plus récent (`lastTime` maximal)
  parmi `status` ∪ `history` sur la fenêtre choisie.
- **Performance** : la requête filtre déjà côté SQL sur `lastTime >=
  cutoff`, donc ne rapatrie pas l'historique complet — reste à valider
  que ça reste rapide sur le volume réel de cette instance (pas testable
  depuis ici, aucun accès réseau à ton Zenoss).

## Forme du JSON produit

```json
{
  "generated_at": "...",
  "source_system": "Zenoss 2.5.2 (legacy)",
  "cutoff_days": 365,
  "device_count": 42,
  "schema_introspection": { "...": "..." },
  "tree": {
    "name": "/",
    "children": [
      {
        "name": "Server",
        "children": [
          {
            "name": "Linux",
            "devices": [
              { "name": "nms-exemple-01", "latest_event": { "device": "...", "lastTime": "...", "severity": 3, "summary": "..." } }
            ]
          }
        ]
      }
    ]
  }
}
```

Compatible tel quel avec l'API `/ingest` existante (n'importe quel JSON
est accepté) et avec les outils déjà construits (arbre JSON de la
corbeille, recherche par mots-clés, détection de dates pour le
calendrier — tous génériques, aucune adaptation nécessaire côté app).
