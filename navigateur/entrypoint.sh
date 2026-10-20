#!/bin/sh
# Écran virtuel + gestionnaire de fenêtres + Chromium (relancé s'il est fermé) + VNC local + noVNC + automate.
# Tout écoute sur 127.0.0.1 (réseau de l'hôte) : l'écran est publié par le bastion du hub, l'automate n'est appelé
# que par l'agent si-agent de l'hôte.
set -e
: "${NAV_JETON:?NAV_JETON manquant (.env)}"
: "${NAV_VNC_MDP:?NAV_VNC_MDP manquant (.env)}"
ECRAN="${NAV_ECRAN:-1366x900}"
L="${ECRAN%x*}"; H="${ECRAN#*x}"
export DISPLAY=:${NAV_DISPLAY:-77}
Xvfb "$DISPLAY" -screen 0 "${ECRAN}x24" -nolisten tcp >/tmp/xvfb.log 2>&1 &
sleep 1
fluxbox >/tmp/fluxbox.log 2>&1 &
x11vnc -storepasswd "$NAV_VNC_MDP" /tmp/vncpass >/dev/null 2>&1
x11vnc -display "$DISPLAY" -rfbauth /tmp/vncpass -forever -shared -localhost -rfbport "${NAV_VNC_PORT:-5977}" -quiet >/tmp/x11vnc.log 2>&1 &
websockify --web /usr/share/novnc "127.0.0.1:${NAV_ECRAN_PORT:-6080}" "127.0.0.1:${NAV_VNC_PORT:-5977}" >/tmp/websockify.log 2>&1 &
CHROME="${NAV_CHROME:-$(ls -d /ms-playwright/chromium-*/chrome-linux/chrome 2>/dev/null | head -1)}"
[ -x "$CHROME" ] || { echo "Chromium introuvable dans l'image" >&2; exit 1; }
(
  while true; do
    "$CHROME" --no-first-run --no-default-browser-check --password-store=basic --user-data-dir=/profil \
      --remote-debugging-address=127.0.0.1 --remote-debugging-port="${NAV_CDP_PORT:-9222}" \
      --window-position=0,0 --window-size="$L,$H" --start-maximized --disable-dev-shm-usage --lang=fr-FR \
      "${NAV_ACCUEIL:-about:blank}" >/tmp/chrome.log 2>&1
    sleep 2      # fermé à la main ou planté : relancé, profil conservé
  done
) &
sleep 2
export NAV_CDP="http://127.0.0.1:${NAV_CDP_PORT:-9222}"
exec python3 /app/automate.py "${NAV_API_PORT:-8094}"
