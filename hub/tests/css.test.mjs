// #917 : toutes les feuilles CSS du hub doivent se parser (accolade non fermée = hub entier bloqué par Vite).
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const require = createRequire(import.meta.url);
const postcss = require("postcss");
const SRC = fileURLToPath(new URL("../src/", import.meta.url));

function feuilles(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const p = path.join(dir, e.name);
    return e.isDirectory() ? feuilles(p) : e.name.endsWith(".css") ? [p] : [];
  });
}

test("chaque feuille CSS du hub se parse sans erreur (#917)", () => {
  const css = feuilles(SRC);
  assert.ok(css.length > 0, "aucune feuille trouvée");
  for (const f of css) {
    assert.doesNotThrow(() => postcss.parse(fs.readFileSync(f, "utf8"), { from: f }), `${path.relative(SRC, f)} ne se parse pas`);
  }
});
