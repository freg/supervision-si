import React from "react";
import { ICONS, resolveIcon, toneVar } from "./hubIconSet.js";

/**
 * Pastille d'icône du hub : rend le pictogramme SVG (jeu Lucide, voir hubIconSet.js) sur un disque coloré par le thème,
 * ou, pour un emoji sans équivalent, le texte tel quel. Charte (icons.js, règle 2) : la pastille porte une couleur d'IDENTITÉ
 * (--hub-icon-teal/orange/purple/brick/green/slate, hub.css, deux thèmes) sauf pour les icônes d'état (--ok/--warning/--danger) ;
 * le trait est --hub-icon-fg. Aucune couleur en dur.
 */
export default function HubIcon({ icon, size = 18, title, className = "" }) {
  const name = resolveIcon(icon);
  if (!name) return icon ? <span className={`hub-icon hub-icon-text ${className}`}>{icon}</span> : null;
  const { tone, body } = ICONS[name];
  return (
    <svg className={`hub-icon hub-icon-${tone} ${className}`} width={size} height={size} viewBox="0 0 48 48" role="img" aria-label={title || name}>
      {title && <title>{title}</title>}
      <circle cx="24" cy="24" r="24" fill={toneVar(tone)} />
      <g transform="translate(12 12)" fill="none" stroke="var(--hub-icon-fg)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" dangerouslySetInnerHTML={{ __html: body }} />
    </svg>
  );
}
