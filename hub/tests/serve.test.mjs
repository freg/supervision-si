import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { resolve, createServer, NO_CACHE, IMMUTABLE } from "../serve.mjs";

const root = fs.mkdtempSync(path.join(os.tmpdir(), "hubdist-"));
fs.mkdirSync(path.join(root, "assets"));
fs.writeFileSync(path.join(root, "index.html"), "<html>hub</html>");
fs.writeFileSync(path.join(root, "assets", "index-abc123.js"), "console.log(1)");
fs.writeFileSync(path.join(root, "favicon.svg"), "<svg/>");

test("résolution : assets immuables, index sans cache, SPA, 404, traversée refusée", () => {
  assert.deepEqual(resolve(root, "/assets/index-abc123.js"), { file: path.join(root, "assets", "index-abc123.js"), cache: IMMUTABLE });
  assert.deepEqual(resolve(root, "/"), { file: path.join(root, "index.html"), cache: NO_CACHE });
  assert.deepEqual(resolve(root, "/agents/pve10?x=1"), { file: path.join(root, "index.html"), cache: NO_CACHE });
  assert.equal(resolve(root, "/favicon.svg").cache, NO_CACHE);
  assert.equal(resolve(root, "/assets/absent.js").file, null);
  const t = resolve(root, "/../../etc/passwd");
  assert.ok(t === null || t.file === null || t.file.startsWith(root));
  assert.equal(resolve(root, "/%E0%A4%A"), null);
});

test("serveur : en-têtes de cache et types", async () => {
  const srv = createServer(root); await new Promise((r) => srv.listen(0, r));
  const base = `http://127.0.0.1:${srv.address().port}`;
  let r = await fetch(base + "/"); assert.equal(r.headers.get("cache-control"), NO_CACHE); assert.match(r.headers.get("content-type"), /text\/html/); assert.equal(await r.text(), "<html>hub</html>");
  r = await fetch(base + "/assets/index-abc123.js"); assert.equal(r.headers.get("cache-control"), IMMUTABLE); assert.match(r.headers.get("content-type"), /javascript/);
  r = await fetch(base + "/assets/x.js"); assert.equal(r.status, 404);
  r = await fetch(base + "/", { method: "POST" }); assert.equal(r.status, 405);
  srv.close();
});
