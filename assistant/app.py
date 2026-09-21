# -*- coding: utf-8 -*-
"""assistant-api (livraison #532, backlog item 81) -- PoC palier 1 de
l'assistant IA interne : un modèle ouvert servi localement (Ollama ou tout
serveur compatible OpenAI : llama.cpp, vLLM) + RAG lexical sur les sources
du hub (documents locaux, tickets, GED) + trois usages mesurés (question
avec sources, classement d'un document GED, résumé d'une demande) + jeu
d'évaluation reproductible (jetons/s, qualité). Rien ne sort du SI : le
modèle tourne sur nos machines, l'API ne connaît aucun secret."""
import glob
import json
import logging
import os
import re
import threading
import time

import requests
from flask import Flask, jsonify, request, send_from_directory

import rag

log = logging.getLogger("assistant")
logging.basicConfig(level=os.environ.get("ASSISTANT_LOG_LEVEL", "INFO"))

DATA_DIR = os.environ.get("ASSISTANT_DATA_DIR", "/data")
DOCS_DIR = os.environ.get("ASSISTANT_DOCS_DIR", "/docs")
# Documentation du dépôt copiée dans l'image (README des modules, CHANGELOG,
# BACKLOG) : indexée en plus des documents (#534).
REPO_DOCS_DIR = os.environ.get("ASSISTANT_REPO_DOCS_DIR", "/repo-docs")
LLM_BASE = os.environ.get("LLM_BASE_URL", "http://ollama:11434/v1").rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "qwen3:8b")
LLM_TIMEOUT = int(os.environ.get("LLM_TIMEOUT_SECONDS", "600"))
LLM_MAX_TOKENS = int(os.environ.get("LLM_MAX_TOKENS", "700"))
# Mode « réflexion » des modèles qui le proposent (Qwen3...) : coupé par
# défaut (#534) -- la latence est divisée par 3 à 5 sur classification et
# résumé ; passe par l'API native d'Ollama (/api/chat, champ think) quand
# LLM_BASE_URL est un Ollama (…/v1), sinon reste sur l'API OpenAI.
LLM_THINK = os.environ.get("LLM_THINK", "false").strip().lower() in ("1", "true", "yes", "on")
TICKETS_API = os.environ.get("TICKETS_API_URL", "").rstrip("/")
GED_API = os.environ.get("GED_API_URL", "").rstrip("/")
PREFIX = "/assistant"
HERE = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=None)
os.makedirs(DATA_DIR, exist_ok=True)
try:
    from version_endpoint import register_version_route
    register_version_route(app, "assistant")
except Exception:  # noqa: BLE001
    pass

INDEX = rag.BM25()
_index_info = {"built_at": None, "docs": 0, "chunks": 0, "sources": {}, "building": False, "error": None}
_lock = threading.Lock()
_journal_path = os.path.join(DATA_DIR, "journal.jsonl")


def _bad(msg, code=400):
    return jsonify({"error": msg}), code


# ---------------------------------------------------------------- modèle
def native_chat_url(base):
    """URL /api/chat d'Ollama déduite d'une base OpenAI …/v1 ; None sinon."""
    return base[:-3] + "/api/chat" if base.endswith("/v1") else None


def parse_chat_response(j):
    """Texte + usage, réponse OpenAI (choices) ou native Ollama (message)."""
    if isinstance(j.get("message"), dict):
        text = j["message"].get("content") or ""
        usage = {"prompt_tokens": j.get("prompt_eval_count") or 0, "completion_tokens": j.get("eval_count") or 0}
        ns = j.get("eval_duration") or 0
        tok_s = round(usage["completion_tokens"] / (ns / 1e9), 1) if ns and usage["completion_tokens"] else None
        return text, usage, tok_s
    text = ((j.get("choices") or [{}])[0].get("message") or {}).get("content") or ""
    return text, j.get("usage") or {}, None


