import test from "node:test";
import assert from "node:assert/strict";
import { businessTree, filterBusinessTree, pathsOfLeaf, reachability, PATHS, ROOTS } from "../src/hubBusiness.js";
import { buildCatalog, viewLabelsFromThemes } from "../src/hubTree.js";
import { THEMES } from "../src/hubThemes.js";

const allViews = THEMES.flatMap((t) => t.entries.filter((e) => e.view).map((e) => e.view));
const fronts = THEMES.flatMap((t) => t.entries.filter((e) => e.front).map((e) => ({ id: e.front, name: e.label, url: "https://x" })));
const catalog = buildCatalog({ availableViews: allViews, viewLabels: viewLabelsFromThemes(THEMES), fronts, isAdmin: true });

test("chaque tuile déclarée a un chemin valide et est joignable par au moins deux chemins", () => {
  const branchIds = new Set();
  const walk = (node, path) => { branchIds.add(path); (node.children || node.branches || []).forEach((c) => walk(c, `${path}/${c.id}`)); };
  ROOTS.forEach((r) => walk(r, r.id));
  for (const [ref, ps] of Object.entries(PATHS)) for (const p of ps) assert.ok(branchIds.has(p), `${ref} → ${p} inconnu`);
  const r = reachability(catalog);
  const single = [...r.entries()].filter(([, n]) => n < 2).map(([k]) => k);
  // les actions de réglage n'ont qu'un chemin (services/hub) : c'est voulu ; toute VUE / FRONT en a deux
  assert.deepEqual(single.filter((k) => !k.startsWith("action:")).filter((k) => !["view:snmp", "view:vigilance", "view:logs", "view:history", "view:memory", "view:netmap-orchestrator", "view:fusion", "view:proxmox", "view:external-bases", "view:classifier", "view:retro", "front:dba", "view:ent", "view:ged", "view:file-manager", "view:imap", "front:assistant", "front:tickets", "front:demande", "view:rights", "view:accounts", "view:notifications", "view:backup-restore", "front:vault", "front:vault-admin", "front:keycloak-admin", "front:ldap-admin"].includes(k)), []);
  for (const leaf of catalog.values()) if (leaf.kind !== "auto") assert.ok(r.get(leaf.id) >= 1, `${leaf.id} injoignable`);
});

test("déploiement : une feuille sous plusieurs branches, « aussi sous », branches vides retirées", () => {
  const t = businessTree(catalog);
  assert.deepEqual(t.roots.map((r) => r.id), ["equipements", "services", "droits", "etats", "cortex"]);
  const paths = pathsOfLeaf(t, "front:mikrotik");
  assert.deepEqual(paths, ["equipements/reseau/routeurs", "droits/acces"]);
  const routeurs = t.roots[0].children.find((c) => c.id === "equipements/reseau").children.find((c) => c.id === "equipements/reseau/routeurs");
  assert.deepEqual(routeurs.leaves.map((l) => l.label), ["Redirections NAT", "Routeurs MikroTik"]);
  assert.deepEqual(routeurs.leaves[1].also, ["Droits et accès › Accès aux équipements"]);
  assert.ok(t.roots.every((r) => r.count > 0));
  // catalogue réduit : la branche « Switchs » disparaît sans Cisco
  const small = buildCatalog({ availableViews: ["cortex"], viewLabels: { cortex: "Cortex" }, fronts: [], isAdmin: false });
  const ts = businessTree(small);
  assert.equal(ts.roots.find((r) => r.id === "equipements").children.length, 0);
  assert.deepEqual(ts.roots.find((r) => r.id === "cortex").children.find((c) => c.id === "cortex/correlation").leaves.map((l) => l.label), ["Cortex"]);
});

test("repli « Autres » pour une feuille sans chemin déclaré, filtre début de mot", () => {
  const cat = buildCatalog({ availableViews: ["nouvelle-vue", "nebula"], viewLabels: { "nouvelle-vue": "Nouvelle vue", nebula: "Nebula" }, fronts: [], isAdmin: false });
  const t = businessTree(cat, { themeOf: (ref) => (ref === "view:nouvelle-vue" ? "reseau" : null) });
  const eq = t.roots.find((r) => r.id === "equipements");
  assert.deepEqual(eq.children.find((c) => c.label === "Autres").leaves.map((l) => l.label), ["Nouvelle vue"]);
  const f = filterBusinessTree(businessTree(catalog), "n");
  const labels = [];
  const walk = (n) => { n.leaves.forEach((l) => labels.push(l.label)); n.children.forEach(walk); };
  f.roots.forEach(walk);
  assert.ok(labels.includes("Nebula") && labels.includes("Notifications"));
  assert.ok(!labels.includes("Cortex"));
  const f2 = filterBusinessTree(businessTree(catalog), "routeur");
  assert.deepEqual(f2.roots.map((r) => r.id), ["equipements", "droits"]);  // branche « Routeurs » + « Routeurs MikroTik » sous Accès
  const full = businessTree(catalog);
  assert.equal(filterBusinessTree(full, ""), full);
});
