"""
Moteur d'orchestration -- même séparation calcul/effet de bord que
netprobe/api/analyzer_engine.py (livraison #307) : les règles
(rules/*.py) sont pures, CE module est le seul point qui appelle
network-agent-api ET qui écrit en base (store.py).
"""
import logging

import network_agent_client as na
import store
from rules import RULES

_log = logging.getLogger("netmap_orchestrator_engine")


def build_context(api_base):
    """Rassemble les données nécessaires aux règles EN UN SEUL passage
    réseau par segment -- jamais un appel par règle, qui multiplierait
    inutilement les requêtes vers network-agent-api pour les mêmes
    données. Renvoie (context, errors) -- `errors` est une liste de
    messages (jamais vide en cas de souci PARTIEL -- un segment en
    échec n'empêche jamais les autres d'être traités)."""
    errors = []
    all_devices = []
    services_by_device = {}

    devices, error = na.list_devices(api_base)
    if error:
        errors.append(error)
        return {"devices": [], "services_by_device": {}}, errors
    all_devices = devices

    segment_ids = sorted({d["network_segment_id"] for d in all_devices if d.get("network_segment_id") is not None})
    for segment_id in segment_ids:
        grouped, seg_error = na.list_services_by_segment(api_base, segment_id)
        if seg_error:
            errors.append(f"segment {segment_id} : {seg_error}")
            continue
        # Clés renvoyées en CHAÎNES par l'API HTTP (JSON n'a pas de
        # clé entière) -- reconverties ici pour correspondre à
        # device["id"] (entier) côté appelant, une seule fois plutôt
        # que dans chaque règle.
        for device_id_str, services in grouped.items():
            try:
                services_by_device[int(device_id_str)] = services
            except (ValueError, TypeError):
                continue

    return {"devices": all_devices, "services_by_device": services_by_device}, errors


def run_rule(db_path, api_base, rule_name, context=None):
    """Exécute UNE règle nommée -- renvoie (nombre_de_suggestions, error).
    `context` réutilisable entre plusieurs appels (voir run_all_rules)
    -- reconstruit depuis network-agent-api si absent, pour un appel
    isolé (ex. déclenché manuellement via l'API)."""
    rule = RULES.get(rule_name)
    if rule is None:
        return None, f"règle inconnue : {rule_name!r} (attendu : {list(RULES)})"

    if context is None:
        context, errors = build_context(api_base)
        if errors:
            return 0, "; ".join(errors)

    try:
        findings = rule.analyze(context)
    except Exception as exc:  # noqa: BLE001 -- une règle en échec ne doit JAMAIS bloquer les autres
        _log.debug("run_rule : %s a échoué -- %s", rule_name, exc)
        return 0, str(exc)

    for finding in findings:
        store.record_or_update_suggestion(
            db_path, rule_name, finding["subject_type"], finding["subject_key"],
            finding["severity"], finding["message"],
            suggested_action=finding.get("suggested_action"),
            action_params=finding.get("action_params"),
        )
    return len(findings), None


def run_all_rules(db_path, api_base):
    """Exécute TOUTES les règles enregistrées avec UN SEUL contexte
    partagé (un seul passage réseau vers network-agent-api, voir
    build_context) -- un échec d'une règle n'empêche jamais les
    autres de tourner. Renvoie {nom: {"count": int, "error": str|None}}."""
    context, context_errors = build_context(api_base)
    results = {}
    for rule_name in RULES:
        if context_errors and not context["devices"]:
            results[rule_name] = {"count": 0, "error": "; ".join(context_errors)}
            continue
        count, error = run_rule(db_path, api_base, rule_name, context=context)
        results[rule_name] = {"count": count, "error": error}
    return results
