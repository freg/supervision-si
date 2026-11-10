// #872 : historique des clients du réseau Nebula (Nebula ne garde que 24 h) -- relève horaire + « Relever maintenant »,
// requête filtrée (texte : MAC avec ou sans séparateurs, IP, nom, fabricant, équipement, SSID ; fabricant ; équipement ;
// vu entre deux dates ; « plus vu depuis ») et triée (clic sur l'en-tête). Clic sur une ligne : périodes de présence.
import { Fragment, useCallback, useEffect, useState } from "react";
import IpPing from "./IpPing.jsx";
import NebulaRelevesCalendrier from "./NebulaRelevesCalendrier.jsx";   // #974 : diodes des relèves
import { texteNouveautes } from "./relevesLib.js";
import { resumeActivite, barres, resumeCategorie, texteCategorie } from "./activiteLib.js";
import BoutonDetail from "./FenetreTexte.jsx";   // #1002 : activité du client (présence, rythme, volumes)

const COLS = [
  ["mac", "MAC"], ["ip", "IP"], ["name", "Nom"], ["manufacturer", "Fabricant"], ["device", "Raccordé à"],
  ["first_seen", "1re vue"], ["last_seen", "Dernière vue"], ["seen_count", "Relèves"],
];
const fmt = (s) => (s ? new Date(s * 1000).toLocaleString("fr-FR", { day: "2-digit", month: "2-digit", year: "2-digit", hour: "2-digit", minute: "2-digit" }) : "—");
const epoch = (d) => (d ? Math.floor(new Date(d).getTime() / 1000) : "");
const depuis = (s) => { if (!s) return ""; const h = (Date.now() / 1000 - s) / 3600; return h < 1 ? "en ligne" : h < 48 ? `il y a ${Math.round(h)} h` : `il y a ${Math.round(h / 24)} j`; };

export default function NebulaClientHistory({ nebulaApiBase, siteId }) {
  const [f, setF] = useState({ q: "", manufacturer: "", device: "", since: "", until: "", absent_since: "" });
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
  const [page, setPage] = useState(0);
  const [versionCal, setVersionCal] = useState(0);
  const PAGE = 200;

  const params = useCallback(() => {
    const p = new URLSearchParams({ sort: tri.sort, order: tri.order, limit: PAGE, offset: page * PAGE });
    if (siteId) p.set("site", siteId);
    for (const k of ["q", "manufacturer", "device"]) if (f[k].trim()) p.set(k, f[k].trim());
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
  }, [nebulaApiBase, siteId]);

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
    setSel(row); setSess(null); setAct(null); setCat(null);
    fetch(`${nebulaApiBase}/client-history/categorie?site=${encodeURIComponent(row.site_id)}&mac=${encodeURIComponent(row.mac)}`, { credentials: "include" })
      .then((r) => r.json()).then((j) => setCat(j && !j.error ? j : { erreur: (j && j.error) || "?" })).catch((e) => setCat({ erreur: e.message }));
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
        <label>vu du {champ("since", { type: "date" })}</label>
        <label>au {champ("until", { type: "date" })}</label>
        <label title="clients disparus : dernière vue avant cette date">plus vu depuis {champ("absent_since", { type: "date" })}</label>
        <button type="button" className="secondary" onClick={() => setF({ q: "", manufacturer: "", device: "", since: "", until: "", absent_since: "" })}>Effacer</button>
      </div>
      {err && <p style={{ color: "var(--danger)" }}>{err}</p>}
      <div className="infra-muted">{d ? `${d.total} client(s)` : "lecture…"}{d && d.total > PAGE && <> · page {page + 1}/{Math.ceil(d.total / PAGE)}{" "}
        <button type="button" className="secondary" disabled={page === 0} onClick={() => setPage(page - 1)}>‹</button>{" "}
        <button type="button" className="secondary" disabled={(page + 1) * PAGE >= d.total} onClick={() => setPage(page + 1)}>›</button></>}</div>
      <div style={{ maxHeight: "calc(100vh - 380px)", overflow: "auto", minHeight: 200 }}>
        <table className="services infra-table" style={{ width: "100%" }}>
          <thead><tr>
            {COLS.map(([k, l]) => <th key={k} onClick={() => trier(k)} className={tri.sort === k ? "sorted" : ""}>{l}{tri.sort === k ? (tri.order === "asc" ? " ▲" : " ▼") : ""}</th>)}
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
                </tr>
                {sel?.mac === r.mac && (
                  <tr><td colSpan={COLS.length}>
                    <div style={{ marginBottom: 8 }}>
                      {cat === null ? <span className="muted">catégorie : lecture…</span> : cat.erreur ? <span style={{ color: "var(--danger)" }}>catégorie : {cat.erreur}</span> : (
                        <>
                          <b>{resumeCategorie(cat)}</b>{" "}
                          <BoutonDetail titre="Catégorie : hypothèses et preuves" urgence={cat.incertain ? "alerte" : "info"} texte={texteCategorie(cat)} />
                          {(cat.singularites || []).length > 0 && <span className="muted"> — singulier : {cat.singularites.map((s) => s.texte).join(" ; ")}</span>}
                        </>)}
                    </div>
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
