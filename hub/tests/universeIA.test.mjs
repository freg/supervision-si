import test from "node:test";
import assert from "node:assert/strict";
import { doitInterroger, candidats, ajouts, apprendre, lireAppris, ecrireAppris, fusionnerSynonymes, deviner, idEntree } from "../src/universeIA.js";

const E = [
  { kind: "view", view: "accounts", label: "Comptes et groupes", themes: ["Sécurité & accès"], aliases: ["droits"] },
  { kind: "view", view: "flux-editeurs", label: "Flux éditeurs", themes: ["Réseau"] },
  { kind: "front", front: "vault", label: "Coffre-fort" },
  { kind: "action", id: "action:aide", label: "Aide" },
];

test("quand interroger", () => {
  assert.equal(doitInterroger("dr", 0), false);
  assert.equal(doitInterroger("droits", 0), true);
  assert.equal(doitInterroger("droits", 2), true);
  assert.equal(doitInterroger("droits", 3), false);
  assert.equal(doitInterroger("192.0.2.1", 0, true), false);
});

test("candidats et ajouts", () => {
  assert.deepEqual(candidats(E).map((c) => c.id), ["view:accounts", "view:flux-editeurs", "front:vault", "action:aide"]);
  assert.equal(idEntree(null), "");
  const a = ajouts([{ id: "view:accounts", raison: "r", source: "modele" }, { id: "view:inconnue" }, { id: "front:vault" }, { id: "front:vault" }], E, [E[2]]);
  assert.deepEqual(a.map((x) => x.id), ["view:accounts"]);
  assert.equal(a[0].leaf.label, "Comptes et groupes");
});

test("apprentissage des synonymes", () => {
  let ap = apprendre({}, "  Droits Utilisateurs ", "view:accounts");
  assert.deepEqual(ap, { "view:accounts": ["droits utilisateurs"] });
  assert.equal(apprendre(ap, "droits utilisateurs", "view:accounts"), ap);
  assert.deepEqual(apprendre(ap, "x", "view:accounts"), ap);
  assert.deepEqual(apprendre(ap, "abcd", "javascript:x"), ap);
  const mem = { v: null, getItem() { return this.v; }, setItem(k, v) { this.v = v; } };
  ecrireAppris(ap, mem);
  assert.deepEqual(lireAppris(mem), ap);
  assert.deepEqual(lireAppris({ getItem() { return "[1]"; } }), {});
  assert.deepEqual(lireAppris({ getItem() { throw new Error("bloqué"); } }), {});
  assert.deepEqual(fusionnerSynonymes({ "view:accounts": ["droits"] }, ap)["view:accounts"], ["droits", "droits utilisateurs"]);
});

test("deviner : catalogue puis modèle, silence sur erreur", async () => {
  const appels = [];
  const rep = (sugg) => ({ ok: true, json: async () => ({ suggestions: sugg }) });
  let etats = [];
  await deviner("/assistant", "ouvrir port", [], (e) => etats.push(e), { fetchFn: async (u, o) => { appels.push(JSON.parse(o.body).llm); return appels.length === 1 ? rep([]) : rep([{ id: "view:flux-editeurs" }]); } });
  assert.deepEqual(appels, [false, true]);
  assert.deepEqual(etats.map((e) => e.phase), ["recherche", "inference", "fini"]);
  assert.equal(etats.at(-1).suggestions[0].id, "view:flux-editeurs");
  etats = [];
  await deviner("/assistant/", "droits", [], (e) => etats.push(e), { fetchFn: async (u) => { assert.equal(u, "/assistant/hub/devine"); return rep([{ id: "view:accounts" }]); } });
  assert.deepEqual(etats.map((e) => e.phase), ["recherche", "fini"]);
  etats = [];
  await deviner("/a", "q", [], (e) => etats.push(e), { fetchFn: async () => ({ ok: false, status: 502 }) });
  assert.deepEqual(etats.at(-1), { phase: "fini", suggestions: [] });
  etats = [];
  await deviner("/a", "q", [], (e) => etats.push(e), { fetchFn: async () => rep([]), annule: () => true });
  assert.deepEqual(etats.map((e) => e.phase), ["recherche"]);
});
