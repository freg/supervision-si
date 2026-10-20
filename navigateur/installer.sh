#!/bin/sh
# Installe le navigateur de l'hôte (#798) à côté de l'agent si-agent (Linux, Docker requis), en root :
#   cd /chemin/supervision-si/navigateur && sudo sh installer.sh
# Crée .env (jeton de l'automate, mot de passe de l'écran, 8 caractères : limite VNC), le dépose pour l'agent
# (/etc/si-agent/navigateur/jeton), construit et démarre le conteneur. Relancer le script ne change pas les secrets.
set -e
cd "$(dirname "$0")"
command -v docker >/dev/null || { echo "Docker requis (apt install docker.io docker-compose-v2)"; exit 1; }
if [ ! -f .env ]; then
  umask 077
  {
    echo "NAV_JETON=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')"
    echo "NAV_VNC_MDP=$(head -c 64 /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 8)"
    echo "NAV_ECRAN=1366x900"
    echo "NAV_ACCUEIL=about:blank"
    echo "NAV_ECRAN_PORT=6080"
    echo "NAV_API_PORT=8094"
  } > .env
  echo ".env créé (secrets générés)"
fi
mkdir -p /etc/si-agent/navigateur
grep '^NAV_JETON=' .env | cut -d= -f2- > /etc/si-agent/navigateur/jeton
grep '^NAV_API_PORT=' .env | cut -d= -f2- > /etc/si-agent/navigateur/port
chmod 600 /etc/si-agent/navigateur/jeton
docker compose up -d --build
echo
echo "Écran : 127.0.0.1:$(grep '^NAV_ECRAN_PORT=' .env | cut -d= -f2) (à publier par le bastion, voir navigateur/README.md)"
echo "Mot de passe de l'écran (à saisir dans le hub) : $(grep '^NAV_VNC_MDP=' .env | cut -d= -f2)"
