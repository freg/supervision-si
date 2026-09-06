"""
Classification sémantique des identités découvertes (livraison #260,
backlog item 34 -- "à prioriser fort car central", demandé
explicitement après une observation concrète sur de vraies données
réseau : des noms d'hôte comme "alice", "bob", "dhcp139",
"nms", "ups-groupe-x" portent chacun un sens différent -- personne,
client DHCP dynamique, service névralgique, équipement).

**Architecture VOLONTAIREMENT à base de DICTIONNAIRES IMPORTABLES**,
pas de listes codées en dur -- décision prise en cours de conception,
suite à la question explicite de la personne ("une interface d'import
de dictionnaires ?") : NLTK n'est pas installable dans cet
environnement de développement (vérifié -- `pip install nltk`
échoue, aucun miroir accessible), et même installé, ses corpus
linguistiques généralistes (mots anglais, noms très majoritairement
anglo-saxons) n'auraient de toute façon PAS couvert le vocabulaire
réseau/télécom/informatique demandé ("plein de dictionnaires
métiers") -- rien de comparable n'existe en bibliothèque standard.
Solution retenue : un stockage de TERMES classés par CATÉGORIE,
enrichissable par import de fichier (un terme par ligne), plutôt
qu'une dépendance à des données externes non disponibles ici.

**Suivi d'usage ("stats d'usage des mots, lexèmes")** -- chaque
classification réussie incrémente `match_count` sur le terme qui a
servi -- répond directement à la demande, permet de voir quels
termes d'un dictionnaire importé sont RÉELLEMENT utiles en pratique.

**Orientation manuelle** -- `confirm_classification` : la personne
peut CONFIRMER ou CORRIGER une classification automatique pour un
texte précis -- journalisé dans `classifier_results`
(`confirmed=1`), et PEUT (sur action explicite, jamais automatique)
ajouter le terme correspondant au dictionnaire si la catégorie
proposée n'existait pas encore pour ce terme -- ferme la boucle
entre classification et enrichissement du dictionnaire.
"""
import re
import sqlite3
import time

SCHEMA = """
-- Dictionnaire de termes, par catégorie, IMPORTABLE (voir
-- import_terms) -- jamais des listes codées en dur dans le code
-- Python, la personne doit pouvoir enrichir sans redéploiement.
CREATE TABLE IF NOT EXISTS classifier_terms (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    term TEXT NOT NULL,
    category TEXT NOT NULL,
    source TEXT,
    added_at TEXT NOT NULL,
    match_count INTEGER NOT NULL DEFAULT 0,
    last_matched_at TEXT,
    UNIQUE(term, category)
);
CREATE INDEX IF NOT EXISTS idx_classifier_terms_category ON classifier_terms(category);
CREATE INDEX IF NOT EXISTS idx_classifier_terms_term ON classifier_terms(term);

-- Journal des classifications -- historique + support de
-- l'orientation manuelle (confirmed=1 = corrigée/confirmée par la
-- personne, jamais une classification automatique écrasée
-- silencieusement).
CREATE TABLE IF NOT EXISTS classifier_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    input_text TEXT NOT NULL,
    category TEXT,
    matched_term_id INTEGER REFERENCES classifier_terms(id),
    confirmed INTEGER NOT NULL DEFAULT 0,
    classified_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_classifier_results_text ON classifier_results(input_text);
"""

