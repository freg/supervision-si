# -*- coding: utf-8 -*-
"""Généalogie des modèles d'IA (#854) : l'histoire des modèles depuis le Transformer (2017), leurs filiations (succession,
affinage, distillation, fusion...), avec dates, auteurs, liens et mode d'emploi -- et qui se tient à jour toute seule.

Même module dans le hub supervision (si-agent-api, routes /modeles/genealogie) et dans le hub maison (/api/modeles/genealogie).

- **Base** : `genealogie_base.json`, relevé à la main (un nœud par modèle marquant, parents avec la relation).
- **Relevés automatiques** (une fois par jour, et à la demande) :
  (a) pour chaque modèle ouvert de la base publié sur Hugging Face, ses dérivés les plus téléchargés (tag
      `base_model:finetune:<id>` / `adapter`) ;
  (b) pour chaque nouveau modèle de la veille des sorties (table `modeles`), sa fiche Hugging Face : s'il déclare un
      modèle de base connu, il est rattaché à l'arbre.
  Les versions quantifiées (GGUF, AWQ...) ne sont jamais des nœuds : elles ne changent pas le modèle.
- **Mode d'emploi** : commande Ollama, VRAM estimée en Q4, machines qui le tiennent (MODELES_MACHINES), licence.

Pur et testé : valider, parents_hf, noeud_hf, fusionner, lignee, emploi."""
import fcntl
import json
import os
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from flask import Blueprint, jsonify, request

try:  # hub maison (paquet api)
    from . import stockage
    from . import modeles
    PREFIXE = "/api/modeles"
except ImportError:
    try:  # hub supervision (si-agent-api)
        import modeles_stockage as stockage
        import modeles
        PREFIXE = "/modeles"
    except ImportError:  # hub maison hors paquet
        import stockage
        import modeles
        PREFIXE = "/api/modeles"

bp = Blueprint("genealogie", __name__)

FICHIER_BASE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "genealogie_base.json")
HF = "https://huggingface.co/api/models"
PERIODE_S = 24 * 3600
DERIVES_PAR_MODELE = int(os.environ.get("GENEALOGIE_DERIVES", "5"))
NOUVEAUX_MAX = 60
RELATIONS_HF = {"finetune": "affinage", "adapter": "adaptateur (LoRA)", "merge": "fusion", "distillation": "distillation"}
OUVERTURES = ("ouvert", "poids", "ferme")
TYPES_PIPELINE = {"text-generation": "texte", "image-text-to-text": "vision", "visual-question-answering": "vision",
                  "automatic-speech-recognition": "audio", "text-to-speech": "audio", "feature-extraction": "embeddings",
                  "sentence-similarity": "embeddings", "translation": "texte", "any-to-any": "vision", "image-to-text": "ocr"}
_DATE = re.compile(r"^\d{4}-\d{2}$")
SCHEMA = """CREATE TABLE IF NOT EXISTS genealogie_releves (id TEXT PRIMARY KEY, noeud TEXT NOT NULL, vu REAL, ecarte INTEGER DEFAULT 0);"""


# -- pur ---------------------------------------------------------------------------------------------------------
def valider(noeuds):
    """Erreurs de la base : identifiants en double, parents inconnus, dates mal formées, ouverture inconnue, cycles."""
    err, ids = [], set()
    for n in noeuds:
        if n.get("id") in ids:
            err.append("doublon : %s" % n.get("id"))
        ids.add(n.get("id"))
        if not _DATE.match(str(n.get("date") or "")):
            err.append("date « %s » mal formée : %s" % (n.get("date"), n.get("id")))
        if n.get("ouverture") not in OUVERTURES:
            err.append("ouverture « %s » inconnue : %s" % (n.get("ouverture"), n.get("id")))
    for n in noeuds:
        for p in n.get("parents") or []:
            if p.get("id") not in ids:
                err.append("parent inconnu %s pour %s" % (p.get("id"), n.get("id")))
    par = {n["id"]: [p["id"] for p in n.get("parents") or []] for n in noeuds if n.get("id")}
    for depart in par:
        vus, pile = set(), list(par[depart])
        while pile:
            x = pile.pop()
            if x == depart:
                err.append("cycle passant par %s" % depart)
                break
            if x not in vus:
                vus.add(x)
                pile.extend(par.get(x) or [])
    return err


