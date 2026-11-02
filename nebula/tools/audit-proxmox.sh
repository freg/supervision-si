#!/bin/sh
# audit-proxmox.sh (#958) -- relevé de sécurité d'un hyperviseur Proxmox VE, LECTURE SEULE (aucune modification).
# À lancer en root sur le nœud :  sh audit-proxmox.sh > audit-proxmox-$(hostname).json
# Puis importer le JSON dans le hub : Réseau › Audit sécurité › Importer un relevé (source : proxmox), ou :
#   curl -s -X POST "$HUB/sites/$SITE/audit/importer" -H 'Content-Type: application/json' \
#        -d "{\"source\":\"proxmox\",\"donnees\":$(cat audit-proxmox-$(hostname).json)}"
# Rien de secret n'est relevé : ni mots de passe, ni clés, ni contenu de VM. Les IP relevées restent dans le JSON (hors dépôt).
set -u
j() { printf '%s' "$1" | sed 's/\\/\\\\/g; s/"/\\"/g' | tr -d '\n\r'; }
jlist() { # lignes -> tableau JSON de chaînes
  first=1; printf '['; while IFS= read -r l; do [ -z "$l" ] && continue; [ $first = 1 ] || printf ','; first=0; printf '"%s"' "$(j "$l")"; done; printf ']'; }

HOST=$(hostname)
PVEVER=$(pveversion 2>/dev/null || cat /etc/debian_version 2>/dev/null)
UPD=$(apt-get -s upgrade 2>/dev/null | grep -c '^Inst ' || true)
UPDSEC=$(apt-get -s upgrade 2>/dev/null | grep '^Inst ' | grep -ci 'security' || true)
PRL=$(sshd -T 2>/dev/null | awk '$1=="permitrootlogin"{print $2}'); [ -z "$PRL" ] && PRL=$(grep -i '^PermitRootLogin' /etc/ssh/sshd_config 2>/dev/null | awk '{print $2}' | tail -1)
PWA=$(sshd -T 2>/dev/null | awk '$1=="passwordauthentication"{print $2}'); [ -z "$PWA" ] && PWA=yes
FWC=$(grep -i '^enable:' /etc/pve/firewall/cluster.fw 2>/dev/null | awk '{print $2}'); [ -z "$FWC" ] && FWC=0
FWH=$(grep -i '^enable:' "/etc/pve/nodes/$HOST/host.fw" 2>/dev/null | awk '{print $2}'); [ -z "$FWH" ] && FWH=0
SUB=$(pvesubscription get 2>/dev/null | awk -F': *' '$1=="status"{print $2}')
ENT=$(grep -rl 'enterprise.proxmox.com' /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null | xargs -r grep -L '^#' | wc -l)
NOSUB=$(grep -rh 'pve-no-subscription' /etc/apt/sources.list /etc/apt/sources.list.d/ 2>/dev/null | grep -vc '^#' || true)
BK=$(grep -c '^vzdump' /etc/pve/jobs.cfg 2>/dev/null || true); [ "$BK" = 0 ] && BK=$(grep -c vzdump /etc/pve/vzdump.cron 2>/dev/null || true)
for v in UPD UPDSEC ENT NOSUB BK; do eval "$v=\${$v:-0}"; eval "$v=\$(printf '%s\n' \"\$$v\" | head -1)"; done
CLUSTER=$(pvecm status 2>/dev/null | awk -F': *' '/^Name/{print $2}')

printf '{"hostname":"%s","pveversion":"%s","updates_pending":%s,"updates_security":%s,"ssh_permit_root_login":"%s","ssh_password_auth":"%s",' \
  "$(j "$HOST")" "$(j "$PVEVER")" "${UPD:-0}" "${UPDSEC:-0}" "$(j "$PRL")" "$(j "$PWA")"
printf '"firewall":{"cluster_enabled":%s,"host_enabled":%s},"subscription":"%s","repos_enterprise":%s,"repos_no_subscription":%s,"backup_jobs":%s,"cluster":"%s",' \
  "$([ "$FWC" = 1 ] && echo true || echo false)" "$([ "$FWH" = 1 ] && echo true || echo false)" "$(j "$SUB")" "$([ "${ENT:-0}" -gt 0 ] && echo true || echo false)" \
  "$([ "${NOSUB:-0}" -gt 0 ] && echo true || echo false)" "${BK:-0}" "$(j "$CLUSTER")"

