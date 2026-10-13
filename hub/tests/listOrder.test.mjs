import test from "node:test";
import assert from "node:assert/strict";
import { orderItems, severityRank, compareText, timeValue, validMode } from "../src/listOrder.js";
import { agentCategory, groupFleet, proxmoxRole, agentSeverity } from "../src/siAgent.js";

const items = [
  { name: "beta", at: "2026-10-12T10:00:00Z", severity: "warning" },
  { name: "Alpha", at: "2026-10-13T08:00:00Z", severity: "info" },
  { name: "gamma", at: null, severity: "critical" },
  { name: "Écluse", at: "2026-10-11T08:00:00Z", severity: "error" },
];

test("ordre alphabétique par défaut, sans casse ni accents, vides à la fin", () => {
  assert.deepEqual(orderItems(items).map((i) => i.name), ["Alpha", "beta", "Écluse", "gamma"]);
  assert.deepEqual(orderItems([{ name: "" }, { name: "b" }, { name: "a" }]).map((i) => i.name), ["a", "b", ""]);
  assert.ok(compareText("item 2", "item 10") < 0);                 // ordre numérique naturel
});

test("antéchronologique : le plus récent d'abord, sans date à la fin", () => {
  assert.deepEqual(orderItems(items, "recent").map((i) => i.name), ["Alpha", "beta", "Écluse", "gamma"]);
  assert.equal(timeValue(1791816150), 1791816150000);
});

test("gravité : critique, erreur, avertissement, info ; vocabulaires mélangés", () => {
  assert.deepEqual(orderItems(items, "severity").map((i) => i.name), ["gamma", "Écluse", "beta", "Alpha"]);
  assert.ok(severityRank("CRIT") < severityRank("warn") && severityRank("warn") < severityRank("ok"));
  assert.equal(severityRank(undefined), severityRank("inconnu"));
  assert.equal(validMode("nimporte"), "alpha");
});

test("catégories d'agents : rôle et OS, étiquette prioritaire", () => {
  assert.equal(agentCategory({ agent_id: "pve10", os: "Debian GNU/Linux 12" }), "proxmox");
  assert.equal(agentCategory({ agent_id: "srv-sauv", plugin_ids: ["pbs"] }), "proxmox");
  assert.equal(agentCategory({ agent_id: "pc-site", os: "Ubuntu 24.04", plugin_ids: ["wifi-probe"] }), "sonde");
  assert.equal(agentCategory({ agent_id: "rpi-1", hardware_model: "Raspberry Pi 4" }), "sonde");
  assert.equal(agentCategory({ agent_id: "web1", os: "Debian 12", virtualization: "kvm" }), "vm");
  assert.equal(agentCategory({ agent_id: "poste", os: "Windows 10 Pro" }), "windows");
  assert.equal(agentCategory({ agent_id: "poste", os: "Windows 10 Pro", virtualization: "none" }), "windows");
  assert.equal(agentCategory({ agent_id: "i9", os: "Ubuntu 24.04", virtualization: "none" }), "linux");
  assert.equal(agentCategory({ agent_id: "mac", os: "macOS 15" }), "other");
  assert.equal(agentCategory({ agent_id: "web1", os: "Debian", virtualization: "kvm", label: "relais #sonde" }), "sonde");
  assert.equal(proxmoxRole({ agent_id: "pbs10" }), "PBS");
  assert.equal(proxmoxRole({ agent_id: "pve11", plugin_ids: ["proxmox"] }), "PVE");
});

test("groupes dans l'ordre fixe, contenu trié selon l'ordre choisi, compteurs", () => {
  const fleet = [
    { agent_id: "zeta", os: "Debian", risks: { state: "warning" }, online: "online" },
    { agent_id: "pve11", os: "Debian", risks: { state: "ok" }, online: "offline" },
    { agent_id: "alpha", os: "Debian", risks: { state: "critical" }, online: "online" },
    { agent_id: "win", os: "Windows 11" },
  ];
  const g = groupFleet(fleet, (xs) => orderItems(xs, "severity", { name: (a) => a.agent_id, severity: agentSeverity }));
  assert.deepEqual(g.map((x) => x.id), ["proxmox", "windows", "linux"]);
  assert.deepEqual(g[2].agents.map((a) => a.agent_id), ["alpha", "zeta"]);
  assert.deepEqual(g[0].counts, { total: 1, critical: 0, offline: 1, warning: 0 });
});
