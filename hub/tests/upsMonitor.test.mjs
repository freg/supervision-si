import { test } from "node:test";
import assert from "node:assert/strict";
import {
  PRIMARY_KEYS, orderedFields, fieldLabel, fieldTone, deviceStatus, formatAge, formatInterval,
  summarizeLast, numericKeys, toLineSeries, timelineRows, windowStart,
} from "../src/upsMonitor.js";

const sections = [
  { title: "UPS Status", fields: [
    { key: "model", label: "Model", value: "NETYS RT 1/1 UPS" },
    { key: "communication", label: "Communication", value: "OK" },
    { key: "output_source", label: "Output Source", value: "On Battery" },
    { key: "battery", label: "Battery", value: "Normal" },
  ] },
  { title: "UPS Measurement", fields: [
    { key: "battery_capacity", label: "Battery Capacity", value: "100 %", number: 100, unit: "%" },
    { key: "input_voltage", label: "Input Voltage", value: "236.0 V", number: 236, unit: "V" },
    { key: "temperature_interne", label: "Température interne", value: "31 °C", number: 31, unit: "°C" },
  ] },
  { title: "Schedule", fields: [{ key: "next_test", label: "Next Test Time", value: "09/07/2026 15:00" }] },
];

test("les champs principaux passent devant, le reste garde l'ordre de la page, la section est conservée", () => {
  const keys = orderedFields(sections).map((f) => f.key);
  assert.deepEqual(keys, ["model", "communication", "output_source", "battery", "input_voltage", "battery_capacity", "temperature_interne", "next_test"]);
  assert.equal(orderedFields(sections)[4].section, "UPS Measurement");
  assert.deepEqual(orderedFields(undefined), []);
  assert.ok(PRIMARY_KEYS.includes("battery_capacity"));
});

test("libellés français et ton des champs d'état", () => {
  assert.equal(fieldLabel("input_voltage"), "Tension d'entrée");
  assert.equal(fieldLabel("temperature_interne", "Température interne"), "Température interne");
  assert.equal(fieldLabel("inconnu"), "inconnu");
  assert.equal(fieldTone({ key: "communication", value: "OK" }), "good");
  assert.equal(fieldTone({ key: "output_source", value: "On Battery" }), "bad");
  assert.equal(fieldTone({ key: "input_voltage", value: "236.0 V" }), "neutral");
  assert.equal(fieldTone(undefined), "neutral");
});

test("état d'un onduleur dans la liste", () => {
  const now = Date.parse("2026-09-07T12:00:00Z");
  assert.deepEqual(deviceStatus(null), { tone: "neutral", text: "—" });
  assert.equal(deviceStatus({ enabled: false }).text, "désactivé");
  assert.equal(deviceStatus({ enabled: true, last_polled_at: null }).text, "jamais relevé");
  const fresh = { enabled: true, last_polled_at: "2026-09-07T11:30:00Z", last_ok: true, last_state: "ok", poll_interval_seconds: 3600 };
  assert.deepEqual(deviceStatus(fresh, now), { tone: "good", text: "normal" });
  assert.deepEqual(deviceStatus({ ...fresh, last_state: "alarm" }, now), { tone: "bad", text: "alarme" });
  assert.equal(deviceStatus({ ...fresh, last_ok: false, last_error: "HTTP 401" }, now).text, "HTTP 401");
  assert.equal(deviceStatus({ ...fresh, last_ok: false, last_error: null }, now).text, "échec du relevé");
  const stale = deviceStatus({ ...fresh, last_polled_at: "2026-09-07T00:00:00Z" }, now);
  assert.equal(stale.tone, "warn");
  assert.match(stale.text, /relevé ancien \(12 h\)/);
  assert.equal(deviceStatus({ ...fresh, poll_interval_seconds: null, last_polled_at: "2026-09-07T09:00:00Z" }, now, 2.5, 3600).tone, "warn", "intervalle par défaut");
  assert.equal(deviceStatus({ ...fresh, last_state: "unknown" }, now).text, "unknown");
});

