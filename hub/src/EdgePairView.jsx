// Tuile « Proxys d'entrée » (livraison #776) : couple de proxys interchangeables (deux VM chez l'hébergeur, sur deux
// nœuds différents) qui renvoient des noms HTTPS (SNI) ou des ports publics vers des serveurs internes. Redirection
// dynamique (serveur interne candidat), application aux deux proxys, contrôle automatique du DNS (serveurs faisant
// autorité et résolveurs publics) et alerte « DNS à configurer » avec le serveur DNS à modifier et l'enregistrement exact.
// Données : si-agent-api /edge (commande `edge` des agents 0.5.74). Logique pure : edgePairLib.js.
import { useCallback, useEffect, useState } from "react";
import { fetchEdge, fetchEdgePreview, saveEdgeProxy, saveEdgeRoute, deleteEdge, switchEdge, saveEdgeSettings, applyEdge, checkEdgeDns } from "./siAgentClient.js";
import { dnsLabel, dnsTone, alerts, routeLabel, reachState, independent, emptyRoute, routeToForm, formToRoute } from "./edgePairLib.js";

function Copy({ text }) {
  const [ok, setOk] = useState(false);
  return <button className="secondary mig-small" onClick={() => navigator.clipboard?.writeText(text).then(() => { setOk(true); setTimeout(() => setOk(false), 1500); })}>{ok ? "copié ✓" : "Copier"}</button>;
}

function DnsDetail({ d }) {
  if (!d) return null;
  return (
    <div>
      <p>{d.message}</p>
      {d.records?.length > 0 && d.state === "a_configurer" && <><p>Enregistrement(s) à poser dans la zone <b>{d.zone}</b> :</p><pre className="mig-cmd">{d.records.join("\n")}</pre><Copy text={d.records.join("\n")} /></>}
      <table className="infra-table"><thead><tr><th>serveur</th><th>rôle</th><th>réponse</th><th>cache</th></tr></thead><tbody>
        {(d.ns || []).map((n) => <tr key={n.name}><td>{n.name} <small className="infra-muted">{n.ip}</small></td><td>autorité</td><td className={n.ok ? "" : "infra-error"}>{n.error || (n.cname ? `CNAME ${n.cname} → ` : "") + (n.addresses || []).join(", ") || "rien"}</td><td>{n.ttl ?? ""}</td></tr>)}
        {(d.public || []).map((p) => <tr key={p.server}><td>{p.server}</td><td>résolveur public</td><td className={p.ok ? "" : "infra-muted"}>{p.error || (p.addresses || []).join(", ") || "rien"}</td><td>{p.ttl ?? ""}</td></tr>)}
      </tbody></table>
    </div>
  );
}

function Problem({ pb, onApply, busy }) {
  const s = pb.solution || {};
  return (
    <div className="mig-error">
      <b>⚠ {pb.title}</b><p>{pb.detail}</p>
      <div>Solution : {s.label}{s.where && s.where !== "hub" && <> · sur <b>{s.where}</b></>}
        {s.kind === "apply" && <> <button disabled={busy} onClick={onApply}>Appliquer aux deux proxys</button></>}
        {s.command && <><pre className="mig-cmd">{s.command}</pre><Copy text={s.command} /></>}</div>
    </div>
  );
}

function RouteForm({ initial, onSave, onCancel }) {
  const [f, setF] = useState(routeToForm(initial));
  const [err, setErr] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <div className="infra-card">
      <div className="mig-vars">
        <label><span>identifiant</span><input value={f.id} onChange={set("id")} placeholder="glpi" /></label>
        <label><span>type</span><select value={f.mode} onChange={set("mode")}><option value="sni">nom HTTPS (443 + 80)</option><option value="tcp">port public → port interne</option></select></label>
        <label><span>{f.mode === "sni" ? "nom public" : "nom (facultatif)"}</span><input value={f.name} onChange={set("name")} placeholder="www.example.org" /></label>
        {f.mode === "tcp" && <label><span>port public</span><input value={f.front_port} onChange={set("front_port")} /></label>}
        <label><span>serveur interne actif (hôte:port)</span><input value={f.backend} onChange={set("backend")} placeholder="192.0.2.10:443" /></label>
        <label><span>autres serveurs candidats</span><input value={f.candidates} onChange={set("candidates")} placeholder="192.0.2.20:443" /></label>
        <label><span>adresse réelle du client (PROXY)</span><input type="checkbox" checked={!!f.send_proxy} onChange={set("send_proxy")} /></label>
        <label><span>active</span><input type="checkbox" checked={!!f.enabled} onChange={set("enabled")} /></label>
      </div>
      {f.send_proxy && <p className="infra-note">Le serveur interne doit accepter l'en-tête PROXY (Apache : <code>RemoteIPProxyProtocol On</code>), sinon il refusera les connexions.</p>}
      <button onClick={async () => { const r = await onSave(formToRoute(f)); setErr(r?.error || null); }}>Enregistrer et appliquer</button> <button className="secondary" onClick={onCancel}>Annuler</button>{err && <span className="infra-error"> {err}</span>}
    </div>
  );
}

