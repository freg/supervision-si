// Onglets d'exploitation de la tuile Serveur de messagerie (livraison #752) : Incidents (constats de la sonde, suivi,
// conduite à tenir), File d'attente (domaines distants, motifs, relancer / retenir / libérer / supprimer), Échecs de
// distribution (reports et rebonds par domaine, code DSN, motif, nature), Listes (tables d'accès Postfix, postscreen,
// postgrey, listes DNS : blanche / grise / noire, ajout / retrait), Réglages (Postfix et Amavis, liste fermée).
// Toute modification exige le motif saisi en haut de la page (journalisé sur le serveur avec l'acteur).
import { useEffect, useState } from "react";
import { AutoColumns } from "./TableColumns.jsx";
import { fetchEvents } from "./siAgentClient.js";
import { fmtAge, playbook, incidentsFrom, settingsDiff, flatEntries, LIST_TONE } from "./mailOpsLib.js";

const when = (t) => (t ? new Date(t > 1e12 ? t : t * 1000).toLocaleString("fr-FR") : "—");
const size = (n) => (n == null ? "" : n > 1e6 ? (n / 1e6).toFixed(1) + " Mo" : n > 1e3 ? Math.round(n / 1e3) + " ko" : n + " o");
function Tone({ tone, children }) { return <span className={`np-tone ${tone || "neutral"}`}>{children}</span>; }
const SEV = { critical: "bad", warning: "warn", info: "neutral" };
const needReason = (reason) => { if ((reason || "").trim().length < 4) { window.alert("Motif requis (en haut de la page) : il est journalisé sur le serveur avec votre nom."); return true; } return false; };

function useAction(run) {
  const [busy, setBusy] = useState(false), [err, setErr] = useState(null), [wait, setWait] = useState(0);
  const go = async (params) => { setBusy(true); setErr(null); try { return await run(params, setWait); } catch (e) { setErr(e.message); return null; } finally { setBusy(false); setWait(0); } };
  const status = busy ? <span className="muted">⏳ l'agent traite… {wait ? `${wait} s` : ""}</span> : err ? <span className="np-tone bad">{err}</span> : null;
  return [go, busy, status];
}

export function MailIncidents({ base, agentId, probe, onTab }) {
  const [inc, setInc] = useState(null);
  const [days, setDays] = useState(30);
  useEffect(() => {
    let stop = false;
    const since = new Date(Date.now() - days * 86400000).toISOString();
    Promise.all(["probe-alert", "probe-recovered"].map((kind) => fetchEvents(base, { agent: agentId, kind, since, limit: 1000 })))
      .then(([a, r]) => !stop && setInc(incidentsFrom([...a, ...r]))).catch(() => !stop && setInc({ open: [], closed: [], byCode: [] }));
    return () => { stop = true; };
  }, [base, agentId, days]);
  const alerts = probe?.data?.alerts || [];
  return (
    <div>
      <h3>Constats en cours ({alerts.length})</h3>
      {alerts.length === 0 ? <p className="muted">Aucun constat sur la dernière relève de la sonde mail-server.</p> : (
        <AutoColumns id="MailOps.alerts"><table><thead><tr><th>Gravité</th><th>Constat</th><th>Conduite à tenir</th><th /></tr></thead>
          <tbody>{alerts.map((a) => { const p = playbook(a.code); return (
            <tr key={a.code}><td><Tone tone={SEV[a.severity]}>{a.severity}</Tone></td><td><b>{p.label}</b><div className="muted">{a.message}</div></td><td>{p.todo}</td>
              <td>{p.tab && <button className="secondary" onClick={() => onTab(p.tab)}>Agir →</button>}</td></tr>); })}</tbody></table></AutoColumns>)}
      <div className="pv-inline" style={{ marginTop: 12 }}><h3 style={{ margin: 0 }}>Suivi des incidents</h3>
        <select value={days} onChange={(e) => setDays(Number(e.target.value))}>{[7, 30, 90].map((d) => <option key={d} value={d}>{d} jours</option>)}</select></div>
      {!inc ? <p className="muted">⏳</p> : <>
        <p className="muted">{inc.open.length} ouvert(s), {inc.closed.length} clos sur la période. Un incident s'ouvre quand la sonde relève un constat et se clôt quand il disparaît.</p>
        {inc.byCode.length > 0 && <AutoColumns id="MailOps.bycode"><table><thead><tr><th>Constat</th><th>Occurrences</th><th>Durée cumulée</th></tr></thead>
          <tbody>{inc.byCode.map((c) => <tr key={c.code}><td>{playbook(c.code).label}</td><td>{c.count}</td><td>{fmtAge(c.total_s)}</td></tr>)}</tbody></table></AutoColumns>}
        <AutoColumns id="MailOps.incidents"><table><thead><tr><th>État</th><th>Gravité</th><th>Constat</th><th>Ouvert</th><th>Clos</th><th>Durée</th></tr></thead>
          <tbody>{[...inc.open.map((i) => ({ ...i, st: "ouvert" })), ...inc.closed.map((i) => ({ ...i, st: "clos" }))].map((i, k) => (
            <tr key={k}><td><Tone tone={i.st === "ouvert" ? "bad" : "good"}>{i.st}</Tone></td><td><Tone tone={SEV[i.severity]}>{i.severity}</Tone></td>
              <td>{playbook(i.code).label}<div className="muted">{i.message}</div></td><td>{when(i.opened)}</td><td>{when(i.closed)}</td><td>{fmtAge(i.duration_s)}</td></tr>))}</tbody></table></AutoColumns>
      </>}
    </div>
  );
}

