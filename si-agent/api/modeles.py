# -*- coding: utf-8 -*-
"""Parc IA -- veille des modèles (livraison #821 ; même module que la tuile « Modèles IA » du hub maison).

- **Veille des modèles** : derniers dépôts publiés par les éditeurs suivis sur Hugging Face (API publique, sans clé),
  relevés toutes les 6 h par le service « cyber ». Le premier passage remonte dans le temps (40 derniers dépôts par
  éditeur, datés de leur publication).
- **Historique** : chaque changement est consigné -- nouveau modèle, licence (ouverture ou fermeture), accès (dépôt
  restreint / gated), disparition ou réapparition d'un modèle suivi.
- **Alertes** : nouveau modèle *utilisable* (tient en Q4 dans la mémoire GPU d'une de nos machines, réglage
  MODELES_MACHINES) et *pertinent* (texte, vision, audio, embeddings ; ni variante quantifiée ni écarté), et tout
  passage ouvert <-> fermé.
- **Usages** : par hôte du Parc IA et par modèle, actif ou non et types d'usage (inventaire déclaratif : le
  branchement automatique des priorités sur ces déclarations est la tranche 2).
- **Bancs** : résultats des bancs comparatifs (donnees/banc-*.json).

Pur et testé : params_depuis, ouverture, vram_q4, machines_ok, normaliser, comparer, alerte."""
import glob
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime

from flask import Blueprint, jsonify, request

import fcntl
import threading

import modeles_stockage as stockage

bp = Blueprint("modeles", __name__)

HF = "https://huggingface.co/api/models"
AGENT = "hub-maison/1.0 (veille des modeles)"
OLLAMA = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434").rstrip("/")
PERIODE_S = 6 * 3600
PAR_AUTEUR = 40
AUTEURS_DEFAUT = ["Qwen", "meta-llama", "mistralai", "google", "microsoft", "deepseek-ai", "openai", "NousResearch", "ibm-granite",
                  "allenai", "nvidia", "CohereLabs", "LiquidAI", "HuggingFaceTB", "moonshotai", "zai-org"]
USAGES = {"preparation": "préparation (extraire, regrouper)", "decideur": "décideur (oui/non, catégories)",
          "explication": "explication / conversation", "code": "code", "embeddings": "embeddings / recherche",
          "vision": "vision (images)", "transcription": "transcription (audio)", "traduction": "traduction"}
PERTINENTS = {"text-generation", "image-text-to-text", "automatic-speech-recognition", "feature-extraction", "sentence-similarity",
              "text-classification", "translation", "any-to-any", "text-to-speech", "visual-question-answering"}
# Licences libres (OSI ou équivalent, usage commercial permis) ; toute autre licence déclarée = poids ouverts sous conditions
LIBRES = {"apache-2.0", "mit", "bsd", "bsd-2-clause", "bsd-3-clause", "bsd-3-clause-clear", "cc-by-4.0", "cc-by-sa-4.0", "cc0-1.0",
          "gpl-2.0", "gpl-3.0", "lgpl-2.1", "lgpl-3.0", "agpl-3.0", "mpl-2.0", "artistic-2.0", "afl-3.0", "ecl-2.0", "isc",
          "unlicense", "odc-by", "cdla-permissive-2.0", "epl-2.0", "openrail", "openrail++", "bigscience-openrail-m",
          "creativeml-openrail-m", "postgresql", "zlib"}