def charger_base(chemin=None):
    with open(chemin or FICHIER_BASE, encoding="utf-8") as fh:
        return json.load(fh)


def parents_hf(item):
    """Modèles de base déclarés par une fiche Hugging Face -> [(id_hf, relation)] ; les quantifications sont ignorées."""
    out = []
    for t in (item or {}).get("tags") or []:
        if not isinstance(t, str) or not t.startswith("base_model:"):
            continue
        reste = t[len("base_model:"):]
        genre, _, cible = reste.partition(":")
        if genre == "quantized":
            continue
        if genre in RELATIONS_HF and cible:
            out.append((cible, RELATIONS_HF[genre]))
        elif not cible and "/" in genre:
            out.append((genre, "affinage"))
    if not out:
        bm = ((item or {}).get("cardData") or {}).get("base_model")
        for b in (bm if isinstance(bm, list) else [bm] if bm else []):
            if isinstance(b, str) and "/" in b:
                out.append((b, "affinage"))
    vus, uniques = set(), []
    for b, r in out:
        if b.lower() not in vus:
            vus.add(b.lower())
            uniques.append((b, r))
    return uniques


def noeud_hf(item, parents):
    """Nœud « relevé automatiquement » à partir d'une fiche Hugging Face ; parents = [{id, relation}] déjà résolus."""
    mid = item.get("id") or item.get("modelId") or ""
    lic = modeles.licence_de(item)
    ouv = {2: "ouvert", 1: "poids"}.get(modeles.ouverture(lic), "poids")
    pipe = item.get("pipeline_tag")
    return {"id": "hf:" + mid, "nom": mid.split("/")[-1], "org": mid.split("/")[0] if "/" in mid else "",
            "date": str(item.get("createdAt") or "")[:7] or time.strftime("%Y-%m"), "types": [TYPES_PIPELINE.get(pipe, "texte")],
            "ouverture": ouv, "licence": lic, "tailles": "", "params_b": modeles.params_depuis(item), "parents": parents,
            "auteurs": mid.split("/")[0] if "/" in mid else "", "liens": {"hf": "https://huggingface.co/" + mid}, "hf": mid,
            "emploi": {}, "auto": True, "telechargements": item.get("downloads"), "likes": item.get("likes")}


def index_hf(noeuds):
    return {str(n["hf"]).lower(): n["id"] for n in noeuds if n.get("hf")}


def resoudre(parents, idx):
    return [{"id": idx[b.lower()], "relation": r} for b, r in parents if b.lower() in idx]


def fusionner(base, releves):
    """Base + relevés : un relevé qui double un modèle de la base est ignoré ; un relevé sans parent connu aussi."""
    noeuds = [dict(n) for n in base]
    ids = {n["id"] for n in noeuds}
    idx = index_hf(noeuds)
    restants = [r for r in releves if str(r.get("hf") or "").lower() not in idx and r["id"] not in ids]
    change = True
    while change and restants:   # un dérivé de dérivé s'accroche une fois son parent placé
        change, suite = False, []
        for r in restants:
            ps = [p for p in r.get("parents") or [] if p["id"] in ids]
            if ps:
                noeuds.append(dict(r, parents=ps))
                ids.add(r["id"])
                change = True
            else:
                suite.append(r)
        restants = suite
    return noeuds


def enfants(noeuds):
    e = {}
    for n in noeuds:
        for p in n.get("parents") or []:
            e.setdefault(p["id"], []).append({"id": n["id"], "relation": p.get("relation")})
    return e