function ProxyForm({ initial, agents, onSave, onCancel }) {
  const [f, setF] = useState({ id: "", label: "", agent: "", public_ip: "", node: "", enabled: true, ...initial });
  const [err, setErr] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  return (
    <div className="infra-card mig-vars">
      <label><span>identifiant</span><input value={f.id} onChange={set("id")} placeholder="proxy-a" /></label>
      <label><span>libellé</span><input value={f.label} onChange={set("label")} /></label>
      <label><span>agent de la VM</span><select value={f.agent} onChange={set("agent")}><option value="">— choisir —</option>{agents.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.name}</option>)}</select></label>
      <label><span>IP publique</span><input value={f.public_ip} onChange={set("public_ip")} /></label>
      <label><span>nœud Proxmox qui porte la VM</span><input value={f.node} onChange={set("node")} /></label>
      <label><span>actif</span><input type="checkbox" checked={!!f.enabled} onChange={set("enabled")} /></label>
      <div><button onClick={async () => { const r = await onSave(f); setErr(r?.error || r?.proxy?.warning || null); }}>Enregistrer</button> <button className="secondary" onClick={onCancel}>Annuler</button>{err && <span className="infra-error"> {err}</span>}</div>
    </div>
  );
}

export default function EdgePairView({ onBack, siAgentApiBase: api, username }) {
  const [v, setV] = useState(null);
  const [err, setErr] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [editR, setEditR] = useState(null);
  const [editP, setEditP] = useState(null);
  const [openDns, setOpenDns] = useState(null);
  const [preview, setPreview] = useState(null);

  const load = useCallback(() => fetchEdge(api).then((d) => { setV(d); setErr(d?.error || null); }), [api]);
  useEffect(() => { load(); const id = setInterval(load, 20000); return () => clearInterval(id); }, [load]);
  const act = async (fn) => { setBusy(true); try { const r = await fn(); setMsg(r?.error ? { ok: false, text: r.error } : r?.message ? { ok: true, text: r.message } : null); await load(); return r; } finally { setBusy(false); } };
  const apply = () => act(() => applyEdge(api, username));
  const st = v?.settings || {};
  const al = alerts(v);

  return (
    <div className="infra-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Proxys d'entrée</h2>
        <button disabled={busy || !v?.proxies?.length} onClick={apply}>Appliquer aux deux proxys</button>
        <button className="secondary" disabled={busy || !v?.routes?.length} onClick={() => act(() => checkEdgeDns(api))}>Vérifier le DNS maintenant</button>
        <button className="secondary" onClick={async () => setPreview(preview ? null : await fetchEdgePreview(api))}>{preview ? "Masquer" : "Voir"} la configuration HAProxy</button>
        {msg && <span className={msg.ok ? "infra-muted" : "infra-error"}>{msg.text}</span>}
      </div>
      {err && <p className="infra-error">{err}</p>}
      {preview && <pre className="mig-log">{preview.error || preview.config}</pre>}
      {v && (
        <>
          {al.map((a, i) => (a.kind === "dns"
            ? <div key={i} className="mig-error"><b>⚠ {a.title}</b><DnsDetail d={a.data} /></div>
            : <Problem key={i} pb={a.problem} onApply={apply} busy={busy} />))}
          <div className="infra-card">
            <b>Le couple</b> <span className="infra-muted">· DNS attendu : {(v.expected_ips || []).join(" et ") || "—"} ({st.dns_mode === "active" ? "proxy actif seulement" : "les deux proxys"})</span>
            {!independent(v.proxies) && v.proxies.length === 2 && <p className="infra-error">Les deux proxys sont sur le même nœud : ils ne se secourent plus.</p>}
            <div className="infra-kpis">
              {v.proxies.map((p) => {
                const s = p.state?.status || {};
                return (
                  <div key={p.id} className={`infra-kpi lat-state ${p.problems.length ? "critical" : "ok"}`}>
                    <span>{p.label} · {p.public_ip}{p.node ? ` · ${p.node}` : ""}</span>
                    <b>{s.active ? "HAProxy actif" : p.state ? "HAProxy arrêté" : "sans nouvelles"}</b>
                    <small>{p.identical ? "configuration à jour ✓" : p.state ? "configuration différente" : ""}{p.state_at ? ` · relevé ${new Date(p.state_at * 1000).toLocaleTimeString("fr-FR")}` : ""}</small>
                    {st.dns_mode === "active" && <small>{st.active_proxy === p.id ? "★ proxy actif" : <button className="secondary mig-small" disabled={busy} onClick={() => act(() => saveEdgeSettings(api, { active_proxy: p.id }, username))}>Rendre actif</button>}</small>}
                    <small><button className="secondary mig-small" onClick={() => setEditP(p)}>Modifier</button><button className="secondary mig-small" disabled={busy} onClick={() => act(() => deleteEdge(api, "proxy", p.id, username))}>Retirer</button></small>
                  </div>
                );
              })}
              {v.proxies.length < 2 && <div className="infra-kpi"><button onClick={() => setEditP({})}>+ Déclarer un proxy</button><small>un couple = deux VM sur deux nœuds différents</small></div>}
            </div>
            {editP && <ProxyForm initial={editP} agents={v.agents || []} onCancel={() => setEditP(null)} onSave={(p) => act(async () => { const r = await saveEdgeProxy(api, p, username); if (!r?.error && !r?.proxy?.warning) setEditP(null); return r; })} />}
          </div>
          <div className="infra-card">
            <b>Routes</b> <button className="secondary mig-small" onClick={() => setEditR(emptyRoute())}>+ Ajouter une route</button>
            {editR && <RouteForm initial={editR} onCancel={() => setEditR(null)} onSave={(r) => act(async () => { const x = await saveEdgeRoute(api, r, username); if (!x?.error) setEditR(null); return x; })} />}
            <div className="infra-table-wrap"><table className="infra-table"><thead><tr><th>entrée</th><th>serveur interne</th><th>vu des proxys</th><th>DNS</th><th></th></tr></thead><tbody>
              {v.routes.map((r) => [
                <tr key={r.id} className={r.enabled ? "" : "infra-muted"}>
                  <td><b>{routeLabel(r)}</b>{r.send_proxy && <small className="infra-muted"> · PROXY</small>}</td>
                  <td>{r.candidates.length > 1
                    ? <select value={r.backend} disabled={busy} onChange={(e) => act(() => switchEdge(api, r.id, e.target.value, username))}>{r.candidates.map((c) => <option key={c} value={c}>{c}</option>)}</select>
                    : r.backend}</td>
                  <td className={reachState(r) === "ok" ? "" : "infra-error"}>{Object.entries(r.reach || {}).map(([p, ms]) => `${p} : ${ms == null ? "injoignable" : `${ms} ms`}`).join(" · ") || "—"}</td>
                  <td>{r.name ? <button className={`secondary mig-small infra-status ${dnsTone(r.dns)}`} onClick={() => setOpenDns(openDns === r.id ? null : r.id)}>{dnsLabel(r.dns)}</button> : "—"}</td>
                  <td><button className="secondary mig-small" onClick={() => setEditR(r)}>Modifier</button><button className="secondary mig-small" disabled={busy} onClick={() => act(() => deleteEdge(api, "route", r.id, username))}>Supprimer</button></td>
                </tr>,
                openDns === r.id && <tr key={`${r.id}-dns`}><td colSpan={5}><DnsDetail d={r.dns?.data} /></td></tr>,
              ])}
            </tbody></table></div>
          </div>
          <details className="infra-card"><summary>Réglages</summary>
            <div className="mig-vars">
              <label><span>DNS des noms</span><select value={st.dns_mode} disabled={busy} onChange={(e) => act(() => saveEdgeSettings(api, { dns_mode: e.target.value }, username))}>
                <option value="both">vers les deux proxys (répartition, secours par le client)</option><option value="active">vers le proxy actif seulement</option></select></label>
              <label><span>contrôle DNS toutes les (min)</span><input type="number" defaultValue={st.check_minutes} onBlur={(e) => act(() => saveEdgeSettings(api, { check_minutes: Number(e.target.value) }, username))} /></label>
              <label><span>durée de cache conseillée (TTL, s)</span><input type="number" defaultValue={st.ttl} onBlur={(e) => act(() => saveEdgeSettings(api, { ttl: Number(e.target.value) }, username))} /></label>
              <label><span>résolveurs publics contrôlés</span><input defaultValue={(st.resolvers || []).join(", ")} onBlur={(e) => act(() => saveEdgeSettings(api, { resolvers: e.target.value }, username))} /></label>
            </div>
          </details>
          <details className="infra-card"><summary>Journal</summary>
            <table className="infra-table"><tbody>{(v.log || []).map((l, i) => <tr key={i}><td className="infra-muted">{l.at}</td><td>{l.who}</td><td>{l.action}</td><td className="infra-muted">{l.detail}</td></tr>)}</tbody></table>
          </details>
        </>
      )}
    </div>
  );
}
