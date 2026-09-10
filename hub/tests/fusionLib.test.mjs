import test from "node:test";
import assert from "node:assert/strict";
import {
  mergeIpSources, filterRows, compareIp, enrichWithGeolocation, extractPostalCodeFromRow, nameResolveSubjects, severityTone,
  summarizeRows, classifyIp, visibleColumns, toggleColumnVisibility, FUSION_COLUMNS,
} from "../src/fusionLib.js";

const IPAM = [{ ip: "10.0.0.10", mac: "aa:bb:cc:00:00:10", hostname: "srv-stmalo-01", subnet: "10.0.0.0/24", state: 1 }, { ip: "10.0.0.2", mac: "aa:bb:cc:00:00:02", hostname: "BIO17-17300-ISLANDE-RB3011", subnet: "10.0.0.0/24" }, { ip: "", hostname: "vide" }];
const ZENOSS = [{ ip: "10.0.0.10", device: "srv-stmalo-01.lan", activeCount: 3, maxSeverity: 5, severityLabel: "critical" }, { ip: "8.8.8.8", device: "dns-google", activeCount: 0, maxSeverity: 0, severityLabel: "clear" }];

test("fusion par IP : tri numérique, sources, noms d'hôte dédupliqués", () => {
  const rows = mergeIpSources(IPAM, ZENOSS);
  assert.deepEqual(rows.map((r) => r.ip), ["8.8.8.8", "10.0.0.2", "10.0.0.10"]);
  const s = rows.find((r) => r.ip === "10.0.0.10");
  assert.deepEqual(s.sources, ["ipam", "zenoss"]);
  assert.deepEqual(s.hostnames, ["srv-stmalo-01", "srv-stmalo-01.lan"]);
  assert.equal(s.mac, "aa:bb:cc:00:00:10");
  assert.equal(compareIp("10.0.0.2", "10.0.0.10") < 0, true);
  assert.equal(compareIp("abc", "10.0.0.1") > 0, true, "IP malformée en fin");
});

test("filtres : global, corrélées, nom d'hôte, alerte", () => {
  const rows = mergeIpSources(IPAM, ZENOSS);
  assert.equal(filterRows(rows, { correlatedOnly: true }).length, 1);
  assert.equal(filterRows(rows, { query: "islande" }).length, 1);
  assert.equal(filterRows(rows, { hostnameQuery: "stmalo" }).length, 1);
  assert.equal(filterRows(rows, { alertQuery: "critical" }).length, 1);
  assert.equal(filterRows(rows, { alertQuery: "critical", hostnameQuery: "google" }).length, 0);
});

test("positions : table par IP, correspondance par nom (#426), code postal, sujets à résoudre", () => {
  const rows = mergeIpSources(IPAM, ZENOSS);
  const geos = [{ localisation: "8.8.8.8", latitude: 37.4, longitude: -122.1, mapped: true }, { localisation: "10.0.0.2", latitude: null, longitude: null, mapped: false }];
  const matches = { "ip:10.0.0.10": { status: "auto", localisation: "Agence Saint-Malo", latitude: 48.65, longitude: -2.0, score: 0.76 }, "ip:10.0.0.2": { status: "rejected", localisation: "x", latitude: 1, longitude: 1 } };
  const enriched = enrichWithGeolocation(rows, geos, matches);
  const by = Object.fromEntries(enriched.map((r) => [r.ip, r]));
  assert.equal(by["8.8.8.8"].position.source, "ip");
  assert.deepEqual([by["10.0.0.10"].position.source, by["10.0.0.10"].position.localisation, by["10.0.0.10"].position.mapped], ["nom", "Agence Saint-Malo", true]);
  assert.equal(by["10.0.0.2"].position.mapped, false, "en attente : entrée pixel-grid sans coordonnées, correspondance rejetée ignorée");
  assert.equal(extractPostalCodeFromRow(by["10.0.0.2"]), "17300");
  assert.equal(extractPostalCodeFromRow(by["10.0.0.10"]), null);
  assert.deepEqual(nameResolveSubjects(enriched), [{ subject: "ip:10.0.0.2", name: "BIO17-17300-ISLANDE-RB3011", site: null }], "seules les lignes sans position avec un nom");
  const sum = summarizeRows(enriched);
  assert.deepEqual(sum, { total: 3, correlated: 1, positioned: 2, byName: 1, ipam: 2, zenoss: 2, privateUnpositioned: 1 });
});

test("sévérité, classification, colonnes", () => {
  assert.deepEqual([severityTone(5), severityTone(3), severityTone(0), severityTone(undefined)], ["bad", "warn", "good", "neutral"]);
  assert.deepEqual([classifyIp("10.1.2.3"), classifyIp("8.8.8.8"), classifyIp("fe80::1"), classifyIp("x")], ["private", "public", "unknown", "invalid"]);
  const hidden = toggleColumnVisibility(new Set(), "mac");
  assert.equal(visibleColumns(hidden).length, FUSION_COLUMNS.length - 1);
  assert.equal(toggleColumnVisibility(hidden, "mac").size, 0);
});
