// Déploiement en masse des agents (livraison #616) -- onglet « Déploiement »
// de la tuile Agents : jetons d'enrôlement par site (ligne à coller en
// PowerShell administrateur ou shell root, ou URL du script pour GPO / Intune /
// PsExec), suivi des postes enrôlés par jeton. Le secret de chaque agent est
// délivré à l'enrôlement, sur le poste seulement : la ligne ne contient que le
// jeton, révocable et borné (usages, expiration).
import { useCallback, useEffect, useState } from "react";

async function call(url, init) {
  const r = await fetch(url, { ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}
const J = (m, b) => ({ method: m, headers: { "Content-Type": "application/json" }, body: JSON.stringify(b) });

function Copy({ text, label }) {
  const [done, setDone] = useState(false);
  return <button type="button" className="secondary" onClick={() => { navigator.clipboard?.writeText(text).then(() => { setDone(true); setTimeout(() => setDone(false), 1500); }); }}>{done ? "✓ copié" : label || "Copier"}</button>;
}

export default function DeployTab({ base, fleet, catalogue, notice, error, login }) {
  const [tokens, setTokens] = useState([]);
  const [publicUrl, setPublicUrl] = useState("");
  const [form, setForm] = useState({ site: "", label: "", central_url: "", max_uses: 0, expires_hours: 72, plugins: [] });
  const [created, setCreated] = useState(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => call(`${base}/enroll-tokens`).then((d) => { setTokens(d.tokens || []); setPublicUrl(d.public_url || ""); }).catch((e) => error(e.message)), [base]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load]);
  const sites = [...new Set((fleet || []).map((a) => a.site).filter(Boolean))].sort();
  const create = async (e) => {
    e.preventDefault(); setBusy("création…");
    try {
      const t = await call(`${base}/enroll-tokens`, J("POST", { ...form, central_url: form.central_url || publicUrl, created_by: login }));
      setCreated(t); notice(`jeton créé pour le site ${t.site}`);
    } catch (err) { error(err.message); }
    setBusy(""); load();
  };
  const revoke = async (tok) => {
    if (!window.confirm("Révoquer ce jeton ? Les postes déjà enrôlés ne sont pas touchés, aucun nouveau poste ne pourra l'utiliser.")) return;
    try { await call(`${base}/enroll-tokens/${encodeURIComponent(tok)}`, { method: "DELETE" }); notice("jeton révoqué"); } catch (err) { error(err.message); }
    load();
  };
  const enrolledBy = (tok) => (fleet || []).filter((a) => a.enrolled_by === tok);
  return (
    <div className="hub-card lic-card">
      <p className="muted" style={{ marginTop: 0 }}>
        Un <b>jeton d'enrôlement</b> par site : la même ligne s'exécute sur tous les postes (PowerShell administrateur, shell root, GPO de démarrage, Intune, PsExec) ; chaque poste s'enrôle sous son nom de machine et reçoit son propre secret. Depuis le campus ou Internet, l'URL publique du frontal suffit (certificat public, pas de CA à distribuer) ; sur le LAN du hub, l'adresse interne épingle la CA du projet.
      </p>
      <form className="lic-form" onSubmit={create} style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))", gap: 8, alignItems: "end" }}>
        <label>Site<input list="deploy-sites" value={form.site} onChange={(e) => setForm({ ...form, site: e.target.value })} placeholder="numeria" required /><datalist id="deploy-sites">{sites.map((s) => <option key={s} value={s} />)}</datalist></label>
        <label>Libellé<input value={form.label} onChange={(e) => setForm({ ...form, label: e.target.value })} placeholder="postes du campus" /></label>
        <label>URL du central vue des postes<input value={form.central_url} onChange={(e) => setForm({ ...form, central_url: e.target.value })} placeholder={publicUrl || "https://…/api/si-agent"} /></label>
        <label>Usages max (0 = illimité)<input type="number" min={0} value={form.max_uses} onChange={(e) => setForm({ ...form, max_uses: Number(e.target.value) })} /></label>
        <label>Validité (heures, 0 = sans limite)<input type="number" min={0} value={form.expires_hours} onChange={(e) => setForm({ ...form, expires_hours: Number(e.target.value) })} /></label>
        <label>Sondes activées à l'enrôlement
          <select multiple value={form.plugins} onChange={(e) => setForm({ ...form, plugins: [...e.target.selectedOptions].map((o) => o.value) })} style={{ minHeight: 70 }}>
            {(catalogue || []).map((p) => <option key={p.id} value={p.id}>{p.id}</option>)}
          </select>
        </label>
        <button type="submit" disabled={!!busy || !form.site}>{busy || "Créer le jeton"}</button>
      </form>
      {created && (
        <div style={{ border: "1px solid var(--ok)", borderRadius: 8, padding: 10, marginTop: 10 }}>
          <b>Jeton créé — lignes à exécuter sur les postes du site {created.site}</b>
          <div style={{ marginTop: 6 }}><span className="muted">Windows (PowerShell administrateur)</span><div style={{ display: "flex", gap: 6, alignItems: "center" }}><code style={{ flex: 1, wordBreak: "break-all", fontSize: 12 }}>{created.commands.windows}</code><Copy text={created.commands.windows} /></div></div>
          <div style={{ marginTop: 6 }}><span className="muted">Linux (root)</span><div style={{ display: "flex", gap: 6, alignItems: "center" }}><code style={{ flex: 1, wordBreak: "break-all", fontSize: 12 }}>{created.commands.linux}</code><Copy text={created.commands.linux} /></div></div>
          <div style={{ marginTop: 6 }}><span className="muted">GPO / Intune / PsExec : script à télécharger et pousser</span><div style={{ display: "flex", gap: 6, alignItems: "center" }}><code style={{ flex: 1, wordBreak: "break-all", fontSize: 12 }}>{created.commands.gpo}</code><Copy text={created.commands.gpo} /></div></div>
          <p className="muted" style={{ margin: "6px 0 0", fontSize: 12 }}>Le poste télécharge l'archive de l'agent et Python depuis python.org (accès Internet requis), s'enrôle, installe la tâche planifiée et apparaît dans la flotte sous son nom de machine en 1 à 2 minutes. Relancer la ligne sur un poste déjà enrôlé redonne un secret neuf, sans doublon.</p>
        </div>
      )}
      <h3 style={{ marginTop: 14 }}>Jetons</h3>
      <div className="hub-table-scroll">
        <table>
          <thead><tr><th>Site</th><th>Libellé</th><th>Central</th><th>Usages</th><th>Expire</th><th>État</th><th>Postes enrôlés</th><th></th></tr></thead>
          <tbody>
            {tokens.length === 0 && <tr><td colSpan={8} className="muted">aucun jeton</td></tr>}
            {tokens.map((t) => {
              const agents = enrolledBy(t.token);
              const online = agents.filter((a) => a.online === "online").length;
              return (
                <tr key={t.token}>
                  <td><b>{t.site}</b></td><td>{t.label || <span className="muted">—</span>}</td><td><code style={{ fontSize: 12 }}>{t.central_url || publicUrl || "?"}</code></td>
                  <td>{t.uses}{t.max_uses ? ` / ${t.max_uses}` : ""}</td>
                  <td className="muted">{t.expires_at ? t.expires_at.replace("T", " ").slice(0, 16) : "jamais"}</td>
                  <td>{t.usable ? <span style={{ color: "var(--ok)" }}>actif</span> : <span className="muted">{t.revoked ? "révoqué" : t.expired ? "expiré" : "épuisé"}</span>}</td>
                  <td>{agents.length === 0 ? <span className="muted">aucun</span> : <>{agents.length} ({online} en ligne) : {agents.map((a) => <code key={a.agent_id} style={{ marginRight: 4, color: a.online === "online" ? "var(--ok)" : undefined }}>{a.agent_id}</code>)}</>}</td>
                  <td style={{ whiteSpace: "nowrap" }}>
                    {t.usable && <Copy label="Ligne Windows" text={`powershell -NoProfile -ExecutionPolicy Bypass -Command "iex (iwr -UseBasicParsing '${(t.central_url || publicUrl).replace(/\/$/, "")}/deploy/windows?token=${t.token}').Content"`} />}{" "}
                    {t.usable && <button type="button" className="secondary" onClick={() => revoke(t.token)}>Révoquer</button>}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
