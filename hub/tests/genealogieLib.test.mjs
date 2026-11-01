import test from "node:test";
import assert from "node:assert/strict";
import { filtrer, parAnnee, lignee, cheminOrigine, valeurs, moisLisible, enfantsDe } from "../src/genealogieLib.js";

const N = [
  { id: "t", nom: "Transformer", org: "Google", date: "2017-06", types: ["architecture"], ouverture: "ouvert", parents: [] },
  { id: "l", nom: "LLaMA", org: "Meta", date: "2023-02", types: ["texte"], ouverture: "poids", parents: [{ id: "t", relation: "architecture" }] },
  { id: "a", nom: "Alpaca", org: "Stanford", date: "2023-03", types: ["texte"], ouverture: "poids", parents: [{ id: "l", relation: "affinage" }] },
  { id: "g", nom: "GPT-4", org: "OpenAI", date: "2023-03", types: ["texte", "vision"], ouverture: "ferme", parents: [{ id: "t", relation: "architecture" }] },
  { id: "hf:x/y", nom: "y", org: "x", date: "2026-09", types: ["texte"], ouverture: "ouvert", auto: true, parents: [{ id: "a", relation: "affinage" }] },
];

test("filtres", () => {
  assert.deepEqual(filtrer(N, { texte: "méta" }).map((n) => n.id), ["l"]);
  assert.deepEqual(filtrer(N, { type: "vision" }).map((n) => n.id), ["g"]);
  assert.deepEqual(filtrer(N, { ouverture: "poids" }).map((n) => n.id), ["l", "a"]);
  assert.equal(filtrer(N, { auto: false }).length, 4);
  assert.deepEqual(filtrer(N, { texte: "2023 stanford" }).map((n) => n.id), ["a"]);
  assert.deepEqual(valeurs(N, "types"), ["architecture", "texte", "vision"]);
});

test("années et mois", () => {
  assert.deepEqual(parAnnee(N).map(([a, l]) => [a, l.map((n) => n.id)]), [["2017", ["t"]], ["2023", ["l", "a", "g"]], ["2026", ["hf:x/y"]]]);
  assert.equal(moisLisible("2023-03"), "mars 2023");
  assert.equal(moisLisible(""), "?");
});

test("lignée et chemin vers l'origine", () => {
  const lg = lignee(N, "a");
  assert.deepEqual(lg.ascendants, [{ id: "l", distance: 1 }, { id: "t", distance: 2 }]);
  assert.deepEqual(lg.descendants, [{ id: "hf:x/y", distance: 1 }]);
  assert.equal(lignee(N, "t").descendants.length, 4);
  assert.deepEqual(cheminOrigine(N, "hf:x/y"), ["hf:x/y", "a", "l", "t"]);
  assert.deepEqual(cheminOrigine(N, "t"), ["t"]);
  assert.deepEqual(enfantsDe(N).t.map((e) => e.id), ["l", "g"]);
});
