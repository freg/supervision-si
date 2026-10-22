# -*- coding: utf-8 -*-
"""Veille cyber (livraison #814, BACKLOG 130 T1-T2) -- fonctions pures : lecture des flux publics (RSS 2.0, Atom,
RDF, catalogue KEV de la CISA), catégories (alertes ; news IA cyber, générale, France / Europe, règlements ANSSI /
RGPD), préfiltres (python, php, linux, bsd, mikrotik + nos modèles), règles de filtre, extraction (CSV, Markdown,
JSON, Atom), publics destinataires (RSSI, développeurs, administrateurs) et rapprochement avec les constats de
vuln-api (CVE présentes dans notre SI). Même logique que la tuile « Cyber news » du hub maison, enrichie ici des
impacts sur le SI, des publics et de la diffusion. Aucune donnée réelle : nos modèles d'équipements sont saisis dans
la tuile et gardés dans la base de vuln-api."""
import csv
import html
import io
import json
import re
import time
import unicodedata
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from xml.sax.saxutils import escape

KEV_JOURS = 60                  # au premier passage, seules les vulnérabilités exploitées ajoutées depuis 60 jours entrent

CATEGORIES = {"alerte": "Alertes", "ia": "IA cyber", "ia_sorties": "IA : sorties (modèles, API, outils)", "generale": "Cyber générale", "france_europe": "France / Europe",
              "reglement": "Règlements ANSSI / RGPD"}
NIVEAUX = {"alerte": "Alerte", "exploitee": "Exploitée", "avis": "Avis"}

# Sources proposées au premier lancement (toutes « non vérifiées » jusqu'à leur première relève réussie).
SOURCES_DEFAUT = [
    ("CERT-FR — alertes", "https://www.cert.ssi.gouv.fr/alerte/feed/", "flux", "alerte", "alerte", 30),
    ("CERT-FR — avis", "https://www.cert.ssi.gouv.fr/avis/feed/", "flux", "alerte", "avis", 60),
    ("CISA — vulnérabilités exploitées (KEV)", "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json", "kev", "alerte", "exploitee", 180),
    ("CISA — avis", "https://www.cisa.gov/cybersecurity-advisories/all.xml", "flux", "alerte", "avis", 120),
    ("CERT-FR — actualités", "https://www.cert.ssi.gouv.fr/actualite/feed/", "flux", "france_europe", None, 120),
    ("CERT-FR — menaces et incidents (CTI)", "https://www.cert.ssi.gouv.fr/cti/feed/", "flux", "france_europe", None, 240),
    ("ZATAZ", "https://www.zataz.com/feed/", "flux", "france_europe", None, 120),
    ("ANSSI — actualités", "https://cyber.gouv.fr/actualites/feed", "flux", "reglement", None, 360),
    ("CNIL — actualités", "https://www.cnil.fr/fr/rss.xml", "flux", "reglement", None, 360),
    ("CEPD / EDPB — actualités", "https://www.edpb.europa.eu/feed/news_en", "flux", "reglement", None, 360),
    ("The Hacker News", "https://feeds.feedburner.com/TheHackersNews", "flux", "generale", None, 60),
    ("BleepingComputer", "https://www.bleepingcomputer.com/feed/", "flux", "generale", None, 60),
    ("SecurityWeek", "https://www.securityweek.com/feed/", "flux", "generale", None, 120),
    ("Krebs on Security", "https://krebsonsecurity.com/feed/", "flux", "generale", None, 360),
    ("SANS Internet Storm Center", "https://isc.sans.edu/rssfeed_full.xml", "flux", "generale", None, 180),
    ("Simon Willison — injection de prompt", "https://simonwillison.net/tags/prompt-injection.atom", "flux", "ia", None, 360),
    ("Embrace The Red (sécurité des IA)", "https://embracethered.com/blog/index.xml", "flux", "ia", None, 360),
    ("arXiv cs.CR (articles sur l'IA seulement)", "https://rss.arxiv.org/rss/cs.CR", "flux", "ia", None, 720),
]
# #818 : sorties de l'IA -- nouveaux modèles, API et outils (versions publiées des projets suivis, blogs des éditeurs).
SOURCES_IA_SORTIES = [
    ("Ollama — versions", "https://github.com/ollama/ollama/releases.atom", "flux", "ia_sorties", None, 360),
    ("llama.cpp — versions", "https://github.com/ggml-org/llama.cpp/releases.atom", "flux", "ia_sorties", None, 720),
    ("vLLM — versions", "https://github.com/vllm-project/vllm/releases.atom", "flux", "ia_sorties", None, 720),
    ("Hermes Agent — versions", "https://github.com/NousResearch/hermes-agent/releases.atom", "flux", "ia_sorties", None, 360),
    ("Open WebUI — versions", "https://github.com/open-webui/open-webui/releases.atom", "flux", "ia_sorties", None, 720),
    ("Transformers — versions", "https://github.com/huggingface/transformers/releases.atom", "flux", "ia_sorties", None, 720),
    ("Hugging Face — blog", "https://huggingface.co/blog/feed.xml", "flux", "ia_sorties", None, 360),
    ("OpenAI — actualités", "https://openai.com/news/rss.xml", "flux", "ia_sorties", None, 360),
    ("Google DeepMind — blog", "https://deepmind.google/blog/rss.xml", "flux", "ia_sorties", None, 720),
    ("Simon Willison — tout", "https://simonwillison.net/atom/everything/", "flux", "ia_sorties", None, 360),
]
SOURCES_DEFAUT = SOURCES_DEFAUT + SOURCES_IA_SORTIES

