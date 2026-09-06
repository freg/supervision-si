"""
API minimale de préférences liées au compte — hub, portail tickets
uniquement (les deux seuls fronts qui connaissent une identité
Keycloak aujourd'hui ; DBA et Supervision SI restent en local
navigateur, décidé avec la personne). Un blob JSON par utilisateur
(`login`), pensé dès le départ pour accueillir d'autres préférences
que le thème plus tard (densité d'affichage, langue...) sans
changement de schéma.

Comme le reste du projet, cette API ne vérifie aucun jeton — le
`login` transmis en paramètre est celui déjà connu du front appelant
(profile.preferred_username via Keycloak), même posture de confiance
que partout ailleurs ("outil interne, réseau de confiance").
"""

import base64
import concurrent.futures
import json
import os
import re
import sqlite3
import ssl
import time
import urllib.error
import urllib.request

import keycloak_admin

from flask import Flask, jsonify, request, Response
from flask_cors import CORS
# Import DÉFENSIF -- version_endpoint.py n'existe que dans le
# conteneur Docker réel (copié depuis shared/ au build, comme
# theme.css/preferences.js pour les fronts). Sans ce garde, tout
# test qui importe ce module directement (sans passer par le build
# complet) casserait au chargement -- bug réel rencontré : plusieurs
# harnais de test existants, sans rapport avec /version, important
# app.py directement.
try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "prefs-api")

DB_PATH = os.environ.get("PREFS_DB_PATH", "/data/prefs.db")

# Défini ICI (déplacé plus tôt lors de la livraison #195, bug réel :
# utilisé par ensure_governance_documents_seeded() dans le bloc `try`
# de démarrage, plus bas dans ce fichier, AVANT que la ligne
# originale de définition ne soit atteinte -- même piège que now_iso()
# précédemment) -- voir la définition complète plus bas (juste avant
# _discover_readmes) pour le raisonnement de sécurité détaillé sur ce
# montage.
PROJECT_ROOT_PATH = os.environ.get("PROJECT_ROOT_PATH", "/project-root")

SCHEMA = """
CREATE TABLE IF NOT EXISTS preferences (
    login TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Paramétrage GLOBAL par application (pas par personne) -- fondation
-- pour une interface de paramétrage centralisée, demandée
-- explicitement : "les administrateurs ont tous les droits sur toutes
-- les applications". Même logique de fusion superficielle que
-- preferences (jamais d'écrasement total), mais clé = nom
-- d'application plutôt que login. AUCUNE vérification de rôle
-- côté serveur ici -- même posture de confiance que le reste du
-- projet (voir tête de fichier) : le frontend décide qui voit
-- l'interface d'édition (groupe Keycloak "administrateurs"), cette
-- API fait confiance à l'appelant. `actor` conservé pour la
-- journalisation uniquement, jamais pour bloquer une requête.
CREATE TABLE IF NOT EXISTS app_settings (
    app_name TEXT PRIMARY KEY,
    data TEXT NOT NULL,
    updated_by TEXT,
    updated_at TEXT NOT NULL
);

-- Timeline du hub (backlog, livraison #118) -- rappels restés sans
-- réaction, changements de tâche (rappel), mouvements entre onglets,
-- tickets créés. PERSONNELLE par technicien (login) -- pas un journal
-- global partagé, voir hub/README.md pour le raisonnement (3 des 4
-- catégories sont déjà intrinsèquement liées à une session de rappel/
-- une coquille à onglets PERSONNELLE, la 4e a été gardée cohérente
-- avec ça). `category` restreint à un petit nombre de valeurs connues
-- (voir VALID_HUB_EVENT_CATEGORIES) -- jamais une chaîne arbitraire
-- qui romprait silencieusement l'affichage différencié côté client.
-- `data` : JSON libre, contexte propre à la catégorie (ex. l'id du
-- ticket concerné) -- jamais de contenu sensible, ce n'est qu'un
-- journal d'ACTIVITÉ, pas un journal de CONTENU.
CREATE TABLE IF NOT EXISTS hub_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts INTEGER NOT NULL,
    login TEXT,
    category TEXT NOT NULL,
    label TEXT,
    data TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_hub_events_login_ts ON hub_events (login, ts);

-- Liens externes gérés par les administrateurs (backlog, livraison
-- #121) -- scope volontairement simple, décidé avec la personne :
-- une simple liste d'URI présentées dans le hub selon des droits
-- d'accès, JAMAIS de pont d'authentification/SSO (les vieilles
-- applis PHP/FatFree visées n'en sont pas capables ; une passerelle
-- unique reste une idée pour plus tard, voir BACKLOG.md #3). Chaque
-- lien reste un lien externe CLASSIQUE (nouvel onglet du navigateur),
-- jamais une iframe intégrée SAUF si `embeddable` est explicitement
-- coché (l'appli visée doit alors accepter d'être embarquée --
-- X-Frame-Options/CSP -- vérifié par l'admin qui coche la case, pas
-- par ce service).
-- `allowed_roles` : JSON, liste de rôles applicatifs (mêmes clés que
-- hub/src/lib.js, ROLE_LABELS) autorisés à VOIR ce lien -- liste
-- VIDE ou NULL = visible de tout le monde, même défaut que les
-- entrées internes du hub qui n'ont pas de condition de rôle (ex.
-- portail tickets). AUCUNE vérification de rôle côté serveur ici --
-- même posture de confiance que le reste de cette API (voir tête de
-- fichier) : le filtrage réel se fait côté hub
-- (buildFrontsList) au moment de l'affichage.
CREATE TABLE IF NOT EXISTS external_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    url TEXT NOT NULL,
    embeddable INTEGER NOT NULL DEFAULT 0,
    allowed_roles TEXT,
    -- Intégration Keycloak en direct (backlog, livraison #124) --
    -- toutes deux NULL = pas (encore) provisionné, reste un simple
    -- lien externe classique. keycloak_client_id : le clientId
    -- AFFICHÉ (ex. "glpi"), à transmettre à l'appli externe pour SA
    -- propre configuration OIDC. keycloak_internal_id : l'UUID
    -- INTERNE Keycloak (nécessaire pour la suppression via l'API
    -- Admin REST -- pas le même identifiant, voir prefs-api/
    -- keycloak_admin.py). Provisionnement/retrait via le compte de
    -- service dédié (droits manage-clients UNIQUEMENT, décidé
    -- explicitement) -- jamais les rôles realm applicatifs propres à
    -- une appli (ex. send/full/compose pour trb140-sms-relay), qui
    -- restent un ajout manuel dans keycloak/realm-template.json (voir
    -- keycloak/README.md pour cette limite assumée).
    keycloak_client_id TEXT,
    keycloak_internal_id TEXT,
    keycloak_redirect_uri TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Sources de logs configurées (livraison #147, backlog "logs de
-- toutes sortes", BACKLOG.md #3) -- table UNIFIÉE pour les 4 types à
-- venir (push/url/fichier/rsyslog), même si SEUL "url" est
-- fonctionnel dans cette livraison -- évite une migration à refaire
-- à chaque étape. `type` : "url" (fonctionnel) | "file" | "rsyslog"
-- (réservés, pas encore traités par le sondeur -- voir
-- log_sources_poller.py). "push" (livraison #142) n'a PAS d'entrée
-- ici -- il s'enregistre lui-même implicitement au premier appel
-- (voir register_shared_log_source), aucune configuration préalable
-- nécessaire, contrairement aux 3 autres qui exigent TOUJOURS un
-- paramétrage explicite (URL à interroger, chemin de fichier, port
-- d'écoute) avant de pouvoir produire quoi que ce soit.
-- `config` : JSON, forme dépendant de `type` (ex. pour "url" :
-- {"url": str, "interval_seconds": int, "format": "jsonl"|"plain"}).
CREATE TABLE IF NOT EXISTS log_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL,
    name TEXT NOT NULL UNIQUE,
    config TEXT NOT NULL,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Suivi des risques cyber (livraison #187, écran hub "Cyber",
-- demandé explicitement -- "au même niveau que Logs", "à
-- destination en premier lieu des politiques et des béotiens").
-- probability/impact : "faible"|"moyenne"|"élevée" (probability),
-- "faible"|"moyen"|"élevé" (impact) -- CHAÎNES, jamais un nombre
-- codé (1/2/3) -- directement lisible en base par quiconque
-- inspecterait les données sans repasser par l'appli, cohérent avec
-- l'esprit "béotiens" de cet écran jusque dans le stockage.
-- status : "a_traiter"|"en_cours"|"traite"|"accepte".
-- scope (livraison #193, évolution ISO/IEC 27001) : "hub" (risque
-- INTRINSÈQUE au hub/à supervision-si lui-même) |
-- "si_supervise" (impact d'un risque du hub SUR le système
-- d'information supervisé -- bases de données, annuaire,
-- équipements réseau... auxquels le hub accède) -- demandé
-- explicitement : "le HUB et ses risques" vs "les impacts risques
-- du HUB sur le SI supervisé". S'aligne sur l'exigence ISO/IEC 27001
-- d'examiner les risques "en tenant compte des menaces,
-- vulnérabilités ET IMPACTS" -- la distinction HUB/impact-SI EST
-- cette dimension d'impact, rendue explicite plutôt qu'implicite.
CREATE TABLE IF NOT EXISTS cyber_risks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL,
    description TEXT,
    category TEXT,
    modules TEXT,
    probability TEXT NOT NULL,
    impact TEXT NOT NULL,
    scope TEXT NOT NULL DEFAULT 'hub',
    status TEXT NOT NULL DEFAULT 'a_traiter',
    progress_notes TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Documents de gouvernance (livraison #195, demandé explicitement --
-- "présenter versionnés dans l'aide et dans iso27000") -- les
-- documents ISO/IEC 27000 (#194) et leurs éventuels successeurs.
-- Contenu stocké en BASE64 directement en base (fichiers courts,
-- quelques dizaines de Ko -- jamais un volume/stockage dédié pour un
-- si petit nombre de documents). `version`/`updated_at` : ce qui
-- rend l'affichage "versionné" -- une personne qui consulte le
-- document sait à quelle version il correspond.
CREATE TABLE IF NOT EXISTS governance_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    version TEXT NOT NULL,
    filename TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_base64 TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Historique VERSIONNÉ de la matrice de risques (livraison #199,
-- "suite des travaux d'urgence... volet transparence", point 1 :
-- "un historique des matrices / versionné"). Un INSTANTANÉ complet
-- du risque est enregistré à chaque création/modification/suppression
-- -- jamais un simple "diff" (trop fragile à interpréter plus tard
-- sans le contexte complet) -- permet de reconstituer l'état de
-- N'IMPORTE QUEL risque, ou de la matrice ENTIÈRE, à N'IMPORTE QUEL
-- instant passé. `change_type` : "created"|"updated"|"deleted".
CREATE TABLE IF NOT EXISTS cyber_risks_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    risk_id INTEGER NOT NULL,
    change_type TEXT NOT NULL,
    label TEXT NOT NULL,
    description TEXT,
    category TEXT,
    modules TEXT,
    probability TEXT NOT NULL,
    impact TEXT NOT NULL,
    scope TEXT NOT NULL,
    status TEXT NOT NULL,
    progress_notes TEXT,
    recorded_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_cyber_risks_history_risk_id ON cyber_risks_history(risk_id);
CREATE INDEX IF NOT EXISTS idx_cyber_risks_history_recorded_at ON cyber_risks_history(recorded_at);
"""

