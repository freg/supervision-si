#!/usr/bin/env bash
# #774 : installe / met à jour l'agent si-agent sur des hôtes Proxmox, depuis un poste Linux (la maison), par SSH.
# Sur chaque hôte : archive de l'agent téléchargée depuis LE CENTRAL de l'hôte (central_url de /etc/si-agent/agent.json,
# CA du projet si présente), ./install.sh --upgrade (configuration, secret et sondes conservés), sondes « migration » et
# « node-activity » activées, service relancé ; affiche la version et l'état. Rien d'autre n'est modifié.
#
#   ./agent-ssh.sh [-J saut] [-p plugin]... root@hote [root@hote2 ...]
#   ./agent-ssh.sh root@pve10 root@pve11                  # les deux nœuds du LAN
#   ./agent-ssh.sh -J moi@passerelle root@pve11           # via une machine de rebond
# Code de sortie : 0 si tous les hôtes sont à jour et l'agent actif, sinon le nombre d'hôtes en échec.
set -uo pipefail
JUMP=() PLUGINS=(migration node-activity) HOSTS=()
while [ $# -gt 0 ]; do
  case "$1" in
    -J) JUMP=(-J "$2"); shift 2;;
    -p) PLUGINS+=("$2"); shift 2;;
    -h|--help) sed -n 2,10p "$0"; exit 0;;
    -*) echo "option inconnue : $1" >&2; exit 2;;
    *) HOSTS+=("$1"); shift;;
  esac
done
[ ${#HOSTS[@]} -gt 0 ] || { sed -n 7,9p "$0"; exit 2; }

REMOTE='set -uo pipefail
PLUGINS="$1"
fail() { echo "ÉCHEC : $*"; exit 1; }
[ "$(id -u)" = 0 ] || fail "il faut se connecter en root"
[ -f /etc/si-agent/agent.json ] || fail "agent absent (/etc/si-agent/agent.json) : faire une installation complète depuis le hub (Agents hôtes › Déploiement)"
read -r CENTRAL CA INSECURE < <(python3 -c "import json;c=json.load(open(\"/etc/si-agent/agent.json\"));print(c[\"central_url\"], c.get(\"ca_file\") or \"-\", \"1\" if c.get(\"insecure\") else \"0\")")
OPT=(-fsS --retry 3 --max-time 300)
[ "$CA" != "-" ] && [ -f "$CA" ] && OPT+=(--cacert "$CA")
[ "$INSECURE" = 1 ] && OPT+=(-k)
before=$(python3 -c "import sys;sys.path.insert(0,\"/opt/si-agent\");import si_agent;print(si_agent.__version__)" 2>/dev/null || echo "?")
echo "central : $CENTRAL · version installée : $before"
T=$(mktemp -d /tmp/si-agent-up.XXXXXX)
curl "${OPT[@]}" -o "$T/agent.tar.gz" "$CENTRAL/package" || fail "téléchargement de $CENTRAL/package impossible (central joignable ? certificat ?)"
tar -C "$T" -xzf "$T/agent.tar.gz" || fail "archive illisible"
D=$(ls -d "$T"/si-agent-agent-*/ 2>/dev/null | head -1)
[ -n "$D" ] && [ -x "$D/install.sh" ] || fail "install.sh absent de l archive"
echo "archive : $(basename "$D")"
(cd "$D" && ./install.sh --upgrade) > "$T/install.log" 2>&1 || { tail -20 "$T/install.log"; fail "install.sh --upgrade a échoué (journal : $T/install.log)"; }
python3 - $PLUGINS <<PY || fail "activation des sondes impossible"
import json, sys
p = "/etc/si-agent/agent.json"
c = json.load(open(p))
pl = c.setdefault("plugins", {})
for i in sys.argv[1:]:
    pl.setdefault(i, {})["enabled"] = True
json.dump(c, open(p + ".tmp", "w"), indent=2)
import os; os.chmod(p + ".tmp", 0o600); os.replace(p + ".tmp", p)
print("sondes activées : " + ", ".join(sys.argv[1:]))
PY
for i in $PLUGINS; do [ -d "/var/lib/si-agent/plugins/$i" ] || echo "ATTENTION : sonde $i absente de /var/lib/si-agent/plugins (archive trop ancienne ?)"; done
mkdir -p /var/lib/si-agent/migration
systemctl restart si-agent; sleep 4
after=$(python3 -c "import sys;sys.path.insert(0,\"/opt/si-agent\");import si_agent;print(si_agent.__version__)" 2>/dev/null || echo "?")
st=$(systemctl is-active si-agent)
echo "version : $before -> $after · service : $st"
rm -rf "$T"
[ "$st" = active ] || { journalctl -u si-agent -n 15 --no-pager; fail "service si-agent inactif"; }
echo "OK"'

bad=0
for h in "${HOSTS[@]}"; do
  echo "===== $h"
  if ssh "${JUMP[@]}" -o ConnectTimeout=15 -o StrictHostKeyChecking=accept-new "$h" bash -s -- "'${PLUGINS[*]}'" <<<"$REMOTE"; then
    :
  else
    echo "===== $h : ÉCHEC (voir ci-dessus)"; bad=$((bad + 1))
  fi
done
echo "===== $(( ${#HOSTS[@]} - bad )) / ${#HOSTS[@]} hôte(s) à jour"
exit $bad
