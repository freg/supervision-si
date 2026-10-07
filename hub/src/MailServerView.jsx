// Tuile « Serveur de messagerie » (livraison #697). S'appuie sur l'agent
// installé sur le serveur Postfix / Amavis / Dovecot (sonde mail-server #692 +
// commande `mail` : si-agent/agent/si_agent/mailctl.py) :
//   - Traitements : état de la sonde + historique regroupé par message ;
//   - Recherche : boîtes (doveadm), historique (journal), quarantaine (SQL
//     Amavis), filtres de / à (utilisateur ou *@domaine) / sujet à jokers /
//     plein texte / contenu / période ; libération depuis la quarantaine ;
//   - Visualiseur : aperçu HTML isolé (aucun script, aucun chargement distant),
//     texte, source, en-têtes, structure MIME, téléchargement .eml ;
//   - Quarantaine (#704) : niveaux, statistiques, redistribution, règles (MailQuarantine.jsx) ;
//   - Journal : arbre programme → évènement → lignes.
// Secret des correspondances : ouvrir un message ou le libérer exige un motif,
// journalisé sur le serveur avec l'acteur (comme chaque recherche).
import { Fragment, useEffect, useMemo, useState } from "react";
import HubIcon from "./HubIcon.jsx";
import MailServerSection from "./MailServerSection.jsx";
import MailQuarantine from "./MailQuarantine.jsx";
import { fetchFleet, fetchAgentMeasurements, sendCommand, fetchCommand } from "./siAgentClient.js";
import { summarize, safeHtmlDocument } from "./mailMime.js";

const STORE_KEY = "mailserver.agent";
const when = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "—");
const size = (n) => (n == null ? "" : n > 1e6 ? (n / 1e6).toFixed(1) + " Mo" : n > 1e3 ? Math.round(n / 1e3) + " ko" : n + " o");
function Tone({ tone, children }) { return <span className={`np-tone ${tone || "neutral"}`}>{children}</span>; }

/** Commande `mail` envoyée à l'agent puis suivie jusqu'à l'acquittement (l'agent relève ses commandes ~ chaque minute). */
async function mailCommand(base, agentId, params, onWait) {
  const r = await sendCommand(base, agentId, "mail", params);
  if (r?.error) throw new Error(r.error);
  const cid = r?.command?.id || r?.id;
  const started = Date.now();
  while (Date.now() - started < 4 * 60 * 1000) {
    await new Promise((ok) => setTimeout(ok, 2500));
    onWait?.(Math.round((Date.now() - started) / 1000));
    const c = await fetchCommand(base, cid).catch(() => null);
    if (c && (c.status === "done" || c.status === "failed" || c.result)) {
      const res = c.result?.result || c.result || {};
      if (c.status === "failed" || res.ok === false) throw new Error(res.error || c.result?.error || c.error || "échec");
      return res;
    }
  }
  throw new Error("l'agent n'a pas répondu en 4 min (hors ligne ?)");
}

const stateTone = (m) => {
  const s = [...(m.states || []), m.amavis?.verdict || ""].join(" ");
  if (/refus|bloqu|Blocked|bounced|reject/i.test(s)) return "bad";
  if (/deferred|différ/i.test(s)) return "warn";
  if (/sent|Passed/.test(s)) return "good";
  return "neutral";
};

