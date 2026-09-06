#!/usr/bin/env bash
# Génère un .env prêt à l'emploi à partir de .env.example, pour un
# premier test rapide du stack -- demandé explicitement (2026-09-05) :
# "un .env.mini avec une détection auto et toutes les variables par
# défaut", pour tester aujourd'hui ET vers un futur package autonome.
#
# CE QUE CE SCRIPT FAIT :
# - Détecte automatiquement HOST_IP (IP LAN réelle de la machine) --
#   CRITIQUE (utilisée ~36 fois dans docker-compose.yml), une valeur
#   vide/localhost casse l'authentification (CORS) dès qu'on accède
#   au hub par une IP réelle plutôt que "localhost" (voir .env.example).
# - Génère aléatoirement les secrets INTERNES à ce docker-compose
#   (jamais partagés avec un système externe réel) : mot de passe
#   admin Keycloak, secret de service prefs-api, mot de passe admin
#   Mayan, passphrase+sel SSH_TUNNELS et SNMP.
# - Détecte COMPOSE_PROJECT_NAME depuis le nom réel du dossier courant
#   (cohérent avec scripts/launcher.sh, qui en dépend pour piloter le
#   vrai Docker de l'hôte).
#
# CE QUE CE SCRIPT NE FAIT JAMAIS :
# - Ne touche PAS aux identifiants de systèmes EXTERNES réels (LDAP,
#   IPAM/Optick/Zenoss/TTSGU/OwnCloud/Cacti -- bases MySQL EXISTANTES
#   hors de ce projet ; GLPI ; Google OAuth ; IMAP réel ; Nebula ;
#   TRB140) -- un secret aléatoire ne correspondrait à AUCUN système
#   réel, ces variables restent donc vides/placeholder comme dans
#   .env.example : les modules concernés démarrent normalement mais
#   répondent une erreur claire tant qu'ils ne sont pas configurés à
#   la main avec de VRAIES valeurs (voir le README de chaque module).
# - Ne touche PAS aux *_RIGHTS_API_URL (restent vides, opt-in) -- les
#   activer sans le groupe Keycloak admin_hub déjà assigné bloquerait
#   vos propres actions sans prévenir.
# - N'active PAS vault-standalone/ (stack séparé, volontairement hors
#   du périmètre "premier test rapide" -- voir vault-standalone/README.md
#   si besoin, sa propre configuration est indépendante).
#
# Écrit DIRECTEMENT vers .env à la racine (jamais .env.mini) --
# gateway/scripts/run.sh et mayan/scripts/run.sh utilisent tous deux
# --env-file pointant explicitement vers "$PROJECT_ROOT/.env" (jamais
# un autre nom de fichier), donc c'est le SEUL nom que Docker Compose
# et ces scripts vont réellement lire.
set -euo pipefail

HERE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$HERE_DIR"

if [ ! -f ".env.example" ]; then
  echo "🔴 .env.example introuvable à la racine du projet -- lancé depuis le bon dossier ?" >&2
  exit 1
fi

if [ -f ".env" ]; then
  echo "⚠️  .env existe déjà à la racine."
  read -r -p "   L'écraser avec une nouvelle génération ? [oui/NON] " confirm
  case "$confirm" in
    oui|OUI|o|O) ;;
    *) echo "   Annulé -- .env existant conservé tel quel."; exit 0 ;;
  esac
fi

# --- Détection HOST_IP ---
# Fonction partagée (livraison #342) -- shared/detect-host-ip.sh,
# désormais réutilisée aussi par scripts/run.sh, gateway/scripts/
# run.sh et mayan/scripts/run.sh, jamais dupliquée séparément ici.
source "$HERE_DIR/shared/detect-host-ip.sh"

HOST_IP_DETECTED="$(detect_host_ip)"
if [ -z "$HOST_IP_DETECTED" ]; then
  echo "⚠️  Détection automatique de HOST_IP échouée -- laissé vide dans .env"
  echo "    (repli sur \"localhost\", ne fonctionnera que depuis la machine elle-même)."
  echo "    Renseigner manuellement l'IP LAN réelle dans .env si besoin d'un accès réseau."
