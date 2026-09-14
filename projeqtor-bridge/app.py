"""projeqtor-bridge — pont entre le format « suivi des demandes » imposé, ProjeQtOr
et la gestion de tickets du hub (livraison #484). Voir
projeqtor-bridge/README.md pour le raisonnement complet.

Routes (toutes sous le préfixe /demande/, routé par tls-proxy) :

    GET  /demande/               formulaire PUBLIC de dépôt (LAN, sans
                                 authentification — confirmé
                                 explicitement par la personne)
    GET  /demande/referentiels   listes demandeurs/catégories/priorités
                                 (lues de ProjeQtOr, source de vérité)
    POST /demande/demandes       dépôt d'une demande -> ticket ProjeQtOr
    GET  /demande/admin          page import/export (posture LAN, même
                                 confiance que le formulaire)
    POST /demande/import         fichier xlsx « suivi » -> tickets ProjeQtOr
    GET  /demande/export         tickets ProjeQtOr -> xlsx « suivi »
    GET  /demande/sync/status    état de la synchronisation vers le hub
    POST /demande/sync/now       tour de synchronisation immédiat
    GET  /demande/health         vivant (pas de dépendance à ProjeQtOr)
    GET  /demande/version        hash de contenu (shared/version_endpoint)

La version en entête de chaque réponse n'est PAS celle du hub : voir
/demande/version pour le hash exact déployé.
"""
import io
import logging
import os
from datetime import datetime

from flask import Flask, jsonify, request, send_file, send_from_directory

import requests

from mapping import LABEL, build_recap, demand_to_ticket, ticket_to_demand
from suivi_format import (
    COL_CATEGORY, COL_CLOSED, COL_COMMENT, COL_DATE, COL_DURATION, COL_ID,
    COL_PRIORITY, COL_PROGRESS, COL_REQUESTER, COL_SUBJECT, build_workbook,
    normalize_key, parse_workbook,
)
from projeqtor_client import ProjeqtorApiError, ProjeqtorClient
import sync

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("projeqtor-bridge")

STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")

PROJEQTOR_API_URL = os.environ.get("PROJEQTOR_API_URL", "http://projeqtor-app/projeqtor/api")
PROJEQTOR_API_USER = os.environ.get("PROJEQTOR_API_USER", "")
PROJEQTOR_API_PASSWORD = os.environ.get("PROJEQTOR_API_PASSWORD", "")

app = Flask(__name__)

try:
    from version_endpoint import register_version_route
    register_version_route(app, "projeqtor-bridge")
except ImportError:
    pass  # tests qui importent ce module directement, sans le build


def get_client():
    """Client construit à CHAQUE requête (léger) — jamais de session
    partagée entre threads Flask, et une config .env fraîchement lue au
    démarrage n'a pas besoin de cache."""
    return ProjeqtorClient(PROJEQTOR_API_URL, PROJEQTOR_API_USER, PROJEQTOR_API_PASSWORD)


def load_referentiels(client):
    """Lit les trois référentiels ProjeQtOr. Retourne
    (par_nom, par_id) — dicts {nom_normalisé: id} et {id: nom}.
    Une classe illisible ne fait jamais échouer les deux autres."""
    by_name, by_id = {"contacts": {}, "urgencies": {}, "types": {}}, {"contacts": {}, "urgencies": {}, "types": {}}
    classes = {"contacts": "Contact", "urgencies": "Urgency", "types": "TicketType"}
    for key, cls in classes.items():
        try:
            items = client.get_all(cls)
            if isinstance(items, dict):
                items = items.get("items") or items.get(cls.lower()) or []
            for item in items:
                name = item.get("name")
                if name and item.get("id") is not None:
                    by_name[key][normalize_key(name)] = item["id"]
                    by_id[key][int(item["id"])] = name
        except ProjeqtorApiError as exc:
            log.warning("référentiel %s illisible : %s", cls, exc)
    return by_name, by_id


# ---------------------------------------------------------------- pages

@app.route("/demande/", methods=["GET"])
def form_page():
    return send_from_directory(STATIC_DIR, "form.html")


@app.route("/demande/admin", methods=["GET"])
def admin_page():
    return send_from_directory(STATIC_DIR, "admin.html")


