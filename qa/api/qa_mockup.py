"""Maquettes en étapes (livraison #728, item 116 tranche 4) -- logique pure, testée sans navigateur.

Une maquette part d'une exécution d'un scénario (la « situation actuelle ») et propose des variantes : chacune est une
feuille CSS injectée dans le navigateur de test seulement (copie isolée de la page, jamais la production). Les
variantes viennent des constats de conformité (#721) -- propositions calculées, sans modèle de vision -- ou sont
écrites à la main. La présentation suit des étapes : avant / proposition / variantes / règles respectées / décision.
"""
import re
from qa_design import parse_rgb, contrast

SAFE_SEL = re.compile(r"^[a-z0-9]+([#.][A-Za-z0-9_-]+)*$")   # forme produite par AUDIT_JS.name()
MAX_CSS = 20000


def _hex(rgb):
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(round(c)))) for c in rgb[:3])


def fix_color(fg, bg, need):
    """Couleur de texte la plus proche de fg (vers le noir ou le blanc) atteignant le contraste `need` sur bg."""
    f, b = parse_rgb(fg), parse_rgb(bg)
    if not f or not b:
        return None
    best = None
    for target in ((0, 0, 0), (255, 255, 255)):
        for k in range(1, 21):
            t = k / 20.0
            c = tuple(f[i] + (target[i] - f[i]) * t for i in range(3))
            r = contrast("rgb(%d, %d, %d)" % tuple(int(round(x)) for x in c), bg)
            if r is not None and r >= need:
                if best is None or t < best[0]:
                    best = (t, _hex(c))
                break
    return best[1] if best else None


def propose(findings, contrast_target=None):
    """Constats -> (css, notes). contrast_target force un seuil (7.0 = AAA) ; règles sans correctif CSS sûr -> notes."""
    css, notes, seen = [], [], set()
    for f in findings or []:
        rule = f.get("rule")
        if rule == "contraste" and f.get("el") and SAFE_SEL.match(f["el"]):
            need = max(contrast_target or 0, (f.get("need") or 4.5) + 0.2)
            col = fix_color(f.get("fg"), f.get("bg"), need)
            key = ("c", f["el"])
            if col and key not in seen:
                seen.add(key)
                css.append("%s { color: %s !important; }   /* contraste %s -> %.1f:1, à reporter dans une variable de theme.css */" % (f["el"], col, f.get("fg"), need))
        elif rule == "entete-fixe" and f.get("el") and SAFE_SEL.match(f["el"]) and ("t", f["el"]) not in seen:
            seen.add(("t", f["el"]))
            css.append("%s thead th { position: sticky; top: 0; z-index: 1; background: var(--panel, var(--bg)); }" % f["el"])
        elif rule == "cible-petite":
            els = [e for e in f.get("els") or [] if SAFE_SEL.match(e) and ("s", e) not in seen]
            seen.update(("s", e) for e in els)
            if els:
                css.append("%s { min-width: 24px; min-height: 24px; }" % ", ".join(els))
        elif rule and contrast_target is None:
            notes.append("%s : %s (pas de correctif CSS automatique)" % (rule, f.get("message", "")))
    return "\n".join(css), sorted(set(notes))


def auto_variants(findings):
    """Variantes calculées : conformité (seuils WCAG AA) puis contraste renforcé (AAA, 7:1)."""
    out = []
    css, notes = propose(findings)
    if css:
        out.append(dict(name="Corrections de conformité", css=css, origin="auto", notes=notes))
    css2, _ = propose([f for f in findings or [] if f.get("rule") == "contraste"], contrast_target=7.0)
    if css2 and css2 != css:
        out.append(dict(name="Contraste renforcé (AAA)", css=css2, origin="auto", notes=[]))
    return out


def clean_variants(variants):
    """Validation des variantes saisies : nom, CSS borné, pas de balise ni d'import externe."""
    out = []
    for i, v in enumerate(variants or [], 1):
        name = str((v or {}).get("name") or "").strip()[:80] or "Variante %d" % i
        css = str((v or {}).get("css") or "")
        if len(css) > MAX_CSS:
            raise ValueError("variante %d : CSS trop long (%d caractères, max %d)" % (i, len(css), MAX_CSS))
        if re.search(r"</?\s*style|<script|@import|url\(\s*['\"]?\s*(https?:|//)", css, re.I):
            raise ValueError("variante %d : balises, @import et ressources externes interdits" % i)
        out.append(dict(name=name, css=css, origin=v.get("origin") if v.get("origin") in ("auto", "manuel") else "manuel",
                        notes=[str(n)[:300] for n in (v.get("notes") or [])][:20]))
    if not out:
        raise ValueError("Ajoutez au moins une variante")
    return out


