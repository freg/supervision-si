#!/bin/bash
# Atteignabilité SSID x VLAN depuis un client Wi-Fi Linux (agent du campus) -- fichier produit par ssid_vlan_list.py.
# usage : sudo ./ssid-vlan-check.sh <interface-wifi> <fichier-ssids> [cible ...]
#   cible = IP (ping) ou IP:port (connexion TCP -- pour un poste Windows qui ne répond pas au ping).
#   Cibles testées depuis chaque SSID : la passerelle de chaque VLAN routé (« #vlans »), les cibles en plus
#   (une machine toujours allumée par VLAN prouve le routage inter-VLAN, une passerelle seule ne prouve que le firewall), 1.1.1.1.
#   Ne pas donner une adresse de la machine elle-même. Variable KM=sae pour des SSID WPA3 seuls.
#   ping -I / curl --interface forcent la sortie par le Wi-Fi (la machine peut aussi être reliée en filaire).
IF=${1:?interface wifi}; F=${2:?fichier ssids}; shift 2
TARGETS="$(grep '^#vlans;' "$F" | cut -d';' -f2 | tr ',' '\n' | while IFS='=' read -r v n; do
  [ -n "$n" ] && python3 -c "import ipaddress,sys;print(next(ipaddress.ip_network(sys.argv[1],strict=False).hosts()))" "$n"; done | tr '\n' ' ') $* 1.1.1.1"

probe() {  # $1 = ip ou ip:port
  case "$1" in
    *:*) timeout 6 curl -s --connect-timeout 4 --interface "$IF" "telnet://$1" </dev/null >/dev/null 2>&1; rc=$?
         [ $rc -eq 0 ] || [ $rc -eq 124 ] ;;            # 124 = connecté puis coupé par timeout
    *)   ping -I "$IF" -c2 -W1 -q "$1" >/dev/null 2>&1 ;;
  esac
}

printf "%-24s %-6s %-18s" "SSID" "VLAN" "adresse"; for T in $TARGETS; do printf " %-15s" "$T"; done; echo
grep -v '^#' "$F" | grep ';' | while IFS=';' read -r S K V N G; do
  [ -z "$S" ] && continue
  # profil explicite : « nmcli dev wifi connect » échoue en « key-mgmt manquante » (SSID absent du dernier scan,
  # ancien profil du même nom) ; profil sans connexion automatique, supprimé après le test
  C="ssidtest-$V-$(echo "$S" | tr -cd 'A-Za-z0-9_-')"; nmcli con delete "$C" >/dev/null 2>&1
  if [ -n "$K" ]; then
    nmcli con add type wifi ifname "$IF" con-name "$C" ssid "$S" connection.autoconnect no ipv6.method ignore \
      wifi-sec.key-mgmt "${KM:-wpa-psk}" wifi-sec.psk "$K" >/dev/null 2>&1
  else
    nmcli con add type wifi ifname "$IF" con-name "$C" ssid "$S" connection.autoconnect no ipv6.method ignore >/dev/null 2>&1
  fi
  E=$(nmcli -w 40 con up "$C" ifname "$IF" 2>&1)
  if [ $? -ne 0 ]; then
    printf "%-24s %-6s %-18s association KO : %s\n" "$S" "$V" "-" "$(echo "$E" | tail -1 | cut -c1-110)"
    nmcli con delete "$C" >/dev/null 2>&1; continue
  fi
  sleep 3; A=$(ip -4 -br a show "$IF" | awk '{print $3}')
  printf "%-24s %-6s %-18s" "$S" "$V" "${A:-pas de bail}"
  for T in $TARGETS; do probe "$T" && R=OK || R=KO; printf " %-15s" "$R"; done; echo
  nmcli con down "$C" >/dev/null 2>&1; nmcli con delete "$C" >/dev/null 2>&1
done
