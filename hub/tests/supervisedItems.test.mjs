import test from "node:test";
import assert from "node:assert/strict";
import {
  fromNetprobe, fromUps, fromSiAgent, fromSnmp, fromSshTunnels, fromWifiAgents, mergeItems, aggregateSupervised,
  buildProposals, filterSupervised, prioritizeSupervised, setPriority, movePriority,
  buildLinks, knownPositions, deducePositions, describeChain, frameLayout, normalizeFrames, summarizeByState, loadPref, savePref,
  appliedMatch, displaySite, resolveSubjects, resolveKey, geoRows, geoSummary,
} from "../src/supervisedItems.js";

const NOW = Date.parse("2026-09-08T10:00:00Z");

test("normalisation : chaque source donne un état homogène", () => {
  const probes = fromNetprobe(
    [{ id: 1, ip_address: "10.0.0.1", label: "Routeur", active: 1 }, { id: 2, ip_address: "10.0.0.2", active: 1 }, { id: 3, ip_address: "10.0.0.3", active: 0 }],
    [{ target_id: 1, success: 1, latency_ms: 2.4, packet_loss_percent: 0, sampled_at: "2026-09-08T09:59:00Z" }, { target_id: 2, success: 0, error: "timeout" }],
  );
  assert.deepEqual(probes.map((p) => [p.state, p.stateText]), [["ok", "2 ms"], ["critical", "timeout"], ["unknown", "désactivée"]]);
  assert.equal(probes[0].identity, "ip:10.0.0.1");
  const ups = fromUps([
    { id: 1, name: "UPS salle", host: "10.0.0.9", site: "Siège", enabled: true, last_ok: true, last_state: "ok", last_polled_at: "2026-09-08T09:30:00Z", poll_interval_seconds: 3600 },
    { id: 2, name: "UPS vieux", host: "10.0.0.10", enabled: true, last_ok: true, last_state: "ok", last_polled_at: "2026-09-07T00:00:00Z", poll_interval_seconds: 3600 },
    { id: 3, name: "UPS alarme", host: "10.0.0.11", enabled: true, last_ok: true, last_state: "alarm", last_polled_at: "2026-09-08T09:59:00Z" },
  ], NOW);
  assert.deepEqual(ups.map((u) => u.state), ["ok", "warning", "critical"]);
  const agents = fromSiAgent([{ agent_id: "a1", hostname: "srv", site: "siege", online: "online", risks: { state: "warning" }, last_ip: "10.0.0.20", blocked: true },
    { agent_id: "a2", online: "offline" }, { agent_id: "a3", online: "never", last_ip: "127.0.0.1" }]);
  assert.deepEqual(agents.map((a) => a.state), ["warning", "critical", "unknown"]);
  assert.match(agents[0].stateText, /bloquées/);
  assert.equal(agents[2].ip, null, "127.x n'est pas une adresse d'hôte");
  assert.equal(fromSnmp([{ id: 1, host: "10.0.0.30", label: "Switch" }])[0].state, "unknown");
  const tunnels = fromSshTunnels([{ id: 1, connection_id: 5, label: "T", status: "running", remote_host: "db", remote_port: 5432 }], [{ id: 5, ssh_host: "bastion" }]);
  assert.equal(tunnels[0].state, "ok");
  assert.equal(tunnels[0].ip, "bastion");
  const wifi = fromWifiAgents([{ agent_id: "w1", last_seen_at: "2026-09-08T09:59:30Z", last_ip: "10.0.0.40" }, { agent_id: "w2", last_seen_at: "2026-09-08T08:00:00Z" }], NOW);
  assert.deepEqual(wifi.map((w) => w.state), ["ok", "warning"]);
});

