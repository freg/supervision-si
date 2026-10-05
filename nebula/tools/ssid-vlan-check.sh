#!/bin/bash
# Atteignabilité SSID x VLAN depuis un client Wi-Fi Linux (agent du campus) -- fichier produit par ssid_vlan_list.py.
# usage : sudo ./ssid-vlan-check.sh <interface-wifi> <fichier-ssids> [cible-en-plus ...]
#   cibles testées depuis chaque SSID : la passerelle de chaque VLAN routé (« #vlans »), les cibles en plus
#   (une machine toujours allumée par VLAN prouve le routage inter-VLAN, la passerelle seule ne prouve que le firewall), 1.1.1.1.
IF=${1:?interface wifi}; F=${2:?fichier ssids}; shift 2
TARGETS="$(grep '^#vlans;' "$F" | cut -d';' -f2 | tr ',' '\n' | while IFS='=' read -r v n; do
  python3 -c "import ipaddress,sys;print(next(ipaddress.ip_network(sys.argv[1],strict=False).hosts()))" "$n"; done | tr '\n' ' ') $* 1.1.1.1"
printf "%-24s %-6s %-18s" "SSID" "VLAN" "adresse"; for T in $TARGETS; do printf " %-15s" "$T"; done; echo
grep -v '^#' "$F" | while IFS=';' read -r S K V N G; do
  [ -z "$S" ] && continue
  if [ -n "$K" ]; then nmcli dev wifi connect "$S" password "$K" ifname "$IF" >/dev/null 2>&1; else nmcli dev wifi connect "$S" ifname "$IF" >/dev/null 2>&1; fi
  if [ $? -ne 0 ]; then printf "%-24s %-6s %-18s association KO\n" "$S" "$V" "-"; continue; fi
  sleep 5; A=$(ip -4 -br a show "$IF" | awk '{print $3}')
  printf "%-24s %-6s %-18s" "$S" "$V" "${A:-pas de bail}"
  for T in $TARGETS; do ping -I "$IF" -c2 -W1 -q "$T" >/dev/null 2>&1 && R=OK || R=KO; printf " %-15s" "$R"; done; echo
done
nmcli dev disconnect "$IF" >/dev/null 2>&1
