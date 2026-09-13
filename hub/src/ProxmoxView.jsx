import React, { useCallback, useEffect, useState } from "react";
import { fetchProxmox } from "./siAgentClient.js";

// Tuile « Proxmox » (livraison #488) : vue dédiée des hyperviseurs
// remontés par le plugin si-agent « proxmox » (#487) -- arbre hôte →
// VM/CT, stockages, pools ZFS, et services/URLs APPRIS par exploration
// (balayage TCP borné, certificats, PTR, redirections). Lecture seule :
// la commande des VM n'est pas encore de cette livraison.
// Données : GET /proxmox du central si-agent (même base que la tuile
// « Agents hôtes »).

const REFRESH_MS = 60000;

function Tone({ tone, children }) {
  return <span className={`np-tone ${tone || "neutral"}`}>{children}</span>;
}

function fmtBytes(n) {
  n = Number(n || 0);
  if (!n) return "—";
  for (const u of ["o", "Ko", "Mo", "Go", "To"]) { if (n < 1024) return `${n.toFixed(n < 10 ? 1 : 0)} ${u}`; n /= 1024; }
  return `${n.toFixed(1)} Po`;
}

function fmtAge(seconds) {
  if (seconds == null) return "—";
  const s = Number(seconds);
  if (s < 3600) return `${Math.max(1, Math.round(s / 60))} min`;
  if (s < 86400) return `${Math.round(s / 3600)} h`;
  return `${Math.round(s / 86400)} j`;
}

function fmtUptime(seconds) {
  if (seconds == null) return "—";
  const d = Math.floor(seconds / 86400);
  return d > 0 ? `${d} j` : fmtAge(seconds);
}

function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR");
}

function vmTone(vm) {
  if (vm.status !== "running") return "neutral";
  if (!vm.last_backup || (vm.last_backup.age_s ?? 0) > 7 * 86400) return "warning";
  if ((vm.snapshots || []).some((s) => s.age_s != null && s.age_s > 30 * 86400)) return "warning";
  return "ok";
}

function certTone(days) {
  if (days == null) return "neutral";
  if (days < 0) return "critical";
  if (days < 14) return "warning";
  return "ok";
}

