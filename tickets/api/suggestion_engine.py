"""
Moteur de SUGGESTION (pas d'exécution automatique) — pour un événement
calendrier importé, propose des tickets candidats plutôt que de
rattacher/créer silencieusement. La décision finale reste humaine, via
l'écran de revue.

Logique reproduisant la pratique réelle décrite :
1. Le mot-clé déclencheur (config, "SAV" par défaut, insensible à la
   casse) doit être présent dans le titre ou la description — sinon
   l'événement n'est même pas considéré comme lié à un ticket.
2. Recherche d'un login connu mentionné dans le texte de l'événement —
   si trouvé, ne considère que les tickets ouverts de ce demandeur.
   Sinon, tous les tickets ouverts sont candidats.
3. Score de similarité par mots significatifs partagés (>3 caractères,
   hors mots vides français courants) entre le texte de l'événement et
   le sujet/description de chaque ticket candidat.

Volontairement simple (pas de NLP) — un score de recouvrement lexical,
explicable et prévisible, pas une boîte noire.
"""
import re
import unicodedata

STOPWORDS = {
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "sur", "pour",
    "avec", "dans", "au", "aux", "ce", "cette", "ces", "est", "sont", "etre",
    "avoir", "que", "qui", "quoi", "dont", "leur", "leurs", "son", "sa",
    "ses", "vers", "chez", "sans", "sous", "entre", "mais", "donc", "or",
    "ni", "car", "puis", "ainsi", "alors", "comme", "quand", "lors",
}


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    return "".join(c for c in normalized if not unicodedata.combining(c))


def extract_significant_words(text: str) -> set[str]:
    words = re.findall(r"[a-zàâäéèêëïîôöùûüçA-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ]+", text or "")
    # Accents normalisés : "accès" et "acces" doivent matcher, la saisie
    # calendrier étant souvent tapée vite, sans accents.
    normalized = {strip_accents(w.lower()) for w in words}
    return {w for w in normalized if len(w) > 3 and w not in STOPWORDS}


def extract_title_words(text: str, exclude: str = None) -> set[str]:
    """
    Comme extract_significant_words mais seuil abaissé à 3 caractères
    (pas 4) — les acronymes courts (SMS, VPN, GED...) sont justement
    les mots les plus significatifs pour rapprocher un titre d'un
    ticket existant, contrairement au mining de noms de personnes où
    ils créent du bruit. `exclude` (optionnel) : motif à retirer avant
    comptage (typiquement le mot-clé déclencheur, pour ne pas faire
    matcher deux titres uniquement parce qu'ils contiennent tous les
    deux "SAV").
    """
    words = re.findall(r"[a-zàâäéèêëïîôöùûüçA-ZÀÂÄÉÈÊËÏÎÔÖÙÛÜÇ]+", text or "")
    normalized = {strip_accents(w.lower()) for w in words}
    result = {w for w in normalized if len(w) >= 3 and w not in STOPWORDS}
    if exclude:
        excluded = strip_accents(exclude.lower())
        result = {w for w in result if w != excluded}
    return result


def analyze_title_matches(events: list[dict], open_tickets: list[dict], trigger_keyword: str = None, min_score: int = 1, max_results: int = 30) -> list[dict]:
    """
    Indépendant du mot-clé déclencheur — pour chaque événement, cherche
    le ticket ouvert avec lequel il partage le plus de mots
    significatifs (>= 3 caractères). Utile pour les événements qu'un
    déclenchement classique ne capte pas (ex: un titre "SMS" seul,
    alors qu'un ticket "SAV Didier/SMS" existe déjà) — propose d'y
    ajouter une nouvelle plage de temps plutôt que de le laisser filer.
    """
    ticket_words_cache = {
        t["id"]: extract_title_words(f"{t.get('subject') or ''} {t.get('description') or ''}", trigger_keyword)
        for t in open_tickets
    }

    results = []
    for event in events:
        event_words = extract_title_words(f"{event.get('summary') or ''} {event.get('description') or ''}", trigger_keyword)
        if not event_words:
            continue

        best_ticket_id, best_score, best_shared = None, 0, set()
        for ticket in open_tickets:
            shared = event_words & ticket_words_cache[ticket["id"]]
            if len(shared) > best_score:
                best_ticket_id, best_score, best_shared = ticket["id"], len(shared), shared

        if best_ticket_id is not None and best_score >= min_score:
            ticket = next(t for t in open_tickets if t["id"] == best_ticket_id)
            results.append({
                "event_id": event["id"], "event_summary": event.get("summary"),
                "ticket_id": best_ticket_id, "ticket_subject": ticket["subject"],
                "score": best_score, "shared_words": sorted(best_shared),
                "is_closed": bool(ticket.get("is_closed")),
            })

    results.sort(key=lambda r: -r["score"])
    return results[:max_results]