def llm_chat(messages, temperature=0.2, max_tokens=None, json_mode=False):
    """Appel du modèle ; renvoie {text, usage, ms, tok_s, error}.

    API native Ollama (think désactivable) quand LLM_THINK est faux et que la
    base est un Ollama ; API compatible OpenAI sinon."""
    native = None if LLM_THINK else native_chat_url(LLM_BASE)
    if native:
        url = native
        body = {"model": LLM_MODEL, "messages": messages, "stream": False, "think": False,
                "options": {"temperature": temperature, "num_predict": max_tokens or LLM_MAX_TOKENS}}
        if json_mode:
            body["format"] = "json"
    else:
        url = LLM_BASE + "/chat/completions"
        body = {"model": LLM_MODEL, "messages": messages, "temperature": temperature, "max_tokens": max_tokens or LLM_MAX_TOKENS, "stream": False}
        if json_mode:
            body["response_format"] = {"type": "json_object"}
    t0 = time.monotonic()
    try:
        r = requests.post(url, json=body, timeout=LLM_TIMEOUT)
        ms = round((time.monotonic() - t0) * 1000.0)
        if r.status_code != 200:
            return {"text": "", "error": "modèle : HTTP %s %s" % (r.status_code, r.text[:200]), "ms": ms}
        j = r.json()
        text, usage, tok_s = parse_chat_response(j)
        comp = usage.get("completion_tokens") or 0
        if tok_s is None and comp:
            tok_s = round(comp / (max(ms, 1) / 1000.0), 1)
        return {"text": text, "usage": usage, "ms": ms, "tok_s": tok_s, "model": j.get("model") or LLM_MODEL, "think": bool(LLM_THINK)}
    except requests.RequestException as exc:
        return {"text": "", "error": "modèle injoignable (%s) : %s" % (LLM_BASE, str(exc)[:120]), "ms": round((time.monotonic() - t0) * 1000.0)}


def llm_models():
    try:
        r = requests.get(LLM_BASE + "/models", timeout=5)
        return [m.get("id") for m in (r.json().get("data") or [])] if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        return None


# ---------------------------------------------------------------- sources
def _collect_dir(base, prefix, source):
    docs = []
    if not base or not os.path.isdir(base):
        return docs
    for path in sorted(glob.glob(os.path.join(base, "**", "*"), recursive=True)):
        if not os.path.isfile(path) or not path.lower().endswith((".md", ".txt", ".rst", ".csv", ".json", ".html")):
            continue
        try:
            if os.path.getsize(path) > 2_000_000:
                continue
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        if path.lower().endswith(".html"):
            text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text)
            text = re.sub(r"(?s)<[^>]+>", " ", text)
        rel = os.path.relpath(path, base)
        docs.append({"id": prefix + rel, "source": source, "title": rel, "text": text, "meta": {"path": rel}})
    return docs


def collect_local_docs():
    """Documents (ASSISTANT_DOCS_DIR) + documentation du dépôt (README des
    modules, CHANGELOG, BACKLOG copiés dans l'image, #534)."""
    return _collect_dir(DOCS_DIR, "doc:", "documents") + _collect_dir(REPO_DOCS_DIR, "repo:", "repo")


def collect_tickets():
    if not TICKETS_API:
        return []
    try:
        r = requests.get(TICKETS_API + "/queue", params={"state": "all", "limit": 500}, timeout=15)
        items = r.json() if r.status_code == 200 else []
        if isinstance(items, dict):
            items = items.get("tickets") or items.get("items") or []
    except (requests.RequestException, ValueError):
        return []
    docs = []
    for t in items or []:
        if not isinstance(t, dict):
            continue
        text = "\n".join(filter(None, [t.get("subject"), t.get("description"), "Type : %s" % t.get("type_label", ""), "Statut : %s" % t.get("statut_label", ""), "Site : %s" % t.get("site_label", "")]))
        docs.append({"id": "ticket:%s" % t.get("id"), "source": "tickets", "title": "Ticket %s — %s" % (t.get("id"), (t.get("subject") or "")[:80]), "text": text, "meta": {"id": t.get("id")}})
    return docs


