import React, { useState, useEffect } from "react";
import { fetchImages, createImage, deleteImage, fetchCoverage } from "./backupRestoreClient.js";

// Tuile "Sauvegardes" (hub), livraison #270 -- backlog item 27
// Étend la vue #249 avec les connecteurs BackupPC, Clonezilla, Restic

const TOOL_LABELS = { clonezilla: "Clonezilla", backuppc: "BackupPC", restic: "Restic", other: "Autre" };
const EMPTY_FORM = { device_mac: "", device_label: "", tool: "clonezilla", taken_at: "", image_type: "", storage_path: "", notes: "" };

function formatBytes(bytes) {
  if (bytes == null) return "—";
  const units = ["o", "Ko", "Mo", "Go", "To"];
  let i = 0;
  let val = bytes;
  while (val >= 1024 && i < units.length - 1) { val /= 1024; i++; }
  return `${val.toFixed(1)} ${units[i]}`;
}

function formatDate(iso) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString("fr-FR");
  } catch {
    return iso;
  }
}

// --- Sous-vue BackupPC ---
function BackupPCView({ apiBase }) {
  const [hosts, setHosts] = useState([]);
  const [selectedHost, setSelectedHost] = useState(null);
  const [versions, setVersions] = useState([]);
  const [content, setContent] = useState(null);
  const [poolStats, setPoolStats] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function loadHosts() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${apiBase}/backuppc/hosts`);
      const data = await res.json();
      setHosts(data.hosts || []);
    } catch (err) {
      setError(`Erreur: ${err.message}`);
    }
    setLoading(false);
  }

  async function loadVersions(host) {
    setSelectedHost(host);
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/backuppc/hosts/${host}/versions`);
      const data = await res.json();
      setVersions(data.versions || []);
    } catch (err) {
      setError(`Erreur versions: ${err.message}`);
    }
    setLoading(false);
  }

  async function loadContent(host, version) {
    setLoading(true);
    try {
      const v = version ? `?version=${version}` : "";
      const res = await fetch(`${apiBase}/backuppc/hosts/${host}/content${v}`);
      const data = await res.json();
      setContent(data);
    } catch (err) {
      setError(`Erreur contenu: ${err.message}`);
    }
    setLoading(false);
  }

  async function loadPoolStats() {
    try {
      const res = await fetch(`${apiBase}/backuppc/pool/stats`);
      setPoolStats(await res.json());
    } catch (err) {
      // silencieux
    }
  }

  useEffect(() => {
    loadHosts();
    loadPoolStats();
  }, [apiBase]);

  return (
    <div>
      {poolStats && (
        <div className="hub-card" style={{ marginBottom: 16 }}>
          <h3>📊 Pool de déduplication</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
            <div><strong>{formatBytes(poolStats.pool_size_bytes)}</strong><br/><span className="muted">Taille du pool</span></div>
            <div><strong>{poolStats.total_files?.toLocaleString("fr-FR")}</strong><br/><span className="muted">Fichiers totaux</span></div>
            <div><strong>{poolStats.unique_files?.toLocaleString("fr-FR")}</strong><br/><span className="muted">Fichiers uniques</span></div>
            <div><strong>{poolStats.dedup_ratio?.toFixed(2)}x</strong><br/><span className="muted">Taux de déduplication</span></div>
          </div>
        </div>
      )}

      {error && <div className="hub-card" style={{ borderColor: "var(--danger)", marginBottom: 16 }}>⚠️ {error}</div>}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="hub-card">
          <h3>🖥️ Hôtes BackupPC</h3>
          {loading && !hosts.length ? <p className="muted">Chargement…</p> : (
            <table style={{ width: "100%" }}>
              <thead><tr><th>Hôte</th><th>Dernière sauvegarde</th><th>Taille</th><th>Statut</th></tr></thead>
              <tbody>
                {hosts.map((h) => (
                  <tr key={h.host} style={{ cursor: "pointer" }} onClick={() => loadVersions(h.host)}>
                    <td><strong>{h.host}</strong><br/><span className="muted">{h.full_name}</span></td>
                    <td className="muted">{formatDate(h.last_backup)}</td>
                    <td>{formatBytes(h.size_bytes)}</td>
                    <td>{h.status === "success" ? "✅" : "❌"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="hub-card">
          <h3>📋 Versions {selectedHost && `(${selectedHost})`}</h3>
          {!selectedHost ? (
            <p className="muted">Sélectionnez un hôte pour voir ses versions.</p>
          ) : loading ? (
            <p className="muted">Chargement…</p>
          ) : (
            <>
              <table style={{ width: "100%" }}>
                <thead><tr><th>#</th><th>Type</th><th>Date</th><th>Taille</th><th></th></tr></thead>
                <tbody>
                  {versions.map((v) => (
                    <tr key={v.num}>
                      <td>{v.num}</td>
                      <td>{v.type}</td>
                      <td className="muted">{formatDate(v.start_time)}</td>
                      <td>{formatBytes(v.size_bytes)}</td>
                      <td><button className="secondary" onClick={() => loadContent(selectedHost, v.num)}>📁</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {content && content.tree && (
                <div style={{ marginTop: 16 }}>
                  <h4>Contenu de la sauvegarde</h4>
                  <ul>
                    {content.tree.map((item, i) => (
                      <li key={i}><strong>{item.name}</strong> {item.type === "dir" ? "📁" : "📄"} {item.size_bytes && `(${formatBytes(item.size_bytes)})`}</li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// --- Sous-vue Clonezilla ---
function ClonezillaView({ apiBase }) {
  const [images, setImages] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [pxeConfig, setPxeConfig] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function loadImages() {
    try {
      const res = await fetch(`${apiBase}/clonezilla/images`);
      const data = await res.json();
      setImages(data.images || []);
    } catch (err) {
      setError(`Erreur images: ${err.message}`);
    }
  }

  async function loadJobs() {
    try {
      const res = await fetch(`${apiBase}/clonezilla/jobs`);
      const data = await res.json();
      setJobs(data.jobs || []);
    } catch (err) {
      setError(`Erreur jobs: ${err.message}`);
    }
  }

  async function loadPxeConfig() {
    try {
      const res = await fetch(`${apiBase}/clonezilla/pxe-config`);
      setPxeConfig(await res.json());
    } catch (err) {
      // silencieux
    }
  }

  useEffect(() => {
    loadImages();
    loadJobs();
    loadPxeConfig();
  }, [apiBase]);

  return (
    <div>
      {error && <div className="hub-card" style={{ borderColor: "var(--danger)", marginBottom: 16 }}>⚠️ {error}</div>}

      {pxeConfig && (
        <div className="hub-card" style={{ marginBottom: 16 }}>
          <h3>🌐 Configuration PXE</h3>
          <p><strong>Serveur:</strong> {pxeConfig.pxe_server || "—"}</p>
          <p><strong>Boot par défaut:</strong> {pxeConfig.next_boot_default || "—"}</p>
          {pxeConfig.clients && (
            <table style={{ width: "100%", marginTop: 8 }}>
              <thead><tr><th>MAC</th><th>Nom</th><th>Dernier boot</th></tr></thead>
              <tbody>
                {pxeConfig.clients.map((c) => (
                  <tr key={c.mac}><td className="muted">{c.mac}</td><td>{c.name}</td><td className="muted">{formatDate(c.last_boot)}</td></tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="hub-card">
          <h3>💾 Images Clonezilla</h3>
          <table style={{ width: "100%" }}>
            <thead><tr><th>Image</th><th>Périphérique</th><th>Date</th><th>Taille</th></tr></thead>
            <tbody>
              {images.map((img) => (
                <tr key={img.name}>
                  <td><strong>{img.name}</strong></td>
                  <td className="muted">{img.device}</td>
                  <td className="muted">{formatDate(img.created_at)}</td>
                  <td>{formatBytes(img.size_bytes)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="hub-card">
          <h3>⚙️ Jobs en cours</h3>
          {jobs.length === 0 ? <p className="muted">Aucun job actif.</p> : (
            <table style={{ width: "100%" }}>
              <thead><tr><th>ID</th><th>Type</th><th>Statut</th><th>Progression</th></tr></thead>
              <tbody>
                {jobs.map((j) => (
                  <tr key={j.id}>
                    <td className="muted">{j.id}</td>
                    <td>{j.type}</td>
                    <td>{j.status === "running" ? "🔄" : j.status === "completed" ? "✅" : "⏳"} {j.status}</td>
                    <td>{j.progress_percent != null ? `${j.progress_percent}%` : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </div>
  );
}

// --- Sous-vue Restic ---
function ResticView({ apiBase }) {
  const [snapshots, setSnapshots] = useState([]);
  const [stats, setStats] = useState(null);
  const [selectedSnapshot, setSelectedSnapshot] = useState(null);
  const [content, setContent] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  async function loadSnapshots() {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/restic/snapshots`);
      const data = await res.json();
      setSnapshots(data.snapshots || []);
    } catch (err) {
      setError(`Erreur snapshots: ${err.message}`);
    }
    setLoading(false);
  }

  async function loadStats() {
    try {
      const res = await fetch(`${apiBase}/restic/stats`);
      setStats(await res.json());
    } catch (err) {
      // silencieux
    }
  }

  async function loadContent(snapshotId) {
    setSelectedSnapshot(snapshotId);
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/restic/snapshots/${snapshotId}/content`);
      setContent(await res.json());
    } catch (err) {
      setError(`Erreur contenu: ${err.message}`);
    }
    setLoading(false);
  }

  useEffect(() => {
    loadSnapshots();
    loadStats();
  }, [apiBase]);

  return (
    <div>
      {error && <div className="hub-card" style={{ borderColor: "var(--danger)", marginBottom: 16 }}>⚠️ {error}</div>}

      {stats && (
        <div className="hub-card" style={{ marginBottom: 16 }}>
          <h3>📊 Statistiques du dépôt</h3>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(150px, 1fr))", gap: 12 }}>
            <div><strong>{formatBytes(stats.total_size)}</strong><br/><span className="muted">Taille totale</span></div>
            <div><strong>{stats.total_file_count?.toLocaleString("fr-FR")}</strong><br/><span className="muted">Fichiers</span></div>
            <div><strong>{stats.dedup_ratio?.toFixed(2)}x</strong><br/><span className="muted">Déduplication</span></div>
            <div><strong>{stats.snapshots_count}</strong><br/><span className="muted">Snapshots</span></div>
          </div>
        </div>
      )}

      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 16 }}>
        <div className="hub-card">
          <h3>📸 Snapshots</h3>
          {loading && !snapshots.length ? <p className="muted">Chargement…</p> : (
            <table style={{ width: "100%" }}>
              <thead><tr><th>ID</th><th>Date</th><th>Hôte</th><th>Tags</th><th></th></tr></thead>
              <tbody>
                {snapshots.map((s) => (
                  <tr key={s.id}>
                    <td className="muted">{s.short_id || s.id?.substring(0, 8)}</td>
                    <td className="muted">{formatDate(s.time)}</td>
                    <td>{s.hostname}</td>
                    <td className="muted">{(s.tags || []).join(", ")}</td>
                    <td><button className="secondary" onClick={() => loadContent(s.id)}>📁</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>

        <div className="hub-card">
          <h3>📁 Contenu {selectedSnapshot && `(${selectedSnapshot.substring(0, 8)}…)`}</h3>
          {!selectedSnapshot ? (
            <p className="muted">Sélectionnez un snapshot pour voir son contenu.</p>
          ) : loading ? (
            <p className="muted">Chargement…</p>
          ) : content && Array.isArray(content) ? (
            <ul>
              {content.map((item, i) => (
                <li key={i}>
                  <strong>{item.name}</strong> {item.type === "dir" ? "📁" : "📄"} {item.size_bytes && `(${formatBytes(item.size_bytes)})`}
                </li>
              ))}
            </ul>
          ) : (
            <p className="muted">Aucun contenu disponible.</p>
          )}
        </div>
      </div>
    </div>
  );
}

// --- Vue principale ---
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
    } else if (which === "images") {
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

  const tabs = [
    { id: "coverage", label: "Couverture" },
    { id: "images", label: "Images enregistrées" },
    { id: "backuppc", label: "BackupPC" },
    { id: "clonezilla", label: "Clonezilla" },
    { id: "restic", label: "Restic" },
  ];

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>💾 Sauvegardes -- couverture & connecteurs</h1>
      </div>

      <div className="hub-card">
        <p className="muted" style={{ margin: 0 }}>
          Suivi des images système, connecteurs BackupPC (hub + versions), Clonezilla (gestion automatisée),
          et Restic (sauvegarde cloud-ready avec déduplication). Les images sont enregistrées manuellement
          dans l'onglet "Images enregistrées" -- ceci ne déclenche AUCUNE capture réelle.
        </p>
      </div>

      {error && (
        <div className="hub-card" style={{ borderColor: "var(--danger)" }}>
          <p style={{ margin: 0 }}>⚠️ {error}</p>
        </div>
      )}

      <div className="hub-card hub-settings-section">
        <div className="tabs" style={{ marginBottom: 16, flexWrap: "wrap" }}>
          {tabs.map((t) => (
            <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
              {t.label}
            </button>
          ))}
        </div>

        {tab === "backuppc" && <BackupPCView apiBase={backupRestoreApiBase} />}
        {tab === "clonezilla" && <ClonezillaView apiBase={backupRestoreApiBase} />}
        {tab === "restic" && <ResticView apiBase={backupRestoreApiBase} />}

        {loading && (tab === "coverage" || tab === "images") && <p className="muted">Chargement…</p>}

        {tab === "coverage" && !loading && (
          !coverage ? (
            <p className="muted">Aucune donnée -- Exploration réseau est-elle bien déployée ?</p>
          ) : (
            <>
              <p>
                <strong>{coverage.without_backup}</strong> appareil(s) sur <strong>{coverage.total}</strong> sans image connue.
              </p>
              <table>
                <thead><tr><th></th><th>Adresse MAC</th><th>IP</th><th>Rôle</th><th>Dernière image</th><th>Depuis</th></tr></thead>
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
        )}

        {tab === "images" && !loading && (
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
                <thead><tr><th>Machine</th><th>MAC</th><th>Outil</th><th>Date</th><th>Emplacement</th><th></th></tr></thead>
                <tbody>
                  {images.map((img) => (
                    <tr key={img.id}>
                      <td>{img.device_label}</td>
                      <td className="muted">{img.device_mac || "—"}</td>
                      <td>{TOOL_LABELS[img.tool] || img.tool}</td>
                      <td className="muted">{img.taken_at}</td>
                      <td className="muted">{img.storage_path || "—"}</td>
                      <td><button className="secondary" disabled={busy} onClick={() => handleDelete(img.id)}>🗑</button></td>
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
