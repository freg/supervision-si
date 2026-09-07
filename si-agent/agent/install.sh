#!/bin/bash
# Installation de si-agent sur un hôte Linux (Debian/Ubuntu/Raspberry Pi OS,
# Python 3 système, aucune dépendance). Livraison #420.
#
#   sudo ./install.sh --agent srv-01 --secret '...' --central https://VM:6443/api/si-agent \
#        [--site siege] [--ca /chemin/ca.crt | --insecure] [--enable-plugin network-neighbors]
#
# Copie le paquet dans /opt/si-agent, les plugins livrés dans
# /var/lib/si-agent/plugins (désactivés), écrit /etc/si-agent/agent.json
# (mode 600), installe et démarre le service systemd.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
AGENT="" SECRET="" CENTRAL="" SITE="default" CA="" INSECURE="false" ENABLE=()
while [ $# -gt 0 ]; do
  case "$1" in
    --agent) AGENT="$2"; shift 2;;
    --secret) SECRET="$2"; shift 2;;
    --central) CENTRAL="$2"; shift 2;;
    --site) SITE="$2"; shift 2;;
    --ca) CA="$2"; shift 2;;
    --insecure) INSECURE="true"; shift;;
    --enable-plugin) ENABLE+=("$2"); shift 2;;
    *) echo "argument inconnu : $1" >&2; exit 2;;
  esac
done
[ -n "$AGENT" ] && [ -n "$SECRET" ] && [ -n "$CENTRAL" ] || { echo "usage : --agent ID --secret SECRET --central URL [--site S] [--ca CRT|--insecure] [--enable-plugin ID]" >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 requis" >&2; exit 1; }

install -d /opt/si-agent /etc/si-agent /var/lib/si-agent/plugins
rm -rf /opt/si-agent/si_agent
cp -r "$HERE/si_agent" /opt/si-agent/
find /opt/si-agent -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
for d in "$HERE"/plugins/*/; do
  id="$(basename "$d")"
  [ -d "/var/lib/si-agent/plugins/$id" ] || cp -r "$d" "/var/lib/si-agent/plugins/$id"
done
chmod 750 /var/lib/si-agent/plugins/*/*.sh /var/lib/si-agent/plugins/*/*.py 2>/dev/null || true
if [ -n "$CA" ]; then install -m 644 "$CA" /etc/si-agent/central-ca.crt; fi

python3 - "$AGENT" "$SECRET" "$CENTRAL" "$SITE" "$INSECURE" "${ENABLE[@]:-}" <<'PY'
import json, sys
agent, secret, central, site, insecure = sys.argv[1:6]
enable = [e for e in sys.argv[6:] if e]
import os
cfg = {"agent_id": agent, "secret": secret, "central_url": central, "site": site,
       "insecure": insecure == "true", "plugins": {e: {"enabled": True} for e in enable}}
if os.path.exists("/etc/si-agent/central-ca.crt"):
    cfg["ca_file"] = "/etc/si-agent/central-ca.crt"
with open("/etc/si-agent/agent.json", "w") as fh:
    json.dump(cfg, fh, indent=2)
PY
chmod 600 /etc/si-agent/agent.json
install -m 644 "$HERE/systemd/si-agent.service" /etc/systemd/system/si-agent.service
systemctl daemon-reload
systemctl enable --now si-agent.service
echo "si-agent installé : systemctl status si-agent ; PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --status"
