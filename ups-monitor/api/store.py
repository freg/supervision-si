"""
Stockage de la tuile UPS (livraison #415) -- SQLite, même motif que
netprobe/store.py : `ensure_schema` idempotent, `PRAGMA foreign_keys = ON`,
paramètres liés, jamais de valeur utilisateur interpolée.

Deux tables :
  ups_devices  -- la liste « onduleurs / site / IP / user / password » de
                 la demande, plus la fréquence de relevé propre à chaque
                 onduleur (vide = valeur globale) et l'état du dernier
                 relevé (dénormalisé pour l'écran de liste, jamais recalculé
                 depuis l'archive à chaque affichage) ;
  ups_readings -- l'ARCHIVE : un relevé par requête, réussie ou non, avec la
                 fiche complète (JSON) et quelques colonnes extraites pour
                 la timeline et les tris (état global, tension, charge,
                 batterie). On archive aussi les échecs : « injoignable
                 depuis 3 h » est une information de supervision.

Le mot de passe est stocké chiffré (credential_crypto, si
UPS_CRED_PASSPHRASE / UPS_CRED_SALT sont fournis) ou en clair sinon --
jamais renvoyé par l'API (`has_password` et `password_encrypted` seulement).
"""
import json
import sqlite3
import time

import credential_crypto

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS ups_devices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    site TEXT NOT NULL DEFAULT '',
    host TEXT NOT NULL,
    scheme TEXT NOT NULL DEFAULT 'http',
    path TEXT NOT NULL DEFAULT '/index.htm',
    username TEXT NOT NULL DEFAULT '',
    password TEXT NOT NULL DEFAULT '',
    poll_interval_seconds INTEGER,
    enabled INTEGER NOT NULL DEFAULT 1,
    notes TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_polled_at TEXT,
    last_ok INTEGER,
    last_state TEXT,
    last_error TEXT,
    last_summary TEXT
);

CREATE TABLE IF NOT EXISTS ups_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ups_id INTEGER NOT NULL REFERENCES ups_devices(id) ON DELETE CASCADE,
    polled_at TEXT NOT NULL,
    ok INTEGER NOT NULL,
    error TEXT,
    state TEXT,
    state_reasons TEXT,
    system_time TEXT,
    fields_json TEXT NOT NULL DEFAULT '{}',
    sections_json TEXT NOT NULL DEFAULT '[]',
    input_voltage REAL,
    output_voltage REAL,
    output_load REAL,
    battery_capacity REAL,
    duration_ms INTEGER,
    resolved_path TEXT
);
CREATE INDEX IF NOT EXISTS idx_ups_readings_ups_time ON ups_readings(ups_id, polled_at);