OUVERTURE = {2: "libre", 1: "poids ouverts sous conditions", 0: "fermé / inconnu"}
VARIANTE = re.compile(r"(?i)[-_.](gguf|awq|gptq|fp8|fp4|int4|int8|mlx|bnb|4bit|8bit|exl2|onnx|nvfp4|w4a16|w8a8|qat)(?![a-z])")
# Dédicace « apprentissage » (#908) : niveau d'enrichissement possible du modèle.
#   1 enrichissable (poids ouverts exploitables) · 2 outillé (adaptation LoRA/PEFT/TRL déclarée) · 3 apprend ET désapprend (l'idéal).
NIV_APPREND = {0: "", 1: "enrichissable", 2: "outillé (LoRA/PEFT)", 3: "apprend & désapprend"}
APPREND_OUTILS = {"peft", "lora", "qlora", "adapter", "adapters", "trl", "sft", "dpo", "orpo", "unsloth", "autotrain"}
APPREND_DYNAMIQUE = ("unlearn", "knowledge-editing", "knowledge-edit", "model-editing", "continual-learning",
                     "lifelong-learning", "online-learning", "incremental-learning", "concept-erasure", "self-correcting")
_TAILLE = re.compile(r"(?i)(?<![a-z\d.])(\d+(?:\.\d+)?)\s?([bm])(?![a-z])")
EXPAND = ["createdAt", "lastModified", "gated", "safetensors", "tags", "pipeline_tag", "downloads", "likes", "cardData"]

SCHEMA = """
CREATE TABLE IF NOT EXISTS modeles (id TEXT PRIMARY KEY, auteur TEXT, cree REAL, maj REAL, params_b REAL, licence TEXT,
  ouverture INTEGER, gated TEXT, pipeline TEXT, telechargements INTEGER, likes INTEGER, variante INTEGER DEFAULT 0, apprend INTEGER DEFAULT 0,
  premier_vu REAL, dernier_vu REAL, disparu REAL, suivi INTEGER DEFAULT 0, ecarte INTEGER DEFAULT 0);
CREATE TABLE IF NOT EXISTS modeles_hist (id INTEGER PRIMARY KEY, modele TEXT NOT NULL, at REAL, evenement TEXT, avant TEXT,
  apres TEXT, alerte INTEGER DEFAULT 0, vu INTEGER DEFAULT 0);
CREATE INDEX IF NOT EXISTS modeles_hist_at ON modeles_hist (at);
CREATE TABLE IF NOT EXISTS modeles_mes (nom TEXT PRIMARY KEY, actif INTEGER DEFAULT 1, usages TEXT, note TEXT, maj REAL);
CREATE TABLE IF NOT EXISTS modeles_etat (cle TEXT PRIMARY KEY, valeur TEXT);
"""


# -- pur ---------------------------------------------------------------------------------------------------------
def params_depuis(item):
    """Milliards de paramètres : safetensors.total, sinon le nom (« Qwen3-30B-A3B » -> 30 ; « 0.6B » ; « 270M »)."""
    st = (item or {}).get("safetensors") or {}
    if isinstance(st, dict) and st.get("total"):
        return round(float(st["total"]) / 1e9, 2)
    nom = str((item or {}).get("id") or "").split("/")[-1]
    for m in _TAILLE.finditer(nom):
        v = float(m.group(1))
        return round(v / 1000.0, 3) if m.group(2).lower() == "m" else v
    return None


def licence_de(item):
    card = (item or {}).get("cardData") or {}
    lic = card.get("license") if isinstance(card, dict) else None
    if isinstance(lic, list):
        lic = lic[0] if lic else None
    if not lic:
        lic = next((t[8:] for t in (item or {}).get("tags") or [] if isinstance(t, str) and t.startswith("license:")), None)
    return str(lic).lower() if lic else None


def ouverture(lic):
    if not lic:
        return 0
    return 2 if lic in LIBRES else 1


def vram_q4(params_b):
    """Mémoire GPU estimée pour une quantification Q4 (~0,6 Go par milliard) + contexte et surcoût (~1,5 Go)."""
    return round(params_b * 0.6 + 1.5, 1) if params_b else None


def lire_machines(spec):
    """« pcia:24,superia:20 » -> [{"nom", "vram"}] (Go)."""
    out = []
    for x in str(spec or "").split(","):
        nom, _, v = x.strip().partition(":")
        try:
            if nom:
                out.append({"nom": nom, "vram": float(v)})
        except ValueError:
            continue
    return out


