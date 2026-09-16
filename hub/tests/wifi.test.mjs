import test from "node:test";
import assert from "node:assert/strict";
import { wifiRows, wifiWorst, wifiTone, rssiTone, pctTone, fmt } from "../src/wifiLib.js";

const M = [
  { at: "2026-09-16T10:00:00Z", data: { link: { connected: true, bssid: "02:1", channel: 48, band: "5 GHz", signal_dbm: -61, tx_mbit: 780 }, rates: { retry_pct: 12 }, channel: { busy_pct: 45, other_pct: 5 }, ping: { avg_ms: 18.5, jitter_ms: 35.2, loss_pct: 5 }, neighbourhood: { our_bss: { stations: 12, utilisation_pct: 50.2 } }, summary: { state: "warning" }, alerts: [{}, {}] } },
  { at: "2026-09-16T09:59:00Z", data: { link: { connected: true, bssid: "02:2", signal_dbm: -75, tx_mbit: 130 }, rates: { retry_pct: 31 }, channel: { busy_pct: 82 }, ping: { avg_ms: 4, jitter_ms: 2, loss_pct: 0 }, summary: { state: "critical" }, alerts: [{}] } },
  { at: "2026-09-16T09:58:00Z", data: { link: { connected: false }, summary: { state: "critical" }, alerts: [{}] } },
  { at: "2026-09-16T09:57:00Z", data: { error: "collecte échouée" } },
];

test("wifiRows : une ligne par mesure exploitable", () => {
  const r = wifiRows(M);
  assert.equal(r.length, 3);
  assert.deepEqual([r[0].rssi, r[0].retry, r[0].busy, r[0].jitter, r[0].stations, r[0].bssUtil, r[0].alerts], [-61, 12, 45, 35.2, 12, 50.2, 2]);
  assert.equal(r[2].connected, false);
  assert.equal(r[2].rssi, null);
  assert.deepEqual(wifiRows(null), []);
});

test("wifiWorst : pires valeurs et bornes vues", () => {
  const w = wifiWorst(wifiRows(M));
  assert.equal(w.samples, 3);
  assert.equal(w.disconnected, 1);
  assert.equal(w.rssi.rssi, -75);
  assert.equal(w.retry.retry, 31);
  assert.equal(w.busy.busy, 82);
  assert.equal(w.jitter.jitter, 35.2);
  assert.equal(w.loss.loss, 5);
  assert.deepEqual(w.bssids, ["02:1", "02:2"]);
  assert.equal(wifiWorst([]).rssi, null);
});

test("tons et formats", () => {
  assert.deepEqual([wifiTone("critical"), wifiTone("warning"), wifiTone("ok")], ["bad", "warn", "good"]);
  assert.deepEqual([rssiTone(-85), rssiTone(-72), rssiTone(-55), rssiTone(null)], ["bad", "warn", "good", "neutral"]);
  assert.deepEqual([pctTone(85, 60, 80), pctTone(65, 60, 80), pctTone(10, 60, 80)], ["bad", "warn", "good"]);
  assert.deepEqual([fmt(null), fmt(12.34, " %", 1), fmt(-61, " dBm")], ["—", "12.3 %", "-61 dBm"]);
});
