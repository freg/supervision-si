import React, { useState, useEffect } from "react";
import {
  fetchInventorySummary, IMPORT_SOURCES, previewImport, commitImport,
  fetchItemsOfType, deleteItem,
} from "./glpiClient.js";
import { fetchSites } from "./networkAgentClient.js";

// Onglet GLPI Inventory (hub), livraison #231 -- backlog item 21,
// enrichi en #269 suite à un audit explicite : "les données
// explorateur réseau et import nebula sont t'elles prêtes à être
// exportées vers glpi ? à partir des logs de nebula je peux exporter
// les clients connectés... pourra t'on les injecter dans glpi avec
// une interface de sélection multiple ? partout dans les imports/
// exports y a t'il la possibilité d'annuler ou de supprimer en
// sélectionnant individuellement ?".
//
// AVANT ce correctif, tous les imports (Excel/Nebula/SNMP/network-
// agent) n'étaient déclenchables que par appel API brut -- aucune
// interface hub. Corrigé ici : sélection de la SOURCE, aperçu avec
// case à cocher PAR CANDIDAT (sélection multiple), import de la
// sélection, et une section de gestion des actifs déjà créés avec
// suppression individuelle (corbeille GLPI native, PAS un mécanisme
// de undo maison -- voir glpi/README.md).

const SOURCE_LABELS = {
  "nebula-devices": "Nebula — équipements d'infrastructure",
  "nebula-clients": "Nebula — clients connectés",
  "network-agent-devices": "Exploration réseau — appareils découverts",
  "snmp-targets": "SNMP — cibles interrogées",
};
const MANAGED_ITEMTYPES = ["Computer", "NetworkEquipment"];

