// Onglet « Quarantaine » de la tuile Serveur de messagerie (livraison #704).
// Niveaux : récupérable (message encore stocké), dépassée (purgée, trace seule),
// historique complet (tous les messages traités, aussi loin que la base remonte) ;
// statistiques par expéditeur / domaine / destinataire / type / jour / client ;
// actions : redistribuer (libération groupée), règles de protection Amavis
// (wblist : ajustement de score, liste blanche, liste noire). Libérer et modifier
// une règle exigent le motif saisi en haut de la page (journalisé sur le serveur).
import { useState } from "react";

import { AutoColumns } from "./TableColumns.jsx";   // #707 : colonnes réglables
const when = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "—");
const day = (t) => (t ? new Date(t * 1000).toLocaleDateString("fr-FR") : "—");
const size = (n) => (n == null ? "" : n > 1e6 ? (n / 1e6).toFixed(1) + " Mo" : n > 1e3 ? Math.round(n / 1e3) + " ko" : n + " o");
function Tone({ tone, children }) { return <span className={`np-tone ${tone || "neutral"}`}>{children}</span>; }

const LEVELS = [["recoverable", "Récupérable"], ["expired", "Dépassée"], ["history", "Historique complet"], ["stats", "Statistiques"], ["rules", "Règles de protection"]];
const DIMS = [["sender", "Expéditeur"], ["sender_domain", "Domaine expéditeur"], ["recipient", "Destinataire"], ["recipient_domain", "Domaine destinataire"],
  ["content", "Type"], ["day", "Jour"], ["client", "Serveur d'origine"]];
const CONTENTS = [["", "tous"], ["S", "spam"], ["V", "virus"], ["B", "pièce jointe interdite"], ["H", "en-tête invalide"], ["Y", "spam sous le seuil"], ["C", "propre"]];
const WB = [["-3", "Adoucir (score −3)"], ["-5", "Adoucir (score −5)"], ["-10", "Adoucir fort (score −10)"], ["W", "Liste blanche"], ["B", "Liste noire"], ["+5", "Durcir (score +5)"]];
const wbLabel = (wb) => (WB.find(([v]) => v === wb)?.[1] || (wb === "W" ? "Liste blanche" : wb === "B" ? "Liste noire" : `score ${wb}`));
const F0 = { from: "", to: "", subject: "", content: "", client: "", days: 30, hide_released: false };

