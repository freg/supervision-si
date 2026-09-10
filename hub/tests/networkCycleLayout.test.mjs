import { test } from "node:test";
import assert from "node:assert/strict";
import {
  MENU_STATES, DEFAULT_MENU_STATE, DEFAULT_VIEW_MODE,
  nextMenuState, graphHeightPx, GRAPH_HEIGHTS,
  loadLayoutPreference, saveLayoutPreference, LAYOUT_STORAGE_KEY, hiddenMenuLabel,
} from "../src/networkCycleLayout.js";

function fakeStorage(initial = {}) {
  const data = { ...initial };
  return { getItem: (k) => (k in data ? data[k] : null), setItem: (k, v) => { data[k] = String(v); }, data };
}

test("le menu est réduit par défaut (le détail est ce qu'on lit)", () => {
  assert.equal(DEFAULT_MENU_STATE, "reduced");
  assert.deepEqual(loadLayoutPreference(undefined), { viewMode: DEFAULT_VIEW_MODE, menuState: "reduced" });
});

test("toggle alterne grand/réduit, hide masque, show restaure l'état d'avant", () => {
  assert.equal(nextMenuState("reduced", "toggle"), "expanded");
  assert.equal(nextMenuState("expanded", "toggle"), "reduced");
  assert.equal(nextMenuState("hidden", "toggle"), "expanded");
  assert.equal(nextMenuState("expanded", "hide"), "hidden");
  assert.equal(nextMenuState("hidden", "show", "expanded"), "expanded");
  assert.equal(nextMenuState("hidden", "show", "reduced"), "reduced");
  assert.equal(nextMenuState("hidden", "show", "hidden"), "reduced", "jamais hidden → hidden");
  assert.equal(nextMenuState("hidden", "show", undefined), "reduced");
  assert.equal(nextMenuState("expanded", "show"), "expanded", "show sans masquage : sans effet");
  assert.equal(nextMenuState("bidon", "inconnue"), DEFAULT_MENU_STATE);
  assert.equal(nextMenuState("expanded", "inconnue"), "expanded");
});

test("chaque état du menu est atteignable et sort de MENU_STATES", () => {
  const seen = new Set();
  let s = "reduced";
  for (const a of ["toggle", "hide", "show", "toggle", "hide"]) { s = nextMenuState(s, a, "expanded"); seen.add(s); assert.ok(MENU_STATES.includes(s)); }
  assert.deepEqual([...seen].sort(), ["expanded", "hidden", "reduced"]);
});

test("hauteur du schéma : moitié haute en grand, un tiers en réduit, bornée", () => {
  assert.equal(graphHeightPx("expanded", 900), 450);
  assert.equal(graphHeightPx("reduced", 900), 270);
  assert.equal(graphHeightPx("expanded", 400), GRAPH_HEIGHTS.expanded.min, "borne basse");
  assert.equal(graphHeightPx("expanded", 3000), GRAPH_HEIGHTS.expanded.max, "borne haute");
  assert.equal(graphHeightPx("reduced", 200), GRAPH_HEIGHTS.reduced.min);
  assert.equal(graphHeightPx("hidden", 900), graphHeightPx("reduced", 900), "état sans hauteur → réduit");
  assert.ok(graphHeightPx("reduced", 900) < graphHeightPx("expanded", 900));
});

test("préférence de disposition : lecture tolérante, écriture validée", () => {
  const st = fakeStorage();
  assert.equal(saveLayoutPreference(st, { viewMode: "graphique", menuState: "expanded" }), true);
  assert.deepEqual(loadLayoutPreference(st), { viewMode: "graphique", menuState: "expanded" });
  assert.equal(saveLayoutPreference(st, { viewMode: "bidon", menuState: "expanded" }), false);
  assert.deepEqual(loadLayoutPreference(st), { viewMode: "graphique", menuState: "expanded" }, "écriture refusée = rien changé");
  assert.deepEqual(loadLayoutPreference(fakeStorage({ [LAYOUT_STORAGE_KEY]: "{pas du json" })), { viewMode: "classique", menuState: "reduced" });
  assert.deepEqual(loadLayoutPreference(fakeStorage({ [LAYOUT_STORAGE_KEY]: JSON.stringify({ viewMode: "graphique", menuState: "n-existe-pas" }) })), { viewMode: "graphique", menuState: "reduced" });
  const broken = { getItem: () => { throw new Error("quota"); }, setItem: () => { throw new Error("quota"); } };
  assert.deepEqual(loadLayoutPreference(broken), { viewMode: "classique", menuState: "reduced" });
  assert.equal(saveLayoutPreference(broken, { viewMode: "classique", menuState: "hidden" }), false);
});

test("la languette nomme ce qu'elle rouvre", () => {
  assert.match(hiddenMenuLabel("graphique"), /schéma/);
  assert.match(hiddenMenuLabel("classique"), /menu/);
});
