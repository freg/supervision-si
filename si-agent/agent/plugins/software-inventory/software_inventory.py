# -*- coding: utf-8 -*-
"""Sonde « software-inventory » (livraison #595) -- logiciels installés sur
le poste, toutes plateformes, pour le gestionnaire de licences du hub.

Sortie JSON : {"os": ..., "hostname": ..., "users": [...], "installed":
[{"name", "version", "publisher", "installed_at", "source"}], "count", "warnings"}.
Parseurs purs (testables sans système) ; aucune action, aucun secret."""
import json
import os
import platform
import re
import subprocess
import sys
import time

OFFICE_KEYS = ("Microsoft 365", "Office 16", "Office 365", "Microsoft Office")


def _run(argv, timeout=120):
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return p.returncode, p.stdout or "", p.stderr or ""
    except (OSError, subprocess.TimeoutExpired) as exc:
        return -1, "", str(exc)


# ---------------------------------------------------------------- parseurs purs
def parse_dpkg(text):
    """`dpkg-query -W -f '${Package}\\t${Version}\\t${Status}\\t${Maintainer}\\n'`."""
    out = []
    for line in (text or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 3 or "installed" not in parts[2] or "not-installed" in parts[2]:
            continue
        out.append({"name": parts[0], "version": parts[1], "publisher": (parts[3] if len(parts) > 3 else "").split("<")[0].strip(), "source": "dpkg"})
    return out


def parse_rpm(text):
    """`rpm -qa --qf '%{NAME}\\t%{VERSION}-%{RELEASE}\\t%{VENDOR}\\t%{INSTALLTIME}\\n'`."""
    out = []
    for line in (text or "").splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        rec = {"name": parts[0], "version": parts[1], "publisher": parts[2] if len(parts) > 2 and parts[2] != "(none)" else "", "source": "rpm"}
        if len(parts) > 3 and parts[3].isdigit():
            rec["installed_at"] = time.strftime("%Y-%m-%d", time.localtime(int(parts[3])))
        out.append(rec)
    return out


def parse_flatpak(text):
    out = []
    for line in (text or "").splitlines():
        parts = line.split("\t")
        if len(parts) >= 3:
            out.append({"name": parts[0] or parts[1], "version": parts[2], "publisher": parts[1].split(".")[1] if "." in parts[1] else "", "source": "flatpak", "id": parts[1]})
    return out


def parse_snap(text):
    out = []
    for line in (text or "").splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[0] not in ("core", "core18", "core20", "core22", "core24", "snapd", "bare"):
            out.append({"name": parts[0], "version": parts[1], "publisher": parts[4].rstrip("✓*") if len(parts) > 4 else "", "source": "snap"})
    return out


def parse_brew(text):
    out = []
    for line in (text or "").splitlines():
        parts = line.split()
        if parts:
            out.append({"name": parts[0], "version": parts[-1] if len(parts) > 1 else "", "publisher": "Homebrew", "source": "brew"})
    return out


def parse_windows(text):
    """JSON produit par PowerShell (liste d'objets DisplayName / DisplayVersion / Publisher / InstallDate)."""
    try:
        data = json.loads((text or "").strip().lstrip("\ufeff") or "[]")
    except ValueError:
        return []
    if isinstance(data, dict):
        data = [data]
    out, seen = [], set()
    for it in data or []:
        name = (it.get("DisplayName") or "").strip()
        if not name or name in seen:
            continue
        seen.add(name)
        d = str(it.get("InstallDate") or "")
        rec = {"name": name, "version": str(it.get("DisplayVersion") or ""), "publisher": (it.get("Publisher") or "").strip(), "source": "windows-registry"}
        if re.match(r"^\d{8}$", d):
            rec["installed_at"] = "%s-%s-%s" % (d[:4], d[4:6], d[6:])
        if it.get("Scope"):
            rec["scope"] = it["Scope"]
        out.append(rec)
    return out


def parse_mac_apps(entries):
    """[(nom.app, version, éditeur)] -> enregistrements."""
    return [{"name": n[:-4] if n.endswith(".app") else n, "version": v or "", "publisher": p or "", "source": "applications"} for n, v, p in entries]


def normalize(items):
    """Dédoublonne par (nom, version), trie, borne à 5000."""
    seen, out = set(), []
    for it in items:
        key = (it.get("name", "").lower(), it.get("version", ""))
        if key in seen or not it.get("name"):
            continue
        seen.add(key)
        out.append(it)
    out.sort(key=lambda x: x["name"].lower())
    return out[:5000]


# ---------------------------------------------------------------- collecte
WIN_PS = r'''$paths = @("HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*","HKLM:\Software\Wow6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*","HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*");
$items = foreach ($p in $paths) { Get-ItemProperty $p -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -and -not $_.SystemComponent } | Select-Object DisplayName, DisplayVersion, Publisher, InstallDate, @{n="Scope";e={ if ($p -like "HKCU*") {"user"} else {"machine"} }} };
$items | ConvertTo-Json -Compress'''


def collect_linux():
    items, warnings = [], []
    code, out, err = _run(["dpkg-query", "-W", "-f", "${Package}\t${Version}\t${Status}\t${Maintainer}\n"])
    if code == 0:
        items += parse_dpkg(out)
    else:
        code, out, err = _run(["rpm", "-qa", "--qf", "%{NAME}\t%{VERSION}-%{RELEASE}\t%{VENDOR}\t%{INSTALLTIME}\n"])
        if code == 0:
            items += parse_rpm(out)
        else:
            warnings.append("ni dpkg ni rpm")
    code, out, _ = _run(["flatpak", "list", "--app", "--columns=name,application,version"])
    if code == 0:
        items += parse_flatpak(out)
    code, out, _ = _run(["snap", "list"])
    if code == 0:
        items += parse_snap(out)
    return items, warnings


def collect_mac():
    items, warnings = [], []
    entries = []
    for base in ("/Applications", os.path.expanduser("~/Applications")):
        try:
            names = [n for n in os.listdir(base) if n.endswith(".app")]
        except OSError:
            continue
        for n in names:
            plist = os.path.join(base, n, "Contents", "Info.plist")
            version, publisher = "", ""
            code, out, _ = _run(["defaults", "read", plist, "CFBundleShortVersionString"], timeout=10)
            if code == 0:
                version = out.strip()
            code, out, _ = _run(["defaults", "read", plist, "CFBundleIdentifier"], timeout=10)
            if code == 0 and out.count(".") >= 1:
                publisher = out.strip().split(".")[1]
            entries.append((n, version, publisher))
    items += parse_mac_apps(entries)
    code, out, _ = _run(["brew", "list", "--versions"])
    if code == 0:
        items += parse_brew(out)
    return items, warnings


def collect_windows():
    ps = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32", "WindowsPowerShell", "v1.0", "powershell.exe")
    code, out, err = _run([ps, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", WIN_PS], timeout=240)
    if code != 0:
        return [], ["powershell : %s" % (err or code)]
    start = out.find("[")
    start2 = out.find("{")
    if start < 0 or (0 <= start2 < start):
        start = start2
    return parse_windows(out[start:] if start >= 0 else out), []


def collect_users():
    """Comptes ayant un répertoire personnel (affectation poste/utilisateur)."""
    users = []
    try:
        if sys.platform.startswith("win"):
            base = os.environ.get("SystemDrive", "C:") + "\\Users"
            users = [n for n in os.listdir(base) if n.lower() not in ("public", "default", "default user", "all users") and not n.startswith(".")]
        elif sys.platform == "darwin":
            users = [n for n in os.listdir("/Users") if not n.startswith(".") and n not in ("Shared",)]
        else:
            users = [n for n in os.listdir("/home") if not n.startswith(".")]
    except OSError:
        pass
    return sorted(users)[:200]


def collect():
    system = platform.system().lower()
    if system == "windows":
        items, warnings = collect_windows()
    elif system == "darwin":
        items, warnings = collect_mac()
    else:
        items, warnings = collect_linux()
    items = normalize(items)
    return {"os": system, "os_version": platform.release(), "hostname": platform.node(), "users": collect_users(),
            "installed": items, "count": len(items), "warnings": warnings, "collected_at": int(time.time())}


def main(argv):
    try:
        print(json.dumps(collect()))
    except Exception as exc:  # noqa: BLE001
        print(json.dumps({"error": "collecte échouée : %s" % exc}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
