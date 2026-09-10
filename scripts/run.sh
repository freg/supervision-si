#!/usr/bin/env bash
# Lance Docker Compose en injectant automatiquement l'IP de la machine
# courante dans HOST_IP, utilisée par le frontend pour joindre l'API
# depuis le navigateur (voir commentaire dans docker-compose.yml).
#
# Usage : ./scripts/run.sh [arguments passés tels quels à docker compose]
#   ./scripts/run.sh up --build
#   ./scripts/run.sh up --build frontend
#   ./scripts/run.sh down
#
# Keycloak + tls-proxy VIVENT DÉSORMAIS ailleurs (backlog, livraison
# #135) : voir gateway/scripts/run.sh pour reset-keycloak/restore-groups
# et le démarrage du proxy/Keycloak lui-même -- ce script-ci ne gère
# plus que les ~20 services applicatifs du stack principal.
#
# Raccourci pratique pour le cycle "down puis rebuild" habituel en
# développement, SANS jamais toucher à gateway/vault-standalone :
# voir scripts/chantier.sh (livraison #149).

set -euo pipefail

# Garde-fou contre une confusion réelle rencontrée : "all"/"main"/
# "vault-standalone"/"gateway" sont des CIBLES du script CENTRAL
# (scripts/run-all.sh), jamais des sous-commandes reconnues ICI --
# transmis tel quel à "docker compose", ça échoue avec un message
# Docker peu clair ("unknown docker command"). Détecté avant même la
# détection HOST_IP, pour échouer vite et clairement plutôt que de
# faire tout le travail de rendu pour rien.
case "${1:-}" in
  all|main|vault-standalone|gateway)
    echo "❌ '$1' n'est pas une sous-commande de ce script -- c'est une CIBLE du" >&2
    echo "   point d'entrée central scripts/run-all.sh. Vouliez-vous plutôt :" >&2
    echo "" >&2
    echo "     ./scripts/run-all.sh $*" >&2
    echo "" >&2
    echo "   (ce script-ci, scripts/run.sh, ne gère QUE le stack principal --" >&2
    echo "   appelé directement, sans argument de cible.)" >&2
    exit 1
    ;;
esac

HERE_DIR="$(dirname "$0")/.."
# export -- ajouté après un cas réel où omettre l'export empêchait
# shared/VERSION.json d'être trouvé par "docker compose build" malgré
# une génération réussie au bon endroit (voir VERSION_FILE plus bas) :
# mécanisme exact non identifié avec certitude (HERE_DIR n'est
# référencé nulle part ailleurs dans docker-compose.yml ni les
# Dockerfiles), mais le correctif est sans risque -- exporter cette
# variable ne peut rien casser, même là où ce n'était apparemment pas
# strictement nécessaire.
export HERE_DIR

# Réseau Docker PARTAGÉ avec gateway/ (livraison #135) -- créé de
# façon IDEMPOTENTE, voir gateway/docker-compose.yml (en-tête) pour le
# raisonnement complet. Peu importe lequel des deux run.sh démarre en
# premier.
NETWORK_NAME="${SUPERVISION_SI_NETWORK_NAME:-supervision-si-net}"
docker network create "$NETWORK_NAME" >/dev/null 2>&1 || true

# HOST_IP -- toujours nécessaire ICI (pas seulement côté gateway) :
# les services applicatifs (frontend, hub, tickets-portal...)
# l'utilisent pour construire leurs propres URLs vers Keycloak/le
# proxy (VITE_KEYCLOAK_URL etc.), même si Keycloak/tls-proxy tournent
# désormais dans un stack séparé.
#
# Détection via shared/detect-host-ip.sh (livraison #342) -- corrige
# un piège macOS réel : `hostname -I` (seule méthode utilisée avant
# cette livraison) N'EXISTE PAS sur macOS (BSD hostname, contrairement
# à GNU coreutils/Linux), échouait silencieusement (stderr supprimé),
# laissant HOST_IP vide -- voir shared/detect-host-ip.sh pour le
# détail complet et l'ordre d'essai (macOS d'abord, Linux ensuite).
source "$HERE_DIR/shared/detect-host-ip.sh"
if [ -z "${HOST_IP:-}" ]; then
  HOST_IP="$(detect_host_ip)"
fi
export HOST_IP

# Si la détection automatique ne convient pas à ta configuration (VPN,
# plusieurs cartes réseau), exporte HOST_IP toi-même avant d'appeler ce
# script pour forcer une valeur précise, ex :
#   HOST_IP=192.168.1.42 ./scripts/run.sh up --build
if [ -z "$HOST_IP" ]; then
  echo "Impossible de détecter automatiquement l'IP — définis HOST_IP manuellement :" >&2
  echo "  HOST_IP=<ton_ip> ./scripts/run.sh $*" >&2
  exit 1
fi

echo "HOST_IP détectée : $HOST_IP"

