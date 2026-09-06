#!/usr/bin/env bash
# Démarrage du stack Keycloak + tls-proxy, SÉPARÉ du stack principal
# (backlog, livraison #135) -- voir gateway/docker-compose.yml pour le
# raisonnement complet (pourquoi ce découpage, réseau Docker partagé,
# migration du volume Keycloak existant).
#
# Usage : ./gateway/scripts/run.sh [arguments passés tels quels à docker compose]
#   ./gateway/scripts/run.sh up -d --build
#   ./gateway/scripts/run.sh down
#
# Sous-commandes spéciales (pas transmises à docker compose), REPRISES
# à l'identique du script principal (scripts/run.sh) -- ce sont des
# opérations Keycloak, elles vivent maintenant ICI, pas là-bas :
#   ./gateway/scripts/run.sh reset-keycloak
#     Force la purge + réimport du realm Keycloak, IRRÉVERSIBLE. Voir
#     scripts/run.sh (raisonnement identique, jamais dupliqué au-delà
#     de ce qui est nécessaire ici).
#   ./gateway/scripts/run.sh reset-ldap-test
#     Force la purge + réamorçage de l'annuaire openldap-test,
#     IRRÉVERSIBLE (livraison #375) -- utile si "LDAP: error code 49 -
#     Invalid Credentials" persiste malgré un .env pourtant correct
#     (annuaire bootstrappé avec un AUTRE mot de passe, jamais mis à
#     jour depuis -- même principe que reset-keycloak ci-dessus).
#   ./gateway/scripts/run.sh restore-groups
#     Réapplique la dernière capture des appartenances aux groupes.
#
# Prompt "realm Keycloak changé" (livraison #155) : si le fichier
# realm-template.json semble différent du dernier import ET qu'aucun
# marqueur n'existe encore (jamais réimporté depuis la création du
# volume), le script REDEMANDE À CHAQUE EXÉCUTION -- répondre "non"
# ne fait volontairement PAS taire l'alerte, pour ne jamais perdre de
# vue un changement réel en attente (voir check_keycloak_realm_change
# plus bas, bug corrigé en #128). Si le realm n'a en réalité PAS
# changé pour de vrai (juste jamais marqué comme importé), répondre
# "marquer" au lieu de "non" : accepte l'état actuel SANS vider ni
# réimporter le volume, mais enregistre quand même le marqueur --
# l'alerte ne reviendra plus pour CE contenu exact, seulement si
# realm-template.json change réellement plus tard.

set -euo pipefail

HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # gateway/
PROJECT_ROOT="$(cd "$HERE_DIR/.." && pwd)"

fail() {
  echo "" >&2
  echo "❌ ARRÊT — le stack gateway n'a PAS été (re)lancé. Voir l'erreur ci-dessus." >&2
  echo "" >&2
  exit 1
}

# Vérification précoce de .env (livraison #346) -- CRITIQUE, sans
# lui docker compose échoue en toute fin de script avec un message
# Docker cru et peu clair ("couldn't find env file"), APRÈS avoir déjà
# rendu le realm/PKI/nginx en silencieusement supposant des valeurs
# de repli partout (LDAP_BIND_PASSWORD/PREFS_API_SERVICE_SECRET
# "change-me" alors qu'aucun des deux n'a en réalité été LU quelque
# part -- juste le défaut codé en dur de get_env(), .env étant
# entièrement absent). Piège réel rencontré : `.env` n'est JAMAIS
# inclus dans une livraison (secret, exclu par .gitignore) -- chaque
# nouvelle extraction d'archive nécessite de relancer
# scripts/generate-env.sh avant tout démarrage, sans quoi ce stade
# tardif et confus est atteint à chaque fois.
if [ ! -f "$PROJECT_ROOT/.env" ]; then
  echo "❌ $PROJECT_ROOT/.env introuvable." >&2
  echo "" >&2
  echo "   .env n'est JAMAIS inclus dans une livraison (secret, exclu du zip) --" >&2
  echo "   à générer une première fois après CHAQUE nouvelle extraction :" >&2
  echo "" >&2
  echo "     ./scripts/generate-env.sh" >&2
  echo "" >&2
  fail
fi

