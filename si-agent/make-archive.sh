#!/bin/bash
# Archive de déploiement de l'agent (livraison #430) :
#   si-agent/make-archive.sh [dossier de sortie]  ->  si-agent-agent-<version>.tar.gz
# Contenu : si_agent/ (le paquet), plugins/, install.sh + systemd/ (variante
# service), docker/ (variante conteneur), windows/ (Windows 10/11, #440), macos/ (macOS, #451),
# README-DEPLOIEMENT.md. Sans
# secret, sans fichier de configuration : tout vient de la ligne de commande.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="${1:-$HERE}"
VERSION="$(python3 -c "import re,sys; print(re.search(r'__version__ = \"([^\"]+)\"', open(sys.argv[1]).read()).group(1))" "$HERE/agent/si_agent/__init__.py")"
NAME="si-agent-agent-$VERSION"
TMP="$(mktemp -d)"
mkdir -p "$TMP/$NAME"
cp -r "$HERE/agent/si_agent" "$HERE/agent/plugins" "$HERE/agent/systemd" "$HERE/agent/docker" "$HERE/agent/windows" "$HERE/agent/macos" "$TMP/$NAME/"
cp "$HERE/agent/install.sh" "$HERE/agent/install-macos.sh" "$HERE/agent/uninstall-macos.sh" "$HERE/agent/README-DEPLOIEMENT.md" "$TMP/$NAME/"
find "$TMP/$NAME" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
chmod 755 "$TMP/$NAME/install.sh" "$TMP/$NAME/install-macos.sh" "$TMP/$NAME/uninstall-macos.sh" "$TMP/$NAME/docker/deploy-docker.sh" "$TMP/$NAME/docker/entrypoint.sh"
mkdir -p "$OUT"
tar -C "$TMP" -czf "$OUT/$NAME.tar.gz" "$NAME"
rm -rf "$TMP"
echo "$OUT/$NAME.tar.gz"
sha256sum "$OUT/$NAME.tar.gz" | cut -d' ' -f1
