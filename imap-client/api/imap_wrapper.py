"""
Wrapper autour d'`imaplib` (bibliothèque STANDARD Python, aucune
dépendance externe nécessaire) -- livraison #179, backlog BACKLOG.md
#4, volet 1/4 ("Client IMAP") : recevoir des messages provenant de
systèmes qui ne savent notifier que par e-mail.

À DISTINGUER explicitement de `pixel-grid/data-generator/
parse_zenoss_emails.py` (mentionné dans le backlog comme précédent) :
CE module-là est un parseur HORS LIGNE, sur un export texte manuel
(Thunderbird), figé sur UN SEUL format Zenoss précis -- CE module-ci
(`imap-client`) est une CONNEXION LIVE à une vraie boîte IMAP,
générique (n'importe quel message, pas seulement du Zenoss), lecture
seule pour l'instant. La généralisation vers un "gabarit
configurable" (volet 3/4, "Gestionnaire d'interpréteur") reste un
chantier SÉPARÉ, pas construit ici.

Volet 1/4 UNIQUEMENT (voir BACKLOG.md #4, ordre donné par la
personne) : connexion + LISTE des dossiers + LISTE/LECTURE des
messages. AUCUNE action d'écriture (marquer lu, déplacer, supprimer,
créer un dossier) -- ça, c'est le volet 2/4 ("Interface de gestion de
la boîte"), volontairement PAS construit dans cette livraison pour
rester dans l'ordre annoncé.

**Volet 2/4 (livraison #189)** : "Interface de gestion de la boîte"
-- création/suppression de DOSSIERS (`create_folder`/`delete_folder`)
et DÉPLACEMENT de message entre dossiers (`move_message`, pour
trier). Ce volet-ci EST le premier à écrire réellement sur le
serveur IMAP -- `select(..., readonly=False)` uniquement pour
`move_message` (jamais pour la lecture, `list_messages`/
`fetch_message` du volet 1 restent `readonly=True`, inchangés).
"Filtres" interprété comme : recherche IMAP native lors du LISTAGE
(`SUBJECT`/`FROM`/`UNSEEN`, voir `list_messages`) -- PAS un moteur de
règles automatiques (façon Sieve, qui déplacerait des messages tout
seul selon des critères enregistrés) -- cette distinction n'était pas
tranchée dans le backlog, APPROXIMATION documentée (mode adopté
depuis #178) : la personne trie manuellement en s'appuyant sur ces
filtres et le déplacement, rien d'automatique pour l'instant.

**Mode "approximer et documenter" adopté explicitement par la
personne (#178)** -- deux approximations notables ici, à
reconsidérer si elles gênent en usage réel :
1. `list_messages` trie par UID DÉCROISSANT (le plus récent en
   dernier arrivé en premier) -- une APPROXIMATION de "plus récent
   d'abord", jamais une garantie du protocole IMAP (RFC 3501) : les
   UID sont croissants avec le temps sur la VASTE majorité des
   serveurs (Dovecot, Exchange...), mais rien ne l'impose absolument.
   Un vrai tri par Date: d'en-tête serait plus robuste mais
   demanderait de FETCHer tous les en-têtes avant de trier --
   coûteux sur une grosse boîte, écarté pour cette première version.
2. Extraction du corps : préfère `text/plain`, repli sur
   `text/html` si aucune partie texte pur n'existe -- le HTML n'est
   JAMAIS nettoyé/assaini ici (ce sera le rôle du volet 3/4,
   l'interpréteur, de décider quoi en faire) -- renvoyé BRUT, à ne
   jamais afficher tel quel sans échappement côté consommateur.
"""
import email
import imaplib
import logging
import re
import time
from email.header import decode_header

# Traces DEBUG (livraison #223, audit rétroactif). RÈGLE ABSOLUE : le
# mot de passe IMAP n'apparaît JAMAIS dans une trace.
_log = logging.getLogger("imap_wrapper")


class ImapError(Exception):
    """Levée pour toute erreur de communication ou de protocole IMAP
    -- jamais une imaplib.IMAP4.error ou OSError brute qui
    remonterait telle quelle à l'appelant HTTP de ce module."""