# Rôles applicatifs connus -- mêmes clés que hub/src/lib.js
# (GROUP_TO_ROLE / ROLE_LABELS), jamais laissés diverger.
VALID_EXTERNAL_LINK_ROLES = (
    "admin",
    "demandeur",
    "technicien",
    "politique",
    "supervision",
    "service",
    "maitre_clefs",
)

# Catégories connues -- voir commentaire du schéma ci-dessus.
VALID_HUB_EVENT_CATEGORIES = (
    "rappel_sans_reaction",
    "changement_activite",
    "mouvement_onglet",
    "ticket_cree",
)

DEFAULT_PREFERENCES = {"theme": "light"}


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def ensure_external_links_keycloak_columns():
    """Migration douce : les bases créées entre la livraison #121
    (external_links elle-même) et #124 (intégration Keycloak) n'ont
    pas encore keycloak_client_id/keycloak_internal_id -- les ajoute
    si absentes, même patron que les migrations ensure_*_column
    ailleurs dans le projet (tickets-api, vault-api). CREATE TABLE IF
    NOT EXISTS (ensure_schema ci-dessus) ne touche jamais une table
    déjà existante, migration séparée indispensable ici."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        for column in ("keycloak_client_id", "keycloak_internal_id", "keycloak_redirect_uri"):
            try:
                cur.execute(f"ALTER TABLE external_links ADD COLUMN {column} TEXT")
                conn.commit()
            except Exception:
                conn.rollback()
    finally:
        conn.close()


# Départ de l'écran "Cyber" (livraison #187) -- les 14 risques
# identifiés dans docs/cyber-risques-resume.md (livraison #186),
# reformulés en langage ACCESSIBLE (label/description) -- cible
# explicite "politiques et béotiens", jamais de jargon technique en
# première lecture. `modules` reste technique (juste une étiquette de
# référence, pas la donnée principale de l'écran). N'insère QUE si la
# table est VIDE -- jamais un doublon au redémarrage, jamais un écrasement
# d'un statut/avancement déjà modifié par la personne.
_INITIAL_CYBER_RISKS = [
    ("Cloisonnement du réseau interne",
     "Tous les programmes du projet peuvent aujourd'hui se parler librement entre eux -- comme des bureaux sans porte verrouillée à l'intérieur d'un même bâtiment.",
     "Réseau", "Tout le stack", "moyenne", "élevé", "hub"),
    ("Contrôle des accès entre programmes internes",
     "N'importe quel programme du projet peut aujourd'hui en interroger un autre sans avoir à prouver qui il est.",
     "Accès", "Toutes les API internes", "moyenne", "élevé", "hub"),
    ("Accès aux bases de données via les connexions distantes",
     "Une fois ouverte, une connexion sécurisée vers un vieux serveur de base de données est accessible depuis tous les autres programmes du projet.",
     "Accès", "ssh-tunnels, dba-api", "faible", "élevé", "si_supervise"),
    ("Mots de passe stockés en clair",
     "Les mots de passe et codes secrets utilisés par les programmes (bases de données, messagerie...) sont enregistrés en texte lisible sur le disque, jamais chiffrés.",
     "Secrets", "Tout le stack", "moyenne", "élevé", "si_supervise"),
    ("Clés de connexion SSH non chiffrées",
     "Les clés utilisées pour se connecter aux serveurs distants sont stockées sur le disque sans chiffrement supplémentaire (accès déjà restreint en lecture seule).",
     "Secrets", "ssh-tunnels", "faible", "élevé", "si_supervise"),
    ("Droits élevés accordés à un programme",
     "Le programme qui gère les partages de fichiers distants a besoin de droits techniques étendus sur sa machine pour fonctionner -- une nécessité documentée, pas un oubli.",
     "Système", "ssh-tunnels", "faible", "élevé", "hub"),
    ("Vérification des données saisies dans les requêtes base de données",
     "Une fonctionnalité récente permet des requêtes flexibles sur les bases de données ; la protection contre une saisie malveillante est en place mais reste basique.",
     "Code", "schema-analyzer, dba-api", "moyenne", "moyen", "si_supervise"),
    ("Conservation des journaux d'activité",
     "Les traces de fonctionnement des programmes sont perdues à chaque redémarrage -- utiles pour surveiller en direct, mais rien ne reste pour enquêter après coup.",
     "Traçabilité", "Tout le stack", "élevée", "moyen", "hub"),
    ("Contenu sensible dans les journaux",
     "Les messages d'erreur enregistrés pourraient occasionnellement contenir des informations sensibles, sans filtrage systématique avant stockage.",
     "Traçabilité", "Tout le stack", "moyenne", "moyen", "hub"),
    ("Logiciel de gestion documentaire externe",
     "Le système de gestion électronique de documents utilisé est un logiciel tiers, dont la sécurité n'a pas été auditée par notre équipe.",
     "Dépendance externe", "ged, mayan", "faible", "moyen", "hub"),
    ("Futur : mots de passe pour les connexions SSH",
     "Une évolution prévue permettrait de se connecter à de vieux serveurs par mot de passe plutôt que par clé -- un mot de passe est intrinsèquement moins robuste qu'une clé.",
     "Évolution prévue", "ssh-tunnels", "à évaluer", "à évaluer", "si_supervise"),
    ("Futur : supervision des équipements réseau",
     "Le protocole envisagé pour interroger les équipements réseau repose souvent sur un simple mot de passe partagé, facilement devinable si mal choisi.",
     "Évolution prévue", "futur module SNMP", "à évaluer", "à évaluer", "si_supervise"),
    ("Bibliothèques logicielles utilisées",
     "Les briques logicielles tierces utilisées par le projet ne sont pas encore vérifiées automatiquement contre les failles de sécurité déjà connues et publiées.",
     "Dépendance externe", "Tout le stack", "moyenne", "moyen", "hub"),
    ("Réception de journaux réseau non authentifiée",
     "Le service qui reçoit les journaux d'autres équipements accepte les envois sans vérifier qui les envoie réellement -- une limite du protocole standard utilisé, pas une erreur de conception.",
     "Réseau", "rsyslog-listener", "moyenne", "faible", "hub"),
]

# Reclassement (livraison #193, évolution ISO/IEC 27001) des 14
# risques ci-dessus pour une base DÉJÀ peuplée AVANT cette livraison
# (scope alors inexistant) -- mise en correspondance par LIBELLÉ
# EXACT (jamais par position -- si la personne a réordonné/modifié
# des lignes depuis #187, cette correspondance reste correcte).
_INITIAL_CYBER_RISKS_SCOPE_BY_LABEL = {label: scope for (label, _d, _c, _m, _p, _i, scope) in _INITIAL_CYBER_RISKS}


def ensure_cyber_risks_seeded():
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM cyber_risks")
        if cur.fetchone()[0] > 0:
            return  # déjà peuplée (premier démarrage passé, ou risques ajoutés/modifiés depuis) -- jamais toucher à nouveau
        now = now_iso()
        for label, description, category, modules, probability, impact, scope in _INITIAL_CYBER_RISKS:
            cur.execute(
                """INSERT INTO cyber_risks
                   (label, description, category, modules, probability, impact, scope, status, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 'a_traiter', ?, ?)""",
                [label, description, category, modules, probability, impact, scope, now, now],
            )
        conn.commit()
    finally:
        conn.close()


def ensure_cyber_risks_scope_column():
    """Migration (livraison #193, évolution ISO/IEC 27001) -- pour
    une base DÉJÀ peuplée par #187 (avant l'existence de `scope`) :
    ajoute la colonne si absente (`ALTER TABLE`, motif idempotent
    déjà établi ailleurs dans ce fichier), PUIS reclasse les 14
    risques de départ CONNUS par leur libellé exact -- jamais une
    valeur par défaut aveugle pour ceux-là, on SAIT dans quelle
    catégorie ils vont. Un risque ajouté DEPUIS par la personne (donc
    pas dans cette liste) garde le défaut 'hub' de la colonne --
    jamais réécrit ici, à ajuster manuellement si besoin (l'onglet
    Suivi le permet)."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(cyber_risks)")
        existing_columns = {row[1] for row in cur.fetchall()}
        if "scope" not in existing_columns:
            cur.execute("ALTER TABLE cyber_risks ADD COLUMN scope TEXT NOT NULL DEFAULT 'hub'")
            conn.commit()
            for label, scope in _INITIAL_CYBER_RISKS_SCOPE_BY_LABEL.items():
                cur.execute("UPDATE cyber_risks SET scope = ? WHERE label = ?", [scope, label])
            conn.commit()
    finally:
        conn.close()


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# Documents de gouvernance de départ (livraison #195) -- métadonnée
# ICI, CONTENU lu depuis PROJECT_ROOT_PATH/docs/ au moment du
# démarrage (voir ensure_governance_documents_seeded) -- jamais le
# contenu binaire codé en dur dans ce fichier source, illisible et
# invérifiable autrement que via le fichier réel sur disque.
_INITIAL_GOVERNANCE_DOCUMENTS = [
    # (name, description, version, filename relatif à docs/, content_type)
    (
        "Charte d'usage du système d'information",
        "Règles d'usage du SI -- volet \"Sécurité du poste de travail\" en premier (dont le branchement USB d'un mobile, recharge et transfert de données).",
        "1.0", "charte-usage-si.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    (
        "Notice — Outils d'autoformation aux bonnes pratiques numériques",
        "Liens vers des ressources d'autoformation officielles et gratuites (ANSSI, Cybermalveillance.gouv.fr).",
        "1.0", "notice-autoformation-cybersecurite.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    (
        "PRA — Secrets de démarrage chiffrés",
        "Procédure de garde et de récupération de la clé maîtresse (mots de passe .env, clés SSH) -- réponse au point 4 de l'urgence matrice de risque.",
        "1.0", "pra-secrets-demarrage.docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
]


def ensure_governance_documents_seeded():
    """Lit les fichiers RÉELS depuis PROJECT_ROOT_PATH/docs/ (même
    montage LECTURE SEULE déjà utilisé par _discover_readmes) et les
    insère encodés en base64 -- SEULEMENT si la table est VIDE (même
    garde que ensure_cyber_risks_seeded, #187) : jamais un écrasement
    d'un document déjà éventuellement mis à jour depuis (nouvelle
    version chargée via PUT /governance-documents/<id>, à venir).
    Fichier source absent (mauvais montage, ou repo modifié depuis) --
    ce document précis est simplement SAUTÉ, jamais une exception qui
    bloquerait le démarrage entier de prefs-api pour ça."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM governance_documents")
        if cur.fetchone()[0] > 0:
            return
        now = now_iso()
        for name, description, version, filename, content_type in _INITIAL_GOVERNANCE_DOCUMENTS:
            source_path = os.path.join(PROJECT_ROOT_PATH, "docs", filename)
            if not os.path.isfile(source_path):
                app.logger.warning("Document de gouvernance introuvable au démarrage, ignoré : %s", source_path)
                continue
            with open(source_path, "rb") as f:
                content_base64 = base64.b64encode(f.read()).decode("ascii")
            cur.execute(
                """INSERT INTO governance_documents
                   (name, description, version, filename, content_type, content_base64, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                [name, description, version, filename, content_type, content_base64, now, now],
            )
        conn.commit()
    finally:
        conn.close()


def ensure_governance_document_present(name):
    """Migration (livraison #203) -- pour une base DÉJÀ peuplée
    (`ensure_governance_documents_seeded` ci-dessus ne s'exécute
    alors plus, la table n'est plus vide) : ajoute UN document précis
    de `_INITIAL_GOVERNANCE_DOCUMENTS`, repéré par son `name`, s'il
    est absent -- jamais un doublon si déjà présent (ex. réinstallation,
    ou fonction rappelée). Fonction GÉNÉRALE, réutilisable pour toute
    future addition ponctuelle à ce catalogue sans nouvelle fonction
    dédiée à chaque fois."""
    conn = sqlite3.connect(DB_PATH)
    try:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM governance_documents WHERE name = ?", [name])
        if cur.fetchone()[0] > 0:
            return
        entry = next((e for e in _INITIAL_GOVERNANCE_DOCUMENTS if e[0] == name), None)
        if entry is None:
            app.logger.warning("ensure_governance_document_present : '%s' absent de _INITIAL_GOVERNANCE_DOCUMENTS", name)
            return
        doc_name, description, version, filename, content_type = entry
        source_path = os.path.join(PROJECT_ROOT_PATH, "docs", filename)
        if not os.path.isfile(source_path):
            app.logger.warning("Document de gouvernance introuvable au démarrage, ignoré : %s", source_path)
            return
        with open(source_path, "rb") as f:
            content_base64 = base64.b64encode(f.read()).decode("ascii")
        now = now_iso()
        cur.execute(
            """INSERT INTO governance_documents
               (name, description, version, filename, content_type, content_base64, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [doc_name, description, version, filename, content_type, content_base64, now, now],
        )
        conn.commit()
    finally:
        conn.close()


try:
    ensure_schema()
    ensure_external_links_keycloak_columns()
    ensure_cyber_risks_seeded()
    ensure_cyber_risks_scope_column()
    ensure_governance_documents_seeded()
    ensure_governance_document_present("PRA — Secrets de démarrage chiffrés")
except Exception as exc:  # noqa: BLE001 — la base peut ne pas être prête au tout premier démarrage
    app.logger.warning("Migration au démarrage reportée : %s", exc)


@app.route("/preferences", methods=["GET"])
def get_preferences():
    login = (request.args.get("user") or "").strip()
    if not login:
        return jsonify({"error": "paramètre 'user' requis"}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT data FROM preferences WHERE login = ?", [login])
        row = cur.fetchone()
        if row is None:
            # Jamais de 404 ici -- l'absence de préférences enregistrées
            # est le cas NORMAL (première visite), pas une erreur. Le
            # front reçoit les valeurs par défaut, à lui de les
            # appliquer comme s'il s'agissait de vraies préférences.
            return jsonify(dict(DEFAULT_PREFERENCES)), 200
        try:
            data = json.loads(row["data"])
        except (TypeError, ValueError):
            return jsonify(dict(DEFAULT_PREFERENCES)), 200
        merged = {**DEFAULT_PREFERENCES, **data}
        return jsonify(merged), 200
    finally:
        conn.close()


@app.route("/preferences", methods=["PUT"])
def put_preferences():
    login = (request.args.get("user") or "").strip()
    if not login:
        return jsonify({"error": "paramètre 'user' requis"}), 400
    body = request.get_json(silent=True) or {}
    if "theme" in body and body["theme"] not in ("light", "dark"):
        return jsonify({"error": "theme doit être 'light' ou 'dark'"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT data FROM preferences WHERE login = ?", [login])
        row = cur.fetchone()
        existing = {}
        if row is not None:
            try:
                existing = json.loads(row["data"])
            except (TypeError, ValueError):
                existing = {}
        # Fusion superficielle -- un PUT ne renseignant QUE "theme" ne
        # doit jamais écraser d'autres préférences enregistrées par
        # ailleurs (ex. une future préférence de densité d'affichage).
        merged = {**existing, **body}
        cur.execute(
            """INSERT INTO preferences (login, data, updated_at) VALUES (?, ?, ?)
               ON CONFLICT(login) DO UPDATE SET data = excluded.data, updated_at = excluded.updated_at""",
            [login, json.dumps(merged), now_iso()],
        )
        conn.commit()
        return jsonify({**DEFAULT_PREFERENCES, **merged}), 200
    finally:
        conn.close()


@app.route("/app-settings", methods=["GET"])
def get_app_settings():
    """Paramétrage global d'une application -- `app` requis (ex.
    "tickets", "hub"). Renvoie {} si rien n'a jamais été configuré,
    jamais une erreur -- une application sans paramétrage global
    encore défini est un état normal, pas un problème."""
    app_name = (request.args.get("app") or "").strip()
    if not app_name:
        return jsonify({"error": "paramètre 'app' requis"}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT data FROM app_settings WHERE app_name = ?", [app_name])
        row = cur.fetchone()
        if row is None:
            return jsonify({}), 200
        try:
            return jsonify(json.loads(row["data"])), 200
        except (TypeError, ValueError):
            return jsonify({}), 200
    finally:
        conn.close()


@app.route("/app-settings", methods=["PUT"])
def put_app_settings():
    app_name = (request.args.get("app") or "").strip()
    actor = (request.args.get("actor") or "").strip() or None
    if not app_name:
        return jsonify({"error": "paramètre 'app' requis"}), 400
    body = request.get_json(silent=True) or {}

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT data FROM app_settings WHERE app_name = ?", [app_name])
        row = cur.fetchone()
        existing = {}
        if row is not None:
            try:
                existing = json.loads(row["data"])
            except (TypeError, ValueError):
                existing = {}
        # Fusion superficielle -- même raisonnement que preferences :
        # un PUT ne renseignant qu'UN paramètre ne doit jamais écraser
        # les autres déjà enregistrés pour cette application.
        merged = {**existing, **body}
        cur.execute(
            """INSERT INTO app_settings (app_name, data, updated_by, updated_at) VALUES (?, ?, ?, ?)
               ON CONFLICT(app_name) DO UPDATE SET data = excluded.data, updated_by = excluded.updated_by, updated_at = excluded.updated_at""",
            [app_name, json.dumps(merged), actor, now_iso()],
        )
        conn.commit()
        return jsonify(merged), 200
    finally:
        conn.close()


CHANGELOG_PATH = os.environ.get("CHANGELOG_PATH", "/data/CHANGELOG.md")
BACKLOG_PATH = os.environ.get("BACKLOG_PATH", "/data/BACKLOG.md")


def read_markdown_file(path):
    """Lit un fichier markdown monté en lecture seule (volume Docker
    pointant directement vers le fichier réel à la racine du dépôt --
    jamais une copie figée au build, ces fichiers changent à chaque
    livraison). Jamais une exception qui remonterait telle quelle --
    un déploiement où le montage n'aurait pas été fait doit échouer
    proprement avec un message clair, pas un plantage confus."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read(), None
    except FileNotFoundError:
        return None, "fichier introuvable -- vérifier le montage du volume (voir docker-compose.yml, service prefs-api)"
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)


