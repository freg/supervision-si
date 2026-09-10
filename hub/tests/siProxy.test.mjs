import test from "node:test";
import assert from "node:assert/strict";
import { parseAdminUsers, canSeeBastion, fmtDuration, fmtBytes, clientLabel, describeEvent, sortAudit, refusalsByPeer, headline } from "../src/siProxy.js";
import { fromSiProxy, buildLinks, ITEM_TYPES } from "../src/supervisedItems.js";

test("accès à la tuile : liste blanche insensible à la casse", () => {
  assert.deepEqual(parseAdminUsers(" freg, Francois ,,"), ["freg", "francois"]);
  assert.equal(canSeeBastion("FREG", "freg"), true);
  assert.equal(canSeeBastion("eve", "freg,francois"), false);
  assert.equal(canSeeBastion("", "freg"), false);
  assert.equal(canSeeBastion("freg", ""), false);
});

test("formats durée / volume / client", () => {
  assert.equal(fmtDuration(42), "42 s");
  assert.equal(fmtDuration(125), "2 min 5 s");
  assert.equal(fmtDuration(3600), "1 h");
  assert.equal(fmtDuration(null), "—");
  assert.equal(fmtBytes(512), "512 o");
  assert.equal(fmtBytes(2048), "2.0 Ko");
  assert.equal(fmtBytes(3 * 1024 * 1024), "3.0 Mo");
  assert.equal(clientLabel("cn:freg"), "freg (certificat)");
  assert.equal(clientLabel("token:client"), "jeton client");
});

test("description des événements du journal", () => {
  assert.equal(describeEvent({ event: "session-start", session: 3, kind: "connect", target: "10.0.0.1:443", client: "cn:freg", peer: "1.2.3.4" }),
    "#3 https (CONNECT) → 10.0.0.1:443 par freg (certificat) depuis 1.2.3.4");
  assert.match(describeEvent({ event: "session-end", session: 3, kind: "shell", duration_s: 90, bytes_up: 100, bytes_down: 2048 }), /#3 shell host — 1 min 30 s, 100 o ↑ \/ 2\.0 Ko ↓/);
  assert.equal(describeEvent({ event: "refused", peer: "9.9.9.9", reason: "jeton refusé", kind: "shell" }), "refus de 9.9.9.9 : jeton refusé (shell host)");
});

test("tri inverse, filtre et refus par IP", () => {
  const ev = [
    { event: "refused", at: "2026-09-08T10:00:00", peer: "9.9.9.9", reason: "jeton refusé" },
    { event: "session-start", at: "2026-09-08T11:00:00", session: 1 },
    { event: "refused", at: "2026-09-08T12:00:00", peer: "9.9.9.9", reason: "jeton refusé" },
    { event: "refused", at: "2026-09-08T09:00:00", peer: "8.8.8.8", reason: "CN non autorisé" },
  ];
  assert.equal(sortAudit(ev)[0].at, "2026-09-08T12:00:00");
  assert.equal(sortAudit(ev, { only: "session-start" }).length, 1);
  assert.equal(sortAudit(ev, { limit: 2 }).length, 2);
  const r = refusalsByPeer(ev);
  assert.deepEqual(r.map((x) => [x.peer, x.count]), [["9.9.9.9", 2], ["8.8.8.8", 1]]);
  assert.equal(r[0].last, "2026-09-08T12:00:00");
});

test("bandeau d'état", () => {
  assert.equal(headline(null).state, "critical");
  assert.equal(headline({ error: "relais injoignable : x" }).text, "relais injoignable : x");
  assert.equal(headline({ host_connected: false, enabled: true, sessions: [] }).state, "warning");
  assert.equal(headline({ host_connected: true, enabled: false, sessions: [] }).state, "warning");
  assert.equal(headline({ host_connected: true, enabled: true, sessions: [{}, {}] }).text, "2 session(s) en cours");
});

test("catégorie Bastion dans la supervision : relais + shim host + liens vers les cibles", () => {
  assert.equal(ITEM_TYPES.bastion.origin, "si-proxy");
  const summary = { state: "ok", state_text: "1 session(s) en cours", host_connected: true, enabled: true, sessions_active: 1,
    last_session: { at: "2026-09-08T12:00:00" },
    targets: [{ host: "192.168.1.10", target: "192.168.1.10:443", count: 2, kinds: ["connect"], bytes: 1100, last: "2026-09-08T12:00:00" }] };
  const items = fromSiProxy(summary, { hubHost: "super" });
  assert.equal(items.length, 2);
  const relay = items.find((i) => i.key === "bastion:relay"), host = items.find((i) => i.key === "bastion:host");
  assert.equal(relay.type, "bastion");
  assert.equal(relay.state, "ok");
  assert.equal(host.stateText, "shim connecté (shell sous freg)");
  // shim absent -> warning sur les deux entrées
  const down = fromSiProxy({ ...summary, state: "warning", state_text: "shim host non connecté", host_connected: false }, { hubHost: "super" });
  assert.equal(down.find((i) => i.key === "bastion:host").state, "warning");
  // relais injoignable -> critical
  assert.equal(fromSiProxy({ state: "critical", state_text: "relais injoignable", relay: "down" }, {})[0].state, "critical");
  assert.deepEqual(fromSiProxy(null, {}), []);
  // liens « bastion » : hub -> cible jointe, via si-proxy
  const links = buildLinks({ bastion: summary, hubHost: "super" });
  const b = links.filter((l) => l.kind === "bastion");
  assert.equal(b.length, 1);
  assert.equal(b[0].via, "si-proxy");
  assert.equal(b[0].b, "ip:192.168.1.10");
  assert.match(b[0].label, /super → 192\.168\.1\.10:443 \(2 session\(s\), https \(CONNECT\)\)/);
  assert.equal(b[0].weight, 1100);
});
