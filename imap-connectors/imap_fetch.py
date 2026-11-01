# -*- coding: utf-8 -*-
"""Récupération IMAP des connecteurs (livraison #489).

Même raisonnement qu'imap-client (#179) : une connexion NEUVE à chaque
relevé (jamais gardée ouverte — timeout d'inactivité IMAP courant),
imaplib de la bibliothèque standard, aucune dépendance.

fetch_unseen() ne marque lu qu'APRÈS prise en charge réussie côté
app.py (mark_seen du connecteur) : un message dont le routage échoue
reste non lu et sera repris au relevé suivant — la boîte fait office
de file d'attente de secours."""
import email
import email.header
import email.utils
import imaplib
import re

BODY_LIMIT = 20000  # corps tronqué au-delà — une alerte n'a pas besoin de plus
FETCH_LIMIT = 50    # messages par relevé et par connecteur


def _decode_header(value):
    if not value:
        return ""
    try:
        return str(email.header.make_header(email.header.decode_header(value)))
    except (email.errors.HeaderParseError, UnicodeDecodeError, LookupError):
        return value


def _strip_html(html):
    text = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    import html as _html
    return re.sub(r"\s+", " ", _html.unescape(text)).strip()


def _body_of(msg):
    """Corps texte : text/plain préféré, text/html décapé sinon."""
    plain, html = None, None
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        ctype = part.get_content_type()
        if ctype not in ("text/plain", "text/html"):
            continue
        try:
            payload = part.get_payload(decode=True)
            charset = part.get_content_charset() or "utf-8"
            text = payload.decode(charset, "replace") if payload else ""
        except (LookupError, UnicodeDecodeError):
            continue
        if ctype == "text/plain" and plain is None:
            plain = text
        elif ctype == "text/html" and html is None:
            html = text
    body = plain if plain is not None else (_strip_html(html) if html else "")
    return (body or "")[:BODY_LIMIT]


def fetch_unseen(cfg, limit=FETCH_LIMIT):
    """Messages non lus d'une boîte. cfg : {host, port, tls, username,
    password, folder}. Retourne (messages, erreur) — jamais d'exception
    vers l'appelant : une boîte injoignable est un état, pas un crash.
    messages : [{uid, message_id, from_addr, subject, date, body}]."""
    conn = None
    try:
        if cfg.get("tls", True):
            conn = imaplib.IMAP4_SSL(cfg["host"], int(cfg.get("port") or 993), timeout=30)
        else:
            conn = imaplib.IMAP4(cfg["host"], int(cfg.get("port") or 143), timeout=30)
            conn.starttls()
        conn.login(cfg["username"], cfg["password"])
        conn.select(cfg.get("folder") or "INBOX", readonly=False)
        _, data = conn.search(None, "UNSEEN")
        ids = (data[0] or b"").split()[-limit:]
        messages = []
        for num in ids:
            _, fetched = conn.fetch(num, "(UID RFC822)")
            raw = fetched[0][1] if fetched and fetched[0] else None
            if not raw:
                continue
            msg = email.message_from_bytes(raw)
            uid = ""
            m = re.search(rb"UID (\d+)", fetched[0][0] if isinstance(fetched[0][0], bytes) else b"")
            if m:
                uid = m.group(1).decode()
            messages.append({
                "uid": uid or num.decode(),
                "message_id": (msg.get("Message-ID") or "").strip(),
                "from_addr": _decode_header(msg.get("From")),
                "subject": _decode_header(msg.get("Subject")),
                "date": msg.get("Date") or "",
                "body": _body_of(msg),
                "_num": num,  # interne : marquage lu après prise en charge
            })
        return messages, None
    except (imaplib.IMAP4.error, OSError) as exc:
        return [], str(exc)[:300]
    finally:
        if conn is not None:
            try:
                conn.logout()
            except Exception:
                pass


def mark_seen(cfg, nums):
    """Marque lus les messages pris en charge (STORE +FLAGS \\Seen).
    Séparé de fetch_unseen : appelé APRÈS routage réussi."""
    conn = None
    try:
        if cfg.get("tls", True):
            conn = imaplib.IMAP4_SSL(cfg["host"], int(cfg.get("port") or 993), timeout=30)
        else:
            conn = imaplib.IMAP4(cfg["host"], int(cfg.get("port") or 143), timeout=30)
            conn.starttls()
        conn.login(cfg["username"], cfg["password"])
        conn.select(cfg.get("folder") or "INBOX", readonly=False)
        for num in nums:
            conn.store(num, "+FLAGS", "\\Seen")
        return None
    except (imaplib.IMAP4.error, OSError) as exc:
        return str(exc)[:300]
    finally:
        if conn is not None:
            try:
                conn.logout()
            except Exception:
                pass
