"""projeqtor-bridge — pont entre le format OPTLINE imposé, ProjeQtOr
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
    POST /demande/import         fichier xlsx OPTLINE -> tickets ProjeQtOr
    GET  /demande/export         tickets ProjeQtOr -> xlsx OPTLINE
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

from mapping import demand_to_ticket, ticket_to_demand
from optline_format import (
    COL_CATEGORY, COL_COMMENT, COL_DURATION, COL_PRIORITY,
    COL_REQUESTER, COL_SUBJECT, build_workbook, normalize_key,
    parse_workbook,
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

@app.route("/demande/import", methods=["POST"])
def import_xlsx():
    if "file" not in request.files:
        return jsonify({"error": "fichier xlsx manquant (champ 'file')"}), 400
    content = request.files["file"].read()
    demands, parse_errors = parse_workbook(content)
    if not demands and parse_errors:
        return jsonify({"error": "aucune demande exploitable", "details": parse_errors}), 400

    client = get_client()
    by_name, _ = load_referentiels(client)
    created, failed = 0, []
    for i, demand in enumerate(demands, start=1):
        fields, unresolved = demand_to_ticket(demand, by_name)
        try:
            client.create("Ticket", fields)
            created += 1
        except ProjeqtorApiError as exc:
            failed.append(f"demande n°{i} « {demand['sujet'][:50]} » : {exc}")
        for name in unresolved:
            failed.append(f"demande n°{i} : {name} absent des référentiels ProjeQtOr (inscrit en clair dans la description)")

    return jsonify({
        "status": "ok" if not failed else "partiel",
        "importees": created,
        "total": len(demands),
        "avertissements": parse_errors + failed,
    }), 200 if created else 502


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
