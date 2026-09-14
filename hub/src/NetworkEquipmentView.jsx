import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  fetchNeStatus, fetchEquipment, fetchEquipmentDetail, updateEquipment, deleteEquipment, importNetworkAgent,
  identifyEquipment, identifyBatch, pollEquipment, fetchProfiles, fetchTopology, fetchFdb, importZenossFile, importOuiFile, createEquipment,
} from "./networkEquipmentClient.js";
import {
  kindLabel, generationTone, generationLabel, confidenceLabel, summarizeFleet, sortEquipment, filterEquipment,
  displayName, pollTone, topologyRows, previewSummary, KIND_CHOICES, isNetworkGear,
} from "./networkEquipment.js";

// Tuile « Équipements réseau » (livraison #506) -- facette de l'exploration :
// QUI sont les routeurs/switchs du LAN (constructeur, modèle, système,
// génération : récent MikroTik ou ancien de l'origine de la boucle locale)
// d'après l'exploration (OUI), SNMP (sysDescr, ENTITY-MIB, LLDP/CDP, table
// MAC), l'inventaire Zenoss (script zendmd ou CSV) et les choix manuels ;
// et QUOI relever dessus (profils de supervision génériques : Cisco IOS,
// HP ProCurve, MikroTik, Juniper, hôte, générique).
// Données : network-equipment-api (VITE_NETWORK_EQUIPMENT_API_BASE_URL).

function Tone({ tone, children, title }) {
  return <span className={`np-tone ${tone || "neutral"}`} title={title}>{children}</span>;
}

function when(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString("fr-FR");
}

const EMPTY_FILTERS = { q: "", kind: "", generation: "", vendor: "", networkOnly: false };

