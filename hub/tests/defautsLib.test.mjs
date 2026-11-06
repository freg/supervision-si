// Tests #975 : bandeau des défauts majeurs.
import { test } from "node:test";
import assert from "node:assert/strict";
import { visibles, ignores, resume, nomFichier, defautsAffiches } from "../src/defautsLib.js";

const DS = [
  { id: 1, code: "historique-clients.enregistrement", statut: "ouvert", ignore: false, occurrences: 16, premiere: 1793900000, derniere: 1793950000 },
  { id: 2, code: "x", statut: "ouvert", ignore: true, occurrences: 1, premiere: 1793900000 },
  { id: 3, code: "y", statut: "resolu", ignore: false },
];

test("visibles / ignorés : seuls les défauts ouverts comptent", () => {
  assert.deepEqual(visibles(DS).map((d) => d.id), [1]);
  assert.deepEqual(ignores(DS).map((d) => d.id), [2]);
  assert.deepEqual(visibles(null), []);
});

test("résumé, nom de fichier, jeton interne absent", () => {
  assert.match(resume(DS[0]), /^16 fois depuis le .+, dernière .+/);
  assert.match(resume(DS[1]), /^le /);
  assert.equal(nomFichier(DS[0], new Date(2026, 10, 6, 9, 5).getTime()), "defaut-historique-clients.enregistrement-20261106-0905.txt");
  assert.deepEqual(defautsAffiches({ defauts: DS, jeton_interne: true }).map((d) => d.id), [1]);
  assert.equal(defautsAffiches({ defauts: DS, jeton_interne: false })[0].code, "notify.jeton-interne");
});

test("étiquette courte", async () => {
  const { etiquette } = await import("../src/defautsLib.js");
  assert.equal(etiquette({ titre: "Historique des clients Nebula : les relèves ne sont pas enregistrées" }), "Historique des clients Nebula");
  assert.equal(etiquette({ titre: "x".repeat(60) }).length, 40);
  assert.equal(etiquette({ code: "a.b" }), "a.b");
});

test("#977 : erreurs des agents -- ignorer pour la journée, lien vers l'onglet de l'objet", async () => {
  const L = await import("../src/defautsLib.js");
  const items = [{ cle: "sonde|probe-alert|wifi-probe", agent_id: "sonde", kind: "probe-alert" }, { cle: "nas|agent-offline|", agent_id: "nas", kind: "agent-offline" },
    { cle: "|fleet-blocked|", agent_id: null, kind: "fleet-blocked" }];
  assert.deepEqual(L.lienAgent(items[0]), { view: "si-agent", agent: "sonde", section: "plugins" });
  assert.deepEqual(L.lienAgent(items[2]), { view: "si-agent", tab: "events" });
  assert.equal(L.sectionDuGenre("command-block"), "historique");
  assert.equal(L.sectionDuGenre("inconnu"), "logs");
  let c = L.basculerIgnore({ vieux: "2026-11-05" }, items[0].cle, true, "2026-11-06");
  assert.deepEqual(c, { [items[0].cle]: "2026-11-06" });                     // la veille est oubliée
  assert.deepEqual(L.actifs(items, c, "2026-11-06").map((x) => x.agent_id), ["nas", null]);
  assert.equal(L.actifs(items, c, "2026-11-07").length, 3);                 // le lendemain : de nouveau à traiter
  c = L.basculerIgnore(c, items[0].cle, false, "2026-11-06");
  assert.deepEqual(c, {});
  assert.equal(L.aujourdhui(new Date(2026, 10, 6, 23, 59).getTime()), "2026-11-06");
});
