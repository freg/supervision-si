#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""si-veille (livraison #841) : veilleur LOCAL et autonome de la chaîne d'accès au hub (DNS, frontal https, certificats,
ports, canal de contrôle du bastion, conteneurs vus par ssh…). Tourne dans la session de l'utilisateur, sans le hub
(il doit justement voir quand le hub tombe), bibliothèque standard seule.

  - SILENCIEUX tant que tout va bien (seulement son journal) ;
  - en cas de problème : notification graphique RÉCURRENTE (toutes les `rappel_min` minutes tant que ça dure) et UN
    courriel au début de l'incident (un second, « rétabli », seulement si demandé) ;
  - vérifications chaînées (`depend_de`) : quand un maillon tombe, ceux qui en dépendent ne sont pas testés et
    l'alerte nomme la cause probable (le premier maillon en échec) ; `seuil_echecs` évite les fausses alertes.
Types : dns, tcp, tls (nom attendu, autorité, jours avant expiration), http (code, texte attendu, certificat), commande
(code de sortie 0 ; ex. ssh super 'docker ps …'). Configuration : ~/.config/si-veille/config.json (les vraies adresses
restent hors dépôt). Pur et testé : ordonner, evaluer_incident, decider_notifications, valider."""
import email.message
import json
import os
import platform
import shutil
import smtplib
import socket
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request

VERSION = "1.1.0"
CONF = os.path.expanduser(os.environ.get("SI_VEILLE_CONF", "~/.config/si-veille/config.json"))
ETAT = os.path.expanduser(os.environ.get("SI_VEILLE_ETAT", "~/.local/state/si-veille/etat.json"))
JOURNAL = os.path.expanduser(os.environ.get("SI_VEILLE_JOURNAL", "~/.local/state/si-veille/journal.log"))
TYPES = ("dns", "tcp", "tls", "http", "commande", "veille_hub")
DEFAUT = {"intervalle_s": 120, "rappel_min": 5, "seuil_echecs": 2, "mail_retabli": False, "mail": {}, "verifs": []}


# -- configuration ----------------------------------------------------------------------------------------------------
def valider(conf):
    """-> (conf complétée, None) ou (None, erreur)."""
    c = dict(DEFAUT)
    c.update(conf or {})
    ids = set()
    for v in c["verifs"]:
        if not v.get("id") or v["id"] in ids:
            return None, "vérification sans id ou id en double : %r" % v.get("id")
        if v.get("type") not in TYPES:
            return None, "%s : type parmi %s" % (v["id"], ", ".join(TYPES))
        ids.add(v["id"])
    for v in c["verifs"]:
        for d in v.get("depend_de") or []:
            if d not in ids:
                return None, "%s dépend de %s, inconnu" % (v["id"], d)
    try:
        ordonner(c["verifs"])
    except ValueError as e:
        return None, str(e)
    return c, None


def ordonner(verifs):
    """Ordre de test : un maillon après ceux dont il dépend (cycle -> erreur)."""
    par_id = {v["id"]: v for v in verifs}
    fait, ordre, en_cours = set(), [], set()

    def visiter(i):
        if i in fait:
            return
        if i in en_cours:
            raise ValueError("dépendances en boucle autour de %s" % i)
        en_cours.add(i)
        for d in par_id[i].get("depend_de") or []:
            visiter(d)
        en_cours.discard(i)
        fait.add(i)
        ordre.append(par_id[i])
    for v in verifs:
        visiter(v["id"])
    return ordre


# -- vérifications ----------------------------------------------------------------------------------------------------
def _ctx(v):
    ctx = ssl.create_default_context(cafile=os.path.expanduser(v["ca"]) if v.get("ca") else None)
    if v.get("sans_verif_nom"):
        ctx.check_hostname = False
    return ctx


def verifier(v, maintenant=None):
    """-> (ok, détail)."""
    t = v["type"]
    delai = float(v.get("delai_s") or 10)
    try:
        if t == "dns":
            adr = sorted({a[4][0] for a in socket.getaddrinfo(v["nom_hote"], None)})
            if v.get("attendu") and v["attendu"] not in adr:
                return False, "résout en %s, %s attendu" % (", ".join(adr), v["attendu"])
            return True, ", ".join(adr)
        if t == "tcp":
            with socket.create_connection((v["hote"], int(v["port"])), timeout=delai):
                return True, "ouvert"
        if t == "tls":
            nom = v.get("nom_attendu") or v["hote"]
            with socket.create_connection((v["hote"], int(v["port"])), timeout=delai) as s:
                with _ctx(v).wrap_socket(s, server_hostname=nom) as tls:
                    cert = tls.getpeercert()
            reste = (ssl.cert_time_to_seconds(cert["notAfter"]) - (maintenant or time.time())) / 86400
            if reste < float(v.get("jours_min") or 14):
                return False, "certificat de %s expire dans %.0f jour(s)" % (nom, reste)
            return True, "certificat valide pour %s, encore %.0f j" % (nom, reste)
        if t == "http":
            req = urllib.request.Request(v["url"], headers={"User-Agent": "si-veille/" + VERSION})
            try:
                with urllib.request.urlopen(req, timeout=delai, context=_ctx(v) if v["url"].startswith("https") else None) as r:
                    code, corps = r.status, r.read(200000).decode("utf-8", "replace")
            except urllib.error.HTTPError as e:
                code, corps = e.code, ""
            attendus = v.get("codes") or [200, 301, 302, 303, 307, 308, 401]
            if code not in attendus:
                return False, "HTTP %s (attendu %s)" % (code, "/".join(map(str, attendus)))
            if v.get("contient") and v["contient"] not in corps:
                return False, "HTTP %s mais « %s » absent de la page" % (code, v["contient"])
            return True, "HTTP %s" % code
        if t == "veille_hub":
            # veille d'un hub (ex. réseau d'un site : /api/nebula/veille/resume?jeton=…) : panne -> échec, dégradé ->
            # doute (orange), détail par vérification dans le menu de l'icône
            req = urllib.request.Request(v["url"], headers={"User-Agent": "si-veille/" + VERSION, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=delai, context=_ctx(v) if v["url"].startswith("https") else None) as r:
                d = json.loads(r.read(2_000_000).decode("utf-8", "replace"))
            sous = [{"nom": x.get("nom"), "statut": {"ok": "ok", "ko": "ko", "doute": "doute"}.get(x.get("statut"), "non_teste"), "detail": x.get("detail") or ""}
                    for x in d.get("verifs") or [] if x.get("statut") != "ok" or v.get("tout_montrer")]
            etat = d.get("etat")
            if etat == "maintenance":                       # pause planifiée du hub (fermeture, travaux) : ni alerte ni doute
                return (True, d.get("resume") or "en pause", {"sous": [], "doute": False})
            return (etat != "panne", ("dégradé : " if etat == "degrade" else "") + (d.get("resume") or etat or "?"),
                    {"sous": sous, "doute": etat == "degrade"})
        if t == "commande":
            r = subprocess.run(v["commande"], shell=True, capture_output=True, text=True, timeout=delai)
            if r.returncode:
                return False, "code %d : %s" % (r.returncode, ((r.stderr or r.stdout or "").strip().splitlines() or [""])[-1][:200])
            return True, (r.stdout or "").strip()[:120] or "ok"
    except subprocess.TimeoutExpired:
        return False, "délai dépassé (%s s)" % delai
    except ssl.SSLCertVerificationError as e:
        return False, "certificat refusé : %s" % (e.verify_message or e)
    except (OSError, ValueError, ssl.SSLError) as e:
        return False, str(getattr(e, "reason", None) or e)[:200]
    return False, "type inconnu"


def passer(conf, etat, maintenant=None, verif=verifier):
    """Un tour : chaque maillon dans l'ordre ; ceux dont un parent est en échec ne sont pas testés."""
    t = maintenant or time.time()
    res = {}
    for v in ordonner(conf["verifs"]):
        parents_ko = [d for d in v.get("depend_de") or [] if res.get(d, {}).get("statut") in ("ko", "non_teste")]
        if parents_ko:
            res[v["id"]] = {"statut": "non_teste", "detail": "non testé : %s en échec" % ", ".join(parents_ko)}
            continue
        r = verif(v, t)
        ok, detail, extra = r[0], r[1], (r[2] if len(r) > 2 else {})
        e = etat.setdefault("verifs", {}).setdefault(v["id"], {"echecs": 0})
        e["echecs"] = 0 if ok else e["echecs"] + 1
        e["dernier"], e["detail"] = t, detail
        seuil = int(v.get("seuil_echecs") or conf["seuil_echecs"])
        res[v["id"]] = {"statut": ("doute" if extra.get("doute") else "ok") if ok else ("ko" if e["echecs"] >= seuil else "doute"), "detail": detail,
                        "nom": v.get("nom") or v["id"]}
        if extra.get("sous") is not None:
            res[v["id"]]["sous"] = extra["sous"][:40]
    return res


