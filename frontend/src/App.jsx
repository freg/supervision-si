import { useState } from "react";
import TopNav from "./components/TopNav.jsx";
import LogFooter from "./components/LogFooter.jsx";
import SupervisionApp from "./apps/SupervisionApp.jsx";
import PixelGridApp from "./apps/PixelGridApp.jsx";
import GeolocationApp from "./apps/GeolocationApp.jsx";
import TicketsApp from "./apps/TicketsApp.jsx";
import IpamApp from "./apps/IpamApp.jsx";
import OptickApp from "./apps/OptickApp.jsx";
import TtsguApp from "./apps/TtsguApp.jsx";
import ZenossApp from "./apps/ZenossApp.jsx";
import CactiApp from "./apps/CactiApp.jsx";
import OwncloudApp from "./apps/OwncloudApp.jsx";
import FusionApp from "./apps/FusionApp.jsx";
import LogsApp from "./apps/LogsApp.jsx";
import SearchApp from "./apps/SearchApp.jsx";
import GeoImportApp from "./apps/GeoImportApp.jsx";

export default function App() {
  const [activeModule, setActiveModule] = useState("supervision");
  // Requête de recentrage carte en attente — posée par un module tiers
  // (ex: bouton "voir sur la carte" de Fusion IP/MAC), consommée par
  // SupervisionApp/MapPanel au montage suivant. null = rien en attente.
  const [mapFocusRequest, setMapFocusRequest] = useState(null);
  // Marqueurs à afficher sur la carte — posés par un module tiers (ex:
  // "voir sur la carte" des géolocalisations), persiste tant qu'un
  // autre module ne les remplace pas (contrairement à mapFocusRequest,
  // consommé une fois -- ceux-ci doivent RESTER affichés).
  const [mapMarkers, setMapMarkers] = useState(null);

  function goToMap(focusRequest) {
    setMapFocusRequest(focusRequest);
    setActiveModule("supervision");
  }

  function showMarkersOnMap(markers) {
    setMapMarkers(markers);
    if (markers.length > 0) {
      // Recentrage sur le premier point -- FitToMarkers (MapPanel)
      // prendra le relais pour cadrer TOUS les points dès que la carte
      // est montée, ce recentrage n'est qu'un filet de sécurité pour
      // le tout premier rendu.
      setMapFocusRequest({ latitude: markers[0].latitude, longitude: markers[0].longitude, zoom: 10 });
    }
    setActiveModule("supervision");
  }

  return (
    <div className="root-shell">
      <TopNav activeModule={activeModule} onSelectModule={setActiveModule} />
      {activeModule === "supervision" && (
        <SupervisionApp
          onNavigate={setActiveModule}
          mapFocusRequest={mapFocusRequest}
          onMapFocusConsumed={() => setMapFocusRequest(null)}
          mapMarkers={mapMarkers}
        />
      )}
      {activeModule === "pixel-grid" && <PixelGridApp />}
      {activeModule === "geolocation" && <GeolocationApp onShowOnMap={showMarkersOnMap} />}
      {activeModule === "tickets" && <TicketsApp />}
      {activeModule === "ipam" && <IpamApp />}
      {activeModule === "optick" && <OptickApp />}
      {activeModule === "tts-gu" && <TtsguApp />}
      {activeModule === "zenoss" && <ZenossApp />}
      {activeModule === "cacti" && <CactiApp />}
      {activeModule === "owncloud" && <OwncloudApp />}
      {activeModule === "fusion" && <FusionApp onGoToMap={goToMap} />}
      {activeModule === "logs" && <LogsApp />}
      {activeModule === "search" && <SearchApp />}
      {activeModule === "geo-import" && <GeoImportApp />}
      <LogFooter onOpenLogs={() => setActiveModule("logs")} />
    </div>
  );
}
