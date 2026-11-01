#!/bin/sh
# install-ancien.sh -- #867 : installation de la supervision sur un hôte Debian ANCIEN (4.0 etch, 5.0 lenny, …) ou récent.
# Fichier GÉNÉRÉ par make-installer.py depuis plugins/systemes/systemes.py : ne pas éditer à la main.
#
# Un seul script pour toutes les versions. Il détecte le système et choisit :
#  - « agent »  : hôte capable de faire tourner l'agent complet (Debian >= 8 en x86_64, glibc >= 2.17)
#                 -> il donne la commande install.sh (Python autonome si besoin, #864) et s'arrête ;
#  - « releve » : hôte trop ancien (Python 3 introuvable, TLS d'avant 1.2 : Debian 4 à 7, i686…)
#                 -> compte local « si-agent » VERROUILLÉ, clé SSH limitée à l'adresse de l'agent relayeur
#                 (from=), commande FORCÉE qui ne fait qu'exécuter le relevé en lecture seule (celui de
#                 la sonde `systemes`) ; ni shell, ni pty, ni redirection. Rien n'est envoyé : c'est
#                 l'agent relayeur (super) qui vient lire, comme pour nms / optick3 (#865/#866).
#
# Par défaut : --verifier (LECTURE SEULE : détection + plan, aucune modification). --installer applique.
# Usage (root) :
#   sh install-ancien.sh [--verifier]                       # diagnostic + ce qui serait fait
#   sh install-ancien.sh --installer --cle /tmp/si_agent_legacy.pub --depuis 192.168.0.197 [--sudo]
#   sh install-ancien.sh --retirer                          # supprime compte, fichiers, ligne sudoers
#   --force-releve : mode relevé même si l'agent complet est possible ; --nom NOM : nom affiché dans le hub
# --sudo (optionnel) : ajoute UNE ligne NOPASSWD limitée au relevé dans /etc/sudoers (vérifiée par visudo),
#   pour avoir les noms des processus à l'écoute ; sans --sudo, le relevé tourne sans privilège.

PATH="/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"; export PATH
LC_ALL=C; export LC_ALL
U=si-agent
HOME_U=/var/lib/si-agent
LIB=/usr/local/lib/si-agent
WRAP=/usr/local/sbin/si-agent-releve
MARQ="# si-agent-releve (#867)"
ACTION=verifier; CLE=""; DEPUIS=""; SUDO=0; FORCE=0; NOM=""

while [ $# -gt 0 ]; do
  case "$1" in
    --verifier) ACTION=verifier;;
    --installer) ACTION=installer;;
    --retirer) ACTION=retirer;;
    --cle) CLE="$2"; shift;;
    --depuis) DEPUIS="$2"; shift;;
    --sudo) SUDO=1;;
    --force-releve) FORCE=1;;
    --nom) NOM="$2"; shift;;
    -h|--help) sed -n '2,22p' "$0"; exit 0;;
    *) echo "option inconnue : $1 (voir --help)" >&2; exit 2;;
  esac
  shift
done

