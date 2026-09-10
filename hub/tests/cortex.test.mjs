import test from "node:test";
import assert from "node:assert/strict";
import { confidenceWord, pct, incidentLine, splitHypotheses, collectHealth, principleText, eventsBySource } from "../src/cortex.js";

test("confiance en mots", () => {
  assert.deepEqual(confidenceWord(0.9), { word: "forte", tone: "good" });
  assert.equal(confidenceWord(0.7).word, "probable");
  assert.equal(confidenceWord(0.45).word, "faible");
  assert.equal(confidenceWord(0.1).word, "très faible");
  assert.equal(pct(0.754), "75 %");
});

test("incident, hypothèses, collecte, principes", () => {
  assert.equal(incidentLine({ entities: ["a", "b"], events: ["x"], weak: true, sources: ["ups", "si-agent"] }), "2 entités, 1 événement · regroupement faible · ups, si-agent");
  const s = splitHypotheses([{ principle: "severity-max" }, { principle: "upstream-first", claim: "c" }, { principle: "site-cluster" }]);
  assert.equal(s.cause.principle, "upstream-first"); assert.equal(s.others.length, 2);
  assert.equal(collectHealth(null).tone, "warn");
  const h = collectHealth({ at: "t", report: { "si-agent": { ok: true }, ups: { ok: false, error: "refus" } } });
  assert.equal(h.tone, "warn"); assert.deepEqual(h.ok, ["si-agent"]); assert.deepEqual(h.failed, ["ups (refus)"]);
  assert.match(principleText({ base: 0.75, measured: null, applied: 3 }), /base 75 %.*3 application/);
  assert.match(principleText({ base: 0.75, measured: 0.6, applied: 9, confirmed: 2, rejected: 4 }), /mesurée 60 %.*2 confirmée.*4 rejetée/);
  assert.deepEqual(eventsBySource([{ source: "a" }, { source: "b" }, { source: "a" }]), [["a", 2], ["b", 1]]);
});