def event_matches_any_pattern(event: dict, patterns: list[str]) -> "tuple[bool, str | None]":
    """
    Utilisé pour la liste d'exclusion : renvoie (True, motif) dès qu'un
    des motifs matche le titre ou la description, sinon (False, None).
    Un motif invalide est ignoré silencieusement (pas de crash sur une
    regex mal formée saisie par erreur).
    """
    haystack = f"{event.get('summary') or ''} {event.get('description') or ''}"
    for pattern in patterns:
        try:
            if re.search(pattern, haystack, re.IGNORECASE):
                return True, pattern
        except re.error:
            continue
    return False, None


def event_has_trigger(event: dict, trigger_keyword: str) -> bool:
    """
    Traité comme une expression régulière (insensible à la casse) —
    cohérent avec le reste de l'app (les règles de filtrage utilisent
    déjà de vraies regex). Un simple mot ("SAV") continue de fonctionner
    tel quel (recherché littéralement). Repli sur une recherche de
    sous-chaîne simple si le motif est invalide, pour ne jamais bloquer
    l'utilisateur sur une erreur de syntaxe regex.
    """
    if not trigger_keyword:
        return True  # pas de mot-clé configuré -> tout événement est candidat
    haystack = f"{event.get('summary') or ''} {event.get('description') or ''}"
    try:
        pattern = re.compile(trigger_keyword, re.IGNORECASE)
    except re.error:
        return trigger_keyword.lower() in haystack.lower()
    return bool(pattern.search(haystack))


def find_mentioned_user(event: dict, users: list[dict]):
    """users : [{'id':.., 'login':..}, ...]. Renvoie l'id du premier
    login trouvé dans le texte de l'événement, ou None."""
    haystack = f"{event.get('summary') or ''} {event.get('description') or ''}".lower()
    for user in users:
        login = (user.get("login") or "").lower()
        if login and login in haystack:
            return user["id"]
    return None


def suggest_candidates(event: dict, trigger_keyword: str, users: list[dict], candidate_tickets: list[dict], max_results=5):
    """
    candidate_tickets : [{'id':.., 'subject':.., 'description':.., 'user_id':.., 'is_closed':bool}, ...]
    -- inclut désormais aussi bien les tickets ouverts que fermés, pour
    reconnaître un événement qui correspond à un ticket déjà traité
    (ex: import d'une base contenant un ticket clos "Paul OwnCloud" +
    un nouvel événement calendrier sur le même sujet) plutôt que de le
    laisser filer sans aucune suggestion. Le tri fait remonter les
    tickets ouverts en priorité à score égal.
    Renvoie {"triggered": bool, "matched_user_id": int|None, "candidates": [{"ticket_id", "score", "is_closed"}, ...]}
    """
    if not event_has_trigger(event, trigger_keyword):
        return {"triggered": False, "matched_user_id": None, "candidates": []}

    matched_user_id = find_mentioned_user(event, users)
    pool = [t for t in candidate_tickets if t["user_id"] == matched_user_id] if matched_user_id else candidate_tickets

    event_words = extract_significant_words(f"{event.get('summary') or ''} {event.get('description') or ''}")

    scored = []
    for ticket in pool:
        ticket_words = extract_significant_words(f"{ticket.get('subject') or ''} {ticket.get('description') or ''}")
        score = len(event_words & ticket_words)
        # Un ticket du bon demandeur reste un candidat même à score 0
        # (le login est déjà un signal fort) ; sans demandeur identifié,
        # n'affiche que les tickets ayant au moins un mot en commun.
        if score > 0 or matched_user_id:
            scored.append({"ticket_id": ticket["id"], "score": score, "is_closed": bool(ticket.get("is_closed"))})

    scored.sort(key=lambda c: (-c["score"], c["is_closed"]))  # score décroissant, ouverts avant fermés à égalité
    return {"triggered": True, "matched_user_id": matched_user_id, "candidates": scored[:max_results]}
