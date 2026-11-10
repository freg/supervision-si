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
    const reg = v.regularite_cv == null ? "" : v.regularite_cv < 0.3 ? " — très régulier" : v.regularite_cv > 1 ? " — par rafales" : "";
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