@app.route("/demande/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "projeqtor-bridge"}), 200


# ---------------------------------------------------------- référentiels

@app.route("/demande/referentiels", methods=["GET"])
def referentiels():
    try:
        _, by_id = load_referentiels(get_client())
    except ProjeqtorApiError as exc:
        return jsonify({"error": str(exc)}), 502
    # Noms d'origine (jamais les clés normalisées) pour le formulaire
    # public — la source de vérité est ProjeQtOr, jamais un fichier.
    return jsonify({
        "demandeurs": sorted(by_id["contacts"].values()),
        "priorites": sorted(by_id["urgencies"].values()),
        "categories": sorted(by_id["types"].values()),
    }), 200


# ------------------------------------------------------------ dépôt public

@app.route("/demande/demandes", methods=["POST"])
def create_demand():
    body = request.get_json(silent=True) or request.form.to_dict()
    subject = (body.get("sujet") or "").strip()
    if not subject:
        return jsonify({"error": "le sujet est obligatoire"}), 400
    requester = (body.get("demandeur") or "").strip()
    if not requester:
        return jsonify({"error": "le demandeur est obligatoire"}), 400

    duration = body.get("duree_j")
    try:
        duration = float(duration) if duration not in (None, "") else None
        if duration is not None and duration < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "la durée doit être un nombre positif de jours"}), 400

    demand = {
        COL_SUBJECT: subject,
        COL_REQUESTER: requester,
        COL_PRIORITY: (body.get("priorite") or "").strip(),
        COL_CATEGORY: (body.get("categorie") or "").strip(),
        COL_DURATION: duration,
        COL_COMMENT: (body.get("commentaire") or "").strip(),
    }

    client = get_client()
    by_name, _ = load_referentiels(client)
    fields, unresolved = demand_to_ticket(demand, by_name)
    try:
        result = client.create("Ticket", fields)
    except ProjeqtorApiError as exc:
        return jsonify({"error": f"création refusée par ProjeQtOr : {exc}"}), 502

    return jsonify({
        "status": "ok",
        "projeqtor": result,
        "non_resolus": unresolved,
        "message": "demande enregistrée — elle sera prise en charge par le service informatique",
    }), 201


# ------------------------------------------------------------ import xlsx

IMPORT_TARGETS = ("tickets", "projeqtor", "both")


def _hub_source_name(demand, index, filename):
    """Clé de déduplication côté tickets-api (source_type + source_nom) :
    l'Id du tableau s'il existe (stable d'un import à l'autre), sinon
    une empreinte de (date, demandeur, sujet) — réimporter le même
    fichier ne crée jamais de doublon, tickets-api répond 409."""
    ident = demand.get(COL_ID)
    if ident not in (None, ""):
        return f"{LABEL}:{ident}"
    import hashlib
    date = demand.get(COL_DATE)
    raw = "|".join([date.strftime("%Y-%m-%d") if date else "", demand.get(COL_REQUESTER) or "", demand.get(COL_SUBJECT) or ""])
    return f"{LABEL}:{hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]}"


def _hub_description(demand, filename):
    parts = []
    if demand.get(COL_COMMENT):
        parts.append(demand[COL_COMMENT])
    parts.append(build_recap(demand))
    date = demand.get(COL_DATE)
    meta = f"Importé du tableau « {filename} »" + (f", demande du {date.strftime('%d/%m/%Y')}" if date else "")
    if demand.get(COL_CLOSED):
        meta += f", clôturée le {demand[COL_CLOSED].strftime('%d/%m/%Y')}"
    parts.append(meta)
    return "\n\n".join(parts)


def push_hub_ticket(demand, index, filename):
    """Une demande du tableau -> un ticket hub À VALIDER (même file que
    la synchronisation ProjeQtOr et les imports ICS). Retourne created /
    known / retry / disabled."""
    if not sync.TICKETS_API:
        return "disabled"
    try:
        resp = requests.post(
            f"{sync.TICKETS_API}/tickets/import-external",
            json={"subject": demand[COL_SUBJECT], "description": _hub_description(demand, filename),
                  "source_type": "tableau", "source_nom": _hub_source_name(demand, index, filename)},
            timeout=15,
        )
    except requests.RequestException as exc:
        log.warning("tickets-api injoignable pour l'import du tableau : %s", exc)
        return "retry"
    if resp.status_code == 201:
        return "created"
    if resp.status_code == 409:
        return "known"
    log.warning("tickets-api a refusé la demande n°%s : %s %s", index, resp.status_code, resp.text[:200])
    return "retry"


def _demand_preview(demand):
    date = demand.get(COL_DATE)
    closed = demand.get(COL_CLOSED)
    return {"id": demand.get(COL_ID), "date": date.strftime("%Y-%m-%d") if date else None,
            "demandeur": demand.get(COL_REQUESTER), "sujet": demand.get(COL_SUBJECT),
            "priorite": demand.get(COL_PRIORITY), "categorie": demand.get(COL_CATEGORY),
            "duree_j": demand.get(COL_DURATION), "accomplissement": demand.get(COL_PROGRESS),
            "cloture": closed.strftime("%Y-%m-%d") if closed else None,
            "commentaire": (demand.get(COL_COMMENT) or "")[:120]}


