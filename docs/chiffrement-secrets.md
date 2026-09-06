# Chiffrement des secrets de démarrage

Suivi technique du chantier ouvert par l'urgence matrice de risque
(points 2/3 : mots de passe `.env` et clés SSH en clair). Complète
`docs/pra-secrets-demarrage.docx` (la procédure de garde de la
phrase de passe, document formel versionné) -- ce fichier-ci est la
référence développeur : ce qui est construit, comment l'utiliser,
ce qui reste à faire.

## État d'avancement

| Étape | Statut | Livraison |
|---|---|---|
| Primitives de chiffrement (`shared/secret_crypto.py`) | ✅ Livré, testé (21 cas) | #202 |
| PRA -- procédure de garde de la phrase de passe | ✅ Livré, versionné dans Aide/Cyber | #203 |
| Outil CLI (`scripts/secrets_tool.py`) | ✅ Livré, testé (CLI + sous-processus réel) | #204 |
| Câblage dans `scripts/run.sh` | ✅ Livré, testé de bout en bout (faux `docker compose`) | #205 |
| Alertes SMS/courriel (PRA section 4) | ✅ Livré, best-effort, testé (dont échecs réseau réels) | #206 |
| Migration des secrets RÉELS (`.env`, clés SSH) | ⬜ Pas commencé -- l'outil (`encrypt-env`) est prêt, reste à décider AVEC la personne quand/comment l'utiliser sur le vrai `.env` | -- |

## Migration vers le chiffrement (`.env` → `.env.encrypted`)

`scripts/run.sh` détecte automatiquement un fichier `.env.encrypted`
à la racine du projet : s'il est absent, RIEN ne change (comportement
actuel préservé à l'identique, aucune invite). S'il est présent, la
phrase de passe est demandée à chaque lancement, les secrets déchiffrés
sont injectés dans l'environnement du seul processus `docker compose`
en cours -- jamais écrits sur disque, jamais persistants au-delà de
ce lancement.

### Voie recommandée : script guidé (livraison #386)

```bash
./scripts/migrate-env-to-encrypted.sh
```

Fait, DANS L'ORDRE, sans jamais toucher au `.env` d'origine :
1. **Sauvegarde** horodatée (`.env.backup-<date>-<heure>`), jamais
   écrasée ni supprimée automatiquement.
2. **Chiffrement** (`encrypt-env`, ci-dessous) -- une phrase de passe
   est demandée deux fois (saisie + confirmation).
3. **Vérification** -- déchiffre IMMÉDIATEMENT le `.env.encrypted`
   fraîchement créé (même phrase de passe redemandée, jamais stockée
   entre les deux étapes) et compare CHAQUE clé/valeur avec
   l'original (`scripts/verify_env_migration.py`) -- pas une
   confiance aveugle dans le chiffrement, une vérification RÉELLE
   que l'aller-retour est fidèle à 100 %.

En cas d'écart détecté (ne devrait normalement arriver que si les
deux phrases de passe saisies ne correspondaient pas) : le script le
signale précisément (quelle(s) clé(s) posent problème) et s'arrête --
`.env` et sa sauvegarde restent intacts dans tous les cas, rien n'est
jamais perdu.

Une fois la vérification réussie, le script rappelle la marche à
suivre pour BASCULER réellement (étape manuelle et délibérée,
JAMAIS automatique) : renommer temporairement `.env` pour tester un
déploiement normal avec `.env.encrypted` seul, confirmer que tout
fonctionne, puis supprimer la sauvegarde SOI-MÊME une fois pleinement
confiant.

### Voie manuelle (contrôle direct, sans sauvegarde automatique)

```bash
# chiffre le .env actuel vers .env.encrypted, sans jamais modifier
# ni supprimer le .env d'origine.
python3 scripts/secrets_tool.py encrypt-env --input .env --output .env.encrypted

# Une fois .env.encrypted en place et vérifié, RETIRER les valeurs
# maintenant redondantes de .env (ou les laisser -- .env.encrypted
# est prioritaire, voir plus bas) et relancer normalement :
./scripts/run.sh up --build
```

