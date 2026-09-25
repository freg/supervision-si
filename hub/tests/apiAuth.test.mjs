import test from "node:test";
import assert from "node:assert/strict";
import { apiBases, isApiUrl, withToken, installApiAuth, setApiToken } from "../src/apiAuth.js";

const env = { VITE_SI_AGENT_API_BASE_URL: "https://192.0.2.10:6443/api/si-agent/", VITE_PREFS_API_BASE_URL: "https://192.0.2.10:6443/api/prefs", VITE_PORTAL_URL: "/tickets", OTHER: "x" };

test("bases d'API depuis l'environnement Vite", () => {
  assert.deepEqual(apiBases(env), ["https://192.0.2.10:6443/api/si-agent", "https://192.0.2.10:6443/api/prefs"]);
});

test("détection des URL d'API", () => {
  const bases = apiBases(env);
  assert.ok(isApiUrl("https://192.0.2.10:6443/api/si-agent/fleet", bases, "https://hub"));
  assert.ok(isApiUrl("/api/licenses/gaps", bases, "https://hub"));
  assert.ok(isApiUrl("https://hub/api/x", bases, "https://hub"));
  assert.ok(!isApiUrl("https://autre.exemple/api/x", bases, "https://hub"));
  assert.ok(!isApiUrl("https://192.0.2.10:6443/auth/realms", bases, "https://hub"));
});

test("en-tête ajouté sans écraser l'existant", () => {
  const a = withToken({ method: "POST" }, "t1");
  assert.equal(a.headers.get("Authorization"), "Bearer t1");
  const b = withToken({ headers: { Authorization: "Bearer autre" } }, "t1");
  assert.equal(new Headers(b.headers).get("Authorization"), "Bearer autre");
  assert.deepEqual(withToken({ x: 1 }, ""), { x: 1 });
});

test("intercepteur : jeton sur les API, rien ailleurs", async () => {
  const seen = [];
  const win = { location: { origin: "https://hub" }, fetch: async (input, init) => { seen.push([input, (init && new Headers(init.headers).get("Authorization")) || null]); return { ok: true }; } };
  installApiAuth(win, env);
  setApiToken("tok");
  await win.fetch("https://192.0.2.10:6443/api/si-agent/fleet");
  await win.fetch("https://cdn.exemple/lib.js");
  await win.fetch("/api/prefs/x", { headers: { Authorization: "Bearer mien" } });
  assert.deepEqual(seen.map((s) => s[1]), ["Bearer tok", null, "Bearer mien"]);
});
