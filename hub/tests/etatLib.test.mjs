import test from "node:test";
import assert from "node:assert/strict";
import { filtrer, depuis, jour, points, maxTendance, nom } from "../src/etatLib.js";

test("filtrer et nom", () => {
  const L = [{ key: "pve-2/100", name: "THD85", node: "pve-2", type: "CT", niveau: "urgent", roles: ["messagerie"], os: { nom: "Debian 9" } },
    { key: "node:pve-2", name: "pve-2", node: "pve-2", type: "nœud", niveau: "ok", libelle: "Hyperviseur" }];
  assert.equal(filtrer(L, { texte: "messagerie" }).length, 1);
  assert.equal(filtrer(L, { type: "nœud" })[0].key, "node:pve-2");
  assert.equal(filtrer(L, { texte: "hyperviseur" }).length, 1);
  assert.equal(nom(L[0]), "THD85 (pve-2/100)");
  assert.equal(nom(L[1]), "Hyperviseur (node:pve-2)");
});

test("depuis, jour", () => {
  assert.equal(depuis(null), "—");
  assert.equal(depuis(3), "3 j");
  assert.equal(depuis(400), "13 mois");
  assert.equal(depuis(1000), "3 ans");
  assert.equal(jour("2026-08-31"), "31/08/2026");
});

test("points de tendance", () => {
  const t = [{ urgent: 2, "à planifier": 4 }, { urgent: 0, "à planifier": 1 }];
  assert.equal(maxTendance(t, ["urgent", "à planifier"]), 4);
  assert.equal(points(t, "urgent", 100, 22, 4), "0.0,11.0 100.0,21.0");
  assert.equal(points([t[0]], "urgent"), "");
});
