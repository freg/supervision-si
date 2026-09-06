// Validation de FORME uniquement (pas un validateur RFC 7946 complet) —
// suffisant pour éviter le crash de react-leaflet/Leaflet quand une
// source sélectionnée dans le panneau de gauche n'est pas un GeoJSON
// du tout (ex: un arbre Zenoss/IPAM figé, un JSON de tickets...).
// Leaflet lève une exception SYNCHRONE non rattrapable par React dans
// ce cas ("Invalid GeoJSON object"), d'où la vérification en amont,
// avant même de monter le composant <GeoJSON>.

const VALID_TOP_LEVEL_TYPES = new Set([
  "FeatureCollection",
  "Feature",
  "GeometryCollection",
  "Point",
  "LineString",
  "Polygon",
  "MultiPoint",
  "MultiLineString",
  "MultiPolygon",
]);

/** true si `data` a la forme minimale d'un objet GeoJSON valide — un
 * `type` reconnu, et pour FeatureCollection/GeometryCollection, un
 * tableau (même vide) au bon endroit. Ne vérifie pas la validité des
 * géométries elles-mêmes (coordonnées, anneaux fermés...) : c'est le
 * rôle de Leaflet, protégé séparément par un ErrorBoundary. */
export function isValidGeoJson(data) {
  if (!data || typeof data !== "object" || Array.isArray(data)) return false;
  if (!VALID_TOP_LEVEL_TYPES.has(data.type)) return false;
  if (data.type === "FeatureCollection") return Array.isArray(data.features);
  if (data.type === "GeometryCollection") return Array.isArray(data.geometries);
  return true;
}
