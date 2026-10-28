#!/usr/bin/env python3
"""Plugin si-agent « partages-samba » (#902, backlog 140) : partages, sessions et verrous d'un serveur Samba, LECTURE SEULE.

À installer sur un serveur Samba (NAS Linux, vieux serveur de fichiers). Relève :
- les partages déclarés (`net conf list` si registre, sinon analyse de smb.conf) : chemin, invité autorisé, lecture
  seule, utilisateurs/groupes valides -- repère les partages ouverts à tous (guest ok) et inscriptibles par tous ;
- les sessions ouvertes et les fichiers verrouillés (`smbstatus`) : qui (utilisateur, machine, IP), quel partage,
  chiffrement, depuis quand -- l'historique des connexions est reconstitué par le hub à partir des relevés.
Aucune écriture, aucun mot de passe lu. `smbstatus` exige les droits root (sonde privilégiée).

Arguments : [--conf /etc/samba/smb.conf] [--idle-days 90]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time

BOOL_OUI = {"yes", "true", "1", "oui"}


def _run(runner, argv, timeout=30):
    try:
        p = runner(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout, universal_newlines=True)
        return (p.stdout or ""), (p.stderr or ""), p.returncode
    except (OSError, subprocess.TimeoutExpired) as e:
        return "", str(e)[:150], -1


def analyser_conf(texte):
    """smb.conf (ou `net conf list`, même syntaxe) -> {section: {clé: valeur}} ; clés normalisées (espaces->_)."""
    sections, cur = {}, None
    for l in (texte or "").splitlines():
        s = l.strip()
        if not s or s[0] in "#;":
            continue
        m = re.match(r"\[(.+)\]$", s)
        if m:
            cur = m.group(1).strip()
            sections[cur] = {}
        elif "=" in s and cur is not None:
            k, v = s.split("=", 1)
            sections[cur][k.strip().lower().replace(" ", "_")] = v.strip()
    return sections


def partages(sections):
    """Sections -> liste des partages (hors [global], [printers], [print$]) avec leurs réglages d'accès."""
    out = []
    for nom, kv in sections.items():
        if nom.lower() in ("global", "printers", "print$"):
            continue
        chemin = kv.get("path") or kv.get("directory")
        if not chemin and "comment" not in kv and "valid_users" not in kv:
            continue
        invite = (kv.get("guest_ok") or kv.get("public") or "no").lower() in BOOL_OUI
        ro = (kv.get("read_only") or ("no" if (kv.get("writable") or kv.get("writeable") or "no").lower() in BOOL_OUI else "yes")).lower() in BOOL_OUI
        out.append({"nom": nom, "chemin": chemin, "commentaire": kv.get("comment", ""), "invite": invite, "lecture_seule": ro,
                    "navigable": (kv.get("browseable") or kv.get("browsable") or "yes").lower() in BOOL_OUI,
                    "utilisateurs_valides": kv.get("valid_users", ""), "liste_ecriture": kv.get("write_list", ""),
                    "force_user": kv.get("force_user", ""), "masque_creation": kv.get("create_mask") or kv.get("create_mode", "")})
    return out


def analyser_smbstatus_json(texte):
    """smbstatus --json -> (sessions, verrous) au format commun."""
    d = json.loads(texte)
    sessions = []
    for s in (d.get("sessions") or {}).values():
        sessions.append({"utilisateur": s.get("username"), "groupe": s.get("groupname"), "machine": s.get("remote_machine") or s.get("hostname"),
                         "ip": (s.get("remote_machine") or "").split(":")[0] if s.get("remote_machine") else s.get("ip"),
                         "chiffrement": s.get("encryption", {}).get("cipher") if isinstance(s.get("encryption"), dict) else s.get("encryption"),
                         "signature": s.get("signing", {}).get("cipher") if isinstance(s.get("signing"), dict) else s.get("signing"),
                         "depuis": s.get("session_dialect") and s.get("connected_at") or s.get("connected_at")})
    verrous = []
    for t in (d.get("tcons") or {}).values():
        verrous.append({"partage": t.get("service"), "machine": t.get("machine"), "ip": t.get("ip_address") or (t.get("machine") or "").split(":")[0],
                        "chiffrement": t.get("encryption", {}).get("cipher") if isinstance(t.get("encryption"), dict) else None, "depuis": t.get("connected_at")})
    return sessions, verrous