def connect(host, port, username, password, use_ssl=True, timeout=10):
    """Connexion + authentification -- délai d'attente EXPLICITE
    (même raisonnement que dba/api/connectors/mysql.py et
    postgres.py, `connect_timeout=5` -- un hôte injoignable doit
    échouer VITE, jamais bloquer indéfiniment un worker Gunicorn).
    `imaplib` n'expose pas nativement `timeout` sur IMAP4 (Python
    <3.9) mais le fait depuis 3.9 -- ce projet cible 3.12 partout
    (voir les autres Dockerfile), donc utilisable sans détour."""
    _log.debug("connect : démarré (%s:%s, ssl=%s, timeout=%ss, jamais le mot de passe ici)", host, port, use_ssl, timeout)
    start = time.monotonic()
    try:
        if use_ssl:
            conn = imaplib.IMAP4_SSL(host, port, timeout=timeout)
        else:
            conn = imaplib.IMAP4(host, port, timeout=timeout)
        conn.login(username, password)
    except (imaplib.IMAP4.error, OSError) as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        _log.debug("connect : ÉCHEC après %d ms -- %s", elapsed_ms, exc)
        raise ImapError(f"connexion IMAP échouée ({host}:{port}) : {exc}") from exc
    elapsed_ms = int((time.monotonic() - start) * 1000)
    _log.debug("connect : succès en %d ms", elapsed_ms)
    return conn


def safe_logout(conn):
    """Best-effort -- ne lève JAMAIS, appelée systématiquement dans
    un `finally` côté app.py, une déconnexion déjà rompue ne doit
    jamais masquer l'erreur PRINCIPALE qui a précédé."""
    try:
        conn.logout()
        _log.debug("safe_logout : déconnexion effectuée")
    except Exception as exc:  # noqa: BLE001 -- best-effort assumé, voir docstring
        _log.debug("safe_logout : échec best-effort ignoré -- %s", exc)


def _decode_mime_header(raw):
    """Décode un en-tête potentiellement encodé RFC 2047 (ex.
    "=?UTF-8?B?...?=") -- Subject/From peuvent contenir des accents
    encodés selon CE standard, jamais de l'UTF-8 brut directement
    dans l'en-tête. Chaîne vide si `raw` est vide/absent, jamais une
    exception."""
    if not raw:
        return ""
    parts = decode_header(raw)
    decoded = []
    for text, charset in parts:
        if isinstance(text, bytes):
            try:
                decoded.append(text.decode(charset or "utf-8", errors="replace"))
            except LookupError:  # charset annoncé mais inconnu de Python
                decoded.append(text.decode("utf-8", errors="replace"))
        else:
            decoded.append(text)
    return "".join(decoded)


def _decode_payload(part):
    """Décode le CORPS d'une partie MIME selon son charset annoncé
    (jamais supposé UTF-8 par défaut sans vérifier) -- repli UTF-8
    avec remplacement si le charset annoncé est invalide/inconnu,
    jamais une exception qui ferait échouer tout le message pour une
    seule partie mal formée."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return payload.decode("utf-8", errors="replace")


def _extract_bodies(msg):
    """Renvoie (body_text, body_html) -- None pour celui absent.
    Ignore les pièces jointes (Content-Disposition: attachment) --
    seul le corps du message lui-même, jamais son contenu joint,
    voir docstring du module pour la limite "HTML jamais assaini
    ici"."""
    body_text, body_html = None, None
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            disposition = str(part.get("Content-Disposition") or "")
            if "attachment" in disposition.lower():
                continue
            if content_type == "text/plain" and body_text is None:
                body_text = _decode_payload(part)
            elif content_type == "text/html" and body_html is None:
                body_html = _decode_payload(part)
    else:
        if msg.get_content_type() == "text/html":
            body_html = _decode_payload(msg)
        else:
            body_text = _decode_payload(msg)
    return body_text, body_html


_FOLDER_NAME_RE = re.compile(r'"([^"]*)"$')


def _parse_folder_line(raw):
    """Une ligne de réponse IMAP LIST ressemble à :
    `(\\HasNoChildren) "/" "INBOX"` -- le nom du dossier est le
    DERNIER token entre guillemets, JAMAIS un split naïf sur
    l'espace (un nom de dossier peut lui-même contenir des espaces,
    ex. "Dossiers partages/Support"). Repli sur le dernier token brut
    si la ligne n'a pas de guillemets (rare, dossiers sans caractère
    spécial sur certains serveurs)."""
    decoded = raw.decode("utf-8", errors="replace") if isinstance(raw, bytes) else raw
    match = _FOLDER_NAME_RE.search(decoded)
    if match:
        return match.group(1)
    tokens = decoded.split()
    return tokens[-1] if tokens else decoded


def list_folders(conn):
    """Liste des noms de dossiers IMAP (ex. ["INBOX", "Archive",
    "Support/Zenoss"])."""
    status, raw_folders = conn.list()
    if status != "OK":
        raise ImapError("liste des dossiers IMAP échouée")
    return [_parse_folder_line(f) for f in raw_folders if f is not None]


def _escape_search_term(term):
    """Échappe les guillemets/antislashs d'un terme de recherche IMAP
    -- une valeur transmise EN L'ÉTAT dans la commande SEARCH sans ça
    pourrait rompre la syntaxe (ou pire, injecter des critères
    supplémentaires) si elle contient elle-même des guillemets."""
    return term.replace("\\", "\\\\").replace('"', '\\"')


