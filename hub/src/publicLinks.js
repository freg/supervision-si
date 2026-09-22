// Pages ouvertes SANS connexion (livraison #505) -- logique pure, testée
// sous Node (hub/tests/publicLinks.test.mjs), rendue par PublicLinks.jsx.
//
// Demandé explicitement : « indiquer les liens externes sans
// authentification sur la page d'accueil du hub sous une autre forme
// que les tuiles ». Les tuiles sont des APPLICATIONS que l'utilisateur
// connecté ouvre ; ces pages-ci sont au contraire destinées à être
// DONNÉES à d'autres (demandeurs qui ne se connectent jamais au hub) :
// ce qui compte est l'adresse elle-même, lisible et copiable -- d'où
// une liste à plat (nom, adresse, Ouvrir, Copier), pas des cartes.
//
// Sources : l'URL d'administration du pont (VITE_DEMANDE_URL, qui vise
// /demande/admin) dont on déduit la racine publique /demande/ et ses
// deux présentations de saisie (#500) ; l'application Supervision SI
// historique (VITE_SUPERVISION_FRONTEND_URL), ouverte sans vérification
// (voir la note de bas de page du hub). Jamais d'exception : une URL
// absente = pas d'entrée.

/** Racine publique du pont à partir de l'URL de sa page d'admin
 *  (`…/demande/admin`, `…/demande/admin/` ou déjà `…/demande/`) --
 *  toujours terminée par « / ». `null` si vide. */
export function demandeBase(adminUrl) {
  const s = String(adminUrl || "").trim();
  if (!s) return null;
  const stripped = s.replace(/\/?admin\/?(?:[?#].*)?$/, "");
  return stripped.endsWith("/") ? stripped : stripped + "/";
}

/** Liste des pages ouvertes : [{id, name, description, url}]. */
export function publicLinks({ demandeUrl, frontendUrl } = {}) {
  const out = [];
  const base = demandeBase(demandeUrl);
  if (base) {
    // #541 : l'espace Simple (accueil, suivi, état des services) -- à donner
    // en PREMIER aux non-initiés, les autres pages restent accessibles.
    out.push({ id: "simple", name: "Support informatique (espace simple)", description: "Accueil en quatre questions : signaler, suivre ma demande, est-ce que ça marche, plusieurs demandes", url: base + "accueil" });
    out.push({ id: "demande", name: "Dépôt de demande", description: "Formulaire classique (une demande, pièces jointes)", url: base });
    out.push({ id: "demande-rapide", name: "Saisie rapide", description: "Une demande en quelques champs, détails formatés", url: base + "rapide" });
    out.push({ id: "demande-tableau", name: "Saisie en tableau", description: "Plusieurs demandes d'un coup, même disposition que le fichier d'import", url: base + "tableau" });
  }
  const front = String(frontendUrl || "").trim();
  if (front) {
    out.push({ id: "supervision", name: "Supervision SI", description: "Application historique, entièrement ouverte", url: front });
  }
  return out;
}

/** Adresse affichée : sans le schéma, pour tenir sur une ligne. */
export function displayUrl(url) {
  return String(url || "").replace(/^https?:\/\//, "");
}

/** #554 : pages publiées par les agents hôtes (publication #547), à donner
 *  aux personnes du site : [{id, name, description, url}]. */
export function agentPublishedLinks(agents) {
  const out = [];
  for (const a of agents || []) {
    const pub = a && a.publish;
    if (!pub || !pub.enabled) continue;
    const host = (a.hostname || a.last_ip || "").trim();
    if (!host) continue;
    out.push({ id: "agent-" + a.agent_id, name: pub.title || "État du réseau", description: `Publiée par l'agent ${a.agent_id}${a.site ? " (" + a.site + ")" : ""}, depuis le réseau du site`, url: `http://${host}:${pub.port || 8081}/` });
  }
  return out;
}