-- Alertes (livraison #433) : une ligne par condition ouverte, fermée
-- quand la condition disparaît ; acquittement humain = notifications
-- coupées tant qu'elle dure.
CREATE TABLE IF NOT EXISTS ups_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ups_id INTEGER NOT NULL REFERENCES ups_devices(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    severity TEXT NOT NULL,
    message TEXT NOT NULL,
    details_json TEXT NOT NULL DEFAULT '{}',
    opened_at TEXT NOT NULL,
    closed_at TEXT,
    acked_at TEXT,
    acked_by TEXT,
    notified_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_ups_alerts_open ON ups_alerts(ups_id, closed_at);
"""

# Colonnes ajoutées après la première livraison : ALTER TABLE tolérant,
# même motif que les autres modules (ensure_xxx_column).
EXTRA_COLUMNS = (
    ("ups_readings", "resolved_path", "TEXT"),
    ("ups_devices", "last_resolved_path", "TEXT"),
    # #433 : seuils (JSON), nombre d'échecs avant « injoignable », notifications
    ("ups_devices", "thresholds", "TEXT"),
    ("ups_devices", "unreachable_after", "INTEGER"),
    ("ups_devices", "notify", "INTEGER"),
    # #434 : méthode de relevé (http | snmp), communauté SNMP (protégée comme le mot de passe), port
    ("ups_devices", "method", "TEXT"),
    ("ups_devices", "snmp_community", "TEXT"),
    ("ups_devices", "snmp_port", "INTEGER"),
    # #435 : pages supplémentaires de la carte (JSON), dernier contrôle de dérive
    ("ups_devices", "extra_pages", "TEXT"),
    ("ups_devices", "last_drift_check", "TEXT"),
    ("ups_readings", "extra_errors", "TEXT"),
)

DEVICE_COLUMNS = ("name", "site", "host", "scheme", "path", "username", "password", "poll_interval_seconds", "enabled", "notes",
                  "thresholds", "unreachable_after", "notify", "method", "snmp_community", "snmp_port", "extra_pages")


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_connection(db_path):
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def ensure_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        for table, column, ctype in EXTRA_COLUMNS:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ctype}")
                conn.commit()
            except sqlite3.OperationalError:
                conn.rollback()  # déjà présente
    finally:
        conn.close()


def _public(row):
    """Ligne d'onduleur SANS le mot de passe (jamais renvoyé)."""
    d = dict(row)
    stored = d.pop("password", "")
    d["has_password"] = bool(stored)
    d["password_encrypted"] = credential_crypto.is_protected(stored)
    d["enabled"] = bool(d["enabled"])
    d["last_ok"] = None if d["last_ok"] is None else bool(d["last_ok"])
    try:
        d["thresholds"] = json.loads(d.get("thresholds") or "{}")
    except (TypeError, ValueError):
        d["thresholds"] = {}
    d["unreachable_after"] = d.get("unreachable_after") or 3
    d["notify"] = bool(d.get("notify", 1) if d.get("notify") is not None else 1)
    community = d.pop("snmp_community", "") or ""
    d["has_snmp_community"] = bool(community)
    try:
        d["extra_pages"] = json.loads(d.get("extra_pages") or "[]")
    except (TypeError, ValueError):
        d["extra_pages"] = []
    d["method"] = d.get("method") or "http"
    d["snmp_port"] = d.get("snmp_port") or 161
    return d


def list_devices(db_path, include_secret=False):
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM ups_devices ORDER BY site, name").fetchall()
        return [_with_secret(r) if include_secret else _public(r) for r in rows]
    finally:
        conn.close()


def get_device(db_path, ups_id, include_secret=False):
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM ups_devices WHERE id = ?", [ups_id]).fetchone()
        if row is None:
            return None
        return _with_secret(row) if include_secret else _public(row)
    finally:
        conn.close()


def _with_secret(row):
    """Ligne AVEC le mot de passe en clair (usage interne : automate).
    Un jeton indéchiffrable devient `password_error`, le mot de passe
    vide -- le relevé échouera avec ce message, jamais en silence."""
    d = dict(row)
    try:
        d["password"] = credential_crypto.reveal(d.get("password") or "")
        d["password_error"] = None
    except ValueError as exc:
        d["password"] = ""
        d["password_error"] = str(exc)
    try:
        d["snmp_community"] = credential_crypto.reveal(d.get("snmp_community") or "")
    except ValueError as exc:
        d["snmp_community"] = ""
        d["password_error"] = d["password_error"] or str(exc)
    d["method"] = d.get("method") or "http"
    d["snmp_port"] = d.get("snmp_port") or 161
    try:
        d["extra_pages"] = json.loads(d.get("extra_pages") or "[]")
    except (TypeError, ValueError):
        d["extra_pages"] = []
    return d


def _normalize_device(data, existing=None):
    """Validation + normalisation d'un onduleur (création ou mise à jour).
    Renvoie (valeurs, erreur)."""
    base = dict(existing or {})
    for col in DEVICE_COLUMNS:
        if col in data:
            base[col] = data[col]
    name = str(base.get("name") or "").strip()
    host = str(base.get("host") or "").strip()
    if not name:
        return None, "'name' requis"
    if not host:
        return None, "'host' requis (IP ou nom)"
    if any(c in host for c in "/@ \t"):
        return None, "'host' : IP ou nom seul, sans schéma ni chemin"
    scheme = str(base.get("scheme") or "http").strip().lower()
    if scheme not in ("http", "https"):
        return None, "'scheme' : http ou https"
    path = str(base.get("path") or "/index.htm").strip()
    if not path.startswith("/"):
        path = "/" + path
    interval = base.get("poll_interval_seconds")
    if interval in ("", None):
        interval = None
    else:
        try:
            interval = int(interval)
        except (TypeError, ValueError):
            return None, "'poll_interval_seconds' : entier (secondes) ou vide"
        if interval < 30:
            return None, "'poll_interval_seconds' : 30 s minimum -- la page se rafraîchit elle-même toutes les 30 s"
    enabled = base.get("enabled", True)
    enabled = 1 if (enabled is True or str(enabled).lower() in ("1", "true", "yes", "on")) else 0
    # #433 : seuils, injoignable après N échecs, notifications
    import alerts as _alerts  # noqa: PLC0415
    thresholds, err = _alerts.validate_thresholds(base.get("thresholds"))
    if err:
        return None, err
    after = base.get("unreachable_after")
    if after in ("", None):
        after = 3
    else:
        try:
            after = int(after)
        except (TypeError, ValueError):
            return None, "'unreachable_after' : entier (nombre d'échecs consécutifs) ou vide"
        if after < 1:
            return None, "'unreachable_after' : 1 minimum"
    notify = base.get("notify")
    if notify is None:
        notify = True
    notify = 1 if (notify is True or notify == 1 or str(notify).lower() in ("1", "true", "yes", "on")) else 0
    method = str(base.get("method") or "http").strip().lower()
    if method not in ("http", "snmp"):
        return None, "'method' : http ou snmp"
    snmp_port = base.get("snmp_port")
    if snmp_port in ("", None):
        snmp_port = 161
    else:
        try:
            snmp_port = int(snmp_port)
        except (TypeError, ValueError):
            return None, "'snmp_port' : entier"
    extra = base.get("extra_pages")
    if isinstance(extra, str):
        try:
            extra = json.loads(extra) if extra.strip().startswith("[") else [p.strip() for p in extra.split(",")]
        except ValueError:
            return None, "'extra_pages' : liste de chemins"
    extra = [str(p).strip() for p in (extra or []) if str(p).strip()]
    for pth in extra:
        if not pth.startswith("/") or any(c in pth for c in " \t"):
            return None, "'extra_pages' : chemins commençant par / (ex. /info_battery.htm)"
    if len(extra) > 8:
        return None, "'extra_pages' : 8 pages au plus"
    return {
        "extra_pages": json.dumps(extra) if extra else None,
        "method": method,
        "snmp_community": str(base.get("snmp_community") or ""),
        "snmp_port": snmp_port,
        "thresholds": json.dumps(thresholds, ensure_ascii=False) if thresholds else None,
        "unreachable_after": after,
        "notify": notify,
        "name": name,
        "site": str(base.get("site") or "").strip(),
        "host": host,
        "scheme": scheme,
        "path": path,
        "username": str(base.get("username") or ""),
        "password": str(base.get("password") or ""),
        "poll_interval_seconds": interval,
        "enabled": enabled,
        "notes": str(base.get("notes") or ""),
    }, None


def create_device(db_path, data):
    values, err = _normalize_device(data)
    if err:
        return None, err
    now = now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO ups_devices (name, site, host, scheme, path, username, password,
                                        poll_interval_seconds, enabled, notes, thresholds, unreachable_after, notify,
                                        method, snmp_community, snmp_port, extra_pages, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [values["name"], values["site"], values["host"], values["scheme"], values["path"],
             values["username"], credential_crypto.protect(values["password"]), values["poll_interval_seconds"], values["enabled"],
             values["notes"], values["thresholds"], values["unreachable_after"], values["notify"],
             values["method"], credential_crypto.protect(values["snmp_community"]), values["snmp_port"], values["extra_pages"], now, now],
        )
        conn.commit()
        return get_device(db_path, cur.lastrowid), None
    finally:
        conn.close()


def update_device(db_path, ups_id, data):
    existing = get_device(db_path, ups_id, include_secret=True)
    if existing is None:
        return None, "onduleur inconnu"
    # Mot de passe : absent ou vide dans la requête = inchangé (le
    # formulaire ne le réaffiche jamais) ; pour l'effacer, envoyer
    # {"clear_password": true}.
    payload = dict(data)
    if data.get("clear_password"):
        payload["password"] = ""
    elif not data.get("password"):
        payload.pop("password", None)
    # #434 : même règle pour la communauté SNMP (absente/vide = inchangée)
    if data.get("clear_snmp_community"):
        payload["snmp_community"] = ""
    elif not data.get("snmp_community"):
        payload.pop("snmp_community", None)
    values, err = _normalize_device(payload, existing)
    if err:
        return None, err
    # Le mot de passe repasse par protect() à chaque modification : un
    # ancien mot de passe en clair est chiffré dès que la configuration
    # existe, sans étape de migration séparée.
    values["password"] = credential_crypto.protect(values["password"])
    values["snmp_community"] = credential_crypto.protect(values["snmp_community"])
    conn = get_connection(db_path)
    if existing.get("password_error") and "password" not in payload:
        # Jeton indéchiffrable (phrase de passe absente ou changée) et pas
        # de nouveau mot de passe : on garde le jeton TEL QUEL plutôt que
        # de l'écraser par du vide -- il redeviendra lisible si la phrase
        # de passe revient.
        raw = conn.execute("SELECT password FROM ups_devices WHERE id = ?", [ups_id]).fetchone()
        values["password"] = raw["password"] if raw else ""
    try:
        conn.execute(
            """UPDATE ups_devices SET name = ?, site = ?, host = ?, scheme = ?, path = ?, username = ?, password = ?,
                                     poll_interval_seconds = ?, enabled = ?, notes = ?, thresholds = ?, unreachable_after = ?, notify = ?,
                                     method = ?, snmp_community = ?, snmp_port = ?, extra_pages = ?, updated_at = ?
               WHERE id = ?""",
            [values["name"], values["site"], values["host"], values["scheme"], values["path"],
             values["username"], values["password"], values["poll_interval_seconds"], values["enabled"],
             values["notes"], values["thresholds"], values["unreachable_after"], values["notify"],
             values["method"], values["snmp_community"], values["snmp_port"], values["extra_pages"], now_iso(), ups_id],
        )
        conn.commit()
    finally:
        conn.close()
    return get_device(db_path, ups_id), None


def delete_device(db_path, ups_id):
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM ups_devices WHERE id = ?", [ups_id])
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def record_reading(db_path, ups_id, result):
    """Archive un relevé (réussi ou non) et met à jour l'état dénormalisé
    de l'onduleur. `result` = sortie de poller.poll_device."""
    fields = result.get("fields") or {}

    def num(key):
        entry = fields.get(key)
        return entry.get("number") if entry else None

    polled_at = result.get("polled_at") or now_iso()
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            """INSERT INTO ups_readings (ups_id, polled_at, ok, error, state, state_reasons, system_time,
                                         fields_json, sections_json, input_voltage, output_voltage,
                                         output_load, battery_capacity, duration_ms, resolved_path)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [ups_id, polled_at, 1 if result.get("ok") else 0, result.get("error"), result.get("state"),
             json.dumps(result.get("state_reasons") or [], ensure_ascii=False), result.get("system_time"),
             json.dumps(fields, ensure_ascii=False), json.dumps(result.get("sections") or [], ensure_ascii=False),
             num("input_voltage"), num("output_voltage"), num("output_load"), num("battery_capacity"),
             result.get("duration_ms"), result.get("resolved_path")],
        )
        # last_resolved_path : page qui a fourni la dernière fiche (#416) --
        # conservé tel quel sur un échec, pour que l'écran puisse dire
        # « la dernière fiche venait de /status.htm ».
        if result.get("extra_errors"):
            conn.execute("UPDATE ups_readings SET extra_errors = ? WHERE id = ?", [json.dumps(result["extra_errors"], ensure_ascii=False), cur.lastrowid])
        conn.execute(
            """UPDATE ups_devices SET last_polled_at = ?, last_ok = ?, last_state = ?, last_error = ?, last_summary = ?,
                                     last_resolved_path = COALESCE(?, last_resolved_path)
               WHERE id = ?""",
            [polled_at, 1 if result.get("ok") else 0, result.get("state"), result.get("error"),
             json.dumps(result.get("summary") or {}, ensure_ascii=False), result.get("resolved_path"), ups_id],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def _reading_row(row, with_fields):
    d = dict(row)
    d["ok"] = bool(d["ok"])
    d["state_reasons"] = json.loads(d.get("state_reasons") or "[]")
    try:
        d["extra_errors"] = json.loads(d.get("extra_errors") or "[]")
    except (TypeError, ValueError):
        d["extra_errors"] = []
    if with_fields:
        d["fields"] = json.loads(d.pop("fields_json") or "{}")
        d["sections"] = json.loads(d.pop("sections_json") or "[]")
    else:
        d.pop("fields_json", None)
        d.pop("sections_json", None)
    return d


def latest_reading(db_path, ups_id):
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM ups_readings WHERE ups_id = ? ORDER BY polled_at DESC, id DESC LIMIT 1", [ups_id]
        ).fetchone()
        return _reading_row(row, True) if row else None
    finally:
        conn.close()


def latest_ok_reading(db_path, ups_id):
    """Dernière fiche COMPLÈTE (relevé réussi) -- ce que l'écran affiche
    quand le dernier relevé a échoué : la dernière fiche connue, datée."""
    conn = get_connection(db_path)
    try:
        row = conn.execute(
            "SELECT * FROM ups_readings WHERE ups_id = ? AND ok = 1 ORDER BY polled_at DESC, id DESC LIMIT 1", [ups_id]
        ).fetchone()
        return _reading_row(row, True) if row else None
    finally:
        conn.close()


def list_readings(db_path, ups_id, start=None, end=None, limit=500, with_fields=False):
    """Timeline : relevés d'un onduleur, du plus ancien au plus récent,
    bornés par [start, end] (ISO) et limités (les `limit` plus RÉCENTS
    si la fenêtre en contient davantage)."""
    limit = max(1, min(int(limit or 500), 5000))
    clauses = ["ups_id = ?"]
    params = [ups_id]
    if start:
        clauses.append("polled_at >= ?")
        params.append(start)
    if end:
        clauses.append("polled_at <= ?")
        params.append(end)
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            f"SELECT * FROM ups_readings WHERE {' AND '.join(clauses)} ORDER BY polled_at DESC, id DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        return [_reading_row(r, with_fields) for r in reversed(rows)]
    finally:
        conn.close()


def field_series(db_path, ups_id, key, start=None, end=None, limit=2000):
    """Série (polled_at, number, value) d'un champ, relevés réussis
    seulement -- un échec n'a pas de valeur, il est visible dans la
    timeline générale, jamais interpolé ici."""
    readings = list_readings(db_path, ups_id, start, end, limit, with_fields=True)
    series = []
    for r in readings:
        if not r["ok"]:
            continue
        entry = r["fields"].get(key)
        if not entry:
            continue
        series.append({"at": r["polled_at"], "number": entry.get("number"), "value": entry.get("value"), "unit": entry.get("unit")})
    return series


def purge_readings(db_path, older_than_iso):
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM ups_readings WHERE polled_at < ?", [older_than_iso])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def counts(db_path):
    conn = get_connection(db_path)
    try:
        devices = conn.execute("SELECT COUNT(*) AS n FROM ups_devices").fetchone()["n"]
        enabled = conn.execute("SELECT COUNT(*) AS n FROM ups_devices WHERE enabled = 1").fetchone()["n"]
        readings = conn.execute("SELECT COUNT(*) AS n FROM ups_readings").fetchone()["n"]
        alarms = conn.execute("SELECT COUNT(*) AS n FROM ups_devices WHERE last_state = 'alarm'").fetchone()["n"]
        down = conn.execute("SELECT COUNT(*) AS n FROM ups_devices WHERE last_ok = 0").fetchone()["n"]
        return {"devices": devices, "enabled": enabled, "readings": readings, "alarms": alarms, "unreachable": down}
    finally:
        conn.close()


# ---- Alertes (livraison #433) --------------------------------------------------

def _alert_row(row):
    d = dict(row)
    try:
        d["details"] = json.loads(d.pop("details_json") or "{}")
    except (TypeError, ValueError):
        d["details"] = {}
    try:
        d["notified"] = json.loads(d.pop("notified_json") or "null")
    except (TypeError, ValueError):
        d["notified"] = None
    return d


def open_alerts(db_path, ups_id):
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT * FROM ups_alerts WHERE ups_id = ? AND closed_at IS NULL", [ups_id]).fetchall()
        return {r["kind"]: _alert_row(r) for r in rows}
    finally:
        conn.close()


def open_alert(db_path, ups_id, alert, at=None):
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO ups_alerts (ups_id, kind, severity, message, details_json, opened_at) VALUES (?, ?, ?, ?, ?, ?)",
            [ups_id, alert["kind"], alert["severity"], alert["message"], json.dumps(alert.get("details") or {}, ensure_ascii=False), at or now_iso()],
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def close_alert(db_path, ups_id, kind, at=None):
    conn = get_connection(db_path)
    try:
        cur = conn.execute("UPDATE ups_alerts SET closed_at = ? WHERE ups_id = ? AND kind = ? AND closed_at IS NULL", [at or now_iso(), ups_id, kind])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def ack_alert(db_path, alert_id, who=None):
    conn = get_connection(db_path)
    try:
        cur = conn.execute("UPDATE ups_alerts SET acked_at = ?, acked_by = ? WHERE id = ? AND closed_at IS NULL", [now_iso(), who, alert_id])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def mark_alert_notified(db_path, alert_id, result):
    conn = get_connection(db_path)
    try:
        conn.execute("UPDATE ups_alerts SET notified_json = ? WHERE id = ?", [json.dumps(result, ensure_ascii=False), alert_id])
        conn.commit()
    finally:
        conn.close()


def list_alerts(db_path, active_only=True, ups_id=None, limit=200):
    conn = get_connection(db_path)
    try:
        q = "SELECT a.*, d.name AS ups_name, d.site AS ups_site FROM ups_alerts a JOIN ups_devices d ON d.id = a.ups_id"
        clauses, params = [], []
        if active_only:
            clauses.append("a.closed_at IS NULL")
        if ups_id:
            clauses.append("a.ups_id = ?"); params.append(ups_id)
        if clauses:
            q += " WHERE " + " AND ".join(clauses)
        q += " ORDER BY a.closed_at IS NOT NULL, a.opened_at DESC LIMIT ?"
        params.append(limit)
        return [_alert_row(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def consecutive_failures(db_path, ups_id, limit=50):
    """Nombre de relevés en échec consécutifs, le plus récent inclus."""
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT ok FROM ups_readings WHERE ups_id = ? ORDER BY polled_at DESC, id DESC LIMIT ?", [ups_id, limit]).fetchall()
    finally:
        conn.close()
    n = 0
    for r in rows:
        if r["ok"]:
            break
        n += 1
    return n


def alert_counts(db_path):
    conn = get_connection(db_path)
    try:
        rows = conn.execute("SELECT severity, COUNT(*) AS n FROM ups_alerts WHERE closed_at IS NULL GROUP BY severity").fetchall()
        out = {"active": 0, "critical": 0, "warning": 0, "unacked": 0}
        for r in rows:
            out["active"] += r["n"]
            out[r["severity"]] = out.get(r["severity"], 0) + r["n"]
        out["unacked"] = conn.execute("SELECT COUNT(*) AS n FROM ups_alerts WHERE closed_at IS NULL AND acked_at IS NULL").fetchone()["n"]
        return out
    finally:
        conn.close()


# ---- Dérive lente (#435) -------------------------------------------------------

def field_values_between(db_path, ups_id, keys, start_iso, end_iso):
    """{clé: [nombres]} des relevés réussis entre deux dates (bornes ISO)."""
    out = {k: [] for k in keys}
    for r in list_readings(db_path, ups_id, start_iso, end_iso, limit=5000, with_fields=True):
        if not r["ok"]:
            continue
        for k in keys:
            e = (r.get("fields") or {}).get(k)
            if e and e.get("number") is not None:
                out[k].append(e["number"])
    return out


def mark_drift_checked(db_path, ups_id, at):
    conn = get_connection(db_path)
    try:
        conn.execute("UPDATE ups_devices SET last_drift_check = ? WHERE id = ?", [at, ups_id])
        conn.commit()
    finally:
        conn.close()
