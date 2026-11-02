#!/data/data/com.termux/files/usr/bin/bash
# Radar Wi-Fi mobile (#954) -- à lancer dans Termux sur le téléphone (applis Termux + Termux:API, F-Droid ; `pkg install termux-api jq curl`).
# Balaye les bornes visibles en continu et envoie chaque balayage au hub (nebula-api, route /sites/<site>/reperage/radar).
# Usage : HUB=https://<nebula-api public> SITE=<site_id> SOURCE="Téléphone Freg" ./radar-mobile.sh [intervalle_s=5]
# Android limite le balayage (4 balayages / 2 min) : Options pour les développeurs → « Limitation de la recherche Wi-Fi » désactivée.
set -u
HUB="${HUB:?HUB=https://… requis (base de nebula-api)}"; SITE="${SITE:?SITE=<site_id> requis}"; SOURCE="${SOURCE:-telephone}"; INT="${1:-5}"
echo "radar → $HUB/sites/$SITE/reperage/radar, source « $SOURCE », toutes les ${INT}s (Ctrl-C pour arrêter)"
n=0; while true; do
  scan=$(termux-wifi-scaninfo 2>/dev/null)
  if [ -z "$scan" ] || [ "$scan" = "[]" ]; then echo "$(date +%T) aucun balayage (limitation Android ? Wi-Fi coupé ?)"; sleep "$INT"; continue; fi
  corps=$(jq -cn --arg s "$SOURCE" --argjson scan "$scan" '{source:$s, scan:$scan}')
  rep=$(curl -sS -m 10 -H 'Content-Type: application/json' -d "$corps" "$HUB/sites/$SITE/reperage/radar" 2>&1)
  n=$((n+1)); echo "$(date +%T) #$n $(echo "$rep" | jq -r 'if .bornes then "\(.bornes) bornes, + forte \(.plus_forte.ssid) \(.plus_forte.rssi) dBm ≈ \(.plus_forte.distance_m) m" else (.error // .) end' 2>/dev/null || echo "$rep")"
  sleep "$INT"
done
