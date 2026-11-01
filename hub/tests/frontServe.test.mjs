import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { stripBase, resolve, IMMUTABLE, NO_CACHE } from "../../shared/front/serve.mjs";

test("#737 serveur commun des fronts : chemin de base retiré, SPA, actifs immuables", () => {
  assert.equal(stripBase("/tickets/assets/a.js", "/tickets/"), "/assets/a.js");
  assert.equal(stripBase("/tickets", "/tickets/"), "/");
  assert.equal(stripBase("/tickets?x=1", "/tickets/"), "/?x=1");
  assert.equal(stripBase("/ticketsX/a", "/tickets/"), "/ticketsX/a");
  assert.equal(stripBase("/a/b", "/"), "/a/b");
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "front-"));
  fs.mkdirSync(path.join(root, "assets")); fs.writeFileSync(path.join(root, "assets", "a.js"), "x"); fs.writeFileSync(path.join(root, "index.html"), "<html>");
  fs.writeFileSync(path.join(root, "env.js"), "window.__HUB_ENV__={}");
  assert.equal(resolve(root, stripBase("/tickets/assets/a.js", "/tickets/")).cache, IMMUTABLE);
  assert.equal(resolve(root, stripBase("/tickets/env.js", "/tickets/")).cache, NO_CACHE);
  assert.ok(resolve(root, stripBase("/tickets/demandes/12", "/tickets/")).file.endsWith("index.html"));
  assert.equal(resolve(root, stripBase("/tickets/../../etc/passwd", "/tickets/")).file, path.join(root, "index.html"));
});
