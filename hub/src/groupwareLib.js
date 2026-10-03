// Logique pure du module Groupware (#664, item 115) : droits (lettres ↔ libellés), partages reçus/donnés, catégories en arbre.
export const APPS = { calendar: "Agenda", addressbook: "Carnet d'adresses", infolog: "InfoLog (notes, appels, tâches)", timesheet: "Feuille de temps", resources: "Ressources", files: "Fichiers", notes: "Notes" };
export const RIGHT_LABELS = { r: "lire", a: "ajouter", e: "modifier", d: "supprimer", p: "voir le privé" };
export const RIGHT_PRESETS = [["r", "lecture"], ["rae", "lecture + ajout + modification"], ["raed", "tout sauf le privé"], ["raedp", "tout"]];

export function rightsLabel(text) {
  const t = String(text || "");
  if (!t) return "aucun";
  const preset = RIGHT_PRESETS.find(([k]) => k === t);
  return preset ? preset[1] : t.split("").map((c) => RIGHT_LABELS[c] || c).join(", ");
}
export function maskToText(mask) {
  const order = ["r", "a", "e", "d", "p"]; const bits = { r: 1, a: 2, e: 4, d: 8, p: 16 };
  return order.filter((k) => (Number(mask) || 0) & bits[k]).join("");
}
// Mes partages donnés, par application ; les reçus, par propriétaire (droits effectifs).
export function myGrants(data, user) {
  const given = {}; for (const g of (data?.grants || []).filter((x) => x.owner === user)) (given[g.app] = given[g.app] || []).push(g);
  const received = []; for (const [app, eff] of Object.entries(data?.effective || {})) for (const [owner, mask] of Object.entries(eff)) if (owner !== user) received.push({ app, owner, rights: maskToText(mask) });
  received.sort((a, b) => a.owner.localeCompare(b.owner) || a.app.localeCompare(b.app));
  return { given, received };
}
// Catégories en arbre (profondeur 1 suffit : parent -> enfants), partagées d'abord.
export function categoryTree(rows) {
  const byParent = {}; for (const c of rows || []) (byParent[c.parent_id || 0] = byParent[c.parent_id || 0] || []).push(c);
  const roots = (byParent[0] || []).sort((a, b) => (a.owner ? 1 : 0) - (b.owner ? 1 : 0) || a.name.localeCompare(b.name));
  return roots.map((r) => ({ ...r, children: (byParent[r.id] || []).sort((a, b) => a.name.localeCompare(b.name)) }));
}
// Nom de collection conforme à la convention (agenda-… / contacts-…) : indispensable pour que les partages s'appliquent.
export function collectionNameOk(app, name) {
  const n = String(name || "").toLowerCase();
  return app === "calendar" ? /^(agenda|cal|calendar)/.test(n) : app === "addressbook" ? /^(contacts|carnet|ab|addressbook)/.test(n) : true;
}