# ---------- détection (lecture seule) ----------
DV=$(head -n 1 /etc/debian_version 2>/dev/null)
DMAJ=$(echo "$DV" | sed -n 's/^\([0-9][0-9]*\).*/\1/p')
ARCH=$(uname -m)
GLIBC=$(ldd --version 2>/dev/null | head -n 1 | sed -n 's/.* \([0-9][0-9]*\.[0-9][0-9]*\)[^0-9]*$/\1/p')
[ -n "$GLIBC" ] || GLIBC=$(ls /lib/libc-*.so /lib/*/libc-*.so 2>/dev/null | head -n 1 | sed -n 's/.*libc-\([0-9.]*\)\.so/\1/p')
PY3=""; command -v python3 >/dev/null 2>&1 && PY3=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null)
OSSL=$(openssl version 2>/dev/null | awk '{print $2}')
SSHV=$(ssh -V 2>&1 | head -n 1 | sed -n 's/^OpenSSH_\([0-9.p]*\).*/\1/p')
HN=$(hostname -s 2>/dev/null || hostname)
# tests seulement : SI_ANCIEN_FAUX="debian_version|arch|glibc|python3|openssl|openssh"
if [ -n "$SI_ANCIEN_FAUX" ]; then
  IFS='|' read DV ARCH GLIBC PY3 OSSL SSHV <<EOT
$SI_ANCIEN_FAUX
EOT
  DMAJ=$(echo "$DV" | sed -n 's/^\([0-9][0-9]*\).*/\1/p')
fi
[ -n "$NOM" ] || NOM=$(echo "$HN" | tr 'A-Z' 'a-z')

ge() { awk -v a="$1" -v b="$2" 'BEGIN { split(a, x, "."); split(b, y, "."); if (x[1] + 0 != y[1] + 0) exit !(x[1] + 0 > y[1] + 0); exit !(x[2] + 0 >= y[2] + 0) }'; }
MODE=releve; RAISON=""
if [ "$ARCH" = x86_64 ] && [ -n "$GLIBC" ] && ge "$GLIBC" 2.17; then MODE=agent; RAISON="glibc $GLIBC x86_64 : Python autonome possible"; fi
if [ -n "$PY3" ] && ge "$PY3" 3.7; then MODE=agent; RAISON="Python $PY3 présent"; fi
[ "$MODE" = releve ] && RAISON="glibc ${GLIBC:-?} / $ARCH / Python 3 ${PY3:-absent} / OpenSSL ${OSSL:-?} : agent complet impossible"
[ "$FORCE" = 1 ] && MODE=releve

echo "== $HN : Debian ${DV:-?} | $ARCH | glibc ${GLIBC:-?} | python3 ${PY3:-absent} | OpenSSL ${OSSL:-?} | OpenSSH ${SSHV:-?}"
case "$DMAJ" in 4|5|6|7|8) echo "   Debian $DMAJ : plus de correctifs de sécurité (fin de support) -- à inscrire au plan de migration";; esac
echo "== mode retenu : $MODE ($RAISON)"

if [ "$MODE" = agent ] && [ "$ACTION" != retirer ]; then
  echo "   -> installer l'agent complet (page Agents du hub, « installer sur un hôte ») :"
  echo "      sh si-agent/agent/install.sh --central https://<central> ...   (Python autonome /opt/pyagent si Python < 3.7, #864)"
  echo "   (ou relancer avec --force-releve pour un simple relevé à distance)"
  exit 0
fi

# ---------- retrait ----------
if [ "$ACTION" = retirer ]; then
  [ "$(id -u)" = 0 ] || { echo "à lancer en root" >&2; exit 1; }
  if grep -q "$MARQ" /etc/sudoers 2>/dev/null; then
    cp -p /etc/sudoers /etc/sudoers.si-agent.bak && grep -v "$MARQ" /etc/sudoers.si-agent.bak > /etc/sudoers.tmp \
      && visudo -c -f /etc/sudoers.tmp >/dev/null && cat /etc/sudoers.tmp > /etc/sudoers; rm -f /etc/sudoers.tmp
    echo "ligne sudoers retirée (copie : /etc/sudoers.si-agent.bak)"
  fi
  id "$U" >/dev/null 2>&1 && userdel -r "$U" 2>/dev/null; rm -rf "$LIB" "$WRAP" "$HOME_U"
  echo "retiré : compte $U, $LIB, $WRAP"; exit 0
fi

# ---------- plan ----------
LIGNE_CLE=""
if [ -n "$CLE" ]; then if [ -f "$CLE" ]; then LIGNE_CLE=$(grep -m 1 '^ssh-' "$CLE"); else LIGNE_CLE="$CLE"; fi; fi
if [ -z "$DEPUIS" ] && [ -n "$SSH_CLIENT" ]; then DEPUIS=${SSH_CLIENT%% *}; echo "   --depuis non fourni : adresse de la session ssh actuelle ($DEPUIS)"; fi
echo "== plan :"
echo "   1. compte $U (mot de passe verrouillé, home $HOME_U)$(id "$U" >/dev/null 2>&1 && echo ' -- EXISTE DÉJÀ, sera mis à jour')"
echo "   2. relevé en lecture seule : $LIB/inventaire.sh + commande forcée $WRAP"
echo "   3. $HOME_U/.ssh/authorized_keys : from=\"${DEPUIS:-?}\",command=\"$WRAP\",no-pty,no-port-forwarding,no-X11-forwarding,no-agent-forwarding <clé>"
[ "$SUDO" = 1 ] && echo "   4. /etc/sudoers : $U ALL=(root) NOPASSWD: $LIB/inventaire.sh   (vérifié par visudo, copie .bak)"
# sshd peut filtrer les comptes (AllowGroups / AllowUsers : OpenMediaVault met AllowGroups) -- vu sur fichiers (#867)
SSHD_CONF=${SSHD_CONF:-/etc/ssh/sshd_config}
# premier groupe listé qui n'est PAS un groupe privilégié (jamais root/wheel/sudo/adm pour ce compte)
GRP_SSH=$(sed -n 's/^[[:space:]]*[Aa]llow[Gg]roups[[:space:]]\{1,\}//p' "$SSHD_CONF" 2>/dev/null | head -n 1 | tr ' \t' '\n\n' | grep -vxE 'root|wheel|sudo|adm|staff|' | head -n 1)
USERS_SSH=$(sed -n 's/^[[:space:]]*[Aa]llow[Uu]sers[[:space:]]\{1,\}//p' "$SSHD_CONF" 2>/dev/null | head -n 1)
[ -n "$GRP_SSH" ] && echo "   5. sshd n'accepte que les groupes AllowGroups : $U ajouté au groupe « $GRP_SSH »"
[ -n "$USERS_SSH" ] && echo "   !! sshd a AllowUsers ($USERS_SSH) : ajouter $U à cette ligne de $SSHD_CONF puis recharger sshd (non fait par ce script)"
command -v sudo >/dev/null 2>&1 || { [ "$SUDO" = 1 ] && echo "   !! sudo absent : --sudo ignoré"; SUDO=0; }

