// #842 : un même nom exporté deux fois dans un module (« redeclaration of const ») casse tout le hub au chargement
// (siAgentClient.js : fetchImages #634 et #834). Ce contrôle couvre tous les modules de src/.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { join, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const SRC = join(dirname(fileURLToPath(import.meta.url)), "..", "src");
const DECL = /^(?:export\s+)?(?:const|let|function|async\s+function|class)\s+([A-Za-z_$][\w$]*)/gm;

test("aucun nom déclaré deux fois au niveau du module", () => {
  const doublons = [];
  for (const f of readdirSync(SRC).filter((n) => /\.(m?js|jsx)$/.test(n))) {
    const vus = new Map();
    for (const m of readFileSync(join(SRC, f), "utf8").matchAll(DECL)) {
      if (vus.has(m[1])) doublons.push(`${f} : ${m[1]}`);
      vus.set(m[1], true);
    }
  }
  assert.deepEqual(doublons, []);
});
