// Comptes et groupes (livraison #557) : tuile pilotant Keycloak via
// accounts-api -- liste des comptes (recherche, filtre par groupe),
// création (mot de passe temporaire ou invitation par e-mail),
// activation, appartenance aux groupes, mot de passe, suppression ; groupes
// (création, suppression, membres). Tableaux alignés à gauche, sans icône.
// Logique pure dans accountsLib.js.
import { useEffect, useMemo, useState } from "react";
import { filterUsers, validateNewUser, membersByGroup } from "./accountsLib.js";

async function call(url, init) {
  const r = await fetch(url, { credentials: "include", ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}

const EMPTY = { username: "", email: "", first_name: "", last_name: "", password: "", temporary: true, member_of: [], allowKeycloakOnly: false };

export default function AccountsView({ onBack, accountsApiBase, groups, login, keycloakConsoleUrl = "" }) {
  const [tab, setTab] = useState("users");
  const [info, setInfo] = useState(null);
  const [users, setUsers] = useState([]);
  const [allGroups, setAllGroups] = useState([]);
  const [query, setQuery] = useState("");
  const [groupFilter, setGroupFilter] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [form, setForm] = useState(EMPTY);
  const [showForm, setShowForm] = useState(false);
  const [editing, setEditing] = useState(null); // user id dont on édite les groupes
  const [editGroups, setEditGroups] = useState([]);
  const [pwFor, setPwFor] = useState(null);
  const [pw, setPw] = useState({ password: "", temporary: true });
  const [newGroup, setNewGroup] = useState("");
  const [members, setMembers] = useState({});
  const me = { groups, user: login };

  const load = async () => {
    setBusy(true); setError(null);
    try {
      const [i, u, g] = await Promise.all([call(`${accountsApiBase}/info`), call(`${accountsApiBase}/users`), call(`${accountsApiBase}/groups`)]);
      setInfo(i); setUsers(u.users || []); setAllGroups(g.groups || []);
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [accountsApiBase]);

  const act = async (fn, ok) => {
    setBusy(true); setError(null); setNotice(null);
    try { await fn(); if (ok) setNotice(ok); await load(); return true; }
    catch (e) { setError(e.message); return false; }
    finally { setBusy(false); }
  };
  const json = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...me, ...(body || {}) }) });

  const shown = useMemo(() => filterUsers(users, query, groupFilter), [users, query, groupFilter]);
  const counts = useMemo(() => membersByGroup(users), [users]);
  const formErrors = validateNewUser(form, info ? info.ldap_writable : true);

  const createUser = async (e) => {
    e.preventDefault();
    if (formErrors.length) return;
    const ok = await act(() => call(`${accountsApiBase}/users`, json("POST", { username: form.username, email: form.email, first_name: form.first_name, last_name: form.last_name, password: form.password || null, temporary: form.temporary, member_of: form.member_of })),
      `Compte ${form.username} créé${form.password ? " avec un mot de passe temporaire" : ""}.`);
    if (ok) { setForm(EMPTY); setShowForm(false); }
  };

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>Comptes et groupes</h1>
      </div>
      <div className="tabs">
        <button className={tab === "users" ? "active" : ""} onClick={() => setTab("users")}>Comptes ({users.length})</button>
        <button className={tab === "groups" ? "active" : ""} onClick={() => setTab("groups")}>Groupes ({allGroups.length})</button>
      </div>
      {info && <p className="muted" style={{ marginTop: 0 }}>Realm {info.realm} · annuaire LDAP {info.ldap_writable ? "en écriture (les comptes créés vont dans l'annuaire)" : "en lecture seule (les comptes créés ici restent dans Keycloak)"} · écriture réservée aux groupes {info.admin_groups.join(", ")}.</p>}
      {error && (
        <p style={{ color: "var(--danger)" }}>
          {error}
          {/compte de service/.test(error) && (
            <span className="muted" style={{ display: "block", marginTop: 4 }}>
              Le secret du client de service ne correspond pas à Keycloak. Ouvrir <a href={`${keycloakConsoleUrl}#/${info?.realm || "supervision-si"}/clients`} target="_blank" rel="noopener noreferrer">la console Keycloak → Clients → {info?.service_client_id || "supervision-si-service"} → Credentials</a> (créer le client en « Client authentication » + « Service accounts roles » s'il n'existe pas, lui donner le rôle <code>realm-management / realm-admin</code>), copier le secret dans <code>.env</code> (<code>KEYCLOAK_SERVICE_CLIENT_SECRET</code>), puis <code>./scripts/run.sh up -d accounts-api</code>.
            </span>
          )}
        </p>
      )}
      {notice && <p style={{ color: "var(--ok, #2e7d32)" }}>{notice}</p>}

      {tab === "users" && (
        <div className="hub-card">
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
            <input placeholder="Rechercher (identifiant, nom, e-mail, groupe)" value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 280 }} />
            <select value={groupFilter} onChange={(e) => setGroupFilter(e.target.value)}><option value="">— tous les groupes —</option>{allGroups.map((g) => <option key={g.id} value={g.name}>{g.name}</option>)}</select>
            <span style={{ flex: 1 }} />
            <button type="button" className="secondary" disabled={busy} onClick={load}>Actualiser</button>
            <button type="button" onClick={() => setShowForm((v) => !v)}>{showForm ? "Fermer" : "Nouveau compte"}</button>
          </div>
          {showForm && (
            <form onSubmit={createUser} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 8, alignItems: "end", marginBottom: 12, padding: 10, border: "1px solid var(--border)", borderRadius: 8 }}>
              <label>Identifiant<input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} autoComplete="off" /></label>
              <label>Prénom<input value={form.first_name} onChange={(e) => setForm({ ...form, first_name: e.target.value })} /></label>
              <label>Nom<input value={form.last_name} onChange={(e) => setForm({ ...form, last_name: e.target.value })} /></label>
              <label>E-mail<input value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
              <label>Mot de passe temporaire (vide = invitation par e-mail)<input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="new-password" /></label>
              <label style={{ gridColumn: "1 / -1" }}>Groupes<div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>{allGroups.map((g) => <label key={g.id} style={{ fontWeight: 400 }}><input type="checkbox" checked={form.member_of.includes(g.name)} onChange={(e) => setForm({ ...form, member_of: e.target.checked ? [...form.member_of, g.name] : form.member_of.filter((x) => x !== g.name) })} /> {g.name}</label>)}</div></label>
              {info && !info.ldap_writable && <label style={{ gridColumn: "1 / -1", fontWeight: 400 }}><input type="checkbox" checked={form.allowKeycloakOnly} onChange={(e) => setForm({ ...form, allowKeycloakOnly: e.target.checked })} /> Je comprends que le compte sera créé dans Keycloak seulement (annuaire en lecture seule).</label>}
              {formErrors.length > 0 && <p className="muted" style={{ gridColumn: "1 / -1", margin: 0 }}>{formErrors.join(" · ")}</p>}
              <div><button type="submit" disabled={busy || formErrors.length > 0}>Créer</button></div>
            </form>
          )}
          <table style={{ width: "100%", textAlign: "left" }}>
            <thead><tr style={{ textAlign: "left" }}><th>Identifiant</th><th>Nom</th><th>E-mail</th><th>Groupes</th><th>Actif</th><th>Source</th><th></th></tr></thead>
            <tbody>
              {shown.map((u) => (
                <tr key={u.id} style={{ verticalAlign: "top", opacity: u.enabled ? 1 : 0.55 }}>
                  <td><strong>{u.username}</strong>{u.required_actions?.length > 0 && <div className="muted" style={{ fontSize: 11 }}>à faire : {u.required_actions.join(", ")}</div>}</td>
                  <td>{[u.first_name, u.last_name].filter(Boolean).join(" ") || <span className="muted">—</span>}</td>
                  <td>{u.email || <span className="muted">—</span>}</td>
                  <td>
                    {editing === u.id ? (
                      <div>
                        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>{allGroups.map((g) => <label key={g.id} style={{ fontWeight: 400, whiteSpace: "nowrap" }}><input type="checkbox" checked={editGroups.includes(g.name)} onChange={(e) => setEditGroups(e.target.checked ? [...editGroups, g.name] : editGroups.filter((x) => x !== g.name))} /> {g.name}</label>)}</div>
                        <div style={{ marginTop: 4, display: "flex", gap: 6 }}>
                          <button type="button" disabled={busy} onClick={async () => { if (await act(() => call(`${accountsApiBase}/users/${u.id}/groups`, json("PUT", { member_of: editGroups })), `Groupes de ${u.username} enregistrés.`)) setEditing(null); }}>Enregistrer</button>
                          <button type="button" className="secondary" onClick={() => setEditing(null)}>Annuler</button>
                        </div>
                      </div>
                    ) : (
                      <span>{(u.groups || []).join(", ") || <span className="muted">aucun</span>} <button type="button" className="secondary" style={{ fontSize: 11 }} onClick={() => { setEditing(u.id); setEditGroups(u.groups || []); }}>modifier</button></span>
                    )}
                  </td>
                  <td><label style={{ fontWeight: 400 }}><input type="checkbox" checked={u.enabled} disabled={busy} onChange={(e) => act(() => call(`${accountsApiBase}/users/${u.id}`, json("PUT", { enabled: e.target.checked })), `${u.username} ${e.target.checked ? "activé" : "désactivé"}.`)} /> {u.enabled ? "oui" : "non"}</label></td>
                  <td className="muted">{u.federated ? "annuaire LDAP" : "Keycloak"}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {pwFor === u.id ? (
                      <span style={{ display: "inline-flex", gap: 4, alignItems: "center" }}>
                        <input type="password" placeholder="nouveau mot de passe" value={pw.password} onChange={(e) => setPw({ ...pw, password: e.target.value })} autoComplete="new-password" style={{ width: 160 }} />
                        <label style={{ fontWeight: 400 }}><input type="checkbox" checked={pw.temporary} onChange={(e) => setPw({ ...pw, temporary: e.target.checked })} /> à changer</label>
                        <button type="button" disabled={busy || pw.password.length < 8} onClick={async () => { if (await act(() => call(`${accountsApiBase}/users/${u.id}/password`, json("PUT", pw)), `Mot de passe de ${u.username} réinitialisé.`)) { setPwFor(null); setPw({ password: "", temporary: true }); } }}>OK</button>
                        <button type="button" className="secondary" onClick={() => { setPwFor(null); setPw({ password: "", temporary: true }); }}>✕</button>
                      </span>
                    ) : (
                      <span style={{ display: "inline-flex", gap: 4 }}>
                        <button type="button" className="secondary" disabled={busy} onClick={() => setPwFor(u.id)}>Mot de passe</button>
                        {u.email && <button type="button" className="secondary" disabled={busy} title="Envoie un e-mail Keycloak demandant un nouveau mot de passe" onClick={() => act(() => call(`${accountsApiBase}/users/${u.id}/send-reset`, json("POST")), `E-mail de réinitialisation envoyé à ${u.email}.`)}>Inviter</button>}
                        <button type="button" className="secondary" disabled={busy || u.username === login} onClick={() => { if (window.confirm(`Supprimer le compte ${u.username} ? Cette action est définitive.`)) act(() => call(`${accountsApiBase}/users/${u.id}`, json("DELETE")), `Compte ${u.username} supprimé.`); }}>Supprimer</button>
                      </span>
                    )}
                  </td>
                </tr>
              ))}
              {shown.length === 0 && <tr><td colSpan={7} className="muted">Aucun compte{query || groupFilter ? " pour ce filtre" : ""}.</td></tr>}
            </tbody>
          </table>
        </div>
      )}

      {tab === "groups" && (
        <div className="hub-card">
          <form onSubmit={(e) => { e.preventDefault(); if (newGroup.trim()) act(() => call(`${accountsApiBase}/groups`, json("POST", { name: newGroup.trim() })), `Groupe ${newGroup.trim()} créé.`).then((ok) => ok && setNewGroup("")); }} style={{ display: "flex", gap: 8, marginBottom: 10 }}>
            <input placeholder="nouveau groupe (ex. site-alpha)" value={newGroup} onChange={(e) => setNewGroup(e.target.value)} />
            <button type="submit" disabled={busy || !newGroup.trim()}>Créer le groupe</button>
          </form>
          <table style={{ width: "100%", textAlign: "left" }}>
            <thead><tr style={{ textAlign: "left" }}><th>Groupe</th><th>Membres</th><th></th></tr></thead>
            <tbody>
              {allGroups.map((g) => (
                <tr key={g.id} style={{ verticalAlign: "top" }}>
                  <td><strong>{g.name}</strong></td>
                  <td>{counts[g.name] || 0}{members[g.id] ? <div className="muted" style={{ fontSize: 12 }}>{members[g.id].map((m) => m.username).join(", ") || "aucun"}</div> : <button type="button" className="secondary" style={{ marginLeft: 6, fontSize: 11 }} onClick={async () => { try { const r = await call(`${accountsApiBase}/groups/${g.id}/members`); setMembers({ ...members, [g.id]: r.members || [] }); } catch (e) { setError(e.message); } }}>voir</button>}</td>
                  <td style={{ whiteSpace: "nowrap" }}><button type="button" className="secondary" disabled={busy || (counts[g.name] || 0) > 0} title={(counts[g.name] || 0) > 0 ? "Retirer d'abord les membres" : ""} onClick={() => { if (window.confirm(`Supprimer le groupe ${g.name} ?`)) act(() => call(`${accountsApiBase}/groups/${g.id}`, json("DELETE")), `Groupe ${g.name} supprimé.`); }}>Supprimer</button></td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="muted" style={{ fontSize: 12 }}>Les droits d'un groupe sur les tuiles et actions du hub se règlent dans la tuile Droits.</p>
        </div>
      )}
    </div>
  );
}
