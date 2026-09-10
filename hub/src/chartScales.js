// Modulation d'échelle des graphiques -- livraison #413. Logique pure,
// testée sous Node (hub/tests/chartScales.test.mjs).
//
// Retour de tests : « modulation d'échelle pour tous les graphiques ». Sur
// un réseau réel, un seul échange (hôte de supervision ↔ passerelle, une
// sauvegarde) écrase tous les autres : en échelle linéaire, les petits flux
// deviennent des traits d'un demi-pixel. D'où trois échelles au choix,
// appliquées au RATIO valeur/maximum (jamais à une valeur absolue, principe
// déjà en vigueur dans le projet -- pixel-grid #371, radial #389) :
//
//   linear -- ratio tel quel : fidèle, mais écrase les petits ;
//   sqrt   -- racine carrée : compromis, un flux 100× plus petit reste 10× plus fin ;
//   log    -- logarithmique : un flux 100× plus petit n'est que ~2× plus fin --
//             lisible partout, au prix de la proportionnalité.
//
// Plus un GAIN (×0.25 à ×4) qui épaissit ou affine tout d'un coup, sans
// changer l'ordre ni la forme de l'échelle.

export const SCALE_MODES = [
  { id: "linear", label: "linéaire" },
  { id: "sqrt", label: "racine" },
  { id: "log", label: "log" },
];
export const DEFAULT_SCALE_MODE = "linear";
export const GAIN_MIN = 0.25;
export const GAIN_MAX = 4;
export const DEFAULT_GAIN = 1;

export function isScaleMode(m) {
  return SCALE_MODES.some((s) => s.id === m);
}

export function clampGain(g) {
  const n = typeof g === "number" ? g : parseFloat(g);
  if (!Number.isFinite(n)) return DEFAULT_GAIN;
  return Math.min(GAIN_MAX, Math.max(GAIN_MIN, n));
}

// Ratio [0, 1] d'une valeur par rapport au maximum, selon l'échelle.
// 0 et les valeurs non positives donnent 0 ; le maximum donne 1 ; entre les
// deux, l'échelle décide. Pour "log", on travaille sur log(1 + v) pour que
// 0 reste 0 sans cas particulier et que l'échelle soit continue.
export function scaleRatio(value, max, mode = DEFAULT_SCALE_MODE) {
  if (!(max > 0) || !(value > 0)) return 0;
  const r = Math.min(1, value / max);
  switch (mode) {
    case "sqrt":
      return Math.sqrt(r);
    case "log":
      return Math.log1p(Math.min(value, max)) / Math.log1p(max);
    default:
      return r;
  }
}

/**
 * Fabrique une fonction valeur → épaisseur (ou hauteur) entre minOut et
 * maxOut, le maximum étant celui de `values` (ou `max` si fourni).
 * @param {number[]} values
 * @param {{mode?: string, gain?: number, minOut?: number, maxOut?: number, max?: number}} opts
 */
export function makeScale(values, opts = {}) {
  const mode = isScaleMode(opts.mode) ? opts.mode : DEFAULT_SCALE_MODE;
  const gain = clampGain(opts.gain ?? DEFAULT_GAIN);
  const minOut = opts.minOut ?? 1;
  const maxOut = opts.maxOut ?? 24;
  const positives = (values || []).filter((v) => v > 0);
  const max = opts.max ?? (positives.length ? Math.max(...positives) : 0);
  const fn = (value) => {
    if (!(value > 0) || !(max > 0)) return minOut;
    // Le gain multiplie la part AU-DESSUS du minimum : un flux existant
    // reste visible (minOut) quel que soit le réglage, et le maximum vaut
    // minOut + gain × (maxOut − minOut).
    return minOut + scaleRatio(value, max, mode) * (maxOut - minOut) * gain;
  };
  fn.max = max;
  fn.mode = mode;
  fn.gain = gain;
  return fn;
}

// Préférence d'échelle partagée par les graphiques de flux : { mode, gain }.
export const SCALE_STORAGE_KEY = "hub.charts.scale";
export const DEFAULT_SCALE_PREF = { mode: DEFAULT_SCALE_MODE, gain: DEFAULT_GAIN };

export function loadScalePreference(storage) {
  try {
    const raw = storage?.getItem(SCALE_STORAGE_KEY);
    if (!raw) return DEFAULT_SCALE_PREF;
    const p = JSON.parse(raw);
    return { mode: isScaleMode(p?.mode) ? p.mode : DEFAULT_SCALE_MODE, gain: clampGain(p?.gain) };
  } catch {
    return DEFAULT_SCALE_PREF;
  }
}

export function saveScalePreference(storage, pref) {
  try {
    storage?.setItem(SCALE_STORAGE_KEY, JSON.stringify({ mode: isScaleMode(pref?.mode) ? pref.mode : DEFAULT_SCALE_MODE, gain: clampGain(pref?.gain) }));
    return true;
  } catch {
    return false;
  }
}