def evaluer_incident(conf, res):
    """Résultats d'un tour -> None (tout va bien) ou {cause, echecs: [(id, nom, détail)], non_testes: n}."""
    ko = [(i, r.get("nom") or i, r["detail"]) for i, r in res.items() if r["statut"] == "ko"]
    if not ko:
        return None
    ordre = [v["id"] for v in ordonner(conf["verifs"])]
    ko.sort(key=lambda x: ordre.index(x[0]))
    return {"cause": ko[0], "echecs": ko, "non_testes": sum(1 for r in res.values() if r["statut"] == "non_teste")}


def decider_notifications(conf, etat, incident, maintenant):
    """-> liste de gestes : ('graphique', texte) récurrent, ('mail', sujet, texte) une fois par incident, et la fin."""
    gestes = []
    inc = etat.get("incident")
    if incident:
        cle = sorted(e[0] for e in incident["echecs"])
        texte = "Cause probable : %s — %s" % (incident["cause"][1], incident["cause"][2])
        if len(incident["echecs"]) > 1:
            texte += " (+%d autre(s) maillon(s) en échec)" % (len(incident["echecs"]) - 1)
        if incident["non_testes"]:
            texte += " ; %d maillon(s) en aval non testé(s)" % incident["non_testes"]
        if not inc:
            inc = etat["incident"] = {"debut": maintenant, "mail": False, "dernier_graphique": 0, "cle": cle}
        inc["cle"], inc["texte"] = cle, texte
        if maintenant - inc["dernier_graphique"] >= conf["rappel_min"] * 60:
            gestes.append(("graphique", "Chaîne du hub en panne", texte))
            inc["dernier_graphique"] = maintenant
        if not inc["mail"]:
            corps = "Panne détectée le %s par si-veille (%s).\n\n%s\n\nMaillons en échec :\n%s\n" % (
                time.strftime("%d/%m/%Y %H:%M", time.localtime(inc["debut"])), socket.gethostname(), texte,
                "\n".join("- %s : %s" % (n, d) for _i, n, d in incident["echecs"]))
            gestes.append(("mail", "[si-veille] panne : %s" % incident["cause"][1], corps))
            inc["mail"] = True
    elif inc:
        duree = int((maintenant - inc["debut"]) / 60)
        gestes.append(("graphique", "Chaîne du hub rétablie", "Rétablie après %d min (%s)" % (duree, inc.get("texte", ""))))
        if conf.get("mail_retabli") and inc.get("mail"):
            gestes.append(("mail", "[si-veille] rétabli", "Chaîne rétablie après %d min.\n\n%s\n" % (duree, inc.get("texte", ""))))
        etat["incident"] = None
    return gestes


