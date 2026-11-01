// #930 : helpers de l'onglet « Sauvegarde ».
import { test } from "node:test";
import assert from "node:assert/strict";
import { octets, lignes, depuisLignes, resume } from "../src/sauvegardeLib.js";

test("formats et conversion texte", () => {
  assert.equal(octets(null), "—");
  assert.equal(octets(500), "500 o");
  assert.equal(octets(2048), "2 ko");
  assert.equal(octets(5_000_000), "5,0 Mo");
  assert.equal(octets(3_200_000_000), "3,2 Go");
  assert.equal(lignes(["a", "b"]), "a\nb");
  assert.deepEqual(depuisLignes(" a \n\n b \n"), ["a", "b"]);
});

test("synthèse d'un résultat", () => {
  const r = resume({
    confs: [{ app: "Thunderbird", octets: 1200 }, { app: "Firefox", octets: 800 }],
    dossiers: [{ app: "Thunderbird", octets: 5_000_000 }, { app: "Chrome", octets: 0, absent: true }],
    destinations: [{ type: "usb", ok: true }, { type: "unc", ok: false }],
    archive: { nom: "bk.zip", octets: 5_100_000 },
  });
  assert.equal(r.apps, 3);
  assert.equal(r.cles, 2);
  assert.equal(r.octetsConfs, 2000);
  assert.equal(r.octetsDossiers, 5_000_000);
  assert.equal(r.destinationsOk, 1);
  assert.equal(r.destinationsKo, 1);
  assert.equal(r.archive.nom, "bk.zip");
  assert.equal(resume(null).archive, null);
});