GARDER_SI_DEFAUT = {"https://rss.arxiv.org/rss/cs.CR": "llm, large language model, prompt injection, jailbreak, agent, agents, machine learning, neural, deepfake, rag"}

PREFILTRES_DEFAUT = {
    "python": ["python", "pypi", "cpython", "django", "flask", "fastapi", "jupyter", "pip", "setuptools", "pytorch"],
    "php": ["php", "laravel", "symfony", "composer", "packagist", "phpunit", "drupal", "fat-free framework"],
    "linux": ["linux", "debian", "ubuntu", "red hat", "rhel", "centos", "fedora", "suse", "almalinux", "rocky linux", "glibc",
              "openssh", "sudo", "systemd", "polkit", "proxmox"],
    "bsd": ["bsd", "freebsd", "openbsd", "netbsd", "dragonfly bsd", "pfsense", "opnsense"],
    "mikrotik": ["mikrotik", "routeros", "winbox", "swos", "the dude"],
}

# Détection automatique des catégories (articles hors alertes). Sigles en MAJUSCULES cherchés tels quels (évite « j'ai »).
SIGLES_IA = re.compile(r"(?<![A-Za-z0-9])(AI|IA|LLMs?|GenAI|RAG|MCP)(?![A-Za-z0-9])")
TERMES_IA = ["intelligence artificielle", "artificial intelligence", "machine learning", "apprentissage automatique", "chatgpt", "openai",
             "anthropic", "gemini", "copilot", "mistral ai", "prompt injection", "injection de prompt", "jailbreak", "deepfake",
             "hypertrucage", "large language model", "modele de langage", "agentic", "model context protocol", "ai agent", "agent ia"]
TERMES_REGLEMENT = ["rgpd", "gdpr", "nis 2", "nis2", "dora", "cyber resilience act", "ai act", "secnumcloud", "cnil", "edpb", "cepd",
                    "reglement europeen", "directive europeenne"]
TERMES_FRANCE_EUROPE = ["france", "french", "anssi", "cert-fr", "cnil", "europe", "european", "europeen", "europeenne", "enisa",
                        "bruxelles", "brussels", "union europeenne", "european union"]
CVE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)


# -- outils purs ------------------------------------------------------------------------------------------------
def normaliser(t):
    """Minuscules sans accents (comparaisons de la veille)."""
    t = unicodedata.normalize("NFKD", str(t or "")).encode("ascii", "ignore").decode()
    return t.lower()