function downloadCsv(name, header, rows) {
  const esc = (v) => { const s = v == null ? "" : String(v); return /[";\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s; };
  const text = "﻿" + [header, ...rows].map((r) => r.map(esc).join(";")).join("\r\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], { type: "text/csv;charset=utf-8" }));
  a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000);
}

export default function MailQuarantine({ run, reason, onOpen }) {
  const [level, setLevel] = useState("recoverable");
  const [f, setF] = useState(F0);
  const [res, setRes] = useState(null);
  const [stats, setStats] = useState(null);
  const [dim, setDim] = useState("sender_domain");
  const [rules, setRules] = useState(null);
  const [ruleDraft, setRuleDraft] = useState(null);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const needReason = () => { if (reason.trim().length < 4) { window.alert("Motif requis (en haut de la page) : il est journalisé sur le serveur."); return true; } return false; };

  const search = async (lv = level, filters = f) => {
    setRes({ loading: true, level: lv });
    try { setRes({ ...(await run({ action: "quarantine_search", ...filters, level: lv, days: +filters.days || 30, limit: 300 })), level: lv, sel: {}, done: {} }); }
    catch (e) { setRes({ error: e.message, level: lv }); }
  };
  const computeStats = async () => {
    setStats({ loading: true });
    try { setStats(await run({ action: "quarantine_stats", level: f.level || "quarantined", ...f, days: +f.days || 30, limit: 100 })); }
    catch (e) { setStats({ error: e.message }); }
  };
  const loadRules = async () => {
    setRules({ loading: true });
    try { setRules(await run({ action: "wblist_list" })); } catch (e) { setRules({ error: e.message }); }
  };
  const drill = (by, key) => {
    const nf = { ...F0, days: f.days, ...(by === "sender" ? { from: key } : by === "sender_domain" ? { from: `*@${key}` } : by === "recipient" ? { to: key }
      : by === "recipient_domain" ? { to: `*@${key}` } : by === "content" ? { content: key } : by === "client" ? { client: key } : {}) };
    setF(nf); setLevel("recoverable"); search("recoverable", nf);
  };
  const proposeRule = (sender) => { setRuleDraft({ sender, recipient: "", wb: "-5" }); setLevel("rules"); if (!rules) loadRules(); };

  const releaseMany = async (ids) => {
    if (!ids.length || needReason()) return;
    if (!window.confirm(`Redistribuer ${ids.length} message(s) à leurs destinataires ?\nMotif : ${reason}`)) return;
    try {
      const r = await run({ action: "quarantine_release", mail_ids: ids, reason });
      const done = { ...(res.done || {}) };
      (r.results || []).forEach((x) => { done[x.mail_id] = x.ok ? "ok" : x.error; });
      setRes({ ...res, done, sel: {} });
      window.alert(`${r.released} libéré(s), ${r.failed} échec(s).`);
    } catch (e) { window.alert(e.message); }
  };

  const box = { border: "1px solid var(--border)", borderRadius: 8, padding: 10, marginBottom: 10 };
  const ov = stats?.overview;
  return (
    <div>
      <div className="na-section-tabs" style={{ display: "flex", gap: 6, marginBottom: 8, flexWrap: "wrap" }}>
        {LEVELS.map(([k, l]) => <button key={k} className={`secondary na-section-toggle${level === k ? " active" : ""}`}
          onClick={() => { setLevel(k); if (k === "rules" && !rules) loadRules(); }}>{l}</button>)}
      </div>
      {ov && <p className="muted" style={{ fontSize: 13 }}>
        Récupérable : <strong>{ov.recoverable.count}</strong> (depuis le {day(ov.recoverable.since)}) · dépassée : <strong>{ov.expired.count}</strong> ·
        historique : <strong>{ov.history.count}</strong> messages depuis le {day(ov.history.since)} · 24 h : {ov.last24h.quarantined} mis en quarantaine sur {ov.last24h.processed}</p>}

      {level !== "rules" && (
        <div style={box}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "end" }}>
            <label>De <input value={f.from} onChange={set("from")} placeholder="*@domaine, adresse" /></label>
            <label>À <input value={f.to} onChange={set("to")} placeholder="bob, *@exemple.fr" /></label>
            <label>Sujet <input value={f.subject} onChange={set("subject")} placeholder="*facture*" /></label>
            <label>Type <select value={f.content} onChange={set("content")}>{CONTENTS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Origine <input value={f.client} onChange={set("client")} placeholder="IP" style={{ width: 120 }} /></label>
            <label>Période <input type="number" min={1} max={3650} value={f.days} onChange={set("days")} style={{ width: 70 }} /> j</label>
            <label><input type="checkbox" checked={f.hide_released} onChange={set("hide_released")} /> masquer les libérés</label>
            {level === "stats"
              ? <button onClick={computeStats} disabled={stats?.loading}>{stats?.loading ? "⏳ calcul…" : "Calculer"}</button>
              : <button onClick={() => search()} disabled={res?.loading}>{res?.loading ? "⏳ agent…" : "Rechercher"}</button>}
            <button className="secondary" onClick={() => setF(F0)}>Effacer</button>
          </div>
          {level === "stats" && <label className="muted" style={{ display: "block", marginTop: 6 }}>Périmètre <select value={f.level || "quarantined"} onChange={set("level")}>
            <option value="quarantined">toute la quarantaine</option><option value="recoverable">récupérable</option><option value="expired">dépassée</option><option value="history">tous les messages traités</option></select></label>}
        </div>)}

      {["recoverable", "expired", "history"].includes(level) && res && res.level === level && (
        res.loading ? <p className="muted">⏳ en attente de l'agent (jusqu'à une minute)…</p> : res.error ? <p style={{ color: "var(--danger)" }}>{res.error}</p>
          : <Rows res={res} level={level} setRes={setRes} onOpen={onOpen} onRelease={releaseMany} onRule={proposeRule} />)}
      {level === "expired" && <p className="muted" style={{ fontSize: 12 }}>Quarantaine dépassée : le message a été purgé (durée de conservation de Modoboa / Amavis), seule la trace subsiste. Pour un message légitime, demander un renvoi à l'expéditeur.</p>}

      {level === "stats" && stats && (stats.loading ? <p className="muted">⏳ calcul sur le serveur…</p> : stats.error ? <p style={{ color: "var(--danger)" }}>{stats.error}</p> : (
        <div>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginBottom: 6 }}>
            {DIMS.map(([k, l]) => <button key={k} className={`secondary na-section-toggle${dim === k ? " active" : ""}`} onClick={() => setDim(k)}>{l}</button>)}
            <button className="secondary" onClick={() => { const g = stats.groups[dim] || []; downloadCsv(`quarantaine-${dim}.csv`,
              ["Clé", "Messages", "Récupérables", "Virus", "Libérés", "Premier", "Dernier", "Score moyen"],
              g.map((r) => [r.label, r.count, r.recoverable, r.virus, r.released, when(r.first), when(r.last), r.avg_score ?? ""])); }}>⬇ CSV</button>
          </div>
          {Array.isArray(stats.groups[dim]) ? (
            <AutoColumns id="MailQuarantine.1"><table><thead><tr><th>{DIMS.find(([k]) => k === dim)[1]}</th><th>Messages</th><th>Récupérables</th><th>Virus</th><th>Libérés</th><th>Période</th><th>Score moy.</th><th /></tr></thead>
              <tbody>{stats.groups[dim].map((r) => (
                <tr key={r.key}><td>{r.label || <span className="muted">(vide)</span>}</td><td>{r.count}</td><td>{r.recoverable}</td>
                  <td>{r.virus ? <Tone tone="bad">{r.virus}</Tone> : 0}</td><td>{r.released || ""}</td><td>{day(r.first)} → {day(r.last)}</td><td>{r.avg_score ?? "—"}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{dim !== "day" && <button className="secondary" onClick={() => drill(dim, r.key)}>Voir</button>}{" "}
                    {(dim === "sender" || dim === "sender_domain") && r.key && <button className="secondary" onClick={() => proposeRule(dim === "sender" ? r.key : `@${r.key}`)}>Règle…</button>}</td></tr>))}</tbody></table></AutoColumns>
          ) : <p style={{ color: "var(--danger)" }}>{stats.groups[dim]?.error || "non calculé"}</p>}
        </div>))}

      {level === "rules" && <Rules rules={rules} reload={loadRules} draft={ruleDraft} setDraft={setRuleDraft} run={run} reason={reason} needReason={needReason} setRules={setRules} />}
    </div>
  );
}

