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

// #665 : carnet -- contact vide, lignes du tableau (téléphone / courriel principaux), formulaire <-> contact.
export const EMPTY_CONTACT = { first: "", last: "", org: "", title: "", tel: "", cell: "", email: "", street: "", zip: "", city: "", country: "", note: "", categories: "" };
export function contactToForm(c) {
  const tel = (c.tels || []).find((t) => t.type !== "cell") || {}; const cell = (c.tels || []).find((t) => t.type === "cell") || {};
  return { first: c.first || "", last: c.last || "", org: c.org || "", title: c.title || "", tel: tel.value || "", cell: cell.value || "", email: (c.emails || [])[0]?.value || "",
    street: c.adr?.street || "", zip: c.adr?.zip || "", city: c.adr?.city || "", country: c.adr?.country || "", note: c.note || "", categories: (c.categories || []).join(", ") };
}
export function formToContact(f) {
  const tels = []; if (f.tel) tels.push({ type: "work", value: f.tel }); if (f.cell) tels.push({ type: "cell", value: f.cell });
  return { first: f.first, last: f.last, org: f.org, title: f.title, tels, emails: f.email ? [{ type: "work", value: f.email }] : [], adr: (f.street || f.city || f.zip) ? { type: "work", street: f.street, zip: f.zip, city: f.city, country: f.country } : null,
    note: f.note, categories: String(f.categories || "").split(",").map((x) => x.trim()).filter(Boolean) };
}
export function contactRow(c) {
  return { name: c.fn || [c.first, c.last].filter(Boolean).join(" ") || c.org || "(sans nom)", org: c.org || "", tel: (c.tels || []).map((t) => t.value).join(" · "), email: (c.emails || []).map((e) => e.value).join(" · "), city: c.adr?.city || "", cats: (c.categories || []).join(", "), writable: /e/.test(c.rights || "") };
}