def _motif(terme):
    return re.compile(r"(?<![a-z0-9])" + re.escape(normaliser(terme).strip()) + r"(?![a-z0-9])")


def termes_trouves(texte_norm, termes):
    """Termes (liste) présents comme mots entiers dans un texte déjà normalisé."""
    return [t for t in termes if t and t.strip() and _motif(t).search(texte_norm)]


def texte_brut(h, limite=1500):
    """HTML d'un flux -> texte (balises retirées, entités décodées, espaces réduits)."""
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", str(h or ""), flags=re.S | re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = re.sub(r"\s+", " ", html.unescape(t)).strip()
    return t[:limite] + ("…" if len(t) > limite else "")


def lire_date(s):
    """RFC 822 (RSS), ISO 8601 (Atom, dc:date), AAAA-MM-JJ (KEV) -> horodatage, ou None."""
    s = (s or "").strip()
    if not s:
        return None
    try:
        return parsedate_to_datetime(s).timestamp()
    except (TypeError, ValueError, IndexError):
        pass
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()
    except ValueError:
        return None


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _enfant(e, *noms):
    for x in e:
        if _local(x.tag) in noms:
            return x
    return None


def _texte(e, *noms):
    x = _enfant(e, *noms)
    if x is None:
        return ""
    if len(x) and _local(x.tag) in ("content", "summary") and x.get("type") == "xhtml":
        return ET.tostring(x, encoding="unicode")
    return (x.text or "").strip()


