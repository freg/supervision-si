import React, { useEffect, useState } from "react";
import { useAuth } from "react-oidc-context";
import {
  createVaultAccount, checkAccountExists, unlockWithPassword, unlockWithRecoveryKey,
  createCollection, grantAccess, unlockCollectionKey, createSecret, decryptSecret,
  changePassword, recordSecretAccess, updateSecretWithHistory, fetchSecretHistory,
  addSecretObservation, fetchSecretObservations, fetchTemplates, createTemplate,
  backfillSystemMasterAccess, archiveSecret, restoreSecret, fetchArchivedSecrets,
  fetchSecretVersions, restoreSecretVersion,
} from "./vaultOps.js";
import { serializeFields, parseFields, isSimpleSingleField, orderFieldsRequiredFirst } from "./vaultFieldsLib.js";
import { getJson } from "./api.js";
import { createAccountThemeStore } from "./preferences.js";
import versionInfo from "./VERSION.json";
import VaultSearchScreen, { revealSecretValue } from "./VaultSearchScreen.jsx";
import DashboardScreen from "./DashboardScreen.jsx";
import ObservationsScreen from "./ObservationsScreen.jsx";
import LocationPicker from "./LocationPicker.jsx";
import CopyableValue from "./CopyableValue.jsx";
import FieldsEditor from "./FieldsEditor.jsx";

// Coffre = identité Keycloak connue (contrairement à DBA/Supervision
// SI) -- préférences liées au compte, même mécanisme que hub/portail
// tickets, pas local au navigateur.
const PREFS_API_BASE_URL = import.meta.env.VITE_PREFS_API_BASE_URL || "";
const themeStore = createAccountThemeStore({ apiBase: PREFS_API_BASE_URL });

