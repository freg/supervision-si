"""Logique pure du module QA (testée à part) : validation/normalisation des étapes d'un scénario, résumé d'une exécution,
rédaction du ticket (incident ou évolution) créé depuis une exécution."""
import re

ACTIONS = {
    "goto": ("value",), "click": ("selector",), "fill": ("selector", "value"), "select": ("selector", "value"), "check": ("selector",),
    "press": ("selector", "value"), "wait": ("value",), "expect_visible": ("selector",), "expect_text": ("value",),
    "expect_url": ("value",), "expect_value": ("selector", "value"), "expect_absent": ("selector",), "screenshot": (),
}
ACTION_LABELS = {
    "goto": "Aller à (URL ou chemin)", "click": "Cliquer", "fill": "Saisir", "select": "Choisir une option", "check": "Cocher",
    "press": "Touche (Enter…)", "wait": "Attendre (ms)", "expect_visible": "Vérifier : visible", "expect_text": "Vérifier : texte présent (dans le sélecteur, sinon la page)",
    "expect_url": "Vérifier : l'URL contient", "expect_value": "Vérifier : valeur du champ", "expect_absent": "Vérifier : absent", "screenshot": "Capture d'écran",
}

def normalize_steps(steps):
    """Liste d'étapes nettoyée ou ValueError explicite (numéro d'étape, champ manquant)."""
    out = []
    if not isinstance(steps, list): raise ValueError("steps doit être une liste")
    for i, s in enumerate(steps, 1):
        if not isinstance(s, dict): raise ValueError(f"étape {i} : objet attendu")
        a = (s.get("action") or "").strip()
        if a not in ACTIONS: raise ValueError(f"étape {i} : action inconnue « {a} »")
        st = dict(action=a, selector=(s.get("selector") or "").strip(), value=("" if s.get("value") is None else str(s.get("value"))).strip(), note=(s.get("note") or "").strip())
        for f in ACTIONS[a]:
            if f == "selector" and not st["selector"]: raise ValueError(f"étape {i} ({a}) : sélecteur manquant")
            if f == "value" and not st["value"] and a != "expect_text": raise ValueError(f"étape {i} ({a}) : valeur manquante")
        if a == "wait" and not re.fullmatch(r"\d+", st["value"]): raise ValueError(f"étape {i} : durée en millisecondes attendue")
        out.append(st)
    if not out: raise ValueError("un scénario a au moins une étape")
    return out

def summarize(results):
    """[{index, action, ok, error, duration_ms}] -> {status: ok|ko, passed, failed, first_failure}."""
    passed = sum(1 for r in results if r.get("ok")); failed = [r for r in results if not r.get("ok")]
    return dict(status="ok" if not failed else "ko", passed=passed, failed=len(failed), total=len(results),
                first_failure=(failed[0].get("error") or "") if failed else "", failed_index=failed[0]["index"] if failed else None)

def ticket_text(kind, site, scenario, run, steps):
    """Sujet + description du ticket : scénario rejoué pas à pas, étape en échec, URL ; devient le test traversant de non-régression."""
    s = summarize(run.get("results") or [])
    subject = ("Incident QA : " if kind == "incident" else "Évolution QA : ") + f"{site['name']} — {scenario['name']}"
    L = [f"Site : {site['name']} ({site['base_url']})", f"Scénario QA n°{scenario['id']} « {scenario['name']} » — exécution n°{run.get('id', '?')} du {run.get('started_at', '')}",
         f"Résultat : {s['passed']}/{s['total']} étapes réussies" + (f" ; échec à l'étape {s['failed_index']} : {s['first_failure']}" if s["failed"] else ""), "", "Étapes :"]
    for i, st in enumerate(steps, 1):
        r = next((x for x in (run.get("results") or []) if x.get("index") == i), None)
        mark = "✔" if r and r.get("ok") else ("✘" if r else "·")
        L.append(f"  {mark} {i}. {ACTION_LABELS.get(st['action'], st['action'])}" + (f" {st['selector']}" if st["selector"] else "") + (f" = « {st['value']} »" if st["value"] else "") + (f" — {st['note']}" if st.get("note") else ""))
    if kind == "evolution": L += ["", "Évolution demandée (à préciser) : comportement attendu à la place du comportement observé ci-dessus."]
    L += ["", "Ce scénario est conservé comme test traversant de non-régression (module QA du hub) : il sera rejoué à chaque campagne."]
    return subject, "\n".join(L)