# --- Invocation docker compose UNIFORME pour tout ce script --------
# -p (nom de projet) DISTINCT du stack principal -- évite toute
# confusion Compose sur "quel projet possède quel conteneur" (deux
# projets, même réseau partagé, mais des ensembles de conteneurs
# disjoints).
# --env-file pointant vers LA RACINE -- ce stack lit le MÊME .env que
# le stack principal (identifiants admin Keycloak, LDAP_*, etc.),
# jamais une seconde copie à maintenir en double. Sans ce flag,
# Compose chercherait un .env dans CE dossier (gateway/), absent.
# --project-directory pointant vers LA RACINE -- fait résoudre tous
# les chemins relatifs de gateway/docker-compose.yml (./keycloak/import,
# ./pki/server, etc.) EXACTEMENT comme s'ils vivaient à la racine,
# cohérent avec KEYCLOAK_IMPORT_DIR/PKI_DIR déjà utilisés par le stack
# principal (même valeur, même résolution, y compris si personnalisés
# en chemin RELATIF dans .env -- voir gateway/docker-compose.yml).
compose() {
  docker compose \
    -p supervision-si-gateway \
    --env-file "$PROJECT_ROOT/.env" \
    --project-directory "$PROJECT_ROOT" \
    -f "$HERE_DIR/docker-compose.yml" \
    "$@"
}

# --- Réseau Docker PARTAGÉ avec le stack principal ------------------
# Créé de façon IDEMPOTENTE -- voir gateway/docker-compose.yml,
# en-tête, pour le raisonnement complet. Peu importe lequel des deux
# run.sh (celui-ci ou scripts/run.sh) démarre en premier -- le second
# à s'exécuter trouve le réseau déjà là, cette commande échoue
# silencieusement (`|| true`), rien d'anormal.
NETWORK_NAME="${SUPERVISION_SI_NETWORK_NAME:-supervision-si-net}"
docker network create "$NETWORK_NAME" >/dev/null 2>&1 || true

# --- Volume Keycloak, même motif IDEMPOTENT (livraison #347) --------
# gateway/docker-compose.yml le référence en `external: true` (voir
# ce fichier -- pensé pour une MIGRATION depuis l'architecture
# pré-#135, où ce volume existait déjà, créé par le stack principal
# avant la séparation). Piège réel pour un tout PREMIER déploiement
# (jamais de stack principal lancé avant, signalé par la personne) :
# `external: true` exige que le volume EXISTE déjà, docker compose ne
# le crée JAMAIS lui-même dans ce cas -- échec immédiat ("external
# volume ... not found") sans cette création préalable. `docker
# volume create` est lui-même idempotent (ne fait rien si le volume
# existe déjà, jamais une erreur ni un écrasement) -- couvre les DEUX
# cas (premier déploiement neuf, ou migration où le volume existe
# déjà) avec la même ligne, sans avoir à distinguer explicitement.
KEYCLOAK_VOLUME_NAME="${KEYCLOAK_DATA_VOLUME_NAME:-supervision-si_keycloak_data}"
docker volume create "$KEYCLOAK_VOLUME_NAME" >/dev/null 2>&1 || true

# --- HOST_IP -- même détection que scripts/run.sh -------------------
# Nécessaire pour KC_HOSTNAME (Keycloak) et GATEWAY_PORT (déjà dans
# .env, pas re-détecté ici).
#
# Détection via shared/detect-host-ip.sh (livraison #342) -- corrige
# un piège macOS réel : `hostname -I` (seule méthode utilisée avant
# cette livraison) N'EXISTE PAS sur macOS (BSD hostname), échouait
# silencieusement, laissant HOST_IP vide -- voir ce fichier pour le
# détail complet.
source "$PROJECT_ROOT/shared/detect-host-ip.sh"
if [ -z "${HOST_IP:-}" ]; then
  HOST_IP="$(detect_host_ip)"
fi
export HOST_IP

if [ -z "$HOST_IP" ]; then
  echo "Impossible de détecter automatiquement l'IP — définis HOST_IP manuellement :" >&2
  echo "  HOST_IP=<ton_ip> ./gateway/scripts/run.sh $*" >&2
  exit 1
fi
echo "HOST_IP détectée : $HOST_IP"

