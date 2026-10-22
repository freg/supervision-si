import test from "node:test";
import assert from "node:assert/strict";
import { commandeEnCours, finsCommandes, ONGLET_RESULTAT } from "../src/commandesLib.js";

test("#833 commande en cours et fin suivie", () => {
  const cmds = [{ id: 7, agent_id: "a", status: "pending", params: { action: "installer", moteur: "nomad" } },
    { id: 6, agent_id: "b", status: "pending", params: { action: "installer", moteur: "nomad" } },
    { id: 5, agent_id: "a", status: "done", params: { action: "installer", moteur: "k3s" } }];
  assert.equal(commandeEnCours(cmds, "a", { action: "installer", moteur: "nomad" }).id, 7);
  assert.equal(commandeEnCours(cmds, "a", { action: "installer", moteur: "k3s" }), null);
  assert.equal(commandeEnCours(cmds, null, { action: "installer", moteur: "nomad", nom: null }).id, 7);
  const suivis = new Set([7]), vus = {};
  assert.deepEqual(finsCommandes(cmds, suivis, vus), []);
  assert.deepEqual(finsCommandes([{ ...cmds[0], status: "done" }], suivis, vus).map((c) => c.id), [7]);
  assert.equal(suivis.has(7), false);
  assert.equal(ONGLET_RESULTAT.deployer, "charges");
});
