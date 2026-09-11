import test from "node:test";
import assert from "node:assert/strict";
import { THEMES, buildThemes, absorbedFrontIds, themeViewMode, isThemeViewMode, themeIdOf, themeOfView, findTheme, normalizeHomeMode } from "../src/hubThemes.js";

test("six thématiques, sans doublon de vue ni de front", () => {
  assert.equal(THEMES.length, 6);
  const views = THEMES.flatMap((t) => t.entries.map((e) => e.view || `front:${e.front}`));
  assert.equal(new Set(views).size, views.length);
  assert.ok(views.includes("si-proxy") && views.includes("supervision-si") && views.includes("front:tickets"));
  assert.ok(views.includes("front:projeqtor")); // thématique dédiée, #482
});

test("viewMode thématique", () => {
  assert.equal(themeViewMode("reseau"), "theme:reseau");
  assert.equal(isThemeViewMode("theme:reseau"), true);
  assert.equal(isThemeViewMode("reseau"), false);
  assert.equal(themeIdOf("theme:donnees"), "donnees");
  assert.equal(themeIdOf("grid"), null);
});

test("construction : entrées disponibles seulement, thématique vide omise, fronts absorbés et restants", () => {
  const fronts = [
    { id: "supervision", name: "Supervision SI", url: "http://old" },
    { id: "tickets", name: "Portail tickets", url: "http://tickets", embeddable: true },
    { id: "vault", name: "Coffre-fort", url: "http://vault" },
    { id: "si-agent", name: "Agents hôtes", onClick: () => {} },
    { id: "ext-42", name: "Wiki interne", url: "http://wiki" },
  ];
  const { themes, leftover } = buildThemes({ available: new Set(["supervision-si", "si-agent", "ent", "si-proxy"]), fronts });
  assert.deepEqual(themes.map((t) => t.id), ["supervision", "documents", "securite"]);
  const sup = findTheme(themes, "supervision");
  assert.deepEqual(sup.labels, ["Supervision SI", "Agents hôtes"]);
  assert.equal(sup.count, 2);
  const doc = findTheme(themes, "documents");
  assert.deepEqual(doc.entries.map((e) => [e.id, e.kind]), [["ent", "view"], ["front:tickets", "link"]]);
  assert.equal(doc.entries[1].url, "http://tickets");
  assert.equal(doc.entries[1].embeddable, true);
  const sec = findTheme(themes, "securite");
  assert.deepEqual(sec.entries.map((e) => e.id), ["si-proxy", "front:vault"]);
  // le lien externe déclaré par un admin reste une tuile à part ; les fronts absorbés non
  assert.deepEqual(leftover.map((f) => f.id), ["ext-42"]);
  assert.ok(absorbedFrontIds().has("supervision") && absorbedFrontIds().has("keycloak-admin"));
});

test("thématique d'une vue, mode d'accueil", () => {
  const { themes } = buildThemes({ available: new Set(["ssh-tunnels", "rights"]), fronts: [] });
  assert.equal(themeOfView(themes, "ssh-tunnels"), "reseau");
  assert.equal(themeOfView(themes, "rights"), "securite");
  assert.equal(themeOfView(themes, "logs"), null);
  assert.equal(normalizeHomeMode("tiles"), "tiles");
  assert.equal(normalizeHomeMode(undefined), "themes");
  assert.equal(normalizeHomeMode("nimp"), "themes");
});
