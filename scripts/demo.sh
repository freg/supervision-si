#!/usr/bin/env bash
# Démonstration automatisée du hub (#982) : visite d'un parcours (demo/parcours/<id>.json), captures, diaporama HTML
# autonome et présentation .pptx dans demo/sorties/<parcours>-<date>/.
#   ./scripts/demo.sh                                   liste des parcours
#   ./scripts/demo.sh idruide
#   ./scripts/demo.sh maj-terminal --var terminal="E22 LabCo" --var nom_reseau="E22-LabCo"
# Réglages (.env) : DEMO_HUB_URL, DEMO_USER, DEMO_PASSWORD -- passés au conteneur par fichier, jamais en argument.
# DEMO_RESEAU (#989) : réseau du conteneur, « host » par défaut ; « bridge » isole Chromium des changements de réseau
# de l'hôte (net::ERR_NETWORK_CHANGED) si le hub est joignable depuis un conteneur ordinaire.
set -euo pipefail
cd "$(dirname "$0")/.."
SORTIE="${DEMO_SORTIE:-$PWD/demo/sorties}"
mkdir -p "$SORTIE"
echo "construction de l'outil de démonstration…"
docker build -q -t si-demo -f demo/Dockerfile . >/dev/null
ENVF="$(mktemp)"; trap 'rm -f "$ENVF"' EXIT
grep -E '^DEMO_(HUB_URL|USER|PASSWORD)=' .env > "$ENVF" || true
RESEAU="${DEMO_RESEAU:-$(sed -n 's/^DEMO_RESEAU=//p' .env | tail -1)}"
docker run --rm --network "${RESEAU:-host}" --env-file "$ENVF" -e DEMO_LIVRAISON="$(cat shared/DELIVERY_NUMBER)" \
  -v "$SORTIE:/sortie" --user "$(id -u):$(id -g)" si-demo "$@"
