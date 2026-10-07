import React, { useState, useEffect, useCallback } from "react";
import { listProjects, getProject, createProject, updateProject, deleteProject, runSteps, getReport, getDecisions, putDecisions, loadDump, uploadFile, archiveUrl } from "./portageClient.js";
import { STEP_LABELS, defaultSteps, summarizeDecisions, parseSmoke, statusLabel, slugify } from "./portageLib.js";
import HubIcon from "./HubIcon.jsx";

import { AutoColumns } from "./TableColumns.jsx";   // #707 : colonnes réglables
// Tuile « Portage PHP → Python » (hub), livraison #650 -- interface de
// création d'un PROJET DE PORTAGE avec import du code et des données, puis
// exécution de l'IA de portage (portage-kit, projet indépendant monté dans
// portage-api) et revue de ses rapports : PORT_SPEC (colonne « décision »
// éditable ici, conservée d'une exécution à l'autre), schéma mesuré, fumée,
// journal. Complète « Rétro-ingénierie » (relations depuis le code) et
// « Analyse de schémas » (relations depuis les données) : ici on PRODUIT le
// port, on ne diagnostique plus seulement.
//
// Non vérifié en navigateur (pas de `npm run build` depuis le shell) :
// syntaxe contrôlée par @babel/parser, logique pure testée sous Node.

const EMPTY = { name: "", kind: "", entry: "index.php", charset: "latin1", table_prefix: "", notes: "",
  auth: { test_login: "", test_password: "", users_table: "", login_col: "", password_col: "", name_col: "", type_col: "", admin_type: "", domains_table: "" } };

