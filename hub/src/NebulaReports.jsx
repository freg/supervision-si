// Rapports et alertes des anomalies réseau (livraison #703) : exports CSV /
// Excel / PDF, récapitulatif quotidien et alertes d'urgence par courriel
// (notify-api), tout paramétrable ; suivi des anomalies et journal d'envoi.
// Données : nebula-api /report/*. Enregistrer et « Envoyer un test » exigent
// le droit `manage` (comme Valider une anomalie).
import { useEffect, useState } from "react";

async function call(url, init) {
  const r = await fetch(url, { credentials: "include", ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `HTTP ${r.status}`);
  return j;
}

const SEVS = [["haute", "Haute"], ["moyenne", "Moyenne"], ["basse", "Basse"], ["info", "Info"]];
const DAYS = [[1, "lun"], [2, "mar"], [3, "mer"], [4, "jeu"], [5, "ven"], [6, "sam"], [7, "dim"]];
const when = (t) => (t ? new Date(t * 1000).toLocaleString("fr-FR") : "—");

export default function NebulaReports({ nebulaApiBase, groups, login }) {
  const base = `${nebulaApiBase}/report`;
  const [data, setData] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [recipients, setRecipients] = useState("");
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState("");

  const load = async () => {
    try { const d = await call(`${base}/settings`); setData(d); setCfg(d.settings); setRecipients(d.settings.recipients.join(", ")); }
    catch (e) { setMsg({ error: e.message }); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [nebulaApiBase]);

  if (!cfg) return msg?.error ? <p style={{ color: "var(--danger)" }}>{msg.error}</p> : <p className="muted">Lecture des réglages…</p>;
  const setD = (k, v) => setCfg({ ...cfg, daily: { ...cfg.daily, [k]: v } });
  const setU = (k, v) => setCfg({ ...cfg, urgent: { ...cfg.urgent, [k]: v } });
  const toggle = (list, v) => (list.includes(v) ? list.filter((x) => x !== v) : [...list, v].sort());

  const save = async () => {
    setBusy("save"); setMsg(null);
    try {
      await call(`${base}/settings`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ groups, user: login, settings: { ...cfg, recipients } }) });
      setMsg({ ok: "Réglages enregistrés." }); await load();
    } catch (e) { setMsg({ error: e.message }); }
    setBusy("");
  };
  const sendTest = async () => {
    setBusy("test"); setMsg(null);
    try { const r = await call(`${base}/send`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ groups, user: login, kind: "test" }) });
      setMsg({ ok: `Récapitulatif de test : ${r.status}${r.recipients != null ? `, ${r.recipients} destinataire(s)` : ""}${r.reason ? ` (${r.reason})` : ""}` }); await load(); }
    catch (e) { setMsg({ error: e.message }); }
    setBusy("");
  };
  const box = { border: "1px solid var(--border)", borderRadius: 8, padding: 12, marginBottom: 12 };

  return (
    <div style={{ width: "100%" }}>
      <div style={box}>
        <strong>Rapport des anomalies</strong> <span className="muted">(tous les sites, anomalies masquées exclues)</span>
        <div style={{ display: "flex", gap: 8, marginTop: 8, flexWrap: "wrap" }}>
          {[["csv", "CSV"], ["xlsx", "Excel"], ["pdf", "PDF"]].map(([f, l]) => <a key={f} className="button secondary" href={`${base}/anomalies?format=${f}`} download>⬇ {l}</a>)}
          <a className="button secondary" href={`${base}/anomalies?format=xlsx&hidden=1`} download>⬇ Excel (masquées comprises)</a>
        </div>
      </div>

      {!data.notify_configured && <p className="hub-warning">Envoi de courriels non configuré pour nebula-api (NOTIFY_INTERNAL_TOKEN absent du .env) : les réglages s'enregistrent, rien ne part.</p>}

      <div style={box}>
        <strong>Destinataires</strong> <span className="muted">(en plus des groupes affectés aux actions « nebula.* » dans la tuile Notifications)</span>
        <textarea rows={2} style={{ width: "100%", marginTop: 6 }} value={recipients} onChange={(e) => setRecipients(e.target.value)} placeholder="adresse@exemple.fr, autre@exemple.fr" />
        <label className="muted">Contrôle toutes les <input type="number" min={5} max={120} value={cfg.check_minutes} onChange={(e) => setCfg({ ...cfg, check_minutes: +e.target.value })} style={{ width: 60 }} /> min</label>
      </div>

      <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
        <div style={{ ...box, flex: "1 1 360px" }}>
          <label><input type="checkbox" checked={cfg.daily.enabled} onChange={(e) => setD("enabled", e.target.checked)} /> <strong>Récapitulatif quotidien</strong></label>
          <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
            <label>Heure <input type="time" value={cfg.daily.time} onChange={(e) => setD("time", e.target.value)} /></label>
            <div>Jours {DAYS.map(([d, l]) => <label key={d} style={{ marginRight: 6 }}><input type="checkbox" checked={cfg.daily.weekdays.includes(d)} onChange={() => setD("weekdays", toggle(cfg.daily.weekdays, d))} /> {l}</label>)}</div>
            <div>Pièces jointes {["xlsx", "pdf", "csv"].map((f) => <label key={f} style={{ marginRight: 6 }}><input type="checkbox" checked={cfg.daily.formats.includes(f)} onChange={() => setD("formats", toggle(cfg.daily.formats, f))} /> {f.toUpperCase()}</label>)}</div>
            <label>Gravité minimale <select value={cfg.daily.min_severity} onChange={(e) => setD("min_severity", e.target.value)}>{SEVS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label><input type="checkbox" checked={cfg.daily.only_if_anomalies} onChange={(e) => setD("only_if_anomalies", e.target.checked)} /> seulement s'il y a des anomalies</label>
            <span className="muted">Prochain envoi : {data.next_daily ? new Date(data.next_daily).toLocaleString("fr-FR") : "—"} · dernier : {when(data.daily_last)}</span>
          </div>
        </div>
        <div style={{ ...box, flex: "1 1 360px" }}>
          <label><input type="checkbox" checked={cfg.urgent.enabled} onChange={(e) => setU("enabled", e.target.checked)} /> <strong>Alerte d'urgence</strong> (apparition d'une anomalie)</label>
          <div style={{ marginTop: 8, display: "grid", gap: 6 }}>
            <label>Gravité minimale <select value={cfg.urgent.min_severity} onChange={(e) => setU("min_severity", e.target.value)}>{SEVS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
            <label>Attendre <input type="number" min={0} max={1440} value={cfg.urgent.delay_minutes} onChange={(e) => setU("delay_minutes", +e.target.value)} style={{ width: 70 }} /> min sans retour à la normale avant d'alerter</label>
            <label>Rappel toutes les <input type="number" min={0} max={168} value={cfg.urgent.repeat_hours} onChange={(e) => setU("repeat_hours", +e.target.value)} style={{ width: 60 }} /> h tant que l'anomalie dure (0 = jamais)</label>
            <label><input type="checkbox" checked={cfg.urgent.notify_recovery} onChange={(e) => setU("notify_recovery", e.target.checked)} /> prévenir du retour à la normale</label>
          </div>
        </div>
      </div>

      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 12 }}>
        <button type="button" disabled={!!busy} onClick={save}>{busy === "save" ? "⏳" : "Enregistrer"}</button>
        <button type="button" className="secondary" disabled={!!busy} onClick={sendTest}>{busy === "test" ? "⏳ envoi…" : "Envoyer un récapitulatif de test"}</button>
        {msg?.ok && <span style={{ color: "var(--ok, green)" }}>{msg.ok}</span>}
        {msg?.error && <span style={{ color: "var(--danger)" }}>{msg.error}</span>}
      </div>

      <details style={box}>
        <summary><strong>Anomalies suivies</strong> ({data.tracked.length}) · résolues depuis 24 h ({data.resolved_24h.length})</summary>
        <table><thead><tr><th>Gravité</th><th>Site</th><th>Constat</th><th>Depuis</th><th>Alerté</th></tr></thead>
          <tbody>{data.tracked.map((e) => <tr key={`${e.site_id}|${e.id}`}><td>{e.severity}</td><td>{e.site}</td><td>{e.message}</td><td>{when(e.first_seen)}</td><td>{when(e.notified_at)}</td></tr>)}
            {data.resolved_24h.map((e) => <tr key={`r${e.site_id}|${e.id}|${e.resolved_at}`} className="muted"><td>résolue</td><td>{e.site}</td><td>{e.message}</td><td>{when(e.first_seen)}</td><td>fin {when(e.resolved_at)}</td></tr>)}</tbody></table>
      </details>
      <details style={box}>
        <summary><strong>Journal d'envoi</strong></summary>
        <ul style={{ fontSize: 13 }}>{data.log.map((l, i) => <li key={i}>{when(l.at)} · <code>{l.event}</code> · {l.text}</li>)}</ul>
      </details>
    </div>
  );
}
