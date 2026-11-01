#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Plugin si-agent « app-logwatch » (#739) : « lsof » d'une application propriétaire (superviseur GTB type
Neutrino GLT de Kieback&Peter…) pour trouver ses journaux et y lire les causes de dysfonctionnement.

À chaque passage :
  1. processus et services de l'application (motifs `--match`, défaut « neutrino,kieback ») : présents, arrêtés ;
  2. fichiers OUVERTS par ces processus — Windows : table des handles (NtQuerySystemInformation, stdlib ctypes, rien
     à installer ; `handle.exe` de Sysinternals utilisé s'il est présent) ; Linux : /proc/<pid>/fd ;
  3. journaux candidats = fichiers ouverts + fichiers récents (*.log, *.txt, *.trc…) des dossiers de l'application
     (dossier de l'exécutable, ProgramData\\Kieback*, …, `--paths`) ;
  4. lecture INCRÉMENTALE de ce qui a été écrit depuis le passage précédent (position mémorisée, rotation détectée),
     UTF-8 / UTF-16 / cp1252 ; lignes d'erreur, d'avertissement et RÉSEAU (délai, refus, injoignable, codes Winsock
     10060/10061/10065/10054…) regroupées par message, avec les adresses IP:port citées (à croiser avec gtb-netwatch) ;
  5. journal d'événements Windows (Application, System) : erreurs du logiciel, plantages (1000/1002/1026), service
     arrêté inopinément (7031/7034).
Sortie JSON : {at, processes, services, open_files, logs, events, findings, alerts, error}. Lecture seule.

Arguments : [--match neutrino,kieback] [--paths D:\\GLT\\Log;C:\\autre] [--minutes 60] [--max-kb 1024]
            [--state FICHIER] [--extensions log,txt,trc,err,out]
"""
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time

EXT_DEFAULT = "log,txt,trc,trace,err,out,lg"
RE_ERROR = re.compile(r"(\berror\b|\berreur|\bfehler|exception|\bfatal\b|\bcritical\b|kritisch|[ée]chec|\bfailed\b|failure|fehlgeschlagen|abgebrochen)", re.I)
RE_WARN = re.compile(r"(\bwarn(ing)?\b|avertissement|warnung)", re.I)
RE_NET = re.compile(r"(time-?out|timed out|zeit[üu]berschreitung|d[ée]lai d.attente|refused|refus[ée]|verweigert|unreachable|injoignable|"
                    r"nicht erreichbar|connection (lost|reset|closed|failed)|verbindung (unterbrochen|getrennt|fehl)|connexion (perdue|interrompue|impossible)|"
                    r"no route|wsae\w+|\b100(60|61|65|54|51|53|50)\b|bacnet|modbus|socket)", re.I)
RE_IPPORT = re.compile(r"\b((?:\d{1,3}\.){3}\d{1,3})(?::(\d{1,5}))?\b")
WINSOCK = {"10060": "délai dépassé (WSAETIMEDOUT) : l'équipement ne répond pas",
           "10061": "connexion refusée (WSAECONNREFUSED) : port fermé ou service arrêté",
           "10065": "hôte injoignable (WSAEHOSTUNREACH)", "10051": "réseau injoignable (WSAENETUNREACH)",
           "10054": "connexion réinitialisée par le distant (WSAECONNRESET)", "10053": "connexion abandonnée localement (WSAECONNABORTED)",
           "10050": "réseau hors service (WSAENETDOWN)"}
CRASH_IDS = {1000: "plantage de l'application", 1002: "application bloquée", 1026: "exception .NET non gérée",
             7031: "service arrêté inopinément", 7034: "service arrêté inopinément", 7023: "service arrêté sur erreur",
             7024: "service arrêté sur erreur spécifique", 7000: "service impossible à démarrer", 7009: "délai de démarrage du service"}
TAIL_FIRST = 64 * 1024


def sh(argv, timeout=60):
    try:
        return subprocess.run(argv, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as exc:
        class R:  # noqa: D401
            returncode, stdout, stderr = -1, "", str(exc)
        return R()


def ps(script, timeout=90):
    return sh(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command",
               "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + script], timeout=timeout)


def json_lines(text):
    out = []
    txt = (text or "").strip()
    if txt.startswith("["):
        try:
            return json.loads(txt)
        except ValueError:
            pass
    for line in txt.splitlines():
        try:
            out.append(json.loads(line))
        except ValueError:
            pass
    return out


def parse_args(argv):
    o, i = {}, 0
    while i < len(argv):
        if argv[i].startswith("--") and i + 1 < len(argv):
            o[argv[i][2:].replace("-", "_")] = argv[i + 1]; i += 2
        else:
            i += 1
    return o


def matches(text, pats):
    t = (text or "").lower()
    return any(p in t for p in pats)


# ------------------------------------------------------------------ processus et services

def processes(pats):
    out = []
    if os.name == "nt":
        r = ps("Get-CimInstance Win32_Process | ForEach-Object { [pscustomobject]@{name=$_.Name; pid=[int]$_.ProcessId; "
               "path=[string]$_.ExecutablePath; cmd=[string]$_.CommandLine; started=[string]$_.CreationDate} | ConvertTo-Json -Compress }")
        for d in json_lines(r.stdout):
            if matches(d.get("name"), pats) or matches(d.get("path"), pats):
                out.append(d)
        return out
    for pid in os.listdir("/proc"):
        if not pid.isdigit():
            continue
        try:
            name = open("/proc/%s/comm" % pid).read().strip()
            path = os.readlink("/proc/%s/exe" % pid) if os.path.exists("/proc/%s/exe" % pid) else ""
            cmd = open("/proc/%s/cmdline" % pid, "rb").read().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        if matches(name, pats) or matches(path, pats) or matches(cmd.split(" ")[0], pats):
            out.append({"name": name, "pid": int(pid), "path": path, "cmd": cmd[:300], "started": None})
    return out


def services(pats):
    if os.name != "nt":
        return []
    r = ps("Get-CimInstance Win32_Service | ForEach-Object { [pscustomobject]@{name=$_.Name; display=$_.DisplayName; state=$_.State; "
           "start=$_.StartMode; path=[string]$_.PathName; pid=[int]$_.ProcessId; account=$_.StartName} | ConvertTo-Json -Compress }")
    return [d for d in json_lines(r.stdout) if matches(d.get("name"), pats) or matches(d.get("display"), pats) or matches(d.get("path"), pats)]


# ------------------------------------------------------------------ fichiers ouverts (« lsof »)

def open_files_linux(pids):
    out = {}
    for pid in pids:
        d = "/proc/%d/fd" % pid
        try:
            for fd in os.listdir(d):
                try:
                    t = os.readlink(os.path.join(d, fd))
                except OSError:
                    continue
                if t.startswith("/") and os.path.isfile(t):
                    out.setdefault(t, set()).add(pid)
        except OSError:
            pass
    return out


def open_files_handle_exe(pids):
    exe = shutil.which("handle64.exe") or shutil.which("handle.exe") or next(
        (p for p in (os.path.join(os.path.dirname(os.path.abspath(__file__)), n) for n in ("handle64.exe", "handle.exe")) if os.path.exists(p)), None)
    if not exe:
        return None
    out = {}
    for pid in pids:
        r = sh([exe, "-accepteula", "-nobanner", "-p", str(pid)], timeout=60)
        for line in (r.stdout or "").splitlines():
            m = re.match(r"\s*[0-9A-F]+:\s+File\s+\([^)]*\)\s+(.+)$", line)
            if m and re.match(r"[A-Za-z]:\\", m.group(1).strip()):
                out.setdefault(m.group(1).strip(), set()).add(pid)
    return out


def open_files_ntapi(pids, budget=60):
    """Table des handles du système, filtrée sur `pids` ; chemin par GetFinalPathNameByHandleW sur une copie du handle.
    Seuls les handles de type disque sont nommés (GetFileType) ; les masques d'accès connus pour bloquer (tubes
    synchrones) sont écartés ; le tout dans un fil borné en temps."""
    import ctypes
    from ctypes import wintypes as wt
    ntdll, k32 = ctypes.WinDLL("ntdll"), ctypes.WinDLL("kernel32", use_last_error=True)

    class ENTRY(ctypes.Structure):
        _fields_ = [("Object", ctypes.c_void_p), ("Pid", ctypes.c_size_t), ("Handle", ctypes.c_size_t), ("Access", wt.ULONG),
                    ("Backtrace", wt.USHORT), ("TypeIndex", wt.USHORT), ("Attributes", wt.ULONG), ("Reserved", wt.ULONG)]
    k32.OpenProcess.restype = wt.HANDLE
    k32.GetCurrentProcess.restype = wt.HANDLE
    k32.DuplicateHandle.argtypes = [wt.HANDLE, wt.HANDLE, wt.HANDLE, ctypes.POINTER(wt.HANDLE), wt.DWORD, wt.BOOL, wt.DWORD]
    k32.GetFileType.argtypes = [wt.HANDLE]
    k32.GetFinalPathNameByHandleW.argtypes = [wt.HANDLE, wt.LPWSTR, wt.DWORD, wt.DWORD]
    k32.CloseHandle.argtypes = [wt.HANDLE]
    size = 1 << 20
    while True:
        buf = ctypes.create_string_buffer(size)
        ret = ctypes.c_ulong(0)
        st = ntdll.NtQuerySystemInformation(64, buf, size, ctypes.byref(ret)) & 0xFFFFFFFF
        if st == 0xC0000004 and size < (1 << 28):
            size = max(size * 2, ret.value + 65536); continue
        if st != 0:
            raise OSError("NtQuerySystemInformation : 0x%08X" % st)
        break
    n = ctypes.c_size_t.from_buffer(buf).value
    off = 2 * ctypes.sizeof(ctypes.c_size_t)
    entries = (ENTRY * n).from_buffer(buf, off)
    want, out, me = set(pids), {}, k32.GetCurrentProcess()
    BAD = {0x0012019F, 0x001A019F, 0x00120189, 0x00100000, 0x0016019F}
    procs = {}
    deadline = time.time() + budget
    for e in entries:
        if e.Pid not in want or e.Access in BAD:
            continue
        if time.time() > deadline:
            break
        hp = procs.get(e.Pid)
        if hp is None:
            hp = procs[e.Pid] = k32.OpenProcess(0x0040, False, e.Pid)        # PROCESS_DUP_HANDLE
        if not hp:
            continue
        h = wt.HANDLE()
        if not k32.DuplicateHandle(hp, wt.HANDLE(e.Handle), me, ctypes.byref(h), 0, False, 2):
            continue
        try:
            if k32.GetFileType(h) != 1:                                     # FILE_TYPE_DISK
                continue
            pb = ctypes.create_unicode_buffer(1024)
            if k32.GetFinalPathNameByHandleW(h, pb, 1024, 0):
                p = pb.value
                p = p[4:] if p.startswith("\\\\?\\") else p
                if p.startswith("UNC\\"):
                    p = "\\" + p[3:]
                out.setdefault(p, set()).add(int(e.Pid))
        finally:
            k32.CloseHandle(h)
    for hp in procs.values():
        if hp:
            k32.CloseHandle(hp)
    return out


def open_files(pids):
    """-> ({chemin: {pid}}, méthode, erreur)."""
    if not pids:
        return {}, None, None
    if os.name != "nt":
        return open_files_linux(pids), "proc", None
    r = open_files_handle_exe(pids)
    if r is not None:
        return r, "handle.exe", None
    res = {}

    def run():
        try:
            res["v"] = open_files_ntapi(pids)
        except Exception as exc:  # noqa: BLE001
            res["e"] = str(exc)
    t = threading.Thread(target=run, daemon=True)
    t.start(); t.join(90)
    if t.is_alive():
        return {}, "ntapi", "énumération des handles interrompue (délai)"
    return res.get("v", {}), "ntapi", res.get("e")


# ------------------------------------------------------------------ journaux

def app_dirs(procs, svcs, extra):
    dirs = []
    for p in procs:
        if p.get("path"):
            d = os.path.dirname(p["path"]); dirs += [d, os.path.dirname(d)]
    for s in svcs:
        m = re.match(r'\s*"?([A-Za-z]:\\[^"]+?\.exe)', s.get("path") or "", re.I)
        if m:
            d = os.path.dirname(m.group(1)); dirs += [d, os.path.dirname(d)]
    if os.name == "nt":
        for root in (os.environ.get("ProgramData", r"C:\ProgramData"), os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")):
            try:
                dirs += [os.path.join(root, n) for n in os.listdir(root) if re.search(r"kieback|neutrino|k&p|kp[ -_]", n, re.I)]
            except OSError:
                pass
    dirs += [d for d in re.split(r"[;,]", extra or "") if d.strip()]
    seen, out = set(), []
    for d in dirs:
        d = os.path.normpath(d.strip())
        if d and d.lower() not in seen and os.path.isdir(d) and len(d) > 3:      # jamais la racine d'un disque
            seen.add(d.lower()); out.append(d)
    return out


def recent_logs(dirs, exts, minutes, limit=300):
    out, horizon = [], time.time() - minutes * 60
    for d in dirs:
        base = d.rstrip("\\/").count(os.sep)
        for root, subs, files in os.walk(d):
            if root.count(os.sep) - base >= 4:
                subs[:] = []
            for f in files:
                if f.rsplit(".", 1)[-1].lower() in exts or re.search(r"log", f, re.I):
                    p = os.path.join(root, f)
                    try:
                        if os.path.getmtime(p) >= horizon:
                            out.append(p)
                    except OSError:
                        pass
                if len(out) >= limit:
                    return out
    return out


def decode_bytes(b):
    if b[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return b.decode("utf-16", "replace")
    if len(b) > 64 and b[1:64:2].count(0) > 24:
        return b.decode("utf-16-le", "replace")
    try:
        return b.decode("utf-8")
    except UnicodeDecodeError:
        return b.decode("cp1252", "replace")


def norm(line):
    s = re.sub(r"^\W*\d{2,4}[-./]\d{1,2}[-./]\d{1,4}[ T]?\d{0,2}:?\d{0,2}:?\d{0,2}[.,]?\d*\s*", "", line)   # horodatage en tête
    return re.sub(r"\d+", "#", s).strip()[:160]


def scan_log(path, st, max_bytes):
    """-> (résumé, nouvel état). Lecture depuis la dernière position ; rotation (taille < position) : depuis le début."""
    try:
        size, mtime = os.path.getsize(path), os.path.getmtime(path)
    except OSError as exc:
        return {"path": path, "error": str(exc)}, st
    prev = st.get(path)
    first = prev is None
    start = max(0, size - TAIL_FIRST) if first else (0 if size < prev["offset"] else prev["offset"])
    rotated = (not first) and size < prev["offset"]
    start = max(start, size - max_bytes)
    try:
        with open(path, "rb") as fh:
            fh.seek(start)
            data = fh.read(size - start)
    except OSError as exc:
        return {"path": path, "size": size, "error": str(exc)}, st
    text = decode_bytes(data)
    counts, groups, last, ips, codes = {"error": 0, "warning": 0, "network": 0}, {}, [], {}, {}
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        cat = "network" if RE_NET.search(line) and (RE_ERROR.search(line) or RE_WARN.search(line) or re.search(r"\b100\d\d\b|refus|time|verweig|injoign|unreach", line, re.I)) \
            else ("error" if RE_ERROR.search(line) else ("warning" if RE_WARN.search(line) else None))
        if not cat:
            continue
        counts[cat] += 1
        g = groups.setdefault((cat, norm(line)), {"category": cat, "message": line[:240], "count": 0})
        g["count"] += 1; g["message"] = line[:240]
        last.append({"category": cat, "line": line[:300]})
        if cat == "network":
            for ip, port in RE_IPPORT.findall(line):
                k = ip + (":" + port if port else "")
                ips[k] = ips.get(k, 0) + 1
            for c in re.findall(r"\b(100[5-6]\d)\b", line):
                if c in WINSOCK:
                    codes[c] = codes.get(c, 0) + 1
    st = dict(st); st[path] = {"offset": size, "mtime": mtime}
    return {"path": path, "size": size, "modified": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(mtime)), "first_read": first,
            "rotated": rotated, "read_bytes": len(data), "counts": counts,
            "top": sorted(groups.values(), key=lambda g: -g["count"])[:15], "last": last[-20:],
            "addresses": sorted(ips.items(), key=lambda x: -x[1])[:20],
            "winsock": [{"code": c, "count": n, "meaning": WINSOCK[c]} for c, n in sorted(codes.items())]}, st


# ------------------------------------------------------------------ journal d'événements Windows

def events(pats, procnames, minutes):
    if os.name != "nt":
        return []
    rx = "|".join(re.escape(p) for p in list(pats) + [n.rsplit(".", 1)[0].lower() for n in procnames if n]) or "neutrino"
    ids = ",".join(str(i) for i in CRASH_IDS)
    r = ps("$s=(Get-Date).AddMinutes(-%d); Get-WinEvent -FilterHashtable @{LogName='Application','System'; StartTime=$s; Level=1,2,3} "
           "-ErrorAction SilentlyContinue | Where-Object { $_.ProviderName -match '%s' -or (@(%s) -contains $_.Id -and $_.Message -match '%s') } | "
           "Select-Object -First 200 | ForEach-Object { [pscustomobject]@{at=$_.TimeCreated.ToString('s'); log=$_.LogName; source=$_.ProviderName; "
           "id=$_.Id; level=$_.LevelDisplayName; message=([string]$_.Message).Substring(0,[Math]::Min(400,([string]$_.Message).Length))} | ConvertTo-Json -Compress }"
           % (minutes, rx.replace("'", "''"), ids, rx.replace("'", "''")), timeout=120)
    return json_lines(r.stdout)


def findings(procs, svcs, logs, evts, pats):
    f = []
    running = [s for s in svcs if (s.get("state") or "").lower() == "running"]
    if not procs and not running:
        f.append({"code": "process-absent", "severity": "critical",
                  "text": "aucun processus ni service actif pour « %s » : l'application ne tourne pas" % ", ".join(pats)})
    for s in svcs:
        if (s.get("start") or "").lower() == "auto" and (s.get("state") or "").lower() != "running":
            f.append({"code": "service-stopped", "severity": "critical", "target": s["name"],
                      "text": "service %s (%s) en démarrage automatique mais %s" % (s.get("display") or s["name"], s["name"], s.get("state"))})
    for e in evts:
        if e.get("id") in CRASH_IDS:
            f.append({"code": "app-crash", "severity": "critical", "target": "%s#%s" % (e.get("source"), e.get("id")),
                      "text": "%s : %s (%s, événement %s) -- %s" % (e.get("at"), CRASH_IDS[e["id"]], e.get("source"), e.get("id"), (e.get("message") or "")[:200])})
    n_ev = len([e for e in evts if e.get("id") not in CRASH_IDS])
    if n_ev:
        f.append({"code": "eventlog-errors", "severity": "warning", "target": "eventlog",
                  "text": "%d erreur(s)/avertissement(s) du logiciel dans le journal d'événements Windows" % n_ev})
    for lg in logs:
        c = lg.get("counts") or {}
        if c.get("network"):
            ws = "; ".join("%s ×%d : %s" % (w["code"], w["count"], w["meaning"]) for w in lg.get("winsock", []))
            adr = ", ".join("%s ×%d" % a for a in lg.get("addresses", [])[:5])
            f.append({"code": "log-network", "severity": "warning", "target": lg["path"],
                      "text": "%s : %d ligne(s) d'erreur réseau%s%s -- ex. « %s »" % (
                          os.path.basename(lg["path"]), c["network"], (" ; " + ws) if ws else "", (" ; équipements cités : " + adr) if adr else "",
                          lg["top"][0]["message"][:160] if lg.get("top") else "")})
        if c.get("error"):
            top = next((t for t in lg.get("top", []) if t["category"] == "error"), None)
            f.append({"code": "log-errors", "severity": "warning", "target": lg["path"],
                      "text": "%s : %d erreur(s)%s -- ex. « %s »" % (os.path.basename(lg["path"]), c["error"], " (première lecture : fin du fichier)" if lg.get("first_read") else "",
                                                                     top["message"][:160] if top else "")})
    return f


def default_state():
    base = os.path.join(os.environ.get("ProgramData", r"C:\ProgramData"), "si-agent") if os.name == "nt" else "/var/lib/si-agent"
    return os.path.join(base, "app-logwatch.state.json")


def main(argv=None):
    o = parse_args(sys.argv[1:] if argv is None else argv)
    pats = [p.strip().lower() for p in (o.get("match") or "neutrino,kieback").split(",") if p.strip()]
    minutes = int(o.get("minutes", "60"))
    max_bytes = int(o.get("max_kb", "1024")) * 1024
    exts = {e.strip().lower().lstrip(".") for e in (o.get("extensions") or EXT_DEFAULT).split(",")}
    state_path = o.get("state") or default_state()
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "match": pats, "processes": [], "services": [], "open_files": [],
           "open_files_method": None, "log_dirs": [], "logs": [], "events": [], "findings": [], "alerts": [], "error": None}
    try:
        st = json.load(open(state_path, encoding="utf-8"))
    except (OSError, ValueError):
        st = {}
    try:
        procs = processes(pats)
        svcs = services(pats)
        pids = sorted({p["pid"] for p in procs} | {s["pid"] for s in svcs if s.get("pid")})
        of, method, err = open_files(pids)
        out.update(processes=procs, services=svcs, open_files_method=method)
        if err:
            out["error"] = "fichiers ouverts : %s" % err
        out["open_files"] = [{"path": p, "pids": sorted(v)} for p, v in sorted(of.items())][:500]
        dirs = app_dirs(procs, svcs, o.get("paths"))
        out["log_dirs"] = dirs
        cands = [p for p in of if p.rsplit(".", 1)[-1].lower() in exts or re.search(r"log|trace", p, re.I)]
        for p in recent_logs(dirs, exts, minutes):
            if p not in cands:
                cands.append(p)
        new_st = {k: v for k, v in st.items() if os.path.exists(k)}
        for p in cands[:100]:
            summary, new_st = scan_log(p, new_st, max_bytes)
            summary["open_by"] = sorted(of.get(p, []))
            out["logs"].append(summary)
        out["events"] = events(pats, [p.get("name") for p in procs], minutes)
        out["findings"] = findings(procs, svcs, out["logs"], out["events"], pats)
        out["alerts"] = [{"code": ("%s@%s" % (f["code"], os.path.basename(str(f.get("target", "app"))) or "app"))[:64], "severity": f["severity"], "message": f["text"]}
                         for f in out["findings"] if f["severity"] in ("warning", "critical")]
        try:
            os.makedirs(os.path.dirname(state_path), exist_ok=True)
            with open(state_path + ".tmp", "w", encoding="utf-8") as fh:
                json.dump(new_st, fh)
            os.replace(state_path + ".tmp", state_path)
        except OSError as exc:
            out["error"] = (out["error"] + " ; " if out["error"] else "") + "état non enregistré : %s" % exc
    except Exception as exc:  # noqa: BLE001
        out["error"] = "%s: %s" % (type(exc).__name__, exc)
    print(json.dumps(out, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
