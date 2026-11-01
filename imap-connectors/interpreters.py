# -*- coding: utf-8 -*-
"""Interpréteurs de messages des connecteurs IMAP (livraison #489).

Demandé : « un gestionnaire de connecteur imap chacun sur une adresse
de réception pour plusieurs api : demandes SAV/Tickets/ProjeQTor,
alertes supervision Zenoss et autres, SMS entrants sur les passerelles
sms, notifications diverses ».

Chaque connecteur a une CIBLE (target) ; l'interpréteur transforme un
message (sujet, expéditeur, date, corps texte) en structure exploitée
par router.py :

- zenoss   : alerte/résolution Zenoss (template de notification
             standard — généralisation LIVE de
             pixel-grid/data-generator/parse_zenoss_emails.py, qui
             reste l'outil HORS LIGNE sur export Thunderbird) ;
- sms      : e-mail de passerelle SMS (expéditeur = n° ou sujet) ;
- tickets  : demande SAV → ticket du hub ;
- projeqtor: demande → pont « suivi » (champs sujet/demandeur/…) ;
- notification : stockage générique.

Fonctions PURES — testées dans tests/test_interpreters.py."""
import json
import re
from datetime import datetime, timezone

# Sujet Zenoss : « [Site A] clear: <équipement> <message> » ou
# « [Site A] <équipement> <message> » — l'étiquette de site est
# quelconque (le template de la personne utilise [Site A]).
ZENOSS_SUBJECT_RE = re.compile(r"^\[[^\]]+\]\s*(?P<clear>clear:\s*)?(?P<device>\S+)\s*(?P<msg>.*)$", re.IGNORECASE)

# Corps Zenoss — mêmes formes que le parseur hors ligne, adaptées à UN
# message (pas d'agrégation multi-messages d'un export Thunderbird).
ZENOSS_CLEARED_RE = re.compile(
    r"Event Cleared At:\s*(?P<cleared_at>[\d/:. ]+?)\s+"
    r"Alert generated at\s*(?P<alert_at>[\d/:. ]+?)\s+"
    r"Clear Message\s*:\s*(?P<clear_msg>.+?)\s+"
    r"Message\s*:\s*(?P<msg>.+?)\s+"
    r"Localisation\s*:\s*(?P<loc>.*?)\s+"
    r"Composants\s*:\s*(?P<comp>.*?)"
    r"(?:\s*Severite\s*:\s*(?P<sev>\S+))?\s*$",
    re.DOTALL,
)
ZENOSS_ACTIVE_RE = re.compile(
    r"Alert generated at\s*(?P<alert_at>[\d/:. ]+?)\s+"
    r"Equipement\s*:\s*(?P<equip>.+?)\s+"
    r"Message\s*:\s*(?P<msg>.+?)\s+"
    r"Localisation\s*:\s*(?P<loc>.*?)\s+"
    r"Composants\s*:\s*(?P<comp>.*?)"
    r"(?:\s*Severite\s*:\s*(?P<sev>\S+))?\s*$",
    re.DOTALL,
)

# Type pixel-grid alimenté par les alertes Zenoss (même type que le
# chargement hors ligne — les deux sources se côtoient dans la grille).
ZENOSS_PIXEL_TYPE = "alerte_zenoss_email"

SMS_NUMBER_RE = re.compile(r"(\+\d[\d .]{4,}|\b0[1-9](?:[ .]?\d{2}){4}\b)")


def _zenoss_ts(raw):
    """'2026/08/11 10:30:12.000' -> epoch UTC (même hypothèse que le
    parseur hors ligne : pas de fuseau dans le texte, traité UTC)."""
    try:
        dt = datetime.strptime(raw.strip(), "%Y/%m/%d %H:%M:%S.%f")
        return int(dt.replace(tzinfo=timezone.utc).timestamp())
    except ValueError:
        return None


def _msg_ts(date_str):
    """Date d'en-tête e-mail -> epoch, repli None (email.utils coûte
    un import pour rien si absente)."""
    if not date_str:
        return None
    from email.utils import parsedate_to_datetime
    try:
        dt = parsedate_to_datetime(date_str)
        return int(dt.timestamp())
    except (TypeError, ValueError):
        return None


