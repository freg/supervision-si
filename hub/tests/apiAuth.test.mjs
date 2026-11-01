import test from "node:test";
import assert from "node:assert/strict";
import { apiBases, isApiUrl, withToken, installApiAuth, setApiToken, setSiteScope, resolveSiteScope, withSiteParam } from "../src/apiAuth.js";

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

test("A1 : périmètre de site (résolution et paramètre)", async () => {
  const sg = { "site-numeria": ["numeria"], "site-groupe": ["optline", "groupe-i"] };
  assert.equal(resolveSiteScope(["administrateurs", "site-numeria"], sg, ["administrateurs"]), null);
  assert.equal(resolveSiteScope(["techniciens"], sg, ["administrateurs"]), null);
  assert.deepEqual(resolveSiteScope(["/site-numeria", "site-groupe"], sg, ["administrateurs"]), ["groupe-i", "numeria", "optline"]);
  assert.equal(withSiteParam("/api/si-agent/fleet", ["numeria"]), "/api/si-agent/fleet?site=numeria");
  assert.equal(withSiteParam("/api/x?a=1#h", ["numeria"]), "/api/x?a=1&site=numeria#h");
  assert.equal(withSiteParam("/api/x?site=optline", ["numeria"]), "/api/x?site=optline");
  const seen = [];
  const win = { location: { origin: "https://hub" }, fetch: async (input, init) => { seen.push([input, (init && init.method) || "GET"]); return { ok: true }; } };
  installApiAuth(win, env); setApiToken("tok"); setSiteScope(["numeria"]);
  await win.fetch("/api/si-agent/fleet"); await win.fetch("/api/si-agent/agents", { method: "POST" }); await win.fetch("https://cdn.exemple/x");
  assert.deepEqual(seen.map((s) => s[0]), ["/api/si-agent/fleet?site=numeria", "/api/si-agent/agents", "https://cdn.exemple/x"]);
  setSiteScope(null);
});
