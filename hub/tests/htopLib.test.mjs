import { test } from "node:test";
import assert from "node:assert/strict";
import { niveau, niveauHote, trier, grouper, invites, projeter, sparkPath, maxDisque, go, pctOf } from "../src/htopLib.js";

const S = { cpu: 90, memoire: 92, swap: 60, iowait: 30, steal: 20, charge: 2 };
const PVE_A = { nom: "pve-a", nature: "pve", ncpu: 16, cpu: 40, memoire: [128e9, 70e9, 20e9], memoire_pct: 39.1, pic_24h: { cpu: 60, cpu_p95: 45, memoire: 50, minutes: 1440 },
  invites: [[102, "app1", "ct", 12, 2, 9e9, 6e9, 8e9]], pics_invites: { 102: [3, 7e9] }, disques: [["/", 100, 50]], pools: [["rpool", 1000, 870, "ONLINE"]] };
const PVE_B = { nom: "pve-b", nature: "pve", ncpu: 8, cpu: 10, memoire: [64e9, 10e9, 0], memoire_pct: 15.6, pic_24h: null,
  invites: [[201, "app2", "vm", 25, 2, 4e9, 4e9, 4e9]], pics_invites: {} };
const CT = { nom: "APP1", nature: "ct", cpu: 95, memoire_pct: 20 };
const VM = { nom: "seule", nature: "vm", cpu: null, memoire_pct: 93, muet: false };

test("niveaux", () => {
  assert.equal(niveau(99, 90, 98).tone, "critical");
  assert.equal(niveau(91, 90, 98).label, "au seuil");
  assert.equal(niveau(75, 90).tone, "near");
  assert.equal(niveau(null, 90).tone, "");
  assert.equal(niveauHote(CT, S), "warning");
  assert.equal(niveauHote(VM, S), "warning");
  assert.equal(niveauHote({ muet: true }, S), "critical");
  assert.equal(niveauHote(PVE_B, S), "");
});

test("tri et regroupement sous le Proxmox", () => {
  assert.deepEqual(trier([PVE_A, CT, VM], "cpu").map((h) => h.nom), ["APP1", "pve-a", "seule"]);   // vide en bas
  assert.deepEqual(trier([PVE_A, CT, VM], "nom", 1).map((h) => h.nom), ["APP1", "pve-a", "seule"]);
  assert.deepEqual(grouper([VM, CT, PVE_B, PVE_A], "nom", 1).map((r) => `${r.ind}${r.h.nom}`), ["0pve-a", "1APP1", "0pve-b", "0seule"]);
  assert.equal(maxDisque(PVE_A), 87);
  assert.equal(maxDisque({}), null);
});

test("projection : invités d'un autre nœud sur la cible", () => {
  assert.equal(invites([PVE_A, PVE_B]).length, 2);
  assert.deepEqual(invites([PVE_A])[0], { pve: "pve-a", vmid: 102, nom: "app1", type: "ct", coeurs: 2, mem: 6e9, limite: 8e9, pic_coeurs: 3, pic_mem: 7e9 });
  const p = projeter([PVE_A, PVE_B], "pve-b", [{ pve: "pve-a", vmid: "102" }, { pve: "pve-b", vmid: 201 }]);   // un invité déjà sur la cible est ignoré
  assert.equal(p.invites.length, 1);
  assert.deepEqual(p.cpu_pic, [10, 47.5]);          // pas d'historique : instantané + 3 cœurs / 8
  assert.deepEqual(p.mem_pic, [15.6, 26.5]);
  assert.deepEqual(p.alloue, [6.3, 18.8]);
  assert.equal(p.verdict, "ok");
  const q = projeter([PVE_A, PVE_B], "pve-a", [{ pve: "pve-b", vmid: 201 }]);
  assert.deepEqual(q.cpu_p95, [45, 57.5]);
  assert.equal(q.minutes, 1440);
  assert.equal(q.verdict, "ok");
  const pointe = { ...PVE_B, nom: "pve-d", invites: [[400, "pointe", "ct", 0, 5, 0, 1e9, 2e9]], pics_invites: { 400: [5, 1e9] } };
  assert.equal(projeter([PVE_A, pointe], "pve-a", [{ pve: "pve-d", vmid: 400 }]).verdict, "juste");   // pic 91 % : marge faible
  const lourd = { ...PVE_B, nom: "pve-c", invites: [[300, "gros", "ct", 0, 12, 0, 60e9, 64e9]], pics_invites: {} };
  assert.equal(projeter([PVE_A, lourd], "pve-a", [{ pve: "pve-c", vmid: 300 }]).verdict, "non");
  assert.equal(projeter([PVE_A], "absent", []), null);
});

test("courbe et formats", () => {
  assert.equal(sparkPath([0, 100], 10, 10), "M0.0,10.0 L10.0,0.0");
  assert.equal(sparkPath([50, null, 50], 10, 10), "M0.0,5.0 M10.0,5.0");
  assert.equal(sparkPath([]), "");
  assert.equal(go(1.5e9), "1.5 Go");
  assert.equal(pctOf(1, 0), null);
});
