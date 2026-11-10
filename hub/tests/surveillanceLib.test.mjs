import { test } from "node:test";
import assert from "node:assert/strict";
import { texteRepere, aTraiter, etatElement, parListe, raccordement, LOT } from "../src/surveillanceLib.js";

const R = { id: 1, liste: "tablettes", element_id: 3, libelle: "T03", mac: "6e:11:22:33:44:55", statut: "discordant", score: 60,
  premier: 1791000000, dernier: 1791003600, client: { name: "DESKTOP-1", ip: "192.0.2.5", device: "borne-atelier", port: "LAN2", vlan: "20" },
  preuves: [{ element: "MAC", poids: 60, texte: "MAC déclarée" }], discordances: [{ force: "forte", texte: "système Windows inattendu" }] };

test("texte d'un repère : preuves pondérées, discordances, consigne", () => {
  const t = texteRepere(R);
  assert.match(t, /\+60 {2}MAC : MAC déclarée/);
  assert.match(t, /\[forte\] système Windows inattendu/);
  assert.match(t, /Raccordement : borne \/ commutateur borne-atelier, port LAN2, VLAN 20/);
  assert.match(t, /Confirmer = c'est bien l'élément/);
  assert.match(texteRepere({ ...R, element_id: LOT, discordances: [] }), /à attribuer/);
});

test("à traiter : discordances d'abord, décisions exclues", () => {
  const l = aTraiter([{ id: 1, statut: "probable", dernier: 5 }, { id: 2, statut: "lot", dernier: 1 }, { id: 3, statut: "discordant", dernier: 1 },
    { id: 4, statut: "discordant", decision: "rejete" }, { id: 5, statut: "reconnu" }]);
  assert.deepEqual(l.map((r) => r.id), [3, 2, 1]);
});

test("état d'un élément et regroupement", () => {
  assert.equal(etatElement({}).texte, "pas encore repéré");
  assert.match(etatElement({ dernier_repere: { statut: "reconnu", decision: "confirme", dernier: 1791000000 } }).texte, /^reconnu \(confirmé\) — /);
  assert.deepEqual(Object.keys(parListe([{ liste: "a" }, { liste: "b" }, { liste: "a" }])), ["a", "b"]);
  assert.equal(raccordement({}), "");
});
