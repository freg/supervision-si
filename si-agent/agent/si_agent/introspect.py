# -*- coding: utf-8 -*-
"""Introspection de l'agent (livraison #616) -- l'agent mesure sa PROPRE
empreinte sur le poste, pour répondre à « quel est l'impact d'une sonde sur
la charge et la stabilité ? » avec des chiffres plutôt qu'une impression.

Mesuré sans dépendance (pas de psutil) :
- temps CPU du processus de l'agent (`os.times`, utilisateur + système,
  ENFANTS inclus : les sondes sont des sous-processus) rapporté au temps
  écoulé -> % d'un cœur sur l'intervalle, et % de la machine (÷ nb de cœurs) ;
- mémoire résidente de l'agent (Linux : /proc/self/status VmRSS ; Windows :
  GetProcessMemoryInfo ; macOS : resource.getrusage) ;
- durée de chaque collecte et de chaque sonde par cycle (min / moyenne / max
  sur la fenêtre), nombre de lancements, échecs ;
- taille de la file locale (mesures en attente) ;
- comparaison avec la charge de l'hôte (host.load) : part de l'agent.

Banc de charge (commande `bench` {minutes, factor}) : pendant `minutes`, les
collectes et toutes les sondes tournent à cadence forcée (intervalle ÷
`factor`, minimum 15 s) ; l'introspection tourne alors toutes les 30 s pour
tracer la courbe avant / pendant / après. `plan_bench` et `summarize` sont
purs et testés ; la lecture système est dans `read_self`.
"""
import os
import sys
import time

WINDOW_MAX = 120  # points gardés (2 h à 60 s, 1 h à 30 s en banc)


class Tracker:
    """Accumule durées de sondes / collectes et instantanés CPU-mémoire."""

    def __init__(self, clock=time.time, cpu_times=os.times, cores=None):
        self.clock = clock
        self.cpu_times = cpu_times
        self.cores = cores or max(1, os.cpu_count() or 1)
        self.durations = {}     # {nom: [secondes, ...]} depuis le dernier instantané
        self.failures = {}      # {nom: nb échecs}
        self.points = []        # instantanés successifs
        t = cpu_times()
        self._last_cpu = t.user + t.system + t.children_user + t.children_system
        self._last_at = clock()

    def record(self, name, seconds, ok=True):
        self.durations.setdefault(name, []).append(float(seconds))
        if not ok:
            self.failures[name] = self.failures.get(name, 0) + 1

    def snapshot(self, rss_bytes=None, queue_size=None, host_load1=None, bench=False):
        now = self.clock()
        t = self.cpu_times()
        cpu = t.user + t.system + t.children_user + t.children_system
        elapsed = max(0.001, now - self._last_at)
        core_pct = 100.0 * (cpu - self._last_cpu) / elapsed
        self._last_cpu, self._last_at = cpu, now
        tasks = {}
        for name, vals in self.durations.items():
            tasks[name] = {"runs": len(vals), "min": round(min(vals), 3), "avg": round(sum(vals) / len(vals), 3), "max": round(max(vals), 3),
                           "total": round(sum(vals), 3), "failed": self.failures.get(name, 0)}
        point = {"at": now, "elapsed": round(elapsed, 1), "cpu_core_percent": round(max(0.0, core_pct), 2),
                 "cpu_machine_percent": round(max(0.0, core_pct) / self.cores, 2), "cores": self.cores,
                 "rss_bytes": rss_bytes, "queue_size": queue_size, "host_load1": host_load1, "bench": bool(bench), "tasks": tasks}
        self.points.append(point)
        del self.points[:-WINDOW_MAX]
        self.durations, self.failures = {}, {}
        return point


def summarize(points):
    """Fenêtre d'instantanés -> résumé : moyenne / max CPU, mémoire, sondes les
    plus coûteuses, et comparaison banc / hors banc si des points de banc existent."""
    pts = [p for p in points or [] if p.get("elapsed")]
    if not pts:
        return {"points": 0}
    def agg(sel):
        if not sel:
            return None
        return {"points": len(sel), "cpu_core_avg": round(sum(p["cpu_core_percent"] for p in sel) / len(sel), 2),
                "cpu_core_max": round(max(p["cpu_core_percent"] for p in sel), 2),
                "cpu_machine_avg": round(sum(p["cpu_machine_percent"] for p in sel) / len(sel), 2),
                "rss_max": max((p.get("rss_bytes") or 0) for p in sel) or None,
                "queue_max": max((p.get("queue_size") or 0) for p in sel)}
    tasks = {}
    for p in pts:
        for name, t in (p.get("tasks") or {}).items():
            acc = tasks.setdefault(name, {"runs": 0, "total": 0.0, "max": 0.0, "failed": 0})
            acc["runs"] += t["runs"]; acc["total"] += t["total"]; acc["max"] = max(acc["max"], t["max"]); acc["failed"] += t.get("failed", 0)
    costly = sorted(({"name": n, **v, "avg": round(v["total"] / v["runs"], 3) if v["runs"] else 0, "total": round(v["total"], 3), "max": round(v["max"], 3)} for n, v in tasks.items()),
                    key=lambda x: -x["total"])[:8]
    return {"points": len(pts), "window_seconds": round(pts[-1]["at"] - pts[0]["at"] + pts[0]["elapsed"], 1), "all": agg(pts),
            "bench": agg([p for p in pts if p.get("bench")]), "normal": agg([p for p in pts if not p.get("bench")]),
            "last": pts[-1], "costly": costly, "cores": pts[-1].get("cores")}


def plan_bench(params, now):
    """{minutes, factor} -> (until, factor, erreur). 1–60 min, facteur 2–20."""
    try:
        minutes = max(1, min(60, int((params or {}).get("minutes", 10))))
        factor = max(2, min(20, int((params or {}).get("factor", 6))))
    except (TypeError, ValueError):
        return None, None, "minutes / factor entiers"
    return now + minutes * 60, factor, None


def forced_interval(base_interval, factor, floor=15):
    return max(floor, float(base_interval or 60) / float(factor or 1))


def read_rss():
    """Mémoire résidente du processus courant, en octets (None si inconnue)."""
    try:
        if sys.platform == "win32":
            import ctypes
            from ctypes import wintypes

            class PMC(ctypes.Structure):
                _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                            ("WorkingSetSize", ctypes.c_size_t), ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t), ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                            ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]
            pmc = PMC(); pmc.cb = ctypes.sizeof(PMC)
            if ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(), ctypes.byref(pmc), pmc.cb):
                return int(pmc.WorkingSetSize)
            return None
        if sys.platform == "darwin":
            import resource
            return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) * 1024
    except (OSError, ValueError, AttributeError):
        return None
    return None
