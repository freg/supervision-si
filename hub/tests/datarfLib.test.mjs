import { test } from "node:test";
import assert from "node:assert/strict";
import { traces, croiser, bornes, age, fmtAge, freqCanal, BANDES } from "../src/datarfLib.js";

test("tracés du spectre d'une bande", () => {
  const t = traces([[2400, -90, -80], [2450, -60, -30], [2500, -90, null], [5180, -50, -40]], BANDES[0], 100, 60, -90, -30);
  assert.equal(t.n, 3);
  assert.equal(t.moy, "M0.0,60.0 L50.0,30.0 L100.0,60.0");
  assert.equal(t.max, "M0.0,50.0 L50.0,0.0");
  assert.equal(traces([], BANDES[1]).moy, "");
});

test("croisement spectre / Wi-Fi", () => {
  const r = croiser({ canaux: [{ canal: 36, occupation_pct: 70, max_db: -36 }, { canal: 40, occupation_pct: 60 }, { canal: 44, occupation_pct: 5 }, { canal: 48, occupation_pct: 60 }] },
    { canaux: [{ canal: 36, occupation_pct: 65, par_s: 300 }, { canal: 40, occupation_pct: null, occupation_estimee_pct: 10 }, { canal: 1, occupation_pct: 20 }] });
  assert.deepEqual(r.map((c) => [c.canal, c.lecture]), [[1, ""], [36, "wifi"], [40, "non-wifi"], [44, ""], [48, ""]]);
  assert.equal(r.find((c) => c.canal === 40).wifi_estime, true);
  assert.equal(r.find((c) => c.canal === 1).freq, 2412);
  assert.equal(croiser(null, null).length, 0);
  assert.equal(freqCanal(100), 5500);
});

test("bornes et âges", () => {
  assert.deepEqual(bornes({ bornes: [{ bssid: "a", signal_max: -70 }, { bssid: "b", signal_max: -40 }, { bssid: "c" }] }).map((b) => b.bssid), ["b", "a", "c"]);
  assert.equal(age("2026-10-21T15:00:00Z", Date.parse("2026-10-21T15:02:00Z")), 120);
  assert.equal(age("x"), null);
  assert.equal(fmtAge(90), "90 s");
  assert.equal(fmtAge(600), "10 min");
  assert.equal(fmtAge(7200), "2 h");
});

import { roleDefaut, configInitiale, verifierConfig, suiviCommande } from "../src/datarfLib.js";

test("configuration radio (#807)", () => {
  const etat = { interfaces: [{ nom: "wlan0", type: "managed" }, { nom: "alfa0", type: "monitor" }, { nom: "wlan1", type: "managed" }],
    reglage: { interfaces: { wlan1: "inactive" }, ssids: [{ ssid: "Ancien", actif: false }] } };
  assert.equal(roleDefaut({ type: "monitor" }), "moniteur");
  const c = configInitiale(etat, { interfaces: { wlan0: "client" }, ssids: [{ ssid: "Campus", acces: "wifi-campus" }] });
  assert.deepEqual(c.interfaces, { wlan0: "client", alfa0: "moniteur", wlan1: "inactive" });
  assert.deepEqual(c.ssids, [{ ssid: "Campus", acces: "wifi-campus", actif: true, iface: "" }]);
  assert.deepEqual(configInitiale(etat, null).ssids, [{ ssid: "Ancien", acces: "", actif: false, iface: "" }]);
  assert.deepEqual(verifierConfig(c), []);
  assert.equal(verifierConfig({ interfaces: { alfa0: "moniteur" }, ssids: [{ ssid: "A", actif: true, iface: "alfa0" }, { ssid: "A" }, { ssid: " " }] }).length, 4);
  assert.deepEqual(suiviCommande({ status: "pending" }).etat, "attente");
  assert.deepEqual(suiviCommande({ status: "done", result: { ok: true, result: { sonde: "s", resultat: { interfaces: [] } } } }).charge, { interfaces: [] });
  assert.deepEqual(suiviCommande({ status: "done", result: { ok: true, result: { interfaces: [1] } } }).charge, { interfaces: [1] });
  assert.equal(suiviCommande({ status: "failed", result: { ok: false, error: "hors ligne" } }).texte, "hors ligne");
});

import { etatSondes, caseRf, caseWifi, caseLan, caseActivite } from "../src/datarfLib.js";

test("état du réseau de sondes (#811)", () => {
  assert.equal(caseActivite({ age_s: 60 }).niveau, "ok");
  assert.equal(caseActivite({ age_s: 4000 }).niveau, "critique");
  assert.equal(caseRf({}).niveau, "absent");
  assert.match(caseRf({ rf_spectrum: { present: false } }).action, /Mayhem/);
  assert.equal(caseRf({ rf_spectrum: { error: "délai dépassé" } }).niveau, "attention");
  assert.equal(caseRf({ rf_spectrum: { canaux: [{ canal: 36, occupation_pct: 70 }, { canal: 1, occupation_pct: 2 }] } }).niveau, "attention");
  assert.equal(caseRf({ rf_spectrum: { canaux: [{ canal: 1, occupation_pct: 2 }] } }).texte, "1 canaux balayés");
  assert.match(caseWifi({ wifi_monitor: { iface: "alfa0", canaux: [], refus: ["6 : Operation not possible due to RF-kill"] } }).action, /rfkill/);
  assert.match(caseWifi({ wifi_monitor: { iface: "alfa0", canaux: [], refus: ["1 : Device or resource busy (-16)"] } }).action, /moniteur/);
  const w = caseWifi({ wifi_monitor: { iface: "alfa0", canaux: [1, 2], bornes: [1] }, wifi_probe: { link: { connected: false } } });
  assert.equal(w.niveau, "attention");
  assert.match(w.texte, /2 canaux · 1 bornes · client non associé/);
  assert.match(w.action, /Configuration radio/);
  assert.equal(caseLan({ path_probe: { summary: { state: "critical" }, paths: [{}] } }).niveau, "critique");
  const t = etatSondes([{ sonde: "b", age_s: 30, rf_spectrum: { canaux: [] } }, { sonde: "a", age_s: 9000 }], [{ message: "a : x" }, { message: "ab : y" }]);
  assert.deepEqual(t.map((r) => [r.sonde, r.global, r.constats]), [["a", "critique", 1], ["b", "ok", 0]]);
});