def machines_ok(params_b, machines):
    v = vram_q4(params_b)
    return [m["nom"] for m in machines if v is not None and v <= m["vram"]]


def _ts(iso):
    if not iso:
        return None
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def apprend_niveau(item):
    """Niveau d'enrichissement par apprentissage (0..3, cf. NIV_APPREND) : 3 si désapprentissage / édition de
    connaissances / apprentissage continu (mots distinctifs dans le nom ou les tags -- l'idéal recherché) ;
    2 si une adaptation légère est déjà outillée (LoRA, PEFT, TRL...) ; 1 si les poids sont ouverts et exploitables
    (safetensors présents, licence au moins sous conditions) ; 0 sinon."""
    tags = [str(t).lower() for t in (item or {}).get("tags") or []]
    blob = str((item or {}).get("id") or "").lower().replace("/", " ") + " " + " ".join(tags)
    if any(mot in blob for mot in APPREND_DYNAMIQUE):
        return 3
    if any(t in APPREND_OUTILS for t in tags):
        return 2
    st = (item or {}).get("safetensors") or {}
    if isinstance(st, dict) and st.get("total") and ouverture(licence_de(item)) >= 1:
        return 1
    return 0


def risque_dispo(m):
    """Urgence de téléchargement (avant disparition / passage payant) : 2 sans tarder (accès restreint « gated », qui
    peut être révoqué ou fermé) · 1 à surveiller (poids sous conditions, licence révocable) · 0 rien · -1 déjà indisponible."""
    if m.get("disparu"):
        return -1
    if m.get("gated"):
        return 2
    return 1 if (m.get("ouverture") or 0) == 1 else 0


def normaliser(item):
    mid = str(item.get("id") or item.get("modelId") or "")
    lic = licence_de(item)
    g = item.get("gated")
    return {"id": mid, "auteur": mid.split("/")[0] if "/" in mid else (item.get("author") or ""), "cree": _ts(item.get("createdAt")),
            "maj": _ts(item.get("lastModified")), "params_b": params_depuis(item), "licence": lic, "ouverture": ouverture(lic),
            "gated": "" if g in (None, False, "false") else str(g), "pipeline": item.get("pipeline_tag") or "",
            "telechargements": int(item.get("downloads") or 0), "likes": int(item.get("likes") or 0),
            "variante": 1 if VARIANTE.search(mid.split("/")[-1]) else 0, "apprend": apprend_niveau(item)}


def comparer(ancien, nouveau):
    """Événements entre deux états d'un même modèle : [(evenement, avant, apres)]."""
    if ancien is None:
        return [("nouveau", None, nouveau.get("licence"))]
    ev = []
    if (ancien.get("ouverture"), ancien.get("licence")) != (nouveau.get("ouverture"), nouveau.get("licence")):
        sens = "ouverture" if (nouveau.get("ouverture") or 0) > (ancien.get("ouverture") or 0) else \
            "fermeture" if (nouveau.get("ouverture") or 0) < (ancien.get("ouverture") or 0) else "licence"
        ev.append((sens, ancien.get("licence"), nouveau.get("licence")))
    if (ancien.get("gated") or "") != (nouveau.get("gated") or ""):
        ev.append(("acces_restreint" if nouveau.get("gated") else "acces_libre", ancien.get("gated") or "", nouveau.get("gated") or ""))
    if ancien.get("disparu"):
        ev.append(("reapparu", None, None))
    return ev


def alerte(evenement, m, machines, initial=False):
    """Mérite-t-il une alerte ? Les passages ouvert/fermé et disparitions toujours (hors variantes) ; un nouveau modèle
    s'il est pertinent et utilisable sur une de nos machines (jamais lors du premier passage, qui remonte le passé)."""
    if m.get("variante") or m.get("ecarte"):
        return False
    if evenement in ("ouverture", "fermeture", "licence", "acces_restreint", "acces_libre", "disparu", "reapparu"):
        return True
    return evenement == "nouveau" and not initial and m.get("pipeline") in PERTINENTS and bool(machines_ok(m.get("params_b"), machines))


