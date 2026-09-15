#!/usr/bin/env bash
# Installeur interactif de supervision-si (livraisons #511, #513).
#
#   scripts/install.sh                     menu (whiptail si présent, sinon questions)
#   scripts/install.sh --answers FICHIER   sans interaction (rejouer une VM)
#   scripts/install.sh --resume            reprend la construction là où elle s'est arrêtée
#
# Profils :
#   light      standalone léger, un seul hôte : cohorte core + tuiles choisies (tests immédiats)
#   node       nœud du déploiement réparti (#513) : ce nœud lance, avec compose et un override
#              généré, les services des cohortes que deploy/nodes.json lui affecte, plus un
#              relais par service distant ; l'agent de nœud (deploy/node_agent.py) est installé
#              en service systemd et écoute sur le VPN. Même profil pour le manager (super :
#              core + passerelle), une VM secondaire LAN, le hub OVH (bordure : jumeau
#              tls-proxy) ou une VM secondaire OVH -- c'est nodes.json qui distingue.
#   super / lan / ovh-hub / ovh   alias de node (anciens noms, #511)
#
# Noyau commun : prérequis (Docker, python3+yaml, RAM/disque), .env complété par
# sync-env.py, PKI, puis construction PAR LOTS (LOT services à la fois, parallélisme
# limité) avec REPRISE : chaque image construite est notée dans
# deploy/generated/install.done ; une relance saute ce qui est déjà fait. C'est la
# réponse au « DeadlineExceeded » de BuildKit quand ~70 images partent d'un coup.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd); cd "$ROOT"
GEN="$ROOT/deploy/generated"; mkdir -p "$GEN"
DONE="$GEN/install.done"; LOG="$GEN/install.log"
ANSWERS=""; RESUME=0
[ "${SI_INSTALL_SOURCE_ONLY:-0}" = 1 ] && set -- 
LOT=${SI_INSTALL_LOT:-4}
DEFAULT_LIGHT_COHORTS="core,reseau,coffre,tickets"

load_env() {  # lit .env clé par clé (le fichier n'est pas sourçable : valeurs avec espaces non citées)
  local k v
  while IFS= read -r line; do
    k=${line%%=*}; v=${line#*=}
    [[ $k =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    v=${v%\"}; v=${v#\"}; v=${v%\'}; v=${v#\'}
    export "$k=$v"
  done < <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "${1:-.env}" 2>/dev/null || true)
}
log() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }
die() { log "ERREUR : $*"; exit 1; }

while [ $# -gt 0 ]; do
  case "$1" in
    --answers) ANSWERS=$2; shift 2 ;;
    --resume) RESUME=1; shift ;;
    -h|--help) sed -n 2,24p "$0"; exit 0 ;;
    *) die "option inconnue : $1" ;;
  esac
done

