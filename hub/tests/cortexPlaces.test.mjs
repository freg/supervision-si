import test from "node:test";
import assert from "node:assert/strict";
import { provenanceStyle, defaultLayers, boundsOf, sortPositions, provenanceCounts, chainText, whereText, LAYERS, ruleText, minutesLeft, predictionStats, sparkPath } from "../src/cortexPlaces.js";

test("provenances, couches et bornes", () => {
  assert.equal(provenanceStyle("déclarée").tone, "good");
  assert.equal(provenanceStyle("repli").tone, "bad");
  assert.equal(provenanceStyle("???").tone, "neutral");
  const d = defaultLayers();
  assert.ok(d.has("positions") && d.has("incidents") && !d.has("density"));
  assert.equal(LAYERS.length, 5);
  assert.equal(boundsOf([]), null);
  const one = boundsOf([{ geometry: { type: "Point", coordinates: [4.83, 45.76] } }]);
  assert.ok(one[0][0] < 45.76 && one[1][0] > 45.76);
  const two = boundsOf([{ geometry: { type: "Point", coordinates: [4.83, 45.76] } }, { geometry: { type: "Point", coordinates: [2.35, 48.85] } }, { geometry: { type: "LineString", coordinates: [[0, 0], [1, 1]] } }]);
  assert.deepEqual(two, [[45.76, 2.35], [48.85, 4.83]]);
});

test("tri, comptes, chaîne, où aller", () => {
  const rows = [{ entity: "a", name: "zed", provenance: "déclarée" }, { entity: "b", name: "alpha", provenance: "repli" }, { entity: "c", name: "beta", provenance: "repli" }, { entity: "d", name: "vm", provenance: "propagée" }];
  assert.deepEqual(sortPositions(rows).map((r) => r.entity), ["b", "c", "d", "a"]);   // le moins sûr d'abord
  assert.deepEqual(sortPositions(rows, "repli").map((r) => r.entity), ["b", "c"]);
  assert.deepEqual(provenanceCounts(rows), [["déclarée", 1], ["propagée", 1], ["repli", 2]]);
  assert.equal(chainText({ evidence: "lieu bureau (site)", chain: [] }), "lieu bureau (site)");
  assert.equal(chainText({ chain: [{ via: "uplink", why: "borne", from: "mac:1", from_provenance: "déclarée" }] }), "borne ← mac:1 [déclarée]");
  assert.equal(whereText({ where: [{ name: "siege" }, { name: "B1" }, { name: "Local technique" }] }), "siege › B1 › Local technique");
  assert.equal(whereText({ where: [], entity: { site: "cloud" } }), "site cloud (non positionné)");
});

test("règles, annonces, sparkline (#465)", () => {
  assert.equal(ruleText({ a_text: "sur batterie sur UPS", b_text: "agent-offline sur srv-a", delay_s: 180, delay_min_s: 120, delay_max_s: 300, count: 5, support_a: 6 }), "agent-offline sur srv-a suit sur batterie sur UPS dans 3 min (5 fois sur 6, entre 2 et 5 min)");
  assert.equal(minutesLeft({ expected_at: new Date(Date.now() + 5 * 60000).toISOString() }), 5);
  assert.equal(minutesLeft({ expected_at: "n/a" }), null);
  const st = predictionStats([{ outcome: null }, { outcome: "hit" }, { outcome: "hit" }, { outcome: "miss" }]);
  assert.deepEqual([st.pending, st.hits, st.misses], [1, 2, 1]); assert.ok(Math.abs(st.accuracy - 2 / 3) < 1e-9);
  assert.equal(predictionStats([]).accuracy, null);
  assert.equal(sparkPath([{ value: 1 }]), "");
  const d = sparkPath([{ value: 0 }, { value: 10 }, { value: 5 }], 100, 20);
  assert.ok(d.startsWith("M1.0,19.0") && d.includes("L50.0,1.0"));
});
