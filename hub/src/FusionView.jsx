import React, { useCallback, useEffect, useMemo, useState } from "react";
import { fetchIpList, fetchGeolocations, fetchLocationMatches, registerIps, fetchCommuneCentroid, upsertGeolocation, resolveByName } from "./fusionClient.js";
import {
  mergeIpSources, filterRows, enrichWithGeolocation, extractPostalCodeFromRow, nameResolveSubjects, severityTone, summarizeRows, classifyIp,
  visibleColumns, toggleColumnVisibility, FUSION_COLUMNS, SOURCE_LABELS,
} from "./fusionLib.js";

// Tuile « Fusion IP/MAC » (livraison #431, backlog 64 point 4, suite) --
// l'onglet de l'ancienne maquette promu dans le hub : corrélation par IP
// entre IPAM et Zenoss, calculée dans le navigateur, positions depuis
// pixel-grid (table par IP, correspondances par nom #426), trois
// compléments de géolocalisation (GeoIP des IP publiques, code postal du
// nom d'hôte, nom d'hôte). Fiche par ligne à droite.

const PREF_COLS = "hub.fusion.hiddenColumns";

export default function FusionView({ onBack, ipamApiBase, zenossApiBase, pixelGridApiBase, groups = [], onNavigate }) {
  const [ipam, setIpam] = useState({ entries: [], error: null, absent: !ipamApiBase });
  const [zenoss, setZenoss] = useState({ entries: [], error: null, absent: !zenossApiBase });
  const [geolocations, setGeolocations] = useState([]);
  const [matches, setMatches] = useState({});
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState({ query: "", hostnameQuery: "", alertQuery: "", correlatedOnly: false });
  const [hidden, setHidden] = useState(() => { try { return new Set(JSON.parse(localStorage.getItem(PREF_COLS) || "[]")); } catch { return new Set(); } });
  const [colsOpen, setColsOpen] = useState(false);
  const [selectedIp, setSelectedIp] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(null);

  useEffect(() => { try { localStorage.setItem(PREF_COLS, JSON.stringify([...hidden])); } catch { /* ignoré */ } }, [hidden]);

  const loadGeo = useCallback(async () => {
    if (!pixelGridApiBase) return;
    const [g, m] = await Promise.all([fetchGeolocations(pixelGridApiBase), fetchLocationMatches(pixelGridApiBase)]);
    setGeolocations(g); setMatches(m);
  }, [pixelGridApiBase]);

  const load = useCallback(async () => {
    setLoading(true);
    const [i, z] = await Promise.all([fetchIpList(ipamApiBase), fetchIpList(zenossApiBase)]);
    setIpam(i); setZenoss(z);
    await loadGeo();
    setLoading(false);
  }, [ipamApiBase, zenossApiBase, loadGeo]);
  useEffect(() => { load(); }, [load]);

  const merged = useMemo(() => enrichWithGeolocation(mergeIpSources(ipam.entries, zenoss.entries), geolocations, matches), [ipam, zenoss, geolocations, matches]);
  const rows = useMemo(() => filterRows(merged, filter), [merged, filter]);
  const stats = useMemo(() => summarizeRows(merged), [merged]);
  const cols = useMemo(() => visibleColumns(hidden), [hidden]);
  const selected = merged.find((r) => r.ip === selectedIp) || null;

  // --- compléments de géolocalisation (mêmes gestes que l'ancienne maquette, en lot) ---
  async function geoIp() {
    setBusy("geoip");
    const r = await registerIps(pixelGridApiBase, [...new Set(merged.map((x) => x.ip))], groups);
    setBusy(null);
    if (!r.ok) { setNotice({ error: r.error }); return; }
    await loadGeo();
    setNotice({ text: `GeoIP : ${r.publicResolved ?? 0} IP publique(s) résolue(s), ${(r.privatePending ?? 0) + (r.publicPending ?? 0)} en attente, ${r.alreadyKnown ?? 0} déjà connue(s)` });
  }
  async function geoPostal() {
    setBusy("postal");
    const candidates = merged.filter((r) => !r.position?.mapped && extractPostalCodeFromRow(r));
    let resolved = 0, notFound = 0;
    for (const row of candidates) {
      const { commune } = await fetchCommuneCentroid(pixelGridApiBase, extractPostalCodeFromRow(row));
      if (!commune || commune.latitude == null) { notFound += 1; continue; }
      if (await upsertGeolocation(pixelGridApiBase, row.ip, commune.latitude, commune.longitude, groups)) resolved += 1;
    }
    await loadGeo(); setBusy(null);
    setNotice({ text: candidates.length ? `Code postal : ${resolved} placée(s), ${notFound} sans commune` : "Code postal : aucune ligne sans position avec un code postal dans le nom d'hôte" });
  }
  async function geoName() {
    setBusy("name");
    const subjects = nameResolveSubjects(merged);
    const m = await resolveByName(pixelGridApiBase, subjects, true);
    setMatches((cur) => ({ ...cur, ...m })); setBusy(null);
    const applied = Object.values(m).filter((x) => ["auto", "validated", "manual"].includes(x.status) && x.latitude != null).length;
    const suggested = Object.values(m).filter((x) => x.status === "suggested").length;
    setNotice({ text: subjects.length ? `Nom d'hôte : ${applied} placée(s), ${suggested} à confirmer (Supervision SI → Localisations)` : "Nom d'hôte : aucune ligne sans position avec un nom d'hôte" });
  }

  function cell(row, key) {
    switch (key) {
      case "ip": return <code>{row.ip}</code>;
      case "mac": return row.mac ? <code>{row.mac}</code> : <span className="muted">—</span>;
      case "hostnames": return row.hostnames.join(", ") || <span className="muted">—</span>;
      case "sources": return row.sources.map((s) => <span key={s} className={`na-chip fu-src-${s}`}>{SOURCE_LABELS[s] || s}</span>);
      case "subnet": return row.ipam?.subnet || <span className="muted">—</span>;
      case "alerts": return row.zenoss ? <span className={`np-tone ${severityTone(row.zenoss.maxSeverity)}`}>{row.zenoss.activeCount} · {row.zenoss.severityLabel}</span> : <span className="muted">—</span>;
      case "position":
        if (row.position?.mapped) return <span title={row.position.source === "nom" ? `${row.position.localisation} d'après le nom d'hôte (${row.position.status}, score ${row.position.score})` : "table des géolocalisations (par IP)"}>📍 {row.position.latitude.toFixed(3)}, {row.position.longitude.toFixed(3)}{row.position.source === "nom" && <span className="muted fu-byname"> ≈ {row.position.localisation}</span>}</span>;
        if (row.position) return <span className="np-tone warn">en attente</span>;
        return <span className="muted">{classifyIp(row.ip) === "private" ? "IP privée" : classifyIp(row.ip) === "public" ? "IP publique" : "—"}</span>;
      default: return null;
    }
  }

  return (
    <div className="hub-settings hub-settings-wide ss-root">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🔗 Fusion IP/MAC</h1>
        <span className="muted" style={{ fontSize: 12 }}>
          {stats.total} IP · {stats.correlated} corrélée(s) · {stats.positioned} positionnée(s){stats.byName ? ` (${stats.byName} par le nom)` : ""} · {stats.privateUnpositioned} privée(s) sans position
        </span>
        <span style={{ flex: 1 }} />
        <span className={`np-tone ${ipam.error ? "bad" : ipam.absent ? "neutral" : "good"}`} style={{ fontSize: 12 }} title={ipam.error || ""}>IPAM {ipam.absent ? "non configuré" : ipam.error ? "⚠ injoignable" : `(${ipam.entries.length})`}</span>
        <span className={`np-tone ${zenoss.error ? "bad" : zenoss.absent ? "neutral" : "good"}`} style={{ fontSize: 12 }} title={zenoss.error || ""}>Zenoss {zenoss.absent ? "non configuré" : zenoss.error ? "⚠ injoignable" : `(${zenoss.entries.length})`}</span>
        <button className="secondary" onClick={load} disabled={loading}>⟳</button>
      </div>
      {notice?.error && <p className="hub-error" style={{ margin: "4px 0" }}>{notice.error}</p>}
      {notice?.text && <p className="muted" style={{ margin: "4px 0", fontSize: 12 }}>{notice.text}</p>}

      <div className="ss-body fu-body">
        <div className="ss-frame">
          <div className="ss-frame-head fu-toolbar">
            <input className="ss-search" placeholder="IP, MAC, hôte, description, subnet" value={filter.query} onChange={(e) => setFilter((f) => ({ ...f, query: e.target.value }))} />
            <input className="ss-search" placeholder="nom d'hôte" value={filter.hostnameQuery} onChange={(e) => setFilter((f) => ({ ...f, hostnameQuery: e.target.value }))} style={{ width: 140 }} />
            <input className="ss-search" placeholder="alerte (critical, 2…)" value={filter.alertQuery} onChange={(e) => setFilter((f) => ({ ...f, alertQuery: e.target.value }))} style={{ width: 140 }} />
            <label className="ups-form-check" style={{ fontSize: 12 }}><input type="checkbox" checked={filter.correlatedOnly} onChange={(e) => setFilter((f) => ({ ...f, correlatedOnly: e.target.checked }))} /> corrélées seulement</label>
            <span style={{ flex: 1 }} />
            {pixelGridApiBase && (
              <>
                <button className="secondary ss-chip" onClick={geoIp} disabled={!!busy || !merged.length} title="enregistre toutes les IP dans pixel-grid : publiques résolues par GeoIP, privées en attente">{busy === "geoip" ? "…" : "🌍 GeoIP"}</button>
                <button className="secondary ss-chip" onClick={geoPostal} disabled={!!busy || !merged.length} title="code postal à 5 chiffres dans le nom d'hôte → centroïde de la commune">{busy === "postal" ? "…" : "🏘 code postal"}</button>
                <button className="secondary ss-chip" onClick={geoName} disabled={!!busy || !merged.length} title="site reconnu dans le nom d'hôte (UPS-Arobase-5 → @5), correspondances conservées et corrigeables dans Supervision SI">{busy === "name" ? "…" : "🏷 nom d'hôte"}</button>
              </>
            )}
            <span style={{ position: "relative" }}>
              <button className="secondary ss-chip" onClick={() => setColsOpen((v) => !v)}>⚙ colonnes</button>
              {colsOpen && (
                <div className="fu-cols-menu">
                  {FUSION_COLUMNS.map((c) => <label key={c.key}><input type="checkbox" checked={!hidden.has(c.key)} onChange={() => setHidden((h) => toggleColumnVisibility(h, c.key))} /> {c.label}</label>)}
                </div>
              )}
            </span>
          </div>
          <div className="ss-frame-body">
            <table className="fu-table">
              <thead><tr>{cols.map((c) => <th key={c.key}>{c.label}</th>)}</tr></thead>
              <tbody>{rows.slice(0, 2000).map((row) => (
                <tr key={row.ip} className={selectedIp === row.ip ? "active" : ""} onClick={() => setSelectedIp(selectedIp === row.ip ? null : row.ip)}>
                  {cols.map((c) => <td key={c.key}>{cell(row, c.key)}</td>)}
                </tr>
              ))}</tbody>
            </table>
            {rows.length === 0 && <p className="muted" style={{ padding: 8 }}>{loading ? "Chargement…" : merged.length ? "Rien pour ces filtres." : "Aucune IP : vérifier IPAM et Zenoss (VITE_IPAM_API_BASE_URL, VITE_ZENOSS_API_BASE_URL)."}</p>}
            {rows.length > 2000 && <p className="muted" style={{ padding: 8 }}>{rows.length} lignes, 2000 affichées : affiner le filtre.</p>}
          </div>
        </div>

        <aside className="ss-frame fu-detail">
          {!selected ? <p className="muted" style={{ padding: 10 }}>Sélectionner une IP : détail IPAM et Zenoss, position, liens.</p> : (
            <div style={{ padding: 10, overflow: "auto", fontSize: 13 }}>
              <h3 style={{ margin: "0 0 6px" }}><code>{selected.ip}</code> {selected.mac && <span className="muted">· {selected.mac}</span>}</h3>
              <p style={{ margin: "0 0 6px" }}>{selected.hostnames.join(", ") || <span className="muted">sans nom d'hôte</span>}</p>
              <p style={{ margin: "0 0 6px" }}>{selected.sources.map((s) => <span key={s} className={`na-chip fu-src-${s}`}>{SOURCE_LABELS[s]}</span>)} {selected.sources.length > 1 ? <span className="np-tone good">corrélée</span> : <span className="muted">une seule source</span>}</p>
              <h4>Position</h4>
              <p style={{ margin: "0 0 6px" }}>{cell(selected, "position")}</p>
              {selected.position?.source === "nom" && <p className="muted" style={{ fontSize: 12 }}>Correspondance {selected.position.status} (score {selected.position.score}) : à valider, rejeter ou corriger dans Supervision SI → cadre « Localisations ».</p>}
              {onNavigate && <p><button className="secondary ss-origin" onClick={() => onNavigate("supervision-si")}>Supervision SI ↗</button> {pixelGridApiBase && <button className="secondary ss-origin" onClick={() => onNavigate("geo-catalog")}>Catalogue de positions ↗</button>}</p>}
              {selected.ipam && (<><h4>IPAM</h4><pre className="eb-json">{JSON.stringify(selected.ipam, null, 2)}</pre></>)}
              {selected.zenoss && (<><h4>Zenoss</h4><pre className="eb-json">{JSON.stringify(selected.zenoss, null, 2)}</pre></>)}
            </div>
          )}
        </aside>
      </div>
    </div>
  );
}
