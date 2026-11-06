// Tuile « Démonstrations » (#993) : logique pure du choix d'un terminal pour les parcours qui ont les variables
// « terminal » (nom dans le registre des équipements du site) et/ou « nom_reseau » (nom annoncé sur le réseau, vu par
// Nebula). Source : nebula-api /sites/<site>/reperage/equipements (registre « Équipements du site »).

export const VARIABLES_TERMINAL = ["terminal", "nom_reseau"];

/** Le parcours demande-t-il un terminal ? */
export function demandeTerminal(variables) {
  return Object.keys(variables || {}).some((k) => VARIABLES_TERMINAL.includes(k));
}

/** Équipements du registre -> [{terminal, nom_reseau, libelle}] triés ; nom réseau = celui vu par Nebula, sinon le nom
 *  du registre aux espaces remplacés par des tirets (convention des tablettes : « E11 AmpIm » -> « E11-AmpIm »). */
export function optionsTerminaux(equipements) {
  const vus = new Set();
  const out = [];
  for (const e of equipements || []) {
    const nom = String(e?.nom || "").trim();
    if (!nom || vus.has(nom)) continue;
    vus.add(nom);
    const reseau = String(e?.nebula?.nom || "").trim() || nom.replace(/\s+/g, "-");
    out.push({ terminal: nom, nom_reseau: reseau, vu: !!e?.nebula, libelle: reseau === nom ? nom : `${nom} (${reseau})` });
  }
  return out.sort((a, b) => a.terminal.localeCompare(b.terminal, "fr", { numeric: true }));
}

/** Valeurs à poser dans les variables du parcours pour l'option choisie (seulement celles que le parcours déclare). */
export function valeursTerminal(option, variables) {
  const out = {};
  for (const k of VARIABLES_TERMINAL) if (option && k in (variables || {})) out[k] = option[k];
  return out;
}
