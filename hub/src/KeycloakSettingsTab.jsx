// Réglages Keycloak depuis le hub, en liste blanche (livraison #614, item 98) :
// général, page de connexion, sessions et jetons, protection force brute, mots
// de passe, événements ; origines des clients OIDC (ajout dérivé de l'origine
// interne, jamais de retrait) ; synchronisation LDAP. Aperçu avant / après
// (simulation) puis application ; tout le reste du realm reste hors de portée.
import { useCallback, useEffect, useState } from "react";

async function call(url, init) {
  const r = await fetch(url, { credentials: "include", ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}
const J = (m, b) => ({ method: m, headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });
const fmtSeconds = (s) => { const n = Number(s); if (!n) return "0"; if (n % 86400 === 0) return `${n / 86400} j`; if (n % 3600 === 0) return `${n / 3600} h`; if (n % 60 === 0) return `${n / 60} min`; return `${n} s`; };
const parseSeconds = (t) => { const m = String(t).trim().match(/^(\d+)\s*(s|min|h|j)?$/i); if (!m) return NaN; return Number(m[1]) * ({ s: 1, min: 60, h: 3600, j: 86400 }[(m[2] || "s").toLowerCase()]); };

export default function KeycloakSettingsTab({ apiBase, me, notice, error, isAdmin }) {
  const [data, setData] = useState(null);
  const [form, setForm] = useState({});
  const [preview, setPreview] = useState(null);
  const [busy, setBusy] = useState("");
  const [origin, setOrigin] = useState("");
  const load = useCallback(() => call(`${apiBase}/keycloak-settings`).then((d) => { setData(d); setForm(Object.fromEntries(Object.entries(d.values).map(([k, v]) => [k, d.fields.find((f) => f.key === k)?.type === "seconds" ? fmtSeconds(v) : v ?? ""]))); }).catch((e) => error(e.message)), [apiBase]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load]);
  if (!data) return <p className="muted">chargement…</p>;
  const values = () => Object.fromEntries(data.fields.map((f) => [f.key, f.type === "seconds" ? parseSeconds(form[f.key]) : f.type === "bool" ? !!form[f.key] : form[f.key]]));
  const simulate = async () => {
    setBusy("simulation…");
    try { const r = await call(`${apiBase}/keycloak-settings`, J("PUT", { ...me, values: values(), dry_run: true })); setPreview(r); if (!Object.keys(r.changes).length && !r.errors.length) notice("aucun changement"); }
    catch (e) { error(e.message); }
    setBusy("");
  };
  const apply = async () => {
    setBusy("application…");
    try { const r = await call(`${apiBase}/keycloak-settings`, J("PUT", { ...me, values: values() })); setPreview(null); notice(r.applied ? `${Object.keys(r.changes).length} réglage(s) appliqué(s) dans Keycloak` : "rien à appliquer"); if (r.errors.length) error(r.errors.join(" ; ")); }
    catch (e) { error(e.message); }
    setBusy(""); load();
  };
  const addOrigin = async (dry) => {
    setBusy(dry ? "aperçu…" : "ajout…");
    try {
      const r = await call(`${apiBase}/keycloak-settings/origins`, J("POST", { ...me, origin, dry_run: dry }));
      if (dry) setPreview({ origins: r.clients });
      else { setPreview(null); notice(r.applied ? `origine ajoutée à ${r.clients.length} client(s) — effet immédiat` : "déjà présente partout"); }
    } catch (e) { error(e.message); }
    setBusy(""); if (!dry) load();
  };
  const ldapSync = async (id, full) => {
    setBusy(full ? "synchronisation complète…" : "synchronisation…");
    try { const r = await call(`${apiBase}/keycloak-settings/ldap-sync`, J("POST", { ...me, id, full })); const s = r.result || {}; notice(`${r.provider} : ${s.added ?? 0} ajouté(s), ${s.updated ?? 0} mis à jour, ${s.removed ?? 0} retiré(s), ${s.failed ?? 0} en échec`); }
    catch (e) { error(e.message); }
    setBusy("");
  };
  const groups = Object.entries(data.groups);
  return (
    <div className="hub-card lic-card">
      <p className="muted" style={{ marginTop: 0 }}>
        Seuls les réglages ci-dessous sont modifiables d'ici (liste blanche côté API) ; le realm master, les clients de service et leurs secrets, les rôles d'administration, les comptes et le mot de passe de liaison LDAP restent hors de portée. Chaque modification est simulée (avant / après) puis appliquée, et tracée dans les Journaux.
        {!isAdmin && <b> Lecture seule (groupe administrateurs requis pour modifier).</b>}
      </p>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))", gap: 12 }}>
        {groups.map(([g, label]) => (
          <div key={g} className="hub-settings-section" style={{ padding: 12 }}>
            <h2 style={{ fontSize: 15 }}>{label}</h2>
            {data.fields.filter((f) => f.group === g).map((f) => (
              <div key={f.key} className="hub-settings-row">
                <label>{f.label}{f.type === "seconds" && <span className="muted"> (s, min, h, j — {f.min}–{fmtSeconds(f.max)})</span>}{f.type === "int" && <span className="muted"> ({f.min}–{f.max})</span>}</label>
                {f.type === "bool" ? <input type="checkbox" checked={!!form[f.key]} disabled={!isAdmin} onChange={(e) => setForm({ ...form, [f.key]: e.target.checked })} />
                  : <input type="text" value={form[f.key] ?? ""} disabled={!isAdmin} onChange={(e) => setForm({ ...form, [f.key]: e.target.value })} />}
              </div>
            ))}
          </div>
        ))}
      </div>
      {isAdmin && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 10, flexWrap: "wrap" }}>
          <button type="button" className="secondary" disabled={!!busy} onClick={simulate}>{busy === "simulation…" ? "⏳ simulation…" : "Simuler (avant / après)"}</button>
          <button type="button" disabled={!!busy || !preview?.changes || !Object.keys(preview.changes).length} onClick={apply}>{busy === "application…" ? "⏳ application…" : "Appliquer dans Keycloak"}</button>
          <button type="button" className="secondary" disabled={!!busy} onClick={load}>Recharger</button>
        </div>
      )}
      {preview?.changes && (
        <div style={{ border: "1px solid var(--warning)", borderRadius: 8, padding: 10, marginTop: 8 }}>
          <b>Changements à appliquer</b>
          {Object.keys(preview.changes).length === 0 && <p className="muted" style={{ margin: "4px 0" }}>aucun</p>}
          <table><tbody>{Object.entries(preview.changes).map(([k, c]) => <tr key={k}><td>{data.fields.find((f) => f.key === k)?.label || k}</td><td><code>{String(c.before ?? "—")}</code> → <code>{String(c.after)}</code></td></tr>)}</tbody></table>
          {preview.errors?.length > 0 && <p style={{ color: "var(--danger)", margin: "4px 0" }}>Refusés : {preview.errors.join(" ; ")}</p>}
        </div>
      )}

      <h2 style={{ fontSize: 15, marginTop: 16 }}>Origines des clients OIDC</h2>
      <p className="muted" style={{ margin: "0 0 6px" }}>Origine interne de référence : <code>{data.hub_origin || "?"}</code>. Ajouter une origine publique (frontal, nom de site) recopie pour chaque client les URL de retour et origines existantes vers la nouvelle — équivalent de <code>KEYCLOAK_EXTRA_ORIGINS</code> + <code>keycloak/sync_clients.py</code>, sans redémarrage. Rien n'est retiré d'ici.</p>
      <div className="hub-table-scroll" style={{ maxHeight: 260, overflow: "auto" }}>
        <table>
          <thead><tr><th>Client</th><th>URL de retour</th><th>Origines web</th></tr></thead>
          <tbody>{data.clients.map((c) => <tr key={c.clientId}><td><b>{c.clientId}</b></td><td>{c.redirectUris.map((u) => <div key={u}><code>{u}</code></div>)}</td><td>{c.webOrigins.map((u) => <div key={u}><code>{u}</code></div>)}</td></tr>)}</tbody>
        </table>
      </div>
      {isAdmin && (
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 8, flexWrap: "wrap" }}>
          <input placeholder="https://supervision.exemple.fr" value={origin} onChange={(e) => setOrigin(e.target.value)} style={{ minWidth: 280 }} />
          <button type="button" className="secondary" disabled={!!busy || !origin} onClick={() => addOrigin(true)}>{busy === "aperçu…" ? "⏳…" : "Aperçu"}</button>
          <button type="button" disabled={!!busy || !origin || !preview?.origins} onClick={() => addOrigin(false)}>{busy === "ajout…" ? "⏳ ajout…" : "Ajouter cette origine"}</button>
        </div>
      )}
      {preview?.origins && (
        <div style={{ border: "1px solid var(--warning)", borderRadius: 8, padding: 10, marginTop: 8 }}>
          <b>Entrées qui seraient ajoutées</b>
          {preview.origins.length === 0 ? <p className="muted" style={{ margin: "4px 0" }}>aucune (déjà présentes, ou aucun client ne référence l'origine interne)</p>
            : preview.origins.map((c) => <div key={c.clientId}><b>{c.clientId}</b> : {(c.redirectUris || []).concat(c.webOrigins || []).filter((u) => u.startsWith(origin.replace(/\/$/, ""))).map((u) => <code key={u} style={{ marginRight: 6 }}>{u}</code>)}</div>)}
        </div>
      )}

      <h2 style={{ fontSize: 15, marginTop: 16 }}>Fédération LDAP</h2>
      {data.ldap.length === 0 ? <p className="muted">Aucune fédération LDAP dans le realm.</p> : data.ldap.map((p) => (
        <div key={p.id} style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 6 }}>
          <b>{p.name}</b> <code>{p.url}</code> <span className="muted">· {p.users_dn} · liaison {p.bind_dn} · {p.edit_mode} · {p.enabled ? "active" : "inactive"}{p.sync_period > 0 && <> · synchro complète toutes les {fmtSeconds(p.sync_period)}</>}{p.changed_sync_period > 0 && <> · changements toutes les {fmtSeconds(p.changed_sync_period)}</>}</span>
          {isAdmin && <>
            <button type="button" className="secondary" disabled={!!busy} onClick={() => ldapSync(p.id, false)}>{busy === "synchronisation…" ? "⏳…" : "Synchroniser les changements"}</button>
            <button type="button" className="secondary" disabled={!!busy} onClick={() => window.confirm("Synchronisation complète de l'annuaire : peut prendre plusieurs minutes. Continuer ?") && ldapSync(p.id, true)}>{busy === "synchronisation complète…" ? "⏳ synchronisation…" : "Synchronisation complète"}</button>
          </>}
        </div>
      ))}
      <p className="muted" style={{ fontSize: 12 }}>Le mot de passe de liaison n'est ni affiché ni modifiable ici (fichier <code>.env</code> + <code>keycloak/render.py</code>). Le reste de la console Keycloak reste accessible aux administrateurs par le lien « console Keycloak » de la tuile.</p>
    </div>
  );
}