test("fusion par identité : même IP dans deux tuiles = un équipement, état le pire", () => {
  const items = mergeItems([
    fromNetprobe([{ id: 1, ip_address: "10.0.0.1", label: "Routeur", active: 1 }], [{ target_id: 1, success: 1, latency_ms: 1 }]),
    fromSnmp([{ id: 7, host: "10.0.0.1", label: "Switch cœur" }]),
    fromUps([{ id: 2, name: "UPS", host: "10.0.0.2", enabled: true, last_ok: false, last_error: "injoignable" }]),
  ]);
  assert.equal(items.length, 2);
  const r = items.find((i) => i.ip === "10.0.0.1");
  assert.equal(r.origins.length, 2);
  assert.equal(r.state, "ok", "une cible SNMP seulement déclarée ne dégrade pas un état mesuré");
  const u = items.find((i) => i.ip === "10.0.0.2");
  assert.equal(u.state, "critical");
  const agg = aggregateSupervised({ netprobeTargets: [{ id: 1, ip_address: "10.0.0.1", active: 1 }], snmpTargets: [{ id: 1, host: "10.0.0.1" }] });
  assert.equal(agg.length, 1);
});

test("propositions : orchestrateur + vigilance + découverts non supervisés, triées par sévérité", () => {
  const supervised = [{ identity: "ip:10.0.0.1", ip: "10.0.0.1", mac: "aa:bb" }];
  const props = buildProposals({
    suggestions: [{ id: 1, status: "open", severity: "warning", message: "Sonder 10.0.0.5", subject_type: "ip", subject_key: "10.0.0.5", last_detected_at: "2026-09-08T09:00:00Z" },
      { id: 2, status: "done", severity: "critical", message: "déjà traitée" }],
    signals: [{ id: 3, severity: "high", device_mac: "cc:dd", device_label: "Inconnu", signal_type: "new_device", detail: "vu la nuit", detected_at: "2026-09-08T09:30:00Z" }],
    devices: [{ id: 10, ip_address: "10.0.0.1", mac_address: "AA:BB" }, { id: 11, ip_address: "10.0.0.7", mac_address: "ee:ff", hostname: "imprimante", role_hint: "imprimante", last_seen: "2026-09-08T09:50:00Z" }],
    supervised,
  });
  assert.deepEqual(props.map((p) => p.kind), ["vigilance", "orchestrateur", "decouvert"]);
  assert.equal(props[2].label, "imprimante");
  assert.equal(props.some((p) => p.key === "dev:10"), false, "appareil déjà supervisé (par MAC, casse ignorée) : pas proposé");
  assert.equal(props.some((p) => p.key === "orch:2"), false, "suggestion traitée : pas proposée");
});

test("filtre et priorisation", () => {
  const items = mergeItems([fromNetprobe([{ id: 1, ip_address: "10.0.0.1", label: "Routeur", active: 1 }, { id: 2, ip_address: "10.0.0.2", label: "NAS", active: 1 }],
    [{ target_id: 1, success: 1 }, { target_id: 2, success: 0, error: "down" }]), fromUps([{ id: 3, name: "UPS", host: "10.0.0.3", site: "Siège", enabled: true, last_ok: true, last_state: "ok", last_polled_at: "2026-09-08T09:59:00Z" }], NOW)]);
  assert.deepEqual(filterSupervised(items, { text: "nas" }).map((i) => i.name), ["NAS"]);
  assert.deepEqual(filterSupervised(items, { site: "siège" }).map((i) => i.name), ["UPS"]);
  assert.deepEqual(filterSupervised(items, { states: ["critical"] }).map((i) => i.name), ["NAS"]);
  assert.deepEqual(filterSupervised(items, { types: ["ups"] }).map((i) => i.name), ["UPS"]);
  assert.deepEqual(prioritizeSupervised(items).map((i) => i.name), ["NAS", "Routeur", "UPS"], "état critique d'abord puis nom");
  let pr = setPriority({}, "ip:10.0.0.3", 1);
  assert.deepEqual(prioritizeSupervised(items, pr).map((i) => i.name), ["UPS", "NAS", "Routeur"], "priorisé en tête");
  pr = movePriority(pr, items.map((i) => i.identity), "ip:10.0.0.1", 0);
  assert.deepEqual(prioritizeSupervised(items, pr).map((i) => i.name), ["UPS", "Routeur", "NAS"]);
  pr = movePriority(pr, items.map((i) => i.identity), "ip:10.0.0.1", -1);
  assert.deepEqual(prioritizeSupervised(items, pr).map((i) => i.name), ["Routeur", "UPS", "NAS"]);
  pr = setPriority(pr, "ip:10.0.0.1", null);
  assert.equal(pr["ip:10.0.0.1"], undefined);
});

