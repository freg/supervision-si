// Tuile « Licences logicielles » (livraison #595) -- demandé : gestionnaire de
// licences logicielles PAR SITE : recueillir les informations sur le réseau et
// les postes (sonde software-inventory des agents), gestionnaires utilisant
// les accès sur les sites des vendeurs (Microsoft Graph via le coffre),
// grille d'affectation poste / utilisateur × logiciel, installeur /
// désinstalleur depuis la tuile (commande software_action à l'agent).
// Onglets : Tableau de bord (écarts), Contrats & catalogue (+ import des
// tableurs), Grille d'affectation, Postes & installations (+ installer /
// désinstaller), Vendeurs, Journal. Note design : en-tête de tableau fixé,
// contenu qui défile, filtre « début de mot d'abord », pied fixe.
import { useCallback, useEffect, useMemo, useState } from "react";
import PageFrame from "./PageFrame.jsx";
import { hubLink, viewParams } from "./hubLinks.js";
import * as api from "./licensesClient.js";
import { KIND_LABEL, GAP_LABEL, SEVERITY_TONE, ACTION_STATUS, VENDOR_KIND_LABEL, contractTone, filterContracts, filterSoftware, filterGaps, filterHosts, filterRows, filterUsers, gapSummary, softwareTotals, pickContract, defaultManager, fmtDays } from "./licensesLib.js";

const TABS = [
  { id: "dash", label: "📊 Tableau de bord" },
  { id: "contracts", label: "📜 Contrats & catalogue" },
  { id: "grid", label: "🧩 Grille d'affectation" },
  { id: "users", label: "👤 Utilisateurs" },
  { id: "hosts", label: "💻 Postes & installations" },
  { id: "vendors", label: "🏬 Vendeurs" },
  { id: "log", label: "📒 Journal" },
];
const COLORS = { red: "#e53935", orange: "#fb8c00", green: "#43a047", grey: "#9e9e9e" };
const when = (t) => (t ? new Date(t * 1000).toLocaleString() : "");
function Tone({ tone, children }) { return <span style={{ color: COLORS[tone] || "inherit", fontWeight: 600 }}>{children}</span>; }
function Lamp({ tone, title }) { return <span title={title} style={{ display: "inline-block", width: 12, height: 12, borderRadius: 6, background: COLORS[tone] || COLORS.grey, marginRight: 6, verticalAlign: "middle" }} />; }
/** Tableau à en-tête fixé : le corps défile, la page non. */
function Scroll({ children, max = "calc(100vh - 300px)" }) { return <div style={{ maxHeight: max, overflow: "auto", border: "1px solid var(--border, #444)", borderRadius: 6 }}>{children}</div>; }
const TH = { position: "sticky", top: 0, background: "var(--panel, #222)", zIndex: 1 };

// ---------------------------------------------------------------------------
function Dashboard({ b, t, site, contracts, reload, notice }) {
  const [gaps, setGaps] = useState(null);
  const [found, setFound] = useState({});
  const [query, setQuery] = useState("");
  const [sev, setSev] = useState("");
  useEffect(() => {
    api.fetchGaps(b, t, site).then((r) => (r.error ? notice(r.error, false) : setGaps(r.gaps || [])));
    api.fetchInstallations(b, t, site).then((r) => !r.error && setFound(r.found || {}));
  }, [b, t, site, contracts]);  // eslint-disable-line react-hooks/exhaustive-deps
  const sum = gapSummary(gaps);
  const totals = useMemo(() => softwareTotals(contracts, found), [contracts, found]);
  const shown = useMemo(() => filterGaps(gaps, query, sev), [gaps, query, sev]);
  return (
    <div>
      <div className="hub-card" style={{ marginBottom: 10, display: "flex", gap: 18, alignItems: "center", flexWrap: "wrap" }}>
        <span><Lamp tone={sum.tone} />{gaps ? `${sum.total} écart(s)` : "…"}</span>
        <span><Tone tone="red">{sum.critical}</Tone> critique(s)</span>
        <span><Tone tone="orange">{sum.warning}</Tone> alerte(s)</span>
        <span><Tone tone="grey">{sum.info}</Tone> info(s)</span>
        <span className="muted">{contracts.length} contrat(s){site ? ` sur ${site}` : ""} · {Object.keys(found).length} logiciel(s) vus sur les postes</span>
        <button type="button" className="secondary" onClick={reload}>↻</button>
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 10 }}>
        <div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
            <input type="search" placeholder="filtrer les écarts" value={query} onChange={(e) => setQuery(e.target.value)} />
            <select value={sev} onChange={(e) => setSev(e.target.value)}><option value="">toutes sévérités</option><option value="critical">critiques</option><option value="warning">alertes</option><option value="info">infos</option></select>
            <span className="muted">{shown.length} / {(gaps || []).length}</span>
          </div>
          <Scroll>
            <table style={{ width: "100%", fontSize: 13 }}>
              <thead style={TH}><tr><th> </th><th>Logiciel</th><th>Écart</th><th>Détail</th></tr></thead>
              <tbody>
                {shown.map((g, i) => (
                  <tr key={i}>
                    <td><Lamp tone={SEVERITY_TONE[g.severity]} title={g.severity} /></td>
                    <td>{g.software}</td>
                    <td><b>{GAP_LABEL[g.kind] || g.kind}</b><br /><span className="muted">{g.text}</span></td>
                    <td className="muted" style={{ fontSize: 12 }}>{Array.isArray(g.detail) ? g.detail.join(", ") : g.detail && typeof g.detail === "object" ? Object.values(g.detail).join(" ") : ""}</td>
                  </tr>
                ))}
                {gaps && !shown.length && <tr><td colSpan={4} className="muted">aucun écart : contrats, attributions et installations concordent.</td></tr>}
              </tbody>
            </table>
          </Scroll>
        </div>
        <div>
          <p className="muted" style={{ margin: "0 0 6px" }}>Par logiciel : licences détenues, attribuées, postes où il est installé, coût annuel connu.</p>
          <Scroll>
            <table style={{ width: "100%", fontSize: 13 }}>
              <thead style={TH}><tr><th> </th><th>Logiciel</th><th>Éditeur</th><th>Licences</th><th>Attribuées</th><th>Installé (postes)</th><th>Coût / an</th></tr></thead>
              <tbody>
                {totals.map((s) => (
                  <tr key={s.software_id}>
                    <td><Lamp tone={s.tone} /></td><td>{s.software}</td><td className="muted">{s.vendor}</td>
                    <td>{s.quantity || "∞"}</td><td><Tone tone={s.quantity && s.assigned > s.quantity ? "red" : "inherit"}>{s.assigned}</Tone></td><td>{s.installed}</td><td>{s.cost ? `${s.cost.toFixed(0)} €` : ""}</td>
                  </tr>
                ))}
                {!totals.length && <tr><td colSpan={7} className="muted">aucun contrat : en créer dans « Contrats & catalogue » ou importer un tableur.</td></tr>}
              </tbody>
            </table>
          </Scroll>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
