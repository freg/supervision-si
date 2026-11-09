// #999 : onglet ownCloud (Migration) -- présentation des instances relevées par la sonde owncloud. Logique pure, testée.

export const STATUTS = {
  actif: { libelle: "actif", ton: "ok" },
  recent: { libelle: "récent", ton: "" },
  inactif: { libelle: "inactif > 1 an", ton: "warn" },
  jamais: { libelle: "jamais connecté", ton: "warn" },
};
export const ETATS = { a_decider: "à décider", accepte: "accepté", refuse: "refusé", a_faire: "à faire", fait: "fait" };
export const TON_ETAT = { a_decider: "warn", accepte: "ok", refuse: "", a_faire: "warn", fait: "ok" };
export const FILTRES = [["tous", "tous"], ["actif", "actifs"], ["recent", "récents"], ["inactif", "inactifs"], ["jamais", "jamais"], ["doublon", "en double"], ["locale", "locaux"]];

export const go = (v) => (v == null ? "—" : `${Number(v).toLocaleString("fr-FR", { maximumFractionDigits: 1 })} Go`);
export const date = (t) => (t ? new Date(t * 1000).toLocaleDateString("fr-FR") : "—");

/** Ancienneté lisible d'un horodatage (s) : « aujourd'hui », « il y a 12 j », « il y a 3 ans ». */
export function depuis(t, maintenant = Date.now() / 1000) {
  if (!t) return "jamais";
  const j = Math.floor((maintenant - t) / 86400);
  if (j <= 0) return "aujourd'hui";
  if (j < 60) return `il y a ${j} j`;
  if (j < 730) return `il y a ${Math.round(j / 30)} mois`;
  return `il y a ${Math.round(j / 365)} ans`;
}

const sansAccent = (s) => String(s || "").normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();

/** Filtre des comptes : statut / doublon / locaux, puis texte au début d'un mot du nom (ou de l'identifiant). */
export function filtrerComptes(comptes, filtre = "tous", texte = "") {
  const t = sansAccent(texte.trim());
  return (comptes || []).filter((c) => {
    if (filtre === "doublon" && !c.doublon) return false;
    if (filtre === "locale" && c.origine !== "locale") return false;
    if (STATUTS[filtre] && c.statut !== filtre) return false;
    if (!t) return true;
    return sansAccent(`${c.nom} ${c.id}`).split(/[\s._-]+/).some((m) => m.startsWith(t));
  });
}

/** Tri des comptes : derniere (connexion récente d'abord), fichiers, corbeille, nom. */
export function trierComptes(comptes, cle = "derniere") {
  const v = (c) => (cle === "fichiers" ? c.go_fichiers : cle === "corbeille" ? c.go_corbeille : c.derniere_connexion) || 0;
  const l = [...(comptes || [])];
  return cle === "nom" ? l.sort((a, b) => String(a.nom).localeCompare(String(b.nom), "fr")) : l.sort((a, b) => v(b) - v(a));
}

/** Répartition du disque ownCloud en parts (%) : fichiers, corbeilles, versions. */
export function repartition(t) {
  const f = t?.fichiers || 0, c = t?.corbeilles || 0, v = t?.versions || 0, s = f + c + v;
  if (!s) return [];
  return [["fichiers", f, "ok"], ["corbeilles", c, "warn"], ["versions", v, ""]].map(([nom, val, ton]) => ({ nom, go: val, pct: Math.round((val * 1000) / s) / 10, ton }));
}

/** Barres d'activité : hauteur relative (0-100) au jour le plus chargé, échelle racine pour garder les petits jours visibles. */
export function barresActivite(activite) {
  const l = activite || [];
  const max = l.reduce((m, a) => Math.max(m, a.actions || 0), 0);
  return l.map((a) => ({ ...a, h: max ? Math.max(2, Math.round((Math.sqrt(a.actions || 0) / Math.sqrt(max)) * 100)) : 0 }));
}

/** Avancement des étapes (fait ou refusé = clos). */
export function avancement(etapes) {
  const l = etapes || [];
  const clos = l.filter((e) => e.etat === "fait" || e.etat === "refuse").length;
  return { clos, total: l.length, decisions: l.filter((e) => e.genre === "décision" && e.etat === "a_decider").length };
}