# comptes et 2FA
printf '"users":['
first=1
pveum user list --output-format json 2>/dev/null | python3 -c '
import json,sys,subprocess
users=json.load(sys.stdin)
try: acl=subprocess.run(["pveum","acl","list","--output-format","json"],capture_output=True,text=True).stdout; acl=json.loads(acl or "[]")
except Exception: acl=[]
roles={}
for a in acl:
    roles.setdefault(a.get("ugid"),set()).add(a.get("roleid"))
out=[]
for u in users:
    uid=u.get("userid")
    out.append({"user":uid,"enabled":bool(u.get("enable",1)),"tfa":bool(u.get("keys") or u.get("tfa-locked-until") is not None or u.get("tfa")),"roles":",".join(sorted(roles.get(uid,set())))})
print(",".join(json.dumps(x) for x in out))' 2>/dev/null
printf '],'

# services à l'écoute (adresse, port, processus)
printf '"listening":['
ss -tlnpH 2>/dev/null | awk '{split($4,a,":"); port=a[length(a)]; addr=$4; sub(":"port"$","",addr); proc=""; if (match($0,/users:\(\("[^"]+"/)) {proc=substr($0,RSTART+9,RLENGTH-10)}; printf "%s{\"addr\":\"%s\",\"port\":\"%s\",\"proc\":\"%s\"}", (NR>1?",":""), addr, port, proc}'
printf '],'

# VM et conteneurs : état, ponts réseau, pare-feu VM, GPU passthrough
printf '"vms":['
first=1
for cfg in /etc/pve/qemu-server/*.conf /etc/pve/lxc/*.conf; do
  [ -f "$cfg" ] || continue
  vmid=$(basename "$cfg" .conf)
  case "$cfg" in *qemu-server*) st=$(qm status "$vmid" 2>/dev/null | awk '{print $2}');; *) st=$(pct status "$vmid" 2>/dev/null | awk '{print $2}');; esac
  name=$(awk -F': *' '$1=="name"||$1=="hostname"{print $2; exit}' "$cfg")
  bridges=$(grep -E '^net[0-9]+:' "$cfg" | grep -o 'bridge=[^,]*' | cut -d= -f2 | sort -u | tr '\n' ' ')
  tags=$(grep -E '^net[0-9]+:' "$cfg" | grep -o 'tag=[^,]*' | cut -d= -f2 | sort -u | tr '\n' ' ')
  fw=$(grep -E '^net[0-9]+:' "$cfg" | grep -c 'firewall=1')
  gpu=$(grep -Ec '^hostpci[0-9]+:' "$cfg")
  [ $first = 1 ] || printf ','; first=0
  printf '{"vmid":"%s","name":"%s","status":"%s","bridges":%s,"vlan_tags":%s,"firewall":%s,"gpu":%s}' \
    "$vmid" "$(j "$name")" "$(j "$st")" "$(printf '%s\n' $bridges | jlist)" "$(printf '%s\n' $tags | jlist)" "$([ "$fw" -gt 0 ] && echo true || echo false)" "$([ "$gpu" -gt 0 ] && echo true || echo false)"
done
printf '],'

# ponts / interfaces (vlan-aware, adresses)
printf '"bridges":['
first=1
for b in $(awk '/^auto|^iface/{if($2 ~ /^vmbr/) print $2}' /etc/network/interfaces 2>/dev/null | sort -u); do
  va=$(awk -v b="$b" '$1=="iface"&&$2==b{f=1;next} f&&/^iface/{f=0} f&&/bridge-vlan-aware/{print $2}' /etc/network/interfaces)
  ip=$(ip -4 -o addr show "$b" 2>/dev/null | awk '{print $4}' | tr '\n' ' ')
  [ $first = 1 ] || printf ','; first=0
  printf '{"name":"%s","vlan_aware":%s,"addresses":"%s"}' "$b" "$([ "$va" = yes ] && echo true || echo false)" "$(j "$ip")"
done
printf '],'
printf '"storage":['
pvesm status 2>/dev/null | awk 'NR>1{printf "%s{\"name\":\"%s\",\"type\":\"%s\",\"used_pct\":\"%s\"}", (NR>2?",":""), $1, $2, $7}'
printf '],'
printf '"releve":"%s"}\n' "$(date -Is)"
