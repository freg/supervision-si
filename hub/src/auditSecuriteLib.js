// Audit de sécurité réseau (#958) -- logique PURE, testée (hub/tests/auditSecuriteLib.test.mjs).
// Les constats, la matrice et les préconisations viennent de nebula-api (audit_securite.py) ; ici : présentation,
// filtres, placement dans la grille, commandes d'aide, exports.
export const COULEUR_NIVEAU = { critique: "var(--danger)", eleve: "var(--warning)", modere: "var(--accent)", faible: "var(--ok)" };
export const FOND_NIVEAU = { critique: "var(--danger-bg)", eleve: "var(--warning-bg)", modere: "var(--panel)", faible: "var(--ok-bg)" };
export const LIBELLE_PROBA = { 1: "rare", 2: "possible", 3: "probable", 4: "certain" };
export const LIBELLE_IMPACT = { 1: "mineur", 2: "gênant", 3: "grave", 4: "majeur" };
export const SITE_KEY = "hub.audit.site";

/** Niveau d'une case de la matrice (même seuils que le serveur). */
export function niveauCase(p, i) {
  const s = p * i;
  return s >= 12 ? "critique" : s >= 8 ? "eleve" : s >= 4 ? "modere" : "faible";
}

/** Filtre les constats : domaine, niveau, état, case (p,i), texte libre. */
export function filtrer(constats, f = {}) {
  const q = (f.q || "").trim().toLowerCase();
  return (constats || []).filter((c) =>
    (!f.domaine || c.domaine === f.domaine) &&
    (!f.niveau || c.niveau === f.niveau) &&
    (!f.etat || (c.etat || "a_traiter") === f.etat) &&
    (!f.cas || (c.probabilite === f.cas.p && c.impact === f.cas.i)) &&
    (!q || [c.titre, c.preuve, c.preconisation, c.element].join(" ").toLowerCase().includes(q)));
}

/** Grille 4×4 pour le rendu : lignes impact 4→1, colonnes probabilité 1→4, chaque case = {p, i, n, niveau}. */
export function grille(matrice) {
  const cases = (matrice && matrice.cases) || {};
  return [4, 3, 2, 1].map((i) => [1, 2, 3, 4].map((p) => ({ p, i, n: ((cases[i] || {})[p] || []).length, niveau: niveauCase(p, i) })));
}

/** Résumé en une ligne pour l'en-tête. */
export function resume(matrice) {
  const n = (matrice && matrice.par_niveau) || {};
  return `${matrice?.total || 0} constat(s) — ${n.critique || 0} critique(s), ${n.eleve || 0} élevé(s), ${n.modere || 0} modéré(s), ${n.faible || 0} faible(s)`;
}

/** Commandes d'aide, chemins complets, sans donnée de site (le JSON reste hors dépôt). */
export function commandesAide(hub, siteId) {
  const s = siteId || "<site>";
  return {
    proxmox: `# sur l'hyperviseur, en root (lecture seule) :\nsh audit-proxmox.sh > audit-proxmox-$(hostname).json\n# puis envoi au hub :\ncurl -s -X POST "${hub}/sites/${s}/audit/importer" -H 'Content-Type: application/json' -d "{\\"source\\":\\"proxmox\\",\\"donnees\\":$(cat audit-proxmox-$(hostname).json)}"`,
    hote: `# depuis une machine du même réseau (mini-PC, portable) :\nsh audit-hote.sh <ip> <nom> > audit-hote-<nom>.json\ncurl -s -X POST "${hub}/sites/${s}/audit/importer" -H 'Content-Type: application/json' -d "{\\"source\\":\\"hote\\",\\"donnees\\":$(cat audit-hote-<nom>.json)}"`,
    scripts: "nebula/tools/audit-proxmox.sh et nebula/tools/audit-hote.sh (dépôt supervision-si)",
  };
}

/** Texte copiable d'un constat (mini bouton de détail). */
export function texteConstat(c, domaines = {}) {
  return [`${c.titre}`, `Domaine : ${domaines[c.domaine] || c.domaine}`, `Niveau : ${c.niveau} (probabilité ${c.probabilite} × impact ${c.impact} = ${c.score})`,
    `Preuve : ${c.preuve || "—"}`, `Préconisation : ${c.preconisation || "—"}`, `Effort : ${c.effort}`, `Source : ${c.source}${c.element ? ` (${c.element})` : ""}`,
    c.note ? `Note : ${c.note}` : null].filter(Boolean).join("\n");
}

/** Âge d'une collecte. */
export function ageCollecte(at, maintenant) {
  if (!at) return "jamais";
  const s = Math.max(0, Math.round((maintenant || Date.now() / 1000) - at));
  return s < 3600 ? `il y a ${Math.max(1, Math.round(s / 60))} min` : s < 86400 ? `il y a ${Math.round(s / 3600)} h` : `il y a ${Math.round(s / 86400)} j`;
}
