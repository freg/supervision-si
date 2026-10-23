#!/bin/sh
# si-veille (#841) : veilleur local de la chaîne du hub, dans la SESSION de l'utilisateur (sans root).
# Usage : sh veille-chaine/installer.sh [fichier-de-config]   |   sh veille-chaine/installer.sh --retirer
set -eu
ICI="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/.local/share/si-veille"; CONF="$HOME/.config/si-veille"
if [ "${1:-}" = "--retirer" ]; then
  if [ "$(uname)" = Darwin ]; then launchctl unload "$HOME/Library/LaunchAgents/fr.exemple.si-veille.plist" 2>/dev/null || true; rm -f "$HOME/Library/LaunchAgents/fr.exemple.si-veille.plist"
  else systemctl --user disable --now si-veille.service 2>/dev/null || true; rm -f "$HOME/.config/systemd/user/si-veille.service"; systemctl --user daemon-reload 2>/dev/null || true; fi
  rm -f "$HOME/.local/bin/si-veille"; echo "si-veille retiré (configuration gardée)"; exit 0
fi
mkdir -p "$APP" "$CONF" "$HOME/.local/bin"; chmod 700 "$CONF"
install -m 0755 "$ICI/si_veille.py" "$APP/si_veille.py"
if [ -n "${1:-}" ]; then install -m 0600 "$1" "$CONF/config.json"; elif [ ! -f "$CONF/config.json" ]; then install -m 0600 "$ICI/config.exemple.json" "$CONF/config.json"; fi
printf '#!/bin/sh\nexec python3 "%s/si_veille.py" "$@"\n' "$APP" > "$HOME/.local/bin/si-veille"; chmod 755 "$HOME/.local/bin/si-veille"
if [ "$(uname)" = Darwin ]; then
  P="$HOME/Library/LaunchAgents/fr.exemple.si-veille.plist"; mkdir -p "$(dirname "$P")"
  cat > "$P" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>fr.exemple.si-veille</string>
<key>ProgramArguments</key><array><string>$(command -v python3)</string><string>$APP/si_veille.py</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/></dict></plist>
PL
  launchctl unload "$P" 2>/dev/null || true; launchctl load "$P"
else
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/si-veille.service" <<UN
[Unit]
# démarre avec la session graphique (GNOME y transmet affichage et bus de session), s'arrête avec elle
PartOf=graphical-session.target
After=graphical-session.target
Description=si-veille -- veilleur local de la chaîne du hub (silencieux si tout va bien)
[Service]
ExecStart=$(command -v python3) $APP/si_veille.py
Restart=always
RestartSec=30
[Install]
WantedBy=graphical-session.target
UN
  # notifications (affichage, bus de session) et clés ssh de l'agent de la session, pour le service utilisateur
  systemctl --user import-environment DISPLAY WAYLAND_DISPLAY XAUTHORITY DBUS_SESSION_BUS_ADDRESS SSH_AUTH_SOCK 2>/dev/null || true
  command -v notify-send >/dev/null || echo "ATTENTION notify-send absent : sudo apt install -y libnotify-bin"
  command -v secret-tool >/dev/null || echo "ATTENTION secret-tool absent (mot de passe SMTP) : sudo apt install -y libsecret-tools"
  systemctl --user daemon-reload && systemctl --user disable si-veille.service 2>/dev/null || true; systemctl --user enable --now si-veille.service >/dev/null && systemctl --user restart si-veille.service
fi
echo "si-veille installé. Premier passage :"; python3 "$APP/si_veille.py" --une-fois || true
echo "Essai des notifications : si-veille --tester-notif"