# Échec d'une étape de préparation (ex. vérification .env) = ARRÊT,
# jamais un démarrage partiel avec une config potentiellement
# périmée/incohérente. `set -e` arrête déjà le script à la ligne
# fautive, mais silencieusement du point de vue de la personne qui lit
# le terminal — ce message la rend impossible à manquer (rencontré en
# conditions réelles : un échec passé inaperçu, la stack jamais
# relancée sans que ce soit évident).
fail() {
  echo "" >&2
  echo "❌ ARRÊT — la stack Docker n'a PAS été (re)lancée. Voir l'erreur ci-dessus." >&2
  echo "" >&2
  exit 1
}

# Vérification précoce de .env (livraison #346) -- voir
# gateway/scripts/run.sh pour le raisonnement complet (même piège,
# jamais dupliqué au-delà de ce qui est nécessaire ici).
if [ ! -f "$HERE_DIR/.env" ]; then
  echo "❌ $HERE_DIR/.env introuvable." >&2
  echo "" >&2
  echo "   .env n'est JAMAIS inclus dans une livraison (secret, exclu du zip) --" >&2
  echo "   à générer une première fois après CHAQUE nouvelle extraction :" >&2
  echo "" >&2
  echo "     ./scripts/generate-env.sh" >&2
  echo "" >&2
  fail
fi

# Cohérence .env / docker-compose.yml / disque -- PUREMENT informatif
# (jamais || fail derrière, contrairement aux étapes ci-dessous) :
# chemins référencés mais absents du disque, variables utilisées mais
# manquantes dans .env, ou l'inverse. Demandé explicitement après une
# confusion réelle sur l'état du déploiement.
if command -v python3 >/dev/null 2>&1; then
  python3 "$(dirname "$0")/check-env.py"
  echo ""
fi

# Rendu Keycloak/PKI/config nginx SORTIS d'ici (livraison #135) --
# voir gateway/scripts/run.sh, qui gère désormais Keycloak/tls-proxy
# dans leur propre stack.

# Fichier de version -- généré à CHAQUE lancement, mais basé sur le
# CONTENU réel des fichiers (hash), PAS un horodatage brut : sans ça,
# lancer "--build" par habitude sur une version inchangée (retour
# réel : c'est exactement ce que fait la personne systématiquement)
# ferait quand même changer la version affichée à chaque fois,
# rendant le numéro inutile comme indicateur de "est-ce vraiment une
# nouvelle version ?". Le hash, lui, reste identique tant que rien
# n'a changé, peu importe le nombre de rebuilds. last_checked_at
# reste purement informatif (à part), jamais utilisé comme identifiant
# de version. Copié comme les autres fichiers partagés (theme.css,
# preferences.js...) dans chaque service qui l'utilise, voir
# shared/README.md.
#
# CHANGELOG.md/ENV_CHANGELOG.md volontairement EXCLUS du hash --
# demandé explicitement : que chaque entrée de changelog référence le
# hash de version correspondant. Si ces fichiers comptaient dans le
# calcul, y ÉCRIRE le hash changerait le hash lui-même (problème
# auto-référentiel) -- les exclure les traite comme des métadonnées
# À PROPOS du code, jamais comme une partie du code fonctionnel.
#
# ssh-tunnels/keys/ et ssh-tunnels/mounts/ EXCLUS depuis la livraison
# #185 -- bug RÉEL rencontré par la personne : `set -euo pipefail`
# (voir en-tête) fait échouer TOUT le script, silencieusement, si UN
# SEUL fichier fait échouer `sha256sum` dans ce pipe (clé privée
# illisible pour une raison quelconque, ou pire, un montage FUSE
# MORT sous ssh-tunnels/mounts/ -- lire à travers un montage cassé
# peut faire planter la lecture). Le symptôme était déroutant :
# aucun message d'erreur visible, juste le script qui s'arrête net
# après l'affichage de check-env.py, sans jamais atteindre `docker
# compose`. Ces deux dossiers ne représentent de toute façon jamais
# du CODE (clés/points de montage, contenu variable et sensible) --
# les exclure ici suit le MÊME raisonnement que leur exclusion déjà
# en place dans le calcul de hash de LIVRAISON (voir les messages de
# livraison successifs dans CHANGELOG.md).
#
# CORRECTIF #188 -- le correctif #185 ci-dessus (`-not -path
# ".../ssh-tunnels/mounts/*"`) N'A PAS SUFFI EN CONDITIONS RÉELLES :
# `-not -path` ne fait que FILTRER le résultat APRÈS COUP -- `find`
# essaie quand même de LIRE (stat) chaque entrée du dossier PENDANT
# qu'il le parcourt, AVANT d'appliquer ce filtre. Sur un montage FUSE
# mort, cette simple tentative de lecture échoue déjà ("Transport
# endpoint is not connected"), qu'elle soit ensuite filtrée ou non --
# confirmé en conditions réelles par la personne (l'erreur `find`
# citait explicitement le point de montage mort, MALGRÉ le filtre
# déjà en place). Corrigé : `-prune`, qui empêche `find` de même
# ENTRER dans le dossier ciblé -- testé et confirmé structurellement
# différent de `-not -path` (voir CHANGELOG.md #188 pour le test).
VERSION_FILE="$HERE_DIR/shared/VERSION.json"
CONTENT_HASH="$(find "$HERE_DIR" \
  \( -path "*/node_modules" -o \
     -path "*/__pycache__" -o \
     -path "*/.git" -o \
     -path "*/keycloak/import" -o \
     -path "*/keycloak/backup" -o \
     -path "*/pki/ca" -o \
     -path "*/pki/server" -o \
     -path "*/tls-proxy/generated" -o \
     -path "*/apache/generated" -o \
     -path "*/data" -o \
     -path "*/ssh-tunnels/keys" -o \
     -path "*/ssh-tunnels/mounts" \) -prune -o \
  -type f \
  -not -name "VERSION.json" \
  -not -name ".env" \
  -not -name ".env.example" \
  -not -name ".last-imported-realm.json" \
  -not -name "CHANGELOG.md" \
  -not -name "ENV_CHANGELOG.md" \
  -print0 2>/dev/null | sort -z | xargs -0 sha256sum 2>/dev/null | sha256sum | cut -c1-12)"