test("liens et positions déduites : un équipement sans coordonnées est placé par ses liens, chaîne conservée", () => {
  const naDevices = [
    { id: 1, ip_address: "10.0.0.1", mac_address: "aa", latitude: 48.85, longitude: 2.35 },
    { id: 2, ip_address: "10.0.0.2", mac_address: "bb" },
    { id: 3, ip_address: "10.0.0.3", mac_address: "cc" },
    { id: 4, ip_address: "10.0.0.4", mac_address: "dd" },
  ];
  const naLinks = [{ device_a_id: 1, device_b_id: 2, bytes_total: 1e6 }, { device_a_id: 2, device_b_id: 3, bytes_total: 10 }];
  const supervised = [{ identity: "ip:10.0.0.2", name: "NAS", ip: "10.0.0.2", site: null }, { identity: "ip:10.0.0.9", name: "UPS", ip: "10.0.0.9", site: "Brest" }, { identity: "ip:10.0.0.4", name: "isolé", ip: "10.0.0.4" }];
  const links = buildLinks({ naLinks, naDevices, supervised });
  assert.equal(links.filter((l) => l.kind === "flux").length, 2);
  assert.equal(links.filter((l) => l.kind === "site").length, 1);
  const known = knownPositions({ naDevices, geolocations: [{ localisation: "Brest", latitude: 48.39, longitude: -4.49 }, { localisation: "__default__", latitude: 46, longitude: 2 }], supervised });
  assert.equal(known.get("ip:10.0.0.1").source, "déclarée");
  assert.equal(known.get("site:brest").source, "site");
  const ids = ["ip:10.0.0.1", "ip:10.0.0.2", "ip:10.0.0.3", "ip:10.0.0.4", "ip:10.0.0.9"];
  const pos = deducePositions(ids, links, known);
  assert.equal(pos.get("ip:10.0.0.2").source, "déduite");
  assert.equal(pos.get("ip:10.0.0.2").depth, 1);
  assert.ok(Math.abs(pos.get("ip:10.0.0.2").lat - 48.85) < 1e-9, "voisin unique positionné : même position");
  assert.equal(pos.get("ip:10.0.0.3").depth, 2, "déduit du déduit");
  assert.equal(pos.get("ip:10.0.0.9").source, "déduite");
  assert.equal(pos.get("ip:10.0.0.9").chain[0].via, "site");
  assert.equal(pos.get("ip:10.0.0.4").source, "repli", "sans lien : position de repli");
  assert.match(describeChain(pos.get("ip:10.0.0.3")), /profondeur 2/);
  const noDefault = deducePositions(ids, links, knownPositions({ naDevices, geolocations: [], supervised }), { useDefault: false });
  assert.equal(noDefault.has("ip:10.0.0.4"), false);
  assert.equal(noDefault.has("ip:10.0.0.9"), false, "site sans coordonnées : rien à déduire");
});

test("cadres : disposition 1-4 et normalisation", () => {
  assert.deepEqual(frameLayout(1).areas, ['"f0"']);
  assert.deepEqual(frameLayout(2).areas, ['"f0 f1"']);
  assert.deepEqual(frameLayout(3).areas, ['"f0 f1"', '"f2 f2"'], "le troisième prend la largeur en bas");
  assert.deepEqual(frameLayout(4).areas, ['"f0 f1"', '"f2 f3"']);
  assert.deepEqual(normalizeFrames(null), [{ kind: "map" }, { kind: "table" }]);
  assert.deepEqual(normalizeFrames([{ kind: "bogus" }, { kind: "links" }]), [{ kind: "links" }]);
  assert.equal(normalizeFrames([{ kind: "map" }, { kind: "map" }, { kind: "map" }, { kind: "map" }, { kind: "map" }]).length, 4);
  const s = summarizeByState([{ state: "ok", type: "ups" }, { state: "critical", type: "ups" }, { state: "ok", type: "probe" }]);
  assert.equal(s.total, 3); assert.equal(s.critical, 1); assert.equal(s.byType.ups.total, 2);
});

