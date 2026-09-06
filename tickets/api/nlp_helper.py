"""
Assistance heuristique à la création (login/nom) et à la découverte de
motifs récurrents dans les imports calendrier.

⚠️ Ce n'est PAS un moteur NLP réel (pas de modèle de langue, pas
d'analyse syntaxique, pas de reconnaissance d'entités nommées) —
aucun accès à un tel outil n'était disponible pendant le développement
(pas de réseau pour installer/télécharger un modèle). Ce qui suit est
un classement par position/fréquence/exclusion de mots-outils :
utile pour repérer des candidats plausibles et accélérer la création,
mais ça se trompera parfois (faux positifs sur des termes techniques
non filtrés, faux négatifs sur des noms rares) — à valider par un
humain avant création, jamais automatique.
"""
import re
from collections import Counter

from suggestion_engine import STOPWORDS, strip_accents

# Vocabulaire technique courant à exclure des candidats "nom de
# personne" — évite qu'un terme métier récurrent (switch, panne...)
# ne soit proposé comme si c'était un login. Liste volontairement
# extensible, pas prétendument exhaustive.
TECH_STOPWORDS = {
    "switch", "serveur", "reseau", "panne", "config", "configuration",
    "vpn", "acces", "imprimante", "test", "demande", "incident",
    "probleme", "install", "installation", "maintenance", "mise",
    "jour", "sauvegarde", "backup", "site", "client", "bureau",
    "agent", "down", "traitement", "suite", "reunion", "rdv",
    "rendez", "vous", "hebdo", "equipe", "diagnostic", "remplacement",
    "module", "baie", "onboarding", "dejeuner", "pause",
    "sms", "sim", "nms", "plateforme", "supervision", "dev", "rapport",
    "wifi", "google", "meet", "https", "urgence", "glpi", "ged",
}

ALL_STOPWORDS = STOPWORDS | TECH_STOPWORDS


def tokenize(text: str) -> list[str]:
    return re.findall(r"[A-Za-zÀ-ÿ]+", text or "")


def is_probable_identifier(token: str) -> bool:
    normalized = strip_accents(token.lower())
    return len(normalized) >= 3 and normalized not in ALL_STOPWORDS


def extract_candidate_names(event: dict, trigger_pattern: "re.Pattern | None" = None, window: int = 4) -> list[str]:
    """
    Pour UN événement : renvoie les tokens plausibles comme login/nom,
    dans l'ordre d'apparition (le premier est en général le plus
    pertinent — juste après le mot-clé déclencheur si trouvé).

    Si un mot-clé déclencheur est configuré, seuls les événements où il
    matche sont considérés — sinon les réunions/rendez-vous sans
    rapport avec un ticket (Google Meet, wifi, GLPI...) noient les
    vrais candidats dans l'analyse en lot. Sans mot-clé configuré
    (trigger_pattern=None), tout le texte reste utilisé.
    """
    text = f"{event.get('summary') or ''} {event.get('description') or ''}"

    if trigger_pattern is not None:
        match = trigger_pattern.search(text)
        if not match:
            return []
        # Priorité aux tokens juste après le déclencheur (motif observé :
        # "SAV <login> - <sujet>"). Le mot-clé lui-même ne doit jamais
        # ressortir comme candidat (absurde de "créer un utilisateur SAV").
        remainder_tokens = tokenize(text[match.end():])[:window]
        candidates = [t for t in remainder_tokens if is_probable_identifier(t) and t.lower() != match.group(0).lower()]
        if candidates:
            return candidates
        # Motif consommant tout (ex: "SAV.*" gourmand) -> repli sur
        # l'ensemble du texte de CET événement (toujours déclenché,
        # donc toujours pertinent), en excluant le mot-clé lui-même.
        return [t for t in tokenize(text) if is_probable_identifier(t) and t.lower() != match.group(0).lower()]

    return [t for t in tokenize(text) if is_probable_identifier(t)]


def best_candidate_name(events: list[dict], trigger_keyword: str | None) -> str | None:
    """Meilleur candidat unique pour pré-remplir un champ login/nom,
    à partir d'un ou plusieurs événements sélectionnés."""
    pattern = None
    if trigger_keyword:
        try:
            pattern = re.compile(trigger_keyword, re.IGNORECASE)
        except re.error:
            pattern = None

    counter = Counter()
    for event in events:
        for token in extract_candidate_names(event, pattern):
            counter[strip_accents(token.lower())] += 1

    if not counter:
        return None
    best_key, _ = counter.most_common(1)[0]
    # Retrouve la casse d'origine du premier token correspondant.
    for event in events:
        for token in extract_candidate_names(event, pattern):
            if strip_accents(token.lower()) == best_key:
                return token
    return best_key


def mine_candidate_identifiers(events: list[dict], trigger_keyword: str | None, known_users: list[dict], top_n: int = 15) -> list[dict]:
    """
    Analyse en lot : fréquence des tokens candidats sur tout un
    ensemble d'événements — pour repérer d'un coup d'œil les
    personnes/projets qui reviennent souvent et n'ont pas encore de
    fiche utilisateur.
    """
    pattern = None
    if trigger_keyword:
        try:
            pattern = re.compile(trigger_keyword, re.IGNORECASE)
        except re.error:
            pattern = None

    counter = Counter()
    original_casing = {}
    for event in events:
        for token in extract_candidate_names(event, pattern):
            key = strip_accents(token.lower())
            counter[key] += 1
            original_casing.setdefault(key, token)

    known_logins = {strip_accents(u["login"].lower()) for u in known_users if u.get("login")}
    known_names = {strip_accents(u["name"].lower()) for u in known_users if u.get("name")}

    results = []
    for key, freq in counter.most_common(top_n):
        results.append({
            "token": original_casing[key],
            "frequency": freq,
            "matches_existing_user": key in known_logins or key in known_names,
        })
    return results