# -- base ----------------------------------------------------------------------------------------------------------
def _migrer(c):
    cols = {r[1] for r in c.execute("PRAGMA table_info(modeles)")}
    if "apprend" not in cols:   # #908 : niveau d'enrichissement par apprentissage, recalculé à la prochaine relève
        c.execute("ALTER TABLE modeles ADD COLUMN apprend INTEGER DEFAULT 0")
        c.commit()


def cnx():
    c = stockage.cnx()
    c.executescript(SCHEMA)
    _migrer(c)
    return c


def lignes(cur):
    return [dict(r) for r in cur]


def etat_get(c, cle, defaut=None):
    r = c.execute("SELECT valeur FROM modeles_etat WHERE cle=?", (cle,)).fetchone()
    return json.loads(r[0]) if r else defaut


def etat_set(c, cle, v):
    c.execute("INSERT OR REPLACE INTO modeles_etat VALUES (?, ?)", (cle, json.dumps(v)))


def machines():
    return lire_machines(os.environ.get("MODELES_MACHINES", "ia-prod:20,ia-preprod:16"))


def auteurs(c):
    return etat_get(c, "auteurs", AUTEURS_DEFAUT)


def _get(url, delai=25):
    req = urllib.request.Request(url, headers={"User-Agent": AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=delai) as r:
        return json.loads(r.read().decode("utf-8"))


def url_auteur(a, n=PAR_AUTEUR):
    q = [("author", a), ("sort", "createdAt"), ("direction", "-1"), ("limit", str(n))] + [("expand[]", e) for e in EXPAND]
    return HF + "?" + urllib.parse.urlencode(q)


notifier = None   # #823 : fourni par app.py -- événement du hub (journal + notifications) pour chaque alerte


def consigner(c, m, evts, maintenant, initial=False):
    mach = machines()
    for e, av, ap in evts:
        al = alerte(e, m, mach, initial)
        c.execute("INSERT INTO modeles_hist (modele, at, evenement, avant, apres, alerte) VALUES (?,?,?,?,?,?)",
                  (m["id"], maintenant, e, av, ap, 1 if al else 0))
        if al and notifier is not None:
            try:
                ok = machines_ok(m.get("params_b"), mach)
                notifier("modèle %s : %s%s" % (m["id"], e.replace("_", " "), (" (%s -> %s)" % (av or "?", ap or "?")) if e != "nouveau" else
                                               (" -- %s B, tient sur %s" % (m.get("params_b") or "?", ", ".join(ok) or "aucune machine"))),
                         {"modele": m["id"], "evenement": e, "avant": av, "apres": ap, "machines": ok})
            except Exception:  # noqa: BLE001 -- la notification ne bloque jamais la veille
                pass


def enregistrer(c, items, maintenant=None, initial=False):
    """Fusionne une liste de l'API dans le catalogue ; renvoie le nombre d'événements consignés."""
    maintenant = maintenant or time.time()
    n = 0
    for it in items or []:
        m = normaliser(it)
        if not m["id"]:
            continue
        r = c.execute("SELECT * FROM modeles WHERE id=?", (m["id"],)).fetchone()
        ancien = dict(r) if r else None
        if ancien:
            m["ecarte"], m["suivi"] = ancien.get("ecarte"), ancien.get("suivi")
        evts = comparer(ancien, m)
        consigner(c, m, evts, maintenant, initial)
        n += len(evts)
        c.execute("""INSERT INTO modeles (id, auteur, cree, maj, params_b, licence, ouverture, gated, pipeline, telechargements, likes,
                     variante, apprend, premier_vu, dernier_vu, disparu) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,NULL)
                     ON CONFLICT(id) DO UPDATE SET maj=excluded.maj, params_b=COALESCE(excluded.params_b, modeles.params_b),
                     licence=excluded.licence, ouverture=excluded.ouverture, gated=excluded.gated, pipeline=excluded.pipeline,
                     telechargements=excluded.telechargements, likes=excluded.likes, apprend=excluded.apprend, dernier_vu=excluded.dernier_vu, disparu=NULL""",
                  (m["id"], m["auteur"], m["cree"], m["maj"], m["params_b"], m["licence"], m["ouverture"], m["gated"], m["pipeline"],
                   m["telechargements"], m["likes"], m["variante"], m["apprend"], maintenant, maintenant))
    c.commit()
    return n


def relever(c, get=None, maintenant=None):
    """Un passage : chaque éditeur suivi, puis les modèles suivis un par un (disparition, fermeture)."""
    get = get or _get
    maintenant = maintenant or time.time()
    erreurs, n = {}, 0
    for a in auteurs(c):
        initial = not c.execute("SELECT 1 FROM modeles WHERE auteur=? LIMIT 1", (a,)).fetchone()
        try:
            try:
                import activite as _ac
                ctx = _ac.suivre("source", "Hugging Face · %s" % a)
            except Exception:  # noqa: BLE001
                ctx = __import__("contextlib").nullcontext()
            with ctx:
                lot = get(url_auteur(a))
            n += enregistrer(c, lot, maintenant, initial)
        except (urllib.error.URLError, OSError, ValueError) as e:
            erreurs[a] = str(e)[:200]
    for (mid,) in c.execute("SELECT id FROM modeles WHERE suivi=1 AND dernier_vu < ?", (maintenant - 60,)).fetchall():
        try:
            n += enregistrer(c, [get(HF + "/" + mid + "?" + urllib.parse.urlencode([("expand[]", e) for e in EXPAND]))], maintenant)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403, 404):   # dépôt retiré ou rendu privé
                r = dict(c.execute("SELECT * FROM modeles WHERE id=?", (mid,)).fetchone())
                if not r.get("disparu"):
                    c.execute("UPDATE modeles SET disparu=? WHERE id=?", (maintenant, mid))
                    consigner(c, r, [("disparu", r.get("licence"), "HTTP %d" % e.code)], maintenant)
                    n += 1
            else:
                erreurs[mid] = str(e)[:200]
        except (urllib.error.URLError, OSError, ValueError) as e:
            erreurs[mid] = str(e)[:200]
    etat_set(c, "derniere_releve", {"at": maintenant, "evenements": n, "erreurs": erreurs})
    c.commit()
    return n, erreurs


