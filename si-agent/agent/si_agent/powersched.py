# -*- coding: utf-8 -*-
"""Redémarrage planifié du poste avec relance des applications (livraison #684).

Remplace les tâches planifiées posées à la main sur le poste écran du campus :
instantané des applications ouvertes dans la session console, événement
`host-reboot`, redémarrage ; au retour, relance de ces applications dans la
session de l'utilisateur (winsession, #683) et événement `host-boot`.

Configuration (commande `power_schedule`, persistée dans state.json) :
  {"enabled": true, "time": "00:00", "days": "1-7", "action": "reboot",
   "delay_seconds": 60, "relaunch": true, "message": "..."}

Module pur : l'agent fournit l'horloge, la liste des processus et l'exécution.
"""
import datetime as _dt
import json
import re

ACTIONS = ("reboot", "shutdown")
WINDOW_MIN = 15            # rattrapage : l'agent occupé ou redémarré pendant 15 min déclenche encore
RELAUNCH_GIVE_UP_S = 4 * 3600
MAX_APPS = 20
TIME_RE = re.compile(r"^([01]?\d|2[0-3]):([0-5]\d)$")
DAYS_RE = re.compile(r"^[1-7](-[1-7])?(,[1-7](-[1-7])?)*$")

# processus de la session qui ne sont pas des applications de l'utilisateur
IGNORED = {n.lower() for n in (
    "explorer.exe", "sihost.exe", "svchost.exe", "runtimebroker.exe", "ctfmon.exe", "taskhostw.exe", "dwm.exe",
    "winlogon.exe", "fontdrvhost.exe", "conhost.exe", "csrss.exe", "shellexperiencehost.exe",
    "startmenuexperiencehost.exe", "searchhost.exe", "searchapp.exe", "searchui.exe", "textinputhost.exe",
    "smartscreen.exe", "securityhealthsystray.exe", "applicationframehost.exe", "systemsettings.exe",
    "useroobebroker.exe", "lockapp.exe", "dllhost.exe", "backgroundtaskhost.exe", "widgets.exe",
    "widgetservice.exe", "phoneexperiencehost.exe", "gamebar.exe", "gamebarftserver.exe", "onedrive.exe",
    "msedgewebview2.exe", "crashpad_handler.exe", "rundll32.exe", "userinit.exe", "cmd.exe", "powershell.exe",
    "pwsh.exe", "windowsterminal.exe", "openconsole.exe", "anydesk.exe", "taskmgr.exe", "python.exe",
    "pythonw.exe", "si-agent.exe", "igfxem.exe", "rtkaudusservice64.exe", "securityhealthservice.exe")}


def _days(v):
    v = str(v or "1-7").replace(" ", "")
    return v if DAYS_RE.match(v) else None


def _day_set(spec):
    out = set()
    for part in (spec or "1-7").split(","):
        a, _, b = part.partition("-")
        out.update(range(int(a), int(b or a) + 1))
    return out


def normalize(cfg):
    """-> (config propre, erreurs)."""
    cfg = cfg or {}
    errors = []
    time_s = str(cfg.get("time") or "00:00").strip()
    m = TIME_RE.match(time_s)
    if not m:
        errors.append("time : HH:MM attendu"); time_s = "00:00"
    else:
        time_s = "%02d:%02d" % (int(m.group(1)), int(m.group(2)))
    days = _days(cfg.get("days"))
    if days is None:
        errors.append("days : 1-7 (lundi = 1), ex. 1-5 ou 1,3,5"); days = "1-7"
    action = cfg.get("action") or "reboot"
    if action not in ACTIONS:
        errors.append("action : reboot ou shutdown"); action = "reboot"
    try:
        delay = max(0, min(600, int(cfg.get("delay_seconds", 60))))
    except (TypeError, ValueError):
        delay = 60
    msg = re.sub(r"[\r\n\"]", " ", str(cfg.get("message") or "Redémarrage planifié (supervision)"))[:120]
    return {"enabled": cfg.get("enabled", True) is not False and not errors, "time": time_s, "days": days,
            "action": action, "delay_seconds": delay, "relaunch": cfg.get("relaunch", True) is not False and action == "reboot",
            "message": msg}, errors


def due(cfg, now_dt, last_fired):
    """Le créneau du jour est-il ouvert et pas encore servi ? -> clé du jour (YYYY-MM-DD) ou None."""
    if not cfg or not cfg.get("enabled"):
        return None
    hh, mm = (int(x) for x in cfg["time"].split(":"))
    start = now_dt.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now_dt < start or now_dt >= start + _dt.timedelta(minutes=WINDOW_MIN):
        return None
    if now_dt.isoweekday() not in _day_set(cfg.get("days")):
        return None
    key = start.strftime("%Y-%m-%d")
    return None if last_fired == key else key


def snapshot_argv():
    """Processus Windows (session, parent, chemin, ligne de commande) en JSON."""
    ps = ("Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,SessionId,Name,ExecutablePath,CommandLine"
          " | ConvertTo-Json -Compress")
    return ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps]


def parse_processes(text):
    try:
        data = json.loads(text or "[]")
    except ValueError:
        return []
    if isinstance(data, dict):
        data = [data]
    return [p for p in data if isinstance(p, dict)]


def console_session(procs):
    """Session de l'explorateur hors session 0 (l'utilisateur de la console)."""
    for p in procs:
        if str(p.get("Name") or "").lower() == "explorer.exe" and p.get("SessionId"):
            return p.get("SessionId")
    return None


def pick_apps(procs, session=None):
    """Applications de l'utilisateur à relancer : processus de la session console,
    lancés par l'explorateur (ou dont le parent n'est plus là), hors processus
    système ; dédoublonnés par ligne de commande. -> [{"name", "command"}]."""
    session = session if session is not None else console_session(procs)
    if session is None:
        return []
    in_session = [p for p in procs if p.get("SessionId") == session]
    by_pid = {p.get("ProcessId"): p for p in in_session}
    out, seen = [], set()
    for p in in_session:
        name = str(p.get("Name") or "").lower()
        path = p.get("ExecutablePath")
        if not path or name in IGNORED or "\\windows\\" in path.lower():
            continue
        parent = by_pid.get(p.get("ParentProcessId"))
        if parent is not None and str(parent.get("Name") or "").lower() != "explorer.exe":
            continue   # processus enfant d'une application : relancé par elle
        cmd = (p.get("CommandLine") or "").strip() or '"%s"' % path
        if cmd.lower() in seen:
            continue
        seen.add(cmd.lower())
        out.append({"name": p.get("Name"), "command": cmd})
        if len(out) >= MAX_APPS:
            break
    return out
