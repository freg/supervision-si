// Tuile « Vulnérabilités » (livraison #688) : SBOM (syft) → OSV (osv-scanner)
// → priorisation EPSS + KEV × exposition → (option) Dependency-Track.
// Ce qui est à traiter d'abord est en haut : P1 = exploitée activement (KEV)
// ou très probable sur un actif exposé.
// #693 : analyse du dépôt et rechargement des flux en arrière-plan (suivi par
// /jobs/<id>, plus de coupure 504 du tls-proxy) + « État de l'installation »
// (/diag : outils, stockage, flux, sortie Internet) affiché d'office en cas d'échec.
import { useEffect, useRef, useState } from "react";
import HubIcon from "./HubIcon.jsx";
import { fetchFleet, sendCommand } from "./siAgentClient.js";  // #699

const PRIO_TONE = { P1: "bad", P2: "warn", P3: "neutral", P4: "neutral" };

// Erreurs sans corps JSON = vuln-api jamais atteint : on dit quoi faire.
export function explainHttp(status) {
  if (status === 404) return "HTTP 404 : route /api/vuln/ absente du tls-proxy (le recréer)";
  if (status === 502 || status === 503) return `HTTP ${status} : vuln-api arrêté ou en cours de démarrage (voir ses journaux)`;
  if (status === 504) return "HTTP 504 : vuln-api n'a pas répondu à temps";
  if (status === 401 || status === 403) return `HTTP ${status} : session expirée ou droit manquant`;
  return `HTTP ${status}`;
}

async function call(base, path, opts = {}) {
  if (!base) throw new Error("VITE_VULN_API_BASE_URL absent du hub : reconstruire le hub");
  let r;
  try { r = await fetch(`${base}${path}`, { credentials: "include", ...opts }); }
  catch (e) { throw new Error(`vuln-api injoignable (${e.message})`); }
  const j = await r.json().catch(() => null);
  if (!r.ok) throw new Error(j?.error || explainHttp(r.status));
  if (j === null) throw new Error("réponse non JSON : la route /api/vuln/ mène ailleurs (tls-proxy à recréer)");
  return j;
}

const JOB_LABEL = { "scan-self": "analyse du dépôt", feeds: "flux EPSS/KEV" };
const ok = (b) => (b ? "✓" : "✗");

const when = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "jamais");

