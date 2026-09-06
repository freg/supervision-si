// Logique pure de l'onglet « Sondes WiFi » (#407).
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  ageSeconds, formatAge, liveness, groupLatestByAgent, describeWifiLink, signalTone,
  describePing, describeScan, describeSys, detectBssidChanges, seriesOf, buildLinePath, taskLabel,
} from "../src/netprobeAgents.js";

const NOW = Date.parse("2026-09-06T12:00:00Z");

test("âge et vivacité d'une sonde", () => {
  assert.equal(ageSeconds("2026-09-06T11:59:30Z", NOW), 30);
  assert.equal(ageSeconds(null), null);
  assert.equal(ageSeconds("pas une date"), null);
  assert.equal(formatAge(30), "30 s");
  assert.equal(formatAge(125), "2 min");
  assert.equal(formatAge(3700), "1 h 1 min");
  assert.equal(formatAge(90000), "1 j");
  assert.equal(formatAge(null), "jamais");
  assert.equal(liveness({ last_seen_at: "2026-09-06T11:55:00Z" }, NOW), "alive");
  assert.equal(liveness({ last_seen_at: "2026-09-06T10:00:00Z" }, NOW), "stale");
  assert.equal(liveness({}, NOW), "never");
});

test("groupLatestByAgent : une ligne par sonde, une case par tâche", () => {
  const g = groupLatestByAgent([
    { agent_id: "a", task: "wifi_link", at: "t1" }, { agent_id: "a", task: "sys", at: "t1" },
    { agent_id: "b", task: "ping:x", at: "t1" }, null, { task: "sans-agent" },
  ]);
  assert.deepEqual(Object.keys(g), ["a", "b"]);
  assert.deepEqual(Object.keys(g.a), ["wifi_link", "sys"]);
});

test("describeWifiLink : connectée, déconnectée, erreur, tonalité de signal", () => {
  const ok = describeWifiLink({ ok: true, data: { connected: true, ssid: "Alpha", band: "2.4", channel: 6, signal_dbm: -61, tx_bitrate_mbps: 72.2, bssid: "aa" } });
  assert.equal(ok.text, "Alpha · 2.4 GHz ch 6 · -61 dBm · 72.2 Mb/s");
  assert.equal(ok.tone, "good");
  assert.equal(ok.bssid, "aa");
  assert.deepEqual(describeWifiLink({ ok: true, data: { connected: false } }), { text: "déconnectée", tone: "bad" });
  assert.equal(describeWifiLink({ ok: false, error: "iw absent" }).text, "iw absent");
  assert.equal(describeWifiLink(null), null);
  assert.equal(signalTone(-50), "good"); assert.equal(signalTone(-70), "warn"); assert.equal(signalTone(-80), "bad"); assert.equal(signalTone(null), "neutral");
});

test("describePing / describeScan / describeSys", () => {
  assert.deepEqual(describePing({ ok: true, data: { host: "gw", rtt_avg_ms: 1.5, loss_pct: 0 } }), { text: "gw · 1.5 ms · 0% perte", tone: "good" });
  assert.equal(describePing({ ok: true, data: { host: "gw", rtt_avg_ms: 40, loss_pct: 20 } }).tone, "warn");
  assert.equal(describePing({ ok: false, data: { host: "gw" } }).text, "gw injoignable");
  const scan = describeScan({ ok: true, data: { summary: { total: 9, our_channel: "2.4/6", co_channel_count: 3, strongest_co_channel: { bssid: "x", signal_dbm: -40 } } } });
  assert.equal(scan.text, "9 bornes visibles · 3 co-canal (2.4/6)");
  assert.equal(scan.tone, "warn");
  assert.equal(scan.strongest.bssid, "x");
  assert.equal(describeScan({ ok: false, error: "busy" }).text, "busy");
  const sys = describeSys({ ok: true, data: { cpu_temp_c: 52.1, load1: 0.3, uptime_s: 3700, under_voltage_now: true } });
  assert.equal(sys.text, "52.1 °C · charge 0.3 · up 1 h 1 min · ⚡ sous-tension");
  assert.equal(sys.tone, "bad");
  assert.equal(describeSys({ ok: true, data: { cpu_temp_c: 80 } }).tone, "warn");
});

