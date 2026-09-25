# -*- coding: utf-8 -*-
"""Filtres d'alertes des agents (livraison #607) -- logique PURE, testée.

Demandé : « les alertes agents sont inutiles pour une partie des cas ; une
case à cocher sur chaque agent pour activer / désactiver un filtrage ; des
groupes de filtres ; classer / catégoriser les alertes ; paramétrage fin
par l'administrateur ; besoin immédiat : filtrer les postes de travail
éteints hors des heures de travail (8 h 30 – 18 h) ».

Modèle : chaque événement a une CATÉGORIE (déduite de son `kind`) ; un
GROUPE DE FILTRES est une liste de règles {catégories et/ou genres,
plage horaire ouvrée facultative, action} ; un agent a « filtrage activé »
+ un groupe. Une règle qui s'applique rend l'événement `muted` : conservé
dans le journal (visible sur demande), mais absent du bandeau, de la
synthèse et des notifications."""
import datetime as _dt
import re

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover
    ZoneInfo = None

CATEGORIES = {
    "availability": "Disponibilité (en ligne / hors ligne)",
    "security": "Sécurité (authentification, blocage, secrets)",
    "plugins": "Sondes (catalogue, affectation, blocage)",
    "updates": "Mises à jour de l'agent",
    "commands": "Commandes",
    "fleet": "Flotte (enrôlement, activation, suppression)",
    "capture": "Captures et relais réseau",
    "risks": "Risques internes de l'hôte",
    "applications": "Applications surveillées (chien de garde)",
    "other": "Autres",
}
KIND_CATEGORY = {
    "agent-offline": "availability", "agent-online": "availability",
    "auth-refused": "security", "agent-blocked": "security", "agent-unblocked": "security", "fleet-blocked": "security", "fleet-unblocked": "security", "secret-rotated": "security",
    "plugin-catalogued": "plugins", "plugin-uncatalogued": "plugins", "plugin-assigned": "plugins", "plugin-unassigned": "plugins", "plugin-blocked": "plugins", "plugin-unblocked": "plugins",
    "update-settings": "updates", "update-scheduled": "updates", "agent-updated": "updates", "agent-update-failed": "updates",
    "command-acked": "commands", "command-failed": "commands", "command-block": "commands", "command-vm": "commands", "command-software": "commands",
    "agent-enrolled": "fleet", "agent-activated": "fleet", "agent-deactivated": "fleet", "agent-deleted": "fleet",
    "capture-relay-failed": "capture", "notification-test": "other",
    # #613 : alimentation, réveil, lanceurs, chien de garde
    "command-power": "commands", "command-wol": "commands", "command-startup": "commands", "watchdog-config": "commands",
    "app-down": "applications", "app-restarted": "applications", "app-restart-failed": "applications", "app-recovered": "applications", "watchdog-error": "applications",
}
WEEKDAYS = ["lun", "mar", "mer", "jeu", "ven", "sam", "dim"]
DEFAULT_TZ = "Europe/Paris"

DEFAULT_GROUPS = [
    {"id": "postes-travail", "label": "Postes de travail (heures ouvrées)",
     "description": "Un poste éteint le soir ou le week-end n'est pas une panne : les alertes de disponibilité ne comptent qu'en heures ouvrées.",
     "rules": [{"categories": ["availability"], "kinds": [], "when": "outside", "days": [0, 1, 2, 3, 4], "start": "08:30", "end": "18:00", "action": "mute"}]},
    {"id": "silencieux", "label": "Silencieux (tout filtrer)", "description": "Aucune alerte de cet agent (matériel de test, démonstration).",
     "rules": [{"categories": list(CATEGORIES), "kinds": [], "when": "always", "action": "mute"}]},
]


def category_of(kind):
    k = str(kind or "")
    if k in KIND_CATEGORY:
        return KIND_CATEGORY[k]
    if k.startswith(("plugin-", "sonde-")):
        return "plugins"
    if k.startswith("command-"):
        return "commands"
    if k.startswith(("update", "agent-update")):
        return "updates"
    if k in ("smb1_enabled", "rdp_without_nla", "smb_signing_optional", "vnc_open", "netbios_silent") or k.startswith("risk"):
        return "risks"
    return "other"


