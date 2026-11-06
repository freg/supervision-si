// #988 : nœuds IA -- accès par groupe, filtrage des tuiles, chemins, nœud retenu, cookie du jeton.
import test from "node:test";
import assert from "node:assert/strict";
import { accesIa, filtrerVuesIa, cheminNoeud, noeudRetenu, pageDeVue, cookieIa, VUES_IA } from "../src/iaNoeudsLib.js";

test("accès : groupe ia, administrateurs ou admin_hub (avec ou sans /)", () => {
  assert.equal(accesIa(["/ia"]), true);
  assert.equal(accesIa(["administrateurs"]), true);
  assert.equal(accesIa(["admin_hub"]), true);
  assert.equal(accesIa(["numeria", "techniciens"]), false);
  assert.equal(accesIa(undefined), false);
});

test("tuiles IA retirées sans le droit, conservées sinon", () => {
  const vues = new Set(["nebula", ...VUES_IA]);
  assert.deepEqual([...filtrerVuesIa(vues, ["numeria"])], ["nebula"]);
  assert.equal(filtrerVuesIa(vues, ["ia"]), vues);
});

test("chemins des pages d'un nœud", () => {
  assert.equal(cheminNoeud("prodia"), "/ia/prodia/");
  assert.equal(cheminNoeud("preprodia", "atelier"), "/ia/preprodia/atelier");
  assert.equal(cheminNoeud("../x", "atelier"), null);
  assert.equal(cheminNoeud("", ""), null);
});

test("nœud retenu et page d'une vue", () => {
  assert.equal(noeudRetenu(["prodia", "preprodia"], "preprodia"), "preprodia");
  assert.equal(noeudRetenu(["prodia"], "disparu"), "prodia");
  assert.equal(noeudRetenu([], "x"), null);
  assert.equal(pageDeVue("hermes"), "");
  assert.equal(pageDeVue("ia-atelier"), "atelier");
  assert.equal(pageDeVue("ia-apprentissage"), "apprentissage");
  assert.equal(pageDeVue("autre"), "");
});

test("cookie du jeton limité à /ia/, effacé quand le jeton est vide", () => {
  assert.equal(cookieIa("abc"), "si_ia_jeton=abc; Path=/ia/; SameSite=Strict; Secure");
  assert.equal(cookieIa("abc", false), "si_ia_jeton=abc; Path=/ia/; SameSite=Strict");
  assert.match(cookieIa(""), /Max-Age=0$/);
});