if [ "$ACTION" = verifier ]; then
  echo "== vérification seulement : rien n'a été modifié. Pour appliquer :"
  echo "   sh $0 --installer --cle <fichier .pub de l'agent relayeur> --depuis <IP de l'agent relayeur>$( [ "$SUDO" = 1 ] && echo ' --sudo')"
  exit 0
fi

# ---------- installation ----------
[ "$(id -u)" = 0 ] || { echo "à lancer en root (su -c / sudo)" >&2; exit 1; }
[ -n "$LIGNE_CLE" ] || { echo "--cle manquante (clé PUBLIQUE de l'agent relayeur, ex. /etc/si-agent/keys/si_agent_legacy.pub)" >&2; exit 1; }
[ -n "$DEPUIS" ] || { echo "--depuis manquant (IP de l'agent relayeur)" >&2; exit 1; }
set -e
id "$U" >/dev/null 2>&1 || useradd -m -d "$HOME_U" -s /bin/sh -c "releve supervision (lecture seule)" "$U"
passwd -l "$U" >/dev/null 2>&1 || true
mkdir -p "$LIB" "$HOME_U/.ssh"
cat > "$LIB/inventaire.sh" <<'SI_INVENTAIRE_FIN'
LC_ALL=C; export LC_ALL
echo "@@node $(hostname -s 2>/dev/null)"
# #857 : état des lieux -- système, mises à jour, versions clés, services, usage, dépendances (noms et nombres seulement)
if [ -r /etc/os-release ]; then ( . /etc/os-release; echo "@@os ${ID:-?}|${VERSION_ID:-?}|${PRETTY_NAME:-?}" )
elif [ -r /etc/debian_version ]; then v=$(head -n 1 /etc/debian_version); echo "@@os debian|${v%%.*}|Debian GNU/Linux $v"
elif [ -r /etc/redhat-release ]; then v=$(head -n 1 /etc/redhat-release); echo "@@os rhel|$(echo "$v" | sed -n 's/[^0-9]*\([0-9]*\).*/\1/p')|$v"; fi
echo "@@kernel $(uname -r 2>/dev/null)"
PATH="$PATH:/sbin:/usr/sbin:/bin:/usr/bin"; export PATH
I=$(hostname -I 2>/dev/null | grep -E '^[0-9a-fA-F.: ]+$'); [ -n "$(echo $I)" ] || I=$(ip -4 -o addr show scope global 2>/dev/null | awk '{sub(/\/.*/, "", $4); printf "%s ", $4}')
echo "@@ips $I"
echo "@@uptime $(cut -d. -f1 /proc/uptime 2>/dev/null)"
echo "@@disque $(df -P / 2>/dev/null | awk 'NR == 2 {sub(/%/, "", $5); print $5}')"
[ -f /var/lib/dpkg/status ] && echo "@@maj $(stat -c %Y /var/lib/dpkg/status 2>/dev/null)"
[ -f /var/cache/apt/pkgcache.bin ] && echo "@@listes $(stat -c %Y /var/cache/apt/pkgcache.bin 2>/dev/null)"
if command -v apt-get >/dev/null 2>&1; then
  U=$(apt-get -s -o Debug::NoLocking=1 upgrade 2>/dev/null | grep '^Inst ')
  if [ -n "$U" ]; then echo "@@attente $(printf '%s\n' "$U" | grep -c '^Inst ') $(printf '%s\n' "$U" | grep -ci 'securi')"; else echo "@@attente 0 0"; fi
  dpkg-query -W -f='${Status} ${Package} ${Version}\n' apache2 apache nginx 'php[0-9]*-common' php-common 'mariadb-server-[0-9]*' mariadb-server \
    'mysql-server-[0-9]*' 'postgresql-[0-9]*' postfix dovecot-core openssh-server docker-ce docker.io pve-manager proxmox-backup-server \
    redis-server nodejs python3 'openjdk-[0-9]*-jre-headless' 'tomcat[0-9]*' bind9 samba squid amavisd-new spamassassin roundcube-core \
    proftpd-basic proftpd vsftpd openssl 2>/dev/null | awk '$3 == "installed" {print "@@pkg", $4, $5}' | head -n 60
