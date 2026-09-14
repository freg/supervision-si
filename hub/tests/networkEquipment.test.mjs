import test from "node:test";
import assert from "node:assert/strict";
import {
  kindLabel, generationTone, generationLabel, confidenceLabel, summarizeFleet, sortEquipment, filterEquipment,
  displayName, pollTone, topologyRows, previewSummary, isNetworkGear,
} from "../src/networkEquipment.js";

const rows = [
  { id: 1, name: "rtr-alpha", ip: "192.0.2.1", mac: "4C:5E:0C:01:02:03", vendor: "MikroTik", model: "RB5009UG+S+", kind: "routeur", generation: "recent", confidence: 0.9 },
  { id: 2, name: "sw-b", ip: "192.0.2.2", vendor: "Cisco", model: "WS-C2950-24", kind: "switch", generation: "ancien", confidence: 0.6, generation_reason: "famille C2950" },
  { id: 3, hostname: "vm-bob", ip: "192.0.2.50", kind: "hôte", confidence: 0.15 },
  { id: 4, ip: "192.0.2.9", mac: "00:C0:B7:00:00:01", vendor: "APC (Schneider)", kind: "onduleur" },
  { id: 5, name: "sw-a", vendor: "Cisco", kind: "switch", generation: "ancien" },
];

test("libellés et tons", () => {
  assert.equal(kindLabel("routeur"), "Routeur");
  assert.equal(kindLabel(undefined), "Inconnu");
  assert.equal(kindLabel("zinzin"), "zinzin");
  assert.equal(generationTone("ancien"), "warn");
  assert.equal(generationTone("recent"), "good");
  assert.equal(generationTone(null), "neutral");
  assert.equal(generationLabel(null), "—");
  assert.deepEqual(confidenceLabel(0.9), { text: "forte", tone: "good" });
  assert.deepEqual(confidenceLabel(0.5), { text: "moyenne", tone: "neutral" });
  assert.deepEqual(confidenceLabel(0.2), { text: "faible", tone: "warn" });
  assert.deepEqual(confidenceLabel(undefined), { text: "aucune", tone: "neutral" });
  assert.ok(isNetworkGear(rows[0]));
  assert.ok(!isNetworkGear(rows[2]));
});

test("summarizeFleet : compteurs et anciens équipements réseau", () => {
  const s = summarizeFleet(rows);
  assert.equal(s.total, 5);
  assert.equal(s.network, 3);
  assert.equal(s.byKind.switch, 2);
  assert.equal(s.byVendor.Cisco, 2);
  assert.equal(s.byVendor["?"], 1);
  assert.deepEqual(s.byGeneration, { recent: 1, ancien: 2, inconnue: 2 });
  assert.deepEqual(s.oldNetwork.map((r) => r.id), [2, 5]);
  assert.equal(s.unidentified, 1);
  assert.equal(summarizeFleet([]).total, 0);
  assert.equal(summarizeFleet(undefined).total, 0);
});

test("sortEquipment : équipements réseau d'abord, puis constructeur, puis nom", () => {
  const ids = sortEquipment(rows).map((r) => r.id);
  assert.deepEqual(ids, [1, 5, 2, 3, 4]);
  assert.equal(rows[0].id, 1); // l'original n'est pas modifié
});

test("filterEquipment : recherche, genre, génération, constructeur, réseau seulement", () => {
  assert.deepEqual(filterEquipment(rows, { q: "2950" }).map((r) => r.id), [2]);
  assert.deepEqual(filterEquipment(rows, { q: "BOB" }).map((r) => r.id), [3]);
  assert.deepEqual(filterEquipment(rows, { kind: "switch" }).map((r) => r.id), [2, 5]);
  assert.deepEqual(filterEquipment(rows, { generation: "inconnue" }).map((r) => r.id), [3, 4]);
  assert.deepEqual(filterEquipment(rows, { vendor: "?" }).map((r) => r.id), [3]);
  assert.deepEqual(filterEquipment(rows, { networkOnly: true }).map((r) => r.id), [1, 2, 5]);
  assert.deepEqual(filterEquipment(rows, { q: "4c:5e" }).map((r) => r.id), [1]);
  assert.equal(filterEquipment(rows, {}).length, 5);
});

test("displayName : nom, hôte, sysName, IP, MAC, identifiant", () => {
  assert.equal(displayName(rows[0]), "rtr-alpha");
  assert.equal(displayName(rows[2]), "vm-bob");
  assert.equal(displayName({ sys_name: "core", ip: "192.0.2.3" }), "core");
  assert.equal(displayName({ mac: "02:00:00:00:00:01" }), "02:00:00:00:00:01");
  assert.equal(displayName({ id: 7 }), "#7");
});

test("pollTone : synthèse du dernier relevé", () => {
  assert.deepEqual(pollTone(null), { tone: "neutral", text: "—" });
  assert.deepEqual(pollTone({ summary: { cpu_percent: 12, memory_percent: 75, alarms: [] } }), { tone: "good", text: "CPU 12 % · RAM 75 %" });
  assert.equal(pollTone({ summary: { cpu_percent: 90, alarms: [] } }).tone, "warn");
  assert.equal(pollTone({ summary: { temperature_c: 71, alarms: [] } }).tone, "warn");
  const bad = pollTone({ summary: { cpu_percent: 10, alarms: ["alimentation 1 : critical"] } });
  assert.equal(bad.tone, "bad");
  assert.match(bad.text, /1 alarme/);
  assert.deepEqual(pollTone({ summary: { alarms: [] }, errors: ["GET : délai"] }), { tone: "warn", text: "sans valeur" });
  assert.deepEqual(pollTone({ summary: { alarms: [] }, errors: [] }), { tone: "neutral", text: "relevé vide" });
});

test("topologyRows : liens lisibles, triés", () => {
  const t = { nodes: [{ id: 1, name: "sw-b" }, { id: 2, name: "rtr-alpha" }], links: [{ from: 1, to: 2, protocol: "lldp", local_port: "Fa0/24", remote_port: "ether1" }, { from: 1, to: 9, protocol: "fdb", local_port: "Fa0/1", remote_port: null }] };
  const r = topologyRows(t);
  assert.equal(r.length, 2);
  assert.deepEqual(r[0], { from: "sw-b", fromId: 1, to: "#9", toId: 9, via: "FDB", ports: "Fa0/1" });
  assert.equal(r[1].ports, "Fa0/24 ↔ ether1");
  assert.deepEqual(topologyRows(null), []);
});

test("previewSummary : compte par genre", () => {
  assert.equal(previewSummary([{ kind: "routeur" }, { kind: "switch" }, { kind: "switch" }, {}]), "2 switch, 1 routeur, 1 inconnu");
  assert.equal(previewSummary([]), "");
});
