# -*- coding: utf-8 -*-
"""Notifications (livraison #590, backlog item 92) -- logique PURE :

- catalogue d'actions « module.action » et groupe PAR DÉFAUT d'un module ;
- résolution des destinataires : action → groupes / méta-groupes → emails,
  méta-groupes développés récursivement (cycles tolérés), liste noire
  (emails, actions, consommateurs) appliquée ;
- gestionnaire d'envoi DÉTACHÉ : regroupement des messages identiques dans
  une fenêtre, détection d'emballement (rafale par action), backoff après
  échec SMTP, disjoncteur après échecs consécutifs, débit maximal.
Rien ici ne touche SQLite ni SMTP : testé à sec."""
import re

ACTION_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*(\.[a-z0-9][a-z0-9_-]*)+$")
EMAIL_RE = re.compile(r"^[^\s@;,<>\"]+@[^\s@;,<>\"]+\.[^\s@;,<>\"]+$")
SEVERITIES = ("info", "warning", "critical")


def module_of(action):
    return action.split(".", 1)[0]


def default_group_id(action):
    return "auto:" + module_of(action)


def valid_action(action):
    return bool(action and ACTION_RE.match(action) and len(action) <= 80)


def valid_email(email):
    return bool(email and EMAIL_RE.match(email) and len(email) <= 254)


def expand_group(group_id, groups, _seen=None):
    """-> ensemble d'emails du groupe (méta-groupes développés, cycles ignorés)."""
    seen = _seen if _seen is not None else set()
    if group_id in seen:
        return set()
    seen.add(group_id)
    g = groups.get(group_id)
    if not g:
        return set()
    out = set(e.strip().lower() for e in (g.get("emails") or []) if e and e.strip())
    for m in g.get("members") or []:
        out |= expand_group(m, groups, seen)
    return out


def resolve(action, assignments, groups, blacklist=None, consumer=None):
    """-> (emails triés, raison si vide). `assignments` : {action: [group_id]}
    (une entrée « module.* » s'applique à tout le module) ; `blacklist` :
    {"email": set, "action": set, "consumer": set}."""
    bl = blacklist or {}
    if action in (bl.get("action") or set()) or module_of(action) + ".*" in (bl.get("action") or set()):
        return [], "action en liste noire"
    if consumer and consumer in (bl.get("consumer") or set()):
        return [], "consommateur en liste noire"
    gids = list(assignments.get(action) or []) + list(assignments.get(module_of(action) + ".*") or [])
    if not gids:
        gids = [default_group_id(action)]
    emails = set()
    for gid in gids:
        emails |= expand_group(gid, groups)
    emails = {e for e in emails if valid_email(e)}
    blocked = {e.lower() for e in (bl.get("email") or set())}
    kept = sorted(emails - blocked)
    if not kept:
        return [], "aucun destinataire (groupe sans adresse ou tout en liste noire)" if emails or gids else "aucun groupe affecté"
    return kept, None


# -- gestionnaire d'envoi -------------------------------------------------------
def coalesce_key(action, subject, recipients):
    return "%s|%s|%s" % (action, (subject or "").strip().lower()[:120], ",".join(recipients))


def backoff_seconds(attempts, base=60, cap=3600):
    """1 → 60 s, 2 → 120, 3 → 240 … plafonné."""
    return min(cap, base * (2 ** max(0, attempts - 1)))


def burst_state(count_recent, threshold):
    """Emballement : au-delà de `threshold` messages d'une même action dans la
    fenêtre, les suivants sont RETENUS et un résumé unique part."""
    return "hold" if threshold and count_recent >= threshold else "send"


def breaker_open(consecutive_failures, threshold, opened_at, now, cooldown):
    """Disjoncteur SMTP : ouvert après `threshold` échecs consécutifs, se
    referme après `cooldown` secondes (une tentative de reprise)."""
    if consecutive_failures < threshold:
        return False
    return opened_at is not None and now - opened_at < cooldown


def allowance(sent_last_minute, max_per_minute):
    """Nombre de messages encore permis dans la minute (0 = attendre)."""
    if not max_per_minute:
        return 10 ** 6
    return max(0, max_per_minute - sent_last_minute)


def summary_body(action, count, first_subject, window_s):
    return ("%d notifications « %s » en %d s -- regroupées pour éviter l'emballement.\n"
            "Première : %s\nLes suivantes sont retenues dans la file (tuile Notifications) jusqu'à la fin de la rafale."
            % (count, action, window_s, first_subject or "-"))


def render_subject(prefix, severity, subject):
    tag = {"critical": "[CRITIQUE] ", "warning": "[ALERTE] "}.get(severity or "", "")
    return "%s%s%s" % ((prefix + " ") if prefix else "", tag, (subject or "").strip()[:180])


# -- #853 : pauses planifiées (fermeture de site, travaux, coupure électrique) ---------------------------------------
def _globs(v):
    return [x.strip() for x in str(v or "").replace(";", ",").split(",") if x.strip()]


def pause_applicable(pauses, action, consumer, context, now):
    """Première pause active qui couvre cette notification, ou None. Pause : {debut, fin, actions, consommateurs,
    contexte: {cle: "motif1,motif2"}} ; motifs de type fnmatch (« si-agent.* », « numeria-* ») ; vide = tout. Un champ
    de contexte absent de la notification n'exclut pas si la pause nomme explicitement ses consommateurs."""
    import fnmatch
    ctx = context or {}
    for p in pauses or []:
        if not (p.get("debut") or 0) <= now < (p.get("fin") or 0):
            continue
        if _globs(p.get("actions")) and not any(fnmatch.fnmatchcase(action or "", g) for g in _globs(p.get("actions"))):
            continue
        if _globs(p.get("consommateurs")) and not any(fnmatch.fnmatchcase(consumer or "", g) for g in _globs(p.get("consommateurs"))):
            continue
        ok = True
        cons_explicite = bool(_globs(p.get("consommateurs")))
        for cle, motifs in (p.get("contexte") or {}).items():
            gl = _globs(motifs)
            if not gl:
                continue
            if cle not in ctx and cons_explicite:
                continue      # producteur nommé dans la pause qui ne précise pas ce champ (ex. nebula, propre au site) : couvert
            if not any(fnmatch.fnmatchcase(str(ctx.get(cle) or ""), g) for g in gl):
                ok = False
                break
        if ok:
            return p
    return None


def valider_pause(b, now):
    """-> (pause propre, None) ou (None, erreur)."""
    try:
        debut, fin = float(b.get("debut")), float(b.get("fin"))
    except (TypeError, ValueError):
        return None, "début et fin requis (horodatages)"
    if fin <= debut:
        return None, "la fin doit suivre le début"
    if fin - debut > 62 * 86400:
        return None, "pause de plus de 2 mois refusée"
    if fin <= now:
        return None, "pause déjà terminée"
    motif = str(b.get("motif") or "").strip()[:200]
    if not motif:
        return None, "motif requis"
    ctx = b.get("contexte") if isinstance(b.get("contexte"), dict) else {}
    return {"debut": debut, "fin": fin, "motif": motif, "site": str(b.get("site") or "")[:60], "type": str(b.get("type") or "maintenance")[:40],
            "actions": ",".join(_globs(b.get("actions")))[:500], "consommateurs": ",".join(_globs(b.get("consommateurs")))[:300],
            "contexte": {str(k)[:40]: ",".join(_globs(v))[:500] for k, v in ctx.items() if _globs(v)}}, None
