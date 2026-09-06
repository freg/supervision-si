#!/usr/bin/env bash
# install.sh -- déploiement AUTOMATISÉ, SANS INTERVENTION MANUELLE,
# adapté à l'environnement détecté. Demandé explicitement (2026-09-05,
# livraison #374) après une session de déploiement particulièrement
# difficile (OOM Keycloak, LDAP mal configuré, volume externe non
# purgé...) : "une archive et un script qui déploie sans intervention
# manuelle avec une config complète d'exemples et une évaluation
# initiale de l'environnement pour cadrer les services déployés qui
# s'adapte à l'os".
#
# CE QUE CE SCRIPT FAIT :
# - Vérifie Docker présent/démarré/plugin compose v2 (pas l'ancien
#   binaire "docker-compose" standalone séparé).
# - Détecte la mémoire RÉELLEMENT disponible POUR DOCKER (pas la RAM
#   totale de la machine) via `docker info --format '{{.MemTotal}}'`
#   -- une SEULE commande, valable identiquement sur macOS (reflète
#   l'allocation de la VM Docker Desktop) et Linux natif (reflète la
#   RAM hôte réelle, confirmé par la documentation Docker officielle).
# - Choisit un périmètre de déploiement selon cette mémoire détectée
#   (voir seuils ci-dessous -- des ESTIMATIONS prudentes basées sur
#   l'observation réelle d'un déploiement à 4 Go, PAS une science
#   exacte -- ajustables si l'expérience montre qu'ils sont mal
#   calibrés).
# - Génère .env automatiquement si absent (SANS DANGER sur une
#   première installation -- generate-env.sh ne demande confirmation
#   que si .env EXISTE déjà, jamais sur un dossier neuf).
# - Déploie le périmètre choisi via les scripts déjà existants
#   (run-all.sh / chantier.sh --minimal) -- AUCUNE invite interactive
#   ne se déclenche sur un environnement réellement neuf (vérifié :
#   les deux garde-fous LDAP/realm de gateway/scripts/run.sh sont
#   tous les deux gated derrière un état PRÉEXISTANT -- volume Keycloak
#   déjà là, ou placeholder resté dans un .env DÉJÀ présent -- aucun
#   des deux ne peut exister sur un premier déploiement).
#
# CE QUE CE SCRIPT NE FAIT JAMAIS :
# - Ne force JAMAIS un choix de périmètre différent de celui détecté
#   sans le dire clairement (voir résumé final).
# - Ne réécrit JAMAIS un .env déjà présent (le laisse tel quel,
#   respecte tout ajustement manuel déjà fait).
# - Ne configure AUCUN système externe réel (LDAP réel, GLPI, IMAP,
#   Nebula...) -- reste un déploiement de DÉMONSTRATION/TEST avec
#   l'annuaire LDAP de test intégré, comme le reste de ce projet.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

echo "=================================================================="
echo " Installation automatisée -- supervision-si"
echo "=================================================================="
echo ""

# --- 1. Docker présent et démarré -----------------------------------
if ! command -v docker >/dev/null 2>&1; then
  echo "❌ Docker introuvable dans le PATH." >&2
  echo "   Installez Docker Desktop (macOS/Windows) ou Docker Engine (Linux)" >&2
  echo "   puis relancez ce script." >&2
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker ne répond pas (pas démarré ?)." >&2
  echo "   Démarrez Docker Desktop (ou le service Docker sur Linux :" >&2
  echo "   'sudo systemctl start docker') puis relancez ce script." >&2
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "❌ 'docker compose' (plugin v2) introuvable." >&2
  echo "   Ce projet utilise la syntaxe 'docker compose' (espace), pas" >&2
  echo "   l'ancien binaire autonome 'docker-compose' (tiret) -- mettez" >&2
  echo "   à jour Docker Desktop, ou installez le plugin compose v2 sur Linux." >&2
  exit 1
fi

echo "✅ Docker présent et démarré ($(docker --version))"
echo ""

# --- 2. Détection mémoire disponible POUR DOCKER ---------------------
MEM_BYTES="$(docker info --format '{{.MemTotal}}' 2>/dev/null || echo 0)"
if [ "$MEM_BYTES" -le 0 ] 2>/dev/null; then
  MEM_BYTES=0
fi
MEM_GB=$(( MEM_BYTES / 1024 / 1024 / 1024 ))

echo "Mémoire disponible pour Docker : ${MEM_GB} Go"
echo "(détectée via 'docker info' -- reflète l'allocation de la VM"
echo " Docker Desktop sur macOS, la RAM hôte réelle sur Linux natif)"
echo ""

# --- 3. Décision du périmètre de déploiement -------------------------
# Seuils choisis par PRUDENCE, pas par mesure scientifique -- voir
# CHANGELOG.md #374 pour le raisonnement complet et le contexte réel
# qui les a motivés (un déploiement à 4 Go où même "gateway + main"
# semblait tendu).
WARNED_LOW_MEM=0
if [ "$MEM_GB" -lt 3 ]; then
  SCOPE="gateway-main-minimal"
  WARNED_LOW_MEM=1
