# -*- coding: utf-8 -*-
"""Assistant IA interne, PoC palier 1 (livraison #532, backlog item 81) --
logique PURE : découpage des documents en morceaux, index lexical BM25
(aucun modèle d'embeddings au PoC : le classement lexical suffit pour
mesurer si le modèle répond juste AVEC les bonnes sources), construction
des invites (RAG, classement GED, résumé de ticket), extraction de JSON
dans une réponse, et notation des cas d'évaluation."""
import json
import math
import re
import unicodedata
from collections import Counter

STOP = set("""le la les l un une des du de d et ou où en au aux a à ce cet cette ces se sa son ses sur pour par pas ne
n est sont été être avec sans dans que qui quoi dont il elle ils elles on nous vous je tu y il ya plus moins très
the of and to in is are for on with by at from as it this that
quel quelle quels quelles comment pourquoi combien lequel laquelle quand lorsque est-ce
fait faire font sert servent porte peut peuvent doit doivent met mettent connait connaît ainsi aussi donc alors
cela ça ceci celui celle ceux mon ma mes ton ta tes leur leurs notre votre nos vos tout tous toute toutes""".split())

# Clitiques interrogatifs (« teste-t-elle », « met-il ») : ôtés avant
# l'indexation, sinon chaque tournure devient un jeton rare très pondéré (#536).
_CLITIC = re.compile(r"-t?-?(il|elle|ils|elles|on|je|tu|nous|vous|ce)$")


