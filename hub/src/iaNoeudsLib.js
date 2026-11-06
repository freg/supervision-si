// #988 : nœuds IA -- Hermes, atelier de codage et apprentissage (hermes-web du hub perso de prodia / preprodia), ouverts
// dans le hub sous /ia/<nœud>/ au seul groupe Keycloak « ia » (et aux administrateurs). Logique pure, testée sous Node.
// La passerelle contrôle chaque requête (auth_request -> services-api /ia/acces) ; les iframes ne pouvant pas envoyer
// d'en-tête Authorization, le hub recopie son jeton d'accès dans un cookie limité au chemin /ia/.

export const GROUPE_IA = "ia";
export const COOKIE_IA = "si_ia_jeton";
export const VUES_IA = ["hermes", "ia-atelier", "ia-apprentissage"];
export const PAGES_IA = [
  { id: "", vue: "hermes", label: "Hermes", detail: "dialogue sous garde-fous, console d'activité, rejeu QA" },
  { id: "atelier", vue: "ia-atelier", label: "Atelier de codage", detail: "backlog, pilote compact, architecte / développeur, rendus" },
  { id: "apprentissage", vue: "ia-apprentissage", label: "Apprentissage", detail: "veilleur, introspecteur, mémoire native d'Hermes" },
];

const norm = (g) => String(g || "").replace(/^\/+/, "").toLowerCase();

/** Groupes Keycloak -> accès aux nœuds IA (groupe « ia », administrateurs, admin_hub). */
export function accesIa(groups) {
  const gs = (groups || []).map(norm);
  return gs.includes(GROUPE_IA) || gs.includes("administrateurs") || gs.includes("admin_hub");
}

/** Retire les tuiles IA d'une liste de vues quand la personne n'y a pas droit. */
export function filtrerVuesIa(vues, groups) {
  if (accesIa(groups)) return vues;
  const out = new Set(vues);
  for (const v of VUES_IA) out.delete(v);
  return out;
}

const NOM = /^[a-z0-9][a-z0-9-]{0,30}$/;

/** URL d'une page d'un nœud : cheminNoeud("prodia", "atelier") -> "/ia/prodia/atelier". */
export function cheminNoeud(noeud, page = "") {
  if (!NOM.test(String(noeud || ""))) return null;
  return `/ia/${noeud}/${page || ""}`;
}

/** Nœud retenu : celui mémorisé s'il existe encore, sinon le premier. */
export function noeudRetenu(noeuds, memo) {
  const l = Array.isArray(noeuds) ? noeuds : [];
  return l.includes(memo) ? memo : (l[0] || null);
}

/** Page correspondant à une vue (hermes -> "", ia-atelier -> "atelier"…). */
export const pageDeVue = (vue) => (PAGES_IA.find((p) => p.vue === vue) || PAGES_IA[0]).id;

/** Cookie du jeton pour /ia/ (vide = effacement). Secure en https ; SameSite=Strict : jamais envoyé par un autre site. */
export function cookieIa(token, https = true) {
  const base = `${COOKIE_IA}=${token || ""}; Path=/ia/; SameSite=Strict${https ? "; Secure" : ""}`;
  return token ? base : base + "; Max-Age=0";
}
