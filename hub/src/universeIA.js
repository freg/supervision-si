// #967 : recherche silencieuse de l'« Univers du hub ». Quand le filtre statique trouve peu, la saisie part en
// arrière-plan vers l'assistant (temps 1 : catalogue sans modèle, temps 2 : modèle). Seul un indice visuel discret
// signale la recherche ; les suggestions s'AJOUTENT à la réponse statique, sinon rien n'apparaît.
// Une suggestion choisie devient un synonyme appris (la prochaine fois, le filtre statique suffit).

export const SEUIL_RESULTATS = 2;     // au-delà, le filtre statique suffit : pas d'IA
export const DELAI_MS = 700;          // pause de frappe avant d'interroger
const CLE_APPRIS = "hub.universe.appris";

export function idEntree(leaf) {
  if (!leaf) return "";
  if (leaf.kind === "view") return "view:" + leaf.view;
  if (leaf.kind === "front") return "front:" + leaf.front;
  return String(leaf.id || "");
}

/** Faut-il interroger l'assistant ? (saisie de 3 caractères ou plus, pas une adresse, peu de résultats statiques) */
export function doitInterroger(query, nbResultats, estAdresse = false) {
  const q = String(query || "").trim();
  return q.length >= 3 && !estAdresse && nbResultats <= SEUIL_RESULTATS;
}

/** Entrées de l'univers -> candidats compacts envoyés à l'assistant. */
export function candidats(entrees) {
  return (entrees || []).map((l) => ({ id: idEntree(l), label: l.label, themes: l.themes || [], aliases: (l.aliases || []).slice(0, 20) }))
    .filter((c) => /^(view|front|action):/.test(c.id));
}

/** Suggestions (ids) -> entrées à ajouter sous la réponse statique : connues, pas déjà affichées, 3 au plus. */
export function ajouts(suggestions, entrees, affichees) {
  const parId = new Map((entrees || []).map((l) => [idEntree(l), l]));
  const deja = new Set((affichees || []).map(idEntree));
  const out = [];
  for (const s of suggestions || []) {
    const l = parId.get(s.id);
    if (!l || deja.has(s.id) || out.some((o) => o.id === s.id)) continue;
    out.push({ id: s.id, leaf: l, raison: s.raison || "", source: s.source || "" });
    if (out.length >= 3) break;
  }
  return out;
}

function plier(s) {
  return String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

/** Synonymes appris : { "view:accounts": ["droits utilisateurs", …] } -- fusionnés aux synonymes du hub. */
export function lireAppris(stockage) {
  try {
    const v = JSON.parse((stockage || globalThis.localStorage)?.getItem(CLE_APPRIS) || "{}");
    return v && typeof v === "object" && !Array.isArray(v) ? v : {};
  } catch { return {}; }
}

export function apprendre(appris, query, id, max = 30) {
  const q = plier(query);
  if (q.length < 3 || !/^(view|front|action):/.test(id || "")) return appris || {};
  const liste = (appris && appris[id]) || [];
  if (liste.includes(q)) return appris;
  return { ...(appris || {}), [id]: [...liste, q].slice(-max) };
}

export function ecrireAppris(appris, stockage) {
  try { (stockage || globalThis.localStorage)?.setItem(CLE_APPRIS, JSON.stringify(appris || {})); } catch { /* stockage indisponible */ }
}

export function fusionnerSynonymes(base, appris) {
  const out = { ...(base || {}) };
  for (const [k, v] of Object.entries(appris || {})) if (Array.isArray(v)) out[k] = [...(out[k] || []), ...v];
  return out;
}

/** Deux temps : catalogue (rapide, sans modèle) puis modèle si le catalogue n'a rien donné.
 *  etat(e) reçoit {phase: "recherche"|"inference"|"fini", suggestions}. Erreurs = silence (fini, sans suggestion). */
export async function deviner(url, query, cands, etat, { fetchFn = globalThis.fetch, annule = () => false } = {}) {
  const appel = async (llm) => {
    const r = await fetchFn(url.replace(/\/?$/, "/") + "hub/devine", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question: query, candidats: cands, llm }) });
    if (!r.ok) throw new Error("HTTP " + r.status);
    return (await r.json()).suggestions || [];
  };
  try {
    etat({ phase: "recherche", suggestions: [] });
    const s1 = await appel(false);
    if (annule()) return;
    if (s1.length) { etat({ phase: "fini", suggestions: s1 }); return; }
    etat({ phase: "inference", suggestions: [] });
    const s2 = await appel(true);
    if (!annule()) etat({ phase: "fini", suggestions: s2 });
  } catch {
    if (!annule()) etat({ phase: "fini", suggestions: [] });
  }
}
