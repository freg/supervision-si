import React, { useState, useEffect } from "react";
import { fetchImages, createImage, deleteImage, fetchCoverage } from "./backupRestoreClient.js";

// Tuile "Sauvegardes -- couverture" (hub), livraison #249 -- backlog
// item 27, sous-volet "backup-restore" marqué URGENT par la
// personne : "Clonezilla (ou équivalent) pour produire une IMAGE
// SYSTÈME complète -- objectif immédiat = future VIRTUALISATION de
// postes Windows existants".
//
// ⚠️ Portée VOLONTAIREMENT LIMITÉE au SUIVI/COUVERTURE -- répond à
// l'exigence explicite du backlog ("toute machine détectée doit
// avoir une image prête à la restauration"), PAS à l'automatisation
// réelle de Clonezilla (PXE/DRBL, hors de portée sans infrastructure
// matérielle à tester). Les images sont enregistrées MANUELLEMENT
// pour l'instant -- voir backup-restore/README.md.

const TOOL_LABELS = { clonezilla: "Clonezilla", backuppc: "BackupPC", other: "Autre" };
const EMPTY_FORM = { device_mac: "", device_label: "", tool: "clonezilla", taken_at: "", image_type: "", storage_path: "", notes: "" };

export default function BackupRestoreView({ onBack, backupRestoreApiBase }) {
  const [tab, setTab] = useState("coverage");
  const [coverage, setCoverage] = useState(null);
  const [images, setImages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);

  useEffect(() => {
    load(tab);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, backupRestoreApiBase]);

  async function load(which) {
    setLoading(true);
    setError(null);
    if (which === "coverage") {
      const result = await fetchCoverage(backupRestoreApiBase);
      if (result.error) setError(result.error);
      else setCoverage(result);
    } else {
      setImages(await fetchImages(backupRestoreApiBase));
    }
    setLoading(false);
  }

  async function handleCreate(e) {
    e.preventDefault();
    if (!form.device_label || !form.tool || !form.taken_at) return;
    setBusy(true);
    setError(null);
    const result = await createImage(backupRestoreApiBase, {
      ...form,
      device_mac: form.device_mac || null,
      image_type: form.image_type || null,
      storage_path: form.storage_path || null,
      notes: form.notes || null,
    });
    if (result.error) setError(result.error);
    else {
      setForm(EMPTY_FORM);
      load("images");
    }
    setBusy(false);
  }

  async function handleDelete(id) {
    setBusy(true);
    await deleteImage(backupRestoreApiBase, id);
    setBusy(false);
    load("images");
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>💾 Sauvegardes -- couverture</h1>
      </div>

      <div className="hub-card">
        <p className="muted" style={{ margin: 0 }}>
          Suivi des images système connues, croisé avec les appareils découverts par{" "}
          <strong>Exploration réseau</strong> -- répond à "toute machine détectée doit avoir une image
          prête à la restauration". Les images sont enregistrées manuellement ici pour l'instant --
          ceci ne déclenche AUCUNE capture Clonezilla réelle, c'est un registre, pas un pilotage.
        </p>
      </div>

      {error && (
        <div className="hub-card" style={{ borderColor: "var(--hub-danger, #c0392b)" }}>
          <p style={{ margin: 0 }}>⚠️ {error}</p>
        </div>
      )}

      <div className="hub-card hub-settings-section">
        <div className="tabs" style={{ marginBottom: 16 }}>
          <button className={tab === "coverage" ? "active" : ""} onClick={() => setTab("coverage")}>Couverture</button>
          <button className={tab === "images" ? "active" : ""} onClick={() => setTab("images")}>Images enregistrées</button>
        </div>

        {loading ? (
          <p className="muted">Chargement…</p>
        ) : tab === "coverage" ? (
          !coverage ? (
            <p className="muted">Aucune donnée -- Exploration réseau est-elle bien déployée et a-t-elle découvert des appareils ?</p>
          ) : (
            <>
              <p>
                <strong>{coverage.without_backup}</strong> appareil(s) sur <strong>{coverage.total}</strong> sans image connue.
              </p>
              <table>
                <thead>
                  <tr><th></th><th>Adresse MAC</th><th>IP</th><th>Rôle</th><th>Dernière image</th><th>Depuis</th></tr>
                </thead>
                <tbody>
                  {coverage.devices.map((d) => (
                    <tr key={d.mac_address}>
                      <td>{d.has_backup ? "✅" : "⚠️"}</td>
                      <td>{d.mac_address}</td>
                      <td>{d.ip_address}</td>
                      <td className="muted">{d.role_hint || "—"}</td>
                      <td className="muted">{d.last_backup_at ? `${d.last_backup_at} (${d.last_backup_tool})` : "aucune"}</td>
                      <td className="muted">{d.days_since_backup != null ? `${d.days_since_backup} j` : "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )
        ) : (
          <>
            <form onSubmit={handleCreate} style={{ marginBottom: 20 }}>
              <div className="hub-settings-row">
                <label>Machine (nom)</label>
                <input value={form.device_label} onChange={(e) => setForm({ ...form, device_label: e.target.value })} required />
              </div>
              <div className="hub-settings-row">
                <label>Adresse MAC (optionnel)</label>
                <input value={form.device_mac} onChange={(e) => setForm({ ...form, device_mac: e.target.value })} placeholder="pour rapprochement avec Exploration réseau" />
              </div>
              <div className="hub-settings-row">
                <label>Outil</label>
                <select value={form.tool} onChange={(e) => setForm({ ...form, tool: e.target.value })}>
                  {Object.entries(TOOL_LABELS).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                </select>
              </div>
              <div className="hub-settings-row">
                <label>Date de l'image</label>
                <input type="datetime-local" value={form.taken_at} onChange={(e) => setForm({ ...form, taken_at: e.target.value ? `${e.target.value}:00Z` : "" })} required />
              </div>
              <div className="hub-settings-row">
                <label>Type (optionnel)</label>
                <input value={form.image_type} onChange={(e) => setForm({ ...form, image_type: e.target.value })} placeholder="ex. disk-full" />
              </div>
              <div className="hub-settings-row">
                <label>Emplacement (optionnel)</label>
                <input value={form.storage_path} onChange={(e) => setForm({ ...form, storage_path: e.target.value })} placeholder="ex. /nas/images/pc1" />
              </div>
              <div className="hub-settings-row">
                <label>Notes (optionnel)</label>
                <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
              </div>
              <button type="submit" disabled={busy}>Enregistrer l'image</button>
            </form>

            {images.length === 0 ? (
              <p className="muted">Aucune image enregistrée.</p>
            ) : (
              <table>
                <thead>
                  <tr><th>Machine</th><th>MAC</th><th>Outil</th><th>Date</th><th>Emplacement</th><th></th></tr>
                </thead>
                <tbody>
                  {images.map((img) => (
                    <tr key={img.id}>
                      <td>{img.device_label}</td>
                      <td className="muted">{img.device_mac || "—"}</td>
                      <td>{TOOL_LABELS[img.tool] || img.tool}</td>
                      <td className="muted">{img.taken_at}</td>
                      <td className="muted">{img.storage_path || "—"}</td>
                      <td>
                        <button className="secondary" disabled={busy} onClick={() => handleDelete(img.id)}>🗑</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </>
        )}
      </div>
    </div>
  );
}
