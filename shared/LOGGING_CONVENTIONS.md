# Convention : traçabilité debug ("rien ne doit être silencieux")

Demandé explicitement (livraison #215) : "vérifier que toutes les
étapes soient logguées en debug, de façon à tracer l'ensemble des
étapes à risque et identifier vite les points de blocage, rien ne
doit être silencieux".

## Trouvaille de fond, corrigée en premier

Avant cette livraison, **aucun service de ce projet ne configurait
explicitement le niveau du logger racine Python** -- il restait à sa
valeur par défaut (`WARNING`). Or le niveau du LOGGER filtre AVANT
même qu'un enregistrement n'atteigne un handler quelconque : un appel
`logging.debug(...)` était donc **silencieusement rejeté**, quelle
que soit la valeur de `LOG_CAPTURE_LEVEL` (qui ne filtre qu'AU NIVEAU
DU HANDLER, en aval -- beaucoup trop tard).

Corrigé de façon **centralisée** dans `shared/log_buffer.py` --
`make_shared_log_handler` positionne désormais le logger racine à
`DEBUG` -- s'applique automatiquement aux ~30 services de ce projet
qui appellent déjà cette fonction, sans modification individuelle.
Le tri "que garder réellement" reste entièrement le rôle de
`LOG_CAPTURE_LEVEL` (toujours `WARNING` par défaut) -- le tampon
partagé reste silencieux par défaut comme avant, mais élever
`LOG_CAPTURE_LEVEL=DEBUG` pour UN service précis suffit désormais à
voir immédiatement toute sa trace fine.

## Règle absolue

**Aucun secret (phrase de passe, mot de passe, communauté SNMP,
contenu déchiffré) n'apparaît JAMAIS dans un message de log, à AUCUN
niveau.** Seules la LONGUEUR, la DURÉE, la PRÉSENCE (booléen) et
l'ISSUE (succès/échec) d'une étape sont tracées -- jamais la valeur
elle-même. Vérifié explicitement par des tests dédiés à chaque module
touché (recherche du secret dans le texte des traces capturées).

## Ce qui est couvert

La chaîne de chiffrement/authentification la plus critique --
modules récents, à haut risque de blocage silencieux :
- `shared/secret_crypto.py` -- dérivation de clé, chiffrement/
  déchiffrement (durée de la dérivation PBKDF2 tracée -- utile pour
  détecter un ralentissement anormal).
- `ssh-tunnels/api/credential_crypto.py`,
  `snmp/api/credential_crypto.py` -- configuration, chiffrement/
  déchiffrement des identifiants stockés.
- `ssh-tunnels/api/tunnel_process.py`,
  `ssh-tunnels/api/mount_process.py` -- lancement/arrêt de VRAIS
  processus OS externes (`ssh`, `sshfs`, `fusermount`) -- le genre
  d'étape la plus susceptible d'échouer ou de se bloquer sans trace
  claire (PID, code retour, contenu de stderr systématiquement
  tracés).
- `snmp/api/snmp_client.py` (livraison #216) -- appels réseau SNMP
  (GET/WALK), durée de chaque échange tracée, chaque tour de WALK
  numéroté (repère précis en cas de blocage sur une cible qui répond
  partiellement).
- `scripts/secrets_tool.py`, `shared/secrets_alert.py` (livraison
  #217) -- outil CLI (nouveau flag `--debug`, traces sur STDERR
  uniquement -- jamais de contamination de STDOUT dont `decrypt-env`
  dépend pour l'`eval` de `scripts/run.sh`) et canaux d'alerte
  SMS/courriel du PRA.

**Particularité de `secrets_tool.py`** : cet outil tourne HORS
Docker, sur la machine de la personne -- pas connecté au tampon
partagé Memcached des autres services. Son mécanisme de traçabilité
est donc DIFFÉRENT : un flag `--debug` en ligne de commande configure
un handler console dédié. Une fois activé, les traces internes de
`secret_crypto.py` remontent AUTOMATIQUEMENT (logger enfant du
logger racine que `--debug` configure) -- vérifié explicitement en
conditions réelles (sous-processus, entrée pipée).

**Modules antérieurs à cette session, audit rétroactif (livraison
#223)** :
- `ldap-admin/api/ldap_client.py` -- export/modification LDIF,
  réinitialisation de mot de passe.
- `glpi/api/glpi_client.py` -- établissement/fermeture de session,
  chemin d'erreur générique.
- `nebula/api/nebula_client.py` -- les deux points de passage réseau
  uniques (`_get`/`_post`), donc toutes les méthodes publiques
  couvertes d'un coup.
- `ged/api/mayan_client.py` -- chemin d'erreur générique + création
  de document.
- `imap-client/api/imap_wrapper.py` -- connexion/déconnexion IMAP.
- `dba/api/connectors/mysql.py`, `postgres.py` -- établissement de
  connexion (mot de passe stocké en clair côté base locale, décision
  déjà documentée dans `dba/README.md` -- jamais introduite ici).
- `vault/admin-api/app.py` -- `send_alert_email` (identifiants SMTP).
- `tickets/api/google_oauth.py` -- échange de code, rafraîchissement
  de jeton, récupération paginée du calendrier.
- `cacti/api/app.py`, `owncloud/api/app.py`, `ipam/api/app.py`,
  `optick/api/app.py`, `zenoss/api/app.py` (livraison #224) --
  connexion MySQL (`get_connection`), motif identique dans les 5.
- `owncloud/search-api/app.py` (#224) -- appels Elasticsearch
  (`es_get`/`es_post`).
- `geo-import/api/app.py` (#224) -- import ogr2ogr (subprocess) et
  synchronisation des géolocalisations pixel-grid (réseau). **Point
  le plus critique de ce lot** : le DSN PostgreSQL passé à `ogr2ogr`
  contient le mot de passe EN CLAIR (`pg_dsn()`, comportement
  EXISTANT non modifié) -- vérifié explicitement, avec un vrai mot de
  passe distinctif injecté dans le DSN et la commande réelle, que
  RIEN n'apparaît dans les traces (seuls le nom de table, le mode et
  le chemin du fichier sont tracés, jamais `cmd` ni `dsn` eux-mêmes).
- `rsyslog-listener/api/listener.py` (#224) -- écoute UDP syslog.
  Traçage VOLONTAIREMENT LIMITÉ au démarrage du socket et au
  ré-enregistrement périodique (déjà throttlé à 300s) -- JAMAIS par
  paquet reçu (flux potentiellement à fort volume, aurait noyé le
  tampon partagé de bruit) -- vérifié explicitement qu'aucune trace
  supplémentaire n'apparaît même après plusieurs paquets traités.
- `tts-gu/api/app.py` (#225) -- connexion MySQL, même motif que
  cacti/owncloud/ipam/optick/zenoss.
- `pixel-grid/api/app.py` (#225) -- trois services externes
  (GeoIP, géocodage BAN/Géoplateforme, communes par code postal).
  URLs de fournisseurs surchargeables via `.env` -- vérifié
  explicitement, avec une clé d'API hypothétique injectée dans une
  URL de test, que l'URL RÉSOLUE n'est jamais tracée (seuls les
  paramètres d'entrée -- IP, requête, code postal -- le sont).
- `schema-analyzer/api/schema_client.py` (#225) -- client HTTP vers
  dba-api (interne, sans authentification).
- `tickets/api/backup_manager.py` (#225) -- sauvegarde/restauration
  PostgreSQL (`pg_dump`/`psql`). Mot de passe transmis via la
  variable d'environnement `PGPASSWORD` (même motif que `SSHPASS`
  côté ssh-tunnels) -- jamais dans la commande elle-même ni dans
  `env`, qui n'est jamais tracé.

**Item considéré comme suffisamment couvert malgré une couverture
partielle** : `dba/api/connectors/postgres.py` -- seule `_connect`
(le point le plus à risque, réseau/authentification) est tracée
depuis #223 ; les 13 méthodes CRUD restantes (list_tables,
browse_rows, execute_sql...) délèguent toutes à `_connect` en
interne et bénéficient donc DÉJÀ de sa traçabilité pour la partie
"établissement de connexion" -- les tracer individuellement
apporterait une valeur marginale pour un effort disproportionné,
cohérent avec la philosophie pragmatique de cet audit.

**Les 19 modules identifiés en #223 sont désormais tous couverts**
(certains partiellement, comme `postgres.py` ci-dessus, par choix
assumé plutôt que par oubli).

**Particularité de l'audit rétroactif** : contrairement à la chaîne
construite pendant cette session (#215-217, traçage exhaustif de
CHAQUE fonction), cet audit privilégie une couverture PRAGMATIQUE --
les points de passage UNIQUES (`_get`/`_post` chez Nebula,
`_raise_with_detail` chez GLPI/Mayan) et les fonctions d'établissement
de connexion/session (les plus critiques pour "identifier vite les
points de blocage"), plutôt qu'un traçage méthode par méthode de
CHAQUE fonction de CHAQUE client -- pour pouvoir avancer sur PLUS de
modules dans le temps disponible.

**Un vrai bug trouvé en testant (`ldap_client.py`)** : les traces
utilisaient `config.get("host")` alors que la vraie clé du dict de
configuration est `url` -- auraient toujours affiché `None`. Corrigé
avant livraison.

## Ce qui N'est PAS encore couvert

Les 19 modules identifiés au démarrage de cet audit (#223) sont tous
traités (voir ci-dessus). Au-delà de cette liste initiale, ce projet
compte encore d'autres modules (front-end hub, scripts ponctuels,
petits utilitaires) jamais passés en revue systématiquement pour ce
chantier précis. La discipline reste la même à appliquer au fil de
l'eau : chaque nouveau module ou modification touchant une étape à
risque (réseau, subprocess, fichier, base de données) devrait suivre
cette même convention dès sa conception, plutôt que d'attendre un
nouvel audit rétroactif.

## Non vérifié dans cet environnement

Le comportement RÉEL en production (volume de logs generé, impact
sur les performances si `LOG_CAPTURE_LEVEL=DEBUG` est activé sur un
service à fort trafic) -- à observer en conditions réelles. Comme
convenu : "on fera des passes d'optimisation ensuite" une fois
l'usage réel constaté.