def analyser_smbstatus_texte(brut, shares_brut):
    """smbstatus classique (sorties texte) -> (sessions, connexions aux partages)."""
    sessions = []
    for l in (brut or "").splitlines():
        m = re.match(r"^\s*(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(.*)$", l)
        if m and m.group(2) not in ("Username", "-------"):
            sessions.append({"pid": m.group(1), "utilisateur": m.group(2), "groupe": m.group(3), "machine": m.group(4), "info": m.group(5).strip()})
    cons = []
    dans = False
    for l in (shares_brut or "").splitlines():
        if l.startswith("Service") and "pid" in l:
            dans = True
            continue
        if not dans or not l.strip() or l.startswith("-"):
            continue
        f = l.split()
        if len(f) >= 4:
            cons.append({"partage": f[0], "pid": f[1], "machine": f[2], "depuis": " ".join(f[3:])})
    return sessions, cons


def main(argv=None, runner=subprocess.run, which=shutil.which):
    ap = argparse.ArgumentParser()
    ap.add_argument("--conf", default="/etc/samba/smb.conf")
    ap.add_argument("--idle-days", type=int, default=90)
    a = ap.parse_args(argv)
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "partages": [], "sessions": [], "verrous": [], "alerts": []}
    net, smbstatus, testparm = which("net"), which("smbstatus"), which("testparm")
    # --- partages : registre (net conf list), sinon testparm -s, sinon smb.conf
    conf_txt = None
    if net:
        o, _e, rc = _run(runner, [net, "conf", "list"])
        if rc == 0 and o.strip():
            conf_txt = o
    if conf_txt is None and testparm:
        o, _e, rc = _run(runner, [testparm, "-s", "--suppress-prompt"])
        if o.strip():
            conf_txt = o
    if conf_txt is None:
        try:
            with open(a.conf, encoding="utf-8", errors="replace") as fh:
                conf_txt = fh.read()
        except OSError as e:
            out["alerts"].append({"code": "samba-conf", "severity": "warning", "message": "configuration Samba illisible : %s" % e})
    if conf_txt:
        out["partages"] = partages(analyser_conf(conf_txt))
    # --- sessions et verrous
    if smbstatus:
        o, _e, rc = _run(runner, [smbstatus, "--json"])
        if rc == 0 and o.strip().startswith("{"):
            try:
                out["sessions"], out["verrous"] = analyser_smbstatus_json(o)
            except ValueError:
                pass
        if not out["sessions"] and not out["verrous"]:
            brut, _e, _rc = _run(runner, [smbstatus, "-b"])
            shares, _e2, _rc2 = _run(runner, [smbstatus, "-S"])
            out["sessions"], out["verrous"] = analyser_smbstatus_texte(brut, shares)
    else:
        out["alerts"].append({"code": "samba-smbstatus", "severity": "info", "message": "smbstatus absent : partages listés, mais ni sessions ni verrous"})
    # --- constats
    for p in out["partages"]:
        if p["invite"] and not p["lecture_seule"]:
            out["alerts"].append({"code": "samba-invite-ecriture@%s" % p["nom"], "severity": "warning", "message": "partage %s : accès invité ET inscriptible (ouvert à tous en écriture)" % p["nom"]})
        elif p["invite"]:
            out["alerts"].append({"code": "samba-invite@%s" % p["nom"], "severity": "info", "message": "partage %s : lisible sans authentification (invité)" % p["nom"]})
    return out


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1:]), ensure_ascii=False))
