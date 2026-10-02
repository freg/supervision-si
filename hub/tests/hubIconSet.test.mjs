import test from "node:test";
import assert from "node:assert/strict";
import { ICONS, EMOJI_TO_ICON, TONES, STATE_TONES, resolveIcon, toneVar } from "../src/hubIconSet.js";
import { readFileSync, readdirSync } from "node:fs";

test("chaque icône a un corps SVG et un ton de thème valide", () => {
  for (const [name, { body, tone }] of Object.entries(ICONS)) {
    assert.ok(body.length > 10 && /<(path|circle|rect|line|polyline|polygon|ellipse)/.test(body), `corps vide : ${name}`);
    assert.ok(TONES.includes(tone), `ton inconnu : ${name} -> ${tone}`);
    assert.ok(!/#[0-9a-f]{3,6}|fill="(?!none|currentColor)/i.test(body), `couleur en dur dans ${name}`);
  }
});

test("tous les emoji des champs icon: du hub ont une pastille", () => {
  const used = new Set();
  for (const f of readdirSync("hub/src")) {
    if (!/\.(js|jsx)$/.test(f) || f === "hubIconSet.js") continue;
    for (const m of readFileSync(`hub/src/${f}`, "utf8").matchAll(/icon: *"([^"]+)"/g)) if (m[1]) used.add(m[1]);
  }
  const missing = [...used].filter((e) => !resolveIcon(e));
  assert.deepEqual(missing, [], `emoji sans pastille : ${missing.join(" ")}`);
});

test("resolveIcon : nom direct, emoji avec ou sans sélecteur de variante, inconnu -> null", () => {
  assert.equal(resolveIcon("router"), "router");
  assert.equal(resolveIcon("🏷️"), "tag");
  assert.equal(resolveIcon("🏷"), "tag");
  assert.equal(resolveIcon("🦄"), null);
  assert.equal(resolveIcon(""), null);
});

test("toneVar : identité -> --hub-icon-*, état -> variable du thème", () => {
  assert.equal(toneVar("teal"), "var(--hub-icon-teal)");
  assert.equal(toneVar("danger"), "var(--danger)");
  for (const t of STATE_TONES) assert.ok(TONES.includes(t));
});
