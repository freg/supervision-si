// #872 : historique des clients du réseau Nebula (Nebula ne garde que 24 h) -- relève horaire + « Relever maintenant »,
// requête filtrée (texte : MAC avec ou sans séparateurs, IP, nom, fabricant, équipement, SSID ; fabricant ; équipement ;
// vu entre deux dates ; « plus vu depuis ») et triée (clic sur l'en-tête). Clic sur une ligne : périodes de présence.
import { Fragment, useCallback, useEffect, useState } from "react";
import IpPing from "./IpPing.jsx";
import NebulaRelevesCalendrier from "./NebulaRelevesCalendrier.jsx";   // #974 : diodes des relèves
import { texteNouveautes } from "./relevesLib.js";
import { resumeActivite, barres, resumeCategorie, texteCategorie, celluleCategorie, celluleType } from "./activiteLib.js";
import { hubLink } from "./hubLinks.js";
import BoutonDetail from "./FenetreTexte.jsx";   // #1002 : activité du client (présence, rythme, volumes)

const COLS = [
  ["mac", "MAC"], ["ip", "IP"], ["name", "Nom"], ["manufacturer", "Fabricant"], ["device", "Raccordé à"],
  ["first_seen", "1re vue"], ["last_seen", "Dernière vue"], ["seen_count", "Relèves"],
];
const fmt = (s) => (s ? new Date(s * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
const epoch = (d) => (d ? Math.floor(new Date(d).getTime() / 1000) : "");
const depuis = (s) => { if (!s) return ""; const h = (Date.now() / 1000 - s) / 3600; return h < 1 ? "en ligne" : h < 48 ? `il y a ${Math.round(h)} h` : `il y a ${Math.round(h / 24)} j`; };

export default function NebulaClientHistory({ nebulaApiBase, siteId, groups = [], login = "" }) {
  const [f, setF] = useState({ q: "", manufacturer: "", device: "", since: "", until: "", absent_since: "", categorie: "", certitude: "", type: "", certitude_type: "" });
  const [tri, setTri] = useState({ sort: "last_seen", order: "desc" });
  const [d, setD] = useState(null);
  const [err, setErr] = useState(null);
  const [st, setSt] = useState(null);
  const [fab, setFab] = useState([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [sel, setSel] = useState(null);
  const [sess, setSess] = useState(null);
  const [act, setAct] = useState(null);
  const [cat, setCat] = useState(null);
  const [menus, setMenus] = useState(null);          // #1004 : catégories présentes et niveaux de certitude
  const [choix, setChoix] = useState("");            // catégorie à confirmer / corriger
  const [choixType, setChoixType] = useState("");    // #1007 : type à confirmer / corriger
  const [decision, setDecision] = useState(null);    // {enCours, erreur, reglage, texte}
  const [decisionT, setDecisionT] = useState(null);  // #1007 : message de la confirmation de type
  const [page, setPage] = useState(0);
  const [versionCal, setVersionCal] = useState(0);
  const PAGE = 200;

  const params = useCallback(() => {
    const p = new URLSearchParams({ sort: tri.sort, order: tri.order, limit: PAGE, offset: page * PAGE });
    if (siteId) p.set("site", siteId);
    for (const k of ["q", "manufacturer", "device", "categorie", "certitude", "type", "certitude_type"]) if (f[k].trim()) p.set(k, f[k].trim());
    for (const k of ["since", "until", "absent_since"]) if (f[k]) p.set(k, epoch(f[k]));
    return p;
  }, [f, tri, page, siteId]);

  const load = useCallback(async () => {
    try {
      const r = await fetch(`${nebulaApiBase}/client-history?${params()}`, { credentials: "include" });
      const j = await r.json();
      if (!r.ok) throw new Error(j.error || r.status);
      setD(j); setErr(null);
    } catch (e) { setErr(String(e.message || e)); }
  }, [nebulaApiBase, params]);
  const loadStatus = useCallback(() => {
    fetch(`${nebulaApiBase}/client-history/status`, { credentials: "include" }).then((r) => r.json()).then(setSt).catch(() => setSt(null));
    fetch(`${nebulaApiBase}/client-history/manufacturers${siteId ? `?site=${encodeURIComponent(siteId)}` : ""}`, { credentials: "include" })
      .then((r) => r.json()).then((j) => setFab(j.manufacturers || [])).catch(() => setFab([]));
    fetch(`${nebulaApiBase}/client-history/categories${siteId ? `?site=${encodeURIComponent(siteId)}` : ""}`, { credentials: "include" })
      .then((r) => r.json()).then(setMenus).catch(() => setMenus(null));
  }, [nebulaApiBase, siteId]);
  const lireCategorie = (row) => fetch(`${nebulaApiBase}/client-history/categorie?site=${encodeURIComponent(row.site_id)}&mac=${encodeURIComponent(row.mac)}`, { credentials: "include" })
    .then((r) => r.json()).then((j) => { setCat(j && !j.error ? j : { erreur: (j && j.error) || "?" }); setChoix((j && j.categorie) || ""); setChoixType((j && j.type && j.type.categorie) || ""); })
    .catch((e) => setCat({ erreur: e.message }));
  const decider = async (row, methode, axe = "categorie") => {
    const setDec = axe === "type" ? setDecisionT : setDecision;   // #1007 : confirmation par axe
    const valeur = axe === "type" ? choixType : choix;
    setDec({ enCours: true });
    try {
      const r = await fetch(`${nebulaApiBase}/client-history/categorie/decision`, { method: methode, credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ site: row.site_id, mac: row.mac, axe, categorie: valeur, groups, user: login }) });
      const j = await r.json();
      if (!r.ok) { setDec({ erreur: j.error || `HTTP ${r.status}`, reglage: j.reglage }); return; }
      setDec({ texte: methode === "DELETE" ? "Confirmation annulée : la proposition du hub revient, l'apprentissage est retiré."
        : j.correction ? `Corrigé en « ${j.categorie} » (le hub proposait « ${j.proposee || "rien"} ») : les clients aux traits semblables en tiennent compte.`
          : `Confirmé « ${j.categorie} » : les clients aux traits semblables en tiennent compte.` });
      await lireCategorie(row); load(); loadStatus();
    } catch (e) { setDec({ erreur: e.message }); }
  };

  useEffect(() => { const t = setTimeout(load, 300); return () => clearTimeout(t); }, [load]);
  useEffect(() => { loadStatus(); const t = setInterval(loadStatus, 60000); return () => clearInterval(t); }, [loadStatus]);
  useEffect(() => { setPage(0); }, [f, tri]);

  const relever = async () => {
    setBusy(true); setMsg("relève en cours…");
    try {
      const r = await fetch(`${nebulaApiBase}/client-history/poll`, { method: "POST", credentials: "include" });
      const j = await r.json();
      setMsg(r.ok ? `relève faite : ${(j.sites || []).map((s) => `${s.clients ?? 0} client(s)${texteNouveautes(s.nouveautes) ? ` — ${texteNouveautes(s.nouveautes)}` : " — rien de nouveau"}${s.error ? ` (${s.error})` : ""}`).join(", ")}` : j.error);
      load(); loadStatus(); setVersionCal((v) => v + 1);
    } catch (e) { setMsg(String(e.message || e)); }
    setBusy(false);
  };
  const ouvrir = async (row) => {
    if (sel?.mac === row.mac) { setSel(null); return; }
    setSel(row); setSess(null); setAct(null); setCat(null); setDecision(null); setDecisionT(null);
    lireCategorie(row);
    fetch(`${nebulaApiBase}/client-history/activite?site=${encodeURIComponent(row.site_id)}&mac=${encodeURIComponent(row.mac)}&jours=14`, { credentials: "include" })
      .then((r) => r.json()).then((j) => setAct(j && !j.error ? j : { erreur: (j && j.error) || "?" })).catch((e) => setAct({ erreur: e.message }));
    try {
      const r = await fetch(`${nebulaApiBase}/client-history/sessions?site=${encodeURIComponent(row.site_id)}&mac=${encodeURIComponent(row.mac)}`, { credentials: "include" });
      setSess((await r.json()).sessions || []);
    } catch { setSess([]); }
  };
  const trier = (k) => setTri((t) => ({ sort: k, order: t.sort === k && t.order === "desc" ? "asc" : "desc" }));
  const champ = (k, props) => <input value={f[k]} onChange={(e) => setF((x) => ({ ...x, [k]: e.target.value }))} {...props} />;
  const dernier = st?.polls?.[0];
  const exportUrl = `${nebulaApiBase}/client-history/export.csv?${(() => { const p = params(); p.delete("limit"); p.delete("offset"); return p; })()}`;

  return (
    <div className="nebula-histo" style={{ display: "flex", flexDirection: "column", gap: 8, minHeight: 0 }}>
      <div className="infra-muted">
        Relève toutes les {st ? Math.round(st.interval_s / 60) : "…"} min · {st?.clients ?? "…"} client(s) connus depuis {fmt(st?.depuis)} · conservation {st?.retention_days ?? 400} j
        {dernier && <> · dernière relève {fmt(dernier.at)} ({dernier.trigger}{dernier.error ? ` — ${dernier.error}` : ""})</>}
        {st && !st.configured && <b style={{ color: "var(--danger)" }}> · clé Nebula non configurée (pas de lien : opération manuelle — NEBULA_API_KEY dans .env)</b>}
        {" "}<button type="button" onClick={relever} disabled={busy}>{busy ? "Relève…" : "Relever maintenant"}</button>
        {" "}<a href={exportUrl}>Exporter (CSV)</a>
        {msg && <span> · {msg}</span>}
      </div>
      <NebulaRelevesCalendrier nebulaApiBase={nebulaApiBase} siteId={siteId} version={versionCal} />
      <div style={{ display: "flex", flexWrap: "wrap", gap: 8, alignItems: "center" }}>
        {champ("q", { placeholder: "MAC, IP, nom, fabricant, équipement, SSID", style: { minWidth: 260 } })}
        <select value={f.manufacturer} onChange={(e) => setF((x) => ({ ...x, manufacturer: e.target.value }))}>
          <option value="">tous fabricants</option>
          {fab.map((m) => <option key={m.manufacturer} value={m.manufacturer}>{m.manufacturer} ({m.n})</option>)}
        </select>
        {champ("device", { placeholder: "raccordé à (borne, commutateur)" })}
        <select value={f.categorie} onChange={(e) => setF((x) => ({ ...x, categorie: e.target.value }))} title="catégorie proposée ou confirmée (#1004)">
          <option value="">toutes catégories</option>
          {(menus?.categories || []).map((c) => <option key={c.categorie} value={c.categorie}>{c.categorie === "aucune" ? "sans catégorie" : c.categorie} ({c.n})</option>)}
        </select>
        <select value={f.certitude} onChange={(e) => setF((x) => ({ ...x, certitude: e.target.value }))} title="niveau de certitude de la catégorie">
          <option value="">toutes certitudes</option>
          {(menus?.niveaux || []).map((n) => <option key={n.niveau} value={n.niveau} disabled={!n.n}>{n.libelle} ({n.n})</option>)}
        </select>
        <select value={f.type} onChange={(e) => setF((x) => ({ ...x, type: e.target.value }))} title="type d'appareil : forme (tablette, mobile, portable, fixe, réseau, supervision) (#1007)">
          <option value="">tous types</option>
          {(menus?.types || []).map((c) => <option key={c.type} value={c.type}>{c.type === "aucun" ? "sans type" : c.type} ({c.n})</option>)}
        </select>
        <select value={f.certitude_type} onChange={(e) => setF((x) => ({ ...x, certitude_type: e.target.value }))} title="niveau de certitude du type">
          <option value="">certitude (type)</option>
          {(menus?.niveaux_type || []).map((n) => <option key={n.niveau} value={n.niveau} disabled={!n.n}>{n.libelle} ({n.n})</option>)}
        </select>
        <label>vu du {champ("since", { type: "date" })}</label>
        <label>au {champ("until", { type: "date" })}</label>
        <label title="clients disparus : dernière vue avant cette date">plus vu depuis {champ("absent_since", { type: "date" })}</label>
        <button type="button" className="secondary" onClick={() => setF({ q: "", manufacturer: "", device: "", since: "", until: "", absent_since: "", categorie: "", certitude: "", type: "", certitude_type: "" })}>Effacer</button>
      </div>
      {err && <p style={{ color: "var(--danger)" }}>{err}</p>}
      <div className="infra-muted">{d ? `${d.total} client(s)` : "lecture…"}{d && d.total > PAGE && <> · page {page + 1}/{Math.ceil(d.total / PAGE)}{" "}
        <button type="button" className="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>‹</button>{" "}
        <button type="button" className="secondary" disabled={(page + 1) * PAGE >= d.total} onClick={() => setPage(page + 1)}>›</button></>}</div>
      <div style={{ maxHeight: "calc(100vh - 380px)", overflow: "auto", minHeight: 200 }}>
        <table className="services infra-table" style={{ width: "100%" }}>
          <thead><tr>
            {COLS.map(([k, l]) => <th key={k} onClick={() => trier(k)} className={tri.sort === k ? "sorted" : ""}>{l}{tri.sort === k ? (tri.order === "asc" ? " ▲" : " ▼") : ""}</th>)}
            <th title="catégorie proposée (confiance) ou confirmée ✔">Catégorie</th>
            <th title="type d'appareil : forme (tablette, mobile, portable, fixe…) ✔ si confirmé">Type</th>
          </tr></thead>
          <tbody>
            {(d?.rows || []).map((r) => (
              <Fragment key={r.site_id + r.mac}>
                <tr onClick={() => ouvrir(r)} style={{ cursor: "pointer" }} className={sel?.mac === r.mac ? "selected" : ""}>
                  <td><code>{r.mac}</code></td>
                  <td onClick={(e) => e.stopPropagation()}><IpPing os={false} ip={r.ip} /></td>
                  <td>{r.name || "—"}</td>
                  <td>{r.manufacturer || "—"}</td>
                  <td>{r.device || "—"}{r.port ? ` · port ${r.port}` : ""}{r.ssid ? ` · ${r.ssid}` : ""}{r.vlan ? ` · VLAN ${r.vlan}` : ""}</td>
                  <td>{fmt(r.first_seen)}</td>
                  <td>{fmt(r.last_seen)} <span className="infra-muted">{depuis(r.last_seen)}</span></td>
                  <td>{r.seen_count}</td>
                  <td style={{ color: celluleCategorie(r).couleur, whiteSpace: "nowrap" }}>{celluleCategorie(r).texte}</td>
                  <td style={{ color: celluleType(r).couleur, whiteSpace: "nowrap" }}>{celluleType(r).texte}</td>
                </tr>
                {sel?.mac === r.mac && (
                  <tr><td colSpan={COLS.length + 2}>
                    <div style={{ marginBottom: 8 }}>
                      {cat === null ? <span className="muted">catégorie : lecture…</span> : cat.erreur ? <span style={{ color: "var(--danger)" }}>catégorie : {cat.erreur}</span> : (
                        <>
                          <b>{resumeCategorie(cat)}</b>{" "}
                          <BoutonDetail titre="Catégorie : hypothèses et preuves" urgence={cat.incertain ? "alerte" : "info"} texte={texteCategorie(cat)} />
                          {(cat.singularites || []).length > 0 && <span className="muted"> — singulier : {cat.singularites.map((s) => s.texte).join(" ; ")}</span>}
                          <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginTop: 4 }}>
                            <span className="muted">C'est bien :</span>
                            <select value={choix} onChange={(e) => setChoix(e.target.value)}>
                              <option value="">choisir…</option>
                              {(menus?.toutes || []).map((c) => <option key={c} value={c}>{c}</option>)}
                            </select>
                            <button type="button" disabled={!choix || decision?.enCours} onClick={() => decider(r, "POST")}>
                              {decision?.enCours ? "⏳ en cours…" : choix && cat.categorie && choix !== cat.categorie ? "✎ Corriger" : "✔ Confirmer"}</button>
                            {cat.decision && <button type="button" className="secondary" disabled={decision?.enCours} onClick={() => decider(r, "DELETE")}>Annuler la confirmation</button>}
                            {decision?.texte && <span style={{ color: "var(--ok)" }}>{decision.texte}</span>}
                            {decision?.erreur && <span style={{ color: "var(--danger)" }}>{decision.erreur}{decision.reglage && <> — <a href={hubLink(decision.reglage.view)}>régler les droits</a> ({decision.reglage.texte})</>}</span>}
                          </div>
                        </>)}
                    </div>
                    {cat && !cat.erreur && (
                    <div style={{ marginBottom: 8 }}>
                      <b>{resumeCategorie(cat.type, "Type")}</b>{" "}
                      <BoutonDetail titre="Type : hypothèses et preuves" urgence={cat.type && cat.type.incertain ? "alerte" : "info"} texte={texteCategorie(cat.type, "Type")} />
                      {cat.type && (cat.type.singularites || []).length > 0 && <span className="muted"> — singulier : {cat.type.singularites.map((sg) => sg.texte).join(" ; ")}</span>}
                      <div style={{ display: "flex", gap: 6, alignItems: "center", flexWrap: "wrap", marginTop: 4 }}>
                        <span className="muted">C'est bien :</span>
                        <select value={choixType} onChange={(e) => setChoixType(e.target.value)}>
                          <option value="">choisir…</option>
                          {(menus?.tous_types || []).map((c) => <option key={c} value={c}>{c}</option>)}
                        </select>
                        <button type="button" disabled={!choixType || decisionT?.enCours} onClick={() => decider(r, "POST", "type")}>
                          {decisionT?.enCours ? "⏳ en cours…" : choixType && cat.type && cat.type.categorie && choixType !== cat.type.categorie ? "✎ Corriger" : "✔ Confirmer"}</button>
                        {cat.type && cat.type.decision && <button type="button" className="secondary" disabled={decisionT?.enCours} onClick={() => decider(r, "DELETE", "type")}>Annuler la confirmation</button>}
                        {decisionT?.texte && <span style={{ color: "var(--ok)" }}>{decisionT.texte}</span>}
                        {decisionT?.erreur && <span style={{ color: "var(--danger)" }}>{decisionT.erreur}{decisionT.reglage && <> — <a href={hubLink(decisionT.reglage.view)}>régler les droits</a> ({decisionT.reglage.texte})</>}</span>}
                      </div>
                    </div>)}
                    <div style={{ marginBottom: 8 }}>
                      <b>Activité sur 14 jours</b>
                      {act === null ? <span className="muted"> — lecture…</span> : act.erreur ? <span style={{ color: "var(--danger)" }}> — {act.erreur}</span> : (
                        <>
                          <div style={{ display: "flex", alignItems: "flex-end", gap: 2, height: 40, margin: "6px 0 2px" }} title="Présence par heure de la journée (nombre de jours)">
                            {barres(act.histogramme).map((h, i) => <div key={i} title={`${i} h : ${act.histogramme[i]} jour(s)`} style={{ width: 10, height: `${Math.max(2, h * 40)}px`, background: h ? "var(--accent)" : "var(--border)" }} />)}
                          </div>
                          <div className="muted" style={{ display: "flex", gap: 2, fontSize: "0.75em" }}>{act.histogramme.map((_x, i) => <span key={i} style={{ width: 10, textAlign: "center" }}>{i % 6 === 0 ? i : ""}</span>)}</div>
                          <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>{resumeActivite(act).map((l, i) => <li key={i}>{l}</li>)}</ul>
                        </>)}
                    </div>
                    {sess === null ? "lecture des périodes…" : sess.length === 0 ? "aucune période enregistrée" : (
                      <table className="services infra-table" style={{ width: "100%" }}>
                        <thead><tr><th>Du</th><th>Au</th><th>IP</th><th>Raccordé à</th><th>Port</th><th>SSID</th><th>VLAN</th></tr></thead>
                        <tbody>{sess.map((s, i) => <tr key={i}><td>{fmt(s.start)}</td><td>{fmt(s.end)}</td><td>{s.ip || "—"}</td><td>{s.device || "—"}</td><td>{s.port || "—"}</td><td>{s.ssid || "—"}</td><td>{s.vlan || "—"}</td></tr>)}</tbody>
                      </table>)}
                  </td></tr>)}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
