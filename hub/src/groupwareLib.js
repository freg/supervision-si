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

// #666 : agenda -- semaine, grille horaire, placement des événements, formulaire <-> événement, disponibilités.
const pad = (n) => String(n).padStart(2, "0");
export const dateKey = (d) => `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
export const localIso = (d) => `${dateKey(d)}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
export function weekOf(d) {
  const x = new Date(d); x.setHours(0, 0, 0, 0); const dow = (x.getDay() + 6) % 7; x.setDate(x.getDate() - dow);   // lundi
  return Array.from({ length: 7 }, (_, i) => { const y = new Date(x); y.setDate(x.getDate() + i); return y; });
}
export function monthGrid(d) {
  const first = new Date(d.getFullYear(), d.getMonth(), 1); const start = weekOf(first)[0]; const weeks = [];
  for (let w = 0; w < 6; w++) { const row = weekOf(new Date(start.getFullYear(), start.getMonth(), start.getDate() + w * 7)); weeks.push(row); if (row[6] >= new Date(d.getFullYear(), d.getMonth() + 1, 0)) break; }
  return weeks;
}
// Événements d'un jour : all_day à part ; placement vertical (minutes depuis 0 h) pour la grille.
export function eventsOfDay(events, day) {
  const k = dateKey(day); const next = dateKey(new Date(day.getFullYear(), day.getMonth(), day.getDate() + 1));
  const inDay = (events || []).filter((e) => e.all_day ? (e.start <= k && e.end > k) : (e.start.slice(0, 10) <= k && e.end.slice(0, 10) >= k && !(e.end.slice(0, 10) === k && e.end.slice(11, 16) === "00:00" && e.start.slice(0, 10) !== k)));
  const timed = inDay.filter((e) => !e.all_day).map((e) => {
    const s = e.start.slice(0, 10) < k ? 0 : Number(e.start.slice(11, 13)) * 60 + Number(e.start.slice(14, 16));
    const en = e.end.slice(0, 10) > k || e.end.slice(0, 10) === next ? 1440 : Number(e.end.slice(11, 13)) * 60 + Number(e.end.slice(14, 16));
    return { ...e, top: s, height: Math.max(20, en - s) };
  }).sort((a, b) => a.top - b.top);
  // colonnes pour les chevauchements (simple : rang = nombre de voisins déjà placés qui chevauchent)
  const placed = []; for (const e of timed) { let col = 0; while (placed.some((p) => p.col === col && p.top < e.top + e.height && p.top + p.height > e.top)) col++; e.col = col; placed.push(e); }
  const cols = Math.max(1, ...placed.map((p) => p.col + 1));
  return { allDay: inDay.filter((e) => e.all_day), timed: placed, cols };
}
export const EMPTY_EVENT = { title: "", start: "", end: "", all_day: false, location: "", description: "", categories: "", freq: "", byday: "", until: "", transparent: false, attendees: "", alarm: "" };
export const PARTSTAT_LABELS = { "NEEDS-ACTION": "sans réponse", ACCEPTED: "accepté", DECLINED: "décliné", TENTATIVE: "peut-être" };
export const ALARM_CHOICES = [["", "aucun"], ["0", "à l'heure"], ["5", "5 min avant"], ["15", "15 min avant"], ["30", "30 min avant"], ["60", "1 h avant"], ["1440", "la veille"]];
// #669 : liste « alice, bob » <-> participants [{name, partstat}] ; les réponses connues sont conservées
export function parseAttendees(text, known = []) { const seen = new Set(); const out = []; for (const n of String(text || "").split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean)) { if (seen.has(n)) continue; seen.add(n); out.push({ name: n, partstat: (known.find((k) => k.name === n) || {}).partstat || "NEEDS-ACTION" }); } return out; }
export function attendeeSummary(list) { const c = { ACCEPTED: 0, DECLINED: 0, TENTATIVE: 0, "NEEDS-ACTION": 0 }; for (const a of list || []) c[a.partstat in c ? a.partstat : "NEEDS-ACTION"]++; return c; }
export function eventToForm(e) {
  return { title: e.title || "", start: (e.start || "").slice(0, e.all_day ? 10 : 16), end: (e.end || "").slice(0, e.all_day ? 10 : 16), all_day: !!e.all_day, location: e.location || "", description: e.description || "",
    categories: (e.categories || []).join(", "), freq: e.rrule?.freq ? e.rrule.freq.toLowerCase() : "", byday: e.rrule?.byday || "", until: (e.rrule?.until || "").slice(0, 10), transparent: !!e.transparent,
    attendees: (e.attendees || []).map((a) => a.name).join(", "), alarm: e.alarm === null || e.alarm === undefined ? "" : String(e.alarm), known: e.attendees || [] };
}
export function formToEvent(f) {
  const ev = { title: f.title, start: f.start, end: f.end || undefined, all_day: !!f.all_day, location: f.location, description: f.description, categories: String(f.categories || "").split(",").map((x) => x.trim()).filter(Boolean), transparent: !!f.transparent };
  ev.rrule = f.freq ? { freq: f.freq, byday: f.byday || undefined, until: f.until ? (f.all_day ? f.until : f.until + "T23:59") : undefined } : null;
  ev.attendees = parseAttendees(f.attendees, f.known || []); ev.alarm = f.alarm === "" || f.alarm === undefined ? null : Number(f.alarm);
  return ev;
}
export function defaultSlot(day, hour = 9) { const s = new Date(day); s.setHours(hour, 0, 0, 0); const e = new Date(s); e.setHours(hour + 1); return { start: localIso(s), end: localIso(e) }; }
// Disponibilités : pour chaque principal, les créneaux occupés d'un jour en minutes.
export function busyOfDay(blocks, day) {
  const k = dateKey(day);
  return (blocks || []).filter((b) => b.start.slice(0, 10) <= k && b.end.slice(0, 10) >= k).map((b) => ({ top: b.start.slice(0, 10) < k ? 0 : Number(b.start.slice(11, 13)) * 60 + Number(b.start.slice(14, 16)), bottom: b.end.slice(0, 10) > k ? 1440 : Number(b.end.slice(11, 13)) * 60 + Number(b.end.slice(14, 16)) }));
}
export function freeSlots(busyByPrincipal, day, fromH = 8, toH = 19, minMinutes = 30) {
  const all = Object.values(busyByPrincipal || {}).flatMap((b) => busyOfDay(b, day)).sort((a, b) => a.top - b.top);
  const out = []; let cur = fromH * 60;
  for (const b of all) { if (b.top > cur && b.top - cur >= minMinutes) out.push([cur, Math.min(b.top, toH * 60)]); cur = Math.max(cur, b.bottom); if (cur >= toH * 60) break; }
  if (cur < toH * 60 && toH * 60 - cur >= minMinutes) out.push([cur, toH * 60]);
  return out.filter(([a, b]) => b > a).map(([a, b]) => `${pad(Math.floor(a / 60))}:${pad(a % 60)}–${pad(Math.floor(b / 60))}:${pad(b % 60)}`);
}