def audit_stats(results):
    """Résultats d'une exécution -> {score moyen, constats par règle, captures (index, shot)}."""
    audits = [r for r in results or [] if r.get("action") == "audit" and isinstance(r.get("findings"), list)]
    rules = {}
    for r in audits:
        for f in r["findings"]:
            rules[f["rule"]] = rules.get(f["rule"], 0) + 1
    score = round(sum(r.get("score") or 0 for r in audits) / len(audits)) if audits else None
    shots = [dict(index=r["index"], action=r["action"], shot=r["shot"]) for r in results or [] if r.get("shot") and not r.get("login")]
    return dict(score=score, rules=rules, shots=shots, ok=all(r.get("ok") for r in results or []))


def presentation(mockup, base, variant_runs, diffs=None):
    """Étapes de présentation. base / variant_runs : exécutions (dict avec id, results, status) ; variant_runs[i] peut
    manquer (variante pas encore rendue) ; diffs[i] : {significant, steps} de la comparaison variante / situation."""
    diffs = diffs or {}
    b = audit_stats(base["results"]) if base else dict(score=None, rules={}, shots=[], ok=False)
    slides = [dict(kind="avant", title="Situation actuelle", run_id=base["id"] if base else None, score=b["score"],
                   rules=b["rules"], shots=b["shots"])]
    stats = []
    for i, v in enumerate(mockup["variants"]):
        r = variant_runs.get(i)
        s = audit_stats(r["results"]) if r else None
        stats.append(s)
        slides.append(dict(kind="proposition" if i == 0 else "variante", variant=i, title=("Proposition : " if i == 0 else "Variante : ") + v["name"],
                           run_id=r["id"] if r else None, rendered=bool(r), status=r["status"] if r else None,
                           score=s["score"] if s else None, delta=(s["score"] - b["score"]) if s and s["score"] is not None and b["score"] is not None else None,
                           shots=s["shots"] if s else [], css=v["css"], notes=v.get("notes") or [], diff=diffs.get(i)))
    rules = sorted(set(b["rules"]) | {k for s in stats if s for k in s["rules"]})
    slides.append(dict(kind="regles", title="Règles respectées", rows=[dict(rule=k, before=b["rules"].get(k, 0),
                       after=[(s["rules"].get(k, 0) if s else None) for s in stats]) for k in rules],
                       variants=[v["name"] for v in mockup["variants"]]))
    slides.append(dict(kind="decision", title="Décision", status=mockup.get("status"), chosen=mockup.get("chosen"),
                       ticket_id=mockup.get("ticket_id"), comment=mockup.get("decision_comment") or "",
                       integrated_run_id=mockup.get("integrated_run_id"), integrated_at=mockup.get("integrated_at")))
    return slides


def ticket_text(mockup, scenario, site, variant, slides):
    """Ticket évolution : variante retenue, gain de note, correctif CSS à intégrer (dans theme.css / le composant)."""
    s = next((x for x in slides if x.get("variant") == mockup["variants"].index(variant)), {})
    subject = "[QA maquette] %s — %s" % (scenario["name"], variant["name"])
    L = ["Maquette « %s » validée (module QA du hub), site %s, scénario « %s »." % (mockup["name"], site["name"], scenario["name"]), ""]
    if s.get("score") is not None:
        L.append("Note de conformité : %s/100%s." % (s["score"], (" (%+d par rapport à la situation actuelle)" % s["delta"]) if s.get("delta") is not None else ""))
    if mockup.get("decision_comment"):
        L += ["", "Commentaire : " + mockup["decision_comment"]]
    L += ["", "Correctif CSS proposé (injecté dans une copie isolée pour la maquette ; à intégrer via les variables de shared/theme.css) :", "", variant["css"] or "(aucun)"]
    if variant.get("notes"):
        L += ["", "Points sans correctif automatique :"] + ["- " + n for n in variant["notes"]]
    L += ["", "Exécutions : situation n°%s, variante n°%s." % (slides[0].get("run_id"), s.get("run_id")),
          "La variante devient la cible du scénario (non-régression) : chaque campagne compare le développement à la maquette ;",
          "la première exécution conforme marque la maquette « intégrée »."]
    return subject, "\n".join(L)