test("detectBssidChanges : itinérance, reconnexion même borne, désordre et erreurs ignorées", () => {
  const ms = [
    { task: "wifi_link", at: "2026-09-06T10:03:00Z", ok: true, data: { connected: true, bssid: "bb", ssid: "N", signal_dbm: -55 } },
    { task: "wifi_link", at: "2026-09-06T10:00:00Z", ok: true, data: { connected: true, bssid: "aa", ssid: "N", signal_dbm: -75 } },
    { task: "wifi_link", at: "2026-09-06T10:01:00Z", ok: false, error: "iw a échoué" },
    { task: "wifi_link", at: "2026-09-06T10:02:00Z", ok: true, data: { connected: true, bssid: "aa", ssid: "N", signal_dbm: -78 } },
    { task: "wifi_link", at: "2026-09-06T10:04:00Z", ok: true, data: { connected: false } },
    { task: "wifi_link", at: "2026-09-06T10:05:00Z", ok: true, data: { connected: true, bssid: "bb", ssid: "N", signal_dbm: -60 } },
    { task: "wifi_link", at: "2026-09-06T10:06:00Z", ok: true, data: { connected: false } },
    { task: "wifi_link", at: "2026-09-06T10:07:00Z", ok: true, data: { connected: true, bssid: "cc", ssid: "N", signal_dbm: -50 } },
    { task: "sys", at: "2026-09-06T10:07:30Z", ok: true, data: { load1: 1 } },
  ];
  const ev = detectBssidChanges(ms);
  assert.equal(ev.length, 3);
  assert.deepEqual([ev[0].from, ev[0].to, ev[0].at, ev[0].signal_before, ev[0].after_disconnect], ["aa", "bb", "2026-09-06T10:03:00Z", -78, false]);
  assert.equal(ev[1].reconnect, true, "déconnexion puis retour sur la même borne : reconnexion, pas itinérance");
  assert.equal(ev[1].disconnected_since, "2026-09-06T10:04:00Z");
  assert.deepEqual([ev[2].from, ev[2].to, ev[2].after_disconnect, ev[2].disconnected_since], ["bb", "cc", true, "2026-09-06T10:06:00Z"]);
  assert.deepEqual(detectBssidChanges([]), []);
  assert.deepEqual(detectBssidChanges(null), []);
});

test("seriesOf et buildLinePath", () => {
  const ms = [
    { ok: true, at: "t2", data: { signal_dbm: -70 } }, { ok: true, at: "t1", data: { signal_dbm: -60 } },
    { ok: false, at: "t3", data: { signal_dbm: -99 } }, { ok: true, at: "t4", data: { signal_dbm: "x" } },
  ];
  const s = seriesOf(ms, "signal_dbm");
  assert.deepEqual(s, [{ at: "t1", value: -60 }, { at: "t2", value: -70 }]);
  const line = buildLinePath(s, 100, 50, 0);
  assert.equal(line.min, -70); assert.equal(line.max, -60);
  assert.equal(line.path, "M 0.0 0.0 L 100.0 50.0", "-60 (max) en haut, -70 (min) en bas");
  assert.equal(buildLinePath([{ at: "t", value: 1 }], 100, 50).path, "", "un seul point : pas de ligne");
  assert.equal(buildLinePath([], 100, 50).path, "");
  const flat = buildLinePath([{ at: "a", value: 5 }, { at: "b", value: 5 }], 100, 50, 0);
  assert.equal(flat.path, "M 0.0 50.0 L 100.0 50.0", "série constante : pas de division par zéro");
});

test("taskLabel", () => {
  assert.equal(taskLabel("ping:192.168.10.1"), "ping 192.168.10.1");
  assert.equal(taskLabel("wifi_link"), "wifi_link");
  assert.equal(taskLabel(""), "");
});
