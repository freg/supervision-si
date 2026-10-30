// #937 : tuile « Sauvegardes » -- tons, détail copiable, filtres, points à traiter, CSV.
import { test } from "node:test";
import assert from "node:assert/strict";
import { ton, urgence, libelle, to, ageTexte, detailPoste, filtrerPostes, etatHote, points, csvPostes, ONGLETS } from "../src/sauvegardesLib.js";

const P = [
  { agent_id: "pc-a", hostname: "PC-A", etat: "critique", raison: "dernière sauvegarde il y a 40 j", at: "2026-09-20T10:00:00Z", age_j: 40, archive: "a.zip", octets: 2.5e9, confs: 3, montages: 1, destinations_ok: ["usb"], destinations_ko: ["unc"], pbs: { ok: false, erreur: "jeton refusé" } },
  { agent_id: "pc-b", hostname: "PC-B", etat: "ok", raison: "", at: "2026-10-30T08:00:00Z", age_j: 0.1, archive: "b.zip", octets: 12e6, confs: 2, montages: 0, destinations_ok: ["unc"], destinations_ko: [], pbs: { ok: true, snapshot: "host/pc-b/x" } },
  { agent_id: "pc-c", hostname: "PC-C", etat: "jamais", raison: "aucune sauvegarde de conf remontée", at: null, age_j: null, confs: 0, montages: 0, destinations_ok: [], destinations_ko: [], pbs: null },
];

test("tons, urgences, libellés, unités françaises", () => {
  assert.equal(ton("critique"), "bad"); assert.equal(ton("jamais"), "warn"); assert.equal(ton("non relevé"), "neutral"); assert.equal(ton("?"), "neutral");
  assert.equal(urgence("erreur"), "critique"); assert.equal(urgence("jamais"), "alerte"); assert.equal(urgence("ok"), "info");
  assert.equal(libelle("jamais"), "jamais sauvegardé");
  assert.equal(to(2.5e9), "2,5 Go"); assert.equal(to(1.2e12), "1,2 To"); assert.equal(to(12e6), "12 Mo"); assert.equal(to(null), "—");
  assert.equal(ageTexte(null), "jamais"); assert.equal(ageTexte(0.3), "aujourd'hui"); assert.equal(ageTexte(1.4), "hier"); assert.equal(ageTexte(40), "il y a 40 j");
});

test("détail copiable d'un poste", () => {
  const d = detailPoste(P[0]);
  assert.match(d, /PC-A \(pc-a\) : critique/);
  assert.match(d, /destinations en échec : unc/);
  assert.match(d, /PBS : poussée en échec -- jeton refusé/);
  assert.match(d, /2,5 Go/);
  assert.match(detailPoste(P[2]), /jamais poussé vers pbs10/);
  assert.equal(detailPoste(null), "");
});

test("filtres et état des hôtes de secours", () => {
  assert.deepEqual(filtrerPostes(P, "a-traiter").map((p) => p.agent_id), ["pc-a", "pc-c"]);
  assert.deepEqual(filtrerPostes(P, "ok").map((p) => p.agent_id), ["pc-b"]);
  assert.equal(filtrerPostes(P, "tous").length, 3);
  assert.equal(etatHote({ echecs: 0, absentes: 0, plus_vieille_h: 12 }), "ok");
  assert.equal(etatHote({ echecs: 0, absentes: 0, plus_vieille_h: 72 }), "attention");
  assert.equal(etatHote({ echecs: 1, absentes: 0 }), "critique");
  assert.equal(etatHote({ erreur: "journal absent" }), "erreur");
  assert.equal(etatHote(null), "non relevé");
});

test("points à traiter : critiques d'abord, puis attention, avec l'onglet cible", () => {
  const ap = { postes: P, pbs: [{ serveur: "pbs10", etat: "attention", alertes: ["ds1 à 91 %"] }],
    copies: { hotes: [{ hote: "secours", echecs: 1, absentes: 0 }], invites: { critique: 2 } }, nas: [{ nom: "qnap", etat: "ok" }] };
  const pts = points(ap);
  assert.equal(pts[0].etat, "critique");
  assert.ok(pts.findIndex((p) => p.etat === "attention") > pts.filter((p) => p.etat === "critique").length - 1);
  assert.ok(pts.some((p) => p.texte === "2 VM/CT sans copie fraîche" && p.onglet === "copies"));
  assert.ok(pts.some((p) => p.texte === "PC-C : jamais sauvegardé" && p.onglet === "postes"));
  assert.ok(pts.some((p) => p.texte.startsWith("PBS pbs10 : ds1")));
  assert.ok(!pts.some((p) => p.texte.startsWith("NAS")));
  assert.deepEqual(points(null), []);
});

test("CSV ; pour Excel français, décimale à virgule", () => {
  const csv = csvPostes(P);
  const l = csv.split("\r\n");
  assert.equal(l.length, 4);
  assert.match(l[0], /^poste;agent;etat/);
  assert.match(l[1], /"PC-A";"pc-a";"critique";"2026-09-20T10:00:00Z";"40"/);
  assert.match(l[2], /"0,1"/);
  assert.match(l[3], /"jamais"$/);
  assert.equal(ONGLETS.length, 6);
});
