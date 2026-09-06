"""
API de stockage du coffre-fort de codes/secrets — chiffrement de bout
en bout (voir shared/vaultCrypto.js pour la mécanique complète). Ce
fichier ne fait QUE stocker et restituer des blobs déjà chiffrés
côté client — aucune fonction de chiffrement/déchiffrement n'existe
ici, volontairement : le serveur ne doit JAMAIS être en mesure de
lire un secret, même en théorie, même par un bug. Si un jour ce
fichier contient un appel à une bibliothèque de chiffrement, c'est un
signal que quelque chose s'est mal passé dans la conception.

Comme le reste du projet, l'identité (`login`) transmise est celle
déjà connue du front appelant (profile.preferred_username via
Keycloak) — aucune vérification de jeton ici non plus (même posture
que partout ailleurs), MAIS la conséquence d'une usurpation
d'identité applicative reste bornée par le chiffrement de bout en
bout lui-même : même en se faisant passer pour quelqu'un d'autre
auprès de cette API, on ne peut RIEN déchiffrer sans son mot de passe
maître ou sa clé de récupération, qui ne transitent jamais ici. C'est
la différence de posture par rapport au reste du projet -- ici, le
chiffrement est la vraie ligne de défense, pas la confiance dans le
réseau.

LIMITE CONNUE ET ASSUMÉE sur la révocation d'accès : supprimer une
entrée collection_access empêche un utilisateur d'obtenir la clé de
collection À L'AVENIR, mais ne peut RIEN faire contre une copie déjà
récupérée avant la révocation (chiffrement de bout en bout : le
serveur ne sait même pas ce qui a été mis en cache côté client). Une
révocation réellement étanche demanderait de faire tourner la clé de
collection et rechiffrer tous les secrets qu'elle protège — pas fait
dans cette première version, à considérer si le besoin devient
concret.
"""

import json
import logging
import os
import sqlite3
import time
import uuid

import requests
from flask import Flask, jsonify, request
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
    register_version_route(app, "vault-api")

_log = logging.getLogger("vault_app")

# Branchement rights-api -- livraison #308, SCOPE VOLONTAIREMENT
# ÉTROIT, jamais un branchement en bloc sur tout ce fichier (voir le
# docstring en tête de module : ce service a une posture DIFFÉRENTE
# du reste du projet, le chiffrement de bout en bout borne déjà la
# confidentialité même sans vérification d'identité). Appliqué
# UNIQUEMENT aux deux routes dont le risque n'est PAS borné par la
# cryptographie -- aucune clé impliquée, une simple écriture/
# suppression en base suffit à l'action :
#   - DELETE /collections/<id>/access/<login> (revoke) -- une pure
#     suppression, jamais besoin de connaître la moindre clé pour
#     couper l'accès de quelqu'un d'autre.
#   - DELETE /users/<login> (reset) -- supprime intégralement un
#     compte (accès + archive de clé de récupération), aucune clé
#     nécessaire pour déclencher la casse.
# DÉLIBÉRÉMENT PAS appliqué à grant_collection_access : cette route
# EXIGE déjà de connaître la clé RÉELLE de la collection pour
# produire un wrapped_key valide (voir vaultOps.js:grantAccess,
# collectionKey en mémoire, jamais transmis en clair) -- borné par
# le chiffrement lui-même, un gate supplémentaire n'y fermerait
# aucune brèche réelle, seulement de la friction. Ni à create_user/
# createCollection/rotate-password (changePassword) : confirmé
# self-service (l'utilisateur agit sur SON PROPRE compte/collection,
# jamais au nom d'un tiers) -- exiger un droit "manage" y bloquerait
# un usage normal, pas une élévation de privilège.
RIGHTS_API_URL = os.environ.get("RIGHTS_API_URL", "").rstrip("/") or None


def _check_manage_right(body):
    """Même motif FAIL CLOSED que ssh-tunnels-api (#289)/ldap-admin-api
    (#290)/vault-admin-api (#291)/dba-api (#292) -- jamais fail-open,
    y compris pour admin_hub si rights-api est injoignable."""
    if not RIGHTS_API_URL:
        return True, None
    groups = body.get("groups") or []
    try:
        resp = requests.post(
            f"{RIGHTS_API_URL}/check",
            json={"groups": groups, "resource_type": "vault-api", "resource_id": None, "action": "manage"},
            timeout=5,
        )
    except requests.RequestException as exc:
        _log.debug("_check_manage_right : rights-api injoignable, refus par prudence -- %s", exc)
        return False, "service de droits injoignable -- action refusée par prudence"
    if resp.status_code != 200:
        _log.debug("_check_manage_right : rights-api a répondu %s", resp.status_code)
        return False, "service de droits indisponible -- action refusée par prudence"
    try:
        allowed = resp.json().get("allowed", False)
    except ValueError:
        return False, "réponse du service de droits illisible -- action refusée par prudence"
    if not allowed:
        _log.debug("_check_manage_right : refusé pour les groupes %s", groups)
    return allowed, None if allowed else "droit 'manage' sur vault-api requis (groupe admin_hub, ou un octroi explicite)"

