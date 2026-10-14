#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""#767 : transcription d'une session de travail (journal JSONL Claude / Cowork) en Markdown lisible, pour nourrir la base
documentaire de l'assistant du hub et ses jeux d'évaluation : demandes de l'utilisateur, réponses, commandes passées
(outil + commande) et extrait borné de leur résultat (erreurs comprises), résumés de contexte.

Secrets masqués d'office (mots de passe, jetons, clés privées, en-têtes Authorization) ; --map applique une table
{réel: fictif} pour produire une version publiable (noms, IP, domaines). Aucune donnée réelle dans ce script.

Usage : transcript_to_md.py session.jsonl [...] [-o sortie.md] [--map table.json] [--max-tool 1200] [--no-tools]"""
import argparse
import json
import re
import sys

SECRET_RES = [
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S), "«clé privée masquée»"),
    (re.compile(r"(?i)\b(authorization\s*:\s*(?:bearer|basic|pveapitoken=?)\s*)\S+"), r"\1«masqué»"),
    (re.compile(r"(?i)\b(pass(?:word|wd)?|mdp|mot de passe|secret|token|api[_-]?key|private[_-]?key)(\s*[:=]\s*[\"']?)([^\s\"',;]{4,})"), r"\1\2«masqué»"),
    (re.compile(r"(?i)(PVEAPIToken=[^=\s]+=)[0-9a-f-]{20,}"), r"\1«masqué»"),
]
NOISE = re.compile(r"<system-reminder>.*?</system-reminder>|<artifact-content-authored-by-others/>", re.S)
CONTINUED = "This session is being continued from a previous conversation"


def redact(text, mapping=None):
    t = text or ""
    for rx, rep in SECRET_RES:
        t = rx.sub(rep, t)
    for real, fake in sorted((mapping or {}).items(), key=lambda kv: -len(kv[0])):
        if real:
            t = re.sub(re.escape(real), fake, t, flags=re.I)
    return t


def _text(content):
    if isinstance(content, str):
        return content
    out = []
    for b in content or []:
        if isinstance(b, dict) and b.get("type") == "text":
            out.append(b.get("text") or "")
    return "\n".join(out)


def _tool_input(inp):
    if not isinstance(inp, dict):
        return str(inp)
    for k in ("command", "query", "pattern", "file_path", "path", "prompt", "message", "url"):
        if inp.get(k):
            return str(inp[k])
    return json.dumps(inp, ensure_ascii=False)[:400]


def _result_text(c):
    if isinstance(c, str):
        return c
    if isinstance(c, list):
        return "\n".join(_result_text(x.get("text") if isinstance(x, dict) and x.get("type") == "text" else "") for x in c)
    return ""


def _clip(t, n):
    t = (t or "").strip()
    return t if len(t) <= n else t[: n // 2] + "\n[…]\n" + t[-n // 2:]


def convert(lines, mapping=None, max_tool=1200, tools=True):
    """Lignes JSONL -> Markdown."""
    md, day, names = [], None, {}
    for raw in lines:
        try:
            d = json.loads(raw)
        except ValueError:
            continue
        typ, msg, ts = d.get("type"), d.get("message") or {}, (d.get("timestamp") or "")
        if typ not in ("user", "assistant"):
            continue
        if ts[:10] and ts[:10] != day:
            day = ts[:10]
            md.append("\n## %s\n" % day)
        hh = ts[11:16]
        content = msg.get("content")
        if typ == "user":
            if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
                if not tools:
                    continue
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        r = _clip(NOISE.sub("", _result_text(b.get("content"))), max_tool)
                        if r:
                            md.append("%s\n```\n%s\n```\n" % ("> ⚠ résultat en erreur" if b.get("is_error") else "> résultat", redact(r, mapping)))
                continue
            t = NOISE.sub("", _text(content)).strip()
            if not t:
                continue
            if t.startswith(CONTINUED) or CONTINUED in t[:400]:
                md.append("### Résumé de contexte (%s)\n\n%s\n" % (hh, redact(t, mapping)))
            else:
                md.append("### Utilisateur (%s)\n\n%s\n" % (hh, redact(t, mapping)))
        else:
            for b in content or []:
                if not isinstance(b, dict):
                    continue
                if b.get("type") == "text" and (b.get("text") or "").strip():
                    md.append("### Assistant (%s)\n\n%s\n" % (hh, redact(b["text"].strip(), mapping)))
                elif b.get("type") == "tool_use" and tools:
                    name = re.sub(r"^mcp__[^_]+(?:-[^_]+)*__", "", b.get("name") or "")
                    names[b.get("id")] = name
                    md.append("> outil `%s` :\n```\n%s\n```\n" % (name, redact(_clip(_tool_input(b.get("input")), max_tool), mapping)))
    return "\n".join(md).strip() + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--output")
    ap.add_argument("--map", help="table JSON {réel: fictif} (version publiable)")
    ap.add_argument("--max-tool", type=int, default=1200)
    ap.add_argument("--no-tools", action="store_true")
    a = ap.parse_args(argv)
    mapping = json.load(open(a.map, encoding="utf-8")) if a.map else None
    out = []
    for p in a.inputs:
        with open(p, encoding="utf-8") as fh:
            out.append("# Session %s\n\n%s" % (p.rsplit("/", 1)[-1].split(".")[0], convert(fh, mapping, a.max_tool, not a.no_tools)))
    text = "\n\n".join(out)
    if a.output:
        with open(a.output, "w", encoding="utf-8") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
