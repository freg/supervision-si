import React, { useState, useEffect, useCallback } from "react";
import { listSources, createSource, updateSource, deleteSource, rotateToken, sourceLog, profiles, runAnalysis, listLinks, decideLink, createLink, search, related, listRows } from "./datasyncClient.js";
import { presenceBadge, sourceStats, connectorConfig, groupLinks, rowSummary, groupNodes } from "./datasyncLib.js";
import HubIcon from "./HubIcon.jsx";

// Tuile « Synchronisation centrale » (hub), livraison #652 -- liaison de
// synchronisation unidirectionnelle des serveurs / applications / bases vers le
// SGBD central du hub (datasync-api) : une source → le central = une API source
// centrale (jeton par source, connecteur autonome). Quatre volets : Sources
// (présence, statistiques), Analyse (profils, correspondances, relations
// déduites, validation), Recherche (plein texte transversal), Relations
// (depuis une ligne, les lignes en relation sémantique à N niveaux).
// Non vérifié en navigateur (pas de `npm run build`) ; logique pure testée sous Node.

const TABS = [["sources", "Sources"], ["analysis", "Analyse"], ["search", "Recherche"], ["relations", "Relations"]];

function RowCard({ n, onRelated }) {
  return (
    <div className="ds-row">
      <div className="ds-row-head"><b>{n.source}</b> › {n.table} <code>#{n.pk}</code>{onRelated && <button className="secondary ds-mini" onClick={() => onRelated(n)}>relations</button>}</div>
      <div className="muted">{rowSummary(n.row, 8)}</div>
    </div>
  );
}

