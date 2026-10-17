import test from "node:test";
import assert from "node:assert/strict";
import { allSteps, focusStep, progress, phaseProgress, controls, stepActions, parsePlan, fmtBytes, fmtRate, fmtDuration, solutionCommand, missingVars, statusLabel } from "../src/migrationLib.js";

const st = (id, status, o = {}) => ({ id, status, kind: "check_ssh", missing_vars: [], ...o });
const view = (steps, o = {}) => ({ plan: { name: "P", phases: [{ id: "A", title: "A", steps }] }, total: steps.length, done: steps.filter((s) => s.status === "fait").length, run: { state: "arrete", mode: "manuel" }, ...o });

test("étape montrée et progression", () => {
  const v = view([st("a1", "fait"), st("a2", "erreur"), st("a3", "a_faire", { next: true })], { next: "a3" });
  assert.equal(focusStep(v).id, "a2");
  assert.deepEqual(progress(v), { total: 3, done: 1, pct: 33 });
  assert.equal(phaseProgress(v.plan.phases[0]).tone, "critical");
  assert.equal(focusStep(view([st("a1", "en_cours"), st("a2", "erreur")])).id, "a1");
  assert.equal(allSteps(v)[0].phase, "A");
  assert.equal(statusLabel("en_pause"), "en pause");
});

test("boutons de pilotage", () => {
  let c = controls(view([st("a1", "a_faire", { next: true })], { next: "a1" }));
  assert.deepEqual(c, { start: true, next: true, pause: false, resume: false, stop: false });
  c = controls(view([st("a1", "en_cours")], { next: null }));
  assert.deepEqual(c, { start: false, next: false, pause: true, resume: false, stop: true });
  c = controls(view([st("a1", "en_pause")]));
  assert.equal(c.resume, true);
  c = controls(view([st("a1", "manuel", { kind: "manual" }), st("a2", "a_faire")], { next: "a1" }));
  assert.equal(c.next, false);   // étape à la main en attente de « Fait »
});

test("gestes par étape", () => {
  assert.deepEqual(stepActions(st("x", "erreur")), ["retry", "done", "skip", "reset"]);
  assert.deepEqual(stepActions(st("x", "fait")), ["reset"]);
  assert.deepEqual(stepActions(st("x", "en_cours")), []);
  assert.deepEqual(stepActions(st("x", "manuel", { kind: "manual" })), ["done", "skip"]);
});

test("plan, formats, solution, variables", () => {
  assert.match(parsePlan("{x").error, /JSON invalide/);
  assert.match(parsePlan("{}").error, /phases/);
  assert.equal(parsePlan('{"phases": []}').error, null);
  assert.equal(fmtBytes(1536), "1.5 Ko");
  assert.equal(fmtRate(106 * 1024 * 1024), "106 Mo/s");
  assert.equal(fmtDuration(3 * 3600 + 5 * 60), "3 h 05");
  assert.equal(fmtDuration(90000), "1 j 1 h");
  assert.equal(solutionCommand({ solution: { kind: "command", command: "ls" } }), "ls");
  assert.equal(solutionCommand({ solution: { kind: "retry" } }), "");
  assert.deepEqual(missingVars(view([st("a1", "a_faire", { missing_vars: ["PVE3"] }), st("a2", "fait", { missing_vars: ["X"] })])), ["PVE3"]);
});
