import test from "node:test";
import assert from "node:assert/strict";
import { dnsLabel, dnsTone, alerts, routeLabel, reachState, independent, routeToForm, formToRoute } from "../src/edgePairLib.js";

test("états DNS, alertes, joignabilité", () => {
  assert.equal(dnsLabel(null), "pas encore contrôlé"); assert.equal(dnsTone({ state: "a_configurer" }), "critical");
  const v = { routes: [{ name: "www.example.org", dns: { state: "a_configurer", data: {} } }, { name: "ok.example.org", dns: { state: "ok" } }],
    proxies: [{ label: "a", problems: [{ title: "HAProxy arrêté" }] }] };
  assert.deepEqual(alerts(v).map((x) => x.kind), ["dns", "proxy"]);
  assert.equal(reachState({ reach: { a: 2, b: null } }), "partiel"); assert.equal(reachState({ reach: { a: 2, b: 3 } }), "ok"); assert.equal(reachState({ reach: {} }), "inconnu");
});

test("couple, formulaires", () => {
  assert.equal(independent([{ node: "pve-a" }, { node: "pve-b" }]), true); assert.equal(independent([{ node: "pve-a" }, { node: "pve-a" }]), false);
  assert.equal(routeLabel({ mode: "tcp", front_port: 9922 }), "port 9922");
  const f = routeToForm({ mode: "sni", name: "w.example.org", backend: "192.0.2.1:443", candidates: ["192.0.2.1:443", "192.0.2.2:443"] });
  assert.equal(f.candidates, "192.0.2.2:443");
  assert.deepEqual(formToRoute({ ...f, mode: "tcp", front_port: "9922" }).front_port, 9922);
  assert.equal("front_port" in formToRoute(f), false);
});
