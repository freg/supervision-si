"""Traduction entre une « demande OPTLINE » (dict plat, voir
optline_format.py) et un ticket ProjeQtOr (champs API, voir
model/TicketMain.php). Livraison #484.

Correspondance :

    Sujet              -> name
    Commentaire        -> description (+ ligne récapitulative [OPTLINE])
    Demandeur          -> idContact     (résolu par nom, classe Contact)
    Niveau de priorité -> idUrgency     (résolu par nom, classe Urgency)
    Catégorie          -> idTicketType  (résolu par nom, classe TicketType)
    Date de demande    -> creationDateTime
    Date de clôture    -> done=1 + doneDateTime
    Id (colonne A)     -> externalReference (« OPTLINE:<id> »)

Principe « RIEN DE PERDU » : priorité, catégorie, durée et
accomplissement sont TOUJOURS inscrits en clair dans la description
(ligne « [OPTLINE] ... »), même quand la résolution par nom réussit —
ProjeQtOr n'a pas de colonne native pour la durée en jours ni
l'accomplissement du tableau, et une valeur non résolue (nom absent
des référentiels) ne doit jamais disparaître. L'export relit cette
ligne pour remplir les colonnes que ProjeQtOr ne stocke pas.

Les noms non résolus sont RETOURNÉS (jamais silencieux) : l'appelant
les affiche dans le compte rendu d'import pour que la personne crée
les entrées manquantes dans ProjeQtOr ou corrige le fichier.
"""
import re
from datetime import datetime

from optline_format import (
    COL_CATEGORY, COL_CLOSED, COL_COMMENT, COL_DATE, COL_DURATION,
    COL_ID, COL_PRIORITY, COL_PROGRESS, COL_REQUESTER, COL_SUBJECT,
    normalize_key,
)

RECAP_PREFIX = "[OPTLINE]"
RECAP_RE = re.compile(
    r"^\[OPTLINE\] Demandeur\s*:\s*(?P<demandeur>.*?)\s*\| "
    r"Priorité\s*:\s*(?P<priorite>.*?)\s*\| "
    r"Catégorie\s*:\s*(?P<categorie>.*?)\s*\| "
    r"Durée\s*:\s*(?P<duree>.*?)\s*\| "
    r"Accomplissement\s*:\s*(?P<avancement>.*?)\s*$",
    re.MULTILINE,
)


def build_recap(demand):
    """Ligne récapitulative stable — lue par l'export (RECAP_RE)."""
    duration = demand.get(COL_DURATION)
    progress = demand.get(COL_PROGRESS)
    return (
        f"{RECAP_PREFIX} Demandeur: {demand.get(COL_REQUESTER) or '-'} | "
        f"Priorité: {demand.get(COL_PRIORITY) or '-'} | "
        f"Catégorie: {demand.get(COL_CATEGORY) or '-'} | "
        f"Durée: {duration if duration is not None else '-'} j | "
        f"Accomplissement: {progress if progress is not None else '-'}"
    )


def parse_recap(description):
    """Retrouve les valeurs OPTLINE dans une description (ou None)."""
    if not description:
        return None
    match = RECAP_RE.search(description)
    return match.groupdict() if match else None


def _resolve(name, referentiel):
    """nom -> id ProjeQtOr (insensible casse/accents/espaces), ou None."""
    if not name:
        return None
    return referentiel.get(normalize_key(name))


