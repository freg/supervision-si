#!/bin/sh
# si-mailbox (#840) : installation dans la SESSION de l'utilisateur (sans root). Linux (systemd --user) ou macOS (LaunchAgent).
# Usage : sh mailbox/installer.sh            (installe ou met à jour, démarre, affiche l'adresse de l'écran)
#         sh mailbox/installer.sh --retirer   (arrête et retire le service ; configuration et journal gardés)
set -eu
ICI="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/.local/share/si-mailbox/app"
command -v python3 >/dev/null || { echo "python3 requis" >&2; exit 1; }
if [ "${1:-}" = "--retirer" ]; then
  if [ "$(uname)" = Darwin ]; then launchctl unload "$HOME/Library/LaunchAgents/fr.exemple.si-mailbox.plist" 2>/dev/null || true; rm -f "$HOME/Library/LaunchAgents/fr.exemple.si-mailbox.plist"
  else systemctl --user disable --now si-mailbox.service 2>/dev/null || true; rm -f "$HOME/.config/systemd/user/si-mailbox.service"; systemctl --user daemon-reload 2>/dev/null || true; fi
  rm -f "$HOME/.local/bin/si-mailbox"; echo "si-mailbox retiré (configuration ~/.config/si-mailbox et journal ~/.local/share/si-mailbox gardés)"; exit 0
fi
mkdir -p "$APP" "$HOME/.local/bin" "$HOME/.config/si-mailbox/scripts"
chmod 700 "$HOME/.config/si-mailbox" "$HOME/.local/share/si-mailbox"
install -m 0755 "$ICI/mailbox_agent.py" "$APP/mailbox_agent.py"
install -m 0644 "$ICI/ecran.html" "$APP/ecran.html"
for s in "$ICI"/scripts-exemples/*; do [ -f "$s" ] && [ ! -e "$HOME/.config/si-mailbox/scripts/$(basename "$s")" ] && install -m 0700 "$s" "$HOME/.config/si-mailbox/scripts/"; done
printf '#!/bin/sh\nexec python3 "%s/mailbox_agent.py" "$@"\n' "$APP" > "$HOME/.local/bin/si-mailbox"; chmod 755 "$HOME/.local/bin/si-mailbox"
if [ "$(uname)" = Darwin ]; then
  P="$HOME/Library/LaunchAgents/fr.exemple.si-mailbox.plist"; mkdir -p "$(dirname "$P")"
  cat > "$P" <<PL
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict><key>Label</key><string>fr.exemple.si-mailbox</string>
<key>ProgramArguments</key><array><string>$(command -v python3)</string><string>$APP/mailbox_agent.py</string></array>
<key>RunAtLoad</key><true/><key>KeepAlive</key><true/>
<key>StandardOutPath</key><string>$HOME/.local/share/si-mailbox/service.log</string><key>StandardErrorPath</key><string>$HOME/.local/share/si-mailbox/service.log</string>
</dict></plist>
PL
  launchctl unload "$P" 2>/dev/null || true; launchctl load "$P"
else
  mkdir -p "$HOME/.config/systemd/user"
  cat > "$HOME/.config/systemd/user/si-mailbox.service" <<UN
[Unit]
Description=si-mailbox -- agent de messagerie de la session (écran local 127.0.0.1:8095)
[Service]
ExecStart=$(command -v python3) $APP/mailbox_agent.py
Restart=on-failure
RestartSec=10
[Install]
WantedBy=default.target
UN
  systemctl --user daemon-reload && systemctl --user enable --now si-mailbox.service >/dev/null && systemctl --user restart si-mailbox.service
fi
sleep 2
echo "si-mailbox installé (mode discret par défaut : aucune liaison avec le hub)."
echo "Écran : $(python3 "$APP/mailbox_agent.py" --ouvrir)"
