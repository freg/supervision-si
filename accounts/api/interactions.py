# -*- coding: utf-8 -*-
"""Journal de nos interactions de travail (livraison #638) -- lit le CHANGELOG
du projet (source horodatée et fidèle de chaque livraison) et le restitue en
frise catégorisée + comptes-rendus par période. Aucune donnée inventée : ce
qui n'est pas dans le CHANGELOG n'apparaît pas. Les durées de conversation ne
sont pas disponibles (non journalisées) ; « minutes » = comptes-rendus.

Logique PURE (aucune E/S) : `parse_changelog`, `categorize`, `period_minutes`.
Le CHANGELOG est cuit dans l'image accounts-api au build (rafraîchi à chaque
déploiement), lu par la route /interactions.
"""
import re
from collections import Counter, defaultdict

# (catégorie lisible, motifs) -- premier motif trouvé (titre + corps) gagne ; ordre = priorité
CATEGORIES = [
    ("Sécurité & accès", r"keycloak|bastion|mtls|coffre|secret|\bca\b|pare-feu|firewall|defender|rdp|bureau à distance|autologon|périmètre|jeton|https|certificat|antivirus"),
    ("IA", r"\bia\b|assistant|ollama|cortex|mod[èe]le|llm|vox|embedding|whisper"),
    ("Réseau & infra", r"r[ée]seau|dns|wifi|wi-fi|nebula|mikrotik|cisco|vlan|proxmox|switch|sonde|netprobe|bande passante|bastion|nat|frontal|swarm|docker|image du poste|p2v|disk2vhd"),
    ("Agent & postes", r"agent|si-agent|windows|lanceur|watchdog|chien de garde|banc|d[ée]marrage|grub|uefi|mise à jour de l'agent|update|winlogon|session"),
    ("Hub & ergonomie", r"hub|tuile|ergonomie|[ée]cran|design|vue|menu|onglet|redesign|accueil|tableau|pied de page|footer|central local"),
    ("Exploitation", r"sauvegarde|ged|notification|licence|import|export|journal|tour de contr[ôo]le|d[ée]ploiement|zip"),
]
_DEFAULT_CAT = "Autre"
ENTRY_RE = re.compile(r"^##\s+(?P<date>\d{4}-\d{2}-\d{2})\s*[—-]\s*(?P<rest>.+?)\s*$", re.M)
DELIVERY_RE = re.compile(r"\(livraison\s*#?(\d+)[^)]*\)")


def categorize(text):
    low = (text or "").lower()
    for name, pat in CATEGORIES:
        if re.search(pat, low):
            return name
    return _DEFAULT_CAT


def parse_changelog(text):
    """CHANGELOG markdown -> [{date, delivery, title, category, summary}] (plus récent d'abord)."""
    text = text or ""
    marks = list(ENTRY_RE.finditer(text))
    entries = []
    for i, m in enumerate(marks):
        rest = m.group("rest").strip()
        body = text[m.end():marks[i + 1].start() if i + 1 < len(marks) else len(text)].strip()
        dm = DELIVERY_RE.search(rest)
        delivery = int(dm.group(1)) if dm else None
        title = DELIVERY_RE.sub("", rest).strip(" .—-")
        summary = re.sub(r"\s+", " ", body)[:400].strip()
        entries.append({"date": m.group("date"), "delivery": delivery, "title": title,
                        "category": categorize(title + " " + body), "summary": summary})
    entries.sort(key=lambda e: (e["date"], e["delivery"] or 0), reverse=True)
    return entries


def _period_key(date, by):
    y, mo, d = (int(x) for x in date.split("-"))
    if by == "day":
        return date
    if by == "month":
        return "%04d-%02d" % (y, mo)
    # semaine ISO
    import datetime
    iso = datetime.date(y, mo, d).isocalendar()
    return "%04d-S%02d" % (iso[0], iso[1])


def period_minutes(entries, by="week"):
    """Comptes-rendus par période : [{period, count, categories:{cat:n}, deliveries:[..], summary}]."""
    groups = defaultdict(list)
    for e in entries:
        groups[_period_key(e["date"], by)].append(e)
    out = []
    for period in sorted(groups, reverse=True):
        items = groups[period]
        cats = Counter(e["category"] for e in items)
        dels = sorted(e["delivery"] for e in items if e["delivery"])
        titles = "; ".join(e["title"] for e in items[:8])
        out.append({"period": period, "count": len(items), "categories": dict(cats),
                    "deliveries": dels, "summary": titles[:500]})
    return out


def timeline(text, category=None, query=None):
    """Frise filtrée (catégorie, recherche texte) + agrégats."""
    entries = parse_changelog(text)
    if category:
        entries = [e for e in entries if e["category"] == category]
    if query:
        q = query.lower()
        entries = [e for e in entries if q in (e["title"] + " " + e["summary"]).lower()]
    by_cat = Counter(e["category"] for e in entries)
    span = None
    if entries:
        span = {"from": entries[-1]["date"], "to": entries[0]["date"]}
    return {"entries": entries, "total": len(entries), "by_category": dict(by_cat),
            "categories": [c for c, _ in CATEGORIES] + [_DEFAULT_CAT], "span": span}
