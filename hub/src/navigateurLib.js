// Logique pure de la tuile « Navigateur des hôtes » (livraison #798), testée sous Node.

/** URL de l'écran noVNC servi par tls-proxy sous /navigateur/<nom>/ (même origine que le hub). */
export function ecranUrl(nom, { scale = true, viewOnly = false } = {}) {
  const p = new URLSearchParams({ autoconnect: "1", reconnect: "1", resize: scale ? "scale" : "remote", path: `navigateur/${nom}/websockify` });
  if (viewOnly) p.set("view_only", "1");
  return `/navigateur/${encodeURIComponent(nom)}/vnc.html?${p.toString()}`;
}

export const EXEMPLE_ETAPES = [
  { action: "goto", value: "/" },
  { action: "expect_visible", selector: "body" },
  { action: "screenshot", note: "page d'accueil" },
];

/** Texte JSON des étapes -> {etapes} ou {erreur} (contrôle léger, l'automate revalide). */
export function lireEtapes(texte) {
  let v;
  try { v = JSON.parse(texte || ""); } catch (e) { return { erreur: "JSON invalide : " + e.message }; }
  if (!Array.isArray(v) || !v.length) return { erreur: "liste d'étapes non vide attendue" };
  const i = v.findIndex((s) => !s || typeof s !== "object" || !s.action);
  if (i >= 0) return { erreur: `étape ${i + 1} : « action » manquante` };
  return { etapes: v };
}

/** Commande du central (type navigateur) -> {etat: attente|ok|ko|confirmation, texte}. */
export function etatCommande(c) {
  if (!c) return { etat: "attente", texte: "…" };
  if (c.status === "pending") return { etat: "attente", texte: "en attente de l'agent (relève des commandes)" };
  const r = c.result || {};
  const x = r.result || {};
  if (x.statut === "confirmation") return { etat: "confirmation", texte: "arrêté avant une étape qui écrit : confirmation attendue" };
  if (c.status === "done") return { etat: "ok", texte: x.titre ? `fait · ${x.titre}` : "fait" };
  return { etat: "ko", texte: r.error || x.error || "échec" };
}

/** Image base64 (JPEG de l'automate) -> data URL, ou "" */
export const imageDe = (b64) => (b64 ? `data:image/jpeg;base64,${b64}` : "");

/** Liste triée des navigateurs, libellé de repli. */
export function trierNavigateurs(liste) {
  return [...(liste || [])].map((n) => ({ ...n, libelle: n.libelle || n.nom })).sort((a, b) => a.libelle.localeCompare(b.libelle, "fr"));
}
