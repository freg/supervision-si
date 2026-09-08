import React, { useCallback, useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Popup, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { fetchStatus, fetchPositions, fetchPosition, sync as syncCatalog, loadCommunes, validate, correct, reset, useRef as useRefApi, push } from "./geoCatalogClient.js";
import { STATUS_LABELS, SOURCE_LABELS, confidenceTone, filterPositions, sortPositions, summarize, orderedRefs, mapPoints, validCoords, fmtCoord } from "./geoCatalog.js";

// Tuile « Catalogue de positions » (livraison #429, backlog 67) : pour
// chaque lieu du SI, la ou les données de référence (fiches agrégées ou
// extraites des référentiels), l'interprétation géographique la plus
// précise, la position, l'estimation en % de justesse, Corriger / Valider,
// et les objets rattachés à chaque position. Base PostGIS dédiée
// (geo-catalog-api), déplaçable sur un hôte secondaire.

const SOURCE_HEX = { position: "#2f6fdb", human: "#2f9e5b", ban: "#d69a2b", commune: "#8e6cc2", osm: "#3aa39b", geolocations: "#888888", nominatim: "#3aa39b" };

function FitBounds({ points }) {
  const map = useMap();
  const key = points.map((p) => `${p.lat.toFixed(4)},${p.lon.toFixed(4)}`).join("|");
  const fit = () => {
    if (!points.length) return;
    if (points.length === 1) { map.setView([points[0].lat, points[0].lon], 14); return; }
    map.fitBounds(points.map((p) => [p.lat, p.lon]), { padding: [24, 24], maxZoom: 16 });
  };
  useEffect(() => { fit(); }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const el = map.getContainer();
    if (typeof ResizeObserver === "undefined" || !el) return undefined;
    const ro = new ResizeObserver(() => { map.invalidateSize(); fit(); });
    ro.observe(el);
    return () => ro.disconnect();
  }, [map]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

// Clic sur la carte = proposition de correction
function ClickPicker({ onPick }) {
  useMapEvents({ click: (e) => onPick(e.latlng.lat, e.latlng.lng) });
  return null;
}

function Bar({ percent }) {
  const tone = confidenceTone(percent);
  return (
    <span className="gc-bar" title={`${percent ?? "—"} % de justesse`}>
      <span className={`gc-bar-fill ${tone}`} style={{ width: `${Math.max(0, Math.min(100, percent || 0))}%` }} />
      <span className="gc-bar-label">{percent == null ? "—" : `${percent} %`}</span>
    </span>
  );
}

export default function GeoCatalogView({ onBack, geoCatalogApiBase, groups = [], onNavigate }) {
  const base = geoCatalogApiBase;
  const [status, setStatus] = useState(null);
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [busy, setBusy] = useState(false);
  const [view, setView] = useState("todo");
  const [q, setQ] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [form, setForm] = useState({ lat: "", lon: "", note: "" });

  const load = useCallback(async () => {
    if (!base) return;
    const [st, ps] = await Promise.all([fetchStatus(base), fetchPositions(base, { limit: 2000 })]);
    setStatus(st?.error ? null : st);
    setRows(ps.positions);
    setError(ps.error || (st?.error ? `état : ${st.error}` : null));
  }, [base]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!base || selectedId == null) { setDetail(null); return; }
    let cancelled = false;
    fetchPosition(base, selectedId).then((d) => { if (!cancelled) { setDetail(d?.error ? null : d); setForm({ lat: d?.lat ?? "", lon: d?.lon ?? "", note: "" }); } });
    return () => { cancelled = true; };
  }, [base, selectedId, rows]);

  const shown = useMemo(() => sortPositions(filterPositions(rows, { view, q })), [rows, view, q]);
  const stats = useMemo(() => summarize(rows), [rows]);

  const act = async (label, fn) => {
    setBusy(true); setNotice(null);
    const r = await fn();
    setBusy(false);
    if (r?.error) { setError(`${label} : ${r.error}`); return null; }
    setError(null); setNotice(`${label} : fait`); await load();
    return r;
  };
  const doSync = () => act("Synchronisation", async () => {
    const r = await syncCatalog(base, groups);
    if (!r?.error) setNotice(`Synchronisation : ${r.positions} position(s), ${r.refs} référence(s), ${r.links} objet(s) rattaché(s)${r.errors?.length ? `, ${r.errors.length} erreur(s)` : ""}`);
    return r;
  });
  const doCommunes = () => act("Chargement des communes", () => loadCommunes(base, groups));
  const doValidate = (p) => act(`Validation de ${p.label}`, () => validate(base, p.id, groups));
  const doReset = (p) => act(`Retour à l'automatique pour ${p.label}`, () => reset(base, p.id, groups));
  const doUseRef = (p, r) => act(`Reprise de la référence ${SOURCE_LABELS[r.source] || r.source}`, () => useRefApi(base, p.id, r.id, groups));
  const doPush = (p) => act(`Recopie de ${p.label} dans les géolocalisations`, () => push(base, p.id, groups));
  const doCorrect = (p) => {
    if (!validCoords(form.lat, form.lon)) { setError("Coordonnées invalides (latitude -90..90, longitude -180..180)."); return; }
    act(`Correction de ${p.label}`, () => correct(base, p.id, { lat: Number(form.lat), lon: Number(form.lon), note: form.note || null }, groups));
  };

  const pts = detail ? mapPoints(detail) : [];

  return (
    <div className="hub-settings hub-settings-wide ss-root">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>📍 Catalogue de positions</h1>
        <span className="muted" style={{ fontSize: 12 }}>
          {stats.total} position(s) · <strong>{stats.todo}</strong> à traiter · {stats.decided} décidée(s) · {stats.unpositioned} sans position · {stats.links} objet(s) rattaché(s)
        </span>
        <span style={{ flex: 1 }} />
        {status && (
          <span className="muted" style={{ fontSize: 12 }} title={`base ${status.db_host} · géocodeur ${status.geocoder}`}>
            communes : {status.communes?.count ? `${status.communes.count} chargées` : <Tone tone="warn">non chargées</Tone>} · OSM local : {status.osm_tables?.length ? "présent" : "absent"}{status.nominatim ? " (Nominatim configuré)" : ""} · cache géocodage : {status.geocode_cache}
            {status.last_sync && <> · dernière synchro {new Date(status.last_sync.finished_at || status.last_sync.started_at).toLocaleString("fr-FR")}</>}
          </span>
        )}
        <button className="secondary" onClick={doCommunes} disabled={busy || !base} title="charge le référentiel des communes (geo.api.gouv.fr, ~35 000 lignes) dans la base du catalogue">Charger les communes</button>
        <button onClick={doSync} disabled={busy || !base} title="relit les localisations et correspondances de pixel-grid, interroge les référentiels, recalcule interprétation et justesse (décisions conservées)">{busy ? "…" : "⟳ Synchroniser"}</button>
      </div>
      {!base && <p className="hub-error">VITE_GEO_CATALOG_API_BASE_URL non configurée.</p>}
      {error && <p className="hub-error" style={{ margin: "4px 0" }}>{error}</p>}
      {notice && <p className="muted" style={{ margin: "4px 0", fontSize: 12 }}>{notice}</p>}

      <div className="ss-body gc-body">
        <div className="ss-frame">
          <div className="ss-frame-head">
            <input className="ss-search" style={{ flex: 1 }} placeholder="filtrer : lieu, référence, objet rattaché" value={q} onChange={(e) => setQ(e.target.value)} />
            {[["todo", `à traiter (${stats.todo})`], ["auto", "automatiques"], ["decided", "validées / corrigées"], ["unpositioned", "sans position"], ["all", "toutes"]].map(([k, l]) => (
              <button key={k} className={`secondary ss-chip${view === k ? " active" : ""}`} onClick={() => setView(k)}>{l}</button>
            ))}
          </div>
          <div className="ss-frame-body">
            <table className="gc-table">
              <thead><tr><th>Donnée(s) de référence</th><th>Interprétation la plus précise</th><th>Position</th><th>Justesse</th><th></th></tr></thead>
              <tbody>{shown.map((p) => {
                const refs = orderedRefs(p.refs);
                const best = p.interpretation?.best;
                return (
                  <tr key={p.id} className={selectedId === p.id ? "active" : ""} onClick={() => setSelectedId(selectedId === p.id ? null : p.id)}>
                    <td>
                      <strong>{p.label}</strong>
                      <div className="gc-refs">
                        {refs.length === 0 && <span className="muted">aucune référence</span>}
                        {refs.slice(0, 4).map((r, i) => <span key={i} className="na-chip" style={{ borderColor: SOURCE_HEX[r.source] }} title={`${r.label} — ${r.precision}${r.score != null ? ` — score ${r.score}` : ""}`}>{SOURCE_LABELS[r.source] || r.source}{r.score != null ? ` ${Math.round(r.score * 100) / 100}` : ""}</span>)}
                        {refs.length > 4 && <span className="muted">+{refs.length - 4}</span>}
                        {(p.links || []).length > 0 && <span className="muted" style={{ fontSize: 11 }}>· {p.links.length} objet(s)</span>}
                      </div>
                    </td>
                    <td>{best ? <><span className="gc-prec">{p.precision_label || p.precision}</span><br /><span className="muted" style={{ fontSize: 12 }}>{best.label}</span></> : <span className="muted">—</span>}</td>
                    <td className="gc-coords">{p.lat != null ? <><code>{fmtCoord(p.lat)}</code><br /><code>{fmtCoord(p.lon)}</code></> : <span className="muted">—</span>}</td>
                    <td><Bar percent={p.lat != null ? p.confidence : null} /><br /><span className={`np-tone ${p.status === "auto" ? "neutral" : "good"}`} style={{ fontSize: 11 }}>{STATUS_LABELS[p.status] || p.status}</span></td>
                    <td onClick={(e) => e.stopPropagation()} className="gc-actions">
                      {p.status === "auto" && p.lat != null && <button className="secondary ss-origin" onClick={() => doValidate(p)} disabled={busy} title="confirmer cette position">✓ Valider</button>}
                      <button className="secondary ss-origin" onClick={() => { setSelectedId(p.id); }} title="ouvrir la fiche pour corriger (clic sur la carte, référence, saisie)">✎ Corriger</button>
                      {p.status !== "auto" && <button className="secondary ss-origin" onClick={() => doReset(p)} disabled={busy} title="oublier la décision">↺</button>}
                    </td>
                  </tr>
                );
              })}</tbody>
            </table>
            {shown.length === 0 && <p className="muted" style={{ padding: 8 }}>{rows.length ? "Rien pour ce filtre." : "Catalogue vide : lancer « Synchroniser » (lit les géolocalisations de pixel-grid)."}</p>}
          </div>
        </div>

        <aside className="ss-frame gc-detail">
          {!detail ? <p className="muted" style={{ padding: 10 }}>Sélectionner une position : carte, références, objets rattachés, correction.</p> : (
            <>
              <div className="ss-frame-head">
                <strong>{detail.label}</strong>
                <span className={`np-tone ${detail.status === "auto" ? "neutral" : "good"}`} style={{ fontSize: 11 }}>{STATUS_LABELS[detail.status]}</span>
                <span style={{ flex: 1 }} />
                <Bar percent={detail.lat != null ? detail.confidence : null} />
              </div>
              <div className="ss-frame-body gc-detail-body">
                <div className="gc-map">
                  <MapContainer center={[46.6, 2.4]} zoom={6} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
                    <TileLayer attribution="&copy; OpenStreetMap" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
                    <FitBounds points={pts} />
                    <ClickPicker onPick={(lat, lon) => setForm((f) => ({ ...f, lat: lat.toFixed(6), lon: lon.toFixed(6) }))} />
                    {pts.map((p, i) => (
                      <CircleMarker key={i} center={[p.lat, p.lon]} radius={p.kind === "position" ? 9 : 6} pathOptions={{ color: p.kind === "position" ? "#fff" : SOURCE_HEX[p.kind] || "#999", fillColor: SOURCE_HEX[p.kind] || "#999", fillOpacity: 0.9, weight: 2 }}>
                        <Popup>{p.kind === "position" ? <strong>position retenue</strong> : <>{SOURCE_LABELS[p.kind] || p.kind} — {p.label}</>}</Popup>
                      </CircleMarker>
                    ))}
                    {validCoords(form.lat, form.lon) && (Number(form.lat) !== detail.lat || Number(form.lon) !== detail.lon) && (
                      <CircleMarker center={[Number(form.lat), Number(form.lon)]} radius={8} pathOptions={{ color: "#d64545", fillColor: "#d64545", fillOpacity: 0.5, dashArray: "3 3" }}><Popup>correction proposée</Popup></CircleMarker>
                    )}
                  </MapContainer>
                </div>
                <div className="gc-detail-text">
                  <p style={{ margin: "6px 0" }}><span className="muted">Interprétation :</span> {detail.precision_label || detail.precision} {detail.interpretation?.best?.label && <>— {detail.interpretation.best.label}</>}</p>
                  {detail.interpretation?.reasons?.length > 0 && <ul className="gc-reasons">{detail.interpretation.reasons.map((r, i) => <li key={i}>{r}</li>)}</ul>}
                  {detail.note && <p className="muted" style={{ fontSize: 12 }}>note : {detail.note}</p>}

                  <h4>Références ({detail.refs?.length || 0})</h4>
                  <table className="gc-reftable">
                    <tbody>{orderedRefs(detail.refs).map((r) => (
                      <tr key={r.id}>
                        <td><span className="na-chip" style={{ borderColor: SOURCE_HEX[r.source] }}>{SOURCE_LABELS[r.source] || r.source}</span></td>
                        <td>{r.label}<br /><span className="muted" style={{ fontSize: 11 }}>{r.precision}{r.score != null ? ` · score ${r.score}` : ""}{r.lat != null ? ` · ${fmtCoord(r.lat)}, ${fmtCoord(r.lon)}` : ""}</span></td>
                        <td>{r.lat != null && r.source !== "human" && <button className="secondary ss-origin" onClick={() => doUseRef(detail, r)} disabled={busy} title="retenir cette référence comme position (correction)">utiliser</button>}</td>
                      </tr>
                    ))}</tbody>
                  </table>
                  {detail.refs?.length === 0 && <p className="muted" style={{ fontSize: 12 }}>Aucun référentiel ne connaît ce libellé : corriger à la main (clic sur la carte ou saisie).</p>}

                  <h4>Corriger</h4>
                  <div className="gc-form">
                    <input placeholder="latitude" value={form.lat} onChange={(e) => setForm((f) => ({ ...f, lat: e.target.value }))} />
                    <input placeholder="longitude" value={form.lon} onChange={(e) => setForm((f) => ({ ...f, lon: e.target.value }))} />
                    <input placeholder="note (facultative)" value={form.note} onChange={(e) => setForm((f) => ({ ...f, note: e.target.value }))} style={{ flex: 1 }} />
                    <button onClick={() => doCorrect(detail)} disabled={busy || !validCoords(form.lat, form.lon)}>Corriger</button>
                    {detail.status === "auto" && detail.lat != null && <button className="secondary" onClick={() => doValidate(detail)} disabled={busy}>✓ Valider</button>}
                    {detail.status !== "auto" && <button className="secondary" onClick={() => doReset(detail)} disabled={busy}>↺ auto</button>}
                    {detail.lat != null && detail.kind === "geolocation" && <button className="secondary" onClick={() => doPush(detail)} disabled={busy} title="recopie la position retenue dans la table des géolocalisations de pixel-grid (utilisée par Supervision SI, la carte, le pont)">→ géolocalisations</button>}
                  </div>
                  <p className="muted" style={{ fontSize: 11 }}>Un clic sur la carte remplit latitude/longitude.</p>

                  <h4>Objets positionnés ici ({detail.links?.length || 0})</h4>
                  {detail.links?.length ? (
                    <ul className="gc-links">{detail.links.map((l) => (
                      <li key={l.id}><span className="na-chip">{l.object_type === "supervised" ? "supervisé" : l.object_type}</span> {l.label}{l.data?.relation ? <span className="muted"> ({l.data.relation})</span> : null}{l.data?.status ? <span className="muted"> · correspondance {l.data.status}</span> : null}
                        {l.object_type === "supervised" && onNavigate && <button className="secondary ss-origin" onClick={() => onNavigate("supervision-si")} title="ouvrir Supervision SI">↗</button>}</li>
                    ))}</ul>
                  ) : <p className="muted" style={{ fontSize: 12 }}>Aucun objet rattaché (les correspondances nom → lieu de Supervision SI et la hiérarchie des géolocalisations y apparaissent après synchronisation).</p>}
                  {detail.nearby?.length > 0 && <p className="muted" style={{ fontSize: 12 }}>À moins de 500 m : {detail.nearby.map((n) => `${n.label} (${Math.round(n.distance_m)} m)`).join(", ")}</p>}
                </div>
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

function Tone({ tone, children }) {
  return <span className={`np-tone ${tone}`}>{children}</span>;
}
