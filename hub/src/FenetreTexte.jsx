// #923 : règle d'ergonomie -- une info-bulle IMPORTANTE (erreur, trace, motif de refus, détail d'un état) a toujours
// son équivalent : un mini bouton, coloré selon l'urgence, visible sur la ligne survolée (toujours visible sur écran
// tactile), qui ouvre une fenêtre DÉFILANTE dont le texte se sélectionne et se COPIE. Échap ou clic hors de la
// fenêtre la ferment.
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

/** Urgences : critique (rouge), alerte (orange), info (couleur d'accent). */
export const URGENCES = ["critique", "alerte", "info"];

export function FenetreTexte({ titre, texte, onFermer }) {
  const [etat, setEtat] = useState("");
  useEffect(() => {
    const touche = (e) => { if (e.key === "Escape") onFermer(); };
    window.addEventListener("keydown", touche);
    return () => window.removeEventListener("keydown", touche);
  }, [onFermer]);
  const copier = async () => {
    try { await navigator.clipboard.writeText(texte || ""); setEtat("copié"); }
    catch { setEtat("copie refusée par le navigateur : sélectionner le texte puis Ctrl+C"); }
  };
  const fenetre = (
    <div className="ft-voile" role="presentation" onClick={(e) => { e.stopPropagation(); onFermer(); }}>
      <div className="ft-fenetre" role="dialog" aria-modal="true" aria-label={titre} onClick={(e) => e.stopPropagation()}>
        <div className="ft-tete">
          <b>{titre}</b>
          <span style={{ flex: 1 }} />
          {etat && <span className="infra-muted">{etat}</span>}
          <button type="button" className="secondary" onClick={copier}>Copier</button>
          <button type="button" className="secondary" onClick={onFermer} aria-label="fermer">✕</button>
        </div>
        <pre className="ft-texte" tabIndex={0}>{texte}</pre>
      </div>
    </div>
  );
  return typeof document !== "undefined" ? createPortal(fenetre, document.body) : fenetre;
}

/** Mini bouton qui ouvre le texte complet. `urgence` : critique | alerte | info. Rien si le texte est vide. */
export default function BoutonDetail({ texte, titre = "Détail", urgence = "info", libelle }) {
  const [ouvert, setOuvert] = useState(false);
  if (!texte) return null;
  const u = URGENCES.includes(urgence) ? urgence : "info";
  return (
    <>
      <button type="button" className={`ft-mini ${u}`} title={`${titre} : ouvrir en grand (copiable)`} aria-label={`${titre} : ouvrir`}
        onClick={(e) => { e.stopPropagation(); setOuvert(true); }}>{libelle || (u === "info" ? "i" : "!")}</button>
      {ouvert && <FenetreTexte titre={titre} texte={texte} onFermer={() => setOuvert(false)} />}
    </>
  );
}
