# -*- coding: utf-8 -*-
"""Recherche sur tout le réseau du site (livraison #852) -- logique PURE, testée (tests/test_recherche.py).
Appareils, clients (nom, IP, MAC, fabricant, système, SSID, VLAN, signal, dates), VLAN, fiches du campus, anomalies :
chaque enregistrement est aplati en texte (dates lisibles « jj/mm/aaaa hh:mm », signal en dBm) ; tous les mots de la
saisie doivent s'y trouver, sans casse ni accents ; une MAC se cherche avec ou sans séparateurs."""
import re
import time
import unicodedata


def plier(s):
    s = unicodedata.normalize("NFD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s)


def _date(v):
    try:
        v = float(v)
    except (TypeError, ValueError):
        return None
    if v > 1e11:
        v /= 1000.0
    if 1e9 < v < 4e9:
        return time.strftime("%d/%m/%Y %H:%M", time.localtime(v))
    return None


def aplatir(obj, cle=""):
    """-> [(chemin, valeur texte)] ; dates et signaux rendus lisibles."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out += aplatir(v, ("%s.%s" % (cle, k)) if cle else str(k))
    elif isinstance(obj, (list, tuple)):
        for v in obj[:50]:
            out += aplatir(v, cle)
    elif obj not in (None, ""):
        t = str(obj)
        bas = cle.lower()
        if bas.endswith("at") or any(m in bas for m in ("seen", "date", "time")):
            t = _date(obj) or t
        if "signal" in bas or "rssi" in bas:
            t = "%s dBm" % t if re.match(r"^-?\d+(\.\d+)?$", t) else t
        out.append((cle, t))
        h = re.sub(r"[^0-9a-f]", "", t.lower())
        if re.match(r"^([0-9a-f]{2}[:-]){5}[0-9a-f]{2}$", t.lower()):
            out.append((cle, h))                                   # MAC sans séparateurs
    return out


def chercher(q, sources, limite=100):
    """sources : [(type, titre(obj), lien(obj), [obj…])] -> [{type, titre, lien, champs: [(chemin, valeur)]}]."""
    mots = [m for m in plier(q).split() if m]
    mots = [re.sub(r"[:\-.]", "", m) if re.match(r"^([0-9a-f]{2}[:\-.]?){3,6}$", m) and len(re.sub(r"[:\-.]", "", m)) >= 6 else m for m in mots]
    if not mots:
        return []
    res = []
    for typ, titre, lien, objets in sources:
        for o in objets or []:
            champs = aplatir(o)
            texte = plier(" ".join(v for _c, v in champs))
            if all(m in texte for m in mots):
                touches = [(c, v) for c, v in champs if any(m in plier(v) for m in mots)]
                res.append({"type": typ, "titre": titre(o), "lien": lien(o), "champs": touches[:6]})
                if len(res) >= limite:
                    return res
    return res
