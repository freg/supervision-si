import React, { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchUpsStatus, fetchUpsList, fetchUps, createUps, updateUps, deleteUps, pollUps, testUps,
  fetchUpsReadings, fetchUpsSeries,
} from "./upsClient.js";
import {
  orderedFields, fieldLabel, fieldTone, deviceStatus, formatAge, formatInterval, summarizeLast,
  numericKeys, toLineSeries, timelineRows, TIME_WINDOWS, windowStart, displayValue,
} from "./upsMonitor.js";
import { buildLinePath } from "./netprobeAgents.js";
import ZoomableChart from "./components/ZoomableChart.jsx";

// Tuile « UPS » (livraison #415), demandée en urgence : liste des
// onduleurs (site / IP / utilisateur / mot de passe), relevé automatique
// par ups-monitor-api (page d'état HTTP de la carte réseau, 1 h par
// défaut), fiche d'état en tableau, archive consultable en timeline.
// Toute la logique non-React est dans upsMonitor.js (testée à part).

const LINE_W = 600;
const LINE_H = 120;
const REFRESH_MS = 60000;

const EMPTY_FORM = {
  name: "", site: "", host: "", scheme: "http", path: "/index.htm",
  username: "", password: "", poll_interval_seconds: "", enabled: true, notes: "",
};

function Tone({ tone, children }) {
  return <span className={`np-tone ${tone || "neutral"}`}>{children}</span>;
}

function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR");
}

