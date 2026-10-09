import test from "node:test";
import assert from "node:assert/strict";
import { envScript } from "../write-env.mjs";

test("#736 env.js : seules les VITE_*, triées, JSON sûr", () => {
  const s = envScript({ VITE_B: "https://h:6443/api/b", VITE_A: "x</script>", SECRET: "non", vite_x: "non" });
  assert.equal(s, 'window.__HUB_ENV__ = {"VITE_A":"x\\u003c/script>","VITE_B":"https://h:6443/api/b"};\n');
  const w = {}; new Function("window", s)(w); assert.equal(w.__HUB_ENV__.VITE_A, "x</script>");
  assert.equal(envScript({}), "window.__HUB_ENV__ = {};\n");
});
