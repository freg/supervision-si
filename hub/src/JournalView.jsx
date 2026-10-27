// Tuile « Journal des chantiers » (livraison #795) : actes, surveillances, relances et interventions de chaque chantier,
// avec date, jour, heures de début / fin, durée, description non technique, résultat, statut et source. Week-ends et heures
// hors bureau (8 h 30 - 12 h 15, 14 h - 18 h) en rouge. Saisie, import (JSON ou CSV de l'export), export CSV pour Excel,
// et suggestions tirées des événements du hub (pilotage de la migration, PRA, sauvegardes, agents, constats critiques).
// Données : si-agent-api /journal. Logique pure : journalLib.js.
import { useCallback, useEffect, useMemo, useState } from "react";
import { fetchJournal, saveJournalEntry, deleteJournalEntry, importJournal, journalExportUrl, fetchJournalSuggestions, acceptJournalSuggestion } from "./siAgentClient.js";
import { NATURES, STATUTS, STATUT_TONE, fmtDay, weekday, durationMin, fmtDuration, offHour, isWeekend, emptyEntry, entryToForm, filterEntries, importPayload, totals } from "./journalLib.js";

import { useNavState } from "./navContext.js";   // #874
function EntryForm({ initial, chantiers, onSave, onCancel, busy }) {
  const [f, setF] = useState(entryToForm(initial));
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  return (
    <form className="infra-card jr-form" onSubmit={(e) => { e.preventDefault(); onSave(f); }}>
      <b>{f.id ? "Modifier l'entrée" : "Nouvelle entrée"}</b>
      <div className="jr-grid">
        <label>Chantier<input list="jr-chantiers" value={f.chantier} onChange={set("chantier")} required /></label>
        <datalist id="jr-chantiers">{chantiers.map((c) => <option key={c} value={c} />)}</datalist>
        <label>Date<input type="date" value={f.day} onChange={set("day")} /></label>
        <label>Début<input type="time" value={f.start} onChange={set("start")} /></label>
        <label>Fin<input type="time" value={f.end} onChange={set("end")} /></label>
        <label>Nature<select value={f.nature} onChange={set("nature")}>{NATURES.map((n) => <option key={n}>{n}</option>)}</select></label>
        <label>Statut<select value={f.statut} onChange={set("statut")}>{STATUTS.map((n) => <option key={n}>{n}</option>)}</select></label>
      </div>
      <label>Acte (intitulé court)<input value={f.acte} onChange={set("acte")} required maxLength={200} /></label>
      <label>Description (pour un lecteur non technicien)<textarea rows={3} value={f.description} onChange={set("description")} /></label>
      <label>Résultat<input value={f.resultat} onChange={set("resultat")} /></label>
      <label>Source<input value={f.source} onChange={set("source")} placeholder="étude du JJ/MM, prévision du JJ/MM, livraison #N…" /></label>
      <small className="infra-muted">{f.day ? `${weekday(f.day)}${durationMin(f) != null ? ` · durée ${fmtDuration(durationMin(f))}` : ""}${offHour(f.day, f.start) || offHour(f.day, f.end) ? " · hors heures de bureau" : ""}` : "sans date"}</small>
      <div><button type="submit" disabled={busy}>Enregistrer</button> <button type="button" className="secondary" onClick={onCancel}>Annuler</button></div>
    </form>
  );
}