test("préférences : lecture tolérante, écriture silencieuse", () => {
  const mem = {}; const storage = { getItem: (k) => mem[k] ?? null, setItem: (k, v) => { mem[k] = v; } };
  assert.deepEqual(loadPref(storage, "x", { a: 1 }), { a: 1 });
  savePref(storage, "x", [1, 2]);
  assert.deepEqual(loadPref(storage, "x", null), [1, 2]);
  mem.x = "{bad";
  assert.equal(loadPref(storage, "x", "fb"), "fb");
  assert.equal(loadPref(null, "x", "fb"), "fb");
  savePref({ setItem: () => { throw new Error("plein"); } }, "x", 1);
});

import { spreadCoincident } from "../src/supervisedItems.js";
test("points superposés écartés, points isolés inchangés", () => {
  const pts = spreadCoincident([{ id: 1, lat: 45.77, lon: 2.4 }, { id: 2, lat: 45.77, lon: 2.4 }, { id: 3, lat: 48, lon: -4 }]);
  const a = pts.find((p) => p.id === 1), b = pts.find((p) => p.id === 2), c = pts.find((p) => p.id === 3);
  assert.equal(a.dlat, 45.77); assert.notEqual(`${b.dlat},${b.dlon}`, `${a.dlat},${a.dlon}`);
  assert.ok(Math.abs(b.dlat - 45.77) < 0.002 && Math.abs(b.dlon - 2.4) < 0.002);
  assert.equal(c.dlat, 48);
});