def list_messages(conn, folder, limit=50, offset=0, subject_filter=None, from_filter=None, unseen_only=False):
    """Renvoie (messages, total) -- `messages` : liste de
    {uid, subject, from, date}, la plus RÉCENTE en premier
    (approximation par UID décroissant, voir docstring du module).
    `readonly=True` sur SELECT -- ce volet ne marque JAMAIS un
    message comme lu, aucun effet de bord sur la boîte distante.
    FETCH seulement RFC822.HEADER (pas le corps entier) pour cette
    liste -- bien moins coûteux sur une boîte volumineuse que de tout
    charger juste pour afficher un sujet.

    **Filtres (livraison #189)** : `subject_filter`/`from_filter`
    (recherche PARTIELLE, insensible à la casse côté serveur --
    comportement IMAP standard) et `unseen_only` -- recherche NATIVE
    IMAP (`SEARCH`), jamais un filtrage après coup côté Python (
    bien plus lourd sur une grosse boîte). Sans filtre -- `ALL`,
    comportement du volet 1 inchangé."""
    status, _ = conn.select(folder, readonly=True)
    if status != "OK":
        raise ImapError(f"dossier '{folder}' introuvable ou inaccessible")

    criteria = []
    if unseen_only:
        criteria.append("UNSEEN")
    if subject_filter:
        criteria.extend(["SUBJECT", f'"{_escape_search_term(subject_filter)}"'])
    if from_filter:
        criteria.extend(["FROM", f'"{_escape_search_term(from_filter)}"'])
    if not criteria:
        criteria = ["ALL"]

    status, data = conn.search(None, *criteria)
    if status != "OK":
        raise ImapError(f"recherche IMAP échouée sur '{folder}'")
    uids = data[0].split() if data and data[0] else []
    uids = list(reversed(uids))
    total = len(uids)
    page = uids[offset:offset + limit]

    messages = []
    for uid in page:
        status, msg_data = conn.fetch(uid, "(RFC822.HEADER)")
        if status != "OK" or not msg_data or msg_data[0] is None:
            continue  # message disparu entre le SEARCH et le FETCH (rare, jamais bloquant)
        raw_header = msg_data[0][1]
        msg = email.message_from_bytes(raw_header)
        messages.append({
            "uid": uid.decode() if isinstance(uid, bytes) else uid,
            "subject": _decode_mime_header(msg.get("Subject", "")),
            "from": _decode_mime_header(msg.get("From", "")),
            "date": msg.get("Date", "") or "",
        })
    return messages, total


def fetch_message(conn, folder, uid):
    """Message COMPLET (en-têtes + corps texte/HTML) pour un UID
    précis. `readonly=True` -- même raisonnement que list_messages,
    jamais de marquage "lu" par ce volet."""
    status, _ = conn.select(folder, readonly=True)
    if status != "OK":
        raise ImapError(f"dossier '{folder}' introuvable ou inaccessible")

    uid_bytes = uid.encode() if isinstance(uid, str) else uid
    status, msg_data = conn.fetch(uid_bytes, "(RFC822)")
    if status != "OK" or not msg_data or msg_data[0] is None:
        raise ImapError(f"message '{uid}' introuvable dans '{folder}'")

    raw = msg_data[0][1]
    msg = email.message_from_bytes(raw)
    body_text, body_html = _extract_bodies(msg)
    return {
        "uid": uid if isinstance(uid, str) else uid.decode(),
        "folder": folder,
        "subject": _decode_mime_header(msg.get("Subject", "")),
        "from": _decode_mime_header(msg.get("From", "")),
        "to": _decode_mime_header(msg.get("To", "")),
        "date": msg.get("Date", "") or "",
        "body_text": body_text,
        "body_html": body_html,
    }


# ------------------------------------------------------------------
# Gestion de la boîte (livraison #189, volet 2/4) -- PREMIÈRES
# actions d'ÉCRITURE de ce module (le volet 1 était lecture seule).
# ------------------------------------------------------------------

def create_folder(conn, name):
    """Crée un dossier IMAP. Lève ImapError avec le détail RÉEL
    renvoyé par le serveur en cas d'échec (nom déjà pris, caractère
    interdit selon le serveur...) -- jamais un message générique."""
    status, data = conn.create(name)
    if status != "OK":
        detail = data[0].decode("utf-8", errors="replace") if data and data[0] else "raison inconnue"
        raise ImapError(f"création du dossier '{name}' échouée : {detail}")


def delete_folder(conn, name):
    """Supprime un dossier IMAP -- ne supprime PAS ses messages au
    préalable (comportement du serveur, hors de portée de ce
    wrapper) -- la plupart des serveurs refusent de toute façon de
    supprimer un dossier non vide, l'erreur renvoyée le dit
    explicitement."""
    status, data = conn.delete(name)
    if status != "OK":
        detail = data[0].decode("utf-8", errors="replace") if data and data[0] else "raison inconnue"
        raise ImapError(f"suppression du dossier '{name}' échouée : {detail}")


