import test from "node:test";
import assert from "node:assert/strict";
import { resumeBilan, age, filtrerMatrice, dureeAlerte, commandesSite, exempleListe, STATUTS, lignesPassage } from "../src/fluxLib.js";

test("bilan, âge, durée", () => {
  assert.equal(resumeBilan(null), "aucun passage");
  assert.equal(resumeBilan({ OK: 78, KO: 1, NS: 28, INSPECTE: 0 }), "78 ouvert(s) · 1 fermé(s) · 28 non servi(s)");
  assert.equal(age(0), "jamais"); assert.equal(age(100, 160), "il y a 60 s"); assert.equal(age(0 + 1, 1 + 7200), "il y a 2 h");
  assert.equal(dureeAlerte({ debut: 0, fin: 1800 }), "30 min"); assert.equal(dureeAlerte({ debut: 0 }, 3 * 86400), "3 j");
  for (const k of ["OK", "KO", "NS", "INSPECTE", "?"]) assert.match(STATUTS[k].couleur, /^var\(--/);
});

test("matrice filtrée et commandes", () => {
  const m = { colonnes: ["tcp/443"], lignes: [{ hote: "a.com", groupe: "g", cellules: { "tcp/443": "OK" } }, { hote: "b.com", groupe: "g", cellules: { "tcp/443": "INSPECTE" } }] };
  assert.deepEqual(filtrerMatrice(m, { problemes: true }).lignes.map((l) => l.hote), ["b.com"]);
  assert.deepEqual(filtrerMatrice(m, { q: "a.c" }).lignes.map((l) => l.hote), ["a.com"]);
  assert.deepEqual(filtrerMatrice(null).lignes, []);
  const c = commandesSite("https://hub/api/nebula", "s1", ["google", "idruide"], "wlp3s0");
  assert.match(c, /HUB=https:\/\/hub\/api\/nebula SITE=s1/); assert.match(c, /IFACE=wlp3s0/); assert.match(c, /-l google,idruide/); assert.match(c, /crontab/);
  assert.match(exempleListe("Idruide"), /^# une cible/); assert.match(exempleListe("Idruide"), /idruide;api\.exemple\.com;tcp;443/);
});

test("visualiseur : filtres et tri", () => {
  const L = [{ hote: "b", port: 1, statut: "NS", groupe: "", detail: "" }, { hote: "a", port: 2, statut: "KO", groupe: "", detail: "" },
    { hote: "c", port: 3, statut: "OK", groupe: "", detail: "" }, { hote: "d", port: 4, statut: "KO", groupe: "", detail: "", ignore: true }];
  assert.deepEqual(lignesPassage(L).map((l) => l.hote), ["a", "b"]);
  assert.deepEqual(lignesPassage(L, "ignores").map((l) => l.hote), ["d"]);
  assert.deepEqual(lignesPassage(L, "tous").map((l) => l.hote), ["a", "d", "b", "c"]);
  assert.deepEqual(lignesPassage(L, "tous", "c").map((l) => l.hote), ["c"]);
  assert.equal(STATUTS.IGN.couleur, "var(--muted)");
});
