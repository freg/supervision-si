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
import html as _html
import io
import json
import logging
import os
import re
import uuid
from datetime import datetime

from flask import Flask, jsonify, request, send_file, send_from_directory

import requests

from mapping import LABEL, build_recap, demand_to_ticket, ticket_to_demand
from suivi_format import (
    COL_CATEGORY, COL_CLOSED, COL_COMMENT, COL_DATE, COL_DURATION, COL_ID,
    COL_PRIORITY, COL_PROGRESS, COL_REQUESTER, COL_SUBJECT, DEFAULT_CATEGORIES,
    DEFAULT_PRIORITIES, build_workbook, demands_from_rows, normalize_key,
    parse_workbook,
)
from projeqtor_client import ProjeqtorApiError, ProjeqtorClient
import sync
import simple

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


@app.route("/demande/rapide", methods=["GET"])
def quick_page():
    """Saisie rapide dépouillée (livraison #500) : sans icône, détails
    formatés multiples dans un volet."""
    return send_from_directory(STATIC_DIR, "rapide.html")


@app.route("/demande/tableau", methods=["GET"])
def sheet_page():
    """Saisie « tableau » (livraison #500) : mêmes colonnes que le
    fichier attendu à l'import, plusieurs lignes d'un coup."""
    return send_from_directory(STATIC_DIR, "tableau.html")


# ------------------------------------------------ espace « Simple » (#541)
# Écrans pour les non-initiés (docs/ergonomie-redesign.md) : accueil,
# suivi d'une demande par son numéro, état des services en français avec
# propagation des dépendances. Même posture LAN que /demande/ ; le suivi ne
# renvoie que l'état, jamais le contenu ni un nom.

ETAT_SERVICES_FILE = os.environ.get("ETAT_SERVICES_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "services.json"))
ETAT_ETATS_FILE = os.environ.get("ETAT_ETATS_FILE", os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "etats.json"))
# #542 : états vivants depuis service-watch (URL interne, vide = fichier seul).
SERVICE_WATCH_API = os.environ.get("SERVICE_WATCH_API_INTERNAL_URL", "").rstrip("/")


@app.route("/demande/accueil", methods=["GET"])
def simple_home():
    return send_from_directory(STATIC_DIR, "accueil.html")


@app.route("/demande/suivi", methods=["GET"])
def simple_track_page():
    return send_from_directory(STATIC_DIR, "suivi.html")


@app.route("/demande/etat", methods=["GET"])
def simple_status_page():
    return send_from_directory(STATIC_DIR, "etat.html")


@app.route("/demande/simple.css", methods=["GET"])
def simple_css():
    return send_from_directory(STATIC_DIR, "simple.css")


def _read_json(path):
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


@app.route("/demande/etat.json", methods=["GET"])
def simple_status_json():
    """Référentiel (`ETAT_SERVICES_FILE`) + états (`ETAT_ETATS_FILE`, posé par
    l'exploitation ; plus tard service-watch / Cortex) -> page calculée."""
    ref = _read_json(ETAT_SERVICES_FILE) or {}
    services = ref.get("services") or []
    etats_doc = _read_json(ETAT_ETATS_FILE) or {}
    manuels = dict(etats_doc.get("etats") or {})
    auto, sources = {}, []
    if SERVICE_WATCH_API:
        try:
            r = requests.get(f"{SERVICE_WATCH_API}/service-watch/entries", timeout=8)
            if r.status_code == 200:
                auto = simple.etats_depuis_service_watch(services, (r.json() or {}).get("entries"))
                sources.append("supervision automatique")
        except (requests.RequestException, ValueError) as exc:
            log.warning("service-watch injoignable pour l'état des services : %s", exc)
    if manuels:
        sources.append(etats_doc.get("source") or "exploitation")
    etats = simple.fusion_etats(manuels, auto)
    etats["_a"] = etats_doc.get("a") or datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    page = simple.etat_des_services(services, etats)
    page["source"] = ", ".join(sources)
    return jsonify(page), 200


@app.route("/demande/suivi/<ref>", methods=["GET"])
def simple_track(ref):
    """État d'une demande par son numéro public (« D-… ») : cherche le ticket
    hub de source_type « demande » dont la clé correspond."""
    if not sync.TICKETS_API:
        return jsonify({"error": "le suivi n'est pas disponible (gestion de tickets non configurée)"}), 503
    try:
        resp = requests.get(f"{sync.TICKETS_API}/queue", params={"source_type": "demande", "state": "all", "include_archived": "true"}, timeout=15)
        rows = resp.json() if resp.status_code == 200 else []
    except (requests.RequestException, ValueError):
        return jsonify({"error": "le suivi est momentanément indisponible, réessayez dans quelques minutes"}), 502
    if isinstance(rows, dict):
        rows = rows.get("tickets") or rows.get("items") or []
    hit = next((t for t in rows if simple.ref_matches(ref, t.get("source_nom"))), None)
    if not hit:
        return jsonify({"error": "numéro inconnu : vérifiez-le, il commence par D- et vous a été donné après l'envoi"}), 404
    return jsonify(simple.plain_status(hit)), 200


