import test from "node:test";
import assert from "node:assert/strict";
import { fmtMs, groups, pointsFor, pointLabel, worst, counts, accessCommand, targetToForm, formToTarget, formToPoint, parseConfig, sparkPoints } from "../src/latencyLib.js";

const V = {
  targets: [{ id: "a", label: "A", grp: "OVH" }, { id: "b", label: "B", grp: "" }, { id: "c", label: "C", grp: "OVH" }],
  points: [{ id: "lan", mode: "agent", agent: "super", label: "LAN", targets: [] }, { id: "in", mode: "direct", agent: "super", login: "francois", host: "198.51.100.7", port: 22, sudo: true, label: "in", targets: ["a"] }],
  cells: { "a|lan": { level: "ok" }, "a|in": { level: "critical" }, "b|lan": { level: "warning" } },
};

test("formats, groupes, points", () => {
  assert.equal(fmtMs(7900), "7.9 s"); assert.equal(fmtMs(85.4), "85 ms"); assert.equal(fmtMs(null), "—");
  assert.deepEqual(groups(V.targets).map((g) => [g.grp, g.targets.map((t) => t.id)]), [["sans groupe", ["b"]], ["OVH", ["a", "c"]]]);
  assert.deepEqual(pointsFor(V.points, "b").map((p) => p.id), ["lan"]);
  assert.equal(pointLabel(V.points[1]), "in (francois@198.51.100.7, sudo depuis super)");
});

test("niveaux", () => {
  assert.equal(worst(V, "a"), "critical"); assert.equal(worst(V, "c"), null);
  assert.deepEqual(counts(V), { ok: 0, warning: 1, critical: 1, none: 1 });
});

test("accès, formulaires, import, sparkline", () => {
  const c = accessCommand({ ...V.points[1], jump: "freg@gw.example.org:9922", port: 2222 });
  assert.match(c, /^K=\$\(ssh root@super /); assert.match(c, /ssh -t -p 2222 -J freg@gw\.example\.org:9922 francois@198\.51\.100\.7 /);
  assert.equal(accessCommand(V.points[0]), "");
  assert.deepEqual(formToTarget(targetToForm({ ports: [22, 443], names: ["x.example.org"] })), { ports: [22, 443], names: ["x.example.org"] });
  assert.deepEqual(formToPoint({ port: "2222", targets: "a, b" }), { port: 2222, targets: ["a", "b"] });
  assert.match(parseConfig("{").error, /JSON invalide/); assert.equal(parseConfig('{"targets": []}').error, null);
  assert.equal(sparkPoints([{ t: 1 }, { t: 3 }], "t", 10, 10), "0,10 10,0");
});