def a_relever(c, maintenant=None):
    d = etat_get(c, "derniere_releve") or {}
    return (maintenant or time.time()) - (d.get("at") or 0) >= PERIODE_S


def enrichir(m, mach):
    m = dict(m)
    m["vram_q4"] = vram_q4(m.get("params_b"))
    m["machines"] = machines_ok(m.get("params_b"), mach)
    m["ouverture_lib"] = OUVERTURE.get(m.get("ouverture") or 0)
    m["risque"] = risque_dispo(m)
    m["apprend_lib"] = NIV_APPREND.get(m.get("apprend") or 0)
    return m


def _recent(m, maintenant, jours):
    t = m.get("cree") or m.get("premier_vu") or 0
    return (maintenant - t) <= jours * 86400


def score_revue(m):
    """Mérite d'être vu aujourd'hui (plus c'est haut, mieux c'est). Dans l'ordre des priorités demandées :
    tenir sur une de nos machines (légèreté, priorité visuelle forte), urgence de téléchargement, capacité
    d'apprentissage (l'idéal 3 ressort), un bonus de popularité."""
    s = 0.0
    nb = len(m.get("machines") or [])
    if nb:
        s += 40 + 6 * nb
        s += max(0.0, 24 - (m.get("vram_q4") or 24))   # plus c'est léger, plus ça monte
    r = m.get("risque") or 0
    s += 30 if r >= 2 else 12 if r == 1 else 0
    s += 14 * (m.get("apprend") or 0)
    s += min(10.0, (m.get("likes") or 0) / 20.0)
    return round(s, 1)