@app.route("/demande/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "projeqtor-bridge"}), 200


# ---------------------------------------------------------- référentiels

@app.route("/demande/referentiels", methods=["GET"])
def referentiels():
    """Listes du formulaire. Source de vérité : ProjeQtOr ; s'il est
    injoignable ou vide (#500), les listes PAR DÉFAUT du format imposé
    (priorités, catégories) sont renvoyées avec `source: "defaut"` --
    une page publique ne doit jamais rester sans liste déroulante."""
    _, by_id = load_referentiels(get_client())
    priorites = sorted(by_id["urgencies"].values())
    categories = sorted(by_id["types"].values())
    source = "projeqtor"
    if not priorites and not categories:
        priorites, categories, source = list(DEFAULT_PRIORITIES), [c.strip() for c in DEFAULT_CATEGORIES], "defaut"
    return jsonify({
        "demandeurs": sorted(by_id["contacts"].values()),
        "priorites": priorites,
        "categories": categories,
        "source": source,
    }), 200


# ------------------------------------------------------------ dépôt public

_TAG_RE = re.compile(r"<[^>]+>")


def html_to_text(fragment):
    """HTML d'un éditeur simple (gras, italique, listes, paragraphes) ->
    texte lisible partout (ticket hub, ProjeQtOr) : **gras**, _italique_,
    « - » pour les puces, sauts de ligne conservés. Toute autre balise
    est retirée ; les entités sont décodées ; jamais de HTML restitué."""
    if not fragment:
        return ""
    t = re.sub(r"(?is)<\s*(script|style)[^>]*>.*?<\s*/\s*\1\s*>", "", fragment)
    t = re.sub(r"(?i)<\s*(br|/p|/div|/li|/h[1-6])\s*/?>", "\n", t)
    t = re.sub(r"(?i)<\s*li[^>]*>", "- ", t)
    t = re.sub(r"(?i)<\s*/?\s*(b|strong)\s*>", "**", t)
    t = re.sub(r"(?i)<\s*/?\s*(i|em)\s*>", "_", t)
    t = _TAG_RE.sub("", t)
    t = _html.unescape(t).replace("\xa0", " ")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def _details_text(details):
    """Liste [{titre, html|texte}] -> blocs de texte, chacun titré."""
    blocks = []
    for d in details or []:
        if not isinstance(d, dict):
            continue
        title = (d.get("titre") or "").strip()
        body = html_to_text(d.get("html") or "") or (d.get("texte") or "").strip()
        if not title and not body:
            continue
        blocks.append((f"{title}\n" if title else "") + body)
    return "\n\n".join(blocks)


@app.route("/demande/demandes", methods=["POST"])
def create_demand():
    """Dépôt public d'une demande. Depuis #500 : `details` (liste de
    blocs formatés du volet « Détails ») ajoutés au commentaire, et
    `target` = both (défaut) | tickets | projeqtor -- une demande
    saisie au comptoir arrive dans les « imports à valider » du hub
    même si ProjeQtOr est indisponible."""
    body = request.get_json(silent=True) or request.form.to_dict()
    subject = (body.get("sujet") or "").strip()
    if not subject:
        return jsonify({"error": "le sujet est obligatoire"}), 400
    requester = (body.get("demandeur") or "").strip()
    if not requester:
        return jsonify({"error": "le demandeur est obligatoire"}), 400
    target = (body.get("target") or "both").strip().lower()
    if target not in IMPORT_TARGETS:
        return jsonify({"error": f"target inconnu : {target}"}), 400

    duration = body.get("duree_j")
    try:
        duration = float(duration) if duration not in (None, "") else None
        if duration is not None and duration < 0:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"error": "la durée doit être un nombre positif de jours"}), 400

    comment = (body.get("commentaire") or "").strip()
    details = _details_text(body.get("details"))
    if details:
        comment = (comment + "\n\n" + details).strip() if comment else details
    if len(comment) > 20000:
        return jsonify({"error": "détails trop longs (20 000 caractères max)"}), 400

    demand = {
        COL_DATE: datetime.now(),
        COL_SUBJECT: subject,
        COL_REQUESTER: requester,
        COL_PRIORITY: (body.get("priorite") or "").strip(),
        COL_CATEGORY: (body.get("categorie") or "").strip(),
        COL_DURATION: duration,
        COL_COMMENT: comment,
    }

    out = {"status": "ok", "non_resolus": [], "cibles": {}}
    key = bridge_key(demand, unique=True)
    if target in ("projeqtor", "both"):
        client = get_client()
        by_name, _ = load_referentiels(client)
        fields, unresolved = demand_to_ticket(demand, by_name, external_ref=key)
        try:
            out["projeqtor"] = client.create("Ticket", fields)
            out["cibles"]["projeqtor"] = "created"
            out["non_resolus"] = unresolved if any(by_name.values()) else []
        except ProjeqtorApiError as exc:
            out["cibles"]["projeqtor"] = "failed"
            if target == "projeqtor":
                return jsonify({"error": f"création refusée par ProjeQtOr : {exc}"}), 502
            log.warning("dépôt public : ProjeQtOr en échec, ticket hub seul (%s)", exc)
    if target in ("tickets", "both"):
        out["cibles"]["tickets"] = push_hub_ticket(demand, 1, "formulaire", source_type="demande", source_name=key)

    if out["cibles"].get("tickets") not in ("created", "known", None) and out["cibles"].get("projeqtor") != "created":
        return jsonify({"error": "demande non enregistrée (gestion de tickets du hub injoignable)"}), 502
    out["message"] = "demande enregistrée — elle sera prise en charge par le service informatique"
    out["reference"] = simple.public_ref(key)  # #541 : numéro de suivi public
    return jsonify(out), 201


