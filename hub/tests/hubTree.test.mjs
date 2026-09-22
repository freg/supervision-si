// Tests de l'arborescence de disposition (livraison #516).
import test from "node:test";
import assert from "node:assert/strict";
import {
  buildCatalog, defaultTree, normalizeTree, resolveTree, themesOf, rootLeaves, themeOfLeaf,
  insertNode, removeNode, moveNode, cloneNode, updateNode, countRefs, exportTree, importTree,
  viewLabelsFromThemes, universeEntries, group, ref, ROOT_ID, REF_EXTERNAL_LINKS,
} from "../src/hubTree.js";

const THEMES = [
  { id: "supervision", name: "Supervision", icon: "🗺", entries: [{ view: "cortex", label: "Cortex" }, { view: "si-agent", label: "Agents hôtes" }, { view: "ups", label: "Onduleurs" }] },
  { id: "reseau", name: "Réseau", icon: "🕸", entries: [{ view: "network-agent", label: "Exploration" }, { front: "cisco", label: "Équipements Cisco" }] },
];
const FRONTS = [
  { id: "cisco", name: "Cisco", url: "https://x/cisco/", embeddable: true },
  { id: "tickets", name: "Portail tickets", url: "https://x/tickets/" },
  { id: "wiki", name: "Wiki maison", url: "https://wiki/" },
];
const catalog = (extra = {}) => buildCatalog({ availableViews: ["cortex", "si-agent", "network-agent"], viewLabels: viewLabelsFromThemes(THEMES), fronts: FRONTS, ...extra });

test("catalogue : vues disponibles, fronts, actions (admin filtré)", () => {
  const c = catalog();
  assert.equal(c.get("view:cortex").label, "Cortex");
  assert.equal(c.get("front:cisco").kind, "link");
  assert.ok(!c.has("view:ups"), "UPS non configuré : absent");
  assert.ok(!c.has("action:external-links"), "réservé aux administrateurs");
  assert.ok(catalog({ isAdmin: true }).has("action:external-links"));
  assert.ok(c.has(REF_EXTERNAL_LINKS));
});

test("arbre par défaut = thématiques #457, identifiants stables", () => {
  const t = defaultTree(THEMES);
  assert.equal(t.root.id, ROOT_ID);
  const ids = t.root.children.map((c) => c.id);
  assert.deepEqual(ids.slice(0, 2), ["r-aide", "r-tabs"]);
  assert.ok(ids.includes("theme:supervision") && ids.includes("theme:reseau") && ids.includes("theme:settings"));
  assert.equal(t.root.children.find((c) => c.id === "theme:reseau").children[1].ref, "front:cisco");
});

test("résolution : feuilles absentes omises, groupes vides supprimés, liens externes développés", () => {
  const t = defaultTree(THEMES);
  const r = resolveTree(t, catalog(), { leftover: [FRONTS[2]] });
  const themes = themesOf(r);
  assert.deepEqual(themes.map((x) => x.id), ["theme:supervision", "theme:reseau", "theme:settings"]);
  assert.deepEqual(themes[0].labels, ["Cortex", "Agents hôtes"]); // UPS omis
  assert.deepEqual(themes[1].entries.map((e) => e.kind), ["view", "link"]);
  const roots = rootLeaves(r);
  assert.deepEqual(roots.map((l) => l.id), ["action:aide", "action:tabs", "front:wiki"]);
  assert.equal(themeOfLeaf(themes, "view:si-agent"), "theme:supervision");
});

test("une feuille peut être référencée plusieurs fois, dans plusieurs groupes", () => {
  let t = defaultTree(THEMES);
  const ctx = group("Astreinte", [ref("view:cortex"), ref("view:si-agent"), ref("front:tickets")]);
  t = insertNode(t, ROOT_ID, ctx, 2);
  assert.equal(countRefs(t, "view:cortex"), 2);
  const themes = themesOf(resolveTree(t, catalog()));
  assert.equal(themes[0].name, "Astreinte");
  assert.deepEqual(themes[0].labels, ["Cortex", "Agents hôtes", "Portail tickets"]);
  assert.equal(themeOfLeaf(themes, "view:cortex"), themes[0].id, "premier groupe qui la contient");
  // même feuille deux fois dans le MÊME groupe : dédoublonnée dans les onglets
  t = insertNode(t, ctx.id, ref("view:cortex"));
  assert.equal(themesOf(resolveTree(t, catalog()))[0].count, 3);
});

test("sous-groupes : sections d'un menu, feuilles aplaties dans la thématique", () => {
  let t = defaultTree(THEMES);
  const sub = group("Terrain", [ref("view:network-agent")]);
  t = insertNode(t, "theme:supervision", sub);
  const r = resolveTree(t, catalog());
  const sup = themesOf(r)[0];
  assert.deepEqual(sup.labels, ["Cortex", "Agents hôtes", "Exploration"]);
  assert.equal(sup.sections.filter((s) => s.type === "group").length, 1);
});