def revue(modeles, maintenant=None, jours=2):
    """Revue synthétique du jour à partir de modèles déjà enrichis : un classement global et des listes ciblées
    (nouveautés récentes, à télécharger sans tarder, légers qui tiennent chez nous, apprentissage, idéal)."""
    maintenant = maintenant or time.time()
    base = [dict(m) for m in modeles if m.get("pipeline") in PERTINENTS and not m.get("variante") and not m.get("ecarte")]
    for m in base:
        m["score"] = score_revue(m)
    classes = sorted(base, key=lambda m: (-m["score"], -(m.get("cree") or m.get("premier_vu") or 0)))
    return {"at": maintenant, "jours": jours, "total": len(classes), "classement": classes[:60],
            "nouveaux": [m for m in classes if _recent(m, maintenant, jours)][:40],
            "a_telecharger": [m for m in classes if (m.get("risque") or 0) >= 2 and m.get("machines")][:20],
            "legers": sorted([m for m in classes if m.get("machines")], key=lambda m: (m.get("vram_q4") or 99, -m["score"]))[:40],
            "apprentissage": [m for m in classes if (m.get("apprend") or 0) >= 2][:30],
            "ideal": [m for m in classes if (m.get("apprend") or 0) >= 3][:20]}


# -- mes modèles (Ollama) ----------------------------------------------------------------------------------------
source_tags = None   # #821 : fournie par app.py -- modèles Ollama de tous les hôtes du Parc IA (« hôte/modèle »)


def ollama_tags(get=None):
    if source_tags is not None:
        try:
            return source_tags()
        except Exception:  # noqa: BLE001
            return None
    try:
        return (get or _get)(OLLAMA + "/api/tags", 10).get("models") or []
    except (urllib.error.URLError, OSError, ValueError):
        return None


def mes_modeles(c, tags):
    reglages = {r["nom"]: r for r in lignes(c.execute("SELECT * FROM modeles_mes"))}
    out = []
    for t in tags or []:
        nom = t.get("name") or t.get("model")
        r = reglages.get(nom) or {}
        d = t.get("details") or {}
        out.append({"nom": nom, "taille": t.get("size"), "famille": d.get("family"), "parametres": d.get("parameter_size"),
                    "quantification": d.get("quantization_level"), "modifie": t.get("modified_at"),
                    "actif": bool(r.get("actif", 1)) if r else True, "usages": json.loads(r["usages"]) if r.get("usages") else [],
                    "note": r.get("note") or "", "installe": True})
    vus = {x["nom"] for x in out}
    for nom, r in reglages.items():   # réglages d'un modèle désinstallé : gardés, signalés
        if nom not in vus:
            out.append({"nom": nom, "actif": bool(r.get("actif")), "usages": json.loads(r["usages"]) if r.get("usages") else [],
                        "note": r.get("note") or "", "installe": False})
    return sorted(out, key=lambda x: (not x["installe"], x["nom"]))


def modele_pour(usage, c=None, hote=None):
    """Premier modèle actif déclaré pour cet usage (None sinon : chaque module garde son défaut). #823 : avec `hote`,
    seulement les modèles « hôte/modèle » de cet hôte, renvoyés sans le préfixe."""
    c = c or cnx()
    for r in lignes(c.execute("SELECT * FROM modeles_mes WHERE actif=1 ORDER BY maj DESC")):
        if usage not in json.loads(r.get("usages") or "[]"):
            continue
        if hote is None:
            return r["nom"]
        if r["nom"].startswith(hote + "/"):
            return r["nom"][len(hote) + 1:]
    return None