else
  echo "✅ HOST_IP détecté : $HOST_IP_DETECTED"
fi

PROJECT_NAME="$(basename "$HERE_DIR")"
echo "✅ COMPOSE_PROJECT_NAME détecté depuis le nom du dossier : $PROJECT_NAME"

# --- Génération des secrets internes ---
# Passphrases : chaîne aléatoire lisible (32 caractères alphanumériques).
# Sels : méthode EXACTE documentée dans .env.example (base64 de 16
# octets aléatoires) -- jamais improvisée différemment.
gen_passphrase() {
  python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(32)))"
}
gen_salt() {
  python3 -c "import secrets,base64; print(base64.b64encode(secrets.token_bytes(16)).decode())"
}

if ! command -v python3 >/dev/null 2>&1; then
  echo "🔴 python3 introuvable -- requis pour générer les secrets (SSH_TUNNELS_CRED_*, SNMP_CRED_*)." >&2
  exit 1
fi

KEYCLOAK_ADMIN_PASSWORD_GEN="$(gen_passphrase)"
# Compte de SERVICE de bootstrap (livraison #361) -- EN PLUS du mot
# de passe utilisateur ci-dessus, jamais à sa place (voir
# keycloak/README.md pour le raisonnement complet).
KEYCLOAK_SERVICE_CLIENT_SECRET_GEN="$(gen_passphrase)"
PREFS_API_SERVICE_SECRET_GEN="$(gen_passphrase)"
MAYAN_AUTOADMIN_PASSWORD_GEN="$(gen_passphrase)"
SSH_TUNNELS_CRED_PASSPHRASE_GEN="$(gen_passphrase)"
SSH_TUNNELS_CRED_SALT_GEN="$(gen_salt)"
SNMP_CRED_PASSPHRASE_GEN="$(gen_passphrase)"
SNMP_CRED_SALT_GEN="$(gen_salt)"
# LDAP_BIND_PASSWORD et LDAP_TEST_ADMIN_PASSWORD reçoivent la MÊME
# valeur -- même compte cn=admin de l'annuaire de test openldap-test
# (livraison #348), utilisé à la fois pour la fédération Keycloak
# (LDAP_BIND_PASSWORD) et comme mot de passe de liaison à saisir pour
# ldap-admin (jamais stocké côté serveur pour ce module, voir
# .env.example).
LDAP_TEST_ADMIN_PASSWORD_GEN="$(gen_passphrase)"

# --- Construction du .env final ---
# Part de .env.example (structure/commentaires intégralement
# préservés) puis remplace UNIQUEMENT les lignes ci-dessus -- jamais
# une réécriture depuis zéro qui perdrait la documentation inline.
# Remplacement via python3 (déjà une dépendance dure de ce script),
# jamais `sed -i` : BSD sed (macOS) et GNU sed (Linux) divergent sur
# la forme exacte de `-i` (argument de suffixe obligatoire et
# SÉPARÉ sur BSD pour un usage sans backup, ex. `-i ''`) -- la
# personne vient de rencontrer un piège de portabilité macOS
# aujourd'hui même (bash 3.2), pas la peine d'en risquer un second
# avec sed dans la foulée.
cp .env.example .env

python3 - "$HOST_IP_DETECTED" "$PROJECT_NAME" "$KEYCLOAK_ADMIN_PASSWORD_GEN" \
  "$KEYCLOAK_SERVICE_CLIENT_SECRET_GEN" \
  "$PREFS_API_SERVICE_SECRET_GEN" "$MAYAN_AUTOADMIN_PASSWORD_GEN" \
  "$SSH_TUNNELS_CRED_PASSPHRASE_GEN" "$SSH_TUNNELS_CRED_SALT_GEN" \
  "$SNMP_CRED_PASSPHRASE_GEN" "$SNMP_CRED_SALT_GEN" "$LDAP_TEST_ADMIN_PASSWORD_GEN" << 'PYEOF'
import re
import sys

(host_ip, project_name, keycloak_pw, keycloak_service_secret, prefs_secret, mayan_pw,
 ssh_passphrase, ssh_salt, snmp_passphrase, snmp_salt, ldap_pw) = sys.argv[1:12]

