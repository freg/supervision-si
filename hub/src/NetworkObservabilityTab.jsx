// Observabilité réseau (livraison #643) : onglet de la tuile « Agents hôtes »
// regroupant, sur toute la flotte (filtrable par site), les deux sondes
// d'observation réseau natives —
//   · dns-observe (item 105) : divergences de résolution DNS entre segments,
//     résolveur ≠ passerelle, réponses changées, résolution partielle ;
//   · resource-access (item 106) : qui (client) accède à quoi (ressource
//     externe dst:port/proto), volumes, accès en clair.
// Vue centrée sur les constats (tri gravité) pour repérer d'un coup d'œil les
// anomalies, avec le détail « qui résout/atteint quoi » en dessous. Sert aussi
// bien sous le hub que sur le front autonome d'un site (même SiAgentView).
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchNetworkObservability } from "./siAgentClient.js";

function Tone({ tone, children, title }) { return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>; }
const toneOfState = (s) => (s === "critical" ? "bad" : s === "warning" ? "warn" : s === "ok" ? "good" : "neutral");
const toneOfSev = (s) => (s === "critical" ? "bad" : s === "warning" ? "warn" : s === "info" ? "neutral" : "neutral");
const SEV_ORDER = { critical: 0, warning: 1, info: 2 };
const SEV_LABEL = { critical: "critique", warning: "à surveiller", info: "info" };

function humanBytes(n) {
  if (!n || n < 1024) return `${n || 0} o`;
  const u = ["Ko", "Mo", "Go", "To"];
  let v = n / 1024, i = 0;
  while (v >= 1024 && i < u.length - 1) { v /= 1024; i += 1; }
  return `${v >= 100 ? Math.round(v) : v.toFixed(1)} ${u[i]}`;
}

// constats de toute la flotte, à plat : {agent, hostname, site, at, code, severity, message}
function flatAlerts(rows) {
  const out = [];
  for (const r of rows || []) {
    for (const a of r.alerts || []) {
      out.push({ agent_id: r.agent_id, hostname: r.hostname || r.agent_id, site: r.site, at: r.at, ...a });
    }
  }
  return out.sort((x, y) => (SEV_ORDER[x.severity] ?? 3) - (SEV_ORDER[y.severity] ?? 3));
}

