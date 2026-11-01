// #735 : activité réseau du hub, posée APRÈS installApiAuth (enveloppe le fetch déjà muni du jeton).
// 1. Retour visuel : <html data-busy="1"> dès qu'une requête dure plus de BUSY_DELAY_MS (barre fine en haut de
//    l'écran, curseur d'attente) -- l'utilisateur voit que sa commande est prise en compte.
// 2. Onglet caché : les GET vers les API du hub attendent que l'onglet redevienne visible, et les GET identiques en
//    attente ne partent qu'une fois (chaque appelant reçoit une copie) -- les ~35 rafraîchissements périodiques des
//    vues ne chargent plus le serveur pour un onglet que personne ne regarde.
import { apiBases, isApiUrl } from "./apiAuth.js";
import { hubEnv } from "./runtimeEnv.js";   // #736

export const BUSY_DELAY_MS = 150;

/** Logique pure (testée sous Node) : fetch enveloppé selon visibilité et suivi d'activité. */
export function createNetActivity({ fetch: base, isHidden, onBusy, isApi, delay = BUSY_DELAY_MS, timer = setTimeout, clear = clearTimeout }) {
  let inflight = 0; let busyTimer = null; let busy = false;
  const waiting = new Map();   // url -> {promise, resolve}
  const setBusy = (b) => { if (b !== busy) { busy = b; onBusy(b); } };
  const start = () => { inflight += 1; if (!busyTimer && !busy) busyTimer = timer(() => { busyTimer = null; if (inflight > 0) setBusy(true); }, delay); };
  const end = () => { inflight = Math.max(0, inflight - 1); if (inflight === 0) { if (busyTimer) { clear(busyTimer); busyTimer = null; } setBusy(false); } };
  const tracked = (input, init) => { start(); let p; try { p = base(input, init); } catch (e) { end(); throw e; } return Promise.resolve(p).finally(end); };

  function wrapped(input, init) {
    const url = typeof input === "string" ? input : input && input.url;
    const method = ((init && init.method) || (typeof input !== "string" && input && input.method) || "GET").toUpperCase();
    if (method === "GET" && isHidden() && isApi(url) && !(init && init.signal)) {
      let w = waiting.get(url);
      if (!w) { let resolve; const promise = new Promise((r) => { resolve = r; }); w = { promise, resolve, input, init }; waiting.set(url, w); }
      return w.promise.then((res) => (res && typeof res.clone === "function" ? res.clone() : res));
    }
    return tracked(input, init);
  }
  function flush() {
    const list = [...waiting.values()]; waiting.clear();
    for (const w of list) tracked(w.input, w.init).then(w.resolve, (e) => w.resolve(Promise.reject(e)));
    return list.length;
  }
  return { fetch: wrapped, flush, state: () => ({ inflight, busy, waiting: waiting.size }) };
}

export function installNetActivity(win = typeof window !== "undefined" ? window : null, env = hubEnv()) {
  if (!win || win.__netActivityInstalled || typeof win.fetch !== "function" || !win.document) return;
  win.__netActivityInstalled = true;
  const bases = apiBases(env); const origin = win.location ? win.location.origin : "";
  const doc = win.document;
  const na = createNetActivity({
    fetch: win.fetch.bind(win),
    isHidden: () => doc.visibilityState === "hidden",
    isApi: (u) => isApiUrl(u, bases, origin),
    onBusy: (b) => { if (b) doc.documentElement.setAttribute("data-busy", "1"); else doc.documentElement.removeAttribute("data-busy"); },
  });
  win.fetch = na.fetch;
  doc.addEventListener("visibilitychange", () => { if (doc.visibilityState !== "hidden") na.flush(); });
}
