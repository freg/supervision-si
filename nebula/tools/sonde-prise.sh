#!/bin/bash
# sonde-prise.sh (#959) -- Raspberry Pi sans écran, branché prise par prise (ou en sortie de panneau de brassage) :
# à chaque lien Ethernet qui monte, lit le commutateur et le port qui l'alimentent (LLDP, sans IP nécessaire), l'envoie au
# hub, puis attend que le téléphone nomme la prise (écran Repérage › 📡 Sonde) ; la LED du Pi signale chaque étape.
#
# Installation (Raspberry Pi OS) :   sudo apt install -y lldpd jq curl   &&   sudo systemctl enable --now lldpd
# Réglages (mémorisés dans ~/.sonde-prise.env, à créer ou passés en variables) :
#   HUB=https://<hub>/api/nebula  SITE=<id ou nom du site>  SOURCE="Pi3 Freg"  MODE=prise|brassage  IFACE=eth0
# Lancement :   sudo ./sonde-prise.sh            (sudo pour la LED ; sinon la LED est ignorée)
# Service :     sudo cp sonde-prise.sh /usr/local/bin/ && voir le bloc [Unit] en bas de ce fichier.
# Le Pi joint le hub par son Wi-Fi (wlan0, SSID d'installation) : le côté brassage n'a souvent pas d'IP.
#
# LED verte (ACT) :  clignote vite = lien monté, LLDP en attente   ·  clignote lent = relevé envoyé, en attente du téléphone
#                    fixe 3 s = prise enregistrée sur le téléphone → débrancher, prise suivante   ·  3 flashs = pas de LLDP (Nebula seul)
set -u
CONF="$HOME/.sonde-prise.env"; [ -f "$CONF" ] && . "$CONF"
HUB="${HUB:?HUB manquant (ex. https://hub/api/nebula)}"; SITE="${SITE:-}"; SOURCE="${SOURCE:-$(hostname)}"; MODE="${MODE:-prise}"; IFACE="${IFACE:-eth0}"
LLDP_ATTENTE="${LLDP_ATTENTE:-45}"      # s : les commutateurs annoncent LLDP toutes les 30 s
case "$MODE" in prise|brassage) ;; *) echo "MODE=prise|brassage"; exit 2;; esac

led=""; for l in /sys/class/leds/ACT /sys/class/leds/led0; do [ -w "$l/brightness" ] && led="$l" && break; done
[ -n "$led" ] && echo none > "$led/trigger" 2>/dev/null
led_set() { [ -n "$led" ] && echo "$1" > "$led/brightness" 2>/dev/null; }
flash() { local i; for i in 1 2 3; do led_set 1; sleep 0.12; led_set 0; sleep 0.12; done; }
log() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*"; }

# site par nom ou id
if [ -z "$SITE" ] || ! curl -sf -m 10 "$HUB/reperage/sites" | jq -e --arg s "$SITE" '.sites[] | select(.site_id == $s)' >/dev/null 2>&1; then
  found=$(curl -sf -m 10 "$HUB/reperage/sites" | jq -r --arg s "$SITE" '.sites[] | select(.name == $s or (.name | ascii_downcase) == ($s | ascii_downcase)) | .site_id' | head -1)
  if [ -z "$found" ]; then echo "Site « $SITE » inconnu. Sites :"; curl -sf -m 10 "$HUB/reperage/sites" | jq -r '.sites[] | "  \(.site_id)\t\(.name)"'; exit 2; fi
  SITE="$found"
fi
printf 'HUB=%q\nSITE=%q\nSOURCE=%q\nMODE=%q\nIFACE=%q\n' "$HUB" "$SITE" "$SOURCE" "$MODE" "$IFACE" > "$CONF"
MAC=$(cat "/sys/class/net/$IFACE/address")
log "sonde $SOURCE · mode $MODE · $IFACE $MAC · site $SITE · hub $HUB"
carrier() { [ "$(cat "/sys/class/net/$IFACE/carrier" 2>/dev/null)" = 1 ]; }