def analyser_flux(data):
    """RSS 2.0 / Atom / RDF (RSS 1.0) -> [{cle, url, titre, resume, publie}]. Entités XML refusées (pas de « milliard de rires »)."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    if b"<!ENTITY" in data:
        raise ValueError("flux refusé : déclaration d'entités XML")
    racine = ET.fromstring(data)
    nom = _local(racine.tag)
    if nom == "rss":
        canal = _enfant(racine, "channel")
        elements = [x for x in (canal if canal is not None else []) if _local(x.tag) == "item"]
    elif nom == "feed":
        elements = [x for x in racine if _local(x.tag) == "entry"]
    elif nom == "RDF":
        elements = [x for x in racine.iter() if _local(x.tag) == "item"]
    else:
        raise ValueError("format inconnu : <%s> (RSS, Atom ou RDF attendus)" % nom)
    out = []
    for e in elements:
        lien = ""
        for x in e:
            if _local(x.tag) == "link":
                if x.get("href") and x.get("rel", "alternate") == "alternate":
                    lien = x.get("href")
                    break
                if (x.text or "").strip() and not lien:
                    lien = x.text.strip()
        titre = texte_brut(_texte(e, "title"), 300)
        resume = texte_brut(_texte(e, "encoded") or _texte(e, "description") or _texte(e, "summary") or _texte(e, "content"))
        date = lire_date(_texte(e, "pubDate") or _texte(e, "published") or _texte(e, "updated") or _texte(e, "date"))
        cle = _texte(e, "guid", "id") or lien or titre
        if not (titre or lien):
            continue
        out.append({"cle": cle[:500], "url": lien, "titre": titre, "resume": resume, "publie": date})
    return out


def analyser_kev(obj, maintenant=None, jours=KEV_JOURS):
    """Catalogue KEV de la CISA (JSON) -> articles des vulnérabilités ajoutées depuis `jours` jours."""
    maintenant = maintenant or time.time()
    out = []
    for v in (obj or {}).get("vulnerabilities") or []:
        cve = str(v.get("cveID") or "").strip()
        date = lire_date(v.get("dateAdded"))
        if not cve or (date and date < maintenant - jours * 86400):
            continue
        resume = str(v.get("shortDescription") or "").strip()
        if v.get("requiredAction"):
            resume += " Action demandée : %s" % str(v["requiredAction"]).strip()
        if str(v.get("knownRansomwareCampaignUse") or "").lower() == "known":
            resume += " Utilisée par des rançongiciels."
        if v.get("dueDate"):
            resume += " Échéance CISA : %s." % v["dueDate"]
        out.append({"cle": "kev:" + cve, "url": "https://nvd.nist.gov/vuln/detail/" + cve,
                    "titre": "%s — %s %s : %s" % (cve, v.get("vendorProject") or "", v.get("product") or "", v.get("vulnerabilityName") or ""),
                    "resume": resume.strip(), "publie": date, "cves": [cve]})
    return out


def categories_auto(titre, resume):
    """Catégories déduites du texte (hors alertes) : ia, reglement, france_europe."""
    brut = "%s %s" % (titre or "", resume or "")
    n = normaliser(brut)
    out = []
    if SIGLES_IA.search(brut) or termes_trouves(n, TERMES_IA):
        out.append("ia")
    if termes_trouves(n, TERMES_REGLEMENT):
        out.append("reglement")
    if termes_trouves(n, TERMES_FRANCE_EUROPE):
        out.append("france_europe")
    return out


def etiqueter(titre, resume, prefiltres):
    """-> (étiquettes des préfiltres trouvés, nos modèles cités). prefiltres : [{nom, termes, modeles, actif}]."""
    n = normaliser("%s %s" % (titre or "", resume or ""))
    tags, modeles = [], []
    for p in prefiltres:
        if not p.get("actif", 1):
            continue
        if termes_trouves(n, p.get("termes") or []):
            tags.append(p["nom"])
            modeles += [m.get("modele") for m in (p.get("modeles") or []) if m.get("modele") and termes_trouves(n, [m["modele"]])]
    return tags, modeles


def decouper_requete(q):
    """Texte de recherche -> (inclus, exclus) ; "expression exacte", -exclusion, a|b (l'un ou l'autre)."""
    inclus, exclus = [], []
    for m in re.finditer(r'(-?)"([^"]+)"|(-?)(\S+)', q or ""):
        moins, mot = (m.group(1), m.group(2)) if m.group(2) is not None else (m.group(3), m.group(4))
        if not mot or mot == "-":
            continue
        (exclus if moins else inclus).append([normaliser(x) for x in mot.split("|") if x])
    return inclus, exclus


def correspond(a, regle, maintenant=None):
    """Article (dict décodé) conforme à la règle d'un filtre ?"""
    r = regle or {}
    maintenant = maintenant or time.time()
    if r.get("jours") and (a.get("publie") or a.get("recu") or 0) < maintenant - float(r["jours"]) * 86400:
        return False
    if r.get("categories") and not set(r["categories"]) & set(a.get("categories") or []):
        return False
    if r.get("niveaux") and a.get("niveau") not in r["niveaux"]:
        return False
    if r.get("prefiltres") and not set(r["prefiltres"]) & set(a.get("tags") or []):
        return False
    if r.get("sources") and a.get("source_id") not in r["sources"]:
        return False
    if r.get("cve") and not a.get("cves"):
        return False
    if r.get("nos_modeles") and not a.get("nos_modeles"):
        return False
    if r.get("non_lus") and a.get("lu"):
        return False
    if r.get("suivis") and not a.get("suivi"):
        return False
    if r.get("texte"):
        n = normaliser(" ".join([a.get("titre") or "", a.get("resume") or "", " ".join(a.get("cves") or []), " ".join(a.get("tags") or [])]))
        inclus, exclus = decouper_requete(r["texte"])
        if any(not any(x in n for x in alt) for alt in inclus) or any(any(x in n for x in alt) for alt in exclus):
            return False
    return True


def _date_iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ") if ts else ""