@app.route("/changelog", methods=["GET"])
def get_changelog():
    """Contenu brut de CHANGELOG.md -- demandé explicitement (vue
    historique des évolutions dans le hub, plutôt qu'un fichier texte
    à ouvrir manuellement). Servi tel quel, le rendu markdown se fait
    côté client (hub/src/markdown.js)."""
    content, error = read_markdown_file(CHANGELOG_PATH)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"content": content}), 200


@app.route("/backlog", methods=["GET"])
def get_backlog():
    """Même principe que /changelog, pour BACKLOG.md."""
    content, error = read_markdown_file(BACKLOG_PATH)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"content": content}), 200


# ------------------------------------------------------------------
# Aide du hub -- s'enrichit des README du projet (livraison #143,
# demandé explicitement : "une aide qui s'enrichit des readme et des
# exemples"). Les README contiennent DÉJÀ abondamment les exemples
# (commandes curl, extraits JSON...) -- les afficher couvre les deux
# à la fois, pas besoin d'une base d'exemples séparée à maintenir.
#
# ATTENTION SÉCURITÉ -- PROJECT_ROOT_PATH est monté en lecture seule
# sur la RACINE ENTIÈRE du dépôt (voir docker-compose.yml), ce qui
# inclut potentiellement .env, les clés PKI, les sauvegardes de realm
# Keycloak... La SEULE protection entre "monté en lecture" et
# "lisible depuis cette API" est la liste blanche ci-dessous --
# JAMAIS un chemin arbitraire fourni par le client, JAMAIS un fichier
# qui ne serait pas nommé EXACTEMENT "README.md". Trois couches :
# (1) le nom de fichier lui-même (aucun secret de ce projet ne
# s'appelle jamais README.md), (2) exclusion de dossiers CONNUS pour
# contenir du contenu généré/sensible (défense en profondeur, pas la
# protection principale), (3) toute lecture revalide le chemin contre
# une redécouverte EN DIRECT (jamais une liste mise en cache qui
# pourrait diverger), PLUS une normalisation qui refuse tout chemin
# sortant de PROJECT_ROOT_PATH même si la liste blanche avait un trou.
# ------------------------------------------------------------------
# PROJECT_ROOT_PATH lui-même est défini plus haut dans ce fichier
# (juste après DB_PATH) -- déplacé lors de la livraison #195 pour
# être disponible dès le bloc `try` de démarrage, voir le commentaire
# à cet endroit. Ce qui suit reste la référence pour le raisonnement
# de sécurité complet sur ce montage.
# Dossiers connus pour contenir du contenu généré ou sensible --
# jamais descendus pendant la découverte. Chemins RELATIFS à
# PROJECT_ROOT_PATH (pas de simples noms de dossier : "server" seul
# exclurait par erreur un dossier sans rapport ailleurs dans le
# projet qui porterait ce nom).
_DOCS_EXCLUDED_RELATIVE_DIRS = {
    ".git", "node_modules", "__pycache__", "data",
    "pki/ca", "pki/server",
    "keycloak/import", "keycloak/backup",
    "tls-proxy/generated", "apache/generated",
}


