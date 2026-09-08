import test from "node:test";
import assert from "node:assert/strict";
import {
  riskLabel, severityTone, stateTone, contactTone, gauge, formatBytes, formatUptime, formatAge, ageSeconds,
  sortFleet, riskSummaryText, diskRows, portRows, mergePlugins, validatePluginForm, defaultEntry,
} from "../src/siAgent.js";

test("jauges : bornes et tons alignés sur les seuils disque de l'agent", () => {
  assert.deepEqual(gauge(null), { percent: null, tone: "neutral", width: 0 });
  assert.equal(gauge(42).tone, "good");
  assert.equal(gauge(85).tone, "warn");
  assert.equal(gauge(95).tone, "bad");
  assert.equal(gauge(140).width, 100);
  assert.equal(gauge(12.345).percent, 12.3);
});

test("formats : octets, uptime, âge", () => {
  assert.equal(formatBytes(512), "512 o");
  assert.equal(formatBytes(1536), "1.5 Ko");
  assert.equal(formatBytes(8000000 * 1024), "7.6 Go");
  assert.equal(formatBytes(null), "—");
  assert.equal(formatUptime(123456), "1 j 10 h");
  assert.equal(formatUptime(3700), "1 h 1 min");
  assert.equal(formatUptime(90), "1 min");
  assert.equal(formatAge(45), "45 s");
  assert.equal(formatAge(3600 * 5), "5 h");
  assert.equal(formatAge(86400 * 3), "3 j");
  assert.equal(ageSeconds("2026-09-07T10:00:00Z", Date.parse("2026-09-07T10:01:30Z")), 90);
  assert.equal(ageSeconds(null), null);
});

test("tons et libellés", () => {
  assert.equal(riskLabel("disk-full"), "Disque plein");
  assert.equal(riskLabel("inconnu"), "inconnu");
  assert.equal(severityTone("critical"), "bad");
  assert.equal(severityTone("warning"), "warn");
  assert.equal(stateTone("ok"), "good");
  assert.equal(stateTone("unknown"), "neutral");
  assert.equal(contactTone("online"), "good");
  assert.equal(contactTone("offline"), "bad");
  assert.equal(contactTone("never"), "neutral");
});

test("tri de la flotte : critiques, hors ligne, avertissements, ok, jamais vus", () => {
  const fleet = [
    { agent_id: "z", site: "b", online: "online", risks: { state: "ok" } },
    { agent_id: "a", site: "b", online: "never", risks: { state: "unknown" } },
    { agent_id: "m", site: "a", online: "offline", risks: { state: "ok" } },
    { agent_id: "k", site: "a", online: "online", risks: { state: "critical" } },
    { agent_id: "w", site: "a", online: "online", risks: { state: "warning" } },
  ];
  assert.deepEqual(sortFleet(fleet).map((a) => a.agent_id), ["k", "m", "w", "z", "a"]);
});

test("résumé des risques", () => {
  assert.equal(riskSummaryText({ state: "critical", counts: { critical: 2, warning: 3, info: 0 } }), "2 critiques, 3 avertissements");
  assert.equal(riskSummaryText({ state: "warning", counts: { warning: 1 } }), "1 avertissement");
  assert.equal(riskSummaryText({ state: "ok", counts: {} }), "aucun");
  assert.equal(riskSummaryText(null), "—");
});

test("disques et ports dérivés d'une mesure host", () => {
  const host = {
    disks: [{ mountpoint: "/", device: "/dev/sda1", fstype: "ext4", used_bytes: 96 * 1024 ** 3, total_bytes: 100 * 1024 ** 3, used_percent: 96 }],
    ports: { ports: [{ proto: "tcp", port: 6379, exposed: false }, { proto: "tcp", port: 3306, exposed: true }, { proto: "tcp", port: 22, exposed: true }] },
  };
  const d = diskRows(host);
  assert.equal(d[0].used, "96 Go");
  assert.equal(d[0].gauge.tone, "bad");
  assert.deepEqual(portRows(host).map((p) => p.port), [22, 3306, 6379]);
  assert.deepEqual(diskRows(null), []);
});