**Priorité en cas de doublon** : si une même clé existe à la fois
dans `.env` (résolu nativement par Docker Compose) et dans
`.env.encrypted` (exportée AVANT l'appel à `docker compose`, donc
dans l'environnement shell), c'est la valeur EXPORTÉE (celle de
`.env.encrypted`) qui l'emporte -- Docker Compose donne toujours la
priorité aux variables d'environnement shell sur celles lues depuis
un fichier `.env`.

**Limite connue, sans conséquence fonctionnelle** : `check-env.py`
(dans `run.sh`, avant le déchiffrement) compare `.env` au contenu de
`docker-compose.yml` -- une variable migrée vers `.env.encrypted`
peut donc y apparaître à tort comme "absente de .env", purement
informatif, sans bloquer le lancement.

## Alertes SMS/courriel (PRA section 4)

Entièrement optionnelles -- variables absentes = canal silencieusement
ignoré, aucun impact sur le déchiffrement lui-même (best-effort dans
les deux sens : un canal configuré mais injoignable au moment du
déploiement ne fait jamais échouer `run.sh`). Déclenchées
automatiquement par `decrypt-env` après un déchiffrement réussi.

```bash
# Canal SMS -- via la route machine de la passerelle SMS Teltonika
# TRB140 (indépendante de Keycloak, voir le PRA section 2/4).
SECRETS_ALERT_SMS_URL=https://trb140-sms-relay.exemple.local
SECRETS_ALERT_SMS_KEY=<RELAY_API_KEY de la passerelle>
SECRETS_ALERT_SMS_NUMBER=<numéro de réception>

# Canal courriel -- SMTP direct, adresse NON PERSONNELLE recommandée
# (boîte partagée de l'organisation, voir le PRA section 4).
SECRETS_ALERT_SMTP_HOST=smtp.exemple.local
SECRETS_ALERT_SMTP_PORT=587
SECRETS_ALERT_SMTP_USER=<optionnel>
SECRETS_ALERT_SMTP_PASSWORD=<optionnel>
SECRETS_ALERT_SMTP_FROM=supervision-si@exemple.local
SECRETS_ALERT_EMAIL_TO=alertes-si@exemple.local
SECRETS_ALERT_SMTP_USE_TLS=true   # défaut, mettre "false" pour désactiver
```

Ces variables sont volontairement à part de `.env`/`.env.encrypted`
(jamais chiffrées elles-mêmes -- ce sont des paramètres de
configuration, pas des secrets au même titre que les mots de passe
applicatifs) -- à définir directement dans l'environnement d'exécution
de `scripts/run.sh`, ou dans `.env` si la personne préfère.

## Utilisation du CLI (`scripts/secrets_tool.py`)

**Aucune de ces commandes ne touche à un secret réel du projet** --
elles produisent des valeurs/fichiers chiffrés que la personne choisit
ensuite d'utiliser ou non.

```bash
# Une seule fois par installation -- génère le sel (non secret, mais
# à ne JAMAIS régénérer une fois des secrets réels chiffrés avec).
python3 scripts/secrets_tool.py init-salt

# Chiffrer une valeur (mot de passe, clé API...) -- saisie masquée,
# jamais en argument de commande.
python3 scripts/secrets_tool.py encrypt-value

# Vérifier qu'un jeton se déchiffre bien avec la bonne phrase de passe.
python3 scripts/secrets_tool.py decrypt-value "gAAAAA..."

# Chiffrer un fichier (ex. une clé SSH) -- écrit <fichier>.enc,
# l'original n'est jamais modifié ni supprimé.
python3 scripts/secrets_tool.py encrypt-file ssh-tunnels/keys/ma_cle.pem

# Vérifier le déchiffrement d'un fichier .enc.
python3 scripts/secrets_tool.py decrypt-file ssh-tunnels/keys/ma_cle.pem.enc

# Chiffrer un fichier .env ENTIER (migration -- voir section dédiée
# ci-dessus) -- commentaires et lignes vides conservés tels quels.
python3 scripts/secrets_tool.py encrypt-env --input .env --output .env.encrypted

# Déchiffrer un .env.encrypted -> lignes "export CLE=valeur" sur
# stdout (utilisé automatiquement par scripts/run.sh, rarement appelé
# à la main directement).
python3 scripts/secrets_tool.py decrypt-env --input .env.encrypted
```

Le sel est stocké par défaut dans `.secrets.salt` à la racine du
projet (non secret, versionnable -- `--salt-file` pour un autre
emplacement).

## Rappel critique

Si la phrase de passe maîtresse est perdue, tout ce qui a été
chiffré avec devient définitivement irrécupérable -- aucune porte
dérobée n'existe ni ne doit exister. Voir la procédure de garde
complète dans `docs/pra-secrets-demarrage.docx`.

## Vérifié réellement

`secrets_tool.py` testé en profondeur : cycle complet chiffrement/
déchiffrement d'une valeur ET d'un fichier (simulant une vraie clé
SSH), protection confirmée -- un sel déjà existant n'est **jamais**
régénéré (même si la commande `init-salt` est rappelée), une
tentative de déchiffrement sans sel existant échoue proprement sans
en inventer un, une mauvaise phrase de passe échoue proprement (code
de sortie 1, jamais un plantage), le fichier original reste
intact après chiffrement. Testé aussi en **sous-processus réel**
avec entrée pipée (pas seulement en import direct des fonctions) --
confirme que le câblage `argparse`/`getpass` fonctionne de bout en
bout, pas seulement la logique interne.

**`migrate-env-to-encrypted.sh` + `verify_env_migration.py`
(livraison #386)** : `verify_env_migration.py` testé avec 3
scénarios (tout correspond, valeur différente après aller-retour,
clé manquante) -- y compris une valeur contenant une apostrophe
(dé-quotage `shlex` correct). Script d'orchestration testé de bout
en bout avec de VRAIS `secrets_tool.py`/`secret_crypto.py` (paquet
`cryptography` disponible dans cet environnement, contrairement à
`ping`/`iperf3`/`pysnmp` -- migration complète réellement exécutée
sur un `.env` de test réaliste), ET séparément avec des remplaçants
factices pour isoler la LOGIQUE D'ORCHESTRATION (sauvegarde créée,
cas de succès, cas d'incohérence détectée -- `.env` original confirmé
INTACT dans les deux cas, refus d'écraser un `.env.encrypted` déjà
présent). **Limite du test avec les vrais outils** : la saisie de
phrase de passe interactive à travers plusieurs invocations Python
enchaînées via un seul pipe stdin s'est révélée peu fiable dans CET
environnement sandboxé spécifiquement (`EOFError` sur la 3e
invite) -- comportement d'un harnais de test automatisé, PAS de la
vraie utilisation interactive (la personne tape sa phrase de passe
en direct, sans pipe) -- à confirmer malgré tout au premier usage
réel.

**`migrate-ssh-keys-to-encrypted.sh` + `verify_file_migration.py`
(livraison #387)** : compagnon de `migrate-env-to-encrypted.sh`
ci-dessus pour les clés SSH de `ssh-tunnels/keys/` -- même séquence
(sauvegarde -> chiffrement -> déchiffrement de vérification), mais
comparaison OCTET PAR OCTET (pas clé=valeur, une clé SSH n'a pas
cette structure). Un vrai bug trouvé en écrivant ce script : les
arguments `path` de `encrypt-file`/`decrypt-file` sont POSITIONNELS,
pas `--path` (confondu avec la convention `--input`/`--output` de
`encrypt-env`/`decrypt-env`, qui eux SONT nommés) -- corrigé avant
tout test. Découverte des clés testée (un fichier = une clé,
`README.md`/`*.pub` correctement exclus, même convention que
`ssh-tunnels-api` lui-même). Logique d'orchestration testée avec des
remplaçants factices (succès, écart détecté -- clé d'origine
confirmée INTACTE --, dossier sans clé à migrer). Même limite de test
que #386 avec les vrais outils (saisie de phrase de passe à travers
plusieurs invocations enchaînées sur un pipe unique, artefact du
harnais de test).

**Bug réel trouvé et corrigé en testant `encrypt-env`/`decrypt-env`**
: une valeur VIDE dans le `.env` source (motif courant de ce projet,
voir `.env.example`) faisait échouer TOUT le déchiffrement dès la
première rencontrée -- `decrypt-env` tentait de déchiffrer une chaîne
vide comme si c'était un jeton. Corrigé pour traiter une valeur vide
symétriquement à `encrypt-env` (jamais chiffrée, jamais déchiffrée).

**Sécurité du passage par le shell** testée avec un fichier `.env`
contenant volontairement des caractères spéciaux (`$`, `'`, `"`,
backtick, espaces) dans une valeur -- confirmé : la valeur ressort
EXACTEMENT identique après le cycle chiffrement → déchiffrement →
`eval` bash, sans qu'aucun caractère ne soit interprété comme une
commande ou casse la syntaxe (protection par `shlex.quote`).
Confirmé aussi que le prompt de phrase de passe et tous les messages
d'état de `decrypt-env` passent par stderr, jamais stdout -- seules
les lignes `export CLE=valeur` s'y trouvent, condition nécessaire
pour un `eval` sûr côté `run.sh`.

**Câblage `scripts/run.sh` testé de bout en bout** avec un faux
`docker compose` (script substitué temporairement, affichant les
variables d'environnement qu'il recevrait réellement) :
- **Sans** `.env.encrypted` : comportement rigoureusement inchangé,
  aucune invite, aucun message supplémentaire.
- **Avec** `.env.encrypted` : la phrase de passe est demandée, les
  secrets déchiffrés atteignent bien le faux `docker compose` avec
  leur valeur exacte d'origine -- confirmé sur un cas réaliste (deux
  secrets, dont un avec espaces).
