// Mode d'affichage (livraison #501) -- demandé explicitement : « les
// utilisateurs de cette appli sont habitués à des interfaces très
// simples sans fioriture ; cet écran est trop riche, la colonne
// centrale suffit, sans icône, en tableau tout aligné à gauche » --
// puis : « conserve le premier design mais en option paramétrable ».
// #502 : « simple » devient le défaut. #507 : « le même design que les
// demandes de SAV » -- mode « tableur » : la liste des codes rendue
// comme la saisie en tableau des demandes (police Calibri, en-tête
// plein, lettres de colonnes, numéros de lignes, quadrillage, fond
// papier), qui devient le défaut ; « simple » (tableau sobre aux
// couleurs du thème) et « complet » (design d'origine) restent en
// option. Choix par navigateur (localStorage), défaut d'installation par
// VITE_VAULT_UI_MODE.
export const UI_MODE_KEY = "supervision-si:vault:ui-mode";
export const UI_MODES = ["tableur", "simple", "complet"];
export const DEFAULT_UI_MODE = "tableur";
export const UI_MODE_LABELS = { tableur: "Affichage tableur", simple: "Affichage simple", complet: "Affichage complet" };
export const UI_MODE_TITLES = {
  tableur: "Liste des codes comme la saisie en tableau des demandes (Calibri, en-tête plein, lettres de colonnes, numéros de lignes)",
  simple: "Colonne centrale seule, en tableau sobre aux couleurs du thème, sans pictogramme",
  complet: "Design d'origine : trois colonnes, pictogrammes",
};
export function loadUiMode(defaultMode = DEFAULT_UI_MODE, storage = globalThis.localStorage) {
  try {
    const v = storage && storage.getItem(UI_MODE_KEY);
    if (UI_MODES.includes(v)) return v;
  } catch { /* stockage indisponible : défaut */ }
  return UI_MODES.includes(defaultMode) ? defaultMode : DEFAULT_UI_MODE;
}
export function saveUiMode(mode, storage = globalThis.localStorage) {
  try { storage && storage.setItem(UI_MODE_KEY, mode); } catch { /* jamais bloquant */ }
}
/** Mode suivant dans le cycle tableur -> simple -> complet -> tableur. */
export function nextUiMode(mode) {
  const i = UI_MODES.indexOf(mode);
  return UI_MODES[(i < 0 ? 0 : i + 1) % UI_MODES.length];
}
/** « simple » et « tableur » partagent la mise en page dépouillée (colonne centrale seule, aucun pictogramme). */
export function isPlainMode(mode) {
  return mode === "simple" || mode === "tableur";
}
