#!/bin/bash
# Copie les modules PARTAGÉS depuis leur source canonique (netprobe/agent)
# -- protocole HMAC et file locale -- jamais une seconde implémentation.
# À relancer après toute modification côté netprobe ; le test
# tests/test_shared_copy.py échoue si les copies divergent.
set -e
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/../../netprobe/agent/netprobe_agent"
cp "$SRC/protocol.py" "$HERE/si_agent/protocol.py"
cp "$SRC/localqueue.py" "$HERE/si_agent/localqueue.py"
echo "copies à jour depuis $SRC"
