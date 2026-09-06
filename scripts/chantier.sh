#!/usr/bin/env bash
# Redéploiement RAPIDE du stack "en chantier" (main -- les ~20
# services applicatifs) -- laisse gateway/ (Keycloak + tls-proxy) ET
# vault-standalone/ COMPLÈTEMENT intacts et en fonctionnement, jamais
# arrêtés ni reconstruits par ce script. Demandé explicitement
# (livraison #149) : pensé pour le cycle de développement habituel où
# Keycloak/le proxy TLS changent rarement une fois en place, alors
# que les services applicatifs sont redéployés à CHAQUE livraison --
# inutile de les faire redémarrer à chaque fois, et un
# `down`/`up --build` involontaire sur gateway/ romprait
# l'authentification en cours de tout le monde pour rien (déconnexion
# Keycloak forcée) sans le moindre bénéfice.
#
# Simple raccourci sur scripts/run.sh, qui ne gère DÉJÀ que le stack
# "main" (voir son en-tête) -- ne duplique aucune logique (détection
# HOST_IP, génération du fichier de version...), juste deux noms de
# sous-commandes plus courts et plus explicites que de retenir la
# bonne combinaison d'arguments docker compose à chaque fois.
#
# Rechargement AUTOMATIQUE de tls-proxy après "build" (livraison
# #162, demandé explicitement) -- le SEUL élément parmi les
# nouveautés récentes (schema-analyzer, ged, ssh-tunnels) qui échappe
# structurellement à un simple "up -d --build" : les autres sont des
# services ORDINAIRES du stack main, déjà bien gérés. tls-proxy, lui,
# lit sa config depuis un fichier monté en VOLUME
# (tls-proxy/generated/services.conf) -- Docker ne détecte PAS ce
# genre de changement comme justifiant un redémarrage de conteneur,
# contrairement à un changement d'IMAGE. Une route nouvellement
# ajoutée à tls-proxy/render_nginx_conf.py (SERVICES) reste donc
# invisible tant que tls-proxy n'est pas explicitement relancé --
# bug RÉEL rencontré deux fois (schema-analyzer #151, ged #157/#160),
# à chaque fois diagnostiqué à la main. Corrigé ici en régénérant la
# config PUIS en redémarrant tls-proxy, appel DIRECT à
# render_nginx_conf.py + `docker compose restart` -- JAMAIS via
# gateway/scripts/run.sh (qui déclencherait AUSSI le prompt de
# changement de realm Keycloak, totalement sans rapport ici).
# Échec NON BLOQUANT (gateway/ peut être arrêté ou pas encore lancé
# la première fois) -- un avertissement clair, jamais un `build`
# principal qui échoue à cause de ça.
#
# Piège RÉEL rencontré (livraison #165) : si
# tls-proxy/generated/services.conf a été créé une PREMIÈRE fois via
# `sudo gateway/scripts/run.sh ...` (root), ce script (lancé SANS
# sudo) ne peut plus l'écraser ensuite -- render_nginx_conf.py
# affiche désormais un message clair avec la commande de correction
# (`sudo chown $(id -u):$(id -g) ...`) plutôt qu'une trace Python
# brute, mais le fichier reste À CORRIGER MANUELLEMENT une fois --
# voir ce message si "build" affiche une erreur de permission ici.
#
# Usage :
#   ./scripts/chantier.sh down [args docker compose supplémentaires]
#   ./scripts/chantier.sh build [args docker compose supplémentaires]
#
#   ./scripts/chantier.sh down              # arrête SEULEMENT main
#   ./scripts/chantier.sh down -v           # idem + supprime les volumes
#   ./scripts/chantier.sh build             # reconstruit + relance SEULEMENT main, puis recharge tls-proxy
#   ./scripts/chantier.sh build prefs-api   # reconstruit + relance un seul service, puis recharge tls-proxy
#
# "build" = up -d --build (jamais un simple "docker compose build" qui
# laisserait les anciens conteneurs tourner avec l'ancienne image --
# le cycle normal de redéploiement en développement est TOUJOURS
# "reconstruire ET relancer", pas l'un sans l'autre).
set -euo pipefail

HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_SH="$HERE_DIR/scripts/run.sh"
GATEWAY_DIR="$HERE_DIR/gateway"