export function MailQueue({ run, reason }) {
  const [res, setRes] = useState(null), [sel, setSel] = useState([]), [dom, setDom] = useState(""), [queue, setQueue] = useState("");
  const [go, busy, status] = useAction(run);
  const load = async (d = dom, q = queue) => { const r = await go({ action: "queue_list", domain: d || undefined, queue: q || undefined }); if (r) { setRes(r); setSel([]); } };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  const act = async (op, ids) => {
    if (needReason(reason)) return;
    const what = { flush: "relancer toute la file maintenant", requeue: "recalculer la route et relancer", hold: "retenir (mise en attente)", release: "libérer de l'attente", deliver: "tenter tout de suite", delete: "SUPPRIMER définitivement" }[op];
    if (!window.confirm(`${what}${ids?.length ? ` : ${ids.length === 1 ? ids[0] : ids.length + " messages"}` : ""} ?`)) return;
    const r = await go({ action: "queue_action", op, ids, reason });
    if (r) { window.alert(`Fait : ${op}${r.output ? " — " + r.output : ""}`); load(); }
  };
  const s = res?.summary;
  return (
    <div>
      <div className="pv-inline"><button className="secondary" onClick={() => load()} disabled={busy}>Actualiser</button>
        <button className="secondary" onClick={() => act("flush")} disabled={busy}>Relancer la file</button>
        <button className="secondary" onClick={() => act("requeue", ["ALL deferred"])} disabled={busy}>Recalculer les routes (tous les reports)</button>{status}</div>
      {s && <>
        <p><b>{s.total}</b> message(s) en file — {Object.entries(s.by_queue).map(([q, n]) => `${q} ${n}`).join(", ") || "vide"} — le plus ancien : {fmtAge(s.oldest_age_s)}</p>
        {s.domains.length > 0 && <><h3>Par domaine distant</h3><AutoColumns id="MailOps.qdom"><table><thead><tr><th>Domaine</th><th>Messages</th><th>Plus ancien</th><th>Motifs</th><th /></tr></thead>
          <tbody>{s.domains.map((d) => <tr key={d.domain}><td>{d.domain}</td><td>{d.messages}</td><td>{fmtAge(d.oldest_age_s)}</td>
            <td>{d.reasons.slice(0, 3).map((r, i) => <div key={i} className="muted">{r.count} × {r.reason}</div>)}</td>
            <td><button className="secondary" onClick={() => { setDom(d.domain); load(d.domain, queue); }}>Voir</button></td></tr>)}</tbody></table></AutoColumns></>}
      </>}
      {res && <>
        <h3>Messages {dom && <>vers <b>{dom}</b> <button className="secondary" onClick={() => { setDom(""); load("", queue); }}>tous</button></>}</h3>
        <div className="pv-inline"><select value={queue} onChange={(e) => { setQueue(e.target.value); load(dom, e.target.value); }}><option value="">toutes les files</option>{["deferred", "active", "hold", "incoming"].map((q) => <option key={q} value={q}>{q}</option>)}</select>
          {sel.length > 0 && <>{sel.length} sélectionné(s) : {["deliver", "requeue", "hold", "release", "delete"].map((op) => <button key={op} className="secondary" onClick={() => act(op, sel)} disabled={busy}>{{ deliver: "Tenter", requeue: "Router", hold: "Retenir", release: "Libérer", delete: "Supprimer" }[op]}</button>)}</>}</div>
        <AutoColumns id="MailOps.queue"><table><thead><tr><th><input type="checkbox" checked={sel.length > 0 && sel.length === res.rows.length} onChange={(e) => setSel(e.target.checked ? res.rows.map((r) => r.queue_id) : [])} /></th><th>N°</th><th>File</th><th>Arrivé</th><th>Taille</th><th>De</th><th>À / motif</th></tr></thead>
          <tbody>{res.rows.map((r) => <tr key={r.queue_id}><td><input type="checkbox" checked={sel.includes(r.queue_id)} onChange={(e) => setSel(e.target.checked ? [...sel, r.queue_id] : sel.filter((x) => x !== r.queue_id))} /></td>
            <td><code>{r.queue_id}</code></td><td><Tone tone={r.queue === "deferred" ? "warn" : r.queue === "hold" ? "neutral" : "good"}>{r.queue}</Tone></td><td>{when(r.arrival)}</td><td>{size(r.size)}</td><td>{r.sender || "<>"}</td>
            <td>{r.recipients.map((x, i) => <div key={i}>{x.address}{x.reason && <div className="muted">{x.reason}</div>}</div>)}</td></tr>)}</tbody></table></AutoColumns>
        {res.total > res.rows.length && <p className="muted">{res.rows.length} affichés sur {res.total}.</p>}
      </>}
    </div>
  );
}

