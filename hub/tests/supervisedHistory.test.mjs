import test from "node:test";
import assert from "node:assert/strict";
import {
  HISTORY_WINDOWS, windowById, pointsFromNetprobeSamples, pointsFromUpsReadings, pointsFromAgentRisks, stateSegments, worstState,
  bucketize, calendarDays, dayTone, buildHierarchy, radialLayout, effectiveSelection, toggleSelection,
} from "../src/supervisedHistory.js";

const T0 = Date.parse("2026-09-08T00:00:00Z");
const H = 3600000;

test("normalisation des historiques en points d'état", () => {
  const np = pointsFromNetprobeSamples([{ sampled_at: "2026-09-08T01:00:00Z", success: 0, error: "timeout" }, { sampled_at: "2026-09-08T00:00:00Z", success: 1, latency_ms: 3 }, { sampled_at: "bogus" }]);
  assert.deepEqual(np.map((p) => p.state), ["ok", "critical"], "triés, invalides écartés");
  assert.equal(np[0].text, "3 ms");
  const ups = pointsFromUpsReadings([{ polled_at: "2026-09-08T00:00:00Z", ok: 1, state: "ok" }, { polled_at: "2026-09-08T01:00:00Z", ok: 1, state: "alarm" }, { polled_at: "2026-09-08T02:00:00Z", ok: 0, error: "HTTP 500" }]);
  assert.deepEqual(ups.map((p) => p.state), ["ok", "critical", "critical"]);
  const ag = pointsFromAgentRisks([{ at: "2026-09-08T00:00:00Z", data: { summary: { state: "warning" } } }, { at: "2026-09-08T00:01:00Z", data: {} }]);
  assert.deepEqual(ag.map((p) => p.state), ["warning", "unknown"]);
  assert.equal(windowById("zzz").id, "24h");
  assert.equal(HISTORY_WINDOWS.length, 4);
});

test("timeline : segments contigus, trous = inconnu, fusion des états égaux", () => {
  const pts = [{ at: T0 + H, state: "ok", text: "a" }, { at: T0 + 2 * H, state: "ok", text: "b" }, { at: T0 + 3 * H, state: "critical", text: "c" }, { at: T0 + 10 * H, state: "ok", text: "d" }];
  const segs = stateSegments(pts, { startMs: T0, endMs: T0 + 12 * H, gapMs: 2 * H });
  assert.deepEqual(segs.map((s) => [s.state, (s.end - s.start) / H]), [["unknown", 1], ["ok", 2], ["critical", 2], ["unknown", 5], ["ok", 2]]);
  assert.deepEqual(stateSegments([], { startMs: T0, endMs: T0 + H }).map((s) => s.state), ["unknown"]);
  const clipped = stateSegments([{ at: T0 - 5 * H, state: "ok" }], { startMs: T0, endMs: T0 + H, gapMs: 24 * H });
  assert.deepEqual(clipped.map((s) => [s.state, s.start === T0]), [["ok", true]], "un point antérieur à la fenêtre couvre son début");
});

test("mosaïque : créneaux, pire état par créneau, créneaux vides", () => {
  assert.equal(worstState(["ok", "warning", "ok"]), "warning");
  assert.equal(worstState([]), null);
  const cells = bucketize([{ at: T0 + 10 * 60000, state: "ok" }, { at: T0 + 50 * 60000, state: "critical" }, { at: T0 + 3 * H, state: "ok" }], { startMs: T0, endMs: T0 + 4 * H, bucketMs: H });
  assert.equal(cells.length, 4);
  assert.deepEqual(cells.map((c) => c.state), ["critical", null, null, "ok"]);
  assert.equal(cells[0].count, 2);
});

test("calendrier de densité : événements pas-ok par jour, seuils de couleur", () => {
  const start = Date.parse("2026-09-01T00:00:00");
  const days = calendarDays({
    a: [{ at: Date.parse("2026-09-02T10:00:00"), state: "critical" }, { at: Date.parse("2026-09-02T11:00:00"), state: "ok" }],
    b: [{ at: Date.parse("2026-09-02T12:00:00"), state: "warning" }, { at: Date.parse("2026-09-03T12:00:00"), state: "unknown" }],
  }, { startMs: start, endMs: Date.parse("2026-09-04T00:00:00") });
  assert.equal(days.length, 3);
  assert.deepEqual(days.map((d) => [d.day, d.events, d.items]), [["2026-09-01", 0, 0], ["2026-09-02", 2, 2], ["2026-09-03", 0, 0]]);
  assert.equal(dayTone(0), "good"); assert.equal(dayTone(1), "warn"); assert.equal(dayTone(3), "bad");
  assert.equal(dayTone(1, { warn: 2, bad: 5 }), "good");
});

test("arbre radial : hiérarchie site → type → équipement et disposition sans chevauchement d'angle", () => {
  const items = [
    { identity: "a", name: "UPS", type: "ups", site: "Siège", state: "ok" }, { identity: "b", name: "Sonde", type: "probe", site: "Siège", state: "critical" },
    { identity: "c", name: "Agent", type: "agent", site: null, state: "warning" },
  ];
  const tree = buildHierarchy(items);
  assert.deepEqual(tree.children.map((c) => c.name), ["Siège", "sans site"]);
  assert.deepEqual(tree.children[0].children.map((c) => c.name), ["probe", "ups"]);
  const lay = radialLayout(tree, { radius: 150 });
  assert.equal(lay.nodes.filter((n) => n.kind === "item").length, 3);
  assert.equal(lay.links.length, lay.nodes.length - 1);
  const leaves = lay.nodes.filter((n) => n.kind === "item").map((n) => n.angle).sort((x, y) => x - y);
  assert.ok(leaves[1] - leaves[0] > 1 && leaves[2] - leaves[1] > 1, "feuilles réparties uniformément");
  const root = lay.nodes.find((n) => n.kind === "root");
  assert.equal(root.r, 0);
  assert.ok(Math.abs(Math.hypot(lay.nodes.find((n) => n.kind === "item").x, lay.nodes.find((n) => n.kind === "item").y) - 150) < 1e-6, "feuilles au rayon demandé");
  // enjambement 0/2π : un nœud avec deux feuilles à 0 et ~2π reste centré vers 0, pas vers π
  const two = radialLayout({ name: "r", kind: "root", children: [{ name: "s", kind: "site", children: [{ name: "x", kind: "item", children: [] }, { name: "y", kind: "item", children: [] }, { name: "z", kind: "item", children: [] }] }] });
  assert.ok(two.nodes.find((n) => n.kind === "site").angle >= 0);
});

test("corbeille de sélection : cochés > priorisés > premiers visibles, bornée", () => {
  const visible = [{ identity: "a" }, { identity: "b" }, { identity: "c" }];
  assert.deepEqual(effectiveSelection([], visible, {}, 2), ["a", "b"]);
  assert.deepEqual(effectiveSelection([], visible, { c: 1 }, 2), ["c"]);
  assert.deepEqual(effectiveSelection(["b", "zz"], visible, { c: 1 }, 2), ["b"], "coché mais non visible ignoré");
  assert.deepEqual(toggleSelection(["a"], "b").sort(), ["a", "b"]);
  assert.deepEqual(toggleSelection(["a", "b"], "a"), ["b"]);
});
