import React, { useState, useEffect } from "react";
import {
  fetchDocuments,
  uploadDocument,
  uploadNewVersion,
  deleteDocument,
  createLink,
  deleteLink,
  documentDownloadUrl,
} from "./gedClient.js";
import OwnCloudTreeView from "./OwnCloudTreeView.jsx";
import OwnCloudSearchView from "./OwnCloudSearchView.jsx";

// Onglet GED (hub), livraison #167 -- interface pour ged-api
// (#157-#166, jusqu'ici accessible seulement via curl ou depuis
// l'onglet Documents joints des tickets). Navigation/gestion
// GÉNÉRALE des documents -- pas limitée à un ticket en particulier,
// contrairement à TicketDocuments.jsx (tickets-portal, #160) --
// filtre optionnel par entité liée, sinon montre tous les documents
// CONNUS de ged-api (au moins une liaison enregistrée).
//
// Sous-onglets "OwnCloud"/"Recherche" ajoutés en #354 (demandé
// explicitement -- "vérifie bien que la tuile ged donne un accès
// séparé visuellement d'un coté à la ged externe et au dépôt
// interne, car par la ged externe on ne doit pas toucher aux
// fichiers internes") -- séparation VISUELLE délibérément appuyée
// (couleur de bordure distincte, bannière "lecture seule" permanente
// sur les deux onglets externes) plutôt qu'une simple différence de
// libellé : ged-api (Mayan, écriture -- upload/suppression/liaisons)
// et owncloud-api/owncloud-search-api (lecture seule, dépôt EXTERNE
// préexistant) ne partagent AUCUN état ni composant, seulement cet
// conteneur à onglets.

const EMPTY_UPLOAD_FORM = { name: "", linkedType: "", linkedId: "" };
const EMPTY_LINK_FORM = { linkedType: "", linkedId: "" };

