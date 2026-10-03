import React, { useState, useEffect, useCallback } from "react";
import { listGrants, createGrant, deleteGrant, listCategories, createCategory, updateCategory, deleteCategory, rawPrefs, putPref, deletePref, davMe, rebuildDav, groupwareHealth, listAddressbooks, createAddressbook, listContacts, createContact, updateContact, deleteContact, listCalendars, createCalendar, listEvents, createEvent, updateEvent, deleteEvent, freeBusy, listResources, createResource, deleteResource } from "./groupwareClient.js";
import { APPS, RIGHT_PRESETS, rightsLabel, myGrants, categoryTree, EMPTY_CONTACT, contactToForm, formToContact, contactRow, weekOf, monthGrid, eventsOfDay, EMPTY_EVENT, eventToForm, formToEvent, defaultSlot, dateKey, localIso, busyOfDay, freeSlots } from "./groupwareLib.js";
import HubIcon from "./HubIcon.jsx";

// Tuile « Groupware » (livraison #664, item 115) -- tranche 1 d'un groupware « façon eGroupware » : mes accès
// CalDAV / CardDAV (Radicale, comptes LDAP), partages de mes données par application (grants : lecture, ajout,
// modification, suppression, privé) à un utilisateur ou un groupe, catégories partagées / personnelles, préférences
// (défaut, groupe, utilisateur, forcées par l'administrateur). Les applications (agenda, carnet, InfoLog) arrivent
// par tranches ; les clients DAV fonctionnent dès maintenant. Non vérifié en navigateur ; logique pure testée sous Node.
const TABS = [["agenda", "Agenda"], ["contacts", "Carnet d'adresses"], ["dav", "Synchronisation (CalDAV, CardDAV)"], ["grants", "Partages"], ["categories", "Catégories"], ["prefs", "Préférences"]];

