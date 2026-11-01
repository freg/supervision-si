// Agents hôtes en mode AUTONOME (livraison #517) : la même tuile que le hub
// (hub/src/SiAgentView.jsx, importée telle quelle -- jamais une copie),
// servie en statique par nginx, sans Keycloak : l'authentification est
// locale (auth basique nginx, mode dégradé), le thème est celui du
// navigateur (bascule en haut à droite, mémorisée en localStorage).
import React, { useState } from "react";
import { createRoot } from "react-dom/client";
import "@hub/theme.css";
import "@hub/hub.css";
import SiAgentView from "@hub/SiAgentView.jsx";

function readTheme() {
  try { return localStorage.getItem("si-agent-standalone.theme") || "dark"; } catch { return "dark"; }
}

function Standalone() {
  const [theme, setTheme] = useState(readTheme);
  document.documentElement.dataset.theme = theme;
  const toggle = () => {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    try { localStorage.setItem("si-agent-standalone.theme", next); } catch { /* ignoré */ }
  };
  return (
    <div className="hub-standalone">
      <header className="hub-header">
        <h1>Agents hôtes <span className="muted">— mode autonome, sans hub</span></h1>
        <div className="hub-user">
          <span className="muted">authentification locale</span>
          <button onClick={toggle} title={theme === "dark" ? "Passer au thème clair" : "Passer au thème sombre"}>{theme === "dark" ? "☀️" : "🌙"}</button>
          <a href="/agents/logout" title="Le navigateur oublie l'identifiant à la fermeture ; ce lien force une nouvelle demande">Se déconnecter</a>
        </div>
      </header>
      <SiAgentView onBack={() => window.location.reload()} siAgentApiBase="/api/si-agent" />
    </div>
  );
}

createRoot(document.getElementById("root")).render(<Standalone />);
