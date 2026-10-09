// #735 : préchargement en tâche de fond des vues chargées à la demande (React.lazy) -- une à la fois, quand le
// navigateur est inactif, pour que le premier clic sur une tuile ne paie plus le téléchargement de son code.
// `schedule(fn)` : requestIdleCallback si disponible, sinon un court délai ; les échecs sont ignorés (la vue sera
// chargée au clic). Retourne une fonction d'arrêt.
export function idleScheduler(win = typeof window !== "undefined" ? window : null) {
  if (win && typeof win.requestIdleCallback === "function") return (fn) => win.requestIdleCallback(fn, { timeout: 2000 });
  return (fn) => setTimeout(fn, 200);
}

export function preloadSequential(loaders, schedule = idleScheduler(), onDone) {
  let stopped = false; let i = 0;
  const next = () => {
    if (stopped) return;
    if (i >= loaders.length) { if (onDone) onDone(i); return; }
    const load = loaders[i++];
    schedule(() => {
      if (stopped) return;
      let p;
      try { p = load(); } catch (_) { p = null; }
      Promise.resolve(p).catch(() => null).then(next);
    });
  };
  next();
  return () => { stopped = true; };
}
