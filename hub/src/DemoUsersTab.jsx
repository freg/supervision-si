// Utilisateurs de démonstration (livraison #608) -- onglet « Démo » de la tuile
// Comptes : profils demo-* (Keycloak local, hors LDAP), activer / désactiver /
// supprimer, mots de passe générés affichés une seule fois (à copier ou à
// lire à voix haute). Ils se connectent par le processus normal du hub.
import { useCallback, useEffect, useState } from "react";

async function call(url, init) {
  const r = await fetch(url, { credentials: "include", ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}
const J = (b) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });

export default function DemoUsersTab({ apiBase, me, notice, error }) {
  const [state, setState] = useState(null);
  const [busy, setBusy] = useState("");
  const [passwords, setPasswords] = useState(null);  // affichés une seule fois
  const load = useCallback(() => call(`${apiBase}/demo`).then(setState).catch((e) => error(e.message)), [apiBase]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load]);
  const enable = async (reset) => {
    setBusy(reset ? "réinitialisation…" : "activation…");
    try {
      const r = await call(`${apiBase}/demo/enable`, J({ ...me, reset_passwords: reset }));
      const withPw = r.users.filter((u) => u.password);
      setPasswords(withPw.length ? withPw : null);
      notice(`${r.users.length} compte(s) de démo actif(s)${withPw.length ? ` — ${withPw.length} mot(s) de passe affiché(s) ci-dessous, une seule fois` : ""}`);
    } catch (e) { error(e.message); }
    setBusy(""); load();
  };
  const disable = async () => {
    setBusy("désactivation…");
    try { const r = await call(`${apiBase}/demo/disable`, J(me)); setPasswords(null); notice(`${r.disabled} compte(s) désactivé(s), sessions fermées`); } catch (e) { error(e.message); }
    setBusy(""); load();
  };
  const remove = async () => {
    if (!window.confirm("Supprimer les comptes de démonstration ? (ils seront recréés à la prochaine activation, avec de nouveaux mots de passe)")) return;
    setBusy("suppression…");
    try { const r = await call(`${apiBase}/demo`, { method: "DELETE", headers: { "Content-Type": "application/json" }, body: JSON.stringify(me) }); setPasswords(null); notice(`${r.deleted} compte(s) supprimé(s)`); } catch (e) { error(e.message); }
    setBusy(""); load();
  };
  if (!state) return <p className="muted">chargement…</p>;
  const mode = state.summary.mode;
  return (
    <div className="hub-card lic-card">
      <p className="muted" style={{ marginTop: 0 }}>
        Comptes <code>demo-*</code> créés dans Keycloak (hors annuaire LDAP), rattachés aux groupes du hub, adresse <code>@{state.mail_domain}</code> (aucun courriel ne part). Ils se connectent par le processus normal.
        Activer crée ou réactive ; désactiver refuse la connexion et ferme les sessions, sans rien supprimer. Le mot de passe n'est montré qu'une fois : le copier ou le réinitialiser au début de chaque démo.
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
        <span style={{ fontWeight: 700, color: mode === "on" ? "var(--ok)" : mode === "partial" ? "var(--warning)" : "var(--muted)" }}>● {mode === "on" ? "démo ACTIVE" : mode === "partial" ? "partiellement active" : "démo inactive"}</span>
        <span className="muted">{state.summary.active} / {state.summary.profiles} compte(s) actif(s)</span>
        {mode !== "on" && <button type="button" onClick={() => enable(false)} disabled={!!busy}>{busy === "activation…" ? "⏳ activation…" : "Activer la démo"}</button>}
        {state.summary.existing > 0 && <button type="button" className="secondary" onClick={() => enable(true)} disabled={!!busy}>{busy === "réinitialisation…" ? "⏳ réinitialisation…" : "Activer + nouveaux mots de passe"}</button>}
        {state.summary.active > 0 && <button type="button" className="secondary" onClick={disable} disabled={!!busy}>{busy === "désactivation…" ? "⏳ désactivation…" : "Désactiver la démo"}</button>}
        {state.summary.existing > 0 && <button type="button" className="secondary" onClick={remove} disabled={!!busy}>Supprimer les comptes</button>}
      </div>
      {passwords && (
        <div style={{ border: "1px solid var(--warning)", borderRadius: 8, padding: 10, marginBottom: 10 }}>
          <b>Mots de passe (affichés une seule fois)</b>
          <table style={{ marginTop: 6, fontSize: 14 }}><tbody>
            {passwords.map((u) => <tr key={u.username}><td><code>{u.username}</code></td><td><code style={{ fontSize: 16, letterSpacing: 1 }}>{u.password}</code></td><td><button type="button" className="secondary" onClick={() => { try { navigator.clipboard.writeText(`${u.username} / ${u.password}`); } catch { /* presse-papiers indisponible */ } }}>copier</button></td></tr>)}
          </tbody></table>
        </div>
      )}
      <table style={{ width: "100%", fontSize: 13 }}>
        <thead><tr><th>Compte</th><th>Nom</th><th>Groupes</th><th>Rôle dans la démo</th><th>État</th></tr></thead>
        <tbody>
          {state.users.map((u) => (
            <tr key={u.username}>
              <td><code>{u.username}</code></td><td>{u.first_name} {u.last_name}</td><td>{u.groups.join(", ")}{u.exists && u.groups_current.join(",") !== u.groups.join(",") ? <span className="muted"> (actuel : {u.groups_current.join(", ") || "aucun"})</span> : null}</td>
              <td className="muted">{u.description}</td>
              <td>{!u.exists ? <span className="muted">absent</span> : u.enabled ? <span style={{ color: "var(--ok)" }}>actif</span> : <span style={{ color: "var(--warning)" }}>désactivé</span>}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="muted" style={{ fontSize: 12, marginBottom: 0 }}>Profils modifiables par <code>ACCOUNTS_DEMO_PROFILES</code> (JSON : username demo-…, groups, first_name, last_name, description) dans <code>.env</code>.</p>
    </div>
  );
}
