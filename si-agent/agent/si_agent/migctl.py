# -*- coding: utf-8 -*-
"""#774 : étapes de la tuile « Migration 2026-2027 » exécutées par l'agent -- copies et vérifications entre nœuds
Proxmox (OVH -> LAN), une étape à la fois, pilotées depuis le hub (démarrer, pause, reprise, arrêt).

Chaque étape est un TYPE connu (jamais une commande libre) et ses paramètres validés ; l'agent écrit un script bash
dans STATE_DIR et le lance DÉTACHÉ (systemd-run, unité si-mig-<id>) : il survit aux redémarrages et mises à jour de
l'agent. Le script écrit son journal (<id>.log) et son code de sortie (<id>.rc) ; la sonde « migration » relit l'état,
la taille copiée et la fin du journal, le central en tire le statut, l'erreur détaillée et sa solution.

Types : check_ssh, check_space, check_file, zfs_create, rsync_pull, rsync_pull_all, zfs_pull, zfs_send_file,
verify_rsync, verify_zfs. Les reprises sont sûres : rsync ne recopie que la différence, zfs recv -s reprend où il
s'était arrêté. Pur (validate, script, measure) ; run() exécute avec un `runner` injectable (tests)."""
import json
import os
import re
import shlex
import time

STATE_DIR = "/var/lib/si-agent/migration"
KINDS = ("check_ssh", "check_space", "check_file", "zfs_create", "rsync_pull", "rsync_pull_all", "zfs_pull", "zfs_send_file",
         "verify_rsync", "verify_zfs")
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.-]{0,252}$")
PATH_RE = re.compile(r"^/[A-Za-z0-9._/+@-]{0,300}$")
DS_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:/-]{0,250}$")
SNAP_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,62}$")
GLOB_RE = re.compile(r"^[A-Za-z0-9._*?-]{1,64}$")
SSH = "ssh -o BatchMode=yes -o ConnectTimeout=20 -o ServerAliveInterval=30 -o StrictHostKeyChecking=accept-new"
REQUIRED = {"check_ssh": ("host",), "check_space": ("path", "min_gb"), "check_file": ("path",), "zfs_create": ("dataset",),
            "rsync_pull": ("host", "src", "dest"), "rsync_pull_all": ("host", "src_dir", "pattern", "dest_dir"),
            "zfs_pull": ("host", "pool", "ids", "snapshot", "dest"), "zfs_send_file": ("dataset", "snapshot", "file"),
            "verify_rsync": ("host", "src", "dest"), "verify_zfs": ("dest", "snapshot")}


def q(s):
    return shlex.quote(str(s))


def validate(step):
    """Étape reçue du central -> (étape normalisée, erreur)."""
    if not isinstance(step, dict):
        return None, "étape attendue (objet)"
    sid, kind, p = str(step.get("id") or ""), str(step.get("kind") or ""), dict(step.get("params") or {})
    if not ID_RE.match(sid):
        return None, "identifiant d'étape invalide"
    if kind not in KINDS:
        return None, "type d'étape inconnu : %s" % kind
    miss = [k for k in REQUIRED[kind] if p.get(k) in (None, "", [])]
    if miss:
        return None, "paramètre(s) manquant(s) : %s" % ", ".join(miss)
    checks = {"host": HOST_RE, "src": PATH_RE, "dest": None, "src_dir": PATH_RE, "dest_dir": PATH_RE, "path": PATH_RE, "file": PATH_RE,
              "pattern": GLOB_RE, "device": PATH_RE, "pool": DS_RE, "dataset": DS_RE, "snapshot": SNAP_RE, "conf": PATH_RE}
    for k, rx in checks.items():
        v = p.get(k)
        if v in (None, ""):
            continue
        if k == "dest":   # chemin (rsync) ou volume ZFS (zfs_pull, verify_zfs)
            rx = DS_RE if kind in ("zfs_pull", "verify_zfs") else PATH_RE
        if k == "path" and kind == "check_space" and not str(v).startswith("/"):
            rx = DS_RE    # volume ZFS ou dossier
        if not isinstance(v, str) or not rx.match(v) or ".." in v:
            return None, "paramètre %s invalide : %s" % (k, str(v)[:80])
    if "ids" in p:
        if not isinstance(p["ids"], list) or not p["ids"] or not all(isinstance(i, int) and 0 < i < 10**7 for i in p["ids"]):
            return None, "ids : liste de numéros de CT / VM"
    for k in ("bwlimit_mb", "min_gb", "max_diff"):
        if p.get(k) not in (None, "") and not (isinstance(p[k], (int, float)) and 0 <= p[k] < 10**7):
            return None, "%s : nombre attendu" % k
    return {"id": sid, "kind": kind, "params": p, "title": str(step.get("title") or sid)[:200]}, None


