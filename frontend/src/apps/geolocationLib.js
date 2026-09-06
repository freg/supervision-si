// Logique pure du module Géolocalisation (pixel-grid) — aucune
// dépendance à import.meta.env ici, pour rester testable via un
// simple script Node (même convention que zenossLib.js/ipamLib.js).

/** Construit l'URL d'un service cartographique externe pour une
 * localisation donnée, à partir d'un gabarit contenant "{q}". */
export function buildExternalMapUrl(template, query) {
  return template.replaceAll("{q}", encodeURIComponent(query || ""));
}