def lignee(noeuds, nid, profondeur=50):
    """Ascendants (jusqu'à l'origine) et descendants d'un nœud, chacun avec sa distance."""
    par = {n["id"]: n.get("parents") or [] for n in noeuds}
    enf = enfants(noeuds)

    def parcours(suivants):
        vus, front, d = {}, [nid], 0
        while front and d < profondeur:
            d += 1
            prochain = []
            for x in front:
                for s in suivants(x):
                    if s["id"] not in vus and s["id"] != nid:
                        vus[s["id"]] = d
                        prochain.append(s["id"])
            front = prochain
        return [{"id": k, "distance": v} for k, v in sorted(vus.items(), key=lambda kv: (kv[1], kv[0]))]
    return {"ascendants": parcours(lambda x: par.get(x, [])), "descendants": parcours(lambda x: enf.get(x, []))}


def emploi(n, mach):
    e = dict(n.get("emploi") or {})
    if e.get("ollama"):
        e["commande"] = "ollama run %s" % e["ollama"]
    elif n.get("auto") and n.get("hf") and n.get("ouverture") != "ferme":
        e["commande"] = "ollama run hf.co/%s   # seulement si un GGUF est publié" % n["hf"]
    e["vram_q4"] = modeles.vram_q4(n.get("params_b"))
    e["machines"] = modeles.machines_ok(n.get("params_b"), mach) if n.get("ouverture") != "ferme" else []
    return e


# -- base de données ---------------------------------------------------------------------------------------------
def cnx():
    c = modeles.cnx()
    c.executescript(SCHEMA)
    return c


def releves(c, tous=False):
    q = "SELECT noeud, ecarte FROM genealogie_releves" + ("" if tous else " WHERE ecarte=0")
    return [dict(json.loads(r[0]), ecarte=bool(r[1])) for r in c.execute(q)]


def garder(c, noeud, maintenant):
    c.execute("""INSERT INTO genealogie_releves (id, noeud, vu) VALUES (?,?,?)
                 ON CONFLICT(id) DO UPDATE SET noeud=excluded.noeud, vu=excluded.vu""", (noeud["id"], json.dumps(noeud), maintenant))


def url_derives(hf, genre="finetune", n=None):
    q = [("filter", "base_model:%s:%s" % (genre, hf)), ("sort", "downloads"), ("direction", "-1"),
         ("limit", str(n or DERIVES_PAR_MODELE))] + [("expand[]", e) for e in modeles.EXPAND]
    return HF + "?" + urllib.parse.urlencode(q)


def relever(c, get=None, maintenant=None, base=None):
    """Un passage complet ; renvoie (nombre de nœuds ajoutés ou rafraîchis, erreurs)."""
    get = get or modeles._get
    maintenant = maintenant or time.time()
    base = base if base is not None else charger_base()["noeuds"]
    etat = modeles.etat_get(c, "genealogie_releve") or {}
    erreurs, n = {}, 0
    idx = index_hf(base + releves(c, tous=True))
    for b in base:   # (a) dérivés des modèles ouverts de la base
        if not b.get("hf") or b.get("ouverture") == "ferme":
            continue
        for genre in ("finetune", "adapter"):
            try:
                lot = get(url_derives(b["hf"], genre)) or []
            except (urllib.error.URLError, OSError, ValueError) as e:
                erreurs[b["hf"]] = str(e)[:200]
                break
            for it in lot:
                mid = it.get("id") or ""
                if not mid or modeles.VARIANTE.search(mid) or mid.lower() in idx and idx[mid.lower()] != "hf:" + mid:
                    continue
                garder(c, noeud_hf(it, [{"id": b["id"], "relation": RELATIONS_HF[genre]}]), maintenant)
                idx[mid.lower()] = "hf:" + mid
                n += 1
    depuis = etat.get("at") or 0   # (b) nouveaux modèles de la veille des sorties
    try:
        nouveaux = [r[0] for r in c.execute("""SELECT id FROM modeles WHERE COALESCE(variante,0)=0 AND COALESCE(ecarte,0)=0
                    AND premier_vu > ? ORDER BY premier_vu DESC LIMIT ?""", (depuis, NOUVEAUX_MAX))]
    except Exception:  # noqa: BLE001 -- table absente : la veille des sorties n'a jamais tourné
        nouveaux = []
    for mid in nouveaux:
        if mid.lower() in idx:
            continue
        try:
            it = get(HF + "/" + urllib.parse.quote(mid, safe="/"))
        except (urllib.error.URLError, OSError, ValueError) as e:
            erreurs[mid] = str(e)[:200]
            continue
        ps = resoudre(parents_hf(it), idx)
        if ps:
            garder(c, noeud_hf(it, ps), maintenant)
            idx[mid.lower()] = "hf:" + mid
            n += 1
    modeles.etat_set(c, "genealogie_releve", {"at": maintenant, "noeuds": n, "erreurs": erreurs})
    c.commit()
    return n, erreurs


