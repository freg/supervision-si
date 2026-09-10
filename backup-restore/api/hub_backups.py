# -*- coding: utf-8 -*-
"""Gestionnaire des sauvegardes DU HUB (livraison #459) -- « un second
incrémental et un gestionnaire avec export ». Inspiré de ce que la personne
retient d'ARCserve (Cheyenne, NetWare, années 90) : un CATALOGUE de
sessions (chaque archive = une session, totale ou incrémentale, chaînées),
une ROTATION de type GFS (grand-père / père / fils : combien de totales
récentes, hebdomadaires, mensuelles on garde, les incrémentales suivant
leur totale), une file d'exécution (une seule sauvegarde à la fois) et la
restauration « à une date » (choisir une session de la chaîne).

Le moteur est scripts/full_backup.py (#458), lancé ici dans le conteneur
backup-restore-api qui monte la racine du projet (/project) et le socket
Docker ; les archives vivent dans /project/backups (jamais versionnées).
La phrase de chiffrement vient de SI_BACKUP_PASSPHRASE (.env) -- sans
elle, aucune sauvegarde automatique (jamais d'archive en clair).

Logique PURE (catalogue, chaînes, rétention GFS) testable sans Docker :
test_hub_backups.py.
"""
import datetime as _dt
import json
import os
import re
import subprocess
import threading
import time

NAME_RE = re.compile(r"^supervision-si-(backup|incr)-[A-Za-z0-9_.-]+-\d{8}-\d{6}$")


# ---------------------------------------------------------------- pur --
def read_catalog(backup_dir):
    """Toutes les sessions du dossier d'après les manifestes en clair
    (<nom>.manifest.json), les plus récentes d'abord."""
    out = []
    if not os.path.isdir(backup_dir):
        return out
    for f in os.listdir(backup_dir):
        if not f.endswith(".manifest.json"):
            continue
        try:
            m = json.load(open(os.path.join(backup_dir, f), encoding="utf-8"))
        except (OSError, ValueError):
            continue
        arc = m.get("archive") or ""
        path = os.path.join(backup_dir, arc)
        out.append({"name": m.get("name") or f[: -len(".manifest.json")], "kind": m.get("kind", "full"), "archive": arc,
                    "present": os.path.exists(path), "size": m.get("size") or (os.path.getsize(path) if os.path.exists(path) else 0),
                    "created_at": m.get("created_at"), "hostname": m.get("hostname"), "host_ip": m.get("host_ip"),
                    "delivery": (m.get("git") or {}).get("delivery"), "commit": ((m.get("git") or {}).get("commit") or "")[:8],
                    "base": m.get("base"), "previous": m.get("previous"), "changed_files": m.get("changed_files"),
                    "deleted": len(m.get("deleted") or []), "volumes": len(m.get("volumes") or []), "mounts": len(m.get("mounts") or []),
                    "encrypted": bool(m.get("encrypted", True))})
    out.sort(key=lambda s: s.get("created_at") or "", reverse=True)
    return out


def build_chains(sessions):
    """Regroupe les sessions en chaînes : une totale + ses incrémentales
    (ordre chronologique). -> [{full, increments:[...], last_at, size}]"""
    by_name = {s["name"]: s for s in sessions}
    chains = {}
    for s in sorted(sessions, key=lambda x: x.get("created_at") or ""):
        if s["kind"] == "full":
            chains.setdefault(s["name"], {"full": s, "increments": []})
        else:
            base = s.get("base")
            if base in by_name:
                chains.setdefault(base, {"full": by_name[base], "increments": []})["increments"].append(s)
            else:
                chains.setdefault("orphelines", {"full": None, "increments": []})["increments"].append(s)
    out = []
    for key, c in chains.items():
        members = ([c["full"]] if c["full"] else []) + c["increments"]
        out.append({"key": key, "full": c["full"], "increments": c["increments"],
                    "last_at": max((m.get("created_at") or "" for m in members), default=""),
                    "size": sum(m.get("size") or 0 for m in members), "count": len(members)})
    out.sort(key=lambda c: c["last_at"], reverse=True)
    return out


