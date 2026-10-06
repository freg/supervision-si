# -*- coding: utf-8 -*-
"""Vulnérabilités du SI (livraison #688) -- logique PURE, testée (vuln/tests).

Quatre orientations : inventaire SBOM (syft, CycloneDX), correspondance avec
la base OSV (osv-scanner), dépôt de référence (Dependency-Track), et
PRIORISATION par la probabilité d'exploitation (EPSS) et l'exploitation avérée
(catalogue KEV de la CISA), pondérées par l'exposition de l'actif (vu
d'Internet ou non).

Rien ici ne touche au réseau ni au disque : l'API (app.py) télécharge et
appelle les outils, ces fonctions lisent leurs sorties."""
import csv
import gzip
import io
import json
import math
import re

CVE_RE = re.compile(r"^CVE-\d{4}-\d{4,}$", re.I)
LABEL_SCORE = {"CRITICAL": 9.5, "HIGH": 7.5, "MODERATE": 5.5, "MEDIUM": 5.5, "LOW": 3.0}


# ------------------------------------------------------------------ EPSS / KEV

def parse_epss(raw):
    """Fichier EPSS courant (csv ou csv.gz) -> ({cve: (epss, percentile)}, meta).
    Première ligne `#model_version:v2025.03.14,score_date:2025-...` (v2 et +)."""
    if isinstance(raw, bytes) and raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    text = raw.decode("utf-8", "replace") if isinstance(raw, bytes) else str(raw or "")
    meta, scores = {}, {}
    lines = text.splitlines()
    if lines and lines[0].startswith("#"):
        for part in lines[0][1:].split(","):
            k, _, v = part.partition(":")
            if k.strip():
                meta[k.strip()] = v.strip()
        lines = lines[1:]
    for row in csv.DictReader(lines):
        cve = (row.get("cve") or "").strip().upper()
        try:
            scores[cve] = (float(row["epss"]), float(row["percentile"]))
        except (KeyError, TypeError, ValueError):
            continue
    return scores, meta


def parse_kev(data):
    """Catalogue KEV (JSON CISA) -> ({cve: {added, due, ransomware, product}}, meta)."""
    if isinstance(data, (bytes, str)):
        data = json.loads(data)
    out = {}
    for v in (data or {}).get("vulnerabilities") or []:
        cve = str(v.get("cveID") or "").upper()
        if CVE_RE.match(cve):
            out[cve] = {"added": v.get("dateAdded"), "due": v.get("dueDate"),
                        "ransomware": str(v.get("knownRansomwareCampaignUse") or "").lower() == "known",
                        "product": "%s %s" % (v.get("vendorProject") or "", v.get("product") or "")}
    return out, {"version": (data or {}).get("catalogVersion"), "count": len(out)}


# ------------------------------------------------------------------ CVSS 3.x

_W = {"AV": {"N": 0.85, "A": 0.62, "L": 0.55, "P": 0.2}, "AC": {"L": 0.77, "H": 0.44}, "UI": {"N": 0.85, "R": 0.62},
      "C": {"H": 0.56, "L": 0.22, "N": 0}, "I": {"H": 0.56, "L": 0.22, "N": 0}, "A": {"H": 0.56, "L": 0.22, "N": 0}}


def _roundup(x):
    i = int(round(x * 100000))
    return i / 100000.0 if i % 10000 == 0 else (math.floor(i / 10000) + 1) / 10.0


def cvss3_base(vector):
    """Score de base CVSS 3.0/3.1 d'un vecteur, None si illisible. Pure."""
    m = dict(p.split(":", 1) for p in str(vector or "").split("/")[1:] if ":" in p)
    try:
        scope_changed = m["S"] == "C"
        pr = {"N": 0.85, "L": 0.68 if scope_changed else 0.62, "H": 0.5 if scope_changed else 0.27}[m["PR"]]
        iss = 1 - (1 - _W["C"][m["C"]]) * (1 - _W["I"][m["I"]]) * (1 - _W["A"][m["A"]])
        impact = 7.52 * (iss - 0.029) - 3.25 * (iss - 0.02) ** 15 if scope_changed else 6.42 * iss
        expl = 8.22 * _W["AV"][m["AV"]] * _W["AC"][m["AC"]] * pr * _W["UI"][m["UI"]]
    except KeyError:
        return None
    if impact <= 0:
        return 0.0
    return _roundup(min(1.08 * (impact + expl), 10)) if scope_changed else _roundup(min(impact + expl, 10))


def vuln_score(v, group=None):
    """Meilleur score disponible : max_severity du groupe osv-scanner, vecteur
    CVSS 3, sinon libellé (GHSA « HIGH »). -> (score|None, source)."""
    if group and group.get("max_severity") not in (None, ""):
        try:
            return float(group["max_severity"]), "osv"
        except (TypeError, ValueError):
            pass
    best = None
    for s in v.get("severity") or []:
        if str(s.get("type", "")).upper().startswith("CVSS_V3"):
            sc = cvss3_base(s.get("score"))
            if sc is not None and (best is None or sc > best):
                best = sc
    if best is not None:
        return best, "cvss3"
    label = str(((v.get("database_specific") or {}).get("severity")) or "").upper()
    return (LABEL_SCORE[label], "label") if label in LABEL_SCORE else (None, None)


