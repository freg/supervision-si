import React, { useCallback, useEffect, useMemo, useState } from "react";
import { MapContainer, TileLayer, CircleMarker, Polyline, Popup, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { fetchTargets, fetchLatestSamples, fetchAgents as fetchWifiAgents } from "./netprobeClient.js";
import { fetchUpsList } from "./upsClient.js";
import { fetchFleet, fetchNetviews } from "./siAgentClient.js";
import { fetchSnmpTargets } from "./snmpClient.js";
import { fetchTunnels, fetchConnections } from "./sshTunnelsClient.js";
import { fetchSites, fetchDevices, fetchLinks } from "./networkAgentClient.js";
import { fetchSuggestions } from "./netmapOrchestratorClient.js";
import { fetchSignals } from "./vigilanceClient.js";
import {
  ITEM_TYPES, STATE_ORDER, aggregateSupervised, buildProposals, filterSupervised, prioritizeSupervised, movePriority, setPriority,
  buildLinks, knownPositions, deducePositions, describeChain, FRAME_KINDS, frameLayout, normalizeFrames, summarizeByState,
  PREF_KEYS, loadPref, savePref, spreadCoincident,
  MATCH_STATUS, appliedMatch, displaySite, resolveSubjects as subjectsOf, resolveKey, geoRows, geoSummary,
} from "./supervisedItems.js";
import { resolveSubjects, decideMatch, resetMatch, fetchAliases, addAlias, deleteAlias } from "./geoMatchesClient.js";
import {
  HISTORY_WINDOWS, windowById, stateSegments, bucketize, calendarDays, dayTone, buildHierarchy, radialLayout,
  effectiveSelection, toggleSelection,
} from "./supervisedHistory.js";
import { fetchItemHistory } from "./supervisedHistoryClient.js";
import ZoomableChart from "./components/ZoomableChart.jsx";

// Nouvelle tuile « Supervision SI » (livraison #423, backlog 64) -- « la
// tuile actuelle était la maquette initiale de la dataviz du hub ; elle doit
// changer radicalement ». Vit DANS le hub. Colonne de gauche à onglets
// Propositions / Supervisés (défaut) / Liens ; page centrale en 1 à 4 cadres
// (défaut carte + table). Agrégation client des tuiles (netprobe, UPS,
// agents, SNMP, tunnels, sondes WiFi), propositions (orchestrateur,
// vigilance, appareils découverts), liens automatiques et positions
// déduites. #424 (point 4) : les outils de l'ancienne maquette reviennent
// comme contenus de cadre -- timeline des états, mosaïque pixel-grid,
// calendrier de densité, arbre radial -- nourris par les historiques des
// tuiles pour une « corbeille » de sélection (cases à cocher). Toute la
// logique non-React est dans supervisedItems.js / supervisedHistory.js.

const REFRESH_MS = 60000;
const STATE_COLORS = { critical: "var(--danger)", warning: "var(--warning)", ok: "var(--ok)", unknown: "var(--muted)" };
const STATE_LABELS = { critical: "critique", warning: "avertissement", ok: "ok", unknown: "inconnu" };
const STATE_HEX = { critical: "#d64545", warning: "#d69a2b", ok: "#2f9e5b", unknown: "#8a8f98" };

// #426 : ligne « localisation d'après le nom » d'une fiche + actions
function MatchActions({ item, match, places, onDecide, onReset }) {
  const [choice, setChoice] = useState("");
  const st = match?.status;
  return (
    <span className="ss-match-actions">
      {(st === "auto" || st === "suggested") && match.localisation && <button className="secondary ss-origin" onClick={() => onDecide(item, "validated")} title="confirmer cette localisation">✓ valider</button>}
      {(st === "auto" || st === "suggested" || st === "manual" || st === "validated") && <button className="secondary ss-origin" onClick={() => onDecide(item, "rejected")} title="ne jamais placer cet équipement d'après son nom">✕ rejeter</button>}
      {(st === "validated" || st === "manual" || st === "rejected") && <button className="secondary ss-origin" onClick={() => onReset(item)} title="oublier la décision, revenir à l'automatique">↺ auto</button>}
      <select value={choice} onChange={(e) => { setChoice(""); if (e.target.value) onDecide(item, "manual", e.target.value); }} title="choisir une autre localisation">
        <option value="">choisir…</option>{places.map((l) => <option key={l} value={l}>{l}</option>)}
      </select>
    </span>
  );
}

function MatchLine({ item, match, places, onDecide, onReset }) {
  const st = match?.status;
  return (
    <p className="ss-match-line" style={{ margin: "0 0 8px", fontSize: 12 }}>
      {st && match.localisation ? (
        <>localisation d'après {(match.method || "").endsWith("/site") ? "le site déclaré" : "le nom"} : <strong>{match.localisation}</strong> <span className="muted">({MATCH_STATUS[st]?.label}{match.score != null && st !== "manual" ? `, ${match.method} ${match.score}` : ""}{match.mapped === false ? ", sans coordonnées" : ""})</span>
          {match.candidates?.length > 1 && <span className="muted"> · autres : {match.candidates.slice(1, 3).map((c) => `${c.localisation} (${c.score})`).join(", ")}</span>}</>
      ) : <span className="muted">aucune localisation reconnue dans le nom{item.site ? " ni le site déclaré" : ""}{match?.candidates?.length ? ` (proche : ${match.candidates.slice(0, 2).map((c) => `${c.localisation} ${c.score}`).join(", ")})` : ""}</span>}
      {" "}<MatchActions item={item} match={match} places={places} onDecide={onDecide} onReset={onReset} />
    </p>
  );
}

function Tone({ state, children }) {
  return <span className={`np-tone ${state === "critical" ? "bad" : state === "warning" ? "warn" : state === "ok" ? "good" : "neutral"}`}>{children}</span>;
}

function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR");
}