@app.route("/demande/import", methods=["POST"])
def import_xlsx():
    """Import d'un tableau (xlsx, xls ou csv) — livraison #497.

    Champs du formulaire : `file` (obligatoire), `target` = tickets |
    projeqtor | both (défaut both : gestion de tickets du hub, file
    « imports à valider », ET ProjeQtOr), `dry_run=1` = analyser sans
    rien créer (aperçu des lignes + avertissements). Un ProjeQtOr
    injoignable n'empêche jamais l'import côté hub, et inversement ;
    chaque cible rend son propre compte.
    """
    if "file" not in request.files:
        return jsonify({"error": "fichier manquant (champ 'file')"}), 400
    upload = request.files["file"]
    filename = upload.filename or "tableau"
    content = upload.read()
    target = (request.form.get("target") or request.args.get("target") or "both").strip().lower()
    if target not in IMPORT_TARGETS:
        return jsonify({"error": f"target inconnu : {target} (attendu : {', '.join(IMPORT_TARGETS)})"}), 400
    dry_run = (request.form.get("dry_run") or request.args.get("dry_run") or "") in ("1", "true", "yes", "on")

    demands, parse_errors = parse_workbook(content, filename)
    if not demands:
        return jsonify({"error": "aucune demande exploitable", "details": parse_errors, "total": 0}), 400
    if dry_run:
        return jsonify({"status": "analyse", "total": len(demands), "avertissements": parse_errors,
                        "lignes": [_demand_preview(d) for d in demands], "target": target,
                        "tickets_api": bool(sync.TICKETS_API)}), 200

    warnings = list(parse_errors)
    result = {"tickets": None, "projeqtor": None}

    # --- cible hub (tickets-api, file « imports à valider ») ---
    if target in ("tickets", "both"):
        counts = {"crees": 0, "deja_connus": 0, "echecs": 0}
        if not sync.TICKETS_API:
            warnings.append("gestion de tickets du hub non configurée (TICKETS_API_INTERNAL_URL) : rien importé côté hub")
        for i, demand in enumerate(demands, start=1):
            outcome = push_hub_ticket(demand, i, filename)
            if outcome == "created":
                counts["crees"] += 1
            elif outcome == "known":
                counts["deja_connus"] += 1
            elif outcome == "retry":
                counts["echecs"] += 1
                warnings.append(f"demande n°{i} « {demand[COL_SUBJECT][:50]} » : non importée côté hub (tickets-api)")
            elif outcome == "disabled":
                break
        result["tickets"] = counts

    # --- cible ProjeQtOr ---
    if target in ("projeqtor", "both"):
        counts = {"crees": 0, "echecs": 0}
        client = get_client()
        by_name, _ = load_referentiels(client)
        refs_ok = any(by_name.values())
        if not refs_ok:
            warnings.append("référentiels ProjeQtOr illisibles (API injoignable ou compte du pont refusé) : "
                            "demandeur / priorité / catégorie inscrits en clair dans la description, non résolus")
        unreachable = False
        for i, demand in enumerate(demands, start=1):
            fields, unresolved = demand_to_ticket(demand, by_name)
            try:
                client.create("Ticket", fields)
                counts["crees"] += 1
            except ProjeqtorApiError as exc:
                counts["echecs"] += 1
                if not unreachable:
                    warnings.append(f"demande n°{i} « {demand[COL_SUBJECT][:50]} » : refusée par ProjeQtOr ({exc})")
                    unreachable = True  # une seule ligne d'explication, pas une par demande
            if refs_ok:
                for name in unresolved:
                    warnings.append(f"demande n°{i} : {name} absent des référentiels ProjeQtOr (inscrit en clair dans la description)")
        result["projeqtor"] = counts

    created = sum((c or {}).get("crees", 0) for c in result.values() if c)
    known = (result["tickets"] or {}).get("deja_connus", 0)
    status = "ok" if created and not any((c or {}).get("echecs") for c in result.values() if c) else ("partiel" if created or known else "echec")
    return jsonify({"status": status, "total": len(demands), "importees": created, "deja_connus": known,
                    "cibles": result, "target": target, "avertissements": warnings}), 200 if (created or known) else 502


# ------------------------------------------------------------ export xlsx

@app.route("/demande/export", methods=["GET"])
def export_xlsx():
    client = get_client()
    try:
        tickets = client.get_all("Ticket")
        if isinstance(tickets, dict):
            tickets = tickets.get("items") or tickets.get("ticket") or []
    except ProjeqtorApiError as exc:
        return jsonify({"error": str(exc)}), 502

    _, by_id = load_referentiels(client)
    demands = [ticket_to_demand(t, by_id) for t in tickets]
    demands.sort(key=lambda d: d.get("date_demande") or datetime.min)

    content = build_workbook(
        demands,
        priorities=_referentiel_names(by_id, "urgencies"),
        categories=_referentiel_names(by_id, "types"),
        requesters=_referentiel_names(by_id, "contacts"),
    )
    return send_file(
        io.BytesIO(content),
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name="Tableau des suivis des demandes.xlsx",
    )


def _referentiel_names(by_id, key):
    return sorted(by_id[key].values())


# ------------------------------------------------------------------ sync

@app.route("/demande/sync/status", methods=["GET"])
def sync_status():
    return jsonify(sync.status()), 200


@app.route("/demande/sync/now", methods=["POST"])
def sync_now():
    return jsonify(sync.sync_once(get_client())), 200


if os.environ.get("BRIDGE_SYNC_DISABLED") != "1":
    sync.start_background(get_client())

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