def extraction(articles, fmt, titre="Veille cyber", sources=None):
    """-> (contenu texte, type MIME, extension). Formats : csv, json, md, atom."""
    sources = sources or {}
    if fmt == "json":
        return json.dumps(articles, ensure_ascii=False, indent=1), "application/json", "json"
    if fmt == "csv":
        f = io.StringIO()
        w = csv.writer(f, delimiter=";")
        w.writerow(["date", "source", "niveau", "categories", "prefiltres", "nos_modeles", "cve", "actifs_touches", "priorite", "publics",
                    "statut", "titre", "url", "resume"])
        for a in articles:
            imp = a.get("impacts") or {}
            w.writerow([_date_iso(a.get("publie") or a.get("recu")), sources.get(a.get("source_id"), ""), a.get("niveau") or "",
                        ",".join(a.get("categories") or []), ",".join(a.get("tags") or []), ",".join(a.get("nos_modeles") or []),
                        ",".join(a.get("cves") or []), ",".join(imp.get("actifs") or []), imp.get("priorite") or "", ",".join(a.get("publics") or []),
                        a.get("statut") or "", a.get("titre") or "", a.get("url") or "", a.get("resume") or ""])
        return "﻿" + f.getvalue(), "text/csv; charset=utf-8", "csv"      # BOM : accents corrects à l'ouverture dans un tableur
    if fmt == "md":
        lignes = ["# %s" % titre, "", "_%d article(s), extrait le %s_" % (len(articles), time.strftime("%d/%m/%Y %H:%M")), ""]
        for a in articles:
            imp = a.get("impacts") or {}
            meta = [x for x in [(_date_iso(a.get("publie") or a.get("recu")) or "")[:10], sources.get(a.get("source_id"), ""),
                                NIVEAUX.get(a.get("niveau") or "", ""), ", ".join(a.get("cves") or []), ", ".join(a.get("tags") or []),
                                ("**touche %s**%s" % (", ".join(imp["actifs"][:8]), " (%s)" % imp["priorite"] if imp.get("priorite") else "")) if imp.get("actifs") else "",
                                a.get("statut") or ""] if x]
            lignes.append("- **[%s](%s)** — %s" % ((a.get("titre") or "").replace("]", "\\]"), a.get("url") or "", " · ".join(meta)))
            if a.get("resume"):
                lignes.append("  > %s" % a["resume"][:400])
        return "\n".join(lignes) + "\n", "text/markdown; charset=utf-8", "md"
    if fmt == "atom":
        maj = max([a.get("publie") or a.get("recu") or 0 for a in articles] or [time.time()])
        x = ['<?xml version="1.0" encoding="utf-8"?>', '<feed xmlns="http://www.w3.org/2005/Atom">',
             "<title>%s</title><id>urn:hub-maison:cyber:%s</id><updated>%s</updated>" % (escape(titre), escape(normaliser(titre).replace(" ", "-")), _date_iso(maj))]
        for a in articles:
            x.append("<entry><title>%s</title><id>%s</id><link href=\"%s\"/><updated>%s</updated><summary>%s</summary></entry>" % (
                escape(a.get("titre") or ""), escape("urn:hub-maison:cyber:%s" % a.get("id")), escape(a.get("url") or "", {'"': "&quot;"}),
                _date_iso(a.get("publie") or a.get("recu")), escape(a.get("resume") or "")))
        x.append("</feed>")
        return "\n".join(x), "application/atom+xml; charset=utf-8", "atom"
    raise ValueError("format : csv, json, md ou atom")


# -- publics et impacts (propres au hub supervision) ---------------------------------------------------------
PUBLICS = {"rssi": "RSSI", "adminsys": "Administrateurs systèmes et réseau", "dev": "Développeurs"}
PRIO_ORDRE = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}


def index_constats(constats):
    """Constats de vuln-api [{asset, package, version, priority, cves (liste ou JSON), kev, epss}] -> {CVE: [constats]}."""
    idx = {}
    for f in constats:
        cves = f.get("cves")
        if isinstance(cves, str):
            try:
                cves = json.loads(cves or "[]")
            except ValueError:
                cves = []
        for c in cves or []:
            idx.setdefault(str(c).upper(), []).append(f)
    return idx


