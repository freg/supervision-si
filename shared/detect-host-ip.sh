#!/usr/bin/env bash
# Détection de HOST_IP -- FONCTION partagée par tous les run.sh du
# projet (scripts/, gateway/scripts/, mayan/scripts/,
# scripts/generate-env.sh) -- jamais dupliquée séparément dans
# chacun, corrigé une seule fois ici après un vrai piège macOS
# rencontré par la personne (2026-09-05, en pleine tentative de
# déploiement) : `hostname -I` (utilisé jusque-là, seule méthode)
# N'EXISTE PAS sur macOS -- BSD `hostname` ne supporte pas ce
# flag (spécifique GNU coreutils/Linux), contrairement à ce que ce
# projet supposait implicitement partout où HOST_IP était détectée.
# Sur macOS, `hostname -I` échoue silencieusement (stderr supprimé
# par tous les appelants), HOST_IP reste vide -- chaque script échoue
# ensuite avec SON PROPRE message "impossible de détecter", jamais un
# crash, mais un dénominateur commun jamais corrigé avant cette
# livraison malgré son usage à 4 endroits distincts.
#
# Usage (à SOURCER, jamais exécuté directement) :
#   source "$PROJECT_ROOT/shared/detect-host-ip.sh"
#   HOST_IP="$(detect_host_ip)"
#
# Ordre d'essai : macOS (ipconfig sur les interfaces les plus
# courantes) -- Linux (ip route, puis hostname -I en dernier
# recours) -- vide si tout échoue, à l'appelant de décider quoi en
# faire (chaque run.sh a déjà sa propre vérification explicite pour
# ce cas, jamais dupliquée ici).
detect_host_ip() {
  local ip=""
  if command -v ipconfig >/dev/null 2>&1; then
    ip="$(ipconfig getifaddr en0 2>/dev/null || true)"
    [ -z "$ip" ] && ip="$(ipconfig getifaddr en1 2>/dev/null || true)"
  fi
  if [ -z "$ip" ] && command -v ip >/dev/null 2>&1; then
    ip="$(ip route get 1.1.1.1 2>/dev/null | grep -oE 'src [0-9.]+' | awk '{print $2}' || true)"
  fi
  if [ -z "$ip" ] && command -v hostname >/dev/null 2>&1; then
    ip="$(hostname -I 2>/dev/null | awk '{print $1}' || true)"
  fi
  echo "$ip"
}