export default function VulnView({ onBack, vulnApiBase, siAgentApiBase }) {
  const [summary, setSummary] = useState(null);
  const [assets, setAssets] = useState([]);
  const [findings, setFindings] = useState([]);
  const [asset, setAsset] = useState("");
  const [prio, setPrio] = useState("P1,P2");
  const [busy, setBusy] = useState("");
  const [msg, setMsg] = useState(null);
  const [diag, setDiag] = useState(null);
  const [diagOpen, setDiagOpen] = useState(false);
  const [jobs, setJobs] = useState({});          // kind -> travail en cours
  const timers = useRef({});

  const load = async () => {
    try {
      const [s, a, f] = await Promise.all([
        call(vulnApiBase, "/summary"), call(vulnApiBase, "/assets"),
        call(vulnApiBase, `/findings?limit=500${prio ? `&priority=${prio}` : ""}${asset ? `&asset=${encodeURIComponent(asset)}` : ""}`),
      ]);
      setSummary(s); setAssets(a); setFindings(f);
    } catch (e) { setMsg(e.message); runDiag(); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [prio, asset]);

  const runDiag = async () => {
    setDiagOpen(true); setDiag({ loading: true });
    try { setDiag(await call(vulnApiBase, "/diag")); }
    catch (e) { setDiag({ unreachable: e.message }); }
  };

  const follow = (job) => {
    setJobs((m) => ({ ...m, [job.kind]: job }));
    clearTimeout(timers.current[job.kind]);
    if (job.state !== "running") {
      const label = JOB_LABEL[job.kind] || job.kind;
      setMsg(job.state === "done" ? `${label} : terminé${job.result?.findings !== undefined ? ` — ${job.result.components} composants, ${job.result.findings} vulnérabilité(s)` : ""}${job.result?.scan_error ? ` (osv-scanner : ${job.result.scan_error})` : ""}`
        : `${label} : échec — ${job.error}`);
      if (job.state === "error") runDiag();
      load();
      return;
    }
    timers.current[job.kind] = setTimeout(async () => {
      try { follow(await call(vulnApiBase, `/jobs/${job.id}`)); }
      catch (e) { setJobs((m) => ({ ...m, [job.kind]: undefined })); setMsg(`suivi interrompu : ${e.message}`); }
    }, 3000);
  };
  useEffect(() => {
    call(vulnApiBase, "/jobs").then((list) => list.filter((j) => j.state === "running").forEach(follow)).catch(() => {});
    const t = timers.current;
    return () => Object.values(t).forEach(clearTimeout);
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, []);

  const startJob = async (path) => {
    setMsg(null);
    try { follow(await call(vulnApiBase, path, { method: "POST" })); }
    catch (e) { setMsg(e.message); runDiag(); }
  };

  const act = async (label, path, opts) => {
    setBusy(label); setMsg(null);
    try { const r = await call(vulnApiBase, path, { method: "POST", ...opts }); setMsg(`${label} : ${r.components} composants, ${r.findings} vulnérabilité(s)${r.scan_error ? ` — osv-scanner : ${r.scan_error}` : ""}`); await load(); }
    catch (e) { setMsg(`${label} : ${e.message}`); runDiag(); }
    setBusy("");
  };
  const since = (j) => (j ? ` ${Math.max(0, Math.round(Date.now() / 1000 - j.started))} s` : "");
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
        <button type="button" className="secondary" disabled={!!jobs.feeds} onClick={() => startJob("/feeds/refresh")}>{jobs.feeds ? `⏳ flux…${since(jobs.feeds)}` : "Recharger EPSS et KEV"}</button>
        <button type="button" className="secondary" disabled={!!jobs["scan-self"]} onClick={() => startJob("/scan/self")}>{jobs["scan-self"] ? `⏳ syft + osv-scanner…${since(jobs["scan-self"])}` : "Analyser le dépôt supervision-si"}</button>
        <button type="button" className="secondary" onClick={() => (diagOpen ? setDiagOpen(false) : runDiag())}>{diagOpen ? "Masquer l'état" : "État de l'installation"}</button>
        <label className="secondary" style={{ cursor: "pointer" }}>Déposer un SBOM (CycloneDX JSON)
          <input type="file" accept=".json" style={{ display: "none" }} onChange={(e) => { upload(e.target.files[0]); e.target.value = ""; }} />
        </label>
      </div>
      {(msg || busy) && <p className="muted" style={{ wordBreak: "break-word" }}>{busy ? `⏳ ${busy}… ` : ""}{msg}</p>}
      {diagOpen && <DiagPanel diag={diag} onRefresh={runDiag} />}

      {siAgentApiBase && <AgentInventory base={siAgentApiBase} assets={assets} />}

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

function DiagPanel({ diag, onRefresh }) {
  if (!diag || diag.loading) return <p className="muted">⏳ vérification de l'installation…</p>;
  if (diag.unreachable) return (
    <div className="np-card" style={{ marginBottom: 12 }}>
      <p><span className="np-tone bad">vuln-api injoignable</span> {diag.unreachable}</p>
      <p className="muted" style={{ fontSize: 12 }}>Sur le serveur, depuis la racine du dépôt :<br />
        <code>./scripts/run.sh up -d --build vuln-api && ./scripts/run.sh logs --tail 40 vuln-api</code><br />
        <code>GATEWAY_REALM_ANSWER=marquer ./gateway/scripts/run.sh up -d --force-recreate tls-proxy</code></p>
    </div>
  );
  const row = (label, good, detail) => <tr key={label}><td>{ok(good)}</td><td>{label}</td><td className="muted">{detail}</td></tr>;
  return (
    <div className="np-card" style={{ marginBottom: 12 }}>
      <p><span className={`np-tone ${diag.ok ? "good" : "bad"}`}>{diag.ok ? "installation opérationnelle" : `${diag.problems.length} problème(s)`}</span>{" "}
        <button type="button" className="secondary" onClick={onRefresh}>Revérifier</button></p>
      {diag.problems.length > 0 && <ul>{diag.problems.map((p) => <li key={p}>{p}</li>)}</ul>}
      <table><tbody>
        {Object.entries(diag.tools).map(([n, t]) => row(n, t.ok, t.ok ? t.version : t.error))}
        {row("stockage", diag.storage.writable, diag.storage.writable ? `${diag.storage.path} — ${diag.storage.free_gb} Go libres` : diag.storage.error)}
        {row("dépôt monté (analyse)", diag.self_scan.present, diag.self_scan.path)}
        {["epss", "kev"].map((f) => row(`flux ${f.toUpperCase()}`, !!diag.feeds[f]?.at, diag.feeds[f]?.at ? `chargé le ${when(diag.feeds[f].at)}${diag.feeds[f].error ? ` (dernier essai : ${diag.feeds[f].error})` : ""}` : (diag.feeds[f]?.error || "jamais chargé")))}
        {Object.entries(diag.network).map(([n, v]) => row(`réseau : ${n}`, v.ok, v.status ? `HTTP ${v.status}` : v.error))}
        {row("base", true, `${diag.counts.assets} actif(s), ${diag.counts.findings} vulnérabilité(s), ${diag.counts.epss} scores EPSS, ${diag.counts.kev} KEV`)}
        {row("Dependency-Track", true, diag.dependency_track ? "branché" : "non configuré (option, profil vuln-dt)")}
      </tbody></table>
    </div>
  );
}

// #699 : inventaire logiciel par les agents (syft sur l'hôte -> central -> vuln-api), à la demande ou périodique
function AgentInventory({ base, assets }) {
  const [agents, setAgents] = useState(null);
  const [install, setInstall] = useState(true);
  const [msg, setMsg] = useState({});
  useEffect(() => { fetchFleet(base).then((l) => setAgents(l.filter((a) => a.active !== false))); }, [base]);
  if (!agents) return null;
  const byName = Object.fromEntries(assets.map((a) => [a.name, a]));
  const send = async (a, params, label) => {
    setMsg((m) => ({ ...m, [a.agent_id]: "⏳ envoi…" }));
    const r = await sendCommand(base, a.agent_id, "sbom", params);
    setMsg((m) => ({ ...m, [a.agent_id]: r?.error ? `refusé : ${r.error}` : `${label} : envoyé (pris au prochain contact de l'agent, inventaire en quelques minutes)` }));
  };
  return (
    <details style={{ marginBottom: 12 }}>
      <summary><strong>Inventaire par les agents</strong> <span className="muted">— syft sur chaque hôte, résultat dans « Actifs » au nom de l'hôte</span></summary>
      <p className="muted" style={{ fontSize: 12 }}>Linux pour l'instant. Priorité basse, sans les zones de données (boîtes, disques de VM, journaux).
        <label style={{ marginLeft: 8 }}><input type="checkbox" checked={install} onChange={(e) => setInstall(e.target.checked)} /> installer syft s'il manque (publication officielle, empreinte vérifiée)</label></p>
      <table>
        <thead><tr><th>Agent</th><th>Hôte</th><th>Contact</th><th>Dernier inventaire</th><th>P1 / P2</th><th>Actions</th></tr></thead>
        <tbody>{agents.map((a) => {
          const asset = byName[a.hostname] || byName[a.agent_id];
          return (
            <tr key={a.agent_id}>
              <td>{a.agent_id}</td><td>{a.hostname || "—"}{a.os && <div className="muted" style={{ fontSize: 11 }}>{a.os}</div>}</td>
              <td>{a.online || "—"}</td>
              <td className="muted">{asset ? when(asset.last_sbom_at) : "jamais"}</td>
              <td>{asset ? `${asset.p1 || 0} / ${asset.p2 || 0}` : "—"}</td>
              <td style={{ whiteSpace: "nowrap" }}>
                <button className="secondary" onClick={() => send(a, { now: true, install }, "inventaire")}>Inventaire maintenant</button>{" "}
                <select defaultValue="" onChange={(e) => { if (e.target.value !== "") send(a, { schedule_days: +e.target.value }, e.target.value === "0" ? "relevé périodique arrêté" : `relevé tous les ${e.target.value} j`); e.target.value = ""; }}>
                  <option value="">périodicité…</option><option value="1">chaque jour</option><option value="7">chaque semaine</option><option value="30">chaque mois</option><option value="0">arrêter</option>
                </select>
                {msg[a.agent_id] && <div className="muted" style={{ fontSize: 11 }}>{msg[a.agent_id]}</div>}
              </td>
            </tr>
          );
        })}</tbody>
      </table>
    </details>
  );
}