# -- notifications ----------------------------------------------------------------------------------------------------
def notifier_graphique(titre, texte):
    if platform.system() == "Darwin" and shutil.which("osascript"):
        subprocess.run(["osascript", "-e", 'display notification "%s" with title "%s" sound name "Basso"' % (texte.replace('"', "'")[:240], titre.replace('"', "'"))],
                       capture_output=True, timeout=15)
    elif shutil.which("notify-send"):
        subprocess.run(["notify-send", "-u", "critical", "-a", "si-veille", titre, texte[:400]], capture_output=True, timeout=15)
    else:
        print("%s : %s" % (titre, texte), file=sys.stderr, flush=True)


def _secret(nom):
    try:
        if platform.system() == "Darwin":
            return subprocess.run(["security", "find-generic-password", "-s", "si-veille", "-a", nom, "-w"], capture_output=True, text=True, check=True).stdout.rstrip("\n")
        if shutil.which("secret-tool"):
            r = subprocess.run(["secret-tool", "lookup", "service", "si-veille", "compte", nom], capture_output=True, text=True)
            if r.returncode == 0 and r.stdout:
                return r.stdout.rstrip("\n")
        return json.load(open(os.path.expanduser("~/.config/si-veille/secrets.json"))).get(nom)
    except (OSError, ValueError, subprocess.CalledProcessError):
        return None


