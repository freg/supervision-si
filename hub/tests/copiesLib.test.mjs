import test from "node:test";
import assert from "node:assert/strict";
import { filtrer, parType, age, volume, cibles, reglesTexte, reglesObjet } from "../src/copiesLib.js";

test("filtrer", () => {
  const L = [{ name: "MED86", vmid: 101, node: "pve-3", verdict: "ok" }, { name: "partages", vmid: 100, node: "pve10", verdict: "critique", niveau: "critique" }];
  assert.equal(filtrer(L, { texte: "med" }).length, 1);
  assert.equal(filtrer(L, { etat: "critique" })[0].vmid, 100);
  assert.equal(filtrer(L, { noeud: "pve-3", texte: "100" }).length, 0);
});

test("parType, age, volume", () => {
  assert.deepEqual(parType([{ type: "zfs", survit: true }, { type: "zfs", survit: false }, { type: "vzdump", survit: true }], true), { zfs: 1, vzdump: 1 });
  assert.equal(age(0.2), "12 min");
  assert.equal(age(30), "30 h");
  assert.equal(age(300), "13 j");
  assert.equal(volume({ volume: "plausible", ratio: 0.31 }), "plausible (31 %)");
  assert.equal(volume({ volume: "inconnu" }), "inconnu");
});

test("cibles et règles", () => {
  assert.deepEqual(cibles("https://a/\n tcp://b:22 ; https://a/"), ["https://a/", "tcp://b:22"]);
  const r = { "ovh/pve2": "pve-2", "data/ovh/pve3": "pve-3" };
  assert.deepEqual(reglesObjet(reglesTexte(r)), r);
  assert.deepEqual(reglesObjet("sans égal\n= x\na = "), {});
});
