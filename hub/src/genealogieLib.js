// #854 Généalogie des modèles : fonctions pures (filtres, années, lignée) partagées par les deux hubs.
export const OUVERTURE = { ouvert: ["libre", "#2e9d5b"], poids: ["poids ouverts sous conditions", "#d08a1e"], ferme: ["fermé (API)", "#7a7f8a"] };

export function sansAccents(s) {
  return String(s ?? "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

export function texteNoeud(n) {
  return sansAccents([n.id, n.nom, n.org, n.auteurs, n.date, n.tailles, n.hf, (n.types || []).join(" "), n.emploi?.ollama, n.emploi?.note].join(" "));
}

// filtres : { texte, ouverture, type, org, auto } -- auto=false masque les relevés automatiques
export function filtrer(noeuds, f = {}) {
  const mots = sansAccents(f.texte).split(/\s+/).filter(Boolean);
  return (noeuds || []).filter((n) => (!f.ouverture || n.ouverture === f.ouverture) && (!f.type || (n.types || []).includes(f.type))
    && (!f.org || n.org === f.org) && (f.auto !== false || !n.auto) && mots.every((m) => texteNoeud(n).includes(m)));
}

export function valeurs(noeuds, cle) {
  const s = new Set();
  for (const n of noeuds || []) for (const v of [].concat(n[cle] ?? [])) if (v) s.add(v);
  return [...s].sort((a, b) => a.localeCompare(b, "fr"));
}

// [[année, [nœuds triés par date puis nom]]] dans l'ordre chronologique
export function parAnnee(noeuds) {
  const m = new Map();
  for (const n of [...(noeuds || [])].sort((a, b) => (a.date || "").localeCompare(b.date || "") || (a.nom || "").localeCompare(b.nom || "", "fr"))) {
    const a = (n.date || "????").slice(0, 4);
    if (!m.has(a)) m.set(a, []);
    m.get(a).push(n);
  }
  return [...m.entries()];
}

export function enfantsDe(noeuds) {
  const e = {};
  for (const n of noeuds || []) for (const p of n.parents || []) (e[p.id] ||= []).push({ id: n.id, relation: p.relation });
  return e;
}

// ascendants / descendants avec la distance (même calcul que genealogie.lignee côté API)
export function lignee(noeuds, id) {
  const par = Object.fromEntries((noeuds || []).map((n) => [n.id, n.parents || []]));
  const enf = enfantsDe(noeuds);
  const parcours = (suivants) => {
    const vus = new Map(); let front = [id]; let d = 0;
    while (front.length && d < 50) {
      d += 1; const prochain = [];
      for (const x of front) for (const s of suivants(x)) if (!vus.has(s.id) && s.id !== id) { vus.set(s.id, d); prochain.push(s.id); }
      front = prochain;
    }
    return [...vus.entries()].map(([i, distance]) => ({ id: i, distance })).sort((a, b) => a.distance - b.distance || a.id.localeCompare(b.id));
  };
  return { ascendants: parcours((x) => par[x] || []), descendants: parcours((x) => enf[x] || []) };
}

// chemin le plus court vers l'origine (le Transformer) : [id, parent, grand-parent, ...]
export function cheminOrigine(noeuds, id) {
  const par = Object.fromEntries((noeuds || []).map((n) => [n.id, (n.parents || []).map((p) => p.id)]));
  const prec = new Map([[id, null]]); let front = [id];
  while (front.length) {
    const prochain = [];
    for (const x of front) {
      if (!(par[x] || []).length) { const ch = []; for (let y = x; y !== null; y = prec.get(y)) ch.unshift(y); return ch; }
      for (const p of par[x]) if (!prec.has(p)) { prec.set(p, x); prochain.push(p); }
    }
    front = prochain;
  }
  return [id];
}

export function moisLisible(d) {
  const M = ["janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc."];
  const m = /^(\d{4})-(\d{2})/.exec(d || "");
  return m ? `${M[Number(m[2]) - 1] || ""} ${m[1]}` : (d || "?");
}