export default function GedView({ onBack, gedApiBase, login, ticketsPortalUrl, ownCloudApiBase, ownCloudSearchApiBase, frontendUrl, onViewRelations }) {
  const [tab, setTab] = useState("interne");
  const [filterType, setFilterType] = useState("");
  const [filterId, setFilterId] = useState("");
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(false);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);
  // Indicateur visuel "action EN COURS" (livraison #209, extension de
  // l'item 18 du backlog -- diode orange déjà en place sur
  // ssh-tunnels, #197). `busy` reste global (désactive tous les
  // boutons) ; ces states-ci distinguent VISUELLEMENT laquelle action
  // précise est en cours -- un envoi de fichier peut prendre un
  // temps réel notable, contrairement aux autres actions de cet
  // écran.
  const [uploading, setUploading] = useState(false);
  const [uploadingVersionForId, setUploadingVersionForId] = useState(null);
  const [expanded, setExpanded] = useState(() => new Set());
  const [uploadForm, setUploadForm] = useState(EMPTY_UPLOAD_FORM);
  const [uploadFile, setUploadFile] = useState(null);
  const [linkForms, setLinkForms] = useState({});

  async function load() {
    setLoading(true);
    const docs = await fetchDocuments(gedApiBase, filterType || undefined, filterId || undefined);
    setDocuments(docs);
    setLoading(false);
    setHasLoadedOnce(true);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  function toggleExpanded(docId) {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(docId)) next.delete(docId);
      else next.add(docId);
      return next;
    });
  }

  async function handleUpload(e) {
    e.preventDefault();
    if (!uploadFile) return;
    setUploading(true);
    setBusy(true);
    setError(null);
    const result = await uploadDocument(
      gedApiBase, uploadFile, uploadForm.name || undefined,
      uploadForm.linkedType || undefined, uploadForm.linkedId || undefined, login,
    );
    setUploading(false);
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setUploadForm(EMPTY_UPLOAD_FORM);
    setUploadFile(null);
    load();
  }

  async function handleNewVersion(documentId, e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    setUploadingVersionForId(documentId);
    setBusy(true);
    setError(null);
    const result = await uploadNewVersion(gedApiBase, documentId, file);
    setUploadingVersionForId(null);
    setBusy(false);
    e.target.value = "";
    if (result.error) {
      setError(result.error);
      return;
    }
    load();
  }

  async function handleDelete(documentId) {
    setBusy(true);
    setError(null);
    const result = await deleteDocument(gedApiBase, documentId);
    setBusy(false);
    if (result && result.error) {
      setError(result.error);
      return;
    }
    load();
  }

  function updateLinkForm(documentId, field, value) {
    setLinkForms((prev) => ({
      ...prev,
      [documentId]: { ...(prev[documentId] || EMPTY_LINK_FORM), [field]: value },
    }));
  }

  async function handleAddLink(documentId) {
    const form = linkForms[documentId] || EMPTY_LINK_FORM;
    if (!form.linkedType.trim() || !form.linkedId.trim()) return;
    setBusy(true);
    setError(null);
    const result = await createLink(gedApiBase, documentId, form.linkedType.trim(), form.linkedId.trim(), login);
    setBusy(false);
    if (result.error) {
      setError(result.error);
      return;
    }
    setLinkForms((prev) => ({ ...prev, [documentId]: EMPTY_LINK_FORM }));
    load();
  }

  async function handleDeleteLink(documentId, linkId) {
    setBusy(true);
    setError(null);
    await deleteLink(gedApiBase, documentId, linkId);
    setBusy(false);
    load();
  }

  return (
    <div className="hub-settings hub-settings-wide">
      <div className="hub-settings-topbar">
        <button className="secondary" onClick={onBack}>◀ Retour</button>
        <h1>📁 GED (documents)</h1>
      </div>

      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        <button className={tab === "interne" ? "" : "secondary"} onClick={() => setTab("interne")}>
          📁 Dépôt interne
        </button>
        <button
          className={tab === "owncloud" ? "" : "secondary"}
          onClick={() => setTab("owncloud")}
          style={tab === "owncloud" ? { borderColor: "var(--warning, #d97706)" } : undefined}
        >
          ☁️ OwnCloud (externe, lecture seule)
        </button>
        <button
          className={tab === "recherche" ? "" : "secondary"}
          onClick={() => setTab("recherche")}
          style={tab === "recherche" ? { borderColor: "var(--warning, #d97706)" } : undefined}
        >
          🔍 Recherche (Elasticsearch, lecture seule)
        </button>
      </div>

      {tab === "owncloud" && (
        <div
          className="hub-card"
          style={{ borderLeft: "4px solid var(--warning, #d97706)", marginBottom: 12, padding: "8px 12px" }}
        >
          🔒 <strong>Dépôt EXTERNE, lecture seule</strong> -- distinct du dépôt interne
          ci-dessus (ged-api/Mayan). Jamais les mêmes fichiers, jamais d'action d'écriture
          possible ici.
        </div>
      )}
      {tab === "owncloud" && <OwnCloudTreeView apiBase={ownCloudApiBase} frontendUrl={frontendUrl} />}

      {tab === "recherche" && (
        <div
          className="hub-card"
          style={{ borderLeft: "4px solid var(--warning, #d97706)", marginBottom: 12, padding: "8px 12px" }}
        >
          🔒 <strong>Index Elasticsearch EXTERNE, lecture seule</strong> -- alimenté par
          OwnCloud (application <code>search_elastic</code>), distinct du dépôt interne
          ci-dessus. Jamais d'action d'écriture possible ici.
        </div>
      )}
      {tab === "recherche" && <OwnCloudSearchView apiBase={ownCloudSearchApiBase} frontendUrl={frontendUrl} />}

      {tab === "interne" && (<>
      <div className="hub-card hub-settings-section">
        <h2>Envoyer un document</h2>
        <form onSubmit={handleUpload} style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="hub-settings-row">
            <label>Fichier</label>
            <input type="file" onChange={(e) => setUploadFile(e.target.files && e.target.files[0])} />
          </div>
          <div className="hub-settings-row">
            <label>Nom (optionnel)</label>
            <input value={uploadForm.name} onChange={(e) => setUploadForm({ ...uploadForm, name: e.target.value })} placeholder="repli : nom du fichier" />
          </div>
          <div className="hub-settings-row">
            <label>Type d'entité liée (optionnel)</label>
            <input value={uploadForm.linkedType} onChange={(e) => setUploadForm({ ...uploadForm, linkedType: e.target.value })} placeholder="ex. ticket" />
          </div>
          <div className="hub-settings-row">
            <label>Id de l'entité liée</label>
            <input value={uploadForm.linkedId} onChange={(e) => setUploadForm({ ...uploadForm, linkedId: e.target.value })} placeholder="ex. 42" />
          </div>
          <button type="submit" disabled={busy || !uploadFile}>{uploading ? "🟠 Envoi en cours…" : "Envoyer"}</button>
        </form>
        {error && <p className="hub-error">{error}</p>}
      </div>

      <div className="hub-card hub-settings-section">
        <h2>Filtrer par entité liée</h2>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "flex-end" }}>
          <div className="hub-settings-row">
            <label>Type</label>
            <input value={filterType} onChange={(e) => setFilterType(e.target.value)} placeholder="ex. ticket" />
          </div>
          <div className="hub-settings-row">
            <label>Id</label>
            <input value={filterId} onChange={(e) => setFilterId(e.target.value)} placeholder="ex. 42" />
          </div>
          <button onClick={load} disabled={loading}>{loading ? "Chargement…" : "Actualiser"}</button>
          {(filterType || filterId) && (
            <button className="secondary" onClick={() => { setFilterType(""); setFilterId(""); load(); }}>
              Retirer le filtre
            </button>
          )}
        </div>
      </div>

      <div className="hub-card hub-settings-section">
        <h2>Documents ({documents.length})</h2>
        {!hasLoadedOnce && <p className="muted">Chargement…</p>}
        {hasLoadedOnce && documents.length === 0 && (
          <p className="muted">Aucun document connu pour l'instant.</p>
        )}
        {documents.map((doc) => {
          const isOpen = expanded.has(doc.id);
          const versions = doc.versions || [];
          const links = doc.links || [];
          const linkForm = linkForms[doc.id] || EMPTY_LINK_FORM;
          return (
            <div key={doc.id} style={{ marginBottom: 12, borderBottom: "1px solid var(--border)", paddingBottom: 8 }}>
              <button className="secondary" onClick={() => toggleExpanded(doc.id)}>
                {isOpen ? "▾" : "▸"} {doc.name || `Document #${doc.id}`} ({versions.length} version{versions.length > 1 ? "s" : ""}, {links.length} liaison{links.length > 1 ? "s" : ""})
              </button>
              {onViewRelations && (
                <button className="secondary" title="Voir les relations" onClick={() => onViewRelations("document", doc.id)}>🔗</button>
              )}
              {isOpen && (
                <div style={{ marginTop: 8, marginLeft: 16 }}>
                  <p>
                    <a href={documentDownloadUrl(gedApiBase, doc.id, "latest")} target="_blank" rel="noreferrer">
                      Télécharger la dernière version
                    </a>
                  </p>

                  <h4>Versions</h4>
                  <ul>
                    {versions.map((v) => (
                      <li key={v.version_number}>
                        Version {v.version_number} —{" "}
                        <a href={documentDownloadUrl(gedApiBase, doc.id, v.version_number)} target="_blank" rel="noreferrer">
                          télécharger
                        </a>
                      </li>
                    ))}
                  </ul>
                  <label className="secondary" style={{ display: "inline-block", cursor: "pointer" }}>
                    <input type="file" style={{ display: "none" }} disabled={busy} onChange={(e) => handleNewVersion(doc.id, e)} />
                    <span className="secondary" style={{ border: "1px solid var(--border)", borderRadius: 4, padding: "4px 8px" }}>
                      {uploadingVersionForId === doc.id ? "🟠 Envoi en cours…" : "+ Nouvelle version"}
                    </span>
                  </label>

                  <h4>Liaisons</h4>
                  {links.length === 0 && <p className="muted">Aucune liaison.</p>}
                  <ul>
                    {links.map((l) => (
                      <li key={l.id}>
                        {l.linked_type === "ticket" && ticketsPortalUrl ? (
                          <a
                            href={`${ticketsPortalUrl}?ticket=${encodeURIComponent(l.linked_id)}`}
                            target="_blank"
                            rel="noreferrer"
                            title="Ouvrir la fiche du ticket (vue technicien si accessible, sinon vos propres tickets)"
                          >
                            {l.linked_type}#{l.linked_id}
                          </a>
                        ) : (
                          <span>{l.linked_type}#{l.linked_id}</span>
                        )}{" "}
                        <button className="secondary" disabled={busy} onClick={() => handleDeleteLink(doc.id, l.id)}>
                          Retirer
                        </button>
                      </li>
                    ))}
                  </ul>
                  <div style={{ display: "flex", gap: 8, alignItems: "flex-end" }}>
                    <div className="hub-settings-row">
                      <label>Type</label>
                      <input value={linkForm.linkedType} onChange={(e) => updateLinkForm(doc.id, "linkedType", e.target.value)} placeholder="ex. ticket" />
                    </div>
                    <div className="hub-settings-row">
                      <label>Id</label>
                      <input value={linkForm.linkedId} onChange={(e) => updateLinkForm(doc.id, "linkedId", e.target.value)} placeholder="ex. 42" />
                    </div>
                    <button disabled={busy} onClick={() => handleAddLink(doc.id)}>Lier</button>
                  </div>

                  <p style={{ marginTop: 8 }}>
                    <button className="secondary" disabled={busy} onClick={() => handleDelete(doc.id)}>
                      🗑 Supprimer ce document
                    </button>
                  </p>
                </div>
              )}
            </div>
          );
        })}
      </div>
      </>)}
    </div>
  );
}
