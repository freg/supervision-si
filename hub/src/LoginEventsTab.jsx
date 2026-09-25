// Journal des connexions (livraison #612) -- onglet « Connexions » de la tuile
// Comptes : événements Keycloak du realm (connexions, échecs, déconnexions,
// échecs des clients de service) avec IP, client et raison traduite. Keycloak
// ne conserve rien par défaut : bouton d'activation (30 jours) sans purge.
// Règles design : en-tête fixé, contenu défile, filtre début de mot, bouton
// qui montre sa prise en compte.
import { useCallback, useEffect, useState } from "react";

async function call(url, init) {
  const r = await fetch(url, { credentials: "include", ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}

export default function LoginEventsTab({ apiBase, me, notice, error }) {
  const [data, setData] = useState(null);
  const [kind, setKind] = useState("");
  const [q, setQ] = useState("");
  const [busy, setBusy] = useState("");
  const load = useCallback(async (silent) => {
    if (!silent) setBusy("chargement…");
    try {
      const p = new URLSearchParams({ kind, q, limit: "400" });
      setData(await call(`${apiBase}/events?${p}`));
    } catch (e) { error(e.message); }
    setBusy("");
  }, [apiBase, kind, q]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { const t = setTimeout(() => load(true), q ? 250 : 0); return () => clearTimeout(t); }, [load, q]);
  const enable = async () => {
    setBusy("activation…");
    try {
      const r = await call(`${apiBase}/events/enable`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(me) });
      notice(r.changed ? `conservation des événements activée (${r.config.expiration_days} jours) — les prochaines connexions apparaîtront ici` : "conservation déjà active");
    } catch (e) { error(e.message); }
    await load(true);
  };
  if (!data) return <p className="muted">chargement…</p>;
  const { events, summary, config, types, labels } = data;
  return (
    <div className="hub-card lic-card hub-fill-column">
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <input placeholder="Filtrer (utilisateur, IP, client, raison)" value={q} onChange={(e) => setQ(e.target.value)} style={{ minWidth: 260 }} />
        <select value={kind} onChange={(e) => setKind(e.target.value)}>
          <option value="">— tous les événements —</option>
          <option value="errors">échecs seulement</option>
          {types.map((t) => <option key={t} value={t}>{labels[t]}</option>)}
        </select>
        <span className="muted">{summary.total} événement(s) · {summary.logins} connexion(s) · {summary.errors} échec(s) · {summary.users} utilisateur(s) · {summary.ips} adresse(s)</span>
        <span style={{ flex: 1 }} />
        <button type="button" className="secondary" disabled={!!busy} onClick={() => load(false)}>{busy === "chargement…" ? "⏳ chargement…" : "Actualiser"}</button>
      </div>
      {!config.enabled ? (
        <p style={{ color: "var(--warning)" }}>
          Keycloak ne conserve pas ses événements (réglage du realm) : seuls les échecs partent dans son journal texte, rien n'est consultable ici.
          {" "}<button type="button" disabled={!!busy} onClick={enable}>{busy === "activation…" ? "⏳ activation…" : `Activer la conservation (${30} jours)`}</button>
        </p>
      ) : (
        <p className="muted" style={{ marginTop: 0 }}>
          Conservation active{config.expiration_days ? ` (${config.expiration_days} jours)` : " (sans expiration)"} · {config.types_all ? "tous les types" : `types suivis${config.missing_types.length ? ` — manquants : ${config.missing_types.join(", ")}` : ""}`}.
          Les échecs « URL de retour non autorisée » se corrigent avec <code>KEYCLOAK_EXTRA_ORIGINS</code> puis <code>python3 keycloak/render.py && python3 keycloak/sync_clients.py</code>.
          {config.missing_types.length > 0 && <> <button type="button" className="secondary" disabled={!!busy} onClick={enable}>{busy === "activation…" ? "⏳…" : "Compléter les types"}</button></>}
        </p>
      )}
      <div className="hub-table-scroll hub-fill-scroll">
        <table>
          <thead><tr><th>Quand</th><th>Événement</th><th>Utilisateur</th><th>Adresse IP</th><th>Client</th><th>Raison / détail</th></tr></thead>
          <tbody>
            {events.length === 0 && <tr><td colSpan={6} className="muted">{config.enabled ? "aucun événement (pour ce filtre)" : "—"}</td></tr>}
            {events.map((e, i) => (
              <tr key={`${e.time}-${i}`} style={e.ok ? undefined : { color: "var(--danger)" }}>
                <td style={{ whiteSpace: "nowrap" }}>{(e.at || "").replace("T", " ").slice(0, 19)}</td>
                <td>{e.label}</td>
                <td>{e.user || <span className="muted">—</span>}</td>
                <td><code>{e.ip}</code></td>
                <td>{e.client}</td>
                <td>{e.reason}{e.redirect_uri && <span className="muted"> · {e.redirect_uri}</span>}{e.ok && e.auth_method && <span className="muted">{e.auth_method}</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