# ------------------------------------------------------------ import xlsx

IMPORT_TARGETS = ("tickets", "projeqtor", "both")


def bridge_key(demand, unique=False):
    """Clé UNIQUE d'une demande passée par le pont (#500) : externalReference
    du ticket ProjeQtOr ET source_nom du ticket hub (source_type
    « demande »). Import de fichier : l'Id du tableau (stable d'un import
    à l'autre) sinon une empreinte date+demandeur+sujet ; formulaire et
    tableau en ligne (`unique`) : un identifiant tiré au sort, chaque
    saisie est nouvelle."""
    if unique:
        return f"{LABEL}:s:{uuid.uuid4().hex[:12]}"
    return _hub_source_name(demand, 0, "")


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
    meta = (f"Saisi via {filename}" if filename in ("formulaire", "tableau en ligne") else f"Importé du tableau « {filename} »") + (f", demande du {date.strftime('%d/%m/%Y')}" if date else "")
    if demand.get(COL_CLOSED):
        meta += f", clôturée le {demand[COL_CLOSED].strftime('%d/%m/%Y')}"
    parts.append(meta)
    return "\n\n".join(parts)


def push_hub_ticket(demand, index, filename, source_type="demande", source_name=None):
    """Une demande du tableau (ou du formulaire, #500) -> un ticket hub À
    VALIDER (même file que la synchronisation ProjeQtOr et les imports
    ICS). Retourne created / known / retry / disabled."""
    if not sync.TICKETS_API:
        return "disabled"
    try:
        resp = requests.post(
            f"{sync.TICKETS_API}/tickets/import-external",
            json={"subject": demand[COL_SUBJECT], "description": _hub_description(demand, filename),
                  "source_type": source_type, "source_nom": source_name or _hub_source_name(demand, index, filename)},
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
    payload = request.get_json(silent=True) if request.is_json else None
    if payload is not None:
        # #500 : lignes saisies dans la page « tableau » (mêmes colonnes
        # que le fichier), sans passer par un xlsx.
        rows = payload.get("rows")
        if not isinstance(rows, list) or not rows:
            return jsonify({"error": "'rows' (liste de lignes) requis"}), 400
        filename = "tableau en ligne"
        target = (payload.get("target") or "both").strip().lower()
        dry_run = bool(payload.get("dry_run"))
        demands, parse_errors = demands_from_rows(rows)
    else:
        if "file" not in request.files:
            return jsonify({"error": "fichier manquant (champ 'file')"}), 400
        upload = request.files["file"]
        filename = upload.filename or "tableau"
        content = upload.read()
        target = (request.form.get("target") or request.args.get("target") or "both").strip().lower()
        dry_run = (request.form.get("dry_run") or request.args.get("dry_run") or "") in ("1", "true", "yes", "on")
        demands, parse_errors = (None, None)
    if target not in IMPORT_TARGETS:
        return jsonify({"error": f"target inconnu : {target} (attendu : {', '.join(IMPORT_TARGETS)})"}), 400
    if demands is None:
        demands, parse_errors = parse_workbook(content, filename)
    if not demands:
        return jsonify({"error": "aucune demande exploitable", "details": parse_errors, "total": 0}), 400
    if dry_run:
        return jsonify({"status": "analyse", "total": len(demands), "avertissements": parse_errors,
                        "lignes": [_demand_preview(d) for d in demands], "target": target,
                        "tickets_api": bool(sync.TICKETS_API)}), 200

    warnings = list(parse_errors)
    result = {"tickets": None, "projeqtor": None}
    online = filename == "tableau en ligne"
    keys = {i: bridge_key(d, unique=online) for i, d in enumerate(demands, start=1)}

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
            fields, unresolved = demand_to_ticket(demand, by_name, external_ref=keys[i])
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

    # --- cible hub (tickets-api, file « imports à valider ») : même clé
    #     que l'externalReference ProjeQtOr -> la synchronisation
    #     ProjeQtOr -> hub retrouve « déjà connu », jamais de doublon ---
    if target in ("tickets", "both"):
        counts = {"crees": 0, "deja_connus": 0, "echecs": 0}
        if not sync.TICKETS_API:
            warnings.append("gestion de tickets du hub non configurée (TICKETS_API_INTERNAL_URL) : rien importé côté hub")
        for i, demand in enumerate(demands, start=1):
            outcome = push_hub_ticket(demand, i, filename, source_type="demande", source_name=keys[i])
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

    created = max([(c or {}).get("crees", 0) for c in result.values() if c] or [0])  # demandes enregistrées, pas cibles x demandes
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
