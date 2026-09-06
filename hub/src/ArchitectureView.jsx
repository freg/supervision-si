import React, { useState, useEffect } from "react";
import {
  fetchEquipmentList, createEquipment, deleteEquipment, fetchOverview,
  fetchInterfaces, createInterface, deleteInterface, createLink, deleteLink,
  importFromNetworkAgent,
} from "./architectureClient.js";

// Tuile "Architecture réseau" (hub), livraison #253 -- nouveau
// chantier, demandé explicitement : quand un équipement remonte dans
// Zenoss ou lors d'un dysfonctionnement, identifier en un seul
// endroit les interfaces amont/aval, les accès de gestion, les lieux
// d'intervention et la documentation liée.
//
// ⚠️ Portée de cette première tranche : la TOPOLOGIE amont/aval est
// DÉCLARÉE ici (saisie manuelle -- connaissance métier, jamais
// déduite automatiquement du trafic observé, voir
// architecture/README.md). Accès (ssh-tunnels) et documents (GED)
// croisés EN DIRECT, jamais dupliqués. Localisation Zenoss PAS
// ENCORE croisée (structure en arbre côté Zenoss, différée à une
// prochaine tranche).

const EMPTY_EQUIPMENT_FORM = { name: "", ip_address: "", mac_address: "", equipment_type: "", notes: "" };

function formatBytes(bytes) {
  if (typeof bytes !== "number") return "?";
  if (bytes < 1024) return `${bytes} o`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} Ko`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} Mo`;
}

