"""si-agent-api -- central des agents hôtes Linux (livraison #421,
backlog 63). Deux faces :

  - face TABLEAU DE BORD (hub, non signée, même niveau de confiance que
    les autres API de module : LAN + passerelle) : flotte, enrôlement,
    catalogue de plugins, affectations, commandes, mesures, risques ;
  - face AGENTS (signée HMAC, préfixe /api/v1, contrat décrit dans
    si-agent/README.md) : configuration, commandes + acquittement, dépôt
    des mesures.

Le protocole et la validation/signature des plugins sont des COPIES de
si-agent/agent/si_agent/{protocol,plugins}.py (voir Dockerfile) -- jamais
une seconde implémentation ici.
"""
import logging
import os
import re
import shlex
import threading
import tempfile
import urllib.request
import time

import requests

from flask import Flask, Response, g, jsonify, request, send_file
from flask_cors import CORS

try:
    import si_agent_protocol as protocol
    import si_agent_control as control
    import si_agent_publish as agent_publish
    import si_agent_imagestore as imagestore
except ImportError:  # dépôt de développement
    import sys as _sys
    _sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "agent"))
    from si_agent import control, protocol  # noqa: E402
    from si_agent import publish as agent_publish  # noqa: E402
    from si_agent import imagestore  # noqa: E402
    import si_agent.plugins as _plugins  # noqa: E402
    _sys.modules.setdefault("si_agent_plugins", _plugins)
    _sys.modules.setdefault("si_agent_control", control)

import package  # noqa: E402
import store  # noqa: E402
import publish as publish_lib  # noqa: E402
import updates  # noqa: E402
import pra  # noqa: E402  -- #653 : plans PRA / opérations PVE
import maint  # noqa: E402  -- #705 : maintenance / réorganisation des Proxmox
import migration  # noqa: E402  -- #658 : migration serveur -> virtualisation (générateur de plan)
import priorites  # noqa: E402  -- #818 : priorités de la page d'accueil (préparation, décideur, explication)
import banc  # noqa: E402  -- #825 : banc d'installation des agents sur un pool de VM
import diffusion  # noqa: E402  -- #822 : diffusions en cascade (déploiement avec dépendances)
import emulation  # noqa: E402  -- #831 : tuile Émulation et déploiement supervisé
import orchestration  # noqa: E402  -- #832 : tuile Orchestration (VM Proxmox, k3s, Nomad)
import activite  # noqa: E402  -- #830 : travaux en cours (pied de page du hub)
import apprentissage  # noqa: E402  -- #828 : jeu de données du décideur, entraînements LoRA, évaluation
import skills  # noqa: E402  -- #827 : skills des IA (consignes versionnées)
import genealogie  # noqa: E402  -- #854 : généalogie des modèles (histoire, filiations, mode d'emploi)
import modeles  # noqa: E402  -- #821 : Parc IA, veille des modèles (sorties, ouvert/fermé, usages)
import prep  # noqa: E402  -- #815 : préparer la réinstallation d'un nœud (quorum, invités transférés, sauvegardes, PRA)
import ping as ping_lib  # noqa: E402  -- #868 : test de connectivité rapide (bouton ping à côté des IP)
import shell_analyses  # noqa: E402  -- #919 : analyse technique à distance (catalogue + interprétation)
import copies as copies_lib  # noqa: E402  -- #856 : inventaire de toutes les copies et distance à la source
import acces as acces_lib  # noqa: E402  -- #856 : accessibilité des services des CT / VM
import risque as risque_lib  # noqa: E402  -- #856 : récapitulatif permanent du risque (Migration › Risques)
import etat as etat_lib  # noqa: E402  -- #857 : état des lieux des systèmes (versions, mises à jour, services, usage, dépendances)
import etat_excel  # noqa: E402  -- #857 : version Excel pour les décideurs
import etat_rapport  # noqa: E402  -- #860 : audit d'obsolescence et de support (page imprimable)
import infra  # noqa: E402  -- #749 : vue d'ensemble PVE / PBS
import views  # noqa: E402  -- #753 : vues de parc paramétrables (serveurs, postes, IA, postes personnels)
import repatriation as repa  # noqa: E402  -- #761 : assistant de rapatriement / nettoyage d'un nœud distant
import guestusage  # noqa: E402  -- #769 : activité des CT / VM de tous les Proxmox
import edgepair  # noqa: E402  -- #776 : couple de proxys d'entrée interchangeables (routes, bascule, contrôle DNS)
import latency  # noqa: E402  -- #775 : latence des IP publiques (cibles, points de mesure, accès)
import navigateurs  # noqa: E402  -- #798 : navigateurs des hôtes (écran web + automate)
import services_poste  # noqa: E402  -- #928 : sites de service à tester depuis un poste (temps d'accès)
import sauvegarde_conf  # noqa: E402  -- #930 : sélection des confs logicielles à sauvegarder
import htoprelay  # noqa: E402  -- #800 : relais si-htop (tuile htop, constats -> événements)
import datarf  # noqa: E402  -- #806 : tuile Data RF (sondes radio des sites)
import parcours as parcoursmod  # noqa: E402  -- #799/#800 : parcours appris, demandes en langage courant
import journal  # noqa: E402  -- #795 : journal des chantiers (actes, surveillances, relances, interventions)
import migrun  # noqa: E402  -- #774 : tuile « Migration 2026-2027 » (plan d'étapes, pilotage, erreurs et solutions)
import rotation  # noqa: E402  -- #743 : tournées de mesures réparties (supervision distribuée, item 120)
import json  # noqa: E402
import notify  # noqa: E402
import alertfilters  # noqa: E402  (#607)

try:
    from version_endpoint import register_version_route
except ImportError:
    register_version_route = None
try:
    from log_buffer import make_shared_log_handler, read_shared_log_buffer
    from pymemcache.client.base import Client as _MemcacheClient
except ImportError:
    make_shared_log_handler = read_shared_log_buffer = _MemcacheClient = None

app = Flask(__name__)
CORS(app)
if register_version_route:
    register_version_route(app, "si-agent-api")
if notify.notify_client is not None and os.environ.get("NOTIFY_API_URL"):   # #716 : catalogue des actions relayées à notify-api
    notify.notify_client.register_actions(notify.HUB_ACTIONS)

# A1 (#620) : périmètre de site par groupe Keycloak (SITE_SCOPE_GROUPS) -- sans jeton rien ne change
try:
    import site_scope as _site_scope
    _site_scope.install(app, os.environ.get("SITE_SCOPE_JWKS_URL") or "%s/realms/%s/protocol/openid-connect/certs" % (
        os.environ.get("KEYCLOAK_INTERNAL_URL", "http://keycloak:8080/auth"), os.environ.get("KEYCLOAK_REALM", "supervision-si")),
        resolve_site=lambda p: (store.get_agent(DB_PATH, p.split("/")[2]) or {}).get("site") if p.startswith("/agents/") and len(p.split("/")) > 2 else None, what="si-agent-api")
except ImportError:
    _site_scope = None

_log = logging.getLogger("si_agent_api")
# Verbosité (#422) : SI_AGENT_LOG_LEVEL=DEBUG trace chaque requête de la face
# agents (identifiant, chemin, statut, durée) et chaque action du tableau
# de bord ; les refus d'authentification sont TOUJOURS journalisés (WARNING)
# et deviennent des événements.
logging.basicConfig(level=getattr(logging, os.environ.get("SI_AGENT_LOG_LEVEL", "INFO").upper(), logging.INFO),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

DB_PATH = os.environ.get("SI_AGENT_DB_PATH", "/data/si-agent.db")
OFFLINE_AFTER_SECONDS = int(os.environ.get("SI_AGENT_OFFLINE_SECONDS", "300"))
RETENTION_DAYS = int(os.environ.get("SI_AGENT_RETENTION_DAYS", "90"))
# #869 : rétention plus courte des grosses mesures déjà agrégées ailleurs (« tâche=jours,tâche=jours »)
TASK_RETENTION = {k.strip(): int(v) for k, v in (x.split("=", 1) for x in os.environ.get(
    "SI_AGENT_RETENTION_TASKS", "plugin:guest-usage=3").split(",") if "=" in x) if v.strip().isdigit()}
# #933 : rétention plus LONGUE des résultats de tests de charge (conservés pour comparaison dans le temps)
TASK_RETENTION_LONG = {k.strip(): int(v) for k, v in (x.split("=", 1) for x in os.environ.get(
    "SI_AGENT_RETENTION_TASKS_LONG", "plugin:poste-charge=730").split(",") if "=" in x) if v.strip().isdigit()}
PUBLIC_URL = os.environ.get("SI_AGENT_PUBLIC_URL", "").rstrip("/")
INTERNAL_URL = os.environ.get("SI_AGENT_INTERNAL_URL", "").rstrip("/")   # #905 : adresse LAN du central (itinérance : secours)
CA_FILE = os.environ.get("SI_AGENT_CA_FILE", "/ca/ca.crt")
EVENTS_RETENTION_DAYS = int(os.environ.get("SI_AGENT_EVENTS_RETENTION_DAYS", "365"))
MEMCACHED_HOST = os.environ.get("MEMCACHED_HOST", "memcached")
MEMCACHED_PORT = int(os.environ.get("MEMCACHED_PORT", "11211"))
SERVICE_NAME = "si-agent-api"
LOG_BUFFER_SIZE = int(os.environ.get("LOG_BUFFER_SIZE", "200"))
LOG_CAPTURE_LEVEL = os.environ.get("LOG_CAPTURE_LEVEL", "WARNING").strip().upper()

store.ensure_schema(DB_PATH)
pra.init(DB_PATH)
rotation.init(DB_PATH)


def get_memcache_client():
    return _MemcacheClient((MEMCACHED_HOST, MEMCACHED_PORT), connect_timeout=2, timeout=2)


if make_shared_log_handler and _MemcacheClient:
    logging.getLogger().addHandler(make_shared_log_handler(
        SERVICE_NAME, get_memcache_client, buffer_size=LOG_BUFFER_SIZE, capture_level=LOG_CAPTURE_LEVEL))


def _purge_loop():
    while True:
        time.sleep(3600)
        try:
            t0 = time.time()
            n = store.purge_measurements(DB_PATH, RETENTION_DAYS, task_retention=TASK_RETENTION, task_retention_long=TASK_RETENTION_LONG)
            _log.info("purge : %d mesure(s) au-delà de %d jours (%s) en %.0f s", n, RETENTION_DAYS, TASK_RETENTION, time.time() - t0)
            n = store.purge_events(DB_PATH, EVENTS_RETENTION_DAYS)
            if n:
                _log.info("purge : %d événement(s) au-delà de %d jours", n, EVENTS_RETENTION_DAYS)
        except Exception as exc:  # noqa: BLE001
            _log.warning("purge impossible : %s", exc)


ALERT_TZ = os.environ.get("SI_AGENT_ALERT_TZ", alertfilters.DEFAULT_TZ)


def alert_groups():
    g = store.get_setting(DB_PATH, "alert_filters", None)
    return g.get("groups") if isinstance(g, dict) and isinstance(g.get("groups"), list) else alertfilters.DEFAULT_GROUPS


def _event(kind, severity, message, agent_id=None, details=None, source="central"):
    """Journalise (base + traces) et notifie si la sévérité le mérite.
    #607 : un événement filtré par le groupe de l'agent est conservé mais
    marqué `muted` -- ni bandeau, ni synthèse, ni notification."""
    ev = store.add_event(DB_PATH, kind, severity, message, agent_id=agent_id, details=details, source=source)
    if ev:
        agent = store.get_agent(DB_PATH, agent_id) if agent_id else None
        muted, why = alertfilters.evaluate(ev, alert_groups(), {"filter_enabled": (agent or {}).get("filter_enabled"), "filter_group": (agent or {}).get("filter_group")}, ALERT_TZ)
        if muted:
            store.mark_muted(DB_PATH, ev["id"], why)
            ev["muted"], ev["muted_by"] = 1, why
            return ev
        notify.dispatch(DB_PATH, ev)
    return ev


def watchdog_tick():
    """Transitions en ligne / hors ligne -> événements (et notifications)."""
    for agent_id, state in store.online_transitions(DB_PATH, OFFLINE_AFTER_SECONDS):
        _event("agent-offline" if state == "offline" else "agent-online", "warning" if state == "offline" else "info",
               "agent %s %s" % (agent_id, "ne répond plus (hors ligne)" if state == "offline" else "de nouveau en ligne"), agent_id=agent_id)
        if state == "offline":   # #654 : plans PRA déclenchés par la perte de cet agent (proposés, ou lancés si trigger_mode = auto)
            try:
                pra.on_agent_offline(DB_PATH, agent_id, lambda kind, sev, msg, aid, det: _event(kind, sev, msg, agent_id=aid, details=det))
            except Exception:  # noqa: BLE001 -- jamais bloquer le chien de garde
                logging.getLogger("si_agent_api").exception("déclencheurs PRA")


def _watchdog_loop():
    while True:
        time.sleep(30)
        try:
            watchdog_tick()
        except Exception as exc:  # noqa: BLE001
            _log.warning("chien de garde : %s", exc)
        try:
            _banc_tick()                    # #825 : banc d'installation (passages sur le pool de VM)
        except Exception as exc:  # noqa: BLE001
            _log.warning("banc : %s", exc)
        try:
            _orch_vms_tick()                # #836 : VM à la demande (Orchestration), durée de vie
        except Exception as exc:  # noqa: BLE001
            _log.warning("VM à la demande : %s", exc)
        try:
            _diffusions_auto()              # #822 : diffusions en cascade en mode automatique
        except Exception as exc:  # noqa: BLE001
            _log.warning("diffusions : %s", exc)
        try:
            rotation.tick(DB_PATH)          # #743 : créneaux des tournées de mesures
        except Exception as exc:  # noqa: BLE001
            _log.warning("tournées : %s", exc)
        try:
            _c = store._connect(DB_PATH)   # #775 : mesures de latence (créneaux, résultats, purge)
            try:
                latency.tick(_c)
                _c.commit()
            finally:
                _c.close()
        except Exception as exc:  # noqa: BLE001
            _log.warning("latence : %s", exc)
        try:
            _c = store._connect(DB_PATH)   # #776 : état des proxys d'entrée, contrôle DNS, alertes « DNS à configurer »
            try:
                edgepair.tick(_c, event=lambda kind, sev, msg, det: _event(kind, sev, msg, details=det))
                _c.commit()
            finally:
                _c.close()
        except Exception as exc:  # noqa: BLE001
            _log.warning("proxys d'entrée : %s", exc)
        try:
            htop_tick()                    # #800 : constats du relais si-htop -> journal et notifications
        except Exception as exc:  # noqa: BLE001
            _log.warning("htop : %s", exc)


def _index_thread():
    """#869 : index (task, agent_id, at) construit en arrière-plan, un seul processus à la fois."""
    import fcntl
    try:
        fh = open(os.path.join(os.path.dirname(DB_PATH) or ".", "index.lock"), "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return
    time.sleep(20)
    try:
        store.ensure_task_index(DB_PATH, log=_log.warning)
    except Exception as exc:  # noqa: BLE001 -- l'index est une optimisation : l'API fonctionne sans
        _log.warning("index des sondes impossible : %s", exc)


if os.environ.get("SI_AGENT_PURGE_THREAD", "1") == "1":
    threading.Thread(target=_index_thread, name="index", daemon=True).start()
    threading.Thread(target=_purge_loop, daemon=True).start()
    threading.Thread(target=_watchdog_loop, daemon=True).start()
app.register_blueprint(genealogie.bp)   # #854 : /modeles/genealogie
app.register_blueprint(modeles.bp)   # #821 : /modeles/* (Parc IA, veille des modèles)


def _modeles_parc():
    """#821 : « Usages » -- les modèles Ollama relevés par la sonde ollama de chaque hôte, nommés « hôte/modèle »."""
    out = []
    for a in store.fleet(DB_PATH):
        ol = ((store.latest_per_task(DB_PATH, a["agent_id"]).get("plugin:ollama") or {}).get("data") or {})
        for m in ol.get("models") or []:
            out.append({"name": "%s/%s" % (a["agent_id"], m.get("name")), "size": m.get("size"), "modified_at": m.get("modified"),
                        "details": {"family": m.get("family"), "parameter_size": m.get("params"), "quantization_level": m.get("quant")}})
    return out


modeles.source_tags = _modeles_parc
app.register_blueprint(skills.bp)   # #827
app.register_blueprint(activite.bp)   # #830
activite.DB_PATH = DB_PATH   # #837 : commandes Émulation / Orchestration dans le pied de page
app.register_blueprint(emulation.bp)   # #831
emulation.DB_PATH = DB_PATH
emulation.evenement = lambda k, s, m, a, d: _event(k, s, m, agent_id=a, details=d)
app.register_blueprint(orchestration.bp)   # #832
orchestration.DB_PATH = DB_PATH
orchestration.evenement = lambda k, s, m, a, d: _event(k, s, m, agent_id=a, details=d)
orchestration.machines = lambda: _infra_now()


def _essai_skill(sk, texte):
    """#827 : joue un skill sur un texte avec le modèle déclaré pour son usage (sinon celui du .env)."""
    t0 = time.time()
    m = priorites.modeles_declares().get(sk["usage"])
    with activite.suivre("ia", "essai du skill %s" % sk["id"]):
        return _essai_skill_brut(sk, texte, m, t0)


def _essai_skill_brut(sk, texte, m, t0):
    if sk["type"] == "decision":
        q = priorites.questions_effectives(json.loads(sk["texte"])) if sk["id"] == "priorites-decideur" else json.loads(sk["texte"])
        d = priorites.decideur.decider_lot([texte], q, cfg={"llm_modele": m} if m else None)
        if d.get("erreur"):
            raise ValueError(d["erreur"])
        return {"sortie": json.dumps((d.get("reponses") or [None])[0], ensure_ascii=False, indent=1), "modele": d.get("modele"), "duree_s": round(time.time() - t0, 1)}
    out = priorites.decideur.llm_chat([{"role": "system", "content": sk["texte"]}, {"role": "user", "content": texte}], modele=m, delai=600)
    return {"sortie": out, "modele": m or priorites.decideur.config()["llm_modele"], "duree_s": round(time.time() - t0, 1)}


skills.essayer_hook = _essai_skill
app.register_blueprint(apprentissage.bp)   # #828
apprentissage.evaluer_lot = lambda etats_, q, m: priorites.decideur.decider_lot(etats_, q, cfg={"llm_modele": m}).get("reponses") or []
modeles.notifier = lambda titre, ctx: _event("modele-alerte", "warning", titre, details=ctx)   # #823 : journal + notifications
if os.environ.get("SI_AGENT_PURGE_THREAD", "1") == "1":
    modeles.demarrer()


# ============================================================
# Face tableau de bord
# ============================================================

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": SERVICE_NAME}), 200


@app.route("/status", methods=["GET"])
def status_route():
    agents = store.fleet(DB_PATH, offline_after_seconds=OFFLINE_AFTER_SECONDS)
    counts = {"online": 0, "offline": 0, "never": 0}
    risk_counts = {"critical": 0, "warning": 0, "info": 0}
    for a in agents:
        counts[a["online"]] = counts.get(a["online"], 0) + 1
        for k, v in (a.get("risks") or {}).get("counts", {}).items():
            risk_counts[k] = risk_counts.get(k, 0) + (v or 0)
    fb = store.fleet_block(DB_PATH)
    return jsonify({"agents": len(agents), "contact": counts, "risks": risk_counts,
                    "plugins": len(store.list_plugins(DB_PATH)), "offline_after_seconds": OFFLINE_AFTER_SECONDS,
                    "retention_days": RETENTION_DAYS, "public_url": PUBLIC_URL or None,
                    "fleet_blocked": bool(fb.get("blocked")), "fleet_block_reason": fb.get("reason"), "fleet_blocked_at": fb.get("at"),
                    "agents_blocked": sum(1 for a in agents if a["blocked"]),
                    "insecure_agents": [a["agent_id"] for a in agents if a.get("insecure_tls")],
                    "ca": _ca_info(), "notifications": notify.describe(),
                    "log_level": logging.getLevelName(logging.getLogger().level),
                    "package": package.package_info(package.find_package())}), 200


@app.route("/package", methods=["GET"])
def package_route():
    """#518 : archive de déploiement de l'agent (sans secret), construite dans
    l'image -- à télécharger depuis la tuile ou par curl sur l'hôte."""
    path = package.find_package()
    if not path:
        return jsonify({"error": "archive absente de l'image (si-agent/make-archive.sh au build)"}), 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path), mimetype="application/gzip")


@app.route("/package/info", methods=["GET"])
def package_info_route():
    info = package.package_info(package.find_package())
    if not info:
        return jsonify({"error": "archive absente"}), 404
    return jsonify(dict(info, url=(PUBLIC_URL or "") + "/package")), 200


def _ca_info():
    try:
        with open(CA_FILE, "rb") as fh:
            pem = fh.read()
        import ssl as _ssl
        import hashlib as _hashlib
        der = _ssl.PEM_cert_to_DER_cert(pem.decode("utf-8"))
        return {"available": True, "sha256": _hashlib.sha256(der).hexdigest(), "path": CA_FILE}
    except (OSError, ValueError):
        return {"available": False, "sha256": None, "path": CA_FILE}


@app.route("/ca", methods=["GET"])
def ca_route():
    """Certificat de l'autorité interne (PEM) pour l'amorçage TLS des agents
    (install.sh --ca-fingerprint) : public par nature, l'EMPREINTE affichée
    dans la tuile fait foi côté hôte."""
    try:
        with open(CA_FILE, "rb") as fh:
            pem = fh.read()
    except OSError:
        return jsonify({"error": "certificat de l'autorité indisponible (SI_AGENT_CA_FILE)"}), 404
    return pem, 200, {"Content-Type": "application/x-pem-file"}


@app.route("/vpn", methods=["GET"])
def vpn_route():
    """#884 : VPN WireGuard (sonde wireguard) -> {serveurs: [état courant par agent], sessions: [historique reconstitué]}.
    ?days=30 (1..365, borné par la rétention des mesures). Aucune clé privée n'est stockée (écartée par la sonde)."""
    import datetime as _dt
    import vpn
    try:
        days = max(1, min(365, int(request.args.get("days", 30))))
    except ValueError:
        days = 30
    conn = store._connect(DB_PATH)
    try:
        courant = infra.latest(conn, vpn.TASK)
        rel = vpn.releves(conn, days)
        se_serveurs, se_sessions = vpn.softether(infra.latest(conn, vpn.TASK_SE))   # #885
    finally:
        conn.close()
    serveurs = [{"relais": a, "hote": h, "at": at, "source": (d or {}).get("source"), "interfaces": (d or {}).get("interfaces") or [],
                 "alertes": (d or {}).get("alerts") or []} for a, h, at, d in courant]
    depuis = (_dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    sessions = vpn.sessions(rel) + [s for s in se_sessions if (s.get("debut") or "") >= depuis or s.get("en_cours")]
    sessions.sort(key=lambda s: s.get("debut") or "", reverse=True)
    return jsonify({"serveurs": serveurs + se_serveurs, "sessions": sessions[:3000], "days": days}), 200


@app.route("/sockets", methods=["GET"])
def sockets_route():
    """#906 : sockets des hôtes (sonde sockets, à la demande). Sans param -> dernier relevé de chaque agent (compteurs).
    ?agent=X -> relevé complet de X + horodatages disponibles (historique). ?agent=X&at=<iso> -> le relevé de cet instant."""
    agent = (request.args.get("agent") or "").strip()
    at = (request.args.get("at") or "").strip()
    conn = store._connect(DB_PATH)
    try:
        if not agent:
            rows = infra.latest(conn, "plugin:sockets")
            hotes = [{"agent": a, "hote": h, "at": t, "counts": (d or {}).get("counts") or {}, "alertes": (d or {}).get("alerts") or []}
                     for a, h, t, d in rows]
            hotes.sort(key=lambda x: x["agent"])
            return jsonify({"hotes": hotes}), 200
        hist = [r["at"] for r in conn.execute(
            "SELECT at FROM measurements WHERE agent_id = ? AND task = 'plugin:sockets' ORDER BY at DESC LIMIT 200", (agent,)).fetchall()]
        if at:
            row = conn.execute("SELECT at, data FROM measurements WHERE agent_id = ? AND task = 'plugin:sockets' AND at = ? LIMIT 1", (agent, at)).fetchone()
        else:
            row = conn.execute("SELECT at, data FROM measurements WHERE agent_id = ? AND task = 'plugin:sockets' ORDER BY at DESC LIMIT 1", (agent,)).fetchone()
        if not row:
            return jsonify({"agent": agent, "at": None, "sockets": [], "counts": {}, "historique": hist}), 200
        import json as _json
        d = _json.loads(row["data"]) if isinstance(row["data"], str) else (row["data"] or {})
        return jsonify({"agent": agent, "at": row["at"], "sockets": (d or {}).get("sockets") or [],
                        "counts": (d or {}).get("counts") or {}, "historique": hist}), 200
    finally:
        conn.close()


@app.route("/postes-windows", methods=["GET"])
def postes_windows_route():
    """#896 : postes Windows (sonde poste-windows) et derniers tests de charge (poste-charge) ; ?agent= pour un seul."""
    seul = (request.args.get("agent") or "").strip()
    conn = store._connect(DB_PATH)
    try:
        cfg = {a: (h, at, d) for a, h, at, d in infra.latest(conn, "plugin:poste-windows")}
        charge = {a: (at, d) for a, _h, at, d in infra.latest(conn, "plugin:poste-charge")}
    finally:
        conn.close()
    out = []
    for a in sorted(set(cfg) | set(charge)):
        if seul and a != seul:
            continue
        h, at, d = cfg.get(a, (None, None, None))
        d = d or {}
        c = charge.get(a)
        e = {"agent": a, "hote": h, "at": at, "poste": d.get("poste"), "alertes": d.get("alerts") or [],
             "charge": dict(c[1] or {}, at=c[0]) if c else None}
        if seul:
            e.update(reinstallation=d.get("reinstallation"), diagnostic=d.get("diagnostic"))
        out.append(e)
    return jsonify({"postes": out}), 200


# ---- #919 : analyse technique à distance (PowerShell par l'agent, résultats interprétés ici) -------------------
@app.route("/shell/analyses", methods=["GET"])
def shell_analyses_route():
    return jsonify({"analyses": shell_analyses.liste()}), 200


def _shell_commandes(agent_id, limit=200):
    return [c for c in store.list_commands(DB_PATH, agent_id, limit=limit)
            if c["type"] == "shell" and (c.get("params") or {}).get("action", "run") == "run"]


def _shell_job(c, mesure):
    p = c.get("params") or {}
    d = (mesure or {}).get("data") or {}
    statut, motif = shell_analyses.etat_commande(c, mesure)     # #926 : en file sur le poste, perdue (agent redémarré)
    return {"id": p.get("id"), "titre": p.get("titre"), "mode": p.get("mode"), "analyse": p.get("analyse"), "format": p.get("format"),
            "par": p.get("par"), "envoye": c.get("created_at"), "statut": statut, "debut": d.get("debut"), "fin": d.get("fin"),
            "code": d.get("code"), "motif": motif, "maj": (mesure or {}).get("at")}


@app.route("/agents/<agent_id>/shell", methods=["GET"])
def shell_liste_route(agent_id):
    a = store.get_agent(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    latest = store.latest_per_task(DB_PATH, agent_id)
    jobs = [_shell_job(c, latest.get("shell:%s" % (c.get("params") or {}).get("id"))) for c in _shell_commandes(agent_id)[:50]]
    return jsonify({"agent": agent_id, "remote_shell": a.get("remote_shell") or "off", "jobs": jobs}), 200


@app.route("/agents/<agent_id>/shell", methods=["POST"])
def shell_lancer_route(agent_id):
    b = request.get_json(silent=True) or {}
    a = store.get_agent(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    ana = None
    if b.get("analyse"):
        ana = shell_analyses.analyse(str(b["analyse"]))
        if ana is None:
            return jsonify({"error": "analyse inconnue"}), 400
    script = ana["script"] if ana else b.get("script")
    mode = "lecture" if ana else str(b.get("mode") or "lecture")
    permis = a.get("remote_shell") or "off"
    if permis == "off" or (mode == "intervention" and permis != "intervention"):
        return jsonify({"error": "commandes à distance %s pour cet agent (réglage dans la fiche de l'agent) -- mode demandé : %s"
                        % ({"off": "désactivées", "lecture": "limitées à la lecture"}.get(permis, permis), mode)}), 403
    try:
        delai = int(ana["delai"] if ana else (b.get("delai") or 300))
    except (TypeError, ValueError):
        delai = 300
    delai = max(5, min(delai, 3600))
    tid = "sh-" + os.urandom(5).hex()
    premiere = next((l.strip() for l in str(script or "").splitlines() if l.strip()), "commande")
    titre = (ana["titre"] if ana else (b.get("titre") or premiere))[:120]
    actor = (str(b.get("actor") or "")[:64]) or None
    params = {"action": "run", "id": tid, "script": script, "mode": mode, "delai": delai, "titre": titre,
              "format": ana["format"] if ana else "texte", "analyse": ana["id"] if ana else None, "par": actor}
    try:
        c = store.create_command(DB_PATH, agent_id, "shell", params)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    import hashlib as _h
    _event("remote-shell-sent", "warning" if mode == "intervention" else "info",
           "commande à distance « %s » (mode %s) envoyée à %s%s" % (titre, mode, agent_id, (" par %s" % actor) if actor else ""),
           agent_id=agent_id, details={"id": tid, "mode": mode, "analyse": params["analyse"], "par": actor,
                                       "sha256": _h.sha256(str(script).encode("utf-8")).hexdigest(), "extrait": str(script)[:300]})
    return jsonify({"job": tid, "command": c}), 200


@app.route("/agents/<agent_id>/shell/<tid>/stop", methods=["POST"])
def shell_stop_route(agent_id, tid):
    try:
        c = store.create_command(DB_PATH, agent_id, "shell", {"action": "stop", "id": tid})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if c is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"command": c}), 200


@app.route("/agents/<agent_id>/shell/<tid>", methods=["GET"])
def shell_detail_route(agent_id, tid):
    c = next((x for x in _shell_commandes(agent_id, 500) if (x.get("params") or {}).get("id") == tid), None)
    if c is None:
        return jsonify({"error": "commande inconnue"}), 404
    ms = store.list_measurements(DB_PATH, agent_id, task="shell:%s" % tid, limit=1)
    mesure = ms[0] if ms else None
    d = (mesure or {}).get("data") or {}
    interp = None
    if d.get("statut") == "fini" and (c.get("params") or {}).get("analyse"):
        try:
            interp = shell_analyses.interpreter(c["params"]["analyse"], d.get("sortie") or "")
        except Exception:  # noqa: BLE001 -- une interprétation ratée ne doit pas masquer la sortie brute
            _log.exception("interprétation de %s", tid)
    job = _shell_job(c, mesure)
    job["script"] = (c.get("params") or {}).get("script")
    return jsonify({"job": job, "sortie": d.get("sortie") or "", "tronque": bool(d.get("tronque")), "interpretation": interp}), 200


@app.route("/postes/charge/lancer", methods=["POST"])
def postes_charge_lancer():
    """#913 : lance un test de charge poste-charge à la demande -- épreuves et paramètres choisis, suivi en direct."""
    b = request.get_json(silent=True) or {}
    agent = (b.get("agent") or "").strip()
    if not agent:
        return jsonify({"error": "agent requis"}), 400
    epreuves = [e for e in (b.get("epreuves") or ["cpu", "memoire", "disque"]) if e in ("cpu", "memoire", "disque")]
    if not epreuves:
        return jsonify({"error": "au moins une épreuve (cpu, memoire, disque)"}), 400
    def _int(cle, defaut, lo, hi):
        try:
            return max(lo, min(int(b.get(cle, defaut)), hi))
        except (TypeError, ValueError):
            return defaut
    args = ["--epreuves", ",".join(epreuves),
            "--cpu-s", str(_int("cpu_s", 120, 5, 1800)),
            "--mem-pct", str(_int("mem_pct", 60, 5, 85)),
            "--mem-max-mo", str(_int("mem_max_mo", 8192, 64, 131072)),
            "--disque-mo", str(_int("disque_mo", 2048, 16, 16384)),
            "--max-s", str(_int("max_s", 240, 10, 1800))]
    try:
        c = store.create_command(DB_PATH, agent, "run_plugin", {"id": "poste-charge", "args": args})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if c is None:  # #919 : agent inconnu -> plus de « 200 » sans commande créée
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"command": c, "agent": agent, "epreuves": epreuves, "args": args}), 200


