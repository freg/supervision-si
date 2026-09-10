# -*- coding: utf-8 -*-
"""Audit du bastion si-proxy (livraison #453) : journal structuré des
sessions (accès) et des refus (erreurs d'autorisation), + registre des
sessions actives pour l'interface de contrôle.

Chaque session enregistre : identité du client (CN du certificat en TLS
mutuel, sinon « token »), genre (`shell` / `connect`), cible, horodatages
début/fin, octets montés/descendus, issue. **Aucun jeton ni octet de
charge n'est journalisé** -- seulement des métadonnées.

Le journal est un fichier JSONL (une ligne JSON par événement), simple à
lire, à faire tourner (logrotate) et à ingérer par la supervision.
"""
import json
import os
import threading
import time


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


class Audit(object):
    """Registre des sessions actives + écriture du journal JSONL. Sûr en
    usage asyncio mono-thread ; le verrou protège seulement l'écriture
    fichier (au cas où plusieurs boucles/threads l'utiliseraient)."""

    def __init__(self, path=None, max_active=1000):
        self.path = path
        self.max_active = max_active
        self._active = {}                 # sid -> dict (session en cours)
        self._counter = {"opened": 0, "closed": 0, "refused": 0}
        self._lock = threading.Lock()

    # -- écriture journal -------------------------------------------------
    def _append(self, record):
        if not self.path:
            return
        line = json.dumps(record, separators=(",", ":"), ensure_ascii=False)
        try:
            with self._lock:
                with open(self.path, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
        except OSError:
            pass  # l'audit ne doit jamais faire échouer une session

    # -- sessions ---------------------------------------------------------
    def start(self, sid, client, kind, target=None, peer=None):
        rec = {"session": sid, "client": client, "kind": kind, "target": target,
               "peer": peer, "started": _now(), "started_mono": time.monotonic()}
        self._active[sid] = rec
        self._counter["opened"] += 1
        self._append({"event": "session-start", "at": rec["started"], "session": sid,
                      "client": client, "kind": kind, "target": target, "peer": peer})
        return rec

    def finish(self, sid, bytes_up=0, bytes_down=0, outcome="closed", error=None):
        rec = self._active.pop(sid, None)
        started = rec.get("started") if rec else None
        dur = round(time.monotonic() - rec["started_mono"], 3) if rec else None
        self._counter["closed"] += 1
        self._append({"event": "session-end", "at": _now(), "session": sid,
                      "client": (rec or {}).get("client"), "kind": (rec or {}).get("kind"),
                      "target": (rec or {}).get("target"), "started": started, "duration_s": dur,
                      "bytes_up": bytes_up, "bytes_down": bytes_down, "outcome": outcome, "error": error})

    def refused(self, client, why, kind=None, target=None, peer=None):
        self._counter["refused"] += 1
        self._append({"event": "refused", "at": _now(), "client": client, "kind": kind,
                      "target": target, "peer": peer, "reason": why})

    # -- lecture (interface de contrôle) ---------------------------------
    def active(self):
        out = []
        for sid, rec in sorted(self._active.items()):
            out.append({"session": sid, "client": rec.get("client"), "kind": rec.get("kind"),
                        "target": rec.get("target"), "peer": rec.get("peer"), "started": rec.get("started"),
                        "duration_s": round(time.monotonic() - rec["started_mono"], 1)})
        return out

    def counters(self):
        return dict(self._counter, active=len(self._active))

    def recent(self, limit=100, max_bytes=131072):
        """Dernières lignes du journal JSONL (au plus `limit`), en lisant la
        fin du fichier (borné par `max_bytes`)."""
        if not self.path or not os.path.exists(self.path):
            return []
        try:
            size = os.path.getsize(self.path)
            with open(self.path, "rb") as fh:
                if size > max_bytes:
                    fh.seek(size - max_bytes)
                    fh.readline()  # jette la ligne partielle
                data = fh.read()
        except OSError:
            return []
        out = []
        for raw in data.decode("utf-8", "replace").splitlines():
            raw = raw.strip()
            if not raw:
                continue
            try:
                out.append(json.loads(raw))
            except ValueError:
                continue
        return out[-limit:]


def client_label(cn, role="client"):
    """Identité journalisée : le CN du certificat (TLS mutuel) sinon un
    libellé générique -- jamais le jeton."""
    return ("cn:%s" % cn) if cn else ("token:%s" % role)
