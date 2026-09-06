import { useState } from "react";
import { splitIntoWords } from "./vaultFieldsLib.js";

/**
 * Affiche une valeur déchiffrée avec :
 * - texte NATIVEMENT sélectionnable (curseur début/fin, double-clic
 *   sur un mot) -- aucun code nécessaire pour ça, juste ne JAMAIS
 *   bloquer la sélection native (pas de user-select:none, jamais un
 *   <input disabled> qui se comporte différemment).
 * - un bouton de copie qui apparaît au SURVOL (voir vault.css,
 *   .vault-copyable-value:hover), copie la valeur ENTIÈRE en un clic.
 * - si la valeur contient PLUSIEURS mots : une liste de mots
 *   cliquables juste en dessous, chacun copiable individuellement --
 *   utile pour une phrase de passe ou un identifiant à communiquer
 *   mot par mot (au téléphone, par exemple).
 *
 * navigator.clipboard peut échouer (contexte non sécurisé, permission
 * refusée) -- JAMAIS bloquant : la sélection manuelle reste toujours
 * possible même si le bouton échoue silencieusement.
 */
export default function CopyableValue({ value }) {
  const [copied, setCopied] = useState(false);
  const [copiedWordIndex, setCopiedWordIndex] = useState(null);
  const words = splitIntoWords(value);

  async function copy(text, onDone) {
    try {
      await navigator.clipboard.writeText(text);
      onDone(true);
      setTimeout(() => onDone(false), 1200);
    } catch {
      // volontairement silencieux, voir commentaire ci-dessus
    }
  }

  return (
    <div className="vault-copyable-value">
      <div className="vault-copyable-value-row">
        <span className="vault-secret-value vault-selectable">{value}</span>
        <button
          type="button"
          className="vault-copy-btn"
          onClick={() => copy(value, setCopied)}
          title="Copier la valeur entière"
        >
          {copied ? "✓" : "📋"}
        </button>
      </div>
      {words.length > 1 && (
        <div className="vault-word-list">
          {words.map((w, i) => (
            <button
              type="button"
              key={i}
              className="vault-word-chip"
              onClick={() => copy(w, (v) => setCopiedWordIndex(v ? i : null))}
              title={`Copier "${w}" seulement`}
            >
              {w}{copiedWordIndex === i && " ✓"}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
