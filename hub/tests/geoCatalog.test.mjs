import test from "node:test";
import assert from "node:assert/strict";
import { confidenceTone, filterPositions, sortPositions, summarize, orderedRefs, mapPoints, validCoords, fmtCoord } from "../src/geoCatalog.js";

const ROWS = [
  { id: 1, label: "Batiment 5", key: "geolocation:Batiment 5", status: "auto", confidence: 92, lat: 45.77, lon: 4.85, refs: [{ source: "ban", precision: "poi", label: "Batiment 5", lat: 45.77, lon: 4.85, score: 0.9 }, { source: "geolocations", precision: "stored", label: "saisie", lat: 45.78, lon: 4.86 }], links: [{ label: "UPS-Batiment-5" }] },
  { id: 2, label: "Parc", key: "geolocation:Parc", status: "auto", confidence: 0, lat: null, lon: null, refs: [], links: [] },
  { id: 3, label: "Agence 17300", key: "geolocation:Agence 17300", status: "corrected", confidence: 100, lat: 45.95, lon: -0.97, refs: [{ source: "human", precision: "manual", label: "décision", lat: 45.95, lon: -0.97 }, { source: "commune", precision: "commune", label: "Rochefort", lat: 45.94, lon: -0.96 }, { source: "osm", precision: "osm", label: "loin", lat: 48.8, lon: 2.3 }], links: [] },
  { id: 4, label: "Annexe", key: "geolocation:Annexe", status: "auto", confidence: 55, lat: 47, lon: 1, refs: [], links: [] },
];

test("tons, filtres, tri, synthèse", () => {
  assert.deepEqual([confidenceTone(95), confidenceTone(60), confidenceTone(10), confidenceTone(null)], ["good", "warn", "bad", "neutral"]);
  assert.deepEqual(filterPositions(ROWS, { view: "todo" }).map((p) => p.id), [2, 4], "automatiques peu sûres ou sans position");
  assert.deepEqual(filterPositions(ROWS, { view: "decided" }).map((p) => p.id), [3]);
  assert.deepEqual(filterPositions(ROWS, { view: "unpositioned" }).map((p) => p.id), [2]);
  assert.deepEqual(filterPositions(ROWS, { view: "all", q: "ups-bati" }).map((p) => p.id), [1], "recherche dans les objets liés");
  assert.deepEqual(sortPositions(ROWS).map((p) => p.id), [2, 4, 1, 3]);
  assert.deepEqual(summarize(ROWS), { total: 4, todo: 2, auto: 3, decided: 1, unpositioned: 1, links: 1 });
});

test("références ordonnées, points de carte, coordonnées", () => {
  assert.deepEqual(orderedRefs(ROWS[2].refs).map((r) => r.source), ["human", "osm", "commune"]);
  assert.deepEqual(orderedRefs([{ source: "ban", label: "x", precision: "poi" }, { source: "ban", label: "x", precision: "poi" }]).length, 1, "dédoublonnées");
  const pts = mapPoints(ROWS[2]);
  assert.deepEqual(pts.map((p) => p.kind), ["position", "human", "commune"], "la référence aberrante à 300 km est écartée de l'emprise");
  assert.equal(mapPoints(ROWS[1]).length, 0);
  assert.equal(validCoords("46.5", "0.3"), true);
  assert.equal(validCoords("abc", 0), false);
  assert.equal(validCoords(91, 0), false);
  assert.equal(fmtCoord(46.123456789), "46.12346");
  assert.equal(fmtCoord(null), "—");
});
