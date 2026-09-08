# -*- coding: utf-8 -*-
"""Collecteurs de Cortex (livraison #462) : lisent les API existantes du
hub (réseau Docker interne), normalisent (normalize.py), écrivent dans le
store et recalculent les incidents (correlate.py). Aucun module d'origine
n'est modifié. Une source injoignable est notée dans le journal de collecte
(transparence) et n'empêche pas les autres.
"""
import logging
import time

import requests

import changes as ch
import correlate
import learn
import normalize as nz
import places as pl
import store

_log = logging.getLogger("cortex.collect")


def _get(base, path, timeout=8):
    if not base:
        return None
    r = requests.get(base.rstrip("/") + path, timeout=timeout)
    r.raise_for_status()
    return r.json()


class Collector(object):
    def __init__(self, db_path, urls, window_s=300, horizon_h=24):
        self.db_path = db_path
        self.urls = urls        # {si_agent, vigilance, ups, orchestrator, netprobe, network_agent, backup}
        self.window_s = window_s
        self.horizon_h = horizon_h   # événements historiques plus vieux : ignorés
        self._na = ([], [])          # dernier (sites, appareils) network-agent lus

    def _snapshot(self):
        fb = store.feedback_counts(self.db_path)
        return ch.snapshot(store.list_entities(self.db_path, limit=100000), store.list_relations(self.db_path), store.list_routes(self.db_path),
                           lambda e: nz.role_hypotheses(e, fb))

    def run(self):
        t0 = time.time()
        ents, rels, evs, routes, report = [], [], [], [], {}
        occurrences, samples = [], []      # #465 : historique pour les séquences, mesures pour les dérives
        u = self.urls
        before = self._snapshot()

        def step(name, fn):
            t = time.time()
            try:
                e, r, v = fn()
                ents.extend(e); rels.extend(r); evs.extend(v)
                report[name] = {"ok": True, "entities": len(e), "relations": len(r), "events": len(v), "ms": int((time.time() - t) * 1000)}
            except Exception as exc:  # noqa: BLE001
                report[name] = {"ok": False, "error": str(exc)[:160], "ms": int((time.time() - t) * 1000)}

        if u.get("si_agent"):
            since = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - self.horizon_h * 3600))
            def si():
                fleet = (_get(u["si_agent"], "/fleet") or {}).get("agents")
                nvs = (_get(u["si_agent"], "/netview") or {}).get("netviews")
                history = (_get(u["si_agent"], "/events?limit=500") or {}).get("events")
                e, r, v = nz.from_si_agent(fleet, nvs, history, _get(u["si_agent"], "/status"), since=since)
                by_agent = {a["agent_id"]: nz.entity_key(ip=a.get("last_ip"), name=a.get("hostname") or a.get("agent_id")) for a in fleet or []}
                routes.extend(nz.routes_from_netviews(nvs, by_agent))
                occurrences.extend(nz.occurrences_from_si_agent(history, by_agent))
                samples.extend(learn.samples_from_si_agent(fleet, lambda a: nz.entity_key(ip=a.get("last_ip"), name=a.get("hostname") or a.get("agent_id"))))
                return e, r, v
            step("si-agent", si)
        if u.get("vigilance"):
            step("vigilance", lambda: nz.from_vigilance(_get(u["vigilance"], "/signals?limit=300")))
        if u.get("ups"):
            def ups():
                d = _get(u["ups"], "/ups")
                devices = d.get("devices") if isinstance(d, dict) else d
                samples.extend(learn.samples_from_ups(devices, lambda x: nz.entity_key(ip=x.get("host"), name=x.get("name"))))
                return nz.from_ups(devices)
            step("ups", ups)
        if u.get("orchestrator"):
            step("netmap-orchestrator", lambda: nz.from_orchestrator((_get(u["orchestrator"], "/suggestions?status=open&limit=300") or {}).get("suggestions")))
        if u.get("netprobe"):
            def np_():
                targets = (_get(u["netprobe"], "/targets") or {}).get("targets")
                latest = (_get(u["netprobe"], "/smokeping/latest") or {}).get("latest")
                samples.extend(learn.samples_from_netprobe(targets, latest, lambda t: nz.entity_key(ip=t.get("ip_address"), name=t.get("label"))))
                return nz.from_netprobe(targets, latest, (_get(u["netprobe"], "/analysis/results?limit=200") or {}).get("results"))
            step("netprobe", np_)
        if u.get("network_agent"):
            def na():
                sites = _get(u["network_agent"], "/sites") or []
                devices = _get(u["network_agent"], "/devices") or []
                self._na = (sites, devices)      # réutilisé par resolve_places (lieux, coordonnées)
                links, services = {}, {}
                for s in sites:
                    for seg in s.get("segments") or []:
                        try:
                            links[seg["id"]] = _get(u["network_agent"], "/links?segment_id=%s" % seg["id"]) or []
                            services.update(_get(u["network_agent"], "/devices/services?segment_id=%s" % seg["id"]) or {})
                        except Exception:  # noqa: BLE001
                            links[seg["id"]] = []
                e, r, v = nz.from_network_agent(sites, devices, links)
                hints = nz.services_hints(devices, services)
                by_key = {}
                for d in devices:
                    k = nz.entity_key(ip=d.get("ip_address"), mac=d.get("mac_address"), name=d.get("hostname"))
                    if k:
                        by_key[k] = d.get("id")
                for ent in e:
                    for h in hints.get(by_key.get(ent["key"]), []):
                        if h not in ent["hints"]:
                            ent["hints"].append(h)
                return e, r, v
            step("network-agent", na)
        if u.get("classifier"):
            def _classifier():
                r = _get(u["classifier"], "/results?limit=500")
                return nz.from_classifier(r.get("results") if isinstance(r, dict) else r)
            step("classifier", _classifier)
        if u.get("nebula"):
            step("nebula", lambda: nz.from_nebula(_get(u["nebula"], "/imported/devices"), _get(u["nebula"], "/imported/clients")))
        if u.get("ipam"):
            step("ipam", lambda: nz.from_ipam((_get(u["ipam"], "/ip_list") or {}).get("entries")))
        if u.get("backup"):
            step("backup-restore", lambda: nz.from_backups(_get(u["backup"], "/hub-backups/status")))

        alias = nz.alias_map(ents)
        ents, rels, evs = nz.apply_aliases(ents, rels, evs, alias)
        for r in routes:
            r["host"] = alias.get(r["host"], r["host"])
        merged = nz.with_vendor_hints(nz.merge_entities(ents))
        store.upsert_entities(self.db_path, merged)
        store.upsert_relations(self.db_path, rels)
        store.upsert_routes(self.db_path, routes)
        # #465 : mesures -> dérives (événements « cortex », même cycle de vie) ; historique -> occurrences
        store.add_samples(self.db_path, samples)
        store.add_occurrences(self.db_path, occurrences)
        drifts = learn.detect_drifts(store.series(self.db_path))
        evs.extend(learn.drift_events(drifts, sites=store.entity_sites(self.db_path)))
        new, refreshed = store.upsert_events(self.db_path, evs)
        ok_sources = {k for k, v in report.items() if v.get("ok")} | {"cortex"}
        closed = store.close_missing_events(self.db_path, {e["fingerprint"] for e in evs}, ok_sources)
        counts = self.recompute()
        learn_report = self.learn()
        report["learning"] = learn_report
        pos_report = self.resolve_places()
        report["positions"] = pos_report
        after = self._snapshot()
        failed = {k for k, v in report.items() if not v.get("ok")}
        diff = ch.compute_changes(before, after, failed_sources=failed, names=store.entity_names(self.db_path)) if before["entities"] else []
        diff.extend(pos_report.get("changes") or [])
        store.add_changes(self.db_path, diff)
        counts.update({"entities": len(merged), "aliases": len(alias), "relations": len(rels), "routes": len(routes), "changes": len(diff),
                       "events_new": new, "events_refreshed": refreshed, "events_closed": closed, "samples": len(samples), "drifts": len(drifts),
                       "rules": learn_report.get("rules"), "predictions_open": learn_report.get("pending")})
        store.add_run(self.db_path, int((time.time() - t0) * 1000), report, counts)
        return report, counts

    def resolve_places(self):
        """Étape 3 (#464) : lieux + positions mémorisées avec provenance.
        Lit pixel-grid (géolocalisations, correspondances) et geo-catalog
        (positions validées) ; les appareils network-agent viennent de la
        collecte courante. -> rapport {ok, places, positions, by_provenance, changes}."""
        u = self.urls
        t = time.time()
        rep = {"ok": True, "sources": {}}
        geos, matches, catalog = [], [], []
        if u.get("pixel_grid"):
            try:
                geos = (_get(u["pixel_grid"], "/geolocations") or {}).get("geolocations") or []
                matches = (_get(u["pixel_grid"], "/geolocations/matches") or {}).get("matches") or []
                rep["sources"]["pixel-grid"] = {"ok": True, "geolocations": len(geos), "matches": len(matches)}
            except Exception as exc:  # noqa: BLE001
                rep["sources"]["pixel-grid"] = {"ok": False, "error": str(exc)[:160]}
        if u.get("geo_catalog"):
            try:
                catalog = (_get(u["geo_catalog"], "/positions?limit=2000") or {}).get("positions") or []
                rep["sources"]["geo-catalog"] = {"ok": True, "positions": len(catalog)}
            except Exception as exc:  # noqa: BLE001
                rep["sources"]["geo-catalog"] = {"ok": False, "error": str(exc)[:160]}
        sites, devices = self._na
        cat_places = pl.places_from_geo_catalog(catalog)
        # un lieu du catalogue lié à un sujet supervisé vaut correspondance (validée si décidée)
        for cp in cat_places:
            for subj in cp.get("links") or []:
                matches.append({"subject": subj, "localisation": cp["name"], "latitude": cp["lat"], "longitude": cp["lon"],
                                "status": "validated" if cp.get("confidence", 0) >= 0.95 else "auto", "method": "geo-catalog", "score": cp.get("confidence")})
        na_places, _ = pl.places_from_network_agent(sites, devices)
        places, alias = pl.merge_places(pl.places_from_geolocations(geos), na_places, cat_places)
        entities = store.list_entities(self.db_path, limit=100000)
        relations = store.list_relations(self.db_path)
        entity_places = {e["key"]: e["place"] for e in entities if e.get("place")}
        positions = pl.resolve_positions(entities, relations, places, alias, geolocations=geos, matches=matches, entity_places=entity_places)
        store.upsert_places(self.db_path, places)
        before = store.positions_map(self.db_path)
        sync = store.sync_positions(self.db_path, positions)
        names = store.entity_names(self.db_path)
        changes = []
        for k, p in positions.items():
            o = before.get(k)
            if o and o.get("principle") == "pos-fallback" and p["principle"] != "pos-fallback":
                changes.append({"kind": "position-found", "subject": k, "principle": p["principle"],
                                "message": "%s a maintenant une position (%s)" % (names.get(k, k), p["provenance"])})
            elif o and (o.get("provenance") != p["provenance"]):
                changes.append({"kind": "position-changed", "subject": k, "principle": p["principle"],
                                "message": "%s : position %s → %s" % (names.get(k, k), o.get("provenance"), p["provenance"])})
            elif o and abs((o.get("lat") or 0) - p["lat"]) + abs((o.get("lon") or 0) - p["lon"]) > 1e-4 and p["principle"] not in ("pos-neighbor", "pos-fallback"):
                changes.append({"kind": "position-moved", "subject": k, "principle": p["principle"],
                                "message": "%s a bougé (%s) : %.5f,%.5f → %.5f,%.5f" % (names.get(k, k), p["provenance"], o.get("lat") or 0, o.get("lon") or 0, p["lat"], p["lon"])})
        rep.update({"places": len(places), "positions": len(positions), "entities": len(entities), "sync": sync, "changes": changes,
                    "by_provenance": pl._count(positions.values(), "provenance"), "ms": int((time.time() - t) * 1000)})
        self._alias = alias
        return rep

    def roles_map(self):
        fb = store.feedback_counts(self.db_path)
        out = {}
        for e in store.list_entities(self.db_path, limit=100000):
            r = nz.role_hypotheses(e, fb)
            if r:
                out[e["key"]] = r[0]["role"]
        return out

    def learn(self):
        """Étape 4 (#465) : règles apprises depuis les occurrences, annonces
        pour les événements ouverts, jugement des annonces en attente."""
        t = time.time()
        roles = self.roles_map()
        occ = store.list_occurrences(self.db_path)
        rules = learn.mine_sequences(occ, roles=roles, window_s=max(self.window_s, 600))
        store.sync_rules(self.db_path, rules)
        pending = store.list_predictions(self.db_path, pending_only=True, limit=1000)
        verdicts = learn.settle_predictions(pending, occ[-5000:])
        store.settle(self.db_path, verdicts)
        all_rules = [r for r in store.list_rules(self.db_path) if r["state"] != "rejected"]
        fb = store.feedback_counts(self.db_path)
        import principles as pr
        eff = {pid: pr.evaluate(pid, fb)["effective"] for pid in ("sequence-learned", "sequence-confirmed")}
        open_events = store.list_events(self.db_path, state="open", limit=2000)
        preds = learn.anticipate(open_events, all_rules, roles=roles, names=store.entity_names(self.db_path), principle_eff=eff)
        for p in preds:
            r = next((x for x in all_rules if "%s=>%s" % (x["a"], x["b"]) == p["rule_id"]), None)
            p["delay_max_s"] = r.get("delay_max_s") if r else None
        added = store.add_predictions(self.db_path, preds, roles=roles)
        return {"ok": True, "occurrences": len(occ), "rules": len(rules), "rules_known": len(all_rules), "settled": len(verdicts),
                "hits": sum(1 for v in verdicts if v["outcome"] == "hit"), "predictions": len(preds), "new_predictions": added,
                "pending": len(store.list_predictions(self.db_path, pending_only=True, limit=1000)), "ms": int((time.time() - t) * 1000)}

    def recompute(self):
        """Recalcule les incidents à partir des événements ouverts/acquittés."""
        events = store.list_events(self.db_path, state="open", limit=2000) + store.list_events(self.db_path, state="acked", limit=2000)
        for e in events:
            e["state"] = "open"
        relations = store.list_relations(self.db_path)
        entities = store.list_entities(self.db_path, limit=5000)
        feedback = store.feedback_counts(self.db_path)
        incidents = correlate.build_incidents(events, relations, entities, window_s=self.window_s, feedback=feedback)
        store.sync_incidents(self.db_path, incidents)
        return {"incidents": len(incidents), "incidents_weak": sum(1 for i in incidents if i.get("weak"))}