function VmDetail({ vm }) {
  const services = vm.services || [];
  const urls = vm.urls || [];
  return (
    <div style={{ padding: "6px 8px" }}>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        <div style={{ minWidth: 320, flex: 1 }}>
          <h4 style={{ margin: "4px 0" }}>Services appris ({services.length})</h4>
          {services.length === 0 ? <p className="muted">Aucun port courant ouvert (ou VM sans IP connue).</p> : (
            <table>
              <thead><tr><th>Port</th><th>Service</th><th>Détail</th></tr></thead>
              <tbody>{services.map((s) => (
                <tr key={s.port}>
                  <td><code>{s.port}</code></td>
                  <td>{s.service}</td>
                  <td style={{ fontSize: 12 }}>
                    {s.tls && <>🔒 {s.tls.cn || "?"}{s.tls.self_signed ? " (auto-signé)" : ""} — <Tone tone={certTone(s.tls.days_left)}>{s.tls.days_left == null ? "?" : s.tls.days_left < 0 ? `expiré depuis ${-s.tls.days_left} j` : `${s.tls.days_left} j`}</Tone></>}
                    {s.http && <>{s.tls ? <br /> : null}🌐 HTTP {s.http.status ?? "?"}{s.http.server ? ` · ${s.http.server}` : ""}{s.http.title ? ` · « ${s.http.title} »` : ""}{s.http.redirect_host ? ` → ${s.http.redirect_host}` : ""}</>}
                    {!s.tls && !s.http && <span className="muted">—</span>}
                  </td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
        <div style={{ minWidth: 320, flex: 1 }}>
          <h4 style={{ margin: "4px 0" }}>URLs entrantes apprises ({urls.length})</h4>
          {urls.length === 0 ? <p className="muted">Aucun nom appris (certificat, PTR, redirection).</p> : (
            <table>
              <thead><tr><th>Nom</th><th>Appris via</th><th>Résolution</th></tr></thead>
              <tbody>{urls.map((u) => (
                <tr key={u.host}>
                  <td><code>{u.host}</code></td>
                  <td className="muted" style={{ fontSize: 12 }}>{u.sources.join(", ")}</td>
                  <td style={{ fontSize: 12 }}>
                    {!u.resolves ? <Tone tone="warning">ne résout pas</Tone>
                      : u.matches_vm ? <Tone tone="ok">→ cette VM</Tone>
                      : <Tone tone="neutral">→ {u.ips.join(", ")}</Tone>}
                  </td>
                </tr>
              ))}</tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

function NodeCard({ node, selected, onSelect }) {
  const n = node.node || {};
  const vms = (node.vms || []).filter((v) => !v.template);
  const running = vms.filter((v) => v.status === "running").length;
  return (
    <div className="panel" style={{ marginBottom: 12 }}>
      <h3 style={{ margin: "4px 0 8px" }}>
        🖥 {n.name || node.hostname || node.agent_id}{" "}
        <span className="muted" style={{ fontSize: 12, fontWeight: "normal" }}>
          {n.pveversion || "version ?"} · uptime {fmtUptime(n.uptime_s)}
          {n.cpu != null && <> · CPU {(n.cpu * 100).toFixed(0)} %</>}
          {n.mem_total ? <> · RAM {fmtBytes(n.mem_used)}/{fmtBytes(n.mem_total)}</> : null}
          {" · "}{running}/{vms.length} VM en marche · relevé {when(node.at)}
          {node.site && <> · site {node.site}</>}
        </span>
      </h3>
      {!node.ok && <p><Tone tone="critical">mesure en erreur : {node.error || "?"}</Tone></p>}
      {(node.warnings || []).length > 0 && (
        <p className="muted" style={{ fontSize: 12 }}>⚠️ {node.warnings.join(" · ")}</p>
      )}
      <div className="hub-table-scroll">
        <table>
          <thead><tr><th>VM</th><th>Type</th><th>État</th><th>IP apprises</th><th>CPU/RAM</th><th>Disque</th><th>Snapshots</th><th>Dernier backup</th><th>Services</th></tr></thead>
          <tbody>{vms.map((vm) => {
            const key = `${node.agent_id}/${vm.vmid}`;
            return (
              <React.Fragment key={key}>
                <tr className={`ups-row${selected === key ? " active" : ""}`} onClick={() => onSelect(selected === key ? null : key)}>
                  <td><strong>{vm.name || `vm ${vm.vmid}`}</strong> <span className="muted">#{vm.vmid}</span></td>
                  <td className="muted">{vm.type}</td>
                  <td><Tone tone={vmTone(vm)}>{vm.status === "running" ? "en marche" : vm.status || "?"}</Tone></td>
                  <td style={{ fontSize: 12 }}>{(vm.ips || []).length ? vm.ips.map((a) => <code key={a} style={{ marginRight: 4 }}>{a}</code>) : <span className="muted">—</span>}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{vm.cpu != null ? `${(vm.cpu * 100).toFixed(0)} %` : "—"} · {fmtBytes(vm.mem)}/{fmtBytes(vm.maxmem)}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{fmtBytes(vm.disk)}/{fmtBytes(vm.maxdisk)}</td>
                  <td style={{ fontSize: 12 }}>{(vm.snapshots || []).length ? vm.snapshots.map((s) => <span key={s.name} title={s.description || ""}>📸 {s.name} <span className="muted">({fmtAge(s.age_s)})</span> </span>) : <span className="muted">—</span>}</td>
                  <td style={{ fontSize: 12 }}>{vm.last_backup ? <>il y a {fmtAge(vm.last_backup.age_s)}</> : <Tone tone="warning">jamais</Tone>}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{(vm.services || []).length ? `${vm.services.length} port(s) · ${(vm.urls || []).length} URL` : "—"}</td>
                </tr>
                {selected === key && <tr><td colSpan={9}><VmDetail vm={vm} /></td></tr>}
              </React.Fragment>
            );
          })}</tbody>
        </table>
        {vms.length === 0 && <p className="muted" style={{ padding: 8 }}>Aucune VM remontée.</p>}
      </div>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginTop: 8 }}>
        <div style={{ minWidth: 300, flex: 1 }}>
          <h4 style={{ margin: "4px 0" }}>Stockages</h4>
          <table>
            <thead><tr><th>Nom</th><th>Type</th><th>Usage</th></tr></thead>
            <tbody>{(node.storages || []).map((s) => (
              <tr key={s.storage}><td>{s.storage}</td><td className="muted">{s.type}</td>
                <td style={{ fontSize: 12 }}>{s.total ? <>{fmtBytes(s.used)}/{fmtBytes(s.total)} <span className="muted">({Math.round((s.used / s.total) * 100)} %)</span></> : "—"}</td></tr>
            ))}</tbody>
          </table>
          {(node.storages || []).length === 0 && <p className="muted">Aucun stockage actif remonté.</p>}
        </div>
        <div style={{ minWidth: 300, flex: 1 }}>
          <h4 style={{ margin: "4px 0" }}>Pools ZFS</h4>
          <table>
            <thead><tr><th>Pool</th><th>Santé</th><th>Capacité</th><th>Frag.</th><th>Erreurs</th></tr></thead>
            <tbody>{(node.zfs || []).map((z) => (
              <tr key={z.pool}>
                <td>{z.pool}</td>
                <td><Tone tone={z.health === "ONLINE" ? "ok" : "critical"}>{z.health || z.state || "?"}</Tone></td>
                <td style={{ fontSize: 12 }}>{z.cap_pct != null ? <Tone tone={z.cap_pct >= 90 ? "critical" : z.cap_pct >= 80 ? "warning" : "ok"}>{z.cap_pct} %</Tone> : "—"} <span className="muted">({fmtBytes(z.alloc)}/{fmtBytes(z.size)})</span></td>
                <td className="muted" style={{ fontSize: 12 }}>{z.frag_pct != null ? `${z.frag_pct} %` : "—"}</td>
                <td className="muted" style={{ fontSize: 12 }}>{z.errors || "—"}</td>
              </tr>
            ))}</tbody>
          </table>
          {(node.zfs || []).length === 0 && <p className="muted">Pas de ZFS sur cet hôte (ou zpool absent).</p>}
        </div>
      </div>
    </div>
  );
}

export default function ProxmoxView({ onBack, siAgentApiBase }) {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  const load = useCallback(async () => {
    const data = await fetchProxmox(siAgentApiBase);
    setNodes(data);
    setError(null);
    setLoading(false);
  }, [siAgentApiBase]);

  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  return (
    <div className="view-proxmox">
      <div className="panel" style={{ marginBottom: 12 }}>
        <button className="secondary" onClick={onBack}>← Retour</button>{" "}
        <strong>Hyperviseurs Proxmox</strong>{" "}
        <span className="muted" style={{ fontSize: 12 }}>
          — remontés par le plugin si-agent « proxmox » (VM, snapshots, backups, stockages, ZFS, services et URLs appris par exploration)
        </span>
      </div>
      {error && <p><Tone tone="critical">{error}</Tone></p>}
      {loading ? <p className="muted">Chargement…</p>
        : nodes.length === 0 ? (
          <div className="panel"><p className="muted">
            Aucun hyperviseur ne remonte. Installer si-agent sur chaque Proxmox puis activer le plugin
            (<code>--enable-plugin proxmox</code> ou catalogue central) — premier relevé sous 30 min.
          </p></div>
        ) : nodes.map((n) => <NodeCard key={n.agent_id} node={n} selected={selected} onSelect={setSelected} />)}
    </div>
  );
}