const EMPTY_SW = { name: "", vendor: "", category: "", patterns: "", pkg_winget: "", pkg_apt: "", pkg_brew: "", pkg_dnf: "" };
const EMPTY_CT = { software_id: "", site: "", label: "", kind: "per-user", quantity: 1, start: "", end: "", cost: "", currency: "EUR", renewal: "", vendor_account: "", sku: "", reference: "", notes: "" };

function Contracts({ b, t, site, sites, software, contracts, reload, notice }) {
  const [query, setQuery] = useState("");
  const [ct, setCt] = useState(null);
  const [sw, setSw] = useState(null);
  // #596 : un seul bouton « Analyser » qui devient « Importer N logiciel(s) » une fois
  // l'analyse faite ; état visible (analyse… / import…) et résultat affiché.
  const [imp, setImp] = useState({ file: null, site: site || "", plan: null, format: "", busy: "", done: null });
  const shown = useMemo(() => filterContracts(contracts, query), [contracts, query]);
  const shownSw = useMemo(() => filterSoftware(software, query), [software, query]);
  const saveCt = async () => {
    const body = { ...ct, software_id: Number(ct.software_id), quantity: Number(ct.quantity) || 0, cost: ct.cost === "" ? null : Number(ct.cost) };
    const r = await api.saveContract(b, t, body, ct.id);
    notice(r.error || `contrat enregistré (${body.label || body.software_id})`, !r.error);
    if (!r.error) { setCt(null); reload(); }
  };
  const saveSw = async () => {
    const pkg = {}; for (const m of ["winget", "apt", "brew", "dnf"]) if (sw[`pkg_${m}`]) pkg[m] = sw[`pkg_${m}`];
    const r = await api.saveSoftware(b, t, { name: sw.name, vendor: sw.vendor, category: sw.category, patterns: String(sw.patterns || "").split(/[\n;]/).map((x) => x.trim()).filter(Boolean), package: pkg, notes: sw.notes || "" }, sw.id);
    notice(r.error || `logiciel enregistré (${sw.name})`, !r.error);
    if (!r.error) { setSw(null); reload(); }
  };
  const editSw = (s) => setSw({ ...EMPTY_SW, ...s, patterns: (s.patterns || []).join("\n"), pkg_winget: s.package?.winget || "", pkg_apt: s.package?.apt || "", pkg_brew: s.package?.brew || "", pkg_dnf: s.package?.dnf || "" });
  const doImport = async () => {
    if (!imp.file) return notice("choisir un fichier .xlsx ou .csv", false);
    const dry = !imp.plan;
    setImp({ ...imp, busy: dry ? "analyse…" : "import…", done: null });
    const r = await api.importFile(b, t, imp.file, imp.site, dry, imp.format);
    if (r.error) { setImp({ ...imp, busy: "", plan: null }); return notice(r.error, false); }
    if (dry) { setImp({ ...imp, busy: "", plan: r.plan, detected: r.format, people: r.people, unknown: r.unknown_people || [] }); notice(`analyse : ${r.plan.length} logiciel(s), ${r.people} personne(s) (format ${r.format}) — vérifier puis cliquer « Importer »`); return; }
    const done = `importé : ${r.created.software} logiciel(s), ${r.created.contracts} contrat(s), ${r.created.assignments} attribution(s), ${r.created.users} utilisateur(s) créé(s)${r.created.software + r.created.contracts + r.created.assignments + r.created.users === 0 ? " (rien de nouveau : déjà importé)" : ""}`;
    setImp({ ...imp, busy: "", plan: null, done });
    notice(done);
    reload();
  };
  const F = (k, props = {}) => <input value={ct[k] ?? ""} onChange={(e) => setCt({ ...ct, [k]: e.target.value })} {...props} />;
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <input type="search" placeholder="filtrer (logiciel, éditeur, site, type, SKU)" value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 260 }} />
        <span className="muted">{shown.length} / {contracts.length} contrat(s) · {software.length} logiciel(s) au catalogue</span>
        <button type="button" onClick={() => setCt({ ...EMPTY_CT, site: site || "" })}>+ contrat</button>
        <button type="button" className="secondary" onClick={() => setSw({ ...EMPTY_SW })}>+ logiciel</button>
      </div>
      {ct && (
        <div className="hub-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>{ct.id ? `Contrat #${ct.id}` : "Nouveau contrat"}</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
            <label>Logiciel<br /><select value={ct.software_id} onChange={(e) => setCt({ ...ct, software_id: e.target.value })}><option value="">—</option>{software.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select></label>
            <label>Site<br /><input list="lic-sites" value={ct.site} onChange={(e) => setCt({ ...ct, site: e.target.value })} /><datalist id="lic-sites">{sites.map((s) => <option key={s} value={s} />)}</datalist></label>
            <label>Libellé<br />{F("label", { placeholder: "ex. Business Standard annuel" })}</label>
            <label>Type<br /><select value={ct.kind} onChange={(e) => setCt({ ...ct, kind: e.target.value })}>{Object.entries(KIND_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></label>
            <label>Quantité (0 = illimité)<br />{F("quantity", { type: "number", min: 0 })}</label>
            <label>Début<br />{F("start", { type: "date" })}</label>
            <label>Fin<br />{F("end", { type: "date" })}</label>
            <label>Coût / an<br />{F("cost", { type: "number", step: "0.01" })}</label>
            <label>Renouvellement<br />{F("renewal", { placeholder: "automatique, manuel…" })}</label>
            <label>Compte vendeur<br />{F("vendor_account", { placeholder: "nom du compte (onglet Vendeurs)" })}</label>
            <label>SKU<br />{F("sku")}</label>
            <label>Référence<br />{F("reference", { placeholder: "n° de contrat, bon de commande" })}</label>
          </div>
          <label>Notes<br /><textarea value={ct.notes || ""} onChange={(e) => setCt({ ...ct, notes: e.target.value })} style={{ width: "100%" }} rows={2} /></label>
          <div style={{ marginTop: 6 }}><button type="button" onClick={saveCt} disabled={!ct.software_id}>Enregistrer</button> <button type="button" className="secondary" onClick={() => setCt(null)}>Annuler</button></div>
        </div>
      )}
      {sw && (
        <div className="hub-card" style={{ marginBottom: 10 }}>
          <h3 style={{ marginTop: 0 }}>{sw.id ? `Logiciel #${sw.id}` : "Nouveau logiciel"}</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            <label>Nom<br /><input value={sw.name} onChange={(e) => setSw({ ...sw, name: e.target.value })} /></label>
            <label>Éditeur<br /><input value={sw.vendor} onChange={(e) => setSw({ ...sw, vendor: e.target.value })} /></label>
            <label>Catégorie<br /><input value={sw.category} onChange={(e) => setSw({ ...sw, category: e.target.value })} placeholder="bureautique, CAO, sécurité…" /></label>
            <label style={{ gridColumn: "span 3" }}>Motifs de reconnaissance sur les postes (un par ligne ; le nom du logiciel suffit souvent ; <code>re:</code> pour une expression régulière)<br />
              <textarea rows={2} style={{ width: "100%" }} value={sw.patterns} onChange={(e) => setSw({ ...sw, patterns: e.target.value })} placeholder={"Microsoft 365 Apps\nOffice 365"} /></label>
            <label>Paquet winget<br /><input value={sw.pkg_winget} onChange={(e) => setSw({ ...sw, pkg_winget: e.target.value })} placeholder="Éditeur.Produit" /></label>
            <label>Paquet apt<br /><input value={sw.pkg_apt} onChange={(e) => setSw({ ...sw, pkg_apt: e.target.value })} /></label>
            <label>Paquet brew / dnf<br /><input value={sw.pkg_brew} onChange={(e) => setSw({ ...sw, pkg_brew: e.target.value, pkg_dnf: e.target.value })} /></label>
          </div>
          <div style={{ marginTop: 6 }}><button type="button" onClick={saveSw} disabled={!sw.name}>Enregistrer</button> <button type="button" className="secondary" onClick={() => setSw(null)}>Annuler</button>
            {sw.id && <button type="button" className="secondary" style={{ marginLeft: 12 }} onClick={async () => { const r = await api.deleteSoftware(b, t, sw.id); notice(r.error || "logiciel supprimé", !r.error); if (!r.error) { setSw(null); reload(); } }}>Supprimer</button>}</div>
        </div>
      )}
      <div style={{ display: "grid", gridTemplateColumns: "2fr 1fr", gap: 10 }}>
        <Scroll>
          <table style={{ width: "100%", fontSize: 13 }}>
            <thead style={TH}><tr><th> </th><th>Logiciel</th><th>Site</th><th>Libellé</th><th>Type</th><th>Licences</th><th>Attribuées</th><th>Fin</th><th>Coût / an</th><th>Vendeur / SKU</th><th> </th></tr></thead>
            <tbody>
              {shown.map((c) => (
                <tr key={c.id}>
                  <td><Lamp tone={contractTone(c)} /></td><td><b>{c.software}</b><br /><span className="muted">{c.vendor}</span></td><td>{c.site}</td><td>{c.label}</td><td>{KIND_LABEL[c.kind] || c.kind}</td>
                  <td>{c.quantity || "∞"}</td><td><Tone tone={c.quantity && c.assigned > c.quantity ? "red" : "inherit"}>{c.assigned}</Tone></td>
                  <td>{c.end || ""}{c.days_left != null && <><br /><Tone tone={c.days_left < 0 ? "red" : c.days_left <= 60 ? "orange" : "grey"}>{fmtDays(c.days_left)}</Tone></>}</td>
                  <td>{c.cost ? `${c.cost} ${c.currency || ""}` : ""}</td><td className="muted" style={{ fontSize: 12 }}>{[c.vendor_account, c.sku].filter(Boolean).join(" / ")}</td>
                  <td><button type="button" className="secondary" onClick={() => setCt({ ...EMPTY_CT, ...c })}>modifier</button> <button type="button" className="secondary" onClick={async () => { const r = await api.deleteContract(b, t, c.id); notice(r.error || "contrat supprimé", !r.error); reload(); }}>×</button></td>
                </tr>
              ))}
              {!shown.length && <tr><td colSpan={11} className="muted">aucun contrat.</td></tr>}
            </tbody>
          </table>
        </Scroll>
        <div>
          <div className="hub-card" style={{ marginBottom: 10 }}>
            <h3 style={{ marginTop: 0 }}>Importer un tableur</h3>
            <p className="muted" style={{ marginTop: 0, fontSize: 12 }}>Formats reconnus : matrice « Logiciel | Éditeur | Licence | Date Fin | personnes… » (croix), export utilisateurs Microsoft 365 (colonnes Nom complet / Licences), comparatif licence × initiales. Analyser d'abord, puis importer : logiciels et contrats manquants sont créés sur le site choisi, les personnes attribuées.</p>
            <input type="file" accept=".xlsx,.csv" onChange={(e) => setImp({ ...imp, file: e.target.files?.[0] || null, plan: null, done: null })} /><br />
            <input list="lic-sites" placeholder="site" value={imp.site} onChange={(e) => setImp({ ...imp, site: e.target.value })} />{" "}
            <select value={imp.format} onChange={(e) => setImp({ ...imp, format: e.target.value, plan: null })}><option value="">format : détection</option><option value="matrix">matrice</option><option value="m365">export Microsoft 365</option><option value="comparatif">comparatif</option></select>
            <div style={{ marginTop: 6, display: "flex", gap: 8, alignItems: "center" }}>
              <button type="button" className={imp.plan ? "" : "secondary"} onClick={doImport} disabled={!imp.file || !!imp.busy}>
                {imp.busy ? `⏳ ${imp.busy}` : imp.plan ? `Importer ${imp.plan.length} logiciel(s)${imp.site ? ` sur ${imp.site}` : ""}` : "1. Analyser le fichier"}
              </button>
              {!imp.file && <span className="muted" style={{ fontSize: 12 }}>choisir un fichier d'abord</span>}
              {imp.plan && !imp.busy && <button type="button" className="secondary" onClick={() => setImp({ ...imp, plan: null })}>annuler</button>}
            </div>
            {imp.done && <p style={{ margin: "6px 0 0", fontSize: 12 }}><Tone tone="green">✓ {imp.done}</Tone></p>}
            {imp.plan && (
              <div style={{ marginTop: 6, fontSize: 12 }}>
                <span className="muted">2. Vérifier — format {imp.detected} · {imp.plan.length} logiciel(s) · {imp.people} personne(s) — puis importer</span>
                {imp.unknown?.length > 0 && <p style={{ margin: "4px 0" }}><Tone tone="orange">{imp.unknown.length} personne(s) absente(s) de l'annuaire</Tone> <span className="muted">(créées « info » sur le site, rattachées plus tard par « Utilisateurs → Synchroniser l'annuaire ») : {imp.unknown.join(", ")}</span></p>}
                <ul style={{ margin: "4px 0", paddingLeft: 18, maxHeight: 180, overflow: "auto" }}>{imp.plan.map((p, i) => <li key={i}><b>{p.software}</b>{p.vendor ? ` (${p.vendor})` : ""} · {p.people.length} personne(s){p.end ? ` · fin ${p.end}` : ""}
                  {p.people.length > 0 && <span className="muted"> : {(p.resolved || []).map((x) => x.login ? x.login : `${x.person} ?`).join(", ")}</span>}</li>)}</ul>
              </div>
            )}
          </div>
          <Scroll max="calc(100vh - 560px)">
            <table style={{ width: "100%", fontSize: 13 }}>
              <thead style={TH}><tr><th>Catalogue</th><th>Éditeur</th><th>Motifs</th></tr></thead>
              <tbody>{shownSw.map((s) => <tr key={s.id} style={{ cursor: "pointer" }} onClick={() => editSw(s)}><td>{s.name}</td><td className="muted">{s.vendor}</td><td className="muted" style={{ fontSize: 12 }}>{(s.patterns || []).join(", ") || <em>nom</em>}</td></tr>)}</tbody>
            </table>
          </Scroll>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
function Grid({ b, t, site, contracts, reload, notice }) {
  const [grid, setGrid] = useState(null);
  const [query, setQuery] = useState("");
  const [kind, setKind] = useState("");
  const [add, setAdd] = useState({ kind: "user", subject: "" });
  const load = useCallback(() => api.fetchGrid(b, t, site).then((r) => (r.error ? notice(r.error, false) : setGrid(r))), [b, t, site]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load, contracts]);
  const rows = useMemo(() => filterRows((grid?.rows || []).filter((r) => !kind || r.kind === kind), query), [grid, query, kind]);
  const cols = useMemo(() => (grid?.columns || []).map((c) => ({ ...c, contracts: c.contracts.map((x) => ({ ...x, assigned: (contracts.find((y) => y.id === x.id) || {}).assigned || 0 })) })), [grid, contracts]);
  const toggle = async (row, col, cell) => {
    if (cell.assigned) {
      const r = await api.deleteAssignment(b, t, cell.assigned);
      notice(r.error || `${row.subject} : ${col.name} retiré`, !r.error);
    } else {
      const c = pickContract(col, row.kind);
      if (!c) return notice("aucun contrat pour ce logiciel", false);
      const r = await api.addAssignment(b, t, { contract_id: c.id, subject_kind: row.kind, subject: row.subject, site: row.site || site || "" });
      notice(r.error || `${row.subject} : ${col.name} attribué${r.over ? " — DÉPASSEMENT du contrat" : ""}`, !r.error && !r.over);
    }
    reload(); load();
  };
  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <input type="search" placeholder="filtrer (poste, utilisateur, site)" value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 240 }} />
        <select value={kind} onChange={(e) => setKind(e.target.value)}><option value="">postes et utilisateurs</option><option value="host">postes</option><option value="user">utilisateurs</option></select>
        <span className="muted">{rows.length} ligne(s) × {cols.length} logiciel(s) sous contrat</span>
        <span style={{ marginLeft: "auto" }} className="muted">ajouter une ligne :</span>
        <select value={add.kind} onChange={(e) => setAdd({ ...add, kind: e.target.value })}><option value="user">utilisateur</option><option value="host">poste</option></select>
        <input placeholder={add.kind === "user" ? "prenom.nom ou adresse" : "nom du poste"} value={add.subject} onChange={(e) => setAdd({ ...add, subject: e.target.value })} />
        <button type="button" className="secondary" disabled={!add.subject.trim() || !cols.length} onClick={() => { const col = cols[0]; toggle({ kind: add.kind, subject: add.subject.trim(), site }, col, { assigned: null }); setAdd({ ...add, subject: "" }); }}>+ (attribue {cols[0]?.name || "…"})</button>
      </div>
      <p className="muted" style={{ margin: "0 0 6px", fontSize: 12 }}>Une case = une attribution (clic pour attribuer / retirer). ✓ attribué · ● installé sur le poste (relevé de l'agent) · ✓● cohérent · ● seul = installé sans attribution · ✓ seul sur un poste = attribué mais absent. Les utilisateurs viennent des attributions et des sessions vues par les agents.</p>
      <Scroll>
        <table style={{ fontSize: 13, borderCollapse: "collapse" }}>
          <thead style={TH}>
            <tr><th style={{ textAlign: "left", position: "sticky", left: 0, background: "var(--panel, #222)", zIndex: 2 }}>Sujet</th><th>Site</th>
              {cols.map((c) => <th key={c.id} title={c.contracts.map((x) => `${x.label || x.id} (${KIND_LABEL[x.kind] || x.kind}, ${x.assigned}/${x.quantity || "∞"})`).join("\n")}>{c.name}<br /><span className="muted" style={{ fontWeight: 400 }}>{c.contracts.reduce((n, x) => n + (x.assigned || 0), 0)}/{c.contracts.reduce((n, x) => n + (x.quantity || 0), 0) || "∞"}</span></th>)}</tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={`${r.kind}:${r.subject}`}>
                <td style={{ position: "sticky", left: 0, background: "var(--panel, #222)", whiteSpace: "nowrap" }} title={r.name || ""}>{r.kind === "host" ? "💻" : "👤"} {r.subject}{r.name && r.name !== r.subject ? <span className="muted"> {r.name}</span> : null}</td><td className="muted">{r.site || ""}</td>
                {r.cells.map((cell, i) => {
                  const col = cols[i];
                  const tone = cell.assigned && cell.installed ? "green" : cell.assigned ? (r.kind === "host" ? "orange" : "green") : cell.installed ? "red" : "grey";
                  return <td key={i} style={{ textAlign: "center", cursor: "pointer" }} title={`${r.subject} × ${col?.name}${cell.assigned ? ` — contrat ${cell.contract_id}` : ""}`} onClick={() => toggle(r, col, cell)}>
                    <Tone tone={tone}>{cell.assigned ? "✓" : ""}{cell.installed ? "●" : ""}{!cell.assigned && !cell.installed ? "·" : ""}</Tone></td>;
                })}
              </tr>
            ))}
            {grid && !rows.length && <tr><td colSpan={2 + cols.length} className="muted">aucune ligne : ajouter un utilisateur / poste ci-dessus, ou activer la sonde <code>software-inventory</code> sur <a href={hubLink("si-agent", { section: "plugins" })}>les agents des postes</a>.</td></tr>}
          </tbody>
        </table>
      </Scroll>
    </div>
  );
}

