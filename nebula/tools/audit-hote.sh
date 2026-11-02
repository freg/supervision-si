#!/bin/sh
# audit-hote.sh (#958) -- relevé LECTURE SEULE d'un hôte non géré (passerelle LoRa, écran, objet connecté…) depuis une
# machine du même réseau (mini-PC agent, Termux, portable Linux). Aucun identifiant n'est essayé, aucune écriture.
#   sh audit-hote.sh <ip> [nom] > audit-hote-<nom>.json
# Balayage : nmap si présent (ports courants + version), sinon essai de connexion sur une liste de ports sensibles.
# Importer ensuite dans le hub : Réseau › Audit sécurité › Importer un relevé (source : hote), ou curl comme dans audit-proxmox.sh.
set -u
IP="${1:?usage: audit-hote.sh <ip> [nom]}"; NOM="${2:-$IP}"
j() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr -d '\n\r'; }
PORTS="21 22 23 53 69 80 111 135 139 161 443 445 502 512 513 1700 1883 1880 3000 3306 3389 5000 5432 5900 6379 8000 8080 8443 8883 9100 27017"
ping -c1 -W1 "$IP" >/dev/null 2>&1 && UP=true || UP=false
MAC=$(ip neigh show "$IP" 2>/dev/null | awk '{print $5}' | head -1); [ -z "$MAC" ] && MAC=$(arp -n "$IP" 2>/dev/null | awk '/:/{print $3}' | head -1)
printf '{"nom":"%s","ip":"%s","mac":"%s","joignable":%s,"releve":"%s","ports":[' "$(j "$NOM")" "$(j "$IP")" "$(j "$MAC")" "$UP" "$(date -Is)"
first=1
if command -v nmap >/dev/null 2>&1; then
  nmap -Pn -sV --version-light -p "$(echo $PORTS | tr ' ' ',')" "$IP" 2>/dev/null | awk '/^[0-9]+\/(tcp|udp)/ && $2=="open"{port=$1; sub(/\/.*/,"",port); svc=$3; $1=$2=$3=""; sub(/^ +/,""); printf "%s{\"port\":%s,\"service\":\"%s\",\"banner\":\"%s\"}", (n++?",":""), port, svc, $0}'
  # UDP LoRa (1700) et SNMP (161) : nmap -sU demande root ; essai léger si possible
  if [ "$(id -u)" = 0 ]; then
    nmap -Pn -sU -p 161,1700,69 "$IP" 2>/dev/null | awk '/^[0-9]+\/udp/ && ($2=="open"||$2=="open|filtered"){port=$1; sub(/\/.*/,"",port); printf ",{\"port\":%s,\"service\":\"%s\",\"banner\":\"udp %s\"}", port, $3, $2}'
  fi
else
  for p in $PORTS; do
    if (command -v nc >/dev/null 2>&1 && nc -z -w1 "$IP" "$p" >/dev/null 2>&1) || (command -v timeout >/dev/null 2>&1 && timeout 1 sh -c "exec 3<>/dev/tcp/$IP/$p" 2>/dev/null); then
      b=""
      case "$p" in 80|8080|8000|3000|1880|5000) b=$(curl -s -m2 -I "http://$IP:$p/" 2>/dev/null | head -1);; 443|8443) b=$(curl -sk -m2 -I "https://$IP:$p/" 2>/dev/null | head -1);; 22) b=$(timeout 2 nc -w1 "$IP" 22 2>/dev/null | head -1);; esac
      [ $first = 1 ] || printf ','; first=0
      printf '{"port":%s,"service":"","banner":"%s"}' "$p" "$(j "$b")"
    fi
  done
fi
printf '],'
# flux sortants observés (si tcpdump dispo et root : 10 s d'écoute sur les paquets émis par l'hôte vers l'extérieur du site)
printf '"sorties_externes":['
if command -v tcpdump >/dev/null 2>&1 && [ "$(id -u)" = 0 ]; then
  timeout 10 tcpdump -nn -q -i any "src host $IP and not dst net 10.0.0.0/8 and not dst net 172.16.0.0/12 and not dst net 192.168.0.0/16 and not dst net 224.0.0.0/4" 2>/dev/null \
    | awk '{for(i=1;i<=NF;i++) if($i==">"){d=$(i+1); sub(/:$/,"",d); sub(/\.[0-9]+$/,"",d); print d}}' | sort -u | head -20 | awk '{printf "%s\"%s\"", (n++?",":""), $0}'
fi
printf '],"defaut_identifiants":false}\n'
