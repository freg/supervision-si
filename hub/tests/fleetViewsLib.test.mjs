import test from "node:test";
import assert from "node:assert/strict";
import { suggestViews, sortHtop, rowTone, moveAgent, viewAgents, gpuCells } from "../src/fleetViewsLib.js";

const fleet = [
  { agent_id: "pve10", plugin_ids: ["proxmox"], os: "Debian GNU/Linux 12" },
  { agent_id: "pcia", plugin_ids: ["ollama"], os: "Ubuntu 24.04", label: "pcia #perso" },
  { agent_id: "srv-web", os: "Debian GNU/Linux 12" },
  { agent_id: "pc-a", os: "Windows 11 Pro" },
  { agent_id: "ad1", os: "Windows Server 2019" },
  { agent_id: "mac", os: "macOS 15", label: "mon mac #perso" },
];
const V = [{ id: "serveurs", label: "Serveurs", groups: [] }, { id: "postes", label: "Postes", groups: [] }, { id: "ia", label: "Serveurs d'IA", groups: [] },
  { id: "perso", label: "Postes personnels", groups: [] }, { id: "autre", label: "Autre", groups: [] }];

test("#753 : rangement proposé par catégorie, OS, sondes et étiquette #perso", () => {
  const s = suggestViews(V, fleet);
  const g = (id) => Object.fromEntries(s.find((v) => v.id === id).groups.map((x) => [x.name, x.agents]));
  assert.deepEqual(g("serveurs"), { "Proxmox (PVE / PBS)": ["pve10"], Linux: ["srv-web"], "Windows Server": ["ad1"] });
  assert.deepEqual(g("postes"), { Windows: ["pc-a"] });
  assert.deepEqual(g("ia"), { Ollama: ["pcia"] });
  assert.deepEqual(g("perso"), { "Mes postes": ["mac", "pcia"] });
  assert.deepEqual(s.find((v) => v.id === "autre").groups, []);
  const kept = suggestViews([{ id: "serveurs", label: "S", groups: [{ name: "x", agents: ["a"] }] }], fleet);
  assert.deepEqual(kept[0].groups, [{ name: "x", agents: ["a"] }]);
});

test("#753 : tri, pastille, déplacement", () => {
  const rows = [{ agent_id: "b", cpu_pct: 10 }, { agent_id: "a", cpu_pct: null }, { agent_id: "c", cpu_pct: 90, hostname: "Zed" }];
  assert.deepEqual(sortHtop(rows, "cpu_pct").map((r) => r.agent_id), ["c", "b", "a"]);
  assert.deepEqual(sortHtop(rows, "name", -1).map((r) => r.agent_id), ["a", "b", "c"]);
  assert.equal(rowTone({ online: "offline" }), "critical");
  assert.equal(rowTone({ online: "online", disk_max_pct: 88 }), "warning");
  assert.equal(rowTone({ online: "online", failed_services: 0, disk_max_pct: 40 }), "good");
  const v = { groups: [{ name: "A", agents: ["x", "y"] }, { name: "B", agents: [] }] };
  assert.deepEqual(moveAgent(v, "x", 1).groups.map((g) => g.agents), [["y"], ["x"]]);
  assert.deepEqual(moveAgent(v, "x", null).groups.map((g) => g.agents), [["y"], []]);
  assert.deepEqual([...viewAgents(v)], ["x", "y"]);
});

test("gpuCells : mémoire vidéo, charge, température, carte sans pilote (#782)", () => {
  const c = gpuCells({ gpus: [
    { name: "NVIDIA RTX A4500", driver: "nvidia", vram_total: 20 * 1073741824, vram_used: 19.5 * 1073741824, vram_pct: 97.5, util_pct: 88.4, temp_c: 66, power_w: 181.2 },
    { name: "Intel Corporation Device", driver: null },
    { name: "NVIDIA Corporation GA102", driver: "vfio-pci", passthrough: true },
    { name: "x", driver: "nvidia", temp_c: 90 }] });
  assert.equal(c[0].name, "RTX A4500"); assert.equal(c[0].label, "20 / 20 Go · 88 % · 66 °C · 181 W"); assert.equal(c[0].tone, "warning");
  assert.equal(c[1].label, "sans pilote"); assert.equal(c[1].tone, "warning"); assert.equal(c[1].name, "Intel Device");
  assert.equal(c[2].label, "passée à une VM"); assert.equal(c[3].tone, "critical");
  assert.deepEqual(gpuCells({}), []);
});
