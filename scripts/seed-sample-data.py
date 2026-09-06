#!/usr/bin/env python3
"""
Peuple quelques données d'exemple dans les modules NATIFS du stack
(pas de système externe PRÉEXISTANT requis) -- demandé explicitement
(2026-09-05) : "un package complet autonome... des données exemples
pour tous les modules". Voir scripts/README-seed.md pour la portée
exacte (quels modules sont couverts, pourquoi certains ne le sont
pas encore).

PRÉREQUIS : le stack COMPLET doit déjà tourner --
`./scripts/run-all.sh all up -d --build` (voir README.md), PAS
`./scripts/run.sh` seul (ne démarre que le stack principal, jamais
`gateway/` -- sans lui, RIEN n'écoute sur GATEWAY_PORT, ce script
échouerait entièrement, "Connection refused" sur chaque appel). .env
déjà généré (`./scripts/generate-env.sh`). Le stack Mayan (inclus
dans `run-all.sh all`, cible séparée `mayan`) doit aussi tourner pour
la section ged-api spécifiquement -- sinon ces appels échouent
proprement (502, comptés en échec) sans bloquer le reste du script.

Cible la PASSERELLE unique (tls-proxy, HOST_IP:GATEWAY_PORT/api/...) --
AUCUN service natif ne publie de port direct sur l'hôte (vérifié :
tickets-api, tasks-api, architecture-api, snmp-api, classifier-api,
ged-api). Certificat auto-signé -- vérification TLS désactivée
volontairement ici (même confiance que le navigateur qui l'accepte
manuellement au premier accès), jamais une pratique à reproduire
pour un usage réel en dehors de ce script de test local.

Aucune authentification Keycloak requise pour ces appels -- confirmé
par relecture de tls-proxy/render_nginx_conf.py (aucun auth_request
sur les chemins /api/*), seul rights-api (opt-in, désactivé par
défaut dans le .env généré) ajouterait une contrainte.

IDEMPOTENT best-effort : relancer ce script ajoute une NOUVELLE copie
de chaque exemple plutôt que d'échouer, JAMAIS un doublon détecté
puis ignoré (pas construit ici, voir "reste à faire") -- pensé pour
un premier peuplement sur un stack fraîchement démarré, pas une
resynchronisation répétée.
"""
import json
import os
import sys
import warnings

try:
    import requests
    import urllib3
except ImportError:
    print("🔴 Le module Python 'requests' est requis pour ce script.")
    print("   Installer avec : pip3 install requests --break-system-packages   (Linux)")
    print("                ou : pip3 install requests                          (macOS)")
    sys.exit(1)

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
warnings.filterwarnings("ignore")

HERE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(HERE_DIR)


def load_env(path):
    """Lecture minimale d'un fichier .env -- juste HOST_IP et
    GATEWAY_PORT, jamais besoin d'un vrai parseur dotenv pour ça."""
    values = {}
    if not os.path.exists(path):
        return values
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


env = load_env(os.path.join(PROJECT_ROOT, ".env"))
HOST_IP = os.environ.get("HOST_IP") or env.get("HOST_IP") or "localhost"
GATEWAY_PORT = os.environ.get("GATEWAY_PORT") or env.get("GATEWAY_PORT") or "6443"
BASE = f"https://{HOST_IP}:{GATEWAY_PORT}/api"

created = {"ok": 0, "error": 0}


def post(path, json_body=None, files=None, data=None, label=""):
    url = f"{BASE}{path}"
    try:
        if files is not None:
            resp = requests.post(url, files=files, data=data, verify=False, timeout=15)
        else:
            resp = requests.post(url, json=json_body, verify=False, timeout=15)
    except requests.RequestException as exc:
        print(f"  🔴 {label} : injoignable -- {exc}")
        created["error"] += 1
        return None
    if resp.status_code >= 300:
        print(f"  🔴 {label} : {resp.status_code} -- {resp.text[:200]}")
        created["error"] += 1
        return None
    print(f"  ✅ {label}")
    created["ok"] += 1
    try:
        return resp.json()
    except ValueError:
        return None


def get(path):
    try:
        resp = requests.get(f"{BASE}{path}", verify=False, timeout=15)
        return resp.json() if resp.status_code == 200 else None
    except requests.RequestException:
        return None


print(f"Cible : {BASE}\n")

# --- tickets-api : données de référence + quelques tickets + un événement ---
print("=== tickets-api ===")
type_incident = post("/tickets/types", {"label": "Incident"}, label="type 'Incident'")
type_demande = post("/tickets/types", {"label": "Demande"}, label="type 'Demande'")
site_a = post("/tickets/sites", {"label": "Site A"}, label="site 'Site A'")
level_n1 = post("/tickets/levels", {"label": "N1", "rank": 1}, label="niveau 'N1'")
level_n2 = post("/tickets/levels", {"label": "N2", "rank": 2}, label="niveau 'N2'")

