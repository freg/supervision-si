import React from "react";
import { getStepIcon } from "./icons.js";

// Rendu des icônes de la charte (icons.js) -- livraison #410.
// Deux composants pour deux contextes : HTML (boutons, titres) et SVG
// (nœuds du graphique du cycle agile). Le choix du jeu est fait par
// l'appelant ; ici on ne fait que dessiner.

// Icône en contexte HTML. `color` s'applique aux symboles et aux tracés
// (currentColor) ; les emoji gardent leurs couleurs propres.
export function StepIcon({ set, step, size = 18, color, className = "", title }) {
  const icon = getStepIcon(set, step);
  if (icon.kind === "svg") {
    return (
      <svg
        className={`hub-icon hub-icon-line ${className}`}
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ color }}
        aria-hidden={title ? undefined : true}
        role={title ? "img" : undefined}
      >
        {title && <title>{title}</title>}
        {icon.value.map((d, i) => <path key={i} d={d} />)}
      </svg>
    );
  }
  return (
    <span
      className={`hub-icon hub-icon-${icon.kind} ${className}`}
      style={{ fontSize: size, color: icon.kind === "glyph" ? color : undefined }}
      title={title}
      aria-hidden={title ? undefined : true}
    >
      {icon.value}
    </span>
  );
}

// Icône en contexte SVG, centrée sur (x, y). Les tracés sont mis à
// l'échelle depuis leur viewBox 24×24 ; les textes utilisent l'ancrage
// central. `color` : couleur de l'étape (symboles et tracés seulement).
export function SvgStepIcon({ set, step, x, y, size = 22, color, className = "" }) {
  const icon = getStepIcon(set, step);
  if (icon.kind === "svg") {
    const k = size / 24;
    return (
      <g
        className={`nc-graph-node-icon-line ${className}`}
        transform={`translate(${x - size / 2} ${y - size / 2}) scale(${k})`}
        fill="none"
        stroke="currentColor"
        strokeWidth={2}
        strokeLinecap="round"
        strokeLinejoin="round"
        style={{ color }}
        pointerEvents="none"
      >
        {icon.value.map((d, i) => <path key={i} d={d} />)}
      </g>
    );
  }
  return (
    <text
      x={x}
      y={y}
      className={`nc-graph-node-icon ${className}`}
      style={{ fontSize: icon.kind === "glyph" ? size * 1.2 : size, fill: icon.kind === "glyph" ? color : undefined }}
    >
      {icon.value}
    </text>
  );
}