def _hm(s, default):
    m = re.match(r"^(\d{1,2})[:h](\d{2})$", str(s or "").strip())
    if not m:
        return default
    h, mi = int(m.group(1)), int(m.group(2))
    return (h, mi) if 0 <= h <= 23 and 0 <= mi <= 59 else default


def in_hours(at_iso, rule, tz=DEFAULT_TZ):
    """L'instant `at_iso` (UTC, ISO) tombe-t-il dans la plage ouvrée de la règle (jours + heures, fuseau local) ?"""
    try:
        t = _dt.datetime.strptime(str(at_iso)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=_dt.timezone.utc)
    except ValueError:
        return True
    if ZoneInfo:
        try:
            t = t.astimezone(ZoneInfo(tz or DEFAULT_TZ))
        except Exception:  # noqa: BLE001
            pass
    days = rule.get("days") if isinstance(rule.get("days"), list) else [0, 1, 2, 3, 4]
    if t.weekday() not in days:
        return False
    sh, sm = _hm(rule.get("start"), (8, 30))
    eh, em = _hm(rule.get("end"), (18, 0))
    cur = t.hour * 60 + t.minute
    return sh * 60 + sm <= cur < eh * 60 + em


def rule_matches(event, rule, tz=DEFAULT_TZ):
    cat = category_of(event.get("kind"))
    kinds = [str(k) for k in (rule.get("kinds") or [])]
    cats = [str(c) for c in (rule.get("categories") or [])]
    if event.get("kind") not in kinds and cat not in cats:
        return False
    when = rule.get("when") or "always"
    if when == "always":
        return True
    inside = in_hours(event.get("at"), rule, tz)
    return (not inside) if when == "outside" else inside


def evaluate(event, groups, agent, tz=DEFAULT_TZ):
    """-> (muted, reason). `agent` : {filter_enabled, filter_group} ; `groups` : liste des groupes."""
    if not agent or not agent.get("filter_enabled"):
        return False, ""
    gid = agent.get("filter_group") or ""
    group = next((g for g in groups or [] if g.get("id") == gid), None)
    if not group:
        return False, ""
    for i, rule in enumerate(group.get("rules") or []):
        if rule_matches(event, rule, tz):
            if (rule.get("action") or "mute") == "mute":
                label = rule.get("label") or ("%s %s" % ("hors" if rule.get("when") == "outside" else "pendant" if rule.get("when") == "inside" else "toujours", "%s–%s" % (rule.get("start", "08:30"), rule.get("end", "18:00")) if rule.get("when") in ("outside", "inside") else ""))
                return True, "%s / règle %d (%s)" % (group.get("label") or gid, i + 1, label.strip())
    return False, ""


def normalize_groups(raw):
    """Validation d'un paramétrage venu du hub -> liste propre ; erreurs -> ValueError."""
    out, seen = [], set()
    for g in raw if isinstance(raw, list) else []:
        gid = re.sub(r"[^a-z0-9_-]+", "-", str(g.get("id") or g.get("label") or "").strip().lower())[:40].strip("-")
        if not gid or gid in seen:
            raise ValueError("identifiant de groupe manquant ou en double : %r" % gid)
        seen.add(gid)
        rules = []
        for r in g.get("rules") or []:
            cats = [c for c in (r.get("categories") or []) if c in CATEGORIES]
            kinds = [str(k).strip() for k in (r.get("kinds") or []) if str(k).strip()]
            if not cats and not kinds:
                raise ValueError("règle sans catégorie ni genre dans le groupe %s" % gid)
            when = r.get("when") if r.get("when") in ("always", "outside", "inside") else "always"
            days = sorted({int(d) for d in (r.get("days") or []) if str(d).lstrip("-").isdigit() and 0 <= int(d) <= 6}) if when != "always" else []
            rules.append({"categories": cats, "kinds": kinds, "when": when, "days": days if days else ([0, 1, 2, 3, 4] if when != "always" else []),
                          "start": "%02d:%02d" % _hm(r.get("start"), (8, 30)), "end": "%02d:%02d" % _hm(r.get("end"), (18, 0)),
                          "action": "mute" if (r.get("action") or "mute") == "mute" else "keep", "label": str(r.get("label") or "")[:80]})
        out.append({"id": gid, "label": str(g.get("label") or gid)[:80], "description": str(g.get("description") or "")[:300], "rules": rules})
    return out