# --- réponses : fichier ou interaction -------------------------------------
ask() {  # ask CLÉ "question" "défaut"
  local key=$1 q=$2 def=${3:-} v
  if [ -n "$ANSWERS" ]; then
    v=$(grep -E "^$key=" "$ANSWERS" | tail -1 | cut -d= -f2- || true)
    [ -n "$v" ] || v=$def
  elif command -v whiptail >/dev/null; then
    v=$(whiptail --title "supervision-si" --inputbox "$q" 10 70 "$def" 3>&1 1>&2 2>&3) || exit 1
  else
    read -r -p "$q [$def] : " v; v=${v:-$def}
  fi
  printf '%s' "$v"
}
menu() {  # menu CLÉ "question" "défaut" item1 "desc1" item2 "desc2" …
  local key=$1 q=$2 def=$3; shift 3; local v
  if [ -n "$ANSWERS" ]; then
    v=$(grep -E "^$key=" "$ANSWERS" | tail -1 | cut -d= -f2- || true); [ -n "$v" ] || v=$def
  elif command -v whiptail >/dev/null; then
    v=$(whiptail --title "supervision-si" --menu "$q" 18 76 8 "$@" 3>&1 1>&2 2>&3) || exit 1
  else
    echo "$q"; local i=1; local -a items=("$@")
    while [ $i -lt ${#items[@]} ]; do echo "  ${items[$((i-1))]}  ${items[$i]}"; i=$((i+2)); done
    read -r -p "choix [$def] : " v; v=${v:-$def}
  fi
  printf '%s' "$v"
}

# --- prérequis --------------------------------------------------------------
preflight() {
  command -v docker >/dev/null || die "docker absent (https://docs.docker.com/engine/install/)"
  docker compose version >/dev/null 2>&1 || die "docker compose (plugin v2) absent"
  command -v python3 >/dev/null || die "python3 absent"
  python3 -c "import yaml" 2>/dev/null || die "PyYAML absent : apt install python3-yaml"

  local mem disk
  mem=$(awk '/MemTotal/{printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo 0)
  disk=$(df -Pm "$ROOT" | awk 'NR==2{print $4}')
  log "prérequis : RAM ${mem} Mo, disque libre ${disk} Mo, $(docker --version)"
  [ "$mem" -ge 3500 ] || log "AVERTISSEMENT : moins de 4 Go de RAM -- profil light conseillé, lots réduits"
  [ "$disk" -ge 15000 ] || log "AVERTISSEMENT : moins de 15 Go libres -- docker system prune conseillé"
  [ -f .env ] || cp .env.example .env
  python3 scripts/sync-env.py >>"$LOG" 2>&1 || log "sync-env.py : voir $LOG"
  load_env .env
}

# --- construction par lots avec reprise ---------------------------------------
build_batches() {  # build_batches "svc svc …"
  local todo=() s
  touch "$DONE"
  for s in $1; do grep -qx "$s" "$DONE" || todo+=("$s"); done
  log "à construire : ${#todo[@]} service(s) (déjà faits : $(wc -l < "$DONE"))"
  export COMPOSE_PARALLEL_LIMIT=${COMPOSE_PARALLEL_LIMIT:-2} DOCKER_CLIENT_TIMEOUT=600 COMPOSE_HTTP_TIMEOUT=600
  local i=0
  while [ $i -lt ${#todo[@]} ]; do
    local lot=("${todo[@]:$i:$LOT}")
    log "lot : ${lot[*]}"
    if docker compose build "${lot[@]}" >>"$LOG" 2>&1; then
      printf '%s\n' "${lot[@]}" >> "$DONE"
    else
      log "échec du lot (${lot[*]}) -- détail dans $LOG ; relancer avec --resume, le lot est retenté seul"
      # second essai service par service pour isoler le fautif
      for s in "${lot[@]}"; do
        if docker compose build "$s" >>"$LOG" 2>&1; then echo "$s" >> "$DONE"; else die "construction de $s impossible (voir $LOG)"; fi
      done
    fi
    i=$((i+LOT))
  done
}

gateway_up() {  # Keycloak / tls-proxy / annuaire de test : vivent dans gateway/
  log "passerelle (Keycloak, tls-proxy) : gateway/scripts/run.sh up -d --build"
  ./gateway/scripts/run.sh up -d --build >>"$LOG" 2>&1 || die "passerelle : voir $LOG"
}

status() {
  log "état :"; docker compose ps --format 'table {{.Name}}\t{{.Status}}' 2>/dev/null | tee -a "$LOG" | tail -n +1 | head -80
  local down; down=$(docker compose ps --format '{{.Name}} {{.Status}}' 2>/dev/null | grep -vi "up\|running" || true)
  [ -z "$down" ] || log "ATTENTION, pas démarrés : $down"
  log "hub : https://${HOST_IP:-localhost}:${GATEWAY_PORT:-6443}/"
}

# --- profils ----------------------------------------------------------------
profile_light() {
  local cohorts; cohorts=$(ask COHORTS "Cohortes à déployer (core toujours incluse) -- voir deploy/cohorts.json" "$DEFAULT_LIGHT_COHORTS")
  local services; services=$(python3 deploy/cohorts.py services "core,$cohorts" 2>>"$LOG" | tr '\n' ' ')
  log "profil light : cohortes $cohorts -> $(echo "$services" | wc -w) services"
  ./scripts/run.sh config -q >>"$LOG" 2>&1 || true   # run.sh recopie shared/, VERSION.json, realm ; sans démarrer
  gateway_up
  build_batches "$services"
  log "démarrage"; ./scripts/run.sh up -d $services >>"$LOG" 2>&1 || die "up : voir $LOG"
  status
}

node_common() {
  [ -f deploy/nodes.json ] || die "deploy/nodes.json absent (copier deploy/nodes.example.json et l'adapter, identique sur tous les nœuds)"
  command -v wg >/dev/null || log "wireguard-tools absent : apt install wireguard ; le VPN doit être monté AVANT (deploy/wg-mesh.sh)"
  local me; me=$(ask NODE_NAME "Nom de ce nœud dans deploy/nodes.json" "$(hostname -s)")
  WG_ADDR=$(python3 -c "import json,sys;print(next((n['wg_address'] for n in json.load(open('deploy/nodes.json'))['nodes'] if n['name']==sys.argv[1]),''))" "$me")
  [ -n "$WG_ADDR" ] || die "nœud $me inconnu dans deploy/nodes.json"
  ip -o addr 2>/dev/null | grep -q "$WG_ADDR" || die "l'adresse VPN $WG_ADDR n'est pas montée (wg-quick@wg0) -- voir deploy/wg-mesh.sh"
  echo "$me" > "$GEN/node.name"; NODE_NAME=$me
  if ! grep -qE '^SI_NODE_TOKEN=.+' .env; then
    local tok; tok=$(openssl rand -hex 24 2>/dev/null || head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')
    grep -q '^SI_NODE_TOKEN=' .env && sed -i "s#^SI_NODE_TOKEN=.*#SI_NODE_TOKEN=$tok#" .env || echo "SI_NODE_TOKEN=$tok" >> .env
    log "SI_NODE_TOKEN généré dans .env : recopier le MÊME .env sur les autres nœuds (jamais dans le dépôt)"
  fi
}

node_agent_install() {  # service systemd : deploy/node_agent.py serve (bibliothèque standard, sur l'hôte)
  if command -v systemctl >/dev/null && [ -d /etc/systemd/system ]; then
    cat > /etc/systemd/system/si-node-agent.service <<UNIT
[Unit]
Description=supervision-si node agent ($NODE_NAME)
After=docker.service wg-quick@wg0.service
Requires=docker.service
[Service]
WorkingDirectory=$ROOT
ExecStart=/usr/bin/python3 $ROOT/deploy/node_agent.py serve
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
UNIT
    systemctl daemon-reload && systemctl enable --now si-node-agent >>"$LOG" 2>&1 || die "si-node-agent : voir $LOG"
    systemctl restart si-node-agent
    log "agent de nœud : systemctl status si-node-agent (écoute $WG_ADDR:${SI_NODE_PORT:-6460})"
  else
    log "pas de systemd : lancer à la main  nohup python3 deploy/node_agent.py serve &"
  fi
}

profile_node() {
  node_common
  python3 deploy/cohorts.py override "$NODE_NAME" | tee -a "$LOG"
  local services; services=$(python3 deploy/cohorts.py node "$NODE_NAME" | tr '\n' ' ')
  local gw; gw=$(python3 -c "import json;print(' '.join(json.load(open('$GEN/node.plan.json'))['gateway']))")
  ./scripts/run.sh config -q >>"$LOG" 2>&1 || true
  if [ -n "$gw" ]; then
    if echo " $gw " | grep -q " keycloak "; then gateway_up; else
      log "bordure : gateway/scripts/run.sh up -d --build $gw (copier pki/ depuis le manager, TLS_EXTRA_SAN = nom public)"
      ./gateway/scripts/run.sh up -d --build $gw >>"$LOG" 2>&1 || die "passerelle : voir $LOG"
    fi
  fi
  build_batches "$services"
  node_agent_install
  log "application du plan (compose up des services de ce nœud + relais)"
  python3 deploy/node_agent.py apply >>"$LOG" 2>&1 || die "apply : voir $LOG"
  status
  log "depuis le manager : deploy/repartition.py status | apply | migrate <cohorte> <nœud>"
}

# --- menu -------------------------------------------------------------------
# tests : `SI_INSTALL_SOURCE_ONLY=1 source scripts/install.sh` charge les fonctions sans rien lancer
if [ "${SI_INSTALL_SOURCE_ONLY:-0}" = 1 ]; then return 0 2>/dev/null || exit 0; fi
preflight
if [ "$RESUME" = 1 ] && [ -f "$GEN/install.profile" ]; then PROFILE=$(cat "$GEN/install.profile"); else
PROFILE=$(menu PROFILE "Que déployer sur cette machine ?" light \
  light "Standalone léger : core + tuiles choisies (tests immédiats)" \
  node "Nœud du déploiement réparti (manager super, VM LAN, hub OVH, VM OVH -- selon deploy/nodes.json)")
fi
echo "$PROFILE" > "$GEN/install.profile"
log "profil : $PROFILE"
case "$PROFILE" in
  light) profile_light ;;
  node|super|lan|ovh-hub|ovh) profile_node ;;
  *) die "profil inconnu : $PROFILE" ;;
esac
log "terminé (journal : $LOG)"
