// Activité d'un client (livraison #1002) -- logique pure, testée (hub/tests/activiteLib.test.mjs).

const nf = (n, d = 1) => Number(n).toLocaleString("fr-FR", { maximumFractionDigits: d, minimumFractionDigits: 0 });

export function octetsFr(n) {
  if (n == null || Number.isNaN(Number(n))) return "—";
  const u = ["o", "Ko", "Mo", "Go", "To"];
  let v = Number(n), i = 0;
  while (v >= 1000 && i < u.length - 1) { v /= 1000; i += 1; }
  return `${nf(v, v < 10 && i ? 1 : 0)} ${u[i]}`;
}

const pct = (x) => (x == null ? "—" : `${nf(x * 100, 0)} %`);

/** Profil (API /client-history/activite) -> lignes lisibles. */
export function resumeActivite(p) {
  if (!p) return [];
  const l = [];
  if (!p.jours_vus) return [`Aucune présence enregistrée sur ${p.jours} jours.`];
  l.push(`Présent ${p.jours_vus} jour(s) sur ${p.jours}, ${nf(p.heures_par_jour)} h par jour en moyenne${p.continu ? " — toujours présent" : ""}.`);
  l.push(`Part de la nuit (0 h – 6 h) : ${pct(p.part_nuit)} ; part du week-end : ${pct(p.part_weekend)}.`);
  const r = [p.filaire && "filaire", p.wifi && `Wi-Fi${(p.ssids || []).length ? ` (${p.ssids.join(", ")})` : ""}`].filter(Boolean).join(" et ") || "inconnu";
  l.push(`Raccordement : ${r}${(p.bornes || []).length > 1 ? ` — ${p.bornes.length} équipements (mobile)` : ""}${(p.vlans || []).length ? ` — VLAN ${p.vlans.join(", ")}` : ""}.`);
  const v = p.volumes || {};
  if (v.mesures) {
    const reg = v.regularite_cv == null || v.mesures < 6 ? "" : v.regularite_cv < 0.3 ? " — très régulier" : v.regularite_cv > 1 ? " — par rafales" : "";   // #1004 : pas de verdict sur 1 relève
    l.push(`Volumes Wi-Fi (${v.mesures} relèves) : ${octetsFr(v.moyenne_heure)} par heure en moyenne, pointe ${octetsFr(v.pointe_heure)} par heure${reg} ; ${pct(v.part_descendant)} reçu.`);
  } else {
    l.push("Volumes : non publiés par Nebula pour ce client (seuls les clients Wi-Fi ont des volumes).");
  }
  return l;
}

/** Histogramme 24 h -> hauteurs relatives 0..1. */
export function barres(histo = []) {
  const m = histo.reduce((a, b) => Math.max(a, b), 0);
  return histo.map((x) => (m ? x / m : 0));
}

// #1003 : catégorie proposée par les éléments et le comportement (API /client-history/categorie)
export function resumeCategorie(c, libelle = "Catégorie") {
  const e = libelle === "Catégorie" ? "e" : "";   // #1007 : « catégorie » féminin, « type » masculin
  if (!c || !c.categorie) return `${libelle} : pas assez d'éléments pour en proposer un${e}.`;
  if (c.decision) return `${libelle} confirmé${e} : ${c.categorie}${c.decision.par ? ` (par ${c.decision.par})` : ""}${c.proposee && c.proposee !== c.categorie ? ` — le hub proposait ${c.proposee}` : ""}`;
  return `${libelle} proposé${e} : ${c.categorie} — confiance ${c.confiance} %${c.incertain ? ` (incertain${e})` : ""}`;
}

// #1004 : niveaux de certitude (menus de filtre, pastille de la colonne Catégorie)
export const NIVEAU_COULEUR = { "confirmée": "var(--ok)", forte: "var(--ok)", moyenne: "var(--warning)", faible: "var(--danger)", aucune: "var(--muted)" };

function _cellule(o, motAucun) {
  if (!o || !o.niveau) return { texte: "—", couleur: "var(--muted)" };
  if (!o.categorie) return { texte: motAucun, couleur: NIVEAU_COULEUR.aucune };
  return { texte: o.niveau === "confirmée" ? `✔ ${o.categorie}` : `${o.categorie} · ${o.confiance} %`, couleur: NIVEAU_COULEUR[o.niveau] || "var(--muted)" };
}
export function celluleCategorie(r) { return _cellule(r && { categorie: r.categorie, confiance: r.confiance, niveau: r.niveau }, "aucune"); }
export function celluleType(r) { return _cellule(r && { categorie: r.type, confiance: r.confiance_type, niveau: r.niveau_type }, "aucun"); }   // #1007 : axe type

export function texteCategorie(c, libelle = "Catégorie") {
  if (!c) return "";
  const l = [resumeCategorie(c, libelle), ""];
  for (const h of c.hypotheses || []) {
    l.push(`${h.categorie} : ${h.score}/100`);
    for (const p of h.preuves || []) l.push(`  ${p.poids > 0 ? "+" : ""}${p.poids}  ${p.texte}`);
    l.push("");
  }
  if ((c.singularites || []).length) {
    l.push(`Singularités (par rapport aux ${c.population ?? "?"} clients du site sur 14 jours) :`);
    for (const s of c.singularites) l.push(`  ${s.texte}`);
  }
  return l.join("\n").trim();
}
