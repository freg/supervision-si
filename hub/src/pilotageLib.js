// Pilotage du réseau du campus (livraison #855) -- fonctions pures de l'onglet « Pilotage » de la tuile Nebula.
// Testées : tests/pilotageLib.test.mjs.

export const OPS = [">", ">=", "<", "<=", "=="];
export const MODES = { conseil: "Conseil (alerte, recommandation, banc proposé)", auto: "Auto (le banc est lancé)" };

/** Valeur lisible : arrondi selon l'ordre de grandeur, « — » si absente. */
export function fmt(v, unite = "") {
  if (v === null || v === undefined || Number.isNaN(+v)) return "—";
  const n = +v;
  const s = Math.abs(n) >= 100 ? Math.round(n).toString() : Math.abs(n) >= 10 ? n.toFixed(1).replace(/\.0$/, "") : n.toFixed(2).replace(/\.?0+$/, "");
  return unite ? `${s} ${unite}` : s;
}

/** « Clients simultanés par borne > 25 pendant 5 min (toutes les cibles) ». */
export function conditionTexte(c, metriques = {}) {
  if (!c) return "";
  const m = metriques[c.metrique];
  const lib = m ? m.libelle : c.metrique;
  const u = m && m.unite ? ` ${m.unite}` : "";
  const d = c.duree_min ? ` pendant ${c.duree_min} min` : " (dernier relevé)";
  return `${lib} ${c.op} ${c.seuil}${u}${d}${c.cible && c.cible !== "*" ? ` (${c.cible})` : " (toutes les cibles)"}`;
}

/** Points SVG d'une mini-courbe : série [[t, v], …] -> "x,y x,y …" dans w × h (axe vertical inversé). */
export function sparkPoints(serie, w = 120, h = 28) {
  const s = (serie || []).filter((p) => p && p[1] !== null && p[1] !== undefined);
  if (s.length < 2) return "";
  const t0 = s[0][0], t1 = s[s.length - 1][0];
  const vs = s.map((p) => +p[1]);
  const lo = Math.min(...vs), hi = Math.max(...vs);
  const dx = t1 - t0 || 1, dy = hi - lo || 1;
  return s.map((p) => `${(((p[0] - t0) / dx) * w).toFixed(1)},${(h - ((+p[1] - lo) / dy) * (h - 2) - 1).toFixed(1)}`).join(" ");
}

/** Formulaire de boucle -> corps envoyé à /pilotage/boucles. */
export function boucleDepuisForm(f) {
  const actions = [];
  if (f.notifier) actions.push({ type: "notifier" });
  if (f.outil) actions.push({ type: "recommander", outil: f.outil });
  if (f.banc) actions.push({ type: "banc", plan: f.banc });
  return {
    nom: (f.nom || "").trim(), description: f.description || "", actif: !!f.actif, mode: f.mode === "auto" ? "auto" : "conseil",
    condition: { metrique: f.metrique, cible: (f.cible || "").trim() || "*", op: f.op || ">", seuil: Number(f.seuil), duree_min: Number(f.duree_min) || 0 },
    actions, delai_min: Number(f.delai_min) || 60,
  };
}

/** Boucle enregistrée -> formulaire (édition). */
export function formDepuisBoucle(b) {
  const a = b?.actions || [];
  const c = b?.condition || {};
  return {
    nom: b?.nom || "", description: b?.description || "", actif: !!b?.actif, mode: b?.mode || "conseil",
    metrique: c.metrique || "borne.simultanes", cible: c.cible && c.cible !== "*" ? c.cible : "", op: c.op || ">", seuil: c.seuil ?? "", duree_min: c.duree_min ?? 5,
    notifier: a.some((x) => x.type === "notifier"), outil: a.find((x) => x.type === "recommander")?.outil || "", banc: a.find((x) => x.type === "banc")?.plan || "",
    delai_min: b?.delai_min ?? 60,
  };
}

/** Avancement d'un banc en cours : étape courante, minutes écoulées / totales, pourcentage. */
export function progression(run, plan, maintenant = Date.now() / 1000) {
  if (!run) return null;
  const etapes = plan?.etapes || [];
  const total = etapes.reduce((s, e) => s + (+e.duree_min || 0), 0);
  const ecoule = Math.max(0, (maintenant - (run.debut ?? maintenant)) / 60);
  const i = Math.max(0, run.etape ?? 0);
  return { etape: i + 1, etapes: etapes.length, nom: etapes[i]?.nom || run.etapes?.[i]?.nom || "", ecoule_min: Math.round(ecoule), total_min: total,
    pct: total ? Math.min(100, Math.round((ecoule / total) * 100)) : 0 };
}

/** Réglages requis par un banc et absents (même règle que nebula-api, pour griser « Lancer »). */
export function manquants(plan, reglages = {}) {
  const t = JSON.stringify(plan?.etapes || []);
  const out = new Set();
  if (t.includes("{serveur}") && !reglages.serveur_iperf) out.add("serveur iperf3");
  if (t.includes("{cible}") && !reglages.cible_ping) out.add("cible du ping");
  if ((t.includes("{url}") || t.includes("{nom}")) && !(reglages.urls || []).length) out.add("adresses à charger");
  if (!(reglages.sondes || []).length) out.add("sondes autorisées pour les bancs");
  return [...out].sort();
}

/** Outils groupés dans l'ordre d'apparition : [[groupe, [outils]], …]. */
export function grouperOutils(outils) {
  const m = new Map();
  for (const o of outils || []) { if (!m.has(o.groupe)) m.set(o.groupe, []); m.get(o.groupe).push(o); }
  return [...m.entries()];
}

/** Tableau par sonde à partir du dernier relevé : [{sonde, rssi, rtt, perte, gigue, perte_udp, debit, http}]. */
export function lignesSondes(valeurs) {
  const v = valeurs || {};
  const cles = { rssi: "sonde.rssi_dbm", rtt: "sonde.rtt_ms", perte: "sonde.perte_pct", gigue: "sonde.gigue_ms", perte_udp: "sonde.perte_udp_pct", debit: "sonde.debit_mbps", http: "sonde.http_ms" };
  const noms = new Set();
  Object.values(cles).forEach((k) => Object.keys(v[k] || {}).forEach((n) => noms.add(n)));
  return [...noms].sort().map((sonde) => Object.fromEntries([["sonde", sonde], ...Object.entries(cles).map(([c, k]) => [c, v[k]?.[sonde] ?? null])]));
}

/** Tableau par borne : [{borne, simultanes, clients, debit}] trié par simultanés décroissants. */
export function lignesBornes(valeurs) {
  const v = valeurs || {};
  const noms = new Set([...Object.keys(v["borne.simultanes"] || {}), ...Object.keys(v["borne.clients"] || {})]);
  return [...noms].map((borne) => ({ borne, simultanes: v["borne.simultanes"]?.[borne] ?? null, clients: v["borne.clients"]?.[borne] ?? null, debit: v["borne.debit_mbps"]?.[borne] ?? null }))
    .sort((a, b) => (b.simultanes ?? -1) - (a.simultanes ?? -1) || a.borne.localeCompare(b.borne));
}
