// #833 Commandes d'agent lancées depuis une tuile (Émulation, Orchestration) : bouton « en cours… » tant que la
// commande correspondante attend l'agent (status pending), onglet où se voit le résultat. Pur et testé.
/** Commande en attente de l'agent dont les paramètres correspondent au critère (valeurs nulles ignorées). */
export function commandeEnCours(cmds = [], agent, critere = {}) {
  return (cmds || []).find((c) => c.status === "pending" && (!agent || c.agent_id === agent)
    && Object.entries(critere).every(([k, v]) => v == null || v === "" || String(c.params?.[k] ?? "") === String(v))) || null;
}
export const ONGLET_RESULTAT = { installer: "clusters", rejoindre: "clusters", desinstaller: "clusters", quota: "clusters", etat: "clusters",
  deployer: "charges", echelle: "charges", supprimer: "charges", lancer: "instances", arreter: "instances", detruire: "instances",
  deployer_agent: "instances", lister: "instances", preparer: "lancer" };
/** Commandes suivies passées de « pending » à terminées depuis le dernier relevé -> [commande]. */
export function finsCommandes(cmds = [], suivis, vus) {
  const out = [];
  for (const c of cmds || []) {
    if (!suivis.has(c.id)) continue;
    const avant = vus[c.id];
    vus[c.id] = c.status;
    if (c.status !== "pending" && avant !== c.status) { suivis.delete(c.id); out.push(c); }
  }
  return out;
}
