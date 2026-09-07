"""
Automate de relevé des onduleurs (livraison #415) -- « un automate /
cron » de la demande. Même motif que netprobe/scheduler.py : une PASSE
testable en isolation (`run_tick`), enveloppée dans un thread de fond par
`start_background_thread` (appelée depuis app.py).

Chaque onduleur est relevé quand son intervalle (propre, sinon global --
`UPS_POLL_INTERVAL_SECONDS`, 1 h par défaut comme demandé) s'est écoulé
depuis son dernier relevé ; le tick lui-même est plus fin (60 s) pour
qu'un intervalle court soit respecté sans sur-solliciter les autres. La
décision « est-il temps ? » se prend sur `last_polled_at` EN BASE, jamais
sur une variable en mémoire : elle survit au redémarrage et au multi-
processus (gunicorn tourne ici avec UN worker, voir Dockerfile -- deux
workers ne feraient qu'un double relevé occasionnel, pas une corruption).

La requête HTTP : `http://user:password@ip/index.htm` de la demande devient
une requête GET avec authentification HTTP Basic (c'est ce que le
navigateur fait de `user:password@` -- le firmware Socomec répond en
Basic ; si une carte répondait par un formulaire, le relevé échouera
proprement avec « 0 champ », voir README). stdlib `urllib` : aucune
dépendance, délai borné, jamais de suivi de redirection vers un autre
hôte.
"""
import base64
import logging
import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import ups_parser
import store

_log = logging.getLogger("ups_monitor_poller")

DEFAULT_INTERVAL_SECONDS = int(os.environ.get("UPS_POLL_INTERVAL_SECONDS", "3600"))
TICK_SECONDS = int(os.environ.get("UPS_POLL_TICK_SECONDS", "60"))
HTTP_TIMEOUT_SECONDS = float(os.environ.get("UPS_HTTP_TIMEOUT_SECONDS", "10"))
RETENTION_DAYS = int(os.environ.get("UPS_HISTORY_RETENTION_DAYS", "365"))
MAX_BODY_BYTES = 512 * 1024


def build_url(device):
    return f"{device.get('scheme') or 'http'}://{device['host']}{device.get('path') or '/index.htm'}"


def fetch_page(url, username="", password="", timeout=HTTP_TIMEOUT_SECONDS, opener=None):
    """GET + Basic. Renvoie (html, erreur). `opener` injectable (tests)."""
    req = urllib.request.Request(url, headers={"User-Agent": "supervision-si ups-monitor/1", "Accept": "text/html"})
    if username or password:
        token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {token}")
    open_fn = opener or urllib.request.urlopen
    try:
        with open_fn(req, timeout=timeout) as resp:
            raw = resp.read(MAX_BODY_BYTES + 1)
            if len(raw) > MAX_BODY_BYTES:
                return None, "réponse trop volumineuse (> 512 Ko) -- pas une page d'état"
            charset = "iso-8859-1"
            try:
                charset = resp.headers.get_content_charset() or charset
            except AttributeError:
                pass
            try:
                return raw.decode(charset, errors="replace"), None
            except LookupError:
                return raw.decode("iso-8859-1", errors="replace"), None
    except urllib.error.HTTPError as exc:
        if exc.code == 401:
            return None, "authentification refusée (401) -- utilisateur / mot de passe"
        return None, f"HTTP {exc.code}"
    except urllib.error.URLError as exc:
        return None, f"injoignable : {exc.reason}"
    except (TimeoutError, OSError) as exc:
        return None, f"injoignable : {exc}"
    except Exception as exc:  # noqa: BLE001 -- un relevé ne doit jamais tuer l'automate
        return None, f"erreur inattendue : {exc}"


# Suivi des frames (#416) : profondeur et nombre de sous-pages bornés --
# un conteneur qui pointe sur un conteneur qui pointe sur… ne doit jamais
# faire boucler l'automate ; 1 + 6 requêtes au pire par relevé.
FRAME_MAX_DEPTH = 2
FRAME_MAX_PAGES = 6


def _same_host(base_url, target_url):
    b = urllib.parse.urlsplit(base_url)
    t = urllib.parse.urlsplit(target_url)
    return (t.scheme or b.scheme) == b.scheme and (t.netloc or b.netloc) == b.netloc


def fetch_status_page(url, username, password, opener=None):
    """Récupère la page d'état en suivant les frames si la page demandée
    n'est qu'un conteneur (#416). Renvoie (parsed, erreur, chemin_effectif,
    pages_visitées). `parsed` est la première page (en largeur d'abord) qui
    contient des champs ; sinon None avec un message qui liste les pages
    essayées -- la personne peut alors fixer le champ « Page » à la main."""
    html, err = fetch_page(url, username, password, opener=opener)
    if html is None:
        return None, err, None, [url]
    parsed = ups_parser.parse_ups_page(html)
    if parsed["field_count"] > 0:
        return parsed, None, urllib.parse.urlsplit(url).path, [url]

    visited = [url]
    queue = [(urllib.parse.urljoin(url, src), 1) for src in ups_parser.extract_frame_sources(html)]
    titles = [parsed["title"] or "sans titre"]
    while queue and len(visited) <= FRAME_MAX_PAGES:
        sub_url, depth = queue.pop(0)
        if sub_url in visited or not _same_host(url, sub_url):
            continue
        visited.append(sub_url)
        sub_html, sub_err = fetch_page(sub_url, username, password, opener=opener)
        if sub_html is None:
            titles.append(f"{urllib.parse.urlsplit(sub_url).path} : {sub_err}")
            continue
        sub = ups_parser.parse_ups_page(sub_html)
        if sub["field_count"] > 0:
            return sub, None, urllib.parse.urlsplit(sub_url).path, visited
        titles.append(f"{urllib.parse.urlsplit(sub_url).path} : {sub['title'] or 'sans titre'}")
        if depth < FRAME_MAX_DEPTH:
            queue.extend((urllib.parse.urljoin(sub_url, s), depth + 1) for s in ups_parser.extract_frame_sources(sub_html))
    tried = " ; ".join(titles)
    if len(visited) > 1:
        return None, f"aucun champ reconnu dans la page ni dans ses {len(visited) - 1} frame(s) ({tried}) -- fixer « Page » sur la page d'état", None, visited
    return None, f"page reçue mais aucun champ reconnu (titre : {parsed['title'] or 'aucun'}) -- chemin ou authentification ?", None, visited


