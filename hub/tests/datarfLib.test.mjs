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
