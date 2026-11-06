// Tests #974 : calendrier des relèves (diodes).
import { test } from "node:test";
import assert from "node:assert/strict";
import { grilleReleves, bilan, texteNouveautes, sommeN, cleJour } from "../src/relevesLib.js";

const at = (j, h, m = 10) => Math.floor(new Date(2026, 10, j, h, m).getTime() / 1000);
const NOW = new Date(2026, 10, 6, 9, 30).getTime();

test("une diode par heure, jour le plus récent en premier, heures à venir marquées", () => {
  const g = grilleReleves([
    { id: 1, at: at(6, 8), etat: "bleu", clients: 40, n: {} },
    { id: 2, at: at(6, 8, 40), etat: "vert", clients: 42, n: { macs: 2 } },   // même heure : le vert l'emporte
    { id: 3, at: at(5, 23), etat: "rouge", clients: null, error: "Nebula injoignable", n: {} },
  ], { jours: 2, maintenant: NOW });
  assert.equal(g.length, 2);
  assert.equal(g[0].jour, "2026-11-06");
  assert.equal(g[0].libelle, "ven. 06/11");
  assert.deepEqual([g[0].cases[8].etat, g[0].cases[8].ids, g[0].cases[8].clients, g[0].cases[8].n], ["vert", [1, 2], 42, { macs: 2 }]);
  assert.equal(g[0].cases[7].etat, "noir");
  assert.equal(g[0].cases[10].futur, true);
  assert.equal(g[1].cases[23].etat, "rouge");
  assert.deepEqual(g[1].cases[23].erreurs, ["Nebula injoignable"]);
  assert.deepEqual(bilan(g), { noir: 32, rouge: 1, bleu: 0, vert: 1 });   // 10 h passées aujourd'hui + 24 hier = 34
});

test("textes et sommes", () => {
  assert.equal(texteNouveautes({ ips: 1, macs: 2, noms: 0 }), "2 nouvelle(s) MAC · 1 nouvelle(s) IP");
  assert.equal(texteNouveautes({}), "");
  assert.deepEqual(sommeN({ macs: 1 }, { macs: 2, ips: 1 }), { macs: 3, ips: 1 });
  assert.equal(cleJour(new Date(2026, 0, 5)), "2026-01-05");
  assert.deepEqual(grilleReleves(null, { jours: 1, maintenant: NOW })[0].cases.filter((c) => !c.futur).length, 10);
});

test("#976 : calendrier d'activité -- lieu dominant par heure, légende par temps passé", async () => {
  const { grilleActivite, nomLieu } = await import("../src/relevesLib.js");
  const lieux = [
    { de: at(6, 8, 10), a: at(6, 9, 10), piece: "Studio", borne: "AP-1", ssid: "Numeria" },
    { de: at(6, 9, 40), a: at(6, 9, 40), borne: "AP-2", ssid: "Numeria" },          // vue ponctuelle
    { de: at(5, 14, 0), a: at(5, 14, 0), ssid: "CN_IoT" },
  ];
  const g = grilleActivite(lieux, { jours: 2, maintenant: NOW });
  assert.deepEqual([g.lignes[0].cases[8].lieu, g.lignes[0].cases[9].lieu, g.lignes[0].cases[7].lieu], ["Studio", "Studio", null]);
  assert.equal(g.lignes[0].cases[9].sessions.length, 2);
  assert.equal(g.lignes[1].cases[14].lieu, "CN_IoT");
  assert.deepEqual(g.legende.map((l) => [l.lieu, l.heures]), [["Studio", 2], ["CN_IoT", 1]]);
  assert.equal(g.couleur.Studio, "var(--accent)");
  assert.equal(nomLieu({ port: "4" }), "port 4");
  assert.equal(nomLieu({}), "lieu inconnu");
});
