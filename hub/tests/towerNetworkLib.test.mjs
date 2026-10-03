import test from "node:test";
import assert from "node:assert/strict";
import { dnsRows, dnsSummary, routingSummary, topFlows, fmtBytes, resourceRows } from "../src/towerNetworkLib.js";

test("dnsRows et dnsSummary", () => {
  const rows = dnsRows([{ name: "www.exemple", last: { ips: ["203.0.113.5"], state: "ok", alerts: [], at: "t1" } }, { name: "mail.exemple", last: { state: "down", alerts: ["x"] } }],
    [{ hostname: "pc-1", at: "t2", alerts: [{ name: "intranet", message: "NXDOMAIN sur VLAN 20" }] }]);
  assert.equal(rows.length, 3); assert.equal(rows[2].kind, "divergence"); assert.equal(rows[2].detail, "NXDOMAIN sur VLAN 20");
  assert.deepEqual(dnsSummary(rows), { total: 3, ko: 2, alerts: 2 });
});

test("routingSummary", () => {
  const s = routingSummary([{ name: "rb", routes: [{ dst: "0.0.0.0/0", gateway: "192.0.2.1", active: true }, { dst: "10.0.0.0/8", gateway: "192.0.2.9", disabled: true }], nat: 3 }, { name: "rc", error: "injoignable" }]);
  assert.deepEqual(s[0], { router: "rb", error: null, total: 2, active: 1, disabled: 1, defaults: ["192.0.2.1"], nat: 3 });
  assert.equal(s[1].error, "injoignable"); assert.equal(s[1].total, 0);
});

test("topFlows, fmtBytes, resourceRows", () => {
  const f = topFlows([{ device_a_name: "pc", device_b_ip: "203.0.113.9", bytes: 5000 }, { a: "x", b: "y", total_bytes: 9000 }], 1);
  assert.deepEqual(f, [{ a: "x", b: "y", bytes: 9000, packets: 0 }]);
  assert.equal(fmtBytes(1536), "1.5 Ko"); assert.equal(fmtBytes(2 * 1073741824), "2.00 Go");
  const r = resourceRows([{ hostname: "pc", resources: [{ name: "ged", clients: ["a", "b"], hits: 4 }, { host: "x", hits: 9, ok: false }] }], 1);
  assert.deepEqual(r, [{ agent: "pc", name: "x", clients: 0, hits: 9, ok: false }]);
});
