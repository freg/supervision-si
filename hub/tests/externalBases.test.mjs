import test from "node:test";
import assert from "node:assert/strict";
import {
  SOURCES, availableSources, countNodes, findPath, relevantIds, pruneToIds, pruneToActive, limitDepth, nodeSummary,
  shortLabel, usagePercent, usageTone, sortRoots, rootCounts,
} from "../src/externalBases.js";

const TREE = {
  id: "s1", type: "section", name: "Siège", raw: { description: "site principal" }, children: [
    { id: 10, type: "subnet", name: "192.168.1.0/24", raw: { state: 1, subnet: "192.168.1.0", usage: { used: 180, maxhosts: 254 } }, children: [
      { id: 11, type: "subnet", name: "192.168.1.0/25", raw: { state: 0 }, children: [] },
      { id: 12, type: "subnet", name: "192.168.1.128/25", raw: { state: 1, usedPercent: 95 }, children: [] },
    ] },
    { id: 20, type: "subnet", name: "10.0.0.0/8", raw: { state: 0 }, children: [{ id: 21, type: "subnet", name: "10.1.0.0/16", raw: { state: 0 }, children: [] }] },
    { id: "s2", type: "section", name: "Annexe", raw: {}, children: [] },
  ],
};

test("sources disponibles selon les URL d'API configurées", () => {
  assert.equal(SOURCES.length, 5);
  assert.deepEqual(availableSources({ ipam: "http://x", cacti: "http://y" }).map((s) => s.id), ["ipam", "cacti"]);
  assert.deepEqual(availableSources(null), []);
});

test("parcours : compteurs, profondeur, chemin", () => {
  const c = countNodes(TREE);
  assert.equal(c.total, 7); assert.equal(c.depth, 2); assert.deepEqual(c.byType, { section: 2, subnet: 5 });
  assert.deepEqual(findPath(TREE, 12).map((n) => n.id), ["s1", 10, 12]);
  assert.deepEqual(findPath(TREE, "nope"), []);
});

test("filtre texte : ancêtres et descendants du match conservés, accents ignorés", () => {
  assert.equal(relevantIds(TREE, "  "), null);
  const ids = relevantIds(TREE, "192.168.1.0/24");
  assert.deepEqual([...ids].sort(), ["s1", 10, 11, 12].sort(), "chemin + tout le sous-arbre du match");
  const pruned = pruneToIds(TREE, ids);
  assert.deepEqual(pruned.children.map((n) => n.id), [10]);
  assert.equal(pruneToIds(TREE, null), TREE);
  assert.equal(relevantIds(TREE, "siege").size, 7, "match sur la racine (sans accent) : toute sa descendance reste visible");
  assert.equal(relevantIds(TREE, "site principal").has("s1"), true, "la description est cherchée");
  assert.equal(relevantIds({ id: 1, name: "x", children: [] }, "zzz").size, 0);
});

test("actifs seulement : sous-réseaux inactifs sans descendant actif retirés, racine gardée", () => {
  const p = pruneToActive(TREE);
  assert.deepEqual(p.children.map((n) => n.id), [10], "10.0.0.0/8 inactif et sa branche disparaissent, la section vide Annexe aussi");
  assert.deepEqual(p.children[0].children.map((n) => n.id), [12]);
  assert.equal(pruneToActive(null), null);
});

test("profondeur bornée : nœud « … +N » replié, dépliable", () => {
  const l = limitDepth(TREE, 1);
  const sub = l.children.find((n) => n.id === 10);
  assert.equal(sub.children.length, 1);
  assert.equal(sub.children[0].type, "more");
  assert.equal(sub.children[0].raw.hidden, 2);
  const l2 = limitDepth(TREE, 1, new Set([10]));
  assert.equal(l2.children.find((n) => n.id === 10).children.length, 2, "déplié malgré la borne");
  assert.equal(limitDepth(TREE, 5).children[1].children.length, 1);
});

test("fiche, libellés, occupation, racines", () => {
  const s = nodeSummary(TREE.children[0]);
  assert.equal(s.descendants, 2); assert.equal(s.type, "subnet");
  assert.equal(shortLabel("abcdefghijklmnopqrstuvwxyz", 10), "abcdefghi…");
  assert.equal(usagePercent(TREE.children[0]), 70.9);
  assert.equal(usagePercent(TREE.children[0].children[1]), 95);
  assert.equal(usagePercent(TREE), null);
  assert.deepEqual([usageTone(95), usageTone(70.9), usageTone(10), usageTone(null)], ["bad", "warn", "good", "neutral"]);
  const roots = sortRoots([{ id: 2, name: "zeta", subnetCount: 3, childSectionCount: 1 }, { id: 1, name: "Alpha", description: "x" }], "");
  assert.deepEqual(roots.map((r) => r.id), [1, 2]);
  assert.deepEqual(sortRoots(roots, "ZET").map((r) => r.id), [2]);
  assert.deepEqual(rootCounts(roots[1]), ["3 subnet", "1 child section"]);
});
