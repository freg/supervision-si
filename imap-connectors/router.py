# -*- coding: utf-8 -*-
"""Routage des messages interprétés vers les API cibles (#489).

- tickets      → POST <tickets_api>/tickets (source_type « imap »,
                 source_nom = nom du connecteur — même convention que
                 les tickets sourcés mikrotik de la #486) ;
- projeqtor    → POST <bridge>/demande/demandes (contrat du formulaire
                 public « suivi », livraison #484) ;
- zenoss       → INSERT dans la base pixel-grid (events + type_meta,
                 type « alerte_zenoss_email » — la liaison directe
                 Zenoss ↔ pixel-grid que le hors-ligne attendait) ;
- sms          → journal du connecteur (la vue hub les affiche ; une
                 notification temps réel reste à brancher) ;
- notification → journal du connecteur.

Chaque livraison est journalisée (deliveries) avec son statut — le
« log » demandé. Les fonctions HTTP sont injectables : les tests ne
font aucun réseau."""
import json
import os
import sqlite3
import time

import requests

TICKETS_API_URL = os.environ.get("TICKETS_API_URL", "http://tickets-api:5000")
PROJEQTOR_BRIDGE_URL = os.environ.get("PROJEQTOR_BRIDGE_URL", "http://projeqtor-bridge:5000")
# pixel-grid : deux backends comme pixel-grid-api (sqlite = fichier
# partagé par volume ; postgres = service pixel-grid-postgres). Le
# déploiement de référence utilise postgres (.env PIXEL_GRID_BACKEND).
PIXEL_GRID_BACKEND = os.environ.get("PIXEL_GRID_BACKEND", "sqlite").strip().lower()
PIXEL_GRID_DB_PATH = os.environ.get("PIXEL_GRID_DB_PATH", "")  # sqlite uniquement
HTTP_TIMEOUT = 15

# Config du type pixel-grid Zenoss — copie de
# pixel-grid/data-generator/configs/alerte_zenoss_email.json (les deux
# sources, hors ligne et live, alimentent le MÊME type).
ZENOSS_TYPE_META = {
    "nom": "alertes_zenoss_email",
    "type": "alerte_zenoss_email",
    "kind": "integer_enum",
    "description": "Alertes Zenoss — e-mails de notification (live via imap-connectors #489, ou hors ligne via parse_zenoss_emails.py). 1 = alerte active, 0 = résolution (clear).",
    "values": {"0": "resolu", "1": "alerte_active"},
    "seuil_taux_attention": 0.05,
    "seuil_taux_alerte": 0.25,
}

PIXEL_SCHEMA = """
CREATE TABLE IF NOT EXISTS events (ts INTEGER, valeur REAL, nom TEXT, type TEXT, data TEXT);
CREATE INDEX IF NOT EXISTS idx_events_type_ts ON events(type, ts);
CREATE TABLE IF NOT EXISTS type_meta (type TEXT PRIMARY KEY, kind TEXT, config_json TEXT);
"""


def _post(url, payload, post=None):
    post = post or requests.post
    try:
        r = post(url, json=payload, timeout=HTTP_TIMEOUT)
        if r.status_code >= 400:
            return False, "HTTP %s : %s" % (r.status_code, r.text[:200])
        try:
            body = r.json()
        except ValueError:
            body = {}
        ident = body.get("id") or (body.get("projeqtor") or {}).get("id")
        return True, "id %s" % ident if ident else "ok"
    except requests.RequestException as exc:
        return False, str(exc)[:300]


def deliver_ticket(connector, parsed, post=None):
    ticket = dict(parsed["ticket"])
    ticket["source_type"] = "imap"
    ticket["source_nom"] = connector["name"]
    if connector.get("default_type_id"):
        ticket["type_id"] = connector["default_type_id"]
    if connector.get("default_level_id"):
        ticket["level_id"] = connector["default_level_id"]
    return _post("%s/tickets" % TICKETS_API_URL.rstrip("/"), ticket, post)


def deliver_demande(connector, parsed, post=None):
    return _post("%s/demande/demandes" % PROJEQTOR_BRIDGE_URL.rstrip("/"), parsed["demande"], post)


def _pg_connection():
    """Backend postgres de pixel-grid (mêmes variables que
    pixel-grid-api). Import paresseux : psycopg2 n'est requis qu'en
    mode postgres."""
    import psycopg2
    return psycopg2.connect(host=os.environ.get("PGHOST", "pixel-grid-postgres"),
                            port=int(os.environ.get("PGPORT", "5432")),
                            user=os.environ.get("PGUSER", "pixelgrid"),
                            password=os.environ.get("PGPASSWORD", "pixelgrid"),
                            dbname=os.environ.get("PGDATABASE", "pixelgrid"),
                            connect_timeout=10)


