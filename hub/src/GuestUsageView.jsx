// Écran « Activité des VM » (livraison #769) : récapitulatif des CT / VM de tous les Proxmox (locaux et OVH) --
// dernier accès et fréquentation HTTP/HTTPS (dont ownCloud), activité MySQL, connexions unix, charge processeur --
// et fiche de paramétrage par CT / VM (comptes unix, compte MySQL, URL HTTPS / ownCloud, IP à ignorer, entrée du
// coffre-fort ; JAMAIS de mot de passe). Données : si-agent-api /infra/guests (sonde guest-usage). Logique pure :
// guestUsageLib.js.
// #771 : activité réelle DANS LE TEMPS (historique accumulé par le central, un an et plus) -- jours actifs par mois,
// « inactif réel depuis », classe ; décision par VM et suivi de migration ; export CSV de la liste pour les décideurs.
import { useEffect, useMemo, useState } from "react";
import DataStatus from "./DataStatus.jsx";
import JournalLinks from "./JournalLinks.jsx";
import { viewParams, clearViewParams } from "./hubLinks.js";
import { fetchGuestUsage, saveGuestProfile } from "./siAgentClient.js";
import { fmtBytes } from "./infraLib.js";
import {
  ago, webLast, loginLast, mysqlLast, ownLast, lastActivity, idleClass, IDLE, daySeries, sortGuests, filterGuests, counts,
  PROFILE_FIELDS, profileToForm, formToProfile, ipIgnored, fmtPct, fmtCount,
  ACT, SELECTS, actClass, idleSince, monthSeries, totals12, decisionLabel, statusLabel, decisionsCsv, DECISIONS,
} from "./guestUsageLib.js";

const KIND = { http: "HTTP", owncloud: "ownCloud", mysql: "MySQL", login: "login" };
const TONE = { actif: "ok", recent: "", calme: "warning", dormant: "critical", inconnu: "" };
const ACT_TONE = Object.fromEntries(ACT.map(([k, , t]) => [k, t]));

function MonthSpark({ row, now }) {   // #771 : jours d'activité réelle par mois, 13 mois
  const s = monthSeries(row, "active_days", 13, now);
  const tip = s.map(({ month, m }) => `${month} : ${m ? `${m.active_days} j actifs · web ${fmtCount(m.req)} · conn. ${m.logins} · MySQL ${fmtCount(m.mysql_q)}` : "—"}`).join("\n");
  return <span title={tip}><Spark series={s.map((x) => ({ day: x.month, v: x.v }))} title="jours d'activité réelle par mois (13 mois)" /></span>;
}

function Months({ row }) {
  const ms = [...(row.activity?.months || [])].reverse();
  if (!ms.length) return null;
  const a = row.activity;
  return (
    <figure className="infra-card gu-months">
      <figcaption>Activité réelle dans le temps <span className="infra-note">historique depuis {a.first_day || "—"} · {a.coverage_days} j relevés · humains seulement (robots, supervision à part)</span></figcaption>
      <table className="infra-table"><thead><tr><th>mois</th><th>jours actifs</th><th>accès web</th><th>volume</th><th>visiteurs·jours</th><th>robots</th><th>connexions</th><th>MySQL req.</th><th>CPU moy.</th><th>réseau</th></tr></thead><tbody>
        {ms.map((m) => <tr key={m.month}><td>{m.month}</td><td>{m.active_days}</td><td>{fmtCount(m.req)}</td><td>{fmtBytes(m.bytes)}</td><td>{fmtCount(m.visitor_days)}</td><td>{fmtCount(m.bot)}</td><td>{m.logins}</td><td>{fmtCount(m.mysql_q)}</td><td>{fmtPct(m.cpu)}</td><td>{m.net ? fmtBytes(m.net) : "—"}</td></tr>)}
      </tbody></table>
    </figure>
  );
}

