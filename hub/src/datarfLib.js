// Tuile « Data RF » (#806) -- calculs purs (testés : tests/datarfLib.test.mjs). Données : si-agent-api /datarf.
export const BANDES = [{ nom: "2,4 GHz", de: 2400, a: 2500, canaux: [1, 6, 11, 13] }, { nom: "5 GHz", de: 5150, a: 5730, canaux: [36, 52, 100, 116, 132] }];
export const freqCanal = (c) => (c <= 14 ? 2407 + 5 * c : 5000 + 5 * c);

// Spectre [[MHz, moy, max]] -> tracés d'une bande dans une boîte w × h, échelle dB [bas, haut]
export function traces(spectre, bande, w = 600, h = 120, bas = -90, haut = -30) {
  const pts = (spectre || []).filter((p) => p[0] >= bande.de && p[0] <= bande.a);
  const x = (f) => (((f - bande.de) * w) / (bande.a - bande.de)).toFixed(1);
  const y = (db) => (h - ((Math.min(haut, Math.max(bas, db)) - bas) * h) / (haut - bas)).toFixed(1);
  const trace = (i) => pts.filter((p) => p[i] != null).map((p, k) => `${k ? "L" : "M"}${x(p[0])},${y(p[i])}`).join(" ");
  return { moy: trace(1), max: trace(2), n: pts.length, x, y };
}

// Croisement par canal : occupation au spectre (rf-spectrum) et trafic Wi-Fi (wifi-monitor) -> soupçon de brouillage non Wi-Fi
export function croiser(rf, wm) {
  const out = new Map();
  for (const c of rf?.canaux || []) out.set(c.canal, { canal: c.canal, freq: c.freq ?? freqCanal(c.canal), spectre_pct: c.occupation_pct, moy_db: c.moy_db, max_db: c.max_db });
  for (const c of wm?.canaux || []) {
    const e = out.get(c.canal) || { canal: c.canal, freq: c.freq ?? freqCanal(c.canal) };
    out.set(c.canal, { ...e, wifi_pct: c.occupation_pct ?? c.occupation_estimee_pct ?? null, wifi_estime: c.occupation_pct == null, trames_s: c.par_s, retry_pct: c.retry_pct, deauth: c.deauth, signal_max: c.signal_max });
  }
  return [...out.values()].sort((a, b) => a.canal - b.canal).map((e) => {
    const s = e.spectre_pct, w = e.wifi_pct;
    // sans écoute Wi-Fi sur ce canal, on ne conclut pas
    const lecture = s == null || w == null ? "" : s >= 30 && w < s / 2 ? "non-wifi" : s >= 30 ? "wifi" : "";
    return { ...e, lecture };
  });
}

export const LECTURE = { "non-wifi": "occupé sans trafic Wi-Fi à la hauteur : brouillage ou émetteur non Wi-Fi probable", wifi: "occupé par du Wi-Fi" };

// Bornes vues par l'écoute, signal le plus fort d'abord
export function bornes(wm) {
  return [...(wm?.bornes || [])].sort((a, b) => (b.signal_max ?? -200) - (a.signal_max ?? -200));
}

// Âge d'une mesure ISO (s) par rapport à maintenant (ms)
export function age(iso, maintenant = Date.now()) {
  const t = Date.parse(iso || "");
  return Number.isFinite(t) ? Math.max(0, Math.round((maintenant - t) / 1000)) : null;
}
export const fmtAge = (s) => (s == null ? "—" : s < 120 ? `${s} s` : s < 7200 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`);