def move_message(conn, source_folder, uid, dest_folder):
    """Déplace UN message -- COPY vers `dest_folder` PUIS marquage
    `\\Deleted` + EXPUNGE sur l'original (motif COMPATIBLE avec TOUS
    les serveurs IMAP, plutôt que l'extension `MOVE`/RFC 6851, pas
    universellement supportée). `select(..., readonly=False)` ICI
    SEULEMENT -- la SEULE fonction de ce module qui ouvre le dossier
    en écriture, voir docstring du module.

    En cas d'échec du STORE/EXPUNGE APRÈS un COPY déjà réussi, lève
    une erreur qui le dit EXPLICITEMENT (le message existe alors en
    DOUBLE, dans les deux dossiers) -- jamais un échec silencieux qui
    laisserait croire à un déplacement raté alors qu'une copie a bien
    été créée."""
    status, _ = conn.select(source_folder, readonly=False)
    if status != "OK":
        raise ImapError(f"dossier '{source_folder}' introuvable ou inaccessible")

    uid_bytes = uid.encode() if isinstance(uid, str) else uid
    status, data = conn.uid("COPY", uid_bytes, dest_folder)
    if status != "OK":
        detail = data[0].decode("utf-8", errors="replace") if data and data[0] else "raison inconnue"
        raise ImapError(f"copie du message '{uid}' vers '{dest_folder}' échouée : {detail}")

    status, data = conn.uid("STORE", uid_bytes, "+FLAGS", "(\\Deleted)")
    if status != "OK":
        detail = data[0].decode("utf-8", errors="replace") if data and data[0] else "raison inconnue"
        raise ImapError(
            f"message copié dans '{dest_folder}' MAIS marquage pour suppression dans "
            f"'{source_folder}' échoué ({detail}) -- le message existe maintenant en double, "
            f"à vérifier manuellement"
        )
    conn.expunge()


# ------------------------------------------------------------------
# Étiquettes et marquage (livraison #190, précision de la personne
# sur le sens de "filtres" -- "poser des étiquettes... déclencher des
# actions"). Une ÉTIQUETTE ici = un mot-clé IMAP personnalisé
# (keyword flag, ex. "Facture") -- PAS un système à part, directement
# le mécanisme de flags IMAP standard, supporté par la plupart des
# serveurs modernes (Dovecot, Gmail...) mais PAS universellement (le
# serveur l'annonce ou non via PERMANENTFLAGS au SELECT) -- jamais
# vérifié explicitement ici, l'erreur du serveur (si non supporté)
# remonte telle quelle si ça échoue.
# ------------------------------------------------------------------

def add_label(conn, folder, uid, label):
    status, _ = conn.select(folder, readonly=False)
    if status != "OK":
        raise ImapError(f"dossier '{folder}' introuvable ou inaccessible")
    uid_bytes = uid.encode() if isinstance(uid, str) else uid
    status, data = conn.uid("STORE", uid_bytes, "+FLAGS", f"({label})")
    if status != "OK":
        detail = data[0].decode("utf-8", errors="replace") if data and data[0] else "raison inconnue"
        raise ImapError(f"ajout de l'étiquette '{label}' échoué : {detail}")


def remove_label(conn, folder, uid, label):
    status, _ = conn.select(folder, readonly=False)
    if status != "OK":
        raise ImapError(f"dossier '{folder}' introuvable ou inaccessible")
    uid_bytes = uid.encode() if isinstance(uid, str) else uid
    status, data = conn.uid("STORE", uid_bytes, "-FLAGS", f"({label})")
    if status != "OK":
        detail = data[0].decode("utf-8", errors="replace") if data and data[0] else "raison inconnue"
        raise ImapError(f"retrait de l'étiquette '{label}' échoué : {detail}")


def mark_seen(conn, folder, uid):
    """Marque un message comme LU (`\\Seen`) -- volontairement SÉPARÉ
    de list_messages/fetch_message (volet 1, toujours en LECTURE
    SEULE, jamais ce marquage en consultant) -- seulement via une
    action EXPLICITE (ici, ou une règle du volet 2/#190)."""
    status, _ = conn.select(folder, readonly=False)
    if status != "OK":
        raise ImapError(f"dossier '{folder}' introuvable ou inaccessible")
    uid_bytes = uid.encode() if isinstance(uid, str) else uid
    status, data = conn.uid("STORE", uid_bytes, "+FLAGS", "(\\Seen)")
    if status != "OK":
        detail = data[0].decode("utf-8", errors="replace") if data and data[0] else "raison inconnue"
        raise ImapError(f"marquage comme lu échoué : {detail}")