def poll_device(device, opener=None, now_iso=None):
    """Un relevé complet : requête (frames suivies au besoin), parse, état.
    Renvoie le dict archivé par store.record_reading -- TOUJOURS, réussi
    ou non. `resolved_path` = page qui a réellement fourni la fiche."""
    started = time.monotonic()
    url = build_url(device)
    result = {
        "polled_at": now_iso or store.now_iso(),
        "url": url,
        "ok": False,
        "error": None,
        "state": None,
        "state_reasons": [],
        "system_time": None,
        "fields": {},
        "sections": [],
        "summary": {},
        "duration_ms": None,
        "resolved_path": None,
        "pages_visited": 0,
    }
    if device.get("password_error"):
        parsed, err, resolved, visited = None, device["password_error"], None, []
    else:
        parsed, err, resolved, visited = fetch_status_page(
            url, device.get("username") or "", device.get("password") or "", opener=opener,
        )
    result["pages_visited"] = len(visited)
    result["resolved_path"] = resolved
    if parsed is None:
        result["error"] = err
    else:
        state, reasons = ups_parser.derive_state(parsed["fields"])
        result.update({
            "ok": True,
            "error": None,
            "state": state,
            "state_reasons": reasons,
            "system_time": parsed["system_time"],
            "fields": parsed["fields"],
            "sections": parsed["sections"],
            "summary": {
                k: parsed["fields"][k]["value"]
                for k in ("model", "communication", "output_source", "battery", "input_voltage", "output_voltage",
                          "output_load", "battery_capacity")
                if k in parsed["fields"]
            },
        })
    result["duration_ms"] = int((time.monotonic() - started) * 1000)
    return result


def _iso_to_ts(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


def is_due(device, now_ts, default_interval=None):
    interval = device.get("poll_interval_seconds") or default_interval or DEFAULT_INTERVAL_SECONDS
    last = _iso_to_ts(device.get("last_polled_at"))
    return last is None or (now_ts - last) >= interval


def run_tick(db_path, now_ts=None, opener=None, default_interval=None, force_ids=None):
    """Une passe : relève chaque onduleur activé dont l'intervalle est
    écoulé (ou listé dans `force_ids`). Renvoie des compteurs."""
    if now_ts is None:
        now_ts = time.time()
    force = set(force_ids or [])
    checked = polled = skipped = failed = 0
    for device in store.list_devices(db_path, include_secret=True):
        checked += 1
        if device["id"] not in force and (not device["enabled"] or not is_due(device, now_ts, default_interval)):
            skipped += 1
            continue
        # Horodatage du relevé = l'instant de décision (injectable) : la
        # prochaine échéance se calcule sur la même horloge.
        result = poll_device(device, opener=opener, now_iso=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts)))
        store.record_reading(db_path, device["id"], result)
        polled += 1
        if not result["ok"]:
            failed += 1
            _log.warning("ups-monitor : %s (%s) -- %s", device["name"], device["host"], result["error"])
    return {"checked": checked, "polled": polled, "skipped": skipped, "failed": failed}


def purge_tick(db_path, now_ts=None):
    if RETENTION_DAYS <= 0:
        return 0
    now_ts = now_ts or time.time()
    cutoff = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now_ts - RETENTION_DAYS * 86400))
    return store.purge_readings(db_path, cutoff)


_thread = None
_lock = threading.Lock()


def start_background_thread(db_path):
    """Boucle de fond, démarrée une fois par processus. Désactivable par
    UPS_POLL_ENABLED=false (tests, environnement sans réseau)."""
    global _thread
    if os.environ.get("UPS_POLL_ENABLED", "true").strip().lower() == "false":
        _log.info("ups-monitor : automate désactivé (UPS_POLL_ENABLED=false)")
        return None
    with _lock:
        if _thread is not None:
            return _thread

        def loop():
            last_purge = 0
            while True:
                try:
                    run_tick(db_path)
                    if time.time() - last_purge > 6 * 3600:
                        purge_tick(db_path)
                        last_purge = time.time()
                except Exception:  # noqa: BLE001
                    _log.exception("ups-monitor : erreur dans la boucle de relevé")
                time.sleep(TICK_SECONDS)

        _thread = threading.Thread(target=loop, name="ups-poller", daemon=True)
        _thread.start()
        return _thread
