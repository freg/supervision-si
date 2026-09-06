#!/usr/bin/env bash
# migrate-env-to-encrypted.sh -- migration GUIDÉE et SÛRE d'un .env en
# clair vers un .env.encrypted (backlog item 22, livraison #386).
# Demandé explicitement : "l'outil (encrypt-env) est prêt et testé,
# reste à décider AVEC la personne quand/comment l'utiliser sur son
# vrai .env -- explicitement PAS improvisée, à faire avec des
# sauvegardes et une procédure de retour arrière claire."
#
# CE QUE CE SCRIPT FAIT :
# 1. Sauvegarde le .env d'origine (horodatée, jamais écrasée).
# 2. Chiffre vers .env.encrypted (secrets_tool.py encrypt-env, déjà
#    testé -- jamais réimplémenté ici, juste orchestré).
# 3. Déchiffre IMMÉDIATEMENT ce .env.encrypted flambant neuf et
#    compare CHAQUE clé/valeur avec l'original (verify_env_migration.py)
#    -- vérifie que l'aller-retour est fidèle à 100%, PAS une simple
#    confiance aveugle dans le chiffrement.
# 4. Rapporte clairement le résultat -- ne supprime JAMAIS le .env
#    d'origine ni la sauvegarde, quel que soit le résultat.
#
# CE QUE CE SCRIPT NE FAIT JAMAIS :
# - Ne supprime ni ne modifie le .env d'origine.
# - Ne bascule PAS automatiquement le déploiement vers
#   .env.encrypted -- ça reste une décision et une action SÉPARÉES
#   de la personne (voir le résumé final pour la marche à suivre).
# - Ne stocke la phrase de passe NULLE PART -- redemandée à CHAQUE
#   étape qui en a besoin (chiffrement, puis déchiffrement de
#   vérification), exactement comme en usage normal.
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

ENV_FILE="${1:-.env}"

echo "=================================================================="
echo " Migration sécurisée : $ENV_FILE -> ${ENV_FILE}.encrypted"
echo " Backlog item 22 -- livraison #386"
echo "=================================================================="
echo ""

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ Fichier introuvable : $ENV_FILE" >&2
  exit 1
fi

if [ -f "${ENV_FILE}.encrypted" ]; then
  echo "⚠️  ${ENV_FILE}.encrypted existe déjà."
  read -r -p "    L'écraser avec une nouvelle migration ? [oui/NON] " confirm
  if [ "$confirm" != "oui" ] && [ "$confirm" != "OUI" ]; then
    echo "Annulé (rien n'a été touché)."
    exit 0
  fi
  echo ""
fi

TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
BACKUP_FILE="${ENV_FILE}.backup-${TIMESTAMP}"

echo "Étape 1/3 : sauvegarde"
cp "$ENV_FILE" "$BACKUP_FILE"
chmod 600 "$BACKUP_FILE" 2>/dev/null || true
echo "✅ Sauvegarde créée : $BACKUP_FILE (jamais supprimée par ce script)"
echo ""

echo "Étape 2/3 : chiffrement"
echo "(une phrase de passe va vous être demandée deux fois -- confirmation --"
echo " RETENEZ-LA, elle n'est stockée NULLE PART, ni ici ni ailleurs)"
python3 scripts/secrets_tool.py encrypt-env --input "$ENV_FILE" --output "${ENV_FILE}.encrypted"
echo ""

echo "Étape 3/3 : vérification -- déchiffrement immédiat + comparaison clé par clé"
echo "(retapez la MÊME phrase de passe que celle utilisée à l'instant)"
set +e
DECRYPTED_OUTPUT="$(python3 scripts/secrets_tool.py decrypt-env --input "${ENV_FILE}.encrypted" 2>/tmp/decrypt_stderr_$$)"
DECRYPT_STATUS=$?
set -e
if [ "$DECRYPT_STATUS" -ne 0 ]; then
  echo ""
  echo "❌ ÉCHEC du déchiffrement de vérification :"
  cat /tmp/decrypt_stderr_$$ >&2
  rm -f "/tmp/decrypt_stderr_$$"
  echo ""
  echo "$ENV_FILE (original) et $BACKUP_FILE (sauvegarde) restent INTACTS."
  echo "${ENV_FILE}.encrypted a été créé mais N'A PAS PU être vérifié -- NE PAS l'utiliser en l'état."
  exit 1
fi
rm -f "/tmp/decrypt_stderr_$$"

echo "$DECRYPTED_OUTPUT" | python3 scripts/verify_env_migration.py "$ENV_FILE"
VERIFY_STATUS=$?

echo ""
echo "=================================================================="
if [ "$VERIFY_STATUS" -eq 0 ]; then
  echo " ✅ Migration vérifiée avec succès"
  echo "=================================================================="
  echo ""
  echo "Fichiers en place :"
  echo "  - $ENV_FILE              (original, INTACT, toujours utilisé par défaut)"
  echo "  - $BACKUP_FILE  (sauvegarde, à conserver jusqu'à confiance totale)"
  echo "  - ${ENV_FILE}.encrypted   (nouveau, vérifié fidèle à 100%)"
  echo ""
  echo "Pour BASCULER réellement vers le chiffré (étape MANUELLE, délibérée) :"
  echo "  1. Testez d'abord SANS toucher à rien : renommez temporairement"
  echo "     $ENV_FILE (ex. 'mv $ENV_FILE ${ENV_FILE}.plain-disabled')"
  echo "     puis relancez un déploiement normal -- scripts/run.sh détecte"
  echo "     ${ENV_FILE}.encrypted automatiquement en l'absence de $ENV_FILE"
  echo "     et vous demandera la phrase de passe à chaque lancement."
  echo "  2. Si tout fonctionne comme avant : gardez cet état."
  echo "     Si quoi que ce soit cloche : restaurez $BACKUP_FILE vers"
  echo "     $ENV_FILE immédiatement (rien n'est perdu)."
  echo "  3. Une fois pleinement confiant (plusieurs déploiements réussis) :"
  echo "     supprimez $BACKUP_FILE vous-même, quand VOUS le décidez --"
  echo "     jamais fait automatiquement par un script."
else
  echo " ❌ Migration NON vérifiée -- ne pas utiliser ${ENV_FILE}.encrypted"
  echo "=================================================================="
  echo ""
  echo "$ENV_FILE (original) et $BACKUP_FILE (sauvegarde) restent INTACTS,"
  echo "rien n'a été perdu. Cause la plus probable : les deux phrases de"
  echo "passe saisies (chiffrement puis vérification) ne correspondaient"
  echo "pas exactement -- relancez ce script depuis le début."
fi
exit "$VERIFY_STATUS"
