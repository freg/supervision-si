import test from "node:test";
import assert from "node:assert/strict";
import { blocker, nextStep, prevStep, cursor, summary, launchesOnNext } from "../src/repaLib.js";

test("#761 : navigation de l'assistant de rapatriement", () => {
  const c = { step: "inventaire", guests: [{ vmid: 102 }, { vmid: 109 }] };
  assert.match(blocker(c), /décider/);
  c.guests[0].decision = "rapatrier"; assert.equal(blocker(c), null);
  assert.match(blocker({ step: "preparation", checks: [{ label: "place libre", ok: false }] }), /place libre/);
  assert.equal(blocker({ step: "preparation", checks: [{ ok: true }] }), null);
  assert.match(blocker({ step: "rapatriement", guests: [{ decision: "rapatrier", phase: "export" }] }), /en cours/);
  assert.equal(blocker({ step: "rapatriement", guests: [{ decision: "rapatrier", phase: "validate" }] }), null);
  assert.match(blocker({ step: "verification", guests: [{ decision: "rapatrier", phase: "validate" }] }), /valider/);
  assert.equal(blocker({ step: "nettoyage", guests: [{ decision: "rapatrier", phase: "done" }, { decision: "garder" }] }), null);
  assert.equal(nextStep("inventaire"), "preparation"); assert.equal(prevStep("inventaire"), "inventaire"); assert.equal(nextStep("bilan"), "bilan");
  assert.equal(launchesOnNext("preparation"), true);
});

test("#761 : curseur du synoptique et bilan", () => {
  assert.deepEqual(cursor({ step: "rapatriement", progress: { percent: 47.5 } }), { index: 2, x: 2.5 / 6, fill: 0.475 });
  const s = summary({ guests: [{ decision: "rapatrier", phase: "done", size: 400e9 }, { decision: "rapatrier", phase: "diff" }, { decision: "garder" }, { decision: "supprimer" }] });
  assert.deepEqual(s, { rapatrier: 2, garder: 1, supprimer: 1, done: 1, freed: 400e9, failed: 1 });
});
