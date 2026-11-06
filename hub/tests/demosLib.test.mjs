import test from "node:test";
import assert from "node:assert/strict";
import { demandeTerminal, optionsTerminaux, valeursTerminal } from "../src/demosLib.js";

test("parcours qui demandent un terminal", () => {
  assert.equal(demandeTerminal({ terminal: "x", nom_reseau: "y" }), true);
  assert.equal(demandeTerminal({ nom_reseau: "y" }), true);
  assert.equal(demandeTerminal({ site: "x" }), false);
  assert.equal(demandeTerminal(undefined), false);
});

test("options : nom réseau vu par Nebula, sinon tirets ; tri naturel, doublons et vides écartés", () => {
  const o = optionsTerminaux([
    { nom: "E11 AmpIm" }, { nom: "E2 LabCo", nebula: { nom: "tab-e2" } }, { nom: "" }, { nom: "E11 AmpIm" }, null,
    { nom: "imprimante", nebula: { nom: "imprimante" } },
  ]);
  assert.deepEqual(o.map((x) => [x.terminal, x.nom_reseau, x.libelle]), [
    ["E2 LabCo", "tab-e2", "E2 LabCo (tab-e2)"], ["E11 AmpIm", "E11-AmpIm", "E11 AmpIm (E11-AmpIm)"], ["imprimante", "imprimante", "imprimante"]]);
  assert.deepEqual(optionsTerminaux(null), []);
});

test("valeurs posées : seulement les variables déclarées", () => {
  const opt = { terminal: "E11 AmpIm", nom_reseau: "E11-AmpIm" };
  assert.deepEqual(valeursTerminal(opt, { terminal: "", nom_reseau: "" }), opt);
  assert.deepEqual(valeursTerminal(opt, { nom_reseau: "" }), { nom_reseau: "E11-AmpIm" });
  assert.deepEqual(valeursTerminal(null, { terminal: "" }), {});
});
