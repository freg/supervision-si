// Tuile « Notifications » (livraison #590, backlog item 92) -- demandé :
// notifications mail des actions sur les routeurs et de tout ce qui impacte
// le SI ; groupes et méta-groupes ; table action → groupe → emails, groupe
// par défaut généré par module ; gestionnaire d'envoi détaché (engorgement,
// emballement, erreurs, liste noire) réutilisable par d'autres services, y
// compris externes. Onglets : Affectations, Groupes, File & journal,
// Consommateurs & liste noire, Réglages.
import { useCallback, useEffect, useMemo, useState } from "react";
import PageFrame from "./PageFrame.jsx";
import { viewParams } from "./hubLinks.js";
import * as api from "./notifyClient.js";
import { byModule, filterActions, effectiveGroups, parseEmails, queueSummary, groupLabel, STATUS_LABEL, STATUS_TONE, SEVERITY_LABEL } from "./notifyLib.js";

const TABS = [
  { id: "assign", label: "🎯 Affectations" },
  { id: "groups", label: "👥 Groupes" },
  { id: "queue", label: "📬 File & journal" },
  { id: "consumers", label: "🔑 Consommateurs & liste noire" },
  { id: "settings", label: "⚙ Réglages" },
];
const COLORS = { red: "#e53935", orange: "#fb8c00", green: "#43a047", grey: "#9e9e9e" };
const when = (t) => (t ? new Date(t * 1000).toLocaleString() : "");
function Tone({ tone, children }) { return <span style={{ color: COLORS[tone] || "inherit", fontWeight: 600 }}>{children}</span>; }