# --minimal (livraison #367, demandé explicitement -- personne sur
# machine à mémoire limitée, voir README.md section "Mémoire Docker
# Desktop limitée") : sous-ensemble curé du stack main, PAS une
# résolution automatique via `depends_on` -- vérifié qu'AUCUN des
# services ci-dessous ne déclare de `depends_on` complet dans
# docker-compose.yml (seul tasks-api en a un, vers memcached
# uniquement) -- lister EXPLICITEMENT chaque dépendance réelle plutôt
# que de compter sur Docker Compose pour les découvrir tout seul.
#
# Défini pour satisfaire "hub ET ses fonctionnalités les plus
# utilisées (tickets, tâches, GED) opérationnelles" (réponse exacte
# de la personne) :
#   - hub, prefs-api : le hub lui-même + ses préférences/personnalisation
#   - memcached : tampon de logs PARTAGÉ par tous les services
#     ci-dessous (voir shared/log_buffer.py) -- sans lui, chacun log
#     silencieusement dans le vide, pas un échec bloquant mais à
#     inclure systématiquement
#   - tickets-api + tickets-postgres : la base est un conteneur
#     SÉPARÉ (PGHOST=tickets-postgres), jamais démarré tout seul par
#     un depends_on ici
#   - tasks-api : dépend déjà de memcached via son propre depends_on,
#     listé explicitement quand même par clarté
#   - ged-api : ⚠️ NE STOCKE/LIT AUCUN document réel sans la stack
#     `mayan` SÉPARÉE (MAYAN_BASE=http://mayan-app:8000, docker-compose.yml)
#     -- ce script (chantier.sh) ne gère QUE "main" par conception (voir
#     en-tête du fichier), --minimal ne peut donc PAS démarrer mayan à
#     sa place. Avertissement affiché à l'usage plutôt que silencieux.
#
# ⚠️ MAINTENANCE ATTENDUE À CHAQUE LIVRAISON (demandé explicitement) :
# toute livraison qui ajoute ou modifie un service destiné à être
# testable "à la carte" doit se demander si CETTE LISTE a besoin d'un
# ajout -- soit en l'étendant directement si le service rejoint le
# "cœur" (rare), soit en rappelant dans le message de livraison que
# `--minimal <nouveau-service>` est la commande à utiliser pour
# tester CETTE livraison précise sans tout redéployer. Ne JAMAIS
# supposer que --minimal reste correct sans y repenser à chaque fois.
MINIMAL_SERVICES=(memcached tickets-postgres hub prefs-api tickets-api tasks-api ged-api)

print_usage() {
  echo "Usage : $0 <down|build> [--all] [--minimal] [args docker compose supplémentaires]"
  echo ""
  echo "Redéploie SEULEMENT le stack main (~20 services applicatifs) --"
  echo "gateway/ (Keycloak + tls-proxy) et vault-standalone/ restent"
  echo "intacts et en fonctionnement, jamais touchés par ce script --"
  echo "SAUF tls-proxy, rechargé (config + redémarrage) après \"build\","
  echo "jamais reconstruit ni arrêté, voir l'en-tête de ce fichier."
  echo ""
  echo "  down       -- arrête le stack main (docker compose down)"
  echo "  build      -- reconstruit + relance le stack main (up -d --build), puis recharge tls-proxy"
  echo "  build --all -- idem, PLUS recrée Keycloak (thèmes/realm) -- opt-in,"
  echo "                 jamais automatique (Keycloak sert d'autres consommateurs,"
  echo "                 ex. TRB140/SMS -- voir keycloak/themes/README.md)"
  echo "  build --minimal -- déploie SEULEMENT ${MINIMAL_SERVICES[*]}"
  echo "                 (hub + tickets/tâches/GED opérationnels) -- machine à"
  echo "                 mémoire limitée, voir README.md. ⚠️  GED répond mais ne"
  echo "                 stocke/lit aucun document réel sans la stack mayan/"
  echo "                 SÉPARÉE (./scripts/run-all.sh mayan up -d --build)."
  echo "  build --minimal <service> -- idem PLUS un service supplémentaire,"
  echo "                 typiquement celui touché par la livraison à tester"
  echo ""
  echo "Exemples :"
  echo "  $0 down"
  echo "  $0 down -v"
  echo "  $0 build"
  echo "  $0 build --all"
  echo "  $0 build prefs-api"
  echo "  $0 build --all prefs-api"
  echo "  $0 build --minimal"
  echo "  $0 build --minimal relations-api   # minimum + le service d'une livraison en cours de test"
}

reload_tls_proxy() {
  echo ""
  echo "🔁 Rechargement de tls-proxy (nouvelles routes éventuelles)…"
  if ! python3 "$HERE_DIR/tls-proxy/render_nginx_conf.py" >/dev/null; then
    echo "⚠️  Rendu de la config nginx échoué -- tls-proxy PAS rechargé, vérifier manuellement (tls-proxy/render_nginx_conf.py)." >&2
    return 0
  fi
  if ! docker compose \
      -p supervision-si-gateway \
      --env-file "$HERE_DIR/.env" \
      --project-directory "$HERE_DIR" \
      -f "$GATEWAY_DIR/docker-compose.yml" \
      restart tls-proxy 2>&1; then
    echo "⚠️  Redémarrage de tls-proxy échoué -- gateway/ est-il bien lancé ? (./scripts/run-all.sh gateway up -d --build)" >&2
    return 0
  fi
  echo "✅ tls-proxy rechargé."
}

