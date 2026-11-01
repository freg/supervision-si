# -*- coding: utf-8 -*-
"""Configuration radio d'une sonde (livraison #807) -- commande du central (ou du collecteur du site) `wifi_config` :
  {action: "etat"}                              interfaces Wi-Fi (pilote, MAC, type, gérée ou non), connexions si-*, réglage courant
  {action: "appliquer", interfaces: {nom: client|moniteur|inactive}, ssids: [{ssid, psk?, actif, iface?}]}
Les SSID actifs deviennent des connexions NetworkManager « si-<ssid> » écrites en fichiers keyfile (0600, la clé n'apparaît
jamais en ligne de commande), sans route par défaut (l'Ethernet reste le chemin d'administration) ; la première de chaque
interface client se connecte seule, les autres servent à la rotation de path-probe. Un SSID désactivé est retiré.
Interfaces « moniteur » et « inactive » : non gérées par NetworkManager (écoute passive, wifi-monitor). Le réglage, sans
les clés, est écrit dans /etc/si-agent/wifi-sondes.json, lu par wifi-probe et path-probe."""
import json
import os
import re
import uuid

REGLAGE = "/etc/si-agent/wifi-sondes.json"
NM_CONNEXIONS = "/etc/NetworkManager/system-connections"
NM_CONF = "/etc/NetworkManager/conf.d/si-sonde-interfaces.conf"
ANCIENNE_CONF = "/etc/NetworkManager/conf.d/si-alfa-monitor.conf"
ROLES = ("client", "moniteur", "inactive")


def nom_connexion(ssid):
    return "si-" + (re.sub(r"[^A-Za-z0-9._-]+", "_", ssid).strip("_") or "ssid")[:40]


def valider(params):
    """-> (interfaces, ssids, erreur)."""
    inter = params.get("interfaces") or {}
    if not isinstance(inter, dict):
        return None, None, "interfaces : {nom: rôle} attendu"
    for n, r in inter.items():
        if not re.match(r"^[A-Za-z0-9_.-]{1,15}$", str(n)) or r not in ROLES:
            return None, None, "interface %r : rôle parmi %s" % (n, ", ".join(ROLES))
    ssids, vus = [], set()
    for s in params.get("ssids") or []:
        if not isinstance(s, dict) or not isinstance(s.get("ssid"), str) or not 1 <= len(s["ssid"].encode("utf-8")) <= 32:
            return None, None, "SSID invalide (1 à 32 octets)"
        if s["ssid"] in vus:
            return None, None, "SSID en double : %s" % s["ssid"]
        vus.add(s["ssid"])
        psk = s.get("psk")
        if psk not in (None, "") and not (isinstance(psk, str) and 8 <= len(psk) <= 63):
            return None, None, "clé de « %s » : 8 à 63 caractères (ou vide pour un réseau ouvert)" % s["ssid"]
        iface = s.get("iface") or ""
        if iface and inter.get(iface) not in (None, "client"):
            return None, None, "« %s » demande %s, qui n'est pas en rôle client" % (s["ssid"], iface)
        ssids.append({"ssid": s["ssid"], "psk": psk or "", "actif": bool(s.get("actif", True)), "iface": iface})
    return inter, ssids, None


def keyfile(nom, ssid, psk, iface, auto, uid):
    lignes = ["[connection]", "id=%s" % nom, "uuid=%s" % uid, "type=wifi", "autoconnect=%s" % ("true" if auto else "false")]
    if iface:
        lignes.append("interface-name=%s" % iface)
    lignes += ["", "[wifi]", "mode=infrastructure", "ssid=%s" % ssid, ""]
    if psk:
        lignes += ["[wifi-security]", "key-mgmt=wpa-psk", "psk=%s" % psk, ""]
    lignes += ["[ipv4]", "method=auto", "never-default=true", "", "[ipv6]", "method=auto", "never-default=true", ""]
    return "\n".join(lignes)


def uuid_existant(chemin):
    try:
        m = re.search(r"^uuid=(\S+)", open(chemin, encoding="utf-8").read(), re.M)
        return m.group(1) if m else None
    except OSError:
        return None


def plan(inter, ssids):
    """-> [(nom de connexion, ssid, psk, iface, autoconnect)] des SSID actifs ; le premier de chaque interface client se connecte seul."""
    clients = [n for n, r in sorted(inter.items()) if r == "client"]
    deja, out = set(), []
    for s in ssids:
        if not s["actif"]:
            continue
        iface = s["iface"] or (clients[0] if len(clients) == 1 else "")
        auto = iface not in deja
        deja.add(iface)
        out.append((nom_connexion(s["ssid"]), s["ssid"], s["psk"], iface, auto))
    return out


def etat(run, reglage=REGLAGE):
    out = {"interfaces": []}
    for n in sorted(os.listdir("/sys/class/net")) if os.path.isdir("/sys/class/net") else []:
        if not os.path.isdir("/sys/class/net/%s/wireless" % n) and not os.path.isdir("/sys/class/net/%s/phy80211" % n):
            continue
        try:
            pilote = os.path.basename(os.readlink("/sys/class/net/%s/device/driver" % n))
        except OSError:
            pilote = ""
        try:
            macad = open("/sys/class/net/%s/address" % n).read().strip()
        except OSError:
            macad = ""
        _rc, info, _e = run(["iw", "dev", n, "info"])
        m = re.search(r"type (\w+)", info)
        out["interfaces"].append({"nom": n, "pilote": pilote, "mac": macad, "type": m.group(1) if m else None})
    _rc, dev, _e = run(["nmcli", "-t", "-f", "DEVICE,STATE,CONNECTION", "device"])
    for l in dev.splitlines():
        f = l.split(":")
        for i in out["interfaces"]:
            if f and f[0] == i["nom"]:
                i["nm"], i["connexion"] = (f[1] if len(f) > 1 else None), (f[2] if len(f) > 2 else None) or None
    _rc, con, _e = run(["nmcli", "-t", "-f", "NAME,DEVICE", "connection", "show"])
    out["connexions"] = [{"nom": l.split(":")[0], "active_sur": l.split(":")[1] or None} for l in con.splitlines() if l.startswith("si-")]
    try:
        out["reglage"] = json.load(open(reglage, encoding="utf-8"))
    except (OSError, ValueError):
        out["reglage"] = None
    return out