def _fixed_versions(v, name):
    out = []
    for a in v.get("affected") or []:
        if str((a.get("package") or {}).get("name", "")).lower() != str(name).lower():
            continue
        for r in a.get("ranges") or []:
            for e in r.get("events") or []:
                if e.get("fixed"):
                    out.append(e["fixed"])
    return sorted(set(out))


# ------------------------------------------------------------------ SBOM / osv-scanner

def sbom_components(bom):
    """CycloneDX JSON -> [{name, version, purl, type}] (paquets seulement)."""
    if isinstance(bom, (bytes, str)):
        bom = json.loads(bom)
    out = []
    for c in (bom or {}).get("components") or []:
        if c.get("type") == "file" or not c.get("name"):
            continue
        out.append({"name": c.get("name"), "version": c.get("version"), "purl": c.get("purl"), "type": c.get("type")})
    return out


def osv_findings(report):
    """Sortie JSON d'osv-scanner (v2) -> une ligne par (paquet, groupe d'alias) :
    {package, version, ecosystem, ids, cves, score, score_source, summary, fixed}."""
    if isinstance(report, (bytes, str)):
        report = json.loads(report) if report else {}
    out = []
    for res in (report or {}).get("results") or []:
        for p in res.get("packages") or []:
            pkg = p.get("package") or {}
            vulns = {v.get("id"): v for v in p.get("vulnerabilities") or []}
            groups = p.get("groups") or [{"ids": [i]} for i in vulns]
            for g in groups:
                ids = [i for i in g.get("ids") or [] if i]
                members = [vulns[i] for i in ids if i in vulns]
                aliases = set(ids)
                for v in members:
                    aliases.update(v.get("aliases") or [])
                cves = sorted(a.upper() for a in aliases if CVE_RE.match(str(a)))
                score, src = None, None
                for v in members or [{}]:
                    s, s_src = vuln_score(v, g)
                    if s is not None and (score is None or s > score):
                        score, src = s, s_src
                fixed = sorted({f for v in members for f in _fixed_versions(v, pkg.get("name"))})
                summary = next((v.get("summary") for v in members if v.get("summary")), None)
                out.append({"package": pkg.get("name"), "version": pkg.get("version"), "ecosystem": pkg.get("ecosystem"),
                            "ids": sorted(ids), "cves": cves, "score": score, "score_source": src,
                            "summary": (summary or "")[:200] or None, "fixed": fixed})
    return out


# ------------------------------------------------------------------ priorisation

def prioritize(finding, epss=None, kev=None, exposed=False):
    """-> finding enrichi {epss, percentile, kev, priority P1..P4, reason}. Pure.

    P1 : exploitation avérée (KEV, même sur un actif interne : mouvement latéral),
         ou EPSS ≥ 0,5 sur un actif exposé ;
    P2 : EPSS ≥ 0,1 (ou centile ≥ 0,95), ou critique (≥ 9) sur un actif exposé ;
    P3 : grave (≥ 7) ou EPSS ≥ 0,01 ;
    P4 : le reste (suivi, correction au fil des mises à jour)."""
    epss, kev = epss or {}, kev or {}
    e = max((epss.get(c, (0.0, 0.0)) for c in finding.get("cves") or []), default=(0.0, 0.0))
    k = next((kev[c] for c in finding.get("cves") or [] if c in kev), None)
    score = finding.get("score") or 0.0
    reasons = []
    if k:
        reasons.append("exploitée activement (KEV, ajoutée le %s%s)" % (k.get("added"), ", rançongiciels" if k.get("ransomware") else ""))
    if e[0] >= 0.01:
        reasons.append("EPSS %.1f %% (centile %d)" % (e[0] * 100, round(e[1] * 100)))
    if score:
        reasons.append("CVSS %.1f" % score)
    if exposed:
        reasons.append("actif exposé à Internet")
    if k or (e[0] >= 0.5 and exposed):
        prio = "P1"
    elif e[0] >= 0.1 or e[1] >= 0.95 or (score >= 9 and exposed):
        prio = "P2"
    elif score >= 7 or e[0] >= 0.01:
        prio = "P3"
    else:
        prio = "P4"
    if finding.get("fixed"):
        reasons.append("corrigée en %s" % ", ".join(finding["fixed"][:3]))
    return dict(finding, epss=round(e[0], 5), percentile=round(e[1], 5), kev=bool(k), priority=prio, reason=" ; ".join(reasons) or "aucun signal")


def summarize(findings):
    out = {"P1": 0, "P2": 0, "P3": 0, "P4": 0, "kev": 0, "total": len(findings)}
    for f in findings:
        out[f["priority"]] = out.get(f["priority"], 0) + 1
        out["kev"] += 1 if f.get("kev") else 0
    return out
