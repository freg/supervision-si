import { useEffect, useState } from "react";
import { createLocalThemeStore } from "../preferences.js";
import versionInfo from "../VERSION.json";

// Une seule instance pour toute la durée de vie de l'appli -- mode
// LOCAL (pas de compte connu ici, décidé avec la personne), voir
// shared/preferences.js.
const themeStore = createLocalThemeStore();

const MODULES = [
  { id: "supervision", label: "Supervision SI" },
  { id: "pixel-grid", label: "Pixel Grid" },
  { id: "geolocation", label: "Géolocalisation" },
  { id: "tickets", label: "Tickets" },
  { id: "ipam", label: "IPAM" },
  { id: "optick", label: "Optick" },
  { id: "tts-gu", label: "TTS-GU" },
  { id: "zenoss", label: "Zenoss" },
  { id: "cacti", label: "Cacti" },
  { id: "owncloud", label: "OwnCloud" },
  { id: "fusion", label: "Fusion IP/MAC" },
  { id: "logs", label: "Logs" },
  { id: "search", label: "Recherche" },
  { id: "geo-import", label: "Dépôt shapefiles" },
];

export default function TopNav({ activeModule, onSelectModule }) {
  const [visible, setVisible] = useState(false);
  const [theme, setThemeState] = useState(themeStore.get() || "dark");
  useEffect(() => themeStore.onChange(setThemeState), []);
  const toggleTheme = () => themeStore.set(theme === "dark" ? "light" : "dark");

  return (
    <>
      {/* Toujours visible, indépendant du survol qui révèle le reste de
          la nav (celle-ci gagne de la place pour la carte en restant
          masquée par défaut — mais ça enterrait complètement ce lien
          retour si on le laissait dedans, rencontré en conditions
          réelles : jamais repéré tant qu'il fallait d'abord survoler
          la bande tout en haut pour même le voir apparaître). Même
          raisonnement pour le bouton de thème -- ajouté juste à côté. */}
      {/* Bug réel signalé (capture d'écran) : 🏠 Hub et ⚙️ Paramètres
          partageaient jusqu'ici EXACTEMENT la même classe
          (top-nav-hub-link-fixed), donc la même position fixe --
          littéralement superposés au même endroit, débordant à leur
          tour sur le bouton de thème et le libellé de l'application.
          Corrigé : les trois regroupés dans un conteneur flexible
          commun (top-nav-fixed-controls) -- espacement naturel entre
          eux, jamais besoin de deviner des décalages en pixels fixes
          pour des textes de longueurs variables. */}
      <div className="top-nav-fixed-controls">
        <a href="/" className="top-nav-hub-link-fixed" title="Retour au hub">🏠 Hub</a>
        <a href="/?view=settings" className="top-nav-hub-link-fixed" title="Paramètres (page dédiée dans le hub)">⚙️ Paramètres</a>
        <button
          className="top-nav-theme-toggle-fixed"
          onClick={toggleTheme}
          title={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}
        >
          {theme === "dark" ? "☀️" : "🌙"}
        </button>
      </div>
      <div className="version-badge" title={`hash contenu : ${versionInfo.content_hash} · hash git : ${versionInfo.git_hash} · dernière vérification : ${versionInfo.last_checked_at}`}>
        #{versionInfo.delivery_number || "?"}
      </div>

      {/* Fine bande invisible tout en haut : suffit à déclencher l'apparition */}
      <div className="top-nav-trigger" onMouseEnter={() => setVisible(true)} />

      <nav
        className={`top-nav ${visible ? "visible" : ""}`}
        onMouseEnter={() => setVisible(true)}
        onMouseLeave={() => setVisible(false)}
      >
        {MODULES.map((m) => (
          <button
            key={m.id}
            className={`top-nav-btn ${activeModule === m.id ? "active" : ""}`}
            onClick={() => onSelectModule(m.id)}
          >
            {m.label}
          </button>
        ))}
      </nav>
    </>
  );
}