# Catégories STRUCTURELLES (motif de nommage, jamais un dictionnaire
# -- "dhcp139" n'est un "terme" de vocabulaire pour personne, c'est
# un PATRON reconnaissable directement). Détectées AVANT toute
# recherche en dictionnaire -- un nom qui matche ce patron est
# tranché sans ambiguïté, contrairement à un mot de vocabulaire qui
# pourrait apparaître dans plusieurs catégories.
_DHCP_PATTERN = re.compile(r"^dhcp0*(\d+)$", re.IGNORECASE)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def get_connection(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(db_path):
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def import_terms(db_path, category, source, raw_text):
    """Importe un dictionnaire -- UN TERME PAR LIGNE, lignes vides et
    commentaires (`#...`) ignorés, jamais une exception sur une ligne
    mal formée (un fichier de plusieurs milliers de lignes ne doit
    jamais échouer en bloc pour UNE ligne bizarre). Termes normalisés
    en minuscules (la comparaison de classification est elle-même
    insensible à la casse, voir `classify`). `INSERT OR IGNORE` --
    un terme déjà présent pour cette catégorie n'est jamais dupliqué
    ni ne réinitialise son `match_count` existant. Renvoie
    (nombre_ajoutés, nombre_lignes_ignorées)."""
    lines = [l.strip().lower() for l in raw_text.splitlines()]
    terms = [l for l in lines if l and not l.startswith("#")]
    skipped = len(lines) - len(terms)

    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        added = 0
        now = now_iso()
        for term in terms:
            cur.execute(
                "INSERT OR IGNORE INTO classifier_terms (term, category, source, added_at) VALUES (?, ?, ?, ?)",
                [term, category, source, now],
            )
            if cur.rowcount > 0:
                added += 1
        conn.commit()
        return added, skipped
    finally:
        conn.close()


def list_terms(db_path, category=None, source=None):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        clauses, params = [], []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if source:
            clauses.append("source = ?")
            params.append(source)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        cur.execute(f"SELECT * FROM classifier_terms {where} ORDER BY match_count DESC, term ASC", params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def delete_term(db_path, term_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM classifier_terms WHERE id = ?", [term_id])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def delete_source(db_path, source):
    """Retire un dictionnaire IMPORTÉ ENTIER (tous les termes d'une
    même `source`) -- corriger un import fait par erreur sans devoir
    supprimer terme par terme."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM classifier_terms WHERE source = ?", [source])
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def list_categories(db_path):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT category FROM classifier_terms ORDER BY category")
        return [r["category"] for r in cur.fetchall()]
    finally:
        conn.close()


def _tokenize(text):
    """Découpe un nom d'hôte en mots -- séparateurs `.`/`-`/`_`,
    jamais une simple recherche de sous-chaîne qui matcherait "ups"
    à l'intérieur de "groupe" par erreur (le vrai cas rencontré :
    "ups-groupe-x" contient bien "groupe", jamais un faux-positif
    voulu)."""
    return [t for t in re.split(r"[.\-_]+", text.lower()) if t]


def classify(db_path, text, ip_address=None, record=True):
    """Classifie `text` (typiquement un nom d'hôte) -- renvoie
    {"category", "matched_term", "matched_token", "reason"} ou
    {"category": None, ...} si rien ne correspond.

    Le texte est d'abord DÉCOUPÉ EN TOKENS (voir _tokenize) -- le
    motif structurel dhcpNNN ET la recherche en dictionnaire sont
    TOUS LES DEUX testés PAR TOKEN, jamais contre la chaîne entière :
    un nom d'hôte réel porte presque toujours un suffixe de domaine
    ("dhcp139.intranet") qui empêcherait un ancrage `^...$` de
    matcher autrement (bug réel trouvé en testant contre de vraies
    données -- "dhcp136.intranet" ne matchait jamais tant que le
    motif dhcp était comparé à la chaîne complète). Tokens triés du
    PLUS LONG au plus court -- une correspondance plus spécifique
    l'emporte sur une plus courte si plusieurs tokens pouvaient
    matcher (ex. "groupe-x" avant "i" seul, si les deux étaient
    enregistrés).

    `record=True` (par défaut) journalise le résultat dans
    `classifier_results` ET incrémente `match_count` sur le terme
    utilisé (voir docstring du module, "stats d'usage") -- mettre à
    `False` pour un essai/aperçu qui ne doit PAS compter dans les
    statistiques (ex. prévisualisation avant import)."""
    tokens = sorted(_tokenize(text), key=len, reverse=True)

    for token in tokens:
        dhcp_match = _DHCP_PATTERN.match(token)
        if dhcp_match:
            suffix = dhcp_match.group(1)
            # Confirmation par l'IP -- comparaison NUMÉRIQUE (pas une
            # comparaison de chaînes) pour gérer naturellement les
            # zéros de tête ("dhcp007" doit confirmer contre une IP
            # finissant en ".7", pas seulement ".007" qui n'existe
            # pas en IPv4).
            ip_confirms = False
            if ip_address:
                last_octet = ip_address.strip().split(".")[-1]
                if last_octet.isdigit() and int(last_octet) == int(suffix):
                    ip_confirms = True
            result = {
                "category": "client_dhcp_dynamique",
                "matched_term": None,
                "matched_token": token,
                "reason": f"motif dhcp+numéro{' (confirmé par l’IP)' if ip_confirms else ''}",
            }
            if record:
                _record_result(db_path, text, result["category"], None)
            return result

    if tokens:
        conn = get_connection(db_path)
        try:
            cur = conn.cursor()
            for token in tokens:
                cur.execute("SELECT * FROM classifier_terms WHERE term = ?", [token])
                row = cur.fetchone()
                if row:
                    result = {
                        "category": row["category"], "matched_term": row["term"],
                        "matched_token": token, "reason": f"trouvé dans le dictionnaire \"{row['source'] or '?'}\"",
                    }
                    if record:
                        cur.execute(
                            "UPDATE classifier_terms SET match_count = match_count + 1, last_matched_at = ? WHERE id = ?",
                            [now_iso(), row["id"]],
                        )
                        conn.commit()
                        _record_result(db_path, text, result["category"], row["id"])
                    return result
        finally:
            conn.close()

    result = {"category": None, "matched_term": None, "matched_token": None, "reason": "aucune correspondance"}
    if record:
        _record_result(db_path, text, None, None)
    return result


def _record_result(db_path, input_text, category, matched_term_id):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO classifier_results (input_text, category, matched_term_id, confirmed, classified_at) VALUES (?, ?, ?, 0, ?)",
            [input_text, category, matched_term_id, now_iso()],
        )
        conn.commit()
    finally:
        conn.close()


# Mots génériques à ne JAMAIS ajouter automatiquement à un
# dictionnaire via la confirmation manuelle -- des suffixes de
# domaine/réseau qui n'identifient RIEN de spécifique par eux-mêmes
# (contrairement à "marc" ou "dupont", extraits d'un nom d'hôte
# composé comme "marc-dupont.intranet").
_GENERIC_TOKENS = {"intranet", "local", "lan", "corp", "internal", "domain", "net", "com", "fr"}


def confirm_classification(db_path, input_text, category, add_to_dictionary=False, source=None):
    """Orientation manuelle (demandé explicitement : "je veux pouvoir
    accéder aux stats d'usage des mots... et d'orienter") -- la
    personne confirme/corrige la classification d'un texte précis.
    `add_to_dictionary` -- sur action EXPLICITE seulement (jamais
    automatique) : ajoute TOUS les tokens SIGNIFICATIFS de
    `input_text` (hors suffixes génériques comme "intranet", voir
    `_GENERIC_TOKENS`) au dictionnaire sous cette catégorie -- un nom
    composé ("marc-dupont.intranet") enrichit ainsi le dictionnaire
    avec CHAQUE partie utile ("marc" ET "dupont"), pas seulement la
    première rencontrée, pour que les PROCHAINES classifications
    reconnaissent l'une ou l'autre partie indépendamment."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO classifier_results (input_text, category, matched_term_id, confirmed, classified_at) VALUES (?, ?, NULL, 1, ?)",
            [input_text, category, now_iso()],
        )
        conn.commit()
    finally:
        conn.close()

    if add_to_dictionary and category:
        significant_tokens = [t for t in _tokenize(input_text) if t not in _GENERIC_TOKENS]
        for token in significant_tokens:
            import_terms(db_path, category, source or "corrections manuelles", token)


def list_results(db_path, category=None, confirmed_only=False, limit=200):
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        clauses, params = [], []
        if category:
            clauses.append("category = ?")
            params.append(category)
        if confirmed_only:
            clauses.append("confirmed = 1")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        cur.execute(f"SELECT * FROM classifier_results {where} ORDER BY classified_at DESC LIMIT ?", params)
        return [dict(r) for r in cur.fetchall()]
    finally:
        conn.close()


def usage_stats(db_path):
    """LES "stats d'usage des mots, lexèmes" demandées explicitement
    -- termes triés par `match_count` décroissant (les plus utiles en
    pratique en tête), avec le nombre de termes JAMAIS utilisés
    (`match_count = 0`) mis en évidence séparément -- signal direct
    de ce qui, dans un dictionnaire importé, ne sert à rien sur les
    données réelles de la personne."""
    conn = get_connection(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT category, COUNT(*) as total_terms, SUM(match_count) as total_matches, SUM(CASE WHEN match_count = 0 THEN 1 ELSE 0 END) as unused_terms FROM classifier_terms GROUP BY category")
        by_category = [dict(r) for r in cur.fetchall()]
        cur.execute("SELECT * FROM classifier_terms WHERE match_count > 0 ORDER BY match_count DESC LIMIT 20")
        top_terms = [dict(r) for r in cur.fetchall()]
        return {"by_category": by_category, "top_terms": top_terms}
    finally:
        conn.close()