GIT_HASH="$(cd "$HERE_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "sans-git")"
LAST_CHECKED_AT="$(date -u +%FT%TZ)"
# DELIVERY_NUMBER -- demandé explicitement (vérification visuelle
# rapide de la version en cours de test, un simple hash ne permettant
# pas de voir d'un coup d'œil "est-ce plus récent que ce que j'ai
# testé avant ?"). Contrairement au hash ci-dessus (recalculé à
# chaque exécution à partir du contenu réel), ce nombre n'est JAMAIS
# recalculé ici -- lu tel quel depuis un fichier committé
# (shared/DELIVERY_NUMBER), incrémenté manuellement à chaque
# livraison. Absent (déploiement antérieur à ce mécanisme) -- "?"
# explicite, jamais une erreur.
DELIVERY_NUMBER_FILE="$HERE_DIR/shared/DELIVERY_NUMBER"
if [ -f "$DELIVERY_NUMBER_FILE" ]; then
  DELIVERY_NUMBER="$(tr -d '[:space:]' < "$DELIVERY_NUMBER_FILE")"
else
  DELIVERY_NUMBER="?"
fi
printf '{"content_hash": "%s", "git_hash": "%s", "last_checked_at": "%s", "delivery_number": "%s"}\n' \
  "$CONTENT_HASH" "$GIT_HASH" "$LAST_CHECKED_AT" "$DELIVERY_NUMBER" > "$VERSION_FILE"
echo "Version (hash du contenu) : $CONTENT_HASH -- livraison #$DELIVERY_NUMBER"
# Inventaire d'exposition (livraison #455) -- shared/EXPOSURE.json, lu par
# si-proxy-admin-api pour l'onglet « Entrées » de la console Bastion :
# routes de la passerelle + ports publiés directement + réseau hôte,
# d'après docker-compose.yml et tls-proxy (jamais maintenu à la main).
python3 "$HERE_DIR/scripts/render-exposure.py" || echo "avertissement : inventaire d'exposition non régénéré (EXPOSURE.json committé conservé)"

# Détection de changement du realm Keycloak, PKI, config nginx --
# SORTIS d'ici (livraison #135), voir gateway/scripts/run.sh. Ce
# script-ci ne gère plus que les ~20 services applicatifs -- un simple
# docker compose suffit, plus de marqueur/confirmation à gérer ici.
# Secrets de démarrage CHIFFRÉS (livraison #205, suite des points 2/3
# de l'urgence matrice de risque -- voir docs/chiffrement-secrets.md
# et docs/pra-secrets-demarrage.docx pour le détail complet).
# `.env.encrypted` OPTIONNEL : absent = comportement EXACTEMENT
# inchangé (personne n'a pas encore migré vers le chiffrement, .env
# classique utilisé tel quel, aucune invite supplémentaire). Présent
# = la phrase de passe maîtresse est RESAISIE à CHAQUE lancement --
# jamais stockée sur disque, jamais dans une variable d'environnement
# persistante -- puis les secrets déchiffrés sont exportés dans CE
# SEUL processus shell, pour la durée de cet appel à docker compose
# uniquement (rien ne survit après la fin du script).
#
# Limite connue, sans conséquence fonctionnelle : check-env.py
# (ci-dessus) compare .env à docker-compose.yml AVANT ce déchiffrement
# -- une variable migrée vers .env.encrypted peut donc apparaître à
# tort comme "absente de .env" dans son rapport, purement informatif.
ENV_ENCRYPTED_FILE="$HERE_DIR/.env.encrypted"
if [ -f "$ENV_ENCRYPTED_FILE" ]; then
  echo ""
  echo "🔐 Secrets chiffrés détectés ($ENV_ENCRYPTED_FILE) :"
  DECRYPTED_EXPORTS="$(python3 "$HERE_DIR/scripts/secrets_tool.py" decrypt-env --input "$ENV_ENCRYPTED_FILE")" || fail
  eval "$DECRYPTED_EXPORTS"
  echo "✅ Secrets déchiffrés, injectés pour ce lancement uniquement."
fi

docker compose "$@"
