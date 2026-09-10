import React, { useState, useEffect } from "react";
import {
  fetchInventorySummary, IMPORT_SOURCES, previewImport, commitImport,
  fetchItemsOfType, deleteItem, fetchAgentsComparison,
} from "./glpiClient.js";
import { fetchSites } from "./networkAgentClient.js";
import { COMPARISON_LABELS, previewRows, dropdownsLabel, describeSiAgent, describeGlpiAgent, importResultLine } from "./glpiImport.js";

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
  "si-agent-hosts": "Agents hôtes — serveurs et postes (si-agent)",
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
  // #437 : hôtes si-agent déjà dans GLPI -> mis à jour plutôt qu'ignorés.
  const [updateExisting, setUpdateExisting] = useState(false);

  // --- Agents GLPI <-> agents hôtes (#437) ---
  const [comparison, setComparison] = useState(null);
  const [comparing, setComparing] = useState(false);

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
    const result = await previewImport(glpiApiBase, source, segmentIdParam, { updateExisting });
    setPreviewing(false);
    if (result.error) {
      setError(result.error);
      setPreview(null);
      return;
    }
    setError(null);
    setPreview(result);
    // Tout coché par défaut -- la personne décoche ce qu'elle ne veut pas.
    // Les mises à jour (#437, aperçu `updated` objets) sont des candidats aussi.
    setSelectedKeys(new Set(previewRows(result).map((c) => c.key)));
  }

  async function handleCompare() {
    setComparing(true);
    const result = await fetchAgentsComparison(glpiApiBase);
    setComparing(false);
    if (result.error) setError(result.error);
    else setComparison(result);
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
    const result = await commitImport(glpiApiBase, source, Array.from(selectedKeys), segmentIdParam, { updateExisting });
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
          {source === "si-agent-hosts" && (
            <label style={{ display: "flex", alignItems: "center", gap: 6, margin: 0, paddingBottom: 6 }}>
              <input type="checkbox" checked={updateExisting} onChange={(e) => { setUpdateExisting(e.target.checked); setPreview(null); }} />
              mettre à jour les hôtes déjà dans GLPI
            </label>
          )}
          <button onClick={handlePreview} disabled={previewing}>
            {previewing ? "Chargement…" : "Prévisualiser"}
          </button>
        </div>
        {source === "si-agent-hosts" && (
          <p className="muted" style={{ marginTop: -4 }}>
            Chaque agent hôte devient un <code>Computer</code> : nom, numéro de série, fabricant / modèle / lieu
            (listes GLPI créées au besoin), OS, CPU, mémoire, disques, interfaces et dernière IP en commentaire.
            Dédoublonnage par l'identifiant d'agent, le numéro de série puis le nom.
          </p>
        )}

        {source === "network-agent-devices" && !selectedSegmentId && (
          <p style={{ color: "var(--warning, #b7791f)" }}>
            ⚠️ Aucun segment choisi -- tous les segments seront mélangés (ex. le réseau de votre
            structure ET celui d'un client comme Alpha). Choisissez un segment précis pour éviter ça.
          </p>
        )}

        {importResult && (
          <p className="muted">{importResultLine(importResult)}</p>
        )}

        {preview && (
          <>
            {previewRows(preview).length === 0 ? (
              <p className="muted">Aucun candidat à importer pour cette source.</p>
            ) : (
              <div style={{ maxHeight: 320, overflowY: "auto", marginBottom: 12 }}>
                <table>
                  <thead><tr><th></th><th>Nom</th><th>Type GLPI</th><th>Action</th>{source === "si-agent-hosts" && <th>Fabricant / modèle / lieu</th>}</tr></thead>
                  <tbody>
                    {previewRows(preview).map((c) => (
                      <tr key={c.key}>
                        <td><input type="checkbox" checked={selectedKeys.has(c.key)} onChange={() => toggleKey(c.key)} /></td>
                        <td title={c.detail}>{c.name}</td>
                        <td className="muted">{c.itemtype}</td>
                        <td className="muted">{c.action}</td>
                        {source === "si-agent-hosts" && (
                          <td className="muted">{dropdownsLabel(c)}</td>
                        )}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            {preview.warnings?.length > 0 && (
              <p style={{ color: "var(--warning, #b7791f)" }}>⚠️ {preview.warnings.join(" ; ")}</p>
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
        <h2>Agents GLPI ↔ agents hôtes</h2>
        <p className="muted" style={{ marginTop: -4 }}>
          Les agents que GLPI connaît (GLPI Agent, inventaire natif GLPI 10) rapprochés de la flotte
          si-agent par nom d'hôte : ce qui est vu des deux côtés, ce que seul si-agent voit (à importer
          ci-dessus), ce que seul GLPI Agent voit (candidats à un agent hôte).
        </p>
        <button onClick={handleCompare} disabled={comparing}>{comparing ? "Chargement…" : "Comparer"}</button>
        {comparison && (
          <div style={{ marginTop: 12 }}>
            <p className="muted">
              {comparison.glpi_agent_count} agent(s) GLPI, {comparison.si_agent_count} agent(s) si-agent —{" "}
              {comparison.counts?.both || 0} {COMPARISON_LABELS.both}, {comparison.counts?.only_si || 0} {COMPARISON_LABELS.only_si},{" "}
              {comparison.counts?.only_glpi || 0} {COMPARISON_LABELS.only_glpi}.
            </p>
            {comparison.glpi_error && <p style={{ color: "var(--warning, #b7791f)" }}>⚠️ GLPI : {comparison.glpi_error}</p>}
            {comparison.si_agent_error && <p style={{ color: "var(--warning, #b7791f)" }}>⚠️ si-agent : {comparison.si_agent_error}</p>}
            {(comparison.rows || []).length > 0 && (
              <div style={{ maxHeight: 320, overflowY: "auto" }}>
                <table>
                  <thead><tr><th>Hôte</th><th>Statut</th><th>si-agent</th><th>GLPI Agent</th></tr></thead>
                  <tbody>
                    {comparison.rows.map((r) => (
                      <tr key={r.hostname}>
                        <td>{r.hostname}</td>
                        <td className="muted">{COMPARISON_LABELS[r.status] || r.status}</td>
                        <td className="muted">{describeSiAgent(r.si)}</td>
                        <td className="muted">{describeGlpiAgent(r.glpi)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
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
