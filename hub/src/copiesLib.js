// Migration › Copies et sauvegardes, Migration › Risques (livraison #856) : fonctions pures (tests : tests/copiesLib.test.mjs).

export const TYPES = {
  "réplique": "réplique pvesr", zfs: "copie ZFS", "instantané": "instantané local", vzdump: "archive vzdump", pbs: "sauvegarde PBS",
  flux: "flux zfs send", rsync: "copie rsync", "restauré": "CT/VM restauré",
};
export const TON = { ok: "good", attention: "warn", critique: "bad", info: "neutral", inconnu: "neutral", na: "neutral", aucune: "neutral" };
export const SYMBOLE = { ok: "✔", attention: "⚠", critique: "⛔", info: "ℹ", inconnu: "?", na: "–", aucune: "–" };
export const NIVEAUX = { critique: "bad", "élevé": "bad", moyen: "warn", faible: "good" };
export const AXES = [["sauvegarde", "Sauvegarde"], ["replication", "Réplication"], ["acces", "Accès aux services"], ["support", "Support"], ["noeud", "Nœud"]];

/** Filtre des invités : texte (nom, n°, nœud), verdict ou niveau, nœud. */
export function filtrer(lignes, { texte = "", etat = "", noeud = "" } = {}) {
  const t = texte.trim().toLowerCase();
  return (lignes || []).filter((l) => (!etat || l.verdict === etat || l.niveau === etat) && (!noeud || l.node === noeud)
    && (!t || `${l.name} ${l.vmid} ${l.node}`.toLowerCase().includes(t)));
}

/** Nombre de copies par type, hors du nœud seulement si `horsNoeud`. */
export function parType(copies, horsNoeud = false) {
  const out = {};
  for (const c of copies || []) if (!horsNoeud || c.survit) out[c.type] = (out[c.type] || 0) + 1;
  return out;
}

/** Âge lisible d'une copie (heures -> « 40 min », « 5 h », « 12 j »). */
export function age(h) {
  if (h == null) return "—";
  if (h < 1) return `${Math.max(1, Math.round(h * 60))} min`;
  if (h < 48) return `${Math.round(h)} h`;
  return `${Math.round(h / 24)} j`;
}

/** Libellé du volume : « ok », « plausible (31 %) », « écart (60 %) ». */
export function volume(c) {
  if (!c || c.volume === "inconnu") return "inconnu";
  const p = c.ratio != null ? ` (${Math.round(c.ratio * 100)} %)` : "";
  return c.volume === "ok" ? `ok${p}` : `${c.volume}${p}`;
}

/** Cibles saisies (une par ligne) -> liste propre, sans doublon. */
export function cibles(texte) {
  return [...new Set(String(texte || "").split(/[\n,;]+/).map((x) => x.trim()).filter(Boolean))];
}

/** Règles d'origine en texte « préfixe = nœud » (une par ligne) <-> objet. */
export function reglesTexte(o) {
  return Object.entries(o || {}).map(([k, v]) => `${k} = ${v}`).join("\n");
}
export function reglesObjet(t) {
  const out = {};
  for (const l of String(t || "").split("\n")) {
    const i = l.indexOf("=");
    if (i > 0) { const k = l.slice(0, i).trim(); const v = l.slice(i + 1).trim(); if (k && v) out[k] = v; }
  }
  return out;
}