# --- Garde-fou LDAP_BIND_PASSWORD -- repris à l'identique -----------
# (voir scripts/run.sh pour le raisonnement complet : bug réel
# RÉCURRENT, un mot de passe LDAP corrigé à la main dans la console
# Keycloak écrasé silencieusement par le placeholder à la purge).
check_ldap_placeholder_and_block() {
  if [ -f "$PROJECT_ROOT/.env" ] && grep -q "^LDAP_BIND_PASSWORD=change-me$" "$PROJECT_ROOT/.env" 2>/dev/null; then
    echo ""
    echo "🔴 LDAP_BIND_PASSWORD vaut encore 'change-me' dans .env"
    echo ""
    echo "    Si tu as déjà corrigé ce mot de passe À LA MAIN dans la console"
    echo "    Keycloak (bug déjà rencontré PLUSIEURS FOIS : LDAP error code 49),"
    echo "    cette purge va ÉCRASER ce correctif par le placeholder et RECASSER"
    echo "    l'authentification LDAP pour tout le monde -- encore une fois."
    echo ""
    echo "    Mets la VRAIE valeur dans .env AVANT de continuer si c'est le cas."
    echo ""
    read -r -p "    Continuer quand même avec le placeholder actuel ? [oui/NON] " ldap_confirm
    case "$ldap_confirm" in
      oui|OUI|o|O) ;;
      *)
        echo "    Annulé -- corrige .env puis relance."
        exit 0
        ;;
    esac
  fi
  # Vérification SÉPARÉE de l'URL (livraison #368, demandé
  # explicitement -- signalé en conditions réelles par la personne :
  # un .env créé AVANT l'ajout de l'annuaire de test #348 garde
  # "ldap.example.local" -- un nom qui ne résout NULLE PART dans le
  # réseau Docker (UnknownHostException côté Keycloak), jamais
  # rattrapé par la vérification ci-dessus qui ne regarde QUE le mot
  # de passe. Purger/réimporter avec cette URL encore fausse
  # reproduit exactement le même échec après coup -- prévenir
  # AVANT plutôt que de laisser la personne redécouvrir la même
  # erreur après une purge (perte de temps, et pour de vrais
  # utilisateurs LDAP, perte de la capture de groupes faite juste
  # avant la purge).
  if [ -f "$PROJECT_ROOT/.env" ] && grep -q "^LDAP_URL=ldap://ldap\.example\.local" "$PROJECT_ROOT/.env" 2>/dev/null; then
    echo ""
    echo "🔴 LDAP_URL vaut encore 'ldap://ldap.example.local:389' dans .env"
    echo ""
    echo "    Ce nom d'hôte ne résout NULLE PART dans le réseau Docker de ce"
    echo "    projet (UnknownHostException côté Keycloak à l'authentification) --"
    echo "    c'est la valeur d'un .env créé AVANT l'ajout de l'annuaire de test"
    echo "    (livraison #348), jamais mise à jour depuis."
    echo ""
    echo "    Si tu utilises l'annuaire de TEST fourni avec ce projet"
    echo "    (openldap-test), la valeur attendue est :"
    echo "      LDAP_URL=ldap://openldap-test:389"
    echo "    Sinon, mets l'adresse RÉELLE de ton propre annuaire LDAP."
    echo ""
    echo "    Continuer maintenant purgerait/réimporterait le realm avec cette"
    echo "    URL encore fausse -- le MÊME échec de connexion réapparaîtrait"
    echo "    juste après, pour rien."
    echo ""
    read -r -p "    Continuer quand même avec cette URL actuelle ? [oui/NON] " ldap_url_confirm
    case "$ldap_url_confirm" in
      oui|OUI|o|O) ;;
      *)
        echo "    Annulé -- corrige LDAP_URL dans .env puis relance."
        exit 0
        ;;
    esac
  fi
}

