import test from "node:test";
import assert from "node:assert/strict";
import { createNetActivity } from "../src/netActivity.js";
import { preloadSequential } from "../src/lazyViews.js";

function setup(hidden = false) {
  const calls = []; const busy = []; let h = hidden; const timers = [];
  const res = (u) => ({ url: u, n: 0, clone() { this.n += 1; return { url: u, copy: this.n }; } });
  const na = createNetActivity({
    fetch: (u) => { calls.push(u); return Promise.resolve(res(u)); },
    isHidden: () => h, isApi: (u) => String(u).startsWith("/api/"), onBusy: (b) => busy.push(b),
    timer: (fn) => { timers.push(fn); return timers.length; }, clear: () => {},
  });
  return { na, calls, busy, timers, show: () => { h = false; } };
}

test("#735 onglet visible : passage direct, indicateur d'activité après délai", async () => {
  const { na, calls, busy, timers } = setup();
  const p = na.fetch("/api/x"); assert.equal(na.state().inflight, 1);
  timers[0](); assert.deepEqual(busy, [true]);
  await p; assert.deepEqual(calls, ["/api/x"]); assert.deepEqual(busy, [true, false]);
});

test("#735 onglet caché : GET d'API retenus, dédoublonnés, partis au retour ; le reste passe", async () => {
  const { na, calls, show } = setup(true);
  const a = na.fetch("/api/poll"); const b = na.fetch("/api/poll");
  await na.fetch("/static/x.js"); await na.fetch("/api/save", { method: "POST" });
  assert.deepEqual(calls, ["/static/x.js", "/api/save"]); assert.equal(na.state().waiting, 1);
  show(); assert.equal(na.flush(), 1);
  const [ra, rb] = await Promise.all([a, b]);
  assert.deepEqual(calls, ["/static/x.js", "/api/save", "/api/poll"]);
  assert.deepEqual([ra.copy, rb.copy], [1, 2]);                       // chaque appelant reçoit sa copie
});

test("#735 préchargement séquentiel des vues, échecs ignorés, arrêt possible", async () => {
  const order = []; const loaders = [() => { order.push(1); return Promise.resolve(); }, () => { order.push(2); return Promise.reject(new Error("x")); }, () => { order.push(3); }];
  await new Promise((done) => preloadSequential(loaders, (fn) => setTimeout(fn, 0), done));
  assert.deepEqual(order, [1, 2, 3]);
  const o2 = []; const stop = preloadSequential([() => o2.push(1), () => o2.push(2)], (fn) => setTimeout(fn, 5));
  stop(); await new Promise((r) => setTimeout(r, 20)); assert.deepEqual(o2, []);
});