// ---------------------------------------------------------------------------
// #597 : utilisateurs par site -- l'annuaire (Keycloak fédéré LDAP, seule source
// d'authentification) fait référence ; les personnes des imports / vendeurs sont
// des « infos » rattachées au compte LDAP dès qu'il existe.
const EMPTY_U = { login: "", name: "", mail: "", site: "", aliases: "" };
function Users({ b, t, site, sites, notice, reload }) {
  const [list, setList] = useState(null);
  const [query, setQuery] = useState("");
  const [u, setU] = useState(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api.fetchUsers(b, t, site).then((r) => (r.error ? notice(r.error, false) : setList(r.users || []))), [b, t, site]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load]);
  const shown = useMemo(() => filterUsers(list, query), [list, query]);
  const save = async () => {
    const r = await api.saveUser(b, t, { login: u.login, name: u.name, mail: u.mail, site: u.site, aliases: String(u.aliases || "").split(/[,;\n]/).map((x) => x.trim()).filter(Boolean) });
    notice(r.error || `utilisateur ${r.login} enregistré`, !r.error);
    if (!r.error) { setU(null); load(); reload(); }
  };
  const setSite = async (x, s) => { const r = await api.saveUser(b, t, { login: x.login, site: s }); notice(r.error || `${x.login} → ${s || "sans site"}`, !r.error); load(); reload(); };
  const sync = async () => {
    setBusy("synchronisation…");
    const r = await api.syncUsers(b, t);
    setBusy("");
    notice(r.error || `annuaire : ${r.directory} compte(s), ${r.added} ajouté(s), ${r.linked} rattaché(s)`, !r.error);
    load(); reload();
  };
  const nDir = (list || []).filter((x) => x.directory).length;
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        L'<b>annuaire</b> (comptes Keycloak fédérés LDAP, via la tuile <a href={hubLink("accounts")}>Comptes</a>) est la référence : ces lignes sont marquées 🗂. Les personnes venues d'un import ou d'un vendeur sont des <em>infos</em> (ℹ) rattachées au compte LDAP dès qu'il existe (login, adresse ou « Prénom Nom »). Le <b>site</b> se renseigne ici (jamais écrasé par la synchronisation) et alimente la grille et les contrats.
      </p>
      <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
        <input type="search" placeholder="filtrer (login, nom, adresse, site)" value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 240 }} />
        <span className="muted">{shown.length} / {(list || []).length} utilisateur(s) · {nDir} de l'annuaire</span>
        <button type="button" onClick={sync} disabled={!!busy}>{busy ? `⏳ ${busy}` : "Synchroniser l'annuaire"}</button>
        <button type="button" className="secondary" onClick={() => setU({ ...EMPTY_U, site: site || "" })}>+ utilisateur (info)</button>
      </div>
      {u && (
        <div className="hub-card" style={{ marginBottom: 10 }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(4, 1fr)", gap: 8 }}>
            <label>Login (identifiant LDAP si connu)<br /><input value={u.login} onChange={(e) => setU({ ...u, login: e.target.value })} disabled={!!u._edit} /></label>
            <label>Nom<br /><input value={u.name} onChange={(e) => setU({ ...u, name: e.target.value })} /></label>
            <label>Adresse<br /><input value={u.mail} onChange={(e) => setU({ ...u, mail: e.target.value })} /></label>
            <label>Site<br /><input list="lic-sites3" value={u.site} onChange={(e) => setU({ ...u, site: e.target.value })} /><datalist id="lic-sites3">{sites.map((s) => <option key={s} value={s} />)}</datalist></label>
            <label style={{ gridColumn: "span 4" }}>Autres écritures (initiales, ancien login, surnom — virgules)<br /><input style={{ width: "100%" }} value={u.aliases} onChange={(e) => setU({ ...u, aliases: e.target.value })} /></label>
          </div>
          <div style={{ marginTop: 6 }}><button type="button" onClick={save} disabled={!u.login.trim()}>Enregistrer</button> <button type="button" className="secondary" onClick={() => setU(null)}>Annuler</button></div>
        </div>
      )}
      <Scroll>
        <table style={{ width: "100%", fontSize: 13 }}>
          <thead style={TH}><tr><th> </th><th>Login</th><th>Nom</th><th>Adresse</th><th>Site</th><th>Attributions</th><th>Autres écritures</th><th> </th></tr></thead>
          <tbody>
            {shown.map((x) => (
              <tr key={x.login} style={{ opacity: x.enabled === 0 ? 0.55 : 1 }}>
                <td title={x.directory ? "compte de l'annuaire" : `info (${x.source})`}>{x.directory ? "🗂" : "ℹ"}</td><td><b>{x.login}</b>{x.enabled === 0 && <span className="muted"> (désactivé)</span>}</td><td>{x.name}</td><td className="muted">{x.mail}</td>
                <td><select value={x.site || ""} onChange={(e) => setSite(x, e.target.value)}><option value="">—</option>{[...new Set([...sites, x.site].filter(Boolean))].map((s) => <option key={s} value={s}>{s}</option>)}</select></td>
                <td>{x.assigned || 0}</td><td className="muted" style={{ fontSize: 12 }}>{(x.aliases || []).join(", ")}</td>
                <td><button type="button" className="secondary" onClick={() => setU({ ...EMPTY_U, ...x, aliases: (x.aliases || []).join(", "), _edit: true })}>modifier</button>{" "}
                  {!x.directory && <button type="button" className="secondary" onClick={async () => { const r = await api.deleteUser(b, t, x.login); notice(r.error || `${x.login} supprimé`, !r.error); load(); }}>×</button>}</td>
              </tr>
            ))}
            {list && !shown.length && <tr><td colSpan={8} className="muted">aucun utilisateur : « Synchroniser l'annuaire », importer un tableur, ou ajouter une info.</td></tr>}
          </tbody>
        </table>
      </Scroll>
    </div>
  );
}

