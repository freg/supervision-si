#!/usr/bin/env bash
# Démarrage du stack Mayan EDMS (livraison #158) -- SÉPARÉ du stack
# principal, même motif que gateway/ (voir gateway/scripts/run.sh
# pour le raisonnement complet sur -p/--env-file/--project-directory
# et le réseau Docker partagé, jamais dupliqué ici au-delà du
# nécessaire).
#
# Usage : ./mayan/scripts/run.sh [arguments passés tels quels à docker compose]
#   ./mayan/scripts/run.sh up -d --build
#   ./mayan/scripts/run.sh down
#
# Contrairement à Keycloak (gateway/), AUCUNE dance d'import manuel
# ici -- Mayan gère sa propre initialisation via MAYAN_AUTOADMIN_*
# (voir docker-compose.yml), un simple `up` suffit toujours.
#
# ⚠️  NON VÉRIFIÉ dans cet environnement (aucun moteur Docker
# disponible ici) -- à tester en PRIORITÉ, voir mayan/README.md.

set -euo pipefail

HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # mayan/
PROJECT_ROOT="$(cd "$HERE_DIR/.." && pwd)"

fail() {
  echo "" >&2
  echo "❌ ARRÊT — le stack mayan n'a PAS été (re)lancé. Voir l'erreur ci-dessus." >&2
  echo "" >&2
  exit 1
}

# Vérification précoce de .env (livraison #346) -- voir
# gateway/scripts/run.sh pour le raisonnement complet (même piège,
# jamais dupliqué au-delà de ce qui est nécessaire ici).
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

compose() {
  docker compose \
    -p supervision-si-mayan \
    --env-file "$PROJECT_ROOT/.env" \
    --project-directory "$PROJECT_ROOT" \
    -f "$HERE_DIR/docker-compose.yml" \
    "$@"
}

# Réseau Docker PARTAGÉ avec le stack principal -- créé de façon
# IDEMPOTENTE, voir gateway/scripts/run.sh pour le raisonnement
# complet (peu importe lequel des run.sh de ce projet démarre en
# premier).
NETWORK_NAME="${SUPERVISION_SI_NETWORK_NAME:-supervision-si-net}"
docker network create "$NETWORK_NAME" >/dev/null 2>&1 || true

# HOST_IP -- même détection que scripts/run.sh, uniquement pour le
# message final ci-dessous (jamais transmis à Mayan lui-même, qui
# n'en a pas besoin -- contrairement au stack principal, aucune URL
# ne se construit dynamiquement avec HOST_IP côté Mayan).
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

compose "$@" || fail

for arg in "$@"; do
  if [ "$arg" = "up" ]; then
    echo ""
    echo "Mayan EDMS : http://${HOST_IP:-localhost}:${MAYAN_PORT:-8100} une fois démarré"
    echo "(premier démarrage plus long que les suivants -- Mayan initialise sa base"
    echo "et crée le compte admin automatiquement, voir MAYAN_AUTOADMIN_* dans .env)."
    echo ""
    break
  fi
done
