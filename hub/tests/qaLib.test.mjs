import test from "node:test";
import assert from "node:assert/strict";
import { validateSteps, loginFromProbe, campaignSummary, runBadge, fieldsFor, emptyStep } from "../src/qaLib.js";
const catalog = [{ id: "goto", fields: ["value"] }, { id: "click", fields: ["selector"] }, { id: "fill", fields: ["selector", "value"] }, { id: "expect_text", fields: ["value"] }, { id: "wait", fields: ["value"] }];

test("validateSteps : mêmes règles que l'API", () => {
  assert.equal(validateSteps([], catalog), "Ajoutez au moins une étape");
  assert.equal(validateSteps([{ action: "click", selector: "" }], catalog), "Étape 1 : sélecteur manquant");
  assert.equal(validateSteps([{ action: "goto", value: "/" }, { action: "fill", selector: "#a", value: "" }], catalog), "Étape 2 : valeur manquante");
  assert.equal(validateSteps([{ action: "expect_text", value: "" }], catalog), "");     // texte vide = page chargée, toléré
  assert.equal(validateSteps([{ action: "wait", value: "abc" }], catalog), "Étape 1 : durée en millisecondes");
  assert.equal(validateSteps([{ action: "teleport" }], catalog), "Étape 1 : action inconnue");
  assert.deepEqual(fieldsFor("fill", catalog), ["selector", "value"]); assert.equal(emptyStep().action, "goto");
});

test("loginFromProbe devine les étapes de connexion", () => {
  const probe = { forms: [{ fields: [{ tag: "input", type: "text", name: "login", id: "login" }, { tag: "input", type: "password", name: "password", id: "" }, { tag: "input", type: "image", name: "submit", id: "submit" }] }] };
  const s = loginFromProbe(probe, "/login");
  assert.deepEqual(s.map((x) => [x.action, x.selector]), [["goto", ""], ["fill", "#login"], ["fill", '[name="password"]'], ["click", "#submit"]]);
  assert.equal(s[0].value, "/login");
  assert.equal(loginFromProbe({ forms: [{ fields: [{ tag: "input", type: "text" }] }] }), null);
  const noSubmit = loginFromProbe({ forms: [{ fields: [{ tag: "input", type: "password", id: "p" }] }] }, "/");
  assert.deepEqual(noSubmit[noSubmit.length - 1], { action: "press", selector: "#p", value: "Enter", note: "valider" });
});

test("campaignSummary et runBadge", () => {
  assert.deepEqual(campaignSummary([{ status: "ok" }, { status: "ko" }, { status: "ok" }]), { total: 3, passed: 2, failed: 1, ratio: 67 });
  assert.deepEqual(campaignSummary([]), { total: 0, passed: 0, failed: 0, ratio: 0 });
  assert.equal(runBadge("ko"), "✘ échec"); assert.equal(runBadge("x"), "—");
});
