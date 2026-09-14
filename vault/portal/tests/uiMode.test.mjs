// Mode d'affichage du coffre-fort (livraison #501, défaut inversé #502, mode tableur #507) :
// défaut « tableur », choix mémorisé par navigateur, valeur inconnue ignorée, stockage absent toléré,
// cycle des trois modes, modes « dépouillés ».
import test from "node:test";
import assert from "node:assert/strict";
import { loadUiMode, saveUiMode, nextUiMode, isPlainMode, UI_MODE_KEY, UI_MODES, UI_MODE_LABELS, UI_MODE_TITLES } from "../src/uiMode.js";

const mem = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v) }; };

test("défaut tableur, défaut d'installation respecté, valeur inconnue ignorée", () => {
  assert.equal(loadUiMode(undefined, mem()), "tableur");
  assert.equal(loadUiMode("complet", mem()), "complet");
  assert.equal(loadUiMode("simple", mem()), "simple");
  assert.equal(loadUiMode("tableur", mem()), "tableur");
  assert.equal(loadUiMode("fantaisie", mem()), "tableur");
  const st = mem(); st.setItem(UI_MODE_KEY, "n'importe quoi");
  assert.equal(loadUiMode("simple", st), "simple");
});

test("choix mémorisé prime sur le défaut ; stockage absent ou cassé toléré", () => {
  const st = mem(); saveUiMode("simple", st);
  assert.equal(loadUiMode("complet", st), "simple");
  assert.equal(loadUiMode("simple", null), "simple");
  const broken = { getItem: () => { throw new Error("x"); }, setItem: () => { throw new Error("x"); } };
  assert.equal(loadUiMode("complet", broken), "complet");
  assert.equal(loadUiMode("fantaisie", broken), "tableur");
  assert.doesNotThrow(() => saveUiMode("simple", broken));
});

test("cycle des modes et modes dépouillés", () => {
  assert.equal(nextUiMode("tableur"), "simple");
  assert.equal(nextUiMode("simple"), "complet");
  assert.equal(nextUiMode("complet"), "tableur");
  assert.equal(nextUiMode("inconnu"), "tableur");
  assert.ok(isPlainMode("simple") && isPlainMode("tableur") && !isPlainMode("complet"));
  for (const m of UI_MODES) { assert.ok(UI_MODE_LABELS[m] && UI_MODE_TITLES[m], m); }
});