elif [ "$MEM_GB" -lt 6 ]; then
  SCOPE="gateway-main-minimal"
elif [ "$MEM_GB" -lt 10 ]; then
  SCOPE="gateway-main-full"
else
  SCOPE="all"
fi

if [ "$WARNED_LOW_MEM" -eq 1 ]; then
  echo "⚠️  Moins de 3 Go détectés pour Docker -- ce projet compte des"
  echo "    dizaines de conteneurs, ce périmètre minimal reste une"
  echo "    TENTATIVE, pas une garantie de stabilité à cette allocation."
  echo ""
  echo "    Si Keycloak (ou autre chose) se fait tuer par manque de"
  echo "    mémoire (code de sortie 137, \"Killed\" dans les journaux),"
  echo "    augmentez l'allocation Docker Desktop (Réglages -> Ressources"
  echo "    -> Mémoire) si votre machine le permet, ou réduisez encore"
  echo "    le périmètre (voir './scripts/chantier.sh build --minimal'"
  echo "    et 'gateway/README.md')."
  echo ""
fi

case "$SCOPE" in
  gateway-main-minimal)
    echo "Périmètre choisi : gateway + main (sous-ensemble minimal)"
    echo "  -> hub accessible, tickets/tâches/GED opérationnels."
    echo "  -> mayan/ (documents RÉELS via GED) et vault-standalone/ non"
    echo "     démarrés -- lancer './scripts/run-all.sh mayan up -d --build'"
    echo "     et/ou './scripts/run-all.sh vault-standalone up -d --build'"
    echo "     séparément si besoin, une fois la mémoire vérifiée suffisante."
    ;;
  gateway-main-full)
    echo "Périmètre choisi : gateway + main (complet)"
    echo "  -> hub et tous ses modules accessibles."
    echo "  -> mayan/ (documents RÉELS via GED) et vault-standalone/ non"
    echo "     démarrés -- lancer séparément si besoin."
    ;;
  all)
    echo "Périmètre choisi : all (gateway + mayan + main + vault-standalone)"
    echo "  -> stack complet, toutes fonctionnalités disponibles."
    ;;
esac
echo ""

# --- 4. Génération .env (sans danger sur une première installation) -
if [ ! -f .env ]; then
  echo "→ .env absent -- génération automatique (première installation)..."
  echo ""
  ./scripts/generate-env.sh
  echo ""
else
  echo "→ .env déjà présent -- conservé tel quel (aucune régénération"
  echo "  automatique, pour respecter tout ajustement manuel déjà fait)."
  echo ""
fi

# --- 5. Déploiement du périmètre choisi -------------------------------
echo "=================================================================="
echo " Déploiement en cours..."
echo "=================================================================="
echo ""

case "$SCOPE" in
  gateway-main-minimal)
    ./scripts/run-all.sh gateway up -d --build
    ./scripts/chantier.sh build --minimal
    ;;
  gateway-main-full)
    ./scripts/run-all.sh gateway up -d --build
    ./scripts/run-all.sh main up -d --build
    ;;
  all)
    ./scripts/run-all.sh all up -d --build
    ;;
esac

# --- 6. Résumé final ---------------------------------------------------
source "$PROJECT_ROOT/shared/detect-host-ip.sh"
DETECTED_IP="$(detect_host_ip)"
GATEWAY_PORT_VALUE="$(grep -E '^GATEWAY_PORT=' .env 2>/dev/null | cut -d= -f2-)"
GATEWAY_PORT_VALUE="${GATEWAY_PORT_VALUE:-6443}"

echo ""
echo "=================================================================="
echo " Déploiement terminé"
echo "=================================================================="
echo ""
echo "Hub accessible sur : https://${DETECTED_IP:-localhost}:${GATEWAY_PORT_VALUE}/"
echo "(certificat auto-signé -- votre navigateur affichera un"
echo " avertissement à accepter manuellement la première fois)"
echo ""
echo "Compte de test LDAP : alice (ou bob), mot de passe : password"
echo ""
echo "Pour connecter de VRAIS systèmes externes (LDAP réel, GLPI, IMAP,"
echo "OwnCloud, Cacti, Optick, Zenoss, IPAM, Nebula, TRB140...), éditez"
echo ".env directement -- .env.example documente CHAQUE variable en"
echo "détail, section par section. Voir aussi le README.md de chaque"
echo "module concerné pour ce qui est spécifiquement attendu."
echo ""
echo "Pour ajuster le périmètre déployé plus tard :"
echo "  ./scripts/run-all.sh mayan up -d --build           # documents réels (Mayan)"
echo "  ./scripts/run-all.sh vault-standalone up -d --build # coffre-fort isolé"
echo "  ./scripts/chantier.sh build --minimal <service>     # ajouter UN service précis"
echo ""
echo "En cas de problème, consultez CHANGELOG.md (section la plus"
echo "récente) et le README.md du module concerné -- ce projet documente"
echo "systématiquement chaque bug réel rencontré en déploiement."