test("édition : déplacer, retirer, dupliquer, renommer ; garde-fous", () => {
  let t = defaultTree(THEMES);
  const before = exportTree(t);
  assert.equal(moveNode(t, ROOT_ID, "theme:reseau", 0), t, "la racine ne bouge pas");
  assert.equal(moveNode(t, "theme:reseau", "theme:reseau", 0), t, "pas dans soi-même");
  const leafId = t.root.children.find((c) => c.id === "theme:reseau").children[0].id;
  assert.equal(moveNode(t, "theme:reseau", leafId, 0), t, "pas dans sa descendance (feuille = pas un groupe non plus)");
  t = moveNode(t, "theme:reseau", ROOT_ID, 0);
  assert.equal(t.root.children[0].id, "theme:reseau");
  // déplacement dans le même parent vers l'avant : index corrigé
  t = moveNode(t, "r-aide", ROOT_ID, 5);
  assert.equal(t.root.children[4].id, "r-aide");
  t = moveNode(t, "r-aide", ROOT_ID, 0);
  assert.equal(t.root.children[0].id, "r-aide");
  const copy = cloneNode(t.root.children.find((c) => c.id === "theme:reseau"));
  assert.notEqual(copy.id, "theme:reseau");
  assert.equal(copy.children.length, 2);
  t = insertNode(t, ROOT_ID, copy);
  assert.equal(countRefs(t, "front:cisco"), 2);
  t = updateNode(t, copy.id, { label: "Réseau (copie)", icon: "🔁" });
  assert.equal(t.root.children.at(-1).label, "Réseau (copie)");
  t = removeNode(t, copy.id);
  assert.equal(countRefs(t, "front:cisco"), 1);
  assert.equal(removeNode(t, ROOT_ID), t);
  assert.equal(exportTree(defaultTree(THEMES)), before, "l'édition est immuable, le défaut est reproductible");
});

test("import : JSON malformé refusé, arbre étranger normalisé (ids manquants/doublons, types inconnus)", () => {
  assert.equal(importTree("{"), null);
  assert.equal(importTree("[]"), null);
  assert.equal(importTree('{"x":1}'), null);
  const t = importTree(JSON.stringify({ root: { type: "group", label: 5, children: [
    { type: "ref", ref: "view:cortex" }, { type: "ref", ref: "view:cortex", id: "dup" }, { type: "ref", id: "dup", ref: "view:si-agent" },
    { type: "bizarre" }, { type: "ref" }, { label: "Sans type", children: [{ type: "ref", ref: "front:tickets" }] },
  ] } }));
  assert.equal(t.root.id, ROOT_ID);
  assert.equal(t.root.label, "5");
  assert.equal(t.root.children.length, 4);
  const ids = new Set();
  const walk = (n) => { assert.ok(!ids.has(n.id)); ids.add(n.id); (n.children || []).forEach(walk); };
  walk(t.root);
  assert.equal(t.root.children[3].type, "group");
  assert.equal(normalizeTree({ children: [] }).root.id, ROOT_ID, "forme sans enveloppe acceptée");
});

test("résolution défensive : arbre absent", () => {
  const r = resolveTree(null, catalog());
  assert.deepEqual(themesOf(r), []);
  assert.deepEqual(rootLeaves(r), []);
});

test("universeEntries (#538) : tout le catalogue sauf les liens automatiques, tri alpha ou ordre d'ajout, filtre sans accents", () => {
  const cat = buildCatalog({ availableViews: ["cortex", "ups", "network-agent"], viewLabels: viewLabelsFromThemes(THEMES),
    fronts: [{ id: "cisco", name: "Équipements Cisco", url: "https://x", onClick: () => {} }], isAdmin: false });
  const since = { cortex: 462, ups: 415, "network-agent": 236, "action:aide": 105 };
  const alpha = universeEntries(cat, { sort: "alpha", since });
  assert.ok(!alpha.some((e) => e.kind === "auto"));
  assert.deepEqual(alpha.slice(0, 3).map((e) => e.label), ["Accueil : thématiques / toutes les tuiles", "Aide", "Cortex"]);
  assert.equal(alpha.find((e) => e.id === "view:cortex").since, 462);
  const added = universeEntries(cat, { sort: "added", since });
  assert.deepEqual(added.slice(0, 3).map((e) => e.id), ["action:aide", "view:network-agent", "view:ups"]);
  assert.equal(added[added.length - 1].since, null); // inconnus à la fin
  assert.deepEqual(universeEntries(cat, { query: "equipements" }).map((e) => e.id), ["front:cisco"]);
  assert.ok(!cat.has("action:external-links")); // non admin
});
