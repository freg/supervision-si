#!/bin/sh
# #806 : installe (ou met à jour) le collecteur de sondes d'un site sur un mini-PC Linux du site, en root : central local
# si-agent (service si-collecteur, https://<IP>:6444) auquel s'enrôlent les sondes Raspberry du site. L'agent du mini-PC,
# enrôlé au hub, remonte ensuite leurs mesures par la sonde collecte-sondes (tuile « Data RF »).
#   sh installer-collecteur.sh [--ref dev|<commit>] [--port 6444] [--site sondes] [--historique]
# Code pris sur GitHub (archive du dépôt public) ; état et jeton conservés d'une mise à jour à l'autre ;
# jeton d'enrôlement des sondes dans /etc/si-collecteur/env (600), jamais affiché sauf par --jeton.
# #807 : interface du collecteur (état, jeton, commandes) servie au mini-PC seulement (--ui-local) ; le hub atteint les
# sondes par l'agent du mini-PC (commande « collecteur »).
set -eu
REF=dev ; PORT=6444 ; SITE=sondes ; HIST="" ; MONTRER=""
while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF="$2"; shift 2 ;;
    --port) PORT="$2"; shift 2 ;;
    --site) SITE="$2"; shift 2 ;;
    --historique) HIST=1; shift ;;
    --jeton) MONTRER=1; shift ;;
    *) echo "option inconnue : $1" >&2; exit 2 ;;
  esac
done
[ "$(id -u)" = 0 ] || { echo "à lancer en root" >&2; exit 2; }
if [ -n "$MONTRER" ]; then sed -n 's/^SI_JETON=//p' /etc/si-collecteur/env; exit 0; fi
command -v python3 >/dev/null || { echo "python3 absent" >&2; exit 2; }
DEST=/opt/si-collecteur
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
curl -fsSL "https://codeload.github.com/freg/supervision-si/tar.gz/$REF" | tar xz -C "$TMP"
SRC=$(ls -d "$TMP"/supervision-si-* | head -n 1)
[ -f "$SRC/si-agent/local-central/local_central.py" ] || { echo "archive du dépôt incomplète ($REF)" >&2; exit 1; }
mkdir -p "$DEST" && rm -rf "$DEST/si-agent.new" && mkdir -p "$DEST/si-agent.new"
cp -a "$SRC/si-agent/agent" "$SRC/si-agent/local-central" "$SRC/si-agent/make-archive.sh" "$SRC/si-agent/README.md" "$DEST/si-agent.new/"
if [ -d "$DEST/si-agent/local-central/data" ]; then rm -rf "$DEST/si-agent.new/local-central/data"; cp -a "$DEST/si-agent/local-central/data" "$DEST/si-agent.new/local-central/data"; fi
rm -rf "$DEST/si-agent.ancien"; [ -d "$DEST/si-agent" ] && mv "$DEST/si-agent" "$DEST/si-agent.ancien"; mv "$DEST/si-agent.new" "$DEST/si-agent"
install -d -m 700 /etc/si-collecteur
if ! grep -q '^SI_JETON=.' /etc/si-collecteur/env 2>/dev/null; then
  umask 077; echo "SI_JETON=$(python3 -c 'import secrets; print(secrets.token_hex(12))')" > /etc/si-collecteur/env
fi
sed -i '/^SI_PORT=/d' /etc/si-collecteur/env && echo "SI_PORT=$PORT" >> /etc/si-collecteur/env   # #807 : lu par l'agent du mini-PC (relais)
chmod 600 /etc/si-collecteur/env
cat > /etc/systemd/system/si-collecteur.service <<EOS
[Unit]
Description=si-collecteur : collecteur des sondes radio du site (central local si-agent, #806)
After=network-online.target
Wants=network-online.target
[Service]
EnvironmentFile=/etc/si-collecteur/env
WorkingDirectory=$DEST/si-agent/local-central
ExecStart=/usr/bin/python3 local_central.py --site $SITE --port $PORT --interval 60 --rebuild-archive --ui-local ${HIST:+--history auto }--token \${SI_JETON} --plugins wifi-probe,path-probe,dns-observe,wifi-monitor,rf-spectrum
Restart=always
RestartSec=5
[Install]
WantedBy=multi-user.target
EOS
systemctl daemon-reload
systemctl enable si-collecteur >/dev/null 2>&1
systemctl restart si-collecteur
for i in $(seq 1 30); do curl -skf "https://127.0.0.1:$PORT/ca" >/dev/null && break; sleep 2; done
systemctl --no-pager --lines=3 status si-collecteur || true
IP=$(ip -4 route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<NF;i++) if($i=="src") print $(i+1)}' | head -n 1)
echo "collecteur prêt : https://$IP:$PORT/ (version $REF)"
echo "enrôler une sonde (sur la sonde, en root) : curl -fsSL -k \"https://$IP:$PORT/deploy/linux?token=\$(jeton)\" | sh"
echo "jeton : sh $0 --jeton"
