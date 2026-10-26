#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sonde « systemes » (#861) : état des lieux des systèmes du SI interne HORS Proxmox (serveurs, NAS, frontaux, postes).
Sur l'hôte de l'agent et sur les hôtes de /etc/si-agent/systemes-remote.json ([{name, host, user, key, role}], ssh,
script sur l'entrée standard, lecture seule) : système, noyau, adresses, dernière mise à jour, correctifs en attente,
versions des paquets clés, ownCloud / Nextcloud, ports écoutés, connexions établies AGRÉGÉES (nombres : sert aux
dépendances et à la liste des serveurs utilisés par les postes), services actifs, requêtes web, comptes.
Hôte Windows (agent Windows) : système, build, dernier correctif installé, ports écoutés et processus, connexions
établies agrégées, services en marche. Des noms et des nombres seulement. Pur et testé : parse_systeme, parse_windows,
windows_os."""
import argparse
import datetime as dt
import json
import os
import re
import socket
import subprocess
import sys

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=30", "-o", "StrictHostKeyChecking=accept-new"]

# même relevé que pve-preflight (#857), exécuté par sh sur l'hôte
INVENTAIRE_SH = r"""LC_ALL=C; export LC_ALL
echo "@@node $(hostname -s 2>/dev/null)"
# #857 : état des lieux -- système, mises à jour, versions clés, services, usage, dépendances (noms et nombres seulement)
if [ -r /etc/os-release ]; then ( . /etc/os-release; echo "@@os ${ID:-?}|${VERSION_ID:-?}|${PRETTY_NAME:-?}" )
elif [ -r /etc/debian_version ]; then v=$(head -n 1 /etc/debian_version); echo "@@os debian|${v%%.*}|Debian GNU/Linux $v"
elif [ -r /etc/redhat-release ]; then v=$(head -n 1 /etc/redhat-release); echo "@@os rhel|$(echo "$v" | sed -n 's/[^0-9]*\([0-9]*\).*/\1/p')|$v"; fi
echo "@@kernel $(uname -r 2>/dev/null)"
I=$(hostname -I 2>/dev/null); [ -n "$(echo $I)" ] || I=$(ip -4 -o addr show scope global 2>/dev/null | awk '{sub(/\/.*/, "", $4); printf "%s ", $4}')
echo "@@ips $I"
echo "@@uptime $(cut -d. -f1 /proc/uptime 2>/dev/null)"
echo "@@disque $(df -P / 2>/dev/null | awk 'NR == 2 {sub(/%/, "", $5); print $5}')"
[ -f /var/lib/dpkg/status ] && echo "@@maj $(stat -c %Y /var/lib/dpkg/status 2>/dev/null)"
[ -f /var/cache/apt/pkgcache.bin ] && echo "@@listes $(stat -c %Y /var/cache/apt/pkgcache.bin 2>/dev/null)"
if command -v apt-get >/dev/null 2>&1; then
  U=$(apt-get -s -o Debug::NoLocking=1 upgrade 2>/dev/null | grep '^Inst ')
  if [ -n "$U" ]; then echo "@@attente $(printf '%s\n' "$U" | grep -c '^Inst ') $(printf '%s\n' "$U" | grep -ci 'securi')"; else echo "@@attente 0 0"; fi
  dpkg-query -W -f='${Status} ${Package} ${Version}\n' apache2 apache nginx 'php[0-9]*-common' php-common 'mariadb-server-[0-9]*' mariadb-server \
    'mysql-server-[0-9]*' 'postgresql-[0-9]*' postfix dovecot-core openssh-server docker-ce docker.io pve-manager proxmox-backup-server \
    redis-server nodejs python3 'openjdk-[0-9]*-jre-headless' 'tomcat[0-9]*' bind9 samba squid amavisd-new spamassassin roundcube-core \
    proftpd-basic proftpd vsftpd openssl 2>/dev/null | awk '$3 == "installed" {print "@@pkg", $4, $5}' | head -n 60
fi
for f in /var/www/*/version.php /var/www/*/*/version.php; do
  [ -f "$f" ] || continue
  v=$(sed -n "s/.*OC_VersionString *= *'\([^']*\)'.*/\1/p" "$f" | head -n 1)
  [ -n "$v" ] && echo "@@app $(grep -qi "vendor *= *'nextcloud'" "$f" && echo nextcloud || echo owncloud) $v"
done
if command -v ss >/dev/null 2>&1; then
  ss -ltnp 2>/dev/null | awk 'NR > 1 {a = $4; n = split(a, x, ":"); p = x[n]; h = substr(a, 1, length(a) - length(p) - 1); u = $0;
    if (sub(/.*users:\(\("/, "", u)) sub(/".*/, "", u); else u = "?"; print "@@ecoute", p, h, u}' | sort -u | head -n 80
  L=" $(ss -ltn 2>/dev/null | awk 'NR > 1 {n = split($4, x, ":"); print x[n]}' | sort -u | tr '\n' ' ') "
  ss -tn 2>/dev/null | awk -v L="$L" 'NR > 1 && $1 == "ESTAB" {n = split($4, a, ":"); lp = a[n]; m = split($5, b, ":"); rp = b[m];
    rh = substr($5, 1, length($5) - length(rp) - 1); gsub(/[][]/, "", rh); sub(/^::ffff:/, "", rh);
    if (rh ~ /^127\./ || rh == "::1") next;
    if (index(L, " " lp " ")) {cin[lp]++; k = lp " " rh; if (!(k in vu)) {vu[k] = 1; din[lp]++}} else cout[rh " " rp]++}
    END {for (p in cin) print "@@cnxin", p, cin[p], din[p]; for (k in cout) print "@@cnxout", k, cout[k]}' | head -n 120
fi
if ! command -v ss >/dev/null 2>&1 && command -v netstat >/dev/null 2>&1; then
  netstat -ltnp 2>/dev/null | awk '$1 ~ /^tcp/ {a = $4; n = split(a, x, ":"); p = x[n]; h = substr(a, 1, length(a) - length(p) - 1);
    u = $7; if (u == "" || u == "-") u = "?"; else sub(/^[0-9]+\//, "", u); print "@@ecoute", p, h, u}' | sort -u | head -n 80
  L=" $(netstat -ltn 2>/dev/null | awk '$1 ~ /^tcp/ {n = split($4, x, ":"); print x[n]}' | sort -u | tr '\n' ' ') "
  netstat -tn 2>/dev/null | awk -v L="$L" '$1 ~ /^tcp/ && $6 == "ESTABLISHED" {n = split($4, a, ":"); lp = a[n]; m = split($5, b, ":"); rp = b[m];
    rh = substr($5, 1, length($5) - length(rp) - 1); sub(/^::ffff:/, "", rh);
    if (rh ~ /^127\./ || rh == "::1") next;
    if (index(L, " " lp " ")) {cin[lp]++; k = lp " " rh; if (!(k in vu)) {vu[k] = 1; din[lp]++}} else cout[rh " " rp]++}
    END {for (p in cin) print "@@cnxin", p, cin[p], din[p]; for (k in cout) print "@@cnxout", k, cout[k]}' | head -n 120
fi
if ! command -v systemctl >/dev/null 2>&1; then
  N=$(runlevel 2>/dev/null | awk '{print $2}'); [ -d "/etc/rc${N:-2}.d" ] || N=2
  for f in /etc/rc${N:-2}.d/S*; do [ -e "$f" ] || continue; b=$(basename "$f"); echo "@@svc $(echo "$b" | sed 's/^S[0-9]*//')"; done | head -n 80
fi
command -v systemctl >/dev/null 2>&1 && systemctl list-units --type=service --state=running --no-legend 2>/dev/null | \
  awk '{u = $1; if (u !~ /^[A-Za-z0-9]/) u = $2; sub(/\.service$/, "", u); print "@@svc", u}' | head -n 80
R=0
for f in /var/log/apache2/*access*.log /var/log/nginx/*access*.log; do [ -f "$f" ] && R=$((R + $(wc -l < "$f"))); done
echo "@@req $R"
echo "@@comptes $(awk -F: '$3 >= 1000 && $3 < 65000 && $7 !~ /(nologin|false)$/' /etc/passwd 2>/dev/null | grep -c .)"
echo "@@fin"
"""

WINDOWS_PS = r"""
$ErrorActionPreference = 'SilentlyContinue'
$o = Get-CimInstance Win32_OperatingSystem
"@@os windows|$($o.Version)|$($o.Caption) $($o.Version)"
"@@build $($o.BuildNumber)"
"@@kernel $($o.Version)"
"@@uptime $([int]((Get-Date) - $o.LastBootUpTime).TotalSeconds)"
$h = Get-HotFix | Where-Object InstalledOn | Sort-Object InstalledOn | Select-Object -Last 1
if ($h) { "@@maj $([int][double]::Parse((Get-Date $h.InstalledOn -UFormat %s)))" }
"@@ips $((Get-NetIPAddress -AddressFamily IPv4 | Where-Object { $_.IPAddress -notlike '127.*' -and $_.IPAddress -notlike '169.254.*' }).IPAddress -join ' ')"
$p = @{}; Get-Process | ForEach-Object { $p[$_.Id] = $_.ProcessName }
Get-NetTCPConnection -State Listen | ForEach-Object { "@@ecoute $($_.LocalPort) $($_.LocalAddress) $($p[[int]$_.OwningProcess])" } | Sort-Object -Unique | Select-Object -First 80
$l = @{}; (Get-NetTCPConnection -State Listen).LocalPort | ForEach-Object { $l[[int]$_] = 1 }
$in = @{}; $cl = @{}; $out = @{}
Get-NetTCPConnection -State Established | Where-Object { $_.RemoteAddress -notlike '127.*' -and $_.RemoteAddress -ne '::1' } | ForEach-Object {
  $ra = $_.RemoteAddress -replace '^::ffff:', ''
  if ($l.ContainsKey([int]$_.LocalPort)) { $in[$_.LocalPort]++; $cl["$($_.LocalPort) $ra"] = 1 } else { $out["$ra $($_.RemotePort)"]++ } }
foreach ($k in $in.Keys) { "@@cnxin $k $($in[$k]) $(@($cl.Keys | Where-Object { $_ -like "$k *" }).Count)" }
foreach ($k in $out.Keys) { "@@cnxout $k $($out[$k])" }
Get-Service | Where-Object Status -eq 'Running' | Select-Object -First 80 | ForEach-Object { "@@svc $($_.Name)" }
"@@comptes $(@(Get-LocalUser | Where-Object Enabled).Count)"
"@@fin"
"""


def parse_systeme(text):
    """#857 : sortie de GUEST_SH (ou section « offline » d'un CT arrêté : lignes ID= / VERSION_ID= / PRETTY_NAME=) ->
    {os: {id, version, nom}, noyau, uptime_s, disque_pct, maj_at, listes_at, attente, attente_secu, paquets {nom: version},
    apps [{nom, version}], ecoute [{port, hote, proc}], cnx_in [{port, n, clients}], cnx_out [{hote, port, n}], services [],
    requetes, comptes} ; None si rien d'exploitable."""
    o = {"os": None, "noyau": None, "uptime_s": None, "disque_pct": None, "maj_at": None, "listes_at": None, "attente": None, "attente_secu": None,
         "paquets": {}, "apps": [], "ecoute": [], "cnx_in": [], "cnx_out": [], "services": [], "requetes": None, "comptes": None, "ips": []}
    env = {}
    vu = False
    for line in (text or "").splitlines():
        line = line.strip()
        m = re.match(r'^(ID|VERSION_ID|PRETTY_NAME)="?([^"]*)"?$', line)
        if m:
            env[m.group(1)] = m.group(2)
            vu = True
            continue
        if not line.startswith("@@"):
            continue
        k, _, v = line[2:].partition(" ")
        p = v.split()
        n = lambda i: int(p[i]) if len(p) > i and p[i].isdigit() else None  # noqa: E731
        vu = vu or k in ("os", "maj", "pkg", "ecoute", "svc")
        if k == "os":
            q = v.split("|")
            o["os"] = {"id": q[0] if q[0] != "?" else None, "version": q[1] if len(q) > 1 and q[1] != "?" else None, "nom": q[2] if len(q) > 2 else None}
        elif k == "kernel":
            o["noyau"] = v or None
        elif k == "uptime":
            o["uptime_s"] = n(0)
        elif k == "ips":
            o["ips"] = [x for x in p if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", x)]
        elif k == "disque":
            o["disque_pct"] = n(0)
        elif k == "maj":
            o["maj_at"] = n(0)
        elif k == "listes":
            o["listes_at"] = n(0)
        elif k == "attente":
            o["attente"], o["attente_secu"] = n(0), n(1)
        elif k == "pkg" and len(p) >= 2:
            o["paquets"][p[0]] = p[1]
        elif k == "app" and len(p) >= 2:
            o["apps"].append({"nom": p[0], "version": p[1]})
        elif k == "ecoute" and len(p) >= 2 and p[0].isdigit():
            e = {"port": int(p[0]), "hote": p[1], "proc": p[2] if len(p) > 2 else "?"}
            if e not in o["ecoute"]:
                o["ecoute"].append(e)
        elif k == "cnxin" and len(p) >= 3:
            o["cnx_in"].append({"port": n(0), "n": n(1), "clients": n(2)})
        elif k == "cnxout" and len(p) >= 3:
            o["cnx_out"].append({"hote": p[0], "port": n(1), "n": n(2)})
        elif k == "svc" and p:
            o["services"].append(p[0])
        elif k == "req":
            o["requetes"] = n(0)
        elif k == "comptes":
            o["comptes"] = n(0)
    if env:
        o["os"] = {"id": env.get("ID"), "version": env.get("VERSION_ID"), "nom": env.get("PRETTY_NAME")}
    return o if vu else None




def windows_os(caption, version):
    """« Microsoft Windows Server 2019 Standard », « 10.0.17763 » -> (famille, version) pour les dates de fin de support."""
    c = caption or ""
    m = re.search(r"Server (\d{4})(?: (R2))?", c)
    if m:
        return "windows-server", m.group(1) + ("r2" if m.group(2) else "")
    try:
        build = int(str(version).split(".")[2])
    except (IndexError, ValueError):
        build = 0
    return "windows", "11" if (build >= 22000 or "Windows 11" in c) else "10"


def parse_windows(text):
    o = parse_systeme(text)
    if o and o.get("os"):
        nom = o["os"].get("nom") or ""
        fam, ver = windows_os(nom, o["os"].get("version"))
        o["os"] = {"id": fam, "version": ver, "nom": nom.replace("Microsoft ", "")}
    return o


def _ssh(h, script, runner, timeout=300):
    if h.get("key") and not os.path.exists(h["key"]):
        raise RuntimeError("clé %s introuvable (la placer dans /etc/si-agent/keys/, chmod 600)" % h["key"])
    args = ["ssh"] + SSH_OPTS + [str(o) for o in (h.get("ssh_options") or [])] + (["-i", h["key"], "-o", "IdentitiesOnly=yes"] if h.get("key") else []) + ["%s@%s" % (h.get("user") or "root", h["host"]), "sh -s"]
    return runner(args, input=script, capture_output=True, text=True, timeout=timeout)


def releve_local(runner=subprocess.run):
    if sys.platform == "win32":
        p = runner(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", WINDOWS_PS], capture_output=True, text=True, timeout=300)
        return parse_windows(p.stdout)
    p = runner(["sh", "-s"], input=INVENTAIRE_SH, capture_output=True, text=True, timeout=300)
    return parse_systeme(p.stdout)


def main(argv=None, runner=subprocess.run):
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote", default="/etc/si-agent/systemes-remote.json")
    ap.add_argument("--role", default="", help="rôle de l'hôte local : serveur ou poste (défaut : déduit du système)")
    ap.add_argument("--no-local", action="store_true")
    a = ap.parse_args(argv)
    out = []
    if not a.no_local:
        try:
            s = releve_local(runner)
            nom = (socket.gethostname() or "local").split(".")[0]
            role = a.role or ("poste" if s and (s.get("os") or {}).get("id") == "windows" else "serveur")
            out.append({"name": nom.lower(), "zone": "local", "role": role, "ok": bool(s), "error": None if s else "relevé vide", "systeme": s})
        except Exception as e:  # noqa: BLE001
            out.append({"name": "local", "zone": "local", "ok": False, "error": str(e)[:200], "systeme": None})
    hosts = []
    if a.remote and os.path.exists(a.remote):
        try:
            with open(a.remote, encoding="utf-8") as fh:
                hosts = [h for h in json.load(fh) if isinstance(h, dict) and h.get("host")]
        except (OSError, ValueError):
            hosts = []
    for h in hosts:
        nom = h.get("name") or h["host"]
        try:
            p = _ssh(h, INVENTAIRE_SH, runner)
            s = parse_systeme(p.stdout)
            if not s:
                raise RuntimeError(((p.stderr or "").strip().splitlines() or ["relevé vide (code %d)" % p.returncode])[-1][:200])
            out.append({"name": nom, "zone": "distant", "role": h.get("role") or "serveur", "ok": True, "error": None, "systeme": s})
        except Exception as e:  # noqa: BLE001 -- un hôte injoignable n'empêche pas les autres
            out.append({"name": nom, "zone": "distant", "role": h.get("role") or "serveur", "ok": False, "error": str(e)[:200], "systeme": None})
    alerts = [{"code": "systeme-injoignable:%s" % x["name"], "severity": "warning", "message": "%s : relevé impossible (%s)" % (x["name"], x["error"])}
              for x in out if not x["ok"]]
    print(json.dumps({"at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "systemes": out, "alerts": alerts,
                      "summary": {"systemes": len(out), "ok": sum(1 for x in out if x["ok"])}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