export default function PortageView({ onBack, portageApiBase }) {
  const [list, setList] = useState([]);
  const [kitInstalled, setKitInstalled] = useState(true);
  const [choices, setChoices] = useState([]);
  const [current, setCurrent] = useState(null);     // projet détaillé
  const [form, setForm] = useState(EMPTY);
  const [creating, setCreating] = useState(false);
  const [steps, setSteps] = useState(Object.keys(STEP_LABELS));
  const [busy, setBusy] = useState("");
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [report, setReport] = useState({ name: "", text: "" });
  const [units, setUnits] = useState([]);
  const [pending, setPending] = useState({});     // décisions modifiées non enregistrées

  const refreshList = useCallback(async () => {
    const r = await listProjects(portageApiBase);
    if (r.error) { setError(r.error); return; }
    setList(r.projects || []); setKitInstalled(r.kit_installed !== false); setChoices(r.decisions || []);
  }, [portageApiBase]);

  const refreshCurrent = useCallback(async (slug) => {
    const r = await getProject(portageApiBase, slug);
    if (r.error) { setError(r.error); return null; }
    setCurrent(r.project); return r.project;
  }, [portageApiBase]);

  useEffect(() => { refreshList(); }, [refreshList]);

  // suivi d'une exécution en cours : rafraîchissement toutes les 3 s
  useEffect(() => {
    if (!current || !(current.running || current.run_status === "running")) return undefined;
    const id = setInterval(async () => {
      const p = await refreshCurrent(current.slug);
      if (p && !(p.running || p.run_status === "running")) { refreshList(); loadDecisions(p.slug); }
    }, 3000);
    return () => clearInterval(id);
  }, [current, refreshCurrent, refreshList]);

  async function open(slug) {
    setError(null); setNotice(null); setReport({ name: "", text: "" }); setPending({});
    const p = await refreshCurrent(slug);
    if (p) { setSteps(defaultSteps(p.files)); loadDecisions(slug); setForm({ ...EMPTY, ...p, auth: { ...EMPTY.auth, ...(p.auth || {}) } }); }
  }

  async function loadDecisions(slug) {
    const r = await getDecisions(portageApiBase, slug);
    if (!r.error) { setUnits(r.units || []); if (r.choices) setChoices(r.choices); }
  }

  async function handleCreate(e) {
    e.preventDefault(); setBusy("create"); setError(null);
    const r = await createProject(portageApiBase, form);
    setBusy("");
    if (r.error) { setError(r.error); return; }
    setCreating(false); setForm(EMPTY); await refreshList(); open(r.project.slug);
  }

  async function handleSave() {
    setBusy("save"); const r = await updateProject(portageApiBase, current.slug, form); setBusy("");
    if (r.error) setError(r.error); else { setCurrent(r.project); setNotice("Fiche enregistrée (apps/<projet>.yml régénéré)"); refreshList(); }
  }

  async function handleUpload(kind, e) {
    const file = e.target.files[0]; if (!file) return;
    setBusy(kind); setError(null); setNotice(null);
    const r = await uploadFile(portageApiBase, current.slug, kind, file);
    setBusy(""); e.target.value = "";
    if (r.error) { setError(r.error); if (r.project) setCurrent(r.project); return; }
    setCurrent(r.project); setSteps(defaultSteps(r.project.files)); refreshList();
    if (kind === "code") setNotice(`Code importé : ${r.detected.php_files} fichier(s) PHP, type détecté « ${r.detected.kind || "inconnu"} », entrée ${r.detected.entry}`);
    if (kind === "dump") setNotice(r.load ? `Dump chargé dans ${r.load.db} : ${r.load.tables} table(s) (${r.load.charset})${r.load.warnings ? " — avertissements, voir le journal MariaDB" : ""}` : "Dump déposé");
    if (r.detected) setForm((f) => ({ ...f, kind: f.kind || r.detected.kind, entry: r.detected.entry }));
  }

  async function handleReload() {
    setBusy("dump"); const r = await loadDump(portageApiBase, current.slug); setBusy("");
    if (r.error || (r.load && r.load.error)) setError(r.error || r.load.error); else setNotice(`Dump rechargé : ${r.load.tables} table(s)`);
  }

  async function handleRun() {
    setBusy("run"); setError(null); setNotice(null);
    const r = await runSteps(portageApiBase, current.slug, steps); setBusy("");
    if (r.error) { setError(r.error); return; }
    setCurrent(r.project); setReport({ name: "", text: "" });
  }

  async function showReport(name) {
    const r = await getReport(portageApiBase, current.slug, name);
    if (r.error) { setError(r.error); return; }
    setReport({ name, text: r.text !== undefined ? r.text : JSON.stringify(r.data, null, 1) });
  }

  async function saveDecisions() {
    setBusy("decisions"); const r = await putDecisions(portageApiBase, current.slug, pending); setBusy("");
    if (r.error) setError(r.error); else { setUnits(r.units); setPending({}); setNotice("Décisions enregistrées : elles pilotent l'étape « Écrans métier » (410 pour les unités mortes ou différées)"); }
  }

  async function handleDelete() {
    if (!window.confirm(`Supprimer le projet « ${current.name} » (code, dump, base ${current.db_name}, port généré) ?`)) return;
    const r = await deleteProject(portageApiBase, current.slug);
    if (r.error) setError(r.error); else { setCurrent(null); refreshList(); }
  }

  const sum = summarizeDecisions(units);
  const smoke = report.name === "smoke" ? parseSmoke(report.text) : null;
  const setF = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  const setA = (k, v) => setForm((f) => ({ ...f, auth: { ...f.auth, [k]: v } }));

  return (
    <div className="hub-settings hub-settings-wide pt-view">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={current ? () => { setCurrent(null); refreshList(); } : onBack}>◀ {current ? "Projets" : "Retour"}</button>
        <h1><HubIcon icon="shuffle" size={22} /> Portage PHP → Python{current ? ` — ${current.name}` : ""}</h1>
      </div>

      {!kitInstalled && <div className="hub-card pt-warn">portage-kit n'est pas monté dans portage-api : la création de projets et les imports fonctionnent, mais aucune étape ne pourra être lancée. Renseigner <code>PORTAGE_KIT_DIR</code> dans <code>.env</code> (voir <code>portage/README.md</code>).</div>}
      {error && <div className="hub-card pt-error">⚠️ {error}</div>}
      {notice && <div className="hub-card pt-notice">{notice}</div>}

      {!current && (
        <>
          <div className="hub-card">
            <p className="muted" style={{ margin: 0 }}>
              Un projet de portage = une application PHP du parc : sa fiche, son code (archive), ses données (dump SQL chargé dans la base
              MariaDB dédiée <code>portage-db</code>, jamais ailleurs), puis les étapes de l'IA de portage. Les décisions prises sur chaque
              unité du PORT_SPEC (porter, simplifier, différer, abandonner) sont conservées d'une exécution à l'autre.
            </p>
          </div>
          <div className="hub-card hub-settings-section">
            <div className="pt-row-between">
              <h2 style={{ margin: 0 }}>Projets ({list.length})</h2>
              <button className="primary" onClick={() => { setCreating((c) => !c); setForm(EMPTY); }}>{creating ? "Annuler" : "+ Nouveau projet"}</button>
            </div>
            {creating && (
              <form onSubmit={handleCreate} className="pt-form">
                <div className="hub-settings-row"><label>Nom</label><input type="text" value={form.name} onChange={(e) => setF("name", e.target.value)} required autoFocus /></div>
                <p className="muted">Identifiant : <code>{slugify(form.name)}</code> (base <code>port_{slugify(form.name).replace(/-/g, "_")}</code>)</p>
                <div className="pt-grid">
                  <div className="hub-settings-row"><label>Type</label>
                    <select value={form.kind} onChange={(e) => setF("kind", e.target.value)}><option value="">détecter à l'import du code</option><option value="fatfree">Fat-Free (routes)</option><option value="monolith">monolithe switch($mode)</option></select></div>
                  <div className="hub-settings-row"><label>Charset de l'original</label>
                    <select value={form.charset} onChange={(e) => setF("charset", e.target.value)}><option value="latin1">latin1 / ISO-8859</option><option value="utf-8">utf-8</option></select></div>
                  <div className="hub-settings-row"><label>Préfixe des tables</label><input type="text" value={form.table_prefix} onChange={(e) => setF("table_prefix", e.target.value)} placeholder="ex. tts_" /></div>
                </div>
                <div className="hub-settings-row"><label>Notes</label><input type="text" value={form.notes} onChange={(e) => setF("notes", e.target.value)} /></div>
                <button className="primary" type="submit" disabled={busy === "create"}>Créer le projet</button>
              </form>
            )}
            <AutoColumns id="PortageView.1"><table className="pt-table">
              <thead><tr><th>Projet</th><th>Type</th><th>Code</th><th>Dump</th><th>Dernière exécution</th><th>Port généré</th></tr></thead>
              <tbody>
                {list.map((p) => (
                  <tr key={p.slug} className="pt-clickable" onClick={() => open(p.slug)}>
                    <td><b>{p.name}</b> <span className="muted">{p.slug}</span></td><td>{p.kind || "—"}</td>
                    <td>{p.files.source ? "✔" : "—"}</td><td>{p.files.dump ? (p.dump_loaded_at ? "✔ chargé" : "déposé") : "—"}</td>
                    <td>{statusLabel(p)}{p.run_finished_at ? ` (${p.run_finished_at.replace("T", " ")})` : ""}</td><td>{p.files.py ? "✔" : "—"}</td>
                  </tr>
                ))}
                {list.length === 0 && <tr><td colSpan={6} className="muted">Aucun projet : créez-en un, puis importez le code et le dump.</td></tr>}
              </tbody>
            </table></AutoColumns>
          </div>
        </>
      )}

      {current && (
        <div className="pt-columns">
          <div className="pt-col">
            <div className="hub-card hub-settings-section">
              <h2>1. Fiche</h2>
              <div className="pt-grid">
                <div className="hub-settings-row"><label>Nom</label><input type="text" value={form.name} onChange={(e) => setF("name", e.target.value)} /></div>
                <div className="hub-settings-row"><label>Type</label>
                  <select value={form.kind} onChange={(e) => setF("kind", e.target.value)}><option value="">(non détecté)</option><option value="fatfree">Fat-Free</option><option value="monolith">monolithe</option></select></div>
                <div className="hub-settings-row"><label>Fichier d'entrée</label><input type="text" value={form.entry} onChange={(e) => setF("entry", e.target.value)} /></div>
                <div className="hub-settings-row"><label>Charset</label>
                  <select value={form.charset} onChange={(e) => setF("charset", e.target.value)}><option value="latin1">latin1</option><option value="utf-8">utf-8</option></select></div>
                <div className="hub-settings-row"><label>Préfixe des tables</label><input type="text" value={form.table_prefix} onChange={(e) => setF("table_prefix", e.target.value)} /></div>
              </div>
              <details className="pt-details"><summary>Compte de test et table des utilisateurs (connexion du port)</summary>
                <div className="pt-grid">
                  <div className="hub-settings-row"><label>Login de test</label><input type="text" value={form.auth.test_login} onChange={(e) => setA("test_login", e.target.value)} /></div>
                  <div className="hub-settings-row"><label>Mot de passe de test</label><input type="text" value={form.auth.test_password} onChange={(e) => setA("test_password", e.target.value)} /></div>
                  <div className="hub-settings-row"><label>Table des utilisateurs</label><input type="text" value={form.auth.users_table} onChange={(e) => setA("users_table", e.target.value)} placeholder="vide = <préfixe>users" /></div>
                  <div className="hub-settings-row"><label>Colonne login</label><input type="text" value={form.auth.login_col} onChange={(e) => setA("login_col", e.target.value)} placeholder="login" /></div>
                  <div className="hub-settings-row"><label>Colonne mot de passe (md5)</label><input type="text" value={form.auth.password_col} onChange={(e) => setA("password_col", e.target.value)} placeholder="password" /></div>
                  <div className="hub-settings-row"><label>Colonne type / valeur admin</label><div className="pt-inline"><input type="text" value={form.auth.type_col} onChange={(e) => setA("type_col", e.target.value)} placeholder="type" /><input type="text" value={form.auth.admin_type} onChange={(e) => setA("admin_type", e.target.value)} placeholder="Admin" /></div></div>
                  <div className="hub-settings-row"><label>Table des domaines (vide = mono-domaine)</label><input type="text" value={form.auth.domains_table} onChange={(e) => setA("domains_table", e.target.value)} /></div>
                </div>
              </details>
              <div className="pt-inline">
                <button className="primary" onClick={handleSave} disabled={busy === "save"}>Enregistrer la fiche</button>
                <button className="secondary" onClick={() => showReport("yml")}>Voir le yml</button>
                <button className="secondary pt-danger" onClick={handleDelete}>Supprimer le projet</button>
              </div>
            </div>

            <div className="hub-card hub-settings-section">
              <h2>2. Code et données</h2>
              <div className="hub-settings-row"><label>Code source (archive .zip / .tar.gz) {current.code_file ? `— actuel : ${current.code_file}` : ""}</label>
                <input type="file" accept=".zip,.tgz,.tar.gz,.tar" onChange={(e) => handleUpload("code", e)} disabled={busy === "code"} /></div>
              <div className="hub-settings-row"><label>Dump SQL (.sql / .sql.gz) {current.dump_file ? `— actuel : ${current.dump_file}${current.dump_loaded_at ? ", chargé le " + current.dump_loaded_at.replace("T", " ") : ""}` : ""}</label>
                <div className="pt-inline"><input type="file" accept=".sql,.gz" onChange={(e) => handleUpload("dump", e)} disabled={busy === "dump"} />
                  {current.files.dump && <button className="secondary" onClick={handleReload} disabled={busy === "dump"}>Recharger dans {current.db_name}</button>}</div></div>
              <p className="muted">Les données restent dans <code>portage-db</code> (réseau Docker interne). L'anonymisation est une étape explicite du kit (<code>kit/anonymize.py</code>), jamais automatique.</p>
            </div>

            <div className="hub-card hub-settings-section">
              <h2>3. Étapes de l'IA de portage</h2>
              <div className="pt-steps">
                {Object.entries(STEP_LABELS).map(([k, label]) => (
                  <label key={k} className="pt-step"><input type="checkbox" checked={steps.includes(k)} onChange={(e) => setSteps((s) => e.target.checked ? Object.keys(STEP_LABELS).filter((x) => s.includes(x) || x === k) : s.filter((x) => x !== k))} /> {label}</label>
                ))}
              </div>
              <div className="pt-inline">
                <button className="primary" onClick={handleRun} disabled={busy === "run" || current.running || !kitInstalled || !current.files.source}>{current.running ? "Exécution en cours…" : "Lancer"}</button>
                <span className="muted">État : {statusLabel(current)}{current.run_steps ? ` (${current.run_steps})` : ""}</span>
              </div>
              {current.log_tail && <pre className="pt-log">{current.log_tail}</pre>}
            </div>
          </div>

          <div className="pt-col">
            <div className="hub-card hub-settings-section">
              <h2>4. Décisions du PORT_SPEC <span className="muted">({sum.total} unités : {sum.porter} à porter, {sum.differe} différées, {sum.mort} abandonnées, {sum.vide} sans décision)</span></h2>
              {units.length === 0 ? <p className="muted">Lancez l'inventaire pour obtenir la liste des unités (modes du monolithe ou routes Fat-Free).</p> : (
                <div className="pt-scroll"><AutoColumns id="PortageView.2"><table className="pt-table">
                  <thead><tr><th>Unité</th><th>Fichier</th><th>Lit</th><th>Écrit</th><th>Entrées</th><th>Mail</th><th>Décision</th></tr></thead>
                  <tbody>{units.map((u) => (
                    <tr key={u.unit}><td><code>{u.unit}</code></td><td className="muted">{u.file}</td><td>{u.reads}</td><td>{u.writes}</td><td className="muted">{u.inputs}</td><td>{u.mail}</td>
                      <td><select value={pending[u.unit] !== undefined ? pending[u.unit] : u.decision} onChange={(e) => setPending((p) => ({ ...p, [u.unit]: e.target.value }))}>
                        {choices.map((c) => <option key={c} value={c}>{c || "— (porter)"}</option>)}</select></td></tr>
                  ))}</tbody></table></AutoColumns></div>
              )}
              {Object.keys(pending).length > 0 && <button className="primary" onClick={saveDecisions} disabled={busy === "decisions"}>Enregistrer {Object.keys(pending).length} décision(s)</button>}
            </div>

            <div className="hub-card hub-settings-section">
              <h2>5. Rapports</h2>
              <div className="pt-inline pt-wrap">
                {[["port_spec", "PORT_SPEC", current.files.port_spec], ["schema", "Schéma mesuré", current.files.schema], ["smoke", "Fumée", current.files.smoke], ["log", "Journal", current.files.log], ["inventory", "Inventaire (json)", current.files.inventory]].map(([k, l, ok]) => (
                  <button key={k} className={report.name === k ? "primary" : "secondary"} disabled={!ok} onClick={() => showReport(k)}>{l}</button>
                ))}
                {current.files.py && <a className="pt-link" href={archiveUrl(portageApiBase, current.slug)}>⬇ Archive du port généré</a>}
              </div>
              {smoke && smoke.routes.length > 0 && (
                <AutoColumns id="PortageView.3"><table className="pt-table pt-smoke"><thead><tr><th>Route</th><th>Statut</th></tr></thead>
                  <tbody>{smoke.routes.map((r) => <tr key={r.route}><td><code>{r.route}</code></td><td className={/^2/.test(r.status) ? "pt-ok" : /^(4|5|err)/.test(r.status) ? "pt-ko" : ""}>{r.status}</td></tr>)}</tbody></table></AutoColumns>
              )}
              {smoke && <p className="muted">{smoke.summary}</p>}
              {report.text && report.name !== "smoke" && <pre className="pt-report">{report.text}</pre>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