lldp_json() { # -> {commutateur, port, port_descr, vlan, ip_gestion} ou vide
  lldpcli -f json show neighbors ports "$IFACE" 2>/dev/null | jq -c '
    (.lldp.interface // {}) | (if type=="array" then (.[0] // {}) else . end) | (to_entries[0].value // empty) |
    { commutateur: (.chassis | to_entries[0].key // (.chassis | to_entries[0].value.name // "")),
      port: (.port.id.value // ""), port_descr: (.port.descr // ""),
      vlan: ((.vlan // []) | (if type=="array" then .[0] else . end) | (.["vlan-id"] // "")),
      ip_gestion: (.chassis | to_entries[0].value | (.["mgmt-ip"] // []) | (if type=="array" then .[0] else . end) // "") }' 2>/dev/null
}

envoyer() { # $1 = JSON lldp ou "{}" ; $2 = id (optionnel) ; -> JSON réponse
  local ip; ip=$(ip -4 -o addr show "$IFACE" 2>/dev/null | awk '{print $4}' | cut -d/ -f1 | head -1)
  jq -nc --arg source "$SOURCE" --arg mode "$MODE" --arg mac "$MAC" --arg ip "$ip" --argjson lldp "${1:-{\}}" --arg id "${2:-}" \
     '{source:$source, mode:$mode, mac:$mac, ip:$ip, lldp:$lldp} + (if $id != "" then {id:($id|tonumber)} else {} end)' \
   | curl -sf -m 15 -X POST "$HUB/sites/$SITE/reperage/sonde$([ -n "${2:-}" ] && echo '?refresh=1')" -H 'Content-Type: application/json' -d @-
}

while :; do
  led_set 0
  until carrier; do sleep 1; done
  log "lien monté sur $IFACE — attente LLDP (≤ $LLDP_ATTENTE s)"
  lldp=""; t=0
  while carrier && [ -z "$lldp" ] && [ $t -lt "$LLDP_ATTENTE" ]; do
    led_set 1; sleep 0.15; led_set 0; sleep 0.35; t=$((t+1))
    if [ $((t % 2)) = 0 ]; then lldp=$(lldp_json); [ "$(printf '%s' "$lldp" | jq -r '.commutateur // ""' 2>/dev/null)" != "" ] || lldp=""; fi
  done
  carrier || { log "débranché avant relevé"; continue; }
  if [ -n "$lldp" ]; then log "LLDP : $lldp"; else log "pas de LLDP : le hub cherchera la MAC dans Nebula (~1 min)"; flash; lldp="{}"; fi
  rep=$(envoyer "$lldp"); id=$(printf '%s' "$rep" | jq -r '.id // ""' 2>/dev/null)
  if [ -z "$id" ]; then log "hub injoignable ($HUB) — nouvel essai dans 5 s"; flash; sleep 5; continue; fi
  log "relevé #$id : $(printf '%s' "$rep" | jq -r '"\(.commutateur // "?") port \(.port // "?") · Nebula \(if .confirme == true then "confirmé" elif .confirme == false then "DIFFÈRE" else "pas encore vu" end)"')"
  # attente de la validation sur le téléphone ; on renvoie le relevé toutes les 15 s tant que Nebula ne confirme pas
  n=0
  while carrier; do
    etat=$(curl -sf -m 10 "$HUB/sites/$SITE/reperage/sonde/etat?source=$(printf '%s' "$SOURCE" | jq -sRr @uri)" | jq -c '.derniere // {}' 2>/dev/null)
    if [ "$(printf '%s' "$etat" | jq -r '.id // ""')" = "$id" ] && [ "$(printf '%s' "$etat" | jq -r '.ack')" = true ]; then
      log "✓ validé sur le téléphone : prise « $(printf '%s' "$etat" | jq -r '.prise // "(ignorée)"') » → débrancher, prise suivante"
      led_set 1; sleep 3; led_set 0
      until ! carrier; do led_set 1; sleep 0.5; led_set 0; sleep 1.5; done   # reste allumée doucement tant que le câble est branché
      break
    fi
    n=$((n+1))
    if [ $((n % 7)) = 0 ] && [ "$(printf '%s' "$etat" | jq -r '.confirme')" != true ]; then
      [ "$lldp" = "{}" ] && l2=$(lldp_json) && [ -n "$l2" ] && lldp="$l2"
      envoyer "$lldp" "$id" >/dev/null && log "relevé #$id renvoyé (Nebula pas encore d'accord)"
    fi
    led_set 1; sleep 0.5; led_set 0; sleep 1.5
  done
  carrier || log "débranché"
done

# ---- /etc/systemd/system/sonde-prise.service ----------------------------------------------------------------------
# [Unit]
# Description=Sonde de repérage prise par prise (supervision-si)
# After=network-online.target lldpd.service
# [Service]
# Environment=HOME=/root
# ExecStart=/usr/local/bin/sonde-prise.sh
# Restart=always
# RestartSec=5
# [Install]
# WantedBy=multi-user.target
# ---- sudo systemctl daemon-reload && sudo systemctl enable --now sonde-prise ; journalctl -fu sonde-prise -----------