export default function ArchitectureView({ onBack, architectureApiBase }) {
  const [equipmentList, setEquipmentList] = useState([]);
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState(null);
  const [overview, setOverview] = useState(null);
  const [interfaces, setInterfaces] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [form, setForm] = useState(EMPTY_EQUIPMENT_FORM);
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [importResult, setImportResult] = useState(null);
  const [newInterfaceLabel, setNewInterfaceLabel] = useState("");
  const [linkForm, setLinkForm] = useState({ direction: "downstream", localInterfaceId: "", remoteEquipmentId: "", remoteInterfaceId: "" });
  const [remoteInterfaces, setRemoteInterfaces] = useState([]);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [architectureApiBase]);

  async function load() {
    setEquipmentList(await fetchEquipmentList(architectureApiBase, search || null));
  }

  async function handleSearch(e) {
    e.preventDefault();
    setEquipmentList(await fetchEquipmentList(architectureApiBase, search || null));
  }

  async function handleSelect(id) {
    setSelectedId(id);
    setLoading(true);
    setError(null);
    const [ov, ifaces] = await Promise.all([
      fetchOverview(architectureApiBase, id),
      fetchInterfaces(architectureApiBase, id),
    ]);
    if (ov.error) setError(ov.error);
    else setOverview(ov);
    setInterfaces(ifaces);
    setLoading(false);
  }

  async function refreshSelected() {
    if (selectedId) await handleSelect(selectedId);
  }

  async function handleImportFromNetworkAgent() {
    setBusy(true);
    setError(null);
    const result = await importFromNetworkAgent(architectureApiBase);
    if (result.error) setError(result.error);
    else setImportResult(result);
    await load();
    setBusy(false);
  }

  async function handleCreateEquipment(e) {
    e.preventDefault();
    if (!form.name) return;
    setBusy(true);
    const result = await createEquipment(architectureApiBase, form);
    if (result.error) setError(result.error);
    else {
      setForm(EMPTY_EQUIPMENT_FORM);
      setShowCreateForm(false);
      await load();
      handleSelect(result.id);
    }
    setBusy(false);
  }

  async function handleDeleteEquipment(id) {
    setBusy(true);
    await deleteEquipment(architectureApiBase, id);
    if (selectedId === id) {
      setSelectedId(null);
      setOverview(null);
    }
    await load();
    setBusy(false);
  }

  async function handleAddInterface(e) {
    e.preventDefault();
    if (!newInterfaceLabel || !selectedId) return;
    setBusy(true);
    await createInterface(architectureApiBase, selectedId, { label: newInterfaceLabel });
    setNewInterfaceLabel("");
    await refreshSelected();
    setBusy(false);
  }

  async function handleDeleteInterface(id) {
    setBusy(true);
    await deleteInterface(architectureApiBase, id);
    await refreshSelected();
    setBusy(false);
  }

  async function handleRemoteEquipmentChange(equipmentId) {
    setLinkForm({ ...linkForm, remoteEquipmentId: equipmentId, remoteInterfaceId: "" });
    setRemoteInterfaces(equipmentId ? await fetchInterfaces(architectureApiBase, equipmentId) : []);
  }

  async function handleCreateLink(e) {
    e.preventDefault();
    const { direction, localInterfaceId, remoteInterfaceId } = linkForm;
    if (!localInterfaceId || !remoteInterfaceId) return;
    setBusy(true);
    const payload = direction === "downstream"
      ? { upstream_interface_id: Number(localInterfaceId), downstream_interface_id: Number(remoteInterfaceId) }
      : { upstream_interface_id: Number(remoteInterfaceId), downstream_interface_id: Number(localInterfaceId) };
    const result = await createLink(architectureApiBase, payload);
    if (result.error) setError(result.error);
    else {
      setLinkForm({ direction: "downstream", localInterfaceId: "", remoteEquipmentId: "", remoteInterfaceId: "" });
      setRemoteInterfaces([]);
      await refreshSelected();
    }
    setBusy(false);
  }

  async function handleDeleteLink(id) {
    setBusy(true);
    await deleteLink(architectureApiBase, id);
    await refreshSelected();
    setBusy(false);
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🗺️ Architecture réseau</h1>
      </div>

      <div className="hub-card">
        <p className="muted" style={{ margin: 0 }}>
          Pour un équipement, en un seul endroit : les interfaces amont/aval (déclarées ici -- connaissance
          métier, jamais déduite automatiquement), les accès de gestion (croisés depuis <strong>Tunnels
          SSH</strong>) et les documents liés (croisés depuis la <strong>GED</strong>). La localisation
          Zenoss n'est pas encore croisée dans cette première tranche.
        </p>
      </div>

      {error && (
        <div className="hub-card" style={{ borderColor: "var(--hub-danger, #c0392b)" }}>
          <p style={{ margin: 0 }}>⚠️ {error}</p>
        </div>
      )}

      <div className="hub-card hub-settings-section">
        <form onSubmit={handleSearch} style={{ display: "flex", gap: 8, marginBottom: 12 }}>
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Rechercher par nom ou IP…" style={{ flex: 1 }} />
          <button type="submit" className="secondary">Rechercher</button>
          <button type="button" onClick={() => setShowCreateForm((v) => !v)}>+ Équipement</button>
          <button type="button" className="secondary" onClick={handleImportFromNetworkAgent} disabled={busy}>
            ⤵ Importer depuis Exploration réseau
          </button>
        </form>
        {importResult && (
          <p className="muted" style={{ marginTop: -4 }}>
            {importResult.created} créé(s), {importResult.updated} IP mise(s) à jour, {importResult.skipped} ignoré(s).
          </p>
        )}

        {showCreateForm && (
          <form onSubmit={handleCreateEquipment} className="hub-card" style={{ marginBottom: 12 }}>
            <div className="hub-settings-row">
              <label>Nom</label>
              <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} required />
            </div>
            <div className="hub-settings-row">
              <label>Adresse IP</label>
              <input value={form.ip_address} onChange={(e) => setForm({ ...form, ip_address: e.target.value })} />
            </div>
            <div className="hub-settings-row">
              <label>Adresse MAC</label>
              <input value={form.mac_address} onChange={(e) => setForm({ ...form, mac_address: e.target.value })} />
            </div>
            <div className="hub-settings-row">
              <label>Type</label>
              <input value={form.equipment_type} onChange={(e) => setForm({ ...form, equipment_type: e.target.value })} placeholder="ex. routeur, switch, serveur" />
            </div>
            <div className="hub-settings-row">
              <label>Notes</label>
              <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
            </div>
            <button type="submit" disabled={busy}>Créer</button>
          </form>
        )}

        <table>
          <thead><tr><th>Nom</th><th>IP</th><th>Type</th><th></th></tr></thead>
          <tbody>
            {equipmentList.map((eq) => (
              <tr key={eq.id} className={selectedId === eq.id ? "active" : ""} style={{ cursor: "pointer" }}>
                <td onClick={() => handleSelect(eq.id)}>{eq.name}</td>
                <td onClick={() => handleSelect(eq.id)} className="muted">{eq.ip_address || "—"}</td>
                <td onClick={() => handleSelect(eq.id)} className="muted">{eq.equipment_type || "—"}</td>
                <td><button className="secondary" onClick={() => handleDeleteEquipment(eq.id)}>🗑</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {loading ? (
        <p className="muted">Chargement…</p>
      ) : overview && (
        <div className="hub-card hub-settings-section">
          <h2>{overview.equipment.name}</h2>
          <p className="muted" style={{ marginTop: -8 }}>
            {overview.equipment.ip_address || "sans IP"} — {overview.equipment.equipment_type || "type non renseigné"}
            {overview.equipment.notes && ` — ${overview.equipment.notes}`}
          </p>

          <div style={{ display: "flex", gap: 24, flexWrap: "wrap" }}>
            <div style={{ flex: "1 1 280px" }}>
              <h3 style={{ marginBottom: 4 }}>⬆️ En amont</h3>
              {overview.neighbors.upstream.length === 0 ? (
                <p className="muted">Aucun (sommet de la chaîne connue, ou pas encore déclaré).</p>
              ) : (
                <ul>
                  {overview.neighbors.upstream.map((n) => (
                    <li key={n.link_id}>
                      {n.local_interface_label} ← {n.remote_interface_label} sur{" "}
                      <a href="#" onClick={(e) => { e.preventDefault(); handleSelect(n.remote_equipment_id); }}>{n.remote_equipment_name}</a>
                      {" "}<button className="secondary" onClick={() => handleDeleteLink(n.link_id)}>🗑</button>
                    </li>
                  ))}
                </ul>
              )}

              <h3 style={{ marginBottom: 4 }}>⬇️ En aval</h3>
              {overview.neighbors.downstream.length === 0 ? (
                <p className="muted">Aucun (extrémité de la chaîne connue, ou pas encore déclaré).</p>
              ) : (
                <ul>
                  {overview.neighbors.downstream.map((n) => (
                    <li key={n.link_id}>
                      {n.local_interface_label} → {n.remote_interface_label} sur{" "}
                      <a href="#" onClick={(e) => { e.preventDefault(); handleSelect(n.remote_equipment_id); }}>{n.remote_equipment_name}</a>
                      {" "}<button className="secondary" onClick={() => handleDeleteLink(n.link_id)}>🗑</button>
                    </li>
                  ))}
                </ul>
              )}

              <h3 style={{ marginBottom: 4 }}>Interfaces</h3>
              <ul>
                {interfaces.map((iface) => (
                  <li key={iface.id}>{iface.label} <button className="secondary" onClick={() => handleDeleteInterface(iface.id)}>🗑</button></li>
                ))}
              </ul>
              <form onSubmit={handleAddInterface} style={{ display: "flex", gap: 8 }}>
                <input value={newInterfaceLabel} onChange={(e) => setNewInterfaceLabel(e.target.value)} placeholder="ex. Gi0/1" />
                <button type="submit" disabled={busy}>+ Interface</button>
              </form>

              <h4 style={{ marginTop: 12, marginBottom: 4 }}>Déclarer un lien</h4>
              <form onSubmit={handleCreateLink} style={{ display: "flex", flexDirection: "column", gap: 6 }}>
                <select value={linkForm.direction} onChange={(e) => setLinkForm({ ...linkForm, direction: e.target.value })}>
                  <option value="downstream">Cet équipement est EN AMONT de…</option>
                  <option value="upstream">Cet équipement est EN AVAL de…</option>
                </select>
                <select value={linkForm.localInterfaceId} onChange={(e) => setLinkForm({ ...linkForm, localInterfaceId: e.target.value })}>
                  <option value="">— interface locale —</option>
                  {interfaces.map((iface) => <option key={iface.id} value={iface.id}>{iface.label}</option>)}
                </select>
                <select value={linkForm.remoteEquipmentId} onChange={(e) => handleRemoteEquipmentChange(e.target.value)}>
                  <option value="">— équipement distant —</option>
                  {equipmentList.filter((eq) => eq.id !== selectedId).map((eq) => <option key={eq.id} value={eq.id}>{eq.name}</option>)}
                </select>
                <select value={linkForm.remoteInterfaceId} onChange={(e) => setLinkForm({ ...linkForm, remoteInterfaceId: e.target.value })}>
                  <option value="">— interface distante —</option>
                  {remoteInterfaces.map((iface) => <option key={iface.id} value={iface.id}>{iface.label}</option>)}
                </select>
                <button type="submit" disabled={busy}>Déclarer ce lien</button>
              </form>
            </div>

            <div style={{ flex: "1 1 280px" }}>
              <h3 style={{ marginBottom: 4 }}>📍 Lieu d'intervention</h3>
              {overview.location_error && <p style={{ color: "var(--hub-danger, #c0392b)" }}>⚠️ {overview.location_error}</p>}
              {!overview.location_error && overview.location === null && (
                <p className="muted">Aucune localisation connue de Zenoss pour cet équipement.</p>
              )}
              {overview.location && (
                <p style={{ margin: 0 }}>
                  <strong>{overview.location.location || "—"}</strong>
                  {overview.location.systems && <span className="muted"> ({overview.location.systems})</span>}
                </p>
              )}

              <h3 style={{ marginBottom: 4, marginTop: 12 }}>🔑 Accès de gestion</h3>
              {overview.ssh_access_error && <p style={{ color: "var(--hub-danger, #c0392b)" }}>⚠️ {overview.ssh_access_error}</p>}
              {overview.ssh_access.length === 0 ? (
                <p className="muted">Aucun accès SSH connu pour cette IP.</p>
              ) : (
                <ul>
                  {overview.ssh_access.map((c) => (
                    <li key={c.id}>{c.label} — {c.ssh_user}@{c.ssh_host}</li>
                  ))}
                </ul>
              )}

              <h3 style={{ marginBottom: 4 }}>📄 Documents liés</h3>
              {overview.documents_error && <p style={{ color: "var(--hub-danger, #c0392b)" }}>⚠️ {overview.documents_error}</p>}
              {overview.documents.length === 0 ? (
                <p className="muted">Aucun document lié.</p>
              ) : (
                <ul>
                  {overview.documents.map((d) => <li key={d.id}>{d.name}</li>)}
                </ul>
              )}

              <h3 style={{ marginBottom: 4 }}>📈 Niveaux d'usage</h3>
              {overview.usage_error && <p style={{ color: "var(--hub-danger, #c0392b)" }}>⚠️ {overview.usage_error}</p>}
              {!overview.usage_error && overview.usage === null && (
                <p className="muted">Cette IP n'est pas surveillée par Exploration réseau -- aucun historique disponible.</p>
              )}
              {overview.usage && (
                <>
                  <p>
                    Volume cumulé actuel : <strong>{formatBytes(overview.usage.device.bytes_total)}</strong>
                    {overview.usage.growth_percent !== null && (
                      <>
                        {" — "}
                        <strong style={{ color: overview.usage.growth_percent > 0 ? "var(--hub-danger, #c0392b)" : "inherit" }}>
                          {overview.usage.growth_percent > 0 ? "+" : ""}{overview.usage.growth_percent}%
                        </strong>{" "}
                        depuis le premier relevé -- utile pour repérer une tendance (engorgement à anticiper) ou
                        justifier un investissement.
                      </>
                    )}
                  </p>
                  {overview.usage.history.length === 0 ? (
                    <p className="muted">Aucun relevé encore enregistré.</p>
                  ) : (
                    <table>
                      <thead><tr><th>Relevé</th><th>Volume cumulé</th></tr></thead>
                      <tbody>
                        {overview.usage.history.map((h, idx) => (
                          <tr key={idx}>
                            <td className="muted">{new Date(h.snapshot_at).toLocaleString("fr-FR")}</td>
                            <td>{formatBytes(h.bytes_total)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