def _insert_pixel_event(conn, ev, backend):
    ph = "%s" if backend == "postgres" else "?"
    cur = conn.cursor()
    cur.execute("INSERT INTO events (ts, valeur, nom, type, data) VALUES (%s,%s,%s,%s,%s)"
                % (ph, ph, ph, ph, ph), (ev["ts"], ev["valeur"], ev["nom"], ev["type"], ev["data"]))
    if backend == "postgres":
        cur.execute("INSERT INTO type_meta (type, kind, config_json) VALUES (%s,%s,%s) "
                    "ON CONFLICT (type) DO UPDATE SET kind = EXCLUDED.kind, config_json = EXCLUDED.config_json"
                    % (ph, ph, ph),
                    (ZENOSS_TYPE_META["type"], ZENOSS_TYPE_META["kind"],
                     json.dumps(ZENOSS_TYPE_META, ensure_ascii=False)))
    else:
        cur.execute("INSERT OR REPLACE INTO type_meta (type, kind, config_json) VALUES (?,?,?)",
                    (ZENOSS_TYPE_META["type"], ZENOSS_TYPE_META["kind"],
                     json.dumps(ZENOSS_TYPE_META, ensure_ascii=False)))
    conn.commit()


def deliver_zenoss(connector, parsed, db_path=None, opener=None, backend=None):
    """Écrit l'événement dans la base pixel-grid (sqlite partagée par
    volume, ou postgres conteneur-à-conteneur). Réessaie sur
    « database is locked » en sqlite — pixel-grid-api lit en parallèle."""
    backend = (backend or PIXEL_GRID_BACKEND or "sqlite").strip().lower()
    ev = parsed["zenoss_event"]
    if not ev.get("ts"):
        return False, "horodatage introuvable (ni corps ni en-tête Date)"
    if backend == "postgres":
        try:
            conn = opener() if opener else _pg_connection()
            try:
                _insert_pixel_event(conn, ev, "postgres")
            finally:
                conn.close()
            return True, "pixel-grid(pg) %s=%s @%s" % (ev["nom"], ev["valeur"], ev["ts"])
        except Exception as exc:
            return False, str(exc)[:300]
    db_path = PIXEL_GRID_DB_PATH if db_path is None else db_path
    if not db_path:
        return False, "PIXEL_GRID_DB_PATH non configuré (backend sqlite)"
    opener = opener or (lambda: sqlite3.connect(db_path, timeout=10))
    last = None
    for _ in range(3):
        try:
            conn = opener()
            try:
                conn.executescript(PIXEL_SCHEMA)
                _insert_pixel_event(conn, ev, "sqlite")
                return True, "pixel-grid %s=%s @%s" % (ev["nom"], ev["valeur"], ev["ts"])
            finally:
                conn.close()
        except sqlite3.OperationalError as exc:
            last = exc
            if "locked" in str(exc):
                time.sleep(0.5)
                continue
            break
    return False, str(last)[:300]


def deliver_stored(connector, parsed):
    """sms / notification : la prise en charge EST le journal (vue hub,
    statistiques) — toujours ok, le message est déjà en base."""
    return True, "journalisé (%s)" % parsed.get("kind", "?")


DELIVERERS = {"tickets": deliver_ticket, "projeqtor": deliver_demande,
              "zenoss": deliver_zenoss, "sms": deliver_stored, "notification": deliver_stored}


def deliver(connector, parsed, **kw):
    """Route un message interprété. Un message NON interprété n'est pas
    routé : il reste journalisé avec parsed=0 (visible dans la vue,
    compté dans les statistiques) et NON marqué lu (repris plus tard
    si l'interpréteur s'améliore)."""
    if not parsed.get("ok"):
        return [("aucune", False, "non interprété : %s" % parsed.get("summary", "?"))]
    deliverer = DELIVERERS.get(connector.get("target"))
    if deliverer is None:
        return [("aucune", False, "cible inconnue : %s" % connector.get("target"))]
    try:
        ok, detail = deliverer(connector, parsed, **kw)
    except Exception as exc:  # un routage qui lève ne casse pas le relevé
        ok, detail = False, str(exc)[:300]
    return [(connector["target"], ok, detail)]
