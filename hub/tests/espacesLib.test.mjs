// Tests #986 : espaces disques / données.
import { test } from "node:test";
import assert from "node:assert/strict";
import { taille, saturationTexte, penteTexte, filtrer, grouper, valeurs } from "../src/espacesLib.js";

const T = 1024 ** 4, G = 1024 ** 3;
const M = [
  { nom: "nas-grpi-1", type: "nas", niveau: "ok", taille: 21 * T, occupe: 7 * T, classement: { role: "NAS", lan: "bureau", hebergeur: "local" }, materiel: { disques: [{ modele: "ST12000VN0007" }] } },
  { nom: "super", type: "agent", niveau: "critique", taille: 100 * G, occupe: 96 * G, classement: { role: "serveur", lan: "bureau", hebergeur: "local" } },
  { nom: "ns3037858", type: "agent", niveau: "attention", taille: 2 * T, occupe: T, classement: { role: "hyperviseur", lan: "ovh", hebergeur: "OVH" } },
];

test("formats français", () => {
  assert.equal(taille(12 * T), "12,0 To");
  assert.equal(taille(0), "—");
  assert.equal(saturationTexte(10), "plein dans 10 j");
  assert.equal(saturationTexte(120), "plein dans 4 mois");
  assert.equal(saturationTexte(null), "");
  assert.equal(penteTexte(2 * G), "+2,0 Go/j");
  assert.equal(penteTexte(0), "stable");
});

test("filtre, regroupement, suggestions", () => {
  assert.deepEqual(filtrer(M, { niveau: "a-surveiller" }).map((m) => m.nom), ["super", "ns3037858"]);
  assert.deepEqual(filtrer(M, { q: "st12000" }).map((m) => m.nom), ["nas-grpi-1"]);
  const g = grouper(M, "lan");
  assert.deepEqual(g.map((x) => [x.valeur, x.machines.length, x.critique]), [["bureau", 2, 1], ["ovh", 1, 0]]);
  assert.equal(g[0].taille, 21 * T + 100 * G);
  assert.deepEqual(valeurs(M, "hebergeur"), ["local", "OVH"]);
});