replacements = {
    "HOST_IP": host_ip,
    "COMPOSE_PROJECT_NAME": project_name,
    "KEYCLOAK_ADMIN_PASSWORD": keycloak_pw,
    "KEYCLOAK_SERVICE_CLIENT_SECRET": keycloak_service_secret,
    "PREFS_API_SERVICE_SECRET": prefs_secret,
    "MAYAN_AUTOADMIN_PASSWORD": mayan_pw,
    "SSH_TUNNELS_CRED_PASSPHRASE": ssh_passphrase,
    "SSH_TUNNELS_CRED_SALT": ssh_salt,
    "SNMP_CRED_PASSPHRASE": snmp_passphrase,
    "SNMP_CRED_SALT": snmp_salt,
    # Même valeur pour les deux -- même compte cn=admin de
    # l'annuaire de test (voir .env.example pour le détail complet).
    "LDAP_BIND_PASSWORD": ldap_pw,
    "LDAP_TEST_ADMIN_PASSWORD": ldap_pw,
}

with open(".env", "r") as f:
    lines = f.readlines()

out = []
for line in lines:
    matched = False
    for key, value in replacements.items():
        if re.match(rf"^{re.escape(key)}=", line):
            out.append(f"{key}={value}\n")
            matched = True
            break
    if not matched:
        out.append(line)

with open(".env", "w") as f:
    f.writelines(out)
PYEOF

# Sauvegarde des secrets générés, SÉPARÉMENT de .env -- pour les
# retrouver après coup (ex. se connecter à la console admin Keycloak)
# sans avoir à les extraire de .env à la main. Permissions restreintes
# (600) -- ce fichier contient des mots de passe en clair, même
# logique que .env lui-même.
SECRETS_SUMMARY=".env.generated-secrets.txt"
cat > "$SECRETS_SUMMARY" << EOF
Secrets générés le $(date +%Y-%m-%d\ %H:%M:%S) par scripts/generate-env.sh
-- gardé pour référence, jamais versionné (voir .gitignore).

Keycloak admin (compte "admin") : $KEYCLOAK_ADMIN_PASSWORD_GEN
Keycloak compte de service ("supervision-si-service" par défaut) : $KEYCLOAK_SERVICE_CLIENT_SECRET_GEN
Mayan admin (compte "admin")    : $MAYAN_AUTOADMIN_PASSWORD_GEN

Annuaire LDAP de test (openldap-test, livraison #348) :
  Connexion Keycloak/hub -- 3 comptes, MÊME mot de passe pour tous :
    alice / bob / admin_test  ->  mot de passe : password
  ldap-admin (écran de gestion) -- compte de liaison à saisir :
    cn=admin,dc=supervision-si,dc=local  ->  mot de passe : $LDAP_TEST_ADMIN_PASSWORD_GEN

(PREFS_API_SERVICE_SECRET, SSH_TUNNELS_CRED_*, SNMP_CRED_* : usage
interne uniquement, jamais besoin de les ressaisir manuellement.)
EOF
chmod 600 "$SECRETS_SUMMARY" ".env"

echo ""
echo "✅ .env généré à la racine du projet."
echo "✅ Identifiants admin (Keycloak/Mayan/LDAP) sauvegardés dans $SECRETS_SUMMARY"
echo ""
echo "Modules NON configurés (attendu, à faire à la main si besoin -- voir le"
echo "README de chaque module) : IPAM, Optick, Zenoss, TTS-GU, OwnCloud,"
echo "Cacti, GLPI, Nebula, IMAP réel, Google OAuth, network-agent, TRB140."
echo "Le reste du stack démarre et fonctionne sans ces modules."
echo ""
echo "Prochaine étape : ./scripts/run-all.sh all up -d --build   (voir README.md)"
echo "(PAS ./scripts/run.sh seul -- celui-ci ne démarre QUE le stack principal,"
echo " jamais gateway/ (Keycloak+tls-proxy, port \$GATEWAY_PORT) ni mayan/ (GED))"
