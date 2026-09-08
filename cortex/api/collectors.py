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
import normalize as nz
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

    def _snapshot(self):
        fb = store.feedback_counts(self.db_path)
        return ch.snapshot(store.list_entities(self.db_path, limit=100000), store.list_relations(self.db_path), store.list_routes(self.db_path),
                           lambda e: nz.role_hypotheses(e, fb))

    def run(self):
        t0 = time.time()
        ents, rels, evs, routes, report = [], [], [], [], {}
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
                e, r, v = nz.from_si_agent(fleet, nvs, (_get(u["si_agent"], "/events?limit=200&min_severity=warning") or {}).get("events"), _get(u["si_agent"], "/status"), since=since)
                by_agent = {a["agent_id"]: nz.entity_key(ip=a.get("last_ip"), name=a.get("hostname") or a.get("agent_id")) for a in fleet or []}
                routes.extend(nz.routes_from_netviews(nvs, by_agent))
                return e, r, v
            step("si-agent", si)
        if u.get("vigilance"):
            step("vigilance", lambda: nz.from_vigilance(_get(u["vigilance"], "/signals?limit=300")))
        if u.get("ups"):
            def ups():
                d = _get(u["ups"], "/ups")
                return nz.from_ups(d.get("devices") if isinstance(d, dict) else d)
            step("ups", ups)
        if u.get("orchestrator"):
            step("netmap-orchestrator", lambda: nz.from_orchestrator((_get(u["orchestrator"], "/suggestions?status=open&limit=300") or {}).get("suggestions")))
        if u.get("netprobe"):
            step("netprobe", lambda: nz.from_netprobe((_get(u["netprobe"], "/targets") or {}).get("targets"), (_get(u["netprobe"], "/smokeping/latest") or {}).get("latest"),
                                                       (_get(u["netprobe"], "/analysis/results?limit=200") or {}).get("results")))
        if u.get("network_agent"):
            def na():
                sites = _get(u["network_agent"], "/sites") or []
                devices = _get(u["network_agent"], "/devices") or []
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
        new, refreshed = store.upsert_events(self.db_path, evs)
        ok_sources = {k for k, v in report.items() if v.get("ok")}
        closed = store.close_missing_events(self.db_path, {e["fingerprint"] for e in evs}, ok_sources)
        counts = self.recompute()
        after = self._snapshot()
        failed = {k for k, v in report.items() if not v.get("ok")}
        diff = ch.compute_changes(before, after, failed_sources=failed, names=store.entity_names(self.db_path)) if before["entities"] else []
        store.add_changes(self.db_path, diff)
        counts.update({"entities": len(merged), "aliases": len(alias), "relations": len(rels), "routes": len(routes), "changes": len(diff),
                       "events_new": new, "events_refreshed": refreshed, "events_closed": closed})
        store.add_run(self.db_path, int((time.time() - t0) * 1000), report, counts)
        return report, counts

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