// #668 : InfoLog -- libellés, colonnes Kanban, retard, formulaire <-> entrée, lien lisible.
export const INFOLOG_TYPES = { note: "Note", call: "Appel", task: "Tâche" };
export const INFOLOG_STATUS = { open: "À faire", ongoing: "En cours", done: "Terminé", cancelled: "Annulé" };
export const PRIORITIES = ["basse", "normale", "haute", "urgente"];
export const EMPTY_INFOLOG = { type: "task", title: "", description: "", status: "open", priority: 1, due: "", start: "", responsible: "", private: false, categories: "", links: [] };
export function isLate(e, today = new Date()) { return !!e.due && ["open", "ongoing"].includes(e.status) && e.due.slice(0, 10) < dateKey(today); }
export function kanban(entries) { const cols = {}; for (const k of Object.keys(INFOLOG_STATUS)) cols[k] = []; for (const e of entries || []) (cols[e.status] = cols[e.status] || []).push(e); return cols; }
export function infologToForm(e) { return { ...EMPTY_INFOLOG, ...e, private: !!e.private, categories: (e.categories || []).join(", "), links: (e.links || []).map((l) => ({ app: l.app, id: l.id })) }; }
export function formToInfolog(f) { return { type: f.type, title: f.title, description: f.description, status: f.status, priority: Number(f.priority), due: f.due, start: f.start, responsible: f.responsible, private: !!f.private, categories: String(f.categories || "").split(",").map((x) => x.trim()).filter(Boolean), links: (f.links || []).filter((l) => l.app && l.id) }; }
export function linkLabel(l) {
  if (!l) return "";
  if (l.app === "contact") { const parts = String(l.id).split("/"); return `contact ${parts[2] || l.id}${parts[0] ? " (" + parts[0] + ")" : ""}`; }
  if (l.app === "event") return `événement ${String(l.id).split("/").slice(-1)[0]}`;
  if (l.app === "ticket") return `ticket n°${l.id}`;
  if (l.app === "ged") return `document ${l.id}`;
  return `${l.app} ${l.id}`;
}
// #670 : rappels -- ceux échus et non écartés, clé stable par occurrence
export const reminderKey = (r) => `${r.owner}/${r.book}/${r.uid}@${r.start}`;
export function dueReminders(list, dismissed = new Set()) { return (list || []).filter((r) => r.due && !dismissed.has(reminderKey(r))); }
export function reminderText(r) { const m = Number(r.minutes_to_start); const when = m <= 0 ? (m === 0 ? "maintenant" : `commencé il y a ${-m} min`) : m < 60 ? `dans ${m} min` : `à ${String(r.start).slice(11, 16)}`; return `${r.title} — ${when}${r.location ? ` · ${r.location}` : ""}`; }