def _limit(p):
    mb = p.get("bwlimit_mb")
    return ("| { command -v pv >/dev/null && pv -q -L %dm || cat; } " % int(mb)) if mb else ""


def script(step):
    """Script bash de l'étape (journal sur la sortie standard ; le code de sortie fait foi)."""
    k, p = step["kind"], step["params"]
    h = "root@%s" % p.get("host", "")
    head = "set -o pipefail\necho \"@@STEP %s %s $(date -Is)\"\n" % (step["id"], k)
    if k == "check_ssh":
        body = "%s %s 'echo connexion OK; hostname; pveversion 2>/dev/null || true'\n" % (SSH, q(h))
    elif k == "check_space":
        body = ("p=%s; need=$((%d * 1024 * 1024 * 1024))\n"
                "avail=$(zfs get -Hp -o value available \"$p\" 2>/dev/null || df -B1 --output=avail \"$p\" | tail -1)\n"
                "echo \"libre : $avail octets, besoin : $need octets ($p)\"\n"
                "[ -n \"$avail\" ] && [ \"$avail\" -ge \"$need\" ] || { echo \"ESPACE INSUFFISANT sur $p\"; exit 3; }\n") % (q(p["path"]), int(p["min_gb"]))
    elif k == "check_file":
        body = ("f=%s\nif [ -d \"$f\" ]; then s=$(du -sb \"$f\" | cut -f1); echo \"dossier : $s octets\"; ls -la \"$f\" | head -20\n"
                "elif [ -f \"$f\" ]; then s=$(stat -c %%s \"$f\"); echo \"taille : $s octets\"\n"
                "else echo \"fichier absent : $f\"; exit 4; fi\n") % q(p["path"])
        if str(p["path"]).endswith(".zfs"):   # flux ZFS : complet si le dernier enregistrement (312 octets) est DRR_END (type 5)
            body += ("t=$(tail -c 312 \"$f\" | od -A n -t u4 -N 4 | tr -d ' '); echo \"dernier enregistrement du flux : type $t\"\n"
                     "[ \"$t\" = 5 ] && echo \"flux ZFS complet (enregistrement de fin présent)\" || { echo \"FICHIER INCOMPLET (flux ZFS sans enregistrement de fin)\"; exit 6; }\n")
        elif p.get("device"):   # copie brute d'un volume (dd / cat d'un zvol) : taille du fichier >= taille du volume
            body += ("t=$(blockdev --getsize64 %s 2>/dev/null); echo \"volume source : $t octets\"\n"
                     "pgrep -af %s | grep -v pgrep | grep -qv '@@' && { echo \"copie encore en cours\"; pgrep -af %s; exit 5; }\n"
                     "[ -n \"$t\" ] && [ \"$s\" -ge \"$t\" ] || { echo \"FICHIER INCOMPLET ($s / $t)\"; exit 6; }\n") % (q(p["device"]), q(p["device"]), q(p["device"]))
        if p.get("dataset") and p.get("snapshot"):
            body += ("t=$(zfs get -Hp -o value referenced %s 2>/dev/null); echo \"snapshot : $t octets\"\n"
                     "pgrep -af 'zfs send' | grep -q %s && { echo \"copie encore en cours\"; exit 5; }\n"
                     "[ -n \"$t\" ] && [ \"$s\" -ge $((t * 9 / 10)) ] || { echo \"FICHIER INCOMPLET ($s / $t)\"; exit 6; }\n") % (
                q("%s@%s" % (p["dataset"], p["snapshot"])), q(p["snapshot"]))
    elif k == "zfs_create":
        body = "zfs list %s >/dev/null 2>&1 && echo \"existe déjà\" || zfs create -p -o compression=lz4 %s\nzfs list %s\n" % (
            q(p["dataset"]), q(p["dataset"]), q(p["dataset"]))
    elif k in ("rsync_pull", "verify_rsync"):
        bw = "--bwlimit=%d " % int(p["bwlimit_mb"] * 1024) if p.get("bwlimit_mb") else ""
        src, dest = p["src"].rstrip("/") + "/", p["dest"].rstrip("/") + "/"
        if k == "rsync_pull":
            body = ("d=%s\nif pgrep -af \"rsync .*$d\" | grep -v \"@@\" | grep -q .; then echo \"UN AUTRE RSYNC ÉCRIT DÉJÀ DANS $d\"; pgrep -af \"rsync .*$d\"; exit 7; fi\n"
                    "mkdir -p \"$d\"\n") % q(dest)
            if p.get("conf"):
                body += "scp -o BatchMode=yes %s:%s %s && echo \"configuration copiée\"\n" % (q(h), q(p["conf"]), q(dest.rstrip("/") + ".conf"))
            body += ("rsync -aHAX --numeric-ids --sparse --stats %s--rsync-path='ionice -c3 nice rsync' -e %s %s:%s \"$d\"\n"
                     "rc=$?; [ $rc -eq 24 ] && { echo \"(fichiers disparus pendant la copie : normal sur un conteneur en service)\"; rc=0; }\nexit $rc\n") % (
                bw, q(SSH), q(h), q(src))
        else:
            body = ("n=$(rsync -aHAXn --numeric-ids --delete --itemize-changes -e %s %s:%s %s | grep -vc '^\\.')\n"
                    "echo \"différences restantes : $n\"\n"
                    "[ \"$n\" -le %d ] || { echo \"TROP DE DIFFÉRENCES ($n) : relancer la copie\"; exit 8; }\n") % (
                q(SSH), q(h), q(src), q(dest), int(p.get("max_diff", 2000)))
    elif k == "rsync_pull_all":
        bw = "--bwlimit=%d " % int(p["bwlimit_mb"] * 1024) if p.get("bwlimit_mb") else ""
        body = ("mkdir -p %s\nfail=0\n"
                "for d in $(%s %s \"ls -d %s/%s 2>/dev/null\"); do n=$(basename \"$d\"); echo \"== $n\"\n"
                "  rsync -aHAX --numeric-ids --sparse --stats %s--rsync-path='ionice -c3 nice rsync' -e %s %s:\"$d/\" %s/\"$n\"/; rc=$?\n"
                "  [ $rc -eq 0 ] || [ $rc -eq 24 ] || { echo \"ÉCHEC $n (code $rc)\"; fail=$rc; }\ndone\n"
                "%s %s 'tar -C /etc/pve -cf - lxc qemu-server 2>/dev/null' | tar -C %s -xf - && echo \"configurations copiées\"\nexit $fail\n") % (
            q(p["dest_dir"]), SSH, q(h), p["src_dir"].rstrip("/"), p["pattern"], bw, q(SSH), q(h), q(p["dest_dir"]), SSH, q(h), q(p["dest_dir"]))
    elif k == "zfs_pull":
        ids = "|".join(str(i) for i in p["ids"])
        body = ("snap=%s; dest=%s; fail=0\nzfs list \"$dest\" >/dev/null 2>&1 || zfs create -p -o compression=lz4 \"$dest\"\n"
                "list=$(%s %s \"zfs list -H -o name -r %s | grep -E '/(subvol|vm)-(%s)-disk-[0-9]+\\$'\")\n"
                "[ -n \"$list\" ] || { echo \"AUCUN VOLUME TROUVÉ pour %s sur %s\"; exit 9; }\n"
                "for ds in $list; do dst=\"$dest/$(basename $ds)\"; echo \"== $ds -> $dst\"\n"
                "  %s %s \"zfs list -H -t snapshot $ds@$snap >/dev/null 2>&1 || zfs snapshot $ds@$snap\" || { fail=10; continue; }\n"
                "  if zfs list -H \"$dst@$snap\" >/dev/null 2>&1; then echo \"déjà reçu\"; continue; fi\n"
                "  tok=$(zfs get -H -o value receive_resume_token \"$dst\" 2>/dev/null)\n"
                "  if [ -n \"$tok\" ] && [ \"$tok\" != \"-\" ]; then echo \"reprise\"; %s %s \"zfs send -t $tok\" %s| zfs recv -s -u \"$dst\" || fail=11\n"
                "  else %s %s \"zfs send -c $ds@$snap\" %s| zfs recv -s -u \"$dst\" || fail=11; fi\ndone\nexit $fail\n") % (
            q(p["snapshot"]), q(p["dest"]), SSH, q(h), q(p["pool"]), ids, ids, p["host"], SSH, q(h), SSH, q(h), _limit(p), SSH, q(h), _limit(p))
    elif k == "zfs_send_file":
        body = ("s=%s; f=%s; mkdir -p \"$(dirname \"$f\")\"\nzfs list -H -t snapshot \"$s\" >/dev/null 2>&1 || zfs snapshot \"$s\"\n"
                "[ -f \"$f\" ] && { echo \"fichier déjà présent, recopie complète (un flux ZFS ne se reprend pas)\"; }\n"
                "zfs send -c \"$s\" %s> \"$f\"\n") % (q("%s@%s" % (p["dataset"], p["snapshot"])), q(p["file"]), _limit(p))
    else:   # verify_zfs
        body = ("snap=%s; n=0; bad=0\nfor ds in $(zfs list -H -o name -r %s | tail -n +2); do n=$((n+1))\n"
                "  if zfs list -H \"$ds@$snap\" >/dev/null 2>&1; then echo \"OK $ds\"; else echo \"MANQUE $ds@$snap\"; bad=$((bad+1)); fi\n"
                "  t=$(zfs get -H -o value receive_resume_token \"$ds\"); [ \"$t\" != \"-\" ] && echo \"  réception inachevée sur $ds\"\ndone\n"
                "echo \"$n volume(s), $bad incomplet(s)\"; [ $bad -eq 0 ] && [ $n -gt 0 ]\n") % (q(p["snapshot"]), q(p["dest"]))
    return head + body


