import React, { useState, useEffect, useCallback } from "react";
import { listZones, createZone, deleteZone, zoneRecords, setRecord, deleteRecord, zoneChanges, revertChange, replayZone } from "./dnsClient.js";

// Tour de contrôle › Réseau › DNS ÉDITABLE (#656) : zones avec fournisseurs ordonnés (OVH / Scaleway = Internet avec
// cache, BIND intranet = fallback), enregistrements consolidés (divergence entre fournisseurs signalée), modification
// appliquée partout, journal avec retour en arrière, rejeu des modifications partielles. Secrets dans le coffre des accès.

export default function TowerDnsPanel({ dnsApiBase, login }) {
  const [zones, setZones] = useState([]); const [zone, setZone] = useState("");
  const [data, setData] = useState(null); const [changes, setChanges] = useState([]);
  const [form, setForm] = useState({ name: "", type: "A", value: "", ttl: 300 });
  const [newZone, setNewZone] = useState(null);
  const [busy, setBusy] = useState(""); const [error, setError] = useState(null); const [notice, setNotice] = useState(null);

  const loadZones = useCallback(async () => { const r = await listZones(dnsApiBase); if (r.error) setError(r.error); else { setZones(r.zones || []); if (!zone && r.zones?.[0]) setZone(r.zones[0].name); } }, [dnsApiBase, zone]);
  useEffect(() => { loadZones(); }, [loadZones]);
  const loadZone = useCallback(async (refresh) => {
    if (!zone) return; setBusy(refresh ? "refresh" : "load");
    const [r, c] = await Promise.all([zoneRecords(dnsApiBase, zone, refresh), zoneChanges(dnsApiBase, zone)]); setBusy("");
    if (r.error) setError(r.error); else { setData(r); if (refresh) setNotice("Rafraîchi : " + Object.entries(r.refreshed).map(([k, v]) => `${k} ${v}`).join(" · ")); }
    if (!c.error) setChanges(c.changes || []);
  }, [dnsApiBase, zone]);
  useEffect(() => { loadZone(false); }, [loadZone]);

  async function submit(e) {
    e.preventDefault(); setBusy("set"); setError(null); setNotice(null);
    const r = await setRecord(dnsApiBase, zone, { ...form, by_user: login }); setBusy("");
    if (r.error) { setError(r.error); return; }
    setNotice(r.status === "ok" ? `Enregistré sur tous les fournisseurs` : r.status === "partial" ? `Appliqué partiellement (${Object.entries(r.change.results).filter(([, v]) => !v.ok).map(([k, v]) => k + " : " + v.error).join(" ; ")}) — l'intranet répond, rejouez quand Internet revient` : `Échec : ${JSON.stringify(r.change?.results)}`);
    loadZone(false); loadZones();
  }
  async function remove(rec) {
    if (!window.confirm(`Supprimer ${rec.name} ${rec.type} sur tous les fournisseurs de ${zone} ?`)) return;
    const r = await deleteRecord(dnsApiBase, zone, { name: rec.name, type: rec.type, by_user: login }); if (r.error) setError(r.error); else { setNotice(`Supprimé (${r.status})`); loadZone(false); }
  }
  async function revert(ch) { const r = await revertChange(dnsApiBase, ch.id, login); if (r.error) setError(r.error); else { setNotice(`Retour en arrière appliqué (${r.status})`); loadZone(false); } }
  async function replay() { const r = await replayZone(dnsApiBase, zone); if (r.error) setError(r.error); else { setNotice(`Rejeu : ${r.replayed} rejouée(s), ${r.remaining} restante(s)`); loadZone(false); loadZones(); } }
  async function addZone() {
    const provs = newZone.providers.filter((p) => p.credential.trim());
    const r = await createZone(dnsApiBase, { ...newZone, providers: provs }); if (r.error) { setError(r.error); return; } setNewZone(null); setZone(r.zone.name); loadZones();
  }
  const z = zones.find((x) => x.name === zone);

  return (
    <div className="td-panel">
      <div className="td-head">
        <select value={zone} onChange={(e) => { setZone(e.target.value); setData(null); }}>{zones.map((x) => <option key={x.name} value={x.name}>{x.name}</option>)}{zones.length === 0 && <option value="">— aucune zone —</option>}</select>
        <button className="secondary td-mini" onClick={() => loadZone(true)} disabled={!zone || busy === "refresh"}>{busy === "refresh" ? "…" : "↻ relire les fournisseurs"}</button>
        <button className="secondary td-mini" onClick={replay} disabled={!zone}>rejouer les modifications partielles</button>
        <button className="secondary td-mini" onClick={() => setNewZone({ name: "", notes: "", providers: [{ kind: "ovh", credential: "", label: "ovh" }, { kind: "scaleway", credential: "", label: "scaleway" }, { kind: "bind", credential: "", label: "intranet", server: "" }] })}>+ zone</button>
        {z && <button className="secondary td-mini td-danger" onClick={async () => { if (window.confirm(`Retirer la zone ${zone} du hub (les fournisseurs ne sont pas touchés) ?`)) { await deleteZone(dnsApiBase, zone); setZone(""); loadZones(); } }}>retirer</button>}
      </div>
      {error && <p className="td-ko">⚠️ {error}</p>}{notice && <p className="td-ok">{notice}</p>}
      {newZone && (<div className="td-new">
        <input type="text" placeholder="zone (exemple.fr)" value={newZone.name} onChange={(e) => setNewZone({ ...newZone, name: e.target.value })} />
        {newZone.providers.map((p, i) => <div key={i} className="td-inline"><span className="muted">{i + 1}. {p.kind}{p.kind === "bind" ? " (intranet, fallback)" : " (Internet)"}</span>
          <input type="text" placeholder="accès du coffre" value={p.credential} onChange={(e) => setNewZone({ ...newZone, providers: newZone.providers.map((x, j) => (j === i ? { ...x, credential: e.target.value } : x)) })} />
          {p.kind === "bind" && <input type="text" placeholder="serveur DNS interne" value={p.server} onChange={(e) => setNewZone({ ...newZone, providers: newZone.providers.map((x, j) => (j === i ? { ...x, server: e.target.value } : x)) })} />}</div>)}
        <p className="muted">Coffre : OVH = identifiant « app_key/consumer_key », mot de passe = app secret · Scaleway = mot de passe = secret key · intranet = identifiant = nom de la clé TSIG, mot de passe = secret. Un fournisseur sans accès est ignoré.</p>
        <div className="td-inline"><button className="primary td-mini" onClick={addZone}>Créer</button><button className="secondary td-mini" onClick={() => setNewZone(null)}>Annuler</button></div></div>)}
      {z && <p className="muted">Fournisseurs : {z.providers.map((p) => { const st = (z.state || []).find((s) => s.provider === p.label); return `${p.label} (${p.role}${st ? ", " + (st.status === "ok" ? "ok" : "dégradé : " + st.last_error) : ""})`; }).join(" → ")}</p>}
      {data && (<table className="tn-table"><thead><tr><th>Nom</th><th>Type</th><th>Valeur</th>{data.providers.map((p) => <th key={p}>{p}</th>)}<th></th></tr></thead>
        <tbody>{data.records.map((r) => <tr key={r.name + r.type} className={r.divergent ? "tn-row-ko" : ""}><td><b>{r.name}</b></td><td>{r.type}</td><td>{r.value}{r.divergent && <span className="td-ko"> divergent</span>}</td>
          {data.providers.map((p) => <td key={p} className="muted">{(r.by_provider[p] || []).join(", ") || "—"}</td>)}
          <td className="td-actions"><button className="secondary td-mini" onClick={() => setForm({ name: r.name, type: r.type, value: r.value, ttl: r.ttl || 300 })}>modifier</button><button className="secondary td-mini td-danger" onClick={() => remove(r)}>✕</button></td></tr>)}
          {data.records.length === 0 && <tr><td colSpan={4 + data.providers.length} className="muted">Cache vide : « relire les fournisseurs ».</td></tr>}</tbody></table>)}
      {zone && (<form onSubmit={submit} className="td-inline td-form"><input type="text" placeholder="nom (@, www…)" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} style={{ width: 120 }} />
        <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>{["A", "AAAA", "CNAME", "TXT", "MX", "SRV", "NS"].map((t) => <option key={t}>{t}</option>)}</select>
        <input type="text" placeholder="valeur" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} style={{ flex: 1 }} /><input type="number" value={form.ttl} onChange={(e) => setForm({ ...form, ttl: Number(e.target.value) })} style={{ width: 80 }} title="TTL" />
        <button className="primary td-mini" type="submit" disabled={busy === "set"}>Appliquer partout</button></form>)}
      {changes.length > 0 && (<details className="tn-details"><summary>Journal ({changes.length})</summary>
        <table className="tn-table"><thead><tr><th>Quand</th><th>Qui</th><th>Action</th><th>Avant → après</th><th>Fournisseurs</th><th></th></tr></thead>
          <tbody>{changes.slice(0, 30).map((c) => <tr key={c.id} className={c.status === "partial" ? "tn-row-ko" : ""}><td className="muted">{(c.at || "").replace("T", " ").slice(0, 16)}</td><td>{c.by_user}</td><td>{c.action} {c.name} {c.type}</td><td>{(c.before || []).join(", ") || "∅"} → {c.after || "∅"}</td>
            <td className="muted">{Object.entries(c.results).map(([k, v]) => `${k} ${v.ok ? "✔" : "✘"}`).join(" ")}</td><td>{!c.reverted_by && <button className="secondary td-mini" onClick={() => revert(c)}>↶ annuler</button>}{c.reverted_by && <span className="muted">annulée (#{c.reverted_by})</span>}</td></tr>)}</tbody></table></details>)}
    </div>
  );
}
