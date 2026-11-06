// #986 : onglet « Espaces disques / données » -- logique pure (testée sous Node).
export const CRITERES = [["role", "rôle"], ["lan", "LAN / site"], ["hebergeur", "hébergeur"]];
export const NIVEAUX = { critique: "var(--danger)", attention: "var(--warning)", ok: "var(--ok)", inconnu: "var(--muted)" };

/** Octets -> « 12,4 To » (unités binaires, virgule décimale). */
export function taille(o) {
  if (typeof o !== "number" || !isFinite(o) || o <= 0) return "—";
  for (const [u, k] of [["To", 1024 ** 4], ["Go", 1024 ** 3], ["Mo", 1024 ** 2]]) if (o >= k) return `${(o / k).toFixed(1).replace(".", ",")} ${u}`;
  return `${o} o`;
}

export function saturationTexte(jours) {
  if (jours == null) return "";
  if (jours <= 0) return "plein";
  if (jours < 60) return `plein dans ${jours} j`;
  if (jours < 730) return `plein dans ${Math.round(jours / 30)} mois`;
  return "plus de 2 ans";
}

export function penteTexte(o) {
  if (typeof o !== "number" || !o) return "stable";
  const s = o > 0 ? "+" : "−";
  return `${s}${taille(Math.abs(o))}/j`;
}

/** Filtre : niveau (tous | a-surveiller) et texte (nom, classement, modèles de disques). */
export function filtrer(machines, { niveau = "tous", q = "" } = {}) {
  const t = String(q || "").toLowerCase().trim();
  return (machines || []).filter((m) => (niveau !== "a-surveiller" || ["critique", "attention"].includes(m.niveau))
    && (!t || [m.nom, m.type, ...Object.values(m.classement || {}), m.materiel?.modele, ...(m.materiel?.disques || []).map((d) => d.modele)]
      .some((x) => String(x || "").toLowerCase().includes(t))));
}

/** Regroupe par critère (rôle, LAN, hébergeur) : groupes triés par gravité puis par nom. */
export function grouper(machines, critere) {
  const g = new Map();
  for (const m of machines || []) {
    const k = m.classement?.[critere] || "?";
    if (!g.has(k)) g.set(k, []);
    g.get(k).push(m);
  }
  const rang = (ms) => (ms.some((m) => m.niveau === "critique") ? 0 : ms.some((m) => m.niveau === "attention") ? 1 : 2);
  return [...g.entries()].map(([valeur, ms]) => ({ valeur, machines: ms, taille: ms.reduce((s, m) => s + (m.taille || 0), 0), occupe: ms.reduce((s, m) => s + (m.occupe || 0), 0),
    critique: ms.filter((m) => m.niveau === "critique").length, attention: ms.filter((m) => m.niveau === "attention").length }))
    .sort((a, b) => rang(a.machines) - rang(b.machines) || a.valeur.localeCompare(b.valeur, "fr"));
}

/** Valeurs déjà utilisées pour un critère (suggestions de saisie). */
export const valeurs = (machines, critere) => [...new Set((machines || []).map((m) => m.classement?.[critere]).filter(Boolean))].sort((a, b) => a.localeCompare(b, "fr"));