def _parse(ts):
    try:
        return _dt.datetime.fromisoformat((ts or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def gfs_plan(chains, keep_daily=7, keep_weekly=4, keep_monthly=6, now=None):
    """Rotation grand-père/père/fils sur les TOTALES (les incrémentales
    suivent leur totale) : on garde les `keep_daily` dernières totales, la
    dernière de chacune des `keep_weekly` dernières semaines, la dernière de
    chacun des `keep_monthly` derniers mois. -> {keep:[chaînes], drop:[chaînes], why:{key: raison}}"""
    fulls = [c for c in chains if c["full"] and _parse(c["full"].get("created_at"))]
    fulls.sort(key=lambda c: c["full"]["created_at"], reverse=True)
    keep, why = set(), {}
    for c in fulls[:keep_daily]:
        keep.add(c["key"]); why[c["key"]] = "récente"
    weeks, months = {}, {}
    for c in fulls:
        d = _parse(c["full"]["created_at"])
        wk = d.strftime("%G-W%V")
        mo = d.strftime("%Y-%m")
        weeks.setdefault(wk, c)      # la plus récente de la semaine (liste triée décroissante)
        months.setdefault(mo, c)
    for wk in sorted(weeks, reverse=True)[:keep_weekly]:
        c = weeks[wk]
        if c["key"] not in keep:
            keep.add(c["key"]); why[c["key"]] = "hebdomadaire %s" % wk
    for mo in sorted(months, reverse=True)[:keep_monthly]:
        c = months[mo]
        if c["key"] not in keep:
            keep.add(c["key"]); why[c["key"]] = "mensuelle %s" % mo
    kept = [c for c in chains if c["key"] in keep or c["key"] == "orphelines"]
    dropped = [c for c in chains if c["key"] not in keep and c["key"] != "orphelines"]
    return {"keep": kept, "drop": dropped, "why": why}


def files_of_chain(chain):
    names = []
    for m in ([chain["full"]] if chain["full"] else []) + chain["increments"]:
        names += [m["archive"], m["name"] + ".manifest.json"]
    return [n for n in names if n]


def safe_name(name):
    return bool(name) and NAME_RE.match(name) is not None


# ------------------------------------------------------------ runner --
class Runner(object):
    """Une sauvegarde à la fois ; journal du dernier run ; planification
    optionnelle (incrémentale toutes les N heures, totale un jour donné)."""

    def __init__(self, project_root, backup_dir, passphrase=None, host_root=None, incr_hours=0, full_weekday=None, full_hour=2):
        self.project_root = project_root
        self.backup_dir = backup_dir
        self.passphrase = passphrase
        self.host_root = host_root
        self.incr_hours = int(incr_hours or 0)
        self.full_weekday = full_weekday      # 0 = lundi ... 6 = dimanche ; None = jamais automatique
        self.full_hour = int(full_hour or 2)
        self._lock = threading.Lock()
        self.current = None                   # {"kind", "started_at"}
        self.last = None                      # {"kind", "started_at", "ended_at", "rc", "log"}
        self._thread = None

    def status(self):
        return {"running": self.current, "last": self.last, "configured": bool(self.passphrase),
                "schedule": {"incremental_every_hours": self.incr_hours, "full_weekday": self.full_weekday, "full_hour": self.full_hour},
                "backup_dir": self.backup_dir}

    def start(self, kind):
        if not self.passphrase:
            return False, "SI_BACKUP_PASSPHRASE absent dans .env : aucune sauvegarde sans chiffrement"
        with self._lock:
            if self.current:
                return False, "une sauvegarde est déjà en cours (%s)" % self.current["kind"]
            self.current = {"kind": kind, "started_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")}
        t = threading.Thread(target=self._run, args=(kind,), daemon=True)
        t.start()
        return True, None

    def _run(self, kind):
        cmd = ["python3", os.path.join(self.project_root, "scripts", "full_backup.py"), "backup", "--out", self.backup_dir]
        if kind == "incremental":
            cmd.append("--incremental")
        env = dict(os.environ, SI_BACKUP_PASSPHRASE=self.passphrase)
        if self.host_root:
            env["SI_BACKUP_HOST_ROOT"] = self.host_root
        started = self.current["started_at"]
        try:
            r = subprocess.run(cmd, cwd=self.project_root, env=env, capture_output=True, text=True, timeout=6 * 3600)
            rc, log = r.returncode, (r.stdout + ("\n" + r.stderr if r.stderr.strip() else ""))[-8000:]
        except Exception as exc:  # noqa: BLE001
            rc, log = 1, str(exc)
        self.last = {"kind": kind, "started_at": started, "ended_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"), "rc": rc, "log": log}
        try:
            with open(os.path.join(self.backup_dir, ".last-run.log"), "w", encoding="utf-8") as fh:
                fh.write(log)
        except OSError:
            pass
        with self._lock:
            self.current = None

    # planification : appelée par un thread de fond toutes les minutes
    def due(self, sessions, now=None):
        """-> 'full' | 'incremental' | None d'après la planification et le catalogue."""
        now = now or _dt.datetime.now(_dt.timezone.utc)
        if not self.passphrase or self.current:
            return None
        fulls = [s for s in sessions if s["kind"] == "full"]
        last_full = _parse(fulls[0]["created_at"]) if fulls else None
        last_any = _parse(sessions[0]["created_at"]) if sessions else None
        if self.full_weekday is not None and now.weekday() == self.full_weekday and now.hour == self.full_hour:
            if not last_full or (now - last_full) > _dt.timedelta(hours=20):
                return "full"
        if self.incr_hours > 0 and last_full is not None:
            if not last_any or (now - last_any) >= _dt.timedelta(hours=self.incr_hours):
                return "incremental"
        if not fulls and (self.full_weekday is not None or self.incr_hours > 0):
            return "full"   # première sauvegarde automatique : totale
        return None

    def schedule_loop(self):
        while True:
            try:
                kind = self.due(read_catalog(self.backup_dir))
                if kind:
                    self.start(kind)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(60)

    def start_scheduler(self):
        if self._thread is None and (self.incr_hours > 0 or self.full_weekday is not None):
            self._thread = threading.Thread(target=self.schedule_loop, daemon=True)
            self._thread.start()
        return self._thread is not None