def a_relever(c, maintenant=None):
    d = modeles.etat_get(c, "genealogie_releve") or {}
    return (maintenant or time.time()) - (d.get("at") or 0) >= PERIODE_S


_en_cours = threading.Event()


def _relever_fond(forcer=False):
    """Relève en tâche de fond, un seul processus à la fois (verrou de fichier), jamais bloquant pour l'API."""
    if _en_cours.is_set():
        return False
    _en_cours.set()

    def tache():
        try:
            with open(stockage.chemin() + ".genealogie.lock", "a") as fh:
                try:
                    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except OSError:
                    return
                c = cnx()
                if forcer or a_relever(c):
                    relever(c)
                c.close()
        except Exception:  # noqa: BLE001 -- la généalogie ne fait jamais tomber l'API
            pass
        finally:
            _en_cours.clear()
    threading.Thread(target=tache, name="genealogie-releve", daemon=True).start()
    return True


def auto_actif():
    return os.environ.get("GENEALOGIE_AUTO", os.environ.get("MODELES_THREAD", "1")) == "1"


# -- routes ------------------------------------------------------------------------------------------------------
@bp.get(PREFIXE + "/genealogie")
def genealogie_api():
    b = charger_base()
    c = cnx()
    if auto_actif() and a_relever(c):
        _relever_fond()
    rel = releves(c)
    etat = modeles.etat_get(c, "genealogie_releve") or {}
    c.close()
    noeuds = fusionner(b["noeuds"], rel)
    mach = modeles.machines()
    for n in noeuds:
        n["emploi"] = emploi(n, mach)
    return jsonify({"noeuds": noeuds, "base_maj": b.get("maj"), "source": b.get("source"), "releve": etat,
                    "en_cours": _en_cours.is_set(), "machines": mach, "erreurs_base": valider(b["noeuds"]),
                    "compte": {"base": len(b["noeuds"]), "releves": len(noeuds) - len(b["noeuds"])}})


@bp.post(PREFIXE + "/genealogie/relever")
def genealogie_relever():
    return jsonify({"lance": _relever_fond(forcer=True), "en_cours": True})


@bp.post(PREFIXE + "/genealogie/ecarter")
def genealogie_ecarter():
    d = request.get_json(silent=True) or {}
    nid = str(d.get("id") or "")
    if not nid.startswith("hf:"):
        return jsonify({"erreur": "seuls les nœuds relevés automatiquement s'écartent (la base se corrige dans genealogie_base.json)"}), 400
    c = cnx()
    cur = c.execute("UPDATE genealogie_releves SET ecarte=? WHERE id=?", (0 if d.get("remettre") else 1, nid))
    c.commit()
    return jsonify({"ok": cur.rowcount == 1})