test("#426 géolocalisation par nom : une correspondance appliquée vaut position, jamais le repli", () => {
  const supervised = [
    { identity: "ip:10.0.0.1", name: "UPS-Arobase-5", ip: "10.0.0.1", site: null, origins: [] },
    { identity: "ip:10.0.0.2", name: "sw-arobase", ip: "10.0.0.2", site: null, origins: [] },
    { identity: "ip:10.0.0.3", name: "pc-compta", ip: "10.0.0.3", site: null, origins: [] },
    { identity: "ip:10.0.0.4", name: "nas", ip: "10.0.0.4", site: "Annexe", origins: [] },
    { identity: "ip:10.0.0.5", name: "ap-rejet", ip: "10.0.0.5", site: null, origins: [] },
  ];
  const geolocations = [{ localisation: "@5", latitude: 45.76, longitude: 4.83 }, { localisation: "Annexe", latitude: 47, longitude: 1 }, { localisation: "__default__", latitude: 45.77, longitude: 2.4 }, { localisation: "Sans coord", latitude: null, longitude: null }];
  const matches = {
    "ip:10.0.0.1": { status: "auto", localisation: "@5", latitude: 45.76, longitude: 4.83, score: 1, method: "exact/nom", mapped: true },
    "ip:10.0.0.2": { status: "suggested", localisation: "@5", latitude: 45.76, longitude: 4.83, score: 0.5, method: "proche/nom", mapped: true },
    "ip:10.0.0.5": { status: "rejected", localisation: "@5", latitude: 45.76, longitude: 4.83, score: 1, mapped: true },
  };
  const known = knownPositions({ geolocations, supervised, matches });
  assert.equal(known.get("ip:10.0.0.1").source, "nom");
  assert.match(known.get("ip:10.0.0.1").label, /@5 d'après le nom \(automatique/);
  assert.equal(known.has("ip:10.0.0.2"), false, "à confirmer : pas appliquée");
  assert.equal(known.has("ip:10.0.0.5"), false, "rejetée : pas appliquée");
  assert.equal(known.get("site:annexe").source, "site", "site déclaré inchangé");
  const pos = deducePositions(supervised.map((i) => i.identity), [], known);
  assert.equal(pos.get("ip:10.0.0.1").source, "nom");
  assert.equal(pos.get("ip:10.0.0.3").source, "repli");
  assert.equal(appliedMatch(matches, "ip:10.0.0.2"), null);
  assert.deepEqual(displaySite(supervised[0], matches), { site: "@5", resolved: true, status: "auto" });
  assert.deepEqual(displaySite(supervised[3], matches), { site: "Annexe", resolved: false });
  assert.deepEqual(resolveSubjects(supervised)[3], { subject: "ip:10.0.0.4", name: "nas", site: "Annexe" });
  assert.deepEqual(resolveSubjects(supervised, [{ name: "Annexe" }, { name: "Dépôt" }]).slice(5), [{ subject: "site:annexe", name: null, site: "Annexe" }, { subject: "site:dépôt", name: null, site: "Dépôt" }], "un sujet par site, sans doublon");
  assert.equal(resolveKey(supervised), resolveKey([...supervised].reverse()), "clé indépendante de l'ordre");
  const known2 = knownPositions({ geolocations, supervised: [{ identity: "ip:9", name: "x", site: "Annexe-Nord", origins: [] }], matches: { "site:annexe-nord": { status: "auto", localisation: "Agence Annexe Nord", latitude: 48.6, longitude: -4.3, mapped: true } } });
  assert.equal(known2.get("site:annexe-nord").source, "site");
  assert.match(known2.get("site:annexe-nord").label, /≈ Agence Annexe Nord/);
  const rows = geoRows(supervised, matches);
  assert.deepEqual(rows.map((r) => r.status), ["suggested", "none", "none", "auto", "rejected"]);
  const sum = geoSummary(rows, geolocations);
  assert.deepEqual(sum, { total: 5, applied: 1, suggested: 1, none: 2, rejected: 1, unmapped: 0, pendingPlaces: 1 });
});

test("#432 vue réseau passive des agents : voisins/pairs non supervisés = propositions, pairs = liens", () => {
  const supervised = [{ identity: "ip:10.50.7.12", name: "srv-isole", ip: "10.50.7.12", mac: null, site: null, origins: [] }, { identity: "ip:10.50.7.1", name: "gw", ip: "10.50.7.1", mac: null, site: null, origins: [] }];
  const netviews = [{ agent_id: "a1", hostname: "srv-isole", last_ip: "10.50.7.12", at: "2026-09-08T10:00:00Z",
    neighbors: [{ ip: "10.50.7.1", mac: "aa:bb:cc:00:00:01" }, { ip: "10.50.7.30", mac: "aa:bb:cc:00:00:30" }, { ip: "127.0.0.1" }],
    summary: { peers: [{ ip: "192.168.100.5", connections: 2, ports: ["tcp/443"], processes: ["curl"], local: false }, { ip: "10.50.7.30", connections: 1, ports: ["tcp/22"] }] } }];
  const props = buildProposals({ suggestions: [], signals: [], devices: [{ id: 1, ip_address: "192.168.100.5", mac_address: null }], supervised, netviews });
  assert.deepEqual(props.filter((p) => p.kind === "agent").map((p) => p.key), ["agentnv:10.50.7.30"], "passerelle déjà supervisée et pair déjà découvert par network-agent (proposé par lui) exclus");
  const a = props.find((p) => p.kind === "agent");
  assert.match(a.detail, /voisin \+ pair de srv-isole · tcp\/22/);
  const links = buildLinks({ supervised, netviews });
  assert.deepEqual(links.filter((l) => l.via === "si-agent").map((l) => [l.a, l.b, l.weight]), [["ip:10.50.7.12", "ip:192.168.100.5", 2048], ["ip:10.50.7.12", "ip:10.50.7.30", 1024]]);
});
