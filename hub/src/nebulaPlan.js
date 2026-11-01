// Plan du site (livraison #555) -- logique PURE, testée sous Node
// (hub/tests/nebulaPlan.test.mjs). Les appareils sont posés sur une image de
// plan (positions en fractions 0..1) ; les clients d'un appareil non placés
// individuellement s'affichent en anneau autour de lui.

/** Position d'un client : la sienne s'il en a une, sinon sur un anneau autour
 *  de l'appareil parent (rayon en fraction, n clients répartis). */
export function clientSpot(parentPos, index, count, radius = 0.025) {
  if (!parentPos) return null;
  const angle = -Math.PI / 2 + (2 * Math.PI * index) / Math.max(1, count);
  const r = radius * (1 + Math.floor(index / 12) * 0.9);  // anneaux concentriques au-delà de 12
  return { x: parentPos.x + r * Math.cos(angle), y: parentPos.y + r * Math.sin(angle), auto: true };
}

/** Éléments à dessiner : appareils placés, clients (placés ou en anneau),
 *  et la liste des appareils encore à poser. `placements` = {clé: {x, y}}. */
export function planItems(tree, placements = {}) {
  const devices = [], clients = [], unplaced = [];
  for (const n of tree.nodes || []) {
    const p = placements[n.id];
    if (p) devices.push({ key: n.id, node: n, x: p.x, y: p.y });
    else unplaced.push(n);
    const cl = n.clients || [];
    const auto = cl.filter((c) => !placements[`client:${c.mac}`]);
    let ai = 0;
    for (const c of cl) {
      const own = placements[`client:${c.mac}`];
      if (own) clients.push({ key: `client:${c.mac}`, client: c, parent: n.id, x: own.x, y: own.y, auto: false });
      else if (p) { const s = clientSpot(p, ai++, auto.length); clients.push({ key: `client:${c.mac}`, client: c, parent: n.id, x: s.x, y: s.y, auto: true }); }
    }
  }
  unplaced.sort((a, b) => a.name.localeCompare(b.name, "fr"));
  return { devices, clients, unplaced };
}

/** Coordonnées écran → fraction, bornées. */
export function toFraction(px, py, box) {
  if (!box || !box.width || !box.height) return null;
  const x = Math.min(1, Math.max(0, (px - box.left) / box.width));
  const y = Math.min(1, Math.max(0, (py - box.top) / box.height));
  return { x: Math.round(x * 10000) / 10000, y: Math.round(y * 10000) / 10000 };
}

/** Fusion locale d'un lot de positions (null = retrait), même sémantique que l'API. */
export function mergePlacements(current, patch) {
  const out = { ...current };
  for (const [k, v] of Object.entries(patch || {})) {
    if (v == null) delete out[k]; else out[k] = { x: v.x, y: v.y };
  }
  return out;
}
