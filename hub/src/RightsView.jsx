import React, { useState, useEffect } from "react";
import { fetchFiles, fetchPermissions, grantPermission, revokePermission, fetchResourceTypes } from "./rightsClient.js";

// Tuile "Droits" (hub), livraison #283 -- demandé explicitement :
// "une gestion de droit incluant la visibilité en listing" + "un
// nouveau groupe admin_hub donnera les tous les droits à ses
// membres et notamment celui de gérer les droits" + "la gestion des
// droits devient une tuile". RÉSERVÉE au groupe admin_hub -- le
// contrôle d'accès à CETTE tuile elle-même se fait côté App.jsx
// (tuile non affichée si absent des groupes), mais TOUTE action de
// gestion (octroyer/révoquer) est de toute façon revérifiée
// côté rights-api lui-même (jamais une confiance aveugle en
// l'affichage -- un contournement du frontend ne donnerait aucun
// droit réel).
//
// Liste de groupes CONNUS à ce jour (voir keycloak/realm-template.json)
// -- statique, PAS récupérée dynamiquement depuis Keycloak (hors
// périmètre de cette première livraison) -- à garder synchronisée
// manuellement si de nouveaux groupes sont créés.
const KNOWN_GROUPS = [
  "administrateurs", "demandeurs", "techniciens", "direction",
  "supervision", "service", "maitre_clefs", "admin_hub",
];

const CATEGORY_LABELS = { configuration: "Configuration", genere: "Généré", secret: "Secret", importe: "Importé" };

export default function RightsView({ onBack, rightsApiBase, groups }) {
  const [tab, setTab] = useState("fichiers");
  const [files, setFiles] = useState([]);
  const [loadingFiles, setLoadingFiles] = useState(true);
  const [permissions, setPermissions] = useState([]);
  const [loadingPerms, setLoadingPerms] = useState(true);
  const [resourceTypes, setResourceTypes] = useState([]);
  const [busy, setBusy] = useState(false);
  const [grantForm, setGrantForm] = useState({ resourceType: "hub-file", resourceId: "", groupName: "techniciens", action: "view" });

  useEffect(() => {
    loadFiles();
    loadPermissions();
    fetchResourceTypes(rightsApiBase).then(setResourceTypes);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rightsApiBase]);

  async function loadFiles() {
    setLoadingFiles(true);
    const result = await fetchFiles(rightsApiBase, groups);
    setFiles(Array.isArray(result.files) ? result.files : []);
    setLoadingFiles(false);
  }

  async function loadPermissions() {
    setLoadingPerms(true);
    setPermissions(await fetchPermissions(rightsApiBase));
    setLoadingPerms(false);
  }

  async function handleGrant(e) {
    e.preventDefault();
    setBusy(true);
    const result = await grantPermission(rightsApiBase, groups, grantForm);
    setBusy(false);
    if (!result.error) {
      setGrantForm({ ...grantForm, resourceId: "" });
      await loadPermissions();
    }
  }

  async function handleRevoke(permissionId) {
    setBusy(true);
    await revokePermission(rightsApiBase, groups, permissionId);
    setBusy(false);
    await loadPermissions();
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>🔐 Droits</h1>
      </div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button className={tab === "fichiers" ? "" : "secondary"} onClick={() => setTab("fichiers")}>📁 Fichiers</button>
        <button className={tab === "permissions" ? "" : "secondary"} onClick={() => setTab("permissions")}>🔑 Permissions</button>
      </div>

      {tab === "fichiers" ? (
        <div className="hub-card">
          <p className="muted" style={{ marginTop: 0 }}>
            Inventaire des fichiers importés, de configuration, générés ou secrets du hub — jamais leur
            contenu, seulement chemin/taille/date. Visibilité filtrée selon vos droits (admin_hub voit tout).
          </p>
          {loadingFiles ? (
            <p className="muted">Chargement…</p>
          ) : files.length === 0 ? (
            <p className="muted">Aucun fichier visible.</p>
          ) : (
            <table>
              <thead><tr><th>Chemin</th><th>Catégorie</th><th>Taille</th><th>Modifié</th><th>Présent</th></tr></thead>
              <tbody>
                {files.map((f) => (
                  <tr key={f.identifier}>
                    <td>{f.identifier}</td>
                    <td className="muted">{CATEGORY_LABELS[f.category] || f.category}</td>
                    <td className="muted">{f.size != null ? `${f.size} o` : "—"}</td>
                    <td className="muted">{f.mtime || "—"}</td>
                    <td>{f.exists ? "✅" : "—"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      ) : (
        <div className="hub-card">
          <h2 style={{ marginTop: 0 }}>Octroyer un droit</h2>
          <form onSubmit={handleGrant} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Type de ressource</label>
              <input value={grantForm.resourceType} onChange={(e) => setGrantForm({ ...grantForm, resourceType: e.target.value })} list="rights-resource-types" />
              <datalist id="rights-resource-types">
                {resourceTypes.map((t) => <option key={t} value={t} />)}
              </datalist>
            </div>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Identifiant précis (vide = tout le type)</label>
              <input value={grantForm.resourceId} onChange={(e) => setGrantForm({ ...grantForm, resourceId: e.target.value })} placeholder="ex. .env" />
            </div>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Groupe</label>
              <select value={grantForm.groupName} onChange={(e) => setGrantForm({ ...grantForm, groupName: e.target.value })}>
                {KNOWN_GROUPS.map((g) => <option key={g} value={g}>{g}</option>)}
              </select>
            </div>
            <div className="hub-settings-row" style={{ margin: 0 }}>
              <label>Action</label>
              <select value={grantForm.action} onChange={(e) => setGrantForm({ ...grantForm, action: e.target.value })}>
                <option value="view">view</option>
                <option value="manage">manage</option>
              </select>
            </div>
            <button type="submit" disabled={busy}>Octroyer</button>
          </form>

          <h2>Droits actuels</h2>
          {loadingPerms ? (
            <p className="muted">Chargement…</p>
          ) : permissions.length === 0 ? (
            <p className="muted">Aucun droit octroyé pour l'instant (admin_hub voit tout indépendamment de cette liste).</p>
          ) : (
            <table>
              <thead><tr><th>Type</th><th>Ressource</th><th>Groupe</th><th>Action</th><th>Octroyé par</th><th></th></tr></thead>
              <tbody>
                {permissions.map((p) => (
                  <tr key={p.id}>
                    <td>{p.resource_type}</td>
                    <td className="muted">{p.resource_id || "(tout le type)"}</td>
                    <td>{p.group_name}</td>
                    <td className="muted">{p.action}</td>
                    <td className="muted">{p.granted_by}</td>
                    <td><button className="secondary" disabled={busy} onClick={() => handleRevoke(p.id)}>🗑</button></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