export default function NetworkEquipmentView({ onBack, networkEquipmentApiBase }) {
  const apiBase = networkEquipmentApiBase;
  const [status, setStatus] = useState(null);
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [tab, setTab] = useState("inventory");
  const [filters, setFilters] = useState(EMPTY_FILTERS);
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [topology, setTopology] = useState(null);
  const [zenossPreview, setZenossPreview] = useState(null);
  const [checked, setChecked] = useState(() => new Set());
  const [access, setAccess] = useState({ credential: "", target_id: "", community: "", port: "" });
  const zenossFileRef = useRef(null);
  const ouiFileRef = useRef(null);

  const load = useCallback(async () => {
    setLoading(true);
    const [st, eq] = await Promise.all([fetchNeStatus(apiBase), fetchEquipment(apiBase)]);
    setStatus(st);
    if (eq?.error) setError(eq.error);
    else setRows(eq.equipment);
    setLoading(false);
  }, [apiBase]);

  useEffect(() => { load(); }, [load]);

  const loadDetail = useCallback(async (id) => {
    if (id == null) { setDetail(null); return; }
    const d = await fetchEquipmentDetail(apiBase, id);
    if (d?.error) { setError(d.error); setDetail(null); return; }
    setDetail(d);
    setAccess({ credential: d.snmp_credential || "", target_id: d.snmp_target_id || "", community: "", port: d.snmp_port || "" });
  }, [apiBase]);

  useEffect(() => { loadDetail(selectedId); }, [selectedId, loadDetail]);

  useEffect(() => {
    if (tab === "profiles" && profiles.length === 0) fetchProfiles(apiBase).then((p) => setProfiles(p?.profiles || []));
    if (tab === "topology") fetchTopology(apiBase).then((t) => setTopology(t?.error ? null : t));
  }, [tab, apiBase, profiles.length]);

  const summary = useMemo(() => summarizeFleet(rows), [rows]);
  const visible = useMemo(() => sortEquipment(filterEquipment(rows, filters)), [rows, filters]);
  const vendors = useMemo(() => Object.entries(summary.byVendor).sort((a, b) => b[1] - a[1]), [summary]);

  const accessBody = () => {
    const b = {};
    if (access.community) b.community = access.community;
    else if (access.credential) b.credential = access.credential;
    else if (access.target_id) b.target_id = Number(access.target_id);
    if (access.port) b.port = Number(access.port);
    return b;
  };

  const run = async (fn, okMessage) => {
    setBusy(true); setError(null);
    const res = await fn();
    setBusy(false);
    if (res?.error) { setError(res.error); return null; }
    if (okMessage) setNotice(typeof okMessage === "function" ? okMessage(res) : okMessage);
    return res;
  };

  const handleImportExploration = () => run(() => importNetworkAgent(apiBase, {}),
    (r) => `Exploration importée : ${r.created} nouvelle(s) fiche(s), ${r.updated} mise(s) à jour, ${r.network_vendors} constructeur(s) réseau reconnu(s).`).then((r) => r && load());

  const handleZenossFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const r = await run(() => importZenossFile(apiBase, file, true));
    if (r) setZenossPreview({ file, result: r });
    e.target.value = "";
  };

  const confirmZenoss = async () => {
    if (!zenossPreview) return;
    const r = await run(() => importZenossFile(apiBase, zenossPreview.file, false),
      (x) => `Zenoss importé (${x.format}) : ${x.created} nouvelle(s) fiche(s), ${x.updated} mise(s) à jour.`);
    setZenossPreview(null);
    if (r) load();
  };

  const handleOuiFile = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const r = await run(() => importOuiFile(apiBase, file), (x) => `Registre OUI chargé : ${x.entries} préfixes.`);
    e.target.value = "";
    if (r) load();
  };

  const handleIdentify = async () => {
    if (!detail) return;
    const r = await run(() => identifyEquipment(apiBase, detail.id, { ...accessBody(), neighbors: true, fdb: true }),
      (x) => `Identifié : ${x.identification.vendor || "?"} ${x.identification.model || ""} (${kindLabel(x.identification.kind)}${x.identification.generation ? `, ${generationLabel(x.identification.generation).toLowerCase()}` : ""})${x.warnings?.length ? " — " + x.warnings.join(" ; ") : ""}`);
    if (r) { await load(); await loadDetail(detail.id); }
  };

  const handlePoll = async () => {
    if (!detail) return;
    const r = await run(() => pollEquipment(apiBase, detail.id, { ...accessBody() }),
      (x) => `Relevé ${x.profile}${x.verified ? "" : " (profil non vérifié sur matériel réel)"} : ${pollTone(x).text}${x.errors?.length ? " — " + x.errors.join(" ; ") : ""}`);
    if (r) { await load(); await loadDetail(detail.id); }
  };

  const handleBatch = async () => {
    const ids = Array.from(checked).slice(0, 50);
    if (!ids.length) return;
    const r = await run(() => identifyBatch(apiBase, ids, accessBody()), (x) => `Identification en lot : ${x.ok} réussie(s), ${x.failed} en échec.`);
    if (r) { setChecked(new Set()); load(); }
  };

  const handleSaveManual = async (form) => {
    if (!detail) return;
    const r = await run(() => updateEquipment(apiBase, detail.id, form), "Fiche mise à jour.");
    if (r) { await load(); await loadDetail(detail.id); }
  };

  const handleDelete = async () => {
    if (!detail || !window.confirm(`Supprimer la fiche « ${displayName(detail)} » ? (les preuves SNMP/Zenoss seront perdues, l'exploration la recréera si l'appareil est revu)`)) return;
    const r = await run(() => deleteEquipment(apiBase, detail.id), "Fiche supprimée.");
    if (r) { setSelectedId(null); load(); }
  };

  const handleCreate = async () => {
    const ip = window.prompt("Adresse IP de l'équipement à ajouter à la main (nom et MAC facultatifs ensuite) :");
    if (!ip) return;
    const r = await run(() => createEquipment(apiBase, { ip: ip.trim() }), "Fiche créée.");
    if (r) { await load(); setSelectedId(r.equipment.id); }
  };

  const toggleChecked = (id) => setChecked((s) => { const n = new Set(s); if (n.has(id)) n.delete(id); else n.add(id); return n; });

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🔎 Équipements réseau</h1>
      </div>

      {error && <p className="hub-error ups-notice">{error} <button className="secondary" onClick={() => setError(null)}>✕</button></p>}
      {notice && <p className="muted ups-notice">{notice} <button className="secondary" onClick={() => setNotice(null)}>✕</button></p>}

      <div className="hub-card hub-settings-section ups-status-card">
        {status && !status.error ? (
          <p style={{ margin: 0 }}>
            {summary.total} fiche(s) dont <Tone tone="good">{summary.network} équipement(s) réseau</Tone>
            {" · "}génération : <Tone tone="good">{summary.byGeneration.recent} récent(s)</Tone>, <Tone tone={summary.byGeneration.ancien ? "warn" : "neutral"}>{summary.byGeneration.ancien} ancien(s)</Tone>, {summary.byGeneration.inconnue} indéterminée(s)
            {" · "}{summary.unidentified} sans constructeur ni modèle · {status.identified} relevé(s) SNMP · {status.neighbors} voisin(s) LLDP/CDP · {status.fdb} adresse(s) MAC apprise(s)
            <br />
            <span className="muted">Sources :</span>{" "}
            {status.network_agent ? <Tone tone="good">exploration réseau</Tone> : <Tone tone="warn">exploration non configurée (NETWORK_AGENT_API_URL)</Tone>}
            {" · "}{status.snmp_api ? <Tone tone="good">snmp-api</Tone> : <Tone tone="warn">snmp-api non configuré</Tone>}
            {" · "}{status.credentials ? <Tone tone="good">coffre des accès</Tone> : <Tone tone="warn">coffre des accès non relié (jeton interne)</Tone>}
            {" · "}OUI : {status.oui?.file ? <Tone tone="good">registre IEEE ({status.oui.file} préfixes)</Tone> : <Tone tone="neutral" title="Charger oui.csv de l'IEEE pour reconnaître tous les constructeurs">amorce embarquée ({status.oui?.seed} préfixes)</Tone>}
            {status.imports?.length > 0 && <> · dernier import : {status.imports[0].source} {when(status.imports[0].at)}</>}
          </p>
        ) : (
          <p className="muted" style={{ margin: 0 }}>{loading ? "Chargement…" : "network-equipment-api injoignable."}</p>
        )}
      </div>

      <div className="ups-toolbar">
        <button className={`secondary na-section-toggle${tab === "inventory" ? " active" : ""}`} onClick={() => setTab("inventory")}>Inventaire ({rows.length})</button>
        <button className={`secondary na-section-toggle${tab === "topology" ? " active" : ""}`} onClick={() => setTab("topology")}>Topologie</button>
        <button className={`secondary na-section-toggle${tab === "profiles" ? " active" : ""}`} onClick={() => setTab("profiles")}>Profils de supervision</button>
        <span style={{ flex: 1 }} />
        <button className="secondary" disabled={busy || !status?.network_agent} onClick={handleImportExploration} title="Reprend les appareils vus par l'exploration réseau (MAC → constructeur)">Importer l'exploration</button>
        <button className="secondary" disabled={busy} onClick={() => zenossFileRef.current?.click()} title="JSON du script zendmd (connectors/zenoss_legacy/zendmd_export_devices.py) ou CSV « Export » de la liste des équipements Zenoss">Importer Zenoss…</button>
        <input ref={zenossFileRef} type="file" accept=".json,.csv,.txt,application/json,text/csv" style={{ display: "none" }} onChange={handleZenossFile} />
        <button className="secondary" disabled={busy} onClick={() => ouiFileRef.current?.click()} title="oui.csv (MA-L) ou oui.txt de standards-oui.ieee.org">Registre OUI…</button>
        <input ref={ouiFileRef} type="file" accept=".csv,.txt" style={{ display: "none" }} onChange={handleOuiFile} />
        <button className="secondary" disabled={busy} onClick={handleCreate}>+ Ajouter une IP</button>
      </div>

      {zenossPreview && (
        <div className="hub-card hub-settings-section">
          <h3 style={{ marginTop: 0 }}>Import Zenoss — analyse de « {zenossPreview.file.name} » ({zenossPreview.result.format})</h3>
          <p>
            {zenossPreview.result.parsed} fiche(s) reconnue(s), {zenossPreview.result.skipped_rows} ligne(s) ignorée(s), {zenossPreview.result.with_hardware} avec matériel/sysDescr.
            {zenossPreview.result.preview?.length > 0 && <> Identification prévue : {previewSummary(zenossPreview.result.preview)}.</>}
          </p>
          <div className="hub-table-scroll" style={{ maxHeight: 220 }}>
            <table>
              <thead><tr><th>Équipement</th><th>IP</th><th>Classe Zenoss</th><th>Constructeur</th><th>Modèle</th><th>Genre</th><th>Génération</th></tr></thead>
              <tbody>{(zenossPreview.result.preview || []).map((p, i) => (
                <tr key={i}><td>{p.name}</td><td><code>{p.ip || "—"}</code></td><td className="muted">{p.device_class || "—"}</td><td>{p.vendor || "—"}</td><td>{p.model || "—"}</td><td>{kindLabel(p.kind)}</td><td><Tone tone={generationTone(p.generation)}>{generationLabel(p.generation)}</Tone></td></tr>
              ))}</tbody>
            </table>
          </div>
          <p>
            <button disabled={busy} onClick={confirmZenoss}>Importer ces {zenossPreview.result.parsed} fiche(s)</button>{" "}
            <button className="secondary" onClick={() => setZenossPreview(null)}>Annuler</button>
          </p>
        </div>
      )}

      {tab === "inventory" && (
        <>
          <div className="ups-toolbar" style={{ flexWrap: "wrap", gap: 8 }}>
            <input type="search" placeholder="Rechercher (nom, IP, MAC, modèle, série…)" value={filters.q} onChange={(e) => setFilters((f) => ({ ...f, q: e.target.value }))} style={{ minWidth: 260 }} />
            <select value={filters.kind} onChange={(e) => setFilters((f) => ({ ...f, kind: e.target.value }))}>
              <option value="">Tous les genres</option>
              {Object.entries(summary.byKind).map(([k, n]) => <option key={k} value={k}>{kindLabel(k)} ({n})</option>)}
            </select>
            <select value={filters.generation} onChange={(e) => setFilters((f) => ({ ...f, generation: e.target.value }))}>
              <option value="">Toute génération</option>
              <option value="ancien">Anciens ({summary.byGeneration.ancien})</option>
              <option value="recent">Récents ({summary.byGeneration.recent})</option>
              <option value="inconnue">Indéterminée ({summary.byGeneration.inconnue})</option>
            </select>
            <select value={filters.vendor} onChange={(e) => setFilters((f) => ({ ...f, vendor: e.target.value }))}>
              <option value="">Tous les constructeurs</option>
              {vendors.map(([v, n]) => <option key={v} value={v}>{v} ({n})</option>)}
            </select>
            <label className="muted" style={{ fontSize: 12 }}><input type="checkbox" checked={filters.networkOnly} onChange={(e) => setFilters((f) => ({ ...f, networkOnly: e.target.checked }))} /> équipements réseau seulement</label>
            {checked.size > 0 && <button className="secondary" disabled={busy} onClick={handleBatch} title="Relevé SNMP d'identification des fiches cochées, avec l'accès saisi dans le volet de droite (coffre, cible snmp-api ou communauté ponctuelle)">Identifier les {checked.size} cochée(s)</button>}
            <span className="muted" style={{ fontSize: 12 }}>{visible.length} affichée(s)</span>
          </div>

          <div className="ne-layout">
            <div className="hub-table-scroll ne-table">
              <table>
                <thead><tr><th></th><th>Équipement</th><th>IP</th><th>MAC</th><th>Constructeur</th><th>Modèle</th><th>Système</th><th>Genre</th><th>Génération</th><th>Confiance</th><th>Sources</th><th>Profil</th><th>Dernier relevé</th></tr></thead>
                <tbody>{visible.map((r) => {
                  const conf = confidenceLabel(r.confidence);
                  const pt = pollTone(r.last_poll);
                  return (
                    <tr key={r.id} className={`ups-row${selectedId === r.id ? " active" : ""}${isNetworkGear(r) ? "" : " inactive"}`} onClick={() => setSelectedId(selectedId === r.id ? null : r.id)}>
                      <td onClick={(e) => e.stopPropagation()}><input type="checkbox" checked={checked.has(r.id)} onChange={() => toggleChecked(r.id)} /></td>
                      <td><strong>{displayName(r)}</strong>{r.site && <span className="muted"> · {r.site}</span>}</td>
                      <td><code>{r.ip || "—"}</code></td>
                      <td className="muted" style={{ fontSize: 12 }}>{r.mac || "—"}</td>
                      <td>{r.vendor || <span className="muted">{r.oui_vendor ? `${r.oui_vendor} ?` : "—"}</span>}</td>
                      <td>{r.model || "—"}</td>
                      <td className="muted" style={{ fontSize: 12 }}>{[r.os, r.os_version].filter(Boolean).join(" ") || "—"}</td>
                      <td>{kindLabel(r.kind)}</td>
                      <td><Tone tone={generationTone(r.generation)} title={r.generation_reason || ""}>{generationLabel(r.generation)}</Tone></td>
                      <td><Tone tone={conf.tone}>{conf.text}</Tone></td>
                      <td className="muted" style={{ fontSize: 12 }}>{(r.sources || []).join(", ") || "—"}</td>
                      <td className="muted" style={{ fontSize: 12 }}>{r.profile_id || "—"}</td>
                      <td style={{ fontSize: 12 }}><Tone tone={pt.tone} title={r.last_poll_at ? when(r.last_poll_at) : ""}>{pt.text}</Tone>{r.last_identify_error && <> <Tone tone="bad" title={r.last_identify_error}>⚠</Tone></>}</td>
                    </tr>
                  );
                })}</tbody>
              </table>
              {visible.length === 0 && <p className="muted">Aucune fiche{rows.length === 0 ? " -- « Importer l'exploration » ou « Importer Zenoss… » pour commencer." : " avec ces filtres."}</p>}
            </div>

            <div className="ne-detail">
              {detail ? (
                <EquipmentDetail detail={detail} access={access} setAccess={setAccess} busy={busy} apiBase={apiBase}
                  onIdentify={handleIdentify} onPoll={handlePoll} onSave={handleSaveManual} onDelete={handleDelete} onSelect={setSelectedId} />
              ) : (
                <div className="panel">
                  <p className="muted" style={{ margin: 0 }}>Sélectionner une fiche pour voir les preuves, l'identifier par SNMP (sysDescr, ENTITY-MIB, voisins, table MAC), corriger à la main ou relever son profil de supervision.</p>
                </div>
              )}
            </div>
          </div>
        </>
      )}

      {tab === "topology" && (
        <div className="panel">
          <h3 style={{ marginTop: 0 }}>Liens appris (LLDP, CDP, table des adresses MAC)</h3>
          {!topology && <p className="muted">Chargement…</p>}
          {topology && topologyRows(topology).length === 0 && <p className="muted">Aucun lien encore : identifier les switchs et routeurs par SNMP (les voisins LLDP/CDP et les ports d'accès des tables MAC sont rapprochés des fiches connues).</p>}
          {topology && topologyRows(topology).length > 0 && (
            <div className="hub-table-scroll"><table>
              <thead><tr><th>De</th><th>Vers</th><th>Vu par</th><th>Ports</th></tr></thead>
              <tbody>{topologyRows(topology).map((l, i) => (
                <tr key={i}><td><button className="secondary" style={{ padding: "0 6px" }} onClick={() => { setTab("inventory"); setSelectedId(l.fromId); }}>{l.from}</button></td>
                  <td><button className="secondary" style={{ padding: "0 6px" }} onClick={() => { setTab("inventory"); setSelectedId(l.toId); }}>{l.to}</button></td>
                  <td>{l.via}</td><td className="muted">{l.ports}</td></tr>
              ))}</tbody>
            </table></div>
          )}
        </div>
      )}

      {tab === "profiles" && (
        <div className="panel">
          <h3 style={{ marginTop: 0 }}>Profils de supervision génériques</h3>
          <p className="muted" style={{ fontSize: 12 }}>Ce que le hub relève en SNMP une fois l'équipement identifié (CPU, mémoire, température, ventilation/alimentation, voisins, table MAC ; interfaces IF-MIB pour tous). Les OID viennent des MIB publiques des constructeurs ; « non vérifié » = jamais relevé sur un équipement réel de ce type -- le premier relevé réel le confirmera.</p>
          {profiles.map((p) => (
            <details key={p.id} style={{ marginBottom: 8 }}>
              <summary><strong>{p.label}</strong> <span className="muted">({p.id})</span> {p.verified ? <Tone tone="good">vérifié</Tone> : <Tone tone="warn">non vérifié</Tone>}</summary>
              {p.notes?.length > 0 && <ul className="muted" style={{ fontSize: 12 }}>{p.notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
              <div className="hub-table-scroll"><table style={{ fontSize: 12 }}>
                <thead><tr><th>Relevé</th><th>OID</th><th>Type</th></tr></thead>
                <tbody>
                  {Object.entries(p.gets || {}).map(([k, g]) => <tr key={`g${k}`}><td>{g.label}</td><td><code>{g.oid}</code></td><td className="muted">GET{g.unit ? ` (${g.unit})` : ""}</td></tr>)}
                  {Object.entries(p.walks || {}).map(([k, w]) => <tr key={`w${k}`}><td>{w.label}</td><td><code>{w.oid}</code></td><td className="muted">WALK{w.unit ? ` (${w.unit})` : ""}</td></tr>)}
                  {Object.entries(p.common || {}).map(([k, w]) => <tr key={`c${k}`}><td>{w.label}</td><td><code>{w.oid}</code></td><td className="muted">WALK (commun)</td></tr>)}
                </tbody>
              </table></div>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}

function EquipmentDetail({ detail, access, setAccess, busy, apiBase, onIdentify, onPoll, onSave, onDelete, onSelect }) {
  const [form, setForm] = useState({ vendor: "", model: "", kind: "", generation: "", notes: "", name: "", site: "" });
  const [fdb, setFdb] = useState(null);
  useEffect(() => {
    const m = detail.manual || {};
    setForm({ vendor: m.vendor || "", model: m.model || "", kind: m.kind || "", generation: m.generation || "", notes: m.notes || "", name: detail.name || "", site: detail.site || "" });
    setFdb(null);
  }, [detail]);
  const conf = confidenceLabel(detail.confidence);
  const lp = detail.last_poll;
  const showFdb = async () => { const r = await fetchFdb(apiBase, detail.id); setFdb(r?.error ? { fdb: [], error: r.error } : r); };
  const zen = detail.zenoss || {};
  return (
    <div className="panel">
      <h3 style={{ margin: "0 0 6px" }}>{displayName(detail)} <span className="muted" style={{ fontSize: 12, fontWeight: "normal" }}>#{detail.id}{detail.ip ? ` · ${detail.ip}` : ""}{detail.mac ? ` · ${detail.mac}` : ""}</span></h3>
      <p style={{ margin: "0 0 8px" }}>
        <strong>{detail.vendor || "constructeur inconnu"}</strong> {detail.model || ""} {detail.os && <span className="muted">· {detail.os} {detail.os_version || ""}</span>}
        <br />{kindLabel(detail.kind)} · <Tone tone={generationTone(detail.generation)}>{generationLabel(detail.generation)}</Tone>{detail.generation_reason && <span className="muted"> ({detail.generation_reason})</span>}
        {" · "}confiance <Tone tone={conf.tone}>{conf.text}</Tone> · sources : {(detail.sources || []).join(", ") || "aucune"}
        {detail.serial && <> · série <code>{detail.serial}</code></>}
      </p>
      {(detail.notes || []).length > 0 && <p className="muted" style={{ fontSize: 12 }}>{detail.notes.join(" · ")}</p>}

      <details open>
        <summary><strong>Preuves</strong></summary>
        <table style={{ fontSize: 12 }}><tbody>
          <tr><td className="muted">OUI</td><td>{detail.oui_vendor || "—"}{detail.oui_category && <span className="muted"> ({detail.oui_category})</span>}</td></tr>
          <tr><td className="muted">sysDescr</td><td style={{ wordBreak: "break-word" }}>{detail.sys_descr || "—"}</td></tr>
          <tr><td className="muted">sysObjectID</td><td><code>{detail.sys_object_id || "—"}</code></td></tr>
          <tr><td className="muted">sysName / lieu</td><td>{detail.sys_name || "—"}{detail.sys_location && <> · {detail.sys_location}</>}</td></tr>
          <tr><td className="muted">ENTITY-MIB</td><td>{detail.entity ? Object.entries(detail.entity).filter(([k]) => k !== "index").map(([k, v]) => `${k}: ${v}`).join(" · ") : "—"}</td></tr>
          <tr><td className="muted">Zenoss</td><td>{detail.zenoss_class || zen.hw_product ? <>{detail.zenoss_class || ""} {zen.hw_manufacturer || ""} {zen.hw_product || ""} {zen.os_product ? `· ${zen.os_product}` : ""} {zen.production_state ? `· ${zen.production_state}` : ""}</> : "—"}</td></tr>
          <tr><td className="muted">Exploration</td><td>{detail.role_hint || "—"}{(detail.ports || []).length > 0 && <> · ports {detail.ports.join(", ")}</>}{detail.hostname && <> · {detail.hostname}</>}</td></tr>
          <tr><td className="muted">Relevé SNMP</td><td>{detail.last_identified_at ? when(detail.last_identified_at) : "jamais"}{detail.last_identify_error && <> · <Tone tone="bad">{detail.last_identify_error}</Tone></>}</td></tr>
        </tbody></table>
      </details>

      <details open>
        <summary><strong>Accès SNMP</strong> <span className="muted">(coffre, cible snmp-api ou communauté ponctuelle -- jamais stockée ici)</span></summary>
        <div className="ne-form">
          <label>Accès du coffre (genre snmp) <input value={access.credential} placeholder="ex. snmp-lan" onChange={(e) => setAccess((a) => ({ ...a, credential: e.target.value }))} /></label>
          <label>Cible snmp-api (id) <input value={access.target_id} placeholder="ex. 3" onChange={(e) => setAccess((a) => ({ ...a, target_id: e.target.value }))} style={{ width: 70 }} /></label>
          <label>Communauté ponctuelle <input type="password" autoComplete="off" value={access.community} onChange={(e) => setAccess((a) => ({ ...a, community: e.target.value }))} /></label>
          <label>Port <input value={access.port} placeholder="161" onChange={(e) => setAccess((a) => ({ ...a, port: e.target.value }))} style={{ width: 60 }} /></label>
        </div>
        <p style={{ margin: "6px 0" }}>
          <button disabled={busy || !detail.ip} onClick={onIdentify} title="sysDescr, sysObjectID, ENTITY-MIB, voisins LLDP/CDP, table des adresses MAC">Identifier par SNMP</button>{" "}
          <button className="secondary" disabled={busy || !detail.ip} onClick={onPoll} title={`Relevé du profil ${detail.profile?.id || ""}`}>Relever le profil {detail.profile?.id ? `(${detail.profile.id})` : ""}</button>
          {!detail.ip && <span className="muted"> · adresse IP inconnue : renseigner l'IP ci-dessous</span>}
        </p>
      </details>

      {lp && (
        <details open>
          <summary><strong>Dernier relevé</strong> <span className="muted">{when(detail.last_poll_at)} · profil {lp.profile}{lp.verified ? "" : " (non vérifié)"}</span></summary>
          <p style={{ margin: "4px 0" }}><Tone tone={pollTone(lp).tone}>{pollTone(lp).text}</Tone></p>
          {(lp.summary?.alarms || []).length > 0 && <ul style={{ margin: "4px 0" }}>{lp.summary.alarms.map((a, i) => <li key={i}><Tone tone="bad">{a}</Tone></li>)}</ul>}
          {(lp.summary?.components || []).length > 0 && <p className="muted" style={{ fontSize: 12 }}>{lp.summary.components.map((c) => `${c.name} : ${c.state}`).join(" · ")}</p>}
          {(lp.interfaces || []).length > 0 && (
            <div className="hub-table-scroll" style={{ maxHeight: 180 }}><table style={{ fontSize: 12 }}>
              <thead><tr><th>Interface</th><th>État</th><th>Vitesse</th></tr></thead>
              <tbody>{lp.interfaces.map((i, k) => <tr key={k}><td>{i.ifDescr}</td><td><Tone tone={i.ifOperStatus === "up" ? "good" : "neutral"}>{i.ifOperStatus}</Tone></td><td className="muted">{i.ifSpeed}</td></tr>)}</tbody>
            </table></div>
          )}
          {(lp.errors || []).length > 0 && <p className="muted" style={{ fontSize: 12 }}>Non relevé : {lp.errors.join(" ; ")}</p>}
          <details><summary className="muted" style={{ fontSize: 12 }}>valeurs brutes</summary><pre style={{ fontSize: 11, maxHeight: 240, overflow: "auto" }}>{JSON.stringify({ gets: lp.gets, walks: lp.walks }, null, 1)}</pre></details>
        </details>
      )}

      <details open={(detail.neighbors || []).length > 0}>
        <summary><strong>Voisins</strong> <span className="muted">({(detail.neighbors || []).length} LLDP/CDP · {detail.fdb_count || 0} MAC apprise(s))</span></summary>
        {(detail.neighbors || []).length > 0 && (
          <table style={{ fontSize: 12 }}><thead><tr><th>Port local</th><th>Voisin</th><th>Port distant</th><th>Vu par</th></tr></thead>
            <tbody>{detail.neighbors.map((n) => (
              <tr key={n.id}><td>{n.local_port || "—"}</td>
                <td>{n.remote_equipment_id ? <button className="secondary" style={{ padding: "0 6px" }} onClick={() => onSelect(n.remote_equipment_id)}>{n.remote_name || n.remote_chassis || n.remote_address}</button> : (n.remote_name || n.remote_chassis || n.remote_address || "?")}{n.remote_platform && <span className="muted"> · {n.remote_platform}</span>}</td>
                <td className="muted">{n.remote_port || "—"}</td><td className="muted">{n.protocol.toUpperCase()}</td></tr>
            ))}</tbody></table>
        )}
        {(detail.where || []).length > 0 && <p style={{ fontSize: 12, margin: "4px 0" }}>Cet équipement est appris sur : {detail.where.map((w, i) => <span key={i}><button className="secondary" style={{ padding: "0 6px" }} onClick={() => onSelect(w.equipment_id)}>{w.name || w.ip}</button> port {w.port}{w.vlan ? ` (VLAN ${w.vlan})` : ""}{w.port_macs > 1 ? ` (${w.port_macs} MAC sur ce port)` : ""} </span>)}</p>}
        {detail.fdb_count > 0 && !fdb && <button className="secondary" style={{ fontSize: 12 }} onClick={showFdb}>Voir la table des adresses MAC</button>}
        {fdb && (
          <div className="hub-table-scroll" style={{ maxHeight: 220 }}><table style={{ fontSize: 12 }}>
            <thead><tr><th>Port</th><th>VLAN</th><th>MAC</th><th>Constructeur</th><th>Fiche</th></tr></thead>
            <tbody>{(fdb.fdb || []).map((f) => <tr key={f.id}><td>{f.port || f.bridge_port}</td><td className="muted">{f.vlan || "—"}</td><td><code>{f.mac}</code></td><td className="muted">{f.oui_vendor || "—"}</td>
              <td>{f.known ? <button className="secondary" style={{ padding: "0 6px" }} onClick={() => onSelect(f.known.id)}>{f.known.name || f.known.ip}</button> : <span className="muted">inconnue</span>}</td></tr>)}</tbody>
          </table></div>
        )}
      </details>

      <details>
        <summary><strong>Corriger à la main</strong> <span className="muted">(le choix manuel a le dernier mot sur les sources)</span></summary>
        <div className="ne-form">
          <label>Nom <input value={form.name} onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))} /></label>
          <label>Site <input value={form.site} onChange={(e) => setForm((f) => ({ ...f, site: e.target.value }))} /></label>
          <label>Constructeur <input value={form.vendor} placeholder={detail.vendor || ""} onChange={(e) => setForm((f) => ({ ...f, vendor: e.target.value }))} /></label>
          <label>Modèle <input value={form.model} placeholder={detail.model || ""} onChange={(e) => setForm((f) => ({ ...f, model: e.target.value }))} /></label>
          <label>Genre <select value={form.kind} onChange={(e) => setForm((f) => ({ ...f, kind: e.target.value }))}><option value="">(déduit : {kindLabel(detail.kind)})</option>{KIND_CHOICES.map((k) => <option key={k} value={k}>{kindLabel(k)}</option>)}</select></label>
          <label>Génération <select value={form.generation} onChange={(e) => setForm((f) => ({ ...f, generation: e.target.value }))}><option value="">(déduite)</option><option value="ancien">Ancien</option><option value="recent">Récent</option></select></label>
          <label style={{ flexBasis: "100%" }}>Notes <input value={form.notes} onChange={(e) => setForm((f) => ({ ...f, notes: e.target.value }))} /></label>
        </div>
        <p style={{ margin: "6px 0" }}>
          <button disabled={busy} onClick={() => onSave(form)}>Enregistrer</button>{" "}
          <button className="secondary" disabled={busy} onClick={onDelete}>Supprimer la fiche</button>
        </p>
      </details>

      {(detail.history || []).length > 0 && (
        <details><summary className="muted" style={{ fontSize: 12 }}>historique des identifications ({detail.history.length})</summary>
          <ul className="muted" style={{ fontSize: 12 }}>{detail.history.map((h) => <li key={h.id}>{when(h.at)} · {h.source} → {h.result.vendor || "?"} {h.result.model || ""} ({kindLabel(h.result.kind)})</li>)}</ul>
        </details>
      )}
    </div>
  );
}