// #666 : agenda dans le hub -- semaine (grille horaire) / mois / liste, tous les agendas lisibles + ressources, création dans un
// agenda où j'ai le droit, récurrences simples, disponibilités de plusieurs personnes (sans détail), ressources réservables
// (salle, matériel : réservation ouverte, conflit refusé). Les mêmes événements apparaissent dans les clients CalDAV.
const DAYS = ["lun.", "mar.", "mer.", "jeu.", "ven.", "sam.", "dim."];
const HOUR_PX = 40;
function Agenda({ base, login, groups, health, isAdmin, setError, setNotice }) {
  const [view, setView] = useState("week");
  const [cursor, setCursor] = useState(() => new Date());
  const [cals, setCals] = useState(null);
  const [events, setEvents] = useState([]);
  const [hidden, setHidden] = useState({});
  const [sel, setSel] = useState(null);
  const [form, setForm] = useState(null);
  const [newCal, setNewCal] = useState("");
  const [who, setWho] = useState("");
  const [busy, setBusy] = useState(null);
  const [resources, setResources] = useState([]);
  const [resForm, setResForm] = useState({ name: "", kind: "salle", capacity: "" });
  const days = view === "month" ? monthGrid(cursor).flat() : view === "week" ? weekOf(cursor) : [cursor];
  const from = dateKey(days[0]) + "T00:00", to = dateKey(new Date(days[days.length - 1].getFullYear(), days[days.length - 1].getMonth(), days[days.length - 1].getDate() + 1)) + "T00:00";
  const load = useCallback(async () => {
    const [c, e, r] = await Promise.all([listCalendars(base, login, groups), listEvents(base, login, groups, from, to), listResources(base)]);
    if (c.error) { setError(c.error); setCals([]); } else setCals(c.calendars || []);
    if (!e.error) setEvents(e.events || []); if (!r.error) setResources(r.resources || []);
  }, [base, login, groups, from, to, setError]);
  useEffect(() => { load(); }, [load]);
  const visible = events.filter((e) => !hidden[`${e.owner}/${e.book}`]);
  const writable = (cals || []).filter((c) => /a/.test(c.rights));
  const move = (n) => { const d = new Date(cursor); if (view === "month") d.setMonth(d.getMonth() + n); else d.setDate(d.getDate() + n * (view === "week" ? 7 : 1)); setCursor(d); };
  function openNew(day, hour) { if (!writable.length) { setError("Aucun agenda où ajouter : créez un agenda ci-dessous."); return; } const slot = defaultSlot(day, hour); setSel(null); setForm({ mode: "new", owner: writable[0].owner, book: writable[0].name, f: { ...EMPTY_EVENT, ...slot } }); }
  async function save() {
    const body = { user: login, groups, owner: form.owner, book: form.book, admin: isAdmin, event: formToEvent(form.f) };
    const r = form.mode === "new" ? await createEvent(base, body) : await updateEvent(base, form.owner, form.book, form.uid, body);
    if (r.error) { setError(r.error + (r.conflicts ? " — " + r.conflicts.map((x) => `${x.title} ${x.start.slice(11, 16)}–${x.end.slice(11, 16)}`).join(", ") : "")); return; }
    setForm(null); setSel(null); setNotice(form.mode === "new" ? "Événement créé" : "Événement enregistré"); load();
  }
  async function remove(e) { if (!window.confirm(`Supprimer « ${e.title} »${e.recurring ? " (toutes les occurrences)" : ""} ?`)) return; const r = await deleteEvent(base, e.owner, e.book, e.uid, login, isAdmin); if (r.error) setError(r.error); else { setSel(null); load(); } }
  async function addCal() { const r = await createCalendar(base, { user: login, name: newCal, displayname: newCal }); if (r.error) setError(r.error); else { setNewCal(""); setNotice(`Agenda ${r.calendar.name} créé — visible dans vos clients CalDAV`); load(); } }
  async function checkBusy() { const users = who.split(",").map((x) => x.trim()).filter(Boolean); const res = resources.filter((r) => users.includes("ressource:" + r.slug) || users.includes(r.slug)).map((r) => r.slug); const r = await freeBusy(base, users.filter((u) => !res.includes(u) && !u.startsWith("ressource:")), res, from, to); if (r.error) setError(r.error); else setBusy(r.busy); }
  async function addResource() { const r = await createResource(base, { name: resForm.name, kind: resForm.kind, capacity: Number(resForm.capacity) || 0 }); if (r.error) setError(r.error); else { setResForm({ name: "", kind: "salle", capacity: "" }); load(); } }
  if (health && health.contacts === false) return <div className="hub-card hub-settings-section"><h2>Agenda</h2><p className="ds-error">Compte de service DAV absent (entrée « {health.credential_name || "groupware-dav"} » du coffre des accès, ou GROUPWARE_DAV_SERVICE_USER / PASSWORD) : l'agenda dans le hub est indisponible ; vos clients CalDAV fonctionnent.</p></div>;
  const title = view === "month" ? cursor.toLocaleDateString("fr-FR", { month: "long", year: "numeric" }) : view === "week" ? `semaine du ${days[0].toLocaleDateString("fr-FR")} au ${days[6].toLocaleDateString("fr-FR")}` : cursor.toLocaleDateString("fr-FR", { weekday: "long", day: "numeric", month: "long", year: "numeric" });
  const colorOf = (e) => e.resource ? "var(--warning)" : e.owner === login ? "var(--accent)" : "var(--muted)";
  return (
    <div className="pv-columns">
      <div className="pv-col" style={{ flex: 3 }}>
        <div className="hub-card hub-settings-section">
          <div className="ds-row-between">
            <div className="ds-inline" style={{ marginTop: 0 }}><button className="secondary pv-mini" onClick={() => move(-1)}>◀</button><button className="secondary pv-mini" onClick={() => setCursor(new Date())}>aujourd'hui</button><button className="secondary pv-mini" onClick={() => move(1)}>▶</button><b style={{ textTransform: "capitalize" }}>{title}</b></div>
            <div className="ds-inline" style={{ marginTop: 0 }}>{[["day", "jour"], ["week", "semaine"], ["month", "mois"], ["list", "liste"]].map(([k, l]) => <button key={k} className={view === k ? "primary pv-mini" : "secondary pv-mini"} onClick={() => setView(k)}>{l}</button>)}<button className="primary" onClick={() => openNew(cursor, 9)}>+ Événement</button></div>
          </div>
          {(view === "week" || view === "day") && (() => { const cols = view === "week" ? days : [cursor]; return (
            <div style={{ display: "grid", gridTemplateColumns: `48px repeat(${cols.length}, 1fr)`, borderTop: "1px solid var(--border)", marginTop: 8, fontSize: 12 }}>
              <div />{cols.map((d) => <div key={dateKey(d)} style={{ textAlign: "center", padding: 4, fontWeight: dateKey(d) === dateKey(new Date()) ? 700 : 400, borderLeft: "1px solid var(--border)" }}>{DAYS[(d.getDay() + 6) % 7]} {d.getDate()}</div>)}
              <div className="muted" style={{ fontSize: 10, padding: 2 }}>journée</div>{cols.map((d) => { const { allDay } = eventsOfDay(visible, d); return <div key={"ad" + dateKey(d)} style={{ borderLeft: "1px solid var(--border)", minHeight: 18, padding: 2 }}>{allDay.map((e) => <div key={e.uid + e.start} onClick={() => { setSel(e); setForm(null); }} style={{ background: colorOf(e), color: "#fff", borderRadius: 3, padding: "1px 4px", marginBottom: 2, cursor: "pointer", overflow: "hidden", whiteSpace: "nowrap" }}>{e.title}</div>)}</div>; })}
              <div style={{ position: "relative", height: 24 * HOUR_PX }}>{Array.from({ length: 24 }, (_, h) => <div key={h} className="muted" style={{ position: "absolute", top: h * HOUR_PX - 6, right: 4, fontSize: 10 }}>{h}h</div>)}</div>
              {cols.map((d) => { const { timed, cols: nc } = eventsOfDay(visible, d); return (
                <div key={dateKey(d)} style={{ position: "relative", height: 24 * HOUR_PX, borderLeft: "1px solid var(--border)", background: dateKey(d) === dateKey(new Date()) ? "var(--bg)" : "transparent" }} onDoubleClick={(ev) => { const rect = ev.currentTarget.getBoundingClientRect(); openNew(d, Math.floor((ev.clientY - rect.top) / HOUR_PX)); }}>
                  {Array.from({ length: 24 }, (_, h) => <div key={h} style={{ position: "absolute", top: h * HOUR_PX, left: 0, right: 0, borderTop: "1px solid var(--border)", opacity: h >= 8 && h < 19 ? 0.6 : 0.25 }} />)}
                  {busy && Object.entries(busy).map(([p, blocks]) => busyOfDay(blocks, d).map((b, i) => <div key={p + i} title={p} style={{ position: "absolute", top: b.top / 60 * HOUR_PX, height: (b.bottom - b.top) / 60 * HOUR_PX, left: 0, right: 0, background: "repeating-linear-gradient(45deg, transparent, transparent 4px, var(--danger) 4px, var(--danger) 5px)", opacity: 0.35, pointerEvents: "none" }} />))}
                  {timed.map((e) => <div key={e.uid + e.start} onClick={() => { setSel(e); setForm(null); }} title={e.title} style={{ position: "absolute", top: e.top / 60 * HOUR_PX, height: e.height / 60 * HOUR_PX - 2, left: `${(e.col / nc) * 100}%`, width: `${100 / nc - 2}%`, background: colorOf(e), color: "#fff", borderRadius: 3, padding: "1px 4px", fontSize: 11, overflow: "hidden", cursor: "pointer", opacity: e.transparent ? 0.6 : 1 }}>{e.start.slice(11, 16)} {e.title}</div>)}
                </div>); })}
            </div>); })()}
          {view === "month" && <div style={{ display: "grid", gridTemplateColumns: "repeat(7, 1fr)", gap: 2, marginTop: 8, fontSize: 12 }}>
            {DAYS.map((d) => <div key={d} className="muted" style={{ textAlign: "center" }}>{d}</div>)}
            {days.map((d) => { const { allDay, timed } = eventsOfDay(visible, d); const other = d.getMonth() !== cursor.getMonth(); return <div key={dateKey(d)} onDoubleClick={() => openNew(d, 9)} style={{ minHeight: 84, border: "1px solid var(--border)", padding: 3, opacity: other ? 0.5 : 1, background: dateKey(d) === dateKey(new Date()) ? "var(--bg)" : "transparent" }}>
              <div style={{ textAlign: "right" }} className="muted">{d.getDate()}</div>
              {[...allDay, ...timed].slice(0, 4).map((e) => <div key={e.uid + e.start} onClick={() => { setSel(e); setForm(null); }} style={{ background: colorOf(e), color: "#fff", borderRadius: 3, padding: "0 3px", marginBottom: 1, cursor: "pointer", overflow: "hidden", whiteSpace: "nowrap", textOverflow: "ellipsis" }}>{e.all_day ? "" : e.start.slice(11, 16) + " "}{e.title}</div>)}
              {allDay.length + timed.length > 4 && <div className="muted">+ {allDay.length + timed.length - 4}</div>}
            </div>; })}
          </div>}
          {view === "list" && <table className="ds-table"><thead><tr><th>Quand</th><th>Quoi</th><th>Où</th><th>Agenda</th></tr></thead><tbody>
            {visible.map((e) => <tr key={e.uid + e.start} style={{ cursor: "pointer" }} className={sel && sel.uid === e.uid && sel.start === e.start ? "pv-selected" : ""} onClick={() => { setSel(e); setForm(null); }}><td>{e.all_day ? e.start : `${e.start.slice(0, 10)} ${e.start.slice(11, 16)}–${e.end.slice(11, 16)}`}{e.recurring ? " ↻" : ""}</td><td><b>{e.title}</b></td><td>{e.location}</td><td className="muted">{e.book_name}{e.owner !== login && !e.resource ? ` (${e.owner})` : ""}</td></tr>)}
            {!visible.length && <tr><td colSpan={4} className="muted">Rien sur la période.</td></tr>}</tbody></table>}
          <p className="muted" style={{ marginBottom: 0 }}>Double-clic sur un créneau = nouvel événement. {busy ? "Hachures = créneaux occupés des personnes / ressources interrogées." : ""}</p>
        </div>
        <div className="hub-card hub-settings-section">
          <h3>Disponibilités</h3>
          <div className="ds-inline"><input type="text" value={who} placeholder="identifiants séparés par des virgules (ex. alice, bob, salle-1)" style={{ width: 360 }} onChange={(e) => setWho(e.target.value)} /><button className="secondary" onClick={checkBusy} disabled={!who}>Voir les créneaux occupés</button>{busy && <button className="secondary pv-mini" onClick={() => setBusy(null)}>effacer</button>}</div>
          {busy && view !== "month" && <table className="ds-table"><thead><tr><th>Jour</th><th>Créneaux libres pour tous (8h–19h, ≥ 30 min)</th></tr></thead><tbody>{days.map((d) => <tr key={dateKey(d)}><td>{DAYS[(d.getDay() + 6) % 7]} {d.getDate()}</td><td>{freeSlots(busy, d).join(" · ") || <span className="muted">aucun</span>}</td></tr>)}</tbody></table>}
          <p className="muted">Les disponibilités se calculent sur tous les agendas de chaque personne, sans en révéler le contenu (comme le free/busy d'eGroupware).</p>
        </div>
      </div>
      <div className="pv-col" style={{ flex: 2 }}>
        {form && (
          <div className="hub-card hub-settings-section">
            <h2>{form.mode === "new" ? "Nouvel événement" : "Modifier"}</h2>
            {form.mode === "new" && <div className="hub-settings-row"><label>Agenda</label><select value={`${form.owner}/${form.book}`} onChange={(e) => { const [owner, book] = e.target.value.split("/"); setForm({ ...form, owner, book }); }}>{writable.map((c) => <option key={`${c.owner}/${c.name}`} value={`${c.owner}/${c.name}`}>{c.resource ? "ressource : " : ""}{c.displayname}{c.mine || c.resource ? "" : ` (${c.owner})`}</option>)}</select></div>}
            <div className="pv-grid">
              <div className="hub-settings-row" style={{ gridColumn: "1 / -1" }}><label>Titre</label><input type="text" value={form.f.title} onChange={(e) => setForm({ ...form, f: { ...form.f, title: e.target.value } })} /></div>
              <label className="pv-check"><input type="checkbox" checked={form.f.all_day} onChange={(e) => { const ad = e.target.checked; setForm({ ...form, f: { ...form.f, all_day: ad, start: ad ? form.f.start.slice(0, 10) : form.f.start.length === 10 ? form.f.start + "T09:00" : form.f.start, end: ad ? form.f.end.slice(0, 10) : form.f.end.length === 10 ? form.f.end + "T10:00" : form.f.end } }); }} /> journée entière</label>
              <label className="pv-check"><input type="checkbox" checked={form.f.transparent} onChange={(e) => setForm({ ...form, f: { ...form.f, transparent: e.target.checked } })} /> ne bloque pas mes disponibilités</label>
              <div className="hub-settings-row"><label>Début</label><input type={form.f.all_day ? "date" : "datetime-local"} value={form.f.start} onChange={(e) => setForm({ ...form, f: { ...form.f, start: e.target.value } })} /></div>
              <div className="hub-settings-row"><label>Fin</label><input type={form.f.all_day ? "date" : "datetime-local"} value={form.f.end} onChange={(e) => setForm({ ...form, f: { ...form.f, end: e.target.value } })} /></div>
              <div className="hub-settings-row"><label>Lieu</label><input type="text" value={form.f.location} onChange={(e) => setForm({ ...form, f: { ...form.f, location: e.target.value } })} /></div>
              <div className="hub-settings-row"><label>Catégories (virgules)</label><input type="text" value={form.f.categories} onChange={(e) => setForm({ ...form, f: { ...form.f, categories: e.target.value } })} /></div>
              <div className="hub-settings-row"><label>Répétition</label><select value={form.f.freq} onChange={(e) => setForm({ ...form, f: { ...form.f, freq: e.target.value } })}><option value="">aucune</option><option value="daily">tous les jours</option><option value="weekly">toutes les semaines</option><option value="monthly">tous les mois</option><option value="yearly">tous les ans</option></select></div>
              {form.f.freq === "weekly" && <div className="hub-settings-row"><label>Jours</label><div className="ds-inline" style={{ marginTop: 0 }}>{["MO", "TU", "WE", "TH", "FR", "SA", "SU"].map((d, i) => <label key={d} className="pv-check"><input type="checkbox" checked={form.f.byday.split(",").includes(d)} onChange={(e) => { const set = new Set(form.f.byday.split(",").filter(Boolean)); e.target.checked ? set.add(d) : set.delete(d); setForm({ ...form, f: { ...form.f, byday: ["MO", "TU", "WE", "TH", "FR", "SA", "SU"].filter((x) => set.has(x)).join(",") } }); }} /> {DAYS[i]}</label>)}</div></div>}
              {form.f.freq && <div className="hub-settings-row"><label>Jusqu'au</label><input type="date" value={form.f.until} onChange={(e) => setForm({ ...form, f: { ...form.f, until: e.target.value } })} /></div>}
              <div className="hub-settings-row" style={{ gridColumn: "1 / -1" }}><label>Description</label><textarea rows={3} value={form.f.description} onChange={(e) => setForm({ ...form, f: { ...form.f, description: e.target.value } })} /></div>
            </div>
            <div className="pv-inline"><button className="primary" onClick={save} disabled={!form.f.title || !form.f.start}>Enregistrer</button><button className="secondary" onClick={() => setForm(null)}>Annuler</button></div>
          </div>
        )}
        {sel && !form && (
          <div className="hub-card hub-settings-section">
            <div className="ds-row-between"><h2 style={{ margin: 0 }}>{sel.title}</h2><div>{(/e/.test(sel.rights || "") || sel.resource) && <button className="secondary pv-mini" onClick={() => setForm({ mode: "edit", owner: sel.owner, book: sel.book, uid: sel.uid, f: eventToForm(sel) })}>modifier</button>}{(/d/.test(sel.rights || "") || sel.resource) && <button className="secondary pv-mini pv-danger" onClick={() => remove(sel)}>supprimer</button>}</div></div>
            <table className="ds-table"><tbody>
              <tr><th>Quand</th><td>{sel.all_day ? `${sel.start} → ${sel.end} (journée)` : `${sel.start.replace("T", " ").slice(0, 16)} → ${sel.end.replace("T", " ").slice(0, 16)}`}{sel.recurring && <div className="muted">récurrent ({sel.rrule?.freq?.toLowerCase()}{sel.rrule?.byday ? " " + sel.rrule.byday : ""}{sel.rrule?.until ? ", jusqu'au " + sel.rrule.until.slice(0, 10) : ""})</div>}</td></tr>
              {sel.location && <tr><th>Lieu</th><td>{sel.location}</td></tr>}
              {sel.description && <tr><th>Description</th><td style={{ whiteSpace: "pre-wrap" }}>{sel.description}</td></tr>}
              {(sel.categories || []).length > 0 && <tr><th>Catégories</th><td>{sel.categories.join(", ")}</td></tr>}
              <tr><th>Agenda</th><td>{sel.resource ? "ressource : " : ""}{sel.book_name}{sel.owner !== login && !sel.resource && <span className="muted"> (partagé par {sel.owner}, {rightsLabel(sel.rights)})</span>}</td></tr>
            </tbody></table>
          </div>
        )}
        <div className="hub-card hub-settings-section">
          <h3>Agendas affichés</h3>
          {(cals || []).map((c) => <label key={`${c.owner}/${c.name}`} className="pv-check" style={{ display: "block" }}><input type="checkbox" checked={!hidden[`${c.owner}/${c.name}`]} onChange={(e) => setHidden({ ...hidden, [`${c.owner}/${c.name}`]: !e.target.checked })} /> {c.resource ? "🏢 " : ""}{c.displayname} <span className="muted">{c.mine ? "" : c.resource ? "ressource" : `${c.owner} · ${rightsLabel(c.rights)}`}</span></label>)}
          <div className="ds-inline"><input type="text" value={newCal} placeholder="nouvel agenda (ex. equipe)" onChange={(e) => setNewCal(e.target.value)} /><button className="secondary" disabled={!newCal} onClick={addCal}>Créer l'agenda</button></div>
        </div>
        <div className="hub-card hub-settings-section">
          <h3>Ressources réservables</h3>
          {resources.length ? <table className="ds-table"><tbody>{resources.map((r) => <tr key={r.slug}><td><b>{r.name}</b> <span className="muted">{r.kind}{r.capacity ? ` · ${r.capacity} pl.` : ""} · {r.slug}</span></td><td>{isAdmin && <button className="secondary pv-mini pv-danger" onClick={async () => { if (window.confirm(`Retirer la ressource « ${r.name} » (l'agenda est conservé) ?`)) { await deleteResource(base, r.slug); load(); } }}>✕</button>}</td></tr>)}</tbody></table> : <p className="muted">Aucune ressource (salle, véhicule, matériel). Une réservation = un événement dans l'agenda de la ressource ; les chevauchements sont refusés.</p>}
          {isAdmin && <div className="ds-inline"><input type="text" value={resForm.name} placeholder="nom (ex. Salle de réunion)" onChange={(e) => setResForm({ ...resForm, name: e.target.value })} /><select value={resForm.kind} onChange={(e) => setResForm({ ...resForm, kind: e.target.value })}><option value="salle">salle</option><option value="vehicule">véhicule</option><option value="materiel">matériel</option><option value="autre">autre</option></select><input type="number" value={resForm.capacity} placeholder="places" style={{ width: 70 }} onChange={(e) => setResForm({ ...resForm, capacity: e.target.value })} /><button className="secondary" disabled={!resForm.name} onClick={addResource}>Ajouter</button></div>}
        </div>
      </div>
    </div>
  );
}

// #665 : carnet d'adresses dans le hub -- tous les carnets lisibles (les miens + partagés), recherche, fiche, création
// dans un carnet où j'ai le droit d'ajouter ; les mêmes contacts apparaissent dans les clients CardDAV.
function Contacts({ base, login, groups, health, setError, setNotice }) {
  const [books, setBooks] = useState(null);
  const [rows, setRows] = useState([]);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(null);           // contact ouvert
  const [form, setForm] = useState(null);         // {mode: new|edit, owner, book, uid, f}
  const [newBook, setNewBook] = useState("");
  const load = useCallback(async () => {
    const [b, c] = await Promise.all([listAddressbooks(base, login, groups), listContacts(base, login, groups, q)]);
    if (b.error) { setError(b.error); setBooks([]); } else setBooks(b.addressbooks || []);
    if (!c.error) setRows(c.contacts || []);
  }, [base, login, groups, q, setError]);
  useEffect(() => { const t = setTimeout(load, 250); return () => clearTimeout(t); }, [load]);
  const writable = (books || []).filter((b) => /a/.test(b.rights));
  async function save() {
    const body = { user: login, groups, owner: form.owner, book: form.book, contact: formToContact(form.f) };
    const r = form.mode === "new" ? await createContact(base, body) : await updateContact(base, form.owner, form.book, form.uid, body);
    if (r.error) { setError(r.error); return; } setForm(null); setSel(null); setNotice(form.mode === "new" ? "Contact créé" : "Contact enregistré"); load();
  }
  async function remove(c) { if (!window.confirm(`Supprimer « ${contactRow(c).name} » ?`)) return; const r = await deleteContact(base, c.owner, c.book, c.uid, login); if (r.error) setError(r.error); else { setSel(null); load(); } }
  async function addBook() { const r = await createAddressbook(base, { user: login, name: newBook, displayname: newBook }); if (r.error) setError(r.error); else { setNewBook(""); setNotice(`Carnet ${r.addressbook.name} créé — visible dans vos clients CardDAV`); load(); } }
  if (health && health.contacts === false) return <div className="hub-card hub-settings-section"><h2>Carnet d'adresses</h2><p className="ds-error">Compte de service DAV absent : entrée « {health.credential_name || "groupware-dav"} » du coffre des accès (tuile Accès d'équipements : identifiant + mot de passe d'un compte LDAP dédié) : le carnet dans le hub est indisponible ; vos clients CardDAV fonctionnent (onglet Synchronisation).</p></div>;
  return (
    <div className="pv-columns">
      <div className="pv-col">
        <div className="hub-card hub-settings-section">
          <div className="ds-row-between"><h2 style={{ margin: 0 }}>Carnet d'adresses <span className="muted">({rows.length})</span></h2>
            <div className="ds-inline" style={{ marginTop: 0 }}><input type="search" value={q} placeholder="rechercher (nom, société, tél, courriel, ville, catégorie)" onChange={(e) => setQ(e.target.value)} style={{ width: 280 }} />
              <button className="primary" disabled={!writable.length} onClick={() => setForm({ mode: "new", owner: writable[0].owner, book: writable[0].name, f: { ...EMPTY_CONTACT } })}>+ Contact</button></div></div>
          <table className="ds-table"><thead><tr><th>Nom</th><th>Société</th><th>Téléphone</th><th>Courriel</th><th>Ville</th><th>Carnet</th></tr></thead>
            <tbody>{rows.map((c) => { const r = contactRow(c); return <tr key={`${c.owner}/${c.book}/${c.uid}`} className={sel && sel.uid === c.uid ? "pv-selected" : ""} style={{ cursor: "pointer" }} onClick={() => { setSel(c); setForm(null); }}><td><b>{r.name}</b>{r.cats && <div className="muted">{r.cats}</div>}</td><td>{r.org}</td><td>{r.tel}</td><td>{r.email}</td><td>{r.city}</td><td className="muted">{c.book_name}{c.owner !== login ? ` (${c.owner})` : ""}</td></tr>; })}
              {!rows.length && <tr><td colSpan={6} className="muted">{books === null ? "chargement…" : q ? "Aucun contact ne correspond." : "Aucun contact : créez un carnet puis un contact, ou importez un .vcf dans l'interface Radicale."}</td></tr>}</tbody></table>
        </div>
        <div className="hub-card hub-settings-section">
          <h3>Mes carnets {books && <span className="muted">({books.length})</span>}</h3>
          <table className="ds-table"><tbody>{(books || []).map((b) => <tr key={`${b.owner}/${b.name}`}><td><b>{b.displayname}</b> <span className="muted">{b.name}</span></td><td>{b.mine ? "à moi" : `partagé par ${b.owner}`}</td><td>{rightsLabel(b.rights)}</td></tr>)}</tbody></table>
          <div className="ds-inline"><input type="text" value={newBook} placeholder="nouveau carnet (ex. clients)" onChange={(e) => setNewBook(e.target.value)} /><button className="secondary" disabled={!newBook} onClick={addBook}>Créer le carnet</button><span className="muted">nommé contacts-… automatiquement</span></div>
        </div>
      </div>
      <div className="pv-col">
        {form && (
          <div className="hub-card hub-settings-section">
            <h2>{form.mode === "new" ? "Nouveau contact" : "Modifier"}</h2>
            {form.mode === "new" && <div className="hub-settings-row"><label>Carnet</label><select value={`${form.owner}/${form.book}`} onChange={(e) => { const [owner, book] = e.target.value.split("/"); setForm({ ...form, owner, book }); }}>{writable.map((b) => <option key={`${b.owner}/${b.name}`} value={`${b.owner}/${b.name}`}>{b.displayname}{b.mine ? "" : ` (${b.owner})`}</option>)}</select></div>}
            <div className="pv-grid">
              {[["first", "Prénom"], ["last", "Nom"], ["org", "Société"], ["title", "Fonction"], ["tel", "Téléphone"], ["cell", "Mobile"], ["email", "Courriel"], ["street", "Rue"], ["zip", "Code postal"], ["city", "Ville"], ["country", "Pays"], ["categories", "Catégories (virgules)"]].map(([k, l]) => <div key={k} className="hub-settings-row"><label>{l}</label><input type="text" value={form.f[k]} onChange={(e) => setForm({ ...form, f: { ...form.f, [k]: e.target.value } })} /></div>)}
              <div className="hub-settings-row" style={{ gridColumn: "1 / -1" }}><label>Note</label><textarea rows={3} value={form.f.note} onChange={(e) => setForm({ ...form, f: { ...form.f, note: e.target.value } })} /></div>
            </div>
            <div className="pv-inline"><button className="primary" onClick={save} disabled={!(form.f.first || form.f.last || form.f.org)}>Enregistrer</button><button className="secondary" onClick={() => setForm(null)}>Annuler</button></div>
          </div>
        )}
        {sel && !form && (() => { const r = contactRow(sel); return (
          <div className="hub-card hub-settings-section">
            <div className="ds-row-between"><h2 style={{ margin: 0 }}>{r.name}</h2><div>{r.writable && <button className="secondary pv-mini" onClick={() => setForm({ mode: "edit", owner: sel.owner, book: sel.book, uid: sel.uid, f: contactToForm(sel) })}>modifier</button>}{/d/.test(sel.rights || "") && <button className="secondary pv-mini pv-danger" onClick={() => remove(sel)}>supprimer</button>}</div></div>
            <table className="ds-table"><tbody>
              {sel.org && <tr><th>Société</th><td>{sel.org}{sel.title ? ` — ${sel.title}` : ""}</td></tr>}
              {(sel.tels || []).map((t, i) => <tr key={"t" + i}><th>Tél. {t.type}</th><td><a href={`tel:${t.value}`}>{t.value}</a></td></tr>)}
              {(sel.emails || []).map((e, i) => <tr key={"e" + i}><th>Courriel</th><td><a href={`mailto:${e.value}`}>{e.value}</a></td></tr>)}
              {sel.adr && <tr><th>Adresse</th><td>{[sel.adr.street, [sel.adr.zip, sel.adr.city].filter(Boolean).join(" "), sel.adr.country].filter(Boolean).join(", ")}</td></tr>}
              {sel.url && <tr><th>Web</th><td><a href={sel.url} target="_blank" rel="noreferrer">{sel.url}</a></td></tr>}
              {sel.note && <tr><th>Note</th><td style={{ whiteSpace: "pre-wrap" }}>{sel.note}</td></tr>}
              {r.cats && <tr><th>Catégories</th><td>{r.cats}</td></tr>}
              <tr><th>Carnet</th><td>{sel.book_name} {sel.owner !== login && <span className="muted">(partagé par {sel.owner}, {rightsLabel(sel.rights)})</span>}{sel.extra > 0 && <span className="muted"> · {sel.extra} champ(s) conservé(s) d'un autre client</span>}</td></tr>
            </tbody></table>
          </div>); })()}
        {!sel && !form && <div className="hub-card hub-settings-section"><p className="muted">Cliquez sur un contact pour l'ouvrir. Les carnets et contacts sont ceux du serveur CardDAV : ce que vous créez ici apparaît sur vos téléphones et dans Thunderbird, et inversement.</p></div>}
      </div>
    </div>
  );
}

export default function GroupwareView({ onBack, groupwareApiBase, login, groups, isAdmin }) {
  const [tab, setTab] = useState("agenda");
  const [health, setHealth] = useState(null);
  const [dav, setDav] = useState(null);
  const [grants, setGrants] = useState(null);
  const [cats, setCats] = useState([]);
  const [prefs, setPrefs] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [form, setForm] = useState({ app: "calendar", grantee_kind: "user", grantee: "", rights: "r" });
  const [catForm, setCatForm] = useState({ name: "", app: "*", shared: false, color: "" });
  const [prefForm, setPrefForm] = useState({ level: "user", subject: "", app: "*", key: "", value: "" });
  const load = useCallback(async () => {
    const [h, d, g, c, p] = await Promise.all([groupwareHealth(groupwareApiBase), davMe(groupwareApiBase, login), listGrants(groupwareApiBase, login, groups), listCategories(groupwareApiBase), isAdmin ? rawPrefs(groupwareApiBase) : { prefs: [] }]);
    setHealth(h); setDav(d); if (!g.error) setGrants(g); else setError(g.error); if (!c.error) setCats(c.categories || []); if (!p.error) setPrefs(p.prefs || []);
  }, [groupwareApiBase, login, groups, isAdmin]);
  useEffect(() => { load(); }, [load]);

  async function addGrant() {
    setError(null); const r = await createGrant(groupwareApiBase, { ...form, owner: login, actor: login });
    if (r.error) { setError(r.error); return; } setNotice(`Partage ${APPS[form.app]} → ${form.grantee_kind === "all" ? "tous" : form.grantee} : ${rightsLabel(form.rights)}${r.dav ? ` · droits DAV régénérés (${r.dav.rules} règle(s))` : ""}`); setForm({ ...form, grantee: "" }); load();
  }
  async function removeGrant(g) { if (!window.confirm(`Retirer le partage ${APPS[g.app]} → ${g.grantee} ?`)) return; const r = await deleteGrant(groupwareApiBase, g.id, login); if (r.error) setError(r.error); else load(); }
  async function addCat() { const r = await createCategory(groupwareApiBase, { name: catForm.name, app: catForm.app, owner: catForm.shared ? "" : login, color: catForm.color || undefined }); if (r.error) setError(r.error); else { setCatForm({ ...catForm, name: "" }); load(); } }
  async function savePref() { const r = await putPref(groupwareApiBase, { ...prefForm, actor: login }); if (r.error) setError(r.error); else { setPrefForm({ ...prefForm, key: "", value: "" }); load(); } }
  const mine = grants ? myGrants(grants, login) : { given: {}, received: [] };

  return (
    <div className="hub-settings hub-settings-wide ds-view">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1><HubIcon icon="calendar" size={22} /> Groupware</h1>
        <div className="ds-tabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "primary" : "secondary"} onClick={() => setTab(k)}>{l}</button>)}</div>
      </div>
      {error && <div className="hub-card ds-error">⚠️ {error}</div>}
      {notice && <div className="hub-card ds-notice">{notice}</div>}

      {tab === "agenda" && <Agenda base={groupwareApiBase} login={login} groups={groups} health={health} isAdmin={isAdmin} setError={setError} setNotice={setNotice} />}
      {tab === "contacts" && <Contacts base={groupwareApiBase} login={login} groups={groups} health={health} setError={setError} setNotice={setNotice} />}
      {tab === "dav" && (
        <div className="hub-card hub-settings-section">
          <h2>Agendas et carnets d'adresses synchronisés (CalDAV / CardDAV)</h2>
          {dav?.error ? <p className="ds-error">{dav.error}</p> : dav && (<>
            <p>Vos agendas et carnets vivent sur le serveur du hub (Radicale) et se synchronisent avec vos clients — identifiants : <b>ceux du hub (LDAP)</b>.</p>
            <table className="ds-table"><tbody>
              <tr><th>URL à donner au client</th><td><code>{dav.principal}</code> <button className="secondary pv-mini" onClick={() => navigator.clipboard?.writeText(dav.principal)}>copier</button></td></tr>
              <tr><th>Interface web Radicale</th><td><a href={`${dav.discovery}.web/`} target="_blank" rel="noreferrer">{dav.discovery}.web/</a> <span className="muted">(créer un agenda ou un carnet, importer un .ics / .vcf)</span></td></tr>
              <tr><th>Convention de nom</th><td>agendas : <code>agenda-…</code> · carnets : <code>contacts-…</code> <span className="muted">— c'est ce qui permet aux partages ci-contre de s'appliquer au bon type</span></td></tr>
            </tbody></table>
            <h3>Clients</h3>
            <table className="ds-table"><tbody>{Object.entries(dav.clients || {}).map(([k, v]) => <tr key={k}><th>{{ thunderbird: "Thunderbird", davx5: "Android (DAVx5)", ios_macos: "iPhone / Mac" }[k] || k}</th><td>{v}</td></tr>)}</tbody></table>
            <p className="muted">{health?.ldap ? "Groupes LDAP reconnus pour les partages de groupe." : "LDAP_GROUPS_DN absent : les partages à un groupe ne sont pas développés en membres côté DAV (seulement nominatifs)."}</p>
          </>)}
        </div>
      )}

      {tab === "grants" && (<>
        <div className="hub-card hub-settings-section">
          <h2>Partager mes données</h2>
          <p className="muted">Comme dans eGroupware : vous accordez à une personne ou à un groupe des droits sur <b>vos</b> données, application par application. Les partages d'agenda et de carnet sont appliqués au serveur CalDAV/CardDAV immédiatement.</p>
          <div className="ds-inline">
            <select value={form.app} onChange={(e) => setForm({ ...form, app: e.target.value })}>{Object.entries(APPS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <select value={form.grantee_kind} onChange={(e) => setForm({ ...form, grantee_kind: e.target.value })}><option value="user">à l'utilisateur</option><option value="group">au groupe</option><option value="all">à tous les connectés</option></select>
            {form.grantee_kind !== "all" && <input type="text" value={form.grantee} placeholder={form.grantee_kind === "user" ? "identifiant (uid)" : "nom du groupe"} onChange={(e) => setForm({ ...form, grantee: e.target.value })} />}
            <select value={form.rights} onChange={(e) => setForm({ ...form, rights: e.target.value })}>{RIGHT_PRESETS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <button className="primary" onClick={addGrant} disabled={form.grantee_kind !== "all" && !form.grantee}>Partager</button>
          </div>
          {Object.entries(mine.given).map(([app, list]) => <div key={app}><h3>{APPS[app]}</h3><table className="ds-table"><tbody>{list.map((g) => <tr key={g.id}><td>{g.grantee_kind === "group" ? "groupe " : g.grantee_kind === "all" ? "" : ""}<b>{g.grantee_kind === "all" ? "tous les connectés" : g.grantee}</b></td><td>{rightsLabel(g.rights_text)}</td><td className="muted">{(g.created_at || "").slice(0, 16).replace("T", " ")}</td><td><button className="secondary pv-mini pv-danger" onClick={() => removeGrant(g)}>retirer</button></td></tr>)}</tbody></table></div>)}
          {!Object.keys(mine.given).length && <p className="muted">Vous ne partagez rien pour l'instant.</p>}
        </div>
        <div className="hub-card hub-settings-section">
          <h2>Ce qu'on me partage</h2>
          {mine.received.length ? <table className="ds-table"><thead><tr><th>Propriétaire</th><th>Application</th><th>Mes droits</th></tr></thead><tbody>{mine.received.map((r, i) => <tr key={i}><td><b>{r.owner}</b></td><td>{APPS[r.app] || r.app}</td><td>{rightsLabel(r.rights)}</td></tr>)}</tbody></table> : <p className="muted">Aucun partage reçu (groupes pris en compte : {(groups || []).join(", ") || "aucun"}).</p>}
          {isAdmin && <p className="muted"><button className="secondary pv-mini" onClick={async () => { const r = await rebuildDav(groupwareApiBase); setNotice(r.ok ? `Droits DAV régénérés : ${r.rules} règle(s)` : r.error); }}>régénérer les droits DAV</button> (après un changement de membres de groupe dans l'annuaire)</p>}
        </div>
      </>)}

      {tab === "categories" && (
        <div className="hub-card hub-settings-section">
          <h2>Catégories</h2>
          <p className="muted">Globales ou par application ; partagées (visibles de tous) ou personnelles. Une catégorie peut avoir un parent.</p>
          <div className="ds-inline">
            <input type="text" value={catForm.name} placeholder="nom" onChange={(e) => setCatForm({ ...catForm, name: e.target.value })} />
            <select value={catForm.app} onChange={(e) => setCatForm({ ...catForm, app: e.target.value })}><option value="*">toutes les applications</option>{Object.entries(APPS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <input type="color" value={catForm.color || "#888888"} onChange={(e) => setCatForm({ ...catForm, color: e.target.value })} />
            <label className="pv-check"><input type="checkbox" checked={catForm.shared} onChange={(e) => setCatForm({ ...catForm, shared: e.target.checked })} /> partagée</label>
            <button className="primary" onClick={addCat} disabled={!catForm.name}>Ajouter</button>
          </div>
          <table className="ds-table"><thead><tr><th>Catégorie</th><th>Application</th><th>Portée</th><th></th></tr></thead>
            <tbody>{categoryTree(cats.filter((c) => !c.owner || c.owner === login)).flatMap((c) => [c, ...c.children.map((x) => ({ ...x, child: true }))]).map((c) => <tr key={c.id}><td style={{ paddingLeft: c.child ? 24 : 7 }}>{c.color && <span style={{ display: "inline-block", width: 10, height: 10, background: c.color, marginRight: 6, borderRadius: 2 }} />}<b>{c.name}</b></td><td>{c.app === "*" ? "toutes" : APPS[c.app] || c.app}</td><td>{c.owner ? "personnelle" : "partagée"}</td>
              <td className="pv-actions"><button className="secondary pv-mini" onClick={async () => { const n = window.prompt("Nouveau nom", c.name); if (n && n !== c.name) { await updateCategory(groupwareApiBase, c.id, { name: n }); load(); } }}>renommer</button>{(c.owner === login || isAdmin) && <button className="secondary pv-mini pv-danger" onClick={async () => { if (window.confirm(`Supprimer « ${c.name} » (et ses sous-catégories) ?`)) { await deleteCategory(groupwareApiBase, c.id); load(); } }}>✕</button>}</td></tr>)}
              {!cats.length && <tr><td colSpan={4} className="muted">Aucune catégorie.</td></tr>}</tbody></table>
        </div>
      )}

      {tab === "prefs" && (
        <div className="hub-card hub-settings-section">
          <h2>Préférences</h2>
          <p className="muted">Quatre niveaux, comme eGroupware : <b>défaut</b> (pour tous), <b>groupe</b>, <b>utilisateur</b>, et <b>forcée</b> par l'administrateur (prime sur tout). Les applications liront la valeur résolue (<code>/api/groupware/prefs?app=…&user=…</code>).</p>
          <div className="ds-inline">
            <select value={prefForm.level} onChange={(e) => setPrefForm({ ...prefForm, level: e.target.value })}><option value="user">utilisateur (moi)</option>{isAdmin && <><option value="group">groupe</option><option value="default">défaut</option><option value="forced">forcée</option></>}</select>
            {prefForm.level === "group" && <input type="text" value={prefForm.subject} placeholder="groupe" onChange={(e) => setPrefForm({ ...prefForm, subject: e.target.value })} />}
            <select value={prefForm.app} onChange={(e) => setPrefForm({ ...prefForm, app: e.target.value })}><option value="*">toutes</option>{Object.entries(APPS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <input type="text" value={prefForm.key} placeholder="clé (ex. view, tz, lang)" onChange={(e) => setPrefForm({ ...prefForm, key: e.target.value })} />
            <input type="text" value={prefForm.value} placeholder="valeur" onChange={(e) => setPrefForm({ ...prefForm, value: e.target.value })} />
            <button className="primary" disabled={!prefForm.key} onClick={() => savePref()}>Enregistrer</button>
          </div>
          {isAdmin && <table className="ds-table"><thead><tr><th>Niveau</th><th>Sujet</th><th>Application</th><th>Clé</th><th>Valeur</th><th></th></tr></thead>
            <tbody>{prefs.map((p) => <tr key={p.id}><td>{p.level}</td><td>{p.subject || "—"}</td><td>{p.app === "*" ? "toutes" : p.app}</td><td><code>{p.key}</code></td><td>{p.value}</td><td><button className="secondary pv-mini pv-danger" onClick={async () => { await deletePref(groupwareApiBase, p); load(); }}>✕</button></td></tr>)}{!prefs.length && <tr><td colSpan={6} className="muted">Aucune préférence enregistrée.</td></tr>}</tbody></table>}
        </div>
      )}
    </div>
  );
}