def parse_zenoss(msg):
    """Alerte ou résolution Zenoss. Retourne fields + événement
    pixel-grid (ts, valeur 1/0, nom=équipement, data JSON)."""
    subject = msg.get("subject") or ""
    body = msg.get("body") or ""
    sm = ZENOSS_SUBJECT_RE.match(subject.strip())
    clear = bool(sm and sm.group("clear"))
    device = sm.group("device") if sm else None

    m = ZENOSS_CLEARED_RE.search(body)
    if m:
        ts = _zenoss_ts(m.group("cleared_at")) or _msg_ts(msg.get("date"))
        fields = {"device": device or "?",  # le corps « clear » ne nomme pas l'équipement : le sujet
                  "message": m.group("msg").strip(), "clear_message": m.group("clear_msg").strip(),
                  "localisation": m.group("loc").strip(), "composants": m.group("comp").strip(),
                  "severite": (m.group("sev") or "").strip() or None, "clear": True}
        return {"ok": True, "kind": "zenoss-clear",
                "summary": "résolution %s : %s" % (fields["device"], fields["clear_message"][:80]),
                "fields": fields,
                "zenoss_event": {"ts": ts, "valeur": 0, "nom": fields["device"],
                                 "type": ZENOSS_PIXEL_TYPE, "data": json.dumps(fields, ensure_ascii=False)}}
    m = ZENOSS_ACTIVE_RE.search(body)
    if m:
        ts = _zenoss_ts(m.group("alert_at")) or _msg_ts(msg.get("date"))
        fields = {"device": m.group("equip").strip() or (device or "?"),
                  "message": m.group("msg").strip(),
                  "localisation": m.group("loc").strip(), "composants": m.group("comp").strip(),
                  "severite": (m.group("sev") or "").strip() or None, "clear": False}
        return {"ok": True, "kind": "zenoss-active",
                "summary": "alerte %s : %s" % (fields["device"], fields["message"][:80]),
                "fields": fields,
                "zenoss_event": {"ts": ts, "valeur": 1, "nom": fields["device"],
                                 "type": ZENOSS_PIXEL_TYPE, "data": json.dumps(fields, ensure_ascii=False)}}
    # Corps non reconnu : conserver quand même l'alerte à partir du
    # sujet — une alerte mal parsée vaut mieux qu'une alerte perdue.
    if sm:
        ts = _msg_ts(msg.get("date"))
        fields = {"device": device, "message": (sm.group("msg") or "").strip(),
                  "clear": clear, "partial": True}
        return {"ok": True, "kind": "zenoss-partial",
                "summary": "%s %s : %s (corps non reconnu)" % ("résolution" if clear else "alerte", device, fields["message"][:60]),
                "fields": fields,
                "zenoss_event": {"ts": ts, "valeur": 0 if clear else 1, "nom": device,
                                 "type": ZENOSS_PIXEL_TYPE, "data": json.dumps(fields, ensure_ascii=False)}}
    return {"ok": False, "summary": "pas une alerte Zenoss reconnue", "fields": {}}


def parse_sms(msg):
    """E-mail de passerelle SMS : l'expéditeur du SMS est dans le sujet
    (numéro) ou l'adresse d'enveloppe ; le texte est le corps."""
    subject = (msg.get("subject") or "").strip()
    body = (msg.get("body") or "").strip()
    m = SMS_NUMBER_RE.search(subject)
    sender = m.group(1) if m else (msg.get("from_addr") or "?")
    text = body or subject
    fields = {"sender": sender, "text": text}
    return {"ok": True, "kind": "sms",
            "summary": "SMS de %s : %s" % (sender, text[:80]),
            "fields": fields, "sms": fields}


def parse_notification(msg):
    subject = (msg.get("subject") or "").strip()
    return {"ok": True, "kind": "notification", "summary": subject[:120],
            "fields": {"subject": subject, "from": msg.get("from_addr")}}


def parse_ticket(msg):
    """Demande SAV reçue par e-mail → ticket du hub."""
    subject = (msg.get("subject") or "").strip() or "(sans objet)"
    body = (msg.get("body") or "").strip()
    sender = msg.get("from_addr") or "inconnu"
    return {"ok": True, "kind": "ticket",
            "summary": "demande de %s : %s" % (sender, subject[:80]),
            "fields": {"sender": sender, "subject": subject},
            "ticket": {"subject": "[IMAP] %s" % subject[:180],
                       "description": "Reçu par e-mail de %s.\n\n%s" % (sender, body[:4000])}}


def parse_demande(msg):
    """Demande → pont « suivi »/ProjeQtOr (champs du formulaire public)."""
    subject = (msg.get("subject") or "").strip() or "(sans objet)"
    body = (msg.get("body") or "").strip()
    sender = msg.get("from_addr") or "inconnu"
    return {"ok": True, "kind": "demande",
            "summary": "demande de %s : %s" % (sender, subject[:80]),
            "fields": {"sender": sender, "subject": subject},
            "demande": {"sujet": subject[:180], "demandeur": sender, "commentaire": body[:4000]}}


PARSERS = {"zenoss": parse_zenoss, "sms": parse_sms, "notification": parse_notification,
           "tickets": parse_ticket, "projeqtor": parse_demande}

TARGETS = sorted(PARSERS)


def parse_message(target, msg):
    """Point d'entrée : target ∈ TARGETS. Une cible inconnue est une
    erreur explicite, jamais un parseur silencieux."""
    parser = PARSERS.get(target)
    if parser is None:
        return {"ok": False, "summary": "cible inconnue : %s" % target, "fields": {}}
    try:
        return parser(msg)
    except Exception as exc:  # un message tordu ne casse pas le relevé
        return {"ok": False, "summary": "interprétation échouée : %s" % exc, "fields": {}}
