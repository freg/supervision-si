#!/bin/bash
# Installation de si-agent sur un hôte Linux (Debian/Ubuntu/Raspberry Pi OS,
# Python 3 système, aucune dépendance). Livraison #420.
#
#   sudo ./install.sh --agent srv-01 --secret '...' --central https://VM:6443/api/si-agent \
#        [--site siege] [--ca /chemin/ca.crt | --ca-fingerprint sha256hex | --insecure] \
#        [--enable-plugin network-neighbors] [--plugins-user nobody] [--log-level DEBUG] [--no-detect]
#        [--python /opt/pyagent/python/bin/python3]   # interpréteur d'EXÉCUTION de l'agent
#
# Python : l'agent requiert Python >= 3.7. Sur un hôte trop ancien (Debian 9 /
# PVE 5 = 3.5), installer un Python autonome (aucun changement système) et le
# passer via --python -- voir docs/agent-python-autonome.md. À défaut, l'install
# REFUSE proprement (plutôt qu'un service qui boucle en crash au démarrage).
#
# Détection (#524) : sur un hôte Proxmox VE (/etc/pve présent et `pvesh`
# disponible) le plugin `proxmox` est activé et les sondes tournent en root
# (pvesh/qm/zpool l'exigent) sans rien ajouter à la ligne du hub ;
# `--plugins-user` explicite l'emporte, `--no-detect` désactive la détection.
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
AGENT="" SECRET="" CENTRAL="" FALLBACK="" SITE="default" CA="" CAFP="" INSECURE="false" ENABLE=() PLUGINS_USER="" LOG_LEVEL="INFO" UPGRADE="false" DETECT="true"
PYAGENT="python3"   # #645 : interpréteur d'exécution de l'agent (peut différer du python3 système)
while [ $# -gt 0 ]; do
  case "$1" in
    --upgrade) UPGRADE="true"; shift;;   # #522 : code et service seulement, configuration/secret/CA/sondes conservés
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
    --no-detect) DETECT="false"; shift;;   # #524 : pas d'activation automatique selon l'hôte
    --python) PYAGENT="$2"; shift 2;;   # #645 : Python >= 3.7 pour faire tourner l'agent (hôte ancien = Python autonome)
    *) echo "argument inconnu : $1" >&2; exit 2;;
  esac
done
# #645 : garde-fou Python -- l'agent tourne sous PYAGENT (>= 3.7). Vérifié AVANT
# tout enrôlement, pour ne jamais laisser un hôte trop ancien s'enrôler puis
# boucler en crash. Les petits scripts d'amorçage ci-dessous (enrôlement, CA)
# restent sous le python3 système : ils sont volontairement compatibles 3.5.
PYAGENT="${SI_AGENT_PYTHON:-$PYAGENT}"
# #685 : une mise à jour (lancée par l'agent, sans --python ni SI_AGENT_PYTHON) garde l'interpréteur du
# service en place -- sinon un hôte en Python autonome (Debian 9) retombait sur le python3 système 3.5 et
# l'installeur s'arrêtait avant de relancer l'agent (« l'installeur n'a pas relancé l'agent »).
if [ "$UPGRADE" = "true" ] && [ "$PYAGENT" = "python3" ] && [ -f /etc/systemd/system/si-agent.service ]; then
  CUR_PY="$(sed -n 's#^ExecStart=\([^ ]*\).*#\1#p' /etc/systemd/system/si-agent.service | head -n 1)"
  [ -n "$CUR_PY" ] && [ -x "$CUR_PY" ] && PYAGENT="$CUR_PY"
fi
PYAGENT_ABS="$(command -v "$PYAGENT" 2>/dev/null || true)"
[ -n "$PYAGENT_ABS" ] || { [ -x "$PYAGENT" ] && PYAGENT_ABS="$PYAGENT"; }
[ -n "$PYAGENT_ABS" ] || { echo "interpréteur Python introuvable : $PYAGENT (voir --python)" >&2; exit 1; }
if ! "$PYAGENT_ABS" -c 'import sys; raise SystemExit(0 if sys.version_info[:2] >= (3, 7) else 1)' 2>/dev/null; then
  ver="$("$PYAGENT_ABS" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null || echo "?")"
  {
    echo "ERREUR : si-agent requiert Python >= 3.7, or $PYAGENT_ABS est en $ver."
    echo "  Hôte trop ancien (ex. Debian 9 / Proxmox VE 5 = Python 3.5)."
    echo "  Installe un Python AUTONOME (aucun changement système) puis relance avec --python :"
    echo "    curl -LsSf https://astral.sh/uv/install.sh | sh"
    echo "    ~/.local/bin/uv python install 3.11"
    echo '    sudo ./install.sh --python "$(~/.local/bin/uv python find 3.11)" <mêmes options>'
    echo "  Détails et variante sans uv : docs/agent-python-autonome.md"
  } >&2
  exit 1
fi

