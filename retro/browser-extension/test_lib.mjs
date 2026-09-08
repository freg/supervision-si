// node --test retro/browser-extension/test_lib.mjs -- fonctions pures de l'extension (#441)
import test from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
const L = createRequire(import.meta.url)("./lib.js");

test("périmètre de l'application", () => {
  assert.equal(L.inScope("https://gestion.exemple.fr/clients", ["https://gestion.exemple.fr"]), true);
  assert.equal(L.inScope("https://gestion.exemple.fr.evil.com/x", ["https://gestion.exemple.fr"]), false);
  assert.equal(L.inScope("http://10.0.0.5/appli/client/4", ["http://10.0.0.5/appli/"]), true);
  assert.equal(L.inScope("http://10.0.0.5/autre", ["http://10.0.0.5/appli"]), false);
  assert.equal(L.inScope("about:blank", []), false);
  assert.equal(L.inScope("https://n-importe.fr/", []), true, "sans périmètre : tout (déconseillé, signalé dans le popup)");
});

test("sélecteur, valeurs de champ, clés de formulaire", () => {
  const mk = (tag, extra) => Object.assign({ tagName: tag, getAttribute: (k) => (extra && extra.attrs || {})[k] || null, parentElement: null, children: [] }, extra || {});
  const body = mk("BODY");
  const table = mk("TABLE", { parentElement: body }); body.children = [table];
  const tr1 = mk("TR", { parentElement: table }), tr2 = mk("TR", { parentElement: table }); table.children = [tr1, tr2];
  const a = mk("A", { parentElement: tr2 }); tr2.children = [a];
  assert.equal(L.selectorFor(a), "table > tr:nth-child(2) > a");
  assert.equal(L.selectorFor(mk("INPUT", { id: "email" })), "#email");
  assert.equal(L.selectorFor(mk("INPUT", { attrs: { name: "nom" } })), "input[name=\"nom\"]");
  assert.deepEqual(L.fieldValue({ type: "password", value: "secret" }, true), { length: 6, value: null });
  assert.deepEqual(L.fieldValue({ type: "text", value: "Dupont" }, false), { length: 6, value: null });
  assert.deepEqual(L.fieldValue({ type: "text", value: "Dupont" }, true), { length: 6, value: "Dupont" });
  assert.deepEqual(L.fieldValue({ type: "checkbox", value: "1", checked: true }, true), { length: null, value: "1" });
  assert.deepEqual(L.formKeys({ formData: { nom: ["x"], email: ["y"] } }), ["nom", "email"]);
  assert.deepEqual(L.formKeys(null), []);
});

test("description d'un formulaire (jamais les valeurs)", () => {
  const el = (name, type, extra) => Object.assign({ name, type, value: "valeur", labels: [], required: false }, extra || {});
  const form = { elements: [el("nom", "text", { labels: [{ textContent: " Nom " }] }), el("pwd", "password"), el("ok", "submit"), el("nom", "text")],
    getAttribute: (k) => ({ action: "/client/42/save", method: "POST" })[k] || null, id: "f1" };
  const d = L.describeForm(form);
  assert.equal(d.action, "/client/42/save"); assert.equal(d.method, "post");
  assert.deepEqual(d.fields.map((f) => [f.name, f.type, f.label]), [["nom", "text", "Nom"], ["pwd", "password", null]]);
  assert.equal(JSON.stringify(d).includes("valeur"), false);
});
