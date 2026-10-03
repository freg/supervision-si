import React, { useState, useEffect, useCallback } from "react";
import { listGrants, createGrant, deleteGrant, listCategories, createCategory, updateCategory, deleteCategory, rawPrefs, putPref, deletePref, davMe, rebuildDav, groupwareHealth, listAddressbooks, createAddressbook, listContacts, createContact, updateContact, deleteContact } from "./groupwareClient.js";
import { APPS, RIGHT_PRESETS, rightsLabel, myGrants, categoryTree, EMPTY_CONTACT, contactToForm, formToContact, contactRow } from "./groupwareLib.js";
import HubIcon from "./HubIcon.jsx";

// Tuile « Groupware » (livraison #664, item 115) -- tranche 1 d'un groupware « façon eGroupware » : mes accès
// CalDAV / CardDAV (Radicale, comptes LDAP), partages de mes données par application (grants : lecture, ajout,
// modification, suppression, privé) à un utilisateur ou un groupe, catégories partagées / personnelles, préférences
// (défaut, groupe, utilisateur, forcées par l'administrateur). Les applications (agenda, carnet, InfoLog) arrivent
// par tranches ; les clients DAV fonctionnent dès maintenant. Non vérifié en navigateur ; logique pure testée sous Node.
const TABS = [["contacts", "Carnet d'adresses"], ["dav", "Synchronisation (CalDAV, CardDAV)"], ["grants", "Partages"], ["categories", "Catégories"], ["prefs", "Préférences"]];

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
  if (health && health.contacts === false) return <div className="hub-card hub-settings-section"><h2>Carnet d'adresses</h2><p className="ds-error">Compte de service CardDAV non configuré (<code>GROUPWARE_DAV_SERVICE_USER</code> / <code>PASSWORD</code> dans le .env) : le carnet dans le hub est indisponible ; vos clients CardDAV fonctionnent (onglet Synchronisation).</p></div>;
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
  const [tab, setTab] = useState("contacts");
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
