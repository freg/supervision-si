#!/bin/sh
# si-onglets (#848) : rouvrir les onglets du terminal à l'ouverture de la session (GNOME Terminal, sans root).
# Usage : sh poste-onglets/installer.sh            puis, depuis un des onglets ouverts : si-onglets --capturer
#         sh poste-onglets/installer.sh --retirer
set -eu
ICI="$(cd "$(dirname "$0")" && pwd)"
APP="$HOME/.local/share/si-onglets"; AUTO="$HOME/.config/autostart/si-onglets.desktop"
if [ "${1:-}" = "--retirer" ]; then
  rm -f "$AUTO" "$HOME/.local/bin/si-onglets"; echo "si-onglets retiré (onglets enregistrés gardés dans ~/.config/si-onglets)"; exit 0
fi
mkdir -p "$APP" "$HOME/.local/bin" "$HOME/.config/autostart"
install -m 0755 "$ICI/si_onglets.py" "$APP/si_onglets.py"
PY="$(command -v /usr/bin/python3 || command -v python3)"     # python du système : indépendant d'un environnement virtuel
printf '#!/bin/sh\nexec %s "%s/si_onglets.py" "$@"\n' "$PY" "$APP" > "$HOME/.local/bin/si-onglets"; chmod 755 "$HOME/.local/bin/si-onglets"
cat > "$AUTO" <<DT
[Desktop Entry]
Type=Application
Name=si-onglets
Comment=Rouvre la fenêtre de terminal et ses onglets
Exec=$HOME/.local/bin/si-onglets --ouvrir
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=3
DT
echo "si-onglets installé. Ouvre tes onglets comme d'habitude, puis depuis l'un d'eux : ~/.local/bin/si-onglets --capturer"