export default function DataSyncView({ onBack, datasyncApiBase, login }) {
  const [tab, setTab] = useState("sources");
  const [sources, setSources] = useState([]);
  const [presenceS, setPresenceS] = useState(600);
  const [form, setForm] = useState(null);           // {name, kind, notes}
  const [token, setToken] = useState(null);          // {source, token}
  const [log, setLog] = useState(null);              // {source, entries}
  const [prof, setProf] = useState([]);
  const [links, setLinks] = useState([]);
  const [manual, setManual] = useState(null);
  const [q, setQ] = useState(""); const [qSource, setQSource] = useState(""); const [results, setResults] = useState(null);
  const [rel, setRel] = useState(null); const [depth, setDepth] = useState(1); const [pick, setPick] = useState({ source: "", table: "", pk: "" });
  const [browse, setBrowse] = useState(null);
  const [busy, setBusy] = useState(""); const [error, setError] = useState(null); const [notice, setNotice] = useState(null);

  const refresh = useCallback(async () => { const r = await listSources(datasyncApiBase); if (r.error) setError(r.error); else { setSources(r.sources || []); setPresenceS(r.presence_s || 600); } }, [datasyncApiBase]);
  useEffect(() => { refresh(); const id = setInterval(refresh, 30000); return () => clearInterval(id); }, [refresh]);
  useEffect(() => { if (tab === "analysis") { profiles(datasyncApiBase).then((r) => !r.error && setProf(r.tables || [])); listLinks(datasyncApiBase).then((r) => !r.error && setLinks(r.links || [])); } }, [tab, datasyncApiBase]);

  async function saveSource() {
    setBusy("source"); setError(null);
    const r = form.id ? await updateSource(datasyncApiBase, form.id, form) : await createSource(datasyncApiBase, form); setBusy("");
    if (r.error) { setError(r.error); return; }
    if (r.token) setToken({ source: r.source, token: r.token }); setForm(null); refresh();
  }
  async function doRotate(s) {
    if (!window.confirm(`Régénérer le jeton de « ${s.name} » ? L'ancien cesse de fonctionner immédiatement.`)) return;
    const r = await rotateToken(datasyncApiBase, s.id); if (r.error) setError(r.error); else setToken({ source: s, token: r.token });
  }
  async function doDelete(s) {
    if (!window.confirm(`Supprimer la source « ${s.name} » et toutes ses lignes centralisées ?`)) return;
    const r = await deleteSource(datasyncApiBase, s.id); if (r.error) setError(r.error); else refresh();
  }
  async function showLog(s) { const r = await sourceLog(datasyncApiBase, s.id); if (r.error) setError(r.error); else setLog({ source: s, entries: r.log }); }
  async function analyse() {
    setBusy("analysis"); setError(null); const r = await runAnalysis(datasyncApiBase); setBusy("");
    if (r.error) { setError(r.error); return; }
    setNotice(`Analyse : ${r.fields} correspondance(s) de champs, ${r.relations} relation(s) déduite(s), ${r.new} nouvelle(s) proposition(s)`);
    const l = await listLinks(datasyncApiBase); if (!l.error) setLinks(l.links);
  }
  async function decide(l, status) { const r = await decideLink(datasyncApiBase, l.id, status, login); if (r.error) setError(r.error); else { const x = await listLinks(datasyncApiBase); if (!x.error) setLinks(x.links); } }
  async function addManual() {
    const r = await createLink(datasyncApiBase, { ...manual, by_user: login }); if (r.error) { setError(r.error); return; }
    setManual(null); const x = await listLinks(datasyncApiBase); if (!x.error) setLinks(x.links);
  }
  async function doSearch(e) {
    if (e) e.preventDefault(); setBusy("search"); setError(null); const r = await search(datasyncApiBase, q, qSource); setBusy("");
    if (r.error) setError(r.error); else setResults(r);
  }
  async function showRelated(n, d) {
    setTab("relations"); setBusy("rel"); setError(null); const r = await related(datasyncApiBase, n.source_id, n.table, n.pk, d || depth); setBusy("");
    if (r.error) setError(r.error); else { setRel({ ...r, root: n }); setPick({ source: String(n.source_id), table: n.table, pk: n.pk }); }
  }
  async function doBrowse(sid, table, offset) { const r = await listRows(datasyncApiBase, sid, table, offset || 0); if (r.error) setError(r.error); else setBrowse({ sid, table, offset: offset || 0, ...r }); }

  const g = groupLinks(links); const srcName = (id) => (sources.find((s) => s.id === id) || {}).slug || id;
  const central = datasyncApiBase;   // l'URL publique de l'API source centrale, telle que le hub la joint

  return (
    <div className="hub-settings hub-settings-wide ds-view">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1><HubIcon icon="database" size={22} /> Synchronisation centrale</h1>
        <div className="ds-tabs">{TABS.map(([k, l]) => <button key={k} className={tab === k ? "primary" : "secondary"} onClick={() => setTab(k)}>{l}</button>)}</div>
      </div>
      {error && <div className="hub-card ds-error">⚠️ {error}</div>}
      {notice && <div className="hub-card ds-notice">{notice}</div>}

      {tab === "sources" && (
        <>
          <div className="hub-card"><p className="muted" style={{ margin: 0 }}>Liaison concentrique en sens unique : chaque serveur, application ou base pousse vers cette API source centrale avec son jeton (connecteur
            <code> datasync/connector/connector.py</code>, ou n'importe quel programme : <code>/ping</code>, <code>/schema</code>, <code>/rows</code>). Une source est « présente » si elle a donné signe de vie depuis moins de {Math.round(presenceS / 60)} min.</p></div>
          <div className="hub-card hub-settings-section">
            <div className="ds-row-between"><h2 style={{ margin: 0 }}>Sources ({sources.length})</h2><button className="primary" onClick={() => setForm({ name: "", kind: "mysql", notes: "" })}>+ Déclarer une source</button></div>
            {form && (
              <div className="ds-grid ds-form">
                <div className="hub-settings-row"><label>Nom</label><input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} autoFocus /></div>
                <div className="hub-settings-row"><label>Type</label><select value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })}><option value="mysql">MySQL / MariaDB</option><option value="postgres">PostgreSQL</option><option value="sqlite">SQLite</option><option value="app">application (pousse elle-même)</option><option value="server">serveur / exports</option></select></div>
                <div className="hub-settings-row"><label>Notes</label><input type="text" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
                <div className="ds-inline"><button className="primary" onClick={saveSource} disabled={busy === "source" || !form.name.trim()}>{form.id ? "Enregistrer" : "Créer (le jeton s'affiche une seule fois)"}</button><button className="secondary" onClick={() => setForm(null)}>Annuler</button></div>
              </div>
            )}
            {token && (
              <div className="ds-token"><b>Jeton de « {token.source.name} »</b> — copiez-le maintenant, il ne sera plus affiché : <code>{token.token}</code>
                <details><summary>Configuration du connecteur</summary><pre>{connectorConfig(central, token.token, token.source)}</pre>
                  <p className="muted">Sur le serveur de la source : <code>python3 connector.py config.json</code> (service systemd conseillé) ; SELECT seulement, aucune écriture.</p></details>
                <button className="secondary" onClick={() => setToken(null)}>Fermer</button></div>
            )}
            <table className="ds-table"><thead><tr><th>Source</th><th>Type</th><th>Présence</th><th>Lignes</th><th>Lots</th><th>Erreurs</th><th>Dernier lot</th><th></th></tr></thead>
              <tbody>{sources.map((s) => { const p = presenceBadge(s); const st = sourceStats(s); return (
                <tr key={s.id}><td><b>{s.name}</b> <span className="muted">{s.slug}</span>{s.last_ping_info?.host && <div className="muted">{s.last_ping_info.host} · v{s.last_ping_info.version}</div>}</td><td>{s.kind}</td>
                  <td className={p.cls}>{p.label}</td><td>{st.rows}</td><td>{st.batches}</td><td className={st.errors ? "ds-ko" : ""}>{st.errors}</td><td className="muted">{st.last.replace("T", " ")}</td>
                  <td className="ds-actions"><button className="secondary ds-mini" onClick={() => showLog(s)}>journal</button><button className="secondary ds-mini" onClick={() => setForm({ id: s.id, name: s.name, kind: s.kind, notes: s.notes })}>éditer</button>
                    <button className="secondary ds-mini" onClick={() => doRotate(s)}>jeton</button><button className="secondary ds-mini ds-danger" onClick={() => doDelete(s)}>✕</button></td></tr>); })}
                {sources.length === 0 && <tr><td colSpan={8} className="muted">Aucune source déclarée.</td></tr>}</tbody></table>
            {sources.map((s) => s.tables.length > 0 && (
              <details key={s.id} className="ds-details"><summary>{s.name} : {s.tables.length} table(s)</summary>
                <table className="ds-table"><thead><tr><th>Table</th><th>Clé</th><th>Lignes</th><th>Dernier lot</th><th>Lignes du lot</th><th>ms</th><th>Lots</th><th>Erreurs</th><th></th></tr></thead>
                  <tbody>{s.tables.map((t) => <tr key={t.name}><td>{t.name}</td><td>{t.pk}</td><td>{t.rows}</td><td className="muted">{(t.last_batch_at || "").replace("T", " ")}</td><td>{t.last_batch_rows}</td><td>{t.last_batch_ms}</td><td>{t.batches}</td>
                    <td className={t.errors ? "ds-ko" : ""} title={t.last_error}>{t.errors}</td><td><button className="secondary ds-mini" onClick={() => { setTab("relations"); doBrowse(s.id, t.name, 0); }}>parcourir</button></td></tr>)}</tbody></table>
              </details>
            ))}
            {log && (<div className="ds-log"><div className="ds-row-between"><h3 style={{ margin: 0 }}>Journal des remontées — {log.source.name}</h3><button className="secondary ds-mini" onClick={() => setLog(null)}>fermer</button></div>
              <table className="ds-table"><thead><tr><th>Quand</th><th>Table</th><th>Lignes</th><th>ms</th><th>Mode</th><th>Erreur</th></tr></thead>
                <tbody>{log.entries.map((e) => <tr key={e.id} className={e.error ? "ds-row-ko" : ""}><td className="muted">{e.at.replace("T", " ")}</td><td>{e.tname}</td><td>{e.rows}</td><td>{e.ms}</td><td>{e.mode}</td><td className="ds-ko">{e.error}</td></tr>)}</tbody></table></div>)}
          </div>
        </>
      )}

      {tab === "analysis" && (
        <>
          <div className="hub-card hub-settings-section">
            <div className="ds-row-between"><h2 style={{ margin: 0 }}>Analyse schéma / étiquette / champ / contenu</h2>
              <div className="ds-inline"><button className="primary" onClick={analyse} disabled={busy === "analysis"}>{busy === "analysis" ? "Analyse…" : "Lancer l'analyse"}</button>
                <button className="secondary" onClick={() => setManual({ kind: "relation", a_source: sources[0]?.id || "", a_table: "", a_column: "", b_source: sources[0]?.id || "", b_table: "", b_column: "" })}>+ Lien manuel</button></div></div>
            <p className="muted">Profil de chaque colonne (format observé : courriel, téléphone, date, identifiant, texte…), correspondances entre champs de tables différentes (nom normalisé, format, recouvrement des valeurs), relations déduites par les valeurs (une colonne <code>id_x</code> résolue dans la clé de <code>x</code>, y compris entre sources). À confirmer ou rejeter : les relations confirmées ou proposées alimentent la recherche relationnelle.</p>
            {manual && (
              <div className="ds-grid ds-form">
                <div className="hub-settings-row"><label>Nature</label><select value={manual.kind} onChange={(e) => setManual({ ...manual, kind: e.target.value })}><option value="relation">relation (colonne → clé)</option><option value="field">correspondance de champs</option></select></div>
                {["a", "b"].map((side) => (<React.Fragment key={side}>
                  <div className="hub-settings-row"><label>{side === "a" ? "Depuis : source" : "Vers : source"}</label><select value={manual[`${side}_source`]} onChange={(e) => setManual({ ...manual, [`${side}_source`]: Number(e.target.value) })}>{sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
                  <div className="hub-settings-row"><label>table</label><input type="text" value={manual[`${side}_table`]} onChange={(e) => setManual({ ...manual, [`${side}_table`]: e.target.value })} /></div>
                  <div className="hub-settings-row"><label>colonne</label><input type="text" value={manual[`${side}_column`]} onChange={(e) => setManual({ ...manual, [`${side}_column`]: e.target.value })} /></div></React.Fragment>))}
                <div className="ds-inline"><button className="primary" onClick={addManual}>Enregistrer (confirmé)</button><button className="secondary" onClick={() => setManual(null)}>Annuler</button></div>
              </div>
            )}
            {[["relation", "Relations déduites (colonne → clé)"], ["field", "Correspondances de champs"]].map(([k, title]) => (
              <div key={k} className="ds-links"><h3>{title} <span className="muted">({g[k].proposed.length} proposées · {g[k].confirmed.length} confirmées · {g[k].rejected.length} rejetées)</span></h3>
                <table className="ds-table"><thead><tr><th>De</th><th>{k === "relation" ? "Vers (clé)" : "Avec"}</th><th>Score</th><th>Pourquoi</th><th>Statut</th><th></th></tr></thead>
                  <tbody>{[...g[k].proposed, ...g[k].confirmed, ...g[k].rejected].map((l) => <tr key={l.id} className={`ds-${l.status}`}>
                    <td>{l.a_source_slug} › {l.a_table}.<b>{l.a_column}</b></td><td>{l.b_source_slug} › {l.b_table}.<b>{l.b_column}</b></td><td>{l.score}</td><td className="muted">{l.reasons}</td>
                    <td>{l.status === "proposed" ? "proposé" : l.status === "confirmed" ? `confirmé${l.by_user ? " (" + l.by_user + ")" : ""}` : "rejeté"}</td>
                    <td className="ds-actions">{l.status !== "confirmed" && <button className="secondary ds-mini" onClick={() => decide(l, "confirmed")}>✔ confirmer</button>}{l.status !== "rejected" && <button className="secondary ds-mini" onClick={() => decide(l, "rejected")}>✘ rejeter</button>}{l.status !== "proposed" && <button className="secondary ds-mini" onClick={() => decide(l, "proposed")}>↺</button>}</td></tr>)}
                    {links.filter((l) => l.kind === k).length === 0 && <tr><td colSpan={6} className="muted">Rien pour l'instant : lancez l'analyse une fois des lignes remontées.</td></tr>}</tbody></table></div>
            ))}
          </div>
          <div className="hub-card hub-settings-section"><h2>Profils des colonnes</h2>
            {prof.map((t) => (<details key={`${t.source_id}-${t.table}`} className="ds-details"><summary>{t.source} › {t.table} <span className="muted">({t.columns.length} colonnes, clé {t.pk || "?"})</span></summary>
              <table className="ds-table"><thead><tr><th>Colonne</th><th>Format</th><th>Formats observés</th><th>Distinctes</th><th>Vides</th><th>Long. moy.</th><th>Exemples</th></tr></thead>
                <tbody>{t.columns.map((c) => <tr key={c.name}><td><b>{c.name}</b></td><td>{c.kind}</td><td className="muted">{Object.entries(c.formats || {}).map(([k, v]) => `${k} ${Math.round(v * 100)} %`).join(", ")}</td><td>{c.distinct}/{c.n}</td><td>{Math.round((c.null_ratio || 0) * 100)} %</td><td>{c.avg_len}</td><td className="muted">{(c.sample || []).join(" · ")}</td></tr>)}</tbody></table></details>))}
            {prof.length === 0 && <p className="muted">Aucune table remontée.</p>}
          </div>
        </>
      )}

      {tab === "search" && (
        <div className="hub-card hub-settings-section">
          <h2>Recherche plein texte transversale</h2>
          <form onSubmit={doSearch} className="ds-inline"><input type="text" className="ds-q" value={q} onChange={(e) => setQ(e.target.value)} placeholder="mots (préfixe), « expression exacte », champ:valeur…" autoFocus />
            <select value={qSource} onChange={(e) => setQSource(e.target.value)}><option value="">toutes les sources</option>{sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
            <button className="primary" type="submit" disabled={busy === "search"}>Chercher</button></form>
          {results && <p className="muted">{results.total} résultat(s){results.total >= 50 ? " (50 premiers)" : ""}</p>}
          {results && results.results.map((r, i) => (<div key={i} className="ds-row"><div className="ds-row-head"><b>{r.source}</b> › {r.table} <code>#{r.pk}</code><button className="secondary ds-mini" onClick={() => showRelated(r, 1)}>relations</button></div>
            <div className="ds-snippet" dangerouslySetInnerHTML={{ __html: (r.snippet || "").replace(/</g, "&lt;").replace(/\[([^\]]+)\]/g, "<mark>$1</mark>") }} /><div className="muted">{rowSummary(r.row)}</div></div>))}
        </div>
      )}

      {tab === "relations" && (
        <div className="hub-card hub-settings-section">
          <h2>Recherche relationnelle</h2>
          <p className="muted">Depuis une ligne, les lignes en relation sémantique par les relations confirmées ou déduites (colonne → clé, dans les deux sens, intra et inter-sources), à 1, 2 ou 3 niveaux.</p>
          <div className="ds-inline">
            <select value={pick.source} onChange={(e) => setPick({ ...pick, source: e.target.value, table: "" })}><option value="">source…</option>{sources.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
            <select value={pick.table} onChange={(e) => setPick({ ...pick, table: e.target.value })}><option value="">table…</option>{(sources.find((s) => String(s.id) === pick.source)?.tables || []).map((t) => <option key={t.name} value={t.name}>{t.name}</option>)}</select>
            <input type="text" value={pick.pk} onChange={(e) => setPick({ ...pick, pk: e.target.value })} placeholder="clé" style={{ width: 120 }} />
            <select value={depth} onChange={(e) => setDepth(Number(e.target.value))}><option value={1}>1 niveau</option><option value={2}>2 niveaux</option><option value={3}>3 niveaux</option></select>
            <button className="primary" disabled={!pick.source || !pick.table || !pick.pk || busy === "rel"} onClick={() => showRelated({ source_id: Number(pick.source), source: srcName(Number(pick.source)), table: pick.table, pk: pick.pk }, depth)}>Explorer</button>
            {pick.source && pick.table && <button className="secondary" onClick={() => doBrowse(Number(pick.source), pick.table, 0)}>Parcourir la table</button>}
          </div>
          {browse && (<div className="ds-browse"><h3>{srcName(browse.sid)} › {browse.table} <span className="muted">({browse.total} lignes)</span></h3>
            {browse.rows.map((r) => <RowCard key={r.pk} n={{ source_id: browse.sid, source: srcName(browse.sid), table: browse.table, pk: r.pk, row: r.row }} onRelated={(n) => showRelated(n, depth)} />)}
            <div className="ds-inline"><button className="secondary ds-mini" disabled={browse.offset === 0} onClick={() => doBrowse(browse.sid, browse.table, Math.max(0, browse.offset - 50))}>◀</button><span className="muted">{browse.offset + 1}–{Math.min(browse.offset + 50, browse.total)}</span><button className="secondary ds-mini" disabled={browse.offset + 50 >= browse.total} onClick={() => doBrowse(browse.sid, browse.table, browse.offset + 50)}>▶</button></div></div>)}
          {rel && (<div className="ds-rel"><h3>Autour de {rel.root.source} › {rel.root.table} <code>#{rel.root.pk}</code> <span className="muted">— {rel.nodes.length - 1} ligne(s) liée(s), {rel.edges.length} lien(s), {rel.links_used} relation(s) actives</span></h3>
            {groupNodes(rel.nodes).map((grp) => (<div key={`${grp.level}-${grp.source}-${grp.table}`} className={`ds-level ds-level-${grp.level}`}><h4>{grp.level === 0 ? "Point de départ" : `Niveau ${grp.level}`} — {grp.source} › {grp.table} ({grp.rows.length})</h4>
              {grp.rows.map((n) => <RowCard key={`${n.source_id}-${n.table}-${n.pk}`} n={n} onRelated={grp.level > 0 ? (x) => showRelated(x, depth) : null} />)}</div>))}
            <details className="ds-details"><summary>Liens suivis ({rel.edges.length})</summary><ul>{rel.edges.map((e, i) => <li key={i} className="muted">{e.from[1]}#{e.from[2]} {e.direction} {e.to[1]}#{e.to[2]} — {e.link} ({e.status === "confirmed" ? "confirmée" : "déduite"})</li>)}</ul></details></div>)}
        </div>
      )}
    </div>
  );
}