function Rows({ res, level, setRes, onOpen, onRelease, onRule }) {
  const rows = res.rows || [];
  const sel = res.sel || {};
  const can = (q) => q.stored && !q.released && res.done?.[q.mail_id] !== "ok";
  const ids = Object.keys(sel).filter((k) => sel[k]);
  const toggleAll = (on) => setRes({ ...res, sel: Object.fromEntries(rows.filter(can).map((q) => [q.mail_id, on])) });
  const exportCsv = () => downloadCsv(`quarantaine-${level}.csv`, ["Reçu", "Type", "Score", "De", "À", "Sujet", "Taille", "Stocké", "Libéré", "Origine", "mail_id"],
    rows.map((q) => [when(q.at), q.content_label, q.score ?? "", q.from, q.to.join(", "), q.subject, q.size, q.stored ? "oui" : "non", q.released ? "oui" : "", q.client, q.mail_id]));
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6, flexWrap: "wrap" }}>
        <span className="muted">{rows.length} message(s){rows.length >= 300 ? " (300 au plus : affiner les filtres)" : ""}</span>
        {level !== "expired" && <button disabled={!ids.length} onClick={() => onRelease(ids)}>Redistribuer la sélection ({ids.length})</button>}
        <button className="secondary" onClick={exportCsv} disabled={!rows.length}>⬇ CSV</button>
      </div>
      <AutoColumns id="MailQuarantine.2"><table><thead><tr>
        <th>{level !== "expired" && <input type="checkbox" onChange={(e) => toggleAll(e.target.checked)} />}</th>
        <th>Reçu</th><th>Type</th><th>Score</th><th>De</th><th>À</th><th>Sujet</th><th>Taille</th><th>État</th><th /></tr></thead>
        <tbody>{rows.map((q) => {
          const done = res.done?.[q.mail_id];
          return (
            <tr key={q.mail_id}>
              <td>{can(q) && <input type="checkbox" checked={!!sel[q.mail_id]} onChange={(e) => setRes({ ...res, sel: { ...sel, [q.mail_id]: e.target.checked } })} />}</td>
              <td>{when(q.at)}</td><td><Tone tone={q.content === "V" ? "bad" : q.content === "S" ? "warn" : "neutral"}>{q.content_label}</Tone></td>
              <td>{q.score ?? "—"}</td><td>{q.from || "<>"}</td><td>{q.to.join(", ")}</td><td>{q.subject}</td><td>{size(q.size)}</td>
              <td>{done === "ok" || q.released ? <Tone tone="good">libéré</Tone> : done ? <Tone tone="bad" >{done}</Tone>
                : q.stored ? <Tone tone="warn">en quarantaine</Tone> : q.quarantined ? <Tone>purgé</Tone> : <Tone>{q.delivery === "P" ? "distribué" : q.delivery || "traité"}</Tone>}</td>
              <td style={{ whiteSpace: "nowrap" }}>{q.stored && <button className="secondary" onClick={() => onOpen("quarantine", q)}>Voir</button>}{" "}
                {q.from && <button className="secondary" title="Proposer une règle pour cet expéditeur ou son domaine" onClick={() => onRule(q.from)}>Règle…</button>}</td>
            </tr>);
        })}</tbody></table></AutoColumns>
    </div>
  );
}