export function MailFailures({ run }) {
  const [hours, setHours] = useState(24), [res, setRes] = useState(null), [kind, setKind] = useState("");
  const [go, busy, status] = useAction(run);
  const load = async (h = hours) => { const r = await go({ action: "delivery_failures", hours: h }); if (r) setRes(r); };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  const kinds = [...new Set((res?.groups || []).map((g) => g.kind))];
  return (
    <div>
      <div className="pv-inline"><select value={hours} onChange={(e) => { setHours(Number(e.target.value)); load(Number(e.target.value)); }}>{[[6, "6 h"], [24, "24 h"], [72, "3 jours"], [168, "7 jours"], [336, "14 jours"]].map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>
        <select value={kind} onChange={(e) => setKind(e.target.value)}><option value="">toutes natures</option>{kinds.map((k) => <option key={k} value={k}>{k}</option>)}</select>
        <button className="secondary" onClick={() => load()} disabled={busy}>Actualiser</button>{status}</div>
      {res && <>
        <p><Tone tone="warn">{res.deferred} report(s)</Tone> <Tone tone="bad">{res.bounced} rebond(s)</Tone> sur {res.hours} h. Les reports sont réessayés par Postfix ; les rebonds sont définitifs (l'expéditeur a reçu un avis de non-remise).</p>
        <AutoColumns id="MailOps.failures"><table><thead><tr><th>État</th><th>Domaine distant</th><th>Nature</th><th>DSN</th><th>Nombre</th><th>Dernier</th><th>Motif</th><th>Relais / destinataires</th></tr></thead>
          <tbody>{res.groups.filter((g) => !kind || g.kind === kind).map((g, i) => <tr key={i}><td><Tone tone={g.status === "bounced" ? "bad" : "warn"}>{g.status === "bounced" ? "rebond" : "report"}</Tone></td>
            <td>{g.domain}</td><td>{g.kind}</td><td><code>{g.dsn}</code></td><td>{g.count}</td><td>{when(g.last)}</td><td style={{ maxWidth: 420 }}>{g.reason}</td>
            <td className="muted">{g.relays.join(", ")}<div>{g.recipients.join(", ")}</div></td></tr>)}</tbody></table></AutoColumns>
      </>}
    </div>
  );
}

export function MailLists({ run, reason }) {
  const [res, setRes] = useState(null), [colour, setColour] = useState(""), [text, setText] = useState(""), [draft, setDraft] = useState(null);
  const [go, busy, status] = useAction(run);
  const load = async () => { const r = await go({ action: "lists" }); if (r) setRes(r); };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  const editable = [...(res?.maps || []).filter((m) => m.editable).map((m) => ({ path: m.path, label: `${m.role} — ${m.type}:${m.path}`, type: m.type })),
    ...(res?.postgrey || []).filter((p) => p.editable).map((p) => ({ path: p.path, label: `postgrey — ${p.path}`, type: "postgrey" }))];
  const save = async (d, remove = false) => {
    if (needReason(reason)) return;
    if (remove && !window.confirm(`Retirer ${d.key} de ${d.path} ?`)) return;
    const r = await go({ action: "list_set", path: d.path, key: d.key, value: d.value, remove, reason });
    if (r) { setDraft(null); load(); }
  };
  const rows = flatEntries(res, colour, text);
  return (
    <div>
      <div className="pv-inline"><button className="secondary" onClick={load} disabled={busy}>Actualiser</button>
        <button className="primary" onClick={() => setDraft({ path: editable[0]?.path || "", key: "", value: "OK" })} disabled={!editable.length}>+ Entrée</button>
        <select value={colour} onChange={(e) => setColour(e.target.value)}><option value="">toutes</option><option value="blanche">liste blanche</option><option value="grise">liste grise</option><option value="noire">liste noire</option><option value="neutre">autres</option></select>
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="filtrer" />{status}</div>
      {draft && <div className="hub-card" style={{ margin: "8px 0" }}>
        <div className="pv-inline"><select value={draft.path} onChange={(e) => setDraft({ ...draft, path: e.target.value })}>{editable.map((m) => <option key={m.path} value={m.path}>{m.label}</option>)}</select>
          <input value={draft.key} onChange={(e) => setDraft({ ...draft, key: e.target.value })} placeholder="adresse, @domaine, domaine, IP ou réseau" style={{ minWidth: 260 }} />
          {editable.find((m) => m.path === draft.path)?.type !== "postgrey" && <input value={draft.value} onChange={(e) => setDraft({ ...draft, value: e.target.value })} placeholder="OK, REJECT motif, 450 motif, permit, reject…" style={{ minWidth: 220 }} />}
          <button className="primary" onClick={() => save(draft)} disabled={busy || !draft.key}>Enregistrer</button><button className="secondary" onClick={() => setDraft(null)}>Annuler</button></div>
        <p className="muted" style={{ fontSize: 12 }}>OK / permit = liste blanche ; REJECT / 5xx / reject = liste noire ; 4xx = refus temporaire (liste grise). La table est sauvegardée (.si-bak-…), recompilée (postmap) et Postfix rechargé ; en cas d'erreur l'état antérieur est rétabli.</p></div>}
      {res && <>
        <AutoColumns id="MailOps.lists"><table><thead><tr><th>Liste</th><th>Clé</th><th>Action</th><th>Contrôle</th><th>Table</th><th /></tr></thead>
          <tbody>{rows.map((e, i) => <tr key={i}><td><Tone tone={LIST_TONE[e.list]}>{e.list}</Tone></td><td><code>{e.key}</code></td><td>{e.value}</td><td>{e.role}</td><td className="muted">{e.type}:{e.path}</td>
            <td>{e.editable && <><button className="secondary" onClick={() => setDraft({ path: e.path, key: e.key, value: e.value })}>Modifier</button> <button className="secondary" onClick={() => save(e, true)}>Retirer</button></>}</td></tr>)}</tbody></table></AutoColumns>
        {(res.maps || []).some((m) => !m.editable) && <p className="muted">Tables en lecture seule (pcre / regexp / sql…) : {(res.maps || []).filter((m) => !m.editable).map((m) => `${m.type}:${m.path}`).join(", ")}.</p>}
        <h3>Listes DNS (réputation)</h3>
        <p>Postfix (smtpd) : {(res.dnsbl?.smtpd || []).map((r) => `${r.check} ${r.zone}`).join(", ") || "aucune"}<br />
          postscreen : {(res.dnsbl?.postscreen_sites || []).join(", ") || "aucune"} — action <b>{res.dnsbl?.postscreen_action || "—"}</b>, seuil {res.dnsbl?.postscreen_threshold || "—"}
          {res.dnsbl?.postscreen_action === "ignore" && <> <Tone tone="warn">consultées sans effet</Tone> (Réglages : postscreen_dnsbl_action)</>}</p>
        <p className="muted">Les règles par expéditeur d'Amavis (score, blanche, noire) sont dans Quarantaine › Règles de protection.</p>
      </>}
    </div>
  );
}

export function MailSettings({ run, reason }) {
  const [cur, setCur] = useState(null), [draft, setDraft] = useState({ postfix: {}, amavis: {} });
  const [go, busy, status] = useAction(run);
  const load = async () => { const r = await go({ action: "settings_get" }); if (r) { setCur(r); setDraft({ postfix: {}, amavis: {} }); } };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, []);
  const diff = settingsDiff(cur, draft);
  const apply = async () => {
    if (!diff || needReason(reason)) return;
    const lines = [...Object.entries(diff.postfix).map(([k, v]) => `Postfix ${k} = ${v}`), ...Object.entries(diff.amavis).map(([k, v]) => `Amavis ${k} = ${v}`)];
    if (!window.confirm(`Appliquer :\n${lines.join("\n")}${Object.keys(diff.amavis).length ? "\n\nAmavis sera redémarré (quelques secondes de refus temporaires 451)." : ""}`)) return;
    const r = await go({ action: "settings_set", ...diff, reason });
    if (r) { window.alert("Réglages appliqués."); load(); }
  };
  const group = (g, title) => (
    <><h3>{title}</h3><AutoColumns id={`MailOps.set.${g}`}><table><thead><tr><th>Réglage</th><th>Valeur actuelle</th><th>Nouvelle valeur</th></tr></thead>
      <tbody>{(cur?.[g] || []).map((r) => <tr key={r.key}><td>{r.label}<div className="muted"><code>{r.key}</code>{r.file ? ` — ${r.file}` : ""}</div></td><td><code>{r.value ?? "(défaut)"}</code></td>
        <td><input value={draft[g][r.key] ?? ""} placeholder={r.value ?? ""} onChange={(e) => setDraft({ ...draft, [g]: { ...draft[g], [r.key]: e.target.value } })} /></td></tr>)}</tbody></table></AutoColumns></>
  );
  return (
    <div>
      <div className="pv-inline"><button className="secondary" onClick={load} disabled={busy}>Actualiser</button><button className="primary" onClick={apply} disabled={busy || !diff}>Appliquer{diff ? ` (${Object.keys(diff.postfix).length + Object.keys(diff.amavis).length})` : ""}</button>{status}</div>
      {cur && <>{group("postfix", "Postfix (postconf -e, postfix check, rechargement)")}{group("amavis", "Antispam — Amavis / SpamAssassin (50-user, redémarrage vérifié)")}
        <p className="muted" style={{ fontSize: 12 }}>Liste fermée de réglages, valeurs contrôlées sur le serveur. Chaque fichier est sauvegardé (.si-bak-…) ; si Postfix refuse la configuration ou si Amavis ne redémarre pas, l'état antérieur est rétabli.</p></>}
    </div>
  );
}
