import { test } from "node:test";
import assert from "node:assert/strict";
import { gb, MODEL_RE, pullText } from "../src/ollama.js";

test("noms de modèles acceptés / refusés", () => {
  for (const ok of ["qwen3:14b", "hf.co/org/m:Q4_K_M", "bge-m3"]) assert.ok(MODEL_RE.test(ok), ok);
  for (const ko of ["", "-x", "a b", "x;rm", "/abs"]) assert.ok(!MODEL_RE.test(ko), ko);
});

test("tailles et progression", () => {
  assert.equal(gb(9_300_000_000), "9.3 Go");
  assert.equal(gb(274_000_000), "274 Mo");
  assert.equal(gb(null), "?");
  assert.equal(pullText(null), null);
  assert.equal(pullText({ running: true, model: "qwen3:8b", status: "pulling abc", completed: 50, total: 200 }), "téléchargement de qwen3:8b : pulling abc 25 %");
  assert.match(pullText({ running: false, model: "x:1b", ok: false, error: "absent" }), /en échec \(absent\)/);
});
