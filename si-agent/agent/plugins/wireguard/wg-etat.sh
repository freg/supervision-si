#!/bin/sh
# #884 : commande forcée À INSTALLER PAR L'ADMINISTRATEUR DU VPN sur le serveur WireGuard (lecture seule).
# Affiche `wg show all dump` en masquant clés privées et partagées ; rien d'autre n'est possible avec la clé SSH du hub.
#   install -m 755 wg-etat.sh /usr/local/bin/wg-etat
#   useradd -r -m -s /bin/sh wgetat ; echo 'wgetat ALL=(root) NOPASSWD: /usr/bin/wg show all dump' > /etc/sudoers.d/wgetat
#   ~wgetat/.ssh/authorized_keys :
#   command="/usr/local/bin/wg-etat",no-pty,no-port-forwarding,no-agent-forwarding,no-X11-forwarding ssh-ed25519 AAAA… si-agent
sudo -n /usr/bin/wg show all dump | awk -F'\t' 'BEGIN{OFS="\t"} NF==5{$2="(masquée)"} NF==9{$3="(masquée)"} {print}'