def bancs(dossier):
    out = []
    for f in sorted(glob.glob(os.path.join(dossier, "banc-*.json")), reverse=True)[:50]:
        try:
            d = json.load(open(f))
        except (OSError, ValueError):
            continue
        out.append({"fichier": os.path.basename(f), "at": d.get("at"), "reference": d.get("reference"),
                    "articles": len(d.get("articles") or []), "synthese": d.get("synthese") or {}})
    return out


# -- API -----------------------------------------------------------------------------------------------------------
@bp.get("/modeles/etat")
def etat():
    c = cnx()
    return jsonify({"nb": c.execute("SELECT COUNT(*) FROM modeles").fetchone()[0],
                    "alertes": c.execute("SELECT COUNT(*) FROM modeles_hist WHERE alerte=1 AND vu=0").fetchone()[0],
                    "releve": etat_get(c, "derniere_releve"), "machines": machines(), "usages": USAGES, "auteurs": auteurs(c),
                    "ouverture": OUVERTURE, "pertinents": sorted(PERTINENTS)})


@bp.get("/modeles/catalogue")
def catalogue():
    c = cnx()
    a = request.args
    try:
        jours = float(a.get("jours") or 90)
    except ValueError:
        return jsonify({"erreur": "jours invalide"}), 400
    mach = machines()
    rows = lignes(c.execute("SELECT * FROM modeles WHERE COALESCE(cree, premier_vu) >= ? ORDER BY COALESCE(cree, premier_vu) DESC",
                            (time.time() - jours * 86400,)))
    out = []
    for m in rows:
        m = enrichir(m, mach)
        if a.get("ecartes") != "1" and m.get("ecarte"):
            continue
        if a.get("ecartes") == "1" and not m.get("ecarte"):
            continue
        if a.get("variantes") != "1" and m.get("variante"):
            continue
        if a.get("pertinents") == "1" and m.get("pipeline") not in PERTINENTS:
            continue
        if a.get("utilisables") == "1" and not m["machines"]:
            continue
        if a.get("auteur") and m.get("auteur") != a.get("auteur"):
            continue
        if a.get("ouverture") not in (None, "") and str(m.get("ouverture")) != a.get("ouverture"):
            continue
        out.append(m)
    return jsonify({"modeles": out[:1000], "total": len(out)})


@bp.get("/modeles/revue")
def revue_api():
    """Revue du jour (#908) : classement synthétique des modèles récents, priorité aux légers qui tiennent sur nos
    machines, urgence de téléchargement et dédicace apprentissage. `jours` = fenêtre « nouveautés », `fenetre` = profondeur du classement."""
    c = cnx()
    a = request.args
    try:
        jours = float(a.get("jours") or 2)
        fenetre = float(a.get("fenetre") or 120)
    except ValueError:
        return jsonify({"erreur": "paramètre invalide"}), 400
    mach = machines()
    rows = lignes(c.execute("SELECT * FROM modeles WHERE disparu IS NULL AND COALESCE(cree, premier_vu) >= ? "
                            "ORDER BY COALESCE(cree, premier_vu) DESC", (time.time() - fenetre * 86400,)))
    return jsonify(revue([enrichir(m, mach) for m in rows], jours=jours))


@bp.get("/modeles/historique")
def historique():
    c = cnx()
    a = request.args
    jours = float(a.get("jours") or 365)
    q = "SELECT h.*, m.auteur, m.params_b, m.pipeline, m.variante, m.cree FROM modeles_hist h LEFT JOIN modeles m ON m.id=h.modele WHERE h.at >= ?"
    p = [time.time() - jours * 86400]
    if a.get("alertes") == "1":
        q += " AND h.alerte=1"
    if a.get("evenement"):
        q += " AND h.evenement=?"
        p.append(a.get("evenement"))
    if a.get("variantes") != "1":
        q += " AND COALESCE(m.variante, 0)=0"
    rows = lignes(c.execute(q + " ORDER BY h.at DESC, COALESCE(m.cree, 0) DESC LIMIT 1000", p))
    return jsonify({"evenements": rows})


