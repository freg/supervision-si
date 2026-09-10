#!/bin/bash
# Installation de si-agent sur macOS 12+ (livraison #451). Python 3 du
# système (Command Line Tools), aucune dépendance. À lancer en admin :
#
#   sudo ./install-macos.sh --agent mac-01 --secret '...' --central https://VM:6443/api/si-agent \
#        [--site siege] [--ca /chemin/ca.crt | --ca-fingerprint sha256hex | --insecure] \
#        [--enable-plugin ID] [--plugins-user nobody] [--log-level DEBUG]
#        [--central-fallback https://hub.exemple.fr/api/si-agent]   # #474 : secours par le nom public
#                                                                  # (frontal, certificat public : magasin système)
#
# Même contrat que install.sh (Linux) : TLS par empreinte (--ca-fingerprint,
# amorçage GET /ca vérifié SHA-256), --ca pour un certificat fourni,
# --insecure pour le dépannage. Copie le paquet dans /usr/local/opt/si-agent,
# les plugins dans /usr/local/var/lib/si-agent/plugins (désactivés), écrit
# /usr/local/etc/si-agent/agent.json (mode 600), installe et charge le
# LaunchDaemon fr.exemple.si-agent (compte root, au démarrage, relancé).
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
OPT="/usr/local/opt/si-agent"; ETC="/usr/local/etc/si-agent"; VAR="/usr/local/var/lib/si-agent"; VARLOG="/usr/local/var/log"
PLIST="/Library/LaunchDaemons/fr.exemple.si-agent.plist"; LABEL="fr.exemple.si-agent"
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
[ -n "$AGENT" ] && [ -n "$SECRET" ] && [ -n "$CENTRAL" ] || { echo "usage : sudo ./install-macos.sh --agent ID --secret SECRET --central URL [--central-fallback URL_PUBLIQUE] [--site S] [--ca CRT|--ca-fingerprint HEX|--insecure] [--enable-plugin ID] [--plugins-user U] [--log-level L]" >&2; exit 2; }
[ "$(id -u)" = "0" ] || { echo "à lancer avec sudo (LaunchDaemon système)" >&2; exit 1; }
PY="$(command -v python3 || true)"
[ -n "$PY" ] || { echo "python3 introuvable : installer les outils en ligne de commande (xcode-select --install) puis relancer" >&2; exit 1; }
case "$CENTRAL" in https://*) ;; http://127.*|http://localhost*) ;; *) echo "AVERTISSEMENT : central en HTTP clair ($CENTRAL) -- réservé au test" >&2;; esac

mkdir -p "$ETC" "$VAR/plugins" "$VARLOG"
if [ -n "$CAFP" ]; then
  "$PY" - "$CENTRAL" "$CAFP" "$ETC/central-ca.crt" <<'PY' || exit 1
import hashlib, ssl, sys, urllib.request
central, expected, dest = sys.argv[1].rstrip("/"), sys.argv[2].lower().replace("sha256:", "").replace(":", ""), sys.argv[3]
ctx = ssl._create_unverified_context()  # amorçage : CA pas encore connue -- l'empreinte fait foi
with urllib.request.urlopen(central + "/ca", timeout=15, context=ctx) as r:
    pem = r.read()
got = hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem.decode("utf-8"))).hexdigest()
if got != expected:
    print("EMPREINTE DE LA CA DIFFÉRENTE : reçue %s, attendue %s -- installation refusée" % (got, expected), file=sys.stderr)
    sys.exit(1)
open(dest, "wb").write(pem)
print("CA du central vérifiée (%s) et installée" % got[:16])
PY
fi
[ -n "$CA" ] && install -m 644 "$CA" "$ETC/central-ca.crt"

rm -rf "$OPT/si_agent"; mkdir -p "$OPT"
cp -r "$HERE/si_agent" "$OPT/"
find "$OPT" -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null || true
# Plugins livrés : copiés s'ils sont présents dans l'archive (un gabarit
# d'archive minimal peut ne pas contenir plugins/ -- ne pas en mourir,
# l'agent fonctionne sans plugin et le central peut en pousser d'autres).
if [ -d "$HERE/plugins" ]; then
  for d in "$HERE"/plugins/*/; do
    [ -e "$d" ] || continue   # glob non résolu : plugins/ vide
    id="$(basename "$d")"
    [ -d "$VAR/plugins/$id" ] || cp -r "$d" "$VAR/plugins/$id"
  done
else
  echo "note : dossier plugins/ absent de l'archive -- installation poursuivie sans plugin livré" >&2
fi
chmod 750 "$VAR"/plugins/*/*.sh "$VAR"/plugins/*/*.py 2>/dev/null || true

SI_AGENT_FALLBACK="$FALLBACK" "$PY" - "$AGENT" "$SECRET" "$CENTRAL" "$SITE" "$INSECURE" "$PLUGINS_USER" "$LOG_LEVEL" "$ETC" "$VAR" "${ENABLE[@]:-}" <<'PY'
import json, os, sys
agent, secret, central, site, insecure, plugins_user, log_level, etc, var = sys.argv[1:10]
enable = [e for e in sys.argv[10:] if e]
cfg = {"agent_id": agent, "secret": secret, "central_url": central, "site": site,
       "insecure": insecure == "true", "plugins": {e: {"enabled": True} for e in enable},
       "plugins_user": plugins_user, "log_level": log_level,
       "queue_path": os.path.join(var, "queue.db"), "plugins_dir": os.path.join(var, "plugins"),
       "state_path": os.path.join(var, "state.json"), "block_file": os.path.join(etc, "BLOCKED"),
       "log_file": os.path.join("/usr/local/var/log", "si-agent.log")}
if os.path.exists(os.path.join(etc, "central-ca.crt")):
    cfg["ca_file"] = os.path.join(etc, "central-ca.crt")
if os.environ.get("SI_AGENT_FALLBACK"):   # #474 : central de secours, vérifié par le magasin système
    cfg["central_fallback_url"] = os.environ["SI_AGENT_FALLBACK"].rstrip("/")
with open(os.path.join(etc, "agent.json"), "w") as fh:
    json.dump(cfg, fh, indent=2)
PY
chmod 600 "$ETC/agent.json"

# LaunchDaemon : réécriture des chemins du gabarit
sed -e "s|__PYTHON__|$PY|g" -e "s|__OPT__|$OPT|g" -e "s|__ETC__|$ETC|g" -e "s|__VARLOG__|$VARLOG|g" \
    "$HERE/macos/fr.exemple.si-agent.plist" > "$PLIST"
chown root:wheel "$PLIST"; chmod 644 "$PLIST"
launchctl bootout system "$PLIST" 2>/dev/null || launchctl unload "$PLIST" 2>/dev/null || true
launchctl bootstrap system "$PLIST" 2>/dev/null || launchctl load -w "$PLIST"
launchctl enable "system/$LABEL" 2>/dev/null || true
echo "si-agent installé et démarré (LaunchDaemon $LABEL)"
echo "état  : sudo launchctl print system/$LABEL | head ; traces : tail -f $VARLOG/si-agent.log"
echo "statut: sudo PYTHONPATH=$OPT $PY -m si_agent.agent --config $ETC/agent.json --status"
echo "blocage d'urgence : sudo touch $ETC/BLOCKED"