# Option --all (livraison #299, corrigée en #300 après diagnostic
# complet en conditions réelles -- voir keycloak/themes/README.md
# pour le détail des fausses pistes éliminées une à une). Les
# fichiers de thème Keycloak sont bien à jour sur disque après un
# "build" classique (montage bind, lu en direct) -- mais le
# CONTENEUR Keycloak lui-même n'est jamais RECRÉÉ par ce chemin
# ("keycloak" vit dans gateway/docker-compose.yml, jamais ciblé par
# scripts/run.sh) -- ses montages restent figés à sa création
# INITIALE, quel que soit le nombre de "restart" lancés depuis (un
# "restart" ne recrée JAMAIS un conteneur, juste son processus).
# Reste VOLONTAIREMENT opt-in, jamais automatique : Keycloak sert
# d'AUTRES consommateurs (ex. TRB140/SMS) qui ne doivent jamais subir
# une coupure comme effet de bord d'un déploiement routinier sans
# rapport avec lui -- décision confirmée explicitement avec la
# personne.
#
# Usage :
#   ./scripts/chantier.sh build --all      # + recrée aussi Keycloak
#   ./scripts/chantier.sh build --all prefs-api   # combinable
recreate_keycloak() {
  echo ""
  echo "🔁 --all demandé : recréation de Keycloak (thèmes/realm potentiellement modifiés)…"
  # "up -d", JAMAIS "restart" seul (bug réel #300, diagnostiqué en
  # conditions réelles) -- "restart" relance le MÊME conteneur, ses
  # montages restent figés à ce qu'ils étaient à sa création INITIALE.
  # Si docker-compose.yml a changé depuis (nouveau chemin de montage,
  # nouvelle variable...), "restart" ne le voit JAMAIS -- seul "up -d"
  # relit la config actuelle et RECRÉE le conteneur si nécessaire.
  if ! docker compose \
      -p supervision-si-gateway \
      --env-file "$HERE_DIR/.env" \
      --project-directory "$HERE_DIR" \
      -f "$GATEWAY_DIR/docker-compose.yml" \
      up -d keycloak 2>&1; then
    echo "⚠️  Recréation de Keycloak échouée -- gateway/ est-il bien lancé ? (./scripts/run-all.sh gateway up -d --build)" >&2
    return 0
  fi
  echo "✅ Keycloak recréé (thèmes/realm rechargés)."
}

if [ $# -eq 0 ]; then
  print_usage
  exit 0
fi

case "$1" in
  down)
    shift
    exec "$RUN_SH" down "$@"
    ;;
  build)
    shift
    FORCE_ALL=0
    MINIMAL=0
    ARGS=()
    for arg in "$@"; do
      if [ "$arg" = "--all" ]; then
        FORCE_ALL=1
      elif [ "$arg" = "--minimal" ]; then
        MINIMAL=1
      else
        ARGS+=("$arg")
      fi
    done
    if [ "$MINIMAL" -eq 1 ]; then
      # ARGS (services supplémentaires explicites) s'AJOUTENT à
      # MINIMAL_SERVICES, jamais à la place -- typiquement le service
      # d'une livraison en cours de test (voir en-tête de ce fichier).
      # ⚠️ ${#ARGS[@]} testé AVANT toute expansion de "${ARGS[@]}" --
      # piège bash 3.2/macOS déjà rencontré une fois dans CE MÊME
      # fichier (voir plus haut, correctif --all) : un tableau VIDE
      # expansé directement sous `set -u` donne "unbound variable"
      # sur bash 3.2 (jamais sur bash 4+/Linux) -- `ARGS` est
      # PRÉCISÉMENT vide ici quand seul `--minimal` est passé, sans
      # service supplémentaire.
      if [ ${#ARGS[@]} -gt 0 ]; then
        ARGS=("${MINIMAL_SERVICES[@]}" "${ARGS[@]}")
      else
        ARGS=("${MINIMAL_SERVICES[@]}")
      fi
      echo "🔹 --minimal : déploiement limité à ${ARGS[*]}"
      echo "⚠️  ged-api répond mais ne stocke/lit aucun document réel sans la stack"
      echo "   mayan SÉPARÉE (./scripts/run-all.sh mayan up -d --build) -- voir"
      echo "   scripts/chantier.sh (en-tête) pour le détail complet."
      echo ""
    fi
    if [ ${#ARGS[@]} -gt 0 ]; then
      "$RUN_SH" up -d --build "${ARGS[@]}"
    else
      "$RUN_SH" up -d --build
    fi
    reload_tls_proxy
    if [ "$FORCE_ALL" -eq 1 ]; then
      recreate_keycloak
    fi
    ;;
  -h|--help|help)
    print_usage
    exit 0
    ;;
  *)
    echo "❌ Sous-commande inconnue : '$1'" >&2
    echo "" >&2
    print_usage >&2
    exit 1
    ;;
esac
