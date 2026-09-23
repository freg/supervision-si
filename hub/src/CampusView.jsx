// Volet « Campus » de la tuile Nebula (livraison #566) : fiches Matériels et
// Services/logiciels importées des tableurs du site, avec pour chaque
// matériel son état Nebula (client rapproché par MAC ou par nom) et le lien
// vers le synoptique / le tableau d'état. Logique pure : campusCards.js.
import { useEffect, useMemo, useState } from "react";
import { groupByLab, labs, assetSummary, ASSET_LABELS, SERVICE_LABELS, accessLinks } from "./campusCards.js";
import WindowsHostsView from "./WindowsHostsView.jsx";
import BroadcastView from "./BroadcastView.jsx";

const STATUS = { online: ["● en ligne", "var(--ok)"], offline: ["● hors ligne", "var(--danger)"] };

async function getJson(url, opts) {
  const r = await fetch(url, { credentials: "include", ...opts });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}

export default function CampusView({ nebulaApiBase, siAgentApiBase = "", agentSite = "", siteId, login = "", onShowInTopology, onShowHealth }) {
  const [tab, setTab] = useState("assets");
  const [data, setData] = useState({ assets: null, services: null });
  const [query, setQuery] = useState("");
  const [lab, setLab] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [open, setOpen] = useState(null);

  const load = async (coll) => {
    if (coll === "windows" || coll === "broadcast") { if (!data.assets) coll = "assets"; else return; }  // #567 : l'onglet Accès a besoin des fiches pour le rapprochement
    setError(null);
    try {
      const q = coll === "assets" && siteId ? `?site_id=${encodeURIComponent(siteId)}` : "";
      const d = await getJson(`${nebulaApiBase}/campus/${coll}${q}`);
      setData((x) => ({ ...x, [coll]: d }));
    } catch (e) { setError(e.message); }
  };
  useEffect(() => { load(tab); setLab(""); setOpen(null); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [tab, siteId, nebulaApiBase]);

  async function importFile(e) {
    const f = e.target.files?.[0]; e.target.value = "";
    if (!f) return;
    const fd = new FormData(); fd.append("file", f); fd.append("mode", "replace"); fd.append("user", login);
    setBusy(true); setError(null); setNotice(null);
    try {
      const r = await getJson(`${nebulaApiBase}/campus/${tab}/import`, { method: "PUT", body: fd });
      setNotice(`${r.count} fiche${r.count > 1 ? "s" : ""} importée${r.count > 1 ? "s" : ""} depuis ${f.name} (colonnes : ${(r.columns || []).join(", ")}).`);
      await load(tab);
    } catch (err) { setError(err.message); }
    setBusy(false);
  }

  const cur = data[tab];
  const items = cur?.items || [];
  const groups = useMemo(() => groupByLab(items, query, lab), [items, query, lab]);
  const labList = useMemo(() => labs(items), [items]);
  const summary = useMemo(() => (tab === "assets" ? assetSummary(items) : null), [items, tab]);
  const labels = tab === "assets" ? ASSET_LABELS : SERVICE_LABELS;
  const when = (ts) => (ts ? new Date(ts * 1000).toLocaleString("fr-FR") : "jamais");

  return (
    <div>
      <div className="tabs" style={{ marginBottom: 10 }}>
        <button className={tab === "assets" ? "active" : ""} onClick={() => setTab("assets")}>Matériels{data.assets ? ` (${data.assets.count})` : ""}</button>
        <button className={tab === "services" ? "active" : ""} onClick={() => setTab("services")}>Services / logiciels{data.services ? ` (${data.services.count})` : ""}</button>
        <button className={tab === "windows" ? "active" : ""} onClick={() => setTab("windows")}>Accès Windows</button>
        <button className={tab === "broadcast" ? "active" : ""} onClick={() => setTab("broadcast")}>Annonces réseau</button>
      </div>
      {tab === "windows" && <WindowsHostsView siAgentApiBase={siAgentApiBase} assets={data.assets?.items || []} site={agentSite} />}
      {tab === "broadcast" && <BroadcastView siAgentApiBase={siAgentApiBase} assets={data.assets?.items || []} site={agentSite} />}
      {tab !== "windows" && tab !== "broadcast" && <>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 8 }}>
        <input type="search" placeholder="filtrer (nom, type, modèle, MAC, lab…)" value={query} onChange={(e) => setQuery(e.target.value)} style={{ minWidth: 260 }} />
        <select value={lab} onChange={(e) => setLab(e.target.value)}><option value="">tous les labs</option>{labList.map((l) => <option key={l} value={l}>{l}</option>)}</select>
        {summary && <span className="muted">{summary.total} matériels · {summary.matched} vus par Nebula ({summary.online} en ligne) · {summary.byKind.slice(0, 5).map(([k, n]) => `${k} ${n}`).join(" · ")}</span>}
        <span style={{ flex: 1 }} />
        <span className="muted">dernier import : {when(cur?.imported_at)}</span>
        <label className="secondary" style={{ cursor: "pointer", padding: "4px 10px", border: "1px solid var(--border)", borderRadius: 6 }}>
          📤 Importer {tab === "assets" ? "l'inventaire" : "les expériences"} (xlsx / ods / csv)
          <input type="file" accept=".xlsx,.ods,.csv" onChange={importFile} disabled={busy} style={{ display: "none" }} />
        </label>
      </div>
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      {notice && <p style={{ color: "var(--ok)" }}>{notice}</p>}
      {cur && !items.length && <p className="muted">Aucune fiche : importer le tableur (première ligne = en-têtes{tab === "assets" ? " Nom, Type, Désignation, Modèle, Numero de série, Adresse MAC, Compte, Lab, Classe, Localisation…" : " Parcours, Lab, Nom de l’atelier, Matériel, Wifi, Lan, Internet, Site…"}). Le fichier reste sur le serveur du hub, jamais dans le code.</p>}
      {groups.map((g) => (
        <section key={g.lab} style={{ marginBottom: 12 }}>
          <h3 style={{ margin: "8px 0 6px", fontSize: 15 }}>{g.lab} <span className="muted">({g.items.length})</span></h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(260px, 1fr))", gap: 8, alignItems: "start" }}>
            {g.items.map((it) => {
              const st = it.nebula ? STATUS[it.nebula.status] || ["● " + it.nebula.status, "var(--muted)"] : null;
              const isOpen = open === it.id;
              return (
                <div key={it.id} className="hub-card" style={{ padding: 10, cursor: "pointer", borderLeft: st ? `4px solid ${st[1]}` : undefined }} onClick={() => setOpen(isOpen ? null : it.id)}>
                  <div style={{ display: "flex", justifyContent: "space-between", gap: 6 }}>
                    <strong>{it.name || it.course || "(sans nom)"}</strong>
                    {st && <span style={{ color: st[1], fontSize: 12, whiteSpace: "nowrap" }}>{st[0]}</span>}
                  </div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    {tab === "assets" ? [it.kind, it.designation, it.model].filter(Boolean).join(" · ") : [it.course !== it.name && it.course, it.hardware].filter(Boolean).join(" · ")}
                  </div>
                  {tab === "services" && <div className="muted" style={{ fontSize: 12 }}>{[it.wifi && "Wi-Fi", it.lan && "LAN", it.internet && "Internet", it.site].filter(Boolean).join(" · ") || "—"}</div>}
                  {it.nebula && <div className="muted" style={{ fontSize: 12 }}>IP {it.nebula.ip || "—"} · via {it.nebula.connected_to || it.nebula.parent_name || "?"} · VLAN {it.nebula.vlan ?? "—"}</div>}
                  {isOpen && (
                    <div style={{ marginTop: 8, fontSize: 13 }} onClick={(e) => e.stopPropagation()}>
                      <table style={{ borderCollapse: "collapse", textAlign: "left" }}><tbody>
                        {Object.entries(labels).filter(([k]) => it[k]).map(([k, l]) => <tr key={k}><td className="muted" style={{ paddingRight: 10, verticalAlign: "top" }}>{l}</td><td>{String(it[k])}</td></tr>)}
                        {Object.entries(it.fields || {}).map(([k, v]) => <tr key={k}><td className="muted" style={{ paddingRight: 10, verticalAlign: "top" }}>{k}</td><td>{v}</td></tr>)}
                      </tbody></table>
                      {tab === "assets" && (
                        <div style={{ display: "flex", gap: 6, marginTop: 8, flexWrap: "wrap" }}>
                          <button type="button" className="secondary" onClick={() => onShowInTopology?.({ macs: it.macs, name: it.name })} title="synoptique visuel : l'appareil et ce qui le relie">Voir dans le synoptique</button>
                          <button type="button" className="secondary" onClick={() => onShowHealth?.()} title="tableau d'état des équipements réseau">Tableau d'état</button>
                          {!it.nebula && <span className="muted" style={{ alignSelf: "center" }}>non vu par Nebula sur la période (MAC ou nom absents des clients)</span>}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </section>
      ))}
      </>}
    </div>
  );
}
