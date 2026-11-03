// Supervision des flux éditeurs (#962) -- logique PURE, testée (hub/tests/fluxLib.test.mjs).
export const STATUTS = {
  OK: { libelle: "ouvert", couleur: "var(--ok)", fond: "var(--ok-bg)" },
  NS: { libelle: "non servi par cet hôte", couleur: "var(--muted)", fond: "var(--panel)" },
  KO: { libelle: "fermé / filtré / DNS", couleur: "var(--danger)", fond: "var(--danger-bg)" },
  INSPECTE: { libelle: "inspection SSL", couleur: "var(--warning)", fond: "var(--warning-bg)" },
  OUVERT: { libelle: "ouvert alors qu'il devrait être fermé", couleur: "var(--danger)", fond: "var(--danger-bg)" },
  CERT: { libelle: "certificat expiré ou à moins de 14 jours", couleur: "var(--warning)", fond: "var(--warning-bg)" },
  "?": { libelle: "UDP non vérifiable", couleur: "var(--muted)", fond: "var(--panel)" },
  IGN: { libelle: "ignoré (ne compte plus, n'alerte plus)", couleur: "var(--muted)", fond: "var(--panel)" },
};
export const SITE_KEY = "hub.flux.site";

export function resumeBilan(b) {
  if (!b) return "aucun passage";
  const p = [`${b.OK || 0} ouvert(s)`];
  if (b.KO) p.push(`${b.KO} fermé(s)`);
  if (b.INSPECTE) p.push(`${b.INSPECTE} inspecté(s)`);
  if (b.OUVERT) p.push(`${b.OUVERT} ouvert(s) à tort`);
  if (b.CERT) p.push(`${b.CERT} certificat(s) à renouveler`);
  if (b.NS) p.push(`${b.NS} non servi(s)`);
  if (b["?"]) p.push(`${b["?"]} UDP non vérifiable(s)`);
  return p.join(" · ");
}

export function age(at, maintenant) {
  if (!at) return "jamais";
  const s = Math.max(0, Math.round((maintenant || Date.now() / 1000) - at));
  return s < 90 ? `il y a ${s} s` : s < 5400 ? `il y a ${Math.round(s / 60)} min` : s < 172800 ? `il y a ${Math.round(s / 3600)} h` : `il y a ${Math.round(s / 86400)} j`;
}

/** Matrice filtrée : seulement les hôtes ayant un statut problématique (KO / INSPECTE) si demandé, recherche texte. */
export function filtrerMatrice(m, { problemes = false, q = "" } = {}) {
  if (!m) return { colonnes: [], lignes: [] };
  const s = q.trim().toLowerCase();
  const lignes = m.lignes.filter((l) => (!problemes || Object.values(l.cellules).some((v) => ["KO", "INSPECTE", "OUVERT", "CERT"].includes(v)))
    && (!s || `${l.hote} ${l.groupe}`.toLowerCase().includes(s)));
  return { colonnes: m.colonnes, lignes };
}

/** Durée d'une alerte (ouverte : jusqu'à maintenant). */
export function dureeAlerte(a, maintenant) {
  const fin = a.fin || maintenant || Date.now() / 1000;
  const s = Math.max(0, fin - a.debut);
  return s < 3600 ? `${Math.round(s / 60)} min` : s < 172800 ? `${Math.round(s / 3600)} h` : `${Math.round(s / 86400)} j`;
}

/** Commandes de mise en place (copiables) pour un site : premier passage, puis supervision continue par cron. */
export function commandesSite(hub, siteId, listes, iface) {
  const l = (listes || []).join(",") || "google";
  const env = `HUB=${hub} SITE=${siteId} SOURCE="$(hostname)${iface ? `-${iface}` : ""}"${iface ? ` IFACE=${iface}` : ""}`;
  return [
    "# 1. récupérer le script (dépôt supervision-si : nebula/tools/test-flux.sh) sur la machine du site, puis :",
    `${env} bash ~/test-flux.sh -l ${l}`,
    "# 2. supervision continue : les réglages sont mémorisés dans ~/.test-flux.env",
    `( crontab -l 2>/dev/null; echo '17 * * * * bash $HOME/test-flux.sh -q >/dev/null 2>&1' ) | crontab -`,
  ].join("\n");
}

/** Une ligne de liste « groupe;hôte;proto;ports » lisible. */
export function exempleListe(nom) {
  const g = (nom || "editeur").toLowerCase().replace(/[^a-z0-9]+/g, "-");
  return `# une cible par ligne : groupe;hôte;proto;ports[;ferme] (ou « hôte proto ports », ou « hôte:port »)\n# 5e champ « ferme » : le port doit rester FERMÉ vu de la source (ex. SSH ou base de données vus d'Internet)\n${g};api.exemple.com;tcp;443\n${g};push.exemple.com;tcp;443,5223-5225\n${g};api.exemple.com;tcp;22,3306;ferme`;
}

/** Lignes d'un passage pour le visualiseur : filtre « a_traiter » (KO, NS, alertes, non ignorées), « ignores », « tous » ; tri par gravité. */
const ORDRE = { OUVERT: 0, KO: 1, CERT: 2, INSPECTE: 3, NS: 4, "?": 5, OK: 6 };
export function lignesPassage(lignes, filtre = "a_traiter", q = "") {
  const s = q.trim().toLowerCase();
  return (lignes || []).filter((l) => (filtre === "tous" || (filtre === "ignores" ? l.ignore : !l.ignore && l.statut !== "OK" && l.statut !== "?"))
    && (!s || `${l.hote} ${l.groupe} ${l.port} ${l.detail}`.toLowerCase().includes(s)))
    .sort((a, b) => (ORDRE[a.statut] ?? 9) - (ORDRE[b.statut] ?? 9) || a.hote.localeCompare(b.hote) || a.port - b.port);
}
