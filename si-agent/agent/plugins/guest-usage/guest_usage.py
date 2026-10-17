#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Activité des CT / VM de tous les Proxmox (#769) : pour chaque invité, dernier accès et fréquentation HTTP/HTTPS
(dont ownCloud), activité MySQL/MariaDB, connexions des comptes unix, charge processeur.

Un passage = UN script bash par nœud (local si /etc/pve existe, distants de pve-remote.json par ssh, script envoyé
sur l'entrée standard) qui, pour chaque invité :
  - lit la charge processeur dans les RRD du nœud (pvesh .../rrddata, jour et semaine) -- tous les invités ;
  - entre dans l'invité démarré (pct exec ; qm guest exec si l'agent invité répond) et y exécute GUEST_SH :
    journaux d'accès Apache / nginx AGRÉGÉS sur place par awk (par heure, par IP, dernier accès, accès ownCloud),
    `last` (wtmp), état MySQL par le compte de maintenance Debian (/etc/mysql/debian.cnf) ou root par socket.
Aucun mot de passe : root du nœud entre dans l'invité. Lecture seule. Jamais de ligne de journal brute remontée.
MySQL ne date pas les connexions : le compteur Connections est comparé d'un passage à l'autre (état local), ce qui
donne les connexions par jour et la dernière activité (à l'intervalle de passage près).
#771 : activité réelle DANS LE TEMPS -- bloc « days » : par jour et par service (web : requêtes et octets des humains,
visiteurs distincts, robots / supervision à part, ownCloud ; connexions unix ; MySQL : connexions, requêtes, octets ;
CPU / réseau / disque des RRD mois (par jour) et année (par semaine)). Reprise de l'historique : une fois par invité
(au plus un CT et une VM par nœud et par passage), TOUS les journaux d'accès encore présents (.gz compris, 800 j
au plus) et wtmp.1 sont résumés sur place. Le central (guestusage.ingest_daily) accumule ces jours : l'historique
continue de s'allonger après la rotation des journaux. Hors reprise, seuls les 3 derniers jours sont envoyés (et
les séries RRD complètes une fois par jour).
Pur et testé : parse_driver, parse_guest, parse_web, parse_days, parse_last, login_days, parse_mysql, rrd_stats,
rrd_days, rrd_weeks, mysql_step, build."""
import argparse
import datetime as dt
import json
import os
import re
import subprocess
import sys
import time

SSH_OPTS = ["-o", "BatchMode=yes", "-o", "ConnectTimeout=15", "-o", "ServerAliveInterval=30", "-o", "StrictHostKeyChecking=accept-new"]
OWN_MYSQL_CONN = 3          # connexions ouvertes par GUEST_SH à chaque passage (status, proc, version)
OWN_MYSQL_Q = 3             # requêtes envoyées par GUEST_SH à chaque passage
KEEP_DAYS = 14
RECENT_DAYS = 3             # #771 : jours envoyés hors reprise (le central garde l'historique)
DEEP_PER_PASS = 1          # reprises d'historique par nœud, par type (CT / VM) et par passage

GUEST_SH = r"""LC_ALL=C; export LC_ALL
echo "## os"; ( . /etc/os-release 2>/dev/null; echo "${PRETTY_NAME:-?}" )
echo "## web"
L=""
for f in /var/log/apache2/*access*.log /var/log/nginx/*access*.log /var/log/httpd/*access_log; do
  [ -f "$f" ] || continue
  [ -f "$f.1" ] && L="$L $f.1"
  L="$L $f"
done
for f in $L; do echo "F $f"; done
[ -n "$L" ] && for f in $L; do tail -n 40000 "$f" 2>/dev/null; done | awk '
BEGIN { split("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec", M, " "); for (i = 1; i <= 12; i++) m[M[i]] = sprintf("%02d", i) }
{ t = $4; if (substr(t, 1, 1) != "[") next; t = substr(t, 2); tz = substr($5, 1, 5)
  n = split(t, a, "[/:]"); if (n < 6 || !(a[2] in m)) next
  k = a[3] m[a[2]] a[1] a[4] a[5] a[6]; h = substr(k, 1, 10) tz
  H[h]++
  if ($7 ~ /(remote|public|status)\.php|\/ocs\/v[12]|index\.php\/login/) { O[h]++; if (k >= ok) { ok = k; ou = $3; otz = tz } }
  if (k >= lk) { lk = k; li = $1; ltz = tz }
  c[$1]++; if (k >= ik[$1]) { ik[$1] = k; iz[$1] = tz } }
END { for (h in H) print "H", h, H[h], O[h] + 0
      if (lk != "") print "L", lk ltz, li
      if (ok != "") print "O", ok otz, ou
      for (i in c) print "I", i, c[i], ik[i] iz[i] }' | sort -k1,1 -k3,3nr | awk '$1 != "I" || n++ < 60'
echo "## days"
echo "M deep ${SI_DEEP:-0}"
D=""
for f in /var/log/apache2/*access*.log* /var/log/nginx/*access*.log* /var/log/httpd/*access_log*; do
  [ -f "$f" ] || continue
  case "$f" in
    *.log|*.log.1|*access_log|*access_log.1) D="$D $f" ;;
    *) [ "${SI_DEEP:-0}" = 1 ] && [ -n "$(find "$f" -mtime -800 2>/dev/null)" ] && D="$D $f" ;;
  esac
done
[ -n "$D" ] && for f in $D; do zcat -f "$f" 2>/dev/null; done | awk '
BEGIN { split("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec", M, " "); for (i = 1; i <= 12; i++) m[M[i]] = sprintf("%02d", i)
        bot = "bot|crawl|spider|slurp|monitor|nagios|zabbix|uptime|check_http|curl|wget|python|go-http|java/|libwww|httpclient|okhttp|si-agent|zgrab|masscan|nmap|scan|headless|pingdom|statuscake|preview|fetch" }
{ t = $4; if (substr(t, 1, 1) != "[") next; split(substr(t, 2), a, "[/:]"); if (!(a[2] in m)) next
  d = a[3] m[a[2]] a[1]; n = split($0, q, "\""); ua = (n >= 6) ? tolower(q[6]) : ""
  b = ($10 ~ /^[0-9]+$/) ? $10 : 0
  if ($1 == "127.0.0.1" || $1 == "::1" || ua == "" || ua == "-" || ua ~ bot) { X[d]++; XB[d] += b; next }
  R[d]++; B[d] += b; if (!((d, $1) in U)) { U[d, $1] = 1; V[d]++ }
  if ($7 ~ /(remote|public|status)\.php|\/ocs\/v[12]|index\.php\/login/) O[d]++ }
END { for (d in R) S[d] = 1; for (d in X) S[d] = 1
      for (d in S) print "W", d, R[d] + 0, B[d] + 0, X[d] + 0, XB[d] + 0, V[d] + 0, O[d] + 0 }'
echo "## login"
if [ "${SI_DEEP:-0}" = 1 ]; then
  for w in /var/log/wtmp /var/log/wtmp.1; do [ -f "$w" ] && last -F -w -f "$w" 2>/dev/null | head -n 20000; done
else
  ( last -F -w -n 300 2>/dev/null || last -n 300 2>/dev/null ) | head -n 300
fi
if command -v mysql >/dev/null 2>&1; then
  M="mysql -N -B"; [ -r /etc/mysql/debian.cnf ] && M="mysql --defaults-file=/etc/mysql/debian.cnf -N -B"
  echo "## mysql status"
  $M -e "SHOW GLOBAL STATUS WHERE Variable_name IN ('Uptime','Connections','Questions','Threads_connected','Max_used_connections','Aborted_connects','Bytes_received','Bytes_sent')" 2>&1 | head -n 20
  echo "## mysql proc"
  $M -e "SELECT USER, SUBSTRING_INDEX(HOST, ':', 1), IFNULL(DB, ''), COMMAND, TIME FROM information_schema.PROCESSLIST WHERE ID <> CONNECTION_ID()" 2>&1 | head -n 300
  echo "## mysql version"; $M -e "SELECT VERSION()" 2>&1 | head -n 1
fi
echo "## internal"
# 777 : activite interne en lecture seule -- SSH, sudo, postfix, fichiers modifies par jour, journaux recents, connexions, processus
LG=${SI_LOG:-/var/log}; DATA=${SI_DATA:-/home /var/www /srv /var/mail /var/vmail /var/lib/owncloud /var/lib/nextcloud}
DP=${SI_DEEP:-0}; A=""
for f in "$LG/auth.log" "$LG/secure" "$LG/mail.log" "$LG/maillog"; do
  [ "$DP" = 1 ] && for g in "$f".*.gz "$f"-*.gz; do [ -f "$g" ] && A="$A $g"; done
  [ -f "$f.1" ] && A="$A $f.1"; [ -f "$f" ] && A="$A $f"
done
if [ -n "$A" ]; then for f in $A; do zcat -f "$f" 2>/dev/null; done
elif command -v journalctl >/dev/null 2>&1; then journalctl -q --no-pager -o short-iso --since "-$([ "$DP" = 1 ] && echo 800 || echo 4)d" 2>/dev/null | grep -E 'sshd|sudo|postfix'
fi | awk -v Y="$(date +%Y)" -v MN="$(date +%m)" '
BEGIN { split("Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec", M, " "); for (i = 1; i <= 12; i++) m[M[i]] = sprintf("%02d", i) }
{ if ($1 ~ /^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]T/) { d = substr($1, 1, 10); tm = substr($1, 12, 8) }
  else if ($1 in m) { mm = m[$1]; y = (mm > MN) ? Y - 1 : Y; d = sprintf("%s-%s-%02d", y, mm, $2); tm = $3 }
  else next
  if ($0 ~ /sshd\[[0-9]+\]: Accepted /) { u = ""; ip = ""
      for (i = 1; i <= NF; i++) { if ($i == "for" && u == "") u = $(i + 1); if ($i == "from") ip = $(i + 1) }
      S[d]++; if (!((d, u) in SU)) { SU[d, u] = 1; SN[d]++ }; k = d " " tm; if (k >= lk) { lk = k; lu = u; li = ip } }
  else if ($0 ~ /sudo(\[[0-9]+\])?: .*COMMAND=/) { U[d]++; k = d " " tm; if (k >= uk) uk = k }
  else if ($0 ~ /postfix\/[a-z]+\[[0-9]+\]: .*status=sent/) { P[d]++; k = d " " tm; if (k >= pk) pk = k } }
END { for (d in S) print "S", d, S[d], SN[d] + 0
      if (lk != "") print "SL", lk, lu, li
      for (d in U) print "U", d, U[d]
      if (uk != "") print "UL", uk
      for (d in P) print "P", d, P[d]
      if (pk != "") print "PL", pk }'
FD=""; for d in $DATA; do [ -d "$d" ] && FD="$FD $d"; done
if [ -n "$FD" ]; then
  if [ "$DP" = 1 ]; then ND=800; TF=150; else ND=4; TF=20; fi
  timeout $TF find $FD -xdev \( -type d \( -name cache -o -name .cache -o -name sessions -o -name tmp -o -name .git -o -name node_modules \) -prune \) \
    -o \( -type f -mtime -$ND ! -name '*.log' ! -name '*.lock' ! -name '*.pid' -printf '%TY-%Tm-%Td %h\n' \) 2>/dev/null | awk -v R="$FD" '
    BEGIN { nr = split(R, rs, " ") }
    { c[$1]++; t = $2; for (i = 1; i <= nr; i++) if (index($2, rs[i]) == 1) { split(substr($2, length(rs[i]) + 2), q, "/"); t = rs[i] (q[1] != "" ? "/" q[1] : ""); break }
      if ($1 >= ld) { ld = $1; lt = t } }
    END { for (d in c) print "M", d, c[d]; if (ld != "") print "ML", ld, lt }'
fi
find "$LG" -xdev -type f -mmin -1440 ! -name '*.gz' ! -name '*.[0-9]' ! -name 'wtmp*' ! -name 'lastlog' -printf 'G %T@ %s %p\n' 2>/dev/null | sort -k2,2nr | head -n 12
if command -v ss >/dev/null 2>&1; then ss -Htn state established 2>/dev/null | awk '{print $3, $4}'
else netstat -tn 2>/dev/null | awk '$6 == "ESTABLISHED" {print $4, $5}'; fi | awk '
  { r = $2; sub(/:[0-9]+$/, "", r); n = split($1, a, ":"); p = a[n] + 0
    if (p >= 32768 || r ~ /^(127\.|\[?::1|\[?::ffff:127\.)/) next
    C[p]++; if (!((p, r) in R)) { R[p, r] = 1; D[p]++ } }
  END { for (p in C) print "C", p, C[p], D[p] }'
ps -eo comm=,time= --sort=-time 2>/dev/null | head -n 5 | awk '{print "T", $1, $2}'
echo "## end"
"""

# Tout le script est une fonction lue en entier par `bash -s` puis exécutée entrée standard fermée : sans cela,
# pct / qm / pvesh avaleraient la suite du script envoyé sur l'entrée standard.
DRIVER_SH = r"""si_main() {
N=$(basename "$(readlink -f /etc/pve/local 2>/dev/null)" 2>/dev/null)
[ -n "$N" ] && [ "$N" != "local" ] || N=$(hostname -s)
echo "@@node $N"
# #777 : script de l'invité écrit dans un fichier et passé aux CT par l'ENTRÉE STANDARD de `pct exec ... sh -s` : le pct de
# PVE 5.4 perd un argument de plusieurs lignes (« sh: 0: -c requires an argument ») ; les VM gardent qm guest exec sh -c.
GF=$(mktemp /tmp/si-gu.XXXXXX)
cat > "$GF" <<'__SI_GUEST__'
%s
__SI_GUEST__
G=$(cat "$GF")
[ -n "$G" ] || { echo "@@error script de l invite vide"; return 1; }
DONE=" __SI_DONE__ "
# reprise d'historique : un invité pas encore repris, au plus DEEP_PER_PASS par boucle (CT, VM)
deep() { P=""; T=60; case "$DONE" in *" $1 "*) return ;; esac; [ "${NDEEP:-0}" -ge __SI_NDEEP__ ] && return; P="SI_DEEP=1; export SI_DEEP; "; T=420; NDEEP=$(( ${NDEEP:-0} + 1 )); }
rrd() { for tf in day week month year; do echo "## rrd $tf"; pvesh get /nodes/$N/$1/$2/rrddata --timeframe $tf --cf AVERAGE --output-format json </dev/null 2>/dev/null | head -c 200000; echo; done; }
pct list 2>/dev/null | awk 'NR>1 {print $1, $2, $NF}' | while read id st name; do
  echo "=== lxc $id $st $name"; rrd lxc $id
  [ "$st" = running ] && { deep $id; echo "## exec"; { printf '%%s' "$P"; cat "$GF"; } | timeout $T pct exec $id -- sh -s 2>&1 | head -c 3000000; echo; }
done
qm list 2>/dev/null | awk 'NR>1 {print $1, $3, $2}' | while read id st name; do
  echo "=== qemu $id $st $name"; rrd qemu $id
  [ "$st" = running ] && { deep $id; echo "## qga"; timeout $T qm guest exec $id --timeout $((T - 10)) -- sh -c "$P$G" </dev/null 2>&1 | head -c 4000000; echo; }
done
rm -f "$GF"
echo "@@done"
}
si_main </dev/null
"""


def driver_script(done=(), ndeep=DEEP_PER_PASS):
    """done : vmid dont l'historique est déjà repris (pas de nouvelle reprise)."""
    return (DRIVER_SH % GUEST_SH.rstrip("\n")).replace("__SI_DONE__", " ".join(str(int(i)) for i in sorted(done, key=int))).replace("__SI_NDEEP__", str(int(ndeep)))


# ---------------------------------------------------------------- découpage

def parse_driver(text):
    """Sortie d'un nœud -> (nom du nœud, [{type, vmid, status, name, sections: {clé: texte}}], complet ?)."""
    node, guests, cur, sec, done = None, [], None, None, False
    for line in (text or "").splitlines():
        if line.startswith("@@node "):
            node = line[7:].strip() or None
            continue
        if line.strip() == "@@done":
            done = True
            continue
        m = re.match(r"^=== (lxc|qemu) (\d+) (\S+)\s*(.*)$", line)
        if m:
            cur = {"type": m.group(1), "vmid": int(m.group(2)), "status": m.group(3), "name": m.group(4).strip(), "sections": {}}
            guests.append(cur)
            sec = None
            continue
        if cur is None:
            continue
        m = re.match(r"^## (rrd day|rrd week|rrd month|rrd year|exec|qga)$", line.strip())
        if m:
            sec = m.group(1)
            cur["sections"][sec] = []
            continue
        if sec:
            cur["sections"][sec].append(line)
    for g in guests:
        g["sections"] = {k: "\n".join(v) for k, v in g["sections"].items()}
    return node, guests, done


def unwrap_qga(text):
    """Sortie de `qm guest exec` (JSON {exitcode, out-data, err-data}) -> (texte, erreur)."""
    t = (text or "").strip()
    i = t.find("{")
    if i < 0:
        return "", (t.splitlines() or ["agent invité absent"])[-1][:160] or "agent invité absent"
    try:
        d = json.loads(t[i:])
    except ValueError:
        return "", "réponse de l'agent invité illisible"
    return d.get("out-data") or "", None if d.get("exited", 1) else "commande interrompue dans l'invité"


def parse_guest(text):
    """Sortie de GUEST_SH -> {clé de section: texte} (os, web, login, mysql status, mysql proc, mysql version, end)."""
    out, sec = {}, None
    for line in (text or "").splitlines():
        m = re.match(r"^## (os|web|days|login|mysql status|mysql proc|mysql version|internal|end)$", line.strip())
        if m:
            sec = m.group(1)
            out[sec] = []
            continue
        if sec:
            out[sec].append(line)
    return {k: "\n".join(v) for k, v in out.items()}


# ---------------------------------------------------------------- HTTP

def _web_time(k):
    """« 20261013101112+0200 » -> datetime UTC (None si illisible)."""
    m = re.match(r"^(\d{14})([+-]\d{4})?$", k or "")
    if not m:
        return None
    try:
        d = dt.datetime.strptime(m.group(1), "%Y%m%d%H%M%S")
        if m.group(2):
            off = int(m.group(2)[1:3]) * 60 + int(m.group(2)[3:5])
            d -= dt.timedelta(minutes=off if m.group(2)[0] == "+" else -off)
        return d.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def _hour_time(h):
    """« 2026101310+0200 » -> datetime UTC du début de l'heure."""
    m = re.match(r"^(\d{10})([+-]\d{4})?$", h or "")
    return _web_time(m.group(1) + "0000" + (m.group(2) or "")) if m else None


def _iso(d):
    return d.strftime("%Y-%m-%dT%H:%M:%SZ") if d else None


def parse_web(text, now):
    """Section web (lignes F/H/L/O/I agrégées par awk dans l'invité) -> résumé ; None si aucun journal d'accès."""
    files, hours, last, oc_last, ips = [], [], None, None, []
    for line in (text or "").splitlines():
        p = line.split()
        if not p:
            continue
        if p[0] == "F" and len(p) >= 2:
            files.append(p[1])
        elif p[0] == "H" and len(p) >= 4:
            t = _hour_time(p[1])
            if t:
                hours.append((t, int(p[2]), int(p[3])))
        elif p[0] == "L" and len(p) >= 2:
            last = {"at": _iso(_web_time(p[1])), "ip": p[2] if len(p) >= 3 else None}
        elif p[0] == "O" and len(p) >= 2:
            oc_last = {"at": _iso(_web_time(p[1])), "user": p[2] if len(p) >= 3 and p[2] != "-" else None}
        elif p[0] == "I" and len(p) >= 4:
            ips.append({"ip": p[1], "hits": int(p[2]), "last_at": _iso(_web_time(p[3]))})
    if not files:
        return None
    day, week = now - dt.timedelta(hours=24), now - dt.timedelta(days=7)
    per_day = {}
    for t, n, oc in hours:
        if t >= now - dt.timedelta(days=KEEP_DAYS):
            d = per_day.setdefault(t.strftime("%Y-%m-%d"), {"day": t.strftime("%Y-%m-%d"), "hits": 0, "owncloud": 0})
            d["hits"] += n
            d["owncloud"] += oc
    oc7 = sum(oc for t, _n, oc in hours if t >= week)
    return {"files": files, "last": last, "hits24": sum(n for t, n, _o in hours if t >= day), "hits7d": sum(n for t, n, _o in hours if t >= week),
            "per_day": sorted(per_day.values(), key=lambda x: x["day"]), "ips": ips[:60],
            "owncloud": {"last_at": (oc_last or {}).get("at"), "last_user": (oc_last or {}).get("user"), "hits7d": oc7} if oc_last or oc7 else None}


def parse_days(text):
    """Bloc days (lignes W de l'awk, jour local de l'invité) -> ([{day, req, bytes, bot, bot_bytes, visitors, owncloud}], reprise ?).
    req / bytes / visitors : humains ; bot / bot_bytes : robots, supervision, outils (curl, wget…) et boucle locale."""
    out, deep = [], False
    for line in (text or "").splitlines():
        p = line.split()
        if len(p) >= 3 and p[0] == "M" and p[1] == "deep":
            deep = p[2] == "1"
        elif len(p) >= 8 and p[0] == "W" and re.match(r"^\d{8}$", p[1]):
            try:
                v = [int(x) for x in p[2:8]]
            except ValueError:
                continue
            out.append({"day": "%s-%s-%s" % (p[1][:4], p[1][4:6], p[1][6:]), "req": v[0], "bytes": v[1], "bot": v[2],
                        "bot_bytes": v[3], "visitors": v[4], "owncloud": v[5]})
    return sorted(out, key=lambda d: d["day"]), deep


# ---------------------------------------------------------------- #777 : activité interne

def parse_internal(text, now):
    """Section internal -> (résumé, jours). résumé : {ssh: {last, users24h…}, sudo_last, mail_last, files: {last_day, last_dir},
    logs: [{path, at, size}], conns: [{port, n, peers}], top: [{comm, time}]} ; jours : {ssh, sudo, mail, files} par jour."""
    days = {"ssh": {}, "sudo": {}, "mail": {}, "files": {}}
    res = {"ssh_last": None, "sudo_last": None, "mail_last": None, "files_last": None, "logs": [], "conns": [], "top": []}
    for line in (text or "").splitlines():
        p = line.split()
        if not p:
            continue
        try:
            if p[0] == "S" and len(p) >= 4:
                days["ssh"][p[1]] = {"day": p[1], "logins": int(p[2]), "users": int(p[3])}
            elif p[0] == "SL" and len(p) >= 3:
                res["ssh_last"] = {"at": "%sT%s" % (p[1], p[2]), "user": p[3] if len(p) > 3 else None, "from": p[4] if len(p) > 4 else None}
            elif p[0] == "U" and len(p) >= 3:
                days["sudo"][p[1]] = {"day": p[1], "cmds": int(p[2])}
            elif p[0] == "UL" and len(p) >= 3:
                res["sudo_last"] = "%sT%s" % (p[1], p[2])
            elif p[0] == "P" and len(p) >= 3:
                days["mail"][p[1]] = {"day": p[1], "sent": int(p[2])}
            elif p[0] == "PL" and len(p) >= 3:
                res["mail_last"] = "%sT%s" % (p[1], p[2])
            elif p[0] == "M" and len(p) >= 3:
                days["files"][p[1]] = {"day": p[1], "files": int(p[2])}
            elif p[0] == "ML" and len(p) >= 2:
                res["files_last"] = {"day": p[1], "dir": p[2] if len(p) > 2 else None}
            elif p[0] == "G" and len(p) >= 4:
                res["logs"].append({"at": _iso(dt.datetime.fromtimestamp(float(p[1]), dt.timezone.utc)), "size": int(p[2]), "path": " ".join(p[3:])[:200]})
            elif p[0] == "C" and len(p) >= 4:
                res["conns"].append({"port": int(p[1]), "n": int(p[2]), "peers": int(p[3])})
            elif p[0] == "T" and len(p) >= 3:
                res["top"].append({"comm": p[1][:40], "time": p[2]})
        except (ValueError, OverflowError):
            continue
    res["conns"].sort(key=lambda c: -c["n"])
    if res["ssh_last"] is None and res["sudo_last"] is None and res["mail_last"] is None and res["files_last"] is None and not res["logs"] and not res["conns"]:
        res = None
    return res, {k: sorted(v.values(), key=lambda d: d["day"]) for k, v in days.items()}


# ---------------------------------------------------------------- connexions (wtmp)

LAST_DATE = re.compile(r"\b(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) +(\d{1,2}) (\d{2}:\d{2})(?::(\d{2}))? ?(\d{4})?")


def _last_rows(text, now):
    rows = []
    for line in (text or "").splitlines():
        if not line.strip() or line.startswith(("wtmp", "btmp")) or line.split()[0] in ("reboot", "shutdown", "runlevel"):
            continue
        m = LAST_DATE.search(line)
        if not m:
            continue
        head = line[:m.start()].split()
        user = head[0] if head else "?"
        frm = head[2] if len(head) >= 3 else None
        year = int(m.group(6)) if m.group(6) else now.year
        try:
            t = dt.datetime.strptime("%d %s %s %s:%s" % (year, m.group(2), m.group(3), m.group(4), m.group(5) or "00"), "%Y %b %d %H:%M:%S")
        except ValueError:
            continue
        if not m.group(6) and t > now.replace(tzinfo=None) + dt.timedelta(days=1):
            t = t.replace(year=year - 1)          # `last` court : décembre lu en janvier
        rows.append({"user": user, "from": frm if frm and not frm.startswith(":") else None, "at": t})
    return rows


def login_days(rows):
    """Sessions -> [{day, logins, users}] (jour local de l'invité), tout l'historique lu."""
    days = {}
    for r in rows:
        d = days.setdefault(r["at"].strftime("%Y-%m-%d"), [0, set()])
        d[0] += 1
        d[1].add(r["user"])
    return [{"day": k, "logins": v[0], "users": len(v[1])} for k, v in sorted(days.items())]


def parse_last(text, now, rows=None):
    """Sortie de `last -F -w` (ou `last` court, année absente) -> {last, users, per_day, count7d} ; heure locale de l'invité."""
    rows = _last_rows(text, now) if rows is None else rows
    if not rows:
        return {"last": None, "users": [], "per_day": [], "count7d": 0}
    naive_now = now.replace(tzinfo=None)
    users = {}
    for r in rows:
        u = users.setdefault(r["user"], {"user": r["user"], "last_at": None, "from": None, "count7d": 0, "count": 0})
        u["count"] += 1
        if u["last_at"] is None or r["at"] > u["last_at"]:
            u["last_at"], u["from"] = r["at"], r["from"]
        if r["at"] >= naive_now - dt.timedelta(days=7):
            u["count7d"] += 1
    per_day = {}
    for r in rows:
        if r["at"] >= naive_now - dt.timedelta(days=KEEP_DAYS):
            k = r["at"].strftime("%Y-%m-%d")
            per_day[k] = per_day.get(k, 0) + 1
    last = max(rows, key=lambda r: r["at"])
    fmt = lambda d: d.strftime("%Y-%m-%dT%H:%M:%S")
    return {"last": {"user": last["user"], "from": last["from"], "at": fmt(last["at"])},
            "users": [dict(u, last_at=fmt(u["last_at"])) for u in sorted(users.values(), key=lambda u: u["last_at"], reverse=True)][:30],
            "per_day": [{"day": k, "logins": v} for k, v in sorted(per_day.items())], "count7d": sum(u["count7d"] for u in users.values())}


# ---------------------------------------------------------------- MySQL

def parse_mysql(status, proc, version):
    """Sections mysql -> {ok, error, version, uptime_s, connections, questions, threads_connected, max_used, sessions}."""
    txt = "\n".join(x for x in (status, proc) if x)
    m = re.search(r"ERROR \d+.*", txt)
    if m:
        return {"ok": False, "error": m.group(0)[:200], "sessions": []}
    st = {}
    for line in (status or "").splitlines():
        p = line.split()
        if len(p) == 2 and p[1].isdigit():
            st[p[0]] = int(p[1])
    sessions = []
    for line in (proc or "").splitlines():
        p = line.split("\t")
        if len(p) >= 5 and p[0] not in ("system user", "event_scheduler", "debian-sys-maint"):
            sessions.append({"user": p[0], "host": p[1], "db": p[2] or None, "command": p[3], "time_s": int(p[4]) if p[4].isdigit() else None})
    if not st:
        return {"ok": False, "error": "état MySQL illisible", "sessions": []}
    return {"ok": True, "error": None, "version": (version or "").strip().splitlines()[0][:60] if (version or "").strip() else None,
            "uptime_s": st.get("Uptime"), "connections": st.get("Connections"), "questions": st.get("Questions"),
            "threads_connected": st.get("Threads_connected"), "max_used": st.get("Max_used_connections"),
            "aborted_connects": st.get("Aborted_connects"), "bytes_in": st.get("Bytes_received"), "bytes_out": st.get("Bytes_sent"),
            "sessions": sessions[:50]}


def mysql_step(my, prev, now):
    """Compare le passage courant au précédent (état local) -> (champs ajoutés au résumé, nouvel état).
    Connexions extérieures = hausse du compteur - connexions de la sonde ; redémarrage (Uptime recule) = repart du compteur."""
    ts = now.timestamp()
    prev = prev or {}
    st = {"connections": my.get("connections"), "questions": my.get("questions"), "uptime_s": my.get("uptime_s"), "at": ts,
          "per_day": dict(prev.get("per_day") or {}), "last_activity_at": prev.get("last_activity_at"), "users": dict(prev.get("users") or {}),
          "qday": dict(prev.get("qday") or {}), "bday": dict(prev.get("bday") or {}),
          "bytes": (my.get("bytes_in") or 0) + (my.get("bytes_out") or 0) if my.get("bytes_in") is not None else None}
    ext = None
    today = now.strftime("%Y-%m-%d")
    restarted = (my.get("uptime_s") or 0) < (prev.get("uptime_s") or 0)
    if prev.get("questions") is not None and my.get("questions") is not None:   # #771 : requêtes et octets par jour
        dq = my["questions"] if restarted else my["questions"] - prev["questions"]
        st["qday"][today] = st["qday"].get(today, 0) + max(0, dq - OWN_MYSQL_Q)
    if prev.get("bytes") is not None and st["bytes"] is not None:
        db = st["bytes"] if restarted else st["bytes"] - prev["bytes"]
        st["bday"][today] = st["bday"].get(today, 0) + max(0, db)
    if prev.get("connections") is not None and my.get("connections") is not None:
        restarted = (my.get("uptime_s") or 0) < (prev.get("uptime_s") or 0)
        delta = my["connections"] if restarted else my["connections"] - prev["connections"]
        ext = max(0, delta - OWN_MYSQL_CONN)
        if ext > 0:
            k = now.strftime("%Y-%m-%d")
            st["per_day"][k] = st["per_day"].get(k, 0) + ext
            st["last_activity_at"] = _iso(now)
    for s in my.get("sessions") or []:
        st["users"][s["user"]] = _iso(now)
        st["last_activity_at"] = _iso(now)
    cut = (now - dt.timedelta(days=KEEP_DAYS)).strftime("%Y-%m-%d")
    st["per_day"] = {k: v for k, v in st["per_day"].items() if k >= cut}
    st["qday"] = {k: v for k, v in st["qday"].items() if k >= cut}
    st["bday"] = {k: v for k, v in st["bday"].items() if k >= cut}
    cut60 = _iso(now - dt.timedelta(days=60))
    st["users"] = {u: t for u, t in st["users"].items() if t >= cut60}
    window = int(ts - prev["at"]) if prev.get("at") else None
    add = {"conn_since_last": ext, "window_s": window, "last_activity_at": st["last_activity_at"],
           "per_day": [{"day": k, "connections": v} for k, v in sorted(st["per_day"].items())],
           "days": [{"day": k, "connections": st["per_day"].get(k, 0), "questions": st["qday"].get(k, 0), "bytes": st["bday"].get(k, 0)}
                    for k in sorted(set(st["per_day"]) | set(st["qday"]) | set(st["bday"]))],
           "conn7d": sum(v for k, v in st["per_day"].items() if k >= (now - dt.timedelta(days=7)).strftime("%Y-%m-%d")),
           "users_seen": [{"user": u, "last_seen": t} for u, t in sorted(st["users"].items(), key=lambda x: x[1], reverse=True)][:30]}
    return add, st


# ---------------------------------------------------------------- charge processeur

def rrd_stats(day_text, week_text, now):
    """rrddata (JSON, jour et semaine) -> {cpu_now, cpu_avg24, cpu_max24, cpu_avg7d, ncpu, netin24, netout24} en % de l'invité."""
    def load(t):
        try:
            v = json.loads((t or "").strip() or "[]")
            return [r for r in v if isinstance(r, dict) and r.get("time")] if isinstance(v, list) else []
        except ValueError:
            return []
    d, w = load(day_text), load(week_text)
    ts = now.timestamp()
    d24 = [r for r in d if r["time"] >= ts - 86400 and isinstance(r.get("cpu"), (int, float))]
    w7 = [r for r in w if r["time"] >= ts - 7 * 86400 and isinstance(r.get("cpu"), (int, float))]
    pct = lambda x: round(100.0 * x, 1)
    out = {"cpu_now": pct(d24[-1]["cpu"]) if d24 else None, "cpu_avg24": pct(sum(r["cpu"] for r in d24) / len(d24)) if d24 else None,
           "cpu_max24": pct(max(r["cpu"] for r in d24)) if d24 else None,
           "cpu_avg7d": pct(sum(r["cpu"] for r in w7) / len(w7)) if w7 else None,
           "ncpu": next((r.get("maxcpu") for r in reversed(d24) if r.get("maxcpu")), None),
           "cpu_series": [{"t": int(r["time"]), "cpu": pct(r["cpu"])} for r in w7][-60:]}
    if len(d24) >= 2:   # débits moyens (octets/s) × durée de chaque point
        step = (d24[-1]["time"] - d24[0]["time"]) / (len(d24) - 1)
        out["netin24"] = int(sum((r.get("netin") or 0) for r in d24) * step)
        out["netout24"] = int(sum((r.get("netout") or 0) for r in d24) * step)
    return out


def _rrd_points(text):
    try:
        v = json.loads((text or "").strip() or "[]")
    except ValueError:
        return []
    return sorted((r for r in v if isinstance(r, dict) and isinstance(r.get("time"), (int, float))), key=lambda r: r["time"]) if isinstance(v, list) else []


def _rrd_step(pts, default):
    if len(pts) < 2:
        return default
    d = sorted(pts[i + 1]["time"] - pts[i]["time"] for i in range(len(pts) - 1))
    return d[len(d) // 2] or default


def _rrd_bucket(pts, step):
    """Points -> {cpu %, netin, netout, diskread, diskwrite en octets} (débits moyens × durée)."""
    cpu = [r["cpu"] for r in pts if isinstance(r.get("cpu"), (int, float))]
    out = {"cpu": round(100.0 * sum(cpu) / len(cpu), 2) if cpu else None}
    for k in ("netin", "netout", "diskread", "diskwrite"):
        v = [r[k] for r in pts if isinstance(r.get(k), (int, float))]
        out[k] = int(sum(v) * step) if v else None
    return out


def rrd_days(month_text):
    """RRD « month » (un point par 12 h environ) -> [{day (UTC), cpu, netin, netout, diskread, diskwrite}]."""
    pts = _rrd_points(month_text)
    step, days = _rrd_step(pts, 43200), {}
    for r in pts:
        days.setdefault(dt.datetime.fromtimestamp(r["time"], dt.timezone.utc).strftime("%Y-%m-%d"), []).append(r)
    return [dict(day=k, **_rrd_bucket(v, step)) for k, v in sorted(days.items())]


def rrd_weeks(year_text):
    """RRD « year » (un point par semaine) -> [{week (jour UTC du point), cpu, netin, netout, diskread, diskwrite}]."""
    pts = _rrd_points(year_text)
    step = _rrd_step(pts, 7 * 86400)
    return [dict(week=dt.datetime.fromtimestamp(r["time"], dt.timezone.utc).strftime("%Y-%m-%d"), **_rrd_bucket([r], step)) for r in pts]


def trim_days(lst, now, key="day", days=RECENT_DAYS):
    cut = (now - dt.timedelta(days=days)).strftime("%Y-%m-%d")
    return [d for d in lst or [] if (d.get(key) or "") >= cut]


# ---------------------------------------------------------------- assemblage

def build(node_name, guests, state, now, full=True):
    """Invités découpés -> (invités résumés, nouvel état de ce nœud). full : séries RRD complètes (une fois par jour) ;
    sinon seuls les RECENT_DAYS derniers jours sont envoyés, sauf pour un invité dont l'historique vient d'être repris."""
    out, new_state = [], {}
    for g in guests:
        s = g["sections"]
        r = {"vmid": g["vmid"], "type": g["type"], "name": g["name"], "status": g["status"], "collected": False, "error": None,
             "os": None, "web": None, "login": None, "mysql": None, "internal": None}
        r.update(rrd_stats(s.get("rrd day"), s.get("rrd week"), now))
        days = {"web": [], "login": [], "mysql": [], "ssh": [], "sudo": [], "mail": [], "files": [], "rrd": rrd_days(s.get("rrd month")), "rrd_weeks": rrd_weeks(s.get("rrd year")), "deep": False}
        if g["status"] == "running":
            raw, err = (s.get("exec"), None) if g["type"] == "lxc" else unwrap_qga(s.get("qga"))
            parts = parse_guest(raw)
            if "end" not in parts:
                r["error"] = err or ((raw or "").strip().splitlines() or ["sortie vide (délai dépassé ?)"])[-1][:160]
            if parts:
                r["collected"] = "end" in parts
                r["os"] = (parts.get("os") or "").strip()[:80] or None
                r["web"] = parse_web(parts.get("web"), now)
                days["web"], days["deep"] = parse_days(parts.get("days"))
                days["deep"] = days["deep"] and "end" in parts
                rows = _last_rows(parts.get("login"), now)
                r["login"] = parse_last(None, now, rows)
                days["login"] = login_days(rows)
                if "internal" in parts:
                    r["internal"], idays = parse_internal(parts.get("internal"), now)
                    days.update(idays)
                if "mysql status" in parts:
                    my = parse_mysql(parts.get("mysql status"), parts.get("mysql proc"), parts.get("mysql version"))
                    key = str(g["vmid"])
                    if my.get("ok"):
                        add, new_state[key] = mysql_step(my, state.get(key), now)
                        days["mysql"] = add.pop("days", [])
                        my.update(add)
                    elif state.get(key):
                        new_state[key] = state[key]
                    r["mysql"] = my
        if not days["deep"]:
            for k in ("web", "login", "mysql", "ssh", "sudo", "mail", "files"):
                days[k] = trim_days(days[k], now)
            if not full:
                days["rrd"], days["rrd_weeks"] = trim_days(days["rrd"], now), []
        r["days"] = days
        out.append(r)
    for k, v in (state or {}).items():   # invité arrêté : son historique MySQL est gardé
        new_state.setdefault(k, v)
    return out, new_state


def alerts_for(nodes):
    out = []
    for n in nodes:
        if not n.get("ok"):
            out.append({"code": "guest-usage-unreachable:%s" % n["name"], "severity": "warning", "message": "%s : activité des CT / VM non relevée (%s)" % (n["name"], n.get("error"))})
            continue
        for g in n.get("guests") or []:
            if g.get("mysql") and not g["mysql"].get("ok"):
                out.append({"code": "guest-usage-mysql:%s:%s" % (n["name"], g["vmid"]), "severity": "info",
                            "message": "%s / %s %s : MySQL présent mais non lisible (%s)" % (n["name"], g["vmid"], g["name"], g["mysql"].get("error"))})
    return out


def run_node(h, script, runner=subprocess.run):
    """h None = nœud local. -> sortie texte du script (exception si injoignable)."""
    if h is None:
        p = runner(["bash", "-s"], input=script, capture_output=True, text=True, timeout=1200)
    else:
        if h.get("key") and not os.path.exists(h["key"]):
            raise RuntimeError("clé %s introuvable pour le service si-agent (ProtectHome masque /root et /home) : la placer dans /etc/si-agent/keys/ (chmod 600) et corriger pve-remote.json" % h["key"])
        args = ["ssh"] + SSH_OPTS + (["-i", h["key"], "-o", "IdentitiesOnly=yes"] if h.get("key") else []) + ["%s@%s" % (h.get("user") or "root", h["host"]), "bash -s"]
        p = runner(args, input=script, capture_output=True, text=True, timeout=1200)
    if "@@node" not in (p.stdout or ""):
        raise RuntimeError(((p.stderr or "").strip().splitlines() or ["code %d" % p.returncode])[-1][:200])
    return p.stdout


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--remote", default="/etc/si-agent/pve-remote.json")
    ap.add_argument("--state", default="/var/lib/si-agent/guest-usage.state.json")
    ap.add_argument("--no-local", action="store_true")
    a = ap.parse_args(argv)
    try:
        with open(a.state) as fh:
            state = json.load(fh)
    except (OSError, ValueError):
        state = {}
    targets = [] if a.no_local or not os.path.isdir("/etc/pve") else [("local", "local", None)]
    if a.remote and os.path.exists(a.remote):
        try:
            with open(a.remote, encoding="utf-8") as fh:
                targets += [(h.get("name") or h["host"], "distant", h) for h in json.load(fh) if isinstance(h, dict) and h.get("host")]
        except (OSError, ValueError):
            pass
    nodes, new_state = [], {}
    deep_state, full_state = dict(state.get("_deep") or {}), dict(state.get("_full") or {})
    for name, zone, h in targets:
        now = dt.datetime.now(dt.timezone.utc)
        today = now.strftime("%Y-%m-%d")
        done_ids = deep_state.get(name) or {}
        try:
            node, guests, done = parse_driver(run_node(h, driver_script(done_ids.keys())))
            label = node or name   # #777 : nom du nœud Proxmox, local ou distant (une seule ligne par invité si deux agents le relèvent)
            full = full_state.get(name) != today
            rows, new_state[label] = build(label, guests, state.get(label) or {}, now, full=full)
            for g in rows:   # #771 : historique repris pour cet invité
                if (g.get("days") or {}).get("deep"):
                    done_ids = dict(done_ids, **{str(g["vmid"]): _iso(now)})
            deep_state[name] = done_ids
            if full and done:
                full_state[name] = today
            nodes.append({"name": label, "zone": zone, "ok": True, "error": None if done else "relevé incomplet (délai dépassé)", "guests": rows})
        except Exception as e:  # noqa: BLE001 -- un nœud injoignable n'empêche pas les autres
            nodes.append({"name": name, "zone": zone, "ok": False, "error": str(e)[:200], "guests": []})
            if name in state:
                new_state[name] = state[name]
    new_state["_deep"], new_state["_full"] = deep_state, full_state
    try:
        os.makedirs(os.path.dirname(a.state), exist_ok=True)
        with open(a.state + ".tmp", "w") as fh:
            json.dump(new_state, fh)
        os.replace(a.state + ".tmp", a.state)
    except OSError:
        pass
    g = [x for n in nodes for x in n["guests"]]
    print(json.dumps({"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "nodes": nodes, "alerts": alerts_for(nodes),
                      "summary": {"nodes": len(nodes), "guests": len(g), "collected": sum(1 for x in g if x["collected"]),
                                  "web": sum(1 for x in g if x.get("web")), "mysql": sum(1 for x in g if x.get("mysql"))}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
