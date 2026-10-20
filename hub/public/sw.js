// #796 : service worker du hub (application installable sur téléphone).
// - navigation : réseau d'abord (le hub n'est jamais servi périmé, cf. #681), page hors ligne si le réseau manque ;
// - push : affiche l'alerte reçue de notify-api (chiffrée RFC 8291) et la garde dans l'historique hors ligne ;
// - clic sur l'alerte : ouvre / remet au premier plan le hub sur l'écran Urgence.
// Les appels d'API ne passent jamais par ici (aucune mise en cache de données authentifiées).
const CACHE = "hub-urgence-v1";
const OFFLINE = "/offline.html";
const PUSH_LOG = "/__urgence-push.json";
const PRECACHE = [OFFLINE, "/icon-192.png", "/manifest.webmanifest"];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(PRECACHE)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(caches.keys()
    .then((ks) => Promise.all(ks.filter((k) => k.startsWith("hub-urgence-") && k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", (e) => {
  const r = e.request;
  if (r.mode !== "navigate" || r.method !== "GET") return;
  e.respondWith(fetch(r).catch(() => caches.match(OFFLINE, { ignoreSearch: true })
    .then((res) => res || new Response("Hub hors ligne", { status: 503, headers: { "Content-Type": "text/plain; charset=utf-8" } }))));
});

async function logPush(msg) {
  try {
    const c = await caches.open(CACHE);
    const old = await c.match(PUSH_LOG);
    const list = old ? await old.json() : [];
    list.unshift({ ...msg, recu: new Date().toISOString() });
    await c.put(PUSH_LOG, new Response(JSON.stringify(list.slice(0, 50)), { headers: { "Content-Type": "application/json" } }));
  } catch (_) { /* historique facultatif */ }
}

self.addEventListener("push", (e) => {
  let m = {};
  try { m = e.data ? e.data.json() : {}; } catch (_) { m = { title: "Hub SI", body: e.data ? e.data.text() : "" }; }
  const title = m.title || "Alerte du hub";
  const crit = m.severity === "critical";
  e.waitUntil(Promise.all([
    logPush(m),
    self.registration.showNotification((crit ? "🔴 " : m.severity === "warning" ? "🟠 " : "") + title, {
      body: m.body || "", tag: m.tag || undefined, renotify: !!m.tag, requireInteraction: crit,
      icon: "/icon-192.png", badge: "/icon-192.png", data: { url: m.url || "/?view=urgence" },
    }),
  ]));
});

self.addEventListener("notificationclick", (e) => {
  e.notification.close();
  const url = new URL((e.notification.data && e.notification.data.url) || "/?view=urgence", self.location.origin).href;
  e.waitUntil(self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((ws) => {
    for (const w of ws) if (new URL(w.url).origin === self.location.origin && "focus" in w) { w.navigate(url).catch(() => {}); return w.focus(); }
    return self.clients.openWindow(url);
  }));
});