def envoyer_mail(conf, sujet, texte):
    m = conf.get("mail") or {}
    if not (m.get("hote") and m.get("a")):
        journal("courriel non configuré : %s" % sujet)
        return False
    msg = email.message.EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = m.get("de") or m.get("utilisateur") or "si-veille", m["a"], sujet
    msg.set_content(texte)
    port = int(m.get("port") or 587)
    srv = smtplib.SMTP_SSL(m["hote"], port, timeout=20) if port == 465 else smtplib.SMTP(m["hote"], port, timeout=20)
    with srv:
        if port != 465 and m.get("starttls", True):
            srv.starttls(context=ssl.create_default_context())
        if m.get("utilisateur"):
            srv.login(m["utilisateur"], _secret("smtp") or "")
        srv.send_message(msg)
    return True


def journal(ligne):
    os.makedirs(os.path.dirname(JOURNAL), exist_ok=True)
    with open(JOURNAL, "a") as fh:
        fh.write(time.strftime("%Y-%m-%d %H:%M:%S ") + ligne + "\n")


def _lire_etat():
    try:
        return json.load(open(ETAT))
    except (OSError, ValueError):
        return {}


def _ecrire_etat(e):
    os.makedirs(os.path.dirname(ETAT), exist_ok=True)
    with open(ETAT + ".tmp", "w") as fh:
        json.dump(e, fh)
    os.replace(ETAT + ".tmp", ETAT)


def tour(conf):
    etat = _lire_etat()
    t = time.time()
    res = passer(conf, etat, t)
    inc = evaluer_incident(conf, res)
    for g in decider_notifications(conf, etat, inc, t):
        try:
            if g[0] == "graphique":
                al = etat.setdefault("alertes", [])               # #845 : lues par l'icône de la barre du haut
                al.append({"ts": t, "titre": g[1], "texte": g[2]})
                del al[:-50]
                notifier_graphique(g[1], g[2])
            else:
                envoyer_mail(conf, g[1], g[2])
            journal("%s : %s" % (g[0], g[1]))
        except Exception as e:  # noqa: BLE001 -- une notification ratée n'arrête pas la veille
            journal("ERREUR %s : %s" % (g[0], e))
            if g[0] == "mail" and etat.get("incident"):
                etat["incident"]["mail"] = False  # réseau coupé côté poste, SMTP muet… : on réessaiera au tour suivant
    if inc:
        journal("panne : " + etat["incident"]["texte"])
    etat["dernier_tour"], etat["resultats"], etat["intervalle_s"] = t, res, conf["intervalle_s"]
    etat["ordre"] = [v["id"] for v in ordonner(conf["verifs"])]
    _ecrire_etat(etat)
    return res


def main():
    try:
        conf, err = valider(json.load(open(CONF)))
    except (OSError, ValueError) as e:
        conf, err = None, "configuration illisible (%s) : %s" % (CONF, e)
    if err:
        print(err, file=sys.stderr)
        sys.exit(2)
    if "--tester-notif" in sys.argv:
        notifier_graphique("si-veille", "Essai de notification graphique")
        try:
            print("courriel envoyé" if envoyer_mail(conf, "[si-veille] essai", "Essai d'envoi de si-veille (%s)." % socket.gethostname()) else "courriel non configuré")
        except Exception as e:  # noqa: BLE001
            print("ERREUR courriel : %s" % e, file=sys.stderr)
            sys.exit(1)
        return
    if "--une-fois" in sys.argv or "--etat" in sys.argv:
        res = tour(conf) if "--une-fois" in sys.argv else (_lire_etat().get("resultats") or {})
        for v in ordonner(conf["verifs"]):
            r = res.get(v["id"], {})
            print("%-9s %-32s %s" % ({"ok": "OK", "ko": "ÉCHEC", "doute": "douteux", "non_teste": "—"}.get(r.get("statut"), "?"), v.get("nom") or v["id"], r.get("detail", "")))
        return
    journal("démarrage (%d maillon(s), toutes les %d s)" % (len(conf["verifs"]), conf["intervalle_s"]))
    while True:
        try:
            tour(conf)
        except Exception as e:  # noqa: BLE001
            journal("ERREUR tour : %s" % e)
        time.sleep(conf["intervalle_s"])


if __name__ == "__main__":
    main()