function Spark({ series, title }) {
  const max = series.reduce((m, d) => Math.max(m, d.v), 0);
  const w = 4, gap = 1, h = 18;
  return (
    <svg className="gu-spark" width={series.length * (w + gap)} height={h} role="img" aria-label={title}>
      <title>{`${title} : ${series.map((d) => `${d.day.slice(5)} ${d.v}`).join(" · ")}`}</title>
      {series.map((d, i) => {
        const bh = max ? Math.max(d.v ? 2 : 0, Math.round((h * d.v) / max)) : 0;
        return <rect key={d.day} x={i * (w + gap)} y={h - bh} width={w} height={bh} className="gu-spark-bar" />;
      })}
    </svg>
  );
}

function When({ v, now }) {
  if (!v) return <span className="infra-muted">—</span>;
  return <span title={`${v.at}${v.who ? ` · ${v.who}` : ""}`}>{ago(v.at, now)}{v.who && <small className="gu-who">{v.who}</small>}</span>;
}

function Bars({ title, series }) {
  const max = series.reduce((m, d) => Math.max(m, d.v), 0);
  return (
    <figure className="infra-card gu-bars">
      <figcaption>{title} <span className="infra-note">14 j · total {series.reduce((s, d) => s + d.v, 0)}</span></figcaption>
      <div className="gu-bars-grid">{series.map((d) => (
        <div key={d.day} className="gu-bar-col" title={`${d.day} : ${d.v}`}>
          <span className="gu-bar" style={{ height: `${max ? Math.max(d.v ? 3 : 0, (100 * d.v) / max) : 0}%` }} />
          <small>{d.day.slice(8)}</small>
        </div>))}
      </div>
    </figure>
  );
}

