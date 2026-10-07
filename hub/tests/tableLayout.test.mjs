// Tests #698 : colonnes configurables (largeur, masquage, mémorisation par compte).
import { test } from "node:test";
import assert from "node:assert/strict";
import { normalizeLayout, toggleHidden, setWidth, resetWidth, visibleColumns, clampWidth, isDefault, configureTablePrefs, loadAccount, saveLayout } from "../src/tableLayout.js";

const COLS = [{ id: "agent", label: "Agent", fixed: true }, { id: "site", label: "Site" }, { id: "cpu", label: "CPU" }, { id: "actions", label: "", fixed: true }];

test("normalisation : colonnes inconnues, largeurs bornées, colonnes fixes jamais masquées", () => {
  const l = normalizeLayout({ widths: { site: 10, cpu: "300", disparue: 200, agent: 99999 }, hidden: ["cpu", "cpu", "agent", "disparue"] }, COLS);
  assert.deepEqual(l, { widths: { site: 40, cpu: 300, agent: 1200 }, hidden: ["cpu"] });
  assert.deepEqual(normalizeLayout(null, COLS), { widths: {}, hidden: [] });
  assert.deepEqual(normalizeLayout("n'importe quoi", COLS), { widths: {}, hidden: [] });
  assert.equal(clampWidth(undefined), 40);
});

test("masquer / réafficher, largeur, retour à l'automatique", () => {
  let l = normalizeLayout(null, COLS);
  l = toggleHidden(l, COLS, "site");
  assert.deepEqual(visibleColumns(COLS, l).map((c) => c.id), ["agent", "cpu", "actions"]);
  assert.equal(toggleHidden(l, COLS, "agent"), l);                   // fixe : sans effet
  l = toggleHidden(l, COLS, "site");
  assert.ok(isDefault(l));
  l = setWidth(l, "cpu", 151.6);
  assert.equal(l.widths.cpu, 152);
  assert.ok(isDefault(resetWidth(l, "cpu")));
});

test("jamais un tableau vide : sans colonne fixe, tout masquer est annulé", () => {
  const cols = [{ id: "a", label: "A" }, { id: "b", label: "B" }];
  assert.deepEqual(normalizeLayout({ hidden: ["a", "b"] }, cols).hidden, []);
});

test("mémorisation : un GET pour tous les tableaux, une écriture regroupée par tableau, clé table.<id>", async () => {
  const calls = [];
  const fake = async (url, opts) => { calls.push([url, opts?.method || "GET", opts?.body]); return { ok: true, json: async () => ({ theme: "dark", "table.agents": { widths: { cpu: 90 }, hidden: [] } }) }; };
  globalThis.fetch = fake;
  configureTablePrefs({ apiBase: "/api/prefs", user: "alice" });
  assert.deepEqual(await loadAccount("agents", fake), { widths: { cpu: 90 }, hidden: [] });
  assert.equal(await loadAccount("autre", fake), null);
  assert.equal(calls.length, 1);
  saveLayout("agents", { widths: { cpu: 100 }, hidden: [] }, fake, 10);
  saveLayout("agents", { widths: { cpu: 120 }, hidden: ["site"] }, fake, 10);
  saveLayout("autre", { widths: {}, hidden: [] }, fake, 10);
  await new Promise((r) => setTimeout(r, 40));
  const puts = calls.filter((c) => c[1] === "PUT");
  assert.equal(puts.length, 2);
  assert.equal(puts[0][0], "/api/prefs/preferences?user=alice");
  assert.deepEqual(JSON.parse(puts[0][2]), { "table.agents": { widths: { cpu: 120 }, hidden: ["site"] } });
  assert.deepEqual(JSON.parse(puts[1][2]), { "table.autre": null });          // réglages par défaut : clé effacée
  assert.deepEqual(await loadAccount("agents", fake), { widths: { cpu: 120 }, hidden: ["site"] });   // cache mis à jour
});
