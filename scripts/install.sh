#!/usr/bin/env bash
# Installeur interactif de supervision-si (livraison #511).
#
#   scripts/install.sh                     menu (whiptail si présent, sinon questions)
#   scripts/install.sh --answers FICHIER   sans interaction (rejouer une VM)
#   scripts/install.sh --resume            reprend la construction là où elle s'est arrêtée
#
# Profils :
#   light      standalone léger (compose, pas de Swarm) : cohorte core + tuiles choisies,
#              pour les tests immédiats
#   super      VM manager : core + coffre en place, Swarm initialisé sur le VPN, registre
#              privé, images construites et poussées, labels des cohortes (nodes.json)
#   lan        VM secondaire LAN : worker Swarm (ne construit rien)
#   ovh-hub    VM hub OVH : worker zone ovh + bordure (jumeau tls-proxy) + frontal public
#   ovh        VM secondaire OVH : worker zone ovh
#
# Noyau commun : prérequis (Docker, python3+yaml, jq, RAM/disque), .env complété par
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
  command -v jq >/dev/null || log "jq absent (apt install jq) : nécessaire pour les profils Swarm"
  local mem disk
  mem=$(awk '/MemTotal/{printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo 0)
  disk=$(df -Pm "$ROOT" | awk 'NR==2{print $4}')
  log "prérequis : RAM ${mem} Mo, disque libre ${disk} Mo, $(docker --version)"
  [ "$mem" -ge 3500 ] || log "AVERTISSEMENT : moins de 4 Go de RAM -- profil light conseillé, lots réduits"
  [ "$disk" -ge 15000 ] || log "AVERTISSEMENT : moins de 15 Go libres -- docker system prune conseillé"
  [ -f .env ] || cp .env.example .env
  python3 scripts/sync-env.py >>"$LOG" 2>&1 || log "sync-env.py : voir $LOG"
  set -a; . ./.env; set +a
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

swarm_common() {
  command -v jq >/dev/null || die "jq requis pour les profils Swarm"
  [ -f deploy/nodes.json ] || die "deploy/nodes.json absent (copier deploy/nodes.example.json et l'adapter)"
  command -v wg >/dev/null || log "wireguard-tools absent : apt install wireguard ; le VPN doit être monté AVANT Swarm"
  local me; me=$(ask NODE_NAME "Nom de ce nœud dans deploy/nodes.json" "$(hostname -s)")
  WG_ADDR=$(jq -r --arg n "$me" '.nodes[] | select(.name==$n) | .wg_address' deploy/nodes.json)
  [ -n "$WG_ADDR" ] && [ "$WG_ADDR" != "null" ] || die "nœud $me inconnu dans deploy/nodes.json"
  ip -o addr 2>/dev/null | grep -q "$WG_ADDR" || die "l'adresse VPN $WG_ADDR n'est pas montée (wg-quick@wg0) -- voir deploy/wg-mesh.sh"
  NODE_NAME=$me
}

profile_super() {
  swarm_common
  local services; services=$(python3 deploy/cohorts.py services core,coffre 2>>"$LOG" | tr '\n' ' ')
  ./scripts/run.sh config -q >>"$LOG" 2>&1 || true
  gateway_up
  if ! docker info 2>/dev/null | grep -q "Swarm: active"; then
    ./deploy/swarm-init.sh manager "$WG_ADDR" | tee -a "$LOG"
  fi
  ./deploy/swarm-init.sh labels deploy/nodes.json >>"$LOG" 2>&1
  grep -q "SI_REGISTRY=" .env && sed -i "s#^SI_REGISTRY=.*#SI_REGISTRY=$WG_ADDR:5000#" .env || echo "SI_REGISTRY=$WG_ADDR:5000" >> .env
  local all; all=$(python3 -c "import yaml;d=yaml.safe_load(open('docker-compose.yml'));print(' '.join(n for n,s in d['services'].items() if s.get('build')))")
  build_batches "$all"
  log "registre + push des images (deploy/build-push.sh)"; ./deploy/build-push.sh >>"$LOG" 2>&1 || die "push : voir $LOG"
  log "déploiement de la pile (deploy/deploy.sh)"; ./deploy/deploy.sh >>"$LOG" 2>&1 || die "stack deploy : voir $LOG"
  docker stack ps si --no-trunc --format 'table {{.Name}}\t{{.Node}}\t{{.CurrentState}}' | tee -a "$LOG" | head -60
  log "jeton worker pour les autres VM : $(docker swarm join-token -q worker)"
}

profile_worker() {  # $1 = zone attendue, $2 = bordure (1/0)
  swarm_common
  local manager token
  manager=$(jq -r '.nodes[] | select(.role=="manager") | .wg_address' deploy/nodes.json)
  token=$(ask JOIN_TOKEN "Jeton worker (affiché par le profil super, ou docker swarm join-token -q worker)" "")
  [ -n "$token" ] || die "jeton requis"
  docker info 2>/dev/null | grep -q "Swarm: active" || ./deploy/swarm-init.sh worker "$manager" "$token" "$WG_ADDR"
  local reg; reg="$manager:5000"
  if ! grep -q "$reg" /etc/docker/daemon.json 2>/dev/null; then
    log "registre privé $reg : ajouter \"insecure-registries\": [\"$reg\"] dans /etc/docker/daemon.json puis systemctl restart docker"
  fi
  if [ "$2" = "1" ]; then
    log "bordure : copier pki/ depuis le manager (certificat avec le nom public, TLS_EXTRA_SAN) puis scripts/front-reverse-proxy.sh"
  fi
  log "sur le manager : deploy/swarm-init.sh labels puis deploy/deploy.sh -- ce nœud recevra les cohortes de deploy/nodes.json ($NODE_NAME, zone $1)"
}

# --- menu -------------------------------------------------------------------
# tests : `SI_INSTALL_SOURCE_ONLY=1 source scripts/install.sh` charge les fonctions sans rien lancer
if [ "${SI_INSTALL_SOURCE_ONLY:-0}" = 1 ]; then return 0 2>/dev/null || exit 0; fi
preflight
if [ "$RESUME" = 1 ] && [ -f "$GEN/install.profile" ]; then PROFILE=$(cat "$GEN/install.profile"); else
PROFILE=$(menu PROFILE "Que déployer sur cette machine ?" light \
  light "Standalone léger : core + tuiles choisies (tests immédiats)" \
  super "VM super : manager Swarm, core + coffre, images, pile" \
  lan "VM secondaire LAN : worker Swarm" \
  ovh-hub "VM hub OVH : worker + bordure (jumeau tls-proxy)" \
  ovh "VM secondaire OVH : worker zone ovh")
fi
echo "$PROFILE" > "$GEN/install.profile"
log "profil : $PROFILE"
case "$PROFILE" in
  light) profile_light ;;
  super) profile_super ;;
  lan) profile_worker local 0 ;;
  ovh-hub) profile_worker ovh 1 ;;
  ovh) profile_worker ovh 0 ;;
  *) die "profil inconnu : $PROFILE" ;;
esac
log "terminé (journal : $LOG)"