export default function JournalView({ onBack, siAgentApiBase: api, username }) {
  const [v, setV] = useState(null);
  const [err, setErr] = useState(null);
  const [tab, setTab] = useNavState("JournalView", "tab", "journal");   // #874 : gardé au rechargement
  const [chantier, setChantier] = useState("");
  const [filt, setFilt] = useState({ q: "", nature: "", statut: "" });
  const [edit, setEdit] = useState(null);
  const [msg, setMsg] = useState(null);
  const [busy, setBusy] = useState(false);
  const [sugg, setSugg] = useState(null);
  const [days, setDays] = useState(30);
  const [impText, setImpText] = useState("");
  const [impName, setImpName] = useState("");
  const [impChantier, setImpChantier] = useState("");

  const load = useCallback(() => fetchJournal(api, chantier).then((d) => { setV(d); setErr(d?.error || null); }), [api, chantier]);
  useEffect(() => { load(); }, [load]);
  const loadSugg = useCallback(() => fetchJournalSuggestions(api, days).then((d) => setSugg(d?.suggestions || [])), [api, days]);
  useEffect(() => { if (tab === "suggestions") loadSugg(); }, [tab, loadSugg]);

  const act = async (fn, okText) => {
    setBusy(true);
    try { const r = await fn(); setMsg(r?.error ? { ok: false, text: r.error } : { ok: true, text: okText ? okText(r) : "enregistré" }); await load(); return r; } finally { setBusy(false); }
  };
  const rows = useMemo(() => filterEntries(v?.entries, filt), [v, filt]);
  const chs = v?.chantiers || [];
  const t = totals(v?.stats);

  return (
    <div className="infra-root">
      <div className="infra-top">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h2>Journal des chantiers</h2>
        {[["journal", "Journal"], ["suggestions", "Suggestions du hub"], ["import", "Import / export"]].map(([k, l]) => <button key={k} className={tab === k ? "" : "secondary"} onClick={() => setTab(k)}>{l}</button>)}
        <select value={chantier} onChange={(e) => setChantier(e.target.value)} title="Chantier affiché">
          <option value="">tous les chantiers</option>{chs.map((c) => <option key={c}>{c}</option>)}
        </select>
        {msg && <span className={msg.ok ? "infra-muted" : "infra-error"}>{msg.text}</span>}
      </div>
      {err && <p className="infra-error">{err}</p>}
      {v && tab === "journal" && (
        <>
          <div className="infra-kpis">
            <div className="infra-kpi"><span>entrées</span><b>{t.lignes}</b><small>{t.fait} réalisée(s) · {t.a_faire} à faire</small></div>
            <div className="infra-kpi"><span>temps tracé</span><b>{fmtDuration(t.minutes) || "0 h 00"}</b><small>actes avec début et fin</small></div>
            <div className="infra-kpi"><span>le week-end</span><b className={t.weekend ? "jr-off" : ""}>{t.weekend}</b></div>
            <div className="infra-kpi"><span>hors heures de bureau</span><b className={t.hors_heures ? "jr-off" : ""}>{t.hors_heures}</b><small>8 h 30 - 12 h 15, 14 h - 18 h</small></div>
          </div>
          {(v.stats || []).length > 1 && !chantier && (
            <div className="infra-table-wrap"><table className="infra-table">
              <thead><tr><th>Chantier</th><th>Entrées</th><th>Réalisées</th><th>En cours / planifiées</th><th>À faire</th><th>Du</th><th>Au</th><th>Temps tracé</th><th>Week-end</th><th>Hors heures</th>{NATURES.map((n) => <th key={n}>{n}</th>)}</tr></thead>
              <tbody>{v.stats.map((s) => (
                <tr key={s.chantier} className="jr-click" onClick={() => setChantier(s.chantier)}>
                  <td><b>{s.chantier}</b></td><td>{s.lignes}</td><td>{s.fait}</td><td>{s.en_cours}</td><td>{s.a_faire}</td><td>{fmtDay(s.premier)}</td><td>{fmtDay(s.dernier)}</td>
                  <td>{fmtDuration(s.minutes)}</td><td className={s.weekend ? "jr-off" : ""}>{s.weekend}</td><td className={s.hors_heures ? "jr-off" : ""}>{s.hors_heures}</td>
                  {NATURES.map((n) => <td key={n}>{s.natures?.[n] || 0}</td>)}
                </tr>))}</tbody>
            </table></div>
          )}
          <div className="jr-tools">
            <button onClick={() => setEdit(emptyEntry(chantier))}>+ Ajouter une entrée</button>
            <input placeholder="filtrer (acte, description, source…)" value={filt.q} onChange={(e) => setFilt({ ...filt, q: e.target.value })} />
            <select value={filt.nature} onChange={(e) => setFilt({ ...filt, nature: e.target.value })}><option value="">toutes natures</option>{NATURES.map((n) => <option key={n}>{n}</option>)}</select>
            <select value={filt.statut} onChange={(e) => setFilt({ ...filt, statut: e.target.value })}><option value="">tous statuts</option>{STATUTS.map((n) => <option key={n}>{n}</option>)}</select>
            <button className="secondary" onClick={() => window.open(journalExportUrl(api, chantier), "_blank", "noopener")}>Exporter (Excel, CSV)</button>
          </div>
          {edit && <EntryForm initial={edit} chantiers={chs} busy={busy} onCancel={() => setEdit(null)}
            onSave={(e) => act(async () => { const r = await saveJournalEntry(api, e, username); if (!r?.error) setEdit(null); return r; })} />}
          {!rows.length && <p className="infra-card">Aucune entrée{filt.q || filt.nature || filt.statut ? " pour ce filtre" : " : « + Ajouter une entrée », l'onglet « Suggestions du hub » ou un import"}.</p>}
          {rows.length > 0 && (
            <div className="infra-table-wrap infra-scroll"><table className="infra-table jr-table">
              <thead><tr>{!chantier && <th>Chantier</th>}<th>Date</th><th>Jour</th><th>Début</th><th>Fin</th><th>Durée</th><th>Nature</th><th>Acte</th><th>Résultat</th><th>Statut</th><th>Source</th><th /></tr></thead>
              <tbody>{rows.map((e) => (
                <tr key={e.id}>
                  {!chantier && <td>{e.chantier}</td>}
                  <td className={isWeekend(e.day) ? "jr-off" : ""}>{fmtDay(e.day)}</td>
                  <td className={isWeekend(e.day) ? "jr-off" : ""}>{weekday(e.day)}</td>
                  <td className={offHour(e.day, e.start) ? "jr-off" : ""}>{e.start || ""}</td>
                  <td className={offHour(e.day, e.end) ? "jr-off" : ""}>{e.end || ""}</td>
                  <td>{fmtDuration(durationMin(e))}</td>
                  <td>{e.nature}</td>
                  <td><b>{e.acte}</b>{e.description && <small className="jr-desc">{e.description}</small>}</td>
                  <td>{e.resultat}</td>
                  <td><span className={`jr-statut ${STATUT_TONE[e.statut] || ""}`}>{e.statut}</span></td>
                  <td className="infra-muted">{e.source}</td>
                  <td className="jr-actions">
                    <button className="secondary mig-small" onClick={() => setEdit(e)}>Modifier</button>
                    <button className="secondary mig-small" disabled={busy} onClick={() => { if (window.confirm(`Supprimer « ${e.acte} » ?`)) act(() => deleteJournalEntry(api, e.id), () => "entrée supprimée"); }}>Supprimer</button>
                  </td>
                </tr>))}</tbody>
            </table></div>
          )}
        </>
      )}
      {tab === "suggestions" && (
        <>
          <p className="infra-muted">Événements du hub qui ressemblent à des actes de chantier (pilotage de la migration, rapatriements, PRA, maintenances, sauvegardes, agents hors ligne, constats critiques) et ne sont pas encore au journal. Un clic les ajoute ; l'intitulé se corrige ensuite dans le journal.</p>
          <div className="jr-tools">
            <label>sur les <select value={days} onChange={(e) => setDays(Number(e.target.value))}>{[7, 30, 90, 365].map((d) => <option key={d} value={d}>{d} derniers jours</option>)}</select></label>
            <button className="secondary" onClick={loadSugg}>Actualiser</button>
          </div>
          {sugg && !sugg.length && <p className="infra-card">Aucune suggestion sur la période.</p>}
          {sugg && sugg.length > 0 && (
            <div className="infra-table-wrap infra-scroll"><table className="infra-table jr-table">
              <thead><tr><th>Date</th><th>Heure</th><th>Chantier proposé</th><th>Nature</th><th>Événement</th><th /></tr></thead>
              <tbody>{sugg.map((s) => (
                <tr key={s.event_id}>
                  <td className={isWeekend(s.day) ? "jr-off" : ""}>{fmtDay(s.day)} {weekday(s.day)}</td>
                  <td className={offHour(s.day, s.start) ? "jr-off" : ""}>{s.start}</td>
                  <td>{s.chantier}</td><td>{s.nature}</td>
                  <td>{s.acte}<small className="jr-desc">{s.source}</small></td>
                  <td className="jr-actions">
                    <button className="mig-small" disabled={busy} onClick={() => act(() => acceptJournalSuggestion(api, s.event_id, chantier || "", username), () => "ajouté au journal").then(loadSugg)}>Ajouter{chantier ? ` à « ${chantier} »` : ""}</button>
                  </td>
                </tr>))}</tbody>
            </table></div>
          )}
        </>
      )}
      {tab === "import" && (
        <div className="infra-card jr-form">
          <b>Importer</b>
          <p className="infra-muted">JSON (liste d'entrées : chantier, day, start, end, nature, acte, description, resultat, statut, source) ou CSV au format de l'export (colonnes Chantier;Date;Début;Fin;Nature;Acte;Description;Résultat;Statut;Source). Les doublons (même chantier, jour, heure de début et acte) sont ignorés.</p>
          <input type="file" accept=".json,.csv,.txt" onChange={(e) => { const file = e.target.files?.[0]; if (!file) return; setImpName(file.name); file.text().then(setImpText); }} />
          <label>Chantier à appliquer aux lignes qui n'en ont pas<input list="jr-chantiers-imp" value={impChantier} onChange={(e) => setImpChantier(e.target.value)} /></label>
          <datalist id="jr-chantiers-imp">{chs.map((c) => <option key={c} value={c} />)}</datalist>
          <textarea rows={6} value={impText} onChange={(e) => setImpText(e.target.value)} placeholder="… ou coller ici le contenu JSON / CSV" />
          <div>
            <button disabled={busy || !impText.trim()} onClick={() => {
              const p = importPayload(impText, impName, impChantier);
              if (p.error) { setMsg({ ok: false, text: p.error }); return; }
              act(() => importJournal(api, p, username), (r) => `${r.added} ajoutée(s), ${r.skipped} doublon(s) ignoré(s)${r.errors?.length ? `, ${r.errors.length} ligne(s) refusée(s) : ${r.errors.slice(0, 3).join(" ; ")}` : ""}`);
            }}>Importer</button>
          </div>
          <b>Exporter</b>
          <p><button className="secondary" onClick={() => window.open(journalExportUrl(api, chantier), "_blank", "noopener")}>Exporter {chantier ? `« ${chantier} »` : "tout le journal"} (CSV pour Excel)</button></p>
        </div>
      )}
    </div>
  );
}