def impacts(article, idx):
    """-> {actifs: [noms], constats: n, priorite: "P1"…|None, detail: [{asset, package, version, priority, cve}]}."""
    det = []
    for c in article.get("cves") or []:
        for f in idx.get(str(c).upper(), []):
            det.append({"asset": f.get("asset"), "package": f.get("package"), "version": f.get("version"), "priority": f.get("priority"), "cve": c})
    prio = min((d["priority"] for d in det if d.get("priority") in PRIO_ORDRE), key=lambda p: PRIO_ORDRE[p], default=None)
    return {"actifs": sorted(set(d["asset"] for d in det if d.get("asset"))), "constats": len(det), "priorite": prio, "detail": det[:50]}


def publics(article, imp=None):
    """Publics concernés : RSSI (alertes, exploitées, règlements, impacts P1/P2, nos modèles), administrateurs (alertes,
    linux, bsd, mikrotik, impacts sur un hôte), développeurs (python, php, impacts sur une application / image / dépôt)."""
    cats, tags = set(article.get("categories") or []), set(article.get("tags") or [])
    imp = imp or {}
    out = set()
    if article.get("niveau") in ("alerte", "exploitee") or "reglement" in cats or imp.get("priorite") in ("P1", "P2") or article.get("nos_modeles"):
        out.add("rssi")
    if "alerte" in cats or tags & {"linux", "bsd", "mikrotik"} or imp.get("actifs"):
        out.add("adminsys")
    if tags & {"python", "php"}:
        out.add("dev")
    return sorted(out)


def a_signaler(article, imp):
    """Alerte immédiate : alerte ou vulnérabilité exploitée QUI NOUS TOUCHE (CVE présente chez nous ou un de nos modèles cité)."""
    return article.get("niveau") in ("alerte", "exploitee") and bool((imp or {}).get("actifs") or article.get("nos_modeles"))


def texte_synthese(articles, public, noms=None, maintenant=None):
    """Corps du courriel quotidien d'un public -> (sujet, corps) ; (None, None) s'il n'y a rien."""
    if not articles:
        return None, None
    noms = noms or {}
    lignes = []
    for a in articles[:40]:
        imp = a.get("impacts") or {}
        meta = [x for x in [NIVEAUX.get(a.get("niveau") or "", ""), ", ".join(a.get("cves") or [])[:80],
                            ("touche : " + ", ".join(imp.get("actifs", [])[:5])) if imp.get("actifs") else "",
                            ("nos modèles : " + ", ".join(a.get("nos_modeles"))) if a.get("nos_modeles") else ""] if x]
        lignes.append("- %s%s\n  %s%s" % (a.get("titre"), (" [" + " · ".join(meta) + "]") if meta else "", noms.get(a.get("source_id"), ""),
                                           (" — " + a["url"]) if a.get("url") else ""))
    touchent = sum(1 for a in articles if (a.get("impacts") or {}).get("actifs"))
    sujet = "Veille cyber %s : %d nouveauté(s)%s" % (PUBLICS.get(public, public), len(articles), (", %d touchant notre SI" % touchent) if touchent else "")
    corps = "%s\n\n%s%s" % (sujet, "\n".join(lignes), "\n… et %d autre(s) dans la tuile Veille cyber." % (len(articles) - 40) if len(articles) > 40 else "")
    return sujet, corps


STATUTS = {"a_traiter": "À traiter", "en_cours": "En cours", "traite": "Traité", "non_applicable": "Non applicable"}


def correspond_si(a, regle, maintenant=None):
    """correspond() + critères propres au hub supervision : touche notre SI, publics, statuts."""
    r = regle or {}
    if not correspond(a, r, maintenant):
        return False
    if r.get("impacts") and not (a.get("impacts") or {}).get("actifs"):
        return False
    if r.get("publics") and not set(r["publics"]) & set(a.get("publics") or []):
        return False
    if r.get("statuts") and (a.get("statut") or "aucun") not in r["statuts"]:
        return False
    return True
