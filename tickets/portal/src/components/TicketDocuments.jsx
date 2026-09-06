import React, { useEffect, useState, useRef } from "react";
import {
  fetchTicketDocuments,
  uploadTicketDocument,
  uploadNewVersion,
  deleteTicketDocument,
  documentDownloadUrl,
} from "../gedApi.js";

// Documents joints à un ticket (livraison #160) -- même motif
// autonome que TicketThread.jsx : reçoit juste `ticketId`/`me`,
// gère son propre chargement, se branche à côté du fil de
// discussion dans les 4 vues (Demandeur/Technicien/Politique/Admin).
// S'appuie sur ged-api (gedApi.js) -- "Documents joints" utilise
// linked_type="ticket" (voir ged/README.md, table de liaison
// polymorphe), jamais une table dédiée côté tickets-api.
export default function TicketDocuments({ ticketId, me }) {
  const [documents, setDocuments] = useState([]);
  const [hasLoadedOnce, setHasLoadedOnce] = useState(false);
  const [error, setError] = useState(null);
  const [uploading, setUploading] = useState(false);
  const fileInputRef = useRef(null);
  const versionInputRefs = useRef({});

  const load = async () => {
    const docs = await fetchTicketDocuments(ticketId);
    setDocuments(docs);
    setHasLoadedOnce(true);
  };

  useEffect(() => {
    setHasLoadedOnce(false);
    setDocuments([]);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ticketId]);

  async function handleUpload(e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    const result = await uploadTicketDocument(ticketId, file, me?.login);
    setUploading(false);
    if (fileInputRef.current) fileInputRef.current.value = "";
    if (result.error) {
      setError(result.error);
      return;
    }
    load();
  }

  async function handleNewVersion(documentId, e) {
    const file = e.target.files && e.target.files[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    const result = await uploadNewVersion(documentId, file);
    setUploading(false);
    if (versionInputRefs.current[documentId]) versionInputRefs.current[documentId].value = "";
    if (result.error) {
      setError(result.error);
      return;
    }
    load();
  }

  async function handleDelete(documentId) {
    setError(null);
    const result = await deleteTicketDocument(documentId);
    if (result && result.error) {
      setError(result.error);
      return;
    }
    load();
  }

  return (
    <div className="ticket-documents">
      <h3>📎 Documents joints</h3>
      {!hasLoadedOnce && <p className="muted">Chargement…</p>}
      {hasLoadedOnce && documents.length === 0 && (
        <p className="muted">Aucun document joint pour l'instant.</p>
      )}
      {documents.length > 0 && (
        <ul className="ticket-documents-list">
          {documents.map((doc) => (
            <li key={doc.id}>
              <a href={documentDownloadUrl(doc.id, "latest")} target="_blank" rel="noreferrer">
                {doc.name || `Document #${doc.id}`}
              </a>
              <span className="muted">
                {" "}
                ({doc.versions ? doc.versions.length : 0} version{doc.versions && doc.versions.length > 1 ? "s" : ""})
              </span>
              <label className="ticket-documents-version-add">
                <input
                  type="file"
                  ref={(el) => { versionInputRefs.current[doc.id] = el; }}
                  onChange={(e) => handleNewVersion(doc.id, e)}
                  disabled={uploading}
                  style={{ display: "none" }}
                />
                <button type="button" className="secondary" disabled={uploading} onClick={() => versionInputRefs.current[doc.id]?.click()}>
                  + Nouvelle version
                </button>
              </label>
              <button type="button" className="secondary" onClick={() => handleDelete(doc.id)} title="Retirer ce document du ticket">
                🗑
              </button>
            </li>
          ))}
        </ul>
      )}
      {error && <p className="error-text">{error}</p>}
      <div className="ticket-documents-upload">
        <input
          type="file"
          ref={fileInputRef}
          onChange={handleUpload}
          disabled={uploading}
        />
        {uploading && <span className="muted"> Envoi en cours…</span>}
      </div>
    </div>
  );
}