def _discover_readmes():
    """Parcourt PROJECT_ROOT_PATH à la recherche de fichiers nommés
    EXACTEMENT "README.md" -- volontairement étroit, voir le
    commentaire de sécurité ci-dessus. Racine absente (montage pas
    fait) -- liste vide, jamais une exception."""
    if not os.path.isdir(PROJECT_ROOT_PATH):
        return []
    results = []
    for dirpath, dirnames, filenames in os.walk(PROJECT_ROOT_PATH):
        rel_dir = os.path.relpath(dirpath, PROJECT_ROOT_PATH)
        rel_dir = "" if rel_dir == "." else rel_dir.replace(os.sep, "/")
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".")
            and (f"{rel_dir}/{d}" if rel_dir else d) not in _DOCS_EXCLUDED_RELATIVE_DIRS
        ]
        if "README.md" in filenames:
            rel_path = f"{rel_dir}/README.md" if rel_dir else "README.md"
            results.append(rel_path)
    return sorted(results)


@app.route("/governance-documents", methods=["GET"])
def list_governance_documents():
    """Liste SANS le contenu (`content_base64` omis) -- potentiellement
    volumineux, inutile pour un simple affichage de liste avec
    version/date, uniquement récupéré par appel séparé au
    téléchargement."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT id, name, description, version, filename, content_type, created_at, updated_at FROM governance_documents ORDER BY id")
        docs = [dict(row) for row in cur.fetchall()]
        return jsonify(docs), 200
    finally:
        conn.close()


@app.route("/governance-documents/<int:doc_id>/download", methods=["GET"])
def download_governance_document(doc_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM governance_documents WHERE id = ?", [doc_id])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "document introuvable"}), 404
        content = base64.b64decode(row["content_base64"])
        return Response(
            content, mimetype=row["content_type"],
            headers={"Content-Disposition": f'attachment; filename="{row["filename"]}"'},
        )
    finally:
        conn.close()


@app.route("/docs", methods=["GET"])
def list_docs():
    """Liste des README découverts -- "s'enrichit" automatiquement,
    un nouveau README.md ajouté n'importe où dans le dépôt apparaît
    au prochain appel, sans le moindre code à modifier ici."""
    return jsonify({"docs": _discover_readmes()}), 200


@app.route("/docs/<path:doc_path>", methods=["GET"])
def get_doc(doc_path):
    """Contenu d'UN README découvert. REFUSE tout chemin n'apparaissant
    pas dans une redécouverte EN DIRECT (jamais une confiance aveugle
    dans le chemin fourni par le client, jamais une liste mise en
    cache qui pourrait diverger de ce qui existe réellement) -- PUIS
    une normalisation qui refuse tout chemin sortant de
    PROJECT_ROOT_PATH, défense en profondeur même si la liste blanche
    avait un trou quelque part."""
    if doc_path not in set(_discover_readmes()):
        return jsonify({"error": "document non trouvé ou non autorisé"}), 404
    root = os.path.normpath(PROJECT_ROOT_PATH)
    full_path = os.path.normpath(os.path.join(root, doc_path))
    if not (full_path == root or full_path.startswith(root + os.sep)):
        return jsonify({"error": "chemin invalide"}), 400
    content, error = read_markdown_file(full_path)
    if error:
        return jsonify({"error": error}), 404
    return jsonify({"content": content, "path": doc_path}), 200


@app.route("/architecture-diagram", methods=["GET"])
def get_architecture_diagram():
    """Vue graphique de l'architecture du projet (livraison #207,
    volet transparence -- 2e partie, la 1re -- historique versionné
    -- ayant été livrée en #199). Fichier FIXE (jamais un chemin
    fourni par le client -- contrairement à /docs/<path>, aucune
    surface d'attaque par chemin ici), lu depuis
    PROJECT_ROOT_PATH/docs/, servi avec le VRAI type MIME SVG --
    permet un simple `<img src=...>` côté hub, sans manipulation de
    chaîne SVG côté client."""
    full_path = os.path.join(PROJECT_ROOT_PATH, "docs", "architecture-projet.svg")
    if not os.path.isfile(full_path):
        return jsonify({"error": "diagramme d'architecture introuvable"}), 404
    with open(full_path, "rb") as f:
        content = f.read()
    return Response(content, mimetype="image/svg+xml")


@app.route("/events", methods=["POST"])
def create_hub_event():
    """Timeline du hub -- backlog, livraison #118. `category` doit être
    l'une des 4 valeurs connues (voir VALID_HUB_EVENT_CATEGORIES) ;
    `login` optionnel mais fortement recommandé (la timeline est
    PERSONNELLE, voir commentaire du schéma) ; `ts` toujours posé côté
    serveur (jamais transmis par l'appelant -- l'horodatage de
    réception fait foi, cohérent quel que soit le décalage d'horloge
    du navigateur)."""
    body = request.get_json(silent=True) or {}
    login = (body.get("login") or "").strip() or None
    category = body.get("category")
    label = body.get("label")
    data = body.get("data")
    if category not in VALID_HUB_EVENT_CATEGORIES:
        return jsonify({"error": f"category doit être l'une de : {', '.join(VALID_HUB_EVENT_CATEGORIES)}"}), 400

    ts = int(time.time())
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO hub_events (ts, login, category, label, data, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [ts, login, category, label, json.dumps(data) if data is not None else None, now_iso()],
        )
        conn.commit()
        return jsonify({"status": "ok", "id": cur.lastrowid, "ts": ts}), 201
    finally:
        conn.close()


@app.route("/events", methods=["GET"])
def list_hub_events():
    """Fenêtre glissante pour la timeline du hub. `login` optionnel
    (absent = tous les logins confondus -- jamais utilisé par la
    timeline personnelle elle-même, qui filtre toujours sur son PROPRE
    login ; gardé pour un futur usage transversal éventuel).
    `since`/`until` en timestamp Unix (secondes). Triée du plus récent
    au plus ancien -- même esprit "flux d'activité récente" que le
    journal du tableau de bord coffre-fort."""
    login = (request.args.get("login") or "").strip() or None
    since = request.args.get("since", type=int)
    until = request.args.get("until", type=int)
    limit = min(int(request.args.get("limit", 200)), 1000)

    conditions = []
    params = []
    if login:
        conditions.append("login = ?")
        params.append(login)
    if since is not None:
        conditions.append("ts >= ?")
        params.append(since)
    if until is not None:
        conditions.append("ts <= ?")
        params.append(until)
    where_sql = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"SELECT id, ts, login, category, label, data, created_at FROM hub_events {where_sql} ORDER BY ts DESC LIMIT ?",
            params + [limit],
        )
        events = []
        for row in cur.fetchall():
            try:
                parsed_data = json.loads(row["data"]) if row["data"] else None
            except (TypeError, ValueError):
                parsed_data = None
            events.append({
                "id": row["id"],
                "ts": row["ts"],
                "login": row["login"],
                "category": row["category"],
                "label": row["label"],
                "data": parsed_data,
            })
        return jsonify({"events": events}), 200
    finally:
        conn.close()


def row_to_external_link(row):
    """Convertit une ligne SQL en dict prêt pour l'API -- allowed_roles
    toujours une LISTE côté client (jamais la chaîne JSON brute ni
    None), embeddable toujours un booléen. Ligne corrompue
    (allowed_roles pas du JSON valide) -- liste vide, jamais une
    exception qui ferait échouer tout le listing pour une seule
    entrée."""
    d = dict(row)
    try:
        d["allowed_roles"] = json.loads(d["allowed_roles"]) if d["allowed_roles"] else []
    except (TypeError, ValueError):
        d["allowed_roles"] = []
    d["embeddable"] = bool(d["embeddable"])
    return d


def clean_allowed_roles(value):
    """Filtre une valeur reçue vers un sous-ensemble cohérent de
    VALID_EXTERNAL_LINK_ROLES -- jamais un rôle inventé stocké
    silencieusement (même raisonnement que required_labels côté
    coffre-fort), jamais une exception si `value` n'est pas une liste
    (retombe sur aucun rôle -- équivalent à "visible de tout le
    monde" si personne n'en a coché, comportement sûr par défaut)."""
    if not isinstance(value, list):
        return []
    return [r for r in value if r in VALID_EXTERNAL_LINK_ROLES]


@app.route("/external-links", methods=["GET"])
def list_external_links():
    """Liste TOUS les liens externes, quel que soit l'appelant --
    AUCUNE vérification de rôle côté serveur (voir commentaire du
    schéma) : le hub filtre par rôle côté client au moment de
    l'affichage (buildFrontsList), l'écran d'administration a de
    toute façon besoin de tout voir pour éditer -- jamais une route
    séparée "déjà filtrée" qui dupliquerait cette logique."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM external_links ORDER BY name")
        return jsonify([row_to_external_link(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/external-links", methods=["POST"])
def create_external_link():
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    url = (body.get("url") or "").strip()
    if not name or not url:
        return jsonify({"error": "'name' et 'url' requis"}), 400

    description = body.get("description")
    embeddable = 1 if body.get("embeddable") else 0
    allowed_roles = clean_allowed_roles(body.get("allowed_roles"))
    created_by = (body.get("actor") or "").strip() or None
    now = now_iso()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO external_links
               (name, description, url, embeddable, allowed_roles, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [name, description, url, embeddable, json.dumps(allowed_roles), created_by, now, now],
        )
        conn.commit()
        return jsonify({"status": "ok", "id": cur.lastrowid}), 201
    finally:
        conn.close()


@app.route("/external-links/<int:link_id>", methods=["PUT"])
def update_external_link(link_id):
    """Mise à jour PARTIELLE -- un champ absent du corps garde sa
    valeur existante (même esprit que la fusion superficielle de
    /preferences et /app-settings), jamais un écrasement total. `name`/
    `url` ne peuvent jamais être vidés par une valeur blanche (retombe
    sur l'existant plutôt que d'accepter silencieusement un lien sans
    nom ou sans URL)."""
    body = request.get_json(silent=True) or {}
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM external_links WHERE id = ?", [link_id])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "lien introuvable"}), 404
        existing = row_to_external_link(row)

        name = ((body.get("name") or "").strip() if "name" in body else existing["name"]) or existing["name"]
        url = ((body.get("url") or "").strip() if "url" in body else existing["url"]) or existing["url"]
        description = body.get("description") if "description" in body else existing["description"]
        embeddable = 1 if body.get("embeddable", existing["embeddable"]) else 0
        allowed_roles = clean_allowed_roles(body["allowed_roles"]) if "allowed_roles" in body else existing["allowed_roles"]

        cur.execute(
            """UPDATE external_links
               SET name = ?, description = ?, url = ?, embeddable = ?, allowed_roles = ?, updated_at = ?
               WHERE id = ?""",
            [name, description, url, embeddable, json.dumps(allowed_roles), now_iso(), link_id],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/external-links/<int:link_id>", methods=["DELETE"])
def delete_external_link(link_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM external_links WHERE id = ?", [link_id])
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


# ------------------------------------------------------------------
# Sources de logs configurées (livraison #147, backlog "logs de
# toutes sortes", BACKLOG.md #3). CRUD complet mais SEULS les types
# "url" (#147) et "file" (#176) sont traités par le sondeur en tâche
# de fond (voir log_sources_poller.py/file_source_poller.py) --
# "rsyslog" accepté ici (pour ne pas devoir remodifier ce CRUD à
# chaque étape) mais n'a encore AUCUN effet, reste silencieusement
# inerte tant que son étape n'est pas livrée. "push" n'a JAMAIS
# d'entrée ici (s'enregistre lui-même implicitement, voir
# POST /push-log plus haut).
# ------------------------------------------------------------------
VALID_LOG_SOURCE_TYPES = ("url", "file", "rsyslog")


def row_to_log_source(row):
    """Convertit une ligne SQL en dict prêt pour l'API -- `config`
    toujours un OBJET côté client (jamais la chaîne JSON brute).
    Ligne corrompue (config pas du JSON valide) -- objet vide, jamais
    une exception qui ferait échouer tout le listing pour une seule
    entrée (même principe que row_to_external_link)."""
    d = dict(row)
    try:
        d["config"] = json.loads(d["config"]) if d["config"] else {}
        if not isinstance(d["config"], dict):
            d["config"] = {}
    except (TypeError, ValueError):
        d["config"] = {}
    d["enabled"] = bool(d["enabled"])
    return d


def validate_log_source_config(source_type, config):
    """Valide la forme de `config` SELON `type`. "url" et "file"
    (livraison #176) ont une forme réellement vérifiée ; "rsyslog"
    accepte n'importe quel objet JSON pour l'instant, sa forme
    définitive n'étant pas encore arrêtée (étape 4/4, pas commencée).
    Renvoie (config_normalisé, erreur) -- erreur = None si valide."""
    if not isinstance(config, dict):
        return None, "'config' doit être un objet"
    if source_type == "url":
        url = (config.get("url") or "").strip()
        if not url:
            return None, "config.url requis pour une source de type 'url'"
        interval = config.get("interval_seconds", 60)
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            return None, "config.interval_seconds doit être un nombre entier"
        if interval < 5:
            return None, "config.interval_seconds doit être ≥ 5 (jamais un sondage trop agressif)"
        fmt = (config.get("format") or "plain").strip().lower()
        if fmt not in ("jsonl", "plain"):
            return None, "config.format doit être 'jsonl' ou 'plain'"
        return {"url": url, "interval_seconds": interval, "format": fmt}, None
    if source_type == "file":
        # `path` RELATIF, résolu à l'intérieur de LOG_FILES_BASE_DIR
        # (voir file_source_poller._resolve_safe_path) -- jamais un
        # chemin absolu accepté ICI (le refus définitif se fait au
        # sondage, contre le VRAI répertoire monté, mais autant
        # prévenir tout de suite un chemin manifestement invalide).
        path = (config.get("path") or "").strip()
        if not path:
            return None, "config.path requis pour une source de type 'file'"
        if path.startswith("/") or path.startswith("\\") or ".." in path.split("/"):
            return None, "config.path doit être un chemin RELATIF, sans '..' (résolu depuis le répertoire de logs monté, jamais un chemin absolu)"
        interval = config.get("interval_seconds", 30)
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            return None, "config.interval_seconds doit être un nombre entier"
        if interval < 5:
            return None, "config.interval_seconds doit être ≥ 5 (jamais un sondage trop agressif)"
        return {"path": path, "interval_seconds": interval}, None
    # "rsyslog" -- pas encore de forme arrêtée, accepté tel quel.
    return config, None


VALID_CYBER_RISK_SCOPES = ("hub", "si_supervise")


def row_to_cyber_risk(row):
    return {
        "id": row["id"],
        "label": row["label"],
        "description": row["description"],
        "category": row["category"],
        "modules": row["modules"],
        "probability": row["probability"],
        "impact": row["impact"],
        "scope": row["scope"],
        "status": row["status"],
        "progress_notes": row["progress_notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@app.route("/cyber-risks", methods=["GET"])
def list_cyber_risks():
    """Liste TOUS les risques -- aucun filtrage serveur (même posture
    que external_links) : l'écran "Cyber" du hub a besoin de tout
    voir, aucune notion de rôle particulière sur cette donnée."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM cyber_risks ORDER BY id")
        return jsonify([row_to_cyber_risk(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


def _record_cyber_risk_history(conn, cur, risk_id, change_type, risk_dict, recorded_at):
    """Instantané COMPLET du risque au moment de l'écriture -- voir
    le commentaire du schéma (cyber_risks_history) pour le
    raisonnement. Appelée à l'intérieur de la MÊME transaction que
    l'écriture sur cyber_risks (même `cur`/`conn`, un seul `commit()`
    côté appelant) -- jamais un historique qui pourrait diverger de
    la table principale si l'un des deux échouait seul."""
    cur.execute(
        """INSERT INTO cyber_risks_history
           (risk_id, change_type, label, description, category, modules,
            probability, impact, scope, status, progress_notes, recorded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        [risk_id, change_type, risk_dict["label"], risk_dict["description"], risk_dict["category"],
         risk_dict["modules"], risk_dict["probability"], risk_dict["impact"], risk_dict["scope"],
         risk_dict["status"], risk_dict["progress_notes"], recorded_at],
    )


@app.route("/cyber-risks", methods=["POST"])
def create_cyber_risk():
    """Ajout d'un risque IDENTIFIÉ APRÈS COUP (les 14 initiaux sont
    déjà en place via ensure_cyber_risks_seeded) -- l'écran doit
    pouvoir grandir au fil de la conception, jamais figé à la liste
    de départ. `scope` (livraison #193) : "hub" par défaut si absent
    -- validé contre VALID_CYBER_RISK_SCOPES, jamais une valeur
    arbitraire stockée qui casserait le classement de la matrice."""
    body = request.get_json(silent=True) or {}
    label = (body.get("label") or "").strip()
    probability = (body.get("probability") or "").strip()
    impact = (body.get("impact") or "").strip()
    if not label or not probability or not impact:
        return jsonify({"error": "'label', 'probability' et 'impact' requis"}), 400
    scope = (body.get("scope") or "hub").strip()
    if scope not in VALID_CYBER_RISK_SCOPES:
        return jsonify({"error": f"'scope' doit être l'un de {VALID_CYBER_RISK_SCOPES}"}), 400

    description = body.get("description")
    category = body.get("category")
    modules = body.get("modules")
    now = now_iso()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO cyber_risks
               (label, description, category, modules, probability, impact, scope, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'a_traiter', ?, ?)""",
            [label, description, category, modules, probability, impact, scope, now, now],
        )
        new_id = cur.lastrowid
        _record_cyber_risk_history(conn, cur, new_id, "created", {
            "label": label, "description": description, "category": category, "modules": modules,
            "probability": probability, "impact": impact, "scope": scope,
            "status": "a_traiter", "progress_notes": None,
        }, now)
        conn.commit()
        return jsonify({"status": "ok", "id": new_id}), 201
    finally:
        conn.close()


@app.route("/cyber-risks/<int:risk_id>", methods=["PUT"])
def update_cyber_risk(risk_id):
    """Champs tous OPTIONNELS -- l'usage principal attendu est de ne
    changer QUE `status`/`progress_notes` (le suivi d'avancement, but
    premier de l'onglet dédié) sans jamais devoir retransmettre tout
    le risque à chaque petite mise à jour."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM cyber_risks WHERE id = ?", [risk_id])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "risque introuvable"}), 404

        body = request.get_json(silent=True) or {}
        if "scope" in body and body["scope"] not in VALID_CYBER_RISK_SCOPES:
            return jsonify({"error": f"'scope' doit être l'un de {VALID_CYBER_RISK_SCOPES}"}), 400
        current = row_to_cyber_risk(row)
        updated = {
            "label": body.get("label", current["label"]),
            "description": body.get("description", current["description"]),
            "category": body.get("category", current["category"]),
            "modules": body.get("modules", current["modules"]),
            "probability": body.get("probability", current["probability"]),
            "impact": body.get("impact", current["impact"]),
            "scope": body.get("scope", current["scope"]),
            "status": body.get("status", current["status"]),
            "progress_notes": body.get("progress_notes", current["progress_notes"]),
        }
        now = now_iso()
        cur.execute(
            """UPDATE cyber_risks SET label = ?, description = ?, category = ?, modules = ?,
               probability = ?, impact = ?, scope = ?, status = ?, progress_notes = ?, updated_at = ?
               WHERE id = ?""",
            [updated["label"], updated["description"], updated["category"], updated["modules"],
             updated["probability"], updated["impact"], updated["scope"], updated["status"], updated["progress_notes"],
             now, risk_id],
        )
        _record_cyber_risk_history(conn, cur, risk_id, "updated", updated, now)
        conn.commit()
        cur.execute("SELECT * FROM cyber_risks WHERE id = ?", [risk_id])
        return jsonify(row_to_cyber_risk(cur.fetchone())), 200
    finally:
        conn.close()


@app.route("/cyber-risks/<int:risk_id>", methods=["DELETE"])
def delete_cyber_risk(risk_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM cyber_risks WHERE id = ?", [risk_id])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "risque introuvable"}), 404
        deleted_snapshot = row_to_cyber_risk(row)
        cur.execute("DELETE FROM cyber_risks WHERE id = ?", [risk_id])
        _record_cyber_risk_history(conn, cur, risk_id, "deleted", deleted_snapshot, now_iso())
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/cyber-risks/history", methods=["GET"])
def list_cyber_risks_history():
    """Historique COMPLET, ou filtré par `risk_id` (query string) pour
    la timeline d'UN risque précis -- utilisé par l'onglet "Historique"
    du hub. Toujours trié du plus récent au plus ancien."""
    risk_id = request.args.get("risk_id", type=int)
    conn = get_connection()
    try:
        cur = conn.cursor()
        if risk_id is not None:
            cur.execute("SELECT * FROM cyber_risks_history WHERE risk_id = ? ORDER BY id DESC", [risk_id])
        else:
            cur.execute("SELECT * FROM cyber_risks_history ORDER BY id DESC")
        return jsonify([dict(row) for row in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/log-sources", methods=["GET"])
def list_log_sources():
    """Liste TOUTES les sources configurées -- aucune vérification de
    rôle côté serveur (même posture que /external-links), le hub gère
    l'affichage/l'accès à l'écran d'administration côté client."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM log_sources ORDER BY name")
        return jsonify([row_to_log_source(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/log-sources", methods=["POST"])
def create_log_source():
    body = request.get_json(silent=True) or {}
    source_type = (body.get("type") or "").strip().lower()
    name = (body.get("name") or "").strip()
    if source_type not in VALID_LOG_SOURCE_TYPES:
        return jsonify({"error": f"'type' doit être l'un de {VALID_LOG_SOURCE_TYPES}"}), 400
    if not name:
        return jsonify({"error": "'name' requis"}), 400
    if len(name) > 100:
        return jsonify({"error": "'name' trop long (100 caractères max)"}), 400

    config, error = validate_log_source_config(source_type, body.get("config") or {})
    if error:
        return jsonify({"error": error}), 400

    enabled = 1 if body.get("enabled", True) else 0
    created_by = (body.get("actor") or "").strip() or None
    now = now_iso()

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """INSERT INTO log_sources
               (type, name, config, enabled, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            [source_type, name, json.dumps(config), enabled, created_by, now, now],
        )
        conn.commit()
        return jsonify({"status": "ok", "id": cur.lastrowid}), 201
    except sqlite3.IntegrityError:
        return jsonify({"error": f"une source nommée '{name}' existe déjà"}), 409
    finally:
        conn.close()


@app.route("/log-sources/<int:source_id>", methods=["PUT"])
def update_log_source(source_id):
    """Mise à jour PARTIELLE -- un champ absent du corps garde sa
    valeur existante, même esprit que /external-links. `type` ne peut
    JAMAIS changer après création (changer le type d'une source
    existante mélangerait des configs incompatibles) -- ignoré s'il
    est fourni, jamais une erreur pour autant (l'appelant qui renvoie
    juste l'objet reçu, type compris, ne doit pas échouer)."""
    body = request.get_json(silent=True) or {}
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM log_sources WHERE id = ?", [source_id])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "source introuvable"}), 404
        existing = row_to_log_source(row)

        name = ((body.get("name") or "").strip() if "name" in body else existing["name"]) or existing["name"]
        if len(name) > 100:
            return jsonify({"error": "'name' trop long (100 caractères max)"}), 400
        if "config" in body:
            config, error = validate_log_source_config(existing["type"], body["config"])
            if error:
                return jsonify({"error": error}), 400
        else:
            config = existing["config"]
        enabled = 1 if body.get("enabled", existing["enabled"]) else 0

        cur.execute(
            """UPDATE log_sources
               SET name = ?, config = ?, enabled = ?, updated_at = ?
               WHERE id = ?""",
            [name, json.dumps(config), enabled, now_iso(), source_id],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 200
    except sqlite3.IntegrityError:
        return jsonify({"error": f"une source nommée '{name}' existe déjà"}), 409
    finally:
        conn.close()


@app.route("/log-sources/<int:source_id>", methods=["DELETE"])
def delete_log_source(source_id):
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM log_sources WHERE id = ?", [source_id])
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


def slugify(text):
    """Réduit un texte libre (le `name` du lien) à un identifiant
    Keycloak propre -- minuscules, alphanumérique + tirets. Jamais une
    exception sur un texte vide/tout en caractères spéciaux -- retombe
    sur "app" plutôt qu'un clientId vide, que Keycloak rejetterait de
    toute façon."""
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-")
    return slug or "app"


@app.route("/external-links/<int:link_id>/keycloak", methods=["POST"])
def provision_keycloak_client(link_id):
    """Provisionne un client OIDC Keycloak EN DIRECT pour ce lien
    externe (backlog "interface d'intégration Keycloak", livraison
    #124) -- action ADMIN explicite et ponctuelle, jamais silencieuse
    comme postHubEvent côté hub : un échec ici doit être vu et compris
    par l'admin. Body : { redirect_uri: str, client_id?: str, adopt?: bool }.
    `client_id` optionnel -- dérivé du nom du lien (slugifié) si
    absent. Ne crée PAS de rôles realm applicatifs (ex. send/full/...
    pour une appli comme trb140-sms-relay) -- hors de portée du compte
    de service (droits manage-clients uniquement, voir
    keycloak_admin.py et keycloak/README.md pour cette limite
    assumée).

    `adopt` (livraison #125) -- cas réel rencontré : l'identifiant du
    client OIDC est parfois déjà FIXÉ côté application externe (ex.
    trb140-sms-relay, provisionné à la main en #123 avec ses 9 rôles
    realm) -- changer l'identifiant casserait cette application, pas
    une option. Plutôt qu'un 409 systématique sur toute collision
    (protection contre un doublon ACCIDENTEL), `adopt: true` permet de
    RATTACHER ce lien à un client Keycloak déjà existant au lieu d'en
    créer un nouveau -- la config réellement utilisée (redirectUris)
    est relue DEPUIS Keycloak, jamais réécrite depuis le formulaire :
    l'adoption reflète la réalité existante, elle ne l'écrase pas."""
    body = request.get_json(silent=True) or {}
    redirect_uri = (body.get("redirect_uri") or "").strip()
    adopt = bool(body.get("adopt"))
    if not redirect_uri and not adopt:
        return jsonify({"error": "redirect_uri requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM external_links WHERE id = ?", [link_id])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "lien introuvable"}), 404
        link = row_to_external_link(row)
        if link.get("keycloak_client_id"):
            return jsonify({"error": "un client Keycloak existe déjà pour ce lien -- le retirer d'abord"}), 409

        client_id = (body.get("client_id") or "").strip() or slugify(link["name"])

        try:
            token = keycloak_admin.get_token()
            # Vérifié AVANT création -- Keycloak n'empêche pas deux
            # clients distincts de porter le même clientId affiché,
            # source de confusion bien réelle si on laissait passer.
            existing = keycloak_admin.find_client_by_client_id(client_id, token)
            if existing and not adopt:
                existing_redirects = existing.get("redirectUris") or []
                return jsonify({
                    "error": f"un client Keycloak '{client_id}' existe déjà",
                    "existing_client": True,
                    "existing_redirect_uris": existing_redirects,
                }), 409
            if existing and adopt:
                internal_id = existing["id"]
                # Source de vérité = Keycloak, jamais le formulaire --
                # voir docstring. Un client sans aucune redirectUri
                # configurée (cas limite improbable mais possible) :
                # retombe sur ce que l'admin avait saisi plutôt qu'une
                # chaîne vide, jamais une exception sur une liste vide.
                existing_redirects = existing.get("redirectUris") or []
                redirect_uri = existing_redirects[0] if existing_redirects else redirect_uri
            elif adopt:
                # adopt=true mais AUCUN client existant sous ce nom --
                # rien à adopter, jamais un provisionnement silencieux
                # à sa place (l'admin croirait adopter l'existant).
                return jsonify({"error": f"aucun client Keycloak '{client_id}' à adopter"}), 404
            else:
                internal_id = keycloak_admin.create_oidc_client(client_id, link["name"], redirect_uri, token)
        except keycloak_admin.KeycloakAdminError as exc:
            return jsonify({"error": str(exc)}), 502

        cur.execute(
            "UPDATE external_links SET keycloak_client_id = ?, keycloak_internal_id = ?, keycloak_redirect_uri = ?, updated_at = ? WHERE id = ?",
            [client_id, internal_id, redirect_uri, now_iso(), link_id],
        )
        conn.commit()
        return jsonify({
            "status": "ok",
            "client_id": client_id,
            "issuer": keycloak_admin.public_issuer(),
            "redirect_uri": redirect_uri,
        }), 201
    finally:
        conn.close()


@app.route("/external-links/<int:link_id>/keycloak", methods=["DELETE"])
def deprovision_keycloak_client(link_id):
    """Retire l'intégration Keycloak de ce lien -- supprime le client
    côté Keycloak (IDEMPOTENT, voir keycloak_admin.delete_oidc_client)
    puis efface les colonnes correspondantes côté external_links. Le
    lien lui-même n'est PAS supprimé -- redevient simplement un lien
    externe classique, sans SSO."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM external_links WHERE id = ?", [link_id])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "lien introuvable"}), 404
        link = row_to_external_link(row)
        if not link.get("keycloak_internal_id"):
            return jsonify({"status": "ok"}), 200  # déjà pas intégré -- rien à faire, jamais une erreur

        try:
            token = keycloak_admin.get_token()
            keycloak_admin.delete_oidc_client(link["keycloak_internal_id"], token)
        except keycloak_admin.KeycloakAdminError as exc:
            return jsonify({"error": str(exc)}), 502

        cur.execute(
            "UPDATE external_links SET keycloak_client_id = NULL, keycloak_internal_id = NULL, keycloak_redirect_uri = NULL, updated_at = ? WHERE id = ?",
            [now_iso(), link_id],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


# ------------------------------------------------------------------
# Journal en memoire (endpoint /logs) -- capture les WARNING et plus
# graves de CE service pour l'agregateur de logs du hub (gestionnaire
# de logs, livraison #139). Meme motif EXACT que api/app.py -- ne
# capture PAS le corps des requetes ni de donnee metier (secrets
# jamais journalises). Tampon circulaire en memoire, borne
# (LOG_BUFFER_SIZE, defaut 200), jamais persiste sur disque. Seuil
# par defaut WARNING (pas INFO) : evite le bruit des logs d'acces
# Werkzeug.
# ------------------------------------------------------------------
# ------------------------------------------------------------------
# Client Memcached -- livraison #145, nécessaire au tampon de logs
# PARTAGÉ ci-dessous (ce service tourne avec 2 workers Gunicorn,
# processus séparés, mémoire NON partagée). Recréé à chaque appel
# (même motif établi ailleurs dans ce projet, voir api/app.py).
# ------------------------------------------------------------------
from pymemcache.client.base import Client as _MemcacheClient

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


# ------------------------------------------------------------------
# Journal PARTAGE (endpoint /logs) -- stocke dans Memcached (voir
# shared/log_buffer.py pour le raisonnement complet), PAS un tampon
# en memoire de processus.
# ------------------------------------------------------------------
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

SERVICE_NAME = "prefs-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

if make_shared_log_handler:
    import logging as _logging
    _log_handler = make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL,
    )
    _logging.getLogger().addHandler(_log_handler)


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


@app.route("/hub-log", methods=["POST"])
def hub_log():
    """Permet au HUB (côté NAVIGATEUR) de journaliser ce qu'il
    constate lui-même -- typiquement une erreur de liaison (un
    indicateur de présence qui bascule, un service devenu injoignable
    depuis le gestionnaire de logs) -- demandé explicitement après un
    test où tout apparaissait injoignable sans la moindre trace du
    pourquoi ni du depuis-quand (livraison #141). Réutilise le MÊME
    tampon que /logs ci-dessus -- pas un 16e service séparé, prefs-api
    est déjà la "base arrière" du hub pour tout le reste (préférences,
    hubLayout, /status, /health). Body : {"level": "WARNING"|"ERROR",
    "message": str}. `message` vide -- 400, jamais une entrée vide
    silencieusement journalisée."""
    body = request.get_json(silent=True) or {}
    level = (body.get("level") or "WARNING").strip().upper()
    message = (body.get("message") or "").strip()
    if not message:
        return jsonify({"error": "message requis"}), 400
    log_fn = app.logger.error if level == "ERROR" else app.logger.warning
    log_fn("[hub] %s", message)
    return jsonify({"status": "ok"}), 200


# ------------------------------------------------------------------
# Sources de logs EXTERNES poussées (livraison #142) -- backlog
# "suivre des logs de toutes sortes" (fichier plat, rsyslog/UDP, URL,
# push), traité dans l'ordre choisi par la personne : push d'abord,
# le plus simple, prolonge /hub-log ci-dessus. DIFFÉRENT de /hub-log :
# celui-ci est réservé au HUB lui-même (message fixe préfixé [hub],
# tampon PARTAGÉ avec les warnings internes de prefs-api) -- /push-log
# est GÉNÉRIQUE, ouvert à N'IMPORTE QUELLE source externe (scripts,
# tâches planifiées, autres outils), chacune identifiée par un nom
# ARBITRAIRE choisi par l'émetteur, PAS une liste fixe comme les 15
# services internes (LOG_SERVICES côté hub) -- une nouvelle source
# apparaît implicitement dès son premier push, jamais à déclarer
# avant.
#
# Stocké dans Memcached (livraison #145, MÊME faille jumelle que
# /logs corrigée en même temps -- ce dictionnaire était lui aussi en
# mémoire de PROCESSUS, invisible à l'autre worker) -- même tampon
# partagé que /logs (log_buffer.py), plus un REGISTRE séparé des noms
# de sources connues (Memcached n'offre pas de "lister les clés",
# voir register_shared_log_source/read_shared_log_source_registry).
# ------------------------------------------------------------------
try:
    from log_buffer import append_shared_log_entry, register_shared_log_source, read_shared_log_source_registry
except ImportError:
    append_shared_log_entry = None
    register_shared_log_source = None
    read_shared_log_source_registry = None

PUSHED_LOG_BUFFER_SIZE = int(os.environ.get("PUSHED_LOG_BUFFER_SIZE", "200"))
PUSHED_LOG_MAX_SOURCE_LENGTH = 100
PUSHED_LOG_SOURCES_REGISTRY_KEY = "pushed_log_sources"

# Archivage PERSISTANT des journaux -- consolidé dans memory-api
# (livraison #353, backlog item 8) : ce module (prefs-api/
# log_archiver.py, livraison #198) faisait le même travail que
# memory-api (#259, plus complet -- repopulation, statistiques,
# garbage collector) EN PARALLÈLE, chacun avec sa propre liste de
# services à sa propre dérive -- découvert en recoupant les deux
# (#351-352). Supprimé (fichier retiré) plutôt que laissé tourner en
# double -- `memory-api` reste désormais la SEULE source d'archivage
# persistant pour ce projet. Voir memory/README.md.


@app.route("/push-log", methods=["POST"])
def push_log():
    """Point de dépôt générique. Body : {"source": str, "level": str
    (optionnel, défaut INFO), "message": str, "logger": str
    (optionnel, défaut = source)}. `source`/`message` vides, ou
    `source` trop long -- 400, jamais une entrée fantôme ou une
    source au nom absurde acceptée silencieusement."""
    body = request.get_json(silent=True) or {}
    source = (body.get("source") or "").strip()
    message = (body.get("message") or "").strip()
    level = (body.get("level") or "INFO").strip().upper()
    logger_name = (body.get("logger") or source).strip()
    if not source or not message:
        return jsonify({"error": "source et message requis"}), 400
    if len(source) > PUSHED_LOG_MAX_SOURCE_LENGTH:
        return jsonify({"error": f"source trop longue ({PUSHED_LOG_MAX_SOURCE_LENGTH} caractères max)"}), 400
    if append_shared_log_entry:
        append_shared_log_entry(source, get_memcache_client, {
            "service": source,
            "timestamp": time.time(),
            "level": level,
            "logger": logger_name,
            "message": message,
        }, buffer_size=PUSHED_LOG_BUFFER_SIZE)
        register_shared_log_source(get_memcache_client, PUSHED_LOG_SOURCES_REGISTRY_KEY, source)
    return jsonify({"status": "ok"}), 200


@app.route("/push-log/sources", methods=["GET"])
def push_log_sources():
    """Sources externes CONNUES (ont reçu au moins un push) -- le hub
    en a besoin pour peupler dynamiquement sa liste de services, ces
    sources n'existant qu'une fois qu'elles ont poussé au moins une
    fois, jamais une liste fixe possible côté client."""
    sources = read_shared_log_source_registry(get_memcache_client, PUSHED_LOG_SOURCES_REGISTRY_KEY) if read_shared_log_source_registry else []
    return jsonify({"sources": sources}), 200


@app.route("/push-log/<source>", methods=["GET"])
def get_pushed_log(source):
    """Même FORME de réponse que GET /logs (service/entries) --
    pour que le hub traite une source externe EXACTEMENT comme un des
    15 services internes, aucune branche spéciale côté client.
    Source inconnue (jamais poussé) -- 404, distinct d'un tampon vide
    (source connue, juste sans entrée récente)."""
    known_sources = read_shared_log_source_registry(get_memcache_client, PUSHED_LOG_SOURCES_REGISTRY_KEY) if read_shared_log_source_registry else []
    if source not in known_sources:
        return jsonify({"error": "source inconnue -- n'a encore jamais poussé de message"}), 404
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(source, get_memcache_client, limit=limit, buffer_size=PUSHED_LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": source, "entries": entries}), 200


@app.route("/health", methods=["GET"])
def health():
    # server_time ajouté livraison #137 -- demandé explicitement,
    # affichage permanent dans le hub pour repérer une désynchronisation
    # d'horloge entre le navigateur et les conteneurs Docker (symptôme
    # rapporté : "tout semble désynchronisé sous docker"). Epoch Unix
    # (secondes, float) -- laissé à interpréter côté client, jamais
    # formaté ici (pas de fuseau horaire à deviner côté serveur).
    return jsonify({"status": "ok", "server_time": time.time()}), 200


def _check_reachable(url, verify_tls=True, timeout=3):
    """Sonde de présence PURE -- vrai si le serveur répond avec un code
    < 500, faux sinon (injoignable, timeout, erreur serveur). Jamais
    d'échange de données sensibles ici, juste "y a-t-il quelque chose
    qui répond" -- ce qui rend acceptable verify_tls=False pour une
    instance interne/LAN dont le certificat auto-signé propre n'est pas
    forcément dans la chaîne de confiance de CE conteneur (vault-standalone
    génère le sien séparément, voir vault-standalone/pki/). NE PAS
    réutiliser ce contournement pour un appel qui échangerait
    réellement des données -- seulement pour cette sonde de présence."""
    try:
        ctx = None
        if not verify_tls:
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            return resp.status < 500
    except Exception:
        return False


@app.route("/status", methods=["GET"])
def status():
    # Indicateurs de présence Keycloak/gateway/vault-standalone (hub,
    # pied de page) -- demandé explicitement, livraison #138.
    #
    # "gateway" reflète EXACTEMENT le même résultat que "keycloak" --
    # choix assumé, pas un oubli : tls-proxy est un simple relais nginx
    # sans logique applicative propre à sonder, et sa disponibilité est
    # de toute façon PROUVÉE par le simple fait que cette page ait pu se
    # charger (elle passe forcément par lui) -- une case "gateway"
    # séparée n'ajouterait aucune information réelle. Voir hub/README.md.
    #
    # vault_standalone : sondé via son PORT PUBLIÉ sur l'hôte (comme le
    # ferait un navigateur), PAS le réseau Docker interne -- stack
    # totalement isolé (réseau Docker séparé, jamais partagé), aucun
    # autre chemin ne l'atteint depuis ce conteneur. HOST_IP en repli
    # si VAULT_STANDALONE_HOST_IP n'est pas explicitement renseigné --
    # "localhost" en dernier recours uniquement, jamais le défaut
    # principal ICI (contrairement à une URL ouverte par un navigateur :
    # "localhost" depuis CE conteneur désignerait le conteneur
    # lui-même, jamais la machine hôte).
    #
    # Vérifications en PARALLÈLE (ThreadPoolExecutor, stdlib) -- jamais
    # l'une après l'autre : un service injoignable ajouterait sinon
    # bêtement son délai d'attente complet à celui du suivant.
    keycloak_internal = os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth")
    keycloak_check_url = f"{keycloak_internal}/realms/supervision-si/.well-known/openid-configuration"

    host_ip = os.environ.get("HOST_IP", "").strip()
    vault_host = os.environ.get("VAULT_STANDALONE_HOST_IP", "").strip() or host_ip or "localhost"
    vault_port = os.environ.get("VAULT_STANDALONE_GATEWAY_PORT", "7443").strip() or "7443"
    vault_check_url = f"https://{vault_host}:{vault_port}/"

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        keycloak_future = executor.submit(_check_reachable, keycloak_check_url, True)
        vault_future = executor.submit(_check_reachable, vault_check_url, False)
        keycloak_up = keycloak_future.result()
        vault_up = vault_future.result()

    return jsonify({
        "keycloak": keycloak_up,
        "gateway": keycloak_up,
        "vault_standalone": vault_up,
    }), 200


# ------------------------------------------------------------------
# Démarrage du sondeur des sources URL (livraison #147) et FICHIER
# (livraison #176) -- lit log_sources depuis la base à CHAQUE cycle
# (voir log_sources_poller.py, start_background_poller), écrit dans
# le tampon Memcached partagé (log_buffer.py, #145) -- même mécanisme
# que /push-log, RÉUTILISE append_shared_log_entry/
# register_shared_log_source déjà importés plus haut. Thread DAEMON,
# tourne dans CHAQUE worker Gunicorn (choix assumé, voir
# log_sources_poller.py pour le raisonnement complet).
# ------------------------------------------------------------------
try:
    import log_sources_poller
except ImportError:
    log_sources_poller = None

try:
    import file_source_poller
except ImportError:
    file_source_poller = None

# Répertoire hôte monté en LECTURE SEULE (voir docker-compose.yml,
# HOST_LOG_FILES_DIR) -- toute source "file" est résolue à
# L'INTÉRIEUR de ce répertoire uniquement (voir
# file_source_poller._resolve_safe_path), jamais un chemin arbitraire
# du conteneur. None si non configuré -- les sources "file" restent
# alors silencieusement inertes (voir poll_all_due_sources), même
# posture que si `file_source_poller` n'était pas importable.
LOG_FILES_BASE_DIR = os.environ.get("LOG_FILES_BASE_DIR") or None


def _get_active_log_sources_for_poller():
    """Sans argument -- passée telle quelle au sondeur, relit la base
    à chaque cycle (une source ajoutée/modifiée/désactivée est prise
    en compte au cycle suivant, jamais besoin de redémarrer). URL ET
    FICHIER (livraison #176) -- le dispatch par type se fait DANS
    log_sources_poller.poll_all_due_sources, pas ici."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM log_sources WHERE type IN ('url', 'file') AND enabled = 1")
        return [row_to_log_source(r) for r in cur.fetchall()]
    finally:
        conn.close()


if log_sources_poller and append_shared_log_entry:
    log_sources_poller.start_background_poller(
        _get_active_log_sources_for_poller,
        get_memcache_client,
        append_shared_log_entry,
        register_shared_log_source,
        PUSHED_LOG_SOURCES_REGISTRY_KEY,
        buffer_size=PUSHED_LOG_BUFFER_SIZE,
        base_dir=LOG_FILES_BASE_DIR,
        poll_file_fn=file_source_poller.poll_file_source if file_source_poller else None,
        log_fn=app.logger.warning,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
