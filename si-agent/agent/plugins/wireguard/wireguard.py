#!/usr/bin/env python3
"""Plugin si-agent « wireguard » (#884) : état d'un serveur WireGuard en LECTURE SEULE.

Source : `wg show all dump`, localement (agent installé sur le serveur VPN, ex. r2d2) ou à distance par SSH vers une
COMMANDE FORCÉE que l'administrateur du VPN installe lui-même (voir wg-etat.sh) : elle ne peut qu'afficher l'état et
masque déjà les clés privées et partagées. Ici aussi, par sécurité, toute clé privée / partagée est écartée avant sortie.
Relevé : interfaces (clé publique, port), pairs (nom, clé publique, adresse d'origine, adresses VPN, dernière poignée
de main, octets reçus / émis, connecté si poignée de main < 3 min). Les noms des pairs viennent des commentaires des
fichiers /etc/wireguard/*.conf (mode local : « # Name = x » ou « # x » dans / juste avant le bloc [Peer]) ou d'un
fichier JSON {clé_publique: nom} (--names). Le hub reconstitue l'historique des connexions à partir des relevés.

MikroTik (#889) : --mikrotik /etc/si-agent/mikrotik-wg.json (root seulement) {"host", "user", "password", "port", "tls"} ;
lecture par l'API RouterOS (routeros.py, commandes …/print uniquement), compte du groupe « read » suffisant ;
noms des pairs = champ name ou comment du routeur.

Arguments : [--ssh compte@hote] [--ssh-key chemin] [--ssh-port 22] [--conf-dir /etc/wireguard] [--names fichier.json]
            [--mikrotik fichier.json] [--connected-s 180]
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import time

MASQUE = "(masquée)"


def parse_dump(texte, now=None, connected_s=180):
    """Sortie de `wg show all dump` -> [{interface, public_key, port, peers: [...]}] ; aucune clé privée / partagée."""
    now = now or time.time()
    ifs = {}
    for ligne in (texte or "").splitlines():
        f = ligne.rstrip("\n").split("\t")
        if len(f) == 5:      # interface, clé privée, clé publique, port, fwmark
            ifs.setdefault(f[0], {"interface": f[0], "peers": []}).update(public_key=f[2], port=int(f[3]) if f[3].isdigit() else None)
        elif len(f) == 9:    # interface, clé publique, clé partagée, origine, adresses, poignée de main, reçu, émis, maintien
            hs = int(f[5]) if f[5].isdigit() else 0
            age = int(now - hs) if hs else None
            ifs.setdefault(f[0], {"interface": f[0], "peers": []})["peers"].append({
                "public_key": f[1], "endpoint": None if f[3] in ("(none)", "") else f[3],
                "allowed_ips": [x for x in f[4].split(",") if x and x != "(none)"],
                "handshake_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(hs)) if hs else None, "handshake_age_s": age,
                "rx": int(f[6]) if f[6].isdigit() else 0, "tx": int(f[7]) if f[7].isdigit() else 0,
                "connected": age is not None and age <= connected_s})
    return list(ifs.values())


def noms_conf(conf_dir):
    """Fichiers *.conf -> {clé_publique: nom} d'après les commentaires (rien d'autre n'est lu ni conservé)."""
    noms = {}
    for chemin in sorted(glob.glob(os.path.join(conf_dir, "*.conf"))):
        try:
            with open(chemin, encoding="utf-8", errors="replace") as fh:
                lignes = fh.read().splitlines()
        except OSError:
            continue
        nom, dans_peer = None, False
        for ligne in lignes:
            s = ligne.strip()
            if s.startswith("#"):
                m = re.match(r"#+\s*(?:name|nom|peer)\s*[=:]\s*(.+)", s, re.I) or re.match(r"#+\s*(.+)", s)
                if m:
                    nom = m.group(1).strip()[:60]
            elif s.lower() == "[peer]":
                dans_peer = True
            elif s.lower() == "[interface]":
                dans_peer, nom = False, None
            elif dans_peer and s.lower().startswith("publickey"):
                cle = s.split("=", 1)[1].strip()
                if nom:
                    noms[cle] = nom
                nom = None
    return noms


def _int(v):
    try:
        return int(str(v).split()[0])
    except (TypeError, ValueError, IndexError):
        return 0


