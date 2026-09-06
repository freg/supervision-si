// Client network-agent : URLs construites et robustesse des réponses,
// avec un `fetch` simulé (aucun réseau). Lancer : node --test hub/tests/
import { test } from "node:test";
import assert from "node:assert/strict";
import { fetchLinkServices, fetchLinkHistory } from "../src/networkAgentClient.js";

function stubFetch(handler) {
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    const r = handler(url);
    return { status: r.status ?? 200, json: async () => { if (r.invalid) throw new Error("bad json"); return r.body; } };
  };
  return calls;
}

test("fetchLinkServices interroge /links/services avec les deux identifiants", async () => {
  const calls = stubFetch(() => ({ body: [{ id: 1, protocol: "tcp", port: 443 }] }));
  const out = await fetchLinkServices("http://api", 7, 12);
  assert.deepEqual(calls, ["http://api/links/services?device_a_id=7&device_b_id=12"]);
  assert.equal(out.length, 1);
});

test("fetchLinkHistory interroge /links/history", async () => {
  const calls = stubFetch(() => ({ body: [] }));
  await fetchLinkHistory("http://api", 3, 4);
  assert.deepEqual(calls, ["http://api/links/history?device_a_id=3&device_b_id=4"]);
});

test("les deux renvoient un tableau vide sur erreur API, JSON invalide ou objet inattendu", async () => {
  stubFetch(() => ({ status: 400, body: { error: "'device_a_id' et 'device_b_id' requis" } }));
  assert.deepEqual(await fetchLinkServices("http://api", 0, 1), []);
  stubFetch(() => ({ invalid: true }));
  assert.deepEqual(await fetchLinkHistory("http://api", 1, 2), []);
  globalThis.fetch = async () => { throw new Error("réseau coupé"); };
  assert.deepEqual(await fetchLinkServices("http://api", 1, 2), []);
});