for subject, description in [
    ("Panne imprimante bureau 210", "L'imprimante réseau ne répond plus depuis ce matin."),
    ("Demande d'accès VPN", "Nouveau collaborateur, besoin d'un accès VPN pour le télétravail."),
    ("Wifi instable bâtiment B", "Coupures répétées depuis hier après-midi, plusieurs postes concernés."),
]:
    post("/tickets/tickets", {"subject": subject, "description": description}, label=f"ticket '{subject}'")

post(
    "/tickets/calendar/import",
    data=(
        "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nBEGIN:VEVENT\r\n"
        "UID:exemple-seed-1@supervision-si\r\n"
        "SUMMARY:Maintenance serveur planifiée\r\n"
        "DESCRIPTION:Redémarrage du serveur de fichiers, prévenir les utilisateurs.\r\n"
        "DTSTART:20261201T090000Z\r\nDTEND:20261201T100000Z\r\n"
        "END:VEVENT\r\nEND:VCALENDAR\r\n"
    ).encode("utf-8"),
    label="événement calendrier 'Maintenance serveur planifiée'",
)

# --- tasks-api : quelques tâches Kanban ---
print("\n=== tasks-api ===")
for title, status in [
    ("Documenter la procédure de sauvegarde", "todo"),
    ("Mettre à jour le firmware des switches", "doing"),
    ("Audit des comptes LDAP inactifs", "done"),
]:
    post("/tasks/tasks", {"title": title, "status": status}, label=f"tâche '{title}' ({status})")

# --- architecture-api : quelques équipements ---
print("\n=== architecture-api ===")
for name, ip, eq_type in [
    ("switch-etage1", "10.0.1.10", "switch"),
    ("routeur-principal", "10.0.1.1", "routeur"),
    ("serveur-fichiers", "10.0.1.50", "serveur"),
]:
    post("/architecture/equipment", {"name": name, "ip_address": ip, "equipment_type": eq_type}, label=f"équipement '{name}'")

# --- snmp-api : une cible d'exemple ---
# Nécessite SNMP_CRED_PASSPHRASE/SALT déjà configurés dans .env (voir
# scripts/generate-env.sh, qui les génère automatiquement) -- sinon
# échoue avec un message clair (503, chiffrement non configuré),
# jamais un crash silencieux.
print("\n=== snmp-api ===")
post(
    "/snmp/targets",
    {"label": "Switch étage 1 (exemple)", "host": "10.0.1.10", "community": "public"},
    label="cible SNMP 'Switch étage 1 (exemple)'",
)

# --- classifier-api : un petit dictionnaire d'exemple ---
print("\n=== classifier-api ===")
sample_terms = "réseau\nserveur\nimprimante\nwifi\nvpn\nsauvegarde\n"
post(
    "/classifier/dictionaries/import",
    files={"file": ("exemple.txt", sample_terms.encode("utf-8"), "text/plain")},
    data={"category": "infrastructure", "source": "exemple-seed"},
    label="dictionnaire 'infrastructure' (6 termes)",
)

# --- ged-api : quelques documents d'exemple ---
# Nécessite le stack Mayan SÉPARÉ démarré (./mayan/scripts/run.sh up
# -d --build, voir mayan/README.md) -- ged-api appelle Mayan de façon
# SYNCHRONE pour créer chaque document (mayan_client.py), jamais un
# crash si Mayan est injoignable, mais une erreur 502 explicite pour
# CHAQUE document -- gérée normalement par post() ci-dessus (comptée
# en échec, jamais un arrêt du reste du script).
print("\n=== ged-api (nécessite mayan/scripts/run.sh up -d --build) ===")
for name, content in [
    ("Procédure de sauvegarde (exemple).txt", "Procédure de sauvegarde hebdomadaire du serveur de fichiers.\n"),
    ("Schéma réseau étage 1 (exemple).txt", "Description du câblage et des équipements de l'étage 1.\n"),
]:
    post(
        "/ged/documents",
        files={"file": (name, content.encode("utf-8"), "text/plain")},
        data={"name": name},
        label=f"document '{name}'",
    )

print(f"\n--- Bilan : {created['ok']} créé(s), {created['error']} échec(s) ---")
if created["error"] > 0:
    print("Des échecs sont normaux si le stack vient tout juste de démarrer")
    print("(services encore en cours d'initialisation) -- relancer ce script")
    print("dans quelques secondes si besoin.")
    sys.exit(1)