def debloquer_rfkill(racine="/sys/class/rfkill"):
    """#808 : lève le blocage logiciel (rfkill) des radios Wi-Fi -- sans l'outil rfkill (vu en réel : paquet manquant,
    radios bloquées, « Operation not possible due to RF-kill »). -> noms débloqués. Le blocage matériel reste."""
    out = []
    for d in sorted(os.listdir(racine)) if os.path.isdir(racine) else []:
        try:
            if open(os.path.join(racine, d, "type")).read().strip() != "wlan" or open(os.path.join(racine, d, "soft")).read().strip() != "1":
                continue
            with open(os.path.join(racine, d, "soft"), "w") as fh:
                fh.write("0")
            out.append(d)
        except OSError:
            pass
    return out


def appliquer(params, run, nm_dir=NM_CONNEXIONS, nm_conf=NM_CONF, reglage=REGLAGE):
    inter, ssids, err = valider(params)
    if err:
        return {"ok": False, "error": err}
    debloques = debloquer_rfkill() if nm_conf == NM_CONF else []
    voulues = plan(inter, ssids)
    garde = set(v[0] for v in voulues)
    ecrites, retirees = [], []
    os.makedirs(nm_dir, exist_ok=True)
    for nom, ssid, psk, iface, auto in voulues:
        chemin = os.path.join(nm_dir, nom + ".nmconnection")
        uid = uuid_existant(chemin) or str(uuid.uuid4())
        fd = os.open(chemin + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(keyfile(nom, ssid, psk, iface, auto, uid))
        os.replace(chemin + ".tmp", chemin)
        ecrites.append(nom)
    for f in os.listdir(nm_dir):
        if f.startswith("si-") and f.endswith(".nmconnection") and f[:-len(".nmconnection")] not in garde:
            run(["nmcli", "connection", "down", f[:-len(".nmconnection")]])
            os.remove(os.path.join(nm_dir, f))
            retirees.append(f[:-len(".nmconnection")])
    non_gerees = sorted(n for n, r in inter.items() if r in ("moniteur", "inactive"))
    os.makedirs(os.path.dirname(nm_conf), exist_ok=True)
    with open(nm_conf, "w", encoding="utf-8") as fh:
        fh.write("# #807 : interfaces de la sonde hors NetworkManager (écoute passive ou coupées), réglées depuis le hub\n[keyfile]\n")
        if non_gerees:
            fh.write("unmanaged-devices=%s\n" % ";".join("interface-name:%s" % n for n in non_gerees))
    if os.path.exists(ANCIENNE_CONF) and nm_conf == NM_CONF:
        os.remove(ANCIENNE_CONF)
    run(["systemctl", "reload", "NetworkManager"])
    run(["nmcli", "connection", "reload"])
    for n, r in sorted(inter.items()):
        run(["nmcli", "device", "set", n, "managed", "yes" if r == "client" else "no"])
        if r == "inactive":
            run(["ip", "link", "set", n, "down"])
    erreurs = []
    for nom, _s, _p, iface, auto in voulues:
        if auto and iface:
            rc, _o, e = run(["nmcli", "connection", "up", nom])
            if rc:
                erreurs.append("%s : %s" % (nom, (e or "").strip()[:160]))
    doc = {"interfaces": inter, "ssids": [{"ssid": s["ssid"], "connexion": nom_connexion(s["ssid"]), "iface": s["iface"], "actif": s["actif"], "ouvert": not s["psk"]} for s in ssids]}
    os.makedirs(os.path.dirname(reglage), exist_ok=True)
    with open(reglage + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
    os.chmod(reglage + ".tmp", 0o644)
    os.replace(reglage + ".tmp", reglage)
    return {"ok": not erreurs, "error": "; ".join(erreurs) or None, "connexions_ecrites": ecrites, "connexions_retirees": retirees,
            "non_gerees": non_gerees, "rfkill_leve": debloques, "reglage": doc}


def run(params, runner):
    a = (params or {}).get("action") or "etat"
    if a == "etat":
        return {"ok": True, "result": etat(runner)}
    if a == "appliquer":
        r = appliquer(params, runner)
        r["etat"] = etat(runner)
        return {"ok": r["ok"], "error": r.get("error"), "result": r}
    return {"ok": False, "error": "action inconnue : %s (etat, appliquer)" % a}


def reglage_lu(chemin=REGLAGE):
    """Pour wifi-probe / path-probe : (première interface client, connexions actives) du réglage, ou (None, [])."""
    try:
        d = json.load(open(chemin, encoding="utf-8"))
    except (OSError, ValueError):
        return None, []
    clients = [n for n, r in sorted((d.get("interfaces") or {}).items()) if r == "client"]
    return (clients[0] if clients else None), [s["connexion"] for s in d.get("ssids") or [] if s.get("actif")]
