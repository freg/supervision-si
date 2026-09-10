#!/bin/bash
# Installation de si-agent sur un hôte Linux (Debian/Ubuntu/Raspberry Pi OS,
# Python 3 système, aucune dépendance). Livraison #420.
#
#   sudo ./install.sh --agent srv-01 --secret '...' --central https://VM:6443/api/si-agent \
#        [--site siege] [--ca /chemin/ca.crt | --ca-fingerprint sha256hex | --insecure] \
#        [--enable-plugin network-neighbors] [--plugins-user nobody] [--log-level DEBUG]
#
# TLS (#422) : `--ca` installe un certificat d'autorité fourni ; `--ca-fingerprint`
# le RÉCUPÈRE du central (GET /ca, sans vérification à ce seul moment) et ne
# l'accepte que si son empreinte SHA-256 est celle affichée dans la tuile
# (amorçage sûr sans copier de fichier) ; `--insecure` n'est qu'un mode de
# dépannage, signalé au central par un événement à chaque démarrage.
#
# Copie le paquet dans /opt/si-agent, les plugins livrés dans
# /var/lib/si-agent/plugins (désactivés), écrit /etc/si-agent/agent.json
# (mode 600), installe et démarre le service systemd.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
AGENT="" SECRET="" CENTRAL="" FALLBACK="" SITE="default" CA="" CAFP="" INSECURE="false" ENABLE=() PLUGINS_USER="nobody" LOG_LEVEL="INFO"
while [ $# -gt 0 ]; do
  case "$1" in
    --agent) AGENT="$2"; shift 2;;
    --secret) SECRET="$2"; shift 2;;
    --central) CENTRAL="$2"; shift 2;;
    --central-fallback) FALLBACK="$2"; shift 2;;   # #474 : central de secours (nom public, cert public -> magasin système)
    --site) SITE="$2"; shift 2;;
    --ca) CA="$2"; shift 2;;
    --ca-fingerprint) CAFP="$2"; shift 2;;
    --insecure) INSECURE="true"; shift;;
    --enable-plugin) ENABLE+=("$2"); shift 2;;
    --plugins-user) PLUGINS_USER="$2"; shift 2;;
    --log-level) LOG_LEVEL="$2"; shift 2;;
    *) echo "argument inconnu : $1" >&2; exit 2;;
  esac
done
[ -n "$AGENT" ] && [ -n "$SECRET" ] && [ -n "$CENTRAL" ] || { echo "usage : --agent ID --secret SECRET --central URL [--site S] [--ca CRT|--ca-fingerprint HEX|--insecure] [--enable-plugin ID] [--plugins-user U] [--log-level L]" >&2; exit 2; }
command -v python3 >/dev/null || { echo "python3 requis" >&2; exit 1; }
case "$CENTRAL" in https://*) ;; http://127.*|http://localhost*) ;; *) echo "AVERTISSEMENT : central en HTTP clair ($CENTRAL) -- réservé au test" >&2;; esac
if [ -n "$CAFP" ]; then
  install -d /etc/si-agent
  python3 - "$CENTRAL" "$CAFP" <<'PY' || exit 1
import hashlib, ssl, sys, urllib.request
central, expected = sys.argv[1].rstrip("/"), sys.argv[2].lower().replace("sha256:", "").replace(":", "")
ctx = ssl._create_unverified_context()  # amorçage : on ne connaît pas encore la CA -- l'empreinte fait foi
with urllib.request.urlopen(central + "/ca", timeout=15, context=ctx) as r:
    pem = r.read()
der = ssl.PEM_cert_to_DER_cert(pem.decode("utf-8"))
got = hashlib.sha256(der).hexdigest()
if got != expected:
    print("EMPREINTE DE LA CA DIFFÉRENTE : reçue %s, attendue %s -- installation refusée" % (got, expected), file=sys.stderr)
    sys.exit(1)
open("/etc/si-agent/central-ca.crt", "wb").write(pem)
print("CA du central vérifiée (%s) et installée" % got[:16])
PY
fi

install -d /opt/si-agent /etc/si-agent /var/lib/si-agent/plugins
rm -rf /opt/si-agent/si_agent
cp -r "$HERE/si_agent" /opt/si-agent/
find /opt/si-agent -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
# Plugins livrés : copiés s'ils sont présents dans l'archive (un gabarit
# d'archive minimal peut ne pas contenir plugins/ -- ne pas en mourir,
# l'agent fonctionne sans plugin et le central peut en pousser d'autres).
if [ -d "$HERE/plugins" ]; then
  for d in "$HERE"/plugins/*/; do
    [ -e "$d" ] || continue   # glob non résolu : plugins/ vide
    id="$(basename "$d")"
    [ -d "/var/lib/si-agent/plugins/$id" ] || cp -r "$d" "/var/lib/si-agent/plugins/$id"
  done
else
  echo "note : dossier plugins/ absent de l'archive -- installation poursuivie sans plugin livré" >&2
fi
chmod 750 /var/lib/si-agent/plugins/*/*.sh /var/lib/si-agent/plugins/*/*.py 2>/dev/null || true
if [ -n "$CA" ]; then install -m 644 "$CA" /etc/si-agent/central-ca.crt; fi

SI_AGENT_FALLBACK="$FALLBACK" python3 - "$AGENT" "$SECRET" "$CENTRAL" "$SITE" "$INSECURE" "$PLUGINS_USER" "$LOG_LEVEL" "${ENABLE[@]:-}" <<'PY'
import json, sys
agent, secret, central, site, insecure, plugins_user, log_level = sys.argv[1:8]
enable = [e for e in sys.argv[8:] if e]
import os
cfg = {"agent_id": agent, "secret": secret, "central_url": central, "site": site,
       "insecure": insecure == "true", "plugins": {e: {"enabled": True} for e in enable},
       "plugins_user": plugins_user, "log_level": log_level,
       "state_path": "/var/lib/si-agent/state.json", "block_file": "/etc/si-agent/BLOCKED"}
if os.path.exists("/etc/si-agent/central-ca.crt"):
    cfg["ca_file"] = "/etc/si-agent/central-ca.crt"
if os.environ.get("SI_AGENT_FALLBACK"):   # #474 : central de secours, vérifié par le magasin système
    cfg["central_fallback_url"] = os.environ["SI_AGENT_FALLBACK"].rstrip("/")
with open("/etc/si-agent/agent.json", "w") as fh:
    json.dump(cfg, fh, indent=2)
PY
chmod 600 /etc/si-agent/agent.json
install -m 644 "$HERE/systemd/si-agent.service" /etc/systemd/system/si-agent.service
systemctl daemon-reload
systemctl enable --now si-agent.service
echo "si-agent installé : systemctl status si-agent ; PYTHONPATH=/opt/si-agent python3 -m si_agent.agent --status"
echo "blocage local d'urgence : touch /etc/si-agent/BLOCKED (ou --block) ; traces : journalctl -u si-agent -f"