// --- Écran : créer un compte coffre (première visite) ---
function CreateAccountScreen({ login, onCreated }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // Une fois la création réussie : la clé de récupération EN CLAIR,
  // affichée UNE SEULE FOIS (jamais retrouvable après ce point) --
  // état SÉPARÉ du reste du formulaire, jamais réinitialisé par erreur.
  const [recoveryKey, setRecoveryKey] = useState(null);
  const [savedConfirmed, setSavedConfirmed] = useState(false);
  const [pendingPrivateKey, setPendingPrivateKey] = useState(null);

  async function handleCreate() {
    setError(null);
    if (password.length < 12) {
      setError("Le mot de passe maître doit faire au moins 12 caractères — c'est la SEULE protection de tout ce que vous y mettrez.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setBusy(true);
    const result = await createVaultAccount(login, password);
    setBusy(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setRecoveryKey(result.recoveryKey);
    setPendingPrivateKey(result.privateKey);
  }

  if (recoveryKey) {
    return (
      <div className="vault-card">
        <h2>🔑 Votre clé de récupération</h2>
        <p className="vault-warning">
          Cette clé ne sera plus JAMAIS affichée. Si vous oubliez votre
          mot de passe maître, c'est la SEULE façon de récupérer l'accès
          à ce coffre — imprimez-la ou conservez-la en lieu sûr,
          physiquement séparée de votre mot de passe.
        </p>
        <pre className="vault-recovery-key">{recoveryKey}</pre>
        <label className="vault-checkbox-row">
          <input type="checkbox" checked={savedConfirmed} onChange={(e) => setSavedConfirmed(e.target.checked)} />
          J'ai conservé cette clé en lieu sûr
        </label>
        <button className="primary" disabled={!savedConfirmed} onClick={() => onCreated(pendingPrivateKey)}>
          Continuer vers le coffre
        </button>
      </div>
    );
  }

  return (
    <div className="vault-card">
      <h2>🔐 Créer votre coffre</h2>
      <p className="vault-muted">
        Connecté en tant que <strong>{login}</strong>. Choisissez un mot
        de passe maître — il ne quitte jamais votre navigateur, personne
        (pas même un administrateur) ne peut le récupérer si vous
        l'oubliez.
      </p>
      <input
        type="password"
        placeholder="mot de passe maître (12 caractères min.)"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
      />
      <input
        type="password"
        placeholder="confirmer le mot de passe"
        value={confirmPassword}
        onChange={(e) => setConfirmPassword(e.target.value)}
        onKeyDown={(e) => e.key === "Enter" && handleCreate()}
      />
      {error && <p className="vault-error">{error}</p>}
      <button className="primary" onClick={handleCreate} disabled={busy}>
        {busy ? "Création…" : "Créer mon coffre"}
      </button>
    </div>
  );
}

// --- Écran : déverrouiller un compte existant ---
function UnlockScreen({ login, onUnlocked }) {
  const [password, setPassword] = useState("");
  const [recoveryKey, setRecoveryKey] = useState("");
  const [useRecovery, setUseRecovery] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  async function handleUnlock() {
    setError(null);
    setBusy(true);
    const result = useRecovery
      ? await unlockWithRecoveryKey(login, recoveryKey.trim())
      : await unlockWithPassword(login, password);
    setBusy(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    onUnlocked(result.privateKey);
  }

  return (
    <div className="vault-card">
      <h2>🔒 Coffre verrouillé</h2>
      <p className="vault-muted">Connecté en tant que <strong>{login}</strong>.</p>
      {!useRecovery ? (
        <input
          type="password"
          placeholder="mot de passe maître"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleUnlock()}
        />
      ) : (
        <input
          type="text"
          placeholder="clé de récupération"
          value={recoveryKey}
          onChange={(e) => setRecoveryKey(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleUnlock()}
        />
      )}
      {error && <p className="vault-error">{error}</p>}
      <button className="primary" onClick={handleUnlock} disabled={busy}>
        {busy ? "Déverrouillage…" : "Déverrouiller"}
      </button>
      <button className="vault-link-btn" onClick={() => { setUseRecovery((v) => !v); setError(null); }}>
        {useRecovery ? "Utiliser le mot de passe à la place" : "Mot de passe oublié ? Utiliser la clé de récupération"}
      </button>
    </div>
  );
}

// --- Une collection ouverte : ses secrets, ajout, gestion d'accès ---
/** Éditeur de champs multiples (libellé/contenu) -- utilisé pour
 * créer ET éditer un secret, un seul composant pour les deux (même
 * comportement voulu, jamais deux implémentations qui divergent avec
 * le temps). Toujours au moins un champ affiché -- une liste vide
 * n'aurait aucun sens pour un secret.
 *
 * `templates`/`onUseTemplate`/`onSaveAsTemplate` optionnels -- permet
 * de préremplir les libellés depuis un modèle existant (ex. "Carte
 * SIM" -> PUK/PIN/Numéro), ou d'enregistrer la structure ACTUELLE
 * (libellés seulement, jamais le contenu) comme nouveau modèle
 * réutilisable. */
/** Affichage en lecture d'une valeur déjà déchiffrée -- un seul champ
 * sans libellé (cas "simple", comme avant ce chantier) affiche juste
 * le contenu ; plusieurs champs (ou un libellé explicite) affichent
 * un tableau à 2 colonnes (Libellé/Contenu) -- backlog #1, demandé
 * explicitement plutôt que la présentation en lignes empilées
 * précédente. Chaque contenu passe par CopyableValue -- survol pour
 * copier, sélection native toujours possible, liste de mots pour une
 * copie partielle (demandé explicitement). */
function FieldsDisplay({ decryptedValue }) {
  const fields = parseFields(decryptedValue);
  if (isSimpleSingleField(fields)) {
    return <CopyableValue value={fields[0].content} />;
  }
  return (
    <table className="vault-fields-display-table">
      <thead>
        <tr><th>Libellé</th><th>Contenu</th></tr>
      </thead>
      <tbody>
        {fields.map((f, i) => (
          <tr key={i}>
            <td>{f.label || "—"}</td>
            <td><CopyableValue value={f.content} /></td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function CollectionDetail({ collection, collectionKey, login, isReadOnly }) {
  const [secrets, setSecrets] = useState([]);
  const [decrypted, setDecrypted] = useState({}); // { [secretId]: {label, value, keyword} }
  const [revealed, setRevealed] = useState({}); // { [secretId]: bool } -- valeur cachée par défaut
  const [loading, setLoading] = useState(true);
  const [newLabel, setNewLabel] = useState("");
  // Formulaire d'ajout de secret replié par défaut -- ouvert via le
  // bouton "+" à côté de "Secrets (n)", même motif que
  // showCreateCollectionForm (écran Collections).
  const [showAddSecretForm, setShowAddSecretForm] = useState(false);
  const [newFields, setNewFields] = useState([{ label: "", content: "" }]);
  const [newLocalisation, setNewLocalisation] = useState("");
  const [newKeyword, setNewKeyword] = useState("");
  const [newTemplateId, setNewTemplateId] = useState(null);
  // Libellés obligatoires du format (modèle) actuellement appliqué --
  // backlog coffre-fort #2, INDICATIF seulement (jamais bloquant à
  // l'enregistrement, voir FieldsEditor.jsx). Distinct de
  // newTemplateId : reste utile même si le modèle est ensuite modifié
  // (les champs déjà pré-remplis gardent leur marqueur).
  const [newRequiredLabels, setNewRequiredLabels] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [error, setError] = useState(null);
  const [accessList, setAccessList] = useState([]);
  const [grantLogin, setGrantLogin] = useState("");
  const [grantBusy, setGrantBusy] = useState(false);
  const [grantError, setGrantError] = useState(null);

  // Édition -- un seul secret modifiable à la fois (évite de gérer N
  // formulaires ouverts en parallèle). motif SÉPARÉ des autres champs,
  // jamais pré-rempli (jamais recopier un motif d'une fois sur
  // l'autre par erreur).
  const [editingId, setEditingId] = useState(null);
  const [editLabel, setEditLabel] = useState("");
  const [editFields, setEditFields] = useState([{ label: "", content: "" }]);
  const [editLocalisation, setEditLocalisation] = useState("");
  const [editKeyword, setEditKeyword] = useState("");
  const [editTemplateId, setEditTemplateId] = useState(null);
  const [editRequiredLabels, setEditRequiredLabels] = useState([]);
  const [editReason, setEditReason] = useState("");
  const [editBusy, setEditBusy] = useState(false);
  const [editError, setEditError] = useState(null);

  // Historique -- affiché à la demande, un secret à la fois (même
  // logique que l'édition, jamais tout charger d'avance).
  const [historyId, setHistoryId] = useState(null);
  const [historyEntries, setHistoryEntries] = useState([]);

  // Observations -- même principe (à la demande, un secret à la fois),
  // jamais ouvertes en même temps que l'édition ou l'historique (une
  // seule zone dépliée par secret, plus lisible).
  const [observationsId, setObservationsId] = useState(null);
  const [observationEntries, setObservationEntries] = useState([]);
  const [newObservationText, setNewObservationText] = useState("");
  const [observationBusy, setObservationBusy] = useState(false);

  // Versions/retour en arrière -- même principe (un secret à la fois).
  const [versionsId, setVersionsId] = useState(null);
  const [versionEntries, setVersionEntries] = useState([]);
  const [versionRestoreBusy, setVersionRestoreBusy] = useState(null); // id de la version en cours de restauration
  const [versionRestoreError, setVersionRestoreError] = useState(null);

  // Archivage -- confirmation avec motif optionnel, un secret à la fois.
  const [archivingId, setArchivingId] = useState(null);
  const [archiveReason, setArchiveReason] = useState("");
  const [archiveBusy, setArchiveBusy] = useState(false);

  // Vue des archives -- repliée par défaut, chargée à la demande
  // seulement (visible à TOUS les membres de la collection, demandé
  // explicitement -- pas juste au propriétaire).
  const [showArchived, setShowArchived] = useState(false);
  const [archivedSecrets, setArchivedSecrets] = useState([]);
  const [archivedDecrypted, setArchivedDecrypted] = useState({});
  const [restoreBusy, setRestoreBusy] = useState(null);
  const [restoreError, setRestoreError] = useState(null);

  async function loadSecrets() {
    setLoading(true);
    const res = await getJson(`/collections/${collection.id}/secrets`);
    if (res.ok) {
      setSecrets(res.data);
      // Déchiffre les LIBELLÉS et MOTS-CLÉS immédiatement (utiles
      // pour la liste elle-même, pas sensibles comme la valeur) --
      // jamais les VALEURS, qui restent cachées tant que la personne
      // ne clique pas explicitement sur "révéler".
      const labels = {};
      for (const s of res.data) {
        try {
          const { label, keyword } = await decryptSecret(s, collectionKey);
          labels[s.id] = { label, keyword, value: null };
        } catch {
          labels[s.id] = { label: "(déchiffrement impossible)", keyword: "", value: null };
        }
      }
      setDecrypted(labels);
    }
    setLoading(false);
  }

  useEffect(() => {
    loadSecrets();
    getJson(`/collections/${collection.id}/access`).then((r) => r.ok && setAccessList(r.data));
    fetchTemplates(collection.id).then(setTemplates);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [collection.id]);

  function applyTemplateToNewFields(templateId) {
    const t = templates.find((tpl) => tpl.id === templateId);
    if (!t) return;
    const required = t.required_labels || [];
    setNewFields(orderFieldsRequiredFirst(t.field_labels.map((label) => ({ label, content: "" })), required));
    setNewTemplateId(templateId);
    setNewRequiredLabels(required);
  }

  function applyTemplateToEditFields(templateId) {
    const t = templates.find((tpl) => tpl.id === templateId);
    if (!t) return;
    const required = t.required_labels || [];
    setEditFields(orderFieldsRequiredFirst(t.field_labels.map((label) => ({ label, content: "" })), required));
    setEditTemplateId(templateId);
    setEditRequiredLabels(required);
  }

  async function handleSaveAsTemplate(name, fields, { requiredLabels, scope } = {}) {
    const fieldLabels = fields.map((f) => f.label.trim()).filter(Boolean);
    if (fieldLabels.length === 0) return; // aucun libellé -- rien de reutilisable a enregistrer
    const res = await createTemplate(name, fieldLabels, login, {
      collectionId: scope === "collection" ? collection.id : undefined,
      requiredLabels,
    });
    if (res.ok) setTemplates(await fetchTemplates(collection.id));
  }

  async function handleReveal(secret) {
    if (revealed[secret.id]) {
      setRevealed((prev) => ({ ...prev, [secret.id]: false }));
      return;
    }
    try {
      const full = await decryptSecret(secret, collectionKey);
      setDecrypted((prev) => ({ ...prev, [secret.id]: full }));
      setRevealed((prev) => ({ ...prev, [secret.id]: true }));
      recordSecretAccess(secret.id); // jamais bloquant, voir vaultOps.js
    } catch {
      setError("Déchiffrement impossible pour ce secret.");
    }
  }

  async function handleAddSecret() {
    const hasContent = newFields.some((f) => f.content.trim());
    if (!newLabel.trim() || !hasContent) return;
    setError(null);
    const value = serializeFields(newFields);
    const res = await createSecret(collection.id, newLabel.trim(), value, collectionKey, login, {
      localisation: newLocalisation.trim() || undefined,
      keyword: newKeyword.trim() || undefined,
      templateId: newTemplateId || undefined,
      reason: "création initiale",
    });
    if (res.ok) {
      setNewLabel("");
      setNewFields([{ label: "", content: "" }]);
      setNewLocalisation("");
      setNewKeyword("");
      setNewTemplateId(null);
      setNewRequiredLabels([]);
      setShowAddSecretForm(false);
      loadSecrets();
    } else {
      setError(res.error);
    }
  }

  function startEditing(secret) {
    setEditingId(secret.id);
    setEditLabel(decrypted[secret.id]?.label || "");
    // La valeur n'est pas forcément déjà déchiffrée (révélation à part) --
    // on la redéchiffre spécifiquement à l'ouverture de l'édition, puis
    // reconstruit la liste de champs (voir vaultFieldsLib.js --
    // rétrocompatible avec un ancien secret à valeur simple).
    decryptSecret(secret, collectionKey).then((full) => setEditFields(parseFields(full.value)));
    setEditLocalisation(secret.localisation || "");
    setEditKeyword(decrypted[secret.id]?.keyword || "");
    setEditTemplateId(secret.template_id || null);
    // Retrouve les libellés obligatoires du modèle déjà associé à ce
    // secret, s'il existe encore (voir commentaire schéma
    // secrets.template_id -- référence logique, un modèle supprimé
    // depuis laisse juste ce lookup vide, jamais une exception).
    const existingTemplate = secret.template_id ? templates.find((t) => t.id === secret.template_id) : null;
    setEditRequiredLabels(existingTemplate?.required_labels || []);
    setEditReason("");
    setEditError(null);
    setHistoryId(null); // jamais édition + historique/observations/versions/archivage ouverts en même temps
    setObservationsId(null);
    setVersionsId(null);
    setArchivingId(null);
  }

  function cancelEditing() {
    setEditingId(null);
  }

  async function handleSaveEdit(secretId) {
    if (!editReason.trim()) {
      setEditError("Le motif de la modification est obligatoire.");
      return;
    }
    setEditBusy(true);
    setEditError(null);
    const res = await updateSecretWithHistory(secretId, collectionKey, login, {
      label: editLabel.trim(),
      value: serializeFields(editFields),
      keyword: editKeyword.trim(),
      localisation: editLocalisation.trim() || null,
      templateId: editTemplateId || null,
      reason: editReason.trim(),
    });
    setEditBusy(false);
    if (res.ok) {
      setEditingId(null);
      setRevealed((prev) => ({ ...prev, [secretId]: false }));
      loadSecrets();
    } else {
      setEditError(res.error);
    }
  }

  async function toggleHistory(secretId) {
    if (historyId === secretId) {
      setHistoryId(null);
      return;
    }
    setEditingId(null); // jamais édition + historique/observations/versions ouverts en même temps
    setObservationsId(null);
    setVersionsId(null);
    setArchivingId(null);
    setHistoryId(secretId);
    setHistoryEntries(await fetchSecretHistory(secretId));
  }

  async function toggleObservations(secretId) {
    if (observationsId === secretId) {
      setObservationsId(null);
      return;
    }
    setEditingId(null);
    setHistoryId(null);
    setVersionsId(null);
    setArchivingId(null);
    setObservationsId(secretId);
    setNewObservationText("");
    setObservationEntries(await fetchSecretObservations(secretId, collectionKey));
  }

  async function handleAddObservation(secretId) {
    if (!newObservationText.trim()) return;
    setObservationBusy(true);
    const res = await addSecretObservation(secretId, newObservationText.trim(), collectionKey, login);
    setObservationBusy(false);
    if (res.ok) {
      setNewObservationText("");
      setObservationEntries(await fetchSecretObservations(secretId, collectionKey));
    }
  }

  async function toggleVersions(secretId) {
    if (versionsId === secretId) {
      setVersionsId(null);
      return;
    }
    setEditingId(null);
    setHistoryId(null);
    setObservationsId(null);
    setArchivingId(null);
    setVersionsId(secretId);
    setVersionRestoreError(null);
    setVersionEntries(await fetchSecretVersions(secretId, collectionKey));
  }

  async function handleRestoreVersion(secretId, versionId) {
    setVersionRestoreBusy(versionId);
    setVersionRestoreError(null);
    const res = await restoreSecretVersion(secretId, versionId, login);
    setVersionRestoreBusy(null);
    if (res.ok) {
      setVersionsId(null);
      setRevealed((prev) => ({ ...prev, [secretId]: false }));
      loadSecrets();
    } else {
      setVersionRestoreError(res.error);
    }
  }

  function startArchiving(secretId) {
    setEditingId(null);
    setHistoryId(null);
    setObservationsId(null);
    setVersionsId(null);
    setArchivingId(secretId);
    setArchiveReason("");
  }

  async function handleConfirmArchive(secretId) {
    setArchiveBusy(true);
    const res = await archiveSecret(secretId, login, archiveReason.trim() || undefined);
    setArchiveBusy(false);
    if (res.ok) {
      setArchivingId(null);
      loadSecrets();
    }
  }

  async function toggleArchivedView() {
    if (showArchived) {
      setShowArchived(false);
      return;
    }
    setShowArchived(true);
    setRestoreError(null);
    const list = await fetchArchivedSecrets(collection.id);
    setArchivedSecrets(list);
    // Déchiffre les libellés pour affichage -- même logique que
    // loadSecrets pour les secrets actifs, juste une liste distincte.
    const decrypted = {};
    for (const s of list) {
      try {
        decrypted[s.id] = await decryptSecret(s, collectionKey);
      } catch {
        decrypted[s.id] = { label: "(déchiffrement impossible)", value: "" };
      }
    }
    setArchivedDecrypted(decrypted);
  }

  async function handleRestoreArchived(secretId) {
    setRestoreBusy(secretId);
    setRestoreError(null);
    const res = await restoreSecret(secretId, login);
    setRestoreBusy(null);
    if (res.ok) {
      setArchivedSecrets((prev) => prev.filter((s) => s.id !== secretId));
      loadSecrets();
    } else {
      setRestoreError(res.error);
    }
  }


  async function handleGrant() {
    if (!grantLogin.trim()) return;
    setGrantBusy(true);
    setGrantError(null);
    const res = await grantAccess(collection.id, grantLogin.trim(), collectionKey, login);
    setGrantBusy(false);
    if (res.ok) {
      setGrantLogin("");
      getJson(`/collections/${collection.id}/access`).then((r) => r.ok && setAccessList(r.data));
    } else {
      setGrantError(res.error);
    }
  }

  return (
    <div className="vault-collection-detail">
      <h2>📁 {collection.name}</h2>

      <div className="vault-panel">
        <div className="vault-panel-header-row">
          <h3>Secrets ({secrets.length})</h3>
          {!isReadOnly && (
            <button
              className="secondary vault-add-btn"
              onClick={() => setShowAddSecretForm((v) => !v)}
              title={showAddSecretForm ? "Annuler" : "Ajouter un secret"}
            >
              {showAddSecretForm ? "✕" : "+"}
            </button>
          )}
        </div>
        {!isReadOnly && showAddSecretForm && (
          <div className="vault-add-secret-form">
            <div className="vault-form-row">
              <input placeholder="libellé (ex. Porte principale, Bât. A)" value={newLabel} onChange={(e) => setNewLabel(e.target.value)} autoFocus />
            </div>
            <FieldsEditor
              fields={newFields}
              onChange={setNewFields}
              templates={templates}
              onUseTemplate={applyTemplateToNewFields}
              onSaveAsTemplate={(name, opts) => handleSaveAsTemplate(name, newFields, opts)}
              requiredLabels={newRequiredLabels}
              collectionName={collection.name}
            />
            <LocationPicker value={newLocalisation} onChange={setNewLocalisation} />
            <div className="vault-form-row">
              <input placeholder="🏷️ mot-clé (optionnel — visible dans la navigation d'urgence)" value={newKeyword} onChange={(e) => setNewKeyword(e.target.value)} />
              <button
                className="primary"
                onClick={handleAddSecret}
                disabled={!newLabel.trim() || !newFields.some((f) => f.content.trim())}
              >
                ➕ Ajouter
              </button>
            </div>
            {error && <p className="vault-error">{error}</p>}
          </div>
        )}
        {loading && <p className="vault-muted">Déchiffrement…</p>}
        {!loading && secrets.length === 0 && <p className="vault-muted">Aucun secret pour l'instant.</p>}
        {!loading && secrets.map((s) => (
          <div key={s.id} className="vault-secret-block">
            {editingId === s.id ? (
              <div className="vault-secret-edit-form">
                <div className="vault-form-row">
                  <input placeholder="libellé" value={editLabel} onChange={(e) => setEditLabel(e.target.value)} />
                </div>
                <FieldsEditor
                  fields={editFields}
                  onChange={setEditFields}
                  templates={templates}
                  onUseTemplate={applyTemplateToEditFields}
                  onSaveAsTemplate={(name, opts) => handleSaveAsTemplate(name, editFields, opts)}
                  requiredLabels={editRequiredLabels}
                  collectionName={collection.name}
                />
                <LocationPicker value={editLocalisation} onChange={setEditLocalisation} />
                <div className="vault-form-row">
                  <input placeholder="🏷️ mot-clé" value={editKeyword} onChange={(e) => setEditKeyword(e.target.value)} />
                </div>
                <div className="vault-form-row">
                  <input
                    placeholder="motif de la modification (obligatoire)"
                    value={editReason}
                    onChange={(e) => setEditReason(e.target.value)}
                    className="vault-edit-reason-input"
                  />
                  <button className="primary" onClick={() => handleSaveEdit(s.id)} disabled={editBusy}>
                    {editBusy ? "…" : "✓ Enregistrer"}
                  </button>
                  <button onClick={cancelEditing} disabled={editBusy}>Annuler</button>
                </div>
                {editError && <p className="vault-error">{editError}</p>}
              </div>
            ) : (
              <div className="vault-secret-row">
                <div className="vault-secret-main">
                  <span className="vault-secret-label">{decrypted[s.id]?.label || "…"}</span>
                  {s.localisation && <span className="vault-secret-loc">📍 {s.localisation}</span>}
                  {decrypted[s.id]?.keyword && <span className="vault-secret-keyword">🏷️ {decrypted[s.id].keyword}</span>}
                  {s.last_changed_by && s.last_changed_by !== s.created_by && (
                    <span
                      className="vault-secret-modified-badge"
                      title={`Modifié par ${s.last_changed_by} (créé par ${s.created_by})`}
                    >
                      ✏️ modifié par {s.last_changed_by}
                    </span>
                  )}
                </div>
                {revealed[s.id] ? (
                  <FieldsDisplay decryptedValue={decrypted[s.id]?.value} />
                ) : (
                  <span className="vault-secret-value">••••••••</span>
                )}
                <button className="secondary" onClick={() => handleReveal(s)}>
                  {revealed[s.id] ? "🙈 Cacher" : "👁️ Révéler"}
                </button>
                {!isReadOnly && (
                  <button className="secondary" onClick={() => startEditing(s)}>✏️ Modifier</button>
                )}
                <button className="secondary" onClick={() => toggleHistory(s.id)}>🕒 Historique</button>
                <button className="secondary" onClick={() => toggleObservations(s.id)}>💬 Observations</button>
                <button className="secondary" onClick={() => toggleVersions(s.id)}>⏱️ Versions</button>
                {!isReadOnly && (
                  <button className="secondary vault-archive-btn" onClick={() => startArchiving(s.id)}>🗄️ Archiver</button>
                )}
              </div>
            )}
            {archivingId === s.id && (
              <div className="vault-secret-archive-confirm">
                <p className="vault-muted">
                  Le secret sera archivé, jamais réellement supprimé — visible par tous les
                  membres de la collection, restaurable par vous (le propriétaire) à tout moment.
                </p>
                <div className="vault-form-row">
                  <input
                    placeholder="motif (optionnel, ex. équipement remplacé)"
                    value={archiveReason}
                    onChange={(e) => setArchiveReason(e.target.value)}
                  />
                  <button className="primary" onClick={() => handleConfirmArchive(s.id)} disabled={archiveBusy}>
                    {archiveBusy ? "…" : "🗄️ Confirmer l'archivage"}
                  </button>
                  <button onClick={() => setArchivingId(null)} disabled={archiveBusy}>Annuler</button>
                </div>
              </div>
            )}
            {historyId === s.id && (
              <div className="vault-secret-history">
                {historyEntries.length === 0 && <p className="vault-muted">Aucun historique.</p>}
                {historyEntries.length > 0 && (
                  <div className="vault-usage-table-scroll">
                    <table className="vault-history-table">
                      <thead>
                        <tr><th>Action</th><th>Auteur</th><th>Date</th><th>Motif</th></tr>
                      </thead>
                      <tbody>
                        {historyEntries.map((h, i) => (
                          <tr key={i}>
                            <td>{h.action === "created" ? "Création" : "Modification"}</td>
                            <td>{h.changed_by}</td>
                            <td className="vault-muted">{new Date(h.changed_at).toLocaleString("fr-FR")}</td>
                            <td className="vault-muted">{h.reason || "—"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
            {observationsId === s.id && (
              <div className="vault-secret-observations">
                {observationEntries.length === 0 && <p className="vault-muted">Aucune observation.</p>}
                <ul>
                  {observationEntries.map((o) => (
                    <li key={o.id}>
                      <span className="vault-observation-text">{o.text}</span>
                      <span className="vault-observation-meta">
                        {o.author} — {new Date(o.createdAt).toLocaleString("fr-FR")}
                      </span>
                    </li>
                  ))}
                </ul>
                {!isReadOnly && (
                <div className="vault-form-row">
                  <input
                    placeholder="nouvelle observation (ex. code changé le 12, porte grippée le matin…)"
                    value={newObservationText}
                    onChange={(e) => setNewObservationText(e.target.value)}
                    className="vault-observation-input"
                  />
                  <button className="secondary" onClick={() => handleAddObservation(s.id)} disabled={observationBusy || !newObservationText.trim()}>
                    {observationBusy ? "…" : "+ Ajouter"}
                  </button>
                </div>
                )}
              </div>
            )}
            {versionsId === s.id && (
              <div className="vault-secret-versions">
                {versionEntries.length === 0 && <p className="vault-muted">Aucune version antérieure -- jamais modifié depuis sa création.</p>}
                {versionEntries.length > 0 && s.created_by !== login && (
                  <p className="vault-muted">Seul le propriétaire ({s.created_by}) peut restaurer une version.</p>
                )}
                {versionRestoreError && <p className="vault-error">{versionRestoreError}</p>}
                {versionEntries.length > 0 && (
                  <div className="vault-usage-table-scroll">
                    <table className="vault-versions-table">
                      <thead>
                        <tr>
                          <th>Libellé</th>
                          <th>Contenu</th>
                          <th>Modifié le</th>
                          <th>Motif</th>
                          {s.created_by === login && <th></th>}
                        </tr>
                      </thead>
                      <tbody>
                        {versionEntries.map((v) => {
                          // Bug réel corrigé ici : v.value est le contenu
                          // STOCKÉ (voir vaultFieldsLib.js) -- pour un
                          // secret à plusieurs champs, c'est du JSON
                          // sérialisé, jamais destiné à s'afficher brut
                          // tel quel (c'était le cas avant ce chantier).
                          // parseFields le reconstruit correctement,
                          // rétrocompatible avec les anciennes versions
                          // à valeur simple.
                          const fields = parseFields(v.value);
                          return fields.map((f, i) => (
                            <tr key={`${v.id}-${i}`} className={i === 0 ? "vault-version-group-start" : undefined}>
                              <td>{f.label || "—"}</td>
                              <td><CopyableValue value={f.content} /></td>
                              <td className="vault-muted">
                                {i === 0 && <>{v.changedBy} — {new Date(v.changedAt).toLocaleString("fr-FR")}</>}
                              </td>
                              <td className="vault-muted">{i === 0 ? (v.reason || "—") : ""}</td>
                              {s.created_by === login && (
                                <td>
                                  {i === 0 && (
                                    <button
                                      className="secondary"
                                      onClick={() => handleRestoreVersion(s.id, v.id)}
                                      disabled={versionRestoreBusy === v.id}
                                    >
                                      {versionRestoreBusy === v.id ? "…" : "↺ Restaurer"}
                                    </button>
                                  )}
                                </td>
                              )}
                            </tr>
                          ));
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="vault-panel">
        <button type="button" className="secondary" onClick={toggleArchivedView}>
          {showArchived ? "✕ Fermer les archives" : "📦 Voir les archives"}
        </button>
        {showArchived && (
          <div className="vault-archived-list">
            {archivedSecrets.length === 0 && <p className="vault-muted">Aucun secret archivé.</p>}
            {restoreError && <p className="vault-error">{restoreError}</p>}
            {archivedSecrets.map((s) => (
              <div key={s.id} className="vault-secret-row vault-secret-row-archived">
                <div className="vault-secret-main">
                  <span className="vault-secret-label">{archivedDecrypted[s.id]?.label || "…"}</span>
                  {s.localisation && <span className="vault-secret-loc">📍 {s.localisation}</span>}
                </div>
                {s.created_by === login ? (
                  <button
                    className="secondary"
                    onClick={() => handleRestoreArchived(s.id)}
                    disabled={restoreBusy === s.id}
                  >
                    {restoreBusy === s.id ? "…" : "↺ Restaurer"}
                  </button>
                ) : (
                  <span className="vault-muted">Restaurable par {s.created_by} seulement</span>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="vault-panel">
        <h3>Accès à cette collection</h3>
        <ul className="vault-access-list">
          {accessList.map((a) => (
            <li key={a.login}>{a.login} <span className="vault-muted">(accordé par {a.granted_by})</span></li>
          ))}
        </ul>
        {!isReadOnly && (
        <>
          <div className="vault-form-row">
            <input placeholder="login de la personne" value={grantLogin} onChange={(e) => setGrantLogin(e.target.value)} />
            <button className="primary" onClick={handleGrant} disabled={grantBusy || !grantLogin.trim()}>
              {grantBusy ? "…" : "Accorder l'accès"}
            </button>
          </div>
          {grantError && <p className="vault-error">{grantError}</p>}
          <p className="vault-muted vault-hint">
            La personne doit déjà avoir créé son propre compte coffre
            (se connecter une première fois ici) avant de pouvoir recevoir un accès.
          </p>
        </>
        )}
      </div>
    </div>
  );
}

// --- Vue principale une fois déverrouillé : liste des collections ---
function VaultView({ login, privateKey, publicKeyBase64, onViewModeChange, isSystemMaster, isReadOnly }) {
  // "search" (recherche par localisation, PRIORITAIRE -- demandé
  // explicitement comme premier écran) par défaut, "collections"
  // (navigation existante par collection, préservée) en alternative.
  const [viewMode, setViewMode] = useState("search"); // "search" | "collections"
  // Notifie le parent (App) du mode actif -- uniquement pour décider
  // si <main> doit s'élargir (voir vault-main-wide, vault.css) :
  // l'écran de recherche a besoin de toute la largeur disponible,
  // contrairement aux formulaires de collections, jamais l'inverse.
  // Bug réel corrigé après retour : tout était concentré dans une
  // colonne de 720px, les 2/3 de l'écran vides, sur l'écran de
  // recherche précisément.
  useEffect(() => {
    onViewModeChange?.(viewMode);
    return () => onViewModeChange?.(null); // au démontage, plus aucun mode actif
  }, [viewMode, onViewModeChange]);

  const [revealSecret, setRevealSecret] = useState(null); // secret (avec collectionKey) en cours de révélation
  const [revealedValue, setRevealedValue] = useState(null); // {label, value} une fois déchiffré
  const [revealError, setRevealError] = useState(null);
  // Mini-tableau d'observations dans ce popup -- demandé explicitement
  // ("c'est tout l'intérêt des observations : permettre à chaque
  // visite/consultation d'ajouter des infos"), jusqu'ici disponible
  // uniquement depuis l'écran Collections. Toujours affiché ici (pas
  // de bascule masquer/montrer -- ce popup est déjà centré sur UN
  // seul secret, rien à désencombrer).
  const [revealObservations, setRevealObservations] = useState([]);
  const [revealObservationText, setRevealObservationText] = useState("");
  const [revealObservationBusy, setRevealObservationBusy] = useState(false);

  const [collections, setCollections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [newName, setNewName] = useState("");
  // Formulaire de création de collection replié par défaut -- ouvert
  // via le bouton "+" à côté de "Vos collections", demandé
  // explicitement (plutôt qu'un panneau toujours visible).
  const [showCreateCollectionForm, setShowCreateCollectionForm] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState(null);
  const [openCollection, setOpenCollection] = useState(null); // { collection, collectionKey } | null
  const [backfillBusy, setBackfillBusy] = useState(false);
  const [backfillResult, setBackfillResult] = useState(null);

  async function loadCollections() {
    setLoading(true);
    const res = await getJson(`/collections?user=${encodeURIComponent(login)}`);
    if (res.ok) setCollections(res.data);
    setLoading(false);
  }

  useEffect(() => { loadCollections(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function handleCreateCollection() {
    if (!newName.trim()) return;
    setCreating(true);
    setError(null);
    const res = await createCollection(newName.trim(), login, publicKeyBase64);
    setCreating(false);
    if (res.ok) {
      setNewName("");
      setShowCreateCollectionForm(false);
      loadCollections();
    } else {
      setError(res.error);
    }
  }

  /** Rattrapage -- voir vaultOps.js, backfillSystemMasterAccess.
   * Action de maintenance, jamais automatique : peut prendre du temps
   * (une requête par collection accessible) et n'a de sens que si un
   * compte maître_système existe déjà, jamais lancé en silence. */
  async function handleBackfillSystemMaster() {
    setBackfillBusy(true);
    setBackfillResult(null);
    const res = await backfillSystemMasterAccess(login, privateKey);
    setBackfillBusy(false);
    setBackfillResult(res);
  }

  async function handleOpen(collection) {
    try {
      const collectionKey = await unlockCollectionKey(collection.wrapped_key, privateKey);
      setOpenCollection({ collection, collectionKey });
    } catch {
      setError("Impossible de déchiffrer cette collection.");
    }
  }

  async function handleOpenSecretFromSearch(secret) {
    setRevealSecret(secret);
    setRevealedValue(null);
    setRevealError(null);
    setRevealObservations([]);
    setRevealObservationText("");
    try {
      const full = await revealSecretValue(secret);
      setRevealedValue(full);
      recordSecretAccess(secret.id); // jamais bloquant, voir vaultOps.js
    } catch {
      setRevealError("Déchiffrement impossible pour ce secret.");
    }
    // Chargement des observations indépendant de la révélation de la
    // valeur -- une éventuelle erreur de déchiffrement du mot de passe
    // ne doit jamais empêcher de consulter/ajouter des observations.
    setRevealObservations(await fetchSecretObservations(secret.id, secret.collectionKey));
  }

  async function handleAddRevealObservation() {
    if (!revealSecret || !revealObservationText.trim()) return;
    setRevealObservationBusy(true);
    const res = await addSecretObservation(revealSecret.id, revealObservationText.trim(), revealSecret.collectionKey, login);
    setRevealObservationBusy(false);
    if (res.ok) {
      setRevealObservationText("");
      setRevealObservations(await fetchSecretObservations(revealSecret.id, revealSecret.collectionKey));
    }
  }

  if (openCollection) {
    return (
      <div>
        <button className="vault-link-btn" onClick={() => setOpenCollection(null)}>← Retour aux collections</button>
        <CollectionDetail collection={openCollection.collection} collectionKey={openCollection.collectionKey} login={login} isReadOnly={isReadOnly} />
      </div>
    );
  }

  return (
    <div>
      <div className="vault-view-tabs">
        <button
          type="button"
          className={viewMode === "search" ? "active" : ""}
          onClick={() => setViewMode("search")}
        >
          🔍 Recherche
        </button>
        <button
          type="button"
          className={viewMode === "collections" ? "active" : ""}
          onClick={() => setViewMode("collections")}
        >
          📁 Collections
        </button>
        <button
          type="button"
          className={viewMode === "observations" ? "active" : ""}
          onClick={() => setViewMode("observations")}
        >
          📝 Observations
        </button>
        {isSystemMaster && (
          <button
            type="button"
            className={viewMode === "dashboard" ? "active" : ""}
            onClick={() => setViewMode("dashboard")}
            title="Vue d'ensemble à travers tout le coffre — accès permanent (maître_système)"
          >
            📊 Tableau de bord
          </button>
        )}
      </div>

      {viewMode === "search" && (
        <VaultSearchScreen
          login={login}
          privateKey={privateKey}
          publicKeyBase64={publicKeyBase64}
          isReadOnly={isReadOnly}
          onOpenSecret={handleOpenSecretFromSearch}
          onCollectionsChanged={loadCollections}
        />
      )}
      {viewMode === "observations" && (
        <ObservationsScreen login={login} privateKey={privateKey} isReadOnly={isReadOnly} />
      )}
      {viewMode === "dashboard" && isSystemMaster && (
        <DashboardScreen login={login} privateKey={privateKey} />
      )}

      {revealSecret && (
        <div className="vault-modal-overlay" onClick={() => setRevealSecret(null)}>
          <div className="vault-card vault-modal" onClick={(e) => e.stopPropagation()}>
            <h2>🔓 {revealSecret.label}</h2>
            {revealSecret.localisation && <p className="vault-muted">📍 {revealSecret.localisation}</p>}
            {revealError && <p className="vault-error">{revealError}</p>}
            {!revealedValue && !revealError && <p className="vault-muted">Déchiffrement…</p>}
            {revealedValue && (
              // FieldsDisplay -- jamais juste revealedValue.value tel
              // quel : bug réel trouvé en construisant la copie
              // partielle, une fiche à champs multiples aurait
              // affiché du JSON brut ici, jamais corrigé depuis
              // l'ajout des champs multiples (cet écran n'a jamais
              // été retouché à ce moment-là).
              <FieldsDisplay decryptedValue={revealedValue.value} />
            )}

            <div className="vault-observations-mini">
              <h3>💬 Observations</h3>
              <div className="vault-form-row">
                <input
                  placeholder="nouvelle observation (ex. code changé le 12, porte grippée le matin…)"
                  value={revealObservationText}
                  onChange={(e) => setRevealObservationText(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && handleAddRevealObservation()}
                />
                <button
                  className="secondary"
                  onClick={handleAddRevealObservation}
                  disabled={revealObservationBusy || !revealObservationText.trim()}
                >
                  {revealObservationBusy ? "…" : "+ Ajouter"}
                </button>
              </div>
              {revealObservations.length === 0 ? (
                <p className="vault-muted">Aucune observation.</p>
              ) : (
                <table className="vault-observations-table">
                  <tbody>
                    {revealObservations.map((o) => (
                      <tr key={o.id}>
                        <td>{o.text}</td>
                        <td className="vault-muted">{o.author} — {new Date(o.createdAt).toLocaleString("fr-FR")}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>

            <div className="vault-modal-actions">
              <button className="primary" onClick={() => setRevealSecret(null)}>Fermer</button>
            </div>
          </div>
        </div>
      )}

      {viewMode === "collections" && (
      <div>
      <div className="vault-panel">
        <div className="vault-panel-header-row">
          <h2>Vos collections ({collections.length})</h2>
          {!isReadOnly && (
            <button
              className="secondary vault-add-btn"
              onClick={() => setShowCreateCollectionForm((v) => !v)}
              title={showCreateCollectionForm ? "Annuler" : "Nouvelle collection"}
            >
              {showCreateCollectionForm ? "✕" : "+"}
            </button>
          )}
        </div>
        {showCreateCollectionForm && !isReadOnly && (
          <div className="vault-form-row" style={{ marginBottom: 12 }}>
            <input
              placeholder="nom (ex. Site A - contrôle accès)"
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleCreateCollection()}
              autoFocus
            />
            <button className="primary" onClick={handleCreateCollection} disabled={creating || !newName.trim()}>
              {creating ? "Création…" : "➕ Créer"}
            </button>
          </div>
        )}
        {error && <p className="vault-error">{error}</p>}
        {loading && <p className="vault-muted">Chargement…</p>}
        {!loading && collections.length === 0 && (
          <p className="vault-muted">Aucune collection accessible pour l'instant.</p>
        )}
        {!loading && collections.map((c) => (
          <button key={c.id} className="vault-collection-card" onClick={() => handleOpen(c)}>
            📁 {c.name}
          </button>
        ))}
      </div>

      {!isReadOnly && (
      <div className="vault-panel">
        <h2>Maintenance</h2>
        <p className="vault-muted">
          Accorde l'accès au maître_système (accès permanent, s'il en existe un) sur toutes
          vos collections qui ne l'ont pas encore — utile pour des collections créées avant
          qu'un compte maître_système n'existe. Sans effet si aucun n'est configuré.
        </p>
        <button className="secondary" onClick={handleBackfillSystemMaster} disabled={backfillBusy}>
          {backfillBusy ? "…" : "↻ Rattraper l'accès maître_système"}
        </button>
        {backfillResult && (
          <p className="vault-muted">
            {backfillResult.granted} octroi{backfillResult.granted > 1 ? "s" : ""} accordé{backfillResult.granted > 1 ? "s" : ""},{" "}
            {backfillResult.skipped} déjà à jour, {backfillResult.failed} échec{backfillResult.failed > 1 ? "s" : ""}.
          </p>
        )}
      </div>
      )}
      </div>
      )}
    </div>
  );
}

// --- Dialogue : changer le mot de passe maître (compte déjà déverrouillé) ---
// Pas de ressaisie du mot de passe ACTUEL demandée : privateKey est
// déjà déchiffrée en mémoire à ce stade (le coffre est déverrouillé),
// la repreuve serait redondante -- changePassword() n'a d'ailleurs
// même pas besoin de l'ancien mot de passe (voir vaultOps.js).
function ChangePasswordDialog({ login, privateKey, onClose }) {
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [done, setDone] = useState(false);

  async function handleSubmit() {
    setError(null);
    if (password.length < 12) {
      setError("Le nouveau mot de passe doit faire au moins 12 caractères.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Les deux mots de passe ne correspondent pas.");
      return;
    }
    setBusy(true);
    const result = await changePassword(login, password, privateKey);
    setBusy(false);
    if (!result.ok) {
      setError(result.error);
      return;
    }
    setDone(true);
  }

  return (
    <div className="vault-modal-overlay" onClick={onClose}>
      <div className="vault-card vault-modal" onClick={(e) => e.stopPropagation()}>
        {done ? (
          <>
            <h2>✅ Mot de passe changé</h2>
            <p className="vault-muted">
              Votre clé de récupération reste inchangée — pas besoin de la
              renoter, elle fonctionne toujours pareil si ce nouveau mot de
              passe s'oublie à son tour.
            </p>
            <button className="primary" onClick={onClose}>Fermer</button>
          </>
        ) : (
          <>
            <h2>🔑 Changer le mot de passe</h2>
            <p className="vault-muted">
              Votre clé de récupération n'est pas affectée — elle continuera
              de fonctionner avec ce nouveau mot de passe.
            </p>
            {error && <p className="vault-error">{error}</p>}
            <input
              type="password"
              placeholder="nouveau mot de passe (12 caractères min.)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
            <input
              type="password"
              placeholder="confirmer le nouveau mot de passe"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
            <div className="vault-modal-actions">
              <button onClick={onClose} disabled={busy}>Annuler</button>
              <button className="primary" onClick={handleSubmit} disabled={busy}>
                {busy ? "Changement…" : "Confirmer"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function App() {
  const auth = useAuth();
  const [theme, setThemeState] = useState(themeStore.get() || "light");
  const [accountState, setAccountState] = useState("checking"); // checking | needs-creation | locked | unlocked
  // Reflet du mode actif dans VaultView -- uniquement pour élargir
  // <main> quand l'écran de recherche est actif (voir VaultView,
  // onViewModeChange, et vault.css .vault-main-wide).
  const [vaultViewMode, setVaultViewMode] = useState(null);
  const [privateKey, setPrivateKey] = useState(null);
  const [publicKeyBase64, setPublicKeyBase64] = useState(null);
  const [isSystemMaster, setIsSystemMaster] = useState(false);
  const [isReadOnly, setIsReadOnly] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);

  const login = auth.user?.profile?.preferred_username;

  useEffect(() => {
    if (!login) return;
    themeStore.load(login);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [login]);
  useEffect(() => themeStore.onChange(setThemeState), []);
  const toggleTheme = () => themeStore.set(theme === "dark" ? "light" : "dark", login);

  useEffect(() => {
    if (!login) return;
    checkAccountExists(login).then((exists) => {
      setAccountState(exists ? "locked" : "needs-creation");
    });
  }, [login]);

  // Nécessaire pour créer une NOUVELLE collection (s'auto-envelopper
  // avec sa propre clé publique) -- récupérée une fois déverrouillé,
  // jamais avant (pas besoin tant que le coffre n'est pas ouvert).
  // Même appel utilisé pour connaître son propre rôle is_system_master
  // (conditionne l'onglet Tableau de bord, voir plus bas) -- jamais un
  // deuxième aller-retour réseau pour ça.
  useEffect(() => {
    if (accountState !== "unlocked" || !login) return;
    getJson(`/users/${encodeURIComponent(login)}`).then((r) => {
      if (r.ok) {
        setPublicKeyBase64(r.data.public_key);
        setIsSystemMaster(!!r.data.is_system_master);
        setIsReadOnly(!!r.data.is_read_only);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [accountState, login]);

  function handleLock() {
    // Efface la clé privée de la mémoire -- redemande le mot de passe
    // maître pour tout accès ultérieur, jusqu'à la fin de cette page.
    setPrivateKey(null);
    setPublicKeyBase64(null);
    setAccountState("locked");
  }

  if (auth.isLoading) {
    return (
      <div className="vault-shell vault-center">
        <p className="vault-muted">Connexion en cours…</p>
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="vault-shell vault-center">
        <div className="vault-card">
          <h1>🔐 Coffre-fort</h1>
          <p className="vault-muted">Connexion via l'annuaire de l'entreprise (Keycloak / LDAP).</p>
          <button className="primary" onClick={() => auth.signinRedirect()}>Se connecter</button>
        </div>
      </div>
    );
  }

  return (
    <div className="vault-shell">
      <header className="vault-header">
        <a href="/" className="vault-hub-link" title="Retour au hub">🏠 Hub</a>
        <a href="/?view=settings" className="vault-hub-link" title="Paramètres (page dédiée dans le hub)">⚙️ Paramètres</a>
        <button
          className="vault-hub-link"
          onClick={toggleTheme}
          title={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}
        >
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
        <h1>🔐 Coffre-fort</h1>
        <div className="vault-header-right">
          <span>👤 {login}</span>
          {accountState === "unlocked" && (
            <>
              <button onClick={() => setShowChangePassword(true)} title="Changer le mot de passe maître">
                🔑 Mot de passe
              </button>
              <button onClick={handleLock} title="Efface la clé de la mémoire — redemande le mot de passe">🔒 Verrouiller</button>
            </>
          )}
          <button onClick={() => auth.signoutRedirect()}>Se déconnecter</button>
        </div>
      </header>
      {showChangePassword && (
        <ChangePasswordDialog
          login={login}
          privateKey={privateKey}
          onClose={() => setShowChangePassword(false)}
        />
      )}
      <main className={`vault-main${vaultViewMode === "search" || vaultViewMode === "dashboard" || vaultViewMode === "collections" || vaultViewMode === "observations" ? " vault-main-wide" : ""}`}>
        {accountState === "checking" && <p className="vault-muted">Vérification du compte…</p>}
        {accountState === "needs-creation" && (
          <CreateAccountScreen
            login={login}
            onCreated={(pk) => { setPrivateKey(pk); setAccountState("unlocked"); }}
          />
        )}
        {accountState === "locked" && (
          <UnlockScreen
            login={login}
            onUnlocked={(pk) => { setPrivateKey(pk); setAccountState("unlocked"); }}
          />
        )}
        {accountState === "unlocked" && publicKeyBase64 && (
          <VaultView
            login={login}
            privateKey={privateKey}
            publicKeyBase64={publicKeyBase64}
            onViewModeChange={setVaultViewMode}
            isSystemMaster={isSystemMaster}
            isReadOnly={isReadOnly}
          />
        )}
        {accountState === "unlocked" && !publicKeyBase64 && <p className="vault-muted">Chargement…</p>}
      </main>
      <div className="version-badge" title={`hash contenu : ${versionInfo.content_hash} · hash git : ${versionInfo.git_hash} · dernière vérification : ${versionInfo.last_checked_at}`}>
        #{versionInfo.delivery_number || "?"}
      </div>
    </div>
  );
}
