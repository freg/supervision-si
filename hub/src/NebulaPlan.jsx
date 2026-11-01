// Plan du site (livraison #555) : une image de plan déposée par site, sur
// laquelle on pose les appareils (passerelle, commutateurs, bornes) ; les
// clients se placent en anneau autour de l'appareil qui les sert, ou à un
// endroit choisi. Positions en fractions de l'image, enregistrées par
// /sites/<id>/placements (fusion) ; couleurs = état courant. Logique pure
// dans nebulaPlan.js.
import { useEffect, useMemo, useRef, useState } from "react";
import { planItems, toFraction, mergePlacements } from "./nebulaPlan.js";
import { KIND_LABEL } from "./nebulaTree.js";
import { STATUS_COLOR } from "./NebulaTopo.jsx";

async function getJson(url, init) {
  const r = await fetch(url, { credentials: "include", ...(init || {}) });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || `${r.status}`);
  return j;
}

const GLYPH = { gateway: "⛨", switch: "▤", ap: "◉", other: "▣" };

export default function NebulaPlan({ nebulaApiBase }) {
  const [sites, setSites] = useState([]);
  const [siteId, setSiteId] = useState("");
  const [tree, setTree] = useState(null);
  const [placements, setPlacements] = useState({});
  const [hasPlan, setHasPlan] = useState(null);
  const [planVersion, setPlanVersion] = useState(0);
  const [size, setSize] = useState(null); // taille naturelle de l'image
  const [placing, setPlacing] = useState(null); // clé en cours de pose
  const [drag, setDrag] = useState(null); // {key, x, y}
  const [selected, setSelected] = useState(null);
  const [showClients, setShowClients] = useState(true);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  const imgRef = useRef(null);
  const base = `${nebulaApiBase}/sites/${encodeURIComponent(siteId)}`;

  useEffect(() => {
    getJson(`${nebulaApiBase}/health-board?hours=1`).then((d) => { setSites(d.sites || []); if (d.sites && d.sites[0]) setSiteId(d.sites[0].site_id); }).catch((e) => setError(e.message));
  }, [nebulaApiBase]);

  const load = async () => {
    if (!siteId) return;
    setBusy(true); setError(null);
    try {
      const [t, p] = await Promise.all([getJson(`${base}/topology`), getJson(`${base}/placements`)]);
      setTree(t); setPlacements(p.placements || {});
      const r = await fetch(`${base}/plan`, { credentials: "include", method: "HEAD" }).catch(() => null);
      setHasPlan(!!(r && r.ok));
    } catch (e) { setError(e.message); }
    finally { setBusy(false); }
  };
  useEffect(() => { load(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [siteId]);
  useEffect(() => { if (!siteId) return; const t = setInterval(() => getJson(`${base}/topology`).then(setTree).catch(() => {}), 60000); return () => clearInterval(t); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [siteId]);

  const items = useMemo(() => (tree ? planItems(tree, placements) : { devices: [], clients: [], unplaced: [] }), [tree, placements]);
  const byId = useMemo(() => new Map((tree?.nodes || []).map((n) => [n.id, n])), [tree]);

  const save = async (patch) => {
    setPlacements((cur) => mergePlacements(cur, patch));
    try { const r = await getJson(`${base}/placements`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ placements: patch }) }); setPlacements(r.placements || {}); }
    catch (e) { setError(`Enregistrement : ${e.message}`); }
  };

  const box = () => imgRef.current?.getBoundingClientRect();
  const onPlanClick = (ev) => {
    if (!placing) { setSelected(null); return; }
    const f = toFraction(ev.clientX, ev.clientY, box());
    if (f) save({ [placing]: f });
    setPlacing(null);
  };
  const onPointerDown = (ev, key) => { ev.stopPropagation(); ev.preventDefault(); setSelected(key); setDrag({ key, moved: false }); };
  const onPointerMove = (ev) => {
    if (!drag) return;
    const f = toFraction(ev.clientX, ev.clientY, box());
    if (f) setDrag({ ...drag, moved: true, ...f });
  };
  const onPointerUp = () => {
    if (drag && drag.moved) save({ [drag.key]: { x: drag.x, y: drag.y } });
    setDrag(null);
  };
  const posOf = (key, x, y) => (drag && drag.key === key && drag.moved ? { x: drag.x, y: drag.y } : { x, y });

  const upload = async (file) => {
    if (!file) return;
    const fd = new FormData(); fd.append("file", file);
    setBusy(true); setError(null);
    try { await getJson(`${base}/plan`, { method: "PUT", body: fd }); setHasPlan(true); setPlanVersion((v) => v + 1); }
    catch (e) { setError(`Dépôt du plan : ${e.message}`); }
    finally { setBusy(false); }
  };

  const W = size?.w || 1000, H = size?.h || 700;
  const sel = selected ? (selected.startsWith("client:") ? items.clients.find((c) => c.key === selected) : byId.get(selected)) : null;

  return (
    <div>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", marginBottom: 10 }}>
        <select value={siteId} onChange={(e) => { setSiteId(e.target.value); setSelected(null); setPlacing(null); }}>{sites.map((s) => <option key={s.site_id} value={s.site_id}>{s.site_name}</option>)}</select>
        <label className="secondary" style={{ cursor: "pointer" }}>{hasPlan ? "Remplacer le plan" : "Déposer un plan (PNG, JPG)"}<input type="file" accept="image/png,image/jpeg,image/webp,image/svg+xml" style={{ display: "none" }} onChange={(e) => { upload(e.target.files?.[0]); e.target.value = ""; }} /></label>
        <label className="muted"><input type="checkbox" checked={showClients} onChange={(e) => setShowClients(e.target.checked)} /> clients</label>
        <button type="button" className="secondary" disabled={busy} onClick={load}>{busy ? "Lecture…" : "Actualiser"}</button>
        {placing && <span style={{ color: "#1565c0" }}>Cliquer sur le plan pour poser <strong>{placing.startsWith("client:") ? items.clients.find((c) => c.key === placing)?.client.name : byId.get(placing)?.name}</strong> · <button type="button" className="secondary" onClick={() => setPlacing(null)}>annuler</button></span>}
      </div>
      {error && <p style={{ color: "var(--danger)" }}>{error}</p>}
      {hasPlan === false && <p className="muted">Aucun plan pour ce site : déposer une image (photo du plan d'évacuation, plan d'architecte…). Elle reste sur le serveur du hub, jamais dans le dépôt.</p>}
      <div style={{ display: "grid", gridTemplateColumns: "minmax(0, 1fr) 260px", gap: 12 }}>
        <div style={{ position: "relative", overflow: "auto", border: "1px solid var(--border)", borderRadius: 8, background: "var(--panel)", maxHeight: "75vh", cursor: placing ? "crosshair" : "default" }}
             onPointerMove={onPointerMove} onPointerUp={onPointerUp} onPointerLeave={onPointerUp}>
          {hasPlan && (
            <div style={{ position: "relative", display: "inline-block", minWidth: "100%" }}>
              <img ref={imgRef} src={`${base}/plan?v=${planVersion}`} alt="Plan du site" style={{ display: "block", width: "100%", height: "auto", userSelect: "none" }} draggable={false}
                   onLoad={(e) => setSize({ w: e.target.naturalWidth, h: e.target.naturalHeight })} onClick={onPlanClick} />
              <svg viewBox={`0 0 ${W} ${H}`} style={{ position: "absolute", inset: 0, width: "100%", height: "100%", pointerEvents: "none" }} fontFamily="system-ui, sans-serif">
                {showClients && items.clients.map((c) => {
                  const p = posOf(c.key, c.x, c.y); const parent = items.devices.find((d) => d.key === c.parent);
                  const pp = parent ? posOf(parent.key, parent.x, parent.y) : null;
                  const r = Math.max(5, W / 220);
                  return (
                    <g key={c.key} style={{ pointerEvents: "all", cursor: "grab" }} onPointerDown={(e) => onPointerDown(e, c.key)}>
                      {pp && !c.auto && <line x1={pp.x * W} y1={pp.y * H} x2={p.x * W} y2={p.y * H} stroke="#90a4ae" strokeWidth={Math.max(1, W / 1200)} strokeDasharray="4 3" />}
                      <circle cx={p.x * W} cy={p.y * H} r={r} fill={STATUS_COLOR[c.client.status] || "#9e9e9e"} stroke="#fff" strokeWidth={Math.max(1, W / 1000)} opacity={selected === c.key ? 1 : 0.85}>
                        <title>{c.client.name} · {c.client.ip || "—"} · {c.client.status}</title>
                      </circle>
                    </g>
                  );
                })}
                {items.devices.map((d) => {
                  const p = posOf(d.key, d.x, d.y); const r = Math.max(9, W / 110); const n = d.node;
                  return (
                    <g key={d.key} style={{ pointerEvents: "all", cursor: "grab" }} onPointerDown={(e) => onPointerDown(e, d.key)}>
                      <circle cx={p.x * W} cy={p.y * H} r={r} fill="#fff" stroke={selected === d.key ? "#1565c0" : STATUS_COLOR[n.status] || "#9e9e9e"} strokeWidth={Math.max(2, W / 400)} />
                      <text x={p.x * W} y={p.y * H + r * 0.4} fontSize={r * 1.1} textAnchor="middle" fill={STATUS_COLOR[n.status] || "#616161"}>{GLYPH[n.kind]}</text>
                      <text x={p.x * W} y={p.y * H + r * 2.1} fontSize={Math.max(10, W / 90)} textAnchor="middle" fill="#212121" stroke="#fff" strokeWidth={3} paintOrder="stroke" fontWeight="600">{n.name}</text>
                    </g>
                  );
                })}
              </svg>
            </div>
          )}
        </div>
        <div>
          {sel && (
            <div className="hub-card" style={{ marginTop: 0 }}>
              <div style={{ display: "flex", justifyContent: "space-between" }}><strong>{sel.client ? sel.client.name : sel.name}</strong><button type="button" className="secondary" onClick={() => setSelected(null)}>✕</button></div>
              {sel.client ? (
                <p className="muted" style={{ margin: "4px 0", fontSize: 12 }}>{sel.client.wired ? "Filaire" : "Wi-Fi"} · servi par {byId.get(sel.parent)?.name} · IP {sel.client.ip || "—"} · VLAN {sel.client.vlan ?? "—"} · {sel.client.status}{sel.auto ? " · placé automatiquement autour de son appareil" : ""}</p>
              ) : (
                <p className="muted" style={{ margin: "4px 0", fontSize: 12 }}>{KIND_LABEL[sel.kind]} · {sel.model || "—"} · {sel.status} · {sel.clients?.length || 0} client{(sel.clients?.length || 0) > 1 ? "s" : ""}</p>
              )}
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                <button type="button" className="secondary" onClick={() => setPlacing(selected)}>Déplacer par clic</button>
                {(sel.client ? !sel.auto : true) && <button type="button" className="secondary" onClick={() => { save({ [selected]: null }); setSelected(null); }}>{sel.client ? "Remettre en anneau" : "Retirer du plan"}</button>}
              </div>
              <p className="muted" style={{ fontSize: 11, margin: "6px 0 0" }}>Glisser un repère sur le plan pour le déplacer.</p>
            </div>
          )}
          <div className="hub-card">
            <strong>À poser ({items.unplaced.length})</strong>
            {items.unplaced.length === 0 ? <p className="muted" style={{ margin: "4px 0" }}>Tous les appareils sont sur le plan.</p> : (
              <ul style={{ margin: "4px 0", paddingLeft: 0, listStyle: "none" }}>
                {items.unplaced.map((n) => <li key={n.id} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 6, padding: "2px 0" }}>
                  <span><span style={{ color: STATUS_COLOR[n.status] || "#9e9e9e" }}>●</span> {n.name} <span className="muted" style={{ fontSize: 11 }}>{n.model}</span></span>
                  <button type="button" className="secondary" disabled={!hasPlan} onClick={() => setPlacing(n.id)}>Poser</button>
                </li>)}
              </ul>
            )}
          </div>
          <div className="hub-card">
            <strong>Posés ({items.devices.length})</strong>
            <ul style={{ margin: "4px 0", paddingLeft: 0, listStyle: "none" }}>
              {items.devices.map((d) => <li key={d.key} style={{ cursor: "pointer", padding: "2px 0" }} onClick={() => setSelected(d.key)}><span style={{ color: STATUS_COLOR[d.node.status] || "#9e9e9e" }}>●</span> {d.node.name}{d.node.clients?.length ? <span className="muted"> · {d.node.clients.length}</span> : null}</li>)}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
