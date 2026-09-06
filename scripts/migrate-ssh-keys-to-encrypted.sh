#!/usr/bin/env bash
# migrate-ssh-keys-to-encrypted.sh -- migration GUIDÉE et SÛRE des
# clés SSH de ssh-tunnels/keys/ vers des fichiers .enc (backlog item
# 22, livraison #387) -- compagnon de migrate-env-to-encrypted.sh
# (#386), MÊME séquence de sécurité (sauvegarde -> chiffrement ->
# déchiffrement de vérification -> comparaison), adaptée à des
# fichiers BINAIRES (comparaison octet par octet, pas clé=valeur).
#
# CE QUE CE SCRIPT FAIT, POUR CHAQUE CLÉ TROUVÉE dans ssh-tunnels/keys/
# (un fichier = une clé, README.md et *.pub exclus -- voir
# ssh-tunnels/keys/README.md pour cette convention déjà établie) :
# 1. Sauvegarde (horodatée, jamais écrasée).
# 2. Chiffrement (secrets_tool.py encrypt-file, déjà testé -- jamais
#    réimplémenté ici, juste orchestré).
# 3. Déchiffrement de vérification immédiat + comparaison OCTET PAR
#    OCTET avec l'original (verify_file_migration.py).
#
# CE QUE CE SCRIPT NE FAIT JAMAIS :
# - Ne supprime ni ne modifie la clé d'origine.
# - Ne bascule PAS automatiquement ssh-tunnels-api vers les clés
#   chiffrées -- ce module ne consomme même pas encore les fichiers
#   .enc directement (voir ssh-tunnels/README.md) ; ce script prépare
#   des fichiers .enc VÉRIFIÉS, la suite (câblage éventuel du module
#   pour les lire) reste un sujet SÉPARÉ, pas traité ici.
# - Ne stocke la phrase de passe NULLE PART -- redemandée pour
#   CHAQUE clé, séparément (jamais réutilisée automatiquement d'une
#   clé à l'autre, même motif que .env : une saisie interactive à
#   chaque fois).
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

KEYS_DIR="ssh-tunnels/keys"

echo "=================================================================="
echo " Migration sécurisée des clés SSH -- $KEYS_DIR"
echo " Backlog item 22 -- livraison #387"
echo "=================================================================="
echo ""

if [ ! -d "$KEYS_DIR" ]; then
  echo "❌ Dossier introuvable : $KEYS_DIR" >&2
  exit 1
fi

# Découverte -- MÊME convention que ssh-tunnels-api lui-même (voir
# ssh-tunnels/keys/README.md) : un fichier = une clé, jamais de
# sous-dossier, README.md et *.pub exclus. *.enc/*.backup-*/*.dec
# également exclus -- artefacts d'une exécution précédente de CE
# script, jamais une clé à migrer une seconde fois par erreur.
KEY_FILES=()
for f in "$KEYS_DIR"/*; do
  [ -f "$f" ] || continue
  base="$(basename "$f")"
  case "$base" in
    README.md|*.pub|*.enc|*.backup-*|*.dec) continue ;;
  esac
  KEY_FILES+=("$f")
done

if [ ${#KEY_FILES[@]} -eq 0 ]; then
  echo "Aucune clé trouvée dans $KEYS_DIR (dossier vide ou seulement"
  echo "README.md/*.pub) -- rien à migrer."
  exit 0
fi

echo "Clé(s) trouvée(s) : ${#KEY_FILES[@]}"
for f in "${KEY_FILES[@]}"; do
  echo "  - $f"
done
echo ""
echo "La phrase de passe sera demandée SÉPARÉMENT pour CHAQUE clé"
echo "(deux fois : saisie + confirmation, puis une 3e fois pour la"
echo "vérification) -- jamais stockée ni réutilisée automatiquement."
echo ""

FAILED_KEYS=()
SUCCEEDED_KEYS=()

for KEY_FILE in "${KEY_FILES[@]}"; do
  echo "------------------------------------------------------------------"
  echo " Clé : $KEY_FILE"
  echo "------------------------------------------------------------------"

  if [ -f "${KEY_FILE}.enc" ]; then
    echo "⚠️  ${KEY_FILE}.enc existe déjà."
    read -r -p "    L'écraser avec une nouvelle migration ? [oui/NON] " confirm
    if [ "$confirm" != "oui" ] && [ "$confirm" != "OUI" ]; then
      echo "Ignoré (rien n'a été touché pour cette clé)."
      echo ""
      continue
    fi
  fi

  TIMESTAMP="$(date +%Y%m%d-%H%M%S)"
  BACKUP_FILE="${KEY_FILE}.backup-${TIMESTAMP}"

  echo "Étape 1/3 : sauvegarde"
  cp "$KEY_FILE" "$BACKUP_FILE"
  chmod 600 "$BACKUP_FILE" 2>/dev/null || true
  echo "✅ Sauvegarde créée : $BACKUP_FILE"
  echo ""

  echo "Étape 2/3 : chiffrement"
  python3 scripts/secrets_tool.py encrypt-file "$KEY_FILE" --output "${KEY_FILE}.enc"
  echo ""

  echo "Étape 3/3 : vérification -- déchiffrement immédiat + comparaison octet par octet"
  echo "(retapez la MÊME phrase de passe que celle utilisée à l'instant)"
  TMP_DECRYPTED="$(mktemp)"
  set +e
  python3 scripts/secrets_tool.py decrypt-file "${KEY_FILE}.enc" --output "$TMP_DECRYPTED"
  DECRYPT_STATUS=$?
  set -e
  if [ "$DECRYPT_STATUS" -ne 0 ]; then
    echo "❌ ÉCHEC du déchiffrement de vérification pour $KEY_FILE."
    rm -f "$TMP_DECRYPTED"
    FAILED_KEYS+=("$KEY_FILE")
    echo ""
    continue
  fi

  set +e
  python3 scripts/verify_file_migration.py "$KEY_FILE" "$TMP_DECRYPTED"
  VERIFY_STATUS=$?
  set -e
  rm -f "$TMP_DECRYPTED"

  if [ "$VERIFY_STATUS" -eq 0 ]; then
    SUCCEEDED_KEYS+=("$KEY_FILE")
  else
    FAILED_KEYS+=("$KEY_FILE")
  fi
  echo ""
done

echo "=================================================================="
echo " Résumé"
echo "=================================================================="
echo "Réussies et vérifiées : ${#SUCCEEDED_KEYS[@]}"
if [ ${#SUCCEEDED_KEYS[@]} -gt 0 ]; then
  for k in "${SUCCEEDED_KEYS[@]}"; do
    echo "  ✅ $k -> ${k}.enc"
  done
fi
if [ ${#FAILED_KEYS[@]} -gt 0 ]; then
  echo "En échec (clé d'origine INTACTE, rien perdu) : ${#FAILED_KEYS[@]}"
  for k in "${FAILED_KEYS[@]}"; do
    echo "  ❌ $k"
  done
fi
echo ""
echo "Comme pour .env : le BASCULEMENT réel (utilisation effective des"
echo "fichiers .enc par ssh-tunnels-api) reste un sujet SÉPARÉ, pas"
echo "encore câblé dans ce module -- voir ssh-tunnels/README.md."

[ ${#FAILED_KEYS[@]} -eq 0 ]