def lire_mikrotik(cfg, connecter=None, now=None, connected_s=180):
    """Routeur MikroTik (RouterOS 7) -> même structure que parse_dump ; aucune clé privée lue ni renvoyée."""
    import routeros
    now = now or time.time()
    connecter = connecter or routeros.connecter
    pwd = cfg["password"]
    # #890 : mot de passe accentué -- RouterOS compare des octets dans le codage du poste qui l'a saisi (Winbox :
    # Windows-1252) ; on essaie UTF-8 puis Windows-1252 (ou le seul codage imposé par "encoding"), une connexion chacun.
    codages = [cfg["encoding"]] if cfg.get("encoding") else (["utf-8"] if all(ord(c) < 128 for c in pwd + cfg["user"]) else ["utf-8", "cp1252"])
    api, erreur = None, None
    for codage in codages:
        api = connecter(cfg["host"], cfg.get("port"), bool(cfg.get("tls")))
        try:
            api.login(cfg["user"], pwd, codage)
            erreur = None
            break
        except RuntimeError as e:
            erreur = e
            try:
                api.s.close()
            except Exception:  # noqa: BLE001
                pass
    if erreur is not None:
        raise RuntimeError("%s (codages essayés : %s)" % (erreur, ", ".join(codages)))
    try:
        ifs = {i.get("name"): {"interface": i.get("name"), "public_key": i.get("public-key"), "port": _int(i.get("listen-port")) or None, "peers": [],
                               "actif": i.get("disabled") != "true" and i.get("running", "true") != "false"}
               for i in api.lire("/interface/wireguard/print")}
        for p in api.lire("/interface/wireguard/peers/print"):
            if p.get("disabled") == "true":
                continue
            age = routeros.duree_s(p.get("last-handshake"))
            adr, port = p.get("current-endpoint-address") or p.get("endpoint-address"), p.get("current-endpoint-port") or p.get("endpoint-port")
            ifs.setdefault(p.get("interface"), {"interface": p.get("interface"), "peers": []})["peers"].append({
                "public_key": p.get("public-key"), "name": (p.get("name") or p.get("comment") or "")[:60],
                "endpoint": ("%s:%s" % (adr, port) if port and port != "0" else adr) if adr else None,
                "allowed_ips": [x for x in (p.get("allowed-address") or "").split(",") if x],
                "handshake_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now - age)) if age is not None else None,
                "handshake_age_s": age, "rx": _int(p.get("rx")), "tx": _int(p.get("tx")),
                "connected": age is not None and age <= connected_s})
        return list(ifs.values())
    finally:
        try:
            api.s.close()
        except Exception:  # noqa: BLE001
            pass


def lire(a, runner=subprocess.run, which=shutil.which):
    if a.ssh:
        cmd = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", "-o", "StrictHostKeyChecking=accept-new", "-p", str(a.ssh_port)]
        if a.ssh_key:
            cmd += ["-i", a.ssh_key]
        cmd += [a.ssh, "wg-etat"]
    else:
        wg = which("wg")
        if not wg:
            raise RuntimeError("commande wg absente (paquet wireguard-tools)")
        cmd = [wg, "show", "all", "dump"]
    p = runner(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True, timeout=60)
    if p.returncode != 0:
        raise RuntimeError((p.stderr or "échec").strip()[:200])
    return p.stdout


def main(argv=None, runner=subprocess.run, which=shutil.which, now=None, connecter=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ssh")
    ap.add_argument("--ssh-key")
    ap.add_argument("--ssh-port", type=int, default=22)
    ap.add_argument("--conf-dir", default="/etc/wireguard")
    ap.add_argument("--names")
    ap.add_argument("--connected-s", type=int, default=180)
    ap.add_argument("--mikrotik")
    a = ap.parse_args(argv)
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "source": a.ssh or "local", "interfaces": [], "alerts": []}
    try:
        if a.mikrotik:
            with open(a.mikrotik, encoding="utf-8") as fh:
                cfg = json.load(fh)
            out["source"] = "mikrotik:%s" % cfg.get("host")
            ifs = lire_mikrotik(cfg, connecter, now=now, connected_s=a.connected_s)
        else:
            ifs = parse_dump(lire(a, runner, which), now=now, connected_s=a.connected_s)
    except Exception as e:  # noqa: BLE001
        out["alerts"].append({"code": "vpn-lecture", "severity": "warning", "message": "état WireGuard illisible (%s) : %s" % (out["source"], str(e)[:150])})
        return out
    noms = {} if (a.ssh or a.mikrotik) else noms_conf(a.conf_dir)
    if a.names:
        try:
            with open(a.names, encoding="utf-8") as fh:
                noms.update({k: str(v)[:60] for k, v in json.load(fh).items()})
        except (OSError, ValueError) as e:
            out["alerts"].append({"code": "vpn-noms", "severity": "info", "message": "fichier des noms illisible : %s" % e})
    for i in ifs:
        for p in i["peers"]:
            p["name"] = noms.get(p["public_key"]) or p.get("name") or ""
    out["interfaces"] = ifs
    if not ifs:
        out["alerts"].append({"code": "vpn-aucune-interface", "severity": "warning", "message": "aucune interface WireGuard active (%s)" % out["source"]})
    return out


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1:]), ensure_ascii=False))
