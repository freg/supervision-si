import React, { useCallback, useEffect, useState } from "react";
import { fetchProxmox, fetchProxmoxHistory } from "./siAgentClient.js";
import { backupSummary, backupRunTone, accessSummary, guestLogsSummary, availabilityOf, nodeBackupSummary, nodeAccessSummary, hostHealthSummary } from "./proxmoxLib.js";

// Tuile « Proxmox » (livraison #488) : vue dédiée des hyperviseurs
// remontés par le plugin si-agent « proxmox » (#487) -- arbre hôte →
// VM/CT, stockages, pools ZFS, et services/URLs APPRIS par exploration
// (balayage TCP borné, certificats, PTR, redirections). #504 :
// disponibilité des VM (échantillons du central), suivi des sauvegardes
// (tâches vzdump, jobs), accès (consoles/API par VM, SSH et échecs
// d'authentification de l'hyperviseur), journaux internes des VM (SSH,
// web) remontés par l'agent invité. Lecture seule : la commande des VM
// n'est pas encore de cette livraison.
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

function whenEpoch(sec) {
  if (!sec) return "—";
  return new Date(sec * 1000).toLocaleString("fr-FR");
}

function VmFollowUp({ vm, history }) {
  const [showRaw, setShowRaw] = useState(null);
  const b = backupSummary(vm);
  const a = accessSummary(vm);
  const g = guestLogsSummary(vm);
  const av = availabilityOf(history, vm.vmid);
  return (
    <div style={{ display: "flex", gap: 16, flexWrap: "wrap", marginBottom: 10 }}>
      <div style={{ minWidth: 260, flex: 1 }}>
        <h4 style={{ margin: "4px 0" }}>Disponibilité (7 j)</h4>
        <p style={{ margin: "2px 0" }}><Tone tone={av.tone}>{av.text}</Tone> <span className="muted" style={{ fontSize: 12 }}>sur {av.samples} relevé{av.samples > 1 ? "s" : ""}</span></p>
        {av.transitions.length > 0 ? (
          <ul style={{ margin: "4px 0", paddingLeft: 18, fontSize: 12 }}>
            {av.transitions.slice(-8).reverse().map((t, i) => <li key={i}><span className="muted">{when(t.at)}</span> {t.from} → <strong>{t.to}</strong></li>)}
          </ul>
        ) : <p className="muted" style={{ fontSize: 12 }}>Aucun changement d'état sur la fenêtre.</p>}
      </div>
      <div style={{ minWidth: 300, flex: 1 }}>
        <h4 style={{ margin: "4px 0" }}>Sauvegardes {b.jobs.length > 0 && <span className="muted" style={{ fontSize: 12, fontWeight: "normal" }}>· jobs {b.jobs.join(", ")}</span>}</h4>
        {b.neverRun ? <p className="muted" style={{ fontSize: 12 }}>Aucune tâche vzdump récente pour cette VM{vm.last_backup ? ` (dernier fichier il y a ${fmtAge(vm.last_backup.age_s)})` : ""}.</p> : (
          <table>
            <thead><tr><th>Quand</th><th>Résultat</th><th>Durée</th><th>Par</th></tr></thead>
            <tbody>{b.runs.map((r) => (
              <tr key={r.upid}><td style={{ fontSize: 12 }}>{whenEpoch(r.at)}</td><td><Tone tone={backupRunTone(r)}>{r.status}</Tone></td>
                <td className="muted" style={{ fontSize: 12 }}>{r.duration_s == null ? "—" : fmtAge(r.duration_s)}</td><td className="muted" style={{ fontSize: 12 }}>{r.user || "—"}</td></tr>
            ))}</tbody>
          </table>
        )}
        {b.failStreak >= 2 && <p><Tone tone="critical">{b.failStreak} échecs consécutifs</Tone></p>}
      </div>
      <div style={{ minWidth: 300, flex: 1 }}>
        <h4 style={{ margin: "4px 0" }}>Accès via l'hyperviseur (24 h)</h4>
        <p style={{ margin: "2px 0" }}><Tone tone={a.tone}>{a.text}</Tone>{a.lastConsoleAt && <span className="muted" style={{ fontSize: 12 }}> · dernière console {whenEpoch(a.lastConsoleAt)}</span>}</p>
        {a.users.length > 0 && <p className="muted" style={{ fontSize: 12, margin: "2px 0" }}>utilisateurs : {a.users.join(", ")}</p>}
        {a.ips.length > 0 && <p className="muted" style={{ fontSize: 12, margin: "2px 0" }}>depuis : {a.ips.join(", ")}</p>}
      </div>
      <div style={{ minWidth: 320, flex: 1 }}>
        <h4 style={{ margin: "4px 0" }}>Journaux internes {g && <span className="muted" style={{ fontSize: 12, fontWeight: "normal" }}>· relevés {whenEpoch(g.collectedAt)}</span>}</h4>
        {!g ? <p className="muted" style={{ fontSize: 12 }}>{vm.status !== "running" ? "VM arrêtée." : vm.type === "qemu" && !vm.agent ? "qemu-guest-agent absent ou désactivé : pas de lecture interne possible." : "Pas encore relevés (tourniquet de 15 VM par passage)."}</p> : (
          <>
            {g.ssh ? (
              <p style={{ margin: "2px 0", fontSize: 12 }}>SSH : <Tone tone={g.ssh.tone}>{g.ssh.accepted} accepté{g.ssh.accepted > 1 ? "s" : ""} · {g.ssh.failed} refusé{g.ssh.failed > 1 ? "s" : ""}{g.ssh.invalid ? ` · ${g.ssh.invalid} utilisateurs inconnus` : ""}</Tone>
                {g.ssh.lastAccepted && <span className="muted"> · dernier : {g.ssh.lastAccepted}</span>}
                {g.ssh.failedByIp.length > 0 && <span className="muted"> · refus : {g.ssh.failedByIp.join(", ")}</span>}
              </p>
            ) : <p className="muted" style={{ fontSize: 12 }}>SSH : journal non lu{g.errors.length ? ` (${g.errors.join(" ; ")})` : ""}.</p>}
            {g.web ? (
              <p style={{ margin: "2px 0", fontSize: 12 }}>Web : <Tone tone={g.web.tone}>{g.web.hits} requête{g.web.hits > 1 ? "s" : ""}</Tone>
                <span className="muted"> · {Object.entries(g.web.status).map(([k, v]) => `${k} ${v}`).join(" · ")}</span>
                {g.web.topIps.length > 0 && <span className="muted"> · clients : {g.web.topIps.join(", ")}</span>}
              </p>
            ) : <p className="muted" style={{ fontSize: 12 }}>Web : aucun journal d'accès nginx/apache trouvé.</p>}
            <p style={{ margin: "4px 0", fontSize: 12 }}>
              {["ssh", "web"].filter((k) => g.raw[k]).map((k) => (
                <button key={k} className="secondary" style={{ marginRight: 6 }} onClick={() => setShowRaw(showRaw === k ? null : k)}>{showRaw === k ? "Masquer" : "Voir"} l'extrait {k}</button>
              ))}
            </p>
            {showRaw && g.raw[showRaw] && <pre style={{ maxHeight: 260, overflow: "auto", fontSize: 11, whiteSpace: "pre-wrap" }}>{g.raw[showRaw]}</pre>}
          </>
        )}
      </div>
    </div>
  );
}

function VmDetail({ vm, history }) {
  const services = vm.services || [];
  const urls = vm.urls || [];
  return (
    <div style={{ padding: "6px 8px" }}>
      <VmFollowUp vm={vm} history={history} />
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

function NodeCard({ node, selected, onSelect, history }) {
  const n = node.node || {};
  const vms = (node.vms || []).filter((v) => !v.template);
  const running = vms.filter((v) => v.status === "running").length;
  const nb = nodeBackupSummary(node);
  const na = nodeAccessSummary(node);
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
      {(nb || na) && (
        <p style={{ fontSize: 12, margin: "0 0 8px" }}>
          {nb && <>Sauvegardes 24 h : <Tone tone={nb.tone}>{nb.ok24} OK · {nb.failed24} en échec</Tone> <span className="muted">· {nb.enabledJobs}/{nb.jobs.length} job(s) actif(s)</span>{" "}</>}
          {na && <>· Accès hyperviseur 24 h : <Tone tone={na.tone}>{na.requests} requêtes · {na.authFailures} échec(s) d'authentification · SSH {na.sshAccepted} accepté(s) / {na.sshFailed} refusé(s)</Tone>
            {na.users.length > 0 && <span className="muted"> · {na.users.slice(0, 4).join(", ")}</span>}
            {na.sshLast && <span className="muted"> · dernier SSH : {na.sshLast}</span>}</>}
        </p>
      )}
      <div className="hub-table-scroll">
        <table>
          <thead><tr><th>VM</th><th>Type</th><th>État</th><th>Dispo. 7 j</th><th>IP apprises</th><th>CPU/RAM</th><th>Disque</th><th>Snapshots</th><th>Sauvegarde</th><th>Accès 24 h</th><th>Services</th></tr></thead>
          <tbody>{vms.map((vm) => {
            const key = `${node.agent_id}/${vm.vmid}`;
            return (
              <React.Fragment key={key}>
                <tr className={`ups-row${selected === key ? " active" : ""}`} onClick={() => onSelect(selected === key ? null : key)}>
                  <td><strong>{vm.name || `vm ${vm.vmid}`}</strong> <span className="muted">#{vm.vmid}</span></td>
                  <td className="muted">{vm.type}</td>
                  <td><Tone tone={vmTone(vm)}>{vm.status === "running" ? "en marche" : vm.status || "?"}</Tone></td>
                  <td style={{ fontSize: 12 }}>{(() => { const av = availabilityOf(history, vm.vmid); return <Tone tone={av.tone}>{av.text}</Tone>; })()}</td>
                  <td style={{ fontSize: 12 }}>{(vm.ips || []).length ? vm.ips.map((a) => <code key={a} style={{ marginRight: 4 }}>{a}</code>) : <span className="muted">—</span>}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{vm.cpu != null ? `${(vm.cpu * 100).toFixed(0)} %` : "—"} · {fmtBytes(vm.mem)}/{fmtBytes(vm.maxmem)}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{fmtBytes(vm.disk)}/{fmtBytes(vm.maxdisk)}</td>
                  <td style={{ fontSize: 12 }}>{(vm.snapshots || []).length ? vm.snapshots.map((s) => <span key={s.name} title={s.description || ""}>📸 {s.name} <span className="muted">({fmtAge(s.age_s)})</span> </span>) : <span className="muted">—</span>}</td>
                  <td style={{ fontSize: 12 }}>{(() => { const b = backupSummary(vm); return (
                    <>{vm.last_backup ? <>il y a {fmtAge(vm.last_backup.age_s)}</> : <Tone tone="warning">jamais</Tone>}
                      {b.last && <> <Tone tone={backupRunTone(b.last)} title={`dernière tâche vzdump : ${b.last.status}`}>{b.last.ok === true ? "✓" : b.last.ok === false ? "✗" : "…"}</Tone></>}
                      {b.failStreak >= 2 && <> <Tone tone="critical">{b.failStreak}×</Tone></>}</>); })()}</td>
                  <td style={{ fontSize: 12 }}>{(() => { const a = accessSummary(vm); return <Tone tone={a.tone}>{a.text}</Tone>; })()}</td>
                  <td className="muted" style={{ fontSize: 12 }}>{(vm.services || []).length ? `${vm.services.length} port(s) · ${(vm.urls || []).length} URL` : "—"}</td>
                </tr>
                {selected === key && <tr><td colSpan={11}><VmDetail vm={vm} history={history} /></td></tr>}
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
      <HostHealth node={node} vms={vms} />
    </div>
  );
}

// #519 : santé de l'hyperviseur -- ce qui étouffe l'hôte (IO par disque et par
// VM, swap, ARC, pools) et les réglages à examiner ; l'agent ne change rien.
function HostHealth({ node, vms }) {
  const h = hostHealthSummary(node);
  if (!h) return null;
  const nameOf = (vmid) => { const v = vms.find((x) => x.vmid === vmid); return v ? `${vmid} ${v.name}` : String(vmid); };
  return (
    <div style={{ marginTop: 10 }}>
      <h4 style={{ margin: "4px 0" }}>Santé de l'hyperviseur <Tone tone={h.tone}>{h.tone === "ok" ? "rien à signaler" : `${h.alerts.length} alerte${h.alerts.length > 1 ? "s" : ""}`}</Tone></h4>
      {h.alerts.length > 0 && (
        <ul style={{ margin: "4px 0 8px 18px", padding: 0, fontSize: 13 }}>
          {h.alerts.map((a, i) => <li key={i}><Tone tone={a.severity === "info" ? "neutral" : a.severity}>{a.severity}</Tone> {a.message}</li>)}
        </ul>
      )}
      <p className="muted" style={{ fontSize: 12, margin: "4px 0" }}>
        {h.memory && <>RAM {fmtBytes(h.memory.total)} · disponible {fmtBytes(h.memory.available)} · swap <Tone tone={h.memory.tone}>{fmtBytes(h.memory.swapUsed)}</Tone>{h.memory.swapTotal ? ` / ${fmtBytes(h.memory.swapTotal)}` : ""}</>}
        {h.arc && <> · ARC ZFS {fmtBytes(h.arc.size)}{h.arc.max ? ` / ${fmtBytes(h.arc.max)}` : ""}{h.arc.hitPct != null ? ` (hit ${h.arc.hitPct} %)` : ""}</>}
        {h.intervalS && <> · IO mesurées sur {h.intervalS} s</>}
      </p>
      <div style={{ display: "flex", gap: 16, flexWrap: "wrap" }}>
        {h.pools.length > 0 && (
          <div style={{ minWidth: 260 }}>
            <table>
              <thead><tr><th>Pool</th><th>IO/s (lect./écr.)</th><th>Débit (lect./écr.)</th></tr></thead>
              <tbody>{h.pools.map((p) => (
                <tr key={p.pool}><td>{p.pool} <Tone tone={p.tone}>{p.capPct != null ? `${p.capPct} %` : p.state || "?"}</Tone></td>
                  <td style={{ fontSize: 12 }}>{p.io ? `${p.io.r_ops.toFixed(0)} / ${p.io.w_ops.toFixed(0)}` : "—"}</td>
                  <td style={{ fontSize: 12 }}>{p.io ? `${fmtBytes(p.io.r_bps)}/s / ${fmtBytes(p.io.w_bps)}/s` : "—"}</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {h.disks.length > 0 && (
          <div style={{ minWidth: 340, flex: 1 }}>
            <table>
              <thead><tr><th>Disque</th><th>Occup.</th><th>Attente</th><th>Lect.</th><th>Écr.</th><th>VM</th></tr></thead>
              <tbody>{h.disks.slice(0, 8).map((d) => (
                <tr key={d.dev}>
                  <td>{d.dev}{d.dataset ? <span className="muted" style={{ fontSize: 11 }}> {d.dataset.split("/").pop()}</span> : null}</td>
                  <td><Tone tone={d.tone}>{d.util_pct} %</Tone></td>
                  <td style={{ fontSize: 12 }}>{d.await_ms} ms</td>
                  <td style={{ fontSize: 12 }}>{d.rkb_s} Kio/s</td>
                  <td style={{ fontSize: 12 }}>{d.wkb_s} Kio/s</td>
                  <td style={{ fontSize: 12 }}>{d.vmid != null ? nameOf(d.vmid) : ""}</td>
                </tr>
              ))}</tbody>
            </table>
          </div>
        )}
        {h.topVms.length > 0 && (
          <div style={{ minWidth: 220 }}>
            <table>
              <thead><tr><th>VM la plus active</th><th>Lect.</th><th>Écr.</th></tr></thead>
              <tbody>{h.topVms.map((t) => (
                <tr key={t.vmid}><td>{nameOf(t.vmid)}</td><td style={{ fontSize: 12 }}>{t.rkb_s} Kio/s</td><td style={{ fontSize: 12 }}>{t.wkb_s} Kio/s</td></tr>
              ))}</tbody>
            </table>
          </div>
        )}
      </div>
      {h.recommendations.length > 0 && (
        <details style={{ marginTop: 6 }}>
          <summary className="muted" style={{ fontSize: 12, cursor: "pointer" }}>Réglages à examiner ({h.recommendations.length}) -- jamais appliqués par l'agent</summary>
          <ul style={{ margin: "4px 0 0 18px", padding: 0, fontSize: 12 }}>{h.recommendations.map((r, i) => <li key={i}>{r}</li>)}</ul>
        </details>
      )}
    </div>
  );
}

export default function ProxmoxView({ onBack, siAgentApiBase }) {
  const [nodes, setNodes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);
  const [histories, setHistories] = useState({});

  const load = useCallback(async () => {
    const data = await fetchProxmox(siAgentApiBase);
    setNodes(data);
    setError(null);
    setLoading(false);
    // #504 : disponibilité 7 j par hyperviseur, jamais bloquante
    const next = {};
    await Promise.all(data.map(async (n) => {
      try { next[n.agent_id] = await fetchProxmoxHistory(siAgentApiBase, n.agent_id, 168); } catch { next[n.agent_id] = null; }
    }));
    setHistories(next);
  }, [siAgentApiBase]);

  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  return (
    <div className="view-proxmox">
      <div className="panel" style={{ marginBottom: 12 }}>
        <button className="secondary" onClick={onBack}>← Retour</button>{" "}
        <strong>Hyperviseurs Proxmox</strong>{" "}
        <span className="muted" style={{ fontSize: 12 }}>
          — remontés par le plugin si-agent « proxmox » (VM, disponibilité, snapshots, sauvegardes, accès, journaux internes, stockages, ZFS, services et URLs appris)
        </span>
      </div>
      {error && <p><Tone tone="critical">{error}</Tone></p>}
      {loading ? <p className="muted">Chargement…</p>
        : nodes.length === 0 ? (
          <div className="panel"><p className="muted">
            Aucun hyperviseur ne remonte. Installer si-agent sur chaque Proxmox puis activer le plugin
            (<code>--enable-plugin proxmox</code> ou catalogue central) — premier relevé sous 30 min.
          </p></div>
        ) : nodes.map((n) => <NodeCard key={n.agent_id} node={n} selected={selected} onSelect={setSelected} history={histories[n.agent_id]} />)}
    </div>
  );
}
