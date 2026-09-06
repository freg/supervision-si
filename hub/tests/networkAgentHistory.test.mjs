// Tests de la logique PURE des historiques de l'agent réseau.
// Lancer : node --test hub/tests/networkAgentHistory.test.mjs
import { test } from "node:test";
import assert from "node:assert/strict";
import {
  formatBytes, aggregateBySnapshot, computeDeltaSeries, buildBarLayout, sumDeltas,
} from "../src/networkAgentHistory.js";

test("formatBytes couvre o/Ko/Mo/Go et refuse l'inconnu", () => {
  assert.equal(formatBytes(512), "512 o");
  assert.equal(formatBytes(2048), "2.0 Ko");
  assert.equal(formatBytes(3 * 1024 * 1024), "3.0 Mo");
  assert.equal(formatBytes(2.5 * 1024 ** 3), "2.50 Go");
  assert.equal(formatBytes(undefined), "?");
  assert.equal(formatBytes(NaN), "?");
});

test("aggregateBySnapshot somme les lignes par relevé et trie par date", () => {
  // Forme réelle de /links/history : une ligne par (relevé, protocole, port),
  // pas forcément triée si on la reçoit d'ailleurs.
  const rows = [
    { snapshot_at: "2026-09-06T12:00:00Z", protocol: "tcp", port: 443, packet_count: 10, bytes_total: 1000 },
    { snapshot_at: "2026-09-06T11:00:00Z", protocol: "tcp", port: 443, packet_count: 4, bytes_total: 400 },
    { snapshot_at: "2026-09-06T12:00:00Z", protocol: "udp", port: 53, packet_count: 2, bytes_total: 200 },
    { snapshot_at: null, bytes_total: 999999 },   // ligne malformée : ignorée
  ];
  const out = aggregateBySnapshot(rows);
  assert.deepEqual(out, [
    { at: "2026-09-06T11:00:00Z", bytes: 400, packets: 4 },
    { at: "2026-09-06T12:00:00Z", bytes: 1200, packets: 12 },
  ]);
});

test("computeDeltaSeries : premier point sans delta, jamais 0", () => {
  const s = computeDeltaSeries([{ snapshot_at: "a", bytes_total: 500 }]);
  assert.equal(s.length, 1);
  assert.equal(s[0].delta, null);
  assert.equal(s[0].cumulative, 500);
});

test("computeDeltaSeries calcule les deltas entre relevés cumulatifs", () => {
  const s = computeDeltaSeries([
    { snapshot_at: "2026-09-06T10:00:00Z", bytes_total: 100 },
    { snapshot_at: "2026-09-06T11:00:00Z", bytes_total: 350 },
    { snapshot_at: "2026-09-06T12:00:00Z", bytes_total: 350 },
  ]);
  assert.deepEqual(s.map((p) => p.delta), [null, 250, 0]);
  assert.ok(s.every((p) => p.reset === false));
});

test("computeDeltaSeries marque un recul du compteur comme reset", () => {
  // Redémarrage de capture : le cumul repart de plus bas. Le delta brut
  // serait négatif -- on prend le nouveau cumul comme estimation et on le
  // signale, plutôt que d'afficher un volume négatif ou de lisser en 0.
  const s = computeDeltaSeries([
    { snapshot_at: "t1", bytes_total: 5000 },
    { snapshot_at: "t2", bytes_total: 800 },
    { snapshot_at: "t3", bytes_total: 1000 },
  ]);
  assert.equal(s[1].reset, true);
  assert.equal(s[1].delta, 800);
  assert.equal(s[2].reset, false);
  assert.equal(s[2].delta, 200);
});

test("computeDeltaSeries résiste aux entrées vides ou invalides", () => {
  assert.deepEqual(computeDeltaSeries([]), []);
  assert.deepEqual(computeDeltaSeries(null), []);
  assert.deepEqual(computeDeltaSeries(undefined), []);
});

test("buildBarLayout : une barre par delta connu, échelle sur le max", () => {
  const series = computeDeltaSeries([
    { snapshot_at: "t1", bytes_total: 0 },
    { snapshot_at: "t2", bytes_total: 100 },
    { snapshot_at: "t3", bytes_total: 150 },
    { snapshot_at: "t4", bytes_total: 150 },
  ]);
  const { bars, max } = buildBarLayout(series, 400, 50, 0);
  assert.equal(max, 100);
  assert.equal(bars.length, 3, "le premier point (delta null) n'a pas de barre");
  assert.equal(bars[0].h, 50, "le max occupe toute la hauteur");
  assert.equal(bars[1].h, 25);
  assert.equal(bars[2].h, 0, "un delta nul donne une barre de hauteur 0 strict");
  // L'axe du temps reste régulier : 4 créneaux de 100 même sans barre au premier.
  assert.equal(bars[0].x, 100);
  assert.equal(bars[0].w, 100);
});

test("buildBarLayout : hauteur minimale visible pour un delta minuscule", () => {
  const series = computeDeltaSeries([
    { snapshot_at: "t1", bytes_total: 0 },
    { snapshot_at: "t2", bytes_total: 1 },
    { snapshot_at: "t3", bytes_total: 1000001 },
  ]);
  const { bars } = buildBarLayout(series, 200, 40);
  assert.equal(bars[0].h, 1, "1 octet sur 1 Mo doit rester visible");
  assert.equal(bars[1].h, 40);
});

test("buildBarLayout : cadre vide ou série vide", () => {
  assert.deepEqual(buildBarLayout([], 100, 50), { bars: [], max: 0 });
  assert.deepEqual(buildBarLayout([{ delta: 1 }], 0, 50), { bars: [], max: 0 });
});

test("sumDeltas ignore le premier point et compte les resets à leur estimation", () => {
  const s = computeDeltaSeries([
    { snapshot_at: "t1", bytes_total: 5000 },
    { snapshot_at: "t2", bytes_total: 6000 },
    { snapshot_at: "t3", bytes_total: 300 },
  ]);
  assert.equal(sumDeltas(s), 1000 + 300);
});
