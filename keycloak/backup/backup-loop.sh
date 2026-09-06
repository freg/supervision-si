#!/bin/sh
# Boucle de sauvegarde AUTOMATIQUE et PÉRIODIQUE du realm Keycloak --
# authentifie via l'API Admin REST (client admin-cli, grant password),
# utilise partial-export (config realm, clients, rôles, groupes,
# fédération LDAP en tant que composant -- JAMAIS les comptes
# utilisateurs fédérés LDAP eux-mêmes, qui vivent dans l'annuaire, pas
# dans Keycloak, rien à en sauvegarder ici).
#
# `sh` pur (BusyBox ash sur alpine), volontairement PAS bash -- même
# leçon que pki/scripts/generate-server-cert.sh (bug réel rencontré
# avec une syntaxe bash sous /bin/sh=dash) : ce script tourne dans un
# conteneur alpine minimal, jamais bash dedans.
#
# set -u seulement (PAS -e) : un échec ponctuel (Keycloak pas encore
# démarré, identifiants admin invalides, réseau transitoire) ne doit
# JAMAIS arrêter cette boucle -- elle doit survivre indéfiniment et
# simplement réessayer au prochain cycle, jamais dépendre d'une
# politique de redémarrage de conteneur pour ça.
set -u

INTERVAL="${KEYCLOAK_BACKUP_INTERVAL_SECONDS:-1800}"
OUT_DIR="/backup"
KC_BASE="http://keycloak:8080/auth"
REALM="supervision-si"
INITIAL_DELAY=30

echo "$(date -u +%FT%TZ) sauvegarde Keycloak : attente initiale ${INITIAL_DELAY}s (le temps que Keycloak démarre)"
sleep "$INITIAL_DELAY"

while true; do
  # Authentification par COMPTE DE SERVICE (livraison #361,
  # grant_type=client_credentials) -- remplace l'authentification par
  # mot de passe sur l'utilisateur de bootstrap utilisée jusqu'ici
  # (voir keycloak/README.md pour l'historique complet : échecs
  # d'authentification répétés après un premier succès, signalés en
  # conditions réelles par la personne, qui a elle-même trouvé la
  # commande `bootstrap-admin service` en explorant l'image Keycloak).
  # Documentation officielle Keycloak
  # (keycloak.org/server/bootstrap-admin-recovery) : un compte de
  # service de bootstrap est explicitement recommandé "for automated
  # scenarios" comme celui-ci, par opposition à l'utilisateur de
  # bootstrap, documenté "temporaire" (mécanisme exact non confirmé à
  # 100%, jamais présumé -- voir le commentaire précédent conservé
  # dans l'historique git). Réponse BRUTE capturée à part -- même
  # raisonnement diagnostic qu'avant : le corps de réponse peut
  # contenir des détails dans certains formats d'erreur OAuth --
  # JAMAIS loggé tel quel, seul le champ "error"/"error_description"
  # (texte libre, jamais un secret) en est extrait.
  TOKEN_RESPONSE=$(curl -s -m 10 -X POST "$KC_BASE/realms/master/protocol/openid-connect/token" \
    -d "client_id=${KEYCLOAK_SERVICE_CLIENT_ID:-supervision-si-service}" \
    -d "client_secret=${KEYCLOAK_SERVICE_CLIENT_SECRET:-change-me}" \
    -d "grant_type=client_credentials" 2>/dev/null)
  TOKEN=$(echo "$TOKEN_RESPONSE" | jq -r '.access_token // empty' 2>/dev/null)

  if [ -z "$TOKEN" ]; then
    ERROR_DETAIL=$(echo "$TOKEN_RESPONSE" | jq -r '.error_description // .error // "réponse illisible"' 2>/dev/null)
    echo "$(date -u +%FT%TZ) sauvegarde échouée : authentification refusée -- $ERROR_DETAIL"
  else
    TMP="$OUT_DIR/.supervision-si-realm-backup.json.tmp"
    HTTP_CODE=$(curl -s -m 30 -o "$TMP" -w "%{http_code}" \
      -X POST \
      -H "Authorization: Bearer $TOKEN" \
      -H "Content-Type: application/json" \
      "$KC_BASE/admin/realms/${REALM}/partial-export?exportClients=true&exportGroupsAndRoles=true" 2>/dev/null)

    if [ "$HTTP_CODE" = "200" ]; then
      mv "$TMP" "$OUT_DIR/supervision-si-realm-backup.json"
      echo "$(date -u +%FT%TZ) sauvegarde réussie -> $OUT_DIR/supervision-si-realm-backup.json"
    else
      echo "$(date -u +%FT%TZ) sauvegarde échouée : HTTP $HTTP_CODE (realm '${REALM}' pas encore importé ?)"
      rm -f "$TMP"
    fi
  fi

  sleep "$INTERVAL"
done
