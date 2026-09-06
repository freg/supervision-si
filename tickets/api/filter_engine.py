"""
Moteur d'application des règles de filtrage regex — pour chaque
événement calendrier importé, essaie chaque règle active (par ordre de
priorité croissante) et applique la première qui matche.

Deux actions possibles, configurables par règle :
- attach_existing : extrait un identifiant de ticket via un groupe
  nommé de la regex, rattache l'événement comme segment de temps si un
  ticket avec cet id existe.
- create_ticket : crée un nouveau ticket (avec les valeurs par défaut
  de la règle) et y rattache l'événement.
- both : essaie d'abord attach_existing (si le groupe nommé matche ET
  qu'un ticket existe) ; sinon crée un ticket.
"""
import re


def compile_rule_pattern(pattern: str):
    """Compile la regex — renvoie None si invalide (pattern utilisateur
    potentiellement mal formé, ne doit jamais faire planter l'import)."""
    try:
        return re.compile(pattern)
    except re.error:
        return None


def extract_ticket_ref(match: "re.Match", group_name: str | None):
    if not group_name:
        return None
    try:
        return match.group(group_name)
    except (IndexError, re.error):
        return None


def apply_rules_to_event(event: dict, rules: list[dict], find_ticket_by_id_fn):
    """
    event : {"summary": str, "description": str, ...}
    rules : liste de dicts (voir schéma calendar_filter_rules), déjà
            triée par priority croissante, actives uniquement.
    find_ticket_by_id_fn : callable(ref: str) -> ticket_id (int) | None

    Renvoie un dict décrivant l'action à effectuer, ou None si aucune
    règle ne matche :
      {"action": "attach", "ticket_id": int, "rule_id": int}
      {"action": "create", "rule": <dict règle>, "rule_id": int}
    """
    for rule in rules:
        target = rule.get("target_field", "summary")
        haystacks = []
        if target in ("summary", "both"):
            haystacks.append(event.get("summary") or "")
        if target in ("description", "both"):
            haystacks.append(event.get("description") or "")

        compiled = compile_rule_pattern(rule["pattern"])
        if compiled is None:
            continue

        match = None
        for haystack in haystacks:
            match = compiled.search(haystack)
            if match:
                break
        if not match:
            continue

        action = rule.get("action", "both")
        ref = extract_ticket_ref(match, rule.get("ticket_ref_group"))

        if action in ("attach_existing", "both") and ref:
            ticket_id = find_ticket_by_id_fn(ref)
            if ticket_id is not None:
                return {"action": "attach", "ticket_id": ticket_id, "rule_id": rule["id"]}
            if action == "attach_existing":
                continue  # ref fourni mais aucun ticket trouvé, et pas de repli création -> règle suivante

        if action in ("create_ticket", "both"):
            return {"action": "create", "rule": rule, "rule_id": rule["id"]}

    return None
