#!/data/data/com.termux/files/usr/bin/bash
# Radar Wi-Fi mobile (#954/#955/#956) -- à lancer dans Termux sur le téléphone (applis Termux + Termux:API de la MÊME source, F-Droid ;
# `pkg install termux-api jq curl`). Balaye les bornes visibles en continu et envoie chaque NOUVEAU balayage au hub (nebula-api).
# Usage : HUB=https://supervision.optline.fr/api/nebula SITE=<site_id> SOURCE="Téléphone Freg" ./radar-mobile.sh [intervalle_s=5]
# Android limite les balayages (4 / 2 min au premier plan, bien moins en arrière-plan) : Options pour les développeurs →
# « Limitation de la recherche Wi-Fi » désactivée, Termux à l'écran, localisation activée. `termux-wifi-scaninfo` renvoie le
# DERNIER balayage du système : s'il n'a pas changé (même horodatage), rien n'est envoyé et le script le dit.
set -u
HUB="${HUB:?HUB=https://… requis (base de nebula-api)}"; SITE="${SITE:?SITE=<site_id> requis}"; SOURCE="${SOURCE:-telephone}"; INT="${1:-5}"
echo "radar → $HUB/sites/$SITE/reperage/radar, source « $SOURCE », toutes les ${INT}s (Ctrl-C pour arrêter)"
# Android ne balaie que si quelque chose le demande : l'écran de choix des réseaux Wi-Fi ouvert relance un balayage toutes
# les ~10 s. On l'ouvre (Termux continue en arrière-plan grâce au verrou de veille) ; revenir à Termux pour lire les lignes.
termux-wake-lock 2>/dev/null || true
am start -a android.settings.WIFI_SETTINGS >/dev/null 2>&1 && echo "écran Wi-Fi d'Android ouvert (il force les balayages) : le laisser affiché pendant la marche"
n=0; dernier=""; fige=0
while true; do
  scan=$(termux-wifi-scaninfo 2>/dev/null)
  # borne CONNECTÉE : RSSI en direct (ce champ se rafraîchit en continu, lui) -> ajoutée / remplacée dans le balayage
  conn=$(termux-wifi-connectioninfo 2>/dev/null)
  if echo "$conn" | jq -e '.bssid and .rssi' >/dev/null 2>&1; then
    scan=$(jq -cn --argjson s "${scan:-[]}" --argjson c "$conn" '($s | map(select(.bssid != $c.bssid))) + [{bssid:$c.bssid, ssid:$c.ssid, rssi:$c.rssi, frequency_mhz:$c.frequency_mhz, timestamp:(now*1000000|floor), connecte:true}]')
  fi
  if [ -z "$scan" ] || [ "$scan" = "[]" ] || ! echo "$scan" | jq -e 'type=="array"' >/dev/null 2>&1; then
    echo "$(date +%T) aucun balayage : $(echo "$scan" | head -c 120) (Termux:API installé ? localisation autorisée ?)"; sleep "$INT"; continue
  fi
  # empreinte = horodatages Android des résultats (µs depuis le démarrage) : identique = pas de nouveau balayage
  empreinte=$(echo "$scan" | jq -c '. as $s | ([$s[] | select(.connecte != true) | .timestamp] | sort) + [$s[] | select(.connecte == true) | .rssi]')
  if [ "$empreinte" = "$dernier" ]; then
    fige=$((fige+1)); [ $((fige % 6)) -eq 1 ] && echo "$(date +%T) balayage inchangé depuis ${fige} tours (limitation Android : désactiver « Limitation de la recherche Wi-Fi », garder Termux à l'écran)"
    sleep "$INT"; continue
  fi
  dernier="$empreinte"; fige=0
  corps=$(jq -cn --arg s "$SOURCE" --argjson scan "$scan" '{source:$s, scan:$scan}')
  rep=$(curl -sS -m 10 -H 'Content-Type: application/json' -d "$corps" "$HUB/sites/$SITE/reperage/radar" 2>&1)
  n=$((n+1)); echo "$(date +%T) #$n $(echo "$rep" | jq -r 'if .bornes then "\(.bornes) bornes, + forte \(.plus_forte.ssid) \(.plus_forte.rssi) dBm ≈ \(.plus_forte.distance_m) m" else (.error // .) end' 2>/dev/null || echo "$rep")"
  sleep "$INT"
done