// ---------------------------------------------------------------------------
function Hosts({ b, t, site, software, notice }) {
  const [data, setData] = useState(null);
  const [query, setQuery] = useState("");
  const [sel, setSel] = useState(null);
  const [detail, setDetail] = useState(null);
  const [dq, setDq] = useState("");
  const [act, setAct] = useState({ action: "install", package: "", manager: "", confirm: "", software_id: "" });
  const [actions, setActions] = useState([]);
  const load = useCallback(() => api.fetchInstallations(b, t, site).then((r) => (r.error ? notice(r.error, false) : setData(r))), [b, t, site]);  // eslint-disable-line react-hooks/exhaustive-deps
  const loadActions = useCallback(() => api.fetchActions(b, t).then((r) => !r.error && setActions(r.actions || [])), [b, t]);
  useEffect(() => { load(); loadActions(); }, [load, loadActions]);
  useEffect(() => {
    if (!sel) return;
    api.fetchInstallation(b, t, sel.agent_id, dq).then((r) => !r.error && setDetail(r));
  }, [b, t, sel, dq]);
  useEffect(() => {
    if (!actions.some((a) => ["pending", "acked"].includes(a.status))) return undefined;
    const id = setInterval(loadActions, 10000);
    return () => clearInterval(id);
  }, [actions, loadActions]);
  const hosts = useMemo(() => filterHosts(data?.hosts, query), [data, query]);
  const unknown = useMemo(() => (data?.unknown || []).filter((u) => !query || (u.name || "").toLowerCase().includes(query.toLowerCase())), [data, query]);
  const pickSoftware = (sid) => {
    const s = software.find((x) => String(x.id) === String(sid));
    const mgr = act.manager || defaultManager(sel?.os);
    setAct({ ...act, software_id: sid, package: (s?.package || {})[mgr] || act.package });
  };
  const send = async () => {
    const r = await api.createAction(b, t, { agent_id: sel.agent_id, host: sel.hostname, action: act.action, package: act.package.trim(), manager: act.manager || undefined, software_id: act.software_id ? Number(act.software_id) : undefined, confirm: act.confirm.trim() });
    notice(r.error || `${act.action === "install" ? "installation" : "désinstallation"} de ${act.package} demandée à ${sel.hostname} (commande ${r.command_id})`, !r.error);
    if (!r.error) { setAct({ ...act, confirm: "" }); loadActions(); }
  };
  const mine = actions.filter((a) => !sel || a.agent_id === sel.agent_id);
  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 1.4fr", gap: 10 }}>
      <div>
        <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 6 }}>
          <input type="search" placeholder="filtrer (poste, site, OS, utilisateur)" value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 220 }} />
          <span className="muted">{hosts.length} poste(s)</span><button type="button" className="secondary" onClick={load}>↻</button>
        </div>
        <Scroll max="calc(100vh - 520px)">
          <table style={{ width: "100%", fontSize: 13 }}>
            <thead style={TH}><tr><th>Poste</th><th>Site</th><th>OS</th><th>Sessions</th><th>Logiciels</th><th>Relevé</th></tr></thead>
            <tbody>
              {hosts.map((h) => <tr key={h.agent_id} style={{ cursor: "pointer", background: sel?.agent_id === h.agent_id ? "rgba(255,255,255,.08)" : undefined }} onClick={() => { setSel(h); setDetail(null); setAct({ ...act, manager: "", confirm: "" }); }}>
                <td><b>{h.hostname}</b>{h.warnings?.length ? <span title={h.warnings.join("\n")}> ⚠</span> : null}</td><td>{h.site}</td><td className="muted">{h.os}</td><td className="muted">{(h.users || []).join(", ")}</td><td>{h.count}</td><td className="muted" style={{ fontSize: 12 }}>{when(h.at)}</td>
              </tr>)}
              {data && !hosts.length && <tr><td colSpan={6} className="muted">aucun relevé : activer la sonde <code>software-inventory</code> (désactivée par défaut, toutes les 6 h) sur <a href={hubLink("si-agent", { section: "plugins" })}>les agents des postes</a> (agent ≥ 0.5.16).</td></tr>}
            </tbody>
          </table>
        </Scroll>
        <h4 style={{ margin: "10px 0 4px" }}>Vus sur les postes, absents du catalogue <span className="muted">({unknown.length})</span></h4>
        <p className="muted" style={{ margin: "0 0 4px", fontSize: 12 }}>Bruit système exclu. Un clic ajoute le logiciel au catalogue (motif = nom relevé) : il apparaît alors dans les écarts « installé sans contrat ».</p>
        <Scroll max="220px">
          <table style={{ width: "100%", fontSize: 12 }}>
            <thead style={TH}><tr><th>Nom relevé</th><th>Éditeur</th><th>Postes</th></tr></thead>
            <tbody>{unknown.slice(0, 200).map((u, i) => <tr key={i} style={{ cursor: "pointer" }} title="ajouter au catalogue" onClick={async () => { const r = await api.saveSoftware(b, t, { name: u.name, vendor: u.publisher || "", patterns: [u.name] }); notice(r.error || `${u.name} ajouté au catalogue`, !r.error); }}><td>{u.name}</td><td className="muted">{u.publisher}</td><td>{u.hosts?.length ?? u.count ?? ""}</td></tr>)}</tbody>
          </table>
        </Scroll>
      </div>
      <div>
        {!sel ? <p className="muted">Choisir un poste : logiciels installés (filtre), installation / désinstallation par l'agent du poste, historique des actions.</p> : (
          <>
            <div className="hub-card" style={{ marginBottom: 8 }}>
              <h3 style={{ margin: "0 0 6px" }}>💻 {sel.hostname} <span className="muted" style={{ fontWeight: 400 }}>{sel.os} · {sel.site} · agent {sel.agent_id}</span></h3>
              <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
                <select value={act.action} onChange={(e) => setAct({ ...act, action: e.target.value })}><option value="install">installer</option><option value="uninstall">désinstaller</option></select>
                <select value={act.software_id} onChange={(e) => pickSoftware(e.target.value)}><option value="">logiciel du catalogue…</option>{software.map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
                <input placeholder="paquet (ex. Mozilla.Firefox, vim)" value={act.package} onChange={(e) => setAct({ ...act, package: e.target.value })} style={{ minWidth: 200 }} />
                <select value={act.manager} onChange={(e) => setAct({ ...act, manager: e.target.value })}><option value="">gestionnaire : {defaultManager(sel.os)} (défaut)</option>{["winget", "choco", "apt", "dnf", "brew"].map((m) => <option key={m} value={m}>{m}</option>)}</select>
              </div>
              <div style={{ display: "flex", gap: 8, alignItems: "center", marginTop: 6 }}>
                <input placeholder={`taper « ${sel.agent_id} » pour confirmer`} value={act.confirm} onChange={(e) => setAct({ ...act, confirm: e.target.value })} style={{ minWidth: 260 }} />
                <button type="button" onClick={send} disabled={!act.package.trim() || act.confirm.trim() !== sel.agent_id}>{act.action === "install" ? "Installer" : "Désinstaller"} sur ce poste</button>
                <span className="muted" style={{ fontSize: 12 }}>exécuté par l'agent du poste (winget / choco / apt / dnf / brew), journalisé et notifié.</span>
              </div>
            </div>
            <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 4 }}>
              <input type="search" placeholder="filtrer les logiciels installés" value={dq} onChange={(e) => setDq(e.target.value)} />
              <span className="muted">{detail ? `${detail.installed.length} logiciel(s)` : "…"}</span>
            </div>
            <Scroll max="calc(100vh - 620px)">
              <table style={{ width: "100%", fontSize: 12 }}>
                <thead style={TH}><tr><th>Nom</th><th>Éditeur</th><th>Version</th><th>Source</th><th> </th></tr></thead>
                <tbody>{(detail?.installed || []).map((x, i) => <tr key={i}><td>{x.name}</td><td className="muted">{x.publisher}</td><td className="muted">{x.version}</td><td className="muted">{x.source}</td>
                  <td><button type="button" className="secondary" style={{ fontSize: 11 }} onClick={() => setAct({ ...act, action: "uninstall", package: x.id || x.name, manager: { dpkg: "apt", rpm: "dnf", winget: "winget", apt: "apt", dnf: "dnf", brew: "brew" }[x.source] || act.manager })}>désinstaller…</button></td></tr>)}</tbody>
              </table>
            </Scroll>
            <h4 style={{ margin: "10px 0 4px" }}>Actions {sel ? `sur ${sel.hostname}` : ""}</h4>
            <Scroll max="160px">
              <table style={{ width: "100%", fontSize: 12 }}>
                <thead style={TH}><tr><th>Quand</th><th>Action</th><th>Paquet</th><th>État</th><th>Résultat</th><th>Par</th></tr></thead>
                <tbody>{mine.map((a) => <tr key={a.id}><td className="muted">{when(a.created_at)}</td><td>{a.action === "install" ? "installer" : "désinstaller"}</td><td>{a.package}{a.manager ? <span className="muted"> ({a.manager})</span> : null}</td>
                  <td><Tone tone={a.status === "done" ? "green" : a.status === "failed" ? "red" : "orange"}>{ACTION_STATUS[a.status] || a.status}</Tone></td><td className="muted" style={{ maxWidth: 260, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }} title={a.result}>{a.result}</td><td className="muted">{a.user}</td></tr>)}
                  {!mine.length && <tr><td colSpan={6} className="muted">aucune action.</td></tr>}</tbody>
              </table>
            </Scroll>
          </>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