def collect_ged():
    """Documents connus de ged-api ; texte de la dernière version quand
    elle est textuelle (txt/md/csv/html), sinon nom + métadonnées seulement."""
    if not GED_API:
        return []
    try:
        r = requests.get(GED_API + "/documents", timeout=20)
        items = r.json() if r.status_code == 200 else []
    except (requests.RequestException, ValueError):
        return []
    docs = []
    for d in items or []:
        name = d.get("name") or "document %s" % d.get("id")
        text = name
        raw = ((d.get("versions") or [{}])[-1].get("raw") or {})
        fname = (raw.get("filename") or raw.get("file") or "").lower()
        if fname.endswith((".txt", ".md", ".csv", ".html", ".htm")):
            try:
                rr = requests.get("%s/documents/%s/versions/latest/download" % (GED_API, d.get("id")), timeout=30)
                if rr.status_code == 200 and len(rr.content) < 2_000_000:
                    text = name + "\n" + rr.content.decode("utf-8", "replace")
            except requests.RequestException:
                pass
        docs.append({"id": "ged:%s" % d.get("id"), "source": "ged", "title": name, "text": text, "meta": {"id": d.get("id"), "filename": fname}})
    return docs


def collect_uploads():
    docs = []
    for path in sorted(glob.glob(os.path.join(DATA_DIR, "uploads", "*"))):
        try:
            text = open(path, encoding="utf-8", errors="replace").read()
        except OSError:
            continue
        docs.append({"id": "upload:" + os.path.basename(path), "source": "uploads", "title": os.path.basename(path), "text": text, "meta": {}})
    return docs


def build_index():
    with _lock:
        _index_info.update(building=True, error=None)
        try:
            raw = collect_local_docs() + collect_uploads() + collect_tickets() + collect_ged()
            chunks, per = [], {}
            for d in raw:
                per[d["source"]] = per.get(d["source"], 0) + 1
                for i, c in enumerate(rag.chunk_text(d["text"])):
                    chunks.append({"id": "%s#%d" % (d["id"], i), "doc": d["id"], "source": d["source"], "title": d["title"], "text": c, "meta": d.get("meta") or {}})
            INDEX.build(chunks)
            _index_info.update(built_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), docs=len(raw), chunks=len(chunks), sources=per)
        except Exception as exc:  # noqa: BLE001
            _index_info["error"] = str(exc)[:200]
        finally:
            _index_info["building"] = False


def journal(kind, payload):
    try:
        with open(_journal_path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(payload, kind=kind, at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())), ensure_ascii=False) + "\n")
    except OSError:
        pass


# ---------------------------------------------------------------- usages
def ask(question, k=5, source=None, free=False):
    hits = [] if free else INDEX.search(question, k=k, source=source)
    if free:
        msgs = [{"role": "system", "content": "Tu es l'assistant interne du système d'information. Réponds en français, brièvement."}, {"role": "user", "content": question}]
    else:
        msgs = rag.build_rag_messages(question, hits)
    out = llm_chat(msgs)
    out["sources"] = [{"id": h["id"], "doc": h.get("doc"), "source": h["source"], "title": h["title"], "score": h["score"], "excerpt": h["text"][:300]} for h in hits]
    out["question"] = question
    journal("ask", {"question": question, "ms": out.get("ms"), "tok_s": out.get("tok_s"), "sources": [h["id"] for h in hits], "error": out.get("error")})
    return out


def classify(text, types=None, sites=None):
    out = llm_chat(rag.build_classify_messages(text, types or [], sites or []), temperature=0.0, json_mode=True)
    out["parsed"] = rag.extract_json(out.get("text"))
    journal("classify", {"ms": out.get("ms"), "tok_s": out.get("tok_s"), "ok": isinstance(out["parsed"], dict), "error": out.get("error")})
    return out


