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

// -- #996 : déploiement d'un nœud IA depuis le hub ------------------------------------------------------------------
export const CMD_ARCHIVE = "cd ~/Downloads/hermes-web && git archive --format=tar.gz --prefix=hermes-web/ -o ~/Downloads/hermes-web.tar.gz HEAD";

/** Nom de nœud proposé d'après l'identifiant de l'agent (minuscules, chiffres, tirets ; « -ia » final retiré). */
export function nomPropose(agentId) {
  const n = String(agentId || "").toLowerCase().replace(/[^a-z0-9-]+/g, "-").replace(/^-+|-+$/g, "").replace(/-ia$/, "");
  return n.slice(0, 31);
}

/** Formulaire de déploiement -> message d'erreur ou null (mêmes règles que l'API et la passerelle). */
export function verifierFormulaire(f) {
  if (!f.agent) return "choisir l'agent du nœud";
  if (!/^[a-z0-9][a-z0-9-]{0,30}$/.test(f.nom || "")) return "nom du nœud : minuscules, chiffres, tirets (ex. prodia)";
  if (!["direct", "bastion"].includes(f.acces)) return "accès : direct ou par le bastion";
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,252}$/.test(f.adresse || "")) return "adresse du nœud (IP ou nom, vue du hub ou du shim)";
  const p = Number(f.port || 8092);
  if (!Number.isInteger(p) || p < 1024 || p > 65535) return "port entre 1024 et 65535";
  if (f.acces === "bastion" && !/^[a-z0-9][a-z0-9-]{0,30}$/.test(f.shim || "")) return "shim du bastion (ex. campus)";
  return null;
}

/** État affiché d'un nœud d'après sa dernière commande et son dernier événement -> {texte, ton}. */
export function etatNoeud(e) {
  const ev = e?.evenement, c = e?.commande;
  if (ev?.kind === "noeud-ia-deploye" && (!c || String(ev.ts || ev.at || "") >= String(c.created_at || ""))) return { texte: ev.message, ton: "ok" };
  if (ev?.kind === "noeud-ia-echec" && (!c || String(ev.ts || ev.at || "") >= String(c.created_at || ""))) return { texte: ev.message, ton: "bad" };
  if (c?.status === "pending") return { texte: "commande en attente de l'agent (relève suivante)", ton: "warn" };
  if (c && c.status !== "pending" && c.result && c.result.ok === false) return { texte: `refusé par l'agent : ${c.result.error || "?"}`, ton: "bad" };
  if (c?.params?.action === "deployer") return { texte: "déploiement en cours sur le nœud (construction de l'image : plusieurs minutes)", ton: "warn" };
  if (c?.params?.action === "etat" && c.result?.result) {
    const r = c.result.result;
    if (r.en_cours) return { texte: `déploiement en cours : ${r.etape || "…"}`, ton: "warn" };
    if (r.sante_actuelle) return { texte: r.sante_actuelle.ok ? `en service (${r.version || "?"})` : `ne répond pas : ${r.sante_actuelle.texte}`, ton: r.sante_actuelle.ok ? "ok" : "bad" };
  }
  return { texte: "état inconnu", ton: "" };
}

export const VERSION_AGENT_MIN = "0.6.43";   // première version de l'agent qui sait déployer un nœud IA (commande noeud_ia)

/** Version de l'agent suffisante (comparaison numérique a.b.c) ; version inconnue = non. */
export function agentAJour(version, min = VERSION_AGENT_MIN) {
  const a = String(version || "").split(".").map(Number), b = min.split(".").map(Number);
  if (!version || a.some(Number.isNaN)) return false;
  for (let i = 0; i < b.length; i++) { const x = a[i] || 0; if (x !== b[i]) return x > b[i]; }
  return true;
}
