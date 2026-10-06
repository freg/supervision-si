// Tuile « Vulnérabilités » (livraison #688) : SBOM (syft) → OSV (osv-scanner)
// → priorisation EPSS + KEV × exposition → (option) Dependency-Track.
// Ce qui est à traiter d'abord est en haut : P1 = exploitée activement (KEV)
// ou très probable sur un actif exposé.
import { useEffect, useState } from "react";
import HubIcon from "./HubIcon.jsx";

const PRIO_TONE = { P1: "bad", P2: "warn", P3: "neutral", P4: "neutral" };

async function call(base, path, opts = {}) {
  const r = await fetch(`${base}${path}`, { credentials: "include", ...opts });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}

const when = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "jamais");

export default function VulnView({ onBack, vulnApiBase }) {
  const [summary, setSummary] = useState(null);
  const [assets, setAssets] = useState([]);
  const [findings, setFindings] = useState([]);
  const [asset, setAsset] = useState("");
  const [prio, setPrio] = useState("P1,P2");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState(null);

  const load = async () => {
    try {
      const [s, a, f] = await Promise.all([
        call(vulnApiBase, "/summary"), call(vulnApiBase, "/assets"),
        call(vulnApiBase, `/findings?limit=500${prio ? `&priority=${prio}` : ""}${asset ? `&asset=${encodeURIComponent(asset)}` : ""}`),
      ]);
      setSummary(s); setAssets(a); setFindings(f);
    } catch (e) { setMsg(e.message); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [prio, asset]);

  const act = async (label, path, opts) => {
    setBusy(label); setMsg(null);
    try { const r = await call(vulnApiBase, path, { method: "POST", ...opts }); setMsg(`${label} : ${JSON.stringify(r).slice(0, 300)}`); await load(); }
    catch (e) { setMsg(`${label} : ${e.message}`); }
    setBusy("");
  };
  const upload = (file) => {
    if (!file) return;
    const name = window.prompt("Nom de l'actif (hôte, image, application) :", file.name.replace(/\.(cdx\.)?json$/, ""));
    if (!name) return;
    const exposed = window.confirm("Cet actif est-il exposé à Internet ?");
    const fd = new FormData(); fd.append("file", file);
    act("dépôt SBOM", `/sbom?asset=${encodeURIComponent(name)}&kind=host&exposed=${exposed ? 1 : 0}`, { body: fd });
  };
  const toggleExposed = async (a) => {
    await call(vulnApiBase, `/assets/${encodeURIComponent(a.name)}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ exposed: !a.exposed }) });
    load();
  };

  const feeds = summary?.feeds || {};
  return (
    <div className="hub-settings">
      <div className="hub-settings-topbar"><button className="secondary" onClick={onBack}>◀ Retour</button><h1><HubIcon icon="shield" size={22} /> Vulnérabilités — SBOM, OSV, EPSS, KEV</h1></div>
      {summary && (
        <p>
          <span className={`np-tone ${summary.P1 ? "bad" : "good"}`}>{summary.P1} P1</span>{" "}
          <span className={`np-tone ${summary.P2 ? "warn" : "neutral"}`}>{summary.P2} P2</span>{" "}
          <span className="np-tone neutral">{summary.P3} P3</span> <span className="np-tone neutral">{summary.P4} P4</span>
          <span className="muted"> · {summary.kev} exploitée(s) activement (KEV) · {summary.assets} actif(s) dont {summary.exposed_assets} exposé(s)
            · EPSS {when(feeds.epss?.at)}{feeds.epss?.error ? " (échec du dernier rechargement)" : ""} · KEV {when(feeds.kev?.at)}{feeds.kev?.error ? " (échec)" : ""}
            · Dependency-Track {summary.dependency_track ? "branché" : "non configuré"}</span>
        </p>
      )}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
        <button type="button" className="secondary" disabled={!!busy} onClick={() => act("flux EPSS/KEV", "/feeds/refresh")}>{busy === "flux EPSS/KEV" ? "⏳…" : "Recharger EPSS et KEV"}</button>
        <button type="button" className="secondary" disabled={!!busy} onClick={() => act("analyse du dépôt", "/scan/self")}>{busy === "analyse du dépôt" ? "⏳ syft…" : "Analyser le dépôt supervision-si"}</button>
        <label className="secondary" style={{ cursor: "pointer" }}>Déposer un SBOM (CycloneDX JSON)
          <input type="file" accept=".json" style={{ display: "none" }} onChange={(e) => { upload(e.target.files[0]); e.target.value = ""; }} />
        </label>
      </div>
      {msg && <p className="muted" style={{ wordBreak: "break-word" }}>{msg}</p>}

      <h3>Actifs ({assets.length})</h3>
      {assets.length === 0 ? <p className="muted">Aucun SBOM reçu. Sur un hôte : <code>syft scan dir:/ -o cyclonedx-json &gt; hote.cdx.json</code> puis « Déposer un SBOM » (les agents le feront d'eux-mêmes à la prochaine tranche).</p> : (
        <table>
          <thead><tr><th>Actif</th><th>Type</th><th>Exposé</th><th>Composants</th><th>P1</th><th>P2</th><th>P3</th><th>P4</th><th>KEV</th><th>Dernier SBOM</th></tr></thead>
          <tbody>{assets.map((a) => (
            <tr key={a.name} style={{ cursor: "pointer", fontWeight: asset === a.name ? 700 : undefined }} onClick={() => setAsset(asset === a.name ? "" : a.name)}>
              <td>{a.name}{a.last_scan_error && <span style={{ color: "var(--danger)" }} title={a.last_scan_error}> ⚠ analyse en échec</span>}</td>
              <td>{a.kind}</td>
              <td><input type="checkbox" checked={a.exposed} onClick={(e) => e.stopPropagation()} onChange={() => toggleExposed(a)} /></td>
              <td>{a.components}</td><td>{a.p1 || ""}</td><td>{a.p2 || ""}</td><td>{a.p3 || ""}</td><td>{a.p4 || ""}</td><td>{a.kev || ""}</td>
              <td className="muted">{when(a.last_sbom_at)}</td>
            </tr>
          ))}</tbody>
        </table>
      )}

      <h3>Vulnérabilités {asset ? `de ${asset}` : ""}
        <select value={prio} onChange={(e) => setPrio(e.target.value)} style={{ marginLeft: 8 }}>
          <option value="P1">P1 seulement</option><option value="P1,P2">P1 et P2</option><option value="P1,P2,P3">P1 à P3</option><option value="">toutes</option>
        </select>
      </h3>
      {findings.length === 0 ? <p className="muted">Rien à ce niveau de priorité.</p> : (
        <table>
          <thead><tr><th>Priorité</th><th>Actif</th><th>Paquet</th><th>CVE / avis</th><th>CVSS</th><th>EPSS</th><th>Correction</th><th>Pourquoi</th></tr></thead>
          <tbody>{findings.map((f, i) => (
            <tr key={i}>
              <td><span className={`np-tone ${PRIO_TONE[f.priority]}`}>{f.priority}</span>{f.kev && <strong> KEV</strong>}</td>
              <td>{f.asset}</td>
              <td>{f.package} <span className="muted">{f.version} ({f.ecosystem})</span></td>
              <td>{(f.cves.length ? f.cves : f.ids).slice(0, 3).join(" ")}{f.summary && <div className="muted" style={{ fontSize: 12 }}>{f.summary}</div>}</td>
              <td>{f.score ?? "—"}</td>
              <td>{f.epss ? `${(f.epss * 100).toFixed(1)} %` : "—"}</td>
              <td>{f.fixed.length ? f.fixed.slice(0, 2).join(", ") : <span className="muted">aucune</span>}</td>
              <td className="muted" style={{ fontSize: 12 }}>{f.reason}</td>
            </tr>
          ))}</tbody>
        </table>
      )}
      <p className="muted" style={{ fontSize: 12 }}>P1 : exploitée activement (catalogue KEV) ou EPSS ≥ 50 % sur un actif exposé · P2 : EPSS ≥ 10 % (ou centile ≥ 95) ou critique sur un actif exposé · P3 : grave (CVSS ≥ 7) ou EPSS ≥ 1 % · P4 : le reste. Cocher « Exposé » re-priorise l'actif.</p>
    </div>
  );
}
