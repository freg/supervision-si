import { useState } from "react";
import { ingestSource } from "../api.js";
import { buildSnapshotSourceName } from "../lib/treeFreeze.js";

/**
 * Bouton générique "Figer cette vue comme source" — réutilisé par les
 * 5 modules de bases en lecture seule. Réutilise le mécanisme
 * d'injection JSON déjà existant (`ingestSource`, le même que le
 * bouton "➕ Injecter" du panneau de gauche) : la source figée
 * bénéficie immédiatement de tout ce qui existe déjà pour les sources
 * JSON (sélection, corbeille, arbre JSON, téléchargement, suppression
 * douce), sans code supplémentaire, et persiste après rechargement.
 *
 * Toujours une PHOTO FIGÉE à l'instant du clic, jamais une vue vivante
 * qui se remettrait à jour — c'est le choix retenu pour l'ensemble du
 * projet (voir ipam/README.md).
 *
 * Props :
 *  - prefix : préfixe du nom de source (ex. "ipam", "optick")
 *  - rootName : nom de la racine actuellement consultée (contexte du nom)
 *  - frozenData : JSON déjà réduit à figer, ou null/undefined si rien
 *    d'utile à figer sous les filtres actifs (désactive le bouton)
 */
export default function FreezeSnapshotButton({ prefix, rootName, frozenData }) {
  const [status, setStatus] = useState(null); // null | "saving" | {ok,name?,error?}

  async function handleClick() {
    if (!frozenData) return;
    setStatus("saving");
    const name = buildSnapshotSourceName(prefix, rootName || prefix);
    const result = await ingestSource(name, frozenData);
    setStatus(result.ok ? { ok: true, name } : { ok: false, error: result.error });
    setTimeout(() => setStatus(null), 5000);
  }

  return (
    <div className="freeze-row">
      <button
        className="freeze-btn"
        onClick={handleClick}
        disabled={!frozenData || status === "saving"}
        title="Enregistre la vue actuelle (filtres compris) comme nouvelle source JSON figée, visible dans l'onglet Supervision"
      >
        📸 {status === "saving" ? "Capture…" : "Figer cette vue comme source"}
      </button>
      {status?.ok && <span className="freeze-status ok">✓ Figée sous « {status.name} »</span>}
      {status?.ok === false && <span className="freeze-status error">⚠️ {status.error}</span>}
    </div>
  );
}
