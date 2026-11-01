import test from "node:test";
import assert from "node:assert/strict";
import { fmt, conditionTexte, sparkPoints, boucleDepuisForm, formDepuisBoucle, progression, manquants, grouperOutils, lignesSondes, lignesBornes } from "../src/pilotageLib.js";

test("fmt", () => {
  assert.equal(fmt(null), "—");
  assert.equal(fmt(123.6, "ms"), "124 ms");
  assert.equal(fmt(12.04), "12");
  assert.equal(fmt(0.5, "%"), "0.5 %");
  assert.equal(fmt(-65, "dBm"), "-65 dBm");
});

test("conditionTexte", () => {
  const M = { "borne.simultanes": { libelle: "Clients simultanés", unite: "clients" } };
  assert.equal(conditionTexte({ metrique: "borne.simultanes", cible: "*", op: ">", seuil: 25, duree_min: 5 }, M), "Clients simultanés > 25 clients pendant 5 min (toutes les cibles)");
  assert.equal(conditionTexte({ metrique: "x", cible: "B1", op: "<", seuil: 1, duree_min: 0 }), "x < 1 (dernier relevé) (B1)");
});

test("sparkPoints", () => {
  assert.equal(sparkPoints([[0, 1]]), "");
  assert.equal(sparkPoints([[0, 0], [10, 10]], 100, 22), "0.0,21.0 100.0,1.0");
  assert.equal(sparkPoints([[0, 5], [10, 5]], 10, 10).split(" ").length, 2);   // série plate : pas de division par zéro
});

test("boucle : formulaire aller-retour", () => {
  const f = { nom: " Latence ", metrique: "sonde.rtt_ms", cible: "", op: ">", seuil: "80", duree_min: "5", notifier: true, outil: "ncc-limite-appli", banc: "cast", mode: "auto", delai_min: "120" };
  const b = boucleDepuisForm(f);
  assert.deepEqual(b.actions, [{ type: "notifier" }, { type: "recommander", outil: "ncc-limite-appli" }, { type: "banc", plan: "cast" }]);
  assert.deepEqual(b.condition, { metrique: "sonde.rtt_ms", cible: "*", op: ">", seuil: 80, duree_min: 5 });
  assert.equal(b.nom, "Latence");
  const g = formDepuisBoucle(b);
  assert.equal(g.cible, "");
  assert.equal(g.banc, "cast");
  assert.deepEqual(boucleDepuisForm(g), b);
});

test("progression", () => {
  const plan = { etapes: [{ nom: "A", duree_min: 3 }, { nom: "B", duree_min: 3 }] };
  const p = progression({ debut: 1000, etape: 1 }, plan, 1000 + 240);
  assert.deepEqual(p, { etape: 2, etapes: 2, nom: "B", ecoule_min: 4, total_min: 6, pct: 67 });
  assert.equal(progression(null, plan), null);
  assert.equal(progression({ debut: 0, etape: 0 }, plan, 99999).pct, 100);
});

test("manquants", () => {
  const plan = { etapes: [{ taches: [{ params: { host: "{serveur}" } }, { params: { url: "{url}" } }] }] };
  assert.deepEqual(manquants(plan, {}), ["adresses à charger", "serveur iperf3", "sondes autorisées pour les bancs"]);
  assert.deepEqual(manquants(plan, { serveur_iperf: "s", urls: ["https://a"], sondes: ["a"] }), []);
});

test("grouperOutils", () => {
  assert.deepEqual(grouperOutils([{ id: 1, groupe: "R" }, { id: 2, groupe: "D" }, { id: 3, groupe: "R" }]).map(([g, l]) => [g, l.length]), [["R", 2], ["D", 1]]);
});

test("lignes sondes et bornes", () => {
  const v = { "sonde.rtt_ms": { b: 10, a: 20 }, "sonde.rssi_dbm": { a: -60 }, "borne.simultanes": { B1: 5, B2: 30 }, "borne.clients": { B3: 2 } };
  const s = lignesSondes(v);
  assert.deepEqual(s.map((x) => [x.sonde, x.rtt, x.rssi]), [["a", 20, -60], ["b", 10, null]]);
  assert.deepEqual(lignesBornes(v).map((x) => x.borne), ["B2", "B1", "B3"]);
  assert.deepEqual(lignesSondes(null), []);
});