const EMPTY_V = { name: "", kind: "microsoft-graph", site: "", tenant: "", client_id: "", credential: "" };
function Vendors({ b, t, sites, notice, reload }) {
  const [list, setList] = useState([]);
  const [v, setV] = useState(null);
  const [busy, setBusy] = useState("");
  const load = useCallback(() => api.fetchVendors(b, t).then((r) => (r.error ? notice(r.error, false) : setList(r.vendors || []))), [b, t]);  // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { load(); }, [load]);
  const save = async () => {
    const r = await api.saveVendor(b, t, { name: v.name, kind: v.kind, site: v.site, config: { tenant: v.tenant, client_id: v.client_id }, credential: v.credential });
    notice(r.error || `compte ${r.name} enregistré`, !r.error);
    if (!r.error) { setV(null); load(); }
  };
  const sync = async (name) => {
    setBusy(name);
    const r = await api.syncVendor(b, t, name);
    setBusy("");
    notice(r.error || `${name} : ${r.skus} SKU, ${r.updated} contrat(s) mis à jour, ${r.created_contracts} créé(s)`, !r.error);
    load(); reload();
  };
  return (
    <div>
      <p className="muted" style={{ marginTop: 0 }}>
        Un compte vendeur lit l'état des licences chez l'éditeur et met à jour les contrats liés (par SKU) : quantités et utilisateurs attribués (note « vendeur »).
        <b> Microsoft 365</b> : application Entra ID avec la permission <code>Organization.Read.All</code> + <code>User.Read.All</code> (application) ; le secret client est le mot de passe d'un accès du <a href={hubLink("credentials")}>coffre des accès</a> (nom de l'accès = champ « accès »), jamais saisi ici.
        Les autres éditeurs sans API : « export du vendeur » (déposer leur fichier dans « Contrats & catalogue → Importer ») ou saisie manuelle.
      </p>
      <button type="button" onClick={() => setV({ ...EMPTY_V })}>+ compte vendeur</button>
      {v && (
        <div className="hub-card" style={{ margin: "8px 0" }}>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
            <label>Nom (identifiant)<br /><input value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} placeholder="m365-site-alpha" /></label>
            <label>Type<br /><select value={v.kind} onChange={(e) => setV({ ...v, kind: e.target.value })}>{Object.entries(VENDOR_KIND_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></label>
            <label>Site<br /><input list="lic-sites2" value={v.site} onChange={(e) => setV({ ...v, site: e.target.value })} /><datalist id="lic-sites2">{sites.map((s) => <option key={s} value={s} />)}</datalist></label>
            {v.kind === "microsoft-graph" && <>
              <label>Tenant (id ou domaine)<br /><input value={v.tenant} onChange={(e) => setV({ ...v, tenant: e.target.value })} placeholder="exemple.onmicrosoft.com" /></label>
              <label>Client id (application)<br /><input value={v.client_id} onChange={(e) => setV({ ...v, client_id: e.target.value })} /></label>
              <label>Accès du coffre (secret client)<br /><input value={v.credential} onChange={(e) => setV({ ...v, credential: e.target.value })} placeholder="nom de l'accès" /></label>
            </>}
          </div>
          <div style={{ marginTop: 6 }}><button type="button" onClick={save} disabled={!v.name}>Enregistrer</button> <button type="button" className="secondary" onClick={() => setV(null)}>Annuler</button></div>
        </div>
      )}
      <Scroll>
        <table style={{ width: "100%", fontSize: 13 }}>
          <thead style={TH}><tr><th>Compte</th><th>Type</th><th>Site</th><th>Configuration</th><th>Dernière synchronisation</th><th>Dernier relevé</th><th> </th></tr></thead>
          <tbody>
            {list.map((x) => (
              <tr key={x.name}>
                <td><b>{x.name}</b></td><td>{VENDOR_KIND_LABEL[x.kind] || x.kind}</td><td>{x.site}</td>
                <td className="muted" style={{ fontSize: 12 }}>{x.kind === "microsoft-graph" ? `${x.config?.tenant || "?"} · ${x.config?.client_id || "?"} · accès « ${x.credential || "?"} »` : ""}</td>
                <td>{x.last_sync ? when(x.last_sync) : <span className="muted">jamais</span>}{x.last_error && <><br /><Tone tone="red">{x.last_error}</Tone></>}</td>
                <td className="muted" style={{ fontSize: 12 }}>{(x.snapshot || []).map((s) => `${s.label} : ${s.consumed ?? "?"}/${s.quantity}`).join(" · ")}</td>
                <td>{x.kind === "microsoft-graph" && <button type="button" onClick={() => sync(x.name)} disabled={busy === x.name}>{busy === x.name ? "…" : "Synchroniser"}</button>}{" "}
                  <button type="button" className="secondary" onClick={() => setV({ ...EMPTY_V, ...x, tenant: x.config?.tenant || "", client_id: x.config?.client_id || "" })}>modifier</button>{" "}
                  <button type="button" className="secondary" onClick={async () => { const r = await api.deleteVendor(b, t, x.name); notice(r.error || "compte supprimé", !r.error); load(); }}>×</button></td>
              </tr>
            ))}
            {!list.length && <tr><td colSpan={7} className="muted">aucun compte vendeur.</td></tr>}
          </tbody>
        </table>
      </Scroll>
    </div>
  );
}

