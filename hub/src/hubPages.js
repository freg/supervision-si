// Pages profondes du hub (livraison #1004) : onglets internes d'une vue (ex. Nebula › Historique des clients) trouvés par
// la recherche générale « Univers du hub » comme les tuiles -- « historique » doit aussi donner l'historique des clients.
// Une page = vue + paramètres d'écran ; elle n'apparaît que si sa vue est disponible.

export const PAGES = [
  { id: "page:nebula-historique", view: "nebula", params: { tab: "historique" }, label: "Historique des clients du réseau",
    aliases: ["historique", "clients", "appareils vus", "catégories", "activité", "présence", "MAC"] },
  { id: "page:nebula-surveillance", view: "nebula", params: { tab: "surveillance" }, label: "Liste de surveillance (appareils attendus)",
    aliases: ["surveillance", "tablettes", "listes", "usurpation", "repérage", "identification"] },
  { id: "page:nebula-vlan", view: "nebula", params: { tab: "vlan" }, label: "Carte des VLAN", aliases: ["vlan", "synoptique", "réseau"] },
  { id: "page:nebula-charge", view: "nebula", params: { tab: "charge" }, label: "Charge du réseau Wi-Fi", aliases: ["charge", "débit", "bornes"] },
  { id: "page:nebula-sante", view: "nebula", params: { tab: "health" }, label: "Santé du réseau (Nebula)", aliases: ["santé", "hors ligne", "pannes"] },
  { id: "page:nebula-pilotage", view: "nebula", params: { tab: "pilotage" }, label: "Pilotage du réseau (Nebula)", aliases: ["pilotage", "actions", "scénarios"] },
  { id: "page:nebula-plan", view: "nebula", params: { tab: "plan" }, label: "Plan du site (Nebula)", aliases: ["plan", "carte", "étage"] },
  { id: "page:nebula-rapports", view: "nebula", params: { tab: "reports" }, label: "Rapports et alertes réseau", aliases: ["rapports", "alertes"] },
  { id: "page:migration-owncloud", view: "migration", params: { page: "owncloud" }, label: "Migration › ownCloud", aliases: ["owncloud", "cloud", "corbeilles"] },
];

/** Pages dont la vue est disponible -> entrées de catalogue (kind « page »). */
export function pagesCatalogue(availableViews, pages = PAGES) {
  const vues = availableViews instanceof Set ? availableViews : new Set(availableViews || []);
  return pages.filter((p) => vues.has(p.view)).map((p) => ({ ...p, kind: "page" }));
}

/** Catalogue étendu pour la recherche générale (les pages ne vont pas dans l'arbre des menus). */
export function catalogueRecherche(catalog, availableViews, pages = PAGES) {
  const out = new Map(catalog);
  for (const p of pagesCatalogue(availableViews, pages)) out.set(p.id, p);
  return out;
}
