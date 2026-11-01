// #927 : potentiel d'évolution d'un NAS (baies, réserve, scénarios d'extension).
import { test } from "node:test";
import assert from "node:assert/strict";
import { baiesDuModele, estSsd, utile, evolution, taille } from "../src/nasEvolution.js";

const TO = 1e12;
// Calqué sur le relevé d'exemple de la sonde (valeurs anonymisées) : 3 × 12 To en RAID 5, un SSD seul en baie 8.
const NAS = {
  systeme: { modele: "TS-883XU-RP" },
  disques: [1, 2, 3].map((b) => ({ emplacement: b, modele: "Seagate ST12000VN0007 (SATA)", octets: 12000138625024 }))
    .concat([{ emplacement: 8, modele: "Samsung SSD 860 QVO 1TB (SATA)", octets: 1000204886016 }]),
  raid: [{ dev: "/dev/md1", niveau: "5" }, { dev: "/dev/md2", niveau: "Single" }],
  reserves: [{ id: 1, octets: 23979871961088, libre_octets: 8484150575104 }],
  volumes: [{ nom: "Volume-1", ko: 8471730536 }, { nom: "Backup", ko: 2096975952 }],
};

test("baies déduites du modèle QNAP", () => {
  assert.equal(baiesDuModele("TS-883XU-RP"), 8);
  assert.equal(baiesDuModele("TS-h1886XU-RP"), 18);
  assert.equal(baiesDuModele("TS-453D"), 4);
  assert.equal(baiesDuModele("TVS-h874"), 8);
  assert.equal(baiesDuModele("TS-1273AU-RP"), 12);
  assert.equal(baiesDuModele("Synology DS920+"), null);
  assert.equal(baiesDuModele(undefined), null);
});

test("capacité utile par RAID", () => {
  assert.equal(utile("5", 3, 12), 24);
  assert.equal(utile("6", 7, 12), 60);
  assert.equal(utile("1", 2, 12), 12);
  assert.equal(utile("10", 4, 12), 24);
  assert.equal(utile("5", 2, 12), null, "RAID 5 : 3 disques au moins");
  assert.equal(utile("10", 5, 12), null);
  assert.ok(estSsd({ modele: "Samsung SSD 860 QVO" }) && !estSsd({ modele: "Seagate ST12000VN0007" }));
});

test("NAS d'exemple : baies libres, réserve, conseils chiffrés", () => {
  const e = evolution(NAS);
  assert.equal(e.baies, 8);
  assert.equal(e.source, "modèle");
  assert.deepEqual(e.libres, [4, 5, 6, 7]);
  assert.deepEqual(e.occupees.map((o) => o.type), ["HDD", "HDD", "HDD", "SSD"]);
  const c = Object.fromEntries(e.conseils.map((x) => [x.cle, x]));
  assert.match(c.reserve.titre, /8,5 To libres/);
  assert.equal(e.volumes["Volume-1"], 8471730536 * 1024 + 8484150575104);
  assert.match(c.ajout.titre, /4 disques de 12,0 To.*\(4, 5, 6, 7\)/);
  assert.match(c.ajout.detail, /24,0 To utiles → 72,0 To/);
  assert.ok(Math.abs(c.ajout.gain - 4 * 12000138625024) < 1);
  assert.match(c.raid6.titre, /7 disques/);
  assert.match(c.raid6.detail, /60,0 To utiles/);
  assert.ok(c["remplacement-16"] && c["remplacement-20"] && !c["remplacement-24"]);
  assert.match(c["remplacement-20"].detail, /→ 40,0 To/);
  assert.ok(c["ssd-8"]);
  assert.ok(!c.extension && !c["baies-inconnues"] && !c.surallocation);
});

test("baies pleines, réglage explicite, RAID 1 migré, modèle inconnu, surallocation", () => {
  const plein = evolution({ ...NAS, baies: 3 });
  assert.equal(plein.source, "réglage");
  assert.deepEqual(plein.libres, []);
  assert.ok(plein.conseils.some((x) => x.cle === "extension"));
  const r1 = evolution({ systeme: { modele: "TS-453D" }, disques: [1, 2].map((b) => ({ emplacement: b, modele: "WD Red", octets: 4 * TO })),
    raid: [{ niveau: "1" }], reserves: [], volumes: [] });
  const aj = r1.conseils.find((x) => x.cle === "ajout");
  assert.match(aj.detail, /RAID 1 migré en RAID 5 : 4,0 To utiles → 12,0 To/);
  assert.ok(!r1.conseils.some((x) => x.cle === "raid6"), "4 To : pas d'insistance RAID 6 à 4 disques");
  const inconnu = evolution({ systeme: { modele: "Autre" }, disques: [] });
  assert.equal(inconnu.baies, null);
  assert.ok(inconnu.conseils.some((x) => x.cle === "baies-inconnues"));
  const sur = evolution({ ...NAS, volumes: [{ nom: "a", ko: 30 * TO / 1024 }] });
  assert.ok(sur.conseils.some((x) => x.cle === "surallocation"));
  assert.equal(taille(null), "—");
});