if [ "${1:-}" = "reset-keycloak" ]; then
  check_ldap_placeholder_and_block
  echo "⚠️  Ceci va ARRÊTER le stack gateway et SUPPRIMER DÉFINITIVEMENT le volume"
  echo "    Keycloak (tous les comptes, groupes, sessions, réglages faits à la main"
  echo "    dans la console -- tout, pas seulement ce que réimporte realm-template.json)."
  echo ""
  read -r -p "Pour confirmer, tape exactement RESET : " confirm
  if [ "$confirm" != "RESET" ]; then
    echo "Annulé (rien n'a été touché)."
    exit 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    echo "Capture des appartenances aux groupes actuelles (avant purge)..."
    python3 "$PROJECT_ROOT/keycloak/group_memberships.py" export || \
      echo "⚠️  Capture échouée (Keycloak indisponible ?) -- rien à restaurer après coup."
  fi
  volume_name="${KEYCLOAK_DATA_VOLUME_NAME:-supervision-si_keycloak_data}"
  compose down
  docker volume rm "$volume_name" 2>/dev/null && echo "Volume '$volume_name' supprimé." || \
    echo "Volume '$volume_name' introuvable (déjà absent, ou KEYCLOAK_DATA_VOLUME_NAME à ajuster dans .env)."
  rm -f "$PROJECT_ROOT/keycloak/.last-imported-realm.json"
  echo "Relance avec : ./gateway/scripts/run.sh up -d --build"
  echo "Puis, une fois Keycloak démarré et la synchronisation LDAP relancée :"
  echo "  ./gateway/scripts/run.sh restore-groups"
  exit 0
fi

if [ "${1:-}" = "reset-ldap-test" ]; then
  # Livraison #375, demandé explicitement ("peux tu préparer une
  # script de nettoyage ?") après un cas RÉEL signalé par la
  # personne : .env avait LDAP_BIND_PASSWORD ET LDAP_TEST_ADMIN_PASSWORD
  # identiques et corrects, mais Keycloak refusait quand même avec
  # "LDAP: error code 49 - Invalid Credentials" -- cause la plus
  # probable (jamais confirmée à 100%, aucun accès direct aux
  # conteneurs de la personne pour vérifier) : l'annuaire openldap-test
  # avait été bootstrappé à un moment où .env portait ENCORE un AUTRE
  # mot de passe -- l'image osixia/openldap, comme Keycloak, n'amorce
  # ses données QU'À LA CRÉATION de ses volumes, jamais relu ensuite
  # même si .env change après coup. Contrairement à `keycloak_data`
  # (volume EXTERNAL, voir reset-keycloak ci-dessus), les volumes
  # openldap-test sont NORMAUX -- trouvés ici par le même filtre
  # d'étiquette Compose que find_keycloak_volume(), jamais un nom en
  # dur (le préfixe dépend de COMPOSE_PROJECT_NAME).
  echo "⚠️  Ceci va ARRÊTER openldap-test et SUPPRIMER DÉFINITIVEMENT ses"
  echo "    données (tous les comptes créés/modifiés depuis le bootstrap"
  echo "    initial) -- réamorcé ensuite depuis"
  echo "    gateway/ldap-seed/bootstrap.ldif avec le mot de passe ACTUEL"
  echo "    de .env (LDAP_TEST_ADMIN_PASSWORD)."
  echo ""
  echo "    Utile si Keycloak refuse l'authentification avec \"LDAP: error"
  echo "    code 49 - Invalid Credentials\" MALGRÉ un .env pourtant correct"
  echo "    (LDAP_BIND_PASSWORD = LDAP_TEST_ADMIN_PASSWORD) -- l'annuaire a"
  echo "    probablement été bootstrappé avec un AUTRE mot de passe,"
  echo "    jamais mis à jour depuis (même principe que reset-keycloak,"
  echo "    voir ci-dessus)."
  echo ""
  read -r -p "Pour confirmer, tape exactement RESET : " confirm
  if [ "$confirm" != "RESET" ]; then
    echo "Annulé (rien n'a été touché)."
    exit 0
  fi
  data_volume="$(docker volume ls --filter "label=com.docker.compose.volume=openldap_test_data" --format '{{.Name}}' 2>/dev/null | head -1)"
  config_volume="$(docker volume ls --filter "label=com.docker.compose.volume=openldap_test_config" --format '{{.Name}}' 2>/dev/null | head -1)"
  compose stop openldap-test 2>/dev/null || true
  compose rm -f openldap-test 2>/dev/null || true
  if [ -n "$data_volume" ]; then
    docker volume rm "$data_volume" && echo "Volume '$data_volume' supprimé."
  else
    echo "Volume de données openldap-test introuvable (déjà absent ?)."
  fi
  if [ -n "$config_volume" ]; then
    docker volume rm "$config_volume" && echo "Volume '$config_volume' supprimé."
  else
    echo "Volume de config openldap-test introuvable (déjà absent ?)."
  fi
  echo ""
  echo "Relance avec : ./gateway/scripts/run.sh up -d --build"
  exit 0
