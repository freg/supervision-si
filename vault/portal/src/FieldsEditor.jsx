import { useState } from "react";
import { loginPasswordPreset, defaultRequiredLabels } from "./vaultFieldsLib.js";

// Éditeur de la liste de champs {label, content} d'un secret --
// utilisé pour la création ET l'édition (CollectionDetail), ainsi que
// pour la création rapide depuis l'écran de recherche
// (VaultSearchScreen). Extrait dans son propre fichier (auparavant
// défini directement dans App.jsx) pour permettre cette réutilisation
// sans créer d'import circulaire entre les deux écrans.
//
// `requiredLabels` (optionnel) : libellés marqués obligatoires par le
// format (modèle) actuellement appliqué -- backlog coffre-fort #2,
// affiche un marqueur "*" à côté du champ concerné, INDICATIF
// seulement (jamais bloquant, décidé explicitement avec la personne).
// `collectionName` (optionnel) : si fourni, propose un choix de
// portée (cette collection / globale) quand on enregistre un nouveau
// format depuis "💾 Enregistrer comme modèle" -- absent, le nouveau
// modèle reste global (comportement historique inchangé).
export default function FieldsEditor({
  fields, onChange, templates = [], onUseTemplate, onSaveAsTemplate,
  requiredLabels = [], collectionName,
}) {
  const [savingAsTemplate, setSavingAsTemplate] = useState(false);
  const [templateName, setTemplateName] = useState("");
  // Set de libellés (normalisés casse/espaces) cochés "obligatoire"
  // pour le NOUVEAU format en cours de définition -- distinct de
  // requiredLabels (prop, format déjà appliqué en lecture).
  const [templateRequired, setTemplateRequired] = useState(new Set());
  const [templateScope, setTemplateScope] = useState(collectionName ? "collection" : "global");

  const requiredLabelSet = new Set((requiredLabels || []).map((l) => (l || "").trim().toLowerCase()));
  const normalizedLabel = (label) => (label || "").trim().toLowerCase();

  function updateField(index, key, value) {
    onChange(fields.map((f, i) => (i === index ? { ...f, [key]: value } : f)));
  }
  function removeField(index) {
    if (fields.length <= 1) return; // toujours au moins un champ
    onChange(fields.filter((_, i) => i !== index));
  }

  function startSavingAsTemplate() {
    // Pré-coche login/mot de passe par défaut -- demandé explicitement
    // ("login/password obligatoires par défaut"), rien d'autre.
    setTemplateRequired(new Set(defaultRequiredLabels(fields).map(normalizedLabel)));
    setTemplateScope(collectionName ? "collection" : "global");
    setSavingAsTemplate(true);
  }

  function toggleTemplateRequired(label) {
    const key = normalizedLabel(label);
    if (!key) return; // un champ sans libellé n'a pas d'identité stable à marquer obligatoire
    setTemplateRequired((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key); else next.add(key);
      return next;
    });
  }

  function confirmSaveAsTemplate() {
    if (!templateName.trim()) return;
    // required_labels transmis en LIBELLÉS bruts (pas normalisés) --
    // c'est ce que le serveur compare à field_labels tel quel (voir
    // vault-api, create_template : filtré à l'intersection).
    const requiredForNewTemplate = fields
      .map((f) => (f.label || "").trim())
      .filter((label) => label && templateRequired.has(normalizedLabel(label)));
    onSaveAsTemplate(templateName.trim(), { requiredLabels: requiredForNewTemplate, scope: templateScope });
    setTemplateName("");
    setSavingAsTemplate(false);
  }

  return (
    <div className="vault-fields-editor">
      {templates.length > 0 && onUseTemplate && (
        <select
          className="vault-template-select"
          value=""
          onChange={(e) => { if (e.target.value) onUseTemplate(e.target.value); }}
        >
          <option value="">Utiliser un modèle…</option>
          {templates.map((t) => (
            <option key={t.id} value={t.id}>{t.name} ({t.field_labels.join(", ")})</option>
          ))}
        </select>
      )}

      {fields.map((f, i) => (
        <div className="vault-form-row vault-field-row" key={i}>
          <input
            placeholder="libellé du champ (optionnel si un seul champ)"
            value={f.label}
            onChange={(e) => updateField(i, "label", e.target.value)}
            className="vault-field-label-input"
          />
          <input
            placeholder="contenu"
            value={f.content}
            onChange={(e) => updateField(i, "content", e.target.value)}
            className="vault-field-content-input"
          />
          {savingAsTemplate ? (
            <label
              className="vault-field-required-toggle"
              title="Obligatoire pour ce format -- indicatif seulement, jamais bloquant à l'enregistrement d'un secret"
            >
              <input
                type="checkbox"
                checked={templateRequired.has(normalizedLabel(f.label))}
                onChange={() => toggleTemplateRequired(f.label)}
                disabled={!f.label.trim()}
              />
              obligatoire
            </label>
          ) : (
            requiredLabelSet.has(normalizedLabel(f.label)) && (
              <span
                className="vault-field-required-marker"
                title="Champ obligatoire selon le format de cette collection (indicatif, jamais bloquant)"
              >
                *
              </span>
            )
          )}
          {fields.length > 1 && (
            <button type="button" className="vault-field-remove" onClick={() => removeField(i)} title="Retirer ce champ">✕</button>
          )}
        </div>
      ))}

      <div className="vault-fields-actions">
        <button type="button" className="secondary" onClick={() => onChange([...fields, { label: "", content: "" }])}>
          + Ajouter un champ
        </button>
        <button type="button" className="secondary" onClick={() => onChange(loginPasswordPreset())}>
          🔑 Identifiants (login/mot de passe)
        </button>
        {onSaveAsTemplate && !savingAsTemplate && (
          <button type="button" className="secondary" onClick={startSavingAsTemplate}>
            💾 Enregistrer comme modèle
          </button>
        )}
      </div>
      {savingAsTemplate && (
        <div className="vault-save-template-panel">
          <div className="vault-form-row">
            <input
              placeholder="nom du modèle (ex. Carte SIM)"
              value={templateName}
              onChange={(e) => setTemplateName(e.target.value)}
              className="vault-template-name-input"
              autoFocus
            />
          </div>
          {collectionName && (
            <div className="vault-template-scope-choice">
              <label>
                <input
                  type="radio"
                  name="vault-template-scope"
                  checked={templateScope === "collection"}
                  onChange={() => setTemplateScope("collection")}
                />
                📁 {collectionName} uniquement
              </label>
              <label>
                <input
                  type="radio"
                  name="vault-template-scope"
                  checked={templateScope === "global"}
                  onChange={() => setTemplateScope("global")}
                />
                🌐 Toutes les collections
              </label>
            </div>
          )}
          <p className="vault-muted vault-template-required-hint">
            Cochez "obligatoire" sur les champs ci-dessus pour ce format — indicatif seulement, jamais bloquant à l'enregistrement d'un secret.
          </p>
          <div className="vault-form-row">
            <button type="button" className="primary" onClick={confirmSaveAsTemplate} disabled={!templateName.trim()}>✓ Enregistrer</button>
            <button type="button" onClick={() => setSavingAsTemplate(false)}>Annuler</button>
          </div>
        </div>
      )}
    </div>
  );
}