function AlertsTable({ alerts, when, empty }) {
  if (!alerts.length) return <p className="muted" style={{ margin: "4px 0" }}>{empty}</p>;
  return (
    <div className="hub-table-scroll">
      <table>
        <thead><tr><th>Gravité</th><th>Poste</th><th>Site</th><th>Constat</th><th>Relevé</th></tr></thead>
        <tbody>
          {alerts.map((a, i) => (
            <tr key={`${a.agent_id}-${a.code}-${i}`}>
              <td><Tone tone={toneOfSev(a.severity)} title={a.code}>{SEV_LABEL[a.severity] || a.severity}</Tone></td>
              <td><b>{a.hostname}</b></td>
              <td>{a.site || "—"}</td>
              <td>{a.message}</td>
              <td className="muted">{when(a.at)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// DNS : « qui résout quoi, et vers quoi » à partir de learned (par poste, par nom)
function DnsResolutionDetail({ rows, when }) {
  const [open, setOpen] = useState(false);
  const withData = (rows || []).filter((r) => Object.keys(r.learned || {}).length);
  if (!withData.length) return null;
  return (
    <>
      <button type="button" className="secondary" style={{ marginTop: 8 }} onClick={() => setOpen(!open)}>
        {open ? "Masquer" : "Voir"} le détail des résolutions ({withData.length} poste{withData.length > 1 ? "s" : ""})
      </button>
      {open && withData.map((r) => (
        <div key={r.agent_id} className="hub-table-scroll" style={{ marginTop: 8 }}>
          <div className="muted" style={{ fontSize: 12, marginBottom: 2 }}><b>{r.hostname || r.agent_id}</b> · {r.site || "—"} · relevé {when(r.at)} · interfaces {(r.ifaces || []).join(", ") || "?"}</div>
          <table>
            <thead><tr><th>Nom</th><th>Réponse</th><th>Source → résolveur</th></tr></thead>
            <tbody>
              {Object.entries(r.learned).map(([name, e]) => {
                const answers = Object.entries(e.answers || {});
                const fails = e.fail || [];
                const rows2 = [];
                answers.forEach(([ips, srcs], j) => rows2.push(
                  <tr key={`${name}-a${j}`}>
                    {j === 0 && <td rowSpan={answers.length + (fails.length ? 1 : 0)}><b>{name}</b></td>}
                    <td><Tone tone={answers.length > 1 ? "warn" : "good"}>{ips}</Tone></td>
                    <td className="muted" style={{ fontSize: 12 }}>{(srcs || []).join(", ")}</td>
                  </tr>
                ));
                if (fails.length) rows2.push(
                  <tr key={`${name}-fail`}>
                    {answers.length === 0 && <td><b>{name}</b></td>}
                    <td><Tone tone="bad">échec</Tone></td>
                    <td className="muted" style={{ fontSize: 12 }}>{fails.map((f) => `${f.src} (${f.rcode})`).join(", ")}</td>
                  </tr>
                );
                return rows2;
              })}
            </tbody>
          </table>
        </div>
      ))}
    </>
  );
}

// Ressources agrégées sur toute la flotte (fusion par clé dst:port/proto)
function mergeResources(rows) {
  const byKey = new Map();
  for (const r of rows || []) {
    for (const res of r.resources || []) {
      const cur = byKey.get(res.key) || { key: res.key, name: res.name, dst: res.dst, port: res.port, proto: res.proto, clients: new Set(), bytes: 0, flows: 0, seen: new Set() };
      (res.clients || []).forEach((c) => cur.clients.add(c));
      cur.bytes += res.bytes || 0; cur.flows += res.flows || 0;
      cur.seen.add(r.hostname || r.agent_id);
      if (!cur.name && res.name) cur.name = res.name;
      byKey.set(res.key, cur);
    }
  }
  return [...byKey.values()]
    .map((r) => ({ ...r, clients: [...r.clients], seen: [...r.seen] }))
    .sort((a, b) => (b.bytes - a.bytes) || (b.flows - a.flows));
}

export default function NetworkObservabilityTab({ base, fleet, when }) {
  const [data, setData] = useState(null);
  const [site, setSite] = useState("");
  const [err, setErr] = useState(null);
  const load = useCallback(() => fetchNetworkObservability(base, site).then((d) => { setData(d); setErr(null); }).catch((e) => setErr(e.message)), [base, site]);
  useEffect(() => { load(); const t = setInterval(load, 60000); return () => clearInterval(t); }, [load]);
  const sites = [...new Set((fleet || []).map((a) => a.site).filter(Boolean))].sort();

  const dnsAlerts = useMemo(() => flatAlerts(data?.dns), [data]);
  const resAlerts = useMemo(() => flatAlerts(data?.resources), [data]);
  const resources = useMemo(() => mergeResources(data?.resources), [data]);

  if (err) return <p style={{ color: "var(--danger)" }}>{err}</p>;
  if (!data) return <p className="muted">chargement…</p>;

  const dnsRows = data.dns || [];
  const resRows = data.resources || [];
  const worst = (rows) => (rows.some((r) => (r.summary || {}).state === "critical") ? "critical" : rows.some((r) => (r.summary || {}).state === "warning") ? "warning" : rows.length ? "ok" : "neutral");
  const cleartext = resAlerts.filter((a) => a.code === "resource-cleartext").length;

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10, flexWrap: "wrap" }}>
        <select value={site} onChange={(e) => setSite(e.target.value)}><option value="">— tous les sites —</option>{sites.map((s) => <option key={s} value={s}>{s}</option>)}</select>
        <span className="muted">DNS : {dnsRows.length} poste(s) · Ressources : {resRows.length} poste(s)</span>
        <button type="button" className="secondary" onClick={load}>Actualiser</button>
      </div>

      <div className="hub-card lic-card" style={{ marginBottom: 12 }}>
        <h3 style={{ marginTop: 0 }}>Résolution DNS <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· sonde dns-observe · <Tone tone={toneOfState(worst(dnsRows))}>{dnsAlerts.length} constat{dnsAlerts.length > 1 ? "s" : ""}</Tone></span></h3>
        <p className="muted" style={{ marginTop: 0 }}>Compare la résolution des mêmes noms depuis chaque segment/interface et chaque résolveur. Un nom qui résout <b>différemment selon la source</b> = divergence (DNS par VLAN). Le résolveur légitime d'un segment est sa passerelle (firewall <code>.1</code>) — un DNS distribué qui n'est pas la passerelle est signalé.</p>
        <AlertsTable alerts={dnsAlerts} when={when} empty="Aucune divergence : les noms résolvent de façon cohérente sur tous les segments observés. Affecter la sonde dns-observe (Catalogue de sondes) pour couvrir plus de postes." />
        <DnsResolutionDetail rows={dnsRows} when={when} />
      </div>

      <div className="hub-card lic-card">
        <h3 style={{ marginTop: 0 }}>Accès aux ressources <span className="muted" style={{ textTransform: "none", letterSpacing: 0 }}>· sonde resource-access · <Tone tone={cleartext ? "warn" : resources.length ? "good" : "neutral"}>{resources.length} ressource{resources.length > 1 ? "s" : ""}</Tone>{cleartext > 0 && <> · {cleartext} en clair</>}</span></h3>
        <p className="muted" style={{ marginTop: 0 }}>Qui (client du LAN) accède à quoi (ressource externe <code>dst:port/proto</code>), d'après la table conntrack. Vue réseau seulement sur une passerelle ou un port miroir ; sur un simple poste, ce sont les flux de ce poste.</p>
        <AlertsTable alerts={resAlerts} when={when} empty="Aucun constat. Affecter la sonde resource-access sur une passerelle/relais (ou un poste) pour voir les accès." />
        {resources.length > 0 && (
          <>
            <h4 style={{ margin: "12px 0 4px" }}>Principales ressources externes</h4>
            <div className="hub-table-scroll">
              <table>
                <thead><tr><th>Ressource</th><th>Port/proto</th><th>Clients</th><th>Flux</th><th>Volume</th><th>Vue par</th></tr></thead>
                <tbody>
                  {resources.slice(0, 40).map((r) => (
                    <tr key={r.key}>
                      <td><b>{r.name || r.dst}</b>{r.name && <span className="muted"> · {r.dst}</span>}</td>
                      <td><Tone tone={[80, 21, 23, 110, 143, 8080].includes(r.port) ? "warn" : "neutral"}>{r.port}/{r.proto}</Tone></td>
                      <td title={r.clients.join(", ")}>{r.clients.length}</td>
                      <td>{r.flows}</td>
                      <td>{humanBytes(r.bytes)}</td>
                      <td className="muted" title={r.seen.join(", ")}>{r.seen.length} poste{r.seen.length > 1 ? "s" : ""}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
