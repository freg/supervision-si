"""#894 : conservation des messages syslog reçus -- un fichier JSON-lignes par émetteur et par jour, purgé au-delà
de RSYSLOG_RETENTION_DAYS ; liste d'émetteurs autorisés (RSYSLOG_ALLOWED, adresses ou réseaux) ; recherche.

Arborescence : <dir>/<adresse de l'émetteur>/<AAAA-MM-JJ>.jsonl, une ligne {t, ip, niveau, sev, fac, hote, app, msg}.
Le message brut n'est jamais réinterprété : seul le texte reçu (décodé UTF-8, repli Windows-1252) est conservé.
"""
import ipaddress
import json
import os
import re
import shutil
import time

SEV = ["urgence", "alerte", "critique", "erreur", "avertissement", "notice", "info", "debug"]
PRI = re.compile(r"^<(\d{1,3})>")
R3164 = re.compile(r"^<\d{1,3}>(?:[A-Z][a-z]{2} [ \d]\d \d\d:\d\d:\d\d )?(?:(\S+) )?([^:\[\s]+)(?:\[\d+\])?: ?(.*)$", re.S)
R5424 = re.compile(r"^<\d{1,3}>1 \S+ (\S+) (\S+) \S+ \S+ (?:-|\[.*?\]) ?(.*)$", re.S)
_IP_SURE = re.compile(r"^[0-9a-fA-F:.]+$")


def reseaux(texte):
    """« 192.168.0.182, 10.0.0.0/8 » -> [réseaux] ; vide -> [] (tout émetteur accepté)."""
    out = []
    for x in re.split(r"[\s,;]+", texte or ""):
        if x:
            out.append(ipaddress.ip_network(x, strict=False))
    return out


def autorise(ip, nets):
    if not nets:
        return True
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(a in n for n in nets)


def analyser(texte):
    """Message syslog brut -> {sev, fac, hote, app, msg} (sans réinterprétation au-delà de l'en-tête)."""
    m = PRI.match(texte)
    pri = int(m.group(1)) if m else 13
    sev, fac = pri % 8, pri // 8
    hote, app, msg = "", "", texte
    r = R5424.match(texte) or R3164.match(texte)
    if r:
        hote, app, msg = (r.group(1) or "").strip("-"), (r.group(2) or "").strip("-"), r.group(3)
    elif m:
        msg = texte[m.end():]
    return {"sev": sev, "niveau": SEV[sev], "fac": fac, "hote": hote, "app": app, "msg": msg.strip()[:4000]}


def decoder(data):
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return data.decode("cp1252", "replace")   # RouterOS et vieux équipements : codage du poste


class Journal:
    def __init__(self, dossier, retention_jours=90):
        self.dossier = dossier
        self.retention = retention_jours
        self._purge = 0.0

    def ecrire(self, ip, texte, t=None):
        if not _IP_SURE.match(ip or ""):
            return None
        t = t or time.time()
        e = dict(analyser(texte), t=round(t, 3), ip=ip)
        rep = os.path.join(self.dossier, ip.replace(":", "_"))
        os.makedirs(rep, exist_ok=True)
        with open(os.path.join(rep, time.strftime("%Y-%m-%d", time.localtime(t)) + ".jsonl"), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(e, ensure_ascii=False) + "\n")
        if t - self._purge > 3600:
            self._purge = t
            self.purger(t)
        return e

    def purger(self, now=None):
        limite = time.strftime("%Y-%m-%d", time.localtime((now or time.time()) - self.retention * 86400))
        n = 0
        for ip in self.emetteurs_ips():
            rep = os.path.join(self.dossier, ip)
            for f in os.listdir(rep):
                if f.endswith(".jsonl") and f[:10] < limite:
                    os.remove(os.path.join(rep, f))
                    n += 1
            if not os.listdir(rep):
                shutil.rmtree(rep, ignore_errors=True)
        return n

    def emetteurs_ips(self):
        try:
            return sorted(d for d in os.listdir(self.dossier) if os.path.isdir(os.path.join(self.dossier, d)))
        except OSError:
            return []

    def emetteurs(self):
        out = []
        for ip in self.emetteurs_ips():
            rep = os.path.join(self.dossier, ip)
            jours = sorted(f[:10] for f in os.listdir(rep) if f.endswith(".jsonl"))
            dernier, hote, n_jour = None, "", 0
            if jours:
                with open(os.path.join(rep, jours[-1] + ".jsonl"), encoding="utf-8", errors="replace") as fh:
                    lignes = fh.readlines()
                n_jour = len(lignes)
                try:
                    e = json.loads(lignes[-1])
                    dernier, hote = e.get("t"), e.get("hote") or ""
                except (ValueError, IndexError):
                    pass
            out.append({"ip": ip.replace("_", ":"), "hote": hote, "dernier": dernier, "jours": len(jours), "premier_jour": jours[0] if jours else None,
                        "messages_dernier_jour": n_jour})
        return out

    def chercher(self, emetteur=None, q=None, sev_max=7, depuis=None, jusque=None, limite=500):
        """Plus récents d'abord. q : sous-chaîne (insensible à la casse) du message, de l'application ou de l'hôte."""
        q = (q or "").lower()
        ips = [emetteur.replace(":", "_")] if emetteur else self.emetteurs_ips()
        fichiers = []
        for ip in ips:
            rep = os.path.join(self.dossier, ip)
            if not os.path.isdir(rep) or "/" in ip or ip.startswith("."):
                continue
            for f in os.listdir(rep):
                if f.endswith(".jsonl"):
                    jour = f[:10]
                    if depuis and jour < time.strftime("%Y-%m-%d", time.localtime(depuis)):
                        continue
                    if jusque and jour > time.strftime("%Y-%m-%d", time.localtime(jusque)):
                        continue
                    fichiers.append((jour, os.path.join(rep, f)))
        out = []
        for _jour, chemin in sorted(fichiers, reverse=True):
            with open(chemin, encoding="utf-8", errors="replace") as fh:
                lignes = fh.readlines()
            for l in reversed(lignes):
                try:
                    e = json.loads(l)
                except ValueError:
                    continue
                if e.get("sev", 7) > sev_max or (depuis and e["t"] < depuis) or (jusque and e["t"] > jusque):
                    continue
                if q and q not in ("%s %s %s" % (e.get("msg", ""), e.get("app", ""), e.get("hote", ""))).lower():
                    continue
                out.append(e)
                if len(out) >= limite:
                    return sorted(out, key=lambda x: -x["t"])
        return sorted(out, key=lambda x: -x["t"])