function ProfileForm({ row, onSave, saving }) {
  const [form, setForm] = useState(() => profileToForm(row.profile));
  const [err, setErr] = useState(null);
  useEffect(() => { setForm(profileToForm(row.profile)); setErr(null); }, [row.key]);   // eslint-disable-line react-hooks/exhaustive-deps
  const submit = (e) => {
    e.preventDefault();
    const { profile, error } = formToProfile(form);
    if (error) { setErr(error); return; }
    setErr(null);
    onSave(profile).catch((x) => setErr(x.message));
  };
  return (
    <form className="infra-card gu-form" onSubmit={submit}>
      <figcaption>Paramétrage de {row.vmid} {row.name} <span className="infra-note">({row.node})</span></figcaption>
      <p className="infra-muted">Aucun mot de passe ici : le ranger dans le coffre-fort et indiquer le nom de l'entrée. La sonde n'en a pas besoin (root du nœud entre dans le CT ; MySQL par le compte de maintenance Debian).</p>
      {PROFILE_FIELDS.map(([k, label, kind, ph]) => (
        <label key={k} className="gu-field"><span>{label}</span>
          {kind === "text"
            ? <textarea rows={3} value={form[k]} placeholder={ph} onChange={(e) => setForm({ ...form, [k]: e.target.value })} />
            : kind.startsWith("select:")
              ? <select value={form[k]} onChange={(e) => setForm({ ...form, [k]: e.target.value })}><option value="">—</option>{SELECTS[kind.slice(7)].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
              : <input type={kind === "date" ? "date" : "text"} value={form[k]} placeholder={ph} autoComplete="off" onChange={(e) => setForm({ ...form, [k]: e.target.value })} />}
        </label>))}
      {err && <p className="infra-error">{err}</p>}
      <div className="gu-form-actions">
        <button type="submit" disabled={saving}>{saving ? "Enregistrement…" : "Enregistrer"}</button>
        <button type="button" className="secondary" onClick={() => setForm(profileToForm(row.profile))}>Annuler</button>
        {row.profile?._updated_at && <span className="infra-muted">modifiée {ago(row.profile._updated_at)}{row.profile._updated_by ? ` par ${row.profile._updated_by}` : ""}</span>}
      </div>
    </form>
  );
}

function Detail({ row, now, onSave, saving }) {
  const w = row.web, m = row.mysql, l = row.login, ign = row.profile?.ignore_ips || [];
  return (
    <div className="gu-detail">
      <div className="infra-grid">
        <figure className="infra-card">
          <figcaption>{row.vmid} {row.name} <span className="infra-note">{row.type === "qemu" ? "VM" : "CT"} · {row.node} · {row.status}{row.os ? ` · ${row.os}` : ""}</span></figcaption>
          {row.error && <p className="infra-error">{row.error} <JournalLinks agentId={row.agent_id} q="guest-usage" /></p>}
          {row.source === "inventaire" && <p className="infra-muted">Connu de l'inventaire seulement : sonde guest-usage absente pour ce nœud.</p>}
          <table className="infra-table"><tbody>
            <tr><td>Dernière activité</td><td><When v={lastActivity(row)} now={now} /></td></tr>
            <tr><td>Activité réelle</td><td><span className={`infra-status ${ACT_TONE[actClass(row)]}`}>{actClass(row)}</span> {idleSince(row)}{row.profile?.decision && <> · décision : <b>{decisionLabel(row.profile.decision)}</b>{row.profile.migration_status ? ` (${statusLabel(row.profile.migration_status)})` : ""}</>}</td></tr>
            <tr><td>HTTP/HTTPS</td><td>{w ? <>{fmtCount(w.hits24)} req. 24 h · {fmtCount(w.hits7d)} 7 j · <span className="infra-muted">{(w.files || []).join(", ")}</span></> : "aucun journal d'accès"}</td></tr>
            {w?.owncloud && <tr><td>ownCloud</td><td><When v={ownLast(row)} now={now} /> · {fmtCount(w.owncloud.hits7d)} req. 7 j{row.profile?.owncloud_user && ownLast(row)?.who === row.profile.owncloud_user ? " · compte suivi" : ""}</td></tr>}
            <tr><td>MySQL</td><td>{m ? (m.ok ? <>{m.version} · {m.threads_connected} connecté(s) · {fmtCount(m.conn7d)} connexions 7 j{m.window_s ? ` · ${m.conn_since_last ?? "?"} depuis le passage précédent` : " · 1er passage"}</> : <span className="infra-error">{m.error}</span>) : "absent"}</td></tr>
            <tr><td>Connexions unix</td><td>{l?.last ? <>{l.count7d} sur 7 j · dernière <When v={loginLast(row)} now={now} /></> : "aucune dans wtmp"}</td></tr>
            <tr><td>CPU</td><td>{fmtPct(row.cpu?.now)} maintenant · moy. 24 h {fmtPct(row.cpu?.avg24)} · pic {fmtPct(row.cpu?.max24)} · moy. 7 j {fmtPct(row.cpu?.avg7d)}{row.cpu?.ncpu ? ` · ${row.cpu.ncpu} vCPU` : ""}</td></tr>
            {row.net24?.in != null && <tr><td>Réseau 24 h</td><td>↓ {fmtBytes(row.net24.in)} · ↑ {fmtBytes(row.net24.out)}</td></tr>}
          </tbody></table>
        </figure>
        <Months row={row} />
        {w && <Bars title="Requêtes HTTP/HTTPS par jour" series={daySeries(w.per_day, "hits", 14, now)} />}
        {m?.ok && <Bars title="Connexions MySQL par jour" series={daySeries(m.per_day, "connections", 14, now)} />}
        {l?.per_day?.length > 0 && <Bars title="Connexions unix par jour" series={daySeries(l.per_day, "logins", 14, now)} />}
        {w?.ips?.length > 0 && (
          <figure className="infra-card"><figcaption>Clients HTTP <span className="infra-note">les plus actifs</span></figcaption>
            <table className="infra-table"><thead><tr><th>IP</th><th>req.</th><th>dernier accès</th></tr></thead><tbody>
              {w.ips.slice(0, 15).map((i) => <tr key={i.ip} className={ipIgnored(i.ip, ign) ? "gu-ignored" : ""}><td>{i.ip}{ipIgnored(i.ip, ign) ? " (ignorée)" : ""}</td><td>{fmtCount(i.hits)}</td><td>{ago(i.last_at, now)}</td></tr>)}
            </tbody></table></figure>)}
        {(l?.users?.length > 0 || m?.users_seen?.length > 0 || m?.sessions?.length > 0) && (
          <figure className="infra-card"><figcaption>Comptes</figcaption>
            <table className="infra-table"><thead><tr><th>compte</th><th>source</th><th>dernier</th></tr></thead><tbody>
              {(l?.users || []).slice(0, 10).map((u) => <tr key={`u${u.user}`} className={(row.profile?.unix_accounts || []).includes(u.user) ? "gu-watched" : ""}><td>{u.user}</td><td>unix{u.from ? ` · ${u.from}` : ""} · {u.count7d} sur 7 j</td><td>{ago(u.last_at, now)}</td></tr>)}
              {(m?.users_seen || []).slice(0, 10).map((u) => <tr key={`m${u.user}`} className={row.profile?.mysql_user === u.user ? "gu-watched" : ""}><td>{u.user}</td><td>MySQL (vu en session)</td><td>{ago(u.last_seen, now)}</td></tr>)}
            </tbody></table></figure>)}
        <ProfileForm row={row} onSave={onSave} saving={saving} />
      </div>
    </div>
  );
}

export default function GuestUsageView({ onBack, siAgentApiBase, username }) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState(null);
  const [at, setAt] = useState(null);
  const [initial] = useState(() => viewParams());   // lien depuis la tuile Proxmox : ?view=guest-usage&q=<vmid>&node=<nœud>
  const [filter, setFilter] = useState({ node: initial.node || "", q: initial.q || "", idle: "", running: false, act: "", decision: "" });
  const [sort, setSort] = useState({ col: "node", dir: 1 });
  const [sel, setSel] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    let stop = false;
    const load = () => fetchGuestUsage(siAgentApiBase).then((d) => { if (!stop) { setData(d); setErr(d?.error || null); setAt(new Date()); } }).catch((e) => !stop && setErr(e.message));
    load();
    const id = setInterval(load, 60000);
    return () => { stop = true; clearInterval(id); };
  }, [siAgentApiBase]);

  const now = at ? at.getTime() : Date.now();
  const all = data?.rows || [];
  const rows = useMemo(() => sortGuests(filterGuests(all, filter, now), sort.col, sort.dir), [all, filter, sort, now]);
  const c = useMemo(() => counts(all, now), [all, now]);
  const nodes = useMemo(() => [...new Set(all.map((r) => r.node))].sort(), [all]);
  const selected = all.find((r) => r.key === sel) || null;
  useEffect(() => {   // un seul CT / VM désigné par le lien : sa fiche s'ouvre
    if (!initial.q || !all.length) return;
    const hit = all.filter((r) => String(r.vmid) === initial.q && (!initial.node || r.node === initial.node));
    if (hit.length === 1) setSel(hit[0].key);
    clearViewParams();
  }, [all.length]);   // eslint-disable-line react-hooks/exhaustive-deps

  const save = async (profile) => {
    setSaving(true);
    try {
      const r = await saveGuestProfile(siAgentApiBase, selected.node, selected.vmid, profile, username);
      if (r?.error) throw new Error(r.error);
      setData((d) => ({ ...d, rows: d.rows.map((x) => (x.key === selected.key ? { ...x, profile: { ...(r.profile || profile), _updated_at: new Date().toISOString(), _updated_by: username } } : x)) }));
    } finally { setSaving(false); }
  };

  const exportCsv = () => {   // #771 : liste pour les décideurs (lignes affichées, moins actives d'abord)
    const url = URL.createObjectURL(new Blob([decisionsCsv(rows)], { type: "text/csv;charset=utf-8" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = `activite-vm-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  const actCount = (k) => all.filter((r) => actClass(r) === k).length;
  const decided = all.filter((r) => r.profile?.decision).length;

  const th = (col, label, title) => <th title={title} onClick={() => setSort({ col, dir: sort.col === col ? -sort.dir : (col === "node" || col === "name" ? 1 : -1) })} className={sort.col === col ? "sorted" : ""}>{label}{sort.col === col ? (sort.dir < 0 ? " ▼" : " ▲") : ""}</th>;

  return (
    <div className="infra-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Activité des VM</h2>
        <select value={filter.node} onChange={(e) => setFilter({ ...filter, node: e.target.value })} aria-label="nœud"><option value="">tous les nœuds</option>{nodes.map((n) => <option key={n} value={n}>{n}</option>)}</select>
        <select value={filter.idle} onChange={(e) => setFilter({ ...filter, idle: e.target.value })} aria-label="activité">
          <option value="">toute activité</option>{IDLE.map(([k, l]) => <option key={k} value={k}>{k} ({l})</option>)}<option value="inconnu">non relevé</option>
        </select>
        <select value={filter.act} onChange={(e) => setFilter({ ...filter, act: e.target.value })} aria-label="activité réelle">
          <option value="">activité réelle : toutes</option>{ACT.map(([k, l]) => <option key={k} value={k}>{k} ({l})</option>)}
        </select>
        <select value={filter.decision} onChange={(e) => setFilter({ ...filter, decision: e.target.value })} aria-label="décision">
          <option value="">toutes décisions</option><option value="aucune">sans décision</option>{DECISIONS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
        <button className="secondary" onClick={exportCsv} disabled={!rows.length} title="lignes affichées, les moins actives d'abord (CSV pour tableur)">Liste décideurs (CSV)</button>
        <label className="infra-muted"><input type="checkbox" checked={filter.running} onChange={(e) => setFilter({ ...filter, running: e.target.checked })} /> démarrés</label>
        <input type="search" placeholder="vmid, nom, rôle, URL…" value={filter.q} onChange={(e) => setFilter({ ...filter, q: e.target.value })} />
        <span className="infra-muted">{at ? `mis à jour ${at.toLocaleTimeString("fr-FR")}` : "lecture…"}</span>
      </div>
      {err && <p className="infra-error">{err}</p>}
      <DataStatus base={siAgentApiBase} tasks={["plugin:guest-usage"]} error={err} refreshKey={now} />
      {(data?.errors || []).map((e) => <p key={`${e.node}${e.agent_id}`} className="infra-error">{e.node} : {e.error} <JournalLinks agentId={e.agent_id} name={e.agent} q="guest-usage" /></p>)}
      {data && !all.length && <p className="infra-muted">Aucun invité : activer la sonde <code>guest-usage</code> sur l'agent qui joint les Proxmox (nœud local + /etc/si-agent/pve-remote.json), fiche de l'agent › Sondes.</p>}
      {data && all.length > 0 && (
        <div className="infra-kpis">
          <div className="infra-kpi"><span>CT / VM</span><b>{c.total}</b><small>{c.collected} relevés</small></div>
          <div className="infra-kpi"><span>avec site web</span><b>{c.web}</b></div>
          <div className="infra-kpi"><span>avec MySQL</span><b>{c.mysql}</b></div>
          <div className={`infra-kpi ${c.dormant ? "warning" : ""}`}><span>démarrés sans activité depuis 30 j</span><b>{c.dormant}</b></div>
          <div className="infra-kpi"><span>non relevés</span><b>{c.unknown}</b><small>arrêtés, sans agent invité, nœud sans sonde</small></div>
          <div className={`infra-kpi ${actCount("inactif") ? "critical" : ""}`}><span>inactifs réels (&gt; 180 j)</span><b>{actCount("inactif")}</b><small>{actCount("dormant")} dormants (31-180 j)</small></div>
          <div className="infra-kpi"><span>décisions prises</span><b>{decided} / {c.total}</b></div>
        </div>)}
      <div className="infra-table-wrap infra-scroll">
        <table className="infra-table gu-table">
          <thead><tr>
            {th("node", "Nœud")}{th("name", "CT / VM")}{th("activity", "Dernière activité", "toutes sources, IP ignorées et comptes suivis de la fiche appliqués")}
            {th("http", "HTTP/HTTPS", "dernier accès · requêtes 24 h / 7 j · 14 derniers jours")}{th("mysql", "MySQL", "dernière activité · connexions 7 j")}
            {th("login", "Login", "dernière connexion unix (last)")}{th("cpu", "CPU", "moyenne 24 h · pic 24 h · moyenne 7 j")}
            {th("months", "13 mois", "jours d'activité réelle par mois (web humain, connexions, MySQL)")}{th("idle", "Inactif réel", "classe et date de la dernière activité réelle, sur tout l'historique relevé")}
            {th("decision", "Décision", "décision et état de la migration (fiche ⚙)")}<th />
          </tr></thead>
          <tbody>
            {rows.map((r) => {
              const a = lastActivity(r), k = idleClass(r, now), w = r.web, m = r.mysql;
              return (
                <tr key={r.key} className={sel === r.key ? "gu-sel" : ""} onClick={() => setSel(sel === r.key ? null : r.key)}>
                  <td>{r.node}</td>
                  <td><b>{r.vmid}</b> {r.name} <small className="infra-muted">{r.type === "qemu" ? "VM" : "CT"}{r.status !== "running" ? ` · ${r.status}` : ""}</small>{r.profile?.role && <small className="gu-who">{r.profile.role}</small>}</td>
                  <td><span className={`infra-status ${TONE[k]}`} title={IDLE.find(([x]) => x === k)?.[1] || "aucune donnée"}>{k}</span> {a ? <span title={a.at}>{ago(a.at, now)} <small className="infra-muted">{KIND[a.kind]}</small></span> : null}</td>
                  <td>{w ? <><When v={webLast(r)} now={now} /> <small className="infra-muted">{fmtCount(w.hits24)} / {fmtCount(w.hits7d)}</small> <Spark series={daySeries(w.per_day, "hits", 14, now)} title="requêtes par jour" />{w.owncloud && <small className="gu-who">ownCloud {ago(w.owncloud.last_at, now)}</small>}</> : <span className="infra-muted">—</span>}</td>
                  <td>{m ? (m.ok ? <><When v={mysqlLast(r)} now={now} /> <small className="infra-muted">{fmtCount(m.conn7d)} conn. 7 j · {m.threads_connected}</small></> : <span className="infra-status warning" title={m.error}>illisible</span>) : <span className="infra-muted">—</span>}</td>
                  <td><When v={loginLast(r)} now={now} /></td>
                  <td>{r.cpu?.avg24 != null ? <span title={`maintenant ${fmtPct(r.cpu.now)}`}>{fmtPct(r.cpu.avg24)} <small className="infra-muted">pic {fmtPct(r.cpu.max24)} · 7 j {fmtPct(r.cpu.avg7d)}</small></span> : <span className="infra-muted">{fmtPct(r.cpu?.now)}</span>}</td>
                  <td><MonthSpark row={r} now={now} /> <small className="infra-muted">{totals12(r, now).active_days} j</small></td>
                  <td><span className={`infra-status ${ACT_TONE[actClass(r)]}`} title={ACT.find(([x]) => x === actClass(r))?.[1]}>{actClass(r)}</span> <small className="infra-muted">{idleSince(r)}</small></td>
                  <td>{r.profile?.decision ? <span title={r.profile.decision_reason || ""}>{decisionLabel(r.profile.decision)}{r.profile.migration_status && <small className="gu-who">{statusLabel(r.profile.migration_status)}{r.profile.planned_for ? ` · ${r.profile.planned_for}` : ""}</small>}</span> : <span className="infra-muted">—</span>}</td>
                  <td><button className="secondary gu-gear" title="Paramétrage de la VM" onClick={(e) => { e.stopPropagation(); setSel(r.key); }}>⚙</button></td>
                </tr>);
            })}
            {data && all.length > 0 && !rows.length && <tr><td colSpan={11} className="infra-muted">Aucun CT / VM pour ces filtres.</td></tr>}
          </tbody>
        </table>
      </div>
      {selected && <Detail row={selected} now={now} onSave={save} saving={saving} />}
    </div>
  );
}
