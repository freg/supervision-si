#!/usr/bin/env python3
"""Sonde sms-gateway (#792) : la passerelle SMS 4G (TRB140 + son relais HTTP) envoie-t-elle vraiment ?
1. envoi d'un SMS de test : GET <relais>/send?number=…&message=…&key=… (clé lue dans un fichier root) -> HTTP 200 attendu ;
2. facultatif : état du modem par l'API du TRB140 (POST /api/login, GET /api/modems/status) : enregistrement réseau,
   opérateur, type de réseau, signal.
Astuce : --numero = le numéro de la SIM du TRB140 lui-même (le test ne dérange personne).
Sortie JSON : {at, envoi{}, modem{}, alerts[], error}. Stdlib seulement."""
import json
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

DOSSIER = "/etc/si-agent/sms-gateway"
SIGNAL_FAIBLE = -100          # dBm (RSSI) : en dessous, envoi incertain


def args_locaux(argv, chemin):
    """#792 : arguments de l'hôte dans un fichier root (« --option valeur » par ligne, # = commentaire), ajoutés à ceux du
    catalogue -- les cibles réelles (IP, comptes) restent sur la machine, jamais dans le dépôt ni le catalogue central."""
    try:
        for l in open(chemin, encoding="utf-8"):
            l = l.strip()
            if l and not l.startswith("#"):
                o, _, v = l.partition(" ")
                argv = argv + ([o, v.strip()] if v.strip() else [o])
    except OSError:
        pass
    return argv


def lire_fichier(p):
    with open(p, encoding="utf-8") as fh:
        return fh.read().strip()


def _ctx():
    c = ssl.create_default_context()
    c.check_hostname = False
    c.verify_mode = ssl.CERT_NONE          # TRB140 : certificat auto-signé
    return c


def http(url, data=None, headers=None, timeout=40):
    req = urllib.request.Request(url, data=data, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_ctx()) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")


def envoyer(relais, numero, cle, texte, http=http):
    url = relais.rstrip("/") + "/send?" + urllib.parse.urlencode({"number": numero, "message": texte, "key": cle})
    t0 = time.monotonic()
    try:
        code, corps = http(url)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "http": None, "duree_s": None, "reponse": "relais injoignable : %s" % str(exc)[:150]}
    return {"ok": code == 200, "http": code, "duree_s": round(time.monotonic() - t0, 1), "reponse": corps.strip()[:200]}


def _val(d, *noms):
    for n in noms:
        for k, v in (d or {}).items():
            if k.lower() == n and v not in (None, ""):
                return v
    return None


def etat_modem(statuts):
    """Réponse de /api/modems/status (RutOS 7, champs selon versions) -> {operateur, reseau, enregistre, signal_dbm, brut}."""
    data = statuts.get("data") if isinstance(statuts, dict) else statuts
    m = data[0] if isinstance(data, list) and data else (data if isinstance(data, dict) else {})
    reseau = str(_val(m, "conntype", "net_mode", "network_type", "service_mode", "ntype") or "")
    enreg = str(_val(m, "netstate", "state", "registration", "net_state") or "")
    sig = _val(m, "rssi", "signal")
    try:
        sig = int(float(sig))
    except (TypeError, ValueError):
        sig = None
    return {"operateur": _val(m, "operator", "provider", "oper"), "reseau": reseau, "enregistre": enreg, "signal_dbm": sig,
            "brut": {k: m[k] for k in list(m)[:25] if not isinstance(m[k], (dict, list))}}


def modem(trb, compte, mdp, http=http):
    code, corps = http(trb.rstrip("/") + "/api/login", data=json.dumps({"username": compte, "password": mdp}).encode(),
                       headers={"Content-Type": "application/json"})
    if code != 200:
        raise RuntimeError("connexion au TRB140 refusée (HTTP %s)" % code)
    jeton = json.loads(corps)["data"]["token"]
    code, corps = http(trb.rstrip("/") + "/api/modems/status", headers={"Authorization": "Bearer " + jeton})
    if code != 200:
        raise RuntimeError("état du modem illisible (HTTP %s)" % code)
    return etat_modem(json.loads(corps))


def alerts_for(envoi, mod):
    out = []
    if envoi and not envoi["ok"]:
        out.append({"code": "sms-gateway-send", "severity": "critical",
                    "message": "passerelle SMS 4G : l'envoi de test a échoué (HTTP %s) : %s" % (envoi["http"], envoi["reponse"][:150])})
    if mod and mod.get("error"):
        out.append({"code": "sms-gateway-modem-api", "severity": "warning", "message": "TRB140 : %s" % mod["error"][:150]})
    elif mod:
        e = (mod.get("enregistre") or "").lower()
        negatif = any(x in e for x in ("not", "non ", "unknown", "denied", "searching", "refus", "inconnu"))
        if e and (negatif or not any(x in e for x in ("registered", "home", "roaming", "enregistr", "connected"))):
            out.append({"code": "sms-gateway-unregistered", "severity": "critical", "message": "TRB140 : modem non enregistré sur le réseau (%s)" % e})
        r = (mod.get("reseau") or "").upper()
        if r and not any(x in r for x in ("LTE", "4G", "5G", "NR")):
            out.append({"code": "sms-gateway-fallback", "severity": "warning", "message": "TRB140 : réseau %s (pas en 4G)" % r})
        if mod.get("signal_dbm") is not None and mod["signal_dbm"] < SIGNAL_FAIBLE:
            out.append({"code": "sms-gateway-signal", "severity": "warning", "message": "TRB140 : signal faible (%d dBm)" % mod["signal_dbm"]})
    return out


def collect(argv, http=http):
    def arg(n, d=None):
        return argv[argv.index(n) + 1] if n in argv[:-1] else d
    out = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "envoi": None, "modem": None, "alerts": [], "error": None}
    relais, numero = arg("--relais"), arg("--numero")
    if relais and numero:
        try:
            cle = lire_fichier(arg("--cle-fichier", DOSSIER + "/relay_key"))
            out["envoi"] = envoyer(relais, numero, cle, arg("--texte", "test passerelle SMS 4G %s" % time.strftime("%d/%m %H:%M")), http)
        except OSError as exc:
            out["error"] = "clé du relais illisible : %s" % exc
    else:
        out["error"] = "--relais et --numero requis pour l'envoi de test"
    if arg("--trb"):
        try:
            out["modem"] = modem(arg("--trb"), arg("--trb-compte", "admin"), lire_fichier(arg("--trb-mdp-fichier", DOSSIER + "/trb_password")), http)
        except Exception as exc:  # noqa: BLE001
            out["modem"] = {"error": str(exc)[:200]}
    out["alerts"] = alerts_for(out["envoi"], out["modem"])
    return out


if __name__ == "__main__":
    print(json.dumps(collect(args_locaux(sys.argv[1:], DOSSIER + "/args")), ensure_ascii=False))
