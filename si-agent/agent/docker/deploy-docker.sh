#!/bin/bash
# Déploiement de si-agent EN CONTENEUR sur un hôte qui a Docker (livraison #430).
#
#   sudo ./docker/deploy-docker.sh --agent srv-01 --secret '...' --central https://VM:6443/api/si-agent \
#        [--site siege] [--ca /chemin/ca.crt | --ca-fingerprint sha256hex | --insecure] \
#        [--enable-plugin network-neighbors] [--log-level DEBUG] [--image si-agent:local] [--name si-agent]
#
# Mêmes options que install.sh (variante systemd). Ce script :
#   1. vérifie la CA du central par empreinte (ou installe --ca), comme install.sh ;
#   2. écrit /etc/si-agent/agent.json (mode 600) sur l'hôte ;
#   3. construit l'image sur place (python:3.12-slim + iproute2, procps, util-linux, journalctl) ;
#   4. lance le conteneur : --network host --pid host, / de l'hôte monté en lecture
#      seule sous /host, file et plugins persistants dans /var/lib/si-agent,
#      redémarrage automatique (unless-stopped), journal Docker limité.
#
# Ce que le conteneur VOIT de l'hôte : OS, noyau, CPU, mémoire, disques (montages
# sous /host), processus (--pid host), ports et connexions (--network host),
# voisins ARP et routes, journal (journalctl -D /host/var/log/journal), comptes
# (/host/etc/passwd), reboot-required, sessions (utmp/wtmp). Ce qu'il ne voit
# PAS sans systemd : les unités systemd en échec (« systemctl indisponible »
# dans la mesure, signalé en partial) -- la variante install.sh les voit.
#
# Relancer ce script met à jour l'image et le conteneur (config conservée).
set -euo pipefail
HERE="$(cd "$(dirname "$0")/.." && pwd)"
AGENT="" SECRET="" CENTRAL="" SITE="default" CA="" CAFP="" INSECURE="false" ENABLE=() LOG_LEVEL="INFO" IMAGE="si-agent:local" NAME="si-agent"
while [ $# -gt 0 ]; do
  case "$1" in
    --agent) AGENT="$2"; shift 2;;
    --secret) SECRET="$2"; shift 2;;
    --central) CENTRAL="$2"; shift 2;;
    --site) SITE="$2"; shift 2;;
    --ca) CA="$2"; shift 2;;
    --ca-fingerprint) CAFP="$2"; shift 2;;
    --insecure) INSECURE="true"; shift;;
    --enable-plugin) ENABLE+=("$2"); shift 2;;
    --log-level) LOG_LEVEL="$2"; shift 2;;
    --image) IMAGE="$2"; shift 2;;
    --name) NAME="$2"; shift 2;;
    --plugins-user) shift 2;;   # accepté pour compatibilité : en conteneur, nobody est déjà l'utilisateur des sondes
    *) echo "argument inconnu : $1" >&2; exit 2;;
  esac
done
if [ -z "$AGENT" ] || [ -z "$SECRET" ] || [ -z "$CENTRAL" ]; then
  if [ -f /etc/si-agent/agent.json ] && [ -z "$AGENT$SECRET$CENTRAL" ]; then
    echo "configuration existante conservée (/etc/si-agent/agent.json) -- mise à jour de l'image et du conteneur"
  else
    echo "usage : --agent ID --secret SECRET --central URL [--site S] [--ca CRT|--ca-fingerprint HEX|--insecure] [--enable-plugin ID] [--log-level L] [--image I] [--name N]" >&2
    exit 2
  fi
fi
command -v docker >/dev/null || { echo "docker requis (cette variante) -- sinon : sudo ./install.sh (systemd)" >&2; exit 1; }
[ "$(id -u)" = 0 ] || { echo "à lancer en root (sudo)" >&2; exit 1; }

install -d -m 755 /etc/si-agent /var/lib/si-agent/plugins
if [ -n "$CAFP" ]; then
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
if [ -n "$CA" ]; then install -m 644 "$CA" /etc/si-agent/central-ca.crt; fi
case "$CENTRAL" in ""|https://*|http://127.*|http://localhost*) ;; *) echo "AVERTISSEMENT : central en HTTP clair ($CENTRAL) -- réservé au test" >&2;; esac

if [ -n "$AGENT" ]; then
  python3 - "$AGENT" "$SECRET" "$CENTRAL" "$SITE" "$INSECURE" "$LOG_LEVEL" "${ENABLE[@]:-}" <<'PY'
import json, os, sys
agent, secret, central, site, insecure, log_level = sys.argv[1:7]
enable = [e for e in sys.argv[7:] if e]
cfg = {"agent_id": agent, "secret": secret, "central_url": central, "site": site,
       "insecure": insecure == "true", "plugins": {e: {"enabled": True} for e in enable},
       "plugins_user": "nobody", "log_level": log_level,
       "queue_path": "/var/lib/si-agent/queue.db", "plugins_dir": "/var/lib/si-agent/plugins",
       "state_path": "/var/lib/si-agent/state.json", "block_file": "/etc/si-agent/BLOCKED"}
if os.path.exists("/etc/si-agent/central-ca.crt"):
    cfg["ca_file"] = "/etc/si-agent/central-ca.crt"
with open("/etc/si-agent/agent.json", "w") as fh:
    json.dump(cfg, fh, indent=2)
PY
  chmod 600 /etc/si-agent/agent.json
fi

echo "construction de l'image $IMAGE…"
docker build -q -t "$IMAGE" -f "$HERE/docker/Dockerfile" "$HERE" >/dev/null
docker rm -f "$NAME" >/dev/null 2>&1 || true
EXTRA=()
[ -e /var/run/utmp ] && EXTRA+=(-v /var/run/utmp:/var/run/utmp:ro)          # sessions ouvertes (who)
[ -e /var/log/wtmp ] && EXTRA+=(-v /var/log/wtmp:/var/log/wtmp:ro)          # dernières connexions (last)
[ -S /run/dbus/system_bus_socket ] && EXTRA+=(-v /run/dbus/system_bus_socket:/run/dbus/system_bus_socket:ro)  # systemctl --failed via le bus de l'hôte (à confirmer)
[ -n "${DOCKER_SOCK:-}" ] && [ -S /var/run/docker.sock ] && EXTRA+=(-v /var/run/docker.sock:/var/run/docker.sock:ro)  # plugin docker-containers (DOCKER_SOCK=1)
docker run -d --name "$NAME" --restart unless-stopped \
  --network host --pid host \
  --log-opt max-size=10m --log-opt max-file=3 \
  -e SI_AGENT_HOST_ROOT=/host \
  -v /:/host:ro \
  -v /etc/si-agent:/etc/si-agent \
  -v /var/lib/si-agent:/var/lib/si-agent \
  ${EXTRA[@]+"${EXTRA[@]}"} \
  "$IMAGE" >/dev/null
sleep 2
docker ps --filter "name=$NAME" --format 'conteneur {{.Names}} : {{.Status}}'
echo "traces : docker logs -f $NAME ; état : docker exec $NAME python3 -m si_agent.agent --status"
echo "collecte à blanc : docker exec $NAME python3 -m si_agent.agent --collect | head -60"
echo "blocage local d'urgence : touch /etc/si-agent/BLOCKED ; arrêt : docker rm -f $NAME"
