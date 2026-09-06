#!/usr/bin/env bash
# Lanceur central du stack -- vue d'état par MODULE (regroupement
# logique de services docker-compose.yml, voir scripts/launcher_status.py
# pour la table exacte) et commandes start/stop/restart, façon
# apachectl/service. Délègue TOUJOURS vers "docker compose", ne
# duplique jamais sa logique -- ce script ne fait qu'ORGANISER les
# appels et PRÉSENTER le résultat.
#
# Usage :
#   ./scripts/launcher.sh status                 # vue d'ensemble
#   ./scripts/launcher.sh status vault            # un seul module
#   ./scripts/launcher.sh start vault             # démarre un module
#   ./scripts/launcher.sh stop vault
#   ./scripts/launcher.sh restart vault
#   ./scripts/launcher.sh start all               # tout démarrer
#   ./scripts/launcher.sh stop all
#   ./scripts/launcher.sh                         # liste les modules connus
set -euo pipefail

HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE_DIR"

# MÊME cartographie que scripts/launcher_status.py (source unique de
# vérité pour l'affichage) -- redéclarée ici en bash pour start/stop
# (docker compose accepte une liste de noms de services en argument).
# Vérifier les DEUX fichiers à jour si un nouveau service est ajouté
# au docker-compose.yml -- pas de mécanisme automatique de synchro
# entre les deux pour l'instant (chacun dans son langage naturel :
# bash pour la commande, python pour le formatage).
#
# ⚠️ CORRIGÉ (livraison #374) -- `declare -A` (tableau associatif) est
# une fonctionnalité BASH 4+, absente de bash 3.2 (celui livré par
# défaut sur macOS) -- même piège que `scripts/run-all.sh`, corrigé
# dans la même livraison. Fonction `case` (bash 3.2-compatible) à la
# place -- MODULE_ORDER (chaîne simple, déjà bash 3.2-safe) reste la
# seule liste à maintenir pour ajouter un nouveau module plus tard.
module_services() {
  case "$1" in
    gateway) echo "tls-proxy" ;;
    keycloak) echo "keycloak keycloak-backup" ;;
    hub) echo "hub" ;;
    supervision) echo "api frontend pipeline memcached" ;;
    pixel-grid) echo "pixel-grid-postgres pixel-grid-api pixel-grid-bridge" ;;
    tickets) echo "tickets-postgres tickets-api tickets-portal" ;;
    dba) echo "dba-api dba-portal" ;;
    vault) echo "vault-api vault-portal vault-admin-api vault-admin-portal" ;;
    ipam) echo "ipam-api" ;;
    optick) echo "optick-api" ;;
    zenoss) echo "zenoss-api" ;;
    tts-gu) echo "tts-gu-api" ;;
    owncloud) echo "owncloud-api owncloud-search-api elasticsearch" ;;
    cacti) echo "cacti-api" ;;
    geo-import) echo "geo-postgres geo-import-api" ;;
    prefs) echo "prefs-api" ;;
    launcher) echo "launcher" ;;
    *) return 1 ;;
  esac
}
MODULE_ORDER="gateway keycloak hub supervision pixel-grid tickets dba vault ipam optick zenoss tts-gu owncloud cacti geo-import prefs launcher"

print_modules() {
  echo "Modules connus :"
  for name in $MODULE_ORDER; do
    echo "  $name  ->  $(module_services "$name")"
  done
}

print_usage() {
  echo "Usage : $0 <commande> [module]"
  echo ""
  echo "Commandes :"
  echo "  status [module]   affiche l'état (tous les modules, ou un seul si précisé)"
  echo "  start <module|all>"
  echo "  stop <module|all>"
  echo "  restart <module|all>"
  echo ""
  print_modules
}

all_services() {
  for name in $MODULE_ORDER; do
    echo "$(module_services "$name")"
  done
}

if [ $# -eq 0 ]; then
  print_usage
  exit 0
fi

command="$1"
shift

case "$command" in
  status)
    if [ $# -gt 0 ]; then
      module="$1"
      if ! module_services "$module" >/dev/null 2>&1; then
        echo "❌ Module inconnu : '$module'" >&2
        echo "" >&2
        print_modules >&2
        exit 1
      fi
      docker compose ps -a --format json $(module_services "$module") | python3 "$HERE_DIR/scripts/launcher_status.py" "$module"
    else
      docker compose ps -a --format json | python3 "$HERE_DIR/scripts/launcher_status.py"
    fi
    ;;

  start|stop|restart)
    if [ $# -eq 0 ]; then
      echo "❌ Précisez un module (ou 'all') : $0 $command <module|all>" >&2
      echo "" >&2
      print_modules >&2
      exit 1
    fi
    module="$1"
    if [ "$module" = "all" ]; then
      # shellcheck disable=SC2046
      docker compose "$command" $(all_services)
    else
      if ! module_services "$module" >/dev/null 2>&1; then
        echo "❌ Module inconnu : '$module'" >&2
        echo "" >&2
        print_modules >&2
        exit 1
      fi
      # shellcheck disable=SC2086
      docker compose "$command" $(module_services "$module")
    fi
    ;;

  *)
    echo "❌ Commande inconnue : '$command'" >&2
    echo "" >&2
    print_usage >&2
    exit 1
    ;;
esac