def summarize(text):
    out = llm_chat(rag.build_summary_messages(text), temperature=0.0, json_mode=True)
    out["parsed"] = rag.extract_json(out.get("text"))
    journal("summarize", {"ms": out.get("ms"), "tok_s": out.get("tok_s"), "ok": isinstance(out["parsed"], dict), "error": out.get("error")})
    return out


# ---------------------------------------------------------------- évaluation
def run_eval(cases):
    results = []
    for c in cases:
        kind = c.get("kind")
        t0 = time.monotonic()
        if kind == "ask":
            r = ask(c["input"], k=c.get("k", 5))
            sc = rag.score_case(c, r.get("text"), sources=r.get("sources"))
        elif kind == "classify":
            r = classify(c["input"], c.get("types"), c.get("sites"))
            sc = rag.score_case(c, r.get("text"), parsed=r.get("parsed"))
        elif kind == "summarize":
            r = summarize(c["input"])
            sc = rag.score_case(c, r.get("text"), parsed=r.get("parsed"))
        else:
            continue
        results.append({"id": c.get("id"), "kind": kind, "score": sc, "ms": r.get("ms"), "tok_s": r.get("tok_s"), "usage": r.get("usage"),
                        "error": r.get("error"), "answer": (r.get("text") or "")[:1500], "parsed": r.get("parsed"), "sources": [s["id"] for s in r.get("sources") or []],
                        "wall_ms": round((time.monotonic() - t0) * 1000)})
    scored = [x["score"]["score"] for x in results if x["score"].get("score") is not None]
    toks = [x["tok_s"] for x in results if x.get("tok_s")]
    by_kind = {}
    for x in results:
        b = by_kind.setdefault(x["kind"], {"n": 0, "score_sum": 0.0, "scored": 0, "errors": 0})
        b["n"] += 1
        if x["error"]:
            b["errors"] += 1
        if x["score"].get("score") is not None:
            b["score_sum"] += x["score"]["score"]; b["scored"] += 1
    for b in by_kind.values():
        b["score"] = round(b["score_sum"] / b["scored"], 2) if b["scored"] else None
        del b["score_sum"]
    report = {"at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "model": LLM_MODEL, "base_url": LLM_BASE, "cases": len(results),
              "score": round(sum(scored) / len(scored), 2) if scored else None, "tok_s_avg": round(sum(toks) / len(toks), 1) if toks else None,
              "tok_s_min": min(toks) if toks else None, "total_s": round(sum(x["wall_ms"] for x in results) / 1000.0, 1), "by_kind": by_kind, "results": results}
    try:
        with open(os.path.join(DATA_DIR, "eval-%s.json" % report["at"].replace(":", "")), "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=1)
    except OSError:
        pass
    return report


_eval_state = {"running": False, "last": None}


def _eval_thread(cases):
    _eval_state["running"] = True
    try:
        _eval_state["last"] = run_eval(cases)
    except Exception as exc:  # noqa: BLE001
        _eval_state["last"] = {"error": str(exc)[:200]}
    finally:
        _eval_state["running"] = False


# ---------------------------------------------------------------- routes
@app.route(PREFIX + "/", methods=["GET"])
def index():
    return send_from_directory(os.path.join(HERE, "static"), "index.html")


@app.route(PREFIX + "/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


@app.route(PREFIX + "/status", methods=["GET"])
def status():
    models = llm_models()
    return jsonify({"model": LLM_MODEL, "base_url": LLM_BASE, "llm_reachable": models is not None, "models": models or [],
                    "model_available": bool(models) and any(LLM_MODEL == m or LLM_MODEL.split(":")[0] == (m or "").split(":")[0] for m in models),
                    "index": _index_info, "eval_running": _eval_state["running"], "sources": {"documents": DOCS_DIR, "repo": REPO_DOCS_DIR if os.path.isdir(REPO_DOCS_DIR) else None, "tickets": bool(TICKETS_API), "ged": bool(GED_API)}, "think": LLM_THINK}), 200


@app.route(PREFIX + "/index/rebuild", methods=["POST"])
def index_rebuild():
    if _index_info["building"]:
        return _bad("indexation déjà en cours", 409)
    threading.Thread(target=build_index, daemon=True).start()
    return jsonify({"started": True}), 202


@app.route(PREFIX + "/search", methods=["GET"])
def search():
    q = request.args.get("q") or ""
    return jsonify({"hits": [{k: v for k, v in h.items() if k != "meta"} for h in INDEX.search(q, k=int(request.args.get("k") or 8), source=request.args.get("source"))]}), 200


@app.route(PREFIX + "/ask", methods=["POST"])
def ask_route():
    b = request.get_json(silent=True) or {}
    q = (b.get("question") or "").strip()
    if not q:
        return _bad("question vide")
    return jsonify(ask(q, k=int(b.get("k") or 5), source=b.get("source"), free=bool(b.get("free")))), 200


@app.route(PREFIX + "/classify", methods=["POST"])
def classify_route():
    b = request.get_json(silent=True) or {}
    if not (b.get("text") or "").strip():
        return _bad("texte vide")
    return jsonify(classify(b["text"], b.get("types"), b.get("sites"))), 200


@app.route(PREFIX + "/summarize", methods=["POST"])
def summarize_route():
    b = request.get_json(silent=True) or {}
    if not (b.get("text") or "").strip():
        return _bad("texte vide")
    return jsonify(summarize(b["text"])), 200


@app.route(PREFIX + "/uploads", methods=["GET", "POST"])
def uploads():
    """Textes de test (documents GED à classer, questions) déposés pour le
    PoC -- indexés comme source « uploads »."""
    d = os.path.join(DATA_DIR, "uploads")
    os.makedirs(d, exist_ok=True)
    if request.method == "GET":
        return jsonify({"files": sorted(os.listdir(d))}), 200
    f = request.files.get("file")
    if not f or not f.filename:
        return _bad("fichier manquant")
    name = re.sub(r"[^A-Za-z0-9._-]", "_", f.filename)[:120]
    f.save(os.path.join(d, name))
    return jsonify({"saved": name}), 201


@app.route(PREFIX + "/eval/cases", methods=["GET"])
def eval_cases():
    return jsonify(_load_cases()), 200


def _load_cases():
    custom = os.path.join(DATA_DIR, "cases.json")
    path = custom if os.path.exists(custom) else os.path.join(HERE, "eval", "cases.json")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


@app.route(PREFIX + "/eval/run", methods=["POST"])
def eval_run():
    if _eval_state["running"]:
        return _bad("évaluation déjà en cours", 409)
    b = request.get_json(silent=True) or {}
    cases = b.get("cases") or _load_cases().get("cases") or []
    if b.get("kind"):
        cases = [c for c in cases if c.get("kind") == b["kind"]]
    threading.Thread(target=_eval_thread, args=(cases,), daemon=True).start()
    return jsonify({"started": len(cases)}), 202


@app.route(PREFIX + "/eval/last", methods=["GET"])
def eval_last():
    return jsonify({"running": _eval_state["running"], "report": _eval_state["last"], "history": sorted(os.path.basename(p) for p in glob.glob(os.path.join(DATA_DIR, "eval-*.json")))}), 200


@app.route(PREFIX + "/eval/history/<name>", methods=["GET"])
def eval_history(name):
    if not re.match(r"^eval-[0-9TZ-]+\.json$", name):
        return _bad("nom invalide")
    try:
        with open(os.path.join(DATA_DIR, name), encoding="utf-8") as fh:
            return jsonify(json.load(fh)), 200
    except OSError:
        return _bad("introuvable", 404)


@app.route(PREFIX + "/journal", methods=["GET"])
def journal_route():
    out = []
    try:
        with open(_journal_path, encoding="utf-8") as fh:
            lines = fh.readlines()[-200:]
        out = [json.loads(l) for l in lines if l.strip()]
    except (OSError, ValueError):
        pass
    return jsonify({"journal": list(reversed(out))}), 200


if os.environ.get("ASSISTANT_INDEX_AT_START", "1") == "1":
    threading.Thread(target=build_index, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