# #616 : enrôlement par jeton de site (SI_AGENT_ENROLL_TOKEN + SI_AGENT_CENTRAL, posés par le script d'amorçage
# GET /deploy/linux?token=) -- l'agent est nommé d'après la machine, le secret est délivré ici.
if [ "$UPGRADE" != "true" ] && [ -n "${SI_AGENT_ENROLL_TOKEN:-}" ]; then
  CENTRAL="${SI_AGENT_CENTRAL:-$CENTRAL}"; [ -n "${SI_AGENT_SITE:-}" ] && SITE="$SI_AGENT_SITE"
  [ -n "${SI_AGENT_CA_SHA256:-}" ] && CAFP="$SI_AGENT_CA_SHA256"
  for p in ${SI_AGENT_PLUGINS:-}; do ENABLE+=("$p"); done
  [ -n "$CENTRAL" ] || { echo "SI_AGENT_CENTRAL requis avec SI_AGENT_ENROLL_TOKEN" >&2; exit 2; }
  ENROLL=$(python3 - "$CENTRAL" "$SI_AGENT_ENROLL_TOKEN" "$(hostname)" <<'PY'
import json, ssl, sys, urllib.request
central, token, host = sys.argv[1:4]
ctx = ssl._create_unverified_context() if not central.startswith("https://") or __import__("re").match(r"^https://(\d{1,3}\.){3}\d{1,3}", central) else None
req = urllib.request.Request(central.rstrip("/") + "/api/v1/enroll", data=json.dumps({"token": token, "hostname": host, "platform": "linux"}).encode(), headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
        d = json.load(r)
except Exception as exc:  # noqa: BLE001
    print("enrôlement refusé : %s" % exc, file=sys.stderr); sys.exit(1)
print(d["agent_id"]); print(d["secret"]); print(d.get("site") or "")
PY
) || exit 1
  AGENT=$(echo "$ENROLL" | sed -n 1p); SECRET=$(echo "$ENROLL" | sed -n 2p); S=$(echo "$ENROLL" | sed -n 3p); [ -n "$S" ] && SITE="$S"
  echo "enrôlé comme « $AGENT » (site $SITE)"
fi
if [ "$UPGRADE" = "true" ]; then
  [ -f /etc/si-agent/agent.json ] || { echo "--upgrade : /etc/si-agent/agent.json absent, faire une installation complète" >&2; exit 2; }
else
  [ -n "$AGENT" ] && [ -n "$SECRET" ] && [ -n "$CENTRAL" ] || { echo "usage : --agent ID --secret SECRET --central URL [--site S] [--ca CRT|--ca-fingerprint HEX|--insecure] [--enable-plugin ID] [--plugins-user U] [--log-level L] | --upgrade" >&2; exit 2; }
fi
command -v python3 >/dev/null || { echo "python3 requis" >&2; exit 1; }
# #524 : hôte Proxmox VE -> plugin proxmox + sondes en root (sauf choix explicite).
if [ "$UPGRADE" != "true" ] && [ "$DETECT" = "true" ] && [ -d /etc/pve ] && command -v pvesh >/dev/null; then
  case " ${ENABLE[*]:-} " in *" proxmox "*) ;; *) ENABLE+=("proxmox");; esac
  [ -n "$PLUGINS_USER" ] || PLUGINS_USER="root"
  echo "hôte Proxmox VE détecté : plugin proxmox activé, sondes exécutées en $PLUGINS_USER (--no-detect pour l'éviter)"
fi
[ -n "$PLUGINS_USER" ] || PLUGINS_USER="nobody"
case "$CENTRAL" in https://*|"") ;; http://127.*|http://localhost*) ;; *) echo "AVERTISSEMENT : central en HTTP clair ($CENTRAL) -- réservé au test" >&2;; esac
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

[ "$UPGRADE" = "true" ] || SI_AGENT_FALLBACK="$FALLBACK" python3 - "$AGENT" "$SECRET" "$CENTRAL" "$SITE" "$INSECURE" "$PLUGINS_USER" "$LOG_LEVEL" "${ENABLE[@]:-}" <<'PY'
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
# #645 : ExecStart pointe sur l'interpréteur choisi (défaut python3 système)
sed -i "s#^ExecStart=[^ ]*#ExecStart=$PYAGENT_ABS#" /etc/systemd/system/si-agent.service
# #685 : interpréteur sous /root ou /home (uv python install) -- ProtectHome=true le rendrait invisible au service
case "$PYAGENT_ABS" in
  /root/*|/home/*) sed -i "s#^ProtectHome=true#ProtectHome=read-only#" /etc/systemd/system/si-agent.service
                   echo "note : $PYAGENT_ABS est sous un dossier personnel -> ProtectHome=read-only";;
esac
systemctl daemon-reload
systemctl enable si-agent.service
# #524 : toujours (re)démarrer -- `enable --now` laissait tourner un ancien
# process avec l'ancienne configuration lors d'une réinstallation (vu sur
# deux hyperviseurs : agent démarré sous le mauvais identifiant / sans CA).
systemctl restart si-agent.service
echo "si-agent installé ($PYAGENT_ABS) : systemctl status si-agent ; PYTHONPATH=/opt/si-agent $PYAGENT_ABS -m si_agent.agent --status"
echo "blocage local d'urgence : touch /etc/si-agent/BLOCKED (ou --block) ; traces : journalctl -u si-agent -f"