export default function GlpiInventoryView({ onBack, glpiApiBase, networkAgentApiBase }) {
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // --- Import avec sélection multiple ---
  const [source, setSource] = useState(IMPORT_SOURCES[0]);
  // Segments network-agent (livraison #269 correctif -- "network-agent-devices"
  // ne doit JAMAIS mélanger le réseau de la structure de la personne
  // et celui d'un client comme Alpha (172.x.x.x), même
  // raisonnement déjà appliqué côté architecture-api/vigilance-api).
  const [sites, setSites] = useState([]);
  const [selectedSegmentId, setSelectedSegmentId] = useState("");
  const [preview, setPreview] = useState(null);
  const [selectedKeys, setSelectedKeys] = useState(() => new Set());
  const [previewing, setPreviewing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importResult, setImportResult] = useState(null);

  // --- Gestion des actifs existants (annuler/supprimer) ---
  const [manageItemtype, setManageItemtype] = useState("Computer");
  const [existingItems, setExistingItems] = useState(null);
  const [managing, setManaging] = useState(false);

  useEffect(() => {
    setLoading(true);
    fetchInventorySummary(glpiApiBase).then((result) => {
      if (result.error) setError(result.error);
      else setSummary(result);
      setLoading(false);
    });
  }, [glpiApiBase]);

  useEffect(() => {
    if (networkAgentApiBase) fetchSites(networkAgentApiBase).then((s) => setSites(Array.isArray(s) ? s : []));
  }, [networkAgentApiBase]);

  async function handlePreview() {
    setPreviewing(true);
    setImportResult(null);
    const segmentIdParam = source === "network-agent-devices" && selectedSegmentId ? Number(selectedSegmentId) : undefined;
    const result = await previewImport(glpiApiBase, source, segmentIdParam);
    setPreviewing(false);
    if (result.error) {
      setError(result.error);
      setPreview(null);
      return;
    }
    setError(null);
    setPreview(result);
    // Tout coché par défaut -- la personne décoche ce qu'elle ne veut pas.
    setSelectedKeys(new Set((result.created || []).map((c) => c.key)));
  }

  function toggleKey(key) {
    setSelectedKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function handleImportSelection() {
    if (selectedKeys.size === 0) return;
    setImporting(true);
    const segmentIdParam = source === "network-agent-devices" && selectedSegmentId ? Number(selectedSegmentId) : undefined;
    const result = await commitImport(glpiApiBase, source, Array.from(selectedKeys), segmentIdParam);
    setImporting(false);
    if (result.error) setError(result.error);
    else {
      setImportResult(result);
      setPreview(null);
      setSelectedKeys(new Set());
    }
  }

  async function loadExistingItems(itemtype) {
    setManaging(true);
    setExistingItems(await fetchItemsOfType(glpiApiBase, itemtype));
    setManaging(false);
  }

  async function handleDelete(itemtype, itemId, name) {
    if (!window.confirm(`Déplacer "${name}" vers la corbeille GLPI ? (récupérable depuis GLPI lui-même, pas une suppression définitive)`)) return;
    setManaging(true);
    const result = await deleteItem(glpiApiBase, itemtype, itemId, false);
    setManaging(false);
    if (result.error) setError(result.error);
    else loadExistingItems(itemtype);
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🖥️ GLPI Inventory</h1>
      </div>

      {error && (
        <div className="hub-card" style={{ borderColor: "var(--danger)" }}>
          <p style={{ margin: 0 }}>⚠️ {error}</p>
        </div>
      )}

      {loading ? (
        <p className="muted">Chargement…</p>
      ) : summary && (
        <div className="hub-card hub-settings-section">
          <h2>Résumé</h2>
          <div style={{ display: "flex", gap: 24 }}>
            <p style={{ margin: 0 }}>
              Ordinateurs : <strong>{summary.computers.count}{summary.computers.capped ? "+" : ""}</strong>
            </p>
            <p style={{ margin: 0 }}>
              Équipements réseau : <strong>{summary.network_equipment.count}{summary.network_equipment.capped ? "+" : ""}</strong>
            </p>
          </div>
        </div>
      )}

      <div className="hub-card hub-settings-section">
        <h2>Importer vers GLPI</h2>
        <p className="muted" style={{ marginTop: -4 }}>
          Aperçu d'abord -- décochez ce que vous ne voulez pas importer, puis validez la sélection.
        </p>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 12 }}>
          <div className="hub-settings-row" style={{ margin: 0 }}>
            <label>Source</label>
            <select value={source} onChange={(e) => { setSource(e.target.value); setPreview(null); }}>
              {IMPORT_SOURCES.map((s) => <option key={s} value={s}>{SOURCE_LABELS[s] || s}</option>)}
            </select>
          </div>
          {source === "network-agent-devices" && (
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Segment réseau</label>
              <select value={selectedSegmentId} onChange={(e) => { setSelectedSegmentId(e.target.value); setPreview(null); }}>
                <option value="">— tous les segments (déconseillé) —</option>
                {sites.flatMap((site) => (site.segments || []).map((seg) => (
                  <option key={seg.id} value={seg.id}>{site.label ? `${site.label} — ` : ""}{seg.label}</option>
                )))}
              </select>
            </div>
          )}
          <button onClick={handlePreview} disabled={previewing}>
            {previewing ? "Chargement…" : "Prévisualiser"}
          </button>
        </div>

        {source === "network-agent-devices" && !selectedSegmentId && (
          <p style={{ color: "var(--warning, #b7791f)" }}>
            ⚠️ Aucun segment choisi -- tous les segments seront mélangés (ex. le réseau de votre
            structure ET celui d'un client comme Alpha). Choisissez un segment précis pour éviter ça.
          </p>
        )}

        {importResult && (
          <p className="muted">
            {importResult.created?.length || 0} créé(s), {importResult.skipped_existing?.length || 0} déjà présent(s),{" "}
            {importResult.skipped_unselected?.length || 0} non sélectionné(s), {importResult.errors?.length || 0} erreur(s).
          </p>
        )}

        {preview && (
          <>
            {(preview.created || []).length === 0 ? (
              <p className="muted">Aucun candidat à importer pour cette source.</p>
            ) : (
              <div style={{ maxHeight: 320, overflowY: "auto", marginBottom: 12 }}>
                <table>
                  <thead><tr><th></th><th>Nom</th><th>Type GLPI</th></tr></thead>
                  <tbody>
                    {preview.created.map((c) => (
                      <tr key={c.key}>
                        <td><input type="checkbox" checked={selectedKeys.has(c.key)} onChange={() => toggleKey(c.key)} /></td>
                        <td>{c.name}</td>
                        <td className="muted">{c.itemtype}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {preview.skipped_existing?.length > 0 && (
              <p className="muted">{preview.skipped_existing.length} déjà présent(s) dans GLPI (non ré-importé(s)).</p>
            )}
            {preview.errors?.length > 0 && (
              <p style={{ color: "var(--danger)" }}>{preview.errors.length} erreur(s) : {preview.errors.join(", ")}</p>
            )}
            <button onClick={handleImportSelection} disabled={importing || selectedKeys.size === 0}>
              {importing ? "Import en cours…" : `Importer la sélection (${selectedKeys.size})`}
            </button>
          </>
        )}
      </div>

      <div className="hub-card hub-settings-section">
        <h2>Actifs déjà créés -- annuler / supprimer individuellement</h2>
        <p className="muted" style={{ marginTop: -4 }}>
          Suppression = déplacement vers la corbeille GLPI native, récupérable depuis GLPI lui-même
          (jamais définitif ici).
        </p>
        <div style={{ display: "flex", gap: 8, alignItems: "flex-end", marginBottom: 12 }}>
          <div className="hub-settings-row" style={{ margin: 0 }}>
            <label>Type</label>
            <select value={manageItemtype} onChange={(e) => setManageItemtype(e.target.value)}>
              {MANAGED_ITEMTYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <button onClick={() => loadExistingItems(manageItemtype)} disabled={managing}>
            {managing ? "Chargement…" : "Charger"}
          </button>
        </div>
        {existingItems && (
          existingItems.length === 0 ? (
            <p className="muted">Aucun {manageItemtype} pour l'instant.</p>
          ) : (
            <div style={{ maxHeight: 320, overflowY: "auto" }}>
              <table>
                <thead><tr><th>Nom</th><th></th></tr></thead>
                <tbody>
                  {existingItems.map((item) => (
                    <tr key={item.id}>
                      <td>{item.name || `#${item.id}`}</td>
                      <td><button className="secondary" onClick={() => handleDelete(manageItemtype, item.id, item.name || `#${item.id}`)}>🗑 Annuler</button></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )
        )}
      </div>
    </div>
  );
}
