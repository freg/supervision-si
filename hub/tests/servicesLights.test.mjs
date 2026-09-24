import test from "node:test";
import assert from "node:assert/strict";
import { sortServices, filterServices, summarize, verdictText, uptimeText } from "../src/servicesLights.js";

const rows = [
  { service: "nebula-api", light: "green", kind: "api", status: "running", text: "HTTP 200 en 12 ms" },
  { service: "ged-api", light: "red", kind: "api", status: "exited", text: "conteneur exited" },
  { service: "hub", light: "orange", kind: "front", status: "running", text: "répond lentement" },
  { service: "nebula-postgres", light: "green", kind: "db", status: "running", text: "en marche" },
];

test("tri rouge → orange → vert puis nom", () => {
  assert.deepEqual(sortServices(rows).map((r) => r.service), ["ged-api", "hub", "nebula-api", "nebula-postgres"]);
});

test("filtre : début de mot d'abord, problèmes seulement", () => {
  assert.deepEqual(filterServices(rows, "neb").map((r) => r.service), ["nebula-api", "nebula-postgres"]);
  assert.deepEqual(filterServices(rows, "panne").map((r) => r.service), ["ged-api"]);
  assert.deepEqual(filterServices(rows, "", true).map((r) => r.service), ["ged-api", "hub"]);
});

test("résumé et verdict", () => {
  const s = summarize(rows);
  assert.equal(s.verdict, "red");
  assert.equal(verdictText(s), "1 en panne, 1 à surveiller sur 4");
  assert.equal(verdictText(summarize(rows.filter((r) => r.light === "green"))), "tout est en marche (2 services)");
  assert.equal(verdictText(summarize([])), "aucun service");
});

test("durée depuis le démarrage", () => {
  const now = Date.parse("2026-09-24T10:00:00Z");
  assert.equal(uptimeText("2026-09-24T09:59:30Z", now), "30 s");
  assert.equal(uptimeText("2026-09-24T08:30:00Z", now), "1 h 30 min");
  assert.equal(uptimeText("2026-09-22T09:00:00Z", now), "2 j 1 h");
  assert.equal(uptimeText("n'importe quoi", now), "");
});
