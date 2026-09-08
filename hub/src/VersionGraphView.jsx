// Visualiseur du graphe d'évolution des versions d'un document (livraison
// #460) : SVG façon « git log --graph » (voies = branches, lignes =
// versions), statut coloré (brouillon / officielle / remplacée / archivée),
// check-out / check-in (SoftSolutions : celui qui a sorti le document est
// le seul à déposer une version), promotion en officielle, choix du parent
// et de la branche, archive immuable, dépôt d'une version dérivée.
import { useCallback, useEffect, useState } from "react";
import { fetchVersionGraph, setVersionMeta, checkoutDocument, checkinDocument, archiveVersion, uploadNewVersionWithMeta, documentDownloadUrl, archiveDownloadUrl } from "./gedClient.js";
import { layout, STATUS, describeNode, nodeActions, checkoutText } from "./versionGraph.js";

export default function VersionGraphView({ gedApiBase, documentId, login, groups = [], onChanged }) {
  const [graph, setGraph] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const [selected, setSelected] = useState(null);
  const [form, setForm] = useState({ branch: "", comment: "", parent: "" });

  const load = useCallback(async () => {
    const g = await fetchVersionGraph(gedApiBase, documentId);
    if (g.error) setError(g.error); else { setError(null); setGraph(g); }
  }, [gedApiBase, documentId]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn) => { setBusy(true); const r = await fn(); setBusy(false); if (r?.error) setError(r.error); else { setError(null); load(); onChanged?.(); } };
  if (error && !graph) return <p className="hub-error">{error}</p>;
  if (!graph) return <p className="muted">Chargement du graphe…</p>;
  const l = layout(graph);
  const sel = graph.nodes.find((n) => n.version === selected) || null;
  const co = graph.checkout;

  return (
    <div className="vg">
      {error && <p className="hub-error">{error}</p>}
      <p style={{ margin: "0 0 6px" }}>
        <strong>{graph.document?.name}</strong> — {graph.nodes.length} version(s), {graph.branches.length} branche(s), officielle : {graph.official ? `v${graph.official}` : "aucune"} · {checkoutText(co, login)}
        {" "}{!co && <button className="secondary ss-origin" disabled={busy} onClick={() => act(() => checkoutDocument(gedApiBase, documentId, login, graph.official || graph.nodes.at(-1)?.version))}>📤 sortir (check-out)</button>}
        {co && co.user === login && <button className="secondary ss-origin" disabled={busy} onClick={() => act(() => checkinDocument(gedApiBase, documentId, login, false, groups))}>📥 rendre (check-in)</button>}
        {co && co.user !== login && groups.includes("admin_hub") && <button className="secondary ss-origin" disabled={busy} onClick={() => { if (window.confirm(`Forcer le retour du document sorti par ${co.user} ?`)) act(() => checkinDocument(gedApiBase, documentId, login, true, groups)); }}>forcer le retour</button>}
      </p>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start", flexWrap: "wrap", flexDirection: "column" }}>
        <svg width={l.width + 640} height={l.height} style={{ flex: "0 0 auto", overflow: "visible" }} role="img" aria-label="graphe des versions">
          {l.edges.map((e, i) => <path key={i} d={e.d} fill="none" stroke={e.fork ? "#d69a2b" : "#6c8ebf"} strokeWidth={2} />)}
          {l.nodes.map((n) => {
            const st = STATUS[n.status] || STATUS.draft;
            return (
              <g key={n.version} transform={`translate(${n.x},${n.y})`} style={{ cursor: "pointer" }} onClick={() => setSelected(n.version === selected ? null : n.version)}>
                <circle r={n.version === selected ? 9 : 7} fill={st.color} stroke={n.version === graph.official ? "#000" : "#fff"} strokeWidth={n.version === graph.official ? 2.5 : 1.5} />
                {n.archived && <circle r={11} fill="none" stroke={STATUS.archived.color} strokeDasharray="3 2" />}
                <text x={l.width - n.x + 4} y={4} fontSize={12} fill="currentColor">{describeNode(n)}{n.comment ? ` — ${n.comment}` : ""}</text>
                <title>{describeNode(n)}{n.created_at ? ` · ${n.created_at}` : ""}{n.filename ? ` · ${n.filename}` : ""}</title>
              </g>
            );
          })}
        </svg>
        <div style={{ flex: "1 1 320px", minWidth: 280 }}>
          <p className="muted" style={{ margin: "0 0 6px", fontSize: 12 }}>
            {Object.entries(STATUS).map(([k, v]) => <span key={k} style={{ marginRight: 10 }}><span style={{ display: "inline-block", width: 10, height: 10, borderRadius: 5, background: v.color, marginRight: 4 }} />{v.label}</span>)}
            · contour noir = officielle · cercle pointillé = archive immuable · trait orange = fourche (branche)
          </p>
          {sel ? (
            <div className="hub-card hub-settings-section" style={{ padding: 10, textAlign: "left" }}>
              <strong>v{sel.version}</strong> <span className="muted">{sel.filename || ""} {sel.created_at || ""}</span>
              <p style={{ margin: "4px 0" }}>
                <a href={documentDownloadUrl(gedApiBase, documentId, sel.version)} target="_blank" rel="noreferrer">télécharger cette version</a>
                {sel.archived && <> · <a href={archiveDownloadUrl(gedApiBase, documentId, sel.version)} target="_blank" rel="noreferrer">copie d'archive (sha256 {sel.archive?.sha256?.slice(0, 12)}…)</a></>}
              </p>
              <p style={{ margin: "4px 0" }}>
                {nodeActions(sel, graph, login).includes("official") && <button className="secondary" disabled={busy} onClick={() => act(() => setVersionMeta(gedApiBase, documentId, sel.version, { status: "official", groups }))}>★ rendre officielle</button>}{" "}
                {nodeActions(sel, graph, login).includes("archive") && <button className="secondary" disabled={busy} onClick={() => { if (window.confirm(`Archiver v${sel.version} (copie immuable, statut définitif) ?`)) act(() => archiveVersion(gedApiBase, documentId, sel.version, login, groups)); }}>🗄 archiver (immuable)</button>}
              </p>
              <details>
                <summary className="muted">Profil de la version : parent, branche, commentaire</summary>
                <p style={{ margin: "4px 0" }}>
                  parent : <select value={form.parent || sel.parent || ""} onChange={(e) => setForm({ ...form, parent: e.target.value })}>
                    <option value="">(aucun)</option>{graph.nodes.filter((n) => n.version < sel.version).map((n) => <option key={n.version} value={n.version}>v{n.version}</option>)}
                  </select>{" "}
                  branche : <input className="ss-search" style={{ width: 140 }} placeholder={sel.branch} value={form.branch} onChange={(e) => setForm({ ...form, branch: e.target.value })} />{" "}
                  commentaire : <input className="ss-search" style={{ width: 200 }} placeholder={sel.comment || ""} value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} />{" "}
                  <button className="secondary" disabled={busy} onClick={() => act(() => setVersionMeta(gedApiBase, documentId, sel.version, {
                    ...(form.parent ? { parent_version: Number(form.parent) } : {}), ...(form.branch ? { branch: form.branch } : {}), ...(form.comment ? { comment: form.comment } : {}), groups }))}>enregistrer</button>
                </p>
              </details>
              {(!co || co.user === login) && (
                <p style={{ margin: "6px 0 0" }}>
                  <label className="secondary" style={{ display: "inline-block", cursor: "pointer", border: "1px solid var(--border)", borderRadius: 4, padding: "4px 8px" }}>
                    + version dérivée de v{sel.version}{form.branch ? ` (branche ${form.branch})` : ""}
                    <input type="file" style={{ display: "none" }} disabled={busy} onChange={(e) => { const f = e.target.files?.[0]; if (f) act(() => uploadNewVersionWithMeta(gedApiBase, documentId, f, { actor: login, parentVersion: sel.version, branch: form.branch || undefined, comment: form.comment || undefined, checkin: !!co })); e.target.value = ""; }} />
                  </label>
                  {co && <span className="muted"> (dépose et rend le document)</span>}
                </p>
              )}
            </div>
          ) : <p className="muted">Cliquer une version pour la promouvoir, l'archiver, régler son parent / sa branche ou déposer une version dérivée.</p>}
        </div>
      </div>
    </div>
  );
}