function Rules({ rules, reload, draft, setDraft, run, reason, needReason, setRules }) {
  const [busy, setBusy] = useState(false);
  const d = draft || { sender: "", recipient: "", wb: "-5" };
  const save = async (p) => {
    if (needReason()) return;
    setBusy(true);
    try { const r = await run({ action: "wblist_set", ...p, reason }); setRules(r); if (r.warning) window.alert(r.warning); if (p.wb !== "delete") setDraft(null); }
    catch (e) { window.alert(e.message); }
    setBusy(false);
  };
  const domain = d.sender.includes("@") ? d.sender.slice(d.sender.indexOf("@")) : "";
  return (
    <div>
      <div style={{ border: "1px solid var(--border)", borderRadius: 8, padding: 10, marginBottom: 10 }}>
        <strong>Nouvelle règle</strong>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "end", marginTop: 6 }}>
          <label>Expéditeur <input value={d.sender} onChange={(e) => setDraft({ ...d, sender: e.target.value })} placeholder="adresse ou @domaine" /></label>
          {domain && d.sender !== domain && <button className="secondary" onClick={() => setDraft({ ...d, sender: domain })}>tout {domain}</button>}
          <label>Pour <select value={d.recipient} onChange={(e) => setDraft({ ...d, recipient: e.target.value })}>
            <option value="">— destinataire —</option>
            {(rules?.recipients || []).map((u) => <option key={u.email} value={u.email}>{u.email === "@." ? "tout le serveur (@.)" : u.email}</option>)}</select></label>
          <label>Règle <select value={d.wb} onChange={(e) => setDraft({ ...d, wb: e.target.value })}>{WB.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
          <button disabled={busy || !d.sender || !d.recipient} onClick={() => save(d)}>{busy ? "⏳" : "Enregistrer"}</button>
        </div>
        <p className="muted" style={{ fontSize: 12, marginTop: 6 }}>
          Préférer « Adoucir » : l'adresse d'expéditeur se falsifie, une liste blanche laisse passer les usurpations (les virus restent bloqués).
          Jamais de liste blanche pour une banque, un service public ou un domaine qu'on usurpe souvent. « Liste noire » : pour les domaines d'hameçonnage
          avérés (bloqués avant analyse). Les règles s'appliquent aux nouveaux messages ; redistribuer ensuite ceux déjà en quarantaine.</p>
      </div>
      {!rules ? null : rules.loading ? <p className="muted">⏳ lecture des règles…</p> : rules.error ? <p style={{ color: "var(--danger)" }}>{rules.error}</p> : (
        <>
          {!rules.available && <p className="hub-warning">{rules.note || "Tables de règles absentes"} : règles par SQL indisponibles sur ce serveur.</p>}
          {rules.available && !rules.lookup_sql && <p className="hub-warning">Amavis ne consulte pas la base pour les règles (<code>@lookup_sql_dsn</code> absent) : les règles enregistrées ici restent sans effet tant que ce n'est pas activé.</p>}
          <AutoColumns id="MailQuarantine.3"><table><thead><tr><th>Expéditeur</th><th>Destinataire</th><th>Règle</th><th /></tr></thead>
            <tbody>{(rules.rules || []).map((r) => (
              <tr key={`${r.recipient}|${r.sender}`}><td>{r.sender}</td><td>{r.recipient}</td>
                <td><Tone tone={r.wb === "B" ? "bad" : r.wb === "W" ? "warn" : "neutral"}>{wbLabel(r.wb)}</Tone></td>
                <td><button className="secondary" disabled={busy} onClick={() => window.confirm(`Supprimer la règle ${r.sender} → ${r.recipient} ?`) && save({ sender: r.sender, recipient: r.recipient, wb: "delete" })}>Supprimer</button></td></tr>))}
              {!rules.rules?.length && <tr><td colSpan={4} className="muted">Aucune règle.</td></tr>}</tbody></table></AutoColumns>
          <button className="secondary" onClick={reload} style={{ marginTop: 6 }}>Relire</button>
        </>)}
    </div>
  );
}