test("formats d'âge et d'intervalle", () => {
  assert.equal(formatAge(45), "45 s");
  assert.equal(formatAge(600), "10 min");
  assert.equal(formatAge(7200), "2 h");
  assert.equal(formatAge(3 * 86400), "3 j");
  assert.equal(formatAge(-1), "—");
  assert.equal(formatInterval(3600), "1 h");
  assert.equal(formatInterval(600), "10 min");
  assert.equal(formatInterval(90), "90 s");
  assert.equal(formatInterval(null), "");
});

test("résumé du dernier relevé depuis le JSON dénormalisé", () => {
  const s = JSON.stringify({ input_voltage: "236.0 V", output_voltage: "229.0 V", output_load: "8 %", battery_capacity: "100 %" });
  assert.equal(summarizeLast(s), "236.0 V → 229.0 V · charge 8 % · batt. 100 %");
  assert.equal(summarizeLast({ battery_capacity: "50 %" }), "batt. 50 %");
  assert.equal(summarizeLast("{cassé"), "");
  assert.equal(summarizeLast(null), "");
});

test("clés numériques pour la courbe, série et fenêtre", () => {
  const fields = { model: { number: null }, input_voltage: { number: 236 }, temperature_interne: { number: 31 }, output_load: { number: 8 } };
  assert.deepEqual(numericKeys(fields), ["input_voltage", "output_load", "temperature_interne"]);
  assert.deepEqual(numericKeys(undefined), []);
  assert.deepEqual(toLineSeries([{ at: "a", number: 1 }, { at: "b", number: null }, { at: "c", number: 3 }]), [{ at: "a", value: 1 }, { at: "c", value: 3 }]);
  const now = Date.parse("2026-09-07T12:00:00Z");
  assert.equal(windowStart("24h", now), "2026-09-06T12:00:00Z");
  assert.equal(windowStart("all", now), null);
  assert.equal(windowStart("bidon", now), null);
});

test("timeline : ce qui change d'un relevé à l'autre est repéré", () => {
  const rows = timelineRows([
    { id: 1, ok: true, state: "ok", input_voltage: 236, output_load: 8, battery_capacity: 100 },
    { id: 2, ok: true, state: "ok", input_voltage: 238, output_load: 8, battery_capacity: 100 },
    { id: 3, ok: false, state: null, input_voltage: null, output_load: null, battery_capacity: null },
    { id: 4, ok: true, state: "alarm", input_voltage: 0, output_load: 8, battery_capacity: 90 },
  ]);
  assert.deepEqual(rows[0].changes, []);
  assert.deepEqual(rows[1].changes, ["input_voltage"]);
  assert.deepEqual(rows[2].changes, ["state", "input_voltage", "output_load", "battery_capacity", "ok"]);
  assert.deepEqual(rows[3].changes, ["state", "input_voltage", "output_load", "battery_capacity", "ok"]);
  assert.deepEqual(timelineRows([]), []);
});

// --- Livraison #417 : Net Vision v6 ---
import { displayValue, SERIES_KEYS } from "../src/upsMonitor.js";

test("valeur affichée avec son unité quand la page ne l'écrit pas ; état de l'ASI coloré", () => {
  assert.equal(displayValue({ value: "230.0", unit: "V" }), "230.0 V");
  assert.equal(displayValue({ value: "236.0 V", unit: "V" }), "236.0 V", "pas de doublon");
  assert.equal(displayValue({ value: "", unit: "minutes" }), "");
  assert.equal(displayValue({ value: "Utilisation sur Onduleur", unit: null }), "Utilisation sur Onduleur");
  assert.equal(displayValue(undefined), "");
  assert.equal(fieldTone({ key: "ups_state", value: "Utilisation sur Onduleur" }), "good");
  assert.equal(fieldTone({ key: "ups_state", value: "Utilisation sur Batterie" }), "bad");
  assert.equal(fieldLabel("ups_state"), "État de l'ASI");
  assert.equal(fieldLabel("temperature"), "Température");
  assert.ok(SERIES_KEYS.includes("temperature"));
  const keys = orderedFields([{ title: "Synthèse ASI", fields: [{ key: "temperature" }, { key: "ups_state" }, { key: "device_date" }] }]).map((f) => f.key);
  assert.deepEqual(keys, ["ups_state", "temperature", "device_date"]);
});