def demand_to_ticket(demand, referentiels):
    """(demande, référentiels) -> (champs ProjeQtOr, noms non résolus).

    `referentiels` : {"contacts": {nom_norm: id}, "urgencies": {...},
    "types": {...}} — construits une fois par requête dans app.py.
    """
    unresolved = []
    fields = {"name": demand[COL_SUBJECT]}

    comment = (demand.get(COL_COMMENT) or "").strip()
    fields["description"] = (comment + "\n" if comment else "") + build_recap(demand)

    contact_id = _resolve(demand.get(COL_REQUESTER), referentiels["contacts"])
    if demand.get(COL_REQUESTER) and contact_id is None:
        unresolved.append(f"demandeur « {demand[COL_REQUESTER]} »")
    if contact_id is not None:
        fields["idContact"] = contact_id

    urgency_id = _resolve(demand.get(COL_PRIORITY), referentiels["urgencies"])
    if demand.get(COL_PRIORITY) and urgency_id is None:
        unresolved.append(f"priorité « {demand[COL_PRIORITY]} »")
    if urgency_id is not None:
        fields["idUrgency"] = urgency_id

    type_id = _resolve(demand.get(COL_CATEGORY), referentiels["types"])
    if demand.get(COL_CATEGORY) and type_id is None:
        unresolved.append(f"catégorie « {demand[COL_CATEGORY]} »")
    if type_id is not None:
        fields["idTicketType"] = type_id

    if demand.get(COL_DATE):
        fields["creationDateTime"] = demand[COL_DATE].strftime("%Y-%m-%d %H:%M:%S")
    if demand.get(COL_CLOSED):
        fields["done"] = 1
        fields["doneDateTime"] = demand[COL_CLOSED].strftime("%Y-%m-%d %H:%M:%S")
    if demand.get(COL_ID) not in (None, ""):
        fields["externalReference"] = f"OPTLINE:{demand[COL_ID]}"

    return fields, unresolved


def _parse_datetime(value):
    """'YYYY-MM-DD HH:MM:SS' (ou date seule) -> datetime, jamais d'exception."""
    if not value:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(str(value).strip()[:19], fmt)
        except ValueError:
            continue
    return None


def _name_of(referentiel_inverse, raw_id):
    if raw_id in (None, "", 0, "0"):
        return ""
    return referentiel_inverse.get(int(raw_id), "")


def ticket_to_demand(ticket, referentiels_inverses):
    """Ticket ProjeQtOr (dict API) -> demande OPTLINE pour l'export.

    `referentiels_inverses` : {"contacts": {id: nom}, ...}. Les
    colonnes sans équivalent ProjeQtOr (durée, accomplissement) sont
    relues depuis la ligne [OPTLINE] de la description quand elle
    existe (demandes entrées par le pont), sinon laissées vides.
    """
    description = ticket.get("description") or ""
    recap = parse_recap(description)
    # La description exportée est le commentaire SANS la ligne récap.
    comment = RECAP_RE.sub("", description).strip()

    duration = None
    progress = None
    if recap:
        try:
            duration = float(recap["duree"].replace("j", "").strip())
            duration = int(duration) if duration == int(duration) else duration
        except (ValueError, TypeError):
            duration = None
        try:
            progress = float(recap["avancement"])
        except (ValueError, TypeError):
            progress = None

    external = ticket.get("externalReference") or ""
    ref_id = external.split(":", 1)[1] if external.startswith("OPTLINE:") else None

    return {
        COL_ID: ref_id if ref_id is not None else ticket.get("id"),
        COL_DATE: _parse_datetime(ticket.get("creationDateTime")),
        COL_REQUESTER: _name_of(referentiels_inverses["contacts"], ticket.get("idContact"))
                       or (recap["demandeur"] if recap and recap["demandeur"] != "-" else ""),
        COL_SUBJECT: ticket.get("name") or "(sans sujet)",
        COL_PRIORITY: _name_of(referentiels_inverses["urgencies"], ticket.get("idUrgency"))
                      or (recap["priorite"] if recap and recap["priorite"] != "-" else ""),
        COL_CATEGORY: _name_of(referentiels_inverses["types"], ticket.get("idTicketType"))
                      or (recap["categorie"] if recap and recap["categorie"] != "-" else ""),
        COL_DURATION: duration,
        COL_COMMENT: comment,
        COL_PROGRESS: progress,
        COL_CLOSED: _parse_datetime(ticket.get("doneDateTime")),
    }
