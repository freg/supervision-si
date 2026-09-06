# Données d'exemple (`scripts/seed-sample-data.py`)

Demandé explicitement (2026-09-05) : "un package complet autonome...
ça signifie aussi des données exemples pour tous les modules". Voir
`README.md` (section "Premier démarrage rapide") pour
`scripts/generate-env.sh`, le préalable à ce script.

## Prérequis

Le stack COMPLET doit déjà tourner -- `./scripts/run-all.sh all up -d
--build` (voir README.md), PAS `./scripts/run.sh` seul (ne démarre
que le stack principal, jamais `gateway/` -- sans lui, RIEN n'écoute
sur `GATEWAY_PORT`, ce script échouerait entièrement). Laisser le temps aux services de finir
leur démarrage avant de lancer ce script (quelques secondes après
`docker compose up`) -- un échec isolé au premier essai est normal si
lancé trop tôt, relancer suffit.

```bash
python3 scripts/seed-sample-data.py
```

## Portée -- modules NATIFS uniquement

Couvre les modules qui ne dépendent d'AUCUN système externe
PRÉEXISTANT :

- **tickets-api** -- 2 types, 1 site, 2 niveaux, 3 tickets d'exemple,
  1 événement calendrier (import ICS direct).
- **tasks-api** -- 3 tâches Kanban (une par colonne : todo/doing/done).
- **architecture-api** -- 3 équipements réseau d'exemple.
- **snmp-api** -- 1 cible SNMP d'exemple (nécessite
  `SNMP_CRED_PASSPHRASE`/`SNMP_CRED_SALT` déjà configurés --
  `scripts/generate-env.sh` s'en charge automatiquement).
- **classifier-api** -- 1 dictionnaire "infrastructure" (6 termes).
- **ged-api** -- 2 documents texte d'exemple. **Nécessite le stack
  Mayan SÉPARÉ démarré en plus** (`./mayan/scripts/run.sh up -d
  --build`, voir mayan/README.md) -- ged-api appelle Mayan de façon
  SYNCHRONE pour créer chaque document, jamais un crash si Mayan est
  injoignable, mais une erreur 502 par document, comptée en échec
  sans bloquer le reste du script.

## Cible la passerelle, jamais un port direct

Vérifié explicitement (2026-09-05) : AUCUN des modules ci-dessus ne
publie de port directement sur l'hôte (`docker-compose.yml`, aucune
section `ports:` pour tickets-api/tasks-api/architecture-api/
snmp-api/classifier-api/ged-api) -- seule la passerelle unique
(`tls-proxy`, `HOST_IP:GATEWAY_PORT/api/<service>/...`) y donne
accès. Ce script cible donc systématiquement cette passerelle,
jamais un port de service individuel.

Vérification TLS désactivée volontairement (certificat auto-signé,
même confiance que le navigateur qui l'accepte manuellement au
premier accès) -- pratique acceptée UNIQUEMENT pour ce script de
test local, jamais à reproduire pour un usage réel en dehors de ce
contexte.

Aucune authentification Keycloak requise pour ces appels -- confirmé
par relecture de `tls-proxy/render_nginx_conf.py` (aucun
`auth_request` sur les chemins `/api/*`), seul `rights-api` (opt-in,
désactivé par défaut dans le `.env` généré par
`scripts/generate-env.sh`) ajouterait une contrainte.

## Explicitement HORS DE PORTÉE ici

- **Tous les modules pont vers un système externe réel** (LDAP,
  IPAM/Optick/Zenoss/TTS-GU/OwnCloud/Cacti, GLPI, Nebula, IMAP réel,
  network-agent) -- une donnée d'exemple n'aurait aucun sens ici, ces
  modules lisent une base/un service qui doit exister réellement
  chez vous. Voir le README de chaque module pour sa propre
  configuration.
- **pixel-grid** -- a DÉJÀ son propre générateur de données dédié et
  bien plus élaboré (`pixel-grid/data-generator/`, séries temporelles
  réalistes), réutilisé tel quel plutôt que dupliqué ici.

## Vérifié réellement

Chaque payload testé directement contre son module (clients de test
Flask, même méthode que le reste de ce projet) avant d'écrire le
script définitif -- tickets-api (types/sites/niveaux/tickets/import
calendrier), tasks-api (3 tâches), architecture-api (3 équipements),
classifier-api (import multipart, 6 termes comptés), ged-api
(création de document, `mayan_client` simulé puisque Mayan lui-même
n'est pas disponible dans cet environnement de développement --
confirmé code 201, jamais le 202 mentionné dans le docstring de la
route, qui décrit la réponse INTERNE de Mayan, pas celle renvoyée par
ged-api à son appelant). snmp-api : `pysnmp` non installable dans cet
environnement (dépendance réelle du conteneur, absente ici) --
logique de chiffrement + stockage (`credential_crypto.py`+
`targets_store.py`) vérifiée directement en contournant l'import
complet de `app.py` (qui charge `snmp_client.py`, lequel importe
`pysnmp` pour d'AUTRES routes non concernées ici).

Idempotence : PAS construite dans cette première passe -- relancer ce
script ajoute une NOUVELLE copie de chaque exemple plutôt que de
détecter un doublon. Pensé pour un premier peuplement sur un stack
fraîchement démarré, pas une resynchronisation répétée.

## Reste à faire

- Détection de doublon avant insertion (idempotence réelle).
- Éventuellement : ssh-tunnels (tunnels d'exemple, mais les clés
  privées nécessitent des fichiers réels sur l'hôte -- moins évident
  à simuler qu'un simple POST JSON).
