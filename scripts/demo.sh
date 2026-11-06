#!/usr/bin/env bash
# Démonstration automatisée du hub (#982) : visite d'un parcours (demo/parcours/<id>.json), captures, diaporama HTML
# autonome et présentation .pptx dans demo/sorties/<parcours>-<date>/.
#   ./scripts/demo.sh                                   liste des parcours
#   ./scripts/demo.sh idruide
#   ./scripts/demo.sh maj-terminal --var terminal="E22 LabCo" --var nom_reseau="E22-LabCo"
# Réglages (.env) : DEMO_HUB_URL, DEMO_USER, DEMO_PASSWORD -- passés au conteneur par fichier, jamais en argument.
set -euo pipefail
cd "$(dirname "$0")/.."
SORTIE="${DEMO_SORTIE:-$PWD/demo/sorties}"
mkdir -p "$SORTIE"
echo "construction de l'outil de démonstration…"
docker build -q -t si-demo -f demo/Dockerfile . >/dev/null
ENVF="$(mktemp)"; trap 'rm -f "$ENVF"' EXIT
grep -E '^DEMO_(HUB_URL|USER|PASSWORD)=' .env > "$ENVF" || true
docker run --rm --network host --env-file "$ENVF" -e DEMO_LIVRAISON="$(cat shared/DELIVERY_NUMBER)" \
  -v "$SORTIE:/sortie" --user "$(id -u):$(id -g)" si-demo "$@"