test("fusion sondes affectées (central) et présentes (inventaire de l'hôte)", () => {
  const merged = mergePlugins(
    [{ id: "hello", version: "2", runner: "shell", enabled: true }, { id: "new", version: "1", runner: "python", enabled: false }],
    [{ id: "hello", version: "1", enabled: true, source: "central" }, { id: "network-neighbors", version: "1", enabled: false, runner: "shell" }],
  );
  assert.deepEqual(merged.map((p) => p.id), ["hello", "network-neighbors", "new"]);
  const hello = merged[0];
  assert.equal(hello.assigned, true);
  assert.equal(hello.present, true);
  assert.equal(hello.version, "2", "la version du catalogue prime");
  assert.equal(merged[1].assigned, false);
  assert.equal(merged[1].source, "bundled", "sans origine déclarée = livrée avec l'agent");
  assert.equal(merged[2].present, false);
});

test("validation du formulaire de sonde (miroir de validate_manifest)", () => {
  const ok = { id: "disk-smart", runner: "shell", entry: "disk_smart.sh", interval_seconds: "300", body: "echo {}" };
  assert.equal(validatePluginForm(ok), null);
  assert.match(validatePluginForm({ ...ok, id: "Bad Id" }), /identifiant/);
  assert.match(validatePluginForm({ ...ok, runner: "perl" }), /runner/);
  assert.match(validatePluginForm({ ...ok, entry: "../x.sh" }), /entrée/);
  assert.match(validatePluginForm({ ...ok, interval_seconds: "5" }), /30 s/);
  assert.match(validatePluginForm({ ...ok, body: "  " }), /vide/);
  assert.equal(defaultEntry("python", "disk-smart"), "disk_smart.py");
  assert.equal(defaultEntry("shell", ""), "plugin.sh");
});

// ---- #422 ----
import { eventKindLabel, isSecurityEvent, summarizeEvents, filterEvents, bannerTone, bannerHeadline } from "../src/siAgent.js";

test("événements : libellés, sécurité, synthèse, filtres", () => {
  assert.equal(eventKindLabel("fleet-blocked"), "BLOCAGE GÉNÉRAL de la flotte");
  assert.equal(eventKindLabel("zzz"), "zzz");
  assert.equal(isSecurityEvent({ kind: "plugin-refused", severity: "warning" }), true);
  assert.equal(isSecurityEvent({ kind: "config-applied", severity: "info" }), false);
  assert.equal(isSecurityEvent({ kind: "whatever", severity: "critical" }), true);
  const evs = [
    { id: 1, kind: "plugin-refused", severity: "warning", source: "agent", agent_id: "a", message: "refusée" },
    { id: 2, kind: "config-applied", severity: "info", source: "agent", agent_id: "a", message: "ok" },
    { id: 3, kind: "fleet-blocked", severity: "critical", source: "central", agent_id: null, message: "incident" },
    { id: 4, kind: "agent-enrolled", severity: "info", source: "central", agent_id: "b", message: "enrôlé" },
  ];
  const sm = summarizeEvents(evs);
  assert.deepEqual([sm.total, sm.critical, sm.warning, sm.info, sm.agent, sm.central, sm.security], [4, 1, 1, 2, 2, 2, 2]);
  assert.deepEqual(filterEvents(evs, { minSeverity: "warning" }).map((e) => e.id), [1, 3]);
  assert.deepEqual(filterEvents(evs, { agent: "a" }).map((e) => e.id), [1, 2]);
  assert.deepEqual(filterEvents(evs, { securityOnly: true }).map((e) => e.id), [1, 3]);
  assert.deepEqual(filterEvents(evs, { text: "ENRÔ" }).map((e) => e.id), [4]);
});

test("bandeau d'accueil : ton et titre", () => {
  assert.equal(bannerTone(null), "neutral");
  assert.equal(bannerTone({ fleet_blocked: true, counts: {} }), "bad");
  assert.equal(bannerTone({ counts: { critical: 1 } }), "bad");
  assert.equal(bannerTone({ counts: { warning: 2 }, agents_offline: [] }), "warn");
  assert.equal(bannerTone({ counts: {}, agents_offline: ["x"] }), "warn");
  assert.equal(bannerTone({ counts: {}, agents_offline: [], agents_blocked: [] }), "good");
  assert.match(bannerHeadline({ fleet_blocked: true, fleet_block_reason: "incident", counts: {} }), /BLOCAGE GÉNÉRAL.*incident/);
  assert.equal(bannerHeadline({ counts: {}, agents_offline: [], agents_blocked: [], window_hours: 24, agents: 3 }), "Agents hôtes : rien à signaler sur 24 h (3 agents)");
  assert.equal(bannerHeadline({ counts: { critical: 1, warning: 2 }, agents_offline: ["a"], agents_blocked: [], window_hours: 24 }), "Agents hôtes, 24 h : 1 critique, 2 avertissements, 1 agent hors ligne");
});
