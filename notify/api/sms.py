# -*- coding: utf-8 -*-
"""#787 : SMS internes du hub -- logique pure (numéros, destinataires, texte, champs reçus).

Canal distinct de celui du client externe (Didier) : notify-api envoie par le relais du TRB140 avec SA propre clé
(NOTIFY_SMS_RELAY_KEY, utilisateur dédié du relais), garde son historique (sortants, entrants) et sa file d'envoi."""
import re

NUM_RE = re.compile(r"^\+[1-9]\d{7,14}$")
CHAMPS_DE = ("de", "from", "sender", "number", "phone")
CHAMPS_TEXTE = ("texte", "text", "message", "msg", "body")
TEXTE_MAX = 640   # 4 SMS concaténés au plus


def normaliser(n):
    """336… / 06… / 0033… / +336… (espaces, points, tirets admis) -> +336… ; None si ce n'est pas un numéro."""
    n = re.sub(r"[\s.\-()]", "", str(n or ""))
    if n.startswith("00"):
        n = "+" + n[2:]
    elif re.match(r"^0[1-9]\d{8}$", n):
        n = "+33" + n[1:]
    elif re.match(r"^[1-9]\d{7,14}$", n):
        n = "+" + n
    return n if NUM_RE.match(n) else None


def destinataires(v, maxi=20):
    """Chaîne « a,b c » ou liste -> (numéros normalisés uniques, rejetés)."""
    items = v if isinstance(v, list) else re.split(r"[,;\n]+", str(v or ""))   # espaces admis DANS un numéro
    ok, bad = [], []
    for it in items:
        if not str(it).strip():
            continue
        n = normaliser(it)
        if n is None:
            bad.append(str(it).strip()[:40])
        elif n not in ok:
            ok.append(n)
    return ok[:maxi], bad


def texte(v):
    return str(v or "").replace("\r\n", "\n").strip()[:TEXTE_MAX]


def premier(champs, noms):
    """Premier champ non vide parmi `noms` (clés comparées en minuscules)."""
    low = {str(k).lower(): v for k, v in (champs or {}).items()}
    return next((str(low[k]) for k in noms if low.get(k)), "")


def segments(t):
    """Nombre de SMS facturés (approximation : 160 caractères seuls, 153 en concaténé ; 70/67 hors alphabet GSM)."""
    gsm = all(ord(ch) < 128 or ch in "éèùìòÇØøÅåÄÖÑÜäöñüà£¥§¿¡" for ch in t)
    seul, suite = (160, 153) if gsm else (70, 67)
    n = len(t)
    return 1 if n <= seul else -(-n // suite)