// ---------------------------------------------------------------------------
function Log({ b, t }) {
  const [events, setEvents] = useState([]);
  useEffect(() => { api.fetchEvents(b, t).then((r) => !r.error && setEvents(r.events || [])); }, [b, t]);
  return (
    <Scroll>
      <table style={{ width: "100%", fontSize: 12 }}>
        <thead style={TH}><tr><th>Quand</th><th>Événement</th><th>Détail</th><th>Par</th></tr></thead>
        <tbody>{events.map((e, i) => <tr key={i}><td className="muted">{when(e.at)}</td><td>{e.event}</td><td>{e.text}</td><td className="muted">{e.user}</td></tr>)}{!events.length && <tr><td colSpan={4} className="muted">journal vide.</td></tr>}</tbody>
      </table>
    </Scroll>
  );
}

// ---------------------------------------------------------------------------
export default function LicensesView({ apiBase, accessToken, username, onBack }) {
  const params = useMemo(() => viewParams(), []);
  const [tab, setTab] = useState(TABS.some((x) => x.id === params.tab) ? params.tab : "dash");
  const [site, setSite] = useState(params.site || "");
  const [sites, setSites] = useState([]);
  const [software, setSoftware] = useState([]);
  const [contracts, setContracts] = useState([]);
  const [notice, setNotice] = useState(null);
  const say = (text, ok = true) => setNotice({ text, ok });
  const reload = useCallback(() => {
    if (!apiBase) return;
    api.fetchSites(apiBase, accessToken).then((r) => !r.error && setSites(r.sites || []));
    api.fetchSoftware(apiBase, accessToken).then((r) => (r.error ? say(r.error, false) : setSoftware(r.software || [])));
    api.fetchContracts(apiBase, accessToken, site).then((r) => (r.error ? say(r.error, false) : setContracts(r.contracts || [])));
  }, [apiBase, accessToken, site]);
  useEffect(() => { reload(); }, [reload]);
  if (!apiBase) return <PageFrame title="🪪 Licences logicielles" onBack={onBack}><p className="muted">licenses-api non configurée (<code>VITE_LICENSES_API_BASE_URL</code>).</p></PageFrame>;
  const b = apiBase, t = accessToken;
  const common = { b, t, site, sites, software, contracts, reload, notice: say };
  return (
    <PageFrame title="🪪 Licences logicielles" onBack={onBack}
      actions={<>
        <select value={site} onChange={(e) => setSite(e.target.value)} title="site"><option value="">tous les sites</option>{sites.map((s) => <option key={s} value={s}>{s}</option>)}</select>
        {TABS.map((x) => <button key={x.id} type="button" className={`secondary na-section-toggle${tab === x.id ? " active" : ""}`} onClick={() => setTab(x.id)}>{x.label}</button>)}
      </>}
      foot={<span>par site · contrats → attributions poste / utilisateur → installations relevées par les agents → écarts · connecté en tant que {username || "?"}{notice ? <> · <span style={{ color: notice.ok ? COLORS.green : COLORS.red }}>{notice.text}</span></> : null}</span>}>
      {tab === "dash" && <Dashboard {...common} />}
      {tab === "contracts" && <Contracts {...common} />}
      {tab === "grid" && <Grid {...common} />}
      {tab === "users" && <Users {...common} />}
      {tab === "hosts" && <Hosts {...common} />}
      {tab === "vendors" && <Vendors {...common} />}
      {tab === "log" && <Log b={b} t={t} />}
    </PageFrame>
  );
}
