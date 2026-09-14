// Mode d'affichage (livraison #501) -- demandé explicitement : « les
// utilisateurs de cette appli sont habitués à des interfaces très
// simples sans fioriture ; cet écran est trop riche, la colonne
// centrale suffit, sans icône, en tableau tout aligné à gauche » --
// puis : « conserve le premier design mais en option paramétrable ».
// Donc : "simple" (colonne centrale seule en tableau, aucun pictogramme,
// DÉFAUT depuis #502 -- « inverse le design par défaut ») ou "complet"
// (design d'origine, en option). Choix par navigateur
// (localStorage), défaut d'installation par VITE_VAULT_UI_MODE.
export const UI_MODE_KEY = "supervision-si:vault:ui-mode";
export const UI_MODES = ["complet", "simple"];
export function loadUiMode(defaultMode = "simple", storage = globalThis.localStorage) {
  try {
    const v = storage && storage.getItem(UI_MODE_KEY);
    if (UI_MODES.includes(v)) return v;
  } catch { /* stockage indisponible : défaut */ }
  return UI_MODES.includes(defaultMode) ? defaultMode : "simple";
}
export function saveUiMode(mode, storage = globalThis.localStorage) {
  try { storage && storage.setItem(UI_MODE_KEY, mode); } catch { /* jamais bloquant */ }
}
