// #932 : historique des tests de charge d'un poste -- résumé d'un relevé pour la liste, et matrice de comparaison
// côte à côte (pour consultation et impression). Module pur, testé par hub/tests/chargeHistorique.test.mjs.

/** Ton d'un verdict (cohérent avec PosteWindowsView) : « non concluant » = orange, défaut = rouge. */
export const tonVerdict = (v) => (v === "aucun défaut reproduit" ? "good" : v === "interrompu" ? "neutral" : v === "non concluant" ? "warn" : "bad");

const nb = (x) => (x == null ? "—" : x);
const tempMax = (arr) => { const v = (arr || []).map((t) => t && t.celsius).filter((c) => typeof c === "number"); return v.length ? Math.max(...v) : null; };

/** Résumé compact d'un run (relevé {at, data}) pour une ligne de tableau. */
export function resumeRun(run) {
  const d = (run && run.data) || {};
  const p = d.processeur, m = d.memoire, dk = d.disque;
  const alertes = d.alerts || [];
  return {
    at: run && run.at,
    debut: d.debut || (run && run.at),
    verdict: d.verdict || "—",
    ton: tonVerdict(d.verdict),
    epreuves: (d.epreuves || []).join(", "),
    cpu: p ? `${nb(p.coeurs_finis ?? p.coeurs)}/${nb(p.coeurs)} cœurs${p.gel_max_s >= 2 ? `, figé ${p.gel_max_s}s` : ""}${p.erreurs_calcul ? `, ${p.erreurs_calcul} err.` : ""}` : "—",
    mem: m ? `${nb(m.mo)} Mo, ${nb(m.blocs_errones)} err.` : "—",
    disque: dk ? `${nb(dk.ecriture_mo_s)}/${nb(dk.lecture_mo_s)} Mo/s${dk.identique === false ? ", DIFFÉRENTE" : dk.statut && dk.statut !== "ok" ? `, ${dk.statut}` : ""}` : "—",
    temp: tempMax(d.temperatures_apres),
    alertes: alertes.length,
    critiques: alertes.filter((a) => a.severity === "critical").length,
  };
}

/** Lignes de métriques pour la comparaison côte à côte de plusieurs runs. */
export const METRIQUES = [
  ["Verdict", (d) => d.verdict || "—"],
  ["Épreuves", (d) => (d.epreuves || []).join(", ") || "—"],
  ["Processeur — cœurs finis", (d) => (d.processeur ? `${nb(d.processeur.coeurs_finis ?? d.processeur.coeurs)}/${nb(d.processeur.coeurs)}` : "—")],
  ["Processeur — gel max", (d) => (d.processeur && d.processeur.gel_max_s != null ? `${d.processeur.gel_max_s} s` : "—")],
  ["Processeur — erreurs calcul", (d) => (d.processeur ? nb(d.processeur.erreurs_calcul) : "—")],
  ["Mémoire — testée", (d) => (d.memoire ? `${nb(d.memoire.mo)} Mo` : "—")],
  ["Mémoire — blocs erronés", (d) => (d.memoire ? nb(d.memoire.blocs_errones) : "—")],
  ["Disque — écriture", (d) => (d.disque && d.disque.ecriture_mo_s != null ? `${d.disque.ecriture_mo_s} Mo/s` : "—")],
  ["Disque — lecture", (d) => (d.disque && d.disque.lecture_mo_s != null ? `${d.disque.lecture_mo_s} Mo/s` : "—")],
  ["Disque — relecture", (d) => (d.disque ? (d.disque.identique === true ? "identique" : d.disque.identique === false ? "DIFFÉRENTE" : d.disque.statut || d.disque.erreur || "—") : "—")],
  ["Température après (max)", (d) => { const t = tempMax(d.temperatures_apres); return t == null ? "—" : `${t} °C`; }],
  ["Alertes", (d) => String((d.alerts || []).length)],
];

/** Matrice de comparaison : { entetes:[{at,debut,verdict,ton}], lignes:[[label, v1, v2,…]] }. */
export function comparer(runs) {
  const list = runs || [];
  const entetes = list.map((r) => ({ at: r.at, debut: (r.data || {}).debut || r.at, verdict: (r.data || {}).verdict || "—", ton: tonVerdict((r.data || {}).verdict) }));
  const lignes = METRIQUES.map(([label, f]) => [label, ...list.map((r) => f(r.data || {}))]);
  return { entetes, lignes };
}
