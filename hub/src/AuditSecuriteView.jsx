// Audit de sécurité réseau d'un site (#958) : collecte Nebula (API) + historiques accumulés + relevés shell (Proxmox,
// hôtes non gérés) + constats manuels → constats cotés (probabilité × impact), matrice 4×4, préconisations priorisées,
// exports Markdown / CSV pour la réunion. Logique pure : auditSecuriteLib.js. API : nebula-api /sites/<site>/audit*.
import { useCallback, useEffect, useMemo, useState } from "react";
import BoutonDetail, { FenetreTexte } from "./FenetreTexte.jsx";
import { COULEUR_NIVEAU, FOND_NIVEAU, LIBELLE_PROBA, LIBELLE_IMPACT, SITE_KEY, filtrer, grille, resume, commandesAide, texteConstat, ageCollecte } from "./auditSecuriteLib.js";

const store = {
  get(k, d) { try { return JSON.parse(localStorage.getItem(k) || "null") ?? d; } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* stockage indisponible */ } },
};
async function getJson(url, init) {
  const r = await fetch(url, { credentials: "include", ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}
const send = (m) => (url, body) => getJson(url, { method: m, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const putJson = send("PUT"), postJson = send("POST");
const DOMAINES_FORM = ["acces", "exposition", "wifi", "segmentation", "equipements", "hyperviseur", "iot", "inventaire", "exploitation"];
const VIDE = { titre: "", domaine: "acces", preuve: "", preconisation: "", probabilite: 2, impact: 3, effort: "moyen", element: "" };

export default function AuditSecuriteView({ onBack, nebulaApiBase }) {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState(() => store.get(SITE_KEY, ""));
  const [audit, setAudit] = useState(null);
  const [err, setErr] = useState(null);
  const [busy, setBusy] = useState(null);       // libellé de l'action en cours
  const [msg, setMsg] = useState(null);
  const [filtre, setFiltre] = useState({});
  const [onglet, setOnglet] = useState("constats");   // constats | preconisations | sources
  const [importSrc, setImportSrc] = useState("proxmox");
  const [importTexte, setImportTexte] = useState("");
  const [manuel, setManuel] = useState(VIDE);
  const [formOuvert, setFormOuvert] = useState(null);  // "import" | "manuel" | "reglages" | null
  const [reglages, setReglages] = useState({ vlans_serveurs: [], vlans_iot: [] });
  const [aide, setAide] = useState(null);
  const base = `${nebulaApiBase}/sites/${encodeURIComponent(siteId)}`;

  useEffect(() => {
    getJson(`${nebulaApiBase}/reperage/sites`).then((d) => { const s = (d.sites || []).filter((x) => !x.test); setSites(s); if (!siteId && s[0]) setSiteId(s[0].site_id); }).catch((e) => setErr("Nebula : " + e.message));
    /* eslint-disable-next-line react-hooks/exhaustive-deps */
  }, [nebulaApiBase]);
  useEffect(() => { if (siteId) store.set(SITE_KEY, siteId); }, [siteId]);

  const charger = useCallback(async () => {
    if (!siteId) return;
    setErr(null);
    try { const [a, r] = await Promise.all([getJson(`${base}/audit`), getJson(`${base}/audit/reglages`)]); setAudit(a); setReglages(r); }
    catch (e) { setErr(e.message); }
  }, [base, siteId]);
  useEffect(() => { charger(); }, [charger]);

  const action = async (libelle, fn, okText) => {
    setBusy(libelle); setMsg(null);
    try { const r = await fn(); setMsg({ ok: true, text: okText ? okText(r) : "✓ fait" }); await charger(); }
    catch (e) { setMsg({ ok: false, text: e.message }); }
    finally { setBusy(null); }
  };
  const collecter = () => action("collecte", () => postJson(`${base}/audit/collecter`, { quoi: ["nebula", "historiques"] }),
    (r) => `✓ Nebula : ${r.nebula?.ok ? `${r.nebula.ssids} SSID, ${r.nebula.clients} clients, ${r.nebula.nat} règle(s) NAT${r.nebula.erreurs?.length ? ` — partiel : ${r.nebula.erreurs.join(" ; ")}` : ""}` : `échec : ${r.nebula?.erreur}`} · historiques : ${r.historiques?.clients_vus} clients vus, ${r.historiques?.anomalies} anomalie(s)`);
  const importer = () => action("import", () => postJson(`${base}/audit/importer`, { source: importSrc, donnees: importTexte }), (r) => { setImportTexte(""); setFormOuvert(null); return `✓ relevé ${r.source} « ${r.libelle} » importé`; });
  const ajouterManuel = () => action("manuel", () => postJson(`${base}/audit/importer`, { source: "manuel", donnees: manuel }), () => { setManuel(VIDE); setFormOuvert(null); return "✓ constat ajouté"; });
  const majConstat = (id, patch) => action(`constat:${id}`, () => putJson(`${base}/audit/constats/${encodeURIComponent(id)}`, patch), () => "✓ enregistré");
  const supprimerCollecte = (id) => action(`collecte:${id}`, () => getJson(`${base}/audit/collectes/${id}`, { method: "DELETE" }), () => "✓ relevé retiré");
  const enregistrerReglages = () => action("reglages", () => putJson(`${base}/audit/reglages`, reglages), () => { setFormOuvert(null); return "✓ réglages enregistrés"; });

  const constats = useMemo(() => filtrer(audit?.constats, filtre), [audit, filtre]);
  const g = useMemo(() => grille(audit?.matrice), [audit]);
  const dom = audit?.domaines || {}, etats = audit?.etats || {}, niveaux = audit?.niveaux || {};
  const cmd = commandesAide(nebulaApiBase, siteId);
  const enCours = (k) => busy === k;

  return (
    <section className="view audit-securite">
      <header className="view-header">
        <button type="button" className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🛡 Audit de sécurité réseau</h1>
        <select value={siteId} onChange={(e) => { setSiteId(e.target.value); setAudit(null); }} aria-label="site">
          {!siteId && <option value="">— site —</option>}
          {sites.map((s) => <option key={s.site_id} value={s.site_id}>{s.name}</option>)}
        </select>
        <button type="button" onClick={collecter} disabled={!siteId || !!busy} title="relit l'API Nebula (SSID, VLAN, NAT, états, micrologiciels, licences, clients) et les historiques accumulés du hub">{enCours("collecte") ? "⏳ collecte en cours…" : "🔄 Collecter Nebula + historiques"}</button>
        <button type="button" className="secondary" onClick={() => setFormOuvert(formOuvert === "import" ? null : "import")} disabled={!siteId}>📥 Importer un relevé</button>
        <button type="button" className="secondary" onClick={() => setFormOuvert(formOuvert === "manuel" ? null : "manuel")} disabled={!siteId}>✍️ Constat manuel</button>
        <button type="button" className="secondary" onClick={() => setFormOuvert(formOuvert === "reglages" ? null : "reglages")} disabled={!siteId}>⚙️ Réglages</button>
        {siteId && <a className="button secondary" href={`${base}/audit.md`} download>⬇ Rapport .md</a>}
        {siteId && <a className="button secondary" href={`${base}/audit.csv`} download>⬇ CSV</a>}
      </header>
      {err && <p className="error">{err}</p>}
      {msg && <p className={msg.ok ? "ok" : "error"}>{msg.text}</p>}

      {formOuvert === "import" && (
        <div className="panel">
          <h3>Importer un relevé shell (JSON produit par <code>{cmd.scripts}</code>)</h3>
          <p>
            <label>Source <select value={importSrc} onChange={(e) => setImportSrc(e.target.value)}><option value="proxmox">Hyperviseur Proxmox (audit-proxmox.sh)</option><option value="hote">Hôte non géré (audit-hote.sh : passerelle LoRa, écran, objet…)</option></select></label>
            {" "}<button type="button" className="secondary" onClick={() => setAide({ titre: "Commandes à lancer (lecture seule)", texte: `${cmd.proxmox}\n\n${cmd.hote}` })}>🛈 commandes</button>
          </p>
          <textarea rows={8} style={{ width: "100%" }} value={importTexte} onChange={(e) => setImportTexte(e.target.value)} placeholder='{"hostname": "...", ...} — coller le JSON ou le charger' />
          <p><input type="file" accept=".json,application/json" onChange={(e) => { const f = e.target.files?.[0]; if (f) f.text().then(setImportTexte); }} />
            {" "}<button type="button" onClick={importer} disabled={!importTexte.trim() || !!busy}>{enCours("import") ? "⏳ envoi…" : "Importer"}</button></p>
        </div>
      )}
      {formOuvert === "manuel" && (
        <div className="panel">
          <h3>Constat saisi à la main (accès distant, mot de passe par défaut, procédure absente…)</h3>
          <p><input style={{ width: "60%" }} placeholder="titre du constat" value={manuel.titre} onChange={(e) => setManuel({ ...manuel, titre: e.target.value })} />
            {" "}<select value={manuel.domaine} onChange={(e) => setManuel({ ...manuel, domaine: e.target.value })}>{DOMAINES_FORM.map((d) => <option key={d} value={d}>{dom[d] || d}</option>)}</select></p>
          <p><input style={{ width: "100%" }} placeholder="preuve / élément concerné" value={manuel.preuve} onChange={(e) => setManuel({ ...manuel, preuve: e.target.value })} /></p>
          <p><input style={{ width: "100%" }} placeholder="préconisation" value={manuel.preconisation} onChange={(e) => setManuel({ ...manuel, preconisation: e.target.value })} /></p>
          <p>
            <label>Probabilité <select value={manuel.probabilite} onChange={(e) => setManuel({ ...manuel, probabilite: Number(e.target.value) })}>{[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} · {LIBELLE_PROBA[n]}</option>)}</select></label>
            {" "}<label>Impact <select value={manuel.impact} onChange={(e) => setManuel({ ...manuel, impact: Number(e.target.value) })}>{[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} · {LIBELLE_IMPACT[n]}</option>)}</select></label>
            {" "}<label>Effort <select value={manuel.effort} onChange={(e) => setManuel({ ...manuel, effort: e.target.value })}><option value="faible">faible</option><option value="moyen">moyen</option><option value="fort">fort</option></select></label>
            {" "}<button type="button" onClick={ajouterManuel} disabled={!manuel.titre.trim() || !!busy}>{enCours("manuel") ? "⏳ envoi…" : "Ajouter"}</button>
          </p>
        </div>
      )}
      {formOuvert === "reglages" && (
        <div className="panel">
          <h3>Réglages de cotation</h3>
          <p><label>VLAN des serveurs (séparés par des virgules) <input value={reglages.vlans_serveurs.join(",")} onChange={(e) => setReglages({ ...reglages, vlans_serveurs: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })} /></label>
            {" "}<label>VLAN réservés aux objets connectés <input value={reglages.vlans_iot.join(",")} onChange={(e) => setReglages({ ...reglages, vlans_iot: e.target.value.split(",").map((x) => x.trim()).filter(Boolean) })} /></label>
            {" "}<button type="button" onClick={enregistrerReglages} disabled={!!busy}>{enCours("reglages") ? "⏳…" : "Enregistrer"}</button></p>
          <p className="muted">Un objet connecté vu sur un VLAN serveurs = impact majeur ; sur un VLAN « objets » = normal.</p>
        </div>
      )}

      {audit && (
        <>
          <div className="panel audit-synthese" style={{ display: "flex", gap: "1.5rem", flexWrap: "wrap", alignItems: "flex-start" }}>
            <div>
              <h3>Matrice des risques <small className="muted">(impact ↓ × probabilité →, cliquer une case pour filtrer)</small></h3>
              <table className="audit-matrice"><tbody>
                {g.map((ligne, k) => (
                  <tr key={k}><th>{ligne[0].i} · {LIBELLE_IMPACT[ligne[0].i]}</th>
                    {ligne.map((c) => (
                      <td key={c.p} onClick={() => setFiltre(filtre.cas && filtre.cas.p === c.p && filtre.cas.i === c.i ? {} : { cas: { p: c.p, i: c.i } })}
                        style={{ background: FOND_NIVEAU[c.niveau], color: COULEUR_NIVEAU[c.niveau], textAlign: "center", width: "4.5rem", height: "2.6rem", cursor: "pointer", fontWeight: c.n ? 700 : 400,
                          outline: filtre.cas && filtre.cas.p === c.p && filtre.cas.i === c.i ? "2px solid var(--accent)" : "none" }}>{c.n || "·"}</td>))}
                  </tr>))}
                <tr><th /> {[1, 2, 3, 4].map((p) => <th key={p}>{p} · {LIBELLE_PROBA[p]}</th>)}</tr>
              </tbody></table>
            </div>
            <div>
              <p><strong>{audit.site}</strong> — {resume(audit.matrice)}</p>
              <p className="muted">Sources : {audit.sources.length ? audit.sources.map((s) => `${s.source} (${s.libelle}, ${ageCollecte(s.at)})`).join(" · ") : "aucune collecte — lancer « Collecter »"}</p>
              <p>
                <button type="button" className={onglet === "constats" ? "" : "secondary"} onClick={() => setOnglet("constats")}>Constats ({audit.constats.length})</button>
                {" "}<button type="button" className={onglet === "preconisations" ? "" : "secondary"} onClick={() => setOnglet("preconisations")}>Préconisations ({audit.preconisations.length})</button>
                {" "}<button type="button" className={onglet === "sources" ? "" : "secondary"} onClick={() => setOnglet("sources")}>Relevés ({audit.sources.length})</button>
              </p>
            </div>
          </div>

          {onglet === "constats" && (
            <div className="panel">
              <p>
                <select value={filtre.domaine || ""} onChange={(e) => setFiltre({ ...filtre, domaine: e.target.value || undefined })}><option value="">tous domaines</option>{Object.entries(dom).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
                {" "}<select value={filtre.niveau || ""} onChange={(e) => setFiltre({ ...filtre, niveau: e.target.value || undefined })}><option value="">tous niveaux</option>{Object.entries(niveaux).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
                {" "}<select value={filtre.etat || ""} onChange={(e) => setFiltre({ ...filtre, etat: e.target.value || undefined })}><option value="">tous états</option>{Object.entries(etats).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
                {" "}<input placeholder="rechercher" value={filtre.q || ""} onChange={(e) => setFiltre({ ...filtre, q: e.target.value })} />
                {Object.keys(filtre).length > 0 && <> <button type="button" className="secondary" onClick={() => setFiltre({})}>✕ filtres</button></>}
              </p>
              <table className="table"><thead><tr><th>Niveau</th><th>Domaine</th><th>Constat</th><th>P</th><th>I</th><th>État</th><th /></tr></thead><tbody>
                {constats.map((c) => (
                  <tr key={c.id} style={{ borderLeft: `4px solid ${COULEUR_NIVEAU[c.niveau]}` }}>
                    <td style={{ color: COULEUR_NIVEAU[c.niveau], fontWeight: 700, whiteSpace: "nowrap" }}>{niveaux[c.niveau]} {c.score}</td>
                    <td>{dom[c.domaine] || c.domaine}</td>
                    <td><strong>{c.titre}</strong><br /><small className="muted">{c.preuve}</small>{c.preconisation && <><br /><small>→ {c.preconisation} <em>(effort {c.effort})</em></small></>}
                      {c.note && <><br /><small>📝 {c.note}</small></>}</td>
                    <td><select value={c.probabilite} onChange={(e) => majConstat(c.id, { probabilite: e.target.value })} title="probabilité">{[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}</select></td>
                    <td><select value={c.impact} onChange={(e) => majConstat(c.id, { impact: e.target.value })} title="impact">{[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}</select></td>
                    <td><select value={c.etat || "a_traiter"} onChange={(e) => majConstat(c.id, { etat: e.target.value })}>{Object.entries(etats).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
                      {enCours(`constat:${c.id}`) && " ⏳"}</td>
                    <td style={{ whiteSpace: "nowrap" }}>
                      <BoutonDetail texte={texteConstat(c, dom)} titre={c.titre} urgence={c.niveau === "critique" ? "critique" : c.niveau === "eleve" ? "alerte" : "info"} />
                      {" "}<button type="button" className="secondary" title="note" onClick={() => { const n = window.prompt("Note (contexte, décision, responsable)", c.note || ""); if (n !== null) majConstat(c.id, { note: n }); }}>📝</button>
                    </td>
                  </tr>))}
                {!constats.length && <tr><td colSpan={7} className="muted">{audit.constats.length ? "aucun constat avec ces filtres" : "aucun constat : collecter d'abord, puis importer les relevés Proxmox / hôtes"}</td></tr>}
              </tbody></table>
            </div>
          )}

          {onglet === "preconisations" && (
            <div className="panel">
              <p className="muted">Ordre : score décroissant, effort faible d'abord ; les constats traités ou acceptés n'apparaissent pas.</p>
              <table className="table"><thead><tr><th>#</th><th>Action</th><th>Niveau</th><th>Effort</th><th>Constat</th></tr></thead><tbody>
                {audit.preconisations.map((p) => (
                  <tr key={p.id}><td>{p.rang}</td><td>{p.action}</td><td style={{ color: COULEUR_NIVEAU[p.niveau], fontWeight: 700 }}>{niveaux[p.niveau]} {p.score}</td><td>{p.effort}</td><td><small>{p.constat}</small></td></tr>))}
              </tbody></table>
            </div>
          )}

          {onglet === "sources" && (
            <div className="panel">
              <table className="table"><thead><tr><th>Source</th><th>Libellé</th><th>Date</th><th>Erreurs</th><th /></tr></thead><tbody>
                {audit.sources.map((s) => (
                  <tr key={s.id}><td>{s.source}</td><td>{s.libelle}</td><td>{ageCollecte(s.at)}</td>
                    <td>{s.erreurs?.length ? <BoutonDetail texte={s.erreurs.join("\n")} titre="Appels Nebula en erreur" urgence="alerte" libelle={`${s.erreurs.length} erreur(s)`} /> : "—"}</td>
                    <td><button type="button" className="secondary" onClick={() => supprimerCollecte(s.id)} disabled={!!busy}>{enCours(`collecte:${s.id}`) ? "⏳" : "✕"}</button></td></tr>))}
              </tbody></table>
              <p><button type="button" className="secondary" onClick={() => setAide({ titre: "Relevés shell (lecture seule)", texte: `${cmd.proxmox}\n\n${cmd.hote}` })}>🛈 commandes des relevés Proxmox / hôtes</button></p>
            </div>
          )}
        </>
      )}
      {aide && <FenetreTexte titre={aide.titre} texte={aide.texte} onFermer={() => setAide(null)} />}
    </section>
  );
}