export default function UpsView({ onBack, upsApiBase }) {
  const [status, setStatus] = useState(null);
  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [now, setNow] = useState(Date.now());

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState(EMPTY_FORM);
  const [editingId, setEditingId] = useState(null);
  const [testResult, setTestResult] = useState(null);
  const [busy, setBusy] = useState(false);

  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [readings, setReadings] = useState([]);
  const [series, setSeries] = useState([]);
  const [seriesKey, setSeriesKey] = useState("input_voltage");
  const [windowId, setWindowId] = useState("7d");
  const [showTimelineTable, setShowTimelineTable] = useState(true);

  const load = useCallback(async () => {
    const [st, list] = await Promise.all([fetchUpsStatus(upsApiBase), fetchUpsList(upsApiBase)]);
    setStatus(st);
    setDevices(list);
    setError(st?.error || null);
    setLoading(false);
    setNow(Date.now());
  }, [upsApiBase]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [load]);

  const loadDetail = useCallback(async (upsId, key = seriesKey, win = windowId) => {
    if (!upsId) return;
    const start = windowStart(win);
    const [d, rows, pts] = await Promise.all([
      fetchUps(upsApiBase, upsId),
      fetchUpsReadings(upsApiBase, upsId, { start, limit: 2000 }),
      fetchUpsSeries(upsApiBase, upsId, key, { start, limit: 2000 }),
    ]);
    setDetail(d?.error ? null : d);
    setReadings(rows);
    setSeries(pts);
  }, [upsApiBase, seriesKey, windowId]);

  useEffect(() => {
    if (selectedId) loadDetail(selectedId);
    else { setDetail(null); setReadings([]); setSeries([]); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedId, seriesKey, windowId]);

  const defaultInterval = status?.settings?.default_interval_seconds || 3600;

  // --- Formulaire ---
  function openCreate() {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setTestResult(null);
    setShowForm(true);
  }

  function openEdit(d) {
    setEditingId(d.id);
    setForm({
      name: d.name, site: d.site || "", host: d.host, scheme: d.scheme || "http", path: d.path || "/index.htm",
      username: d.username || "", password: "", poll_interval_seconds: d.poll_interval_seconds || "",
      enabled: d.enabled, notes: d.notes || "",
    });
    setTestResult(null);
    setShowForm(true);
  }

  function payload() {
    const p = { ...form };
    if (p.poll_interval_seconds === "") p.poll_interval_seconds = null;
    if (editingId && !p.password) delete p.password;
    return p;
  }

  async function handleTest() {
    setBusy(true);
    setTestResult(null);
    // En modification sans nouveau mot de passe, l'essai n'a pas le mot de
    // passe stocké : on relève l'onduleur enregistré à la place.
    const r = editingId && !form.password ? await pollUps(upsApiBase, editingId) : await testUps(upsApiBase, payload());
    setTestResult(r);
    setBusy(false);
  }

  async function handleSave(e) {
    e.preventDefault();
    setBusy(true);
    const r = editingId ? await updateUps(upsApiBase, editingId, payload()) : await createUps(upsApiBase, payload());
    setBusy(false);
    if (r?.error) { setError(r.error); return; }
    setError(null);
    setShowForm(false);
    setNotice(editingId ? "Onduleur modifié." : "Onduleur ajouté -- premier relevé au prochain passage de l'automate (≤ 1 min), ou « Relever » tout de suite.");
    await load();
    if (!editingId && r?.id) setSelectedId(r.id);
  }

  async function handlePoll(d) {
    setBusy(true);
    const r = await pollUps(upsApiBase, d.id);
    setBusy(false);
    setNotice(r?.ok ? `${d.name} : relevé effectué (${r.duration_ms} ms).` : `${d.name} : ${r?.error || "échec"}`);
    await load();
    if (selectedId === d.id) loadDetail(d.id);
  }

  async function handleDelete(d) {
    if (!window.confirm(`Supprimer « ${d.name} » et tout son historique de relevés ?`)) return;
    const r = await deleteUps(upsApiBase, d.id);
    if (r?.error) { setError(r.error); return; }
    if (selectedId === d.id) setSelectedId(null);
    await load();
  }

  // --- Dérivés d'affichage ---
  const fiche = detail?.latest_ok || null;
  const fields = useMemo(() => (fiche ? orderedFields(fiche.sections) : []), [fiche]);
  const keys = useMemo(() => numericKeys(fiche?.fields), [fiche]);
  const line = useMemo(() => buildLinePath(toLineSeries(series), LINE_W, LINE_H, 6), [series]);
  const rows = useMemo(() => timelineRows(readings), [readings]);
  const unit = series.find((p) => p.unit)?.unit || "";
  const selected = devices.find((d) => d.id === selectedId) || null;

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🔋 Onduleurs (UPS)</h1>
      </div>

      {error && <p className="hub-error">{error}</p>}
      {notice && <p className="muted ups-notice">{notice} <button className="secondary" onClick={() => setNotice(null)}>✕</button></p>}

      <div className="hub-card hub-settings-section ups-status-card">
        {status && !status.error ? (
          <p style={{ margin: 0 }}>
            {status.counts.devices} onduleur(s), {status.counts.enabled} relevé(s) automatiquement toutes les {formatInterval(status.settings.default_interval_seconds)} par défaut
            {" · "}{status.counts.readings} relevé(s) archivés ({status.settings.retention_days ? `${status.settings.retention_days} jours conservés` : "sans limite"})
            {status.counts.alarms > 0 && <> · <Tone tone="bad">{status.counts.alarms} en alarme</Tone></>}
            {status.counts.unreachable > 0 && <> · <Tone tone="bad">{status.counts.unreachable} injoignable(s)</Tone></>}
            {!status.settings.poll_enabled && <> · <Tone tone="warn">automate désactivé (UPS_POLL_ENABLED)</Tone></>}
            {!status.settings.secrets_encrypted && (
              <><br /><Tone tone="warn">⚠ mots de passe stockés en clair -- définir UPS_CRED_PASSPHRASE et UPS_CRED_SALT (voir ups-monitor/README.md)</Tone></>
            )}
          </p>
        ) : (
          <p className="muted" style={{ margin: 0 }}>{loading ? "Chargement…" : "ups-monitor-api injoignable."}</p>
        )}
      </div>

      <div className="ups-toolbar">
        <h2 style={{ margin: 0 }}>Onduleurs ({devices.length})</h2>
        <button className="secondary" onClick={() => (showForm ? setShowForm(false) : openCreate())}>{showForm ? "✕ Fermer" : "+ Ajouter"}</button>
        <button className="secondary" onClick={load} disabled={busy}>⟳ Rafraîchir</button>
      </div>

      {showForm && (
        <form className="hub-card hub-settings-section ups-form" onSubmit={handleSave}>
          <h3 style={{ marginTop: 0 }}>{editingId ? "Modifier l'onduleur" : "Nouvel onduleur"}</h3>
          <div className="ups-form-grid">
            <label>Nom <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required placeholder="Salle serveurs" /></label>
            <label>Site <input value={form.site} onChange={(e) => setForm({ ...form, site: e.target.value })} placeholder="Siège" /></label>
            <label>IP / nom <input value={form.host} onChange={(e) => setForm({ ...form, host: e.target.value })} required placeholder="192.168.1.107" /></label>
            <label>Schéma
              <select value={form.scheme} onChange={(e) => setForm({ ...form, scheme: e.target.value })}>
                <option value="http">http</option><option value="https">https</option>
              </select>
            </label>
            <label>Page <input value={form.path} onChange={(e) => setForm({ ...form, path: e.target.value })} placeholder="/index.htm" /></label>
            <label>Utilisateur <input value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} autoComplete="off" /></label>
            <label>Mot de passe
              <input type="password" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} autoComplete="new-password" placeholder={editingId ? "(inchangé)" : ""} />
            </label>
            <label>Fréquence (s)
              <input type="number" min="30" step="30" value={form.poll_interval_seconds} onChange={(e) => setForm({ ...form, poll_interval_seconds: e.target.value })} placeholder={`${defaultInterval} (défaut)`} />
            </label>
            <label className="ups-form-check"><input type="checkbox" checked={!!form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} /> relevé automatique</label>
            <label className="ups-form-wide">Notes <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></label>
          </div>
          <p className="muted" style={{ margin: "8px 0" }}>
            Requête envoyée : <code>{form.scheme}://{form.username ? `${form.username}:•••@` : ""}{form.host || "ip"}{form.path || "/index.htm"}</code>
            {" "}-- l'identifiant devient une authentification HTTP Basic, comme dans le navigateur.
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="secondary" onClick={handleTest} disabled={busy || !form.host}>🔎 Tester la requête</button>
            <button type="submit" className="primary" disabled={busy}>{editingId ? "Enregistrer" : "Ajouter"}</button>
          </div>
          {testResult && (
            <div className={`ups-test-result ${testResult.ok ? "ok" : "bad"}`}>
              {testResult.ok ? (
                <>
                  <Tone tone="good">✔ page reçue et reconnue</Tone> -- {Object.keys(testResult.fields || {}).length} champ(s), état {testResult.state}
                  {testResult.system_time && <> · heure de l'onduleur : {testResult.system_time}</>}
                  {testResult.fields?.model && <> · {testResult.fields.model.value}</>}
                  {testResult.resolved_path && testResult.resolved_path !== (form.path || "/index.htm") && (
                    <> · <Tone tone="warn">fiche trouvée dans la frame <code>{testResult.resolved_path}</code></Tone> ({testResult.pages_visited} pages lues -- mettre ce chemin dans « Page » évite les lectures intermédiaires)</>
                  )}
                </>
              ) : (
                <Tone tone="bad">✖ {testResult.error || "échec"}</Tone>
              )}
            </div>
          )}
        </form>
      )}

      {loading ? (
        <p className="muted">Chargement…</p>
      ) : devices.length === 0 ? (
        <p className="muted">Aucun onduleur déclaré -- « + Ajouter » : nom, site, IP, utilisateur, mot de passe.</p>
      ) : (
        <div className="hub-table-scroll">
          <table>
            <thead>
              <tr><th>Nom</th><th>Site</th><th>Adresse</th><th>État</th><th>Dernier relevé</th><th>Mesures</th><th>Fréquence</th><th className="ups-actions-head"></th></tr>
            </thead>
            <tbody>
              {devices.map((d) => {
                const st = deviceStatus(d, now, 2.5, defaultInterval);
                const age = d.last_polled_at ? (now - Date.parse(d.last_polled_at)) / 1000 : null;
                return (
                  <tr key={d.id} className={`ups-row${selectedId === d.id ? " active" : ""}${d.enabled ? "" : " inactive"}`} onClick={() => setSelectedId(selectedId === d.id ? null : d.id)}>
                    <td><strong>{d.name}</strong>{d.notes && <div className="muted" style={{ fontSize: 11 }}>{d.notes}</div>}</td>
                    <td>{d.site || <span className="muted">—</span>}</td>
                    <td><code>{d.host}</code></td>
                    <td><Tone tone={st.tone}>{st.text}</Tone></td>
                    <td className="muted" title={when(d.last_polled_at)}>{age == null ? "—" : `il y a ${formatAge(age)}`}</td>
                    <td className="muted">{summarizeLast(d.last_summary) || "—"}</td>
                    <td className="muted">{formatInterval(d.poll_interval_seconds || defaultInterval)}{!d.poll_interval_seconds && " (défaut)"}</td>
                    <td className="ups-actions" onClick={(e) => e.stopPropagation()}>
                      <button className="secondary" onClick={() => handlePoll(d)} disabled={busy} title="Relever maintenant">⟳</button>
                      <button className="secondary" onClick={() => openEdit(d)} title="Modifier">✎</button>
                      <button className="secondary" onClick={() => handleDelete(d)} title="Supprimer">🗑</button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {selected && (
        <div className="hub-card hub-settings-section ups-detail">
          <h2 style={{ marginTop: 0 }}>🔋 {selected.name} <span className="muted" style={{ fontWeight: 400, fontSize: 13 }}>{selected.site} · {detail?.url || selected.host}</span></h2>

          {detail?.latest && !detail.latest.ok && (
            <p className="hub-error">
              Dernier relevé le {when(detail.latest.polled_at)} en échec : {detail.latest.error}
              {fiche && <> -- fiche ci-dessous : dernière réussie, le {when(fiche.polled_at)}.</>}
            </p>
          )}

          <h3>Fiche d'état</h3>
          {!fiche ? (
            <p className="muted">Aucune fiche encore -- « ⟳ » pour relever maintenant.</p>
          ) : (
            <>
              <p className="muted" style={{ marginTop: -6 }}>
                Relevé le {when(fiche.polled_at)}
                {fiche.system_time && <> · heure de l'onduleur : {fiche.system_time}</>}
                {" · "}état global : <Tone tone={fiche.state === "ok" ? "good" : fiche.state === "alarm" ? "bad" : "neutral"}>{fiche.state}</Tone>
                {fiche.state_reasons?.length > 0 && <> ({fiche.state_reasons.join(" ; ")})</>}
                {fiche.resolved_path && fiche.resolved_path !== (selected.path || "/index.htm") && (
                  <> · <Tone tone="warn">lue dans la frame <code>{fiche.resolved_path}</code></Tone> (la page configurée est un conteneur ; « ✎ » pour fixer « Page » à ce chemin)</>
                )}
              </p>
              <div className="hub-table-scroll">
                <table className="ups-fiche">
                  <thead><tr><th>Section</th><th>Champ</th><th>Valeur</th></tr></thead>
                  <tbody>
                    {fields.map((f) => (
                      <tr key={`${f.section}-${f.key}`}>
                        <td className="muted">{f.section}</td>
                        <td title={f.key}>{fieldLabel(f.key, f.label)}</td>
                        <td><Tone tone={fieldTone(f)}>{displayValue(f) || <span className="muted">(vide)</span>}</Tone></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          )}

          <h3>Timeline</h3>
          <div className="ups-timeline-controls">
            <label>Fenêtre
              <select value={windowId} onChange={(e) => setWindowId(e.target.value)}>
                {TIME_WINDOWS.map((w) => <option key={w.id} value={w.id}>{w.label}</option>)}
              </select>
            </label>
            <label>Courbe
              <select value={seriesKey} onChange={(e) => setSeriesKey(e.target.value)}>
                {(keys.length ? keys : [seriesKey]).map((k) => <option key={k} value={k}>{fieldLabel(k)}</option>)}
              </select>
            </label>
            <span className="muted">{readings.length} relevé(s) dans la fenêtre · {readings.filter((r) => !r.ok).length} échec(s)</span>
          </div>
          {line.path ? (
            <div className="np-line-wrap">
              <ZoomableChart viewBox={`0 0 ${LINE_W} ${LINE_H}`} preserveAspectRatio="none" className="ups-line-svg" label={`${fieldLabel(seriesKey)} dans le temps`}>
                <path d={line.path} className="np-line-path" />
                {line.points.map((p, i) => (
                  <circle key={i} cx={p.x} cy={p.y} r="2.5" className="np-line-point">
                    <title>{when(p.at)} : {p.value} {unit}</title>
                  </circle>
                ))}
              </ZoomableChart>
              <div className="np-line-caption muted">
                min {line.min} {unit} · max {line.max} {unit} · de {when(series[0]?.at)} à {when(series[series.length - 1]?.at)}
              </div>
            </div>
          ) : (
            <p className="muted">Pas assez de relevés réussis pour tracer {fieldLabel(seriesKey)} (2 minimum).</p>
          )}

          <button className="secondary na-section-toggle" onClick={() => setShowTimelineTable((v) => !v)} aria-expanded={showTimelineTable} style={{ marginTop: 8 }}>
            {showTimelineTable ? "▾" : "▸"} Relevés ({rows.length})
          </button>
          {showTimelineTable && rows.length > 0 && (
            <div className="hub-table-scroll ups-timeline-table">
              <table>
                <thead><tr><th>Quand</th><th>État</th><th>Entrée</th><th>Sortie</th><th>Charge</th><th>Batterie</th><th>Durée</th></tr></thead>
                <tbody>
                  {[...rows].reverse().map((r) => (
                    <tr key={r.id} className={r.ok ? "" : "ups-reading-failed"}>
                      <td className="muted">{when(r.polled_at)}</td>
                      <td>
                        {r.ok
                          ? <Tone tone={r.state === "ok" ? "good" : r.state === "alarm" ? "bad" : "neutral"}>{r.state}{r.state_reasons?.length ? ` (${r.state_reasons.join(" ; ")})` : ""}</Tone>
                          : <Tone tone="bad">échec : {r.error}</Tone>}
                      </td>
                      <td className={r.changes.includes("input_voltage") ? "ups-changed" : ""}>{r.input_voltage ?? "—"}</td>
                      <td className={r.changes.includes("output_voltage") ? "ups-changed" : ""}>{r.output_voltage ?? "—"}</td>
                      <td className={r.changes.includes("output_load") ? "ups-changed" : ""}>{r.output_load != null ? `${r.output_load} %` : "—"}</td>
                      <td className={r.changes.includes("battery_capacity") ? "ups-changed" : ""}>{r.battery_capacity != null ? `${r.battery_capacity} %` : "—"}</td>
                      <td className="muted">{r.duration_ms != null ? `${r.duration_ms} ms` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