function storage() {
  try { return typeof window !== "undefined" ? window.localStorage : null; } catch { return null; }
}

// Recadre la carte sur les points quand ils changent, et recalcule la
// taille de la carte quand son cadre change (1 à 4 cadres : Leaflet ne
// voit pas seul un redimensionnement CSS -- marqueurs hors champ sinon).
function FitBounds({ points }) {
  const map = useMap();
  const key = points.map((p) => `${p.lat.toFixed(3)},${p.lon.toFixed(3)}`).join("|");
  const fit = () => {
    if (!points.length) return;
    if (points.length === 1) { map.setView([points[0].lat, points[0].lon], 12); return; }
    map.fitBounds(points.map((p) => [p.lat, p.lon]), { padding: [24, 24], maxZoom: 15 });
  };
  useEffect(() => { fit(); }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    const el = map.getContainer();
    if (typeof ResizeObserver === "undefined" || !el) return undefined;
    const ro = new ResizeObserver(() => { map.invalidateSize(); fit(); });
    ro.observe(el);
    return () => ro.disconnect();
  }, [map, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

export default function SupervisionSiView({
  onBack, onNavigate, legacyFrontendUrl,
  netprobeApiBase, upsApiBase, siAgentApiBase, snmpApiBase, sshTunnelsApiBase, networkAgentApiBase,
  netmapOrchestratorApiBase, vigilanceApiBase, pixelGridApiBase, groups = [],
}) {
  const [sources, setSources] = useState(null);
  const [loading, setLoading] = useState(true);
  const [errors, setErrors] = useState([]);
  const [now, setNow] = useState(Date.now());
  const [tab, setTab] = useState(() => loadPref(storage(), PREF_KEYS.tab, "supervised"));
  const [frames, setFrames] = useState(() => normalizeFrames(loadPref(storage(), PREF_KEYS.frames, null)));
  const [priorities, setPriorities] = useState(() => loadPref(storage(), PREF_KEYS.priorities, {}));
  const [checkedProposals, setCheckedProposals] = useState(() => loadPref(storage(), PREF_KEYS.proposals, {}));
  const [filter, setFilter] = useState({ text: "", types: [], states: [], site: "" });
  const [selected, setSelected] = useState(null);
  // #424 : corbeille de sélection + historiques
  const [selection, setSelection] = useState(() => loadPref(storage(), PREF_KEYS.selection, []));
  const [windowId, setWindowId] = useState(() => loadPref(storage(), PREF_KEYS.window, "24h"));
  const [history, setHistory] = useState({}); // identity -> points
  const [historyLoading, setHistoryLoading] = useState(false);
  // #426 : correspondances nom/site -> localisation (pixel-grid), alias
  const [matches, setMatches] = useState({});
  const [matchesError, setMatchesError] = useState(null);
  const [aliases, setAliases] = useState([]);
  const [geoFilter, setGeoFilter] = useState("todo");
  const [aliasForm, setAliasForm] = useState({ alias: "", localisation: "" });

  useEffect(() => savePref(storage(), PREF_KEYS.tab, tab), [tab]);
  useEffect(() => savePref(storage(), PREF_KEYS.frames, frames), [frames]);
  useEffect(() => savePref(storage(), PREF_KEYS.priorities, priorities), [priorities]);
  useEffect(() => savePref(storage(), PREF_KEYS.proposals, checkedProposals), [checkedProposals]);
  useEffect(() => savePref(storage(), PREF_KEYS.selection, selection), [selection]);
  useEffect(() => savePref(storage(), PREF_KEYS.window, windowId), [windowId]);

  const load = useCallback(async () => {
    const errs = [];
    const safe = async (label, fn, fallback) => {
      try { const r = await fn(); if (r && r.error) { errs.push(`${label} : ${r.error}`); return fallback; } return r; } catch (e) { errs.push(`${label} : ${e.message}`); return fallback; }
    };
    const [netprobeTargets, netprobeLatest, wifiAgents, upsDevices, siAgentFleet, snmpTargets, sshTunnels, sshConnections, sites, suggestions, signals, geolocations, netviews] = await Promise.all([
      netprobeApiBase ? safe("Sondes réseau", () => fetchTargets(netprobeApiBase), []) : [],
      netprobeApiBase ? safe("Sondes réseau (relevés)", () => fetchLatestSamples(netprobeApiBase), []) : [],
      netprobeApiBase ? safe("Sondes WiFi", async () => (await fetchWifiAgents(netprobeApiBase)).filter((a) => a.role === "probe"), []) : [],
      upsApiBase ? safe("Onduleurs", () => fetchUpsList(upsApiBase), []) : [],
      siAgentApiBase ? safe("Agents hôtes", () => fetchFleet(siAgentApiBase), []) : [],
      snmpApiBase ? safe("SNMP", () => fetchSnmpTargets(snmpApiBase), []) : [],
      sshTunnelsApiBase ? safe("Tunnels SSH", () => fetchTunnels(sshTunnelsApiBase), []) : [],
      sshTunnelsApiBase ? safe("Connexions SSH", () => fetchConnections(sshTunnelsApiBase), []) : [],
      networkAgentApiBase ? safe("Exploration réseau (sites)", () => fetchSites(networkAgentApiBase), []) : [],
      netmapOrchestratorApiBase ? safe("Orchestrateur", () => fetchSuggestions(netmapOrchestratorApiBase, { status: "open" }), []) : [],
      vigilanceApiBase ? safe("Vigilance", () => fetchSignals(vigilanceApiBase), []) : [],
      pixelGridApiBase ? safe("Géolocalisations", async () => { const r = await fetch(`${pixelGridApiBase}/geolocations`); const d = await r.json(); return Array.isArray(d?.geolocations) ? d.geolocations : []; }, []) : [],
      siAgentApiBase ? safe("Agents hôtes (vue réseau)", () => fetchNetviews(siAgentApiBase), []) : [],
    ]);
    // appareils et flux de chaque segment (exploration réseau)
    const naDevices = [], naLinks = [];
    if (networkAgentApiBase) {
      const segs = (sites || []).flatMap((s) => (s.segments || []).map((seg) => ({ ...seg, siteName: s.name })));
      const res = await Promise.all(segs.map(async (seg) => [
        await safe(`Appareils ${seg.label}`, () => fetchDevices(networkAgentApiBase, seg.id), []),
        await safe(`Flux ${seg.label}`, () => fetchLinks(networkAgentApiBase, seg.id), []),
        seg,
      ]));
      for (const [devs, lks, seg] of res) {
        for (const d of devs) naDevices.push({ ...d, siteName: seg.siteName });
        naLinks.push(...lks);
      }
    }
    setSources({ netprobeTargets, netprobeLatest, wifiAgents, upsDevices, siAgentFleet, snmpTargets, sshTunnels, sshConnections, sites, suggestions, signals, geolocations, naDevices, naLinks, netviews });
    setErrors(errs);
    setLoading(false);
    setNow(Date.now());
  }, [netprobeApiBase, upsApiBase, siAgentApiBase, snmpApiBase, sshTunnelsApiBase, networkAgentApiBase, netmapOrchestratorApiBase, vigilanceApiBase, pixelGridApiBase]);

  useEffect(() => { load(); const id = setInterval(load, REFRESH_MS); return () => clearInterval(id); }, [load]);

  // --- Dérivés (logique pure) ---
  const supervised = useMemo(() => (sources ? aggregateSupervised(sources, now) : []), [sources, now]);
  const sitesList = useMemo(() => [...new Set(supervised.map((i) => i.site).filter(Boolean))].sort(), [supervised]);
  const visible = useMemo(() => prioritizeSupervised(filterSupervised(supervised, filter), priorities), [supervised, filter, priorities]);
  const proposals = useMemo(() => (sources ? buildProposals({ suggestions: sources.suggestions, signals: sources.signals, devices: sources.naDevices, supervised, netviews: sources.netviews }) : []), [sources, supervised]);
  const links = useMemo(() => (sources ? buildLinks({ naLinks: sources.naLinks, naDevices: sources.naDevices, tunnels: sources.sshTunnels, connections: sources.sshConnections, supervised, netviews: sources.netviews }) : []), [sources, supervised]);
  // #426 : résolution par nom, relancée quand la liste (identités, noms,
  // sites) change -- pas à chaque rafraîchissement d'état.
  const subjectsKey = useMemo(() => resolveKey(supervised, sources?.sites), [supervised, sources]);
  const refreshMatches = useCallback(async () => {
    if (!pixelGridApiBase || !supervised.length) return;
    const [{ matches: m, error }, { aliases: al }] = await Promise.all([resolveSubjects(pixelGridApiBase, subjectsOf(supervised, sources?.sites)), fetchAliases(pixelGridApiBase)]);
    setMatches(m); setMatchesError(error); setAliases(al);
  }, [pixelGridApiBase, subjectsKey]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { refreshMatches(); }, [refreshMatches]);
  const positions = useMemo(() => {
    if (!sources) return new Map();
    const known = knownPositions({ naDevices: sources.naDevices, geolocations: sources.geolocations, sites: sources.sites, supervised, matches });
    return deducePositions(supervised.map((i) => i.identity), links, known);
  }, [sources, supervised, links, matches]);
  const geoList = useMemo(() => geoRows(supervised, matches), [supervised, matches]);
  const geoStats = useMemo(() => geoSummary(geoList, sources?.geolocations || []), [geoList, sources]);
  const placeNames = useMemo(() => (sources?.geolocations || []).map((g) => g.localisation).filter((l) => l !== "__default__").sort(), [sources]);
  const summary = useMemo(() => summarizeByState(supervised), [supervised]);
  const selectedItem = supervised.find((i) => i.identity === selected) || null;

  // --- #424 : corbeille et historiques des équipements retenus ---
  const win = windowById(windowId);
  const needsHistory = frames.some((f) => ["timeline", "grid", "calendar"].includes(f.kind));
  const basket = useMemo(() => effectiveSelection(selection, visible, priorities, 12), [selection, visible, priorities]);
  const basketItems = basket.map((id) => supervised.find((i) => i.identity === id)).filter(Boolean);
  const basketKey = basket.join("|") + "@" + windowId;
  useEffect(() => {
    if (!needsHistory || !basketItems.length) return undefined;
    let cancelled = false;
    setHistoryLoading(true);
    const startIso = new Date(Date.now() - win.seconds * 1000).toISOString();
    (async () => {
      const entries = await Promise.all(basketItems.map(async (it) => [it.identity, await fetchItemHistory(it, { netprobe: netprobeApiBase, ups: upsApiBase, siAgent: siAgentApiBase }, { startIso, limit: win.id === "30d" ? 2000 : 800 })]));
      if (cancelled) return;
      setHistory((h) => ({ ...h, ...Object.fromEntries(entries) }));
      setHistoryLoading(false);
    })();
    return () => { cancelled = true; };
  }, [basketKey, needsHistory, now]); // eslint-disable-line react-hooks/exhaustive-deps

  // --- Actions ---
  const toggleType = (t) => setFilter((f) => ({ ...f, types: f.types.includes(t) ? f.types.filter((x) => x !== t) : [...f.types, t] }));
  const toggleState = (s) => setFilter((f) => ({ ...f, states: f.states.includes(s) ? f.states.filter((x) => x !== s) : [...f.states, s] }));
  const bump = (it, delta) => setPriorities((p) => movePriority(p, visible.map((i) => i.identity), it.identity, delta));
  const pin = (it) => setPriorities((p) => (p[it.identity] != null ? setPriority(p, it.identity, null) : movePriority(p, visible.map((i) => i.identity), it.identity, 0)));
  const setFrameKind = (i, kind) => setFrames((fr) => fr.map((f, j) => (j === i ? { kind } : f)));
  const removeFrame = (i) => setFrames((fr) => (fr.length > 1 ? fr.filter((_, j) => j !== i) : fr));
  const addFrame = () => setFrames((fr) => (fr.length < 4 ? [...fr, { kind: fr.some((f) => f.kind === "links") ? "summary" : "links" }] : fr));
  const toggleProposal = (p) => setCheckedProposals((c) => ({ ...c, [p.key]: !c[p.key] }));
  const toggleBasket = (it) => setSelection((sel) => toggleSelection(sel, it.identity));
  const decide = async (it, status, localisation) => {
    const r = await decideMatch(pixelGridApiBase, it.identity, { status, localisation, name: it.name, site: it.site, groups });
    if (r?.error) setMatchesError(r.error); else { setMatchesError(null); await refreshMatches(); }
  };
  const undecide = async (it) => { const r = await resetMatch(pixelGridApiBase, it.identity, groups); if (r?.error) setMatchesError(r.error); else await refreshMatches(); };
  const submitAlias = async (e) => {
    e.preventDefault();
    if (!aliasForm.alias || !aliasForm.localisation) return;
    const r = await addAlias(pixelGridApiBase, aliasForm.alias, aliasForm.localisation, groups);
    if (r?.error) setMatchesError(r.error); else { setAliasForm({ alias: "", localisation: "" }); await refreshMatches(); }
  };
  const goto = (origin) => { if (onNavigate) onNavigate(origin === "netprobe" ? "netprobe" : origin === "ups" ? "ups" : origin === "si-agent" ? "si-agent" : origin === "snmp" ? "snmp" : origin === "ssh-tunnels" ? "ssh-tunnels" : origin); };

  // --- Cadres ---
  const layout = frameLayout(frames.length);
  const mapPoints = spreadCoincident(visible.map((it) => ({ it, p: positions.get(it.identity) })).filter((x) => x.p).map((x) => ({ ...x, lat: x.p.lat, lon: x.p.lon })));
  const positionedIds = new Set(mapPoints.map((x) => x.it.identity));
  const mapLinks = links.filter((l) => l.kind !== "site" && positionedIds.has(l.a) && positionedIds.has(l.b)).slice(0, 400);

  function renderFrame(f, i) {
    let body;
    if (f.kind === "map") {
      body = (
        <div className="ss-map">
          <MapContainer center={[46.6, 2.4]} zoom={6} style={{ height: "100%", width: "100%" }} scrollWheelZoom>
            <TileLayer attribution="&copy; OpenStreetMap" url="https://tile.openstreetmap.org/{z}/{x}/{y}.png" />
            <FitBounds points={mapPoints.map((x) => x.p)} />
            {mapLinks.map((l, k) => {
              const a = positions.get(l.a), b = positions.get(l.b);
              return <Polyline key={k} positions={[[a.lat, a.lon], [b.lat, b.lon]]} pathOptions={{ color: l.kind === "tunnel" ? "#7b61ff" : "#6c8ebf", weight: 1.5, opacity: 0.6 }} />;
            })}
            {mapPoints.map(({ it, p, dlat, dlon }) => (
              <CircleMarker key={it.identity} center={[dlat, dlon]} radius={selected === it.identity ? 11 : 8}
                pathOptions={{ color: p.source === "déduite" || p.source === "repli" ? "#ffffff" : p.source === "nom" ? "#666666" : STATE_HEX[it.state], fillColor: STATE_HEX[it.state], fillOpacity: p.source === "repli" ? 0.35 : 0.85, weight: 2, dashArray: p.source === "déduite" ? "3 3" : null }}
                eventHandlers={{ click: () => setSelected(it.identity) }}>
                <Popup>
                  <strong>{it.name}</strong> — {STATE_LABELS[it.state]} ({it.stateText})<br />
                  {it.ip && <code>{it.ip}</code>}{it.site && <> · {it.site}</>}<br />
                  <span className="muted">position : {describeChain(p)}</span>
                </Popup>
              </CircleMarker>
            ))}
          </MapContainer>
          <div className="ss-map-legend">
            {Object.entries(STATE_HEX).map(([s, c]) => <span key={s}><i style={{ background: c }} /> {STATE_LABELS[s]}</span>)}
            <span><i style={{ background: "transparent", border: "2px dashed #666" }} /> déduite</span>
            <span><i style={{ background: "#999", opacity: 0.4 }} /> repli</span>
            <span><i style={{ background: "transparent", border: "2px solid #666" }} /> nom</span>
            <span className="muted">{mapPoints.length}/{visible.length} positionnés · {mapLinks.length} liens</span>
          </div>
        </div>
      );
    } else if (f.kind === "table") {
      body = (
        <div className="hub-table-scroll ss-table">
          <table>
            <thead><tr><th></th><th>Équipement</th><th>Adresse</th><th>Site</th><th>État</th><th>Dernier relevé</th><th>Origine(s)</th><th>Position</th></tr></thead>
            <tbody>{visible.map((it) => {
              const p = positions.get(it.identity);
              return (
                <tr key={it.identity} className={`ups-row${selected === it.identity ? " active" : ""}`} onClick={() => setSelected(selected === it.identity ? null : it.identity)}>
                  <td title={ITEM_TYPES[it.type]?.label}>{ITEM_TYPES[it.type]?.icon}{priorities[it.identity] != null && <span title={`priorité ${priorities[it.identity]}`}> ★</span>}</td>
                  <td><strong>{it.name}</strong></td>
                  <td>{it.ip ? <code>{it.ip}</code> : <span className="muted">—</span>}</td>
                  <td>{(() => { const d = displaySite(it, matches); return d.site ? <>{d.site}{d.resolved && <span className="muted ss-resolved" title={`localisation ${MATCH_STATUS[d.status]?.label} d'après le nom`}> ({MATCH_STATUS[d.status]?.label})</span>}</> : <span className="muted">—</span>; })()}</td>
                  <td><Tone state={it.state}>{STATE_LABELS[it.state]}</Tone> <span className="muted" style={{ fontSize: 11 }}>{it.stateText}</span></td>
                  <td className="muted">{when(it.lastSeen)}</td>
                  <td onClick={(e) => e.stopPropagation()}>{it.origins.map((o) => <button key={o.key} className="secondary ss-origin" onClick={() => goto(o.origin)} title={`ouvrir la tuile ${o.origin}`}>{ITEM_TYPES[o.type]?.label || o.origin}</button>)}</td>
                  <td className="muted" style={{ fontSize: 11 }}>{p ? p.source : "—"}</td>
                </tr>
              );
            })}</tbody>
          </table>
          {visible.length === 0 && <p className="muted" style={{ padding: 8 }}>{loading ? "Chargement…" : "Rien de supervisé pour ces critères."}</p>}
        </div>
      );
    } else if (f.kind === "links") {
      const shown = selectedItem ? links.filter((l) => l.a === selectedItem.identity || l.b === selectedItem.identity) : links.filter((l) => l.kind !== "site").slice(0, 200);
      body = (
        <div className="ss-links">
          {selectedItem ? (
            <>
              <p style={{ margin: "4px 0 4px" }}><strong>{selectedItem.name}</strong> — position : {describeChain(positions.get(selectedItem.identity))}</p>
              {pixelGridApiBase && <MatchLine item={selectedItem} match={matches[selectedItem.identity]} places={placeNames} onDecide={decide} onReset={undecide} />}
            </>
          ) : <p className="muted" style={{ margin: "4px 0 8px" }}>Sélectionner un équipement pour voir sa chaîne de déduction ; ci-dessous les {shown.length} premiers liens.</p>}
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Type</th><th>Lien</th><th>Poids</th><th>Via</th></tr></thead>
              <tbody>{shown.map((l, k) => <tr key={k}><td>{l.kind}</td><td>{l.label}</td><td className="muted">{l.weight ? Math.round(l.weight / 1024) + " Ko" : "—"}</td><td className="muted">{l.via}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      );
    } else if (f.kind === "proposals") {
      body = <ProposalList proposals={proposals} checked={checkedProposals} onToggle={toggleProposal} compact />;
    } else if (f.kind === "timeline" || f.kind === "grid" || f.kind === "calendar") {
      const endMs = now, startMs = now - win.seconds * 1000;
      const header = (
        <div className="ss-tool-head">
          <span className="muted">{basketItems.length} équipement(s) {selection.length ? "cochés" : Object.keys(priorities).length ? "priorisés" : "(premiers visibles)"}{historyLoading ? " · chargement…" : ""}</span>
          <span style={{ flex: 1 }} />
          {HISTORY_WINDOWS.map((w) => <button key={w.id} className={`secondary ss-chip${windowId === w.id ? " active" : ""}`} onClick={() => setWindowId(w.id)}>{w.label}</button>)}
        </div>
      );
      if (f.kind === "timeline") {
        const W = 800, ROW = 22, LEFT = 150;
        const rows = basketItems.map((it) => ({ it, segs: stateSegments(history[it.identity] || [], { startMs, endMs, gapMs: win.bucketSeconds * 1000 * 3 }) }));
        const x = (t) => LEFT + ((t - startMs) / (endMs - startMs)) * (W - LEFT - 10);
        body = (
          <div className="ss-tool">
            {header}
            {rows.length === 0 ? <p className="muted">Rien à tracer : cocher des équipements dans la colonne Supervisés.</p> : (
              <ZoomableChart viewBox={`0 0 ${W} ${rows.length * ROW + 24}`} className="ss-timeline-svg" label="états dans le temps">
                {rows.map(({ it, segs }, i) => (
                  <g key={it.identity} transform={`translate(0, ${i * ROW})`}>
                    <text x={LEFT - 6} y={14} textAnchor="end" fontSize="11" fill="currentColor" className={selected === it.identity ? "ss-strong" : ""}>{it.name.slice(0, 22)}</text>
                    {segs.map((sg, k) => (
                      <rect key={k} x={x(sg.start)} y={4} width={Math.max(1, x(sg.end) - x(sg.start))} height={14} fill={STATE_HEX[sg.state]} opacity={sg.state === "unknown" ? 0.25 : 0.9} onClick={() => setSelected(it.identity)}>
                        <title>{`${it.name} — ${STATE_LABELS[sg.state]} (${sg.text || ""})
${when(new Date(sg.start).toISOString())} → ${when(new Date(sg.end).toISOString())}`}</title>
                      </rect>
                    ))}
                  </g>
                ))}
                <text x={LEFT} y={rows.length * ROW + 16} fontSize="10" fill="currentColor" opacity="0.7">{when(new Date(startMs).toISOString())}</text>
                <text x={W - 10} y={rows.length * ROW + 16} fontSize="10" fill="currentColor" opacity="0.7" textAnchor="end">{when(new Date(endMs).toISOString())}</text>
              </ZoomableChart>
            )}
          </div>
        );
      } else if (f.kind === "grid") {
        const bucketMs = win.bucketSeconds * 1000;
        const rows = basketItems.map((it) => ({ it, cells: bucketize(history[it.identity] || [], { startMs, endMs, bucketMs }) }));
        body = (
          <div className="ss-tool">
            {header}
            <p className="muted" style={{ margin: "0 0 6px", fontSize: 11 }}>Une case = {win.bucketSeconds >= 86400 ? "1 jour" : win.bucketSeconds >= 3600 ? `${win.bucketSeconds / 3600} h` : `${win.bucketSeconds / 60} min`}, couleur = pire état du créneau, gris = aucun relevé.</p>
            <div className="ss-grid">
              {rows.map(({ it, cells }) => (
                <div key={it.identity} className="ss-grid-row" onClick={() => setSelected(it.identity)}>
                  <span className="ss-grid-label" title={it.name}>{it.name.slice(0, 18)}</span>
                  <span className="ss-grid-cells">{cells.map((c, k) => <i key={k} style={{ background: c.state ? STATE_HEX[c.state] : "var(--border)" }} title={`${when(new Date(c.start).toISOString())} : ${c.state ? STATE_LABELS[c.state] : "aucun relevé"} (${c.count} relevé(s))`} />)}</span>
                </div>
              ))}
              {rows.length === 0 && <p className="muted">Rien à afficher : cocher des équipements.</p>}
            </div>
          </div>
        );
      } else {
        const calStart = now - Math.max(win.seconds, 30 * 86400) * 1000;
        const days = calendarDays(Object.fromEntries(basketItems.map((it) => [it.identity, history[it.identity] || []])), { startMs: calStart, endMs: now });
        body = (
          <div className="ss-tool">
            {header}
            <p className="muted" style={{ margin: "0 0 6px", fontSize: 11 }}>Un jour = nombre de relevés « pas ok » sur les équipements retenus (vert = 0, orange ≥ 1, rouge ≥ 3) ; les 30 derniers jours au moins.</p>
            <div className="ss-calendar">
              {days.map((d) => <div key={d.day} className={`ss-day ${dayTone(d.events)}`} title={`${d.day} : ${d.events} événement(s) sur ${d.items} équipement(s)`}><span>{d.day.slice(8)}</span><b>{d.events || ""}</b></div>)}
            </div>
          </div>
        );
      }
    } else if (f.kind === "geo") {
      const shownRows = geoList.filter((r) => geoFilter === "all" || (geoFilter === "todo" ? (r.status === "suggested" || r.status === "none" || (r.applied && !r.mapped)) : geoFilter === "applied" ? r.applied : r.status === geoFilter));
      body = (
        <div className="ss-geo">
          <div className="ss-tool-head">
            <span className="muted">{geoStats.applied}/{geoStats.total} localisés par le nom ou le site · {geoStats.suggested} à confirmer · {geoStats.none} sans correspondance · {geoStats.rejected} rejetés{geoStats.unmapped ? ` · ${geoStats.unmapped} lieu(x) sans coordonnées` : ""}{geoStats.pendingPlaces ? ` · ${geoStats.pendingPlaces} lieu(x) en attente de coordonnées` : ""}</span>
            <span style={{ flex: 1 }} />
            {[["todo", "à traiter"], ["applied", "appliquées"], ["rejected", "rejetées"], ["all", "toutes"]].map(([k, l]) => <button key={k} className={`secondary ss-chip${geoFilter === k ? " active" : ""}`} onClick={() => setGeoFilter(k)}>{l}</button>)}
          </div>
          {matchesError && <p className="hub-error" style={{ fontSize: 12 }}>{matchesError}</p>}
          {!pixelGridApiBase && <p className="muted">VITE_PIXEL_GRID_API_BASE_URL non configurée : pas de résolution par nom.</p>}
          <div className="hub-table-scroll">
            <table>
              <thead><tr><th>Équipement</th><th>Localisation</th><th>Statut</th><th></th></tr></thead>
              <tbody>{shownRows.map((r) => (
                <tr key={r.item.identity} className={selected === r.item.identity ? "active" : ""} onClick={() => setSelected(r.item.identity)}>
                  <td><strong>{r.item.name}</strong><br /><span className="muted" style={{ fontSize: 11 }}>{[r.item.ip, r.item.site ? `site déclaré : ${r.item.site}` : null].filter(Boolean).join(" · ") || "—"}</span></td>
                  <td>{r.match?.localisation ? <>{r.match.localisation}{r.match.mapped === false && <span className="muted"> (sans coordonnées)</span>}</> : <span className="muted">aucune</span>}{r.match?.score != null && r.match.status !== "manual" && <span className="muted" style={{ fontSize: 11 }}> · {r.match.method} {r.match.score}</span>}</td>
                  <td><span className={`np-tone ${r.applied ? "good" : r.status === "suggested" ? "warn" : "neutral"}`} style={{ fontSize: 11 }}>{r.status === "none" ? "aucune" : MATCH_STATUS[r.status]?.label}</span></td>
                  <td onClick={(e) => e.stopPropagation()}><MatchActions item={r.item} match={r.match} places={placeNames} onDecide={decide} onReset={undecide} /></td>
                </tr>
              ))}</tbody>
            </table>
            {shownRows.length === 0 && <p className="muted" style={{ padding: 8 }}>Rien pour ce filtre.</p>}
          </div>
          <details className="ss-aliases">
            <summary>Alias déclarés ({aliases.length}) — « @5 » → « Parc/Batiment 5 »</summary>
            <ul className="ss-list">
              {aliases.map((a) => <li key={a.alias}><span className="ss-name"><strong>{a.alias}</strong> → {a.localisation}</span><button className="secondary ss-origin" onClick={() => deleteAlias(pixelGridApiBase, a.alias, groups).then(refreshMatches)} title="supprimer l'alias">✕</button></li>)}
            </ul>
            <form className="ss-alias-form" onSubmit={submitAlias}>
              <input className="ss-search" placeholder="alias (ex. @5, tp5)" value={aliasForm.alias} onChange={(e) => setAliasForm((f) => ({ ...f, alias: e.target.value }))} />
              <select value={aliasForm.localisation} onChange={(e) => setAliasForm((f) => ({ ...f, localisation: e.target.value }))}><option value="">localisation…</option>{placeNames.map((l) => <option key={l} value={l}>{l}</option>)}</select>
              <button type="submit" className="secondary" disabled={!aliasForm.alias || !aliasForm.localisation}>Ajouter</button>
            </form>
          </details>
        </div>
      );
    } else if (f.kind === "radial") {
      const lay = radialLayout(buildHierarchy(visible), { radius: 230 });
      const S = 560;
      body = (
        <div className="ss-tool">
          <p className="muted" style={{ margin: "0 0 4px", fontSize: 11 }}>Sites → types → équipements ({visible.length}) ; couleur = état, clic = sélection. Molette/Ctrl pour zoomer, glisser pour déplacer.</p>
          <ZoomableChart viewBox={`0 0 ${S} ${S}`} className="ss-radial-svg" label="arbre radial des supervisés">
            <g transform={`translate(${S / 2}, ${S / 2})`}>
              {lay.links.map((l, k) => <line key={k} x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y} stroke="currentColor" opacity="0.25" />)}
              {lay.nodes.map((n, k) => (
                <g key={k} transform={`translate(${n.x}, ${n.y})`} onClick={() => n.identity && setSelected(n.identity)} style={{ cursor: n.identity ? "pointer" : "default" }}>
                  <circle r={n.kind === "item" ? (selected === n.identity ? 7 : 5) : n.kind === "root" ? 8 : 6} fill={n.kind === "item" ? STATE_HEX[n.state] : "var(--accent)"} opacity={n.kind === "item" ? 0.95 : 0.7} />
                  {/* feuilles : texte le long du rayon, retourné sur la moitié gauche pour rester lisible */}
                  <text x={n.kind !== "item" ? 0 : n.angle > Math.PI ? -8 : 8} y={n.kind === "item" ? 4 : -10} fontSize={n.kind === "item" ? 10 : 11}
                    textAnchor={n.kind !== "item" ? "middle" : n.angle > Math.PI ? "end" : "start"} fill="currentColor"
                    transform={n.kind === "item" ? `rotate(${(n.angle * 180) / Math.PI - 90 + (n.angle > Math.PI ? 180 : 0)})` : undefined}>
                    {n.kind === "type" ? (ITEM_TYPES[n.name]?.label || n.name) : n.name.slice(0, 20)}
                  </text>
                  <title>{n.kind === "item" ? `${n.name} — ${STATE_LABELS[n.state]}` : `${n.name} (${n.leafCount})`}</title>
                </g>
              ))}
            </g>
          </ZoomableChart>
        </div>
      );
    } else {
      body = (
        <div className="ss-summary">
          {["critical", "warning", "unknown", "ok"].map((s) => (
            <div key={s} className="ss-summary-card" style={{ borderColor: STATE_COLORS[s] }} onClick={() => toggleState(s)}>
              <div className="ss-summary-n" style={{ color: STATE_COLORS[s] }}>{summary[s] || 0}</div>
              <div className="muted">{STATE_LABELS[s]}</div>
            </div>
          ))}
          <div className="ss-summary-types">
            {Object.entries(summary.byType).map(([t, c]) => <div key={t}>{ITEM_TYPES[t]?.icon} {ITEM_TYPES[t]?.label} : {c.total}{c.critical ? <> · <Tone state="critical">{c.critical} critique(s)</Tone></> : null}{c.warning ? <> · <Tone state="warning">{c.warning} avert.</Tone></> : null}</div>)}
          </div>
        </div>
      );
    }
    return (
      <div key={i} className="ss-frame" style={{ gridArea: `f${i}` }}>
        <div className="ss-frame-head">
          <select value={f.kind} onChange={(e) => setFrameKind(i, e.target.value)}>
            {Object.entries(FRAME_KINDS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <span style={{ flex: 1 }} />
          {frames.length > 1 && <button className="secondary" onClick={() => removeFrame(i)} title="retirer ce cadre">✕</button>}
        </div>
        <div className="ss-frame-body">{body}</div>
      </div>
    );
  }

  return (
    <div className="hub-settings hub-settings-wide ss-root">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🗺 Supervision SI</h1>
        <span className="muted" style={{ fontSize: 13 }}>
          {summary.total} supervisé(s) · <Tone state="critical">{summary.critical} critique(s)</Tone> · <Tone state="warning">{summary.warning} avert.</Tone> · {proposals.length} proposition(s)
        </span>
        <span style={{ flex: 1 }} />
        {frames.length < 4 && <button className="secondary" onClick={addFrame}>+ cadre</button>}
        <button className="secondary" onClick={load}>⟳</button>
        {legacyFrontendUrl && <a className="secondary ss-legacy" href={legacyFrontendUrl} target="_blank" rel="noreferrer" title="ancienne maquette (outils en cours de redistribution)">ancienne maquette ↗</a>}
      </div>
      {errors.length > 0 && <p className="muted ss-errors" title={errors.join("\n")}>⚠ {errors.length} source(s) injoignable(s) : {errors.map((e) => e.split(" : ")[0]).join(", ")}</p>}

      <div className="ss-body">
        <aside className="ss-left">
          <div className="ss-tabs">
            {[["proposals", `Propositions (${proposals.length})`], ["supervised", `Supervisés (${visible.length})`], ["links", "Liens"]].map(([k, l]) => (
              <button key={k} className={`secondary na-section-toggle${tab === k ? " active" : ""}`} onClick={() => setTab(k)}>{l}</button>
            ))}
          </div>

          {tab === "supervised" && (
            <>
              <input className="ss-search" placeholder="filtrer : nom, IP, site, état" value={filter.text} onChange={(e) => setFilter({ ...filter, text: e.target.value })} />
              <div className="ss-chips">
                {Object.entries(ITEM_TYPES).map(([t, d]) => <button key={t} className={`secondary ss-chip${filter.types.includes(t) ? " active" : ""}`} onClick={() => toggleType(t)} title={d.label}>{d.icon} {d.label}</button>)}
              </div>
              <div className="ss-chips">
                {Object.keys(STATE_ORDER).map((s) => <button key={s} className={`secondary ss-chip${filter.states.includes(s) ? " active" : ""}`} style={{ borderColor: STATE_COLORS[s] }} onClick={() => toggleState(s)}>{STATE_LABELS[s]} ({summary[s] || 0})</button>)}
                {sitesList.length > 0 && (
                  <select value={filter.site} onChange={(e) => setFilter({ ...filter, site: e.target.value })}>
                    <option value="">tous les sites</option>{sitesList.map((s) => <option key={s} value={s}>{s}</option>)}
                  </select>
                )}
              </div>
              {selection.length > 0 && <div className="muted" style={{ fontSize: 11 }}>{selection.length} retenu(s) dans la corbeille <button className="secondary ss-chip" onClick={() => setSelection([])}>vider</button></div>}
              <ul className="ss-list">
                {visible.map((it) => (
                  <li key={it.identity} className={selected === it.identity ? "active" : ""} onClick={() => setSelected(selected === it.identity ? null : it.identity)}>
                    <input type="checkbox" className="ss-basket" checked={selection.includes(it.identity)} onChange={() => toggleBasket(it)} onClick={(e) => e.stopPropagation()} title="retenir pour la timeline / mosaïque / calendrier (corbeille)" />
                    <span className="ss-dot" style={{ background: STATE_COLORS[it.state] }} title={STATE_LABELS[it.state]} />
                    <span className="ss-icon" title={ITEM_TYPES[it.type]?.label}>{ITEM_TYPES[it.type]?.icon}</span>
                    <span className="ss-name"><strong>{it.name}</strong><br /><span className="muted">{it.ip || ""}{it.site ? ` · ${it.site}` : ""} · {it.stateText}</span></span>
                    <span className="ss-prio" onClick={(e) => e.stopPropagation()}>
                      <button className="secondary" title="prioriser / dé-prioriser" onClick={() => pin(it)}>{priorities[it.identity] != null ? "★" : "☆"}</button>
                      {priorities[it.identity] != null && <><button className="secondary" onClick={() => bump(it, -1)} title="monter">▲</button><button className="secondary" onClick={() => bump(it, 1)} title="descendre">▼</button></>}
                    </span>
                  </li>
                ))}
                {visible.length === 0 && <li className="muted">{loading ? "Chargement…" : "Aucun supervisé pour ces critères."}</li>}
              </ul>
            </>
          )}

          {tab === "proposals" && <ProposalList proposals={proposals} checked={checkedProposals} onToggle={toggleProposal} onNavigate={onNavigate} />}

          {tab === "links" && (
            <div className="ss-linkstab">
              <p className="muted" style={{ margin: "6px 0" }}>Liens construits automatiquement (flux captés, tunnels, appartenance à un site) : ils régissent la carte — un équipement sans coordonnées est positionné par ce à quoi il parle.</p>
              <ul className="ss-list">
                {visible.map((it) => {
                  const p = positions.get(it.identity);
                  const n = links.filter((l) => l.a === it.identity || l.b === it.identity).length;
                  return (
                    <li key={it.identity} className={selected === it.identity ? "active" : ""} onClick={() => setSelected(selected === it.identity ? null : it.identity)}>
                      <span className="ss-dot" style={{ background: p ? (p.source === "déduite" ? "#6c8ebf" : p.source === "repli" ? "#bbb" : STATE_COLORS.ok) : STATE_COLORS.critical }} title={p ? p.source : "sans position"} />
                      <span className="ss-name"><strong>{it.name}</strong> <span className="muted">· {n} lien(s)</span><br /><span className="muted">{describeChain(p)}</span></span>
                    </li>
                  );
                })}
              </ul>
            </div>
          )}
        </aside>

        <main className="ss-center" style={{ gridTemplateColumns: layout.columns, gridTemplateRows: layout.rows, gridTemplateAreas: layout.areas.join(" ") }}>
          {frames.map(renderFrame)}
        </main>
      </div>
    </div>
  );
}

function ProposalList({ proposals, checked, onToggle, onNavigate, compact }) {
  const KIND = { orchestrateur: { label: "orchestrateur", tool: "network-cycle" }, vigilance: { label: "vigilance", tool: "vigilance" }, decouvert: { label: "découvert", tool: "network-agent" }, agent: { label: "vu par un agent", tool: "si-agent" } };
  if (!proposals.length) return <p className="muted" style={{ padding: 6 }}>Aucune proposition : rien de nouveau côté orchestrateur, vigilance ni exploration.</p>;
  const kept = proposals.filter((p) => checked[p.key]).length;
  return (
    <div className="ss-proposals">
      {!compact && <p className="muted" style={{ margin: "6px 0" }}>{kept} retenue(s) sur {proposals.length} — cocher = à traiter (retenue), décocher = écartée ; le traitement se fait dans la tuile d'origine.</p>}
      <ul className="ss-list">
        {proposals.map((p) => (
          <li key={p.key} className={checked[p.key] ? "active" : ""}>
            <input type="checkbox" checked={!!checked[p.key]} onChange={() => onToggle(p)} title="retenir" />
            <span className="ss-name">
              <Tone state={p.severity === "critical" || p.severity === "high" ? "critical" : p.severity === "warning" || p.severity === "medium" ? "warning" : "unknown"}>{KIND[p.kind]?.label}</Tone> <strong>{p.label}</strong>
              <br /><span className="muted">{p.detail}{p.at ? ` · ${when(p.at)}` : ""}</span>
            </span>
            {onNavigate && <button className="secondary ss-origin" onClick={() => onNavigate(KIND[p.kind]?.tool)} title="ouvrir la tuile d'origine">↗</button>}
          </li>
        ))}
      </ul>
    </div>
  );
}