@app.route("/postes/charge/stop", methods=["POST"])
def postes_charge_stop():
    """#913 : interrompt le test de charge en cours (l'agent pose la sentinelle d'arrêt / coupe l'épreuve)."""
    b = request.get_json(silent=True) or {}
    agent = (b.get("agent") or "").strip()
    if not agent:
        return jsonify({"error": "agent requis"}), 400
    c = store.create_command(DB_PATH, agent, "stop_plugin", {"id": "poste-charge"})
    if c is None:  # #919
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"command": c, "agent": agent}), 200


@app.route("/postes/charge/live", methods=["GET"])
def postes_charge_live():
    """#913 : tension/progression en direct (dernière mesure poste-charge-live) + dernier résultat complet."""
    agent = (request.args.get("agent") or "").strip()
    if not agent:
        return jsonify({"error": "agent requis"}), 400
    tasks = store.latest_per_task(DB_PATH, agent)
    live = tasks.get("plugin:poste-charge-live") or {}
    res = tasks.get("plugin:poste-charge") or {}
    return jsonify({"agent": agent,
                    "live": {"at": live.get("at"), "data": live.get("data")},
                    "resultat": {"at": res.get("at"), "data": res.get("data")}}), 200


@app.route("/postes/charge/historique", methods=["GET"])
def postes_charge_historique():
    """#932 : historique des tests de charge d'un poste (relevés successifs plugin:poste-charge, conservés 90 j) --
    pour consultation, comparaison et impression. ?agent= requis, ?limit= (défaut 30)."""
    agent = (request.args.get("agent") or "").strip()
    if not agent:
        return jsonify({"error": "agent requis"}), 400
    try:
        limit = max(1, min(int(request.args.get("limit") or 30), 200))
    except ValueError:
        limit = 30
    ms = store.list_measurements(DB_PATH, agent, task="plugin:poste-charge", limit=limit)
    runs = [{"at": m.get("at"), "data": m.get("data")} for m in ms if m.get("data")]
    return jsonify({"agent": agent, "historique": runs}), 200


@app.route("/nas", methods=["GET"])
def nas_route():
    """#883 : NAS relevés par SNMP (sonde nas-snmp) -> {nas: [{… relevé, relais, at}]} (dernière mesure de chaque agent)."""
    conn = store._connect(DB_PATH)
    try:
        rows = infra.latest(conn, "plugin:nas-snmp")
    finally:
        conn.close()
    out = []
    for agent_id, _h, at, d in rows:
        for n in (d or {}).get("nas") or []:
            out.append(dict(n, relais=agent_id, at=at))
    out.sort(key=lambda n: str(n.get("name")))
    return jsonify({"nas": out}), 200


@app.route("/relayed-hosts", methods=["GET"])
def relayed_hosts_route():
    """#876 : hôtes relevés à distance par un agent relais (sonde `systemes` : serveurs trop anciens pour l'agent,
    ex. Debian 4 / 5) -> {hosts: [{relay, name, role, ok, error, at, os, noyau, ips, ports}]}, affichés sous leur relais."""
    conn = store._connect(DB_PATH)
    try:
        rows = infra.latest(conn, "plugin:systemes")
    finally:
        conn.close()
    out = etat_lib.hotes_relayes(rows)
    return jsonify({"hosts": out}), 200


@app.route("/fleet", methods=["GET"])
def fleet_route():
    return jsonify({"agents": store.fleet(DB_PATH, site=request.args.get("site"), offline_after_seconds=OFFLINE_AFTER_SECONDS)}), 200


