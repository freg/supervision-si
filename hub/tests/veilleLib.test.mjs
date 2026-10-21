import test from "node:test";
import assert from "node:assert/strict";
import { paramsRegle, basculer, termes, dateCourte, ton, chezNous, fmtEpss } from "../src/veilleLib.js";

test("veille : paramètres de règle", () => {
  assert.equal(paramsRegle({ categories: ["alerte"], publics: ["rssi"], statuts: ["a_traiter", "aucun"], texte: " openssh -windows ", jours: 7, impacts: true, cve: false }),
    "categories=alerte&publics=rssi&statuts=a_traiter%2Caucun&texte=openssh+-windows&jours=7&impacts=1");
  assert.equal(paramsRegle({}), "jours=30");
});

test("veille : puces, termes, dates", () => {
  assert.deepEqual(basculer(["a", "b"], "a"), ["b"]);
  assert.deepEqual(basculer([], "c"), ["c"]);
  assert.deepEqual(termes("mikrotik, routeros ; winbox\nmikrotik,,"), ["mikrotik", "routeros", "winbox"]);
  const ts = new Date(2026, 9, 21, 14, 5).getTime() / 1000;
  assert.equal(dateCourte(ts, new Date(2026, 11, 1)), "21/10 14:05");
  assert.equal(dateCourte(ts, new Date(2027, 0, 1)), "21/10/2026");
  assert.equal(dateCourte(null), "—");
});

test("veille : ton, chez nous, EPSS", () => {
  assert.equal(ton({ niveau: "avis", impacts: { actifs: ["a"], priorite: "P1" } }), "bad");
  assert.equal(ton({ niveau: "avis", impacts: { actifs: ["a"], priorite: "P3" } }), "warn");
  assert.equal(ton({ niveau: "alerte", nos_modeles: ["RB4011"], impacts: { actifs: [] } }), "bad");
  assert.equal(ton({ impacts: { actifs: [] } }), "neutral");
  assert.equal(chezNous({ actifs: ["a", "b", "c", "d"], priorite: "P2" }), "a, b +2 (P2)");
  assert.equal(chezNous({ actifs: [] }), "");
  assert.equal(fmtEpss(0.9731), "97 %");
  assert.equal(fmtEpss(0.0123), "1,2 %");
  assert.equal(fmtEpss(null), "—");
});
