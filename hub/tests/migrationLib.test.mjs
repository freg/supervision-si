import test from "node:test";
import assert from "node:assert/strict";
import { allSteps, focusStep, progress, phaseProgress, controls, stepActions, parsePlan, fmtBytes, fmtProgress, fmtRate, fmtDuration, solutionCommand, missingVars, statusLabel } from "../src/migrationLib.js";

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

test("avancement restant / transféré / total", () => {
  const T = 1024 ** 4;
  assert.equal(fmtProgress({ size: 2.8 * T, total: 7.9 * T }), "5.1 To / 2.8 To / 7.9 To");
  assert.equal(fmtProgress({ size: 2.8 * T }), "2.8 To");
  assert.equal(fmtProgress({ size: 2.8 * T, scope: "volume" }), "≈ 2.8 To");
  assert.equal(fmtProgress({ size: 9 * T, total: 8 * T }), "0 o / 9.0 To / 8.0 To");
  assert.equal(fmtProgress({}), "");
});

test("onglets : Migration et MX, vue restreinte (#784)", async () => {
  const { tabsOf, tabView, controls, focusStep } = await import("../src/migrationLib.js");
  const view = { run: { state: "en_cours" }, onglets: ["", "MX"], nexts: { "": "a2", MX: "m1" }, plan: { phases: [
    { id: "A", onglet: "", steps: [{ id: "a1", status: "fait" }, { id: "a2", status: "a_faire", next: true }] },
    { id: "M", onglet: "MX", steps: [{ id: "m1", kind: "manual", status: "a_faire", next: true }, { id: "m2", kind: "manual", status: "erreur" }] }] } };
  const t = tabsOf(view);
  assert.deepEqual(t.map((x) => [x.id, x.label, x.done, x.total, x.bad]), [["", "Migration", 1, 2, false], ["MX", "MX", 0, 2, true]]);
  const mx = tabView(view, "MX");
  assert.equal(mx.next, "m1"); assert.equal(mx.total, 2); assert.deepEqual(mx.plan.phases.map((p) => p.id), ["M"]);
  assert.equal(focusStep(mx).id, "m2");                       // l'erreur de l'onglet passe devant
  assert.equal(controls(mx).next, true);
  assert.equal(tabView(view, "").next, "a2");
  assert.deepEqual(tabsOf({ plan: { phases: [{ id: "A", steps: [] }] } }).map((x) => x.label), ["Migration"]);
});
