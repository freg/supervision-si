#!/usr/bin/env bash
# Point d'entrée CENTRAL pour les différents stacks du projet -- ne
# duplique JAMAIS la logique de chaque run.sh (détection HOST_IP,
# rendu Keycloak/PKI/nginx, garde-fous LDAP...), délègue simplement
# vers le bon script au bon endroit. Ajouter un nouveau stack plus
# tard = une ligne dans TARGETS ci-dessous, rien d'autre à changer ici.
#
# Usage :
#   ./scripts/run-all.sh <cible> [arguments passés tels quels au run.sh de cette cible]
#   ./scripts/run-all.sh gateway up -d --build
#   ./scripts/run-all.sh main up -d --build
#   ./scripts/run-all.sh vault-standalone up -d --build
#   ./scripts/run-all.sh all up -d --build      # les trois, dans l'ordre
#   ./scripts/run-all.sh all down               # arrête les trois
#   ./scripts/run-all.sh                        # liste les cibles disponibles
set -euo pipefail

HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Cibles connues -- nom court -> chemin du run.sh correspondant,
# relatif à la racine du projet. Ordre = ordre d'exécution pour "all".
# "gateway" EN PREMIER (livraison #135) -- Keycloak/tls-proxy doivent
# être joignables avant que les services applicatifs ("main") ne s'y
# fient (LDAP, vérification de jeton future...) ; l'inverse reste
# possible grâce à la résolution DNS dynamique de tls-proxy (livraison
# #134) et au réseau Docker créé de façon idempotente par les deux
# scripts, mais cet ORDRE reste le plus logique par défaut. "mayan"
# (livraison #158) placé JUSTE APRÈS -- initialisation plus longue au
# premier démarrage (base + compte admin), autant lui laisser le plus
# de temps possible avant que "main" (ged-api) ne cherche à le
# joindre -- même raisonnement, pas un vrai blocage garanti pour
# autant (ged-api reste défensif si Mayan n'est pas encore prêt).
TARGETS_ORDER=(gateway mayan main vault-standalone)
# ⚠️ CORRIGÉ (livraison #374) -- `declare -A` (tableau associatif) est
# une fonctionnalité BASH 4+, absente de bash 3.2 (celui livré par
# défaut sur macOS, `/bin/bash`, jamais mis à jour par Apple depuis
# des années pour des raisons de licence GPLv3) -- `#!/usr/bin/env
# bash` en tête de ce fichier résout VERS CE bash 3.2 système sur un
# Mac qui n'a pas explicitement une version plus récente AVANT lui
# dans le PATH (ex. via Homebrew). Restait latent, jamais signalé --
# le même piège déjà trouvé une fois dans `scripts/chantier.sh`
# (#340, tableau vide + `set -u`), mais jamais recherché ailleurs
# dans ce fichier précis avant cette livraison. Remplacé par une
# fonction de correspondance (`case`, bash 3.2-compatible) --
# TARGETS_ORDER (tableau INDEXÉ simple, jamais associatif) reste
# la seule liste à maintenir pour ajouter un nouveau stack plus tard.
target_script() {
  case "$1" in
    gateway) echo "gateway/scripts/run.sh" ;;
    mayan) echo "mayan/scripts/run.sh" ;;
    main) echo "scripts/run.sh" ;;
    vault-standalone) echo "vault-standalone/scripts/run.sh" ;;
    *) return 1 ;;
  esac
}

print_usage() {
  echo "Usage : $0 <cible> [arguments...]"
  echo ""
  echo "Cibles disponibles :"
  for name in "${TARGETS_ORDER[@]}"; do
    echo "  $name  ->  $(target_script "$name")"
  done
  echo "  all   ->  toutes les cibles ci-dessus, dans l'ordre"
  echo ""
  echo "Exemples :"
  echo "  $0 gateway up -d --build"
  echo "  $0 mayan up -d --build"
  echo "  $0 main up -d --build"
  echo "  $0 vault-standalone up -d --build"
  echo "  $0 all up -d --build"
  echo "  $0 all down"
}

if [ $# -eq 0 ]; then
  print_usage
  exit 0
fi

target="$1"
shift

run_target() {
  local name="$1"
  shift
  local rel_script
  rel_script="$(target_script "$name")" || {
    echo "❌ $name : cible inconnue" >&2
    return 1
  }
  local script="$HERE_DIR/$rel_script"
  if [ ! -x "$script" ]; then
    echo "❌ $name : script introuvable ou non exécutable ($script)" >&2
    return 1
  fi
  echo ""
  echo "=== $name ($script) ==="
  "$script" "$@"
}

if [ "$target" = "all" ]; then
  # Arrêt volontaire au premier échec (set -e + pas de "|| true" ici) :
  # continuer à construire une autre cible après l'échec de la
  # première prêterait à confusion sur ce qui tourne réellement.
  for name in "${TARGETS_ORDER[@]}"; do
    run_target "$name" "$@"
  done
  exit 0
fi

if ! target_script "$target" >/dev/null 2>&1; then
  echo "❌ Cible inconnue : '$target'" >&2
  echo "" >&2
  print_usage >&2
  exit 1
fi

run_target "$target" "$@"