export default function MailServerView({ onBack, siAgentApiBase, username, isAdmin = false }) {
  const base = siAgentApiBase;
  const [agents, setAgents] = useState(null);
  const [agentId, setAgentId] = useState(() => { try { return localStorage.getItem(STORE_KEY) || ""; } catch { return ""; } });
  const [probe, setProbe] = useState(null);
  const [tab, setTab] = useState("traitements");
  const [viewer, setViewer] = useState(null);
  const [reason, setReason] = useState("");

  useEffect(() => {
    if (!isAdmin) return;
    (async () => {
      const fleet = await fetchFleet(base);
      const linux = fleet.filter((a) => !/win|darwin|mac/i.test(a.platform || a.os || ""));
      const found = [];
      await Promise.all(linux.map(async (a) => {
        const m = await fetchAgentMeasurements(base, a.agent_id, { task: "plugin:mail-server", limit: 1 });
        if (m.length) found.push({ ...a, latest: m[0] });
      }));
      found.sort((x, y) => x.agent_id.localeCompare(y.agent_id));
      setAgents(found);
      if (found.length && !found.some((a) => a.agent_id === agentId)) setAgentId(found[0].agent_id);
    })();
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [base]);
  useEffect(() => {
    try { if (agentId) localStorage.setItem(STORE_KEY, agentId); } catch { /* stockage indisponible */ }
    setProbe((agents || []).find((a) => a.agent_id === agentId)?.latest || null);
  }, [agentId, agents]);

  const run = (params, onWait) => mailCommand(base, agentId, { ...params, actor: username || undefined }, onWait);
  const open = async (kind, row) => {
    if (reason.trim().length < 4) { setViewer({ error: "Indiquer d'abord le motif de consultation (secret des correspondances), en haut de la page." }); return; }
    setViewer({ loading: true, title: row.subject || row.mail_id });
    try {
      const p = kind === "quarantine" ? { action: "quarantine_get", mail_id: row.mail_id } : { action: "mailbox_get", user: row.user, guid: row.guid, uid: row.uid };
      const r = await run({ ...p, reason }, (s) => setViewer((v) => (v?.loading ? { ...v, wait: s } : v)));
      setViewer({ raw: r.raw, truncated: r.truncated, size: r.size, kind, row });
    } catch (e) { setViewer({ error: e.message }); }
  };
  const release = async (row) => {
    if (reason.trim().length < 4) { window.alert("Motif de consultation requis (en haut de la page)."); return false; }
    if (!window.confirm(`Libérer le message ${row.mail_id} de ${row.from || "<>"} vers ${(row.to || []).join(", ")} ?`)) return false;
    const r = await run({ action: "quarantine_release", mail_id: row.mail_id, reason });
    window.alert(`Libéré : ${r.output || "ok"}`);
    return true;
  };

  return (
    <div className="hub-settings">
      <div className="hub-settings-topbar"><button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1><HubIcon icon="mail" size={22} /> Serveur de messagerie</h1></div>

      {!isAdmin ? <p className="muted">Réservé aux administrateurs (accès au contenu des boîtes et à la quarantaine).</p>
        : agents === null ? <p className="muted">⏳ recherche des serveurs équipés de la sonde mail-server…</p>
        : agents.length === 0 ? <p className="muted">Aucun agent ne porte la sonde <code>mail-server</code> : l'activer sur l'agent du serveur de messagerie (fiche de l'agent → Commandes → « Activer une sonde »).</p> : (
        <>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap", alignItems: "center", marginBottom: 8 }}>
            <label>Serveur <select value={agentId} onChange={(e) => setAgentId(e.target.value)}>
              {agents.map((a) => <option key={a.agent_id} value={a.agent_id}>{a.agent_id}{a.hostname ? ` — ${a.hostname}` : ""}</option>)}
            </select></label>
            <label style={{ flex: "1 1 320px" }}>Motif de consultation <input style={{ width: "100%" }} value={reason} onChange={(e) => setReason(e.target.value)}
              placeholder="ex. demande de l'utilisateur, faux positif signalé (obligatoire pour ouvrir ou libérer, journalisé)" /></label>
          </div>
          <div className="na-section-tabs" style={{ display: "flex", gap: 6, marginBottom: 10 }}>
            {[["traitements", "Traitements"], ["recherche", "Recherche"], ["quarantaine", "Quarantaine"], ["journal", "Journal"]].map(([k, l]) =>
              <button key={k} className={`secondary na-section-toggle${tab === k ? " active" : ""}`} onClick={() => setTab(k)}>{l}</button>)}
          </div>
          {tab === "traitements" && <Treatments probe={probe} run={run} />}
          {tab === "recherche" && <Search run={run} onOpen={open} onRelease={release} />}
          {tab === "quarantaine" && <MailQuarantine run={run} reason={reason} onOpen={open} />}
          {tab === "journal" && <LogTree run={run} />}
          <p className="muted" style={{ fontSize: 12 }}>Chaque action passe par l'agent du serveur, qui relève ses commandes environ chaque minute : compter jusqu'à une minute par recherche.</p>
        </>
      )}
      {viewer && <Viewer v={viewer} onClose={() => setViewer(null)} onRelease={release} />}
    </div>
  );
}

// ------------------------------------------------------------------ Traitements

function Treatments({ probe, run }) {
  const [hours, setHours] = useState(1);
  const [res, setRes] = useState(null);
  const [wait, setWait] = useState(null);
  const load = async () => {
    setRes(null); setWait(0);
    try { setRes(await run({ action: "log_search", hours, limit: 300 }, setWait)); } catch (e) { setRes({ error: e.message }); }
    setWait(null);
  };
  const counts = useMemo(() => {
    const c = {};
    for (const m of res?.rows || []) {
      const k = m.amavis?.verdict || (m.states.find((s) => s.startsWith("refusé")) ? "refusé à la connexion" : m.states.includes("sent") ? "remis" : m.states[m.states.length - 1] || "en cours");
      c[k] = (c[k] || 0) + 1;
    }
    return Object.entries(c).sort((a, b) => b[1] - a[1]);
  }, [res]);
  return (
    <>
      {probe ? <MailServerSection latest={probe} when={when} /> : <p className="muted">Pas encore de mesure de la sonde mail-server.</p>}
      <h3>Traitements des messages
        <select value={hours} onChange={(e) => setHours(+e.target.value)} style={{ marginLeft: 8 }}>
          {[1, 6, 24, 72, 168].map((h) => <option key={h} value={h}>{h < 24 ? `${h} h` : `${h / 24} j`}</option>)}
        </select>{" "}
        <button className="secondary" disabled={wait !== null} onClick={load}>{wait !== null ? `⏳ ${wait} s` : "Charger"}</button>
      </h3>
      {res?.error && <p style={{ color: "var(--danger)" }}>{res.error}</p>}
      {counts.length > 0 && <p>{counts.map(([k, n]) => <span key={k} style={{ marginRight: 10 }}><Tone tone={/refus|Blocked/.test(k) ? "bad" : /Passed|remis/.test(k) ? "good" : "neutral"}>{n}</Tone> {k}</span>)}
        {res.truncated && <span className="muted"> · {res.total} messages, 300 affichés</span>}</p>}
      {res?.rows && <MessageTable rows={res.rows} />}
    </>
  );
}

function MessageTable({ rows }) {
  const [open, setOpen] = useState(null);
  if (!rows.length) return <p className="muted">Aucun message.</p>;
  return (
    <table>
      <thead><tr><th>Dernière étape</th><th>De</th><th>À</th><th>Filtre</th><th>États</th><th>N°</th></tr></thead>
      <tbody>{rows.map((m) => (
        <Fragment key={m.key}>
          <tr style={{ cursor: "pointer" }} onClick={() => setOpen(open === m.key ? null : m.key)}>
            <td>{when(m.last)}</td><td>{m.from || "<>"}</td><td>{(m.to || []).join(", ")}</td>
            <td>{m.amavis ? <>{m.amavis.verdict}{m.amavis.hits != null && <span className="muted"> ({m.amavis.hits})</span>}</> : "—"}</td>
            <td><Tone tone={stateTone(m)}>{[...new Set(m.states)].join(", ") || "—"}</Tone></td>
            <td className="muted"><code>{m.key}</code></td>
          </tr>
          {open === m.key && <tr><td colSpan={6}><pre style={{ whiteSpace: "pre-wrap", fontSize: 12, margin: 0 }}>{m.lines.map((l) => l.line).join("\n")}</pre></td></tr>}
        </Fragment>
      ))}</tbody>
    </table>
  );
}

// ------------------------------------------------------------------ Recherche

const EMPTY = { from: "", to: "", user: "", subject: "", text: "", body: "", since: "", before: "", hours: 24, days: 30, onlyQuarantined: true };

function Search({ run, onOpen, onRelease }) {
  const [f, setF] = useState(EMPTY);
  const [scopes, setScopes] = useState({ mailbox: true, log: true, quarantine: true });
  const [res, setRes] = useState({});
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const go = async (e) => {
    e?.preventDefault();
    const jobs = {
      mailbox: () => run({ action: "mailbox_search", from: f.from, to: f.to, user: f.user, subject: f.subject, text: f.text, body: f.body, since: f.since, before: f.before, limit: 200 }),
      log: () => run({ action: "log_search", from: f.from, to: f.to || f.user, hours: f.hours, limit: 200 }),
      quarantine: () => run({ action: "quarantine_search", from: f.from, to: f.to || f.user.replace(/^\*$/, ""), subject: f.subject, days: f.days, only_quarantined: f.onlyQuarantined, limit: 200 }),
    };
    const next = {};
    for (const k of Object.keys(jobs)) if (scopes[k]) next[k] = { loading: true };
    setRes(next);
    await Promise.all(Object.keys(next).map(async (k) => {
      try { const r = await jobs[k](); setRes((s) => ({ ...s, [k]: r })); } catch (err) { setRes((s) => ({ ...s, [k]: { error: err.message } })); }
    }));
  };
  const field = (k, label, ph, w = 220) => <label style={{ display: "flex", flexDirection: "column", fontSize: 13 }}>{label}<input value={f[k]} onChange={set(k)} placeholder={ph} style={{ width: w }} /></label>;
  return (
    <>
      <form onSubmit={go} style={{ display: "flex", gap: 10, flexWrap: "wrap", alignItems: "flex-end", marginBottom: 8 }}>
        {field("from", "Expéditeur", "*@exemple.org, alice")}
        {field("to", "Destinataire", "bob@…, *@domaine.fr")}
        {field("user", "Boîte(s)", "bob@domaine.fr ou *@domaine.fr (vide = toutes)")}
        {field("subject", "Sujet (jokers * ?)", "*facture*")}
        {field("text", "Plein texte", "en-têtes + corps", 180)}
        {field("body", "Contenu (corps)", "mot du corps", 180)}
        <label style={{ display: "flex", flexDirection: "column", fontSize: 13 }}>Depuis<input type="date" value={f.since} onChange={set("since")} /></label>
        <label style={{ display: "flex", flexDirection: "column", fontSize: 13 }}>Avant<input type="date" value={f.before} onChange={set("before")} /></label>
        <span style={{ fontSize: 13 }}>
          {[["mailbox", "boîtes"], ["log", "historique"], ["quarantine", "quarantaine"]].map(([k, l]) =>
            <label key={k} style={{ marginRight: 8 }}><input type="checkbox" checked={scopes[k]} onChange={(e) => setScopes({ ...scopes, [k]: e.target.checked })} /> {l}</label>)}
          <br />historique <select value={f.hours} onChange={set("hours")}>{[1, 6, 24, 72, 168, 336].map((h) => <option key={h} value={h}>{h < 24 ? `${h} h` : `${h / 24} j`}</option>)}</select>
          {" "}quarantaine <select value={f.days} onChange={set("days")}>{[1, 7, 30, 90, 365].map((d) => <option key={d} value={d}>{d} j</option>)}</select>
          {" "}<label><input type="checkbox" checked={f.onlyQuarantined} onChange={set("onlyQuarantined")} /> en quarantaine seulement</label>
        </span>
        <button type="submit">Rechercher</button>
        <button type="button" className="secondary" onClick={() => { setF(EMPTY); setRes({}); }}>Effacer</button>
      </form>
      <p className="muted" style={{ fontSize: 12 }}>Jokers <code>*</code> et <code>?</code>, sans joker = « contient ». Le sujet et le contenu ne figurent pas dans le journal : l'historique filtre sur l'expéditeur et le destinataire. Plein texte sur toutes les boîtes sans index : plusieurs minutes possibles — restreindre par boîte ou par date.</p>

      {res.mailbox && <Section title="Boîtes" r={res.mailbox}>{(r) => (
        <table><thead><tr><th>Reçu</th><th>Boîte</th><th>Dossier</th><th>De</th><th>À</th><th>Sujet</th><th>Taille</th><th /></tr></thead>
          <tbody>{r.rows.map((m) => <tr key={`${m.user}/${m.guid}/${m.uid}`}><td>{m.date}</td><td>{m.user}</td><td>{m.mailbox}</td><td>{m.from}</td><td>{m.to}</td><td>{m.subject}</td><td>{size(m.size)}</td>
            <td><button className="secondary" onClick={() => onOpen("mailbox", m)}>Voir</button></td></tr>)}</tbody></table>)}</Section>}
      {res.log && <Section title="Historique de traitement" r={res.log}>{(r) => <MessageTable rows={r.rows} />}</Section>}
      {res.quarantine && <Section title="Quarantaine" r={res.quarantine}>{(r) => <QuarantineTable rows={r.rows} onOpen={onOpen} onRelease={onRelease} />}</Section>}
    </>
  );
}

function Section({ title, r, children }) {
  return (
    <details open style={{ marginBottom: 10 }}>
      <summary><strong>{title}</strong> {r.loading ? <span className="muted">⏳ en attente de l'agent…</span> : r.error ? <span style={{ color: "var(--danger)" }}>{r.error}</span>
        : <span className="muted">{r.total ?? r.rows?.length} résultat(s){r.truncated ? `, ${r.rows.length} affichés` : ""}</span>}</summary>
      {!r.loading && !r.error && (r.rows?.length ? children(r) : <p className="muted">Aucun résultat.</p>)}
    </details>
  );
}

function QuarantineTable({ rows, onOpen, onRelease }) {
  const [done, setDone] = useState({});
  return (
    <table><thead><tr><th>Reçu</th><th>Type</th><th>Score</th><th>De</th><th>À</th><th>Sujet</th><th>Taille</th><th /></tr></thead>
      <tbody>{rows.map((q) => (
        <tr key={q.mail_id}>
          <td>{when(q.at)}</td><td><Tone tone={q.content === "V" ? "bad" : q.content === "S" ? "warn" : "neutral"}>{q.content_label}</Tone></td>
          <td>{q.score ?? "—"}</td><td>{q.from || "<>"}</td><td>{q.to.join(", ")}</td><td>{q.subject}</td><td>{size(q.size)}</td>
          <td style={{ whiteSpace: "nowrap" }}>{q.quarantined && <button className="secondary" onClick={() => onOpen("quarantine", q)}>Voir</button>}{" "}
            {q.quarantined && (done[q.mail_id] ? <Tone tone="good">libéré</Tone>
              : <button className="secondary" onClick={async () => { try { if (await onRelease(q)) setDone({ ...done, [q.mail_id]: true }); } catch (e) { window.alert(e.message); } }}>Libérer</button>)}</td>
        </tr>
      ))}</tbody></table>
  );
}

// ------------------------------------------------------------------ Visualiseur

function Viewer({ v, onClose, onRelease }) {
  const [mode, setMode] = useState("html");
  const info = useMemo(() => (v.raw ? summarize(v.raw) : null), [v.raw]);
  const download = () => {
    const url = URL.createObjectURL(new Blob([v.raw], { type: "message/rfc822" }));
    const a = document.createElement("a"); a.href = url; a.download = `${(info?.subject || v.row?.mail_id || "message").replace(/[^\w.-]+/g, "_").slice(0, 60)}.eml`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  return (
    <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,.45)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center" }} onClick={onClose}>
      <div className="np-card" style={{ width: "min(1100px, 96vw)", height: "90vh", display: "flex", flexDirection: "column", background: "var(--bg, #fff)", padding: 12 }} onClick={(e) => e.stopPropagation()}>
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <strong style={{ flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{info?.subject || v.title || "Message"}</strong>
          {info && [["html", "Aperçu HTML"], ["text", "Texte"], ["source", "Source"], ["headers", "En-têtes"], ["tree", "Structure"]].map(([k, l]) =>
            <button key={k} className={`secondary na-section-toggle${mode === k ? " active" : ""}`} onClick={() => setMode(k)}>{l}</button>)}
          {info && <button className="secondary" onClick={download}>.eml</button>}
          {info && v.kind === "quarantine" && <button className="secondary" onClick={() => onRelease(v.row).catch((e) => window.alert(e.message))}>Libérer</button>}
          <button className="secondary" onClick={onClose}>✕</button>
        </div>
        {v.loading && <p className="muted">⏳ récupération par l'agent… {v.wait ? `${v.wait} s` : ""}</p>}
        {v.error && <p style={{ color: "var(--danger)" }}>{v.error}</p>}
        {info && (
          <>
            <p className="muted" style={{ fontSize: 13, margin: "6px 0" }}>De <strong>{info.from}</strong> · à {info.to}{info.cc ? ` · cc ${info.cc}` : ""} · {info.date}
              {info.spam && <> · {info.spam}</>}{info.attachments.length > 0 && <> · 📎 {info.attachments.map((a) => `${a.filename} (${size(a.size)})`).join(", ")}</>}
              {info.remoteImages > 0 && <> · <Tone tone="warn">{info.remoteImages} image(s) distante(s) bloquée(s)</Tone></>}
              {v.truncated && <> · <Tone tone="warn">tronqué à 3 Mo sur {size(v.size)}</Tone></>}</p>
            <div style={{ flex: 1, minHeight: 0, overflow: "auto", border: "1px solid var(--border)", borderRadius: 6 }}>
              {mode === "html" && <iframe title="aperçu" sandbox="" srcDoc={safeHtmlDocument(info)} style={{ width: "100%", height: "100%", border: 0, background: "#fff" }} />}
              {mode === "text" && <pre style={{ whiteSpace: "pre-wrap", padding: 8, margin: 0 }}>{info.text || "(pas de partie texte)"}</pre>}
              {mode === "source" && <pre style={{ whiteSpace: "pre-wrap", padding: 8, margin: 0, fontSize: 12 }}>{v.raw}</pre>}
              {mode === "headers" && <table><tbody>{info.tree.headers.map((h, i) => <tr key={i}><td style={{ whiteSpace: "nowrap", verticalAlign: "top" }}><code>{h.name}</code></td><td style={{ wordBreak: "break-word" }}>{h.value}</td></tr>)}</tbody></table>}
              {mode === "tree" && <MimeTree node={info.tree} />}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function MimeTree({ node, depth = 0 }) {
  return (
    <div style={{ marginLeft: depth ? 16 : 4, fontSize: 13 }}>
      <code>{node.type}</code>{node.params.charset && <span className="muted"> {node.params.charset}</span>}{node.encoding && <span className="muted"> · {node.encoding}</span>}
      {node.filename && <> · 📎 {node.filename}</>}{node.cid && <span className="muted"> · cid {node.cid}</span>}<span className="muted"> · {size(node.size)}</span>
      {node.parts.map((p, i) => <MimeTree key={i} node={p} depth={depth + 1} />)}
    </div>
  );
}

// ------------------------------------------------------------------ Journal en arbre

function LogTree({ run }) {
  const [minutes, setMinutes] = useState(60);
  const [res, setRes] = useState(null);
  const [wait, setWait] = useState(null);
  const [filter, setFilter] = useState("");
  const [json, setJson] = useState(false);
  const load = async () => {
    setWait(0);
    try { setRes(await run({ action: "log_tree", minutes }, setWait)); } catch (e) { setRes({ error: e.message }); }
    setWait(null);
  };
  const tree = useMemo(() => {
    if (!res?.tree) return null;
    const f = filter.trim().toLowerCase();
    const out = {};
    for (const [b, subs] of Object.entries(res.tree)) for (const [s, leaf] of Object.entries(subs)) {
      const lines = f ? leaf.lines.filter((l) => l.line.toLowerCase().includes(f)) : leaf.lines;
      if (lines.length || !f) (out[b] = out[b] || {})[s] = { ...leaf, lines };
    }
    return out;
  }, [res, filter]);
  return (
    <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <select value={minutes} onChange={(e) => setMinutes(+e.target.value)}>{[15, 60, 240, 720, 1440].map((m) => <option key={m} value={m}>{m < 60 ? `${m} min` : `${m / 60} h`}</option>)}</select>
        <button className="secondary" disabled={wait !== null} onClick={load}>{wait !== null ? `⏳ ${wait} s` : "Charger le journal"}</button>
        <input placeholder="filtrer les lignes (adresse, n°, IP…)" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ minWidth: 260 }} />
        <label><input type="checkbox" checked={json} onChange={(e) => setJson(e.target.checked)} /> JSON brut</label>
        {res?.lines != null && <span className="muted">{res.lines} ligne(s) sur {res.minutes} min</span>}
      </div>
      {res?.error && <p style={{ color: "var(--danger)" }}>{res.error}</p>}
      {tree && (json ? <pre style={{ fontSize: 12, whiteSpace: "pre-wrap" }}>{JSON.stringify(tree, null, 2)}</pre> : (
        <div style={{ fontFamily: "ui-monospace, monospace", fontSize: 13 }}>
          {Object.entries(tree).sort().map(([b, subs]) => (
            <details key={b} open={!!filter}>
              <summary>▸ <strong>{b}</strong> <span className="muted">{Object.values(subs).reduce((n, l) => n + l.count, 0)}</span></summary>
              <div style={{ marginLeft: 18 }}>{Object.entries(subs).sort((x, y) => y[1].count - x[1].count).map(([s, leaf]) => (
                <details key={s} open={!!filter}>
                  <summary>▸ {s} <span className="muted">{leaf.count}{leaf.lines.length < leaf.count ? ` (${leaf.lines.length} affichées)` : ""}</span></summary>
                  <div style={{ marginLeft: 18 }}>{leaf.lines.map((l, i) => <div key={i} style={{ whiteSpace: "pre-wrap", wordBreak: "break-all", borderLeft: "2px solid var(--border)", paddingLeft: 6 }}>{l.line}</div>)}</div>
                </details>
              ))}</div>
            </details>
          ))}
        </div>
      ))}
    </>
  );
}
