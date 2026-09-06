import { Component } from "react";

/**
 * Filet de sécurité générique — capture toute erreur de rendu/effet
 * dans le sous-arbre (ex: Leaflet qui lève sur une géométrie malformée
 * passée la vérification de forme en amont) sans faire disparaître le
 * reste de l'application. Réutilisable, aucune connaissance métier.
 *
 * Ne remplace PAS isValidGeoJson (lib/geojson.js) : celle-ci évite
 * l'erreur la plus fréquente et la plus prévisible (source pas du
 * tout GeoJSON) avant même de monter <GeoJSON> ; ce composant reste
 * un filet pour tout le reste (géométrie individuellement malformée,
 * bug futur non anticipé...).
 */
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props);
    this.state = { hasError: false };
  }

  static getDerivedStateFromError() {
    return { hasError: true };
  }

  componentDidCatch(error, info) {
    // eslint-disable-next-line no-console
    console.error("ErrorBoundary a intercepté une erreur :", error, info);
  }

  componentDidUpdate(prevProps) {
    // Si la clé de "reset" change (ex: la source sélectionnée change),
    // on retente un rendu normal plutôt que de rester bloqué sur le
    // fallback pour toujours.
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false });
    }
  }

  render() {
    if (this.state.hasError) {
      return this.props.fallback || <p className="zenoss-error">Affichage indisponible pour cet élément.</p>;
    }
    return this.props.children;
  }
}