fi

if [ "${1:-}" = "restore-groups" ]; then
  echo "Restauration des appartenances aux groupes depuis la dernière capture..."
  echo "(nécessite que Keycloak tourne ET que les utilisateurs concernés aient"
  echo " déjà été synchronisés depuis LDAP -- \"Sync all users\" dans la console"
  echo " si ce n'est pas déjà fait.)"
  echo ""
  python3 "$PROJECT_ROOT/keycloak/group_memberships.py" restore
  exit $?
fi

# --- Rendu du realm Keycloak + config nginx -------------------------
# MÊMES scripts que le stack principal utilisait avant l'extraction,
# jamais dupliqués -- voir keycloak/render.py et
# tls-proxy/render_nginx_conf.py (racine du projet, pas copiés ici).
if command -v python3 >/dev/null 2>&1; then
  python3 "$PROJECT_ROOT/keycloak/render.py" || fail
else
  echo "⚠️  python3 introuvable — realm Keycloak non régénéré (keycloak/README.md)" >&2
fi

# CA (une fois pour toutes) puis certificat serveur (régénéré à chaque
# lancement pour coller au HOST_IP courant) -- voir pki/README.md.
if [ -x "$PROJECT_ROOT/pki/scripts/generate-ca.sh" ]; then
  "$PROJECT_ROOT/pki/scripts/generate-ca.sh" || fail
  "$PROJECT_ROOT/pki/scripts/generate-server-cert.sh" || fail
else
  echo "⚠️  pki/scripts/ introuvable — TLS non préparé (pki/README.md)" >&2
fi

if command -v python3 >/dev/null 2>&1; then
  python3 "$PROJECT_ROOT/tls-proxy/render_nginx_conf.py" || fail
fi

# --- Détection d'un realm Keycloak modifié --------------------------
# Repris à l'identique de scripts/run.sh (voir ce fichier pour le
# raisonnement complet -- pourquoi une confirmation explicite, capture
# des groupes avant purge, l'indicateur REALM_PURGE_DECLINED corrigé
# en #128). SEULE différence : `docker compose down`/`docker volume
# rm` invoqués via la fonction compose() définie plus haut (bons
# flags -p/--env-file/--project-directory), et find_keycloak_volume()
# n'a PAS besoin d'être réimplémentée -- le filtre par étiquette
# fonctionne À L'IDENTIQUE, cette étiquette ayant été posée à la
# création ORIGINALE du volume (par le stack principal, avant
# extraction), jamais liée à qui le référence ensuite.
REALM_JSON="$(python3 -c "
import sys, os
sys.path.insert(0, '$PROJECT_ROOT/keycloak')
from render import parse_env, resolve_import_dir
env = parse_env(os.path.join('$PROJECT_ROOT', '.env'))
try:
    print(os.path.join(resolve_import_dir(env), 'supervision-si-realm.json'))
except ValueError:
    pass
" 2>/dev/null)"
REALM_JSON="${REALM_JSON:-$PROJECT_ROOT/keycloak/import/supervision-si-realm.json}"
REALM_MARKER="$PROJECT_ROOT/keycloak/.last-imported-realm.json"

find_keycloak_volume() {
  docker volume ls --filter "label=com.docker.compose.volume=keycloak_data" --format '{{.Name}}' 2>/dev/null | head -1
}