@bp.post("/modeles/alertes/vu")
def alertes_vu():
    b = request.get_json(silent=True) or {}
    c = cnx()
    if b.get("tout"):
        c.execute("UPDATE modeles_hist SET vu=1 WHERE alerte=1")
    else:
        c.executemany("UPDATE modeles_hist SET vu=1 WHERE id=?", [(int(i),) for i in b.get("ids") or [] if str(i).isdigit()])
    c.commit()
    return jsonify({"ok": True})


@bp.post("/modeles/marquer")
def marquer():
    b = request.get_json(silent=True) or {}
    c = cnx()
    if not c.execute("SELECT 1 FROM modeles WHERE id=?", (str(b.get("id") or ""),)).fetchone():
        return jsonify({"erreur": "modèle inconnu"}), 404
    for k in ("ecarte", "suivi"):
        if k in b:
            c.execute("UPDATE modeles SET %s=? WHERE id=?" % k, (1 if b[k] else 0, b["id"]))
    c.commit()
    return jsonify({"ok": True})


@bp.route("/modeles/auteurs", methods=["GET", "PUT"])
def auteurs_api():
    c = cnx()
    if request.method == "PUT":
        liste = [str(x).strip() for x in (request.get_json(silent=True) or {}).get("auteurs") or [] if re.match(r"^[\w.-]{1,64}$", str(x).strip())]
        if not liste:
            return jsonify({"erreur": "au moins un éditeur (identifiant Hugging Face)"}), 400
        etat_set(c, "auteurs", liste)
        c.commit()
    return jsonify({"auteurs": auteurs(c), "defaut": AUTEURS_DEFAUT})


@bp.post("/modeles/relever")
def relever_api():
    c = cnx()
    n, err = relever(c)
    return jsonify({"evenements": n, "erreurs": err})


@bp.get("/modeles/mes")
def mes_api():
    c = cnx()
    tags = ollama_tags()
    return jsonify({"modeles": mes_modeles(c, tags or []), "ollama": tags is not None, "usages": USAGES})


@bp.post("/modeles/mes")
def mes_regler():
    b = request.get_json(silent=True) or {}
    nom = str(b.get("nom") or "").strip()
    if not nom or len(nom) > 120:
        return jsonify({"erreur": "nom requis"}), 400
    usages = [u for u in b.get("usages") or [] if u in USAGES]
    c = cnx()
    c.execute("INSERT OR REPLACE INTO modeles_mes (nom, actif, usages, note, maj) VALUES (?,?,?,?,?)",
              (nom, 1 if b.get("actif", True) else 0, json.dumps(usages), str(b.get("note") or "")[:300], time.time()))
    c.commit()
    return jsonify({"ok": True, "usages": usages})


@bp.get("/modeles/bancs")
def bancs_api():
    return jsonify({"bancs": bancs(os.path.dirname(os.path.abspath(stockage.chemin())))})


# -- relève en tâche de fond (gunicorn : plusieurs workers -> verrou de fichier, un seul relève) -------------------
def _boucle():
    verrou = stockage.chemin() + ".releve.lock"
    while True:
        try:
            with open(verrou, "a") as fh:
                try:
                    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    time.sleep(60)
                    continue
                c = cnx()
                if a_relever(c):
                    relever(c)
                c.close()
                fcntl.flock(fh, fcntl.LOCK_UN)
        except Exception:  # noqa: BLE001 -- la veille des modèles ne fait jamais tomber l'API
            pass
        time.sleep(60)


def demarrer():
    if os.environ.get("MODELES_THREAD", "1") == "1":
        threading.Thread(target=_boucle, name="modeles-veille", daemon=True).start()
