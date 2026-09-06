// Zoom SVG générique avec point focal — pur, testable sans DOM. Le
// point "focal" est exprimé dans l'espace du viewBox SVG (pas en
// pixels écran) : côté composant, on le calcule via
// svg.createSVGPoint() + getScreenCTM().inverse(), qui gère
// automatiquement toute mise à l'échelle CSS entre l'écran et le
// viewBox — voir IpamRadialTree.jsx.

export const DEFAULT_ZOOM_TRANSFORM = { tx: 0, ty: 0, scale: 1 };

export function clampScale(scale, min, max) {
  return Math.min(max, Math.max(min, scale));
}

/**
 * Nouveau {tx, ty, scale} qui zoome de `factor` (>1 = avant, <1 =
 * arrière) EN GARDANT `focal` visuellement fixe à l'écran — c'est le
 * "avec focus" demandé : le point sous le curseur reste au même
 * endroit pendant le zoom, le reste de l'arbre se rapproche/s'éloigne
 * de lui, pas un zoom générique centré sur l'origine.
 *
 * Le scale résultant est toujours borné à [min, max]. Utilise le
 * facteur RÉELLEMENT appliqué (après bornage) pour le calcul de la
 * translation — sans ça, une fois la borne atteinte, chaque cran de
 * molette supplémentaire continuerait à faire glisser tx/ty sans que
 * le scale bouge, un dérapage cumulatif classique de ce genre de calcul.
 */
export function computeZoomTransform(prev, factor, focal, min = 0.3, max = 6) {
  const prevScale = prev?.scale ?? 1;
  const prevTx = prev?.tx ?? 0;
  const prevTy = prev?.ty ?? 0;
  const fx = focal?.x ?? 0;
  const fy = focal?.y ?? 0;

  const nextScale = clampScale(prevScale * factor, min, max);
  const effectiveFactor = prevScale === 0 ? 1 : nextScale / prevScale;

  return {
    tx: fx - (fx - prevTx) * effectiveFactor,
    ty: fy - (fy - prevTy) * effectiveFactor,
    scale: nextScale,
  };
}