check_keycloak_realm_change() {
  [ -f "$REALM_JSON" ] || return 0

  if [ -f "$REALM_MARKER" ] && cmp -s "$REALM_JSON" "$REALM_MARKER"; then
    return 0
  fi

  local volume_name
  volume_name="$(find_keycloak_volume)"

  if [ -z "$volume_name" ]; then
    return 0
  fi

  echo ""
  echo "⚠️  Le realm Keycloak (keycloak/realm-template.json) a changé depuis le dernier import."
  if [ -f "$REALM_MARKER" ]; then
    echo "    Différences détectées :"
    # (diff ... || true) -- `diff` renvoie 1 quand des différences
    # sont trouvées (comportement NORMAL ici, c'est précisément ce
    # qu'on cherche à détecter) -- sous `set -euo pipefail`, ce 1
    # ferait sortir tout le script AVANT d'atteindre la question
    # interactive plus bas, sans jamais l'afficher. Bug réel #280,
    # signalé par la personne en plein déploiement (le contournement
    # `< /dev/tty` n'y changeait rien, la vraie cause était une ligne
    # avant le `read`, jamais l'entrée standard elle-même).
    (diff -u "$REALM_MARKER" "$REALM_JSON" 2>/dev/null || true) | grep -E "^[+-]" | grep -v "^+++\|^---" | head -20 | sed 's/^/    /'
  else
    echo "    (aucun import précédent tracé — impossible d'afficher un diff, mais un volume Keycloak existe déjà)"
  fi
  echo ""
  echo "    Keycloak n'importe le realm QU'À LA CRÉATION de son volume --"
  echo "    tant que ce volume existe, ces changements resteront invisibles"
  echo "    pour Keycloak sans le vider et le réimporter."
  echo ""
  echo "    ⚠️  Vider ce volume perd TOUT ce qui n'existe QUE dans Keycloak"
  echo "    lui-même (mots de passe LDAP corrigés à la main, appartenances"
  echo "    aux groupes réajustées après incident, sessions actives...)."
  echo ""

  check_ldap_placeholder_and_block

  if command -v python3 >/dev/null 2>&1; then
    echo "    Capture des appartenances aux groupes actuelles (avant purge)..."
    python3 "$PROJECT_ROOT/keycloak/group_memberships.py" export || \
      echo "    ⚠️  Capture échouée (Keycloak indisponible ?) -- rien à restaurer après coup si tu continues."
    echo ""
  fi

  read -r -p "    Vider le volume Keycloak (${volume_name}) et réimporter maintenant ? [oui/non/marquer] " reply
  case "$reply" in
    oui|OUI|o|O)
      echo "    Arrêt du stack gateway, suppression du volume..."
      compose down || fail
      docker volume rm "$volume_name" || fail
      ;;
    marquer|MARQUER|m|M)
      # Demandé explicitement : le volume garde son contenu actuel
      # (rien vidé, rien réimporté), mais CE contenu exact de
      # realm-template.json est accepté comme "su" -- le marqueur sera
      # mis à jour normalement en fin de script (REALM_PURGE_DECLINED
      # reste à 0, la logique de fin de script s'en charge). Le
      # message ne reviendra donc PLUS pour ce contenu précis --
      # seulement si realm-template.json change à nouveau après ça.
      echo "    Volume conservé tel quel, mais ce contenu de realm MARQUÉ comme accepté --"
      echo "    ce message ne réapparaîtra plus pour cette version exacte. Il reviendra"
      echo "    si keycloak/realm-template.json change à nouveau plus tard."
      ;;
    *)
      echo "    Volume conservé tel quel -- le stack va démarrer avec l'ANCIEN realm."
      echo "    Relance ce script et réponds 'oui' quand tu seras prêt à réimporter."
      REALM_PURGE_DECLINED=1
      ;;
  esac
  echo ""
}

REALM_PURGE_DECLINED=0
check_keycloak_realm_change

compose "$@"

# Marqueur mis à jour uniquement après un "up" qui a RÉUSSI, et
# seulement si le réimport n'a pas été explicitement refusé --
# raisonnement identique à scripts/run.sh (bug corrigé en #128).
for arg in "$@"; do
  if [ "$arg" = "up" ]; then
    if [ "$REALM_PURGE_DECLINED" = "1" ]; then
      echo "⚠️  Marqueur de realm NON mis à jour (réimport refusé plus haut) --"
      echo "   la prochaine exécution te redemandera tant que tu n'auras pas répondu 'oui'."
    else
      cp "$REALM_JSON" "$REALM_MARKER" 2>/dev/null || true
    fi
    break
  fi
done
