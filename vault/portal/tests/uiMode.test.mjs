// Mode d'affichage du coffre-fort (livraison #501) : défaut « complet »,
// choix mémorisé par navigateur, valeur inconnue ignorée, stockage absent toléré.
import test from "node:test";
import assert from "node:assert/strict";
import { loadUiMode, saveUiMode, UI_MODE_KEY } from "../src/uiMode.js";

const mem = () => { const m = new Map(); return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, v) }; };

test("défaut complet, défaut d'installation respecté, valeur inconnue ignorée", () => {
  assert.equal(loadUiMode("complet", mem()), "complet");
  assert.equal(loadUiMode("simple", mem()), "simple");
  assert.equal(loadUiMode("fantaisie", mem()), "complet");
  const st = mem(); st.setItem(UI_MODE_KEY, "n'importe quoi");
  assert.equal(loadUiMode("simple", st), "simple");
});

test("choix mémorisé prime sur le défaut ; stockage absent ou cassé toléré", () => {
  const st = mem(); saveUiMode("simple", st);
  assert.equal(loadUiMode("complet", st), "simple");
  assert.equal(loadUiMode("simple", null), "simple");
  const broken = { getItem: () => { throw new Error("x"); }, setItem: () => { throw new Error("x"); } };
  assert.equal(loadUiMode("complet", broken), "complet");
  assert.doesNotThrow(() => saveUiMode("simple", broken));
});