def normalize(text):
    s = unicodedata.normalize("NFKD", text or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    return s


def tokenize(text):
    toks = re.findall(r"[a-z0-9][a-z0-9_.-]{1,}", normalize(text))
    out = []
    for t in toks:
        t = _CLITIC.sub("", t.strip(".-_"))
        # mot composé (« auto-mise », « path-probe ») : le composé ET ses parties (#536)
        parts = [t] + ([p for p in t.split("-") if len(p) > 1] if "-" in t else [])
        for w in parts:
            if len(w) < 2 or w in STOP:
                continue
            # racine grossière : pluriels / féminins
            if len(w) > 5 and w.endswith(("es", "s")):
                w = w.rstrip("s")
            out.append(w)
    return out


def chunk_text(text, size=900, overlap=150):
    """Morceaux de ~size caractères, coupés de préférence sur un saut de
    ligne ou une phrase, avec recouvrement."""
    text = (text or "").strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    out, i = [], 0
    while i < len(text):
        j = min(len(text), i + size)
        if j < len(text):
            cut = max(text.rfind("\n", i + size // 2, j), text.rfind(". ", i + size // 2, j))
            if cut > i:
                j = cut + 1
        out.append(text[i:j].strip())
        if j >= len(text):
            break
        i = max(j - overlap, i + 1)
    return [c for c in out if c]


_HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*#*\s*$")


def chunk_markdown(text, size=900, overlap=150):
    """Comme chunk_text, mais par section Markdown : chaque morceau est
    préfixé du fil des titres (« § Titre 1 › Titre 2 ») pour que la question
    qui nomme la section retrouve son passage, et que le modèle sache d'où
    vient l'extrait (#536). Sans titre, identique à chunk_text."""
    if not re.search(r"(?m)^#{1,6}\s+\S", text or ""):
        return chunk_text(text, size, overlap)
    sections, trail, buf = [], {}, []

    def flush():
        body = "\n".join(buf).strip()
        if body:
            heads = [trail[k] for k in sorted(trail)]
            sections.append((("§ " + " › ".join(heads) + "\n") if heads else "", body))
        buf.clear()

    for line in (text or "").splitlines():
        m = _HEADING.match(line)
        if m:
            flush()
            lvl = len(m.group(1))
            trail = {k: v for k, v in trail.items() if k < lvl}
            trail[lvl] = m.group(2).strip()
            continue
        buf.append(line)
    flush()
    out = []
    for prefix, body in sections:
        for c in chunk_text(body, max(200, size - len(prefix)), overlap):
            out.append(prefix + c)
    return out


class BM25:
    """Index BM25 en mémoire : docs = [{id, source, title, text, meta}]."""

    def __init__(self, k1=1.5, b=0.75):
        self.k1, self.b, self.docs, self.tf, self.df, self.avgdl = k1, b, [], [], Counter(), 0.0

    def build(self, docs):
        self.docs, self.tf, self.df = list(docs), [], Counter()
        total = 0
        for d in self.docs:
            # Titre compté triple (#535) : une question qui nomme le module
            # (si-agent, service-watch...) remonte son README avant le journal.
            title = tokenize(d.get("title") or "")
            toks = title * 3 + tokenize(d.get("text") or "")
            c = Counter(toks)
            self.tf.append(c)
            self.df.update(c.keys())
            total += len(toks)
        self.avgdl = total / len(self.docs) if self.docs else 0.0
        return self

    def search(self, query, k=5, source=None, max_per_doc=0):
        """k meilleurs morceaux. `weight` du morceau (défaut 1) multiplie le
        score BM25 ; `max_per_doc` > 0 plafonne les morceaux d'un même
        document (#535) -- désactivé par défaut depuis #536 : le plafond
        chassait les bons passages au profit de README hors sujet."""
        q = tokenize(query)
        if not q or not self.docs:
            return []
        n = len(self.docs)
        scores = []
        for i, d in enumerate(self.docs):
            if source and d.get("source") != source:
                continue
            tf = self.tf[i]
            dl = sum(tf.values()) or 1
            s = 0.0
            for t in q:
                if t not in tf:
                    continue
                idf = math.log(1 + (n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                s += idf * tf[t] * (self.k1 + 1) / (tf[t] + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1)))
            if s > 0:
                scores.append((s * float(d.get("weight") or 1.0), i))
        scores.sort(reverse=True)
        out, per = [], Counter()
        for s, i in scores:
            key = self.docs[i].get("doc") or self.docs[i].get("id")
            if max_per_doc and per[key] >= max_per_doc:
                continue
            per[key] += 1
            out.append(dict(self.docs[i], score=round(s, 3)))
            if len(out) >= k:
                break
        return out


# --- invites ------------------------------------------------------------------

SYSTEM_RAG = ("Tu es l'assistant interne du système d'information. Tu réponds en français, de façon brève et précise, "
              "UNIQUEMENT à partir des extraits fournis. Si les extraits ne permettent pas de répondre, dis-le. "
              "Cite les sources utilisées sous la forme [n].")
SYSTEM_JSON = "Tu réponds uniquement par un objet JSON valide, sans texte autour, sans balise de code."


def build_rag_messages(question, hits, max_chars=6000):
    ctx, used = [], 0
    for i, h in enumerate(hits, 1):
        piece = "[%d] (%s — %s)\n%s\n" % (i, h.get("source"), h.get("title") or h.get("id"), (h.get("text") or "")[:1500])
        if used + len(piece) > max_chars:
            break
        ctx.append(piece); used += len(piece)
    user = "Extraits :\n\n%s\nQuestion : %s" % ("\n".join(ctx), question)
    return [{"role": "system", "content": SYSTEM_RAG}, {"role": "user", "content": user}]


def build_classify_messages(text, types, sites, max_chars=5000):
    user = ("Document à classer (extrait) :\n\"\"\"\n%s\n\"\"\"\n\n"
            "Types possibles : %s\nSites possibles : %s\n\n"
            "Renvoie un JSON avec les clés : type (un des types possibles ou \"autre\"), site (un des sites ou null), "
            "titre (court), resume (2 phrases), mots_cles (liste de 3 à 6), date (AAAA-MM-JJ ou null), confiance (0 à 1)."
            % ((text or "")[:max_chars], ", ".join(types) or "libre", ", ".join(sites) or "libre"))
    return [{"role": "system", "content": SYSTEM_JSON}, {"role": "user", "content": user}]


def build_summary_messages(ticket_text, max_chars=5000):
    user = ("Demande / ticket :\n\"\"\"\n%s\n\"\"\"\n\nRenvoie un JSON : resume (3 phrases max), categorie (materiel, logiciel, reseau, acces, "
            "impression, messagerie, autre), urgence (basse, normale, haute, critique), actions_suggerees (liste de 1 à 3), "
            "questions_a_poser (liste, éventuellement vide)." % (ticket_text or "")[:max_chars])
    return [{"role": "system", "content": SYSTEM_JSON}, {"role": "user", "content": user}]


EXTRACT_SCHEMAS = {
    "asset": ["Nom", "Type", "Désignation", "Modèle", "Numero de série", "Adresse MAC", "Adresse IP", "Compte", "Lab", "Localisation", "Date de mise en service",
              "Processeur", "Mémoire", "Carte graphique", "Disque", "Système", "Passerelle DHCP", "Rôle", "Commentaire"],
    "service": ["Parcours", "Lab", "Nom de l’atelier", "Matériel", "Wifi", "Lan", "Internet", "Site", "Commentaire"],
}
SENSITIVE_HINT = ("Champs sensibles à signaler dans `sensible` (liste de noms de champs) : adresses IP et MAC, numéros de série, "
                  "identifiants Windows (ID de périphérique, ID de produit), comptes, mots de passe (à NE PAS recopier : mettre \"[masqué]\").")


def build_extract_messages(text, schema="asset", fields=None, context="", max_chars=12000):
    """#571 : extraction de fiches structurées depuis un texte libre (collage
    d'un « À propos » Windows, courriel, PV de livraison…)."""
    cols = fields or EXTRACT_SCHEMAS.get(schema) or EXTRACT_SCHEMAS["asset"]
    user = ("Texte source :\n\"\"\"\n%s\n\"\"\"\n\n%s"
            "Extrais TOUTES les fiches (un objet par équipement ou atelier) dans un JSON de la forme "
            "{\"fiches\": [ {%s} ], \"sensible\": [noms de champs], \"remarques\": [anomalies relevées : IP incohérente, doublon, valeur manquante]}. "
            "Champs : %s. Valeur \"\" si absente, jamais inventée ; dates en AAAA-MM-JJ ; conserve les noms tels quels. %s"
            % ((text or "")[:max_chars], ("Contexte : %s\n\n" % context) if context else "", ", ".join('"%s": ""' % c for c in cols[:6]) + ", ...", ", ".join(cols), SENSITIVE_HINT))
    return [{"role": "system", "content": SYSTEM_JSON}, {"role": "user", "content": user}]


def extract_json(text):
    """Premier objet JSON d'une réponse (le modèle peut bavarder ou entourer de ```)."""
    if not text:
        return None
    s = re.sub(r"<think>.*?</think>", "", text, flags=re.S)  # modèles « raisonnants »
    s = re.sub(r"```(?:json)?", "", s)
    start = s.find("{")
    while start != -1:
        depth = 0
        for i in range(start, len(s)):
            if s[i] == "{":
                depth += 1
            elif s[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(s[start:i + 1])
                    except ValueError:
                        break
        start = s.find("{", start + 1)
    return None


# --- évaluation ---------------------------------------------------------------

def score_case(case, answer, parsed=None, sources=None):
    """Note un cas : mots-clés attendus présents (rappel), JSON valide et
    champs attendus, source attendue dans les extraits. 0..1 par critère."""
    out = {}
    exp = case.get("expect") or {}
    ans_n = normalize(answer or "")
    if exp.get("keywords"):
        hits = [k for k in exp["keywords"] if normalize(k) in ans_n]
        out["keywords"] = round(len(hits) / len(exp["keywords"]), 2)
        out["missing"] = [k for k in exp["keywords"] if normalize(k) not in ans_n]
    if exp.get("forbidden"):
        bad = [k for k in exp["forbidden"] if normalize(k) in ans_n]
        out["forbidden_ok"] = 0.0 if bad else 1.0
    if exp.get("json"):
        out["json_valid"] = 1.0 if isinstance(parsed, dict) else 0.0
        if isinstance(parsed, dict):
            fields = exp["json"]
            ok = 0
            for k, v in fields.items():
                got = parsed.get(k)
                if v is None:
                    ok += 1 if k in parsed else 0
                elif isinstance(v, list):
                    ok += 1 if normalize(str(got)) in [normalize(x) for x in v] else 0
                else:
                    ok += 1 if normalize(str(got)) == normalize(str(v)) else 0
            out["json_fields"] = round(ok / len(fields), 2) if fields else 1.0
    if exp.get("source"):
        out["source_found"] = 1.0 if any(exp["source"] in (s.get("id") or "") or exp["source"] in (s.get("title") or "") for s in sources or []) else 0.0
    vals = [v for k, v in out.items() if isinstance(v, float)]
    out["score"] = round(sum(vals) / len(vals), 2) if vals else None
    return out
