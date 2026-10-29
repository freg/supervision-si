import test from "node:test";
import assert from "node:assert/strict";
import { echantillons, serieDisque, dernierEtat, estFini } from "../src/chargeLive.js";

const ECH = [
  { phase: "début", epreuves: ["disque"], t: 100 },
  { phase: "disque", sous: "écriture", mo_s: 300, pct: 2, t: 100 },
  { phase: "disque", sous: "écriture", mo_s: 40, pct: 52, t: 101 },
  { phase: "disque", sous: "lecture", mo_s: 500, pct: 50, t: 103 },
  { phase: "fini", verdict: "aucun défaut reproduit", t: 104 },
];

test("echantillons : accepte {echantillons:[…]} et liste directe", () => {
  assert.equal(echantillons({ echantillons: ECH }).length, 5);
  assert.equal(echantillons(ECH).length, 5);
  assert.deepEqual(echantillons(null), []);
});

test("serieDisque : points disque, temps relatif, max par reduce", () => {
  const s = serieDisque(ECH);
  assert.equal(s.points.length, 3);
  assert.equal(s.points[0].t, 0);          // relatif au 1er échantillon disque
  assert.equal(s.points[2].t, 3);
  assert.equal(s.moSMax, 500);
  assert.equal(s.tMax, 3);
});

test("dernierEtat : dernier échantillon utile (hors début/fini)", () => {
  assert.equal(dernierEtat(ECH).sous, "lecture");
});

test("estFini : marqueur de fin présent", () => {
  assert.equal(estFini(ECH), true);
  assert.equal(estFini(ECH.slice(0, 3)), false);
});