@app.route("/software-inventory", methods=["GET"])
def software_inventory_route():
    """#595 : logiciels installés par poste (plugin software-inventory), `?site=` -- lu par licenses-api."""
    return jsonify({"inventories": store.latest_software_inventory(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/site-scopes", methods=["GET"])
def site_scopes_route():
    """A1 (#620) : réglage du périmètre de site par groupe (lu par le hub pour verrouiller ses vues)."""
    return jsonify({"groups": app.config.get("SITE_SCOPE_GROUPS") or {}, "full_groups": app.config.get("SITE_SCOPE_FULL_GROUPS") or [],
                    "scope": getattr(g, "site_scope", None) if hasattr(g, "site_scope") else None}), 200


@app.route("/web-audit", methods=["GET"])
def web_audit_route():
    """#617 : dernier audit d'application web par poste (plugin web-audit), `?site=` -- matrice URL × poste."""
    rows = store.latest_web_audit(DB_PATH, site=request.args.get("site"))
    urls = sorted({u["url"] for r in rows for u in r["urls"]})
    return jsonify({"audits": rows, "urls": urls}), 200


@app.route("/windows-hosts", methods=["GET"])
def windows_hosts_route():
    """#567 : postes Windows (et autres hôtes) vus par la sonde windows-probe
    des agents (`?site=`) -- nom NetBIOS, groupe, MAC, ports (SMB, RDP,
    AnyDesk, VNC, WinRM, SSH), dialecte SMB, NLA, constats."""
    return jsonify(store.latest_windows_hosts(DB_PATH, site=request.args.get("site"))), 200


@app.route("/broadcasts", methods=["GET"])
def broadcasts_route():
    """#568 : annonces diffusées sur le segment de chaque agent (sonde
    broadcast-probe, `?site=`) : protocoles, annonceurs, constats."""
    return jsonify({"probes": store.latest_broadcasts(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/netview", methods=["GET"])
def netview_route():
    """#432 : vue réseau passive de chaque agent (dernière mesure netview)."""
    return jsonify({"netviews": store.latest_netviews(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/proxmox", methods=["GET"])
def proxmox_route():
    """#487 : dernière mesure du plugin proxmox par hyperviseur (nœud,
    VM/CT, stockages, ZFS) -- lue par la supervision SI (type « vm »)."""
    return jsonify({"proxmox": store.latest_proxmox(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/network-observability", methods=["GET"])
def network_observability_route():
    """#643 : panneau « Observabilité réseau » -- regroupe la dernière mesure
    des sondes dns-observe (105, divergences de résolution) et resource-access
    (106, qui accède à quoi) par agent, filtrable par `?site=`."""
    site = request.args.get("site")
    return jsonify({"dns": store.latest_dns_observe(DB_PATH, site=site),
                    "resources": store.latest_resource_access(DB_PATH, site=site)}), 200


@app.route("/proxmox/history", methods=["GET"])
def proxmox_history_route():
    """#504 : disponibilité des VM d'un hyperviseur (échantillons du plugin
    sur `hours`, défaut 7 jours) : taux, transitions d'état."""
    agent_id = (request.args.get("agent_id") or "").strip()
    if not agent_id:
        return jsonify({"error": "agent_id requis"}), 400
    try:
        hours = int(request.args.get("hours") or 168)
    except ValueError:
        return jsonify({"error": "hours invalide"}), 400
    return jsonify(store.proxmox_history(DB_PATH, agent_id, hours=max(1, min(hours, 24 * 90)))), 200


@app.route("/risks", methods=["GET"])
def risks_route():
    return jsonify({"risks": store.fleet_risks(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/ping", methods=["GET", "POST"])
def ping_route():
    """#868 : GET ?host=… (un hôte) ou POST {"hosts": [...]} (64 max) -> joignable / délai, ICMP puis TCP."""
    client = _client_ip()
    if request.method == "GET":
        if not ping_lib.allow(client, 1):
            return jsonify({"error": "trop de tests, réessayer dans une minute"}), 429
        return jsonify(ping_lib.ping(request.args.get("host", ""))), 200
    body = request.get_json(silent=True) or {}
    hosts = [h for h in dict.fromkeys(body.get("hosts") or []) if isinstance(h, str)][:ping_lib.MAX_BATCH]
    if not ping_lib.allow(client, max(1, len(hosts))):
        return jsonify({"error": "trop de tests, réessayer dans une minute", "results": []}), 429
    _log.info("ping : %d hôte(s) demandé(s) depuis %s", len(hosts), client)
    return jsonify({"results": ping_lib.ping_many(hosts)}), 200


@app.route("/agents", methods=["GET"])
def list_agents_route():
    return jsonify({"agents": store.list_agents(DB_PATH, site=request.args.get("site"))}), 200


@app.route("/agents", methods=["POST"])
def create_agent_route():
    body = request.get_json(silent=True) or {}
    try:
        created = store.create_agent(DB_PATH, body.get("agent_id", ""), body.get("site", ""), label=body.get("label"),
                                     host_interval_seconds=body.get("host_interval_seconds"),
                                     risk_thresholds=body.get("risk_thresholds"), notes=body.get("notes"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    created["install_command"] = _install_command(created["agent_id"], created["secret"], created["site"])
    _event("agent-enrolled", "info", "agent %s enrôlé (site %s)" % (created["agent_id"], created["site"]), agent_id=created["agent_id"])
    return jsonify(created), 201


@app.route("/agents/<agent_id>", methods=["GET"])
def get_agent_route(agent_id):
    a = store.get_agent(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    a["latest"] = store.latest_per_task(DB_PATH, agent_id)
    a["plugins"] = store.agent_plugins(DB_PATH, agent_id)
    a["commands"] = store.list_commands(DB_PATH, agent_id, limit=20)
    cfg = store.config_for_agent(DB_PATH, agent_id)
    a["config_version"] = cfg["version"] if cfg else None
    a["config_applied"] = bool(cfg and a.get("last_config_version") == cfg["version"])
    return jsonify(a), 200


@app.route("/agents/<agent_id>", methods=["PUT"])
def update_agent_route(agent_id):
    body = request.get_json(silent=True) or {}
    try:
        a = store.update_agent(DB_PATH, agent_id, label=body.get("label"), active=body.get("active"), site=body.get("site"),
                               host_interval_seconds=body.get("host_interval_seconds"),
                               risk_thresholds=body.get("risk_thresholds"), notes=body.get("notes"), publish=body.get("publish"),
                               filter_enabled=body.get("filter_enabled"), filter_group=body.get("filter_group"),  # #607
                               remote_shell=body.get("remote_shell"))  # #919
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    if body.get("remote_shell") is not None:  # #919 : changement de mode journalisé (avertissement si intervention)
        _event("remote-shell-mode", "warning" if body["remote_shell"] == "intervention" else "info",
               "commandes à distance : %s pour %s%s" % ({"off": "désactivées", "lecture": "lecture seule", "intervention": "intervention autorisée"}[body["remote_shell"]],
                                                       agent_id, (" (par %s)" % str(body.get("actor"))[:64]) if body.get("actor") else ""), agent_id=agent_id)
    if body.get("active") is not None:
        _event("agent-activated" if body["active"] else "agent-deactivated", "info" if body["active"] else "warning",
               "agent %s %s" % (agent_id, "réactivé" if body["active"] else "désactivé (requêtes refusées)"), agent_id=agent_id)
    return jsonify(a), 200


@app.route("/agents/<agent_id>", methods=["DELETE"])
def delete_agent_route(agent_id):
    purge = request.args.get("purge", "false").lower() == "true"
    if not store.delete_agent(DB_PATH, agent_id, purge_measurements=purge):
        return jsonify({"error": "agent inconnu"}), 404
    _event("agent-deleted", "warning", "agent %s supprimé" % agent_id, agent_id=agent_id)
    return jsonify({"deleted": agent_id, "measurements_purged": purge}), 200


@app.route("/agents/<agent_id>/rotate-secret", methods=["POST"])
def rotate_secret_route(agent_id):
    a = store.rotate_secret(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    a["install_command"] = _install_command(a["agent_id"], a["secret"], a["site"])
    a["package"] = package.package_info(package.find_package())
    a["download_command"] = package.download_command(PUBLIC_URL, a["package"])
    _event("secret-rotated", "warning", "secret de l'agent %s renouvelé -- réinstallation requise" % agent_id, agent_id=agent_id)
    return jsonify(a), 200


# -- blocage général et individuel (#422) ------------------------------------

def _queue_block_command(agent_id, ctype, params=None):
    """Le blocage est DÉCLARATIF (configuration, relue toutes les 5 min) ET
    IMMÉDIAT (commande relevée toutes les minutes)."""
    try:
        store.create_command(DB_PATH, agent_id, ctype, params or {})
    except ValueError:
        pass


@app.route("/block", methods=["POST"])
def block_fleet_route():
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip() or "blocage général de la flotte"
    store.set_setting(DB_PATH, "fleet_block", {"blocked": True, "reason": reason, "at": store.now_iso()})
    for a in store.list_agents(DB_PATH):
        _queue_block_command(a["agent_id"], "block_all", {"reason": reason})
    _event("fleet-blocked", "critical", "BLOCAGE GÉNÉRAL des sondes sur toute la flotte : %s" % reason, details={"reason": reason})
    return jsonify(store.fleet_block(DB_PATH)), 200


@app.route("/unblock", methods=["POST"])
def unblock_fleet_route():
    store.set_setting(DB_PATH, "fleet_block", {"blocked": False, "reason": None, "at": None})
    for a in store.list_agents(DB_PATH):
        if not a["blocked"]:
            _queue_block_command(a["agent_id"], "unblock_all")
    _event("fleet-unblocked", "warning", "blocage général levé")
    return jsonify(store.fleet_block(DB_PATH)), 200


@app.route("/agents/<agent_id>/block", methods=["POST"])
def block_agent_route(agent_id):
    body = request.get_json(silent=True) or {}
    reason = (body.get("reason") or "").strip() or "blocage depuis le tableau de bord"
    if not store.set_agent_blocked(DB_PATH, agent_id, True, reason):
        return jsonify({"error": "agent inconnu"}), 404
    _queue_block_command(agent_id, "block_all", {"reason": reason})
    _event("agent-blocked", "warning", "sondes de l'agent %s bloquées : %s" % (agent_id, reason), agent_id=agent_id)
    return jsonify(store.get_agent(DB_PATH, agent_id)), 200


@app.route("/agents/<agent_id>/unblock", methods=["POST"])
def unblock_agent_route(agent_id):
    if not store.set_agent_blocked(DB_PATH, agent_id, False):
        return jsonify({"error": "agent inconnu"}), 404
    if not store.fleet_block(DB_PATH).get("blocked"):
        _queue_block_command(agent_id, "unblock_all")
    _event("agent-unblocked", "info", "sondes de l'agent %s débloquées" % agent_id, agent_id=agent_id)
    return jsonify(store.get_agent(DB_PATH, agent_id)), 200


# -- journal d'événements (#422) ----------------------------------------------

@app.route("/events", methods=["GET"])
def events_route():
    return jsonify({"events": store.list_events(
        DB_PATH, agent_id=request.args.get("agent"), severity=request.args.get("severity"), kind=request.args.get("kind"),
        since=request.args.get("since"), limit=request.args.get("limit", 200, type=int), min_severity=request.args.get("min_severity"),
        include_muted=request.args.get("include_muted") in ("1", "true"))}), 200


# ---- #607 : filtres d'alertes (catégories, groupes de règles, réglage par agent) ----
@app.route("/alert-filters", methods=["GET"])
def alert_filters_get():
    groups = alert_groups()
    usage = {}
    for a in store.fleet(DB_PATH, offline_after_seconds=OFFLINE_AFTER_SECONDS):
        if a.get("filter_enabled"):
            usage[a.get("filter_group") or ""] = usage.get(a.get("filter_group") or "", 0) + 1
    return jsonify({"groups": groups, "categories": alertfilters.CATEGORIES, "kinds": sorted(alertfilters.KIND_CATEGORY), "weekdays": alertfilters.WEEKDAYS,
                    "tz": ALERT_TZ, "usage": usage, "default": store.get_setting(DB_PATH, "alert_filters", None) is None}), 200


@app.route("/alert-filters", methods=["PUT"])
def alert_filters_put():
    body = request.get_json(silent=True) or {}
    try:
        groups = alertfilters.normalize_groups(body.get("groups"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    store.set_setting(DB_PATH, "alert_filters", {"groups": groups})
    _event("alert-filters", "info", "filtres d'alertes : %d groupe(s) enregistré(s)" % len(groups), details={"groups": [g["id"] for g in groups]})
    return jsonify({"groups": groups}), 200


@app.route("/alert-filters/test", methods=["POST"])
def alert_filters_test():
    """{kind, at?, agent_id? | filter_group} -> l'événement serait-il filtré ? (pour régler sans attendre la nuit)"""
    body = request.get_json(silent=True) or {}
    agent = store.get_agent(DB_PATH, body.get("agent_id")) if body.get("agent_id") else None
    ag = {"filter_enabled": 1, "filter_group": body.get("filter_group")} if body.get("filter_group") else {"filter_enabled": (agent or {}).get("filter_enabled"), "filter_group": (agent or {}).get("filter_group")}
    ev = {"kind": body.get("kind") or "agent-offline", "at": body.get("at") or store.now_iso()}
    muted, why = alertfilters.evaluate(ev, alert_groups(), ag, ALERT_TZ)
    return jsonify({"muted": muted, "reason": why, "category": alertfilters.category_of(ev["kind"]), "at": ev["at"]}), 200


@app.route("/events/summary", methods=["GET"])
def events_summary_route():
    hours = max(1, min(request.args.get("hours", 24, type=int), 24 * 30))
    return jsonify(store.events_summary(DB_PATH, hours=hours, offline_after_seconds=OFFLINE_AFTER_SECONDS)), 200


@app.route("/notifications/test", methods=["POST"])
def notifications_test_route():
    body = request.get_json(silent=True) or {}
    ev = {"id": None, "at": store.now_iso(), "agent_id": None, "site": None, "source": "central", "kind": "notification-test",
          "severity": body.get("severity") or "warning", "message": body.get("message") or "test de notification depuis le hub", "details": {}}
    return jsonify(notify.send_all(ev, force=True)), 200


def _install_command(agent_id, secret, site):
    central = PUBLIC_URL or "https://<VM>:6443/api/si-agent"
    ca = _ca_info()
    tls = (" --ca-fingerprint %s" % ca["sha256"]) if ca.get("sha256") else " --ca /chemin/ca.crt"
    return "sudo ./install.sh --agent %s --secret %s --central %s --site %s%s" % (
        shlex.quote(agent_id), shlex.quote(secret), shlex.quote(central), shlex.quote(site or "default"), tls)


def _install_command_docker(agent_id, secret, site):
    """Variante conteneur (#430, archive si-agent-agent-<version>.tar.gz)."""
    return _install_command(agent_id, secret, site).replace("sudo ./install.sh", "sudo ./docker/deploy-docker.sh", 1)


def _install_command_macos(agent_id, secret, site):
    """Variante macOS (#451, même archive) : install-macos.sh installe un
    LaunchDaemon (compte root, au démarrage)."""
    return _install_command(agent_id, secret, site).replace("sudo ./install.sh", "sudo ./install-macos.sh", 1)


def _ps_quote(s):
    """Guillemets doubles : compris par PowerShell ET par cmd.exe (les
    simples restent littéraux sous cmd) ; l'identifiant, le secret et
    l'URL ne contiennent ni `"` ni `$` (retirés par prudence)."""
    return '"' + re.sub(r'["$`]', "", str(s)) + '"'


def _win_tls_fallback(central):
    """#905 : argument(s) TLS d'install.ps1 pour `central` (URL principale), avec itinérance si une adresse interne
    distincte est connue (SI_AGENT_INTERNAL_URL). L'agent bascule seul entre principal et secours (#474).
    - principal public + interne connu -> principal magasin système (-SystemCa), CA interne épinglée pour le
      secours interne (-Fallback) : le portable passe du nom public (Internet) à l'adresse LAN tout seul ;
    - principal interne -> CA interne épinglée (-CaFingerprint), secours public si distinct ;
    - sinon -> magasin système."""
    sha = _ca_info().get("sha256")
    pub_central = not _pin_internal_ca(central)
    if pub_central and INTERNAL_URL and INTERNAL_URL != central and _pin_internal_ca(INTERNAL_URL) and sha:
        return " -SystemCa -CaFingerprint %s -Fallback %s" % (sha, INTERNAL_URL)
    if not pub_central:
        tls = (" -CaFingerprint %s" % sha) if sha else " -Ca C:\\chemin\\ca.crt"
        if PUBLIC_URL and PUBLIC_URL != central and not _pin_internal_ca(PUBLIC_URL):
            tls += " -Fallback %s" % PUBLIC_URL
        return tls
    return " -SystemCa"


def _install_command_windows(agent_id, secret, site):
    """Variante Windows 10/11 (#440, même archive). #446 : passe par
    `powershell -ExecutionPolicy Bypass -File` -- un poste Windows refuse
    les scripts par défaut (politique Restricted) et un double-clic ouvre
    le .ps1 dans le Bloc-notes ; `windows/install.cmd` fait la même chose
    avec élévation automatique en administrateur."""
    central = PUBLIC_URL or "https://<VM>:6443/api/si-agent"
    return "powershell -NoProfile -ExecutionPolicy Bypass -File .\\windows\\install.ps1 -Agent %s -Secret %s -Central %s -Site %s%s" % (
        _ps_quote(agent_id), _ps_quote(secret), _ps_quote(central), _ps_quote(site or "default"), _win_tls_fallback(central))


def _ascii(s):
    import unicodedata
    return unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode()


def _install_cmd_windows(agent_id, secret, site):
    """#446 bis : fichier `.cmd` SILENCIEUX propre à l'agent -- valeurs
    incluses, élévation UAC, install.ps1 sans question (sortie dans un
    journal), « OK » à la fin puis le fichier s'efface (il contient le
    secret) ; en erreur, le journal est affiché et la fenêtre reste
    ouverte. #899 : se suffit à lui-même -- archive décompressée à côté
    utilisée si présente, sinon téléchargée depuis le central (curl.exe,
    empreinte SHA-256 inscrite ici) et décompressée (tar) ; double-cliquer. ASCII seul (cmd.exe lit la page de
    code OEM) ; l'empreinte de la CA interne est obligatoire (jamais
    `-Insecure` en silence)."""
    ca = _ca_info()
    central = _ascii(PUBLIC_URL or "https://<VM>:6443/api/si-agent")
    interne = _pin_internal_ca(central)
    if interne and not ca.get("sha256"):
        return None   # central interne sans CA épinglée : pas d'installation silencieuse (jamais -Insecure)
    aid, sec, st = _ascii(agent_id), _ascii(secret), _ascii(site or "default")
    for v in (aid, sec, central, st):
        if re.search(r'["%!^&<>|]', v):
            return None
    pkg = package.package_info(package.find_package()) or {}
    sha = re.sub(r"[^0-9A-Fa-f]", "", str(pkg.get("sha256") or "")).upper()
    lines = [
        "@echo off",
        "rem si-agent -- installation silencieuse de l'agent %s (fichier genere par le central, contient le secret : s'efface apres succes)." % aid,
        "rem #899 : se suffit a lui-meme -- double-cliquer (UAC une fois) ; l'archive de l'agent est utilisee si elle est deja decompressee a cote, sinon telechargee depuis le central et verifiee (SHA-256).",
        "setlocal",
        # élévation d'abord : l'instance administrateur refait tout le reste
        "net session >nul 2>&1",
        'if not "%errorlevel%"=="0" (',
        '  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath \'%~f0\' -Verb RunAs"',
        "  exit /b",
        ")",
        'cd /d "%~dp0"',
        'set "PS1=%~dp0windows\\install.ps1"',
        'if not exist "%PS1%" set "PS1=%~dp0install.ps1"',
        # #898 : archive décompressée à côté, ou dossier en double créé par l'Explorateur
        'if not exist "%PS1%" for /d %%D in ("%~dp0si-agent-agent-*") do if exist "%%D\\windows\\install.ps1" set "PS1=%%D\\windows\\install.ps1"',
        'if not exist "%PS1%" for /d %%D in ("%~dp0si-agent-agent-*") do for /d %%E in ("%%D\\si-agent-agent-*") do if exist "%%E\\windows\\install.ps1" set "PS1=%%E\\windows\\install.ps1"',
        'if exist "%PS1%" goto :pret',
        # #899 : sinon, téléchargement depuis le central (curl.exe et tar sont livrés avec Windows 10 / 11)
        'set "WORK=%TEMP%\\si-agent-pkg"',
        'if exist "%WORK%" rmdir /s /q "%WORK%"',
        'mkdir "%WORK%"',
        "echo Telechargement de l'agent depuis %s ..." % central,
        'curl.exe -fsSk -o "%%WORK%%\\agent.tgz" "%s/package"' % central,
        'if not "%errorlevel%"=="0" ( echo ERREUR : telechargement impossible depuis le central. & pause & exit /b 1 )',
    ] + ([
        # -k ci-dessus (CA interne non encore installée) : l'intégrité est garantie par l'empreinte inscrite ici par le central
        'powershell -NoProfile -Command "if ((Get-FileHash \'%%WORK%%\\agent.tgz\' -Algorithm SHA256).Hash -ne \'%s\') { exit 1 }"' % sha,
        'if not "%errorlevel%"=="0" ( echo ERREUR : archive alteree ^(empreinte SHA-256 differente^) -- installation abandonnee. & pause & exit /b 1 )',
    ] if sha else []) + [
        'tar -xzf "%WORK%\\agent.tgz" -C "%WORK%"',
        'for /d %%D in ("%WORK%\\si-agent-agent-*") do if exist "%%D\\windows\\install.ps1" set "PS1=%%D\\windows\\install.ps1"',
        'if not exist "%PS1%" ( echo ERREUR : install.ps1 introuvable apres telechargement. & pause & exit /b 1 )',
        ":pret",
        'set "LOG=%TEMP%\\si-agent-install.log"',
        'powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "%%PS1%%" -Agent "%s" -Secret "%s" -Central "%s" -Site "%s" %s -PythonUrl "%s/deploy/python" > "%%LOG%%" 2>&1' % (aid, sec, central, st, _win_tls_fallback(central).strip(), central),
        'if not "%errorlevel%"=="0" goto :erreur',
        "echo OK - agent %s installe et demarre (journal : %%LOG%%)" % aid,
        "timeout /t 10 >nul",
        '(goto) 2>nul & del "%~f0"',
        ":erreur",
        "echo ERREUR (code %errorlevel%) - journal %LOG% :",
        'type "%LOG%"',
        "pause",
        "exit /b 1",
    ]
    return "\r\n".join(lines) + "\r\n"


@app.route("/agents/<agent_id>/install.cmd", methods=["GET"])
def install_cmd_route(agent_id):
    """Le `.cmd` silencieux de l'agent (même exposition du secret que
    /install : réservée au hub). 409 sans CA interne."""
    a = store.get_agent(DB_PATH, agent_id, with_secret=True)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    body = _install_cmd_windows(agent_id, a["secret"], a["site"])
    if body is None:
        return jsonify({"error": "CA interne absente (empreinte requise pour une installation silencieuse) ou caractère interdit dans l'identifiant, le site ou l'URL"}), 409
    return Response(body, mimetype="text/plain", headers={"Content-Disposition": 'attachment; filename="si-agent-install-%s.cmd"' % re.sub(r"[^A-Za-z0-9_.-]", "_", agent_id)})


# ---- #899 : installation depuis l'accueil du hub, sans authentification (fenêtre ouverte par un administrateur) --
import accueil as _accueil
_ACCUEIL_LIMITE = _accueil.Limiteur(n=10, fenetre_s=600)


@app.route("/agents/<agent_id>/accueil", methods=["GET", "PUT"])
def agent_accueil_route(agent_id):
    """Hub (administrateur) : état ou ouverture / fermeture ({heures: 24 | 0}) de l'installation depuis l'accueil."""
    a = store.get_agent(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    if request.method == "PUT":
        heures = (request.get_json(silent=True) or {}).get("heures", 24)
        try:
            heures = float(heures)
        except (TypeError, ValueError):
            return jsonify({"error": "heures : nombre attendu"}), 400
        store.set_setting(DB_PATH, _accueil.CLE, _accueil.ouvrir(store.get_setting(DB_PATH, _accueil.CLE, {}), agent_id, heures))
        _event("accueil-installation", "info", "installation sans connexion %s pour l'agent %s" % ("ouverte %g h" % heures if heures > 0 else "fermée", agent_id), agent_id=agent_id)
    etat = store.get_setting(DB_PATH, _accueil.CLE, {}) or {}
    ouvert, motif = _accueil.statut(etat, agent_id, a)
    f = etat.get(agent_id) or {}
    return jsonify({"agent_id": agent_id, "ouvert": ouvert, "motif": motif,
                    "jusqua": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(f["jusqua"])) if f.get("jusqua") else None}), 200


def _accueil_agent():
    """Contrôles communs des deux routes publiques -> (agent avec secret, None) ou (None, réponse d'erreur)."""
    ip = _client_ip()
    if not _ACCUEIL_LIMITE.accepte(ip):
        return None, (jsonify({"error": "trop de demandes : réessayer dans quelques minutes"}), 429)
    nom = (request.args.get("nom") or "").strip()
    if not _accueil.NOM.match(nom):
        return None, (jsonify({"error": "nom de poste invalide"}), 400)
    a = store.get_agent(DB_PATH, nom, with_secret=True)
    ouvert, motif = _accueil.statut(store.get_setting(DB_PATH, _accueil.CLE, {}) or {}, nom, a)
    if not ouvert:
        _log.warning("accueil : installation refusée pour « %s » depuis %s (%s)", nom, ip, motif)
        # même réponse que l'agent existe ou non : le nom d'un agent ne se devine pas par l'accueil
        return None, (jsonify({"error": "aucune installation ouverte pour ce nom : demander à un administrateur de l'ouvrir dans le hub (fiche de l'agent › Installation)"}), 404)
    _event("accueil-installation-lue", "warning", "éléments d'installation de l'agent %s remis depuis l'accueil (sans connexion) à %s" % (nom, ip), agent_id=nom)
    return a, None


@app.route("/accueil/agent", methods=["GET"])
def accueil_agent_route():
    """PUBLIC (#899) : ?nom= -> éléments d'installation de l'agent si son installation est ouverte."""
    a, err = _accueil_agent()
    if err:
        return err
    aid = a["agent_id"]
    return jsonify({"agent_id": aid, "site": a["site"], "secret": a["secret"], "central_url": PUBLIC_URL or None,
                    "package": package.package_info(package.find_package()),
                    "install_command": _install_command(aid, a["secret"], a["site"]),
                    "install_command_windows": _install_command_windows(aid, a["secret"], a["site"]),
                    "install_command_macos": _install_command_macos(aid, a["secret"], a["site"]),
                    "install_cmd_available": _install_cmd_windows(aid, a["secret"], a["site"]) is not None}), 200


@app.route("/accueil/agent.cmd", methods=["GET"])
def accueil_agent_cmd_route():
    """PUBLIC (#899) : ?nom= -> le .cmd silencieux de l'agent si son installation est ouverte."""
    a, err = _accueil_agent()
    if err:
        return err
    body = _install_cmd_windows(a["agent_id"], a["secret"], a["site"])
    if body is None:
        return jsonify({"error": "fichier .cmd indisponible (CA interne absente ou caractère interdit)"}), 409
    return Response(body, mimetype="text/plain", headers={"Content-Disposition": 'attachment; filename="si-agent-install-%s.cmd"' % re.sub(r"[^A-Za-z0-9_.-]", "_", a["agent_id"])})


@app.route("/agents/<agent_id>/install", methods=["GET"])
def install_route(agent_id):
    """Secret + commande d'installation prête à coller sur l'hôte -- la
    seule lecture qui renvoie le secret (même logique que
    netprobe /provision)."""
    a = store.get_agent(DB_PATH, agent_id, with_secret=True)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "secret": a["secret"], "site": a["site"],
                    "central_url": PUBLIC_URL or None,
                    "package": package.package_info(package.find_package()),
                    "download_command": package.download_command(PUBLIC_URL, package.package_info(package.find_package())),
                    "install_command": _install_command(agent_id, a["secret"], a["site"]),
                    "install_command_docker": _install_command_docker(agent_id, a["secret"], a["site"]),
                    "install_command_windows": _install_command_windows(agent_id, a["secret"], a["site"]),
                    "install_command_macos": _install_command_macos(agent_id, a["secret"], a["site"]),
                    "install_cmd_available": _install_cmd_windows(agent_id, a["secret"], a["site"]) is not None,
                    "agent_json": {"agent_id": agent_id, "secret": a["secret"], "site": a["site"],
                                   "central_url": PUBLIC_URL or "https://<VM>:6443/api/si-agent"}}), 200


@app.route("/agents/<agent_id>/measurements", methods=["GET"])
def agent_measurements_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "measurements": store.list_measurements(
        DB_PATH, agent_id, task=request.args.get("task"), limit=request.args.get("limit", 200, type=int),
        since=request.args.get("since"))}), 200


@app.route("/agents/<agent_id>/latest", methods=["GET"])
def agent_latest_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "latest": store.latest_per_task(DB_PATH, agent_id)}), 200


@app.route("/agents/<agent_id>/config-preview", methods=["GET"])
def config_preview_route(agent_id):
    """Ce que l'agent recevra (sans les corps de scripts ni signatures)."""
    cfg = store.config_for_agent(DB_PATH, agent_id)
    if cfg is None:
        return jsonify({"error": "agent inconnu"}), 404
    cfg["plugins"] = [{k: v for k, v in p["manifest"].items() if k != "signature"} for p in cfg["plugins"]]
    return jsonify(cfg), 200


# -- plugins : catalogue et affectations --------------------------------

@app.route("/plugins", methods=["GET"])
def list_plugins_route():
    return jsonify({"plugins": store.list_plugins(DB_PATH)}), 200


@app.route("/plugins", methods=["POST"])
def create_plugin_route():
    body = request.get_json(silent=True) or {}
    manifest = body.get("manifest") if isinstance(body.get("manifest"), dict) else {
        k: body.get(k) for k in ("id", "version", "runner", "entry", "interval_seconds", "timeout_seconds", "args", "description",
                                 "privileged", "max_memory_mb") if k in body}
    try:
        p = store.upsert_plugin(DB_PATH, manifest, body.get("body"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _event("plugin-catalogued", "warning" if p.get("privileged") else "info",
           "sonde %s v%s enregistrée au catalogue%s" % (p["id"], p["version"], " (PRIVILÉGIÉE : tourne en root)" if p.get("privileged") else ""),
           details={"plugin": p["id"], "version": p["version"], "sha256": p["sha256"], "privileged": p.get("privileged"), "assigned_agents": p.get("assigned_agents", 0)})
    return jsonify(p), 201


@app.route("/plugins/<plugin_id>", methods=["GET"])
def get_plugin_route(plugin_id):
    p = store.get_plugin(DB_PATH, plugin_id, with_body=request.args.get("body", "false").lower() == "true")
    if p is None:
        return jsonify({"error": "plugin inconnu"}), 404
    return jsonify(p), 200


@app.route("/plugins/<plugin_id>", methods=["DELETE"])
def delete_plugin_route(plugin_id):
    if not store.delete_plugin(DB_PATH, plugin_id):
        return jsonify({"error": "plugin inconnu"}), 404
    _event("plugin-uncatalogued", "warning", "sonde %s retirée du catalogue (désinstallation chez les agents affectés)" % plugin_id, details={"plugin": plugin_id})
    return jsonify({"deleted": plugin_id}), 200


@app.route("/agents/<agent_id>/plugins", methods=["GET"])
def agent_plugins_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "plugins": store.agent_plugins(DB_PATH, agent_id)}), 200


@app.route("/agents/<agent_id>/plugins/<plugin_id>", methods=["PUT"])
def assign_plugin_route(agent_id, plugin_id):
    body = request.get_json(silent=True) or {}
    existing = {p["id"]: p for p in store.agent_plugins(DB_PATH, agent_id)}
    prev = existing.get(plugin_id)
    try:
        res = store.assign_plugin(DB_PATH, agent_id, plugin_id, enabled=body.get("enabled", prev["enabled"] if prev else True))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if res is None:
        return jsonify({"error": "agent inconnu"}), 404
    if "blocked" in body:
        blocked = bool(body["blocked"])
        store.set_plugin_blocked(DB_PATH, agent_id, plugin_id, blocked, body.get("reason"))
        if not prev or prev["blocked"] != blocked:
            _queue_block_command(agent_id, "block_plugin" if blocked else "unblock_plugin", {"id": plugin_id, "reason": body.get("reason")})
            _event("plugin-blocked" if blocked else "plugin-unblocked", "warning" if blocked else "info",
                   "sonde %s %s sur l'agent %s%s" % (plugin_id, "bloquée" if blocked else "débloquée", agent_id, (" : " + body["reason"]) if body.get("reason") else ""),
                   agent_id=agent_id, details={"plugin": plugin_id})
        res = store.agent_plugins(DB_PATH, agent_id)
    elif prev is None:
        _event("plugin-assigned", "info", "sonde %s affectée à l'agent %s" % (plugin_id, agent_id), agent_id=agent_id, details={"plugin": plugin_id})
    return jsonify({"agent_id": agent_id, "plugins": res}), 200


@app.route("/agents/<agent_id>/plugins/<plugin_id>", methods=["DELETE"])
def unassign_plugin_route(agent_id, plugin_id):
    if not store.unassign_plugin(DB_PATH, agent_id, plugin_id):
        return jsonify({"error": "affectation inconnue"}), 404
    _event("plugin-unassigned", "info", "sonde %s retirée de l'agent %s" % (plugin_id, agent_id), agent_id=agent_id, details={"plugin": plugin_id})
    return jsonify({"agent_id": agent_id, "plugins": store.agent_plugins(DB_PATH, agent_id)}), 200


# -- commandes -------------------------------------------------------------

@app.route("/agents/<agent_id>/commands", methods=["GET"])
def list_commands_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    return jsonify({"agent_id": agent_id, "commands": store.list_commands(
        DB_PATH, agent_id, status=request.args.get("status"), limit=request.args.get("limit", 50, type=int))}), 200


@app.route("/agents/<agent_id>/commands", methods=["POST"])
def create_command_route(agent_id):
    body = request.get_json(silent=True) or {}
    try:
        c = store.create_command(DB_PATH, agent_id, body.get("type"), body.get("params"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    if c is None:
        return jsonify({"error": "agent inconnu"}), 404
    _log.info("commande %s (%s) créée pour %s", c["id"], c["type"], agent_id)
    open_interactive(agent_id, 120)                    # #709 : la suite d'une action depuis le hub arrive vite
    if c["type"] in control.BLOCK_COMMANDS:
        _event("command-block", "warning", "commande %s envoyée à l'agent %s" % (c["type"], agent_id), agent_id=agent_id, details={"command": c["id"], "params": c["params"]})
    return jsonify(c), 201


# -- #522 : mises à jour contrôlées ------------------------------------------

def _updates_settings():
    return updates.normalize_settings(store.get_setting(DB_PATH, "updates", None))


def _updates_plan(settings=None):
    settings = settings or _updates_settings()
    pkg = package.package_info(package.find_package())
    agents = store.list_agents(DB_PATH)
    last = {a["agent_id"]: store.last_command(DB_PATH, a["agent_id"], "update") for a in agents}
    return pkg, settings, updates.plan(agents, pkg, settings, last)


def _schedule_updates(only_agent=None, actor="central"):
    """Crée les commandes `update` pour les agents éligibles ; [(agent, commande)]."""
    pkg, settings, planned = _updates_plan()
    created = []
    if not pkg:
        return created
    for aid in updates.to_schedule(planned):
        if only_agent and aid != only_agent:
            continue
        c = store.create_command(DB_PATH, aid, "update", updates.command_params(pkg))
        if c:
            created.append((aid, c["id"]))
            _event("update-scheduled", "info", "mise à jour %s → %s planifiée pour l'agent %s (%s)" % (
                next((p["version"] for p in planned if p["agent_id"] == aid), "?"), pkg["version"], aid, actor), agent_id=aid,
                details={"command": c["id"], "to": pkg["version"], "by": actor})
    return created


# ============================================================
# #822 : diffusions en cascade -- règles (cible + étapes ordonnées par dépendances), plan par agent, gestes
# ============================================================

def _diffusions():
    return store.get_setting(DB_PATH, "diffusions", None) or []


def _diffusion_plan(regle):
    pkg = package.package_info(package.find_package())

    def ctx(aid):
        return ({p_["id"]: p_ for p_ in store.agent_plugins(DB_PATH, aid)}, store.latest_per_task(DB_PATH, aid),
                store.last_command(DB_PATH, aid, "update"))
    return pkg, diffusion.planifier(regle, store.fleet(DB_PATH), ctx, (pkg or {}).get("version"))


def _diffusion_executer(regle, actor):
    """Fait les gestes « à faire » d'une règle ; [(agent, étape, résultat)]."""
    pkg, plan = _diffusion_plan(regle)
    faits = []
    for aid, e in plan["gestes"]:
        if e["type"] == "mise_a_jour":
            if not pkg:
                continue
            c = store.create_command(DB_PATH, aid, "update", updates.command_params(pkg))
            res = "commande %s" % (c or {}).get("id")
            _event("update-scheduled", "info", "diffusion « %s » : mise à jour -> %s planifiée pour l'agent %s (%s)" % (regle["nom"], pkg["version"], aid, actor),
                   agent_id=aid, details={"command": (c or {}).get("id"), "to": pkg["version"], "by": actor, "diffusion": regle.get("id")})
        else:
            on = e["type"] == "activer_sonde"
            store.assign_plugin(DB_PATH, aid, e["sonde"], enabled=on)
            res = "sonde %s %s" % (e["sonde"], "activée" if on else "désactivée")
            _event("plugin-assigned" if on else "plugin-disabled", "info", "diffusion « %s » : %s sur l'agent %s (%s)" % (regle["nom"], res, aid, actor),
                   agent_id=aid, details={"plugin": e["sonde"], "by": actor, "diffusion": regle.get("id")})
        faits.append({"agent_id": aid, "etape": e["id"], "resultat": res})
    return faits


_diff_verrou = {"t": 0}


def _diffusions_auto():
    if time.time() - _diff_verrou["t"] < 120:
        return
    _diff_verrou["t"] = time.time()
    import fcntl
    with open(DB_PATH + ".diffusions.lock", "a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return   # un autre worker s'en charge
        for r in _diffusions():
            if r.get("actif") and r.get("auto"):
                _diffusion_executer(r, "automatique")


# ============================================================
# #825 : banc d'installation des agents sur un pool de VM (BACKLOG 133)
# ============================================================

def _orch_vms_tick(maintenant=None):   # #836
    orchestration.vms_tick(maintenant)


def _banc_runs():
    return store.get_setting(DB_PATH, "banc_runs", None) or []


def _banc_tick(maintenant=None):
    """Fait avancer les passages en cours (un seul worker, verrou de fichier)."""
    import fcntl
    pool = store.get_setting(DB_PATH, "banc_pool", None)
    runs = _banc_runs()
    if not pool or not any(not r.get("fin") for r in runs):
        return
    with open(DB_PATH + ".banc.lock", "a") as fh:
        try:
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            return
        runs = _banc_runs()
        t = maintenant or time.time()
        for r in runs:
            for _ in range(len(banc.ETAPES)):      # plusieurs étapes sans attente peuvent s'enchaîner dans un même passage
                if r.get("fin"):
                    break
                st = r["etapes"][r["etape"]]
                c = store.get_command(DB_PATH, st["commande"]) if st["commande"] else None
                avant = (r["etape"], st["commande"])
                r, geste = banc.avancer(r, c, t)
                if geste == "envoyer":
                    params = banc.params_etape(r, pool)
                    if params is None:
                        banc.sauter(r, t)
                        continue
                    cmd = store.create_command(DB_PATH, pool["noeud"], "vm_action", params)
                    r["etapes"][r["etape"]]["commande"] = (cmd or {}).get("id")
                    if not cmd:
                        banc._echouer(r, "commande refusée par le central (agent du nœud inconnu ?)", t)
                    break
                if (r["etape"], r["etapes"][r["etape"]]["commande"] if not r.get("fin") else None) == avant:
                    break
            if r.get("fin") and not r.get("signale"):
                r["signale"] = True
                _event("banc-run", "info" if not r.get("echec") else "warning", "banc d'installation %s (%s) : %s" % (r["nom"], r["os"], banc.resultat(r)),
                       agent_id=pool["noeud"], details={"run": r["id"], "modele": r["modele"], "echec": r.get("echec")})
        store.set_setting(DB_PATH, "banc_runs", runs[-100:])


@app.route("/mailbox", methods=["GET"])
def mailbox_route():
    """#840 : agents si-mailbox reliés (sonde « mailbox » des postes) -- résumés sans contenu de messages."""
    out = []
    for a in store.fleet(DB_PATH):
        m = store.latest_per_task(DB_PATH, a["agent_id"]).get("plugin:mailbox")
        for p in (((m or {}).get("data") or {}).get("postes") or []):
            out.append(dict(p, agent_id=a["agent_id"], releve=(m or {}).get("at")))
    return jsonify({"postes": out}), 200


@app.route("/banc", methods=["GET"])
def banc_route():
    runs = _banc_runs()
    for r in runs:
        r["resultat"] = banc.resultat(r)
    pool = store.get_setting(DB_PATH, "banc_pool", None)
    noeud = (pool or {}).get("noeud")
    modeles_noeud, fabrications = [], []
    if noeud and store.get_agent(DB_PATH, noeud):
        modeles_noeud = banc.modeles_du_noeud((((store.latest_per_task(DB_PATH, noeud).get("plugin:proxmox") or {}).get("data")) or {}).get("vms"))
        fabrications = [{"id": c["id"], "status": c["status"], "params": c["params"], "created_at": c.get("created_at"),
                         "error": (c.get("result") or {}).get("error"), "stdout": ((c.get("result") or {}).get("result") or {}).get("stdout")}
                        for c in store.list_commands(DB_PATH, noeud, limit=200) if c["type"] == "banc_modele"][:20]
    return jsonify({"recettes": banc.recettes(), "modeles_noeud": modeles_noeud, "fabrications": fabrications,
                    "pool": banc.pool_public(pool), "runs": list(reversed(runs)),
                    "etapes": [{"id": e, "libelle": banc.LIBELLES[e]} for e in banc.ETAPES],
                    "verifier": banc.VERIFIER, "desinstaller": banc.DESINSTALLER}), 200


@app.route("/banc/modeles", methods=["POST"])
def banc_modele_route():
    """#826 : fabriquer un modèle de VM Linux sur le nœud du pool (image cloud vérifiée -> template)."""
    body = request.get_json(silent=True) or {}
    pool = store.get_setting(DB_PATH, "banc_pool", None) or {}
    noeud = str(body.get("noeud") or pool.get("noeud") or "")
    if store.get_agent(DB_PATH, noeud) is None:
        return jsonify({"error": "agent du nœud inconnu : %r (régler d'abord le pool ou préciser noeud)" % noeud}), 400
    v, err = banc.bancmod.valider(body)
    if err:
        return jsonify({"error": err}), 400
    if pool and pool["vmid_min"] <= v["vmid"] <= pool["vmid_max"]:
        return jsonify({"error": "vmid dans la plage des clones du pool"}), 400
    c = store.create_command(DB_PATH, noeud, "banc_modele", v)
    _event("banc-modele", "info", "modèle de banc %s demandé sur %s (vmid %d)" % (v["recette"], noeud, v["vmid"]), agent_id=noeud,
           details={"command": (c or {}).get("id"), "recette": v["recette"], "vmid": v["vmid"]})
    return jsonify({"commande": (c or {}).get("id"), "noeud": noeud, "parametres": v}), 201


@app.route("/banc/pool", methods=["PUT"])
def banc_pool_route():
    body = request.get_json(silent=True) or {}
    ancien = store.get_setting(DB_PATH, "banc_pool", None) or {}
    for o in ("linux", "windows"):   # commande masquée renvoyée telle quelle par le hub : on garde l'ancienne
        c = ((body.get("commandes") or {}).get(o) or {})
        for k in ("installer", "verifier", "desinstaller"):
            if "•••" in str(c.get(k) or ""):
                c[k] = ((ancien.get("commandes") or {}).get(o) or {}).get(k, "")
    pool, err = banc.valider_pool(body)
    if err:
        return jsonify({"error": err}), 400
    if store.get_agent(DB_PATH, pool["noeud"]) is None:
        return jsonify({"error": "agent du nœud inconnu : %s" % pool["noeud"]}), 400
    store.set_setting(DB_PATH, "banc_pool", pool)
    return jsonify(banc.pool_public(pool)), 200


@app.route("/banc/runs", methods=["POST"])
def banc_lancer_route():
    pool = store.get_setting(DB_PATH, "banc_pool", None)
    if not pool:
        return jsonify({"error": "pool non configuré"}), 400
    body = request.get_json(silent=True) or {}
    noms = body.get("modeles") or [m["nom"] for m in pool["modeles"]]
    runs = _banc_runs()
    crees = []
    for m in pool["modeles"]:
        if m["nom"] not in noms:
            continue
        utilises = {r["vmid"] for r in runs if not r.get("fin")}
        rid = max([r["id"] for r in runs] or [0]) + 1
        r, err = banc.nouveau_run(pool, m, rid, utilises, time.time())
        if err:
            return jsonify({"error": err, "crees": crees}), 409
        runs.append(r)
        crees.append(r["nom"])
    store.set_setting(DB_PATH, "banc_runs", runs[-100:])
    return jsonify({"crees": crees}), 201


@app.route("/banc/runs/<int:rid>/arreter", methods=["POST"])
def banc_arreter_route(rid):
    runs = _banc_runs()
    r = next((x for x in runs if x["id"] == rid), None)
    if not r:
        return jsonify({"error": "passage inconnu"}), 404
    if not r.get("fin") and r["etape"] < banc.NETTOYAGE:
        banc._echouer(r, "arrêté à la main", time.time())
        store.set_setting(DB_PATH, "banc_runs", runs)
    return jsonify({"ok": True}), 200


@app.route("/banc/runs", methods=["DELETE"])
def banc_purger_route():
    store.set_setting(DB_PATH, "banc_runs", [r for r in _banc_runs() if not r.get("fin")])
    return jsonify({"ok": True}), 200


@app.route("/diffusions", methods=["GET"])
def diffusions_route():
    out = []
    for r in _diffusions():
        pkg, plan = _diffusion_plan(r)
        out.append(dict(r, plan=plan["agents"], gestes=len(plan["gestes"])))
    pkg = package.package_info(package.find_package())
    return jsonify({"diffusions": out, "types": diffusion.TYPES, "exemple": diffusion.EXEMPLE, "version_servie": (pkg or {}).get("version"),
                    "sondes": sorted(p_["id"] for p_ in store.list_plugins(DB_PATH))}), 200


@app.route("/diffusions", methods=["POST"])
@app.route("/diffusions/<int:did>", methods=["PUT"])
def diffusion_ecrire_route(did=None):
    regle, err = diffusion.valider(request.get_json(silent=True) or {}, {p_["id"] for p_ in store.list_plugins(DB_PATH)})
    if err:
        return jsonify({"error": err}), 400
    lst = _diffusions()
    if did is None:
        regle["id"] = max([r["id"] for r in lst] or [0]) + 1
        lst.append(regle)
    else:
        if not any(r["id"] == did for r in lst):
            return jsonify({"error": "diffusion inconnue"}), 404
        regle["id"] = did
        lst = [regle if r["id"] == did else r for r in lst]
    store.set_setting(DB_PATH, "diffusions", lst)
    return jsonify(regle), 201 if did is None else 200


@app.route("/diffusions/<int:did>", methods=["DELETE"])
def diffusion_supprimer_route(did):
    lst = _diffusions()
    if not any(r["id"] == did for r in lst):
        return jsonify({"error": "diffusion inconnue"}), 404
    store.set_setting(DB_PATH, "diffusions", [r for r in lst if r["id"] != did])
    return jsonify({"ok": True}), 200


@app.route("/diffusions/<int:did>/executer", methods=["POST"])
def diffusion_executer_route(did):
    r = next((x for x in _diffusions() if x["id"] == did), None)
    if not r:
        return jsonify({"error": "diffusion inconnue"}), 404
    body = request.get_json(silent=True) or {}
    if body.get("simulation"):
        _pkg, plan = _diffusion_plan(r)
        return jsonify({"simulation": True, "gestes": [{"agent_id": a, "etape": e["id"], "type": e["type"], "sonde": e.get("sonde")} for a, e in plan["gestes"]]}), 200
    return jsonify({"faits": _diffusion_executer(r, (body.get("actor") or "bouton")[:64])}), 200


@app.route("/updates", methods=["GET"])
def updates_route():
    pkg, settings, planned = _updates_plan()
    return jsonify(dict(updates.summary(planned, pkg, settings), agents=planned)), 200


@app.route("/updates", methods=["PUT"])
def updates_put_route():
    body = request.get_json(silent=True) or {}
    current = _updates_settings()
    for k in ("beta_agents", "general_enabled", "auto", "retry_after_s"):
        if k in body:
            current[k] = body[k]
    current["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    current["updated_by"] = (body.get("actor") or request.args.get("actor") or "")[:64] or None
    settings = updates.normalize_settings(current)
    store.set_setting(DB_PATH, "updates", settings)
    _event("update-settings", "info", "déploiement des mises à jour : canal bêta %s, activation générale %s, auto %s" % (
        ", ".join(settings["beta_agents"]) or "vide", "oui" if settings["general_enabled"] else "non", "oui" if settings["auto"] else "non"),
        details={"by": settings["updated_by"]})
    created = _schedule_updates(actor=settings["updated_by"] or "réglages") if settings["auto"] else []
    pkg, settings, planned = _updates_plan(settings)
    return jsonify(dict(updates.summary(planned, pkg, settings), agents=planned, scheduled=[a for a, _ in created])), 200


@app.route("/updates/apply", methods=["POST"])
def updates_apply_route():
    body = request.get_json(silent=True) or {}
    created = _schedule_updates(only_agent=body.get("agent_id"), actor=(body.get("actor") or "bouton")[:64])
    pkg, settings, planned = _updates_plan()
    return jsonify(dict(updates.summary(planned, pkg, settings), agents=planned, scheduled=[a for a, _ in created])), 200


# ============================================================
# #653 : plans PRA / opérations PVE (séquences de vm_action, simulation puis exécution)
# ============================================================

# ============================================================
# #743 : tournées de mesures réparties (supervision distribuée, item 120)
# ============================================================

@app.route("/rotations", methods=["GET"])
def rotations_route():
    now = int(time.time())
    out = []
    for p_ in rotation.list_plans(DB_PATH):
        runs = rotation.list_runs(DB_PATH, p_["id"], 500)
        p_["coverage_24h"] = rotation.coverage(runs, p_, now - 86400, now)
        p_["next"] = [{"at": t, "agent": a or rotation.choose_agent(p_, t, set(p_["agents"]))[0]} for t, a in rotation.slots(p_, now, now + 2 * p_["period_seconds"])][:6]
        out.append(p_)
    return jsonify({"rotations": out, "now": now}), 200


def _rotation_body():
    body = request.get_json(silent=True) or {}
    return rotation.validate(body, known_plugins={p_["id"] for p_ in store.list_plugins(DB_PATH)},
                             known_agents={a["agent_id"] for a in store.list_agents(DB_PATH)})


@app.route("/rotations", methods=["POST"])
def rotation_create_route():
    p_, err = _rotation_body()
    if err:
        return jsonify({"error": err}), 400
    return jsonify(rotation.save_plan(DB_PATH, p_)), 201


@app.route("/rotations/<int:pid>", methods=["PUT"])
def rotation_update_route(pid):
    if not rotation.get_plan(DB_PATH, pid):
        return jsonify({"error": "tournée inconnue"}), 404
    p_, err = _rotation_body()
    if err:
        return jsonify({"error": err}), 400
    return jsonify(rotation.save_plan(DB_PATH, p_, pid)), 200


@app.route("/rotations/<int:pid>", methods=["DELETE"])
def rotation_delete_route(pid):
    return (jsonify({"deleted": pid}), 200) if rotation.delete_plan(DB_PATH, pid) else (jsonify({"error": "tournée inconnue"}), 404)


@app.route("/rotations/<int:pid>/runs", methods=["GET"])
def rotation_runs_route(pid):
    return jsonify({"runs": rotation.list_runs(DB_PATH, pid, int(request.args.get("limit", 200)))}), 200


@app.route("/pra/plans", methods=["GET"])
def pra_plans_route():
    conn = store._connect(DB_PATH)
    try:
        plans = [pra.plan_public(r) for r in conn.execute("SELECT * FROM pra_plans ORDER BY name")]
        for p_ in plans:
            r = conn.execute("SELECT id, mode, status, started_at, finished_at FROM pra_runs WHERE plan_id = ? ORDER BY id DESC LIMIT 1", (p_["id"],)).fetchone()
            p_["last_run"] = dict(r) if r else None
    finally:
        conn.close()
    return jsonify({"plans": plans, "actions": list(pra.ACTIONS), "required": pra.REQUIRED, "migration_methods": list(migration.METHODS)}), 200


@app.route("/pra/plans", methods=["POST"])
def pra_plan_create_route():
    body = request.get_json(silent=True) or {}
    steps, err = pra.validate_steps(body.get("steps"))
    if err:
        return jsonify({"error": err}), 400
    rb, err = pra.validate_steps(body["rollback_steps"]) if body.get("rollback_steps") else ([], None)
    if err:
        return jsonify({"error": "retour en arrière : " + err}), 400
    if not (body.get("name") or "").strip():
        return jsonify({"error": "nom du plan requis"}), 400
    conn = store._connect(DB_PATH)
    try:
        cur = conn.execute("INSERT INTO pra_plans (name, kind, notes, steps, continue_on_error, created_at, updated_at, trigger_agent_id, trigger_mode, trigger_cooldown_s, rollback_steps, auto_rollback) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                           (body["name"].strip(), body.get("kind") or "pra", body.get("notes") or "", json.dumps(steps, ensure_ascii=False), 1 if body.get("continue_on_error") else 0, store.now_iso(), store.now_iso(),
                            str(body.get("trigger_agent_id") or ""), "auto" if body.get("trigger_mode") == "auto" else "notify", int(body.get("trigger_cooldown_s") or 3600),
                            json.dumps(rb, ensure_ascii=False), 1 if body.get("auto_rollback") else 0))
        row = conn.execute("SELECT * FROM pra_plans WHERE id = ?", (cur.lastrowid,)).fetchone(); conn.commit()
    finally:
        conn.close()
    return jsonify({"plan": pra.plan_public(row)}), 201


@app.route("/pra/plans/<int:pid>", methods=["PUT"])
def pra_plan_update_route(pid):
    body = request.get_json(silent=True) or {}
    conn = store._connect(DB_PATH)
    try:
        row = conn.execute("SELECT * FROM pra_plans WHERE id = ?", (pid,)).fetchone()
        if not row:
            return jsonify({"error": "plan inconnu"}), 404
        steps = json.loads(row["steps"]); rb = json.loads(row["rollback_steps"] or "[]")
        if "steps" in body:
            steps, err = pra.validate_steps(body["steps"])
            if err:
                return jsonify({"error": err}), 400
        if "rollback_steps" in body:
            rb, err = pra.validate_steps(body["rollback_steps"]) if body["rollback_steps"] else ([], None)
            if err:
                return jsonify({"error": "retour en arrière : " + err}), 400
        conn.execute("UPDATE pra_plans SET name = ?, kind = ?, notes = ?, steps = ?, continue_on_error = ?, updated_at = ?, trigger_agent_id = ?, trigger_mode = ?, trigger_cooldown_s = ?, rollback_steps = ?, auto_rollback = ? WHERE id = ?",
                     ((body.get("name") or row["name"]).strip(), body.get("kind", row["kind"]), body.get("notes", row["notes"]), json.dumps(steps, ensure_ascii=False),
                      1 if body.get("continue_on_error", row["continue_on_error"]) else 0, store.now_iso(),
                      str(body.get("trigger_agent_id", row["trigger_agent_id"]) or ""), "auto" if body.get("trigger_mode", row["trigger_mode"]) == "auto" else "notify",
                      int(body.get("trigger_cooldown_s", row["trigger_cooldown_s"]) or 3600), json.dumps(rb, ensure_ascii=False), 1 if body.get("auto_rollback", row["auto_rollback"]) else 0, pid))
        row = conn.execute("SELECT * FROM pra_plans WHERE id = ?", (pid,)).fetchone(); conn.commit()
    finally:
        conn.close()
    return jsonify({"plan": pra.plan_public(row)}), 200


@app.route("/pra/plans/<int:pid>", methods=["DELETE"])
def pra_plan_delete_route(pid):
    conn = store._connect(DB_PATH)
    try:
        n = conn.execute("DELETE FROM pra_plans WHERE id = ?", (pid,)).rowcount; conn.execute("DELETE FROM pra_runs WHERE plan_id = ?", (pid,)); conn.commit()
    finally:
        conn.close()
    return (jsonify({"ok": True}), 200) if n else (jsonify({"error": "plan inconnu"}), 404)


@app.route("/pra/plans/<int:pid>/run", methods=["POST"])
def pra_plan_run_route(pid):
    """{mode: simulate|execute, actor}. Exécution réelle : commandes vm_action envoyées une à une aux agents des hyperviseurs."""
    body = request.get_json(silent=True) or {}
    mode = body.get("mode") or "simulate"
    if mode not in ("simulate", "execute"):
        return jsonify({"error": "mode : simulate ou execute"}), 400
    conn = store._connect(DB_PATH)
    try:
        row = conn.execute("SELECT * FROM pra_plans WHERE id = ?", (pid,)).fetchone()
        running = conn.execute("SELECT id FROM pra_runs WHERE plan_id = ? AND status = 'running' AND mode = 'execute'", (pid,)).fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "plan inconnu"}), 404
    if running and mode == "execute":
        return jsonify({"error": "une exécution de ce plan est déjà en cours (n°%s)" % running["id"]}), 409
    rid = pra.start_run(DB_PATH, pra.plan_public(row), mode, str(body.get("actor") or ""))
    return jsonify({"run_id": rid}), 202


@app.route("/pra/roles", methods=["GET"])
def pra_roles_route():
    conn = store._connect(DB_PATH)
    try:
        roles = [pra.role_public(r) for r in conn.execute("SELECT * FROM pra_roles ORDER BY name")]
    finally:
        conn.close()
    return jsonify({"roles": roles, "mechanisms": list(pra.ROLE_MECHANISMS), "mikrotik": bool(pra.MIKROTIK_API_URL), "dns": bool(pra.DNS_API_URL)}), 200


@app.route("/pra/roles", methods=["POST"])
def pra_role_create_route():
    f, err = pra.validate_role(request.get_json(silent=True) or {})
    if err:
        return jsonify({"error": err}), 400
    conn = store._connect(DB_PATH)
    try:
        cur = conn.execute("INSERT INTO pra_roles (name, service_url, candidates, mechanism, notes, created_at, updated_at) VALUES (?,?,?,?,?,?,?)",
                           (f["name"], f["service_url"], json.dumps(f["candidates"], ensure_ascii=False), json.dumps(f["mechanism"]), f["notes"], store.now_iso(), store.now_iso()))
        row = conn.execute("SELECT * FROM pra_roles WHERE id = ?", (cur.lastrowid,)).fetchone(); conn.commit()
    finally:
        conn.close()
    return jsonify({"role": pra.role_public(row)}), 201


@app.route("/pra/roles/<int:rid>", methods=["PUT", "DELETE"])
def pra_role_edit_route(rid):
    conn = store._connect(DB_PATH)
    try:
        row = conn.execute("SELECT * FROM pra_roles WHERE id = ?", (rid,)).fetchone()
        if not row:
            return jsonify({"error": "rôle inconnu"}), 404
        if request.method == "DELETE":
            conn.execute("DELETE FROM pra_roles WHERE id = ?", (rid,)); conn.commit()
            return jsonify({"ok": True}), 200
        cur = pra.role_public(row); body = {**{k: cur[k] for k in ("name", "service_url", "candidates", "mechanism", "notes")}, **(request.get_json(silent=True) or {})}
        f, err = pra.validate_role(body)
        if err:
            return jsonify({"error": err}), 400
        conn.execute("UPDATE pra_roles SET name = ?, service_url = ?, candidates = ?, mechanism = ?, notes = ?, updated_at = ? WHERE id = ?",
                     (f["name"], f["service_url"], json.dumps(f["candidates"], ensure_ascii=False), json.dumps(f["mechanism"]), f["notes"], store.now_iso(), rid))
        row = conn.execute("SELECT * FROM pra_roles WHERE id = ?", (rid,)).fetchone(); conn.commit()
    finally:
        conn.close()
    return jsonify({"role": pra.role_public(row)}), 200


@app.route("/pra/roles/<int:rid>/switch", methods=["POST"])
def pra_role_switch_route(rid):
    """{to: indice du candidat, actor} -- bascule « celui qui répond » : mécanisme appliqué, service vérifié, événement."""
    body = request.get_json(silent=True) or {}
    try:
        to = int(body.get("to"))
    except (TypeError, ValueError):
        return jsonify({"error": "to (indice du candidat) requis"}), 400
    r = pra.switch_role(DB_PATH, rid, to, by_user=str(body.get("actor") or ""))
    if r.get("role"):
        _event("role-switch", "info" if r["ok"] else "warning", "rôle « %s » basculé vers %s par %s%s" % (r["role"], r["to"]["label"], body.get("actor") or "?", "" if r["ok"] else " -- " + str(r.get("error"))), details=r)
    return jsonify(r), (200 if r.get("ok") else 502 if r.get("role") else 404)


@app.route("/pra/roles/<int:rid>/check", methods=["POST"])
def pra_role_check_route(rid):
    role = pra.get_role(DB_PATH, rid)
    if not role:
        return jsonify({"error": "rôle inconnu"}), 404
    chk = pra.check_role(role)
    conn = store._connect(DB_PATH)
    try:
        conn.execute("UPDATE pra_roles SET last_check = ? WHERE id = ?", (json.dumps(chk), rid)); conn.commit()
    finally:
        conn.close()
    return jsonify({"check": chk}), 200


@app.route("/pra/runs/<int:rid>", methods=["GET"])
def pra_run_route(rid):
    conn = store._connect(DB_PATH)
    try:
        row = conn.execute("SELECT * FROM pra_runs WHERE id = ?", (rid,)).fetchone()
    finally:
        conn.close()
    return (jsonify({"run": pra.run_public(row)}), 200) if row else (jsonify({"error": "exécution inconnue"}), 404)


@app.route("/pra/runs/<int:rid>/resume", methods=["POST"])
def pra_run_resume_route(rid):
    """#658 : « Reprendre » une exécution arrêtée à une étape de transition (checkpoint)."""
    r = pra.resume_run(DB_PATH, rid)
    return jsonify(r), 200 if r.get("ok") else 409


@app.route("/pra/runs/<int:rid>/abort", methods=["POST"])
def pra_run_abort_route(rid):
    """#658 : « Abandonner » {rollback: bool, actor} -- l'exécution s'arrête ; avec rollback, les étapes de retour du plan sont lancées."""
    body = request.get_json(silent=True) or {}
    conn = store._connect(DB_PATH)
    try:
        row = conn.execute("SELECT status FROM pra_runs WHERE id = ?", (rid,)).fetchone()
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "exécution inconnue"}), 404
    if row["status"] not in ("running", "paused"):
        return jsonify({"error": "exécution déjà terminée (%s)" % row["status"]}), 409
    r = pra.abort_run(DB_PATH, rid, rollback=bool(body.get("rollback")), by_user=str(body.get("actor") or ""))
    return jsonify(r), 200 if r.get("ok") else 400


@app.route("/pra/runs/<int:rid>/rollback", methods=["POST"])
def pra_run_rollback_route(rid):
    """#658 : retour en arrière après une exécution terminée (rollback_steps du plan)."""
    body = request.get_json(silent=True) or {}
    conn = store._connect(DB_PATH)
    try:
        run = conn.execute("SELECT plan_id, status FROM pra_runs WHERE id = ?", (rid,)).fetchone()
        row = conn.execute("SELECT * FROM pra_plans WHERE id = ?", (run["plan_id"],)).fetchone() if run else None
    finally:
        conn.close()
    if not row:
        return jsonify({"error": "exécution ou plan inconnu"}), 404
    if run["status"] in ("running", "paused"):
        return jsonify({"error": "exécution en cours : utiliser Abandonner (avec retour)"}), 409
    plan = pra.plan_public(row)
    if not plan["rollback_steps"]:
        return jsonify({"error": "ce plan n'a pas d'étapes de retour"}), 400
    rb = pra.start_rollback(DB_PATH, plan, rid, str(body.get("actor") or ""))
    return jsonify({"run_id": rb}), 202


@app.route("/pra/migrations/plan", methods=["POST"])
def pra_migration_plan_route():
    """#658 (item 112) : plan de migration d'un serveur vers la virtualisation -- {method: image|rebuild, source_agent_id, pve_agent_id,
    vmid, storage, bridge, memory, cores, os, image_target | template, role_id/role_from/role_to, purge_on_rollback, auto_rollback, save}.
    Sans `save` : aperçu (étapes + retour) ; avec : plan enregistré (kind migration)."""
    body = request.get_json(silent=True) or {}
    plan, err = migration.build(body)
    if err:
        return jsonify({"error": err}), 400
    steps, err = pra.validate_steps(plan["steps"])
    if err:
        return jsonify({"error": err}), 400
    rb, err = pra.validate_steps(plan["rollback_steps"]) if plan["rollback_steps"] else ([], None)   # #750 : rapatriement sans retour
    if err:
        return jsonify({"error": "retour : " + err}), 400
    plan.update(steps=steps, rollback_steps=rb)
    if not body.get("save"):
        return jsonify({"plan": plan}), 200
    conn = store._connect(DB_PATH)
    try:
        cur = conn.execute("INSERT INTO pra_plans (name, kind, notes, steps, continue_on_error, created_at, updated_at, rollback_steps, auto_rollback) VALUES (?,?,?,?,?,?,?,?,?)",
                           (plan["name"], "migration", plan["notes"], json.dumps(steps, ensure_ascii=False), 0, store.now_iso(), store.now_iso(), json.dumps(rb, ensure_ascii=False), 1 if plan["auto_rollback"] else 0))
        row = conn.execute("SELECT * FROM pra_plans WHERE id = ?", (cur.lastrowid,)).fetchone(); conn.commit()
    finally:
        conn.close()
    return jsonify({"plan": pra.plan_public(row)}), 201


@app.route("/pra/plans/<int:pid>/runs", methods=["GET"])
def pra_plan_runs_route(pid):
    conn = store._connect(DB_PATH)
    try:
        rows = conn.execute("SELECT * FROM pra_runs WHERE plan_id = ? ORDER BY id DESC LIMIT 20", (pid,)).fetchall()
    finally:
        conn.close()
    return jsonify({"runs": [pra.run_public(r) for r in rows]}), 200


@app.route("/commands/<cid>", methods=["GET"])
def get_command_route(cid):
    c = store.get_command(DB_PATH, cid)
    if c is None:
        return jsonify({"error": "commande inconnue"}), 404
    return jsonify(c), 200


# ============================================================
# Face agents (signée)
# ============================================================

def _signed_path():
    """Chemin tel que l'agent l'a signé : tls-proxy retire `/api/si-agent`,
    l'agent signe `/api/v1/agents/<id>/config` et Flask voit ce chemin."""
    qs = request.query_string.decode("utf-8") if request.query_string else ""
    return request.path + ("?" + qs if qs else "")


_auth_failures = {}


def _verify_agent(agent_id):
    header_id = request.headers.get(protocol.HEADER_ID)
    info, why = None, None
    if not header_id:
        why = "en-tête %s absent" % protocol.HEADER_ID
    elif header_id != agent_id:
        why = "identifiant signataire différent de l'URL"
    else:
        info = store.get_secret(DB_PATH, agent_id)
        if info is None:
            why = "agent inconnu ou désactivé"
        else:
            ok, reason = protocol.verify(info["secret"], request.method, _signed_path(), request.headers, request.get_data())
            if not ok:
                info, why = None, reason
    if info is None:
        _log.warning("face agents : refus %s %s pour %s depuis %s -- %s", request.method, request.path, agent_id, _client_ip(), why)
        # un événement par (agent, motif) et par 10 min -- jamais une tempête
        key = (agent_id, why)
        last = _auth_failures.get(key, 0)
        if time.time() - last > 600:
            _auth_failures[key] = time.time()
            _event("auth-refused", "warning", "requête refusée pour l'agent %s : %s (depuis %s)" % (agent_id, why, _client_ip()),
                   agent_id=agent_id if store.get_agent(DB_PATH, agent_id) else None, details={"path": request.path, "ip": _client_ip(), "reason": why})
        return None, why
    _log.debug("face agents : %s %s par %s depuis %s", request.method, request.path, agent_id, _client_ip())
    return info, None


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr)


def _signed_json(secret, payload, status=200):
    """Réponse JSON SIGNÉE avec le secret de l'agent (voir control.py) :
    l'agent n'applique une configuration / une commande que si cette
    signature est valide."""
    raw = protocol.canonical_json(payload)
    headers = control.response_headers(secret, raw)
    headers["Content-Type"] = "application/json; charset=utf-8"
    return raw, status, headers


# ---- #616 : enrôlement en masse (jeton de site) ------------------------------
@app.route("/enroll-tokens", methods=["GET"])
def enroll_tokens_list_route():
    return jsonify({"tokens": store.list_enroll_tokens(DB_PATH), "public_url": PUBLIC_URL}), 200


@app.route("/enroll-tokens", methods=["POST"])
def enroll_tokens_create_route():
    body = request.get_json(silent=True) or {}
    try:
        t = store.create_enroll_token(DB_PATH, body.get("site", ""), label=body.get("label"), central_url=body.get("central_url") or PUBLIC_URL,
                                      plugins=body.get("plugins") or [], max_uses=body.get("max_uses") or 0,
                                      expires_hours=body.get("expires_hours", 72), created_by=body.get("created_by"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    _event("enroll-token-created", "info", "jeton d'enrôlement créé pour le site %s (%s)" % (t["site"], t.get("label") or "sans libellé"))
    t["commands"] = _deploy_commands(t)
    return jsonify(t), 201


@app.route("/enroll-tokens/<token>", methods=["DELETE"])
def enroll_tokens_revoke_route(token):
    if not store.revoke_enroll_token(DB_PATH, token):
        return jsonify({"error": "jeton inconnu"}), 404
    _event("enroll-token-revoked", "info", "jeton d'enrôlement révoqué")
    return jsonify({"revoked": True}), 200


def _pin_internal_ca(base_url):
    """Vrai si l'URL du central désigne une adresse IP ou un nom local (.local, .lan, sans point) :
    c'est la PKI interne qui la sert. Un nom public (frontal) est servi par un certificat public."""
    import re as _re
    host = _re.sub(r"^https?://", "", base_url or "").split("/")[0].split(":")[0].strip("[]")
    return bool(_re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host)) or "." not in host or host.endswith((".local", ".lan", ".home", ".internal"))


def _deploy_commands(t):
    """Lignes à coller (PowerShell administrateur / shell root) ou à pousser par GPO."""
    base = (t.get("central_url") or PUBLIC_URL or "https://<VM>:6443/api/si-agent").rstrip("/")
    tok = t["token"]
    ca = _ca_info().get("sha256") if _pin_internal_ca(base) else None
    return {
        "windows": "powershell -NoProfile -ExecutionPolicy Bypass -Command \"iex (iwr -UseBasicParsing '%s/deploy/windows?token=%s').Content\"" % (base, tok),
        "linux": "curl -fsSL '%s/deploy/linux?token=%s' | sudo bash" % (base, tok),
        "gpo": "%s/deploy/windows?token=%s" % (base, tok),
        # #626 : poste sous antivirus (la ligne « télécharge + exécute » est bloquée par heuristique) --
        # archive téléchargée par le navigateur, installeur lancé à la main, aucun secret dans la ligne
        "windows_manual": "cd $env:USERPROFILE\\Downloads ; tar -xzf si-agent-agent-*.tar.gz ; cd si-agent-agent-* ; "
                          "powershell -NoProfile -ExecutionPolicy Bypass -File .\\windows\\install.ps1 -EnrollToken %s -Central %s -Site %s %s%s"
                          % (tok, base, t["site"], ("-CaFingerprint " + ca) if ca else "-SystemCa", (" -EnablePlugin " + ",".join(t["plugins"])) if t.get("plugins") else ""),
        "package": base + "/package",
    }


_PYTHON_EMBED_URL = os.environ.get("SI_AGENT_PYTHON_EMBED_URL", "https://www.python.org/ftp/python/3.12.7/python-3.12.7-embed-amd64.zip")
_PYTHON_EMBED_CACHE = os.environ.get("SI_AGENT_PYTHON_EMBED_CACHE", os.path.join(tempfile.gettempdir(), "si-agent-python-embed.zip"))
_PYTHON_EMBED_LOCK = threading.Lock()


@app.route("/deploy/python", methods=["GET"])
def deploy_python_route():
    """Sert la distribution Python « embeddable » aux postes qui n'ont pas accès
    à python.org : le central (qui, lui, a Internet) la récupère une fois et la
    met en cache, le poste la télécharge depuis le central. install.ps1 la reçoit
    via -PythonUrl. Aucun secret ici -- fichier public, comme /package."""
    path = _PYTHON_EMBED_CACHE
    ok = os.path.exists(path) and os.path.getsize(path) > 1_000_000
    if not ok:
        with _PYTHON_EMBED_LOCK:
            if not (os.path.exists(path) and os.path.getsize(path) > 1_000_000):
                try:
                    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
                    tmp = path + ".part"
                    urllib.request.urlretrieve(_PYTHON_EMBED_URL, tmp)
                    if os.path.getsize(tmp) < 1_000_000:
                        os.remove(tmp)
                        raise RuntimeError("archive trop petite, téléchargement incomplet")
                    os.replace(tmp, path)
                except Exception as exc:  # noqa: BLE001
                    return jsonify({"error": "python embarqué indisponible (le central n'a pas pu le récupérer depuis %s) : %s" % (_PYTHON_EMBED_URL, exc)}), 502
    return send_file(path, mimetype="application/zip", as_attachment=True, download_name="python-embed.zip")


_INSTALL_PAGE = (
    '<!doctype html><html lang="fr"><head><meta charset="utf-8">'
    '<meta name="viewport" content="width=device-width, initial-scale=1">'
    '<title>si-agent - installation</title><style>'
    'body{font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:760px;margin:24px auto;padding:0 16px;line-height:1.5;color:#111;background:#fff}'
    'h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:22px}'
    'pre{background:#0d1117;color:#e6edf3;padding:12px;border-radius:6px;overflow:auto;white-space:pre-wrap;word-break:break-all}'
    'button{padding:6px 12px;margin-top:6px;cursor:pointer}code{background:#eee;padding:1px 4px;border-radius:3px}'
    '.err{color:#b00020}.note{color:#444;font-size:.95rem}a{color:#0b62c4}</style></head><body>__BODY__</body></html>'
)


@app.route("/install", methods=["GET"])
def install_page_route():
    """Page d'aide, ATTEIGNABLE DEPUIS LE POSTE (navigateur, 443), protegee par
    le jeton (?token=). Donne la ligne a coller (script telecharge puis execute,
    pas de iex -> compatible antivirus) et les liens : agent + Python servis par
    le central. Aucune option a saisir."""
    import html as _html
    token = request.args.get("token", "")
    t = store.get_enroll_token(DB_PATH, token) if token else None
    base = ((t.get("central_url") if t else None) or PUBLIC_URL or request.url_root.rstrip("/")).rstrip("/")
    if t is None or not t.get("usable"):
        body = ("<h1>si-agent - installation</h1>"
                "<p class=err>Jeton d'enrolement absent, invalide ou expire.</p>"
                "<p class=note>Cree un jeton dans le hub (Agents hotes -> Deploiement), puis ouvre cette page avec <code>?token=LE-JETON</code>.</p>")
        return Response(_INSTALL_PAGE.replace("__BODY__", body), mimetype="text/html; charset=utf-8"), 403
    site = t.get("site") or "default"
    cmd = "\n".join([
        "$b = '" + base + "'",
        'iwr "$b/deploy/windows?token=' + token + '" -OutFile si-agent-install.ps1 -UseBasicParsing',
        'powershell -NoProfile -ExecutionPolicy Bypass -File .\\si-agent-install.ps1',
    ])
    body = (
        "<h1>si-agent - installation du poste</h1>"
        "<p>Site : <b>" + _html.escape(site) + "</b>. Ouvre <b>PowerShell en administrateur</b>, colle ces lignes :</p>"
        "<pre id=cmd>" + _html.escape(cmd) + "</pre>"
        "<button onclick=\"navigator.clipboard.writeText(document.getElementById('cmd').innerText)\">Copier</button>"
        "<p class=note>Le script telecharge l'agent <b>et Python depuis ce serveur</b> (pas besoin de python.org), s'enrole sous le nom de la machine et demarre le service.</p>"
        "<h2>Telechargements manuels</h2><ul>"
        "<li><a href=\"" + base + "/deploy/windows?token=" + token + "\">Script d'installation (.ps1)</a></li>"
        "<li><a href=\"" + base + "/package\" download>Archive de l'agent (.tgz)</a></li>"
        "<li><a href=\"" + base + "/deploy/python\" download>Python embarque (.zip)</a></li>"
        "</ul>"
    )
    return Response(_INSTALL_PAGE.replace("__BODY__", body), mimetype="text/html; charset=utf-8")

@app.route("/deploy/<platform>", methods=["GET"])
def deploy_script_route(platform):
    """Script d'amorçage (texte) : télécharge l'archive de l'agent, l'extrait et
    lance l'installeur avec le jeton ; ne contient AUCUN secret d'agent (le
    secret est délivré à l'enrôlement, sur ce poste seulement)."""
    t = store.get_enroll_token(DB_PATH, request.args.get("token", ""))
    if t is None or not t["usable"]:
        # #680 : refus tracé (jeton masqué) -- motif lisible dans les journaux de si-agent-api
        tok = request.args.get("token", "")
        why = "inconnu" if t is None else ("révoqué" if t["revoked"] else "expiré" if t["expired"] else "épuisé (%d/%d usages)" % (t.get("uses", 0), t["max_uses"]))
        _log.warning("amorçage %s refusé depuis %s : jeton %s (%s…, %d car.)%s", platform, _client_ip(), why, tok[:4], len(tok),
                     " -- « $ » dans le jeton : variable shell non développée (guillemets simples ?)" if "$" in tok else "")
        return Response("jeton d'enrôlement %s\n" % why, status=403, mimetype="text/plain")
    base = (t.get("central_url") or PUBLIC_URL or "").rstrip("/") or request.url_root.rstrip("/")
    # CA interne épinglée seulement quand le central est joint par son adresse LAN (PKI du projet) ;
    # par un nom public (frontal Let's Encrypt), le magasin système du poste fait foi.
    ca_sha = _ca_info().get("sha256") if _pin_internal_ca(base) else ""
    if platform == "windows":
        body = _WINDOWS_BOOTSTRAP % {"base": base, "token": t["token"], "site": t["site"], "ca": ca_sha or "", "plugins": ",".join(t["plugins"])}
        return Response(body, mimetype="text/plain; charset=utf-8")
    if platform == "linux":
        body = _LINUX_BOOTSTRAP % {"base": base, "token": t["token"], "site": t["site"], "ca": ca_sha or "", "plugins": " ".join(t["plugins"])}
        return Response(body, mimetype="text/plain; charset=utf-8")
    return jsonify({"error": "platform : windows ou linux"}), 404


_WINDOWS_BOOTSTRAP = r"""# si-agent -- amorçage Windows (#616) : archive + installeur + enrôlement par jeton
$ErrorActionPreference = "Stop"
$base = "%(base)s"; $token = "%(token)s"
$tmp = Join-Path $env:TEMP ("si-agent-" + [guid]::NewGuid().ToString("N").Substring(0,8))
New-Item -ItemType Directory -Path $tmp | Out-Null
Write-Host "si-agent : téléchargement de l'archive depuis $base ..."
Invoke-WebRequest -UseBasicParsing -Uri "$base/package" -OutFile (Join-Path $tmp "agent.tgz")
tar -xzf (Join-Path $tmp "agent.tgz") -C $tmp
$dir = Get-ChildItem -Path $tmp -Directory | Select-Object -First 1
$ps = Join-Path $dir.FullName "windows\install.ps1"
$args = @("-EnrollToken", $token, "-Central", $base, "-Site", "%(site)s", "-PythonUrl", "$base/deploy/python")
if ("%(ca)s") { $args += @("-CaFingerprint", "%(ca)s") } else { $args += "-SystemCa" }
if ("%(plugins)s") { $args += @("-EnablePlugin", ("%(plugins)s" -split ",")) }
& powershell -NoProfile -ExecutionPolicy Bypass -File $ps @args
Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
"""

_LINUX_BOOTSTRAP = r"""#!/bin/sh
# si-agent -- amorçage Linux (#616) : archive + installeur + enrôlement par jeton
set -e
BASE="%(base)s"; TOKEN="%(token)s"
TMP=$(mktemp -d /tmp/si-agent.XXXXXX)
echo "si-agent : téléchargement de l'archive depuis $BASE ..."
curl -fsSL "$BASE/package" -o "$TMP/agent.tgz"
tar -xzf "$TMP/agent.tgz" -C "$TMP"
DIR=$(find "$TMP" -mindepth 1 -maxdepth 1 -type d | head -1)
cd "$DIR"
SI_AGENT_ENROLL_TOKEN="$TOKEN" SI_AGENT_CENTRAL="$BASE" SI_AGENT_SITE="%(site)s" SI_AGENT_CA_SHA256="%(ca)s" SI_AGENT_PLUGINS="%(plugins)s" ./install.sh
rm -rf "$TMP"
"""


@app.route(protocol.API_PREFIX + "/enroll", methods=["POST"])
def enroll_route():
    """Face machine : {token, hostname, platform} -> {agent_id, secret, site, central_url}.
    Pas de signature (l'agent n'a pas encore de secret) : le jeton fait foi."""
    body = request.get_json(silent=True) or {}
    try:
        a, t = store.enroll_with_token(DB_PATH, body.get("token", ""), body.get("hostname", ""), body.get("platform"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 403
    _event("agent-enrolled", "info", "agent %s enrôlé par jeton (site %s, %s)" % (a["agent_id"], a["site"], body.get("platform") or "?"), agent_id=a["agent_id"])
    return jsonify({"agent_id": a["agent_id"], "secret": a["secret"], "site": a["site"],
                    "central_url": (t.get("central_url") or PUBLIC_URL or "").rstrip("/"),
                    "ca_sha256": _ca_info().get("sha256") if _pin_internal_ca(t.get("central_url") or PUBLIC_URL) else None,
                    "plugins": t["plugins"]}), 201


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/config", methods=["GET"])
def agent_config_route(agent_id):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    cfg = store.config_for_agent(DB_PATH, agent_id)
    prev = store.get_agent(DB_PATH, agent_id)
    conn = store._connect(DB_PATH)
    try:
        store.touch_agent(conn, agent_id, _client_ip(), config_version=cfg["version"])
        conn.commit()
    finally:
        conn.close()
    if prev and prev.get("last_config_version") != cfg["version"]:
        _log.info("agent %s : configuration %s servie (%d sonde(s)%s)", agent_id, cfg["version"], len(cfg["plugins"]), ", BLOQUÉ" if cfg["blocked"] else "")
    return _signed_json(info["secret"], cfg)


NEBULA_API_URL = os.environ.get("NEBULA_API_URL", "").rstrip("/")


def _publish_board(pub):
    """Tableau de santé pour l'agent (#547) : nebula-api, site précis ou tous.
    Renvoie (board, transitions par site, erreur) -- #564 : l'historique des
    changements d'état accompagne le tableau (page publiée : historique par
    thématique, exports)."""
    if not NEBULA_API_URL:
        return None, {}, "NEBULA_API_URL non configurée sur le central"
    path = ("/sites/%s/health-board" % pub["site_id"]) if pub.get("site_id") else "/health-board"
    try:
        r = requests.get("%s%s?hours=%d" % (NEBULA_API_URL, path, pub["hours"]), timeout=10)
        if r.status_code != 200:
            return None, {}, "nebula-api : %s" % r.status_code
        board = r.json()
    except (requests.RequestException, ValueError) as exc:
        return None, {}, "nebula-api injoignable : %s" % exc
    transitions = {}
    sites = board.get("sites") if isinstance(board, dict) and "sites" in board else [board]
    for s in sites[:10]:
        sid = s.get("site_id") if isinstance(s, dict) else None
        if not sid:
            continue
        try:
            t = requests.get("%s/sites/%s/transitions?hours=%d" % (NEBULA_API_URL, sid, pub["hours"]), timeout=10)
            if t.status_code == 200:
                transitions[sid] = (t.json() or {}).get("transitions") or []
        except (requests.RequestException, ValueError):
            pass
    return board, transitions, None


@app.route("/agents/<agent_id>/publish/preview", methods=["GET"])
def publish_preview_route(agent_id):
    """La page EXACTE que l'agent sert sur son LAN (#549 : même gabarit,
    même contenu, calculé ici), pour la voir depuis le hub sans être sur
    le site. Le JSON voisin `board.json` est relatif, comme sur l'agent."""
    a = store.get_agent(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    pub = a.get("publish") or {}
    return Response(agent_publish.render_page(pub.get("title") or "État du réseau"), mimetype="text/html; charset=utf-8")


@app.route("/agents/<agent_id>/publish/board.json", methods=["GET"])
def publish_preview_board_route(agent_id):
    a = store.get_agent(DB_PATH, agent_id)
    if a is None:
        return jsonify({"error": "agent inconnu"}), 404
    pub = a.get("publish") or {}
    if not pub.get("enabled"):
        return jsonify({"at": None, "stale": True, "sites": [], "error": "publication désactivée pour cet agent"}), 200
    board, transitions, why = _publish_board(pub)
    payload = publish_lib.board_payload(board or {}, pub["title"], int(time.time()), pub.get("hub_url") or "", transitions)
    payload["received_at"] = time.time()
    if why:
        payload["error"] = why
    return jsonify(agent_publish.with_age(payload)), 200


# ---- #634 : réception des images P2V envoyées par les agents (morceaux signés, reprise) ----
IMAGES_DIR = os.environ.get("SI_AGENT_IMAGES_DIR", os.path.join(os.path.dirname(DB_PATH), "images"))
pra.IMAGES_DIR = IMAGES_DIR
_images = None


def _image_store():
    global _images
    if _images is None:
        _images = imagestore.ImageStore(IMAGES_DIR)
    return _images


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/images/<name>/status", methods=["GET"])
def image_status_route(agent_id, name):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    size, done = _image_store().size(agent_id, name)
    return jsonify({"size": size, "complete": done}), 200


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/images/<name>", methods=["PUT"])
def image_chunk_route(agent_id, name):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    safe = re.sub(r"[^A-Za-z0-9._-]", "-", name)[:120]
    if not safe or safe.startswith("."):
        return jsonify({"error": "nom invalide"}), 400
    st, out = _image_store().append(agent_id, safe, request.args.get("offset"), request.get_data())
    return jsonify(out), st


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/images/<name>/complete", methods=["POST"])
def image_complete_route(agent_id, name):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    body = request.get_json(silent=True) or {}
    st, out = _image_store().complete(agent_id, name, body.get("size"), body.get("sha256"))
    if st == 200:
        _event("image-received", "info", "image %s reçue de %s (%d octets)" % (name, agent_id, out["size"]), agent_id=agent_id, details={"path": out["path"], "sha256": out["sha256"]})
    return jsonify(out), st


VULN_API_URL = os.environ.get("VULN_API_URL", "http://vuln-api:5000").rstrip("/")


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/sbom", methods=["POST"])
def sbom_route(agent_id):
    """#699 : inventaire logiciel (CycloneDX, gzip) d'un agent -> vuln-api (actif = nom d'hôte, sinon identifiant).
    L'exposition de l'actif reste celle réglée dans la tuile Vulnérabilités."""
    import gzip as _gz
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    raw = request.get_data()
    try:
        bom = _gz.decompress(raw) if raw[:2] == b"\x1f\x8b" else raw
    except OSError:
        return jsonify({"error": "archive gzip illisible"}), 400
    if not bom or len(bom) > 200 * 1024 * 1024:
        return jsonify({"error": "SBOM vide ou trop volumineux"}), 400
    agent = store.get_agent(DB_PATH, agent_id) or {}
    kind = request.args.get("kind") or "host"
    if kind not in ("host", "image"):
        return jsonify({"error": "kind : host ou image"}), 400
    if kind == "image":                                  # #711 : image Docker en service sur l'hôte de l'agent -- actif = l'image
        asset = re.sub(r"[^A-Za-z0-9._:@/+-]", "-", str(request.args.get("name") or ""))[:150]
        if not asset:
            return jsonify({"error": "nom de l'image requis"}), 400
    else:
        asset = re.sub(r"[^A-Za-z0-9 ._:@/()+-]", "-", str(agent.get("hostname") or agent_id))[:100] or agent_id
    try:
        r = requests.post(VULN_API_URL + "/sbom", params={"asset": asset, "kind": kind, "source": "agent:%s" % agent_id},
                          data=bom, headers={"Content-Type": "application/json"}, timeout=1200)
        out = r.json() if r.headers.get("Content-Type", "").startswith("application/json") else {"error": r.text[:200]}
    except requests.RequestException as exc:
        _event("sbom-failed", "warning", "inventaire de %s non transmis à vuln-api : %s" % (agent_id, exc), agent_id=agent_id)
        return jsonify({"error": "vuln-api injoignable : %s" % str(exc)[:200]}), 502
    if r.ok:
        _event("sbom-received", "info", "inventaire de %s : %s composant(s), %s vulnérabilité(s)" % (agent_id, out.get("components"), out.get("findings")),
               agent_id=agent_id, details={"asset": asset, "scan_error": out.get("scan_error")})
    return jsonify(out), r.status_code


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/images/<src_agent>/<name>/download", methods=["GET"])
def image_download_route(agent_id, src_agent, name):
    """#658 : un agent (nœud Proxmox) télécharge, par requête signée, une image complète reçue d'un autre agent (reprise par Range)."""
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    safe_a, safe_n = re.sub(r"[^A-Za-z0-9._-]", "-", src_agent)[:64], re.sub(r"[^A-Za-z0-9._-]", "-", name)[:120]
    path = os.path.join(IMAGES_DIR, safe_a, safe_n)
    if not safe_n or safe_n.startswith(".") or not os.path.isfile(path):
        return jsonify({"error": "image inconnue ou incomplète"}), 404
    return send_file(path, as_attachment=True, download_name=safe_n, conditional=True, mimetype="application/octet-stream")


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/relay/<src_agent>", methods=["GET"])
def image_relay_route(agent_id, src_agent):
    """#748 : relais direct -- l'agent CIBLE (nœud Proxmox) lit l'image de l'agent SOURCE au fil de l'eau, à partir de
    `offset` (tout ce qui précède est chez lui : le central le libère). Le premier appel ouvre le relais (fenêtre `window_gb`).
    200 + octets ; 204 = rien de neuf, réessayer ; en-têtes X-Relay-Name / -Available / -Complete / -Total / -Sha256."""
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    safe_a = re.sub(r"[^A-Za-z0-9._-]", "-", src_agent)[:64]
    try:
        offset = int(request.args.get("offset") or 0)
        mx = max(1 << 20, min(64 << 20, int(request.args.get("max") or (8 << 20))))
        window = int(float(request.args.get("window_gb") or 4) * 2**30)
    except ValueError:
        return jsonify({"error": "offset / max / window_gb numériques"}), 400
    store_ = _image_store()
    if not store_.relay_get(safe_a):
        store_.relay_open(safe_a, agent_id, window)
        _event("p2v-relay-opened", "info", "relais direct ouvert : images de %s -> %s (fenêtre %.0f Go)" % (safe_a, agent_id, window / 2**30), agent_id=agent_id, details={"source": safe_a})
    st, hdr, data = store_.relay_read(safe_a, agent_id, offset, mx)
    if st in (403, 404, 416):
        return jsonify({"error": {403: "relais réservé à un autre agent", 404: "aucun relais", 416: "offset au-delà de ce qui est disponible"}[st]}), st, hdr
    return Response(data, status=st, headers=hdr, mimetype="application/octet-stream")


def _repa_db(sql, args=(), one=False, write=False):
    conn = store._connect(DB_PATH)
    try:
        conn.execute(repa.SCHEMA)
        cur = conn.execute(sql, args)
        if write:
            conn.commit(); return cur.lastrowid
        rows = cur.fetchall()
        return (rows[0] if rows else None) if one else rows
    finally:
        conn.close()


def _infra_now():
    conn = store._connect(DB_PATH)
    try:
        return infra.overview(infra.latest(conn, "plugin:node-activity"), infra.latest(conn, "plugin:proxmox"), infra.latest(conn, "plugin:pve-remote"), infra.latest(conn, "plugin:pbs"))
    finally:
        conn.close()


def _repa_runs(guests):
    out = {}
    ids = [g["run_id"] for g in guests if g.get("run_id")]
    if ids:
        conn = store._connect(DB_PATH)
        try:
            for r in conn.execute("SELECT * FROM pra_runs WHERE id IN (%s)" % ",".join("?" * len(ids)), ids):
                out[r["id"]] = pra.run_public(r)
        finally:
            conn.close()
    return out


def _repa_full(row, refresh_inventory=True):
    c = repa.public(row)
    ov = _infra_now()
    if refresh_inventory:
        c["guests"] = repa.merge_inventory(c["guests"], [v for v in ov.get("vms") or [] if v.get("node") == c["remote"] and v.get("zone") == "distant"])
    runs = _repa_runs(c["guests"])
    phases = {}
    for g in c["guests"]:
        code, detail = repa.guest_phase(runs.get(g.get("run_id")))
        g["phase"], g["phase_label"], g["phase_detail"] = code, repa.PHASES[code][0], detail
        if g.get("decision") == "rapatrier":
            phases[g["vmid"]] = code
        r = runs.get(g.get("run_id"))
        if r:
            g["run"] = {"id": r["id"], "status": r["status"], "steps": [{"label": s.get("label"), "status": s.get("status"), "result": s.get("result")} for s in r.get("steps") or []]}
    conn = store._connect(DB_PATH)
    try:   # nom du nœud Proxmox remonté par l'agent du nœud local (sonde proxmox)
        node_of = {aid: (d.get("node") or {}).get("name") or host for aid, host, _at, d in infra.latest(conn, "plugin:proxmox")}
        reports = [(t, host or aid, at, d, aid) for t in ("plugin:pve-remote", "plugin:node-activity") for aid, host, at, d in infra.latest(conn, t)]
    finally:
        conn.close()
    tname = node_of.get(c["pve_agent_id"], c["pve_agent_id"])
    target = next((n for n in ov.get("nodes") or [] if n.get("zone") == "local" and (n.get("collected_by") == c["pve_agent_id"] or n.get("name") == tname)), None)
    remote = next((n for n in ov.get("nodes") or [] if n.get("zone") == "distant" and n.get("name") == c["remote"]), None)
    c["checks"] = repa.preparation(c, target, remote, c["guests"])
    c["inventory"] = repa.inventory_state(c["remote"], reports, c["guests"])   # #764
    c["progress"] = repa.progress(c, phases)
    c["steps_def"] = [{"id": s, "label": l, "weight": w} for s, l, w in repa.STEPS]
    c["remote_nodes"] = [n["name"] for n in ov.get("nodes") or [] if n.get("zone") == "distant"]
    c["local_storages"] = [s.get("storage") or s.get("name") for s in (target or {}).get("storages") or []]
    return c


@app.route("/repatriation", methods=["GET"])
def repa_list_route():
    """#761 : campagnes de rapatriement (avancement résumé)."""
    rows = _repa_db("SELECT * FROM repatriation ORDER BY id DESC")
    conn = store._connect(DB_PATH)
    try:   # #763 : nœuds locaux = agents qui remontent la sonde proxmox (même si elle n'a pas été affectée depuis le hub)
        local = [{"agent_id": aid, "hostname": host, "node": (d.get("node") or {}).get("name") or host} for aid, host, _at, d in infra.latest(conn, "plugin:proxmox")]
    finally:
        conn.close()
    return jsonify({"campaigns": [dict(id=c["id"], name=c["name"], remote=c["remote"], step=c["step"], updated_at=c["updated_at"],
                                       percent=c["progress"]["percent"]) for c in (_repa_full(r, False) for r in rows)],
                    "remote_nodes": [n["name"] for n in _infra_now().get("nodes") or [] if n.get("zone") == "distant"], "local_agents": local}), 200


def _leftover_ctx(agent_id):
    """#765 : contexte d'évaluation des restes d'un nœud local -> (local_vms, pbs_groups, copies, base)."""
    conn = store._connect(DB_PATH)
    try:
        local = {}
        for aid, _h, _at, d in infra.latest(conn, "plugin:proxmox"):
            if aid == agent_id:
                local = {int(v["vmid"]): v.get("status") for v in d.get("vms") or [] if v.get("vmid") and not v.get("template")}
        pbs_groups = [g for _a, _h, _at, d in infra.latest(conn, "plugin:pbs") for g in d.get("groups") or []]
    finally:
        conn.close()
    copies, base = {}, repa.DEFAULT_SETTINGS["newid_base"]
    for r in _repa_db("SELECT * FROM repatriation WHERE pve_agent_id = ?", (agent_id,)):
        c = _repa_full(r)
        base = c["settings"].get("newid_base", base)
        for g in c["guests"]:
            if g.get("newid"):
                copies[int(g["vmid"])] = {"newid": int(g["newid"]), "remote": c["remote"],
                                          "original": "présent" if g.get("present") else "détruit ou absent de l'inventaire"}
    return local, pbs_groups, copies, base


@app.route("/repatriation/cleanup/evaluate", methods=["POST"])
def repa_cleanup_eval_route():
    """#765 : {agent_id, items (action xfer leftovers de l'agent)} -> éléments avec conditions de suppression."""
    b = request.get_json(silent=True) or {}
    aid = str(b.get("agent_id") or "")
    if not re.match(r"^[A-Za-z0-9._-]{1,64}$", aid):
        return jsonify({"error": "agent_id requis"}), 400
    local, pbs_groups, copies, base = _leftover_ctx(aid)
    items = repa.leftover_checks(b.get("items") or [], local, pbs_groups, copies, base)
    return jsonify({"items": items, "pbs_seen": bool(pbs_groups), "local_vms": len(local)}), 200


@app.route("/repatriation/cleanup/purge", methods=["POST"])
def repa_cleanup_purge_route():
    """#765 : {agent_id, item, reason, force, actor} -> commande xfer purge (conditions réévaluées ici ; forcer exige un motif)."""
    b = request.get_json(silent=True) or {}
    aid, it, reason = str(b.get("agent_id") or ""), b.get("item") or {}, str(b.get("reason") or "").strip()
    if not re.match(r"^[A-Za-z0-9._-]{1,64}$", aid) or not it.get("path"):
        return jsonify({"error": "agent_id et item requis"}), 400
    if len(reason) < 8:
        return jsonify({"error": "motif requis (8 caractères au moins)"}), 400
    local, pbs_groups, copies, base = _leftover_ctx(aid)
    ev = repa.leftover_checks([it], local, pbs_groups, copies, base)[0]
    if not ev["ok"] and not b.get("force"):
        ko = [c["label"] for c in ev["checks"] if c["required"] and not c["ok"]]
        return jsonify({"error": "conditions non remplies : %s (forcer avec un motif)" % ", ".join(ko), "item": ev}), 409
    params = {"action": "purge", "path": it["path"], "confirm": it["path"].rsplit("/", 1)[-1], "reason": reason,
              "actor": str(b.get("actor") or ""), "force": bool(b.get("force")) and not ev["ok"]}
    c = store.create_command(DB_PATH, aid, "xfer", params)
    return jsonify({"command": c, "item": ev}), 201


@app.route("/repatriation", methods=["POST"])
def repa_create_route():
    b = request.get_json(silent=True) or {}
    remote, pve = str(b.get("remote") or "").strip(), str(b.get("pve_agent_id") or "").strip()
    if not re.match(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$", remote) or not re.match(r"^[A-Za-z0-9._-]{1,64}$", pve):
        return jsonify({"error": "remote (nœud distant) et pve_agent_id (agent du nœud local) requis"}), 400
    name = str(b.get("name") or "Rapatriement %s" % remote)[:100]
    cid = _repa_db("INSERT INTO repatriation (name, remote, pve_agent_id, storage, settings, created_at, updated_at, by_user) VALUES (?,?,?,?,?,?,?,?)",
                   (name, remote, pve, str(b.get("storage") or ""), json.dumps(repa.DEFAULT_SETTINGS), store.now_iso(), store.now_iso(), str(b.get("actor") or "")), write=True)
    return jsonify(_repa_full(_repa_db("SELECT * FROM repatriation WHERE id = ?", (cid,), one=True))), 201


@app.route("/repatriation/<int:cid>", methods=["GET"])
def repa_get_route(cid):
    row = _repa_db("SELECT * FROM repatriation WHERE id = ?", (cid,), one=True)
    if not row:
        return jsonify({"error": "campagne inconnue"}), 404
    return jsonify(_repa_full(row)), 200


@app.route("/repatriation/<int:cid>", methods=["PUT"])
def repa_put_route(cid):
    """{step, storage, settings, decisions: {vmid: décision}, newids: {vmid: id}, name}"""
    row = _repa_db("SELECT * FROM repatriation WHERE id = ?", (cid,), one=True)
    if not row:
        return jsonify({"error": "campagne inconnue"}), 404
    b = request.get_json(silent=True) or {}
    c = _repa_full(row)
    if b.get("step") is not None and b["step"] not in repa.STEP_IDS:
        return jsonify({"error": "étape inconnue"}), 400
    dec, nid = b.get("decisions") or {}, b.get("newids") or {}
    for g in c["guests"]:
        k = str(g["vmid"])
        if k in dec:
            if dec[k] not in repa.DECISIONS:
                return jsonify({"error": "décision : rapatrier, garder, supprimer"}), 400
            if g.get("run_id") and dec[k] != "rapatrier":
                return jsonify({"error": "%s : déjà lancé, utiliser Abandonner" % k}), 409
            g["decision"] = dec[k]
        if k in nid and not g.get("run_id"):
            try:
                g["newid"] = int(nid[k]) if nid[k] not in (None, "") else None
            except (TypeError, ValueError):
                return jsonify({"error": "nouvel identifiant entier"}), 400
    settings = dict(c["settings"], **{k: v for k, v in (b.get("settings") or {}).items() if k in repa.DEFAULT_SETTINGS})
    keep = [{k: v for k, v in g.items() if k not in ("phase", "phase_label", "phase_detail", "run")} for g in c["guests"]]
    _repa_db("UPDATE repatriation SET name = ?, step = ?, storage = ?, settings = ?, guests = ?, updated_at = ? WHERE id = ?",
             (str(b.get("name") or c["name"])[:100], b.get("step") or c["step"], str(b.get("storage") if b.get("storage") is not None else c["storage"]),
              json.dumps(settings), json.dumps(keep, ensure_ascii=False), store.now_iso(), cid), write=True)
    return jsonify(_repa_full(_repa_db("SELECT * FROM repatriation WHERE id = ?", (cid,), one=True))), 200


def _resume_first_checkpoint(rid):
    """La transition 1 du plan (« prévenir ») est faite par l'étape Préparation de l'assistant : reprise automatique."""
    import time as _t
    for _ in range(60):
        _t.sleep(1)
        if pra.resume_run(DB_PATH, rid).get("ok"):
            return


@app.route("/repatriation/<int:cid>/launch", methods=["POST"])
def repa_launch_route(cid):
    """Lance un plan repatriate (#750) pour chaque invité « rapatrier » pas encore lancé (ou ceux de `vmids`)."""
    row = _repa_db("SELECT * FROM repatriation WHERE id = ?", (cid,), one=True)
    if not row:
        return jsonify({"error": "campagne inconnue"}), 404
    b = request.get_json(silent=True) or {}
    c = _repa_full(row)
    if not c["storage"]:
        return jsonify({"error": "stockage local à choisir (étape Préparation)"}), 400
    only = {int(x) for x in b.get("vmids") or []}
    used = {g.get("newid") for g in c["guests"] if g.get("newid")}
    launched, errors = [], []
    for g in c["guests"]:
        if g.get("decision") != "rapatrier" or g.get("run_id") or (only and g["vmid"] not in only) or not g.get("present", True):
            continue
        if not g.get("newid"):
            n = int(c["settings"]["newid_base"]) + g["vmid"] if g["vmid"] < 1000 else g["vmid"] + 90000
            while n in used:
                n += 1
            g["newid"] = n; used.add(n)
        s = c["settings"]
        plan, err = migration.build({"method": "repatriate", "pve_agent_id": c["pve_agent_id"], "remote": c["remote"], "vmid": g["vmid"], "newid": g["newid"],
                                     "kind": g.get("kind") or "lxc", "storage": c["storage"], "mode": s["mode"], "bwlimit_mbps": s["bwlimit_mbps"],
                                     "window": s["window"], "slice_gb": s["slice_gb"], "plan_name": "%s — %s %d %s" % (c["name"], c["remote"], g["vmid"], g.get("name") or "")})
        steps, err2 = pra.validate_steps(plan["steps"]) if plan else (None, err)
        if err or err2:
            errors.append("%d : %s" % (g["vmid"], err or err2)); continue
        pid = _repa_db("INSERT INTO pra_plans (name, kind, notes, steps, continue_on_error, created_at, updated_at, rollback_steps, auto_rollback) VALUES (?,?,?,?,?,?,?,?,?)",
                       (plan["name"], "migration", plan["notes"], json.dumps(steps, ensure_ascii=False), 0, store.now_iso(), store.now_iso(), "[]", 0), write=True)
        prow = _repa_db("SELECT * FROM pra_plans WHERE id = ?", (pid,), one=True)
        rid = pra.start_run(DB_PATH, pra.plan_public(prow), "execute", str(b.get("actor") or "assistant de rapatriement"))
        threading.Thread(target=_resume_first_checkpoint, args=(rid,), daemon=True).start()
        g.update(plan_id=pid, run_id=rid)
        launched.append(g["vmid"])
    keep = [{k: v for k, v in g.items() if k not in ("phase", "phase_label", "phase_detail", "run")} for g in c["guests"]]
    _repa_db("UPDATE repatriation SET guests = ?, step = ?, updated_at = ? WHERE id = ?",
             (json.dumps(keep, ensure_ascii=False), "rapatriement" if launched else c["step"], store.now_iso(), cid), write=True)
    _event("repatriation-launched", "info", "rapatriement « %s » : %d plan(s) lancé(s)%s" % (c["name"], len(launched), (" ; erreurs : " + " ; ".join(errors)) if errors else ""))
    return jsonify({"launched": launched, "errors": errors, "campaign": _repa_full(_repa_db("SELECT * FROM repatriation WHERE id = ?", (cid,), one=True))}), 200


@app.route("/repatriation/<int:cid>/guest/<int:vmid>/<action>", methods=["POST"])
def repa_guest_route(cid, vmid, action):
    """validate : copie validée -> la destruction de l'original part dans la plage horaire ; abort : abandon du plan."""
    row = _repa_db("SELECT * FROM repatriation WHERE id = ?", (cid,), one=True)
    g = next((x for x in repa.public(row)["guests"] if x["vmid"] == vmid), None) if row else None
    if not g or not g.get("run_id"):
        return jsonify({"error": "invité sans plan lancé"}), 404
    if action == "validate":
        r = pra.resume_run(DB_PATH, g["run_id"])
    elif action == "abort":
        r = pra.abort_run(DB_PATH, g["run_id"], by_user=str((request.get_json(silent=True) or {}).get("actor") or ""))
    else:
        return jsonify({"error": "action : validate, abort"}), 400
    return jsonify(r), 200 if r.get("ok") else 409


DIAG_HINTS = {   # #763 : que faire quand une source ne remonte rien
    "plugin:proxmox": "sonde proxmox des agents installés sur les PVE (activée à l'installation ; fiche de l'agent › Sondes)",
    "plugin:pve-remote": "sonde pve-remote sur l'agent qui joint les nœuds distants (PBS ou PVE local) : /etc/si-agent/pve-remote.json puis activer la sonde",
    "plugin:node-activity": "sonde node-activity sur les agents des PVE / PBS (fiche de l'agent › Sondes) ; nœuds distants : /etc/si-agent/pve-remote.json",
    "plugin:pbs": "sonde pbs sur l'agent du serveur de sauvegarde",
    "plugin:guest-usage": "sonde guest-usage sur l'agent qui joint les Proxmox (nœud local + /etc/si-agent/pve-remote.json), fiche de l'agent › Sondes",
    "plugin:ollama": "sonde ollama sur l'agent du poste d'IA",
    "plugin:hub-watch": "sonde hub-watch sur un agent d'un AUTRE hôte que le hub (fiche de l'agent › Sondes) + réglages dans /etc/si-agent/hub-watch/args",   # #793
    "plugin:sms-gateway": "sonde sms-gateway sur un agent Linux du LAN (fiche de l'agent › Sondes) + réglages dans /etc/si-agent/sms-gateway/args",   # #792
    "plugin:remote-status": "sonde remote-status sur un agent Linux du LAN (fiche de l'agent › Sondes) + cibles dans /etc/si-agent/remote-status/args",   # #792
    "plugin:gpu": "sonde gpu sur l'agent de chaque hôte à carte graphique (fiche de l'agent › Sondes, ou tuile Parc IA)",
    "plugin:docker-containers": "sonde docker-containers sur l'agent de l'hôte Docker",
    "plugin:wifi-monitor": "sonde wifi-monitor sur l'agent d'une sonde à carte Wi-Fi USB en mode moniteur (Alfa AWUS036ACM ; kit netprobe/rpi --alfa monitor)",   # #801
    "plugin:collecte-sondes": "sonde collecte-sondes sur l'agent du mini-PC du site qui porte le collecteur (si-agent/local-central/installer-collecteur.sh), fiche de l'agent › Sondes",   # #806
    "plugin:rf-spectrum": "sonde rf-spectrum sur l'agent d'une sonde équipée d'un HackRF / PortaPack en mode HackRF (paquet hackrf ; kit netprobe/rpi --hackrf)",
    "plugin:mail-server": "sonde mail-server sur l'agent du serveur de messagerie",
    "plugin:pve-preflight": "sonde pve-preflight sur l'agent qui joint les Proxmox (nœud local + /etc/si-agent/pve-remote.json, comme guest-usage), fiche de l'agent › Sondes",   # #815
    "host": "relevé de base de tout agent (agent arrêté ou injoignable si absent)",
}


@app.route("/diag/tasks", methods=["GET"])
def diag_tasks_route():
    """#763 : état des sources d'un écran -- pour chaque tâche (sonde), les agents qui la remontent, l'âge de la dernière
    mesure, sa réussite et son erreur ; + une indication quand rien ne remonte. Sert le bandeau « État des données »."""
    tasks = [t for t in (request.args.get("tasks") or "").split(",") if re.match(r"^[a-z0-9:_-]{1,64}$", t)][:12]
    now = time.time()
    conn = store._connect(DB_PATH)
    out = []
    try:
        for t in tasks:
            rows = conn.execute("SELECT a.agent_id, a.hostname, a.last_seen_at, m.at, m.ok, m.error, m.received_at FROM agents a JOIN (SELECT agent_id, MAX(at) AS at FROM measurements "
                                "WHERE task = ? GROUP BY agent_id) l ON l.agent_id = a.agent_id JOIN measurements m ON m.agent_id = l.agent_id AND m.at = l.at AND m.task = ?", (t, t)).fetchall()
            agents = []
            for r in rows:
                try:
                    import calendar as _cal
                    age = int(now - _cal.timegm(time.strptime(r["at"][:19], "%Y-%m-%dT%H:%M:%S")))
                except (TypeError, ValueError):
                    age = None
                agents.append({"agent_id": r["agent_id"], "hostname": r["hostname"], "at": r["at"], "age_s": age, "ok": bool(r["ok"]), "error": r["error"]})
            out.append({"task": t, "agents": agents, "hint": DIAG_HINTS.get(t, "")})
    finally:
        conn.close()
    return jsonify({"tasks": out, "at": store.now_iso()}), 200


@app.route("/views", methods=["GET"])
def views_route():
    """#753 : vues de parc (groupes d'agents) -- réglage partagé, vues par défaut tant que rien n'est enregistré."""
    return jsonify({"views": store.get_setting(DB_PATH, "fleet_views", None) or views.DEFAULT_VIEWS}), 200


@app.route("/views", methods=["PUT"])
def views_save_route():
    body = request.get_json(silent=True) or {}
    v, err = views.normalize(body.get("views"))
    if err:
        return jsonify({"error": err}), 400
    store.set_setting(DB_PATH, "fleet_views", v)
    _event("views-saved", "info", "vues de parc enregistrées (%d vue(s)) par %s" % (len(v), body.get("actor") or "?"))
    return jsonify({"views": v}), 200


@app.route("/views/<vid>/overview", methods=["GET"])
def views_overview_route(vid):
    """#753 : en-tête « htop » de chaque agent de la vue, groupe par groupe, plus les agents non rangés."""
    view = next((v for v in (store.get_setting(DB_PATH, "fleet_views", None) or views.DEFAULT_VIEWS) if v["id"] == vid), None)
    if not view:
        return jsonify({"error": "vue inconnue"}), 404
    rows = {a["agent_id"]: views.row(a, store.latest_per_task(DB_PATH, a["agent_id"])) for a in store.fleet(DB_PATH)}
    return jsonify(views.overview(view, rows)), 200


ASSISTANT_API_URL = os.environ.get("ASSISTANT_API_URL", "http://assistant-api:5000/assistant").rstrip("/")   # #756
IA_ASSISTANT_PATHS = ("status", "eval/summary", "eval/last", "journal/stats")


@app.route("/ia/overview", methods=["GET"])
def ia_overview_route():
    """#756 : tuile Parc IA -- hôtes portant Ollama (sonde) ou déclarés (réglage ia_hosts) : en-tête htop, modèles,
    conteneurs Docker (sonde docker-containers)."""
    extra = store.get_setting(DB_PATH, "ia_hosts", None) or []
    hosts = []
    for a in store.fleet(DB_PATH):
        if not {"ollama", "gpu"} & set(a.get("plugin_ids") or []) and a["agent_id"] not in extra:   # #782 : gpu aussi
            continue
        latest = store.latest_per_task(DB_PATH, a["agent_id"])
        r = views.row(a, latest)
        ol = (latest.get("plugin:ollama") or {}).get("data") or {}
        dk = (latest.get("plugin:docker-containers") or {})
        r.update(ollama_data=ol or None, models=ol.get("models") or [], ollama_url=ol.get("url"), ollama_error=ol.get("error"), ollama_at=(latest.get("plugin:ollama") or {}).get("at"),
                 models_dir=ol.get("models_dir"), ollama_alerts=ol.get("alerts") or [], declared=a["agent_id"] in extra, os_family=a.get("os"),
                 virtualization=a.get("virtualization"), hardware_model=a.get("hardware_model"),
                 containers=(dk.get("data") or {}).get("containers"), containers_at=dk.get("at"), containers_error=dk.get("error"))
        hosts.append(r)
    return jsonify({"hosts": sorted(hosts, key=lambda h: h["agent_id"]), "declared": extra, "assistant": bool(ASSISTANT_API_URL)}), 200


@app.route("/ia/hosts", methods=["PUT"])
def ia_hosts_route():
    """#756 : hôtes ajoutés à la main au Parc IA (ex. la VM qui fait tourner l'assistant sous Docker)."""
    body = request.get_json(silent=True) or {}
    ids = [str(x) for x in (body.get("agents") or []) if re.match(r"^[A-Za-z0-9._-]{1,64}$", str(x))][:100]
    store.set_setting(DB_PATH, "ia_hosts", ids)
    return jsonify({"declared": ids}), 200


@app.route("/ia/assistant/<path:sub>", methods=["GET"])
def ia_assistant_route(sub):
    """#756 : relais en lecture vers l'assistant (même origine pour le hub) -- état, évaluations, activité."""
    if sub not in IA_ASSISTANT_PATHS:
        return jsonify({"error": "chemin non relayé"}), 404
    try:
        import urllib.request
        q = ("?" + request.query_string.decode()) if request.query_string else ""
        with urllib.request.urlopen(ASSISTANT_API_URL + "/" + sub + q, timeout=20) as r:
            return app.response_class(r.read(), status=r.status, mimetype="application/json")
    except Exception as exc:  # noqa: BLE001 -- assistant arrêté ou absent (profil compose « assistant »)
        return jsonify({"error": "assistant injoignable (%s) : %s" % (ASSISTANT_API_URL, str(exc)[:200])}), 502


@app.route("/infra/overview", methods=["GET"])
def infra_overview_route():
    """#749 : tuile « Infra PVE / PBS » -- nœuds locaux et distants, VM, transferts, totaux, constats."""
    conn = store._connect(DB_PATH)
    try:
        args = [infra.latest(conn, t) for t in ("plugin:node-activity", "plugin:proxmox", "plugin:pve-remote", "plugin:pbs")]
    finally:
        conn.close()
    return jsonify(infra.overview(*args)), 200


HTOP_RELAIS_URL = os.environ.get("HTOP_RELAIS_URL", "")
HTOP_JETON_INTERNE = os.environ.get("HTOP_JETON_INTERNE", "")


def htop_tick():
    """#800 : constats du relais si-htop apparus / aggravés -> « htop-alert », disparus -> « htop-recovered »."""
    if not HTOP_RELAIS_URL:
        return
    code, d = htoprelay.lire(HTOP_RELAIS_URL, HTOP_JETON_INTERNE, "/constats")
    if code != 200:
        return
    evs, apres = htoprelay.transitions(store.get_setting(DB_PATH, "htop_constats", {}) or {}, d.get("constats"))
    for kind, sev, msg, det in evs:
        _event(kind, sev, msg, details=det, source="htop")
    if evs:
        store.set_setting(DB_PATH, "htop_constats", apres)


@app.route("/datarf", methods=["GET"])
def datarf_route():
    """#806 : tuile « Data RF » -- sondes radio des sites (collecte du mini-PC de chaque site + sondes enrôlées directement)."""
    conn = store._connect(DB_PATH)
    try:
        collectes = infra.latest(conn, "plugin:collecte-sondes")
        directes = {t: infra.latest(conn, t) for t, _c in datarf.DIRECTES}
    finally:
        conn.close()
    borne = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 2 * 3600))   # #812 : sondes directes désactivées depuis 2 h
    return jsonify(datarf.assembler(collectes, directes, borne)), 200


@app.route("/datarf/config", methods=["GET"])
def datarf_config_get():
    """#807 : configuration radio mémorisée d'une sonde (?sonde=) -- rôles des interfaces, SSID, noms d'accès du coffre (jamais de clé)."""
    sonde = str(request.args.get("sonde") or "").strip()
    if not re.match(r"^[A-Za-z0-9._-]{1,64}$", sonde):
        return jsonify({"error": "sonde requise"}), 400
    return jsonify({"sonde": sonde, "config": store.get_setting(DB_PATH, "datarf_config:" + sonde.lower(), None)}), 200


@app.route("/datarf/config", methods=["POST"])
def datarf_config_post():
    """#807 : {sonde, via_agent | agent_id, action: etat | appliquer, interfaces, ssids:[{ssid, acces, actif, iface}], actor}
    -> commande wifi_config (sonde directe) ou collecteur (sonde d'un site, par l'agent du mini-PC). Clés lues dans le coffre."""
    b = request.get_json(silent=True) or {}
    sonde = str(b.get("sonde") or "").strip()
    via, aid = str(b.get("via_agent") or "").strip() or None, str(b.get("agent_id") or "").strip() or None
    if not re.match(r"^[A-Za-z0-9._-]{1,64}$", sonde) or not (via or aid):
        return jsonify({"error": "sonde et via_agent (collecteur du site) ou agent_id (sonde directe) requis"}), 400
    if b.get("action") == "etat":
        params, memo = {"action": "etat"}, None
    else:
        params, memo, err = datarf.preparer_config(b, reveler_acces)
        if err:
            return jsonify({"error": err}), 400
    cible, ctype, cparams = datarf.commande(sonde, via, aid, params)
    try:
        cmd = store.create_command(DB_PATH, cible, ctype, cparams)
    except (ValueError, KeyError) as e:
        return jsonify({"error": str(e)}), 400
    if cmd is None:
        return jsonify({"error": "agent inconnu : %s" % cible}), 404
    open_interactive(cible, 180)                     # relève rapide des commandes : la suite arrive vite
    if memo is not None:
        store.set_setting(DB_PATH, "datarf_config:" + sonde.lower(), memo)
        _event("datarf-config", "info", "configuration radio de %s envoyée par %s (%d SSID actifs, %s)" % (
            sonde, str(b.get("actor") or "?")[:64], sum(1 for s in memo["ssids"] if s["actif"]), ", ".join("%s=%s" % kv for kv in sorted(memo["interfaces"].items())) or "interfaces inchangées"),
            details={"sonde": sonde, "via": via, "commande": (cmd or {}).get("id")})
    return jsonify({"ok": True, "id": cmd["id"], "agent_id": cible, "type": ctype}), 201   # jamais les paramètres (clés du coffre)


@app.route("/htop", methods=["GET"])
def htop_route():
    """#800 : tuile « htop » -- état du relais si-htop (hôtes en direct, constats, seuils, pics 24 h)."""
    code, d = htoprelay.lire(HTOP_RELAIS_URL, HTOP_JETON_INTERNE, "/etat")
    return jsonify(d), code


@app.route("/htop/hote/<nom>", methods=["GET"])
def htop_hote_route(nom):
    """#800 : détail d'un hôte (courbes 10 min et 24 h, processus, invités)."""
    code, d = htoprelay.lire(HTOP_RELAIS_URL, HTOP_JETON_INTERNE, htoprelay.chemin_hote(nom))
    return jsonify(d), code


@app.route("/infra/guests", methods=["GET"])
def guest_usage_route():
    """#769 : écran « Activité des VM » -- dernière mesure guest-usage de chaque agent + invités de l'inventaire Infra + fiches."""
    conn = store._connect(DB_PATH)
    try:
        reports = infra.latest(conn, "plugin:guest-usage")
        profiles = guestusage.load_profiles(conn)
        act = guestusage.activity(conn)   # #771 : activité dans le temps
    finally:
        conn.close()
    return jsonify(guestusage.assemble(reports, _infra_now().get("vms") or [], profiles, act)), 200


@app.route("/infra/guests/history", methods=["GET"])
def guest_history_route():
    """#771 : série quotidienne d'un CT / VM (?node=&vmid=&days=400) : web, login, mysql, rrd (jour), rrdw (semaine)."""
    node, vmid = str(request.args.get("node") or "").strip(), request.args.get("vmid", type=int)
    days = max(1, min(request.args.get("days", default=400, type=int) or 400, 1500))
    if not re.match(r"^[A-Za-z0-9._-]{1,64}$", node) or not vmid:
        return jsonify({"error": "node et vmid requis"}), 400
    import datetime as _dt
    since = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
    conn = store._connect(DB_PATH)
    try:
        h = guestusage.history(conn, node, vmid, since)
    finally:
        conn.close()
    return jsonify({"node": node, "vmid": vmid, "since": since, "series": h}), 200


@app.route("/infra/guests/profile", methods=["PUT"])
def guest_profile_route():
    """#769 : {node, vmid, profile, actor} -> fiche de paramétrage d'un CT / VM (vide = effacée). Tout champ « secret » est refusé."""
    b = request.get_json(silent=True) or {}
    node, vmid = str(b.get("node") or "").strip(), b.get("vmid")
    if not re.match(r"^[A-Za-z0-9._-]{1,64}$", node) or not isinstance(vmid, int) or not 0 < vmid < 1000000000:
        return jsonify({"error": "node et vmid requis"}), 400
    prof, err = guestusage.normalize_profile(b.get("profile") or {})
    if err:
        return jsonify({"error": err}), 400
    actor = str(b.get("actor") or "")[:64]
    conn = store._connect(DB_PATH)
    try:
        guestusage.save_profile(conn, node, vmid, prof, store.now_iso(), actor)
    finally:
        conn.close()
    _event("guest-profile", "info", "fiche de %s/%s %s par %s (%s)" % (node, vmid, "enregistrée" if prof else "effacée", actor or "?", ", ".join(sorted(prof)) or "vide"),
           details={"node": node, "vmid": vmid, "fields": sorted(prof)})
    return jsonify({"ok": True, "profile": prof}), 200


@app.route("/edge", methods=["GET"])
def edge_view_route():
    """#776 : proxys (état, empreinte, serveurs internes joignables), routes (serveur actif, candidats, DNS), problèmes et solutions."""
    return jsonify(_lat(edgepair.view)), 200


@app.route("/edge/preview", methods=["GET"])
def edge_preview_route():
    return jsonify(_lat(edgepair.preview)), 200


@app.route("/edge/proxies", methods=["PUT"])
def edge_proxy_route():
    b = request.get_json(silent=True) or {}
    p, err = _lat(lambda c: edgepair.save_proxy(c, b.get("proxy") or {}, str(b.get("actor") or "")[:64]))
    return (jsonify({"error": err}), 400) if err else (jsonify({"ok": True, "proxy": p}), 200)


@app.route("/edge/routes", methods=["PUT"])
def edge_route_route():
    b = request.get_json(silent=True) or {}
    actor = str(b.get("actor") or "")[:64]

    def go(c):
        r, err = edgepair.save_route(c, b.get("route") or {}, actor)
        if not err and b.get("apply", True):
            edgepair.apply_all(c, actor)
        return r, err
    r, err = _lat(go)
    return (jsonify({"error": err}), 400) if err else (jsonify({"ok": True, "route": r}), 200)


@app.route("/edge/<what>/<oid>", methods=["DELETE"])
def edge_delete_route(what, oid):
    if what not in ("route", "proxy"):
        return jsonify({"error": "route ou proxy"}), 400
    actor = str(request.args.get("actor") or "")[:64]

    def go(c):
        ok = edgepair.delete(c, what, oid, actor)
        if ok and what == "route":
            edgepair.apply_all(c, actor)
        return ok
    return jsonify({"ok": _lat(go)}), 200


@app.route("/edge/switch", methods=["POST"])
def edge_switch_route():
    """{route, backend, actor} -> le serveur interne actif de la route change, appliqué aux deux proxys."""
    b = request.get_json(silent=True) or {}
    actor = str(b.get("actor") or "")[:64]

    def go(c):
        r, err = edgepair.switch_backend(c, str(b.get("route") or ""), str(b.get("backend") or ""), actor)
        if not err:
            edgepair.apply_all(c, actor)
        return r, err
    r, err = _lat(go)
    if err:
        return jsonify({"error": err}), 400
    _event("edge", "info", "proxys d'entrée : %s renvoyé vers %s par %s" % (r.get("name") or r["id"], r["backend"], actor or "?"))
    return jsonify({"ok": True, "route": r, "message": "%s -> %s : appliqué aux deux proxys" % (r.get("name") or r["id"], r["backend"])}), 200


@app.route("/edge/settings", methods=["PUT"])
def edge_settings_route():
    b = request.get_json(silent=True) or {}
    s, err = _lat(lambda c: edgepair.set_settings(c, b.get("settings") or {}, str(b.get("actor") or "")[:64]))
    return (jsonify({"error": err}), 400) if err else (jsonify({"ok": True, "settings": s}), 200)


@app.route("/edge/apply", methods=["POST"])
def edge_apply_route():
    b = request.get_json(silent=True) or {}
    n = _lat(lambda c: edgepair.apply_all(c, str(b.get("actor") or "")[:64]))
    return jsonify({"ok": True, "message": "configuration envoyée à %d proxy(s)" % n}), 200


@app.route("/edge/dns-check", methods=["POST"])
def edge_dns_route():
    n = _lat(lambda c: edgepair.check_dns(c, time.time(), event=lambda kind, sev, msg, det: _event(kind, sev, msg, details=det), force=True))
    return jsonify({"ok": True, "message": "%d nom(s) contrôlé(s)" % n}), 200


def _lat(fn):
    conn = store._connect(DB_PATH)
    try:
        out = fn(conn)
        conn.commit()
        return out
    finally:
        conn.close()


@app.route("/navigateurs", methods=["GET", "PUT"])
def navigateurs_route():
    """#798 : registre des navigateurs d'hôte -- GET liste (avec l'état de l'agent), PUT {navigateurs: [...]} remplace."""
    if request.method == "PUT":
        b = request.get_json(silent=True) or {}
        connus = {a["agent_id"] for a in store.list_agents(DB_PATH)}
        liste, err = navigateurs.valider(b.get("navigateurs"), connus)
        if err:
            return jsonify({"error": err}), 400
        store.set_setting(DB_PATH, "navigateurs", liste)
        _event("navigateurs", "info", "navigateurs des hôtes : %d déclaré(s) par %s" % (len(liste), str(b.get("actor") or "?")[:64]))
    agents = {a["agent_id"]: a for a in store.list_agents(DB_PATH)}
    out = []
    for n in store.get_setting(DB_PATH, "navigateurs", []) or []:
        a = agents.get(n["agent_id"]) or {}
        out.append(dict(n, hostname=a.get("hostname"), os=a.get("os"), last_seen_at=a.get("last_seen_at"), agent_version=a.get("agent_version")))
    return jsonify({"navigateurs": out}), 200


@app.route("/services-poste", methods=["GET", "PUT"])
def services_poste_route():
    """#928 : liste des sites de service testés depuis un poste (GET) / remplacement (PUT {services:[...], actor}).
    Aucun secret dans la liste : seulement le NOM d'un accès du coffre."""
    if request.method == "PUT":
        b = request.get_json(silent=True) or {}
        liste, err = services_poste.valider(b.get("services"))
        if err:
            return jsonify({"error": err}), 400
        store.set_setting(DB_PATH, "services-poste", liste)
        _event("services-poste", "info", "sites de service : %d déclaré(s) par %s" % (len(liste), str(b.get("actor") or "?")[:64]))
    return jsonify({"services": store.get_setting(DB_PATH, "services-poste", []) or []}), 200


@app.route("/postes-sauvegarde", methods=["GET", "PUT"])
def postes_sauvegarde_route():
    """#930 : réglage de la sauvegarde des postes -- liste éditée des confs + options (catalogue, déduction). GET
    renvoie le réglage et le catalogue par défaut ; PUT {confs, inclure_catalogue, inclure_deduit, actor} remplace."""
    if request.method == "PUT":
        b = request.get_json(silent=True) or {}
        liste, err = sauvegarde_conf.valider(b.get("confs"))
        if err:
            return jsonify({"error": err}), 400
        reglage = {"confs": liste, "inclure_catalogue": bool(b.get("inclure_catalogue", True)), "inclure_deduit": bool(b.get("inclure_deduit", False))}
        store.set_setting(DB_PATH, "postes-sauvegarde", reglage)
        _event("sauvegarde", "info", "réglage de sauvegarde des postes mis à jour par %s" % str(b.get("actor") or "?")[:64])
    reglage = store.get_setting(DB_PATH, "postes-sauvegarde", {"confs": [], "inclure_catalogue": True, "inclure_deduit": False})
    return jsonify({"reglage": reglage, "catalogue": sauvegarde_conf.CATALOGUE_DEFAUT}), 200


def _poste_windows_releve(agent_id):
    """Dernier relevé poste-windows d'un agent -> le bloc « reinstallation » (montages, logiciels) ou {}."""
    ms = store.list_measurements(DB_PATH, agent_id, task="plugin:poste-windows", limit=1)
    return ((ms[0].get("data") if ms else None) or {}).get("reinstallation") or {}


@app.route("/agents/<agent_id>/sauvegarde/lancer", methods=["POST"])
def sauvegarde_lancer_route(agent_id):
    """#930 : lance la sauvegarde confs+montages sur `agent_id`. Les confs finales sont calculées (catalogue +
    déduction des logiciels relevés + liste éditée) ; les montages viennent du dernier relevé poste-windows ; les
    identifiants du partage UNC sont révélés depuis le coffre et n'apparaissent jamais en réponse ni en trace.
    {destinations:{usb, unc:{chemin, acces?}}, actor}."""
    b = request.get_json(silent=True) or {}
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    reglage = store.get_setting(DB_PATH, "postes-sauvegarde", {"confs": [], "inclure_catalogue": True, "inclure_deduit": False})
    pw = _poste_windows_releve(agent_id)
    confs = sauvegarde_conf.cibles(reglage.get("confs"), pw.get("logiciels"),
                                   bool(reglage.get("inclure_catalogue", True)), bool(reglage.get("inclure_deduit", False)))
    if not confs:
        return jsonify({"error": "aucune configuration à sauvegarder (régler la liste : onglet « Sauvegarde »)"}), 400
    montages = sauvegarde_conf.montages_du_releve(pw)
    d = b.get("destinations") if isinstance(b.get("destinations"), dict) else {}
    dest = {}
    if str(d.get("usb") or "").strip():
        dest["usb"] = str(d["usb"]).strip()
    coffre_ko = None
    if isinstance(d.get("unc"), dict) and str(d["unc"].get("chemin") or "").strip():
        unc = {"chemin": str(d["unc"]["chemin"]).strip()}
        acces = str(d["unc"].get("acces") or "").strip()
        if acces:
            try:
                c = reveler_acces(acces)
                unc.update(user=c.get("username") or "", secret=c.get("password") or "", avec_identifiants=True)
            except RuntimeError as e:
                coffre_ko = str(e)
        dest["unc"] = unc
    if not dest:
        return jsonify({"error": "aucune destination : préciser une clé USB et/ou un partage"}), 400
    try:
        c = store.create_command(DB_PATH, agent_id, "sauvegarde-poste", {"confs": confs, "montages": montages, "destinations": dest})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    _event("sauvegarde", "info", "sauvegarde envoyée à %s : %d application(s), %d lecteur(s), %d partage(s)%s par %s"
           % (agent_id, len(confs), len(montages.get("lecteurs") or []), len(montages.get("partages") or []),
              (" -- accès coffre indisponible" if coffre_ko else ""), str(b.get("actor") or "?")[:64]),
           agent_id=agent_id, details={"confs": len(confs), "destinations": [k for k in dest]})
    return jsonify({"command": c["id"], "confs": len(confs), "montages": {"lecteurs": len(montages.get("lecteurs") or []),
                    "partages": len(montages.get("partages") or []), "imprimantes": len(montages.get("imprimantes") or [])},
                    "destinations": [k for k in dest], "coffre_indisponible": coffre_ko,
                    "note_poste_windows": None if pw else "aucun relevé poste-windows : lance d'abord la sonde poste-windows pour inclure les montages"}), 200


@app.route("/postes-sauvegarde-pbs", methods=["GET", "PUT"])
def postes_sauvegarde_pbs_route():
    """#931 : réglage de la poussée vers PBS (pbs10). GET renvoie le réglage (jamais de secret) ; PUT le remplace.
    { pousseur, repository, namespace, fingerprint, acces (nom d'accès du coffre pour le jeton), base_partage, actor }.
    Le dépôt (`repository`) contient le NOM du jeton, pas son secret -- le secret reste au coffre."""
    if request.method == "PUT":
        b = request.get_json(silent=True) or {}
        reglage = {"pousseur": str(b.get("pousseur") or "").strip(), "repository": str(b.get("repository") or "").strip(),
                   "namespace": str(b.get("namespace") or "postes").strip(), "fingerprint": str(b.get("fingerprint") or "").strip(),
                   "acces": str(b.get("acces") or "").strip(), "base_partage": str(b.get("base_partage") or "").strip()}
        store.set_setting(DB_PATH, "postes-sauvegarde-pbs", reglage)
        _event("sauvegarde", "info", "réglage poussée PBS mis à jour par %s" % str(b.get("actor") or "?")[:64])
    r = store.get_setting(DB_PATH, "postes-sauvegarde-pbs", {"pousseur": "", "repository": "", "namespace": "postes", "fingerprint": "", "acces": "", "base_partage": ""})
    return jsonify({"reglage": r}), 200


def _pbs_commande(action, backup_id=None, fichier=None):
    """Construit et envoie la commande pbs-push à l'agent pousseur (celui du serveur PBS). Résout le jeton au coffre.
    -> (reponse_json, code)."""
    r = store.get_setting(DB_PATH, "postes-sauvegarde-pbs", {}) or {}
    pousseur, repo = r.get("pousseur"), r.get("repository")
    if not pousseur or not repo:
        return {"error": "poussée PBS non configurée (onglet Sauvegarde › Pousser vers PBS)"}, 400
    if store.get_agent(DB_PATH, pousseur) is None:
        return {"error": "agent pousseur « %s » inconnu" % pousseur}, 400
    params = {"action": action, "repository": repo, "namespace": r.get("namespace") or "postes"}
    if r.get("fingerprint"):
        params["fingerprint"] = r["fingerprint"]
    if r.get("acces"):
        try:
            c = reveler_acces(r["acces"])
            params["token_secret"] = c.get("password") or ""
        except RuntimeError as e:
            return {"error": "jeton PBS indisponible au coffre : %s" % e}, 502
    if action == "push":
        params["backup_id"] = backup_id
        params["fichier"] = fichier
    try:
        cmd = store.create_command(DB_PATH, pousseur, "pbs-push", params)
    except ValueError as e:
        return {"error": str(e)}, 400
    _event("pbs-push", "info", "poussée PBS (%s)%s envoyée à %s" % (action, (" de « %s »" % backup_id) if backup_id else "", pousseur),
           agent_id=pousseur, details={"action": action, "backup_id": backup_id})
    return {"command": cmd["id"], "pousseur": pousseur, "action": action}, 200


@app.route("/agents/<agent_id>/sauvegarde/pbs", methods=["POST"])
def sauvegarde_pbs_route(agent_id):
    """#931 : pousse vers PBS (pbs10) la dernière archive de sauvegarde du poste `agent_id`, OU fait un préflight
    (lecture seule). {action: push|preflight, actor}. L'archive doit avoir été écrite sur le partage de pbs10 ; le
    chemin local côté PBS = base_partage + nom de l'archive."""
    b = request.get_json(silent=True) or {}
    action = str(b.get("action") or "push")
    if action == "preflight":
        rep, code = _pbs_commande("preflight")
        return jsonify(rep), code
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    ms = store.list_measurements(DB_PATH, agent_id, task="sauvegarde-poste", limit=1)
    arch = (((ms[0].get("data") if ms else None) or {}).get("archive") or {}).get("nom") if ms else None
    if not arch:
        return jsonify({"error": "aucune archive de sauvegarde pour ce poste : lance d'abord une sauvegarde vers le partage de pbs10"}), 400
    r = store.get_setting(DB_PATH, "postes-sauvegarde-pbs", {}) or {}
    base = (r.get("base_partage") or "").rstrip("/")
    if not base:
        return jsonify({"error": "chemin du partage côté PBS non réglé (base_partage)"}), 400
    fichier = base + "/" + arch
    rep, code = _pbs_commande("push", backup_id=agent_id, fichier=fichier)
    if code == 200:
        rep["archive"] = arch
    return jsonify(rep), code


@app.route("/agents/<agent_id>/sauvegarde/pbs", methods=["GET"])
def sauvegarde_pbs_resultat_route(agent_id):
    """#931 : dernier résultat de poussée PBS concernant ce poste (mesure pbs-push de l'agent pousseur, backup_id = poste)."""
    r = store.get_setting(DB_PATH, "postes-sauvegarde-pbs", {}) or {}
    pousseur = r.get("pousseur")
    res = None
    if pousseur:
        for m in store.list_measurements(DB_PATH, pousseur, task="pbs-push", limit=20):
            d = m.get("data") or {}
            if d.get("action") == "push" and d.get("backup_id") == agent_id:
                res = {"at": m.get("at"), "resultat": d}
                break
    return jsonify({"agent": agent_id, "pousseur": pousseur, **(res or {"at": None, "resultat": None})}), 200


@app.route("/agents/<agent_id>/sauvegarde", methods=["GET"])
def sauvegarde_resultat_route(agent_id):
    """#930 : dernier résultat de sauvegarde d'un agent (archive, destinations, constats ; sans secret)."""
    ms = store.list_measurements(DB_PATH, agent_id, task="sauvegarde-poste", limit=1)
    m = ms[0] if ms else None
    return jsonify({"agent": agent_id, "at": (m or {}).get("at"), "resultat": (m or {}).get("data")}), 200


@app.route("/agents/<agent_id>/acces-services/tester", methods=["POST"])
def acces_services_tester_route(agent_id):
    """#928 : lance le test d'accès aux services depuis `agent_id`. Révèle les accès du coffre et compose les cibles ;
    le secret ne sort jamais en réponse ni en trace (commande caviardée). {actor?, services?} -- services facultatifs
    pour tester une sélection ; sinon toute la liste configurée."""
    b = request.get_json(silent=True) or {}
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    if isinstance(b.get("services"), list):
        liste, err = services_poste.valider(b["services"])
        if err:
            return jsonify({"error": err}), 400
    else:
        liste = store.get_setting(DB_PATH, "services-poste", []) or []
    if not liste:
        return jsonify({"error": "aucun site de service configuré (régler la liste : onglet « Accès services »)"}), 400
    cibles, erreurs = services_poste.cibles_pour_mesure(liste, reveler_acces)
    try:
        c = store.create_command(DB_PATH, agent_id, "acces-services", {"cibles": cibles, "timeout": int(b.get("timeout") or 10)})
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    avec_auth = sum(1 for x in cibles if x.get("auth"))
    _event("acces-services", "info", "test d'accès aux services envoyé à %s (%d site(s), %d authentifié(s))%s par %s"
           % (agent_id, len(cibles), avec_auth, (" -- %d accès coffre indisponible(s)" % len(erreurs)) if erreurs else "",
              str(b.get("actor") or "?")[:64]), agent_id=agent_id,
           details={"sites": len(cibles), "authentifies": avec_auth, "coffre_ko": [e["nom"] for e in erreurs]})
    return jsonify({"command": c["id"], "sites": len(cibles), "authentifies": avec_auth, "coffre_indisponibles": erreurs}), 200


@app.route("/agents/<agent_id>/acces-services", methods=["GET"])
def acces_services_resultat_route(agent_id):
    """#928 : dernier résultat du test d'accès aux services d'un agent (temps bruts + authentifiés, sans secret)."""
    ms = store.list_measurements(DB_PATH, agent_id, task="acces-services", limit=1)
    m = ms[0] if ms else None
    return jsonify({"agent": agent_id, "at": (m or {}).get("at"), "resultat": (m or {}).get("data")}), 200


# -- #799/#800 : parcours appris dans le navigateur d'un hôte, joués avec les accès du coffre, demandés en langage courant --
CREDENTIALS_API_URL = os.environ.get("CREDENTIALS_API_URL", "http://credentials-api:5000").rstrip("/")


def reveler_acces(nom):
    """Identifiant et mot de passe d'un accès du coffre (credentials-api, jeton interne) -> {username, password}."""
    import urllib.error
    import urllib.parse
    import urllib.request
    tok = os.environ.get("CREDENTIALS_INTERNAL_TOKEN", "")
    if not tok:
        raise RuntimeError("CREDENTIALS_INTERNAL_TOKEN absent : accès du coffre indisponibles pour les parcours")
    req = urllib.request.Request("%s/credentials/reveal/%s" % (CREDENTIALS_API_URL, urllib.parse.quote(nom, safe="")),
                                 headers={"X-Credentials-Token": tok, "X-Credentials-Consumer": "si-agent-api/parcours"})
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError("coffre : accès « %s » : HTTP %d" % (nom, e.code))
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError("coffre injoignable : %s" % e)


def interpreter_demande(texte, catalogue):
    """Assistant du hub (modèle local) : demande en langage courant + catalogue -> {parcours_id, valeurs, confiance, explication}."""
    import urllib.error
    import urllib.request
    req = urllib.request.Request(ASSISTANT_API_URL + "/intent", data=json.dumps({"text": texte, "catalogue": catalogue}).encode(),
                                 method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=180) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError("assistant : HTTP %d %s" % (e.code, e.read()[:200].decode("utf-8", "replace")))
    except (urllib.error.URLError, OSError) as e:
        raise RuntimeError("assistant injoignable (%s) : %s" % (ASSISTANT_API_URL, e))


@app.route("/parcours", methods=["GET", "POST"])
def parcours_route():
    if request.method == "GET":
        return jsonify({"parcours": _lat(parcoursmod.lister)}), 200
    b = request.get_json(silent=True) or {}
    p, err = _lat(lambda c: parcoursmod.enregistrer(c, b.get("parcours") or {}, str(b.get("actor") or "")))
    if err:
        return jsonify({"error": err}), 400
    _event("parcours", "info", "parcours appris : « %s » (%d étape(s)) par %s" % (p["nom"], len(p["etapes"]), b.get("actor") or "?"))
    return jsonify({"parcours": p}), 201


@app.route("/parcours/<int:pid>", methods=["PUT", "DELETE"])
def parcours_item_route(pid):
    if request.method == "DELETE":
        return jsonify({"ok": _lat(lambda c: parcoursmod.supprimer(c, pid))}), 200
    b = request.get_json(silent=True) or {}
    p, err = _lat(lambda c: parcoursmod.enregistrer(c, b.get("parcours") or {}, str(b.get("actor") or ""), pid))
    return (jsonify({"error": err}), 404 if err == "parcours inconnu" else 400) if err else (jsonify({"parcours": p}), 200)


@app.route("/parcours/<int:pid>/jouer", methods=["POST"])
def parcours_jouer_route(pid):
    """{valeurs, confirmer, navigateur?, actor} -> commande « navigateur » sur l'hôte. Sans `confirmer`, arrêt avant la
    première étape qui écrit (le hub montre l'état et rejoue avec confirmer=true)."""
    b = request.get_json(silent=True) or {}
    p = _lat(lambda c: parcoursmod.lire(c, pid))
    if not p:
        return jsonify({"error": "parcours inconnu"}), 404
    nom_nav = str(b.get("navigateur") or p.get("navigateur") or "")
    nav = next((n for n in store.get_setting(DB_PATH, "navigateurs", []) or [] if n["nom"] == nom_nav), None)
    if not nav:
        return jsonify({"error": "navigateur « %s » non déclaré (tuile Navigateur des hôtes)" % (nom_nav or "?")}), 400
    coffre = None
    if p.get("acces"):
        try:
            coffre = reveler_acces(p["acces"])
        except RuntimeError as e:
            return jsonify({"error": str(e)}), 502
    etapes, manquants = parcoursmod.appliquer(p, b.get("valeurs") or {}, coffre)
    if manquants:
        return jsonify({"error": "valeur(s) manquante(s) : %s" % ", ".join(manquants), "manquants": manquants}), 400
    params = {"action": "etapes", "etapes": etapes, "base_url": p.get("base_url") or None,
              "arret_avant_ecriture": not bool(b.get("confirmer")), "parcours_id": pid}
    c = store.create_command(DB_PATH, nav["agent_id"], "navigateur", params)
    if c is None:
        return jsonify({"error": "agent inconnu : %s" % nav["agent_id"]}), 404
    open_interactive(nav["agent_id"], 300)
    _lat(lambda cn: parcoursmod.noter_jeu(cn, pid, c["id"]))
    _event("parcours", "info", "parcours « %s » joué sur %s%s par %s" % (p["nom"], nom_nav, " (écriture confirmée)" if b.get("confirmer") else "",
                                                                        str(b.get("actor") or "?")[:64]), agent_id=nav["agent_id"])
    return jsonify({"commande": c["id"], "agent_id": nav["agent_id"], "arret_avant_ecriture": params["arret_avant_ecriture"]}), 201


@app.route("/parcours/interpreter", methods=["POST"])
def parcours_interpreter_route():
    """#800 : {texte} -> plan {parcours_id, parcours, valeurs, manquants, confiance, explication, ecrit} (rien n'est joué)."""
    texte = str((request.get_json(silent=True) or {}).get("texte") or "").strip()
    if not texte:
        return jsonify({"error": "demande vide"}), 400
    liste = _lat(parcoursmod.lister)
    if not liste:
        return jsonify({"error": "aucun parcours appris : en apprendre un dans la tuile Navigateur des hôtes"}), 400
    try:
        r = interpreter_demande(texte[:2000], parcoursmod.catalogue(liste))
    except RuntimeError as e:
        return jsonify({"error": str(e)}), 502
    plan = parcoursmod.plan_depuis_interpretation(liste, (r or {}).get("parsed") if isinstance(r, dict) and "parsed" in r else r)
    plan["modele"] = (r or {}).get("model") if isinstance(r, dict) else None
    return jsonify(plan), (200 if plan.get("ok") else 422)


@app.route("/journal", methods=["GET", "PUT"])
def journal_route():
    """#795 : GET = entrées (filtre ?chantier=), chantiers, indicateurs ; PUT = ajout ou modification d'une entrée."""
    if request.method == "GET":
        return jsonify(_lat(lambda c: journal.view(c, (request.args.get("chantier") or "").strip() or None))), 200
    b = request.get_json(silent=True) or {}
    e, err = _lat(lambda c: journal.save(c, b.get("entry") or {}, str(b.get("actor") or "")[:64]))
    return (jsonify({"error": err}), 400) if err else (jsonify({"ok": True, "entry": e}), 200)


@app.route("/journal/<int:eid>", methods=["DELETE"])
def journal_delete_route(eid):
    return jsonify({"ok": _lat(lambda c: journal.delete(c, eid))}), 200


@app.route("/journal/import", methods=["POST"])
def journal_import_route():
    """{rows: [...]} (JSON) ou {csv: "...", chantier: "..."} (format de l'export) ; doublons ignorés."""
    b = request.get_json(silent=True) or {}
    rows = b.get("rows") if isinstance(b.get("rows"), list) else journal.parse_csv(str(b.get("csv") or ""), str(b.get("chantier") or ""))
    r = _lat(lambda c: journal.import_rows(c, rows, str(b.get("actor") or "")[:64]))
    if r["added"]:
        _event("journal", "info", "journal des chantiers : %d entrée(s) importée(s) par %s" % (r["added"], b.get("actor") or "?"))
    return jsonify(dict(r, ok=True)), 200


@app.route("/journal/export.csv", methods=["GET"])
def journal_export_route():
    ch = (request.args.get("chantier") or "").strip() or None
    body = _lat(lambda c: journal.to_csv(journal.list_entries(c, ch)))
    name = "journal-chantiers%s.csv" % ("-" + re.sub(r"[^A-Za-z0-9_-]+", "-", ch) if ch else "")
    return app.response_class(body.encode("utf-8"), mimetype="text/csv",
                              headers={"Content-Disposition": "attachment; filename=%s" % name})


@app.route("/journal/suggestions", methods=["GET"])
def journal_suggestions_route():
    days = max(1, min(request.args.get("days", default=30, type=int) or 30, 365))
    return jsonify({"suggestions": _lat(lambda c: journal.suggestions(c, days))}), 200


@app.route("/journal/suggestions/<int:event_id>", methods=["POST"])
def journal_accept_route(event_id):
    b = request.get_json(silent=True) or {}
    e, err = _lat(lambda c: journal.accept(c, event_id, str(b.get("actor") or "")[:64], (b.get("chantier") or "").strip() or None))
    return (jsonify({"error": err}), 400) if err else (jsonify({"ok": True, "entry": e}), 200)


@app.route("/latency", methods=["GET"])
def latency_view_route():
    """#775 : cibles × points de mesure (dernière mesure, diagnostic, médiane / p95 24 h), état des points, erreurs et solutions."""
    return jsonify(_lat(latency.view)), 200


@app.route("/latency/history", methods=["GET"])
def latency_history_route():
    t, p = str(request.args.get("target") or ""), str(request.args.get("point") or "")
    hours = max(1, min(request.args.get("hours", default=24, type=int) or 24, 24 * 31))
    return jsonify(_lat(lambda c: latency.history(c, t, p, hours))), 200


@app.route("/latency/targets", methods=["PUT"])
def latency_target_route():
    b = request.get_json(silent=True) or {}
    t, err = _lat(lambda c: latency.save_target(c, b.get("target") or {}, str(b.get("actor") or "")[:64]))
    return (jsonify({"error": err}), 400) if err else (jsonify({"ok": True, "target": t}), 200)


@app.route("/latency/points", methods=["PUT"])
def latency_point_route():
    b = request.get_json(silent=True) or {}
    p, err = _lat(lambda c: latency.save_point(c, b.get("point") or {}, str(b.get("actor") or "")[:64]))
    if err:
        return jsonify({"error": err}), 400
    _event("latency", "info", "point de mesure %s (%s) enregistré par %s" % (p["id"], p["mode"], b.get("actor") or "?"))
    return jsonify({"ok": True, "point": p}), 200


@app.route("/latency/<what>/<oid>", methods=["DELETE"])
def latency_delete_route(what, oid):
    if what not in ("target", "point"):
        return jsonify({"error": "target ou point"}), 400
    return jsonify({"ok": _lat(lambda c: latency.delete(c, what, oid))}), 200


@app.route("/latency/settings", methods=["PUT"])
def latency_settings_route():
    s, err = _lat(lambda c: latency.set_settings(c, request.get_json(silent=True) or {}))
    return (jsonify({"error": err}), 400) if err else (jsonify({"ok": True, "settings": s}), 200)


@app.route("/latency/run", methods=["POST"])
def latency_run_route():
    b = request.get_json(silent=True) or {}
    n = _lat(lambda c: latency.run_now(c, str(b.get("point") or "") or None))
    return jsonify({"ok": True, "launched": n, "message": "%d mesure(s) demandée(s), résultats d'ici une à deux minutes" % n}), 200


@app.route("/latency/config", methods=["GET", "PUT"])
def latency_config_route():
    """GET : export JSON (cibles, points, réglages) ; PUT : import (ajoute ou remplace par identifiant)."""
    if request.method == "GET":
        return jsonify(_lat(latency.export_config)), 200
    b = request.get_json(silent=True) or {}
    n, errs = _lat(lambda c: latency.import_config(c, b, str(b.get("actor") or "")[:64]))
    return jsonify({"ok": not errs, "imported": n, "errors": errs}), (200 if not errs else 207)


@app.route("/migration", methods=["GET"])
def migration_view_route():
    """#774 : plan, paramètres, marche (arrêtée / en cours / en pause / terminée ; manuel / auto), étapes avec état, mesure et erreur classée."""
    conn = store._connect(DB_PATH)
    try:
        v = migrun.view(conn)
        conn.commit()
    finally:
        conn.close()
    return jsonify(v), 200


@app.route("/priorites", methods=["GET"])
def priorites_route():
    """#818 : page d'accueil -- les 5 urgences (préparation par le modèle local, décision urgent / non urgent par le décideur,
    explication et solutions par le modèle conversationnel). ?refresh=1 relance le calcul (tâche de fond, gardé 15 min)."""
    def evenements():
        since = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(time.time() - 48 * 3600))
        return store.list_events(DB_PATH, since=since, limit=2000)

    def contacts():
        return {a["agent_id"]: a.get("last_seen_at") for a in store.list_agents(DB_PATH)}
    v = priorites.vue(evenements, contacts, forcer=request.args.get("refresh") == "1")
    try:   # #829 : tes décisions (✓ / ✎) sur les éléments affichés
        dec = apprentissage.decisions_par_cle()
        v = dict(v, urgences=[dict(u, decision=dec.get(str(u.get("id")))) for u in v.get("urgences") or []],
                 autres=[dict(u, decision=dec.get(str(u.get("id")))) for u in v.get("autres") or []])
    except Exception:  # noqa: BLE001
        pass
    return jsonify(v), 200


@app.route("/migration/preparation", methods=["GET"])
def migration_prep_route():
    """#815 : ?cible=<nœud à réinstaller>&accueil=<nœud qui reste>&debit_restore=&debit_lan=&ip_min=&demarrage_min=&quorum_min=&transferes=102,119
    -> quorum (et simulation sans la cible), contrôles « prêt à réinstaller », invités (santé, sauvegardes, PRA estimé)."""
    conn = store._connect(DB_PATH)
    try:
        reports = infra.latest(conn, "plugin:pve-preflight")
        lan = infra.latest(conn, "plugin:pulled-backups")
        profils = guestusage.load_profiles(conn)
        cands = _agents_proxmox(conn)
    finally:
        conn.close()
    noms = sorted(prep.noeuds(reports))
    cible = str(request.args.get("cible") or "") or next((n for n in noms if n.endswith("3")), noms[0] if noms else "")
    accueil = str(request.args.get("accueil") or "") or next((n for n in noms if n != cible), "")
    params = {}
    for k in prep.DEFAUTS:
        try:
            if request.args.get(k) not in (None, ""):
                params[k] = max(0.01, float(request.args.get(k)))
        except ValueError:
            return jsonify({"error": "%s : nombre attendu" % k}), 400
    transferes = [int(x) for x in str(request.args.get("transferes") or "").split(",") if x.strip().isdigit()]
    liens, manuel = _liens_sonde(cands)
    if not reports:
        return jsonify({"noeuds": [], "error": "aucun relevé pve-preflight : activer la sonde pve-preflight sur l'agent qui joint les Proxmox "
                                               "(nœud local + pve-remote.json, comme guest-usage)", "liens": liens, "manuel": manuel}), 200
    return jsonify(prep.assemble(reports, lan, profils, cible, accueil, params, transferes, liens_sonde=liens, manuel_sonde=manuel)), 200


# -- #856 : copies et sauvegardes, risques ---------------------------------------------------------------------------
def _inventaire():
    conn = store._connect(DB_PATH)
    try:
        reports = infra.latest(conn, "plugin:copies-inventory")
        cands = _agents_proxmox(conn)
    finally:
        conn.close()
    regles = store.get_setting(DB_PATH, "copies_regles", {}) or {}
    return reports, copies_lib.assemble(reports, regles), regles, cands


@app.route("/copies/inventaire", methods=["GET"])
def copies_inventaire_route():
    """#856 : toutes les copies (répliques, ZFS, instantanés, vzdump, PBS, flux, rsync, restaurés) et leur distance à la source."""
    reports, inv, regles, cands = _inventaire()
    liens, manuel = _liens_sonde(cands, "copies-inventory")
    if not reports:
        return jsonify({"invites": [], "hotes": [], "orphelines": [], "resume": {}, "regles": regles, "liens": liens, "manuel": manuel,
                        "error": "aucun relevé copies-inventory : activer la sonde copies-inventory sur l'agent qui joint les Proxmox "
                                 "(hôtes dans /etc/si-agent/copies-hosts.json, sinon nœuds de pve-remote.json)"}), 200
    return jsonify(dict(inv, regles=regles, liens=liens, manuel=manuel)), 200


@app.route("/copies/regles", methods=["PUT"])
def copies_regles_route():
    """#856 : {regles: {origines: {préfixe de chemin: nœud}, dans: {hôte: hôte physique}, sites: {hôte: site}}, actor}."""
    b = request.get_json(silent=True) or {}
    r = b.get("regles") or {}
    propre = {}
    for k in ("origines", "dans", "sites"):
        v = r.get(k, {})
        if v is None:
            v = {}
        if not isinstance(v, dict):
            return jsonify({"error": "%s : objet {clé: valeur} attendu" % k}), 400
        propre[k] = {str(a)[:200]: str(c)[:64] for a, c in list(v.items())[:200] if str(a).strip() and str(c).strip()}
    store.set_setting(DB_PATH, "copies_regles", propre)
    return jsonify({"regles": propre}), 200


def _acces_invites():
    conn = store._connect(DB_PATH)
    try:
        reports = infra.latest(conn, "plugin:pve-preflight")
    finally:
        conn.close()
    return prep.noeuds(reports)


def acces_passage():
    nodes = _acces_invites()
    etat = store.get_setting(DB_PATH, "acces_etat", {}) or {}
    e = acces_lib.passage(acces_lib.invites_en_marche(nodes), etat)
    cur = store.get_setting(DB_PATH, "acces_etat", {}) or {}
    e["manuels"] = cur.get("manuels") or {}          # une cible saisie pendant le passage n'est pas perdue
    store.set_setting(DB_PATH, "acces_etat", e)
    return e


def _acces_boucle():
    import fcntl
    try:
        fh = open(os.path.join(os.path.dirname(DB_PATH) or ".", "acces.lock"), "w")
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return
    time.sleep(60)
    while True:
        try:
            acces_passage()
        except Exception as e:  # noqa: BLE001 -- le contrôle d'accès ne fait jamais tomber l'API
            _log.warning("acces : %s", e)
        time.sleep(300)


if os.environ.get("ACCES_THREAD", "1") == "1":
    threading.Thread(target=_acces_boucle, name="acces", daemon=True).start()


@app.route("/migration/acces", methods=["PUT"])
def migration_acces_route():
    """#856 : {key: "nœud/vmid", cibles: ["https://…", "tcp://hôte:port"]} -> cibles manuelles d'un invité."""
    b = request.get_json(silent=True) or {}
    key = str(b.get("key") or "")
    if not re.match(r"^[A-Za-z0-9_.-]+/\d+$", key):
        return jsonify({"error": "key : nœud/vmid"}), 400
    cib = []
    for c in b.get("cibles") or []:
        c = str(c).strip()[:300]
        if re.match(r"^(https?://\S+|(tcp://)?[A-Za-z0-9_.:-]+:\d{1,5})$", c):
            cib.append(c)
        elif c:
            return jsonify({"error": "cible illisible : %s (https://…, tcp://hôte:port)" % c}), 400
    e = store.get_setting(DB_PATH, "acces_etat", {}) or {}
    e.setdefault("manuels", {})[key] = cib
    if not cib:
        e["manuels"].pop(key, None)
    store.set_setting(DB_PATH, "acces_etat", e)
    return jsonify({"key": key, "cibles": cib}), 200


@app.route("/migration/acces/verifier", methods=["POST"])
def migration_acces_verifier_route():
    """#856 : contrôle immédiat (en tâche de fond ; résultat au prochain affichage)."""
    threading.Thread(target=acces_passage, name="acces-maintenant", daemon=True).start()
    return jsonify({"ok": True, "message": "contrôle lancé"}), 202


@app.route("/migration/risques", methods=["GET"])
def migration_risques_route():
    """#856 : risque permanent de chaque CT / VM : réplication, sauvegarde, accès, support, nœud. ?cible=<nœud à réinstaller>"""
    reports, inv, _regles, cands = _inventaire()
    nodes = _acces_invites()
    e = store.get_setting(DB_PATH, "acces_etat", {}) or {}
    cible = str(request.args.get("cible") or store.get_setting(DB_PATH, "migration_cible", "") or "")
    r = risque_lib.assemble(inv, copies_lib.hotes(reports), nodes, e.get("resultats") or {}, cible or None)
    liens, manuel = _liens_sonde(cands, "copies-inventory")
    r.update(manuels=e.get("manuels") or {}, liens=liens, manuel=manuel,
             error=None if reports else "aucun relevé copies-inventory : activer la sonde copies-inventory (et pve-preflight pour l'accès aux services)")
    return jsonify(r), 200


@app.route("/migration/cible", methods=["PUT"])
def migration_cible_route():
    """#856 : nœud en cours de réinstallation (ses invités sont signalés dans les risques)."""
    b = request.get_json(silent=True) or {}
    store.set_setting(DB_PATH, "migration_cible", str(b.get("cible") or "")[:64])
    return jsonify({"cible": str(b.get("cible") or "")[:64]}), 200


# -- #857 : état des lieux des systèmes ---------------------------------------------------------------------------------
def _etat_plan(e):
    """#878 / #882 : plan estimé (barème en points, marge, regroupements de dépendances, phases, calendrier)."""
    import etat_plan
    r = store.get_setting(DB_PATH, "etat_plan", {}) or {}
    b = store.get_setting(DB_PATH, "etat_bareme", {}) or {}
    if "marge" not in b and r.get("marge"):
        b = dict(b, marge=r["marge"])
    try:
        import datetime as _dtm
        debut = _dtm.date.fromisoformat(r["debut"]) if r.get("debut") else None
    except ValueError:
        debut = None
    return etat_plan.plan(e, personnes=int(r.get("personnes") or 1), debut=debut, bareme=b)


@app.route("/etat-des-lieux/bareme", methods=["GET", "PUT"])
def etat_bareme_route():
    """#882 : barème des estimations façon planning poker. GET -> pesage (types, points, occurrences dans l'état actuel,
    totaux) ; PUT {points: {type: n}, heures_par_point, marge, seuil_reconstruction, logiciel_avec_os} -> enregistre ;
    PUT {defaut: true} -> revient au barème par défaut."""
    import etat_plan
    if request.method == "PUT":
        b = request.get_json(silent=True) or {}
        store.set_setting(DB_PATH, "etat_bareme", {} if b.get("defaut") else etat_plan.bareme_normalise(b))
    return jsonify(etat_plan.pesage(_etat()[1], store.get_setting(DB_PATH, "etat_bareme", {}) or {})), 200


@app.route("/etat-des-lieux/plan", methods=["GET", "PUT"])
def etat_plan_route():
    """#878 : GET -> plan estimé ; PUT {marge, personnes, debut} -> réglages (marge 1 à 10, 1 à 20 personnes, AAAA-MM-JJ)."""
    if request.method == "PUT":
        b = request.get_json(silent=True) or {}
        try:
            r = {"personnes": min(20, max(1, int(b.get("personnes", 1)))), "debut": str(b.get("debut") or "")[:10] or None}
            if b.get("marge") not in (None, ""):   # #882 : la marge vit dans le barème
                bar = store.get_setting(DB_PATH, "etat_bareme", {}) or {}
                bar["marge"] = min(10.0, max(1.0, float(b["marge"])))
                store.set_setting(DB_PATH, "etat_bareme", bar)
        except (TypeError, ValueError):
            return jsonify({"error": "marge, personnes ou début invalides"}), 400
        store.set_setting(DB_PATH, "etat_plan", r)
    return jsonify(_etat_plan(_etat()[1])), 200

def _etat():
    conn = store._connect(DB_PATH)
    try:
        reports = infra.latest(conn, "plugin:pve-preflight")
        lus = etat_lib.hors_ligne(infra.latest(conn, "plugin:guest-usage"))   # #859 : VM arrêtées lues hors ligne
        autres = etat_lib.autres_systemes(infra.latest(conn, "plugin:systemes"))   # #861 : SI interne hors Proxmox
        scan = etat_lib.hotes_audit(infra.latest(conn, "plugin:lan-audit"))      # #873 : audit réseau (hôtes, services, versions)
        cands = _agents_proxmox(conn)
        conn.execute("CREATE TABLE IF NOT EXISTS etat_historique (jour TEXT PRIMARY KEY, data TEXT NOT NULL)")
        e = etat_lib.assemble(prep.noeuds(reports), eol=store.get_setting(DB_PATH, "etat_eol", {}) or {},
                              libelles=store.get_setting(DB_PATH, "etat_libelles", {}) or {},
                              manuels=store.get_setting(DB_PATH, "etat_manuels", {}) or {}, lus=lus, autres=autres, scan=scan)
        e = etat_lib.regrouper(e, store.get_setting(DB_PATH, "etat_regroupements", {}) or {})   # #879 : copies, clones, préparations
        if reports:     # une ligne par jour : le suivi à long terme
            conn.execute("INSERT OR REPLACE INTO etat_historique VALUES (?, ?)", (time.strftime("%Y-%m-%d"), json.dumps(etat_lib.instantane(e))))
            conn.execute("DELETE FROM etat_historique WHERE jour < ?", (time.strftime("%Y-%m-%d", time.gmtime(time.time() - 800 * 86400)),))
            conn.commit()
        hist = [(r[0], json.loads(r[1])) for r in conn.execute("SELECT jour, data FROM etat_historique ORDER BY jour")]
        try:   # #862 : chantiers (journal, plan de migration) et décisions à prendre, pour les décideurs
            mig = migrun.view(conn)
            conn.commit()
        except Exception:  # noqa: BLE001
            mig = None
        e["chantiers"] = etat_lib.chantiers(journal.list_entries(conn), mig, store.get_setting(DB_PATH, "etat_decisions", []) or [])
        # #863 : où, quand, combien -- phases du chantier (fiches saisies) et serveurs concernés (inventaire des copies)
        e["chantiers"]["organisation"] = etat_lib.organisation(mig, store.get_setting(DB_PATH, "etat_phases", {}) or {})
        try:
            inv = copies_lib.assemble(infra.latest(conn, "plugin:copies-inventory"), store.get_setting(DB_PATH, "copies_regles", {}) or {})
            e["chantiers"]["infrastructure"] = etat_lib.infrastructure(inv.get("hotes"), e["systemes"])
        except Exception:  # noqa: BLE001
            e["chantiers"]["infrastructure"] = []
    finally:
        conn.close()
    return reports, e, etat_lib.tendance(hist), cands


@app.route("/etat-des-lieux", methods=["GET"])
def etat_route():
    """#857 : état des lieux des systèmes actifs (nœuds, CT, VM) et suivi dans le temps."""
    reports, e, t, cands = _etat()
    liens, manuel = _liens_sonde(cands)
    e.update(tendance=t, libelles=store.get_setting(DB_PATH, "etat_libelles", {}) or {}, manuels=store.get_setting(DB_PATH, "etat_manuels", {}) or {},
             decisions=store.get_setting(DB_PATH, "etat_decisions", []) or [], phases=store.get_setting(DB_PATH, "etat_phases", {}) or {},
             liens=liens, manuel=manuel,
             error=None if reports else "aucun relevé pve-preflight : activer la sonde pve-preflight (agent 0.6.1 ou plus récent pour les versions et services)")
    return jsonify(e), 200


@app.route("/etat-des-lieux/libelles", methods=["PUT"])
def etat_libelles_route():
    """#857 : {libelles: {clé: libellé métier}} -- le nom compris par les décideurs (ex. « Messagerie »)."""
    b = request.get_json(silent=True) or {}
    v = b.get("libelles")
    if not isinstance(v, dict):
        return jsonify({"error": "libelles : objet {clé: libellé}"}), 400
    propre = {str(k)[:80]: str(x).strip()[:120] for k, x in list(v.items())[:500] if str(x).strip()}
    store.set_setting(DB_PATH, "etat_libelles", propre)
    return jsonify({"libelles": propre}), 200


@app.route("/etat-des-lieux/manuel", methods=["PUT"])
def etat_manuel_route():
    """#858 : fiche déclarée à la main d'un système illisible : {key, fiche: {famille, version, nom, maj: AAAA-MM-JJ, note} | null}."""
    b = request.get_json(silent=True) or {}
    key = str(b.get("key") or "")
    if not re.match(r"^(node:)?[A-Za-z0-9_.-]+(/\d+)?$", key):
        return jsonify({"error": "key : nœud/vmid"}), 400
    m = store.get_setting(DB_PATH, "etat_manuels", {}) or {}
    f = b.get("fiche")
    if not f:
        m.pop(key, None)
    else:
        if not str(f.get("famille") or "").strip() or not str(f.get("version") or "").strip():
            return jsonify({"error": "famille et version requises"}), 400
        if f.get("maj") and not re.match(r"^\d{4}-\d{2}-\d{2}$", str(f["maj"])):
            return jsonify({"error": "maj : AAAA-MM-JJ"}), 400
        m[key] = {k: str(f.get(k) or "").strip()[:120] for k in ("famille", "version", "nom", "maj", "note")}
        m[key]["famille"] = m[key]["famille"].lower()
    store.set_setting(DB_PATH, "etat_manuels", m)
    return jsonify({"key": key, "fiche": m.get(key)}), 200


@app.route("/etat-des-lieux/decisions", methods=["PUT"])
def etat_decisions_route():
    """#862 : décisions à prendre présentées aux décideurs : {decisions: [{titre, detail, montant, echeance}]}."""
    b = request.get_json(silent=True) or {}
    v = b.get("decisions")
    if not isinstance(v, list):
        return jsonify({"error": "decisions : liste [{titre, detail, montant, echeance}]"}), 400
    propre = [{k: str(d.get(k) or "").strip()[:400] for k in ("titre", "detail", "montant", "echeance")} for d in v[:50] if isinstance(d, dict) and str(d.get("titre") or "").strip()]
    store.set_setting(DB_PATH, "etat_decisions", propre)
    return jsonify({"decisions": propre}), 200


@app.route("/etat-des-lieux/phases", methods=["PUT"])
def etat_phases_route():
    """#863 : fiches des phases pour les décideurs : {phases: {id: {quand, ou, volume_go, debit_mo_s, coupure, contraintes}}}."""
    b = request.get_json(silent=True) or {}
    v = b.get("phases")
    if not isinstance(v, dict):
        return jsonify({"error": "phases : objet {id de phase: fiche}"}), 400
    propre = {}
    for pid, f in list(v.items())[:100]:
        if not isinstance(f, dict):
            continue
        g = {k: str(f.get(k) or "").strip()[:300] for k in etat_lib.CHAMPS_PHASE if str(f.get(k) or "").strip()}
        for k in ("volume_go", "debit_mo_s"):
            if k in g and etat_lib._nb(g[k]) is None:
                return jsonify({"error": "%s %s : nombre attendu" % (pid, k)}), 400
        if g:
            propre[str(pid)[:20]] = g
    store.set_setting(DB_PATH, "etat_phases", propre)
    return jsonify({"phases": propre}), 200


@app.route("/etat-des-lieux/eol", methods=["PUT"])
def etat_eol_route():
    """#857 : dates de fin de support modifiées : {eol: {famille: {version: "AAAA-MM-JJ"}}}."""
    b = request.get_json(silent=True) or {}
    v = b.get("eol")
    if not isinstance(v, dict):
        return jsonify({"error": "eol : objet {famille: {version: date}}"}), 400
    propre = {}
    for fam, t in v.items():
        if not isinstance(t, dict):
            return jsonify({"error": "%s : objet {version: date}" % fam}), 400
        for ver, d in t.items():
            if not re.match(r"^\d{4}-\d{2}-\d{2}$", str(d)):
                return jsonify({"error": "%s %s : date AAAA-MM-JJ" % (fam, ver)}), 400
            propre.setdefault(str(fam)[:40], {})[str(ver)[:20]] = str(d)
    fusion = {f: dict(etat_lib.EOL.get(f, {}), **t) for f, t in propre.items()}
    store.set_setting(DB_PATH, "etat_eol", fusion)
    return jsonify({"eol": fusion}), 200


@app.route("/etat-des-lieux/audit.html", methods=["GET"])
def etat_audit_route():
    """#860 : audit d'obsolescence et de support pour les décideurs (page autonome, imprimable en PDF)."""
    _r, e, _t, _c = _etat()
    from flask import Response
    return Response(etat_rapport.page(e, os.environ.get("ETAT_ORGANISATION", ""), plan=_etat_plan(e)), mimetype="text/html; charset=utf-8")   # #878


@app.route("/etat-des-lieux/export.xlsx", methods=["GET"])
def etat_export_route():
    """#857 : classeur Excel pour les décideurs (synthèse, systèmes, dépendances, évolution), sans jargon."""
    _r, e, t, _c = _etat()
    data = etat_excel.classeur(e, t, os.environ.get("ETAT_ORGANISATION", ""), plan=_etat_plan(e))   # #878
    from flask import Response
    return Response(data, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition": "attachment; filename=etat-des-lieux-%s.xlsx" % time.strftime("%Y-%m-%d")})


def _agents_proxmox(conn):
    """#815 : agents qui joignent des Proxmox (sondes pve-remote / guest-usage, sinon proxmox) -> [(agent_id, hôte)]."""
    vus = {}
    for t in ("plugin:pve-remote", "plugin:guest-usage", "plugin:proxmox"):
        for aid, host, _at, _d in infra.latest(conn, t):
            vus.setdefault(aid, host or aid)
        if vus:
            break
    return sorted(vus.items(), key=lambda x: x[1] or "")


def _liens_sonde(cands, sonde="pve-preflight"):
    """Règle du hub (#570, absolue depuis #817) : « activer / régler X » donne le lien vers l'endroit où on le fait ;
    sans lien possible, une opération manuelle explicite."""
    if cands:
        return [{"label": "Sondes de %s → activer %s" % (h, sonde), "view": "si-agent", "params": {"agent": a, "section": "plugins"}} for a, h in cands], None
    if sonde == "copies-inventory":
        return [], ("pas de lien : opération manuelle -- sur l'agent Linux qui joint les Proxmox et le LAN, créer /etc/si-agent/copies-hosts.json "
                    "([{\"name\": \"pve10\", \"local\": true, \"paths\": [\"/opt/usb\"]}, {\"name\": \"pve-2\", \"host\": \"<IP>\", \"key\": "
                    "\"/etc/si-agent/keys/pve\"}, {\"name\": \"pbs10\", \"host\": \"<IP>\", \"dans\": \"pve10\"}]), puis activer copies-inventory dans sa fiche › Sondes")
    return [], ("pas de lien : opération manuelle -- sur l'agent Linux qui joindra les Proxmox, créer /etc/si-agent/pve-remote.json "
                "([{\"name\": \"pve-2\", \"host\": \"<IP>\", \"key\": \"/etc/si-agent/keys/pve\"}]), puis activer pve-preflight dans sa fiche › Sondes")


@app.route("/migration/plan", methods=["PUT"])
def migration_plan_route():
    """#774 : {plan, actor} -> importe (remplace) le plan ; les paramètres déjà saisis et l'état des étapes sont gardés."""
    b = request.get_json(silent=True) or {}
    actor = str(b.get("actor") or "")[:64]
    conn = store._connect(DB_PATH)
    try:
        p, err = migrun.set_plan(conn, b.get("plan"), actor)
        conn.commit()
    finally:
        conn.close()
    if err:
        return jsonify({"error": err}), 400
    _event("migration", "info", "plan de migration « %s » importé par %s (%d étape(s))" % (p["name"], actor or "?", len(migrun.all_steps(p))))
    return jsonify({"ok": True, "message": "plan « %s » importé : %d étape(s), étapes déjà faites conservées" % (p["name"], len(migrun.all_steps(p)))}), 200


@app.route("/migration/vars", methods=["PUT"])
def migration_vars_route():
    """#774 : {vars: {NOM: valeur}, actor} -> paramètres du plan (adresses des nœuds...)."""
    b = request.get_json(silent=True) or {}
    if not isinstance(b.get("vars"), dict):
        return jsonify({"error": "vars (objet) requis"}), 400
    conn = store._connect(DB_PATH)
    try:
        v, err = migrun.set_vars(conn, b["vars"], str(b.get("actor") or "")[:64])
        conn.commit()
    finally:
        conn.close()
    if err:
        return jsonify({"error": err}), 400
    return jsonify({"ok": True, "vars": v}), 200


@app.route("/migration/control", methods=["POST"])
def migration_control_route():
    """#774 : {action: start|next|pause|resume|stop|auto|manuel|retry|skip|done|reset, step?, actor} -> geste journalisé."""
    b = request.get_json(silent=True) or {}
    action, actor = str(b.get("action") or ""), str(b.get("actor") or "")[:64]
    step = str(b.get("step") or "") or None
    onglet = str(b.get("onglet") or "")[:40]   # #784 : onglet de la tuile (suite d'étapes propre)
    conn = store._connect(DB_PATH)
    try:
        ok, msg = migrun.control(conn, action, step, actor, onglet)
        conn.commit()
    finally:
        conn.close()
    _event("migration", "info" if ok else "warning", "migration : %s%s par %s -> %s" % (action, " " + step if step else "", actor or "?", msg))
    return jsonify({"ok": ok, "message": msg}), (200 if ok else 409)


@app.route("/images", methods=["GET"])
def images_list_route():
    """Images reçues (hub) : agent, nom, taille, complète, chemin sur le serveur."""
    site = request.args.get("site")
    items = _image_store().list()
    if site:
        allowed = {a["agent_id"] for a in store.list_agents(DB_PATH) if a.get("site") == site}
        items = [i for i in items if i["agent_id"] in allowed]
    return jsonify({"images": items, "dir": IMAGES_DIR}), 200


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/publish", methods=["GET"])
def agent_publish_route(agent_id):
    """Contenu à publier par l'agent sur le LAN de son site (#547), signé
    comme la configuration ; vide si la publication est désactivée."""
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    a = store.get_agent(DB_PATH, agent_id)
    pub = (a or {}).get("publish") or {}
    if not pub.get("enabled"):
        return _signed_json(info["secret"], {"enabled": False})
    board, transitions, why = _publish_board(pub)
    payload = publish_lib.board_payload(board or {}, pub["title"], int(time.time()), pub.get("hub_url") or "", transitions)
    payload["enabled"] = True
    if why:
        payload["error"] = why
    return _signed_json(info["secret"], payload)


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/commands", methods=["GET"])
def agent_commands_route(agent_id):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    conn = store._connect(DB_PATH)
    try:
        store.touch_agent(conn, agent_id, _client_ip())
        conn.commit()
    finally:
        conn.close()
    body = {"commands": store.pending_commands_for_agent(DB_PATH, agent_id)}
    left = _interactive.get(agent_id, 0) - time.time()
    if left > 0:                                       # #709 : session interactive ouverte depuis le hub
        body["fast_poll"] = {"seconds": FAST_POLL_SECONDS, "for": int(left)}
    return _signed_json(info["secret"], body)


# #709 : sessions interactives (tuile Messagerie…) -- l'agent relève ses commandes toutes les FAST_POLL_SECONDS
# au lieu de chaque minute tant que la session vit ; renouvelée par le hub, ouverte aussi par chaque commande créée.
FAST_POLL_SECONDS = max(2, int(os.environ.get("SI_AGENT_FAST_POLL_SECONDS", "3")))
_interactive = {}


def open_interactive(agent_id, seconds):
    until = time.time() + max(10, min(900, int(seconds)))
    _interactive[agent_id] = max(_interactive.get(agent_id, 0), until)
    return _interactive[agent_id]


@app.route("/agents/<agent_id>/interactive", methods=["POST"])
def interactive_route(agent_id):
    if store.get_agent(DB_PATH, agent_id) is None:
        return jsonify({"error": "agent inconnu"}), 404
    body = request.get_json(silent=True) or {}
    if body.get("close"):
        _interactive.pop(agent_id, None)
        return jsonify({"agent_id": agent_id, "until": None}), 200
    until = open_interactive(agent_id, body.get("seconds") or 300)
    return jsonify({"agent_id": agent_id, "until": int(until), "fast_poll_seconds": FAST_POLL_SECONDS}), 200


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/commands/<cid>/ack", methods=["POST"])
def agent_ack_route(agent_id, cid):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    result = request.get_json(silent=True) or {}
    if not store.ack_command(DB_PATH, agent_id, cid, result):
        return _signed_json(info["secret"], {"error": "commande inconnue ou déjà acquittée"}, 404)
    c = store.get_command(DB_PATH, cid) or {}
    _log.info("agent %s : commande %s (%s) acquittée ok=%s", agent_id, cid, c.get("type"), bool(result.get("ok")))
    if not result.get("ok"):
        _event("command-failed", "warning", "commande %s (%s) en échec sur %s : %s" % (cid, c.get("type"), agent_id, result.get("error")),
               agent_id=agent_id, details={"command": cid, "type": c.get("type")})
    elif c.get("type") in control.BLOCK_COMMANDS:
        _event("command-acked", "info", "commande %s appliquée par %s" % (c.get("type"), agent_id), agent_id=agent_id, details={"command": cid})
    return _signed_json(info["secret"], {"acked": cid})


NETWORK_AGENT_API_URL = os.environ.get("NETWORK_AGENT_API_URL", "").rstrip("/")


def relay_capture_measurements(agent_id, info, items, post=None):
    """#436 : chaque mesure `plugin:capture-relay` réussie (pcap en base64,
    bornée par le plugin) est versée dans network-agent-api
    (`POST /capture/upload`, site de l'agent, segment = nom d'hôte). Le pcap
    n'est PAS conservé ici (la mesure stockée le contient déjà ; purge par
    rétention). Échec = événement, jamais un refus de la mesure."""
    if not NETWORK_AGENT_API_URL:
        return 0
    post = post or (lambda url, payload: requests.post(url, json=payload, timeout=60))
    done = 0
    agent = store.get_agent(DB_PATH, agent_id) or {}
    for m in items:
        if not isinstance(m, dict) or m.get("task") != "plugin:capture-relay" or not m.get("ok"):
            continue
        data = m.get("data") or {}
        if not isinstance(data, dict) or not data.get("pcap_base64"):
            continue
        payload = {"site": agent.get("site") or info.get("site") or "relais", "segment": agent.get("hostname") or agent_id,
                   "cidr": data.get("cidr"), "pcap_base64": data["pcap_base64"], "source": "si-agent %s (%s)" % (agent_id, data.get("interface"))}
        try:
            r = post(NETWORK_AGENT_API_URL + "/capture/upload", payload)
            if r.status_code == 200:
                done += 1
                _log.info("relais d'exploration : %s -> %s paquet(s) versés (segment %s)", agent_id, (r.json() or {}).get("packets"), payload["segment"])
            else:
                _event("capture-relay-failed", "warning", "relais d'exploration refusé par network-agent-api (%s) pour %s" % (r.status_code, agent_id), agent_id=agent_id,
                       details={"status": r.status_code, "error": (r.json() or {}).get("error") if r.content else None})
        except Exception as exc:  # noqa: BLE001 -- jamais bloquant
            _event("capture-relay-failed", "warning", "relais d'exploration impossible pour %s : %s" % (agent_id, exc), agent_id=agent_id, details={})
    return done


@app.route(protocol.API_PREFIX + "/agents/<agent_id>/measurements", methods=["POST"])
def agent_measurements_ingest_route(agent_id):
    info, err = _verify_agent(agent_id)
    if info is None:
        return jsonify({"error": err}), 401
    body = request.get_json(silent=True) or {}
    items = body.get("measurements")
    if not isinstance(items, list):
        return jsonify({"error": "'measurements' (liste) attendu"}), 400
    if len(items) > 5000:
        return jsonify({"error": "lot trop volumineux (max 5000)"}), 400
    accepted, duplicates, rejected, events = store.ingest_measurements(DB_PATH, agent_id, items, ip=_client_ip())
    relay_capture_measurements(agent_id, info, items)  # #436 : relais d'exploration vers network-agent-api
    if any(m.get("task") == "inventory" for m in items if isinstance(m, dict)):
        # #522 : la version de l'agent vient de l'inventaire -- planifier sa mise à jour s'il est éligible (auto)
        try:
            if _updates_settings()["auto"]:
                _schedule_updates(only_agent=agent_id, actor="auto")
        except Exception as exc:  # noqa: BLE001
            _log.warning("planification de mise à jour pour %s : %s", agent_id, exc)
    _log.debug("agent %s : %d mesure(s) acceptée(s), %d doublon(s), %d rejet(s), %d événement(s)", agent_id, accepted, duplicates, len(rejected), len(events))
    for ev in events:
        notify.dispatch(DB_PATH, dict(ev, source="agent", details={}))
    if rejected and not accepted and not duplicates and items:
        return _signed_json(info["secret"], {"error": "aucune mesure valide", "rejected": rejected[:10]}, 400)
    return _signed_json(info["secret"], {"accepted": accepted, "duplicates": duplicates, "rejected": rejected[:10]}, 201)


@app.route("/logs", methods=["GET"])
def get_logs():
    limit = request.args.get("limit", type=int)
    entries = read_shared_log_buffer(SERVICE_NAME, get_memcache_client, limit=limit, buffer_size=LOG_BUFFER_SIZE) if read_shared_log_buffer else []
    return jsonify({"service": SERVICE_NAME, "entries": entries}), 200


# #705 : maintenance / réorganisation des Proxmox (campagnes, avancement détecté, planification, sauvegardes)
maint.register(app, DB_PATH, lambda: store.latest_proxmox(DB_PATH), start_loop=os.environ.get("SI_AGENT_PURGE_THREAD", "1") == "1",
               emit=lambda kind, sev, msg, details: _event(kind, sev, msg, details=details, source="maintenance"))


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