DB_PATH = os.environ.get("VAULT_DB_PATH", "/data/vault.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    login TEXT PRIMARY KEY,
    salt TEXT NOT NULL,
    public_key TEXT NOT NULL,
    wrapped_private_key_iv TEXT NOT NULL,
    wrapped_private_key_ciphertext TEXT NOT NULL,
    wrapped_private_key_recovery_iv TEXT NOT NULL,
    wrapped_private_key_recovery_ciphertext TEXT NOT NULL,
    created_at TEXT NOT NULL,
    -- Trois capacités INDÉPENDANTES et CUMULABLES, décidées avec la
    -- personne -- jamais un rôle unique (enum), une même personne
    -- peut légitimement cumuler plusieurs capacités si voulu :
    --
    -- is_read_only : ne peut jamais créer/modifier/supprimer un
    -- secret ou une collection, uniquement consulter/révéler ce à
    -- quoi elle a accès. Appliqué CÔTÉ INTERFACE uniquement pour
    -- l'instant (masque les actions) -- vault-api ne vérifie aucun
    -- jeton serveur sur ses routes (caractéristique déjà existante de
    -- toute l'architecture, pas un manque propre à cette fonction),
    -- donc ceci n'est PAS une garantie de sécurité serveur, à garder
    -- en tête.
    --
    -- is_recovery_controller : capacité de contrôler les clés de
    -- récupération archivées (mécanisme maître_clefs existant, voir
    -- vault-admin-api) -- ponctuelle et ciblée, aide quelqu'un à
    -- retrouver SES PROPRES données, jamais un accès direct au
    -- contenu de qui que ce soit.
    --
    -- is_system_master : capacité AMBIANTE et PERMANENTE -- co-
    -- destinataire systématique de la clé de CHAQUE collection dès sa
    -- création (voir vaultOps.js, createCollection), peut déchiffrer
    -- n'importe quel secret à tout moment. Volontairement séparée de
    -- is_recovery_controller (décision explicite après discussion :
    -- fusionner les deux augmenterait ce qu'il y a à perdre si le
    -- compte est un jour compromis).
    is_read_only INTEGER NOT NULL DEFAULT 0,
    is_recovery_controller INTEGER NOT NULL DEFAULT 0,
    is_system_master INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS collections (
    -- TEXT (UUID v4, généré côté client à la création) -- PAS un
    -- entier auto-incrémenté, pour rester fusionnable sans collision
    -- entre plusieurs instances indépendantes (coffre isolé, voir
    -- vault/README.md, section synchronisation) -- deux instances
    -- créant chacune "leur" collection #47 en même temps produiraient
    -- une collision silencieuse et indétectable avec un compteur
    -- local, jamais avec un UUID.
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    -- is_public : "partage à tous" par défaut, décidé avec la
    -- personne -- tous les comptes coffre EXISTANT au moment de la
    -- création reçoivent l'accès automatiquement. Limite
    -- cryptographique assumée (voir vault/README.md) : un compte créé
    -- APRÈS coup n'est PAS automatiquement inclus -- personne ne peut
    -- s'auto-accorder l'accès à une collection existante, propriété
    -- du chiffrement de bout en bout, pas un manque. 0/1 (SQLite n'a
    -- pas de vrai booléen, même convention que le reste du projet).
    is_public INTEGER NOT NULL DEFAULT 0
    -- Volontairement AUCUNE contrainte FK sur created_by (retiré après
    -- un bug réel : réinitialiser un compte -- voir DELETE
    -- /users/<login> -- échouait avec IntegrityError dès que la
    -- personne avait créé une collection, la contrainte bloquant la
    -- suppression de sa ligne. Même raisonnement que secrets.created_by
    -- et secret_history.changed_by, déjà non contraints pour la même
    -- raison : une référence informative doit pouvoir survivre à la
    -- disparition de la personne référencée.
);

CREATE TABLE IF NOT EXISTS collection_access (
    collection_id TEXT NOT NULL,
    login TEXT NOT NULL,
    wrapped_key TEXT NOT NULL,
    granted_by TEXT NOT NULL,
    granted_at TEXT NOT NULL,
    PRIMARY KEY (collection_id, login),
    FOREIGN KEY (collection_id) REFERENCES collections(id),
    FOREIGN KEY (login) REFERENCES users(login)
);

CREATE TABLE IF NOT EXISTS secrets (
    -- TEXT (UUID v4) -- même raisonnement que collections.id ci-dessus.
    id TEXT PRIMARY KEY,
    collection_id TEXT NOT NULL,
    encrypted_label_iv TEXT NOT NULL,
    encrypted_label_ciphertext TEXT NOT NULL,
    encrypted_value_iv TEXT NOT NULL,
    encrypted_value_ciphertext TEXT NOT NULL,
    -- Mot-clé personnalisé -- EN CLAIR, comme localisation ci-dessous,
    -- décision revue après retour explicite de la personne : chiffré
    -- au départ (même logique que le libellé/la valeur), mais
    -- CONTRADICTOIRE avec l'objectif même du champ -- aider quelqu'un
    -- à retrouver un code EN URGENCE, y compris avant d'avoir accès à
    -- la collection concernée, via une navigation par mot-clé
    -- (impossible si chiffré : personne ne peut parcourir ce qu'il ne
    -- peut pas déchiffrer). Le libellé et la valeur, eux, restent
    -- chiffrés -- seul ce champ de CATÉGORISATION devient visible,
    -- pas le contenu sensible lui-même. Optionnel.
    keyword TEXT,
    -- Localisation (bâtiment/étage/pièce/point d'accès) -- EN CLAIR,
    -- décision explicite prise avec la personne : le libellé et la
    -- valeur du secret restent chiffrés de bout en bout, mais ce
    -- lien-là non, pour permettre une recherche/arbre de navigation
    -- rapide côté serveur. Référence LOGIQUE vers
    -- geolocations.localisation (module pixel-grid, service et base
    -- séparés) -- jamais une vraie contrainte FK SQL inter-services,
    -- résolue côté client au moment de l'affichage.
    localisation TEXT,
    -- Référence LOGIQUE vers secret_templates.id -- comme localisation
    -- ci-dessus, jamais une vraie contrainte FK stricte : un modèle
    -- supprimé ne doit jamais empêcher de lire/modifier les secrets
    -- qui le référençaient, juste leur faire perdre le regroupement
    -- par modèle. Optionnel (NULL si créé sans modèle).
    template_id TEXT,
    -- Suivi d'usage ("top 10 des codes utilisés") -- un compteur
    -- simple, pas un journal détaillé : incrémenté via
    -- POST /secrets/<id>/record-access, appelé par le front quand la
    -- VALEUR (pas juste le libellé) est révélée. Ne révèle jamais ce
    -- qu'est le secret, juste qu'il a été consulté.
    access_count INTEGER NOT NULL DEFAULT 0,
    last_accessed_at TEXT,
    -- Archivage -- remplace la SUPPRESSION véritable, demandé
    -- explicitement : "suppression... avec archivage pour tous les
    -- utilisateurs". Un secret archivé disparaît de la liste normale
    -- (GET .../secrets) mais reste consultable via un endpoint dédié,
    -- restaurable par son PROPRIÉTAIRE (created_by) -- jamais une
    -- vraie destruction, aucune purge construite pour l'instant.
    is_archived INTEGER NOT NULL DEFAULT 0,
    -- Qui a fait la DERNIÈRE modification -- distinct de created_by
    -- (qui ne change jamais). Sert à l'indicateur visuel "modifié par
    -- quelqu'un d'autre" (demandé explicitement) SANS devoir charger
    -- tout l'historique de chaque secret juste pour ça -- une simple
    -- comparaison created_by vs last_changed_by suffit côté client.
    last_changed_by TEXT,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY (collection_id) REFERENCES collections(id)
);

-- Versions -- CONTRAIREMENT à secret_history ci-dessous (jamais le
-- contenu, volontaire), celle-ci conserve un INSTANTANÉ CHIFFRÉ
-- complet à chaque modification, pour permettre un vrai retour en
-- arrière (demandé explicitement : "possibilité pour le propriétaire
-- de revenir en arrière"). Les deux tables coexistent pour des
-- usages différents -- secret_history reste le journal léger
-- (dashboard, audit), secret_versions sert UNIQUEMENT la
-- restauration. Écrite AVANT chaque modification (capture l'état
-- qui s'apprête à être remplacé, jamais après). Référence LOGIQUE
-- vers secrets.id, jamais une contrainte FK stricte -- même
-- raisonnement que secret_history : une version doit pouvoir
-- survivre à l'archivage/une éventuelle suppression future de son
-- secret.
CREATE TABLE IF NOT EXISTS secret_versions (
    id TEXT PRIMARY KEY,
    secret_id TEXT NOT NULL,
    encrypted_label_iv TEXT NOT NULL,
    encrypted_label_ciphertext TEXT NOT NULL,
    encrypted_value_iv TEXT NOT NULL,
    encrypted_value_ciphertext TEXT NOT NULL,
    keyword TEXT,
    localisation TEXT,
    template_id TEXT,
    changed_by TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    reason TEXT
);

-- Historique des modifications -- qui/quand/motif, JAMAIS le contenu
-- avant/après (pas un diff des blobs chiffrés, juste la trace de
-- l'événement). Demandé explicitement pour l'audit d'un coffre de
-- codes d'accès physiques : savoir QUI a changé un code et POURQUOI
-- (départ d'une personne, incident...) compte plus qu'un diff
-- technique du contenu chiffré, qu'il faudrait de toute façon
-- déchiffrer pour être lisible.
CREATE TABLE IF NOT EXISTS secret_history (
    id TEXT PRIMARY KEY,
    -- secret_id : référence LOGIQUE, PAS une vraie contrainte FK --
    -- volontaire : un historique doit pouvoir SURVIVRE à la
    -- suppression du secret qu'il documente (tout l'intérêt d'un
    -- audit -- "ce secret a existé, a été modifié par X, supprimé
    -- par Y"), jamais bloquer cette suppression. Bug réel rencontré :
    -- avec une contrainte FK stricte, supprimer un secret ayant un
    -- historique échouait purement et simplement.
    secret_id TEXT NOT NULL,
    action TEXT NOT NULL,
    changed_by TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    reason TEXT
);

-- Observations -- liste d'annotations libres, horodatées, distinctes
-- de secret_history ci-dessus : jamais une modification du secret
-- lui-même, juste des notes de terrain accumulées au fil du temps
-- ("code changé le 12 par le prestataire X", "porte grippée le
-- matin"...). CHIFFRÉES comme le libellé/les champs (voir
-- vault/README.md, "tout est chiffré" -- demande explicite). Contrairement
-- à secret_history : vraie contrainte FK avec CASCADE -- une
-- observation n'a aucun sens sans le secret qu'elle documente
-- (jamais une trace d'audit à préserver après coup, juste une note
-- de travail), supprimer le secret doit logiquement les supprimer
-- aussi.
CREATE TABLE IF NOT EXISTS secret_observations (
    id TEXT PRIMARY KEY,
    secret_id TEXT NOT NULL,
    encrypted_text_iv TEXT NOT NULL,
    encrypted_text_ciphertext TEXT NOT NULL,
    author TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (secret_id) REFERENCES secrets(id) ON DELETE CASCADE
);

-- Modèles de fiche -- nom + liste de libellés de champs (ex. "Carte
-- SIM" -> PUK/PIN/Numéro), EN CLAIR : pure métadonnée de STRUCTURE,
-- jamais de contenu de secret (même raisonnement que keyword/
-- localisation sur secrets -- voir plus haut). GLOBAUX PAR DÉFAUT
-- (collection_id NULL) -- un modèle "Carte SIM" a du sens à travers
-- tout le coffre. Depuis backlog coffre-fort #2 (livraison #110),
-- peuvent AUSSI être scopés à une collection précise (collection_id
-- renseigné) et porter une liste de champs obligatoires
-- (required_labels, sous-ensemble de field_labels) -- ces deux
-- colonnes ajoutées via migration douce (ensure_secrets_new_columns,
-- voir plus bas), jamais recréées ici pour ne jamais perdre les
-- modèles déjà existants. Obligatoire = INDICATIF seulement (jamais
-- bloquant à l'enregistrement d'un secret, décidé explicitement avec
-- la personne) -- juste un ordre d'affichage (obligatoires en
-- premier) et un marqueur visuel. Référence LOGIQUE vers
-- collections.id comme secrets.template_id ci-dessus -- jamais une
-- vraie contrainte FK, une collection supprimée ne doit jamais
-- empêcher de lire un modèle qui la référençait. Permet la création
-- rapide ("utiliser ce modèle" pré-remplit les libellés à la création
-- d'un secret) ET le parcours ("quels secrets utilisent ce modèle",
-- voir secrets.template_id plus bas) -- même esprit que la navigation
-- par mot-clé.
CREATE TABLE IF NOT EXISTS secret_templates (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    -- JSON, ex. ["PUK", "PIN", "Numéro"] -- jamais de contenu, juste
    -- la FORME (quels champs, dans quel ordre).
    field_labels TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL
);

-- "Dépôt" des clés de récupération individuelles, chiffrées avec la
-- clé PUBLIQUE du compte maître_principal (voir vault/README.md,
-- section maître_clefs) -- écriture accessible à quiconque crée un
-- compte coffre (dépôt à sens unique, jamais de lecture depuis cette
-- API normale), lecture réservée à vault-admin-api (service séparé,
-- jamais exposé par la passerelle publique).
CREATE TABLE IF NOT EXISTS recovery_key_archive (
    login TEXT PRIMARY KEY,
    wrapped_recovery_key_for_master TEXT NOT NULL,
    archived_at TEXT NOT NULL,
    FOREIGN KEY (login) REFERENCES users(login)
);
"""


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def ensure_uuid_ids():
    """Migration STRUCTURELLE -- convertit collections.id/secrets.id
    d'entiers auto-incrémentés vers des UUID texte, EN PRÉSERVANT
    toutes les relations existantes (collection_access.collection_id,
    secrets.collection_id). Nécessaire pour la synchronisation avec
    une instance isolée (voir vault/README.md) : deux instances
    créant chacune "leur" collection #47 en même temps produiraient
    une collision silencieuse et indétectable avec un compteur local,
    jamais avec un UUID généré indépendamment.

    SQLite ne permet pas de changer le TYPE d'une colonne existante
    via ALTER TABLE -- reconstruction complète des trois tables
    concernées, dans une seule transaction (tout ou rien, jamais un
    état intermédiaire à moitié migré si quelque chose échoue en
    cours de route). Idempotente : ne fait RIEN si collections.id est
    déjà du type TEXT (vérifié via PRAGMA table_info AVANT toute
    action) -- base déjà migrée, ou base fraîche créée directement
    avec le nouveau schéma (ensure_schema ci-dessus).
    """
    try:
        # isolation_level=None -- contrôle manuel de la transaction
        # (BEGIN explicite plus bas) : indispensable pour que les
        # CREATE/DROP/ALTER TABLE ci-dessous soient RÉELLEMENT annulés
        # par conn.rollback() en cas d'échec. Vérifié en isolant le
        # problème avant d'écrire ce correctif : par défaut, le module
        # sqlite3 de Python ne place PAS les instructions DDL dans la
        # transaction annulable -- une CREATE TABLE reste en place
        # même après rollback() sans ce réglage, ce qui aurait rendu
        # cette migration NON atomique malgré les apparences.
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        conn.row_factory = sqlite3.Row  # indispensable pour dict(row) plus bas
        # PRAGMA foreign_keys ne prend effet que HORS transaction --
        # doit donc être réglé AVANT le BEGIN explicite ci-dessous,
        # jamais après (sinon silencieusement sans effet).
        conn.execute("PRAGMA foreign_keys = OFF")  # le temps de la reconstruction uniquement
        cur = conn.cursor()

        cur.execute("PRAGMA table_info(collections)")
        columns = {row[1]: row[2] for row in cur.fetchall()}
        if not columns:
            return  # table pas encore créée du tout -- ensure_schema s'en chargera avec le bon type direct ; fermeture gérée par le finally
        if columns.get("id", "").upper() == "TEXT":
            return  # déjà migrée -- idempotent ; fermeture gérée par le finally

        app.logger.warning("Migration UUID des identifiants collections/secrets en cours...")
        cur.execute("BEGIN")

        # --- Nouvelles tables, schéma UUID -- execute() individuels,
        # PAS executescript() : ce dernier force un commit implicite
        # avant de s'exécuter en Python (piège connu du module sqlite3),
        # ce qui casserait l'atomicité de cette migration -- soit tout
        # réussit, soit rien n'est modifié en cas d'échec en cours de
        # route.
        cur.execute("""
            CREATE TABLE collections_new (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_public INTEGER NOT NULL DEFAULT 0
            )
        """)
        cur.execute("""
            CREATE TABLE secrets_new (
                id TEXT PRIMARY KEY,
                collection_id TEXT NOT NULL,
                encrypted_label_iv TEXT NOT NULL,
                encrypted_label_ciphertext TEXT NOT NULL,
                encrypted_value_iv TEXT NOT NULL,
                encrypted_value_ciphertext TEXT NOT NULL,
                localisation TEXT,
                access_count INTEGER NOT NULL DEFAULT 0,
                last_accessed_at TEXT,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE collection_access_new (
                collection_id TEXT NOT NULL,
                login TEXT NOT NULL,
                wrapped_key TEXT NOT NULL,
                granted_by TEXT NOT NULL,
                granted_at TEXT NOT NULL,
                PRIMARY KEY (collection_id, login)
            )
        """)

        # --- collections : ancien id entier -> nouvel UUID, mapping conservé ---
        old_to_new_collection_id = {}
        cur.execute("SELECT * FROM collections")
        for row in cur.fetchall():
            row = dict(row)
            new_id = str(uuid.uuid4())
            old_to_new_collection_id[row["id"]] = new_id
            cur.execute(
                "INSERT INTO collections_new (id, name, created_by, created_at, is_public) VALUES (?, ?, ?, ?, ?)",
                [new_id, row["name"], row["created_by"], row["created_at"], row.get("is_public", 0)],
            )

        # --- secrets : nouvel UUID pour id, collection_id TRADUIT via le mapping ci-dessus ---
        cur.execute("SELECT * FROM secrets")
        for row in cur.fetchall():
            row = dict(row)
            new_collection_id = old_to_new_collection_id.get(row["collection_id"])
            if new_collection_id is None:
                # Secret référençant une collection déjà absente (ne
                # devrait jamais arriver, contrainte FK -- filet de
                # sécurité) -- ignoré plutôt que de faire échouer toute
                # la migration pour une ligne orpheline.
                app.logger.warning("Secret %s ignoré (collection %s introuvable)", row["id"], row["collection_id"])
                continue
            cur.execute(
                """INSERT INTO secrets_new
                   (id, collection_id, encrypted_label_iv, encrypted_label_ciphertext,
                    encrypted_value_iv, encrypted_value_ciphertext, localisation,
                    access_count, last_accessed_at, created_by, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                [
                    str(uuid.uuid4()), new_collection_id,
                    row["encrypted_label_iv"], row["encrypted_label_ciphertext"],
                    row["encrypted_value_iv"], row["encrypted_value_ciphertext"],
                    row.get("localisation"), row.get("access_count", 0), row.get("last_accessed_at"),
                    row["created_by"], row["created_at"], row["updated_at"],
                ],
            )

        # --- collection_access : collection_id TRADUIT via le même mapping ---
        cur.execute("SELECT * FROM collection_access")
        for row in cur.fetchall():
            row = dict(row)
            new_collection_id = old_to_new_collection_id.get(row["collection_id"])
            if new_collection_id is None:
                continue  # même filet de sécurité que ci-dessus
            cur.execute(
                "INSERT INTO collection_access_new (collection_id, login, wrapped_key, granted_by, granted_at) VALUES (?, ?, ?, ?, ?)",
                [new_collection_id, row["login"], row["wrapped_key"], row["granted_by"], row["granted_at"]],
            )

        # --- Bascule atomique : anciennes tables supprimées, nouvelles
        # renommées -- execute() individuels, même raison qu'au-dessus.
        cur.execute("DROP TABLE collections")
        cur.execute("DROP TABLE secrets")
        cur.execute("DROP TABLE collection_access")
        cur.execute("ALTER TABLE collections_new RENAME TO collections")
        cur.execute("ALTER TABLE secrets_new RENAME TO secrets")
        cur.execute("ALTER TABLE collection_access_new RENAME TO collection_access")

        conn.commit()
        app.logger.warning(
            "Migration UUID terminée : %d collection(s), %d secret(s) migrés.",
            len(old_to_new_collection_id), cur.execute("SELECT COUNT(*) FROM secrets").fetchone()[0],
        )
    except Exception as exc:  # noqa: BLE001 — jamais bloquer le démarrage, mais ARRÊTER la migration en cours (pas de commit partiel)
        app.logger.error("Migration UUID échouée, annulée (rien n'a été modifié) : %s", exc)
        conn.rollback()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()


def ensure_collections_created_by_not_fk():
    """Migration STRUCTURELLE -- retire la contrainte FK stricte sur
    collections.created_by, si elle existe encore (installations
    créées AVANT ce correctif, voir le schéma ci-dessus pour le
    raisonnement complet). Bug réel trouvé en testant la
    réinitialisation d'un compte ayant créé des collections :
    IntegrityError bloquant, alors que le but même de cette route est
    de PRÉSERVER les collections en supprimant seulement le compte.

    Idempotente -- ne fait RIEN si la contrainte est déjà absente
    (installation fraîche après ce correctif, PRAGMA foreign_key_list
    vérifié AVANT toute action). Même technique que ensure_uuid_ids
    ci-dessus (isolation_level=None + BEGIN explicite, foreign_keys
    coupées le temps de la reconstruction) -- reconstruction complète
    de la table étant le seul moyen SQLite de retirer une contrainte
    existante."""
    try:
        conn = sqlite3.connect(DB_PATH, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = OFF")
        cur = conn.cursor()

        cur.execute("PRAGMA foreign_key_list(collections)")
        has_created_by_fk = any(row["from"] == "created_by" for row in cur.fetchall())
        if not has_created_by_fk:
            return  # déjà corrigée (ou installation fraîche) -- idempotent

        app.logger.warning("Retrait de la contrainte FK collections.created_by en cours...")
        cur.execute("BEGIN")
        cur.execute("""
            CREATE TABLE collections_fixed (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_by TEXT NOT NULL,
                created_at TEXT NOT NULL,
                is_public INTEGER NOT NULL DEFAULT 0
            )
        """)
        # SELECT * puis row.get("is_public", 0) -- DÉFENSIF, même
        # raisonnement qu'ensure_uuid_ids ci-dessus : is_public a pu
        # ne pas encore exister sur une installation suffisamment
        # ancienne (ajoutée par ensure_secrets_new_columns plus bas,
        # qui n'a peut-être pas encore tourné sur cette base à ce
        # stade précis de la migration).
        cur.execute("SELECT * FROM collections")
        for row in cur.fetchall():
            row = dict(row)
            cur.execute(
                "INSERT INTO collections_fixed (id, name, created_by, created_at, is_public) VALUES (?, ?, ?, ?, ?)",
                [row["id"], row["name"], row["created_by"], row["created_at"], row.get("is_public", 0)],
            )
        cur.execute("DROP TABLE collections")
        cur.execute("ALTER TABLE collections_fixed RENAME TO collections")
        cur.execute("COMMIT")
        app.logger.warning("Contrainte FK collections.created_by retirée avec succès.")
    except Exception as exc:  # noqa: BLE001 — jamais bloquer le démarrage, mais ARRÊTER la migration en cours
        app.logger.error("Migration collections.created_by échouée, annulée (rien n'a été modifié) : %s", exc)
        conn.rollback()
    finally:
        conn.execute("PRAGMA foreign_keys = ON")
        conn.close()


def ensure_secrets_new_columns():
    """Migration DOUCE -- ajoute localisation/access_count/
    last_accessed_at à la table secrets existante si absentes, jamais
    une recréation. CREATE TABLE IF NOT EXISTS (ensure_schema
    ci-dessus) ne touche jamais une table déjà créée avec l'ancienne
    structure -- même précaution que pour geolocations
    (pixel-grid/api), par cohérence, même si ce coffre est encore
    jeune."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute("PRAGMA table_info(secrets)")
        existing = {row[1] for row in cur.fetchall()}
        if "localisation" not in existing:
            cur.execute("ALTER TABLE secrets ADD COLUMN localisation TEXT")
        if "access_count" not in existing:
            cur.execute("ALTER TABLE secrets ADD COLUMN access_count INTEGER NOT NULL DEFAULT 0")
        if "last_accessed_at" not in existing:
            cur.execute("ALTER TABLE secrets ADD COLUMN last_accessed_at TEXT")
        if "keyword" not in existing:
            cur.execute("ALTER TABLE secrets ADD COLUMN keyword TEXT")
        if "template_id" not in existing:
            cur.execute("ALTER TABLE secrets ADD COLUMN template_id TEXT")
        if "is_archived" not in existing:
            cur.execute("ALTER TABLE secrets ADD COLUMN is_archived INTEGER NOT NULL DEFAULT 0")
        if "last_changed_by" not in existing:
            cur.execute("ALTER TABLE secrets ADD COLUMN last_changed_by TEXT")
        cur.execute("PRAGMA table_info(collections)")
        existing_collections = {row[1] for row in cur.fetchall()}
        if "is_public" not in existing_collections:
            cur.execute("ALTER TABLE collections ADD COLUMN is_public INTEGER NOT NULL DEFAULT 0")
        cur.execute("PRAGMA table_info(users)")
        existing_users = {row[1] for row in cur.fetchall()}
        if "is_read_only" not in existing_users:
            cur.execute("ALTER TABLE users ADD COLUMN is_read_only INTEGER NOT NULL DEFAULT 0")
        if "is_recovery_controller" not in existing_users:
            cur.execute("ALTER TABLE users ADD COLUMN is_recovery_controller INTEGER NOT NULL DEFAULT 0")
        if "is_system_master" not in existing_users:
            cur.execute("ALTER TABLE users ADD COLUMN is_system_master INTEGER NOT NULL DEFAULT 0")
        cur.execute("PRAGMA table_info(secret_templates)")
        existing_templates = {row[1] for row in cur.fetchall()}
        if "collection_id" not in existing_templates:
            cur.execute("ALTER TABLE secret_templates ADD COLUMN collection_id TEXT")
        if "required_labels" not in existing_templates:
            cur.execute("ALTER TABLE secret_templates ADD COLUMN required_labels TEXT")
        conn.commit()
        conn.close()
    except Exception as exc:  # noqa: BLE001 — la base peut ne pas être prête au tout premier démarrage
        app.logger.warning("Migration colonnes secrets reportée : %s", exc)


try:
    ensure_schema()
except Exception as exc:  # noqa: BLE001 — la base peut ne pas être prête au tout premier démarrage
    app.logger.warning("Migration au démarrage reportée : %s", exc)

# Ordre volontaire : structure (UUID) avant les colonnes simples --
# ensure_uuid_ids() gère de toute façon leur absence proprement
# (row.get(...) avec repli), mais autant partir de la table déjà
# reconstruite avec toutes ses colonnes avant d'y ajouter le reste.
ensure_uuid_ids()
ensure_collections_created_by_not_fk()
ensure_secrets_new_columns()


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ============================================================

@app.route("/users/<login>", methods=["GET"])
def get_user(login):
    """Nécessaire pour deux usages : la personne elle-même (récupérer
    ses blobs chiffrés pour déverrouiller) ET n'importe qui voulant
    lui accorder l'accès à une collection (récupérer sa clé PUBLIQUE
    pour envelopper une clé de collection à son intention)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT * FROM users WHERE login = ?", [login])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "utilisateur introuvable"}), 404
        return jsonify(dict(row)), 200
    finally:
        conn.close()


@app.route("/users/<login>", methods=["DELETE"])
def reset_user(login):
    """Réinitialise un compte -- pour quelqu'un ayant perdu mot de
    passe ET clé de récupération (voir vault/README.md, section
    "réinitialiser sans perdre les données"). Supprime le compte pour
    permettre sa recréation (nouveau trousseau, nouveau mot de passe),
    mais capture D'ABORD la liste des collections auxquelles il avait
    accès -- c'est au CLIENT (voir vaultOps.js, resetAccount) de
    décider ensuite quoi en faire (réattribution manuelle via
    grantAccess, exactement comme un octroi normal -- rien de
    spécial ici, ce compte "reset" redevient un simple nouveau
    membre).

    Nettoyage dans l'ORDRE requis par les contraintes FK (jamais de
    CASCADE sur ces tables, volontairement -- voir leurs schémas) :
    collection_access et recovery_key_archive AVANT users, sinon la
    suppression finale échouerait.

    Protégée par rights-api (#308) -- action DESTRUCTIVE totale
    (compte + tout accès + archive de clé de récupération), aucune
    clé impliquée dans son déclenchement -- même raisonnement que
    revoke_collection_access ci-dessus."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE login = ?", [login])
        if cur.fetchone() is None:
            return jsonify({"error": "utilisateur introuvable"}), 404

        cur.execute(
            """SELECT ca.collection_id AS id, c.name AS name
               FROM collection_access ca
               JOIN collections c ON c.id = ca.collection_id
               WHERE ca.login = ?
               ORDER BY c.name""",
            [login],
        )
        had_access_to = [dict(r) for r in cur.fetchall()]

        cur.execute("DELETE FROM collection_access WHERE login = ?", [login])
        cur.execute("DELETE FROM recovery_key_archive WHERE login = ?", [login])
        cur.execute("DELETE FROM users WHERE login = ?", [login])
        conn.commit()
        return jsonify({"status": "ok", "had_access_to": had_access_to}), 200
    finally:
        conn.close()


@app.route("/users", methods=["POST"])
def create_user():
    """Création du compte coffre — une fois par personne, jamais
    réécrasable via cette route (voir /users/<login>/rotate-password
    pour un changement de mot de passe, mécanisme différent)."""
    body = request.get_json(silent=True) or {}
    required = [
        "login", "salt", "public_key",
        "wrapped_private_key_iv", "wrapped_private_key_ciphertext",
        "wrapped_private_key_recovery_iv", "wrapped_private_key_recovery_ciphertext",
    ]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({"error": f"champs requis manquants : {missing}"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE login = ?", [body["login"]])
        if cur.fetchone() is not None:
            return jsonify({"error": "un compte existe déjà pour cet utilisateur"}), 409
        cur.execute(
            """INSERT INTO users
               (login, salt, public_key, wrapped_private_key_iv, wrapped_private_key_ciphertext,
                wrapped_private_key_recovery_iv, wrapped_private_key_recovery_ciphertext, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                body["login"], body["salt"], body["public_key"],
                body["wrapped_private_key_iv"], body["wrapped_private_key_ciphertext"],
                body["wrapped_private_key_recovery_iv"], body["wrapped_private_key_recovery_ciphertext"],
                now_iso(),
            ],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 201
    finally:
        conn.close()


@app.route("/users/<login>/rotate-password", methods=["POST"])
def rotate_password(login):
    """Changement de mot de passe maître (ou reconstruction après usage
    de la clé de récupération) — remplace SEULEMENT l'enveloppe liée au
    mot de passe. La clé privée RSA elle-même NE CHANGE JAMAIS ici (le
    client la déchiffre avec l'ancien mot de passe ou la clé de
    récupération, puis la rechiffre avec le nouveau mot de passe) --
    tous les accès aux collections déjà accordés restent valides sans
    aucune action supplémentaire, puisqu'ils portent sur la même paire
    de clés RSA. L'enveloppe de récupération n'est PAS touchée par
    cette route (un mécanisme séparé s'en occuperait, pas construit
    dans cette version)."""
    body = request.get_json(silent=True) or {}
    required = ["salt", "wrapped_private_key_iv", "wrapped_private_key_ciphertext"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({"error": f"champs requis manquants : {missing}"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """UPDATE users SET salt = ?, wrapped_private_key_iv = ?, wrapped_private_key_ciphertext = ?
               WHERE login = ?""",
            [body["salt"], body["wrapped_private_key_iv"], body["wrapped_private_key_ciphertext"], login],
        )
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "utilisateur introuvable"}), 404
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


# ============================================================
# Collections
# ============================================================

@app.route("/collections", methods=["POST"])
def create_collection():
    """La personne qui crée la collection doit IMMÉDIATEMENT s'auto-
    accorder l'accès (sinon elle ne pourrait jamais rouvrir ce qu'elle
    vient de créer) -- fait en une seule requête via `self_wrapped_key`
    (déjà enveloppée avec sa PROPRE clé publique côté client), pas une
    deuxième requête séparée qui laisserait une fenêtre où la
    collection existe sans que personne n'y ait accès.

    `is_public` : marque juste l'intention -- cette route ne peut PAS
    accorder l'accès aux autres elle-même (aucune opération
    cryptographique ne se fait côté serveur, par conception). C'est au
    client d'enchaîner un appel à /collections/<id>/access pour chaque
    utilisateur existant (voir vaultOps.js, createCollection) après
    avoir créé la collection ici."""
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    created_by = body.get("created_by")
    self_wrapped_key = body.get("self_wrapped_key")
    is_public = 1 if body.get("is_public") else 0
    if not name or not created_by or not self_wrapped_key:
        return jsonify({"error": "name, created_by et self_wrapped_key requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE login = ?", [created_by])
        if cur.fetchone() is None:
            return jsonify({"error": f"utilisateur '{created_by}' introuvable"}), 400
        now = now_iso()
        # UUID généré ici plutôt que côté client -- même garantie
        # d'unicité globale (un UUID v4 est unique peu importe qui le
        # génère), sans exiger de changement côté frontend pour la
        # génération elle-même (voir vault/README.md, migration UUID).
        collection_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO collections (id, name, created_by, created_at, is_public) VALUES (?, ?, ?, ?, ?)",
            [collection_id, name, created_by, now, is_public],
        )
        cur.execute(
            """INSERT INTO collection_access (collection_id, login, wrapped_key, granted_by, granted_at)
               VALUES (?, ?, ?, ?, ?)""",
            [collection_id, created_by, self_wrapped_key, created_by, now],
        )
        conn.commit()
        return jsonify({"status": "ok", "id": collection_id}), 201
    finally:
        conn.close()


@app.route("/users", methods=["GET"])
def list_users():
    """Liste des logins + clés publiques -- nécessaire pour le
    "partage à tous" par défaut (voir vaultOps.js, createCollection) :
    le client doit connaître tout le monde pour envelopper la clé de
    collection à l'intention de chacun. Jamais les blobs chiffrés
    (clé privée) de qui que ce soit ici -- uniquement ce qui est déjà
    public par construction.

    `?role=system_master` -- filtre sur les comptes ayant cette
    capacité, utilisé par le même mécanisme pour l'escrow systématique
    (voir vaultOps.js, createCollection) : chaque nouvelle collection
    enveloppe aussi sa clé pour CES comptes-là, en plus du créateur et
    des destinataires normaux."""
    role_filter = request.args.get("role")
    conn = get_connection()
    try:
        cur = conn.cursor()
        if role_filter == "system_master":
            cur.execute("SELECT login, public_key FROM users WHERE is_system_master = 1 ORDER BY login")
        elif role_filter == "recovery_controller":
            cur.execute("SELECT login, public_key FROM users WHERE is_recovery_controller = 1 ORDER BY login")
        else:
            cur.execute("SELECT login, public_key FROM users ORDER BY login")
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/collections", methods=["GET"])
def list_collections():
    """Collections auxquelles CET utilisateur a accès -- la jointure
    avec collection_access EST le contrôle d'accès fin lui-même,
    jamais un filtre appliqué après coup : une collection à laquelle
    la personne n'a pas d'entrée n'apparaît tout simplement jamais
    dans les résultats de cette requête."""
    login = (request.args.get("user") or "").strip()
    if not login:
        return jsonify({"error": "paramètre 'user' requis"}), 400
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT c.id, c.name, c.created_by, c.created_at, c.is_public, ca.wrapped_key
               FROM collections c
               JOIN collection_access ca ON ca.collection_id = c.id
               WHERE ca.login = ?
               ORDER BY c.name""",
            [login],
        )
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/collections/<collection_id>/access", methods=["GET"])
def list_collection_access(collection_id):
    """Qui a accès à cette collection -- pour l'interface de gestion
    des accès. N'expose jamais wrapped_key des AUTRES (ne serait de
    toute façon utilisable par personne d'autre que son destinataire,
    mais pas de raison de l'exposer inutilement)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT login, granted_by, granted_at FROM collection_access WHERE collection_id = ? ORDER BY granted_at",
            [collection_id],
        )
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/collections/<collection_id>/access", methods=["POST"])
def grant_collection_access(collection_id):
    """Accorde l'accès à quelqu'un -- wrapped_key déjà calculée côté
    client (enveloppée avec la clé PUBLIQUE du destinataire), cette
    route ne fait que la stocker. Le champ `granted_by` trace qui a
    accordé l'accès (jamais déductible après coup autrement)."""
    body = request.get_json(silent=True) or {}
    login = body.get("login")
    wrapped_key = body.get("wrapped_key")
    granted_by = body.get("granted_by")
    if not login or not wrapped_key or not granted_by:
        return jsonify({"error": "login, wrapped_key et granted_by requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM collections WHERE id = ?", [collection_id])
        if cur.fetchone() is None:
            return jsonify({"error": "collection introuvable"}), 404
        cur.execute("SELECT 1 FROM users WHERE login = ?", [login])
        if cur.fetchone() is None:
            return jsonify({"error": f"utilisateur '{login}' introuvable"}), 400
        cur.execute(
            """INSERT INTO collection_access (collection_id, login, wrapped_key, granted_by, granted_at)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(collection_id, login) DO UPDATE SET wrapped_key = excluded.wrapped_key,
                   granted_by = excluded.granted_by, granted_at = excluded.granted_at""",
            [collection_id, login, wrapped_key, granted_by, now_iso()],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 201
    finally:
        conn.close()


@app.route("/collections/<collection_id>/access/<login>", methods=["DELETE"])
def revoke_collection_access(collection_id, login):
    """Révoque l'accès -- voir la note en tête de fichier : empêche un
    accès FUTUR, ne peut rien contre une copie déjà récupérée avant
    cette révocation (limite inhérente au chiffrement de bout en bout
    sans rotation de clé, assumée pour cette version).

    Protégée par rights-api (#308) -- AUCUNE clé n'est impliquée dans
    cette action (pure suppression en base), contrairement à
    grant_collection_access qui exige déjà de connaître la clé réelle
    de la collection. Sans ce gate, n'importe qui aurait pu couper
    l'accès de n'importe qui, sans rien avoir besoin de déchiffrer.
    `groups` lu depuis le corps JSON (optionnel sur DELETE, mais lu
    ici comme ailleurs dans ce projet) -- absent ou vide = refusé dès
    que RIGHTS_API_URL est configuré (FAIL CLOSED)."""
    body = request.get_json(silent=True) or {}
    allowed, error = _check_manage_right(body)
    if not allowed:
        return jsonify({"error": error}), 403
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM collection_access WHERE collection_id = ? AND login = ?",
            [collection_id, login],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


# ============================================================
# Secrets
# ============================================================

@app.route("/collections/<collection_id>/secrets", methods=["GET"])
def list_secrets(collection_id):
    """`?archived=true` -- liste les secrets ARCHIVÉS de cette
    collection au lieu des actifs (jamais les deux mélangés). Visible
    à quiconque a accès à la collection -- demandé explicitement :
    "archivage pour tous les utilisateurs", pas réservé au
    propriétaire (seule la RESTAURATION l'est, voir /restore
    ci-dessous)."""
    show_archived = request.args.get("archived") == "true"
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM secrets WHERE collection_id = ? AND is_archived = ? ORDER BY created_at",
            [collection_id, 1 if show_archived else 0],
        )
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/collections/<collection_id>/secrets", methods=["POST"])
def create_secret(collection_id):
    body = request.get_json(silent=True) or {}
    required = [
        "encrypted_label_iv", "encrypted_label_ciphertext",
        "encrypted_value_iv", "encrypted_value_ciphertext", "created_by",
    ]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({"error": f"champs requis manquants : {missing}"}), 400

    # localisation : EN CLAIR (voir commentaire du schéma) -- optionnelle,
    # référence logique vers geolocations.localisation (pixel-grid),
    # jamais vérifiée ici (services/bases séparés) -- résolue côté
    # client au moment de l'affichage.
    localisation = body.get("localisation")
    # mot-clé : EN CLAIR aussi (voir commentaire du schéma -- revu
    # après retour explicite : chiffré aurait empêché la navigation
    # par mot-clé, contraire à l'objectif même du champ), optionnel.
    keyword = body.get("keyword")
    # template_id : référence logique vers secret_templates.id, EN
    # CLAIR comme localisation/keyword -- jamais vérifiée ici (un
    # modèle supprimé ne doit jamais bloquer la création d'un secret).
    template_id = body.get("template_id")

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM collections WHERE id = ?", [collection_id])
        if cur.fetchone() is None:
            return jsonify({"error": "collection introuvable"}), 404
        now = now_iso()
        # UUID généré ici -- même raisonnement que create_collection ci-dessus.
        secret_id = str(uuid.uuid4())
        cur.execute(
            """INSERT INTO secrets
               (id, collection_id, encrypted_label_iv, encrypted_label_ciphertext,
                encrypted_value_iv, encrypted_value_ciphertext, keyword, localisation,
                template_id, created_by, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                secret_id, collection_id, body["encrypted_label_iv"], body["encrypted_label_ciphertext"],
                body["encrypted_value_iv"], body["encrypted_value_ciphertext"],
                keyword, localisation, template_id, body["created_by"], now, now,
            ],
        )
        # Historique -- première entrée à la création, même mécanisme
        # que les modifications ultérieures (voir update_secret).
        cur.execute(
            "INSERT INTO secret_history (id, secret_id, action, changed_by, changed_at, reason) VALUES (?, ?, ?, ?, ?, ?)",
            [str(uuid.uuid4()), secret_id, "created", body["created_by"], now, body.get("reason")],
        )
        conn.commit()
        return jsonify({"status": "ok", "id": secret_id}), 201
    finally:
        conn.close()


@app.route("/secrets/<secret_id>", methods=["PUT"])
def update_secret(secret_id):
    """Modification -- exige `changed_by` (qui) pour journaliser dans
    secret_history, `reason` (motif) optionnel mais transmis tel quel.
    secret_history ne garde JAMAIS le contenu avant/après -- mais
    AVANT d'appliquer la modification, un INSTANTANÉ COMPLET du
    contenu ACTUEL (celui qui s'apprête à être remplacé) est capturé
    dans secret_versions, pour permettre un retour en arrière (voir
    /versions/<version_id>/restore plus bas)."""
    body = request.get_json(silent=True) or {}
    changed_by = body.get("changed_by")
    if not changed_by:
        return jsonify({"error": "changed_by requis pour journaliser la modification"}), 400

    fields = {
        k: body[k] for k in [
            "encrypted_label_iv", "encrypted_label_ciphertext",
            "encrypted_value_iv", "encrypted_value_ciphertext",
        ] if k in body
    }
    # localisation/keyword/template_id traités séparément -- champs EN
    # CLAIR, explicitement autorisés à être `None` (retirer la valeur)
    # contrairement aux champs chiffrés ci-dessus (jamais vidés par
    # erreur : absents du corps = non touchés, "in body" fait foi).
    if "localisation" in body:
        fields["localisation"] = body["localisation"]
    if "keyword" in body:
        fields["keyword"] = body["keyword"]
    if "template_id" in body:
        fields["template_id"] = body["template_id"]
    if not fields:
        return jsonify({"error": "aucun champ fourni"}), 400
    fields["updated_at"] = now_iso()
    fields["last_changed_by"] = changed_by

    conn = get_connection()
    try:
        cur = conn.cursor()
        # Instantané AVANT modification -- capture l'état ACTUEL
        # (encore complet, avant remplacement), jamais après.
        cur.execute("SELECT * FROM secrets WHERE id = ?", [secret_id])
        current = cur.fetchone()
        if current is None:
            return jsonify({"error": "secret introuvable"}), 404
        cur.execute(
            """INSERT INTO secret_versions
               (id, secret_id, encrypted_label_iv, encrypted_label_ciphertext,
                encrypted_value_iv, encrypted_value_ciphertext, keyword, localisation,
                template_id, changed_by, changed_at, reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                str(uuid.uuid4()), secret_id,
                current["encrypted_label_iv"], current["encrypted_label_ciphertext"],
                current["encrypted_value_iv"], current["encrypted_value_ciphertext"],
                current["keyword"], current["localisation"], current["template_id"],
                changed_by, fields["updated_at"], body.get("reason"),
            ],
        )

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        cur.execute(f"UPDATE secrets SET {set_clause} WHERE id = ?", [*fields.values(), secret_id])
        cur.execute(
            "INSERT INTO secret_history (id, secret_id, action, changed_by, changed_at, reason) VALUES (?, ?, ?, ?, ?, ?)",
            [str(uuid.uuid4()), secret_id, "updated", changed_by, fields["updated_at"], body.get("reason")],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/keywords", methods=["GET"])
def list_keywords():
    """Navigation par mot-clé -- À TRAVERS TOUTES les collections,
    peu importe si la personne y a accès ou non. Demandé explicitement
    après un retour clair : le but du mot-clé est d'aider quelqu'un à
    retrouver un code EN URGENCE, y compris avant d'avoir l'accès à la
    collection concernée -- il doit donc pouvoir être parcouru sans
    filtrage par accès, contrairement à tout le reste de cette API.

    Expose UNIQUEMENT mot-clé + nom de la collection (pour savoir où
    chercher / qui contacter) -- JAMAIS le libellé exact ni la valeur,
    qui restent chiffrés et hors de portée sans le bon accès. "Tout ne
    doit pas être visible" (dixit la personne) -- seul ce niveau de
    catégorisation devient repérable, pas le contenu sensible lui-même.
    """
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT s.keyword, s.collection_id, c.name AS collection_name, s.localisation
               FROM secrets s
               JOIN collections c ON c.id = s.collection_id
               WHERE s.keyword IS NOT NULL AND s.keyword != ''
               ORDER BY s.keyword"""
        )
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/templates", methods=["GET"])
def list_templates():
    """Modèles de fiche. Sans `?collection_id=`, comportement INCHANGÉ
    (tous les modèles, tous globaux avant ce chantier) -- avec, ajoute
    les modèles propres à CETTE collection à la liste des globaux
    (jamais les modèles d'une AUTRE collection). Toujours pure
    structure, jamais de contenu sensible, visible de tout le monde
    comme les mots-clés."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        collection_id = request.args.get("collection_id")
        if collection_id:
            cur.execute(
                "SELECT id, name, field_labels, collection_id, required_labels, created_by, created_at "
                "FROM secret_templates WHERE collection_id IS NULL OR collection_id = ? ORDER BY name",
                [collection_id],
            )
        else:
            cur.execute(
                "SELECT id, name, field_labels, collection_id, required_labels, created_by, created_at "
                "FROM secret_templates ORDER BY name"
            )
        templates = []
        for r in cur.fetchall():
            row = dict(r)
            try:
                row["field_labels"] = json.loads(row["field_labels"])
            except (ValueError, TypeError):
                row["field_labels"] = []  # ligne corrompue -- jamais faire échouer toute la liste pour une seule entrée
            try:
                row["required_labels"] = json.loads(row["required_labels"]) if row["required_labels"] else []
            except (ValueError, TypeError):
                row["required_labels"] = []  # même précaution -- indicatif seulement, jamais bloquant de toute façon
            templates.append(row)
        return jsonify(templates), 200
    finally:
        conn.close()


@app.route("/templates", methods=["POST"])
def create_template():
    """`field_labels` : liste de chaînes (ex. ["PUK", "PIN", "Numéro"])
    -- jamais de contenu, uniquement la FORME. `collection_id` optionnel
    (absent/None = modèle GLOBAL, comportement inchangé). `required_labels`
    optionnel -- INDICATIF seulement (jamais bloquant à l'enregistrement
    d'un secret, décidé explicitement avec la personne) : filtré pour ne
    garder que les libellés réellement présents dans field_labels, jamais
    une valeur incohérente stockée silencieusement. Aucune contrainte
    d'unicité sur le nom : deux personnes peuvent légitimement créer
    des variantes "Carte SIM" différentes, pas à cette route de trancher."""
    body = request.get_json(silent=True) or {}
    name = (body.get("name") or "").strip()
    field_labels = body.get("field_labels")
    created_by = body.get("created_by")
    if not name or not created_by or not isinstance(field_labels, list) or not field_labels:
        return jsonify({"error": "name, created_by et field_labels (liste non vide) requis"}), 400
    collection_id = body.get("collection_id") or None
    required_labels_in = body.get("required_labels")
    required_labels = (
        [l for l in required_labels_in if l in field_labels]
        if isinstance(required_labels_in, list)
        else []
    )

    conn = get_connection()
    try:
        cur = conn.cursor()
        template_id = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO secret_templates (id, name, field_labels, collection_id, required_labels, created_by, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            [template_id, name, json.dumps(field_labels), collection_id, json.dumps(required_labels), created_by, now_iso()],
        )
        conn.commit()
        return jsonify({"status": "ok", "id": template_id}), 201
    finally:
        conn.close()


@app.route("/templates/<template_id>", methods=["DELETE"])
def delete_template(template_id):
    """Ne touche JAMAIS aux secrets créés depuis ce modèle -- voir
    commentaire du schéma secrets.template_id (référence logique,
    jamais bloquée par une suppression)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM secret_templates WHERE id = ?", [template_id])
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/secrets/<secret_id>/history", methods=["GET"])
def get_secret_history(secret_id):
    """Qui/quand/motif -- jamais le contenu avant/après (voir
    commentaire du schéma secret_history). Ordre chronologique
    croissant (création en premier), le plus lisible pour une
    lecture d'audit."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT action, changed_by, changed_at, reason FROM secret_history WHERE secret_id = ? ORDER BY changed_at",
            [secret_id],
        )
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/history", methods=["GET"])
def get_global_history():
    """Journal À TRAVERS TOUT LE COFFRE -- pour le tableau de bord du
    maître_système (voir vault/README.md), pas le journal d'UN secret
    (ci-dessus). Ordre chronologique DÉCROISSANT (le plus récent en
    premier, plus utile pour une vue d'ensemble que pour un audit
    ciblé) -- inverse volontaire par rapport à get_secret_history.

    Jamais le contenu, comme toujours -- secret_id seul ne révèle rien
    (libellé chiffré) : c'est au CLIENT de croiser avec les secrets
    déjà déchiffrés pour afficher un libellé lisible (voir
    vaultOps.js, fetchGlobalHistory). Volontairement PAS restreinte
    par rôle ici : ce n'est que des métadonnées (qui/quand/motif),
    jamais de contenu -- l'interface, elle, réserve son affichage au
    maître_système (is_system_master), cohérent avec la demande
    d'origine, mais rien ici n'empêcherait techniquement un accès plus
    large si un jour souhaité.

    Limité aux 200 entrées les plus récentes -- un tableau de bord,
    pas un export exhaustif."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT secret_id, action, changed_by, changed_at, reason FROM secret_history ORDER BY changed_at DESC LIMIT 200"
        )
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/secrets/observations-summary", methods=["POST"])
def observations_summary():
    """Résumé agrégé (nombre + horodatage le plus récent) des
    observations pour un ENSEMBLE de secrets -- demandé explicitement
    (page "Observations", tableau trié/filtré sur tous les secrets
    accessibles à la personne). Jamais le TEXTE des observations ici
    (chiffré, inutile pour un résumé -- juste compter et dater),
    évite l'aller-retour en N+1 requêtes qu'aurait demandé une liste
    complète par secret.

    POST plutôt qu'un GET avec paramètres de requête -- la liste
    d'identifiants peut être longue (autant de secrets que la
    personne a accès), une URL a une limite de longueur pratique
    qu'une liste de dizaines d'UUID dépasserait vite.

    Filtrage d'accès fait CÔTÉ CLIENT (qui connaît déjà la liste des
    secrets accessibles via GET /collections puis
    /collections/<id>/secrets) -- cette route répond pour EXACTEMENT
    les identifiants demandés, sans revalidation d'accès côté serveur
    (même posture de confiance que le reste de cette API)."""
    body = request.get_json(silent=True) or {}
    ids = body.get("ids", [])
    if not isinstance(ids, list) or not ids:
        return jsonify({}), 200

    conn = get_connection()
    try:
        cur = conn.cursor()
        placeholders = ",".join(["?"] * len(ids))
        cur.execute(
            f"""SELECT secret_id, COUNT(*) as count, MAX(created_at) as most_recent_at
                FROM secret_observations
                WHERE secret_id IN ({placeholders})
                GROUP BY secret_id""",
            ids,
        )
        result = {r["secret_id"]: {"count": r["count"], "most_recent_at": r["most_recent_at"]} for r in cur.fetchall()}
        return jsonify(result), 200
    finally:
        conn.close()


@app.route("/secrets/<secret_id>/observations", methods=["GET"])
def list_secret_observations(secret_id):
    """Liste chronologique croissante (plus ancienne en premier, comme
    l'historique ci-dessus) -- chaque entrée reste un blob chiffré
    opaque pour ce serveur, comme le libellé/les champs."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, encrypted_text_iv, encrypted_text_ciphertext, author, created_at
               FROM secret_observations WHERE secret_id = ? ORDER BY created_at""",
            [secret_id],
        )
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/secrets/<secret_id>/observations", methods=["POST"])
def add_secret_observation(secret_id):
    """Ajoute une observation -- texte déjà chiffré côté client (voir
    commentaire du schéma secret_observations), cette route ne fait
    que le stocker. Pas de modification/suppression individuelle en
    V1 (liste d'annotations accumulées, pas un contenu qu'on retouche)."""
    body = request.get_json(silent=True) or {}
    required = ["encrypted_text_iv", "encrypted_text_ciphertext", "author"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return jsonify({"error": f"champs requis manquants : {missing}"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM secrets WHERE id = ?", [secret_id])
        if cur.fetchone() is None:
            return jsonify({"error": "secret introuvable"}), 404
        observation_id = str(uuid.uuid4())
        cur.execute(
            """INSERT INTO secret_observations
               (id, secret_id, encrypted_text_iv, encrypted_text_ciphertext, author, created_at)
               VALUES (?, ?, ?, ?, ?, ?)""",
            [observation_id, secret_id, body["encrypted_text_iv"], body["encrypted_text_ciphertext"],
             body["author"], now_iso()],
        )
        conn.commit()
        return jsonify({"status": "ok", "id": observation_id}), 201
    finally:
        conn.close()


@app.route("/secrets/<secret_id>/record-access", methods=["POST"])
def record_secret_access(secret_id):
    """Incrémente le compteur d'usage -- appelé par le front quand la
    VALEUR du secret est révélée (pas juste le libellé, qui est déjà
    visible dans la liste). Ne révèle jamais CE QU'EST le secret,
    juste qu'il a été consulté -- utilisé pour le "top 10 des codes
    utilisés" (agrégé côté client à travers les collections
    accessibles, pas une requête cross-collection ici)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE secrets SET access_count = access_count + 1, last_accessed_at = ? WHERE id = ?",
            [now_iso(), secret_id],
        )
        conn.commit()
        if cur.rowcount == 0:
            return jsonify({"error": "secret introuvable"}), 404
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/secrets/<secret_id>", methods=["DELETE"])
def archive_secret(secret_id):
    """ARCHIVAGE, pas une vraie suppression -- décision explicite
    (retour : "suppression... avec archivage pour tous les
    utilisateurs"). Exige `archived_by` (même discipline que
    update_secret) -- journalisé dans secret_history comme les autres
    actions. Le secret RESTE en base, is_archived=1, restaurable via
    /restore ci-dessous."""
    body = request.get_json(silent=True) or {}
    archived_by = body.get("archived_by")
    if not archived_by:
        return jsonify({"error": "archived_by requis pour journaliser l'archivage"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        now = now_iso()
        cur.execute(
            "UPDATE secrets SET is_archived = 1, last_changed_by = ? WHERE id = ?",
            [archived_by, secret_id],
        )
        if cur.rowcount == 0:
            conn.rollback()
            return jsonify({"error": "secret introuvable"}), 404
        cur.execute(
            "INSERT INTO secret_history (id, secret_id, action, changed_by, changed_at, reason) VALUES (?, ?, ?, ?, ?, ?)",
            [str(uuid.uuid4()), secret_id, "archived", archived_by, now, body.get("reason")],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/secrets/<secret_id>/restore", methods=["POST"])
def restore_secret(secret_id):
    """Annule un archivage -- réservé au PROPRIÉTAIRE (created_by),
    demandé explicitement ("possibilité pour le PROPRIÉTAIRE de
    revenir en arrière"). Vérification LOGIQUE uniquement (compare
    `restored_by` à created_by), pas une vraie garantie serveur --
    vault-api ne vérifie aucun jeton d'authentification sur aucune de
    ses routes, caractéristique déjà connue de toute cette API."""
    body = request.get_json(silent=True) or {}
    restored_by = body.get("restored_by")
    if not restored_by:
        return jsonify({"error": "restored_by requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT created_by FROM secrets WHERE id = ?", [secret_id])
        row = cur.fetchone()
        if row is None:
            return jsonify({"error": "secret introuvable"}), 404
        if row["created_by"] != restored_by:
            return jsonify({"error": "seul le propriétaire (créateur) peut restaurer ce secret"}), 403

        now = now_iso()
        cur.execute(
            "UPDATE secrets SET is_archived = 0, last_changed_by = ? WHERE id = ?",
            [restored_by, secret_id],
        )
        cur.execute(
            "INSERT INTO secret_history (id, secret_id, action, changed_by, changed_at, reason) VALUES (?, ?, ?, ?, ?, ?)",
            [str(uuid.uuid4()), secret_id, "restored", restored_by, now, body.get("reason")],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/secrets/<secret_id>/versions", methods=["GET"])
def list_secret_versions(secret_id):
    """Versions PASSÉES avec contenu complet (voir commentaire du
    schéma secret_versions) -- pour l'écran de retour en arrière.
    Ordre chronologique DÉCROISSANT (la plus récente en premier, la
    plus probable à vouloir restaurer)."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """SELECT id, encrypted_label_iv, encrypted_label_ciphertext,
                      encrypted_value_iv, encrypted_value_ciphertext, keyword,
                      localisation, template_id, changed_by, changed_at, reason
               FROM secret_versions WHERE secret_id = ? ORDER BY changed_at DESC""",
            [secret_id],
        )
        return jsonify([dict(r) for r in cur.fetchall()]), 200
    finally:
        conn.close()


@app.route("/secrets/<secret_id>/versions/<version_id>/restore", methods=["POST"])
def restore_secret_version(secret_id, version_id):
    """Retour en arrière -- réservé au PROPRIÉTAIRE (created_by), même
    raisonnement que /restore ci-dessus. AVANT d'appliquer la version
    choisie, capture l'état ACTUEL dans une NOUVELLE entrée
    secret_versions -- un retour en arrière reste toujours lui-même
    annulable, jamais une opération à sens unique."""
    body = request.get_json(silent=True) or {}
    restored_by = body.get("restored_by")
    if not restored_by:
        return jsonify({"error": "restored_by requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT created_by FROM secrets WHERE id = ?", [secret_id])
        secret_row = cur.fetchone()
        if secret_row is None:
            return jsonify({"error": "secret introuvable"}), 404
        if secret_row["created_by"] != restored_by:
            return jsonify({"error": "seul le propriétaire (créateur) peut restaurer une version"}), 403

        cur.execute("SELECT * FROM secret_versions WHERE id = ? AND secret_id = ?", [version_id, secret_id])
        version_row = cur.fetchone()
        if version_row is None:
            return jsonify({"error": "version introuvable"}), 404

        now = now_iso()
        # Instantané de l'état ACTUEL avant de le remplacer -- même
        # principe que update_secret, un retour en arrière reste
        # lui-même annulable.
        cur.execute("SELECT * FROM secrets WHERE id = ?", [secret_id])
        current = cur.fetchone()
        cur.execute(
            """INSERT INTO secret_versions
               (id, secret_id, encrypted_label_iv, encrypted_label_ciphertext,
                encrypted_value_iv, encrypted_value_ciphertext, keyword, localisation,
                template_id, changed_by, changed_at, reason)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                str(uuid.uuid4()), secret_id,
                current["encrypted_label_iv"], current["encrypted_label_ciphertext"],
                current["encrypted_value_iv"], current["encrypted_value_ciphertext"],
                current["keyword"], current["localisation"], current["template_id"],
                restored_by, now, f"état remplacé par un retour en arrière",
            ],
        )

        cur.execute(
            """UPDATE secrets SET
               encrypted_label_iv = ?, encrypted_label_ciphertext = ?,
               encrypted_value_iv = ?, encrypted_value_ciphertext = ?,
               keyword = ?, localisation = ?, template_id = ?,
               updated_at = ?, last_changed_by = ?
               WHERE id = ?""",
            [
                version_row["encrypted_label_iv"], version_row["encrypted_label_ciphertext"],
                version_row["encrypted_value_iv"], version_row["encrypted_value_ciphertext"],
                version_row["keyword"], version_row["localisation"], version_row["template_id"],
                now, restored_by, secret_id,
            ],
        )
        cur.execute(
            "INSERT INTO secret_history (id, secret_id, action, changed_by, changed_at, reason) VALUES (?, ?, ?, ?, ?, ?)",
            [str(uuid.uuid4()), secret_id, "reverted", restored_by, now, body.get("reason")],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 200
    finally:
        conn.close()


@app.route("/recovery-archive", methods=["POST"])
def deposit_recovery_key():
    """
    Dépôt de la clé de récupération d'un utilisateur, chiffrée avec la
    clé PUBLIQUE du compte maître_principal — appelé côté client à la
    création d'un compte coffre, UNIQUEMENT si un maître_principal
    existe (décision prise côté front, pas ici). Dépôt à SENS UNIQUE :
    cette route n'expose AUCUNE lecture -- voir vault-admin-api pour
    ça, un service séparé, jamais exposé par la passerelle publique.

    UPSERT volontaire (pas un simple "créer si absent") : si le
    compte maître_principal est un jour recréé (nouvelle paire de
    clés), les anciennes archives deviendraient inutilisables --
    permettre un redépôt évite de bloquer silencieusement ce cas,
    même si la vraie procédure de rotation reste à définir plus tard.
    """
    body = request.get_json(silent=True) or {}
    login = body.get("login")
    wrapped_key = body.get("wrapped_recovery_key_for_master")
    if not login or not wrapped_key:
        return jsonify({"error": "login et wrapped_recovery_key_for_master requis"}), 400

    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM users WHERE login = ?", [login])
        if cur.fetchone() is None:
            return jsonify({"error": f"utilisateur '{login}' introuvable"}), 400
        cur.execute(
            """INSERT INTO recovery_key_archive (login, wrapped_recovery_key_for_master, archived_at)
               VALUES (?, ?, ?)
               ON CONFLICT(login) DO UPDATE SET wrapped_recovery_key_for_master = excluded.wrapped_recovery_key_for_master,
                   archived_at = excluded.archived_at""",
            [login, wrapped_key, now_iso()],
        )
        conn.commit()
        return jsonify({"status": "ok"}), 201
    finally:
        conn.close()


# ------------------------------------------------------------------
# Journal en memoire (endpoint /logs) -- capture les WARNING et plus
# graves de CE service pour l'agregateur de logs du hub (gestionnaire
# de logs, livraison #139). Meme motif EXACT que api/app.py -- ne
# capture PAS le corps des requetes ni de donnee metier (coffre-fort
# CHIFFRE -- seulement ce que ce fichier journalise deja lui-meme,
# jamais un secret). Tampon circulaire en memoire, borne
# (LOG_BUFFER_SIZE, defaut 200), jamais persiste sur disque. Seuil
# par defaut WARNING (pas INFO) : evite le bruit des logs d'acces
# Werkzeug.
# ------------------------------------------------------------------
# Client Memcached -- livraison #145, nécessaire au tampon de logs
# PARTAGÉ ci-dessous (ce service tourne avec 2 workers Gunicorn,
# processus séparés, mémoire NON partagée). Recréé à chaque appel
# (même motif établi ailleurs dans ce projet, voir api/app.py) --
# évite de garder une connexion morte si Memcached redémarre.
from pymemcache.client.base import Client as _MemcacheClient

MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


# Journal PARTAGE (endpoint /logs) -- stocke dans Memcached (voir
# shared/log_buffer.py pour le raisonnement complet) -- PAS un tampon
# en memoire de processus.
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
except ImportError:
    make_shared_log_handler = None
    read_shared_log_buffer = None

SERVICE_NAME = "vault-api"
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


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
