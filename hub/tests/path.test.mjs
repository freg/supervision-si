import test from "node:test";
import assert from "node:assert/strict";
import { pathRows, pathWorst, pathLabel, dnsSummary } from "../src/pathLib.js";

const P1 = { iface: "wlan0", ssid: "Exemple", ip: "192.0.2.63", gw_ping: { avg_ms: 8, loss_pct: 0 }, dns: [{ server: "192.0.2.5", ok: false }, { server: "192.0.2.1", ok: true, ms: 12 }], dns_public: [{ server: "8.8.8.8", ok: true, ms: 9 }], http: { ok: true, ms: 300 }, https: { ok: true, ms: 400 }, summary: { state: "warning" }, alerts: [{}] };
const P2 = { iface: "eth0", connection: "Filaire", ip: "192.0.2.10", gw_ping: { avg_ms: 1, loss_pct: 0 }, dns: [{ server: "192.0.2.1", ok: true, ms: 2 }], dns_public: [], http: { ok: false, portal: true }, summary: { state: "critical" }, alerts: [{}, {}] };
const M = [
  { at: "2026-09-17T14:00:00Z", data: { paths: [P1, P2] } },
  { at: "2026-09-17T13:59:00Z", data: { paths: [{ ...P1, ip: null, gw_ping: null, dns: [], summary: { state: "critical" }, alerts: [{}] }] } },
  { at: "2026-09-17T13:58:00Z", data: { error: "collecte échouée" } },
];

test("pathLabel / dnsSummary", () => {
  assert.equal(pathLabel(P1), "Exemple");
  assert.equal(pathLabel(P2), "Filaire");
  assert.equal(pathLabel({ iface: "eth1" }), "eth1");
  assert.deepEqual(dnsSummary(P1.dns), { ok: 1, total: 2, worstMs: 12, down: ["192.0.2.5"] });
  assert.deepEqual(dnsSummary(null), { ok: 0, total: 0, worstMs: null, down: [] });
});

test("pathRows : une ligne par chemin et par mesure", () => {
  const r = pathRows(M);
  assert.equal(r.length, 3);
  assert.deepEqual([r[0].label, r[0].dnsOk, r[0].dnsTotal, r[0].dnsMs, r[0].httpMs, r[0].state], ["Exemple", 1, 2, 12, 300, "warning"]);
  assert.deepEqual([r[1].label, r[1].portal, r[1].httpOk, r[1].httpMs], ["Filaire", true, false, null]);
  assert.equal(r[2].ip, null);
  assert.deepEqual(pathRows(null), []);
});

test("pathWorst : par chemin", () => {
  const w = pathWorst(pathRows(M));
  const ex = w.find((x) => x.label === "Exemple");
  assert.deepEqual([ex.samples, ex.noIp, ex.dnsFail, ex.critical, ex.httpMs], [2, 1, 1, 1, 300]);
  const fi = w.find((x) => x.label === "Filaire");
  assert.deepEqual([fi.samples, fi.httpFail], [1, 1]);
});