// ---------------------------------------------------------------------------
function Assignments({ b, t, groups, notice }) {
  const [actions, setActions] = useState([]);
  const [query, setQuery] = useState("");
  const load = useCallback(() => api.fetchActions(b, t).then((r) => !r.error && setActions(r.actions || [])), [b, t]);
  useEffect(() => { load(); }, [load]);
  const shown = useMemo(() => filterActions(actions, query), [actions, query]);
  const gmap = useMemo(() => Object.fromEntries((groups || []).map((g) => [g.id, g])), [groups]);
  const toggle = async (action, gid, on) => {
    const cur = new Set(action.groups || []);
    if (on) cur.add(gid); else cur.delete(gid);
    const r = await api.setActionGroups(b, t, action.id, [...cur]);
    notice(r.error || `${action.id} → ${[...cur].join(", ") || "groupe par défaut"}`, !r.error);
    load();
  };
  const addModuleRule = async (module) => {
    const r = await api.setActionGroups(b, t, `${module}.*`, []);
    notice(r.error || `règle « ${module}.* » créée : cocher ses groupes`, !r.error);
    load();
  };
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Chaque action déclarée par un module (ou vue passer) est rattachée par défaut au groupe automatique de son module (<code>auto:&lt;module&gt;</code>) :
        renseigner ses adresses dans « Groupes » suffit. Cocher des groupes ici remplace ce défaut pour l'action ; une ligne <code>module.*</code> s'applique à tout le module.
        Un groupe <em>méta</em> unit plusieurs groupes.
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <input type="search" placeholder="filtrer (action, module, libellé)" value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 260 }} />
        <span className="muted">{shown.length} / {actions.length} action(s)</span>
      </div>
      {byModule(shown).map(([module, list]) => (
        <div key={module} className="hub-card" style={{ marginBottom: 10 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h3 style={{ margin: 0 }}>{module}</h3>
            <span className="muted">groupe par défaut : {gmap[`auto:${module}`] ? groupLabel(gmap[`auto:${module}`]) : `auto:${module}`}</span>
            <span style={{ flex: 1 }} />
            {!list.some((a) => a.id === `${module}.*`) && <button type="button" className="secondary" onClick={() => addModuleRule(module)}>règle pour tout le module</button>}
          </div>
          <table className="hub-table">
            <thead><tr><th>Action</th><th>Gravité</th><th>Vues</th><th>Effectif</th>{(groups || []).map((g) => <th key={g.id} title={g.id}>{g.name}</th>)}</tr></thead>
            <tbody>
              {list.map((a) => {
                const eff = effectiveGroups(a, actions);
                return (
                  <tr key={a.id}>
                    <td><code>{a.id}</code>{a.label && a.label !== a.id ? <div className="muted">{a.label}</div> : null}</td>
                    <td><Tone tone={a.severity === "critical" ? "red" : a.severity === "warning" ? "orange" : "grey"}>{SEVERITY_LABEL[a.severity] || a.severity}</Tone></td>
                    <td className="muted">{a.count || 0}{a.last_seen ? ` · ${when(a.last_seen)}` : ""}</td>
                    <td className="muted" title={`source : ${eff.source}`}>{eff.groups.map((g) => gmap[g]?.name || g).join(", ")} <small>({eff.source})</small></td>
                    {(groups || []).map((g) => <td key={g.id} style={{ textAlign: "center" }}><input type="checkbox" checked={(a.groups || []).includes(g.id)} onChange={(e) => toggle(a, g.id, e.target.checked)} /></td>)}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      ))}
      {!actions.length && <p className="muted">aucune action déclarée encore : les modules s'enregistrent à leur démarrage (Cisco, MikroTik, tour de contrôle) et toute notification reçue crée son action.</p>}
    </div>
  );
}

// ---------------------------------------------------------------------------
function Groups({ b, t, groups, reload, notice }) {
  const [edit, setEdit] = useState(null);
  const [newName, setNewName] = useState("");
  const [newKind, setNewKind] = useState("group");
  const save = async () => {
    const body = { name: edit.name, emails: parseEmails(edit.emailsText), members: edit.members || [], note: edit.note || "" };
    const r = await api.saveGroup(b, t, edit.id, body);
    notice(r.error || "groupe enregistré", !r.error);
    if (!r.error) { setEdit(null); reload(); }
  };
  const create = async () => {
    const r = await api.createGroup(b, t, { name: newName, kind: newKind });
    notice(r.error || `groupe ${r.id} créé`, !r.error);
    if (!r.error) { setNewName(""); reload(); }
  };
  const remove = async (g) => {
    if (!window.confirm(`Supprimer le groupe « ${g.name} » ?`)) return;
    const r = await api.deleteGroup(b, t, g.id);
    notice(r.error || "groupe supprimé", !r.error);
    reload();
  };
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 10 }}>
        <input placeholder="nouveau groupe" value={newName} onChange={(e) => setNewName(e.target.value)} />
        <select value={newKind} onChange={(e) => setNewKind(e.target.value)}><option value="group">groupe (adresses)</option><option value="meta">méta-groupe (union de groupes)</option></select>
        <button type="button" className="primary" disabled={!newName.trim()} onClick={create}>Créer</button>
      </div>
      <table className="hub-table">
        <thead><tr><th>Groupe</th><th>Type</th><th>Adresses</th><th>Membres</th><th>Adresses effectives</th><th></th></tr></thead>
        <tbody>
          {(groups || []).map((g) => (
            <tr key={g.id}>
              <td><strong>{g.name}</strong><div className="muted"><code>{g.id}</code>{g.auto ? " · défaut du module" : ""}</div>{g.note && <div className="muted">{g.note}</div>}</td>
              <td>{g.kind === "meta" ? "méta" : "groupe"}</td>
              <td>{(g.emails || []).join(", ") || <Tone tone="orange">aucune</Tone>}</td>
              <td className="muted">{(g.members || []).join(", ")}</td>
              <td className="muted">{(g.resolved || []).length}</td>
              <td style={{ whiteSpace: "nowrap" }}>
                <button type="button" className="secondary" onClick={() => setEdit({ ...g, emailsText: (g.emails || []).join("\n") })}>Modifier</button>
                {" "}{!g.auto && <button type="button" className="secondary" onClick={() => remove(g)}>Supprimer</button>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {edit && (
        <div className="hub-card" style={{ marginTop: 12 }}>
          <h3 style={{ marginTop: 0 }}>{edit.id}</h3>
          <div className="hub-settings-row"><label>Nom</label><input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} /></div>
          <div className="hub-settings-row"><label>Adresses (une par ligne, virgules acceptées)</label><textarea rows={4} value={edit.emailsText} onChange={(e) => setEdit({ ...edit, emailsText: e.target.value })} style={{ width: "100%" }} /></div>
          <div className="hub-settings-row"><label>Membres (groupes unis{edit.kind === "meta" ? "" : " — aussi possible pour un groupe simple"})</label>
            <div style={{ columns: 3 }}>{(groups || []).filter((g) => g.id !== edit.id).map((g) => (
              <label key={g.id} style={{ display: "block" }}><input type="checkbox" checked={(edit.members || []).includes(g.id)} onChange={(e) => setEdit({ ...edit, members: e.target.checked ? [...(edit.members || []), g.id] : (edit.members || []).filter((x) => x !== g.id) })} /> {g.name}</label>
            ))}</div>
          </div>
          <div className="hub-settings-row"><label>Note</label><input value={edit.note || ""} onChange={(e) => setEdit({ ...edit, note: e.target.value })} /></div>
          <button type="button" className="primary" onClick={save}>Enregistrer</button> <button type="button" className="secondary" onClick={() => setEdit(null)}>Annuler</button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
function Queue({ b, t, notice }) {
  const [data, setData] = useState(null);
  const [status, setStatus] = useState("");
  const [detail, setDetail] = useState(null);
  const [events, setEvents] = useState([]);
  const load = useCallback(() => { api.fetchQueue(b, t, status).then((r) => !r.error && setData(r)); api.fetchEvents(b, t).then((r) => !r.error && setEvents(r.events || [])); }, [b, t, status]);
  useEffect(() => { load(); const id = setInterval(load, 15000); return () => clearInterval(id); }, [load]);
  const act = async (id, verb) => { const r = await api.queueAct(b, t, id, verb); notice(r.error || `message ${id} : ${verb}`, !r.error); load(); };
  const s = data?.sender || {};
  return (
    <div>
      <div className="hub-card" style={{ marginBottom: 10 }}>
        <strong>Gestionnaire d'envoi</strong> — {queueSummary(data?.counts)} ·
        SMTP {s.smtp ? <Tone tone="green">configuré</Tone> : <Tone tone="red">non configuré (NOTIFY_SMTP_*)</Tone>} ·
        disjoncteur {s.breaker_open ? <Tone tone="red">ouvert ({s.consecutive_failures} échecs : {s.last_error})</Tone> : <Tone tone="green">fermé</Tone>} ·
        {s.sent_last_minute || 0} envoyé(s) cette minute · dernier envoi {s.last_sent ? when(s.last_sent) : "—"}
        {" "}<button type="button" className="secondary" onClick={async () => { const r = await api.releaseHeld(b, t); notice(r.error || `${r.released} message(s) libéré(s)`, !r.error); load(); }}>Libérer les retenus</button>
      </div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8 }}>
        <select value={status} onChange={(e) => setStatus(e.target.value)}><option value="">tous les états</option>{Object.entries(STATUS_LABEL).filter(([k]) => k !== "merged").map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <button type="button" className="secondary" onClick={load}>↻</button>
      </div>
      <table className="hub-table">
        <thead><tr><th>#</th><th>Quand</th><th>Action</th><th>Sujet</th><th>Destinataires</th><th>État</th><th></th></tr></thead>
        <tbody>
          {(data?.queue || []).map((q) => (
            <tr key={q.id}>
              <td className="muted">{q.id}</td><td className="muted" style={{ whiteSpace: "nowrap" }}>{when(q.created_at)}</td>
              <td><code>{q.action}</code><div className="muted">{q.consumer}</div></td>
              <td><a href="#detail" onClick={(e) => { e.preventDefault(); api.fetchQueueItem(b, t, q.id).then(setDetail); }}>{q.subject}</a>{q.merged ? <span className="muted"> (+{q.merged} regroupé(s))</span> : null}</td>
              <td className="muted">{(q.recipients || []).length}</td>
              <td><Tone tone={STATUS_TONE[q.status]}>{STATUS_LABEL[q.status] || q.status}</Tone>{q.reason ? <div className="muted">{q.reason}</div> : null}{q.last_error ? <div className="muted">{q.attempts} tentative(s) : {q.last_error}</div> : null}</td>
              <td style={{ whiteSpace: "nowrap" }}>
                {["failed", "no-recipients", "held", "dropped"].includes(q.status) && <button type="button" className="secondary" onClick={() => act(q.id, "retry")}>Renvoyer</button>}
                {" "}{["queued", "held", "failed", "no-recipients"].includes(q.status) && <button type="button" className="secondary" onClick={() => act(q.id, "drop")}>Abandonner</button>}
              </td>
            </tr>
          ))}
          {!(data?.queue || []).length && <tr><td colSpan={7} className="muted">rien</td></tr>}
        </tbody>
      </table>
      {detail && (
        <div className="hub-card" style={{ marginTop: 12 }}>
          <div style={{ display: "flex", gap: 8 }}><h3 style={{ margin: 0 }}>#{detail.id} — {detail.subject}</h3><span style={{ flex: 1 }} /><button type="button" className="secondary" onClick={() => setDetail(null)}>Fermer</button></div>
          <p className="muted">à : {(detail.recipients || []).join(", ") || "—"}</p>
          <pre style={{ whiteSpace: "pre-wrap", fontSize: 12 }}>{detail.body}</pre>
          {detail.context && Object.keys(detail.context).length > 0 && <pre style={{ fontSize: 12 }}>{JSON.stringify(detail.context, null, 2)}</pre>}
        </div>
      )}
      <h3>Journal du gestionnaire</h3>
      <table className="hub-table"><thead><tr><th>Quand</th><th>Événement</th><th>Détail</th></tr></thead>
        <tbody>{events.map((e, i) => <tr key={i}><td className="muted" style={{ whiteSpace: "nowrap" }}>{when(e.at)}</td><td>{e.event}</td><td>{e.text}</td></tr>)}</tbody></table>
    </div>
  );
}

// ---------------------------------------------------------------------------
function Consumers({ b, t, notice }) {
  const [list, setList] = useState([]);
  const [bl, setBl] = useState([]);
  const [name, setName] = useState("");
  const [tokenShown, setTokenShown] = useState(null);
  const [blNew, setBlNew] = useState({ kind: "email", value: "", reason: "" });
  const load = useCallback(() => { api.fetchConsumers(b, t).then((r) => !r.error && setList(r.consumers || [])); api.fetchBlacklist(b, t).then((r) => !r.error && setBl(r.blacklist || [])); }, [b, t]);
  useEffect(() => { load(); }, [load]);
  const create = async () => {
    const r = await api.createConsumer(b, t, { name });
    if (r.error) { notice(r.error, false); return; }
    setTokenShown(r); setName(""); load();
  };
  const apiUrl = `${window.location.origin}/api/notify/notify`;
  return (
    <div>
      <div className="hub-card" style={{ marginBottom: 10 }}>
        <h3 style={{ marginTop: 0 }}>Services consommateurs</h3>
        <p className="muted">Les modules du hub utilisent le jeton interne (<code>NOTIFY_INTERNAL_TOKEN</code>). Un service <em>externe</em> (GED, script, autre application) reçoit son propre jeton, montré une seule fois, puis appelle
          <code> POST {apiUrl}</code> avec l'en-tête <code>X-Notify-Token</code> et un corps <code>{"{"}"action": "ged.upload", "subject": "…", "body": "…", "context": {"{}"}{"}"}</code>. L'action est créée au premier appel avec son groupe par défaut.</p>
        <div style={{ display: "flex", gap: 8 }}><input placeholder="nom du service (ex. ged-externe)" value={name} onChange={(e) => setName(e.target.value)} /><button type="button" className="primary" disabled={!name.trim()} onClick={create}>Émettre un jeton</button></div>
        {tokenShown && <p><Tone tone="orange">Jeton de « {tokenShown.name} » (copier maintenant, il ne sera plus affiché) :</Tone> <code>{tokenShown.token}</code></p>}
        <table className="hub-table"><thead><tr><th>Service</th><th>Créé</th><th>Dernier appel</th><th></th></tr></thead>
          <tbody>{list.map((c) => <tr key={c.name}><td>{c.name}</td><td className="muted">{when(c.created_at)}</td><td className="muted">{c.last_seen ? when(c.last_seen) : "jamais"}</td>
            <td><button type="button" className="secondary" onClick={async () => { if (window.confirm(`Révoquer le jeton de « ${c.name} » ?`)) { await api.deleteConsumer(b, t, c.name); load(); } }}>Révoquer</button></td></tr>)}
          {!list.length && <tr><td colSpan={4} className="muted">aucun service externe</td></tr>}</tbody></table>
      </div>
      <div className="hub-card">
        <h3 style={{ marginTop: 0 }}>Liste noire</h3>
        <p className="muted">Une adresse ne reçoit plus rien ; une action (ou <code>module.*</code>) n'est plus envoyée ; un consommateur est ignoré. Les messages concernés restent visibles dans la file (« sans destinataire »).</p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <select value={blNew.kind} onChange={(e) => setBlNew({ ...blNew, kind: e.target.value })}><option value="email">adresse</option><option value="action">action</option><option value="consumer">consommateur</option></select>
          <input placeholder="valeur" value={blNew.value} onChange={(e) => setBlNew({ ...blNew, value: e.target.value })} />
          <input placeholder="raison" value={blNew.reason} onChange={(e) => setBlNew({ ...blNew, reason: e.target.value })} />
          <button type="button" className="secondary" disabled={!blNew.value.trim()} onClick={async () => { const r = await api.addBlacklist(b, t, blNew); notice(r.error || "ajouté", !r.error); setBlNew({ ...blNew, value: "", reason: "" }); load(); }}>Ajouter</button>
        </div>
        <table className="hub-table"><thead><tr><th>Type</th><th>Valeur</th><th>Raison</th><th></th></tr></thead>
          <tbody>{bl.map((x) => <tr key={x.kind + x.value}><td>{x.kind}</td><td><code>{x.value}</code></td><td className="muted">{x.reason}</td><td><button type="button" className="secondary" onClick={async () => { await api.delBlacklist(b, t, x.kind, x.value); load(); }}>Retirer</button></td></tr>)}
          {!bl.length && <tr><td colSpan={4} className="muted">vide</td></tr>}</tbody></table>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
function Settings({ b, t, notice }) {
  const [s, setS] = useState(null);
  const [to, setTo] = useState("");
  useEffect(() => { api.fetchSettings(b, t).then((r) => !r.error && setS(r)); }, [b, t]);
  if (!s) return <p className="muted">Chargement…</p>;
  const num = (k, label, help) => (
    <div className="hub-settings-row"><label>{label}</label><input type="number" min={0} value={s[k]} onChange={(e) => setS({ ...s, [k]: Number(e.target.value) })} style={{ width: 90 }} /> <span className="muted">{help}</span></div>
  );
  return (
    <div>
      <div className="hub-card">
        <p className="muted" style={{ marginTop: 0 }}>SMTP : {s.smtp_host ? <><code>{s.smtp_host}</code>, expéditeur <code>{s.smtp_from}</code></> : <Tone tone="red">non configuré — NOTIFY_SMTP_HOST / NOTIFY_SMTP_FROM (ou SECRETS_ALERT_SMTP_*) dans le .env</Tone>} · préfixe des sujets <code>{s.subject_prefix}</code></p>
        <label><input type="checkbox" checked={!!s.enabled} onChange={(e) => setS({ ...s, enabled: e.target.checked })} /> envois actifs (décoché : tout est retenu dans la file, rien n'est perdu)</label>
        {num("max_per_minute", "Débit maximal", "messages par minute (0 = illimité)")}
        {num("coalesce_seconds", "Regroupement", "s : un message identique (action, sujet, destinataires) encore en file est fusionné")}
        {num("burst_threshold", "Seuil d'emballement", "messages d'une même action dans la fenêtre : au-delà, retenus et un résumé unique part (0 = jamais)")}
        {num("burst_window", "Fenêtre d'emballement", "secondes")}
        {num("breaker_failures", "Disjoncteur", "échecs SMTP consécutifs avant pause")}
        {num("breaker_cooldown", "Pause du disjoncteur", "secondes avant nouvel essai")}
        {num("retry_max", "Tentatives", "par message avant abandon (backoff 1, 2, 4… min)")}
        <button type="button" className="primary" onClick={async () => { const r = await api.saveSettings(b, t, s); notice(r.error || "réglages enregistrés", !r.error); if (!r.error) setS({ ...s, ...r }); }}>Enregistrer</button>
      </div>
      <div className="hub-card">
        <h3 style={{ marginTop: 0 }}>Test d'envoi</h3>
        <input placeholder="adresse" value={to} onChange={(e) => setTo(e.target.value)} /> <button type="button" className="secondary" onClick={async () => { const r = await api.testSend(b, t, to); notice(r.error || `envoyé à ${to}`, !r.error); }}>Envoyer un message de test</button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
export default function NotificationsView({ apiBase, accessToken, username, onBack }) {
  const params = useMemo(() => viewParams(), []);
  const [tab, setTab] = useState(TABS.some((x) => x.id === params.tab) ? params.tab : "assign");
  const [groups, setGroups] = useState([]);
  const [notice, setNotice] = useState(null);
  const say = (text, ok = true) => setNotice({ text, ok });
  const reloadGroups = useCallback(() => apiBase && accessToken && api.fetchGroups(apiBase, accessToken).then((r) => !r.error ? setGroups(r.groups || []) : say(r.error, false)), [apiBase, accessToken]);
  useEffect(() => { reloadGroups(); }, [reloadGroups]);
  if (!apiBase) return <PageFrame title="📣 Notifications" onBack={onBack}><p className="muted">notify-api non configurée (<code>VITE_NOTIFY_API_BASE_URL</code>).</p></PageFrame>;
  const b = apiBase, t = accessToken;
  return (
    <PageFrame title="📣 Notifications" onBack={onBack}
      actions={TABS.map((x) => <button key={x.id} type="button" className={`secondary na-section-toggle${tab === x.id ? " active" : ""}`} onClick={() => setTab(x.id)}>{x.label}</button>)}
      foot={<span>action → groupe / méta-groupe → adresses · gestionnaire d'envoi détaché · connecté en tant que {username || "?"}{notice ? <> · <span style={{ color: notice.ok ? COLORS.green : COLORS.red }}>{notice.text}</span></> : null}</span>}>
      {tab === "assign" && <Assignments b={b} t={t} groups={groups} notice={say} />}
      {tab === "groups" && <Groups b={b} t={t} groups={groups} reload={reloadGroups} notice={say} />}
      {tab === "queue" && <Queue b={b} t={t} notice={say} />}
      {tab === "consumers" && <Consumers b={b} t={t} notice={say} />}
      {tab === "settings" && <Settings b={b} t={t} notice={say} />}
    </PageFrame>
  );
}
