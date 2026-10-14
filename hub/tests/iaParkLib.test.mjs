import test from "node:test";
import assert from "node:assert/strict";
import { byModel, activityTotals, allowedContainers, gestureParams, scoreTone } from "../src/iaParkLib.js";

test("#756 : évaluations par modèle (dernier et meilleur passage)", () => {
  const r = byModel([{ at: "2026-10-14", model: "qwen3:14b", base_url: "b", score: 0.7 }, { at: "2026-10-13", model: "qwen3:14b", base_url: "b", score: 0.9 },
    { at: "2026-10-12", model: "qwen3:8b", base_url: "b", score: 0.6 }]);
  assert.equal(r.length, 2); assert.equal(r[0].runs, 2); assert.equal(r[0].last.score, 0.7); assert.equal(r[0].best.score, 0.9);
  assert.equal(scoreTone(0.9), "good"); assert.equal(scoreTone(0.4), "critical"); assert.equal(scoreTone(null), "neutral");
});

test("#756 : activité et gestes encadrés", () => {
  const t = activityTotals([{ n: 2, errors: 1, ms_avg: 1000, tok_s_avg: 10 }, { n: 6, errors: 0, ms_avg: 3000, tok_s_avg: 20 }]);
  assert.deepEqual(t, { n: 8, errors: 1, ms_avg: 2500, tok_s_avg: 15, max: 6 });
  assert.equal(activityTotals([]).ms_avg, null);
  assert.deepEqual(allowedContainers([{ name: "open-webui" }, { name: "postgres" }], ["open-*"]).map((c) => c.name), ["open-webui"]);
  const cat = { write: ["service_restart", "docker_restart", "compose_update"] };
  assert.equal(gestureParams({ action: "journal" }, cat).error, "choisir le service");
  assert.deepEqual(gestureParams({ action: "journal", unit: "ollama", lines: "50" }, cat).params, { action: "journal", unit: "ollama", lines: 50 });
  assert.match(gestureParams({ action: "service_restart", unit: "ollama", reason: "x" }, cat).error, /motif/);
  const ok = gestureParams({ action: "service_restart", unit: "ollama", reason: " modèle bloqué " }, cat);
  assert.equal(ok.write, true); assert.equal(ok.params.reason, "modèle bloqué");
  assert.deepEqual(gestureParams({ action: "disk" }, cat).params, { action: "disk" });
});
