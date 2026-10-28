#!/usr/bin/env python3
"""Plugin si-agent « sockets » (#906) : relevé complet des sockets réseau d'un hôte, façon `netstat -laputen`, À LA
DEMANDE (horodaté, avec historique côté hub). En écoute ET établies, TCP ET UDP, avec le processus, le PID et
l'utilisateur. Lecture seule.

Linux : `ss -Htaupne` (parse). Windows : Get-NetTCPConnection + Get-NetUDPEndpoint (processus et utilisateur par PID).
Par socket : proto, état, adresse et port locaux, adresse et port distants, pid, processus, utilisateur ; drapeaux
`ecoute` (LISTEN / UNCONN) et `expose` (écoute sur 0.0.0.0 / :: , donc joignable du réseau).

Arguments : aucun.
"""
import json
import os
import re
import subprocess
import sys
import time

USERS = re.compile(r'users:\(\("([^"]+)",pid=(\d+)')
UID = re.compile(r'uid:(\d+)')
EXPOSE = ("0.0.0.0", "*", "::", "")


def _user_linux(uid):
    try:
        import pwd
        return pwd.getpwuid(int(uid)).pw_name
    except (KeyError, ValueError, ImportError):
        return str(uid)


def _user_de_pid(pid):
    """Propriétaire d'un processus par son PID (/proc/<pid>/status -> Uid). ss récent n'émet pas toujours uid: (omet uid:0)."""
    try:
        with open("/proc/%s/status" % pid) as fh:
            for ligne in fh:
                if ligne.startswith("Uid:"):
                    return _user_linux(ligne.split()[1])
    except (OSError, IndexError, ValueError):
        pass
    return None


def parse_ss(texte, user_de_uid=_user_linux, user_de_pid=_user_de_pid):
    """Sortie de `ss -Htaupne` -> [socket]. Colonnes : Netid State Recv-Q Send-Q Local Peer [Process …]."""
    out = []
    for ligne in (texte or "").splitlines():
        parts = ligne.split()
        if len(parts) < 6:
            continue
        proto, etat, local, peer = parts[0], parts[1], parts[4], parts[5]
        if ":" not in local:
            continue
        la, lp = local.rsplit(":", 1)
        ra, rp = (peer.rsplit(":", 1) + [""])[:2] if ":" in peer else (peer, "")
        mu = USERS.search(ligne)
        muid = UID.search(ligne)
        pid = int(mu.group(2)) if mu else None
        user = user_de_uid(muid.group(1)) if muid else (user_de_pid(pid) if pid else None)
        try:
            lp = int(lp)
        except ValueError:
            continue
        la = la.strip("[]")
        out.append({"proto": proto, "etat": etat, "local_ip": la, "local_port": lp,
                    "remote_ip": ra.strip("[]"), "remote_port": int(rp) if rp.isdigit() else None,
                    "process": mu.group(1) if mu else None, "pid": pid, "user": user,
                    "ecoute": etat in ("LISTEN", "UNCONN"),
                    "expose": etat in ("LISTEN", "UNCONN") and la in EXPOSE})
    return out


PS = r"""[Console]::OutputEncoding=[Text.Encoding]::UTF8; $ErrorActionPreference='SilentlyContinue'
$procs=@{}; Get-Process -IncludeUserName | ForEach-Object { $procs[[int]$_.Id]=@{n=$_.ProcessName; u=$_.UserName} }
$o=New-Object System.Collections.ArrayList
foreach($c in (Get-NetTCPConnection)){ $p=$procs[[int]$c.OwningProcess]
  [void]$o.Add([ordered]@{proto='tcp';etat=[string]$c.State;local_ip=[string]$c.LocalAddress;local_port=[int]$c.LocalPort;remote_ip=[string]$c.RemoteAddress;remote_port=[int]$c.RemotePort;pid=[int]$c.OwningProcess;process=$p.n;user=$p.u}) }
foreach($u in (Get-NetUDPEndpoint)){ $p=$procs[[int]$u.OwningProcess]
  [void]$o.Add([ordered]@{proto='udp';etat='UNCONN';local_ip=[string]$u.LocalAddress;local_port=[int]$u.LocalPort;remote_ip='';remote_port=0;pid=[int]$u.OwningProcess;process=$p.n;user=$p.u}) }
@{sockets=$o} | ConvertTo-Json -Depth 4 -Compress"""


def collect_windows(runner=subprocess.run):
    ps = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    p = runner([ps if os.path.exists(ps) else "powershell.exe", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", PS],
               stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    s = (p.stdout or b"").decode("utf-8", "replace")
    d = json.loads(s[s.find("{"):]) if "{" in s else {}
    out = []
    for c in (d.get("sockets") or []):
        etat = c.get("etat") or ""
        la = str(c.get("local_ip") or "")
        out.append({"proto": c.get("proto"), "etat": etat, "local_ip": la, "local_port": c.get("local_port"),
                    "remote_ip": c.get("remote_ip") or "", "remote_port": c.get("remote_port") or None,
                    "process": c.get("process"), "pid": c.get("pid"), "user": c.get("user"),
                    "ecoute": etat in ("Listen", "UNCONN", "Bound"),
                    "expose": etat in ("Listen", "UNCONN", "Bound") and la in EXPOSE})
    return out


def analyse(sockets, now=None):
    ecoute = [s for s in sockets if s.get("ecoute")]
    etab = [s for s in sockets if not s.get("ecoute")]
    return {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)), "sockets": sockets,
            "counts": {"total": len(sockets), "ecoute": len(ecoute), "etablies": len(etab),
                       "exposes": len([s for s in ecoute if s.get("expose")]),
                       "tcp": len([s for s in sockets if s.get("proto") == "tcp"]),
                       "udp": len([s for s in sockets if s.get("proto") == "udp"])},
            "alerts": []}


def main(argv=None, runner=subprocess.run, plateforme=sys.platform):
    if plateforme == "win32":
        try:
            socks = collect_windows(runner)
        except Exception as e:  # noqa: BLE001
            return {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "alerts": [{"code": "sockets-windows", "severity": "warning", "message": "relevé PowerShell illisible : %s" % str(e)[:150]}]}
        return analyse(socks)
    p = runner(["ss", "-Htaupne"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
    if p.returncode != 0 and not p.stdout:
        return {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "alerts": [{"code": "sockets-ss", "severity": "warning", "message": "ss indisponible : %s" % ((p.stderr or b"").decode("utf-8", "replace")[:150])}]}
    return analyse(parse_ss((p.stdout or b"").decode("utf-8", "replace")))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8") if hasattr(sys.stdout, "reconfigure") else None
    print(json.dumps(main(sys.argv[1:]), ensure_ascii=False))