fi
for f in /var/www/*/version.php /var/www/*/*/version.php; do
  [ -f "$f" ] || continue
  v=$(sed -n "s/.*OC_VersionString *= *'\([^']*\)'.*/\1/p" "$f" | head -n 1)
  [ -n "$v" ] && echo "@@app $(grep -qi "vendor *= *'nextcloud'" "$f" && echo nextcloud || echo owncloud) $v"
done
if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | awk 'NR > 1 {a = ($1 ~ /^[0-9]+$/) ? $3 : $4; n = split(a, x, ":"); p = x[n]; h = substr(a, 1, length(a) - length(p) - 1); u = $0;
    if (sub(/.*users:\(\("/, "", u)) sub(/".*/, "", u); else u = "?"; print "@@ecoute", p, h, u}' | sort -u | head -n 80
  L=" $(ss -ltn 2>/dev/null | awk 'NR > 1 {n = split(($1 ~ /^[0-9]+$/) ? $3 : $4, x, ":"); print x[n]}' | sort -u | tr '\n' ' ') "
  ss -tn 2>/dev/null | awk -v L="$L" 'NR > 1 && $1 == "ESTAB" {n = split($4, a, ":"); lp = a[n]; m = split($5, b, ":"); rp = b[m];
    rh = substr($5, 1, length($5) - length(rp) - 1); gsub(/[][]/, "", rh); sub(/^::ffff:/, "", rh);
    if (rh ~ /^127\./ || rh == "::1") next;
    if (index(L, " " lp " ")) {cin[lp]++; k = lp " " rh; if (!(k in vu)) {vu[k] = 1; din[lp]++}} else cout[rh " " rp]++}
    END {for (p in cin) print "@@cnxin", p, cin[p], din[p]; for (k in cout) print "@@cnxout", k, cout[k]}' | head -n 120
fi
if ! command -v ss >/dev/null 2>&1 && command -v netstat >/dev/null 2>&1; then
  netstat -ltnp 2>/dev/null | awk '$1 ~ /^tcp/ {a = $4; n = split(a, x, ":"); p = x[n]; h = substr(a, 1, length(a) - length(p) - 1);
    u = $7; if (u == "" || u == "-") u = "?"; else sub(/^[0-9]+\//, "", u); print "@@ecoute", p, h, u}' | sort -u | head -n 80
  L=" $(netstat -ltn 2>/dev/null | awk '$1 ~ /^tcp/ {n = split($4, x, ":"); print x[n]}' | sort -u | tr '\n' ' ') "
  netstat -tn 2>/dev/null | awk -v L="$L" '$1 ~ /^tcp/ && $6 == "ESTABLISHED" {n = split($4, a, ":"); lp = a[n]; m = split($5, b, ":"); rp = b[m];
    rh = substr($5, 1, length($5) - length(rp) - 1); sub(/^::ffff:/, "", rh);
    if (rh ~ /^127\./ || rh == "::1") next;
    if (index(L, " " lp " ")) {cin[lp]++; k = lp " " rh; if (!(k in vu)) {vu[k] = 1; din[lp]++}} else cout[rh " " rp]++}
    END {for (p in cin) print "@@cnxin", p, cin[p], din[p]; for (k in cout) print "@@cnxout", k, cout[k]}' | head -n 120
fi
if ! command -v systemctl >/dev/null 2>&1; then
  N=$(runlevel 2>/dev/null | awk '{print $2}'); [ -d "/etc/rc${N:-2}.d" ] || N=2
  for f in /etc/rc${N:-2}.d/S*; do [ -e "$f" ] || continue; b=$(basename "$f"); echo "$b" | sed 's/^S[0-9]*//'; done | grep -Evx 'rc\.local|rmnologin|stop-bootlogd|stop-bootlogd-single|bootlogs|single|killprocs|sendsigs|motd|README' | sed 's/^/@@svc /' | head -n 80
fi
command -v systemctl >/dev/null 2>&1 && systemctl list-units --type=service --state=running --no-legend 2>/dev/null | \
  awk '{u = $1; if (u !~ /^[A-Za-z0-9]/) u = $2; sub(/\.service$/, "", u); print "@@svc", u}' | head -n 80
R=0
for f in /var/log/apache2/*access*.log /var/log/nginx/*access*.log; do [ -f "$f" ] && R=$((R + $(wc -l < "$f"))); done
echo "@@req $R"
echo "@@comptes $(awk -F: '$3 >= 1000 && $3 < 65000 && $7 !~ /(nologin|false)$/' /etc/passwd 2>/dev/null | grep -c .)"
echo "@@fin"
SI_INVENTAIRE_FIN
if [ "$SUDO" = 1 ]; then
  printf '#!/bin/sh\n# commande forcée (#867) : relevé seul, entrée standard ignorée\nexec sudo %s/inventaire.sh </dev/null\n' "$LIB" > "$WRAP"
else
  printf '#!/bin/sh\n# commande forcée (#867) : relevé seul, entrée standard ignorée\nexec /bin/sh %s/inventaire.sh </dev/null\n' "$LIB" > "$WRAP"
fi
chown root:root "$LIB/inventaire.sh" "$WRAP"; chmod 755 "$LIB/inventaire.sh" "$WRAP"
echo "from=\"$DEPUIS\",command=\"$WRAP\",no-pty,no-port-forwarding,no-X11-forwarding,no-agent-forwarding $LIGNE_CLE" > "$HOME_U/.ssh/authorized_keys"
chown -R "$U" "$HOME_U"; chmod 700 "$HOME_U/.ssh"; chmod 600 "$HOME_U/.ssh/authorized_keys"
set +e
if [ "$SUDO" = 1 ] && ! grep -q "$MARQ" /etc/sudoers; then
  cp -p /etc/sudoers /etc/sudoers.si-agent.bak
  { cat /etc/sudoers; echo "$U ALL=(root) NOPASSWD: $LIB/inventaire.sh $MARQ"; } > /etc/sudoers.tmp
  if visudo -c -f /etc/sudoers.tmp >/dev/null 2>&1; then cat /etc/sudoers.tmp > /etc/sudoers; echo "sudoers : ligne ajoutée"
  else echo "!! sudoers refusé par visudo : rien changé, relevé sans privilège"
    printf '#!/bin/sh\nexec /bin/sh %s/inventaire.sh </dev/null\n' "$LIB" > "$WRAP"; fi
  rm -f /etc/sudoers.tmp
fi

if [ -n "$GRP_SSH" ] && getent group "$GRP_SSH" >/dev/null 2>&1; then
  usermod -a -G "$GRP_SSH" "$U" && echo "== $U ajouté au groupe $GRP_SSH (AllowGroups de sshd)"
fi

# ---------- auto-test ----------
R=$(su "$U" -c "$WRAP" 2>/dev/null | tail -n 1)
[ "$R" = "@@fin" ] && echo "== auto-test : relevé OK" || echo "!! auto-test : relevé incomplet (dernière ligne : '$R')"
# adresse vue par le relayeur : source de la route vers lui (hostname -i donne 127.0.1.1 sur Debian)
IP=$(ip route get "$DEPUIS" 2>/dev/null | sed -n 's/.* src \([0-9.]*\).*/\1/p' | head -n 1)
[ -n "$IP" ] || IP=$(hostname -i 2>/dev/null | tr ' ' '\n' | grep -v '^127\.' | head -n 1)
echo "== sur l'agent relayeur ($DEPUIS), ajouter à /etc/si-agent/systemes-remote.json :"
echo "   {\"name\": \"$NOM\", \"host\": \"${IP:-<ip>}\", \"user\": \"$U\", \"key\": \"/etc/si-agent/keys/si_agent_legacy\", \"role\": \"serveur\","
echo "    \"ssh_options\": [\"-o\", \"KexAlgorithms=+diffie-hellman-group14-sha1,diffie-hellman-group1-sha1\", \"-o\", \"HostKeyAlgorithms=+ssh-rsa\", \"-o\", \"PubkeyAcceptedAlgorithms=+ssh-rsa\"]}"
echo "   puis cocher la sonde « systemes » de cet agent (page Agents du hub)."
