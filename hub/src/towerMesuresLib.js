// #995 : mesure des mises à jour de la tour -- durée et charge de l'hôte par étape (relevés du runner toutes les 5 s),
// comparaison avec les lancements à la main (.maj-historique.jsonl). Logique pure, testée sous Node.

/** Ton d'une charge (load1) rapportée au nombre de cœurs : ok < 1 par cœur, warn < 2, bad au-delà. */
export function tonCharge(load, coeurs) {
  if (load == null) return "";
  const c = coeurs > 0 ? coeurs : 1;
  return load < c ? "ok" : load < 2 * c ? "warn" : "bad";
}

/** Ton de l'attente disque (iowait en %) : ok < 10, warn < 30, bad au-delà. */
export const tonIo = (p) => (p == null ? "" : p < 10 ? "ok" : p < 30 ? "warn" : "bad");

export function duree(s) {
  if (s == null) return "—";
  if (s < 60) return `${s} s`;
  const m = Math.floor(s / 60), r = s % 60;
  return m < 60 ? `${m} min ${String(r).padStart(2, "0")}` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, "0")}`;
}

export const nombre = (v, d = 1) => (v == null ? "—" : Number(v).toLocaleString("fr-FR", { maximumFractionDigits: d }));

/** Étape la plus lourde (durée) -- celle à regarder d'abord. */
export function etapeLaPlusLongue(m) {
  return (m?.etapes || []).reduce((a, e) => (e.duree_s != null && (!a || e.duree_s > a.duree_s) ? e : a), null);
}

/** Phrase de comparaison à la main / par la tour (médianes par service construit). */
export function texteComparaison(c) {
  const main = c?.main, tour = c?.tour;
  if (!main && !tour) return "pas encore de construction mesurée";
  const p = (x, nom) => (x ? `${nom} : ${duree(x.secondes_par_service)} par service (${nombre(x.services_par_lancement, 0)} service(s) par lancement, ${x.n} lancement(s))` : `${nom} : pas de mesure`);
  let s = `${p(main, "à la main")} · ${p(tour, "par la tour")}`;
  if (main && tour && main.secondes_par_service > 0) s += ` · rapport ${nombre(tour.secondes_par_service / main.secondes_par_service, 1)}×`;
  return s;
}