def measure(step):
    """Ce que la sonde mesure pendant l'étape : {type: zfs|df|file, target}."""
    k, p = step["kind"], step["params"]
    if k == "zfs_pull":
        return {"type": "zfs", "target": p["dest"]}
    if k == "zfs_send_file":
        return {"type": "file", "target": p["file"]}
    if k in ("rsync_pull", "rsync_pull_all"):
        return {"type": "path", "target": p.get("dest") or p.get("dest_dir")}
    return None


def unit(sid):
    return "si-mig-" + re.sub(r"[^A-Za-z0-9_-]", "-", sid)


def run(params, runner, state_dir=STATE_DIR, now=None):
    """Action du hub : start | stop | pause | resume | status (step = étape complète pour start, id sinon)."""
    action = str((params or {}).get("action") or "")
    if action not in ("start", "stop", "pause", "resume", "status"):
        return {"ok": False, "error": "action inconnue"}
    if action == "start":
        st, err = validate((params or {}).get("step"))
        if err:
            return {"ok": False, "error": err}
        sid = st["id"]
    else:
        sid = str((params or {}).get("id") or "")
        if not ID_RE.match(sid):
            return {"ok": False, "error": "identifiant d'étape invalide"}
    os.makedirs(state_dir, exist_ok=True)
    base, u = os.path.join(state_dir, sid), unit(sid)
    if action == "start":
        if runner(["systemctl", "is-active", "--quiet", u])[0] == 0:
            return {"ok": False, "error": "l'étape %s tourne déjà" % sid}
        for ext in (".rc",):
            try:
                os.remove(base + ext)
            except OSError:
                pass
        with open(base + ".sh", "w") as fh:
            fh.write(script(st))
        total = None
        if st["kind"] == "zfs_send_file":
            rc, out, _e = runner(["zfs", "get", "-Hp", "-o", "value", "referenced", "%s@%s" % (st["params"]["dataset"], st["params"]["snapshot"])])
            total = int(out.strip()) if rc == 0 and out.strip().isdigit() else None
        meta = {"id": sid, "kind": st["kind"], "title": st["title"], "unit": u, "started_at": time.time() if now is None else now,
                "measure": measure(st), "total": total, "params": st["params"]}
        with open(base + ".json", "w") as fh:
            json.dump(meta, fh)
        wrap = "bash %s >> %s 2>&1; echo $? > %s" % (q(base + ".sh"), q(base + ".log"), q(base + ".rc"))
        with open(base + ".log", "a") as fh:
            fh.write("\n@@START %s\n" % time.strftime("%Y-%m-%dT%H:%M:%S"))
        rc, out, errt = runner(["systemd-run", "--unit", u, "--collect", "--quiet", "--property=KillMode=control-group", "/bin/bash", "-c", wrap])
        if rc != 0:
            return {"ok": False, "error": "lancement impossible : %s" % (errt or out).strip()[:300]}
        return {"ok": True, "message": "étape %s lancée (%s)" % (sid, u)}
    if action == "status":
        rc, out, _e = runner(["systemctl", "is-active", u])
        return {"ok": True, "active": out.strip()}
    sig = {"pause": ["systemctl", "kill", "-s", "SIGSTOP", u], "resume": ["systemctl", "kill", "-s", "SIGCONT", u], "stop": ["systemctl", "stop", u]}[action]
    rc, out, errt = runner(sig)
    if action == "stop":
        with open(base + ".rc", "w") as fh:
            fh.write("143\n")
    if action in ("pause", "resume"):
        with open(base + ".paused", "w") if action == "pause" else open(os.devnull, "w") as fh:
            fh.write("1")
        if action == "resume":
            try:
                os.remove(base + ".paused")
            except OSError:
                pass
    return {"ok": rc == 0 or action == "stop", "error": None if rc == 0 else (errt or out).strip()[:200], "message": "%s : %s" % (sid, action)}
