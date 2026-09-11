# ProjeQtOr (fork supervision-si)

Gestion de projets intégrée au hub, à partir d'un **fork de
[ProjeQtOr](https://www.projeqtor.org/) V13.1.0** (PHP + Dojo côté
client, base MySQL/MariaDB ou PostgreSQL, licence AGPL/GPL — voir
`src/license.txt`). Livraison #476.

But annoncé par la personne : **réutiliser ProjeQtOr et y contribuer
avec une ergonomie revue à sa façon**, en l'intégrant au hub comme une
tuile de premier rang.

## Architecture

- `projeqtor-app` (`Dockerfile`, `docker-entrypoint.sh`) : Apache +
  PHP 8.3, sources dans `/var/www/html/projeqtor/`. **PHP 8.3 et pas
  8.4** : l'extension `imap` (requise, voir `src/readme.txt`) a quitté
  le noyau PHP en 8.4.
- `projeqtor-db` : MariaDB 11.4 **dédiée** (volume `projeqtor_db_data`,
  aucun port publié — joignable uniquement depuis le réseau Docker
  partagé). Choix fait avec la personne : chemin de référence upstream,
  isole le fork du reste de la plateforme.
- Routage : `tls-proxy/render_nginx_conf.py`, chemin `/projeqtor/`,
  type **"spa"** (préfixe CONSERVÉ — le docroot Apache contient le
  dossier `projeqtor/`, comme l'installation traditionnelle en
  sous-dossier). Après le premier déploiement, **penser au
  `./gateway/scripts/run.sh restart tls-proxy`** (piège connu #151 :
  `up -d --build` ne redémarre pas tls-proxy pour un fichier monté).
- Tuile hub : `hub/src/lib.js` (`buildFrontsList`, paramètre
  `projeqtorUrl`), **visible de tous** (décision explicite), embarquable
  en onglet de la coquille (même origine via tls-proxy).
- Page publique : `/projeqtor/` passe par le frontal public comme le
  reste de la passerelle — voir `docs/acces-public-frontal.md` § 6 pour
  les conséquences de sécurité (l'écran de connexion de ProjeQtOr est la
  SEULE barrière côté Internet).

## Politique de fork — IMPORTANT pour les futures retouches

`src/` contient l'archive officielle **V13.1.0 TELLE QUELLE**
(sha256 du zip : `221c2a0b2facbdfc0b5af9878e030cdd7ded6e3f989b1da9cd609eccebaa0a69`,
SourceForge `projectorria`). Règle : tant qu'une retouche d'ergonomie
n'est pas décidée, **ne rien modifier dans `src/`** — un
`diff -r` contre l'archive officielle doit montrer exactement nos
seules modifications, ce qui conditionne la capacité à merger les
montées de version upstream (ProjeQtOr publie une version majeure
environ tous les 2 mois) et à contribuer en retour.

Les adaptations d'infrastructure (localisation du fichier de
paramètres, configuration) ne sont PAS dans `src/` : elles vivent dans
le `Dockerfile` (`tool/parametersLocation.php` écrit au build) et
`docker-entrypoint.sh` (génération de `parameters.php` au premier
démarrage).

## Paramètres et données

- `/data` (bind mount `${PROJEQTOR_DATA_DIR:-./projeqtor/data}`) :
  `config/parameters.php`, `attachments/`, `documents/`, `logs/`,
  `tmp/` — tous HORS de la portée web (conseil de sécurité upstream).
  **`config/parameters.php` contient le mot de passe de la base en
  clair** (fonctionnement natif de ProjeQtOr, même posture que
  `dba/data`).
- Le fichier de paramètres est généré UNE SEULE FOIS depuis les
  variables `.env` (`PROJEQTOR_*` + `LDAP_*`). ProjeQtOr le réécrit
  quand on utilise son écran de configuration ; l'entrypoint n'écrase
  jamais un fichier existant. Le supprimer pour repartir des variables
  d'environnement.
- `PROJEQTOR_DB_PASSWORD` / `PROJEQTOR_DB_ROOT_PASSWORD` : générés par
  `scripts/generate-env.sh`.

## Premier démarrage

1. `./scripts/generate-env.sh` si pas déjà fait (nouvelle extraction).
2. `./scripts/run-all.sh all up -d --build` puis
   `./gateway/scripts/run.sh restart tls-proxy` (route `/projeqtor/`).
3. Ouvrir la tuile **ProjeQtOr** dans le hub (ou
   `https://<HOST_IP>:<GATEWAY_PORT>/projeqtor/`). ProjeQtOr crée son
   schéma à la première connexion.
4. Compte intégré **`admin` / `admin`** — **à changer immédiatement**,
   d'autant que la page est publique (voir ci-dessus).

## Authentification LDAP (annuaire du hub)

Si `LDAP_URL` est renseignée (c'est le défaut : `openldap-test`), les
paramètres `paramLdap_*` sont générés dans `parameters.php` :
`uid=%USERNAME%` sous `LDAP_USERS_DN`, compte de recherche
`LDAP_BIND_DN`. Les mêmes identifiants que le hub ouvrent donc une
session ProjeQtOr. Le profil ProjeQtOr du nouvel utilisateur reste à
définir côté ProjeQtOr (comportement natif : création au premier
login, profil par défaut paramétrable dans l'administration).

Le groupe Keycloak **`projeqtor`** existe dans le realm (et le mapping
`GROUP_TO_ROLE` du hub) mais **ne filtre encore rien** : la tuile est
visible de tous. Réservé aux filtrages futurs.

## Vérifications

- **Faites ici** : 17 tests fonctionnels de l'entrypoint (rendu du
  `parameters.php`, échappement des quotes, parsing `ldap://`/`ldaps://`
  avec et sans port, idempotence, fail-fast sans
  `PROJEQTOR_DB_PASSWORD`) ; `render_nginx_conf.py --check` (route
  présente) ; tests Node de `buildFrontsList` (tuile visible sans
  groupe, absente si URL vide) ; non-régression des 29 tests hub ;
  `generate-env.sh` + `check-env.py` sur une copie complète ;
  validation YAML/JSON du compose et du realm.
- **JAMAIS vérifiées ici** (pas de Docker dimensionné, pas de
  navigateur) : le build de l'image (extensions PHP), le démarrage
  réel, l'initialisation de la base au premier accès, l'authentification
  LDAP réelle, l'embarquabilité en iframe de la coquille (Apache
  n'envoie pas de `X-Frame-Options` par défaut et tls-proxy non plus —
  attendu OK, à confirmer en conditions réelles), le comportement de
  ProjeQtOr derrière le double proxy du frontal public.

## Suite prévue (backlog)

Refonte d'ergonomie « à la façon » de la personne — par itérations
séparées, chaque modification visible via `diff -r` contre l'archive
upstream. ProjeQtOr supporte des thèmes ; commencer par là avant de
toucher aux vues Dojo.
